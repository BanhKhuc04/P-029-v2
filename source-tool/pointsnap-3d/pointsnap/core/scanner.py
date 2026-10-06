"""Bộ quét kiểm tra chất lượng nhãn 3D (việc A5).

Tập hợp các bộ phát hiện (size, track, ground/floating) và điều phối việc quét một job.
"""

from __future__ import annotations

from typing import Callable, Iterable, Sequence

import numpy as np

from pointsnap.adapters.cvat.reader import JobData, ManifestFrames
from pointsnap.core.config import Config
from pointsnap.core.model import (
    Cuboid,
    ErrorType,
    Finding,
    Severity,
    group_by_track,
)

DetectorFn = Callable[[JobData, Config, ManifestFrames | None], list[Finding]]


def check_size_manual_ranges(job: JobData, config: Config, manifest: ManifestFrames | None = None) -> list[Finding]:
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


def check_size_in_track(job: JobData, config: Config, manifest: ManifestFrames | None = None) -> list[Finding]:
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


DEFAULT_DETECTORS: Sequence[DetectorFn] = (
    check_size_manual_ranges,
    check_size_in_track,
)


def scan_cuboids(
    job: JobData,
    config: Config,
    manifest: ManifestFrames | None = None,
    detectors: Sequence[DetectorFn] | None = None,
) -> list[Finding]:
    """Chạy toàn bộ các bộ phát hiện trên các box của job và trả về danh sách finding."""
    active_detectors = detectors if detectors is not None else DEFAULT_DETECTORS
    findings: list[Finding] = []
    for detector in active_detectors:
        findings.extend(detector(job, config, manifest))
    return sorted(findings, key=lambda f: f.sort_key())
