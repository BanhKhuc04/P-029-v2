"""Empirical adversarial stress test and fuzzing suite for pointsnap.core.repair.

Authored by: challenger_m2_1 (M2 Challenger - Empirical Stress & Fuzzing)
Focus areas:
1. Extreme Z heights (+100m, -100m, close to zero, elevated ground, underground).
2. Wild heading flips (various angle differences, wrap-around at ±pi, motion singularity).
3. Corner case point clouds (0 points, 1 point, 2-4 points, collinear, far away, identical).
4. Invariant checks: finite floats, positive dimensions, normalized angles, valid confidence [0, 1].
5. Scanner clearance robustness with degenerate frame sources.
"""

from __future__ import annotations

import json
import math
import numpy as np
import pytest

from pointsnap.core.config import load_config
from pointsnap.core.geometry import normalize_angle
from pointsnap.core.model import Cuboid, Severity
from pointsnap.core.repair import (
    BoxRepairDelta,
    compute_box_repair,
    verify_repaired_box_passes_scanner,
)
from pointsnap.core.synthetic import inject_floating, inject_size_in_track


def _make_box(
    x: float = 10.0,
    y: float = 0.0,
    z: float = 0.0,
    l: float = 4.5,
    w: float = 1.9,
    h: float = 1.6,
    yaw: float = 0.0,
    label: str = "car",
    frame: int = 0,
    track_id: int = 1,
    outside: bool = False,
    attrs: dict | None = None,
) -> Cuboid:
    return Cuboid(
        center=(float(x), float(y), float(z)),
        dims=(float(l), float(w), float(h)),
        yaw=float(yaw),
        label=label,
        frame=frame,
        track_id=track_id,
        outside=outside,
        attrs=attrs or {},
    )


def _assert_valid_delta(delta: BoxRepairDelta, allow_empty: bool = False):
    """Kiểm tra các bất biến toán học của BoxRepairDelta."""
    assert isinstance(delta, BoxRepairDelta)
    assert len(delta.delta_center) == 3
    assert len(delta.delta_dims) == 3
    for v in delta.delta_center:
        assert isinstance(v, float)
        assert math.isfinite(v)
    for v in delta.delta_dims:
        assert isinstance(v, float)
        assert math.isfinite(v)
    assert isinstance(delta.delta_yaw, float)
    assert math.isfinite(delta.delta_yaw)
    assert -math.pi <= delta.delta_yaw <= math.pi

    # Confidence phải nằm trong [0.0, 1.0]
    assert 0.0 <= delta.confidence <= 1.0

    # Target offset phải là số thực hữu hạn
    assert math.isfinite(delta.target_offset_m)

    # Repaired cuboid phải hợp lệ
    rep = delta.repaired_cuboid
    assert isinstance(rep, Cuboid)
    for c in rep.center:
        assert math.isfinite(c)
    for d in rep.dims:
        assert math.isfinite(d)
        assert d > 0.0
    assert math.isfinite(rep.yaw)
    assert -math.pi <= rep.yaw <= math.pi

    # JSON serializable
    d_dict = delta.to_dict()
    json_str = json.dumps(d_dict)
    assert len(json_str) > 0


# ==============================================================================
# 1. EXTREME Z HEIGHTS (+100m, -100m, close to zero, elevated ground, underground)
# ==============================================================================


@pytest.mark.parametrize("extreme_z", [100.0, 500.0, -100.0, -500.0, 0.0, 1e-6, -1e-6])
def test_repair_floating_extreme_z_without_ground_points(extreme_z: float):
    """Hộp ở cao độ cực hạn khi không có điểm ground cục bộ: fallback an toàn, delta=0, confidence=0."""
    box = _make_box(z=extreme_z)
    track = [box]
    # Point cloud ở xa hoặc rỗng
    pts = np.zeros((0, 3), dtype=np.float64)

    delta = compute_box_repair(box, track, pts, rule="floating")
    _assert_valid_delta(delta)

    assert delta.delta_center == (0.0, 0.0, 0.0)
    assert delta.confidence == 0.0
    assert delta.repaired_cuboid.center[2] == pytest.approx(extreme_z)


@pytest.mark.parametrize("extreme_z,ground_z", [
    (100.0 + 0.8 + 0.35, 100.0),    # Cầu vượt cao 100m, lơ lửng +35cm
    (100.0 + 0.8 - 0.25, 100.0),    # Cầu vượt cao 100m, lún -25cm
    (-100.0 + 0.8 + 0.40, -100.0),  # Hầm sâu 100m, lơ lửng +40cm
    (-100.0 + 0.8 - 0.30, -100.0),  # Hầm sâu 100m, lún -30cm
    (0.0 + 0.8 + 0.30, 0.0),        # Mốc mặt đất z=0, lơ lửng +30cm
    (0.0 + 0.8 - 0.20, 0.0),        # Mốc mặt đất z=0, lún -20cm
])
def test_repair_floating_extreme_z_with_local_ground_points(extreme_z: float, ground_z: float):
    """Hộp ở cao độ cực hạn nhưng có mặt đất thực tế ở cao độ đó: sửa chính xác về sát mặt đất."""
    h = 1.6
    box = _make_box(z=extreme_z, h=h)
    track = [box]

    # Tạo 200 điểm mặt đất phẳng quanh box ở cao độ ground_z
    rng = np.random.default_rng(123)
    xy = rng.uniform(-5.0, 5.0, (200, 2)) + np.array(box.center[:2])
    z = np.full(200, ground_z) + rng.normal(0, 0.005, 200)
    pts = np.column_stack([xy, z])

    delta = compute_box_repair(box, track, pts, rule="floating")
    _assert_valid_delta(delta)

    # Đáy box sau sửa phải sát ground_z
    expected_bottom = ground_z
    expected_cz = ground_z + h / 2.0
    assert delta.repaired_cuboid.bottom_z == pytest.approx(expected_bottom, abs=0.03)
    assert delta.repaired_cuboid.center[2] == pytest.approx(expected_cz, abs=0.03)
    assert 0 < delta.confidence <= 0.75


@pytest.mark.parametrize("extreme_z,offset", [
    (100.0, 0.45),
    (100.0, -0.35),
    (-100.0, 0.50),
    (-100.0, -0.40),
    (0.0, 0.30),
    (0.0, -0.25),
])
def test_repair_floating_extreme_z_from_finding_details(extreme_z: float, offset: float):
    """Khi chỉ có finding_details (không có point cloud), sửa chính xác theo offset từ scanner."""
    box = _make_box(z=extreme_z)
    details = {
        "distance": offset,
        "track_median_distance": 0.0,
        "num_ground_points": 25,
    }
    delta = compute_box_repair(box, [box], None, rule="floating", finding_details=details)
    _assert_valid_delta(delta)

    assert delta.delta_center[2] == pytest.approx(-offset, abs=0.001)
    assert delta.repaired_cuboid.center[2] == pytest.approx(extreme_z - offset, abs=0.001)
    assert 0 < delta.confidence <= 0.75


# ==============================================================================
# 2. WILD HEADING FLIPS & ANGLE BOUNDARY CONDITIONS
# ==============================================================================


@pytest.mark.parametrize("delta_angle", [
    0.0,
    math.pi / 6,
    math.pi / 4,
    math.pi / 2,
    math.pi * 3 / 4,
    math.pi,
    -math.pi,
    math.pi + 1e-5,
    -math.pi - 1e-5,
    2 * math.pi,
    -2 * math.pi,
    100 * math.pi,
    -99 * math.pi,
    1e-7,
    -1e-7,
])
def test_heading_flip_various_angle_differences(delta_angle: float):
    """Kiểm tra xử lý góc xoay bất kỳ và điều kiện biên ±pi."""
    ref_yaw = 0.5  # góc chuẩn
    box_yaw = normalize_angle(ref_yaw + delta_angle)
    box = _make_box(yaw=box_yaw, frame=1)

    peer1 = _make_box(yaw=ref_yaw, frame=0)
    peer2 = _make_box(yaw=ref_yaw, frame=2)
    track = [peer1, box, peer2]

    delta = compute_box_repair(box, track, points=None, rule="heading.flip", finding_details={"target_yaw_sensor": ref_yaw})
    _assert_valid_delta(delta)

    # Repaired yaw phải hội tụ về ref_yaw
    angle_err = abs(normalize_angle(delta.repaired_cuboid.yaw - ref_yaw))
    assert angle_err == pytest.approx(0.0, abs=1e-5)
    assert delta.confidence >= 0.90


@pytest.mark.parametrize("dx,dy,expected_yaw_or_flip", [
    (10.0, 0.0, 0.0),                   # Đi thẳng theo trục +x
    (-10.0, 0.0, math.pi),              # Đi lùi theo trục -x -> yaw = pi (-pi)
    (0.0, 10.0, math.pi / 2.0),         # Rẽ trái theo trục +y -> yaw = pi/2
    (0.0, -10.0, -math.pi / 2.0),       # Rẽ phải theo trục -y -> yaw = -pi/2
    (1e-8, 1e-8, "insufficient_motion"),
    (0.0, 0.0, "insufficient_motion"),
])
def test_heading_motion_vector_stress(dx: float, dy: float, expected_yaw_or_flip: float | str):
    """Kiểm tra heading.motion với các vector vận tốc đa dạng và điểm kỳ dị đứng yên."""
    b0 = _make_box(x=0.0, y=0.0, yaw=0.0, frame=0)
    b1 = _make_box(x=dx, y=dy, yaw=math.pi / 4.0, frame=1)  # box cần sửa
    b2 = _make_box(x=2 * dx, y=2 * dy, yaw=0.0, frame=2)
    track = [b0, b1, b2]

    delta = compute_box_repair(b1, track, points=None, rule="heading.motion",
        finding_details={"target_yaw_sensor": expected_yaw_or_flip} if expected_yaw_or_flip != "insufficient_motion" else {})
    _assert_valid_delta(delta)

    if expected_yaw_or_flip == "insufficient_motion":
        assert delta.delta_yaw == 0
        assert delta.confidence == 0
    else:
        assert abs(normalize_angle(delta.repaired_cuboid.yaw - float(expected_yaw_or_flip))) < 1e-4


# ==============================================================================
# 3. CORNER CASE POINT CLOUDS (0 pts, 1 pt, collinear, far away, identical)
# ==============================================================================


def test_point_cloud_empty():
    """Point cloud rỗng (0 điểm): tất cả các luật không được crash."""
    box = _make_box()
    track = [box]
    empty_pts = np.zeros((0, 3), dtype=np.float64)

    for rule in ["floating", "heading.flip", "heading.motion", "heading.points", "fit.outside", "fit.loose", "size.in_track"]:
        delta = compute_box_repair(box, track, empty_pts, rule=rule)
        _assert_valid_delta(delta)


def test_point_cloud_single_point():
    """Point cloud chỉ có 1 điểm duy nhất: không crash, fallback an toàn."""
    box = _make_box()
    track = [box]
    single_pt = np.array([[10.0, 0.0, 0.0]], dtype=np.float64)

    for rule in ["floating", "heading.points", "fit.outside"]:
        delta = compute_box_repair(box, track, single_pt, rule=rule)
        _assert_valid_delta(delta)


@pytest.mark.parametrize("n_points", [2, 3, 4])
def test_point_cloud_under_threshold(n_points: int):
    """Point cloud từ 2 đến 4 điểm (dưới ngưỡng tối thiểu 5-15 điểm): an toàn."""
    box = _make_box()
    track = [box]
    pts = np.array([[10.0 + 0.1 * i, 0.1 * i, 0.0] for i in range(n_points)], dtype=np.float64)

    for rule in ["floating", "heading.points", "fit.outside"]:
        delta = compute_box_repair(box, track, pts, rule=rule)
        _assert_valid_delta(delta)


def test_point_cloud_collinear_points():
    """Điểm cộng tuyến (100 điểm thẳng hàng 1D): không gây suy biến ma trận hay lỗi chia 0."""
    box = _make_box(l=4.5, w=1.9, h=1.6)
    track = [box]

    # 100 điểm thẳng hàng dọc theo trục x
    xs = np.linspace(-2.0, 2.0, 100)
    pts = np.column_stack([box.center[0] + xs, np.full(100, box.center[1]), np.full(100, box.center[2])])

    # Sửa fit.outside trên tập điểm cộng tuyến
    delta_fit = compute_box_repair(box, track, pts, rule="fit.outside")
    _assert_valid_delta(delta_fit)
    assert delta_fit.repaired_cuboid.length > 0.0
    assert delta_fit.repaired_cuboid.width > 0.0
    assert delta_fit.repaired_cuboid.height > 0.0

    # Sửa heading.points trên tập điểm cộng tuyến
    delta_heading = compute_box_repair(box, track, pts, rule="heading.points")
    _assert_valid_delta(delta_heading)


def test_point_cloud_identical_points():
    """50 điểm trùng khít nhau ở cùng một tọa độ: phương sai = 0, không chia cho 0."""
    box = _make_box()
    track = [box]
    pts = np.tile(np.array([box.center[0], box.center[1], box.center[2]]), (50, 1))

    for rule in ["floating", "heading.points", "fit.outside"]:
        delta = compute_box_repair(box, track, pts, rule=rule)
        _assert_valid_delta(delta)


def test_point_cloud_points_far_away():
    """1000 điểm ở khoảng cách rất xa (+10000m): ngoài phạm vi box, fallback an toàn."""
    box = _make_box(x=0.0, y=0.0, z=0.0)
    track = [box]
    pts = np.random.uniform(9900.0, 10100.0, (1000, 3))

    for rule in ["floating", "heading.points", "fit.outside"]:
        delta = compute_box_repair(box, track, pts, rule=rule)
        _assert_valid_delta(delta)


# ==============================================================================
# 4. SCANNER CLEARANCE UNDER ADVERSARIAL COMBINATIONS
# ==============================================================================


def test_scanner_clearance_with_none_points():
    """verify_repaired_box_passes_scanner khi points=None không crash và trả về boolean."""
    box = _make_box(z=-1.0)
    track = [_make_box(z=-1.0, frame=f) for f in range(5)]
    res = verify_repaired_box_passes_scanner(box, track, points=None, rule="heading.flip")
    assert isinstance(res, bool)


def test_scanner_clearance_with_empty_points():
    """verify_repaired_box_passes_scanner khi points rỗng không crash."""
    box = _make_box(z=-1.0)
    track = [_make_box(z=-1.0, frame=f) for f in range(5)]
    res = verify_repaired_box_passes_scanner(box, track, points=np.zeros((0, 3)), rule="heading.flip")
    assert isinstance(res, bool)


def test_scanner_clearance_with_dict_points():
    """verify_repaired_box_passes_scanner với points dạng dict {frame: pts}."""
    box = _make_box(z=-1.0)
    track = [_make_box(z=-1.0, frame=f) for f in range(3)]
    pts_dict = {
        0: np.zeros((0, 3)),
        1: np.array([[10.0, 0.0, -1.0]]),
        2: np.zeros((0, 3)),
    }
    res = verify_repaired_box_passes_scanner(box, track, points=pts_dict, rule="heading.flip")
    assert isinstance(res, bool)


# ==============================================================================
# 5. DEGENERATE TRACK COMBINATIONS
# ==============================================================================


def test_empty_track_list():
    """Track rỗng (chỉ có box được sửa nhưng track=[]) không crash."""
    box = _make_box()
    for rule in ["heading.flip", "heading.motion", "size.in_track"]:
        delta = compute_box_repair(box, [], points=None, rule=rule)
        _assert_valid_delta(delta)


def test_single_box_track():
    """Track chỉ chứa đúng 1 box (không có peers): không crash và có giá trị dự phòng hợp lý."""
    box = _make_box()
    track = [box]
    for rule in ["heading.flip", "heading.motion", "size.in_track"]:
        delta = compute_box_repair(box, track, points=None, rule=rule)
        _assert_valid_delta(delta)


# ==============================================================================
# 6. RANDOMIZED STRESS FUZZING (100+ randomized iterations per category)
# ==============================================================================


def test_fuzz_floating_random_parameters():
    """Fuzzing ngẫu nhiên 100 mẫu tham số box và ground cho floating: không crash, delta hữu hạn."""
    rng = np.random.default_rng(2026)
    for _ in range(100):
        cz = float(rng.uniform(-200.0, 200.0))
        box = _make_box(
            x=float(rng.uniform(-100.0, 100.0)),
            y=float(rng.uniform(-100.0, 100.0)),
            z=cz,
            l=float(rng.uniform(1.0, 15.0)),
            w=float(rng.uniform(1.0, 5.0)),
            h=float(rng.uniform(0.5, 4.0)),
            yaw=float(rng.uniform(-math.pi, math.pi)),
        )

        n_pts = int(rng.integers(0, 300))
        if n_pts > 0:
            xy = rng.uniform(-10.0, 10.0, (n_pts, 2)) + np.array(box.center[:2])
            gz = cz - box.dims[2] / 2.0 + rng.uniform(-2.0, 2.0)
            z = np.full(n_pts, gz) + rng.normal(0, 0.05, n_pts)
            pts = np.column_stack([xy, z])
        else:
            pts = np.zeros((0, 3))

        details = None
        if rng.random() > 0.5:
            details = {
                "distance": float(rng.uniform(-5.0, 5.0)),
                "track_median_distance": float(rng.uniform(-1.0, 1.0)),
                "num_ground_points": int(rng.integers(0, 50)),
            }

        delta = compute_box_repair(box, [box], pts, rule="floating", finding_details=details)
        _assert_valid_delta(delta)


def test_fuzz_heading_random_parameters():
    """Fuzzing ngẫu nhiên 100 mẫu track và hướng cho các luật heading."""
    rng = np.random.default_rng(2027)
    rules = ["heading.flip", "heading.motion", "heading.points"]
    for _ in range(100):
        n_peers = int(rng.integers(1, 10))
        track = [
            _make_box(
                x=float(rng.uniform(-50.0, 50.0)),
                y=float(rng.uniform(-50.0, 50.0)),
                yaw=float(rng.uniform(-math.pi, math.pi)),
                frame=i,
            )
            for i in range(n_peers)
        ]
        target = track[rng.integers(0, n_peers)]
        rule = rng.choice(rules)

        n_pts = int(rng.integers(0, 100))
        pts = rng.uniform(-10.0, 10.0, (n_pts, 3)) if n_pts > 0 else None

        details = None
        if rng.random() > 0.5:
            details = {
                "track_heading_deg": float(rng.uniform(-180.0, 180.0)),
                "deviation_deg": float(rng.uniform(-90.0, 90.0)),
                "track_median_deg": float(rng.uniform(-45.0, 45.0)),
            }

        delta = compute_box_repair(target, track, pts, rule=rule, finding_details=details)
        _assert_valid_delta(delta)


def test_fuzz_fit_and_size_random_parameters():
    """Fuzzing ngẫu nhiên 100 mẫu cho các luật fit và size."""
    rng = np.random.default_rng(2028)
    rules = ["fit.outside", "fit.loose", "size.in_track", "size.class_range"]
    labels = ["car", "bus", "truck", "pedestrian", "bicycle"]
    for _ in range(100):
        box = _make_box(
            l=float(rng.uniform(0.5, 12.0)),
            w=float(rng.uniform(0.5, 4.0)),
            h=float(rng.uniform(0.5, 4.0)),
            label=str(rng.choice(labels)),
        )
        peer = _make_box(
            l=float(rng.uniform(1.0, 10.0)),
            w=float(rng.uniform(1.0, 3.5)),
            h=float(rng.uniform(1.0, 3.5)),
            label=box.label,
            frame=1,
        )
        track = [box, peer]
        rule = str(rng.choice(rules))

        n_pts = int(rng.integers(0, 80))
        pts = rng.uniform(-15.0, 15.0, (n_pts, 3)) if n_pts > 0 else None

        delta = compute_box_repair(box, track, pts, rule=rule)
        _assert_valid_delta(delta)


# ==============================================================================
# 7. SCANNER CLEARANCE ON EXTREME ELEVATION & WRAP-AROUND YAW
# ==============================================================================


@pytest.mark.parametrize("ground_z,delta_z,expected_unrep", [
    (100.0, 0.35, False),   # Cầu vượt cao +100m, lơ lửng +35cm
    (-100.0, -0.35, False), # Hầm sâu -100m, lún -35cm
])
def test_scanner_clearance_extreme_elevation(ground_z: float, delta_z: float, expected_unrep: bool):
    """Xác nhận scanner clearance hoạt động chính xác ở cao độ cực hạn (+100m, -100m)."""
    from tests.test_repair import _scene_ground_points

    track = [
        Cuboid(center=(10.0 + f * 5.0, 0.0, ground_z + 0.8), dims=(4.5, 1.9, 1.6), yaw=0.0, label="car", frame=f, track_id=1)
        for f in range(5)
    ]
    injected, _ = inject_floating(track, track_id=1, frame=2, delta_z_m=delta_z)
    pts = _scene_ground_points(track, ground_z=ground_z)

    # Box chưa sửa phải không đạt scanner
    assert verify_repaired_box_passes_scanner(injected[2], injected, pts, rule="floating") is expected_unrep

    # Sau khi sửa phải đạt scanner
    delta = compute_box_repair(injected[2], injected, pts, rule="floating")
    _assert_valid_delta(delta)
    assert verify_repaired_box_passes_scanner(delta.repaired_cuboid, injected, pts, rule="floating") is True


@pytest.mark.parametrize("ref_yaw,flip_yaw", [
    (0.0, math.pi),
    (math.pi, 0.0),
    (3.10, 3.10 - math.pi),
    (-3.10, -3.10 + math.pi),
])
def test_scanner_clearance_heading_flip_boundary(ref_yaw: float, flip_yaw: float):
    """Xác nhận scanner clearance hoạt động chính xác khi heading đảo chiều quanh biên ±pi."""
    track = [
        Cuboid(center=(10.0 + f * 5.0, 0.0, 0.0), dims=(4.5, 1.9, 1.6), yaw=ref_yaw, label="car", frame=f, track_id=1)
        for f in range(5)
    ]
    track[2] = track[2].replace(yaw=flip_yaw)

    # Chưa sửa -> Không đạt
    assert verify_repaired_box_passes_scanner(track[2], track, points=None, rule="heading.flip") is False

    # Đã sửa -> Đạt
    delta = compute_box_repair(track[2], track, points=None, rule="heading.flip", finding_details={"target_yaw_sensor": ref_yaw})
    _assert_valid_delta(delta)
    assert verify_repaired_box_passes_scanner(delta.repaired_cuboid, track, points=None, rule="heading.flip") is True


# ==============================================================================
# 8. DATA HYGIENE & DEFENSIVE INPUT PARSING
# ==============================================================================


def test_nan_and_inf_points_graceful_fallback():
    """Tập điểm chứa NaN/Inf không gây exception và fallback an toàn."""
    box = _make_box()
    nan_pts = np.array([[np.nan, np.nan, np.nan], [np.inf, -np.inf, 0.0]])
    for rule in ["floating", "heading.points", "fit.outside"]:
        delta = compute_box_repair(box, [box], nan_pts, rule=rule)
        _assert_valid_delta(delta)


def test_multichannel_point_clouds():
    """Point cloud có số kênh bổ sung (x, y, z, intensity, ring...) xử lý bình thường."""
    box = _make_box()
    pts4 = np.random.randn(50, 4)
    pts5 = np.random.randn(50, 5)
    for pts in [pts4, pts5]:
        for rule in ["floating", "heading.points", "fit.outside"]:
            delta = compute_box_repair(box, [box], pts, rule=rule)
            _assert_valid_delta(delta)


def test_string_encoded_numbers_in_finding_details():
    """Chuỗi số trong finding_details được parse an toàn thành float."""
    box = _make_box()
    d1 = compute_box_repair(box, [box], None, rule="floating", finding_details={"distance": "0.35", "track_median_distance": "0.05"})
    _assert_valid_delta(d1)
    assert d1.delta_center[2] == pytest.approx(-0.30)

    d2 = compute_box_repair(box, [box], None, rule="heading.flip", finding_details={"track_heading_deg": "180.0"})
    _assert_valid_delta(d2)

    d3 = compute_box_repair(box, [box], None, rule="heading.points", finding_details={"deviation_deg": "25.0"})
    _assert_valid_delta(d3)


def test_all_peers_outside_or_occluded():
    """Tất cả các box peer đều bị đánh dấu outside hoặc occluded: không crash."""
    target = _make_box(frame=1)
    peer1 = _make_box(frame=0, outside=True)
    peer2 = _make_box(frame=2, attrs={"occluded": True})
    track = [peer1, target, peer2]
    for rule in ["floating", "heading.flip", "heading.motion", "heading.points", "fit.outside", "fit.loose", "size.in_track", "size.class_range"]:
        delta = compute_box_repair(target, track, points=None, rule=rule)
        _assert_valid_delta(delta)


def test_target_missing_from_track():
    """Hộp cần sửa không nằm trong danh sách track được truyền vào: không crash."""
    target = _make_box(frame=5)
    other = _make_box(frame=0)
    for rule in ["floating", "heading.flip", "heading.motion", "heading.points", "fit.outside", "fit.loose", "size.in_track", "size.class_range"]:
        delta = compute_box_repair(target, [other], points=None, rule=rule)
        _assert_valid_delta(delta)
    res = verify_repaired_box_passes_scanner(target, [other], points=None, rule="heading.flip")
    assert isinstance(res, bool)


