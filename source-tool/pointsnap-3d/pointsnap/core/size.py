"""Phát hiện sai kích thước (việc B4, mục 4.1b của đề xuất).

- Kiểu 1 `size.class_range`: l, w, h so với khoảng [p_low, p_high] của class. Khoảng lấy từ thống kê nhãn chuẩn
  (`size.class_range.stats`, sinh bằng `scripts/build_size_stats.py`); class ít mẫu dùng `size.manual_ranges`.
  Cảnh báo nếu ngoài [p_low·(1 − warning_margin), p_high·(1 + warning_margin)], Lỗi nếu ngoài biên `error_margin`.
- Kiểu 2 `size.in_track`: độ lệch mỗi keyframe so với trung vị của track. Cảnh báo nếu lệch
  > max(warning_abs_m, warning_rel · trung vị), Lỗi nếu > max(error_abs_m, error_rel · trung vị).
Mỗi box có tối đa một finding mỗi kiểu, ghi chiều lệch nhiều nhất.
"""

from __future__ import annotations

from typing import Iterable

import numpy as np

from pointsnap.core.config import DIMENSIONS, Config
from pointsnap.core.model import Cuboid, ErrorType, Finding, Severity, group_by_track

DIM_VI = {"length": "Chiều dài", "width": "Chiều rộng", "height": "Chiều cao"}


def _dims(box: Cuboid) -> dict[str, float]:
    return dict(zip(DIMENSIONS, box.dims))


def class_ranges(config: Config) -> dict[str, dict[str, tuple[float, float]]]:
    """Khoảng kích thước dùng cho từng class: thống kê nếu có, không thì khoảng nhập tay."""
    return {**config.size.manual_ranges, **config.size.class_range.stats}


def _class_range_violation(
    label: str, dims: dict[str, float], limits: dict[str, tuple[float, float]], config: Config,
) -> tuple[Severity, str, float, float] | None:
    """Chiều vượt khoảng nhiều nhất: `(mức, chiều, giá trị, biên đã vượt)`, hoặc `None` nếu nằm trong khoảng."""
    cfg = config.size.class_range
    worst: tuple[Severity, float, str, float, float] | None = None
    for dim, value in dims.items():
        low, high = limits[dim]
        for severity, margin in ((Severity.ERROR, cfg.error_margin), (Severity.WARNING, cfg.warning_margin)):
            lo, hi = low * (1 - margin), high * (1 + margin)
            if value < lo or value > hi:
                bound = lo if value < lo else hi
                excess = abs(value - bound) / bound
                if worst is None or (severity.rank, -excess) < (worst[0].rank, -worst[1]):
                    worst = (severity, excess, dim, value, bound)
                break
    return None if worst is None else (worst[0], worst[2], worst[3], worst[4])


def check_size_class_range(cuboids: Iterable[Cuboid], config: Config, frames=None) -> list[Finding]:
    """Kiểu 1. Track được xét bằng trung vị kích thước của nó và báo **một mục cho cả track** (gắn vào keyframe lệch
    nhiều nhất), vì kích thước theo class là thuộc tính của đối tượng; keyframe lẻ lệch khỏi track do kiểu 2 bắt.
    Box lẻ (không có track) xét riêng từng box."""
    ranges = class_ranges(config)
    cuboids = [c for c in cuboids if not c.outside and c.label in ranges]
    groups: list[list[Cuboid]] = [[c] for c in cuboids if c.track_id is None]
    groups += list(group_by_track(cuboids).values())

    findings: list[Finding] = []
    for boxes in groups:
        label = boxes[0].label
        dims = {dim: float(np.median([_dims(b)[dim] for b in boxes])) for dim in DIMENSIONS}
        violation = _class_range_violation(label, dims, ranges[label], config)
        if violation is None:
            continue
        severity, dim, value, bound = violation
        pick = max if value > bound else min
        box = pick(boxes, key=lambda b: _dims(b)[dim])
        low, high = ranges[label][dim]
        side = "nhỏ hơn" if value < bound else "lớn hơn"
        scope = f" (trung vị của {len(boxes)} keyframe)" if len(boxes) > 1 else ""
        findings.append(Finding(
            error_type=ErrorType.SIZE, rule="size.class_range", severity=severity, frame=box.frame, label=label,
            message=f"{DIM_VI[dim]} {value:.2f} m{scope} {side} khoảng thường gặp của {label} ({low:.2f}–{high:.2f} m)",
            track_id=box.track_id, source_id=box.source_id, value=value, threshold=bound,
            details={"dimension": dim, "range": [low, high], "keyframes": len(boxes)},
        ))
    return findings

def check_size_in_track(cuboids: Iterable[Cuboid], config: Config, frames=None) -> list[Finding]:
    cfg = config.size.in_track
    findings: list[Finding] = []
    for boxes in group_by_track(cuboids).values():
        active = [b for b in boxes if not b.outside]
        if len(active) < cfg.min_keyframes or active[0].label in cfg.excluded_classes:
            continue
        medians = {dim: float(np.median([_dims(b)[dim] for b in active])) for dim in DIMENSIONS}
        for box in active:
            worst: tuple[Severity, float, str, float] | None = None  # (mức, lệch tương đối, chiều, lệch m)
            for dim, value in _dims(box).items():
                median = medians[dim]
                diff = abs(value - median)
                rel = diff / max(median, 1e-4)
                if diff > max(cfg.error_abs_m, cfg.error_rel * median):
                    severity = Severity.ERROR
                elif diff > max(cfg.warning_abs_m, cfg.warning_rel * median):
                    severity = Severity.WARNING
                else:
                    continue
                if worst is None or (severity.rank, -rel) < (worst[0].rank, -worst[1]):
                    worst = (severity, rel, dim, diff)
            if worst is None:
                continue
            severity, rel, dim, diff = worst
            value, median = _dims(box)[dim], medians[dim]
            message = (f"{DIM_VI[dim]} {value:.2f} m lệch {diff * 100:.0f} cm ({rel * 100:.0f}%) "
                       f"so với trung vị của track ({median:.2f} m)")
            if rel > cfg.suspect_id_rel:
                message += " — nghi nhầm ID"
            threshold = cfg.error_abs_m if severity is Severity.ERROR else cfg.warning_abs_m
            findings.append(Finding(
                error_type=ErrorType.SIZE, rule="size.in_track", severity=severity, frame=box.frame,
                label=box.label, message=message, track_id=box.track_id, source_id=box.source_id,
                value=rel, threshold=threshold, details={"dimension": dim, "diff_m": diff, "track_median_m": median},
            ))
    return findings
