"""Kiểm thử unit test cho Assisted 3D Box Repair Geometry Engine (Milestone M2, F4-F7)."""

from __future__ import annotations

import math
import numpy as np
import pytest

from pointsnap.core.config import load_config
from pointsnap.core.model import Cuboid, Severity
from pointsnap.core.repair import (
    BoxRepairDelta,
    compute_box_repair,
    verify_repaired_box_passes_scanner,
)
from pointsnap.core.scanner import scan_cuboids
from pointsnap.core.synthetic import inject_floating, inject_heading_rotate, inject_size_in_track


def _car_track(n: int = 6, speed: float = 8.0, yaw: float = 0.0, track_id: int = 1, label: str = "car", ground_z: float = -1.8) -> list[Cuboid]:
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
    for k, box in enumerate(boxes):
        # Điểm L-shape trên thân xe
        l, w = box.dims[0], box.dims[1]
        n_side = 80
        # Cạnh trước x = +l/2, y in [-w/2, w/2]
        front = np.column_stack([
            np.full(n_side, l / 2),
            rng.uniform(-w / 2, w / 2, n_side),
        ])
        # Cạnh trái y = +w/2, x in [-l/2, l/2]
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


# --- F4: Ground Delta & Floating Repair ----------------------------------------------------------------


def test_repair_floating_box_delta_z():
    """Kiểm tra sửa box lơ lửng: hạ đáy box xuống sát mặt đất đo được."""
    ground_z = -1.80
    track = _car_track(n=6, ground_z=ground_z)
    points = _scene_ground_points(track, ground_z=ground_z)

    # Chèn lỗi floating +30 cm tại frame 2
    injected_track, _ = inject_floating(track, track_id=1, frame=2, delta_z_m=0.30)
    target_box = injected_track[2]

    delta = compute_box_repair(target_box, injected_track, points, rule="floating")

    # Kiểm tra delta_center: Δz xấp xỉ -0.30m
    assert delta.delta_center[0] == 0.0
    assert delta.delta_center[1] == 0.0
    assert delta.delta_center[2] == pytest.approx(-0.30, abs=0.03)
    assert delta.target_offset_m == pytest.approx(0.30, abs=0.03)
    assert delta.confidence >= 0.80
    assert "hạ" in delta.reason.lower()

    # Kiểm tra repaired_cuboid
    repaired = delta.repaired_cuboid
    assert repaired.center[2] == pytest.approx(track[2].center[2], abs=0.03)
    assert repaired.bottom_z == pytest.approx(ground_z, abs=0.03)

    # Scanner clearance: box sau sửa không còn lỗi floating
    passed = verify_repaired_box_passes_scanner(repaired, injected_track, points, rule="floating")
    assert passed is True


def test_repair_underground_box_delta_z():
    """Kiểm tra sửa box lún đất: nâng đáy box lên sát mặt đất đo được."""
    ground_z = -1.80
    track = _car_track(n=6, ground_z=ground_z)
    points = _scene_ground_points(track, ground_z=ground_z)

    # Chèn lỗi lún -25 cm tại frame 2
    injected_track, _ = inject_floating(track, track_id=1, frame=2, delta_z_m=-0.25)
    target_box = injected_track[2]

    delta = compute_box_repair(target_box, injected_track, points, rule="floating")

    assert delta.delta_center[2] == pytest.approx(+0.25, abs=0.03)
    assert delta.target_offset_m == pytest.approx(-0.25, abs=0.03)
    assert "nâng" in delta.reason.lower()

    repaired = delta.repaired_cuboid
    assert repaired.bottom_z == pytest.approx(ground_z, abs=0.03)

    passed = verify_repaired_box_passes_scanner(repaired, injected_track, points, rule="floating")
    assert passed is True


def test_repair_single_box_floating_ground_offset():
    """Kiểm tra sửa box đơn lẻ (không có track) bị lơ lửng."""
    ground_z = -1.80
    single_box = Cuboid(center=(10.0, 0.0, -1.80 + 0.8 + 0.35), dims=(4.5, 1.9, 1.6), yaw=0.0, label="car", frame=0)
    points = _scene_ground_points([single_box.replace(center=(10.0, 0.0, -1.80 + 0.8))], ground_z=ground_z)

    delta = compute_box_repair(single_box, [single_box], points, rule="floating")

    assert delta.delta_center[2] == pytest.approx(-0.35, abs=0.04)
    assert delta.repaired_cuboid.bottom_z == pytest.approx(ground_z, abs=0.04)


# --- F5: Heading/Yaw Delta & Heading Repair -----------------------------------------------------------


def test_repair_heading_flip_delta_yaw():
    """Kiểm tra sửa box lật ngược 180° so với track: hiệu chỉnh yaw quay 180°."""
    track = _car_track(n=6, yaw=0.0)
    # Lật ngược frame 3 (yaw = pi)
    injected_track = list(track)
    injected_track[3] = track[3].replace(yaw=math.pi)
    target_box = injected_track[3]

    delta = compute_box_repair(target_box, injected_track, points=None, rule="heading.flip")

    assert abs(abs(delta.delta_yaw) - math.pi) < 0.05
    assert delta.repaired_cuboid.yaw == pytest.approx(0.0, abs=0.05)
    assert delta.confidence >= 0.90
    assert "hướng chuẩn" in delta.reason

    passed = verify_repaired_box_passes_scanner(delta.repaired_cuboid, injected_track, points=None, rule="heading.flip")
    assert passed is True


def test_repair_heading_points_l_shape():
    """Kiểm tra sửa box lệch góc so với cụm điểm LiDAR qua L-shape closeness."""
    true_box = Cuboid(center=(10.0, 0.0, -1.0), dims=(4.5, 1.9, 1.6), yaw=0.0, label="car", frame=0, track_id=1)
    points = _scene_ground_points([true_box], seed=123)

    # Box bị vẽ xoay 25°
    drawn_box = true_box.replace(yaw=math.radians(25.0))
    track = [true_box.replace(frame=f) for f in range(5)]
    track[2] = drawn_box.replace(frame=2)

    delta = compute_box_repair(track[2], track, points, rule="heading.points")

    # Góc xoay hiệu chỉnh phải xấp xỉ -25° để đưa yaw về ~0°
    assert math.degrees(delta.delta_yaw) == pytest.approx(-25.0, abs=3.5)
    assert delta.repaired_cuboid.yaw == pytest.approx(0.0, abs=math.radians(3.5))
    assert delta.confidence >= 0.85

    passed = verify_repaired_box_passes_scanner(delta.repaired_cuboid, track, points, rule="heading.points")
    assert passed is True


def test_repair_heading_motion():
    """Kiểm tra sửa box ngược hướng vector vận tốc."""
    track = _car_track(n=6, speed=10.0, yaw=0.0)
    # Frame 2 bị gán ngược hướng vận tốc
    injected = list(track)
    injected[2] = track[2].replace(yaw=math.pi)

    delta = compute_box_repair(injected[2], injected, points=None, rule="heading.motion")

    assert delta.repaired_cuboid.yaw == pytest.approx(0.0, abs=0.05)
    assert delta.confidence >= 0.90


# --- F6: Dimension & Center Delta (fit.outside, size.in_track) ----------------------------------------


def test_repair_size_in_track_oversized():
    """Kiểm tra sửa box bị phóng to kích thước so với trung vị track."""
    track = _car_track(n=5)
    # Frame 2 bị tăng kích thước lên 5.5 x 2.5 x 2.2 m
    injected, _ = inject_size_in_track(track, track_id=1, frame=2, scale_factor=1.35)
    target = injected[2]

    delta = compute_box_repair(target, injected, points=None, rule="size.in_track")

    assert delta.repaired_cuboid.dims == pytest.approx((4.5, 1.9, 1.6), abs=0.01)
    # Bảo toàn bottom_z
    assert delta.repaired_cuboid.bottom_z == pytest.approx(target.bottom_z, abs=0.01)

    passed = verify_repaired_box_passes_scanner(delta.repaired_cuboid, injected, points=None, rule="size.in_track")
    assert passed is True


def test_repair_size_in_track_undersized():
    """Kiểm tra sửa box bị co nhỏ kích thước so với trung vị track."""
    track = _car_track(n=5)
    injected, _ = inject_size_in_track(track, track_id=1, frame=2, scale_factor=0.70)
    target = injected[2]

    delta = compute_box_repair(target, injected, points=None, rule="size.in_track")

    assert delta.repaired_cuboid.dims == pytest.approx((4.5, 1.9, 1.6), abs=0.01)
    passed = verify_repaired_box_passes_scanner(delta.repaired_cuboid, injected, points=None, rule="size.in_track")
    assert passed is True


def test_repair_fit_outside_recenters_and_encompasses():
    """Kiểm tra sửa box bị lệch tâm làm điểm vật thể tràn ra ngoài viền (fit.outside)."""
    true_box = Cuboid(center=(10.0, 0.0, -1.0), dims=(4.5, 1.9, 1.6), yaw=0.0, label="car", frame=0, track_id=1)
    points = _scene_ground_points([true_box], seed=42)

    # Box bị dời tâm sang phải 0.6 m (dy = -0.6 m)
    shifted_box = true_box.replace(center=(10.0, -0.6, -1.0))
    track = [true_box.replace(frame=f) for f in range(5)]
    track[1] = shifted_box.replace(frame=1)

    delta = compute_box_repair(track[1], track, points, rule="fit.outside")

    # Tâm y được hiệu chỉnh về lại gần 0.0
    assert delta.delta_center[1] == pytest.approx(0.6, abs=0.15)
    assert delta.repaired_cuboid.center[1] == pytest.approx(0.0, abs=0.15)
    assert delta.confidence >= 0.85

    passed = verify_repaired_box_passes_scanner(delta.repaired_cuboid, track, points, rule="fit.outside")
    assert passed is True


def test_repair_size_class_range():
    """Kiểm tra sửa box ô tô bị gán kích thước xe buýt (11.0m) vượt khoảng class."""
    weird_car = Cuboid(center=(10.0, 0.0, 0.0), dims=(11.0, 2.9, 3.4), yaw=0.0, label="car", frame=0)
    delta = compute_box_repair(weird_car, [weird_car], points=None, rule="size.class_range")

    assert delta.repaired_cuboid.length <= 5.76 + 0.01
    assert delta.repaired_cuboid.width <= 2.38 + 0.01
    assert delta.repaired_cuboid.height <= 2.30 + 0.01


# --- F7: Scanner Re-scan Clearance & Verification ----------------------------------------------------


def test_scanner_clearance_helper_fails_on_unrepaired_box():
    """Xác nhận `verify_repaired_box_passes_scanner` trả về False nếu box chưa được sửa."""
    track = _car_track(n=5)
    injected, _ = inject_floating(track, track_id=1, frame=2, delta_z_m=0.35)
    points = _scene_ground_points(injected)

    # Chưa sửa -> Không vượt qua scanner
    assert verify_repaired_box_passes_scanner(injected[2], injected, points, rule="floating") is False


def test_scanner_clearance_helper_passes_on_repaired_box():
    """Xác nhận `verify_repaired_box_passes_scanner` trả về True khi đã sửa đúng."""
    track = _car_track(n=5)
    injected, _ = inject_floating(track, track_id=1, frame=2, delta_z_m=0.35)
    points = _scene_ground_points(track)

    delta = compute_box_repair(injected[2], injected, points, rule="floating")
    assert verify_repaired_box_passes_scanner(delta.repaired_cuboid, injected, points, rule="floating") is True


# --- Edge Cases & Robustness --------------------------------------------------------------------------


def test_repair_edge_case_sparse_points():
    """Kiểm tra xử lý an toàn khi cụm điểm LiDAR quá thưa (0 điểm hoặc chỉ 2 điểm)."""
    box = Cuboid(center=(10.0, 0.0, 0.0), dims=(4.5, 1.9, 1.6), yaw=0.0, label="car", frame=0)
    sparse_points = np.array([[10.0, 0.0, 0.0], [10.1, 0.1, 0.1]])

    # Không bị crash, trả về delta an toàn hoặc fallback
    delta_floating = compute_box_repair(box, [box], sparse_points, rule="floating")
    assert delta_floating.confidence == 0.0
    assert delta_floating.delta_center == (0.0, 0.0, 0.0)

    delta_heading = compute_box_repair(box, [box], sparse_points, rule="heading.points")
    assert delta_heading.confidence == 0.0
    assert delta_heading.delta_yaw == 0.0


def test_repair_edge_case_missing_ground_with_finding_details():
    """Kiểm tra khi không có point cloud nhưng có finding_details: sửa thành công từ metadata."""
    box = Cuboid(center=(10.0, 0.0, 0.0), dims=(4.5, 1.9, 1.6), yaw=0.0, label="car", frame=0)
    details = {
        "distance": 0.28,
        "track_median_distance": 0.05,
        "ground_z": -1.08,
        "num_ground_points": 25,
    }
    delta = compute_box_repair(box, [box], points=None, rule="floating", finding_details=details)

    # offset = 0.28 - 0.05 = 0.23 -> delta_z = -0.23
    assert delta.delta_center[2] == pytest.approx(-0.23, abs=0.01)
    assert delta.confidence >= 0.75


def test_repair_dataclass_contract_and_to_dict():
    """Kiểm tra tính bất biến (frozen), cấu trúc trường và hàm to_dict() của BoxRepairDelta."""
    box = Cuboid(center=(1.0, 2.0, 3.0), dims=(4.0, 2.0, 1.5), yaw=0.5, label="car", frame=0)
    delta = BoxRepairDelta(
        delta_center=(0.1, 0.2, -0.3),
        delta_dims=(0.0, 0.0, 0.0),
        delta_yaw=0.1,
        repaired_cuboid=box,
        rule="floating",
        target_offset_m=0.3,
        confidence=0.95,
        reason="Test repair",
    )

    with pytest.raises(Exception):
        delta.delta_yaw = 0.2  # type: ignore[misc]

    d = delta.to_dict()
    assert d["rule"] == "floating"
    assert d["delta_center"] == [0.1, 0.2, -0.3]
    assert d["repaired_cuboid"]["center"] == [1.0, 2.0, 3.0]
    assert d["confidence"] == 0.95


def test_unsupported_rule_raises_value_error():
    """Kiểm tra báo lỗi với rule không hỗ trợ."""
    box = Cuboid(center=(0.0, 0.0, 0.0), dims=(1.0, 1.0, 1.0), yaw=0.0, label="car", frame=0)
    with pytest.raises(ValueError, match="Unsupported repair rule"):
        compute_box_repair(box, [box], points=None, rule="unsupported.magic_rule")
