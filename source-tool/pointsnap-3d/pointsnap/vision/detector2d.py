"""Nhận diện vật thể trên ảnh camera bằng model 2D có sẵn (việc C3, lớp 2 của Box Verifier).

Dùng Mask R-CNN ResNet-50 FPN v2 của torchvision, huấn luyện trên COCO (không dùng nuScenes, nên đánh giá trên nuScenes
không bị rò dữ liệu). Kết quả mỗi ảnh (khung, điểm tin cậy, class, mặt nạ thu nhỏ 1/4) được lưu vào bộ đệm
`~/.pointsnap/cache/det2d/` nên chỉ chạy model một lần cho mỗi ảnh; quét lại / đánh giá nhiều vòng chỉ đọc bộ đệm.

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

MODEL_NAME = "maskrcnn_resnet50_fpn_v2_coco"
MASK_SCALE = 4
"""Mặt nạ lưu ở độ phân giải 1/4 để bộ đệm nhỏ."""

GROUP_OF_COCO = {
    "person": "person",
    "bicycle": "two_wheeler", "motorcycle": "two_wheeler",
    "car": "vehicle", "bus": "vehicle", "truck": "vehicle", "train": "vehicle",
    "dog": "animal", "cat": "animal", "cow": "animal", "horse": "animal", "sheep": "animal",
}
"""Class COCO → nhóm dùng để so với nhãn 3D. Class COCO khác (biển báo, đèn…) bỏ qua."""


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
        return [GROUP_OF_COCO.get(n) for n in self.names]


def available() -> bool:
    try:
        import torch  # noqa: F401
        import torchvision  # noqa: F401
    except ImportError:
        return False
    return True


def cuda_available() -> bool:
    if not available():
        return False
    import torch

    return bool(torch.cuda.is_available())


def default_cache_dir() -> Path:
    home = os.environ.get("POINTSNAP_HOME")
    return (Path(home) if home else Path.home() / ".pointsnap") / "cache" / "det2d"


class Detector2D:
    """Mask R-CNN COCO, chạy lười (chỉ nạp model khi gặp ảnh chưa có trong bộ đệm)."""

    def __init__(self, cache_dir: str | Path | None = None, device: str | None = None, min_score: float = 0.3):
        self.cache_dir = Path(cache_dir) if cache_dir else default_cache_dir()
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.device = device
        self.min_score = min_score
        self._model = None
        self._categories: list[str] | None = None

    def _key(self, path: Path) -> Path:
        stat = path.stat()
        raw = f"{MODEL_NAME}|{path.resolve()}|{stat.st_size}|{int(stat.st_mtime)}|{self.min_score}"
        return self.cache_dir / f"{hashlib.sha1(raw.encode('utf-8')).hexdigest()}.npz"

    def _load_model(self):
        import torch
        from torchvision.models.detection import MaskRCNN_ResNet50_FPN_V2_Weights, maskrcnn_resnet50_fpn_v2

        weights = MaskRCNN_ResNet50_FPN_V2_Weights.COCO_V1
        self.device = self.device or ("cuda" if torch.cuda.is_available() else "cpu")
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
        result = self._run(path)
        _save(cache, result)
        return result

    def _run(self, path: Path) -> Detections:
        import torch
        from PIL import Image
        from torchvision.transforms.functional import to_tensor

        if self._model is None:
            self._load_model()
        image = to_tensor(Image.open(path).convert("RGB")).to(self.device)
        with torch.inference_mode():
            out = self._model([image])[0]
        boxes = out["boxes"].cpu().numpy().astype(np.float32)
        scores = out["scores"].cpu().numpy().astype(np.float32)
        names = [self._categories[int(i)] for i in out["labels"].cpu().numpy()]
        masks_full = (out["masks"][:, 0] > 0.5)
        small = torch.nn.functional.avg_pool2d(masks_full[:, None].float(), MASK_SCALE)[:, 0] > 0.5
        masks = [m for m in small.cpu().numpy()]
        return Detections(boxes, scores, names, masks, image_brightness(path))


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
