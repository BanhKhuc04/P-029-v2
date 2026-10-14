"""Conservative, read-only repair previews. This module never writes annotations."""
from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Sequence

from pointsnap.core.config import FloatingConfig
from pointsnap.core.model import Cuboid, Finding, Severity


class RepairPreviewError(ValueError):
    """Evidence is insufficient for this preview; keep manual editing."""


@dataclass(frozen=True)
class ZPreview:
    before: Cuboid
    after: Cuboid
    delta_z_m: float
    reference_frames: tuple[int, ...]
    reference_distance_m: float


def _number(value, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise RepairPreviewError(f"Thiếu số đo hữu hạn: {name}")
    return float(value)


def floating_z_preview(
    finding: Finding, box: Cuboid, boxes: Sequence[Cuboid], config: FloatingConfig,
    *, object_points: int,
) -> ZPreview:
    """Translate one keyframe in Z to the measured track clearance, not necessarily ground zero.

    This is an experimental suggestion, not human acceptance or an instruction to PATCH CVAT.
    Slopes, curbs, sparse evidence, absolute-only estimates and large shifts remain manual.
    """
    if finding.rule != "floating" or finding.severity not in (Severity.WARNING, Severity.ERROR):
        raise RepairPreviewError("Chỉ xem thử cho finding lơ lửng/lún có đủ bằng chứng")
    identity = lambda b: (b.frame, b.track_id, b.source_id, b.label)
    if identity(box) != (finding.frame, finding.track_id, finding.source_id, finding.label):
        raise RepairPreviewError("Finding không khớp đúng box và frame")
    if sum(identity(b) == identity(box) for b in boxes) != 1:
        raise RepairPreviewError("Box thiếu hoặc có định danh trùng trong snapshot")
    if box.track_id is None or not box.visible or not box.keyframe or box.label not in config.classes:
        raise RepairPreviewError("Cần keyframe nhìn thấy được và có track để đối chiếu")
    if type(object_points) is not int or object_points < 20:
        raise RepairPreviewError("Cần ít nhất 20 điểm của vật để đối chiếu gợi ý")
    for name in ("cvat_rx", "cvat_ry", "tilt_rad"):
        if abs(_number(box.attrs.get(name, 0.0), name)) > math.radians(1.5):
            raise RepairPreviewError("Có độ nghiêng của box trong hệ dữ liệu: giữ sửa tay trong bản thử đầu")
    d = finding.details or {}
    pitch = _number(d.get("pitch_deg"), "độ dốc")
    curb = _number(d.get("curb_step_m", 0.0) or 0.0, "bậc vỉa hè")
    if abs(pitch) > 1.5 or abs(curb) > 0.08 or d.get("curb_surface_near_bottom") or d.get("terrain_reference"):
        raise RepairPreviewError("Mặt đất dốc hoặc có nhiều mức: cần đối chiếu và sửa tay")
    n_ground = d.get("num_ground_points")
    if type(n_ground) is not int or n_ground < config.min_ground_points:
        raise RepairPreviewError("Thiếu điểm mặt đất")
    reference = _number(d.get("track_median_distance"), "trung vị track")
    distance = _number(d.get("distance"), "khoảng đáy–mặt đất")
    ground = _number(d.get("ground_z"), "mặt đất")
    bottom = _number(d.get("bottom_z"), "đáy box")
    offset = _number(finding.value, "độ lệch track")
    if not (math.isclose(bottom, box.bottom_z, abs_tol=1e-6, rel_tol=0)
            and math.isclose(distance, bottom - ground, abs_tol=1e-6, rel_tol=0)
            and math.isclose(offset, distance - reference, abs_tol=1e-6, rel_tol=0)):
        raise RepairPreviewError("Số đo và snapshot không khớp; cần quét lại")
    refs = d.get("reference_frames")
    if (not isinstance(refs, (list, tuple)) or any(type(f) is not int or f < 0 or f == box.frame for f in refs)
            or len(set(refs)) != len(refs) or len(refs) < max(2, config.min_track_boxes)):
        raise RepairPreviewError("Cần ít nhất hai frame tham chiếu độc lập trong track")
    for frame in refs:
        peers = [b for b in boxes if b.frame == frame and b.track_id == box.track_id and b.label == box.label]
        if len(peers) != 1 or not peers[0].visible or not peers[0].keyframe:
            raise RepairPreviewError("Frame tham chiếu không khớp snapshot")
    if not 0.02 <= abs(offset) <= 0.5:
        raise RepairPreviewError("Bản thử chỉ xem dịch Z từ 2 đến 50 cm; giữ sửa tay cho ca này")
    after = box.replace(center=(box.center[0], box.center[1], box.center[2] - offset))
    return ZPreview(box, after, -offset, tuple(refs), reference)
