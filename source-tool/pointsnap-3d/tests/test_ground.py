"""Kiểm thử module ước lượng mặt đất (Ground Module) - việc B2.

Kiểm tra trên point cloud giả lập:
- Mặt phẳng nằm ngang và mặt phẳng nghiêng có nhiễu.
- Có cụm điểm vật thể (xe/người/cột) trong không gian và trong vành đai.
- Box chuẩn tiếp đất, box lơ lửng (+25 cm), box lún đất (-20 cm).
- Tiêu chí xong theo TASKS.md / giao-viec: sai số ước lượng độ cao mặt đất < 2 cm.
"""

from __future__ import annotations

import math
import numpy as np
import pytest

from pointsnap.core.config import FloatingConfig
from pointsnap.core.ground import (
    GroundEstimate,
    estimate_ground_for_box,
    estimate_ground_for_frame,
    filter_min_z_grid,
    fit_plane_ransac,
)
from pointsnap.core.model import Cuboid


def _create_synthetic_scene(
    plane_fn,  # (x, y) -> z
    ground_noise_std: float = 0.01,
    num_ground_pts: int = 5000,
    x_range: tuple[float, float] = (-20.0, 20.0),
    y_range: tuple[float, float] = (-20.0, 20.0),
    seed: int = 42,
) -> np.ndarray:
    """Tạo point cloud mặt đất với hàm độ cao plane_fn và nhiễu Gaussian."""
    rng = np.random.default_rng(seed)
    xs = rng.uniform(x_range[0], x_range[1], size=num_ground_pts)
    ys = rng.uniform(y_range[0], y_range[1], size=num_ground_pts)
    zs = plane_fn(xs, ys) + rng.normal(0.0, ground_noise_std, size=num_ground_pts)
    intensity = rng.uniform(0.1, 0.9, size=num_ground_pts)
    ring = rng.integers(0, 32, size=num_ground_pts).astype(float)
    return np.column_stack([xs, ys, zs, intensity, ring])


def test_filter_min_z_grid_basic():
    # 2 điểm trong cùng ô [0, 1]x[0, 1]: 1 điểm ground z=0.0, 1 điểm vật cản z=1.5
    pts = np.array([
        [0.2, 0.2, 0.0],
        [0.3, 0.3, 1.5],
        [1.2, 1.2, -0.5],
        [1.4, 1.4, 0.8],
    ])
    mask = filter_min_z_grid(pts, cell_size=1.0, height_threshold=0.15)
    assert mask[0]  # z=0.0 <= min_z (0.0) + 0.15
    assert not mask[1]  # z=1.5 > min_z (0.0) + 0.15
    assert mask[2]  # z=-0.5 <= min_z (-0.5) + 0.15
    assert not mask[3]  # z=0.8 > min_z (-0.5) + 0.15


def test_fit_plane_ransac_flat():
    rng = np.random.default_rng(123)
    xs = rng.uniform(-5.0, 5.0, 200)
    ys = rng.uniform(-5.0, 5.0, 200)
    zs = -1.8 + rng.normal(0.0, 0.005, 200)  # Mặt phẳng z = -1.8 m
    pts = np.column_stack([xs, ys, zs])

    plane, inliers = fit_plane_ransac(pts, distance_threshold=0.03, min_inliers=20, seed=123)
    assert plane is not None
    a, b, c, d = plane
    # Normal phải hướng lên gần thẳng đứng (c ~ 1.0)
    assert abs(a) < 0.02
    assert abs(b) < 0.02
    assert c > 0.99
    # Độ cao tại gốc z = -d/c ~ -1.8
    assert abs(-d / c - (-1.8)) < 0.01
    assert np.sum(inliers) > 180


def test_fit_plane_ransac_inclined():
    # Mặt phẳng nghiêng: z = 0.04*x - 0.02*y - 1.5
    rng = np.random.default_rng(456)
    xs = rng.uniform(-5.0, 5.0, 300)
    ys = rng.uniform(-5.0, 5.0, 300)
    zs = 0.04 * xs - 0.02 * ys - 1.5 + rng.normal(0.0, 0.01, 300)
    # Thêm 50 điểm nhiễu outlier (vật thể bay/xe)
    out_x = rng.uniform(-5.0, 5.0, 50)
    out_y = rng.uniform(-5.0, 5.0, 50)
    out_z = rng.uniform(0.0, 3.0, 50)
    pts = np.vstack([np.column_stack([xs, ys, zs]), np.column_stack([out_x, out_y, out_z])])

    plane, inliers = fit_plane_ransac(pts, distance_threshold=0.03, min_inliers=20, seed=456)
    assert plane is not None
    a, b, c, d = plane
    # Kiểm tra độ cao tại tâm (x=2.0, y=1.0)
    expected_z = 0.04 * 2.0 - 0.02 * 1.0 - 1.5
    fitted_z = -(a * 2.0 + b * 1.0 + d) / c
    assert abs(fitted_z - expected_z) < 0.015


def test_estimate_ground_flat_surface():
    """Test trên mặt phẳng ngang z = -1.80 m, box tiếp đất đúng chuẩn."""
    ground_z_true = -1.80
    pts = _create_synthetic_scene(lambda x, y: np.full_like(x, ground_z_true), ground_noise_std=0.01, seed=1)

    # Box xe: center z = -0.9, height = 1.8 -> bottom_z = -1.80
    car = Cuboid(
        center=(5.0, 3.0, -0.9),
        dims=(4.5, 1.8, 1.8),
        yaw=0.3,
        label="car",
        frame=0,
    )

    est = estimate_ground_for_box(pts, car, seed=42)
    assert est.is_valid
    assert est.status == "ok"
    assert est.ground_z is not None
    assert est.distance is not None

    # Tiêu chí: sai số ước lượng mặt đất < 2 cm (0.02 m)
    assert abs(est.ground_z - ground_z_true) < 0.02
    assert abs(est.distance) < 0.02


def test_estimate_ground_inclined_surface_with_obstacles():
    """Test trên mặt phẳng nghiêng z = 0.05*x - 0.03*y - 1.60 m kèm các cụm điểm xe/vật cản."""
    def ground_eq(x, y):
        return 0.05 * x - 0.03 * y - 1.60

    pts_ground = _create_synthetic_scene(ground_eq, ground_noise_std=0.012, num_ground_pts=8000, seed=2)

    # Thêm cụm điểm vật cản (ví dụ một người hoặc xe khác đứng cạnh ở x=11, y=3.5, z=[-1.0..0.5])
    rng = np.random.default_rng(999)
    obs_x = rng.uniform(10.5, 11.5, 100)
    obs_y = rng.uniform(3.0, 4.0, 100)
    obs_z = rng.uniform(-1.0, 0.5, 100)
    obs_pts = np.column_stack([obs_x, obs_y, obs_z, np.zeros(100), np.zeros(100)])
    all_pts = np.vstack([pts_ground, obs_pts])

    # Đặt box tại (x=10.0, y=2.0)
    cx, cy = 10.0, 2.0
    expected_ground_z = ground_eq(cx, cy)  # 0.05*10 - 0.03*2 - 1.6 = 0.5 - 0.06 - 1.6 = -1.16 m
    height = 1.6
    center_z = expected_ground_z + height / 2.0  # tiếp đất chuẩn

    car = Cuboid(
        center=(cx, cy, center_z),
        dims=(4.2, 1.8, height),
        yaw=math.radians(15.0),
        label="car",
        frame=0,
    )

    est = estimate_ground_for_box(all_pts, car, seed=42)
    assert est.is_valid
    # Sai số so với ground thật < 2 cm
    assert abs(est.ground_z - expected_ground_z) < 0.02
    assert abs(est.distance) < 0.02


def test_estimate_ground_floating_box():
    """Test box lơ lửng 25 cm (+0.25 m)."""
    ground_z_true = -1.75
    pts = _create_synthetic_scene(lambda x, y: np.full_like(x, ground_z_true), ground_noise_std=0.01, seed=3)

    height = 1.8
    floating_delta = 0.25
    center_z = ground_z_true + floating_delta + height / 2.0
    car = Cuboid(
        center=(0.0, 5.0, center_z),
        dims=(4.6, 1.9, height),
        yaw=0.0,
        label="car",
        frame=0,
    )

    est = estimate_ground_for_box(pts, car, seed=42)
    assert est.is_valid
    # ground_z ước lượng phải xấp xỉ ground_z_true
    assert abs(est.ground_z - ground_z_true) < 0.02
    # distance d = bottom_z - ground_z phải xấp xỉ +0.25 m với sai số < 2 cm
    assert abs(est.distance - floating_delta) < 0.02


def test_estimate_ground_sunk_box():
    """Test box lún đất 20 cm (-0.20 m)."""
    ground_z_true = -1.70
    pts = _create_synthetic_scene(lambda x, y: np.full_like(x, ground_z_true), ground_noise_std=0.01, seed=4)

    height = 1.5
    sunk_delta = -0.20
    center_z = ground_z_true + sunk_delta + height / 2.0
    car = Cuboid(
        center=(-3.0, 4.0, center_z),
        dims=(4.0, 1.8, height),
        yaw=0.5,
        label="car",
        frame=0,
    )

    est = estimate_ground_for_box(pts, car, seed=42)
    assert est.is_valid
    assert abs(est.ground_z - ground_z_true) < 0.02
    assert abs(est.distance - sunk_delta) < 0.02


def test_estimate_ground_insufficient_points():
    """Test trường hợp vành đai quá ít điểm ground -> thiếu bằng chứng (no_evidence)."""
    # Chỉ tạo 4 điểm quanh box (ít hơn min_ground_points = 10)
    pts = np.array([
        [2.0, 3.0, -1.8, 0.5, 1.0],
        [2.2, 3.1, -1.8, 0.5, 1.0],
        [1.8, 2.9, -1.8, 0.5, 1.0],
        [2.1, 2.8, -1.8, 0.5, 1.0],
    ])
    car = Cuboid(
        center=(2.0, 3.0, -0.9),
        dims=(4.0, 1.8, 1.8),
        yaw=0.0,
        label="car",
        frame=0,
    )
    est = estimate_ground_for_box(pts, car, min_ground_points=10)
    assert est.status == "no_evidence"
    assert not est.is_valid
    assert est.ground_z is None
    assert est.distance is None


def test_estimate_ground_for_frame():
    """Test hàm batch estimate_ground_for_frame có áp dụng FloatingConfig."""
    pts = _create_synthetic_scene(lambda x, y: np.full_like(x, -1.8), ground_noise_std=0.01, seed=5)

    car = Cuboid(center=(4.0, 2.0, -0.9), dims=(4.0, 1.8, 1.8), yaw=0.0, label="car", frame=0)
    ped = Cuboid(center=(-3.0, 2.0, -0.95), dims=(0.8, 0.8, 1.7), yaw=0.0, label="pedestrian", frame=0)
    cone = Cuboid(center=(1.0, 1.0, -1.6), dims=(0.4, 0.4, 0.8), yaw=0.0, label="traffic_cone", frame=0)

    config = FloatingConfig(
        classes=("car", "pedestrian"),
        warning_m=0.10,
        error_m=0.20,
        ring_inner_m=0.5,
        ring_outer_m=1.5,
        min_ground_points=10,
    )

    results = estimate_ground_for_frame(pts, [car, ped, cone], config=config)
    assert results[car].is_valid
    assert results[ped].is_valid
    # traffic_cone không nằm trong classes tiếp đất -> status no_evidence
    assert results[cone].status == "no_evidence"


def test_estimate_ground_real_nuscenes():
    """Kiểm thử trên dữ liệu nuScenes thật nếu có (việc B2 kiểm chứng ~200 box)."""
    from pathlib import Path
    import os
    from pointsnap.adapters.nuscenes import NuScenesReader

    data_dir = Path(os.environ.get("NUSCENES_ROOT") or
                    Path(__file__).resolve().parent.parent / "data" / "nuscenes")
    if not (data_dir / "v1.0-mini").is_dir():
        pytest.skip("Chưa có dữ liệu nuScenes v1.0-mini local")

    reader = NuScenesReader(data_dir)
    scene = reader.scenes()[0].name
    samples = reader.samples(scene)
    anns = reader.annotations(scene)

    cuboids_by_frame = {}
    for a in anns:
        cuboids_by_frame.setdefault(a.frame, []).append(a)

    errors = []
    checked_boxes = 0
    for sample in samples:
        fd = reader.frame_data(sample)
        for b in cuboids_by_frame.get(sample.frame, []):
            if b.label in ("car", "truck", "bus"):
                dist = np.linalg.norm(b.center[:2])
                if dist <= 30.0:  # Xe ở gần (dưới 30m) có đủ điểm LiDAR
                    checked_boxes += 1
                    est = estimate_ground_for_box(fd.points, b)
                    if est.is_valid:
                        errors.append(abs(est.distance))

    assert checked_boxes >= 50
    assert len(errors) / checked_boxes > 0.6  # Ít nhất 60% box gần ước lượng được mặt đất
    median_err = float(np.median(errors))
    assert median_err < 0.15  # Sai số trung vị dưới 15 cm trên dữ liệu thật
