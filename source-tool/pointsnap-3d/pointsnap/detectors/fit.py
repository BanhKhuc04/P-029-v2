"""Bộ phát hiện box vẽ lệch khỏi vật (việc C1).

Spec 4.2: box phải bao trọn toàn bộ vật thể, không dư thừa quá mức; không gán box khi vật quá ít điểm. Bốn luật:

1. `fit.empty`: vùng quanh box được LiDAR quét dày (đo được mặt đất) nhưng trong box không có điểm nào cao hơn mặt
   box (≤ `empty_max_points`), và box không đánh `occluded` → Cảnh báo (vẽ vào chỗ trống, hoặc vật bị che mà chưa
   đánh occluded; trên nhãn chuẩn có cả vật thấp / đổ chỉ để lại vài điểm sát đáy nên không để mức Lỗi). Box có ít điểm
   hơn `sparse_warning_points` → Cảnh báo "quá ít điểm" (tắt mặc định, chờ chốt P-009).
2. `fit.outside`: trong vùng box nới `outside_margin_m`, sau khi bỏ mặt đất và điểm của box khác, tỉ lệ điểm của vật
   nằm ngoài box cao hơn trung vị của các frame khác cùng track quá `outside_warning_ratio` → box nhỏ hoặc lệch.
3. `fit.loose`: mặt box quay về phía cảm biến (nhìn thấy được, không bị che) mà cách điểm gần nhất của vật hơn
   `loose_warning_m` → box dư. Chỉ xét box gần, nhiều điểm; mặt sau của vật vốn không có điểm nên không xét.
4. `fit.overlap`: hai box cùng frame chồng nhau (diện tích phần chung nhìn từ trên / diện tích box nhỏ hơn, và chồng
   theo chiều cao) > `overlap_warning` → nghi vẽ trùng một vật. Chỉ xét class trong `overlap_classes`; spec 4.3B cho
   phép người đứng sát nhau chồng box, xe kéo rơ-moóc chồng ở chỗ nối (`overlap_allowed_pairs`). Báo trên box nhỏ hơn.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
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


@dataclass(frozen=True)
class OutsideMeasure:
    """Số đo của luật `fit.outside` cho một box: số điểm của vật, số điểm nằm ngoài box, phía và độ thò ra nhiều nhất."""

    box: Cuboid
    outside: int
    total: int
    side: str
    reach_m: float

    @property
    def ratio(self) -> float:
        return self.outside / self.total


def outside_measure(item: BoxPointSet, cfg: FitConfig) -> OutsideMeasure | None:
    """Đo điểm của vật nằm ngoài box; `None` nếu vật có ít hơn `outside_min_points` điểm."""
    total, outside = item.num_object_points, item.num_outside
    if total < cfg.outside_min_points:
        return None
    side, reach = "", 0.0
    if outside:
        out = item.local[~item.inside]
        half = np.asarray(item.box.dims) / 2.0
        excess = np.maximum(np.abs(out) - half, 0.0)
        axis = int(np.argmax(excess[:, :2].sum(axis=0)))
        sign = 1 if np.sum(np.sign(out[:, axis]) * excess[:, axis]) >= 0 else -1
        side, reach = FACE_NAMES[(axis, sign)], float(np.percentile(excess[:, axis], 90))
    return OutsideMeasure(item.box, outside, total, side, reach)


def outside_findings(measures: Sequence[OutsideMeasure], cfg: FitConfig) -> list[Finding]:
    """Luật `fit.outside`: tỉ lệ điểm của vật nằm ngoài box, **so với trung vị của các box khác cùng track**.

    Vật mang đồ, người đứng sát không có box, cây sát xe… làm tỉ lệ này cao đều trong cả track (đo trên 5 cảnh kiểm
    tra: gần như mọi báo nhầm thuộc vài track người đi bộ); keyframe bị co / dời lệch khác thường so với chính track
    mới là lỗi vẽ. Box lẻ hoặc track có ít hơn 2 box khác đo được thì so tỉ lệ tuyệt đối.
    """
    by_track: dict[int, list[float]] = {}
    for m in measures:
        if m.box.track_id is not None:
            by_track.setdefault(m.box.track_id, []).append(m.ratio)
    findings: list[Finding] = []
    for m in measures:
        if m.outside < cfg.outside_min_points:
            continue
        others = list(by_track.get(m.box.track_id, [])) if m.box.track_id is not None else []
        if others:
            others.remove(m.ratio)
        reference = float(np.median(others)) if len(others) >= 2 else 0.0
        excess = m.ratio - reference
        if excess <= cfg.outside_warning_ratio:
            continue
        severity = Severity.ERROR if excess > cfg.outside_error_ratio else Severity.WARNING
        threshold = cfg.outside_error_ratio if excess > cfg.outside_error_ratio else cfg.outside_warning_ratio
        relative = f"; các frame khác của track: {reference:.0%}" if len(others) >= 2 else ""
        findings.append(_finding(
            "fit.outside", severity, m.box,
            f"{m.outside}/{m.total} điểm của vật ({m.ratio:.0%}) nằm ngoài box, nhiều nhất phía {m.side} "
            f"(tới {m.reach_m * 100:.0f} cm){relative}: box nhỏ hoặc lệch khỏi vật (ngưỡng {threshold:.0%})",
            excess, threshold, {"outside": m.outside, "total": m.total, "ratio": m.ratio, "track_median": reference,
                                "side": m.side, "reach_m": m.reach_m},
        ))
    return findings


def outside_finding(item: BoxPointSet, cfg: FitConfig) -> Finding | None:
    """`fit.outside` cho một box đứng riêng (so tỉ lệ tuyệt đối)."""
    measure = outside_measure(item, cfg)
    found = outside_findings([measure], cfg) if measure is not None else []
    return found[0] if found else None


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
) -> tuple[list[Finding], list[OutsideMeasure]]:
    """Luật box rỗng và box dư của một frame, cùng số đo cho luật điểm ngoài box (chốt sau khi có cả job,
    `outside_findings`). Box rỗng thì không xét hai luật kia."""
    findings: list[Finding] = []
    measures: list[OutsideMeasure] = []
    for item in items:
        if empty and (f := empty_finding(item, cfg)) is not None:
            findings.append(f)
            continue
        if outside and (m := outside_measure(item, cfg)) is not None:
            measures.append(m)
        if loose and (f := loose_finding(item, cfg, frame_points)) is not None:
            findings.append(f)
    return findings, measures
