"""Bộ phát hiện lỗi lơ lửng / lún đất (việc B3).

Quy ước: CONVENTIONS.md mục 4 (mã luật `floating`, `floating.no_evidence`).
Định nghĩa: d = z_đáy_box - z_ground_cục_bộ (cm).
  d > 0: lơ lửng
  d < 0: lún đất
Ngưỡng mặc định: Cảnh báo khi |d| > 10 cm, Lỗi khi |d| > 20 cm.
Chống báo động giả: Ít hơn min_ground_points điểm ground -> mức Thông tin ("thiếu bằng chứng").
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Sequence

import numpy as np

from pointsnap.core.ground import GroundEstimate, estimate_ground_for_box
from pointsnap.core.model import ErrorType, Finding, Severity

if TYPE_CHECKING:
    from pointsnap.core.config import FloatingConfig
    from pointsnap.core.model import Cuboid


def detect_floating_for_box(
    cuboid: Cuboid,
    points: np.ndarray,
    config: FloatingConfig,
    seed: int | None = 42,
) -> Finding | None:
    """Kiểm tra lỗi lơ lửng / lún đất cho một box 3D."""
    if cuboid.outside or cuboid.label not in config.classes:
        return None

    est: GroundEstimate = estimate_ground_for_box(
        points=points,
        cuboid=cuboid,
        ring_inner_m=config.ring_inner_m,
        ring_outer_m=config.ring_outer_m,
        min_ground_points=config.min_ground_points,
        seed=seed,
    )

    if est.status == "no_evidence":
        return Finding(
            error_type=ErrorType.FLOATING,
            rule="floating.no_evidence",
            severity=Severity.INFO,
            frame=cuboid.frame,
            label=cuboid.label,
            track_id=cuboid.track_id,
            source_id=cuboid.source_id,
            message=(
                f"Vành đai quanh box chỉ có {est.num_ground_points} điểm ground "
                f"(< {config.min_ground_points}), thiếu bằng chứng kết luận"
            ),
            value=float(est.num_ground_points),
            threshold=float(config.min_ground_points),
            details={"num_ground_points": est.num_ground_points},
        )

    if not est.is_valid or est.distance is None:
        return None

    d = est.distance
    abs_d = abs(d)

    if abs_d > config.error_m:
        severity = Severity.ERROR
        thresh = config.error_m
    elif abs_d > config.warning_m:
        severity = Severity.WARNING
        thresh = config.warning_m
    else:
        return None

    d_cm = abs_d * 100.0
    thresh_cm = thresh * 100.0
    direction = "lơ lửng" if d > 0 else "lún đất"

    message = f"Đáy box {direction} {d_cm:.1f} cm so với mặt đất (ngưỡng {thresh_cm:.0f} cm)"

    return Finding(
        error_type=ErrorType.FLOATING,
        rule="floating",
        severity=severity,
        frame=cuboid.frame,
        label=cuboid.label,
        track_id=cuboid.track_id,
        source_id=cuboid.source_id,
        message=message,
        value=float(d),
        threshold=float(thresh),
        details={
            "distance": d,
            "ground_z": est.ground_z,
            "bottom_z": cuboid.bottom_z,
            "num_inliers": est.num_inliers,
            "num_ground_points": est.num_ground_points,
        },
    )


def detect_floating(
    cuboids: Sequence[Cuboid],
    points: np.ndarray,
    config: FloatingConfig,
    seed: int | None = 42,
) -> list[Finding]:
    """Phát hiện lỗi lơ lửng / lún đất trên danh sách box của một frame."""
    findings: list[Finding] = []
    for cuboid in cuboids:
        finding = detect_floating_for_box(cuboid, points, config, seed=seed)
        if finding is not None:
            findings.append(finding)
    return findings
