"""Nhận diện vật thể trên ảnh camera bằng model 2D có sẵn (việc C3, lớp 2 của Box Verifier).

Hai model, chọn bằng `camera.model` của guideline:

- `maskrcnn`: Mask R-CNN ResNet-50 FPN v2 của torchvision, huấn luyện trên COCO. Chỉ có 4 nhóm vật dùng được (người, xe
  hai bánh, xe, động vật); COCO không có cọc tiêu, rào chắn.
- `gdino-sam2`: **Grounding DINO** (IDEA Research, Apache 2.0) tìm vật theo từ khóa (`PROMPTS`), rồi **SAM 2.1** (Meta,
  Apache 2.0) cắt mặt nạ từ từng khung. Nhận diện theo từ khóa nên có thêm cọc tiêu, rào chắn. Cần thêm `transformers`;
  trọng số tải từ Hugging Face ở lần chạy đầu (~1 GB).

Cả hai không huấn luyện trên nuScenes, nên đánh giá trên nuScenes không bị rò dữ liệu. Kết quả mỗi ảnh (khung, điểm tin
cậy, tên vật, mặt nạ thu nhỏ 1/4) được lưu vào bộ đệm `~/.pointsnap/cache/det2d/`, khóa theo model, nên chỉ chạy model một
lần cho mỗi ảnh; quét lại / đánh giá nhiều vòng chỉ đọc bộ đệm.

PyTorch là phụ thuộc tùy chọn (`pip install -e ".[vision]"`); không có thì `available()` trả `False` và các luật ảnh
bỏ qua.
"""

from __future__ import annotations

import dataclasses

import hashlib
import os
from dataclasses import dataclass
from pathlib import Path

import numpy as np

MODELS = ("maskrcnn", "gdino-sam2")
MODEL_NAME = "maskrcnn_resnet50_fpn_v2_coco"
"""Tên của `maskrcnn` trong khóa bộ đệm (giữ nguyên để dùng lại bộ đệm cũ)."""
GDINO_ID = "IDEA-Research/grounding-dino-base"
SAM2_ID = "facebook/sam2.1-hiera-small"
MASK_SCALE = 4
"""Mặt nạ lưu ở độ phân giải 1/4 để bộ đệm nhỏ."""

GROUP_OF_COCO = {
    "person": "person",
    "bicycle": "two_wheeler", "motorcycle": "two_wheeler",
    "car": "vehicle", "bus": "vehicle", "truck": "vehicle", "train": "vehicle",
    "dog": "animal", "cat": "animal", "cow": "animal", "horse": "animal", "sheep": "animal",
}
"""Class COCO → nhóm dùng để so với nhãn 3D. Class COCO khác (biển báo, đèn…) bỏ qua."""

PROMPTS = {
    "car": "vehicle", "truck": "vehicle", "bus": "vehicle", "trailer": "vehicle", "construction vehicle": "vehicle",
    "person": "person", "bicycle": "two_wheeler", "motorcycle": "two_wheeler",
    "traffic cone": "traffic_cone", "barrier": "barrier", "dog": "animal",
}
"""Từ khóa gửi Grounding DINO → nhóm."""
FRAGMENTS = {"vehicle": "vehicle", "construction": "vehicle"}
"""Grounding DINO đôi khi chỉ trả một phần từ khóa nhiều chữ ("construction vehicle"). "traffic" một mình không rõ là
cọc tiêu hay đèn nên bỏ."""

SUPPORTED_GROUPS = {
    "maskrcnn": frozenset(GROUP_OF_COCO.values()),
    "gdino-sam2": frozenset(PROMPTS.values()),
}
"""Nhóm vật mỗi model nhận được. Box 3D thuộc nhóm model không nhận được thì không đối chiếu (không có bằng chứng)."""


def group_of_name(name: str) -> str | None:
    """Nhóm của tên vật model trả về. Grounding DINO đôi khi ghép hai từ khóa liền nhau ("car truck"): lấy từ khóa
    đứng đầu."""
    if name in GROUP_OF_COCO:
        return GROUP_OF_COCO[name]
    if name in PROMPTS:
        return PROMPTS[name]
    if name in FRAGMENTS:
        return FRAGMENTS[name]
    hits = [(name.find(p), -len(p), g) for p, g in PROMPTS.items() if p in name]
    return min(hits)[2] if hits else None


@dataclass(frozen=True, eq=False)
class Detections:
    """Kết quả nhận diện của một ảnh. `masks[i]` là mặt nạ bool (H/4, W/4) của vật thứ i."""

    boxes: np.ndarray  # (N, 4) x1, y1, x2, y2 pixel ảnh gốc
    scores: np.ndarray  # (N,)
    names: list[str]
    masks: list[np.ndarray]
    brightness: float | None = None
    """Độ sáng trung bình của ảnh (xám 0–255); ảnh đêm của nuScenes 7–89, ảnh ngày 95–117."""

    def groups(self) -> list[str | None]:
        return [group_of_name(n) for n in self.names]


def available(model: str = "maskrcnn") -> bool:
    try:
        import torch  # noqa: F401
        import torchvision  # noqa: F401

        if model == "gdino-sam2":
            import transformers  # noqa: F401
    except ImportError:
        return False
    return True


def cuda_available(model: str = "maskrcnn") -> bool:
    if not available(model):
        return False
    import torch

    return bool(torch.cuda.is_available())


def default_cache_dir() -> Path:
    home = os.environ.get("POINTSNAP_HOME")
    return (Path(home) if home else Path.home() / ".pointsnap") / "cache" / "det2d"


class Detector2D:
    """Model 2D theo `model` (`maskrcnn` / `gdino-sam2`), chạy lười (chỉ nạp model khi gặp ảnh chưa có trong bộ đệm).

    `min_score` là ngưỡng giữ vật khi ghi bộ đệm; luật ảnh lọc tiếp bằng ngưỡng của guideline. Điểm tin cậy của
    Grounding DINO thấp hơn Mask R-CNN (vật rõ thường 0,4 – 0,6), nên bộ đệm của `gdino-sam2` giữ từ 0,2.
    """

    def __init__(self, cache_dir: str | Path | None = None, device: str | None = None, min_score: float = 0.3,
                 model: str = "maskrcnn"):
        if model not in MODELS:
            raise ValueError(f"model ảnh không hỗ trợ: {model!r} (chọn {', '.join(MODELS)})")
        self.cache_dir = Path(cache_dir) if cache_dir else default_cache_dir()
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.device = device
        self.model = model
        self.min_score = min_score if model == "maskrcnn" else min(min_score, 0.2)
        self.supported_groups = SUPPORTED_GROUPS[model]
        self._model = None
        self._categories: list[str] | None = None

    def _key(self, path: Path) -> Path:
        stat = path.stat()
        name = MODEL_NAME if self.model == "maskrcnn" else f"{GDINO_ID}+{SAM2_ID}|{'.'.join(PROMPTS)}"
        raw = f"{name}|{path.resolve()}|{stat.st_size}|{int(stat.st_mtime)}|{self.min_score}"
        return self.cache_dir / f"{hashlib.sha1(raw.encode('utf-8')).hexdigest()}.npz"

    def _load_model(self):
        import torch

        self.device = self.device or ("cuda" if torch.cuda.is_available() else "cpu")
        if self.model == "gdino-sam2":
            self._model = _GroundedSam2(self.device, self.min_score)
            return
        from torchvision.models.detection import MaskRCNN_ResNet50_FPN_V2_Weights, maskrcnn_resnet50_fpn_v2

        weights = MaskRCNN_ResNet50_FPN_V2_Weights.COCO_V1
        model = maskrcnn_resnet50_fpn_v2(weights=weights, box_score_thresh=self.min_score)
        self._model = model.eval().to(self.device)
        self._categories = list(weights.meta["categories"])

    def detect(self, path: str | Path) -> Detections:
        path = Path(path)
        cache = self._key(path)
        if cache.is_file():
            result = _load(cache)
            if result.brightness is None:  # bộ đệm cũ: bổ sung độ sáng, không chạy lại model
                result = dataclasses.replace(result, brightness=image_brightness(path))
                _save(cache, result)
            return result
        result = dataclasses.replace(self._run(path), brightness=image_brightness(path))
        _save(cache, result)
        return result

    def _run(self, path: Path) -> Detections:
        import torch
        from PIL import Image
        from torchvision.transforms.functional import to_tensor

        if self._model is None:
            self._load_model()
        if self.model == "gdino-sam2":
            with Image.open(path) as im:
                return self._model(im.convert("RGB"))
        image = to_tensor(Image.open(path).convert("RGB")).to(self.device)
        with torch.inference_mode():
            out = self._model([image])[0]
        boxes = out["boxes"].cpu().numpy().astype(np.float32)
        scores = out["scores"].cpu().numpy().astype(np.float32)
        names = [self._categories[int(i)] for i in out["labels"].cpu().numpy()]
        return Detections(boxes, scores, names, _shrink(out["masks"][:, 0] > 0.5))


def _shrink(masks_full) -> list[np.ndarray]:
    """Mặt nạ (N, H, W) bool → danh sách mặt nạ 1/4 độ phân giải."""
    import torch

    if len(masks_full) == 0:
        return []
    small = torch.nn.functional.avg_pool2d(masks_full[:, None].float(), MASK_SCALE)[:, 0] > 0.5
    return list(small.cpu().numpy())


class _GroundedSam2:
    """Grounding DINO (khung theo từ khóa) + SAM 2.1 (mặt nạ từ khung)."""

    BATCH = 32
    """SAM 2.1 cắt tối đa chừng này khung mỗi lượt để vừa GPU 4 GB."""

    def __init__(self, device: str, min_score: float):
        from transformers import AutoModelForZeroShotObjectDetection, AutoProcessor, Sam2Model, Sam2Processor

        self.device, self.min_score = device, min_score
        self.text = ". ".join(PROMPTS) + "."
        self.gdino_proc = AutoProcessor.from_pretrained(GDINO_ID)
        self.gdino = AutoModelForZeroShotObjectDetection.from_pretrained(GDINO_ID).to(device).eval()
        self.sam_proc = Sam2Processor.from_pretrained(SAM2_ID)
        self.sam = Sam2Model.from_pretrained(SAM2_ID).to(device).eval()

    def __call__(self, image) -> Detections:
        import torch

        with torch.inference_mode(), torch.autocast("cuda", dtype=torch.float16, enabled=self.device == "cuda"):
            inputs = self.gdino_proc(images=image, text=self.text, return_tensors="pt").to(self.device)
            out = self.gdino(**inputs)
        res = self.gdino_proc.post_process_grounded_object_detection(
            out, inputs.input_ids, threshold=self.min_score, text_threshold=0.25, target_sizes=[image.size[::-1]])[0]
        names = [str(n) for n in res.get("text_labels", res["labels"])]
        boxes = res["boxes"].float().cpu()
        scores = res["scores"].float().cpu().numpy().astype(np.float32)
        masks: list[np.ndarray] = []
        for start in range(0, len(boxes), self.BATCH):
            chunk = boxes[start:start + self.BATCH]
            with torch.inference_mode():
                inp = self.sam_proc(images=image, input_boxes=[chunk.tolist()], return_tensors="pt").to(self.device)
                pred = self.sam(**inp, multimask_output=False).pred_masks
            full = self.sam_proc.post_process_masks(pred.cpu(), inp["original_sizes"])[0][:, 0]
            masks.extend(_shrink(full.bool()))
        return Detections(boxes.numpy().astype(np.float32).reshape(-1, 4), scores, names, masks)


def image_brightness(path: str | Path) -> float:
    from PIL import Image

    with Image.open(path) as im:
        im.draft("L", (im.width // 8, im.height // 8))
        return float(np.asarray(im.convert("L")).mean())


def _save(path: Path, det: Detections) -> None:
    shape = det.masks[0].shape if det.masks else (0, 0)
    packed = np.stack([np.packbits(m.ravel()) for m in det.masks]) if det.masks else np.zeros((0, 0), np.uint8)
    extra = {} if det.brightness is None else {"brightness": np.array(det.brightness)}
    np.savez_compressed(path, boxes=det.boxes, scores=det.scores, names=np.array(det.names, dtype=str),
                        masks=packed, shape=np.array(shape), **extra)


def _load(path: Path) -> Detections:
    data = np.load(path)
    h, w = (int(v) for v in data["shape"])
    masks = [np.unpackbits(row)[: h * w].reshape(h, w).astype(bool) for row in data["masks"]] if h else []
    brightness = float(data["brightness"]) if "brightness" in data else None
    return Detections(data["boxes"], data["scores"], [str(n) for n in data["names"]], masks, brightness)
