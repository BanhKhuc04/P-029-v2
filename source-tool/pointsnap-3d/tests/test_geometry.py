import math

import numpy as np
import pytest

from pointsnap.core.geometry import (
    LIDAR_TO_EGO_ROT,
    bev_iou,
    corners,
    footprint,
    footprint_ring_mask,
    invert_pose,
    normalize_angle,
    points_in_cuboid,
    polygon_area,
    pose_matrix,
    quaternion_to_matrix,
    rotate_cuboid_to_ego,
    rotate_points_z90,
    rotate_pose_to_ego,
    to_box_frame,
    transform_points,
)
from pointsnap.core.model import Cuboid


def box(center=(0.0, 0.0, 0.0), dims=(4.0, 2.0, 1.5), yaw=0.0, **kw):
    return Cuboid(center=center, dims=dims, yaw=yaw, label="car", frame=0, **kw)



@pytest.mark.parametrize(
    "angle, expected",
    [(0.0, 0.0), (math.pi, -math.pi), (-math.pi, -math.pi), (3 * math.pi / 2, -math.pi / 2), (2 * math.pi, 0.0)],
)
def test_normalize_angle(angle, expected):
    assert normalize_angle(angle) == pytest.approx(expected)


def test_corners_axis_aligned():
    c = corners(box(center=(10.0, 5.0, 1.0)))
    assert c.shape == (8, 3)
    np.testing.assert_allclose(c.min(axis=0), [8.0, 4.0, 0.25])
    np.testing.assert_allclose(c.max(axis=0), [12.0, 6.0, 1.75])
    # 4 góc đầu là đáy, góc đầu tiên là trước-trái
    np.testing.assert_allclose(c[0], [12.0, 6.0, 0.25])
    assert np.all(c[:4, 2] == 0.25) and np.all(c[4:, 2] == 1.75)


def test_corners_rotated_90_degrees():
    # Quay 90°: chiều dài 4 m nằm dọc trục y
    c = corners(box(yaw=math.pi / 2))
    np.testing.assert_allclose(c.max(axis=0)[:2], [1.0, 2.0], atol=1e-12)
    np.testing.assert_allclose(c[0, :2], [-1.0, 2.0], atol=1e-12)


def test_to_box_frame_inverts_rotation():
    b = box(center=(3.0, -2.0, 0.5), yaw=0.7)
    world = corners(b)
    local = to_box_frame(world, b)
    np.testing.assert_allclose(np.abs(local), np.tile([2.0, 1.0, 0.75], (8, 1)), atol=1e-12)


def test_points_in_cuboid_rotated():
    b = box(yaw=math.pi / 2)  # dài theo y
    pts = np.array([[0.0, 1.9, 0.0], [1.9, 0.0, 0.0], [0.0, 0.0, 0.8], [0.0, 0.0, 0.7]])
    assert points_in_cuboid(pts, b).tolist() == [True, False, False, True]
    assert points_in_cuboid(pts, b, margin=0.1).tolist() == [True, False, True, True]


def test_points_with_extra_columns_are_accepted():
    pts = np.array([[0.0, 0.0, 0.0, 99.0, 7.0]])  # x, y, z, intensity, ring như nuScenes
    assert points_in_cuboid(pts, box()).tolist() == [True]


def test_footprint_ring_mask():
    b = box()  # footprint x ∈ [-2, 2], y ∈ [-1, 1]
    pts = np.array([
        [0.0, 0.0, -0.75],   # trong box
        [2.3, 0.0, -0.8],    # cách mép 0.3 m: trong vùng loại
        [3.0, 0.0, -0.8],    # cách mép 1.0 m: trong vành đai
        [0.0, 2.4, -0.8],    # cách mép 1.4 m: trong vành đai
        [4.0, 0.0, -0.8],    # cách mép 2.0 m: ngoài vành đai
    ])
    assert footprint_ring_mask(pts, b, inner=0.5, outer=1.5).tolist() == [False, False, True, True, False]
    with pytest.raises(ValueError):
        footprint_ring_mask(pts, b, inner=1.5, outer=0.5)


def test_footprint_is_counter_clockwise_and_has_box_area():
    fp = footprint(box(yaw=0.3))
    x, y = fp[:, 0], fp[:, 1]
    signed = 0.5 * (np.dot(x, np.roll(y, -1)) - np.dot(y, np.roll(x, -1)))
    assert signed > 0
    assert polygon_area(fp) == pytest.approx(8.0)
    assert polygon_area(footprint(box(), margin=0.5)) == pytest.approx(5.0 * 3.0)


def test_area_and_iou_are_stable_at_large_coordinates():
    # Tọa độ cỡ 10^6 m (như UTM): công thức shoelace không dời gốc sai tới ~4e-4 m².
    rng = np.random.default_rng(0)
    for _ in range(200):
        x, y, yaw = rng.uniform(-1e6, 1e6), rng.uniform(-1e6, 1e6), rng.uniform(-math.pi, math.pi)
        far_a = box(center=(x, y, 0.0), yaw=yaw)
        far_b = box(center=(x + 1.0, y + 0.5, 0.0), yaw=yaw + 0.5)
        near_a = far_a.replace(center=(0.0, 0.0, 0.0))
        near_b = far_b.replace(center=(1.0, 0.5, 0.0))
        assert polygon_area(footprint(far_a)) == pytest.approx(8.0, abs=1e-8)
        assert bev_iou(far_a, far_b) == pytest.approx(bev_iou(near_a, near_b), abs=1e-8)


def test_quaternion_and_pose_helpers():
    # Quay 90° quanh z: [cos 45°, 0, 0, sin 45°]
    q = [math.cos(math.pi / 4), 0.0, 0.0, math.sin(math.pi / 4)]
    np.testing.assert_allclose(quaternion_to_matrix(q), [[0, -1, 0], [1, 0, 0], [0, 0, 1]], atol=1e-12)
    np.testing.assert_allclose(quaternion_to_matrix([2.0, 0, 0, 0]), np.eye(3))  # tự chuẩn hóa
    with pytest.raises(ValueError):
        quaternion_to_matrix([0, 0, 0, 0])
    pose = pose_matrix([1.0, 2.0, 3.0], q)
    np.testing.assert_allclose(transform_points(np.array([[1.0, 0.0, 0.0]]), pose), [[1.0, 3.0, 3.0]], atol=1e-12)
    np.testing.assert_allclose(invert_pose(pose) @ pose, np.eye(4), atol=1e-12)


def test_transform_points():
    m = np.eye(4)
    m[:3, :3] = [[0, -1, 0], [1, 0, 0], [0, 0, 1]]  # quay 90° quanh z
    m[:3, 3] = [10, 0, 1]
    out = transform_points(np.array([[1.0, 0.0, 0.0]]), m)
    np.testing.assert_allclose(out, [[10.0, 1.0, 1.0]])
    with pytest.raises(ValueError):
        transform_points(np.zeros((1, 3)), np.eye(3))


def test_bev_iou():
    a = box(dims=(2.0, 1.0, 1.0))
    assert bev_iou(a, a) == pytest.approx(1.0)
    # lệch 1 m theo x: giao 1 m², hợp 3 m²
    assert bev_iou(a, a.replace(center=(1.0, 0.0, 0.0))) == pytest.approx(1 / 3)
    assert bev_iou(a, a.replace(center=(5.0, 0.0, 0.0))) == 0.0
    # hình vuông quay 90° trùng với chính nó
    sq = box(dims=(2.0, 2.0, 1.0))
    assert bev_iou(sq, sq.replace(yaw=math.pi / 2)) == pytest.approx(1.0)
    # chạm cạnh và cạnh trùng phương: không chia cho 0
    assert bev_iou(a, a.replace(center=(2.0, 0.0, 0.0))) == pytest.approx(0.0)
    assert bev_iou(a, a.replace(center=(0.0, 0.5, 0.0))) == pytest.approx(1 / 3)
    # hình vuông quay 45°: giao là bát giác đều, diện tích 8(√2 − 1)
    expected_inter = 8 * (math.sqrt(2) - 1)
    assert bev_iou(sq, sq.replace(yaw=math.pi / 4)) == pytest.approx(expected_inter / (8 - expected_inter))


def test_rotate_to_ego():
    # Điểm: (x=1, y=2, z=3) -> (x=2, y=-1, z=3)
    pts = np.array([[1.0, 2.0, 3.0, 10.0]], dtype=np.float32)
    rotated = rotate_points_z90(pts)
    np.testing.assert_allclose(rotated, [[2.0, -1.0, 3.0, 10.0]])

    # Box: tâm (1, 2, 3), yaw pi/2 -> tâm (2, -1, 3), yaw 0
    b = box(center=(1.0, 2.0, 3.0), dims=(4.0, 2.0, 1.5), yaw=math.pi / 2)
    b_ego = rotate_cuboid_to_ego(b)
    assert b_ego.center == (2.0, -1.0, 3.0)
    assert b_ego.yaw == pytest.approx(0.0)
    assert b_ego.dims == (4.0, 2.0, 1.5)

    # Điểm trong box giữ nguyên sau khi cả hai cùng quay
    inside = np.array([[1.0, 2.0, 3.0], [1.0, 2.0 + 1.5, 3.0]], dtype=np.float32)
    mask_orig = points_in_cuboid(inside, b)
    mask_ego = points_in_cuboid(rotate_points_z90(inside), b_ego)
    np.testing.assert_array_equal(mask_orig, mask_ego)

    # Pose: quay 90° quanh z thì sensor_to_world @ rot4.T giữ nguyên tọa độ world của điểm
    pose = pose_matrix([10.0, 20.0, 0.0], [1.0, 0.0, 0.0, 0.0])
    ego_pose = rotate_pose_to_ego(pose)
    p_world_orig = transform_points(inside, pose)
    p_world_ego = transform_points(rotate_points_z90(inside), ego_pose)
    np.testing.assert_allclose(p_world_orig, p_world_ego, atol=1e-12)

