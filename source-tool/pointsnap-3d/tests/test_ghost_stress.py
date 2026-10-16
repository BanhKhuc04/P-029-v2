"""Adversarial Stress Test Suite for Ghost Target Engine & Spatial Residuals (Milestone M1).

Probes boundary conditions, extreme rotations, steep slope leveling, inverted contact distances,
and Monte Carlo perturbations for Green Lock predicate scanner clearance.
"""

from __future__ import annotations

import math
from typing import Any

import numpy as np
import pytest

from pointsnap.core.ghost import (
    ClusterBounds,
    GhostTarget,
    SpatialResiduals,
    compute_spatial_residuals,
    generate_ghost_target,
)
from pointsnap.core.model import Cuboid
from pointsnap.core.ground import ring_ground_for_box
from pointsnap.core.repair import verify_repaired_box_passes_scanner
from tests.test_ghost_guides import _car_track, _scene_ground_points


# =========================================================================
# 1. Boundary Conditions: Point Cloud Sizes (0, 1, 4, 5, 10,000 points)
# =========================================================================


@pytest.mark.parametrize("n_points", [0, 1, 4, 5, 10000])
def test_boundary_point_cloud_sizes(n_points: int):
    """Kiểm tra độ bền với kích thước point cloud 0, 1, 4, 5, 10,000 điểm."""
    box = Cuboid(center=(10.0, 5.0, -1.0), dims=(4.5, 2.0, 1.6), yaw=0.2, label="car", frame=0)

    if n_points == 0:
        pts = np.zeros((0, 3), dtype=np.float64)
    else:
        rng = np.random.default_rng(n_points)
        local_pts = np.column_stack([
            rng.uniform(-box.length / 2.0 * 0.9, box.length / 2.0 * 0.9, n_points),
            rng.uniform(-box.width / 2.0 * 0.9, box.width / 2.0 * 0.9, n_points),
            rng.uniform(-box.height / 2.0 * 0.9, box.height / 2.0 * 0.9, n_points),
        ])
        from pointsnap.core.geometry import _from_box_frame
        pts = _from_box_frame(local_pts, box)

    gt = generate_ghost_target(box, points=pts, rule="")
    assert gt is not None
    assert math.isfinite(gt.center[0])
    assert math.isfinite(gt.center[1])
    assert math.isfinite(gt.center[2])
    assert gt.roll == 0.0
    assert gt.pitch == 0.0

    if n_points < 5:
        assert gt.cluster_bounds is None
        assert gt.confidence <= 0.85
    else:
        assert gt.cluster_bounds is not None
        assert gt.cluster_bounds.num_points >= 5
        assert gt.confidence >= 0.80

    res = compute_spatial_residuals(box, gt, points=pts)
    assert res is not None
    assert math.isfinite(res.delta_z_cm)
    assert math.isfinite(res.delta_yaw_deg)
    assert math.isfinite(res.delta_dist_3d_cm)


def test_corrupted_and_non_finite_points():
    """Kiểm tra khả năng chống chịu point cloud chứa NaN, Inf, và shape bất thường."""
    box = Cuboid(center=(0.0, 0.0, 0.0), dims=(4.5, 2.0, 1.6), yaw=0.0, label="car", frame=0)

    # Tất cả NaN/Inf
    dirty_pts = np.array([
        [np.nan, np.nan, np.nan],
        [np.inf, 0.0, 0.0],
        [-np.inf, 1.0, 2.0],
    ])
    gt = generate_ghost_target(box, points=dirty_pts)
    assert gt.confidence == 0.70  # fallback an toàn
    assert gt.center == (0.0, 0.0, 0.0)

    res = compute_spatial_residuals(box, gt, points=dirty_pts)
    assert res.clearance_front_cm == 0.0
    assert res.clearance_back_cm == 0.0

    # Shape 1D hoặc không đủ 3 cột
    gt_1d = generate_ghost_target(box, points=np.array([1.0, 2.0, 3.0]))
    assert gt_1d.confidence == 0.70

    gt_2col = generate_ghost_target(box, points=np.zeros((10, 2)))
    assert gt_2col.confidence == 0.70


def test_identical_collinear_points():
    """Kiểm tra khi tất cả 5 điểm trùng khít nhau (phương sai không gian = 0)."""
    box = Cuboid(center=(0.0, 0.0, 0.0), dims=(4.0, 2.0, 1.5), yaw=0.0, label="car", frame=0)
    pts = np.tile([0.5, 0.5, 0.0], (5, 1))

    for rule in ["", "fit.outside", "fit.loose"]:
        gt = generate_ghost_target(box, points=pts, rule=rule, details={"face": "đầu"})
        assert gt.cluster_bounds is not None
        assert gt.cluster_bounds.span_x == 0.0 if hasattr(gt.cluster_bounds, "span_x") else True
        assert gt.dims[0] > 0.0
        assert gt.dims[1] > 0.0
        assert gt.dims[2] > 0.0


# =========================================================================
# 2. Extreme Rotations: +/-180°, +/-360°, +/-720°, NaN, inf
# =========================================================================


@pytest.mark.parametrize("angle_deg", [180.0, -180.0, 360.0, -360.0, 720.0, -720.0])
def test_extreme_rotations_normalization(angle_deg: float):
    """Kiểm tra góc xoay cực hạn và chuẩn hóa góc trong [-π, π)."""
    rad = math.radians(angle_deg)
    box = Cuboid(center=(0.0, 0.0, 0.0), dims=(4.5, 2.0, 1.6), yaw=rad, label="car", frame=0)
    assert -math.pi <= box.yaw <= math.pi

    gt = generate_ghost_target(box)
    assert -math.pi <= gt.yaw <= math.pi

    res = compute_spatial_residuals(box, gt)
    assert abs(res.delta_yaw_deg) == pytest.approx(0.0, abs=1e-5)
    assert res.is_green_locked is True


def test_branch_cut_wrapping():
    """Kiểm tra góc giáp ranh nhánh cắt (+179.9° vs -179.9°)."""
    box = Cuboid(center=(0.0, 0.0, 0.0), dims=(4.0, 2.0, 1.5), yaw=math.radians(179.9), label="car", frame=0)
    gt = GhostTarget(center=(0.0, 0.0, 0.0), dims=(4.0, 2.0, 1.5), yaw=math.radians(-179.9))

    res = compute_spatial_residuals(box, gt)
    assert abs(res.delta_yaw_deg) == pytest.approx(0.2, abs=1e-3)
    assert res.is_green_locked is True


@pytest.mark.parametrize("bad_yaw", [float("nan"), float("inf"), float("-inf")])
def test_rejection_of_non_finite_yaw(bad_yaw: float):
    """Kiểm tra hệ thống từ chối giá trị góc NaN và Inf một cách an toàn."""
    with pytest.raises(ValueError, match="yaw phải là số hữu hạn"):
        Cuboid(center=(0.0, 0.0, 0.0), dims=(4.5, 2.0, 1.6), yaw=bad_yaw, label="car", frame=0)

    box = Cuboid(center=(0.0, 0.0, 0.0), dims=(4.5, 2.0, 1.6), yaw=0.0, label="car", frame=0)
    gt_bad = GhostTarget(center=(0.0, 0.0, 0.0), dims=(4.5, 2.0, 1.6), yaw=bad_yaw)
    res = compute_spatial_residuals(box, gt_bad)
    # NaN/Inf yaw không bao giờ được cấp Green Lock
    assert res.is_green_locked is False


# =========================================================================
# 3. Ground Leveling Under Steep Slopes and Inverted Contact Distances
# =========================================================================


@pytest.mark.parametrize("slope_deg", [0.0, 10.0, 15.0, 20.0, 30.0, 45.0, 60.0])
def test_ground_leveling_under_steep_slopes(slope_deg: float):
    """Kiểm tra cân bằng mặt sàn (Ground Leveling) trên các dốc nghiêng từ 0° đến 60°."""
    box = Cuboid(center=(0.0, 0.0, -1.0), dims=(4.5, 2.0, 1.6), yaw=0.0, label="car", frame=0)

    slope_rad = math.radians(slope_deg)
    rng = np.random.default_rng(int(slope_deg) + 7)
    xs = rng.uniform(-5.0, 5.0, 2500)
    ys = rng.uniform(-5.0, 5.0, 2500)
    zs = -1.8 + xs * math.tan(slope_rad)
    pts = np.column_stack([xs, ys, zs])

    gt = generate_ghost_target(box, points=pts, rule="floating")
    assert gt is not None
    assert gt.roll == 0.0
    assert gt.pitch == 0.0
    assert math.isfinite(gt.target_bottom_z)
    assert gt.center[2] == pytest.approx(gt.target_bottom_z + gt.dims[2] / 2.0)


@pytest.mark.parametrize("sunken_m", [0.10, 0.30, 0.50, 1.00, 2.00])
def test_inverted_contact_distance_sunken_box(sunken_m: float):
    """Kiểm tra xử lý khoảng cách tiếp xúc âm (hộp bị lún / chôn sâu dưới đất)."""
    # Đáy chuẩn là -1.8; hộp bị lún nên đáy ở -1.8 - sunken_m
    bottom_z = -1.8 - sunken_m
    box = Cuboid(center=(0.0, 0.0, bottom_z + 0.8), dims=(4.5, 2.0, 1.6), yaw=0.0, label="car", frame=0)

    # 1. Qua finding_details distance âm
    gt_detail = generate_ghost_target(box, rule="floating", details={"distance": -sunken_m})
    assert gt_detail.target_bottom_z == pytest.approx(-1.8, abs=1e-4)
    assert gt_detail.roll == 0.0
    assert gt_detail.pitch == 0.0

    # 2. Qua point cloud trực tiếp (nếu trong dải band 0.8m)
    if sunken_m <= 0.60:
        rng = np.random.default_rng(42)
        xs = rng.uniform(-5.0, 5.0, 2000)
        ys = rng.uniform(-5.0, 5.0, 2000)
        zs = np.full(2000, -1.8) + rng.normal(0, 0.01, 2000)
        pts = np.column_stack([xs, ys, zs])

        gt_pts = generate_ghost_target(box, points=pts, rule="floating")
        assert gt_pts.target_bottom_z == pytest.approx(-1.8, abs=0.05)


# =========================================================================
# 4. Green Lock Predicate Against Monte Carlo Perturbed Boxes
# =========================================================================


def test_green_lock_monte_carlo_scanner_clearance():
    """Monte Carlo stress test: 100 hộp nhiễu ngẫu nhiên trong dung sai Green Lock (<= 2cm, <= 2°, roll/pitch <= 0.5°).

    Khẳng định rằng:
    1. Residuals luôn xác nhận is_green_locked = True và status_text = 'GREEN_LOCK'.
    2. Scanner tái quét đạt 0 errors, 0 warnings (verify_repaired_box_passes_scanner = True).
    """
    track = _car_track(n=6, speed=8.0, yaw=0.0, ground_z=-1.8)
    points = _scene_ground_points(track, ground_z=-1.8, seed=42)
    target_box = track[2]

    gt = generate_ghost_target(target_box, track, points)
    ideal_box = gt.to_cuboid(label="car", frame=target_box.frame, track_id=target_box.track_id)

    rng = np.random.default_rng(20261015)
    total_samples = 100

    for i in range(total_samples):
        # 3D translation: Euclidean dist <= 1.95 cm (< 2.0 cm)
        d_cm = rng.uniform(0.0, 1.95)
        vec = rng.normal(size=3)
        vec /= np.linalg.norm(vec)
        dx, dy, dz = vec * (d_cm / 100.0)

        # Yaw perturbation: <= 1.95 deg (< 2.0 deg)
        dyaw_deg = rng.uniform(-1.95, 1.95)
        dyaw = math.radians(dyaw_deg)

        # Roll / pitch: <= 0.48 deg (< 0.5 deg)
        rx_deg = rng.uniform(-0.48, 0.48)
        ry_deg = rng.uniform(-0.48, 0.48)
        rx = math.radians(rx_deg)
        ry = math.radians(ry_deg)

        test_box = ideal_box.replace(
            center=(ideal_box.center[0] + dx, ideal_box.center[1] + dy, ideal_box.center[2] + dz),
            yaw=ideal_box.yaw + dyaw,
            attrs={"cvat_rx": rx, "cvat_ry": ry},
        )

        res = compute_spatial_residuals(test_box, gt, points=points)
        assert res.is_green_locked is True, (
            f"Iter {i} failed is_green_locked: dist={res.delta_dist_3d_cm:.2f}cm, "
            f"yaw={res.delta_yaw_deg:.2f}°, rx={res.roll_deg:.2f}°, ry={res.pitch_deg:.2f}°"
        )
        assert res.status_text == "GREEN_LOCK"

        # Tái quét qua scanner toàn diện
        passes = verify_repaired_box_passes_scanner(test_box, track, points, rule="")
        assert passes is True, f"Iter {i} failed scanner clearance!"


def test_green_lock_strict_tolerance_boundaries():
    """Kiểm tra ranh giới dung sai nghiêm ngặt: vượt quá 2cm hoặc 2° lập tức mất Green Lock."""
    box = Cuboid(center=(0.0, 0.0, 0.0), dims=(4.5, 2.0, 1.6), yaw=0.0, label="car", frame=0)
    gt = GhostTarget(center=(0.0, 0.0, 0.0), dims=(4.5, 2.0, 1.6), yaw=0.0)

    # 1. Khoảng cách 2.1 cm (> 2.0 cm) -> Mất Green Lock, nhưng vẫn Snapped (<= 8.0 cm)
    b_dist = box.replace(center=(0.021, 0.0, 0.0))
    res_dist = compute_spatial_residuals(b_dist, gt)
    assert res_dist.is_green_locked is False
    assert res_dist.is_snapped is True
    assert res_dist.status_text == "SNAPPED"

    # 2. Góc lệch 2.1° (> 2.0°) -> Mất Green Lock, nhưng vẫn Snapped (<= 4.0°)
    b_yaw = box.replace(yaw=math.radians(2.1))
    res_yaw = compute_spatial_residuals(b_yaw, gt)
    assert res_yaw.is_green_locked is False
    assert res_yaw.is_snapped is True
    assert res_yaw.status_text == "SNAPPED"

    # 3. Roll 0.55° (> 0.5°) -> Mất Green Lock
    b_roll = box.replace(attrs={"cvat_rx": math.radians(0.55)})
    res_roll = compute_spatial_residuals(b_roll, gt)
    assert res_roll.is_green_locked is False

    # 4. Pitch 0.55° (> 0.5°) -> Mất Green Lock
    b_pitch = box.replace(attrs={"cvat_ry": math.radians(0.55)})
    res_pitch = compute_spatial_residuals(b_pitch, gt)
    assert res_pitch.is_green_locked is False

    # 5. Khoảng cách 8.1 cm và góc 4.1° -> Mất cả Snap lẫn Green Lock -> OFF_TARGET
    b_off = box.replace(center=(0.081, 0.0, 0.0), yaw=math.radians(4.1))
    res_off = compute_spatial_residuals(b_off, gt)
    assert res_off.is_green_locked is False
    assert res_off.is_snapped is False
    assert res_off.status_text == "OFF_TARGET"
