"""Bộ phát hiện box vẽ lệch khỏi vật (việc C1).

Spec 4.2: box phải bao trọn toàn bộ vật thể, không dư thừa quá mức; không gán box khi vật quá ít điểm. Bốn luật:

1. `fit.empty`: vùng quanh box được LiDAR quét dày (đo được mặt đất) nhưng trong box không có điểm nào cao hơn mặt
   box (≤ `empty_max_points`), và box không đánh `occluded` → Cảnh báo (vẽ vào chỗ trống, hoặc vật bị che mà chưa
   đánh occluded; trên nhãn chuẩn có cả vật thấp / đổ chỉ để lại vài điểm sát đáy nên không để mức Lỗi). Box có ít điểm
   hơn `sparse_warning_points` → Cảnh báo "quá ít điểm" (tắt mặc định, chờ chốt P-009).
2. `fit.outside`: trong vùng box nới `outside_margin_m`, sau khi bỏ mặt đất và điểm của box khác, tỉ lệ điểm của vật
   nằm ngoài box > `outside_warning_ratio` → box nhỏ hoặc lệch khỏi vật.
3. `fit.loose`: mặt box quay về phía cảm biến (nhìn thấy được, không bị che) mà cách điểm gần nhất của vật hơn
   `loose_warning_m` → box dư. Chỉ xét box gần, nhiều điểm; mặt sau của vật vốn không có điểm nên không xét.
4. `fit.overlap`: hai box cùng frame chồng nhau (diện tích phần chung nhìn từ trên / diện tích box nhỏ hơn, và chồng
   theo chiều cao) > `overlap_warning` → nghi vẽ trùng một vật. Chỉ xét class trong `overlap_classes`; spec 4.3B cho
   phép người đứng sát nhau chồng box, xe kéo rơ-moóc chồng ở chỗ nối (`overlap_allowed_pairs`). Báo trên box nhỏ hơn.
"""

from __future__ import annotations

import math
from itertools import combinations
from typing import TYPE_CHECKING, Callable, Iterable, Sequence

import numpy as np

from pointsnap.core.box_points import BoxPointSet
from pointsnap.core.geometry import _clip_convex, footprint, polygon_area
from pointsnap.core.model import Cuboid, ErrorType, Finding, Severity

if TYPE_CHECKING:
    from pointsnap.core.config import FitConfig

FACE_NAMES = {(0, 1): "đầu", (0, -1): "đuôi", (1, 1): "bên trái", (1, -1): "bên phải"}


def _finding(rule: str, severity: Severity, box: Cuboid, message: str, value: float, threshold: float,
             details: dict) -> Finding:
    return Finding(error_type=ErrorType.FIT, rule=rule, severity=severity, frame=box.frame, label=box.label,
                   track_id=box.track_id, source_id=box.source_id, message=message, value=value,
                   threshold=threshold, details=details)


def empty_finding(item: BoxPointSet, cfg: FitConfig) -> Finding | None:
    box = item.box
    if box.attrs.get("occluded"):
        return None
    if item.raw_inside <= cfg.empty_max_points and item.ground_z is not None:
        return _finding("fit.empty", Severity.WARNING, box,
                        f"Box không có điểm LiDAR nào ({item.raw_inside} điểm): vẽ vào chỗ trống, hoặc vật bị che "
                        f"thì đánh dấu occluded", float(item.raw_inside), float(cfg.empty_max_points),
                        {"num_points": item.raw_inside})
    if cfg.sparse_warning_points and item.raw_inside < cfg.sparse_warning_points:
        return _finding("fit.empty", Severity.WARNING, box,
                        f"Box chỉ có {item.raw_inside} điểm LiDAR (< {cfg.sparse_warning_points}): spec 4.2 không "
                        f"nên gán box khi vật quá ít điểm", float(item.raw_inside), float(cfg.sparse_warning_points),
                        {"num_points": item.raw_inside})
    return None


def outside_finding(item: BoxPointSet, cfg: FitConfig) -> Finding | None:
    total, outside = item.num_object_points, item.num_outside
    if outside < cfg.outside_min_points or total == 0:
        return None
    ratio = outside / total
    if ratio <= cfg.outside_warning_ratio:
        return None
    severity = Severity.ERROR if ratio > cfg.outside_error_ratio else Severity.WARNING
    threshold = cfg.outside_error_ratio if ratio > cfg.outside_error_ratio else cfg.outside_warning_ratio
    out = item.local[~item.inside]
    half = np.asarray(item.box.dims) / 2.0
    excess = np.maximum(np.abs(out) - half, 0.0)
    axis = int(np.argmax(excess[:, :2].sum(axis=0)))
    side = 1 if np.sum(np.sign(out[:, axis]) * excess[:, axis]) >= 0 else -1
    where = FACE_NAMES[(axis, side)]
    reach = float(np.percentile(excess[:, axis], 90))
    return _finding("fit.outside", severity, item.box,
                    f"{outside}/{total} điểm của vật ({ratio:.0%}) nằm ngoài box, nhiều nhất phía {where} "
                    f"(tới {reach * 100:.0f} cm): box nhỏ hoặc lệch khỏi vật (ngưỡng {threshold:.0%})",
                    ratio, threshold, {"outside": outside, "total": total, "side": where, "reach_m": reach})


def _occluded(points: np.ndarray, target: np.ndarray, own: np.ndarray, radius: float = 0.3) -> bool:
    """Đường từ cảm biến (gốc) tới `target` có bị điểm khác (ngoài vật) chắn không."""
    distance = float(np.linalg.norm(target))
    if distance < 1e-6:
        return False
    direction = target / distance
    along = points @ direction
    candidate = (along > 1.0) & (along < distance - 0.5)
    if not candidate.any():
        return False
    pts = points[candidate]
    perp = np.linalg.norm(pts - np.outer(along[candidate], direction), axis=1)
    blocking = perp < radius
    if own.size:
        blocking &= ~np.isin(np.flatnonzero(candidate), own)
    return int(blocking.sum()) >= 3


def loose_finding(item: BoxPointSet, cfg: FitConfig, frame_points: np.ndarray | None = None) -> Finding | None:
    box = item.box
    if item.num_object_points < cfg.loose_min_points or item.range_m > cfg.loose_max_range_m:
        return None
    half = np.asarray(box.dims) / 2.0
    inside = item.local[item.inside]
    if len(inside) < cfg.loose_min_points:
        return None
    worst: tuple[float, str] | None = None
    for axis in (0, 1):
        for side in (1, -1):
            if side * item.sensor_local[axis] <= half[axis]:
                continue  # mặt này quay lưng về cảm biến
            extent = float(np.percentile(side * inside[:, axis], 98))
            gap = half[axis] - extent
            if gap <= cfg.loose_warning_m:
                continue
            if frame_points is not None:
                c, s = math.cos(box.yaw), math.sin(box.yaw)
                local = np.zeros(2)
                local[axis] = side * half[axis]
                face = np.array([box.center[0] + c * local[0] - s * local[1],
                                 box.center[1] + s * local[0] + c * local[1], box.center[2]])
                if _occluded(frame_points, face, np.empty(0, dtype=np.int64)):
                    continue
            if worst is None or gap > worst[0]:
                worst = (gap, FACE_NAMES[(axis, side)])
    if worst is None:
        return None
    gap, where = worst
    severity = Severity.ERROR if gap > cfg.loose_error_m else Severity.WARNING
    threshold = cfg.loose_error_m if gap > cfg.loose_error_m else cfg.loose_warning_m
    return _finding("fit.loose", severity, box,
                    f"Mặt {where} của box cách điểm gần nhất của vật {gap * 100:.0f} cm dù nhìn thấy rõ từ LiDAR: "
                    f"box dư so với vật (ngưỡng {threshold * 100:.0f} cm)", gap, threshold,
                    {"gap_m": gap, "face": where, "num_points": int(len(inside))})


def _overlap_ratio(a: Cuboid, b: Cuboid) -> float:
    z_overlap = min(a.top_z, b.top_z) - max(a.bottom_z, b.bottom_z)
    if z_overlap <= 0.3 * min(a.height, b.height):
        return 0.0
    origin = np.asarray(a.center[:2])
    fa, fb = footprint(a) - origin, footprint(b) - origin
    inter = polygon_area(_clip_convex(fa, fb))
    smaller = min(polygon_area(fa), polygon_area(fb))
    return inter / smaller if smaller > 0 else 0.0


def overlap_findings(
    boxes: Iterable[Cuboid], cfg: FitConfig, typed: Callable[[Cuboid], str] | None = None,
) -> list[Finding]:
    """Luật `fit.overlap`. `typed(box)` cho tên chi tiết `Class/thuộc tính phân loại` (vd `Vehicle/truck`) để cặp
    được phép có thể ghi theo tên chi tiết; mặc định chỉ dùng class."""
    allowed = {frozenset(p) for p in cfg.overlap_allowed_pairs}
    typed = typed or (lambda box: box.label)
    findings: list[Finding] = []
    active = [b for b in boxes if b.visible]
    for a, b in combinations(active, 2):
        reach = (math.hypot(a.length, a.width) + math.hypot(b.length, b.width)) / 2.0
        if math.hypot(a.center[0] - b.center[0], a.center[1] - b.center[1]) > reach:
            continue
        if a.label not in cfg.overlap_classes or b.label not in cfg.overlap_classes:
            continue
        names_a, names_b = {a.label, typed(a)}, {b.label, typed(b)}
        if any(frozenset((x, y)) in allowed for x in names_a for y in names_b):
            continue
        ratio = _overlap_ratio(a, b)
        if ratio <= cfg.overlap_warning:
            continue
        small, other = (a, b) if a.length * a.width <= b.length * b.width else (b, a)
        severity = Severity.ERROR if ratio > cfg.overlap_error else Severity.WARNING
        threshold = cfg.overlap_error if ratio > cfg.overlap_error else cfg.overlap_warning
        who = f"track {other.track_id}" if other.track_id is not None else "box khác"
        findings.append(_finding("fit.overlap", severity, small,
                                 f"Box chồng {ratio:.0%} diện tích lên box {other.label} ({who}): nghi vẽ trùng một "
                                 f"vật hoặc hai box lấn nhau (ngưỡng {threshold:.0%})", ratio, threshold,
                                 {"other_track_id": other.track_id, "other_label": other.label}))
    return findings


def fit_findings_for_frame(
    items: Sequence[BoxPointSet], cfg: FitConfig, frame_points: np.ndarray | None,
    empty: bool = True, outside: bool = True, loose: bool = True,
) -> list[Finding]:
    findings: list[Finding] = []
    for item in items:
        if empty and (f := empty_finding(item, cfg)) is not None:
            findings.append(f)
            continue
        if outside and (f := outside_finding(item, cfg)) is not None:
            findings.append(f)
        if loose and (f := loose_finding(item, cfg, frame_points)) is not None:
            findings.append(f)
    return findings
