"""Thống kê kích thước theo class từ nhãn chuẩn nuScenes của các cảnh tinh chỉnh (việc B4).

In ra đoạn YAML cho `size.class_range.stats` trong `pointsnap/config.yaml`: với mỗi class có ít nhất
`min_instances` đối tượng, khoảng [p_low, p_high] (percentile theo config) của length, width, height, tính trên
**trung vị kích thước của từng đối tượng** (giống cách luật xét theo track), không phải trên từng box.
Class ít mẫu hơn được liệt kê riêng để dùng `size.manual_ranges`.

Chạy: python scripts/build_size_stats.py --data D:/Vin_uni/data/nuscenes
"""

from __future__ import annotations

import argparse
import os
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pointsnap.adapters.nuscenes import NuScenesReader  # noqa: E402
from pointsnap.core.config import DIMENSIONS, load_config  # noqa: E402
from pointsnap.eval.split import TUNING_SCENES  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--data", default=os.environ.get("NUSCENES_ROOT"), help="thư mục nuScenes")
    parser.add_argument("--scenes", nargs="*", default=list(TUNING_SCENES), help="cảnh dùng để thống kê")
    args = parser.parse_args()
    if not args.data:
        print("Thiếu --data hoặc NUSCENES_ROOT", file=sys.stderr)
        return 2

    cfg = load_config().size.class_range
    reader = NuScenesReader(args.data)
    per_object: dict[tuple[str, str, int], list[tuple[float, float, float]]] = defaultdict(list)
    for scene in args.scenes:
        for box in reader.annotations(scene):
            per_object[(box.label, scene, box.track_id)].append(box.dims)
    dims: dict[str, list[np.ndarray]] = defaultdict(list)
    boxes: dict[str, int] = defaultdict(int)
    for (label, _, _), values in per_object.items():
        dims[label].append(np.median(np.asarray(values), axis=0))
        boxes[label] += len(values)

    print(f"# Sinh bằng scripts/build_size_stats.py từ {len(args.scenes)} cảnh tinh chỉnh: {', '.join(args.scenes)}")
    print(f"# p{cfg.percentile_low:g} – p{cfg.percentile_high:g}; chỉ class có >= {cfg.min_instances} đối tượng")
    print("stats:")
    few = []
    for label in sorted(dims):
        if len(dims[label]) < cfg.min_instances:
            few.append(f"{label} ({len(dims[label])} đối tượng)")
            continue
        values = np.asarray(dims[label])
        parts = []
        for i, dim in enumerate(DIMENSIONS):
            low, high = np.percentile(values[:, i], [cfg.percentile_low, cfg.percentile_high])
            parts.append(f"{dim}: [{low:.2f}, {high:.2f}]")
        print(f"  {label + ':':22s}{{{', '.join(parts)}}}  # {len(values)} đối tượng, {boxes[label]} box")
    print("# Class ít mẫu, dùng manual_ranges: " + (", ".join(few) or "không có"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
