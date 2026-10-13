"""Fresh cached-model inference on real nuScenes images, then a cache roundtrip.

Uses only already downloaded checkpoints. Does not download other
models or report task precision from the predicted detections.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import time

import numpy as np


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--model", choices=("maskrcnn", "gdino-sam2", "hybrid"), default="maskrcnn")
    parser.add_argument("--images", type=int, default=3)
    args = parser.parse_args()
    if args.images < 1:
        parser.error("--images must be positive")
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    import torch
    from torchvision.models.detection import MaskRCNN_ResNet50_FPN_V2_Weights
    from pointsnap.vision.detector2d import Detector2D
    checkpoint = Path(torch.hub.get_dir()) / "checkpoints" / Path(MaskRCNN_ResNet50_FPN_V2_Weights.COCO_V1.url).name
    if args.model in ("maskrcnn", "hybrid") and not checkpoint.is_file():
        print("SKIP: cached Mask R-CNN checkpoint missing")
        return 77
    weights = {}
    if args.model in ("maskrcnn", "hybrid"):
        weights["maskrcnn"] = checkpoint
    if args.model in ("gdino-sam2", "hybrid"):
        from huggingface_hub.constants import HF_HUB_CACHE
        for name, folder in (("Grounding DINO", "models--IDEA-Research--grounding-dino-base"),
                             ("SAM 2.1", "models--facebook--sam2.1-hiera-small")):
            paths = list((Path(HF_HUB_CACHE) / folder / "snapshots").glob("*/*.safetensors"))
            if not paths:
                print(f"SKIP: cached {name} checkpoint missing")
                return 77
            weights[name] = sorted(paths)[-1]
    args.out.mkdir(parents=True, exist_ok=True)
    # A fresh cache under this run forces actual inference, regardless of prior results.
    detector = Detector2D(cache_dir=args.out / "fresh-cache", model=args.model)
    images = sorted((args.dataset / "samples/CAM_FRONT").glob("*.jpg"))[:args.images]
    if len(images) != args.images:
        raise ValueError("Need the requested number of real CAM_FRONT images")
    rows = []
    for path in images:
        started = time.monotonic()
        detected = detector.detect(path)
        seconds = time.monotonic() - started
        assert detected.boxes.shape == (len(detected.scores), 4)
        assert len(detected.scores) == len(detected.names) == len(detected.masks)
        assert np.isfinite(detected.boxes).all() and np.isfinite(detected.scores).all()
        assert ((detected.scores >= 0) & (detected.scores <= 1)).all()
        cached = detector.detect(path)
        assert np.array_equal(cached.boxes, detected.boxes)
        assert np.array_equal(cached.scores, detected.scores) and cached.names == detected.names
        assert all(np.array_equal(a, b) for a, b in zip(cached.masks, detected.masks))
        rows.append(dict(image=path.name, sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                         detections=len(detected.names), groups=sorted({g for g in detected.groups() if g}),
                         seconds=round(seconds, 3), cache_roundtrip="PASS"))
    def sha256(path):
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(block)
        return digest.hexdigest()
    result = dict(model=args.model, torch=torch.__version__, offline_weights=True,
                  device=detector.device or "hybrid parts select CUDA when available",
                  checkpoint_sha256={name: sha256(path) for name, path in weights.items()},
                  images=rows, manual_precision=None)
    (args.out / "model.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
