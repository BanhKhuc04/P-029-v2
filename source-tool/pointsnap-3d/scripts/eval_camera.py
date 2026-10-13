"""Đo riêng lớp ảnh camera (`cam.*`) của Box Verifier, so các model ảnh (`camera.model`).

`pointsnap eval` chèn lỗi vào box ngẫu nhiên, phần lớn không nhìn rõ trên ảnh, nên mỗi kiểu lỗi chỉ còn ~10 mẫu cho luật
ảnh. Script này làm lệch **từng box mà luật ảnh đo được** trên nhãn chuẩn (mỗi box một lần, giữ nguyên các box khác) rồi
xem `cam.mismatch` có báo đúng frame đó không, nên có hàng nghìn mẫu:

- Phạm vi: box nhìn thấy được, frame ban ngày, model ảnh thấy vật cùng nhóm trùng khung chiếu (đo được phần mặt nạ ngoài
  khung) và track có đủ lần đo khác để so. "Box trong phạm vi / box nhìn thấy" là độ phủ của model ảnh.
- Lỗi chèn: dời ngang 0,5 m (trục ngang của box), nhảy 1 m (hướng ngẫu nhiên), co ×0,7, phóng ×1,3.
- Báo nhầm: số mục `cam.mismatch` (tính như mức Cảnh báo) và `cam.class` trên nhãn chuẩn / 100 box nhìn thấy;
  `cam.missing` (Thông tin).

`--min-scores` và `--rises` quét ngưỡng `camera.min_score` / `camera.mask_rise_warning` một lượt (mặt nạ chỉ tính lại theo
`min_score`). Chỉ chọn ngưỡng trên `--scenes tuning`.

    python scripts/eval_camera.py --model gdino-sam2 --scenes tuning --min-scores 0.3 0.35 0.4 --rises 0.15 0.2 0.25
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import math
import os
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pointsnap.adapters.nuscenes import NuScenesReader  # noqa: E402
from pointsnap.core.config import load_config  # noqa: E402
from pointsnap.core.model import add_track_markers, group_by_frame  # noqa: E402
from pointsnap.detectors.camera import camera_findings, collect_observations, mask_reference  # noqa: E402
from pointsnap.eval.split import TEST_SCENES, TUNING_SCENES  # noqa: E402
from pointsnap.vision.detector2d import Detector2D  # noqa: E402

PERTURB = ("dời ngang 0,5 m", "nhảy 1 m", "co x0,7", "phóng x1,3")


class _Memo:
    """Giữ kết quả nhận diện trong bộ nhớ (mỗi ảnh được đọc lại nhiều lần khi làm lệch từng box)."""

    def __init__(self, detector: Detector2D):
        self.detector, self.cache = detector, {}

    @property
    def supported_groups(self):
        return self.detector.supported_groups

    def detect(self, path):
        if path not in self.cache:
            self.cache[path] = self.detector.detect(path)
        return self.cache[path]


def _perturb(box, kind: str, rng: np.random.Generator):
    c, s = math.cos(box.yaw), math.sin(box.yaw)
    x, y, z = box.center
    if kind == PERTURB[0]:
        side = rng.choice([-1.0, 1.0]) * 0.5
        return box.replace(center=(x - s * side, y + c * side, z))
    if kind == PERTURB[1]:
        a = rng.uniform(0, 2 * math.pi)
        return box.replace(center=(x + math.cos(a), y + math.sin(a), z))
    factor = 0.7 if kind == PERTURB[2] else 1.3
    return box.replace(dims=tuple(np.asarray(box.dims) * factor))


def _rises(obs_of_box, clean_by_track, frame, min_obs):
    """Độ tăng phần mặt nạ ngoài khung của các lần đo `obs_of_box` so với trung vị các frame khác của track."""
    return [o.mask_outside-ref for o in obs_of_box if o.mask_outside is not None
            and (ref := mask_reference(clean_by_track,o,min_obs)) is not None]


def evaluate(reader, scenes, cfg, detector, seed=0):
    """Trả về (số box nhìn thấy, độ tăng lớn nhất của từng mẫu theo kiểu lỗi, số box trong phạm vi)."""
    rng = np.random.default_rng(seed)
    visible_total, in_scope = 0, 0
    samples: dict[str, list[float]] = defaultdict(list)
    for scene in scenes:
        frames = reader.frames(scene)
        boxes = [b for b in add_track_markers(reader.annotations(scene), frames.num_frames) if b.visible]
        visible_total += len(boxes)
        obs, _ = collect_observations(boxes, frames, detector, cfg)
        by_track = defaultdict(list)
        for o in obs:
            if o.mask_outside is not None and o.box.track_id is not None:
                by_track[(o.box.track_id,o.box.label)].append(o)
        targets = {(o.box.track_id, o.box.label, o.box.frame) for os_ in by_track.values() for o in os_
                   if len(_rises([o], os_, o.box.frame, cfg.min_track_observations))}
        in_scope += len(targets)
        frame_boxes = group_by_frame(boxes)
        for track_id, label, frame in sorted(targets):
            others_in_frame = [b for b in frame_boxes[frame] if (b.track_id,b.label) != (track_id,label)]
            original = next(b for b in frame_boxes[frame] if (b.track_id,b.label) == (track_id,label))
            for kind in PERTURB:
                moved = _perturb(original, kind, rng)
                new_obs, _ = collect_observations([moved, *others_in_frame], frames, detector, cfg)
                mine = [o for o in new_obs if o.box is moved]
                rises = _rises(mine, by_track[(track_id,label)], frame, cfg.min_track_observations)
                samples[kind].append(max(rises) if rises else -1.0)
        print(f"{scene}: {len(boxes)} box nhìn thấy, {len(targets)} box trong phạm vi", flush=True)
    return visible_total, dict(samples), in_scope


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure") and (stream.encoding or "").lower() not in ("utf-8", "utf8"):
            stream.reconfigure(encoding="utf-8")
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--model", choices=("maskrcnn", "gdino-sam2", "hybrid"), default="maskrcnn")
    p.add_argument("--scenes", choices=("tuning","test"), default="tuning", help="tuning | test")
    p.add_argument("--dataroot", default=os.environ.get("NUSCENES_ROOT"))
    p.add_argument("--config", type=Path, help="guideline YAML (mặc định: cấu hình mặc định)")
    p.add_argument("--min-scores", type=float, nargs="+", help="các giá trị camera.min_score cần thử")
    p.add_argument("--rises", type=float, nargs="+", help="các giá trị camera.mask_rise_warning cần thử")
    p.add_argument("--out", type=Path, help="ghi kết quả JSON")
    args = p.parse_args()
    if not args.dataroot:
        p.error("cần --dataroot hoặc biến môi trường NUSCENES_ROOT")

    base = load_config(args.config)
    base_cam = dataclasses.replace(base.camera, model=args.model, mismatch_severity="warning")
    reader = NuScenesReader(args.dataroot)
    scenes = TUNING_SCENES if args.scenes == "tuning" else TEST_SCENES
    detector = _Memo(Detector2D(model=args.model))
    rows = []
    for min_score in args.min_scores or [base_cam.min_score]:
        cfg = dataclasses.replace(base_cam, min_score=min_score)
        visible, samples, in_scope = evaluate(reader, scenes, cfg, detector)
        for rise in args.rises or [cfg.mask_rise_warning]:
            clean_cfg = dataclasses.replace(cfg, mask_rise_warning=rise)
            row = {"model": args.model, "min_score": min_score, "mask_rise_warning": rise, "visible_boxes": visible,
                   "in_scope_boxes": in_scope, "coverage": in_scope / visible,
                   "recall": {k: float(np.mean(np.asarray(v) > rise)) for k, v in samples.items()},
                   "samples": {k: len(v) for k, v in samples.items()}}
            rows.append((row, cfg, clean_cfg))
    # Báo nhầm phụ thuộc cả hai ngưỡng: chấm lại nhãn chuẩn cho từng cặp (nhanh, ảnh đã nằm trong bộ nhớ).
    results = []
    for row, cfg, clean_cfg in rows:
        fp = _clean_fp(reader, scenes, clean_cfg, detector)
        row["clean_per_100"] = {k: 100.0 * v / row["visible_boxes"] for k, v in fp.items()}
        results.append(row)
        recall = " · ".join(f"{k} {v:.0%}" for k, v in row["recall"].items())
        fps = " · ".join(f"{k} {v:.2f}" for k, v in row["clean_per_100"].items())
        print(f"min_score {row['min_score']:.2f} rise {row['mask_rise_warning']:.2f} | phủ {row['coverage']:.0%} "
              f"({row['in_scope_boxes']}/{row['visible_boxes']}) | {recall} | báo nhầm /100 box: {fps}", flush=True)
    if args.out:
        args.out.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0


def _clean_fp(reader, scenes, cfg, detector) -> dict[str, int]:
    counts: dict[str, int] = {"cam.mismatch": 0, "cam.class": 0, "cam.missing": 0}
    for scene in scenes:
        frames = reader.frames(scene)
        boxes = [b for b in add_track_markers(reader.annotations(scene), frames.num_frames) if b.visible]
        obs, missing = collect_observations(boxes, frames, detector, cfg)
        for f in camera_findings(obs, cfg):
            counts[f.rule] = counts.get(f.rule, 0) + 1
        counts["cam.missing"] += len(missing)
    return counts


if __name__ == "__main__":
    raise SystemExit(main())
