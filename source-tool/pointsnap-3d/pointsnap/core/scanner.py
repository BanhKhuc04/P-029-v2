"""Bộ quét kiểm tra chất lượng nhãn 3D (việc A5).

Nối các bộ phát hiện của `pointsnap.detectors` (lơ lửng / lún, kích thước, đứt track; từ C1 thêm sai hướng box và box
lệch khỏi vật) và điều phối việc quét một job (việc A6). `check_size_manual_ranges` / `check_size_in_track` là luật kích thước cũ của A5, giữ để tương thích.
"""

from __future__ import annotations

import dataclasses
from types import SimpleNamespace
from typing import Callable, Iterable, Sequence

import numpy as np

from pointsnap.adapters.cvat.reader import JobData
from pointsnap.core.box_points import box_point_sets
from pointsnap.core.config import Config
from pointsnap.core.model import (
    Cuboid,
    ErrorType,
    Finding,
    FrameSource,
    Severity,
    group_by_frame,
    group_by_track,
)
from pointsnap.detectors.attributes import detect_attribute_errors
from pointsnap.detectors.fit import fit_findings_for_frame, loose_findings, outside_findings, overlap_findings
from pointsnap.detectors.floating import detect_floating_scene
from pointsnap.detectors.static import detect_static_errors
from pointsnap.detectors.heading import detect_heading_track, heading_points_findings, heading_points_measure
from pointsnap.detectors.size import detect_size
from pointsnap.detectors.track import detect_track_errors

DetectorFn = Callable[[JobData, Config, FrameSource | None], list[Finding]]


def check_size_manual_ranges(job: JobData, config: Config, frames: FrameSource | None = None) -> list[Finding]:
    """Kiểm tra kích thước các box thuộc class có khoảng giá trị thủ công (bus, trailer...)."""
    findings: list[Finding] = []
    ranges = config.size.manual_ranges

    for c in job.cuboids:
        if c.outside:
            continue
        cls_ranges = ranges.get(c.label)
        if not cls_ranges:
            continue

        dims_map = {"length": c.length, "width": c.width, "height": c.height}
        for dim_name, (min_v, max_v) in cls_ranges.items():
            val = dims_map[dim_name]
            dim_vi = {"length": "Chiều dài", "width": "Chiều rộng", "height": "Chiều cao"}[dim_name]
            if val < min_v:
                dev = min_v - val
                sev = Severity.ERROR if dev > 0.3 else Severity.WARNING
                findings.append(Finding(
                    error_type=ErrorType.SIZE,
                    rule="size.class_range",
                    severity=sev,
                    frame=c.frame,
                    label=c.label,
                    track_id=c.track_id,
                    source_id=c.source_id,
                    value=val,
                    threshold=min_v,
                    message=f"{dim_vi} ({val:.2f} m) nhỏ hơn ngưỡng tối thiểu ({min_v:.2f} m)",
                ))
            elif val > max_v:
                dev = val - max_v
                sev = Severity.ERROR if dev > 0.3 else Severity.WARNING
                findings.append(Finding(
                    error_type=ErrorType.SIZE,
                    rule="size.class_range",
                    severity=sev,
                    frame=c.frame,
                    label=c.label,
                    track_id=c.track_id,
                    source_id=c.source_id,
                    value=val,
                    threshold=max_v,
                    message=f"{dim_vi} ({val:.2f} m) vượt quá ngưỡng tối đa ({max_v:.2f} m)",
                ))

    return findings


def check_size_in_track(job: JobData, config: Config, frames: FrameSource | None = None) -> list[Finding]:
    """Kiểm tra kích thước dao động bất thường trong cùng một track (kiểu 2)."""
    findings: list[Finding] = []
    cfg = config.size.in_track
    tracks = group_by_track(job.cuboids)

    for tid, boxes in tracks.items():
        active = [b for b in boxes if not b.outside]
        if len(active) < cfg.min_keyframes:
            continue
        first_box = active[0]
        if first_box.label in cfg.excluded_classes:
            continue

        lengths = np.array([b.length for b in active])
        widths = np.array([b.width for b in active])
        heights = np.array([b.height for b in active])

        med_l, med_w, med_h = float(np.median(lengths)), float(np.median(widths)), float(np.median(heights))

        for b in active:
            for dim_name, val, med in (("length", b.length, med_l), ("width", b.width, med_w), ("height", b.height, med_h)):
                diff = abs(val - med)
                rel = diff / max(med, 1e-4)
                dim_vi = {"length": "Chiều dài", "width": "Chiều rộng", "height": "Chiều cao"}[dim_name]

                is_err = diff > cfg.error_abs_m or rel > cfg.error_rel
                is_warn = diff > cfg.warning_abs_m or rel > cfg.warning_rel

                if is_err:
                    msg = f"{dim_vi} ({val:.2f} m) lệch lớn so với trung vị track ({med:.2f} m, lệch {diff*100:.0f} cm)"
                    if rel > cfg.suspect_id_rel:
                        msg += " — nghi nhầm ID"
                    findings.append(Finding(
                        error_type=ErrorType.SIZE,
                        rule="size.in_track",
                        severity=Severity.ERROR,
                        frame=b.frame,
                        label=b.label,
                        track_id=b.track_id,
                        source_id=b.source_id,
                        value=diff,
                        threshold=cfg.error_abs_m,
                        message=msg,
                    ))
                elif is_warn:
                    findings.append(Finding(
                        error_type=ErrorType.SIZE,
                        rule="size.in_track",
                        severity=Severity.WARNING,
                        frame=b.frame,
                        label=b.label,
                        track_id=b.track_id,
                        source_id=b.source_id,
                        value=diff,
                        threshold=cfg.warning_abs_m,
                        message=f"{dim_vi} ({val:.2f} m) lệch so với trung vị track ({med:.2f} m, lệch {diff*100:.0f} cm)",
                    ))

    return findings


def check_floating(job: JobData, config: Config, frames: FrameSource | None = None) -> list[Finding]:
    """Lơ lửng / lún (B3, `detectors.floating`), so với các frame khác của track. Cần point cloud."""
    if frames is None:
        return []
    return detect_floating_scene(job.cuboids, frames, config.floating)


def check_size(job: JobData, config: Config, frames: FrameSource | None = None) -> list[Finding]:
    """Sai kích thước theo class và trong track (B4, `detectors.size`)."""
    findings = detect_size(job.cuboids, config.size)
    if frames is not None:
        from pointsnap.detectors.size import relax_filled_oversize

        findings = relax_filled_oversize(findings, job.cuboids, frames, config.size.cargo_classes,
                                        class_key=lambda box: _typed_label(box, config))
    return findings


def check_track(job: JobData, config: Config, frames: FrameSource | None = None) -> list[Finding]:
    """Đứt track (B5, `detectors.track`). Có `frames` thì dùng pose xe thu và thời điểm thật của từng frame."""
    sensor_to_world, timestamps = _poses(job, frames)
    return detect_track_errors(job.cuboids, config.track, sensor_to_world, timestamps,
                               stop_frame=getattr(job, "stop_frame", None),
                               class_key=lambda box: _typed_label(box, config))
def _poses(job: JobData, frames: FrameSource | None):
    if frames is None:
        return None, None
    data = {f: frames.frame_data(f, with_points=False) for f in sorted({c.frame for c in job.cuboids})}
    sensor_to_world = {f: d.sensor_to_world for f, d in data.items() if d.sensor_to_world is not None} or None
    timestamps = {f: d.timestamp for f, d in data.items() if d.timestamp is not None} or None
    return sensor_to_world, timestamps


def check_heading(job: JobData, config: Config, frames: FrameSource | None = None) -> list[Finding]:
    """Sai hướng box theo track (C1, `detectors.heading`): lật hướng giữa hai keyframe, lệch hướng chuyển động."""
    sensor_to_world, timestamps = _poses(job, frames)
    return detect_heading_track(job.cuboids, config.heading, config.track.keyframe_interval_s, sensor_to_world,
                                timestamps, flip=config.rules.heading_flip, motion=config.rules.heading_motion)


def _typed_label(box: Cuboid, config: Config) -> str:
    """`Class/giá trị thuộc tính phân loại` (size.key_attributes, vd `Vehicle/truck`), hoặc `Class` nếu không có."""
    attr = config.size.key_attributes.get(box.label)
    value = box.attrs.get(attr) if attr else None
    return f"{box.label}/{value}" if value not in (None, "") else box.label


def check_box_points(job: JobData, config: Config, frames: FrameSource | None = None) -> list[Finding]:
    """Luật dựa trên điểm LiDAR của từng vật (C1): trục box so với cụm điểm, box rỗng / nhỏ / lệch / dư; box chồng nhau.

    Box chồng nhau không cần point cloud nên vẫn chạy khi không có `frames`.
    """
    r = config.rules
    findings: list[Finding] = []
    measures = []
    outside = []
    loose = []
    for frame, boxes in group_by_frame(c for c in job.cuboids if c.visible).items():
        if r.fit_overlap:
            findings.extend(overlap_findings(boxes, config.fit, typed=lambda b: _typed_label(b, config)))
        if frames is None or not (r.heading_points or r.fit_empty or r.fit_outside or r.fit_loose):
            continue
        points = frames.frame_data(frame).points
        items = box_point_sets(points, boxes, margin=config.fit.outside_margin_m,
                               clearance=config.fit.ground_clearance_m, margin_rel=config.fit.outside_margin_rel)
        frame_findings, frame_outside, frame_loose = fit_findings_for_frame(
            items, config.fit, points[:, :3], empty=r.fit_empty, outside=r.fit_outside, loose=r.fit_loose)
        findings.extend(frame_findings)
        outside.extend(frame_outside)
        loose.extend(frame_loose)
        if r.heading_points:
            measures.extend((item.box, dev) for item in items
                            if (dev := heading_points_measure(item, config.heading.points)) is not None)
    findings.extend(heading_points_findings(measures, config.heading.points))
    if r.fit_outside:
        findings.extend(outside_findings(outside, config.fit))
    if r.fit_loose:
        findings.extend(loose_findings(loose, config.fit))
    return findings


def check_static(job: JobData, config: Config, frames: FrameSource | None = None) -> list[Finding]:
    """Box dịch / xoay của vật đứng yên trong hệ toàn cục (C3, `detectors.static`). Cần pose xe thu."""
    sensor_to_world, _ = _poses(job, frames)
    return detect_static_errors(job.cuboids, config.static, sensor_to_world, shift=config.rules.track_static_shift,
                                rotate=config.rules.heading_static)


_DETECTORS: dict = {}


def _detector(model: str = "maskrcnn"):
    if model not in _DETECTORS:
        from pointsnap.vision.detector2d import Detector2D

        _DETECTORS[model] = Detector2D(model=model)
    return _DETECTORS[model]


def check_camera(job: JobData, config: Config, frames: FrameSource | None = None) -> list[Finding]:
    """Đối chiếu box 3D với ảnh camera (C3, `detectors.camera`). Cần ảnh camera và PyTorch; không có thì bỏ qua."""
    if frames is None or not hasattr(frames, "camera_views") or not config.camera.active():
        return []
    from pointsnap.detectors.camera import camera_findings, collect_observations

    r = config.rules
    effective = config.camera.effective_model()
    try:
        detector = _detector(effective)
        observations, missing = collect_observations(job.cuboids, frames, detector, config.camera)
        findings = camera_findings(observations,config.camera,mismatch=r.cam_mismatch,wrong_class=r.cam_class)
        if r.cam_sparse:
            from pointsnap.detectors.camera import sparse_unconfirmed
            findings += sparse_unconfirmed(job.cuboids,frames,detector,config.camera)
        findings += missing if r.cam_missing else []
        reason = getattr(detector,"fallback_reason",None)
        if config.camera.model == "hybrid" and effective != "hybrid":
            reason = "hybrid chỉ chạy COCO vì thiếu dependency DINO/SAM"
        if reason:
            findings.append(_camera_no_evidence(job,reason))
        return findings
    except (OSError, ImportError, RuntimeError) as exc:
        return [_camera_no_evidence(job,f"Model/ảnh camera chưa dùng được: {exc}")]


def _camera_no_evidence(job, message: str) -> Finding:
    return Finding(error_type=ErrorType.FIT,rule="camera.no_evidence",severity=Severity.INFO,
                   frame=min((b.frame for b in job.cuboids),default=0),label="Camera",
                   message="Kiểm tra camera một phần: "+message)


def check_missing(job: JobData, config: Config, frames: FrameSource | None = None) -> list[Finding]:
    """Sót đối tượng bằng LiDAR (C7, `detectors.missing`). Cần point cloud và pose xe thu."""
    if frames is None:
        return []
    from pointsnap.detectors.missing import detect_missing_objects

    use_camera = hasattr(frames,"camera_views") and config.camera.active()
    try:
        detector = _detector(config.camera.effective_model()) if use_camera else None
        findings = detect_missing_objects(job.cuboids,frames,config.missing,detector,config.camera)[0]
        reason = getattr(detector,"fallback_reason",None) if detector is not None else None
        if reason:
            findings.append(_camera_no_evidence(job,reason))
        return findings
    except (OSError,ImportError,RuntimeError) as exc:
        if not use_camera:
            raise
        # ponytail: recompute LiDAR on camera failure; split detector stages if this recovery becomes costly.
        findings = detect_missing_objects(job.cuboids,frames,config.missing,None,config.camera)[0]
        return findings+[_camera_no_evidence(job,f"Camera chưa xác nhận vật đứng yên: {exc}")]


def check_critic(job: JobData, config: Config, frames: FrameSource | None = None) -> list[Finding]:
    """Box Critic (C3, lớp 3): chỉ chạy khi guideline khai `critic.model` và có PyTorch."""
    if frames is None or not config.critic.model:
        return []
    from pointsnap.critic import available

    if not available():
        return []
    from pointsnap.critic import critic_findings

    return critic_findings(job.cuboids, frames, config.critic)


def check_attributes(job: JobData, config: Config, frames: FrameSource | None = None) -> list[Finding]:
    """Thiếu / sai thuộc tính theo spec của dự án (C2, `detectors.attributes`)."""
    from pointsnap.detectors.attributes import detect_attribute_height, detect_rider_state, detect_spec_geometry

    sensor_to_world, timestamps = _poses(job, frames)
    return (detect_attribute_errors(job.cuboids, config.spec) + detect_attribute_height(job.cuboids, config.spec)
            + detect_spec_geometry(job.cuboids, config.spec)
            + detect_rider_state(job.cuboids, config.spec, sensor_to_world, config.track.keyframe_interval_s, timestamps))


_RULE_SWITCH = {
    "track.reuse_id": "track_reuse_id", "track.occluded_long": "track_occluded_long", "track.id_swap": "track_id_swap",
    "attr.missing": "attr_missing", "attr.invalid": "attr_invalid", "attr.height": "attr_height",
    "spec.inside": "spec_inside", "spec.rider_double": "spec_rider_double", "lidar.missing": "lidar_missing",
    "attr.rider_state": "attr_rider_state", "cam.sparse": "cam_sparse",
    "track.static_shift": "track_static_shift", "heading.static": "heading_static",
    "cam.mismatch": "cam_mismatch", "cam.class": "cam_class", "cam.missing": "cam_missing",
    "critic.box": "critic_box",
    "heading.flip": "heading_flip", "heading.motion": "heading_motion", "heading.points": "heading_points",
    "fit.empty": "fit_empty", "fit.outside": "fit_outside", "fit.loose": "fit_loose", "fit.overlap": "fit_overlap",
}


def is_rule_enabled(rule: str, config: Config) -> bool:
    """Kiểm tra một rule có được bật trong config.rules không."""
    if rule in ("floating", "floating.no_evidence"):
        return bool(config.rules.floating)
    if rule in ("size.class_range", "size.manual_range"):
        return bool(config.rules.size_class_range)
    if rule in ("size.in_track", "size.in_track_manual"):
        return bool(config.rules.size_in_track)
    if rule == "track.jump":
        return bool(config.rules.track_jump)
    if rule == "track.split_id":
        return bool(config.rules.track_split_id)
    if rule == "track.long_interpolation":
        return bool(config.rules.track_long_interpolation and config.track.long_interpolation.enabled)
    switch = _RULE_SWITCH.get(rule)
    return True if switch is None else bool(getattr(config.rules, switch))


DEFAULT_DETECTORS: Sequence[DetectorFn] = (
    check_floating,
    check_size,
    check_track,
    check_heading,
    check_box_points,
    check_attributes,
    check_static,
    check_camera,
    check_critic,
    check_missing,
)


def scan_cuboids(
    job: JobData | Iterable[Cuboid],
    config: Config,
    frames: FrameSource | None = None,
    detectors: Sequence[DetectorFn] | None = None,
) -> list[Finding]:
    """Chạy toàn bộ các bộ phát hiện trên các box của job (hoặc danh sách box) và trả về danh sách finding.

    `frames` cung cấp point cloud và pose theo frame (`ManifestFrames` khi quét job CVAT, `NuScenesFrames` khi quét
    thẳng nuScenes).
    """
    if not hasattr(job, "cuboids"):
        job = SimpleNamespace(cuboids=list(job))

    if detectors is not None:
        active_detectors = list(detectors)
    else:
        active_detectors = []
        r = config.rules
        if r.floating:
            active_detectors.append(check_floating)
        if r.size_class_range or r.size_in_track:
            active_detectors.append(check_size)
        if (r.track_jump or r.track_split_id or r.track_long_interpolation or r.track_reuse_id
                or r.track_occluded_long or r.track_id_swap):
            active_detectors.append(check_track)
        if r.heading_flip or r.heading_motion:
            active_detectors.append(check_heading)
        if r.heading_points or r.fit_empty or r.fit_outside or r.fit_loose or r.fit_overlap:
            active_detectors.append(check_box_points)
        if (r.attr_missing or r.attr_invalid or r.attr_height or r.spec_inside or r.spec_rider_double
                or r.attr_rider_state):
            active_detectors.append(check_attributes)
        if r.track_static_shift or r.heading_static:
            active_detectors.append(check_static)
        if r.cam_mismatch or r.cam_class or r.cam_missing or r.cam_sparse:
            active_detectors.append(check_camera)
        if r.critic_box:
            active_detectors.append(check_critic)
        if r.lidar_missing:
            active_detectors.append(check_missing)

    from pointsnap.core.context import DetectionContext
    from pointsnap.detectors.base import BaseDetector

    ctx = DetectionContext.from_job(job, config, frames)
    findings: list[Finding] = []
    for detector in active_detectors:
        if isinstance(detector, BaseDetector):
            findings.extend(detector(ctx))
        else:
            findings.extend(detector(job, config, frames))

    filtered = [f for f in findings if is_rule_enabled(f.rule, config)]
    filtered = apply_evidence_gate(filtered, job.cuboids, config, frames)
    return sorted(filtered, key=lambda f: f.sort_key())


def apply_evidence_gate(
    findings: list[Finding], cuboids: Iterable[Cuboid], config: Config, frames: FrameSource | None,
) -> list[Finding]:
    """Hạ Cảnh báo / Lỗi của các luật trong `config.evidence.rules` xuống Thông tin khi box (ở frame của finding) có ít hơn
    `evidence.min_points` điểm của vật: người duyệt không kiểm được trên point cloud (chấm tay held-out 13/10)."""
    gate = config.evidence
    if gate.min_points <= 0 or frames is None:
        return findings
    targets = [i for i, f in enumerate(findings)
               if f.rule in gate.rules and f.severity in (Severity.WARNING, Severity.ERROR)]
    if not targets:
        return findings
    by_frame = group_by_frame(c for c in cuboids if c.visible)
    counts: dict[tuple[int, int | None, str], int] = {}
    for frame in sorted({findings[i].frame for i in targets}):
        boxes = by_frame.get(frame, [])
        if not boxes:
            continue
        items = box_point_sets(frames.frame_data(frame).points, boxes, margin=config.fit.outside_margin_m,
                               clearance=config.fit.ground_clearance_m, margin_rel=config.fit.outside_margin_rel)
        for item in items:
            counts[(frame, item.box.track_id if item.box.track_id is not None else item.box.source_id,
                    item.box.label)] = item.num_object_points
    result = list(findings)
    for i in targets:
        f = findings[i]
        n = counts.get((f.frame, f.track_id if f.track_id is not None else f.source_id, f.label))
        if n is None or n >= gate.min_points:
            continue
        result[i] = dataclasses.replace(
            f, severity=Severity.INFO,
            message=f"Ít điểm LiDAR ({n} điểm, cần ≥ {gate.min_points}): chưa đủ bằng chứng để kết luận. {f.message}",
            details={**(f.details or {}), "evidence_points": n, "evidence_severity": f.severity.value},
        )
    return result


def scan_coverage_gaps(job: JobData, config: Config, frames: FrameSource | None) -> list[str]:
    """Thiếu dữ liệu cho các luật đang bật; không coi nguồn frame có mặt là đã đủ pose.

    Kiểm tra bảo thủ ở cấp job; không chứng nhận độ chính xác của detector hay mọi box.
    Lỗi đọc frame được chuyển cho caller để lần quét thất bại, không trả ĐẠT.
    """
    cloud_rules = ("floating", "heading_points", "fit_empty", "fit_outside", "fit_loose", "critic_box")
    pose_rules = ("track_jump", "track_split_id", "track_long_interpolation", "heading_flip", "heading_motion",
                  "attr_rider_state", "track_static_shift", "heading_static")
    gaps: list[str] = []
    enabled_cloud = [name for name in cloud_rules if getattr(config.rules, name)
                     and (name != "critic_box" or config.critic.model)]
    camera_rules = any(getattr(config.rules,name) for name in ("cam_mismatch","cam_class","cam_missing","cam_sparse"))
    if config.camera.enabled == "true" and camera_rules:
        if not config.camera.active():
            gaps.append("Kiểm tra một phần: thiếu runtime model camera đã bật")
        if frames is None or not hasattr(frames,"camera_views"):
            gaps.append("Kiểm tra một phần: thiếu ảnh/calibration camera đã bật")
        else:
            visible_frames = sorted({c.frame for c in job.cuboids if c.visible and c.keyframe})
            missing_views = [f for f in visible_frames if not frames.camera_views(f)]
            missing_pose = [f for f in visible_frames if frames.frame_data(f,with_points=False).sensor_to_world is None]
            if missing_views or missing_pose:
                gaps.append(f"Kiểm tra một phần: thiếu ảnh/pose camera ở {len(set(missing_views+missing_pose))} frame")
    if config.rules.critic_box and config.critic.model and any(c.visible and c.keyframe for c in job.cuboids):
        from pointsnap.critic import available
        if not available():
            gaps.append("Kiểm tra một phần: thiếu PyTorch cho luật critic_box")
    if frames is None and enabled_cloud and any(c.visible for c in job.cuboids):
        gaps.append("Kiểm tra một phần: thiếu point cloud cho luật " + ", ".join(enabled_cloud))
    elif frames is not None and enabled_cloud:
        visible_frames = sorted({c.frame for c in job.cuboids if c.visible})
        empty = [frame for frame in visible_frames if len(frames.frame_data(frame, with_points=True).points) == 0]
        if empty:
            gaps.append(f"Kiểm tra một phần: point cloud rỗng ở {len(empty)} frame cho luật " + ", ".join(enabled_cloud))

    enabled_pose = [name for name in pose_rules if getattr(config.rules, name)
                    and (name != "track_long_interpolation" or config.track.long_interpolation.enabled)
                    and (name != "attr_rider_state" or (config.spec.rider_state and any(
                        c.visible and c.label == config.spec.rider_state["class"] for c in job.cuboids)))]
    tracked_frames = sorted({c.frame for c in job.cuboids if c.visible and c.track_id is not None})
    if enabled_pose and tracked_frames:
        missing = [frame for frame in tracked_frames
                   if frames is None or frames.frame_data(frame, with_points=False).sensor_to_world is None]
        if missing:
            gaps.append(f"Kiểm tra một phần: thiếu pose ở {len(missing)} frame cho luật " + ", ".join(enabled_pose))
    return gaps

def actionable(findings: Iterable[Finding]) -> list[Finding]:
    """Finding mức Lỗi / Cảnh báo: những mục được gắn cờ lên CVAT và tính ở `gate`."""
    return [f for f in findings if f.severity is not Severity.INFO]
