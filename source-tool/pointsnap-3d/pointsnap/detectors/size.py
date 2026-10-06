"""Bộ phát hiện sai kích thước (việc B4).

Hai kiểu phát hiện:
1. Kiểu 1 (`size.class_range`): So sánh (l, w, h) với khoảng [p1, p99] của class.
   - Cảnh báo nếu ngoài [p1 - 5%, p99 + 5%].
   - Lỗi nếu ngoài [p1 - 15%, p99 + 15%].
2. Kiểu 2 (`size.in_track`): Kích thước một keyframe lệch so với trung vị của track.
   - Bỏ qua class người đi bộ (pedestrian).
   - Cảnh báo nếu lệch > max(10 cm, 5%).
   - Lỗi nếu lệch > max(30 cm, 15%).
   - Lệch > 30%: ghi chú "nghi nhầm ID".
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Iterable, Mapping, Sequence

import numpy as np

from pointsnap.core.model import Cuboid, ErrorType, Finding, Severity, group_by_track

if TYPE_CHECKING:
    from pointsnap.core.config import SizeConfig

DIM_NAMES = ("length", "width", "height")
DIM_VI = {"length": "chiều dài", "width": "chiều rộng", "height": "chiều cao"}

# Thống kê phân vị [p1, p99] tính từ 5 cảnh tinh chỉnh nuScenes v1.0-mini
DEFAULT_CLASS_RANGES: dict[str, dict[str, tuple[float, float]]] = {
    "car": {"length": (3.48, 5.76), "width": (1.60, 2.38), "height": (1.40, 2.30)},
    "truck": {"length": (4.54, 10.20), "width": (1.79, 2.88), "height": (1.72, 3.96)},
    "bus": {"length": (6.91, 13.82), "width": (2.56, 3.52), "height": (2.81, 3.61)},
    "trailer": {"length": (1.79, 14.01), "width": (2.17, 2.33), "height": (3.31, 3.89)},
    "construction_vehicle": {"length": (3.71, 7.56), "width": (2.11, 3.02), "height": (2.03, 2.92)},
    "pedestrian": {"length": (0.37, 1.04), "width": (0.43, 0.98), "height": (1.35, 2.00)},
    "motorcycle": {"length": (1.81, 2.40), "width": (0.56, 1.20), "height": (1.34, 1.93)},
    "bicycle": {"length": (1.34, 2.07), "width": (0.43, 0.93), "height": (1.03, 1.93)},
    "traffic_cone": {"length": (0.30, 0.64), "width": (0.29, 1.21), "height": (0.51, 1.31)},
    "barrier": {"length": (0.40, 0.76), "width": (1.79, 3.59), "height": (0.89, 1.34)},
}


def compute_class_ranges(
    cuboids: Iterable[Cuboid],
    percentile_low: float = 1.0,
    percentile_high: float = 99.0,
    min_instances: int = 20,
    manual_ranges: Mapping[str, Mapping[str, tuple[float, float]]] | None = None,
) -> dict[str, dict[str, tuple[float, float]]]:
    """Tính khoảng kích thước [p_low, p_high] cho từng class từ tập box.

    Class có ít hơn `min_instances` box sẽ dùng `manual_ranges`.
    """
    by_label: dict[str, list[tuple[float, float, float]]] = {}
    for c in cuboids:
        if not c.outside:
            by_label.setdefault(c.label, []).append(c.dims)

    ranges: dict[str, dict[str, tuple[float, float]]] = {}
    for label, dims_list in by_label.items():
        if len(dims_list) < min_instances and manual_ranges and label in manual_ranges:
            ranges[label] = dict(manual_ranges[label])
            continue

        arr = np.array(dims_list)
        class_dict = {}
        for idx, dim_name in enumerate(DIM_NAMES):
            p_lo = float(np.percentile(arr[:, idx], percentile_low))
            p_hi = float(np.percentile(arr[:, idx], percentile_high))
            class_dict[dim_name] = (p_lo, p_hi)
        ranges[label] = class_dict

    # Bổ sung các class có trong manual_ranges nếu tập box chưa có
    if manual_ranges:
        for label, m_dict in manual_ranges.items():
            if label not in ranges:
                ranges[label] = dict(m_dict)

    return ranges


def get_resolved_class_ranges(
    config: SizeConfig,
    custom_ranges: Mapping[str, Mapping[str, tuple[float, float]]] | None = None,
) -> dict[str, dict[str, tuple[float, float]]]:
    """Kết hợp default ranges và manual_ranges trong config."""
    resolved = {label: dict(dim_dict) for label, dim_dict in DEFAULT_CLASS_RANGES.items()}
    if config.manual_ranges:
        for label, manual_dict in config.manual_ranges.items():
            resolved.setdefault(label, {}).update(manual_dict)
    if custom_ranges:
        for label, c_dict in custom_ranges.items():
            resolved.setdefault(label, {}).update(c_dict)
    return resolved


def detect_size_class_range_for_box(
    cuboid: Cuboid,
    config: SizeConfig,
    class_ranges: Mapping[str, Mapping[str, tuple[float, float]]],
) -> list[Finding]:
    """Kiểm tra kiểu 1: kích thước bất thường so với class."""
    if cuboid.outside or cuboid.label not in class_ranges:
        return []

    c_cfg = config.class_range
    warn_m = c_cfg.warning_margin
    err_m = c_cfg.error_margin

    ranges = class_ranges[cuboid.label]
    findings: list[Finding] = []

    for dim_name, val in zip(DIM_NAMES, cuboid.dims):
        if dim_name not in ranges:
            continue
        p_lo, p_hi = ranges[dim_name]

        warn_min = p_lo * (1.0 - warn_m)
        warn_max = p_hi * (1.0 + warn_m)
        err_min = p_lo * (1.0 - err_m)
        err_max = p_hi * (1.0 + err_m)

        severity: Severity | None = None
        threshold: float | None = None
        bound_type: str = ""

        if val < err_min:
            severity = Severity.ERROR
            threshold = err_min
            bound_type = "nhỏ"
        elif val > err_max:
            severity = Severity.ERROR
            threshold = err_max
            bound_type = "lớn"
        elif val < warn_min:
            severity = Severity.WARNING
            threshold = warn_min
            bound_type = "nhỏ"
        elif val > warn_max:
            severity = Severity.WARNING
            threshold = warn_max
            bound_type = "lớn"

        if severity is not None and threshold is not None:
            vi_name = DIM_VI[dim_name]
            msg = (
                f"{vi_name.capitalize()} {val:.2f} m {bound_type} bất thường so với class {cuboid.label} "
                f"(khoảng chuẩn [{p_lo:.2f}, {p_hi:.2f}] m)"
            )
            findings.append(
                Finding(
                    error_type=ErrorType.SIZE,
                    rule="size.class_range",
                    severity=severity,
                    frame=cuboid.frame,
                    label=cuboid.label,
                    track_id=cuboid.track_id,
                    source_id=cuboid.source_id,
                    message=msg,
                    value=float(val),
                    threshold=float(threshold),
                    details={
                        "dimension": dim_name,
                        "class_range": (p_lo, p_hi),
                        "bound_type": bound_type,
                    },
                )
            )

    return findings


def detect_size_in_track(
    track_boxes: Sequence[Cuboid],
    config: SizeConfig,
) -> list[Finding]:
    """Kiểm tra kiểu 2: dao động kích thước trong cùng track."""
    if not track_boxes:
        return []

    label = track_boxes[0].label
    t_cfg = config.in_track

    # Bỏ qua class người đi bộ do tư thế thay đổi
    if label in t_cfg.excluded_classes:
        return []

    # Lọc các box hợp lệ (không outside)
    active_boxes = [b for b in track_boxes if not b.outside]
    if len(active_boxes) < t_cfg.min_keyframes:
        return []

    dims_arr = np.array([b.dims for b in active_boxes])
    medians = np.median(dims_arr, axis=0)  # (length_med, width_med, height_med)

    findings: list[Finding] = []

    for b in active_boxes:
        for idx, (dim_name, val, med) in enumerate(zip(DIM_NAMES, b.dims, medians)):
            diff = abs(val - med)
            rel = diff / med if med > 0 else 0.0

            warn_thresh = max(t_cfg.warning_abs_m, t_cfg.warning_rel * med)
            err_thresh = max(t_cfg.error_abs_m, t_cfg.error_rel * med)

            severity: Severity | None = None
            threshold: float | None = None

            if diff > err_thresh:
                severity = Severity.ERROR
                threshold = err_thresh
            elif diff > warn_thresh:
                severity = Severity.WARNING
                threshold = warn_thresh

            if severity is not None and threshold is not None:
                vi_name = DIM_VI[dim_name]
                suspect_note = ""
                if rel > t_cfg.suspect_id_rel:
                    suspect_note = " (lệch > 30%, nghi nhầm ID)"

                msg = (
                    f"{vi_name.capitalize()} {val:.2f} m lệch {diff:.2f} m ({rel*100:.1f}%) "
                    f"so với trung vị track ({med:.2f} m){suspect_note}"
                )
                findings.append(
                    Finding(
                        error_type=ErrorType.SIZE,
                        rule="size.in_track",
                        severity=severity,
                        frame=b.frame,
                        label=b.label,
                        track_id=b.track_id,
                        source_id=b.source_id,
                        message=msg,
                        value=float(diff),
                        threshold=float(threshold),
                        details={
                            "dimension": dim_name,
                            "median": float(med),
                            "relative_diff": float(rel),
                            "suspect_id": bool(rel > t_cfg.suspect_id_rel),
                        },
                    )
                )

    return findings


def detect_size(
    cuboids: Sequence[Cuboid],
    config: SizeConfig,
    class_ranges: Mapping[str, Mapping[str, tuple[float, float]]] | None = None,
) -> list[Finding]:
    """Phát hiện lỗi kích thước (cả kiểu 1 và kiểu 2) trên tập box."""
    resolved_ranges = get_resolved_class_ranges(config, class_ranges)
    findings: list[Finding] = []

    # Kiểu 1: theo class
    for c in cuboids:
        findings.extend(detect_size_class_range_for_box(c, config, resolved_ranges))

    # Kiểu 2: theo track
    tracks = group_by_track(cuboids)
    for track_boxes in tracks.values():
        findings.extend(detect_size_in_track(track_boxes, config))

    return findings
