"""Unit & Integration tests for Ghost Target Guides Engine and Spatial Residuals (Milestone M1).

Kiểm thử toàn diện:
- F1: Ghost Target Data Model (ClusterBounds, GhostTarget, SpatialResiduals)
- F2: Ground Leveling Math & Zero Roll/Pitch
- F3: Spatial Residuals & Facial Clearances
- F4: Ghost Target REST Route (/api/jobs/{job_id}/tracks/{track_id}/ghost-target)
- Re-scan scanner clearance với hộp đạt Green Lock (verify_repaired_box_passes_scanner)
"""

from __future__ import annotations

import copy
import math
from pathlib import Path
from typing import Any

import numpy as np
import pytest
from fastapi.testclient import TestClient

from pointsnap.adapters.cvat.shapes import cuboid_to_points
from pointsnap.core.geometry import normalize_angle
from pointsnap.core.ghost import (
    ClusterBounds,
    GhostTarget,
    SpatialResiduals,
    compute_spatial_residuals,
    generate_ghost_target,
)
from pointsnap.core.model import Cuboid
from pointsnap.core.repair import verify_repaired_box_passes_scanner
from pointsnap.core.synthetic import inject_floating, inject_heading_rotate
from pointsnap.web.app import create_app


# =========================================================================
# Helper Fixtures & Generators
# =========================================================================


def _car_track(
    n: int = 6,
    speed: float = 8.0,
    yaw: float = 0.0,
    track_id: int = 1,
    label: str = "car",
    ground_z: float = -1.8,
) -> list[Cuboid]:
    """Tạo track xe ô tô chạy thẳng trên mặt đường cao độ `ground_z`."""
    dims = (4.5, 1.9, 1.6)
    boxes = []
    for f in range(n):
        x = math.cos(yaw) * speed * 0.5 * f
        y = math.sin(yaw) * speed * 0.5 * f
        cz = ground_z + dims[2] / 2.0  # Đáy sát mặt đất: cz - h/2 = ground_z
        boxes.append(Cuboid(center=(x, y, cz), dims=dims, yaw=yaw, label=label, frame=f, track_id=track_id))
    return boxes


def _scene_ground_points(boxes: list[Cuboid], ground_z: float = -1.8, seed: int = 42) -> np.ndarray:
    """Tạo point cloud mặt đất z = ground_z quanh các box và thân xe."""
    rng = np.random.default_rng(seed)
    ground = np.column_stack([
        rng.uniform(-30, 30, 15000),
        rng.uniform(-30, 30, 15000),
        np.full(15000, ground_z) + rng.normal(0, 0.01, 15000),
    ])
    parts = [ground]
    for box in boxes:
        l, w = box.dims[0], box.dims[1]
        n_side = 80
        front = np.column_stack([
            np.full(n_side, l / 2),
            rng.uniform(-w / 2, w / 2, n_side),
        ])
        side = np.column_stack([
            rng.uniform(-l / 2, l / 2, n_side),
            np.full(n_side, w / 2),
        ])
        local_2d = np.vstack([front, side]) + rng.normal(0, 0.02, (2 * n_side, 2))
        c, s = math.cos(box.yaw), math.sin(box.yaw)
        rot = np.array([[c, s], [-s, c]])
        world_xy = local_2d @ rot + np.array(box.center[:2])
        z = rng.uniform(box.bottom_z + 0.2, box.top_z, len(local_2d))
        parts.append(np.column_stack([world_xy, z]))
    return np.vstack(parts)


@pytest.fixture
def sample_cvat_track_data() -> dict[str, Any]:
    """Tạo dữ liệu track CVAT chuẩn 5 frame cho REST API test."""
    shapes = []
    for f in range(5):
        # [px, py, pz, rx, ry, rz, sx, sy, sz, 0, 0, 0, 0, 0, 0, 0]
        pts = [
            10.0 + f * 2.0,
            5.0,
            -0.5,
            0.0,
            0.0,
            0.15,
            4.5,
            2.0,
            1.6,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
        ]
        shapes.append({
            "id": 2000 + f,
            "frame": f,
            "type": "cuboid",
            "occluded": False,
            "outside": False,
            "keyframe": True,
            "points": pts,
            "attributes": [
                {"id": 1, "name": "subtype", "value": "sedan"},
                {"id": 2, "name": "reviewed", "value": "true"},
            ],
        })
    return {
        "id": 101,
        "label": "car",
        "label_id": 10,
        "frame": 0,
        "shapes": shapes,
        "attributes": [],
    }


@pytest.fixture
def api_client(tmp_path: Path) -> TestClient:
    """Tạo FastAPI TestClient."""
    app = create_app(home_dir=tmp_path)
    return TestClient(app)


# =========================================================================
# Feature F1: Dataclass Contracts & Serialization
# =========================================================================


def test_cluster_bounds_dataclass_contract_and_to_dict():
    """Kiểm tra ClusterBounds dataclass, tính bất biến và hàm to_dict."""
    cb = ClusterBounds(
        min_x=-2.2, max_x=2.3,
        min_y=-1.0, max_y=1.1,
        p1_x=-2.15, p99_x=2.25,
        p1_y=-0.95, p99_y=1.05,
        num_points=120,
    )
    d = cb.to_dict()
    assert d["min_x"] == pytest.approx(-2.2)
    assert d["max_x"] == pytest.approx(2.3)
    assert d["min_y"] == pytest.approx(-1.0)
    assert d["max_y"] == pytest.approx(1.1)
    assert d["p1_x"] == pytest.approx(-2.15)
    assert d["p99_x"] == pytest.approx(2.25)
    assert d["p1_y"] == pytest.approx(-0.95)
    assert d["p99_y"] == pytest.approx(1.05)
    assert d["num_points"] == 120

    # Immutability check
    with pytest.raises(Exception):
        cb.num_points = 200  # type: ignore


def test_ghost_target_dataclass_contract_and_to_cuboid():
    """Kiểm tra GhostTarget dataclass, to_dict và chuyển đổi to_cuboid."""
    cb = ClusterBounds(
        min_x=-2.2, max_x=2.2, min_y=-1.0, max_y=1.0,
        p1_x=-2.1, p99_x=2.1, p1_y=-0.9, p99_y=0.9, num_points=85,
    )
    gt = GhostTarget(
        center=(15.0, 5.0, -1.0),
        dims=(4.6, 2.0, 1.6),
        yaw=0.25,
        roll=0.0,
        pitch=0.0,
        ground_z=-1.8,
        target_bottom_z=-1.8,
        confidence=0.96,
        reason="Khung mục tiêu chuẩn",
        cluster_bounds=cb,
    )
    d = gt.to_dict()
    assert d["center"] == [15.0, 5.0, -1.0]
    assert d["dims"] == [4.6, 2.0, 1.6]
    assert d["yaw"] == pytest.approx(0.25)
    assert d["roll"] == 0.0
    assert d["pitch"] == 0.0
    assert d["ground_z"] == pytest.approx(-1.8)
    assert d["target_bottom_z"] == pytest.approx(-1.8)
    assert d["confidence"] == pytest.approx(0.96)
    assert d["cluster_bounds"]["num_points"] == 85

    # Chuyển đổi sang Cuboid
    cuboid = gt.to_cuboid(label="bus", frame=3, track_id=42, attrs={"cvat_rx": 0.5})
    assert cuboid.label == "bus"
    assert cuboid.frame == 3
    assert cuboid.track_id == 42
    assert cuboid.center == (15.0, 5.0, -1.0)
    assert cuboid.dims == (4.6, 2.0, 1.6)
    assert cuboid.yaw == pytest.approx(0.25)
    # Roll và pitch phải luôn được triệt tiêu về 0 trong attrs
    assert cuboid.attrs["cvat_rx"] == 0.0
    assert cuboid.attrs["cvat_ry"] == 0.0


# =========================================================================
# Feature F2: Ground Leveling & Ghost Target Generation
# =========================================================================


def test_generate_ghost_target_floating_error():
    """Kiểm tra tạo GhostTarget cho lỗi floating (+30cm): đáy đưa về z_ground, roll/pitch=0."""
    ground_z = -1.80
    track = _car_track(n=6, ground_z=ground_z)
    points = _scene_ground_points(track, ground_z=ground_z)

    # Chèn lỗi floating +30 cm tại frame 2
    injected_track, _ = inject_floating(track, track_id=1, frame=2, delta_z_m=0.30)
    target_box = injected_track[2]

    ghost = generate_ghost_target(target_box, injected_track, points, rule="floating")

    assert ghost.roll == 0.0
    assert ghost.pitch == 0.0
    assert ghost.target_bottom_z == pytest.approx(ground_z, abs=0.03)
    assert ghost.center[2] == pytest.approx(ground_z + target_box.height / 2.0, abs=0.03)
    assert ghost.confidence >= 0.80
    assert ghost.cluster_bounds is not None

    # Scanner clearance
    repaired_box = ghost.to_cuboid(label=target_box.label, frame=target_box.frame, track_id=target_box.track_id)
    assert verify_repaired_box_passes_scanner(repaired_box, injected_track, points, rule="floating") is True


def test_generate_ghost_target_underground_error():
    """Kiểm tra tạo GhostTarget cho lỗi lún đất (-25cm): nâng đáy về mặt đất."""
    ground_z = -1.80
    track = _car_track(n=6, ground_z=ground_z)
    points = _scene_ground_points(track, ground_z=ground_z)

    injected_track, _ = inject_floating(track, track_id=1, frame=2, delta_z_m=-0.25)
    target_box = injected_track[2]

    ghost = generate_ghost_target(target_box, injected_track, points, rule="floating")

    assert ghost.target_bottom_z == pytest.approx(ground_z, abs=0.03)
    assert ghost.roll == 0.0
    assert ghost.pitch == 0.0

    repaired_box = ghost.to_cuboid(label=target_box.label, frame=target_box.frame, track_id=target_box.track_id)
    assert verify_repaired_box_passes_scanner(repaired_box, injected_track, points, rule="floating") is True


def test_generate_ghost_target_heading_flip():
    """Kiểm tra tạo GhostTarget cho lỗi heading.flip: xoay 180° về hướng chuẩn track."""
    ground_z = -1.80
    track = _car_track(n=6, ground_z=ground_z, yaw=0.0)
    points = _scene_ground_points(track, ground_z=ground_z)

    # Chèn lỗi xoay 180 độ tại frame 2
    injected_track, _ = inject_heading_rotate(track, track_id=1, frame=2, delta_deg=180.0)
    target_box = injected_track[2]

    ghost = generate_ghost_target(target_box, injected_track, points, rule="heading.flip")

    assert normalize_angle(ghost.yaw - 0.0) == pytest.approx(0.0, abs=0.05)
    assert ghost.roll == 0.0
    assert ghost.pitch == 0.0
    assert ghost.confidence >= 0.80

    repaired_box = ghost.to_cuboid(label=target_box.label, frame=target_box.frame, track_id=target_box.track_id)
    assert verify_repaired_box_passes_scanner(repaired_box, injected_track, points, rule="heading.flip") is True


def test_generate_ghost_target_heading_points_l_shape():
    """Kiểm tra tạo GhostTarget cho lỗi heading.points qua thuật toán khớp L-shape."""
    ground_z = -1.80
    track = _car_track(n=6, ground_z=ground_z, yaw=0.0)
    points = _scene_ground_points(track, ground_z=ground_z)

    # Lệch yaw 20 độ tại frame 3
    injected_track, _ = inject_heading_rotate(track, track_id=1, frame=3, delta_deg=20.0)
    target_box = injected_track[3]

    ghost = generate_ghost_target(target_box, injected_track, points, rule="heading.points")

    assert normalize_angle(ghost.yaw - 0.0) == pytest.approx(0.0, abs=0.08)
    assert ghost.roll == 0.0
    assert ghost.pitch == 0.0

    repaired_box = ghost.to_cuboid(label=target_box.label, frame=target_box.frame, track_id=target_box.track_id)
    assert verify_repaired_box_passes_scanner(repaired_box, injected_track, points, rule="heading.points") is True


def test_generate_ghost_target_fit_outside():
    """Kiểm tra tạo GhostTarget cho lỗi fit.outside: dời tâm và nới kích thước theo cụm điểm."""
    ground_z = -1.80
    track = _car_track(n=6, ground_z=ground_z)
    points = _scene_ground_points(track, ground_z=ground_z)

    # Co ngắn box tại frame 2 khiến điểm thò ra ngoài 30cm
    target_box = track[2].replace(dims=(3.2, 1.9, 1.6))
    injected_track = [target_box if i == 2 else b for i, b in enumerate(track)]

    ghost = generate_ghost_target(target_box, injected_track, points, rule="fit.outside")

    assert ghost.dims[0] >= 3.8
    assert ghost.cluster_bounds is not None
    assert ghost.cluster_bounds.num_points > 10

    repaired_box = ghost.to_cuboid(label=target_box.label, frame=target_box.frame, track_id=target_box.track_id)
    assert verify_repaired_box_passes_scanner(repaired_box, injected_track, points, rule="fit.outside") is True


def test_generate_ghost_target_fit_loose():
    """Kiểm tra tạo GhostTarget cho lỗi fit.loose: thu gọn mặt hở theo cụm điểm."""
    ground_z = -1.80
    dims = (6.5, 1.9, 1.6)
    box = Cuboid(center=(10.0, 5.0, ground_z + dims[2] / 2.0), dims=dims, yaw=0.0, label="car", frame=0)

    # Điểm cụm vật thể thực tế (dài 4.5m) nằm bên trong box 6.5m
    rng = np.random.default_rng(42)
    local_car = rng.uniform([-2.25, -0.95, -0.8], [2.25, 0.95, 0.8], (100, 3))
    world_pts = local_car + np.array(box.center)

    ghost = generate_ghost_target(
        box,
        [box],
        world_pts,
        rule="fit.loose",
        details={"face": "đầu", "gap": 0.8},
    )

    assert ghost.dims[0] < box.dims[0]
    assert ghost.roll == 0.0
    assert ghost.pitch == 0.0


def test_generate_ghost_target_zero_roll_pitch_leveling():
    """Kiểm tra đưa roll và pitch về 0.0 bất kể box ban đầu bị nghiêng."""
    ground_z = -1.80
    track = _car_track(n=3, ground_z=ground_z)
    points = _scene_ground_points(track, ground_z=ground_z)

    tilted_box = track[1].replace(attrs={"cvat_rx": 0.25, "cvat_ry": -0.18})
    ghost = generate_ghost_target(tilted_box, track, points)

    assert ghost.roll == 0.0
    assert ghost.pitch == 0.0

    cuboid = ghost.to_cuboid()
    assert cuboid.attrs["cvat_rx"] == 0.0
    assert cuboid.attrs["cvat_ry"] == 0.0


def test_generate_ghost_target_sparse_points_fallback():
    """Kiểm tra xử lý biên khi point cloud bị thiếu hoặc quá thưa (< 5 điểm)."""
    ground_z = -1.80
    track = _car_track(n=4, ground_z=ground_z)

    sparse_pts = np.array([[10.0, 5.0, -1.8], [10.5, 5.2, -1.8]])
    ghost = generate_ghost_target(track[1], track, sparse_pts, rule="fit.outside")

    assert ghost.confidence == pytest.approx(0.70)
    assert ghost.dims == track[1].dims
    assert ghost.roll == 0.0
    assert ghost.pitch == 0.0


# =========================================================================
# Feature F3: Spatial Residuals & Real-time Telemetry Calculations
# =========================================================================


def test_compute_spatial_residuals_exact_cm_and_deg():
    """Kiểm tra tính toán chính xác tuyệt đối các đại lượng sai số (cm, deg)."""
    # Box hiện tại: center=(10.0, 5.0, 1.0), dims=(4.5, 1.8, 2.0), yaw=0.10 rad
    # Đáy hiện tại: 1.0 - 2.0/2 = 0.0 m
    current = Cuboid(
        center=(10.0, 5.0, 1.0),
        dims=(4.5, 1.8, 2.0),
        yaw=0.10,
        label="car",
        frame=0,
        attrs={"cvat_rx": 0.005, "cvat_ry": -0.003},
    )

    # Ghost target: center=(10.05, 5.0, 0.8), dims=(4.5, 1.8, 2.0), yaw=0.05 rad
    # Đáy mục tiêu: 0.8 - 2.0/2 = -0.2 m
    target = GhostTarget(
        center=(10.05, 5.0, 0.8),
        dims=(4.5, 1.8, 2.0),
        yaw=0.05,
        target_bottom_z=-0.2,
    )

    res = compute_spatial_residuals(current, target, points=None)

    # delta_z_cm = (0.0 - (-0.2)) * 100 = +20.0 cm
    assert res.delta_z_cm == pytest.approx(20.0, abs=1e-4)

    # delta_yaw_deg = normalize_angle(0.10 - 0.05) * 180 / pi = 0.05 * 180 / pi = 2.864789 deg
    expected_dyaw = math.degrees(0.05)
    assert res.delta_yaw_deg == pytest.approx(expected_dyaw, abs=1e-4)

    # delta_dist_3d_cm = sqrt(0.05^2 + 0^2 + 0.2^2) * 100 = sqrt(0.0425) * 100 = 20.6155 cm
    expected_d3d = math.hypot(0.05, 0.2) * 100.0
    assert res.delta_dist_3d_cm == pytest.approx(expected_d3d, abs=1e-4)

    # delta_dist_xy_cm = 0.05 * 100 = 5.0 cm
    assert res.delta_dist_xy_cm == pytest.approx(5.0, abs=1e-4)

    # roll_deg = 0.005 * 180 / pi, pitch_deg = 0.003 * 180 / pi
    assert res.roll_deg == pytest.approx(math.degrees(0.005), abs=1e-4)
    assert res.pitch_deg == pytest.approx(math.degrees(0.003), abs=1e-4)


def test_compute_spatial_residuals_snap_conditions():
    """Kiểm tra điều kiện bắt dính Magnet Snap (dist <= 8cm hoặc yaw <= 4 deg)."""
    target = GhostTarget(center=(10.0, 5.0, 0.0), dims=(4.5, 1.8, 1.5), yaw=0.0)

    # TH1: Khoảng cách 7cm (<= 8cm), góc lệch 10 độ (> 4 độ) -> SNAPPED do khoảng cách
    c1 = Cuboid(center=(10.07, 5.0, 0.0), dims=(4.5, 1.8, 1.5), yaw=math.radians(10.0), label="car", frame=0)
    r1 = compute_spatial_residuals(c1, target)
    assert r1.is_snapped is True
    assert r1.is_green_locked is False
    assert r1.status_text == "SNAPPED"

    # TH2: Khoảng cách 15cm (> 8cm), góc lệch 3.5 độ (<= 4 độ) -> SNAPPED do góc
    c2 = Cuboid(center=(10.15, 5.0, 0.0), dims=(4.5, 1.8, 1.5), yaw=math.radians(3.5), label="car", frame=0)
    r2 = compute_spatial_residuals(c2, target)
    assert r2.is_snapped is True
    assert r2.is_green_locked is False
    assert r2.status_text == "SNAPPED"

    # TH3: Khoảng cách 15cm (> 8cm) VÀ góc lệch 10 độ (> 4 độ) -> OFF_TARGET
    c3 = Cuboid(center=(10.15, 5.0, 0.0), dims=(4.5, 1.8, 1.5), yaw=math.radians(10.0), label="car", frame=0)
    r3 = compute_spatial_residuals(c3, target)
    assert r3.is_snapped is False
    assert r3.is_green_locked is False
    assert r3.status_text == "OFF_TARGET"


def test_compute_spatial_residuals_green_lock_conditions():
    """Kiểm tra điều kiện Khóa Xanh Green Lock (dist <= 2cm, yaw <= 2 deg, roll <= 0.5 deg, pitch <= 0.5 deg)."""
    target = GhostTarget(center=(10.0, 5.0, 0.0), dims=(4.5, 1.8, 1.5), yaw=0.0)

    # TH1: Vị trí hoàn hảo: d = 1.2cm, yaw = 1.0 deg, roll = 0.2 deg, pitch = 0.1 deg -> GREEN_LOCK
    c_perfect = Cuboid(
        center=(10.012, 5.0, 0.0),
        dims=(4.5, 1.8, 1.5),
        yaw=math.radians(1.0),
        label="car",
        frame=0,
        attrs={"cvat_rx": math.radians(0.2), "cvat_ry": math.radians(0.1)},
    )
    r_perfect = compute_spatial_residuals(c_perfect, target)
    assert r_perfect.is_green_locked is True
    assert r_perfect.is_snapped is True
    assert r_perfect.status_text == "GREEN_LOCK"

    # TH2: Vị trí tâm và yaw chuẩn nhưng roll = 1.5 deg (> 0.5 deg) -> Không đạt Green Lock
    c_tilted = Cuboid(
        center=(10.01, 5.0, 0.0),
        dims=(4.5, 1.8, 1.5),
        yaw=math.radians(1.0),
        label="car",
        frame=0,
        attrs={"cvat_rx": math.radians(1.5), "cvat_ry": 0.0},
    )
    r_tilted = compute_spatial_residuals(c_tilted, target)
    assert r_tilted.is_green_locked is False
    assert r_tilted.is_snapped is True
    assert r_tilted.status_text == "SNAPPED"

    # TH3: d = 3.0cm (> 2.0cm), yaw = 1.0 deg -> Không đạt Green Lock
    c_far = Cuboid(
        center=(10.03, 5.0, 0.0),
        dims=(4.5, 1.8, 1.5),
        yaw=math.radians(1.0),
        label="car",
        frame=0,
    )
    r_far = compute_spatial_residuals(c_far, target)
    assert r_far.is_green_locked is False
    assert r_far.is_snapped is True
    assert r_far.status_text == "SNAPPED"


def test_compute_spatial_residuals_facial_clearances():
    """Kiểm tra tính toán khoảng hở 4 mặt thân xe (front, back, left, right)."""
    # Box dài 4.0m (half=2.0), rộng 2.0m (half=1.0), cao 1.5m
    box = Cuboid(center=(0.0, 0.0, 0.0), dims=(4.0, 2.0, 1.5), yaw=0.0, label="car", frame=0)
    target = GhostTarget(center=(0.0, 0.0, 0.0), dims=(4.0, 2.0, 1.5), yaw=0.0)

    # Điểm LiDAR:
    # Điểm trước nhất: x = +1.8m -> clearance_front = (2.0 - 1.8) * 100 = 20.0 cm
    # Điểm sau nhất: x = -1.7m -> clearance_back = (2.0 - 1.7) * 100 = 30.0 cm
    # Điểm trái nhất: y = +0.8m -> clearance_left = (1.0 - 0.8) * 100 = 20.0 cm
    # Điểm phải nhất: y = -0.7m -> clearance_right = (1.0 - 0.7) * 100 = 30.0 cm
    pts = np.array([
        [1.8, 0.0, 0.0],
        [-1.7, 0.0, 0.0],
        [0.0, 0.8, 0.0],
        [0.0, -0.7, 0.0],
    ])

    res = compute_spatial_residuals(box, target, points=pts)
    assert res.clearance_front_cm == pytest.approx(20.0, abs=0.1)
    assert res.clearance_back_cm == pytest.approx(30.0, abs=0.1)
    assert res.clearance_left_cm == pytest.approx(20.0, abs=0.1)
    assert res.clearance_right_cm == pytest.approx(30.0, abs=0.1)


# =========================================================================
# Scanner Clearance Proof with Green Locked Box
# =========================================================================


def test_green_locked_box_passes_scanner():
    """Chứng minh hình học: Mọi box đạt trạng thái Green Lock đều vượt qua bộ quét 100%."""
    ground_z = -1.80
    track = _car_track(n=6, ground_z=ground_z)
    points = _scene_ground_points(track, ground_z=ground_z)

    # Tạo ghost target chuẩn tại frame 2
    ghost = generate_ghost_target(track[2], track, points)
    ideal_box = ghost.to_cuboid(label="car", frame=2, track_id=1)

    # Thử nghiệm với các độ lệch trong dung sai Green Lock:
    # delta_dist_3d <= 2 cm (0.02m), delta_yaw <= 2 deg (0.0349 rad)
    offsets = [
        (0.015, 0.01, 0.005, math.radians(1.2)),
        (-0.01, -0.015, -0.008, math.radians(-1.5)),
        (0.00, 0.00, 0.018, math.radians(0.8)),
    ]

    for dx, dy, dz, dyaw in offsets:
        test_box = ideal_box.replace(
            center=(ideal_box.center[0] + dx, ideal_box.center[1] + dy, ideal_box.center[2] + dz),
            yaw=normalize_angle(ideal_box.yaw + dyaw),
        )
        res = compute_spatial_residuals(test_box, ghost)
        assert res.is_green_locked is True

        # Re-scan toàn bộ hệ thống scanner với rule="" (nghiêm ngặt: không có bất kỳ error hay warning nào)
        passed = verify_repaired_box_passes_scanner(test_box, track, points, rule="")
        assert passed is True, f"Box trong vùng Green Lock (dx={dx}, dy={dy}, dz={dz}, dyaw={dyaw}) phải sạch cờ lỗi"


# =========================================================================
# Feature F4: Integration Tests for REST API Route
# =========================================================================


def test_rest_api_get_ghost_target_floating(api_client: TestClient, sample_cvat_track_data: dict[str, Any]):
    """F4: GET /api/jobs/{job_id}/tracks/{track_id}/ghost-target trả về đúng schema và dung sai."""
    api_client.app.state.mock_tracks = {(4, 101): sample_cvat_track_data}

    resp = api_client.get("/api/jobs/4/tracks/101/ghost-target?frame=2&rule=floating")
    assert resp.status_code == 200
    data = resp.json()

    assert data["status"] == "ok"
    assert data["job_id"] == 4
    assert data["track_id"] == 101
    assert data["frame"] == 2
    assert "ghost_target" in data
    assert "track_etag" in data

    gt = data["ghost_target"]
    assert "center" in gt
    assert "dims" in gt
    assert "yaw" in gt
    assert gt["roll"] == 0.0
    assert gt["pitch"] == 0.0
    assert gt["confidence"] >= 0.70

    # Kiểm tra bộ dung sai chuẩn
    tol = data["tolerances"]
    assert tol["snap_distance_m"] == 0.08
    assert tol["snap_angle_deg"] == 4.0
    assert tol["lock_distance_m"] == 0.02
    assert tol["lock_angle_deg"] == 2.0


def test_rest_api_get_ghost_target_heading(api_client: TestClient, sample_cvat_track_data: dict[str, Any]):
    """F4: GET /api/jobs/{job_id}/tracks/{track_id}/ghost-target cho rule heading.flip."""
    api_client.app.state.mock_tracks = {(4, 101): sample_cvat_track_data}

    resp = api_client.get("/api/jobs/4/tracks/101/ghost-target?frame=0&rule=heading.flip")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["ghost_target"]["roll"] == 0.0
    assert data["ghost_target"]["pitch"] == 0.0


def test_rest_api_get_ghost_target_invalid_track_404(api_client: TestClient):
    """F4: GET ghost-target với track_id không tồn tại trả HTTP 404."""
    resp = api_client.get("/api/jobs/4/tracks/9999/ghost-target?frame=0")
    assert resp.status_code == 404
    data = resp.json()
    assert data["code"] == 404
    assert "9999" in data["detail"]


def test_rest_api_get_ghost_target_invalid_frame_404(api_client: TestClient, sample_cvat_track_data: dict[str, Any]):
    """F4: GET ghost-target với frame không tồn tại trong track trả HTTP 404."""
    api_client.app.state.mock_tracks = {(4, 101): sample_cvat_track_data}

    resp = api_client.get("/api/jobs/4/tracks/101/ghost-target?frame=999")
    assert resp.status_code == 404
    data = resp.json()
    assert data["code"] == 404
    assert "999" in data["detail"]
