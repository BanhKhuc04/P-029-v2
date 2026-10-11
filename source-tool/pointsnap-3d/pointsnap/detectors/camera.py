"""Bộ phát hiện đối chiếu box 3D với ảnh camera (việc C3, lớp 2 của Box Verifier).

Mỗi box nhìn thấy được chiếu lên các ảnh camera của frame (`core.camera`), so với vật mà model 2D nhận ra trên ảnh
(`vision.detector2d`: Mask R-CNN COCO, hoặc Grounding DINO + SAM 2.1 theo `camera.model`). Chỉ xét box thuộc nhóm vật
model ảnh nhận được, nằm gần trọn trong ảnh, đủ lớn, không quá xa và không bị box gần hơn che quá `max_occlusion`.

Khung chiếu của box 3D đúng vẫn lệch khung 2D một lượng ổn định theo vật (gương, phần khuất, góc nhìn), nên giống các luật
khác của PointSnap, so **độ trùng (IoU) của box với IoU ở các frame khác của chính track**:

1. `cam.mismatch` (Thông tin, đổi bằng `mismatch_severity`): tỉ lệ **mặt nạ** của vật trên ảnh (vật cùng nhóm trùng khung chiếu nhất) nằm ngoài khung
   chiếu 8 góc box cao hơn trung vị các frame khác của track quá `mask_rise_warning` → box lệch / nhỏ so với vật. Mặt nạ
   bám thân vật nên nhạy hơn IoU khung chữ nhật (đo trên 5 cảnh tuning: cùng mức báo nhầm, bắt box dời 0,5 m 24% so với
   14%, box co x0,7 15% so với 2%). Model 2D không thấy vật (xa, mờ, bị che) thì không có bằng chứng, không báo. Trong
   đánh giá đầy đủ, luật chỉ bắt thêm 4/400 lỗi chèn so với các luật LiDAR (phần lớn đã được `track.static_shift`,
   `track.jump` bắt) mà tăng báo nhầm, nên mặc định là bằng chứng phụ mức Thông tin.
2. `cam.class` (Cảnh báo, một mục mỗi track): ở đa số lần nhìn thấy, vật trên ảnh trùng khung chiếu thuộc **nhóm khác**
   (người / xe hai bánh / xe / động vật) với nhãn → nghi sai class.
3. `cam.missing` (Thông tin): model 2D thấy vật chắc chắn (điểm ≥ `missing_min_score`), có điểm LiDAR, nhưng không box 3D
   nào chiếu tới → nghi sót đối tượng. Không có box nên không gắn cờ được lên CVAT, chỉ hiện trong báo cáo.

Frame tối (trung vị độ sáng các ảnh camera < `min_brightness`: ban đêm) bị bỏ qua cho cả ba luật: trên 5 cảnh tuning, cảnh đêm
scene-1094 chiếm 31/52 mục báo nhầm của `cam.mismatch`. Xe đạp / xe máy có người ngồi thì model ảnh hay nhận là người,
nên `cam.class` không tính phiếu người ↔ xe hai bánh.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import TYPE_CHECKING, Sequence

import numpy as np

from pointsnap.core.camera import Projection, covered_fraction, iou_2d, project_box, project_points
from pointsnap.core.model import Cuboid, ErrorType, Finding, Severity, group_by_frame
from pointsnap.vision.detector2d import MASK_SCALE

if TYPE_CHECKING:
    from pointsnap.core.config import CameraConfig
    from pointsnap.vision.detector2d import Detections, Detector2D

RIDER_PAIR = {"person", "two_wheeler"}
"""Người ngồi trên xe hai bánh: model ảnh hay tách ra / nhận nhầm hai nhóm này, không coi là sai class."""
GROUP_VI = {"person": "người", "two_wheeler": "xe hai bánh", "vehicle": "xe", "animal": "động vật",
            "traffic_cone": "cọc tiêu", "barrier": "rào chắn"}


@dataclass(frozen=True)
class Observation:
    box: Cuboid
    channel: str
    iou: float  # IoU với vật cùng nhóm trùng nhất (0 nếu không có)
    overlap_any_same_group: bool
    mask_outside: float | None  # tỉ lệ mặt nạ của vật trùng nhất nằm ngoài khung chiếu
    best_other_group: str | None  # nhóm của vật trùng nhất (mọi nhóm) nếu IoU ≥ 0.5
    best_other_score: float


def _hull(points: np.ndarray) -> np.ndarray:
    pts = sorted(map(tuple, points))
    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
    lower, upper = [], []
    for p in pts:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= 0:
            lower.pop()
        lower.append(p)
    for p in reversed(pts):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= 0:
            upper.pop()
        upper.append(p)
    return np.array(lower[:-1] + upper[:-1])


def _inside_hull(xy: np.ndarray, hull: np.ndarray) -> np.ndarray:
    inside = np.ones(len(xy), dtype=bool)
    for i in range(len(hull)):
        a, b = hull[i], hull[(i + 1) % len(hull)]
        inside &= (b[0] - a[0]) * (xy[:, 1] - a[1]) - (b[1] - a[1]) * (xy[:, 0] - a[0]) >= 0
    return inside


def _mask_outside(mask: np.ndarray, polygon: np.ndarray) -> float | None:
    ys, xs = np.nonzero(mask)
    if len(xs) < 20:
        return None
    xy = np.column_stack([xs * MASK_SCALE + MASK_SCALE / 2, ys * MASK_SCALE + MASK_SCALE / 2])
    return float(1.0 - _inside_hull(xy, _hull(polygon)).mean())


def _observe(box: Cuboid, proj: Projection, det: Detections, group: str, cfg: CameraConfig, channel: str) -> Observation:
    groups = det.groups()
    best_iou, best_i, overlap = 0.0, None, False
    best_any, best_any_i = 0.0, None
    for i, (b, g, s) in enumerate(zip(det.boxes, groups, det.scores)):
        if g is None or s < cfg.min_score:
            continue
        iou = iou_2d(proj.box, tuple(b))
        if iou > best_any:
            best_any, best_any_i = iou, i
        if g == group:
            overlap |= iou >= 0.05
            if iou > best_iou:
                best_iou, best_i = iou, i
    mask_out = (_mask_outside(det.masks[best_i], proj.polygon)
                if best_i is not None and det.masks and best_iou >= cfg.min_mask_iou else None)
    other = groups[best_any_i] if best_any_i is not None and best_any >= 0.5 else None
    return Observation(box, channel, best_iou, overlap, mask_out, other,
                       float(det.scores[best_any_i]) if best_any_i is not None else 0.0)


def collect_observations(
    cuboids: Sequence[Cuboid], frames, detector: Detector2D, cfg: CameraConfig,
) -> tuple[list[Observation], list[Finding]]:
    """Quan sát của mọi box trên mọi ảnh, và các mục `cam.missing`."""
    observations: list[Observation] = []
    missing: list[Finding] = []
    supported = getattr(detector, "supported_groups", None)
    for frame, boxes in group_by_frame(c for c in cuboids if c.visible).items():
        data = frames.frame_data(frame)
        if data.sensor_to_world is None:
            continue
        world_points = None
        views = list(frames.camera_views(frame))
        detections = [detector.detect(view.path) for view in views]
        brightness = [d.brightness for d in detections if d.brightness is not None]
        if brightness and float(np.median(brightness)) < cfg.min_brightness:
            continue  # frame ban đêm: xét theo trung vị các camera vì ảnh hướng về đèn đường vẫn sáng
        for view, det in zip(views, detections):
            projections = [(b, project_box(b, data.sensor_to_world, view)) for b in boxes]
            projections = [(b, p) for b, p in projections if p is not None]
            for box, proj in projections:
                group = cfg.group_of(box.label)
                height = proj.box[3] - proj.box[1]
                if (group is None or (supported is not None and group not in supported)
                        or proj.inside_ratio < cfg.min_inside or proj.depth > cfg.max_depth_m
                        or height < cfg.min_box_px):
                    continue
                nearer = [p.box for b, p in projections if b is not box and p.depth < proj.depth - 0.5]
                if covered_fraction(proj.box, nearer) > cfg.max_occlusion:
                    continue
                observations.append(_observe(box, proj, det, group, cfg, view.channel))
            if world_points is None:
                pts = np.asarray(data.points, dtype=np.float64)[:, :3]
                mat = np.asarray(data.sensor_to_world)
                world_points = pts @ mat[:3, :3].T + mat[:3, 3]
            missing.extend(_missing(frame, view, det, [p for _, p in projections], world_points, cfg, supported))
    return observations, missing


def _missing(frame, view, det: Detections, projections: list[Projection], world_points, cfg: CameraConfig,
             supported=None):
    findings = []
    groups = det.groups()
    tracked = cfg.tracked_groups() if supported is None else cfg.tracked_groups() & set(supported)
    pixels = depth = None
    for b, g, s in zip(det.boxes, groups, det.scores):
        if g is None or g not in tracked or s < cfg.missing_min_score:
            continue
        if b[3] - b[1] < cfg.missing_min_px:
            continue
        box = tuple(float(v) for v in b)
        if any(iou_2d(box, p.box) >= 0.1 or covered_fraction(box, [p.box]) > 0.5 for p in projections):
            continue
        if pixels is None:
            pixels, depth = project_points(world_points, view)
        inside = ((depth > 1.0) & (depth < cfg.max_depth_m) & (pixels[:, 0] >= box[0]) & (pixels[:, 0] <= box[2])
                  & (pixels[:, 1] >= box[1]) & (pixels[:, 1] <= box[3]))
        if inside.sum() < cfg.missing_min_points:
            continue
        d = float(np.median(depth[inside]))
        findings.append(Finding(
            error_type=ErrorType.FIT, rule="cam.missing", severity=Severity.INFO, frame=frame,
            label=GROUP_VI.get(g, g),
            message=(f"Ảnh {view.channel} thấy {GROUP_VI.get(g, g)} (độ tin cậy {s:.0%}, cách ~{d:.0f} m, "
                     f"{int(inside.sum())} điểm LiDAR) nhưng không có box 3D nào: nghi sót đối tượng"),
            value=float(s), details={"camera": view.channel, "box_2d": [round(v, 1) for v in box], "depth_m": d},
        ))
    return findings


def camera_findings(observations: Sequence[Observation], cfg: CameraConfig, mismatch: bool = True,
                    wrong_class: bool = True) -> list[Finding]:
    by_track: dict[object, list[Observation]] = defaultdict(list)
    for o in observations:
        key = o.box.track_id if o.box.track_id is not None else ("shape", id(o.box))
        by_track[key].append(o)
    findings: list[Finding] = []
    for key, obs in by_track.items():
        if mismatch:
            findings.extend(_mismatch(obs, cfg))
        if wrong_class:
            findings.extend(_wrong_class(obs, cfg))
    return findings


def _mismatch(obs: list[Observation], cfg: CameraConfig) -> list[Finding]:
    measured = [o for o in obs if o.mask_outside is not None]
    worst: dict[int, tuple[float, Observation, float]] = {}
    for o in measured:
        others = [x.mask_outside for x in measured if x.box.frame != o.box.frame]
        if len(others) < cfg.min_track_observations:
            continue
        reference = float(np.median(others))
        rise = o.mask_outside - reference
        if rise <= cfg.mask_rise_warning:
            continue
        frame = o.box.frame
        if frame not in worst or rise > worst[frame][0]:
            worst[frame] = (rise, o, reference)
    return [Finding(
        error_type=ErrorType.FIT, rule="cam.mismatch", severity=Severity(cfg.mismatch_severity),
        frame=o.box.frame, label=o.box.label, track_id=o.box.track_id, source_id=o.box.source_id,
        value=rise, threshold=cfg.mask_rise_warning,
        message=(f"Box chiếu lên ảnh {o.channel}: {o.mask_outside:.0%} thân vật trên ảnh nằm ngoài khung box, các frame "
                 f"khác của track chỉ {reference:.0%} (IoU {o.iou:.0%}): box lệch hoặc nhỏ so với vật"),
        details={"camera": o.channel, "iou": o.iou, "mask_outside": o.mask_outside, "track_median": reference},
    ) for rise, o, reference in worst.values()]


def _wrong_class(obs: list[Observation], cfg: CameraConfig) -> list[Finding]:
    expected = cfg.group_of(obs[0].box.label)
    seen = [o for o in obs if o.best_other_group is not None]
    if len(seen) < cfg.class_min_observations:
        return []
    other = [o for o in seen if o.best_other_group != expected and o.best_other_score >= cfg.class_min_score
             and {o.best_other_group, expected} != RIDER_PAIR]
    if len(other) < cfg.class_vote * len(seen):
        return []
    votes: dict[str, int] = defaultdict(int)
    for o in other:
        votes[o.best_other_group] += 1
    group = max(votes, key=votes.get)
    first = min(other, key=lambda o: o.box.frame)
    return [Finding(
        error_type=ErrorType.ATTRIBUTE, rule="cam.class", severity=Severity.WARNING, frame=first.box.frame,
        label=first.box.label, track_id=first.box.track_id, source_id=first.box.source_id,
        value=len(other) / len(seen), threshold=cfg.class_vote,
        message=(f"Ảnh camera nhận vật là {GROUP_VI.get(group, group)} ở {len(other)}/{len(seen)} lần nhìn rõ, nhãn là "
                 f"{first.box.label}: nghi sai class"),
        details={"camera_group": group, "votes": dict(votes)},
    )]
