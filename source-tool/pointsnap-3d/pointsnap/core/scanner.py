"""Bộ quét kiểm tra chất lượng nhãn 3D (việc A5).

Nối ba bộ phát hiện của `pointsnap.detectors` (lơ lửng / lún, kích thước, đứt track) và điều phối việc quét một job
(việc A6). `check_size_manual_ranges` / `check_size_in_track` là luật kích thước cũ của A5, giữ để tương thích.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Callable, Iterable, Sequence

import numpy as np

from pointsnap.adapters.cvat.reader import JobData
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
from pointsnap.detectors.floating import detect_floating
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
    """Lơ lửng / lún (B3, `detectors.floating`). Cần point cloud: không có `frames` thì không chạy."""
    if frames is None:
        return []
    classes = set(config.floating.classes)
    findings: list[Finding] = []
    for frame, boxes in group_by_frame(c for c in job.cuboids if not c.outside).items():
        if any(b.label in classes for b in boxes):
            findings.extend(detect_floating(boxes, frames.frame_data(frame).points, config.floating))
    return findings


def check_size(job: JobData, config: Config, frames: FrameSource | None = None) -> list[Finding]:
    """Sai kích thước theo class và trong track (B4, `detectors.size`)."""
    return detect_size(job.cuboids, config.size)


def check_track(job: JobData, config: Config, frames: FrameSource | None = None) -> list[Finding]:
    """Đứt track (B5, `detectors.track`). Có `frames` thì dùng pose xe thu và thời điểm thật của từng frame."""
    sensor_to_world = timestamps = None
    if frames is not None:
        data = {f: frames.frame_data(f, with_points=False) for f in sorted({c.frame for c in job.cuboids})}
        sensor_to_world = {f: d.sensor_to_world for f, d in data.items() if d.sensor_to_world is not None} or None
        timestamps = {f: d.timestamp for f, d in data.items() if d.timestamp is not None} or None
    return detect_track_errors(job.cuboids, config.track, sensor_to_world, timestamps)


DEFAULT_DETECTORS: Sequence[DetectorFn] = (
    check_floating,
    check_size,
    check_track,
)


def scan_cuboids(
    job: JobData | Iterable[Cuboid],
    config: Config,
    frames: FrameSource | None = None,
    detectors: Sequence[DetectorFn] | None = None,
) -> list[Finding]:
    """Chạy toàn bộ các bộ phát hiện trên các box của job (hoặc danh sách box) và trả về danh sách finding.

    `frames` cung cấp point cloud và pose theo frame (`ManifestFrames` khi quét job CVAT, `NuScenesFrames` khi quét
    thẳng nuScenes). Không có thì bỏ luật lơ lửng / lún và luật đứt track dùng tọa độ của từng frame.
    """
    if not hasattr(job, "cuboids"):
        job = SimpleNamespace(cuboids=list(job))
    active_detectors = detectors if detectors is not None else DEFAULT_DETECTORS
    findings: list[Finding] = []
    for detector in active_detectors:
        findings.extend(detector(job, config, frames))
    return sorted(findings, key=lambda f: f.sort_key())


def actionable(findings: Iterable[Finding]) -> list[Finding]:
    """Finding mức Lỗi / Cảnh báo: những mục được gắn cờ lên CVAT và tính ở `gate`."""
    return [f for f in findings if f.severity is not Severity.INFO]