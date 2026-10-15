"""Empirical Challenger 1: Adversarial Stress Test Suite for Assisted 3D Box Repair.

Focus:
1. Floating Repair Stress:
   - Point cloud sparsity: 0 pt, 1 pt, 5 pts, 14 pts, 15 pts, 16 pts, 1000 pts, 20000 pts.
   - Ground noise: zero noise, moderate noise, extreme Gaussian noise (sigma=0.5m), bimodal/curb ground.
   - Inverted and extreme heights: z in [-1000, 1000], negative offsets, inverted bottom coordinates.
   - Mathematical invariants: delta_center[:2] == (0, 0), dims unchanged, yaw unchanged, confidence in [0, 1].

2. Heading Repair Stress:
   - heading.flip: exact boundary angles (0, pi/2, pi, -pi, 2pi, -2pi, 100pi, machine eps near pi).
   - Symmetric / cancelling peer orientations (atan2(0, 0) singularity).
   - heading.points: sparse points (<10), exactly 10, collinear points, circular distribution, identical points.
   - heading.motion: threshold boundary (0.49m vs 0.51m), reversing flag, collinear motion, negative X/Y axes.
   - heading.static: target_yaw_sensor handling, missing target_yaw_sensor handling (ValueError / safe fallback).

3. Fit & Size Repair Stress:
   - fit.loose: all valid faces (đầu, đuôi, bên trái, bên phải, đầu và đuôi), invalid/missing face fallback.
   - fit.outside: extreme outliers (points at +/-1000m vs percentile trimming), tight point cluster (1mm spread).
   - size.in_track: bottom_z preservation invariant (delta_center[2] == delta_dims[2] / 2), single vs multi-peer.
   - size.class_range: all 5 standard classes (car, bus, truck, pedestrian, bicycle) with extreme dims.

4. Scanner Clearance Verification across all rule permutations & frame source permutations.
"""

from __future__ import annotations

import math
import numpy as np
import pytest

from pointsnap.core.config import load_config
from pointsnap.core.geometry import normalize_angle
from pointsnap.core.model import Cuboid, Severity
from pointsnap.core.repair import (
    BoxRepairDelta,
    SimpleFrameSource,
    compute_box_repair,
    verify_repaired_box_passes_scanner,
)
from pointsnap.core.scanner import scan_cuboids
from pointsnap.core.synthetic import inject_floating, inject_size_in_track
from tests.test_repair import _scene_ground_points


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


def _assert_strict_invariants(delta: BoxRepairDelta):
    """Enforces mathematical invariants on BoxRepairDelta."""
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
    assert 0.0 <= delta.confidence <= 1.0
    assert math.isfinite(delta.target_offset_m)

    rep = delta.repaired_cuboid
    assert isinstance(rep, Cuboid)
    for c in rep.center:
        assert math.isfinite(c)
    for d in rep.dims:
        assert math.isfinite(d)
        assert d > 0.0
    assert math.isfinite(rep.yaw)
    assert -math.pi <= rep.yaw <= math.pi

    d_dict = delta.to_dict()
    assert "delta_center" in d_dict
    assert "delta_dims" in d_dict
    assert "delta_yaw" in d_dict
    assert "repaired_cuboid" in d_dict
    assert "repaired_box" in d_dict
    assert "confidence" in d_dict


# ==============================================================================
# SECTION 1: FLOATING REPAIR EMPIRICAL STRESS
# ==============================================================================


@pytest.mark.parametrize("n_points", [0, 1, 5, 14])
def test_floating_sparse_points_under_threshold(n_points: int):
    """Under 15 points: ring_ground_for_box cannot estimate ground. Fallback to delta=0, conf=0 without details."""
    box = _make_box(z=0.0, h=1.6)
    track = [box]
    rng = np.random.default_rng(42)
    if n_points > 0:
        pts = rng.uniform(-2.0, 2.0, (n_points, 3)) + np.array(box.center)
    else:
        pts = np.zeros((0, 3), dtype=np.float64)

    delta = compute_box_repair(box, track, pts, rule="floating")
    _assert_strict_invariants(delta)
    assert delta.delta_center == (0.0, 0.0, 0.0)
    assert delta.confidence == 0.0
    assert delta.repaired_cuboid.center == box.center


@pytest.mark.parametrize("n_points", [15, 16, 50, 1000, 20000])
def test_floating_points_at_and_above_threshold(n_points: int):
    """At and above 15 points: estimate ground with confidence reduced without a track reference."""
    ground_z = -1.80
    h = 1.6
    # Box is floating +30cm above ground
    floating_cz = ground_z + h / 2.0 + 0.30
    box = _make_box(z=floating_cz, h=h)
    track = [box]

    rng = np.random.default_rng(101)
    # Generate points strictly within the footprint ring [inner=0.1, outer=0.8]
    # For a car: half-length = 2.25, half-width = 0.95
    # Along front/back edges: x in [2.35, 2.85], y in [-0.8, 0.8]
    l_half = box.dims[0] / 2.0
    w_half = box.dims[1] / 2.0

    # Distribute n_points around the 4 sides of the ring
    pts_list = []
    for i in range(n_points):
        side = i % 4
        if side == 0:  # Front ring
            x = box.center[0] + l_half + rng.uniform(0.15, 0.65)
            y = box.center[1] + rng.uniform(-w_half, w_half)
        elif side == 1:  # Back ring
            x = box.center[0] - l_half - rng.uniform(0.15, 0.65)
            y = box.center[1] + rng.uniform(-w_half, w_half)
        elif side == 2:  # Left ring
            x = box.center[0] + rng.uniform(-l_half, l_half)
            y = box.center[1] + w_half + rng.uniform(0.15, 0.65)
        else:  # Right ring
            x = box.center[0] + rng.uniform(-l_half, l_half)
            y = box.center[1] - w_half - rng.uniform(0.15, 0.65)
        z = ground_z + rng.normal(0, 0.005)
        pts_list.append([x, y, z])

    pts = np.array(pts_list, dtype=np.float64)

    delta = compute_box_repair(box, track, pts, rule="floating")
    _assert_strict_invariants(delta)
    assert delta.delta_center[2] == pytest.approx(-0.30, abs=0.04)
    assert delta.repaired_cuboid.bottom_z == pytest.approx(ground_z, abs=0.04)
    assert 0 < delta.confidence <= 0.75


@pytest.mark.parametrize("noise_std", [0.0, 0.05, 0.15, 0.30, 0.50])
def test_floating_ground_noise_robustness(noise_std: float):
    """Stress test ground estimation with increasing Gaussian elevation noise."""
    ground_z = -1.50
    h = 1.6
    box = _make_box(z=ground_z + h / 2.0 + 0.40, h=h)
    track = [box]

    rng = np.random.default_rng(202)
    n_points = 500
    l_half = box.dims[0] / 2.0
    w_half = box.dims[1] / 2.0

    pts_list = []
    for i in range(n_points):
        side = i % 4
        if side == 0:
            x = box.center[0] + l_half + rng.uniform(0.15, 0.65)
            y = box.center[1] + rng.uniform(-w_half, w_half)
        elif side == 1:
            x = box.center[0] - l_half - rng.uniform(0.15, 0.65)
            y = box.center[1] + rng.uniform(-w_half, w_half)
        elif side == 2:
            x = box.center[0] + rng.uniform(-l_half, l_half)
            y = box.center[1] + w_half + rng.uniform(0.15, 0.65)
        else:
            x = box.center[0] + rng.uniform(-l_half, l_half)
            y = box.center[1] - w_half - rng.uniform(0.15, 0.65)
        z = ground_z + rng.normal(0, noise_std)
        pts_list.append([x, y, z])

    pts = np.array(pts_list, dtype=np.float64)

    delta = compute_box_repair(box, track, pts, rule="floating")
    _assert_strict_invariants(delta)
    # Under noise, delta lowers the box
    assert delta.delta_center[2] < 0.0
    assert delta.repaired_cuboid.bottom_z == pytest.approx(ground_z, abs=max(0.08, noise_std * 1.5))


def test_floating_bimodal_curb_ground():
    """Ground with a curb: 50% road at -1.8m, 50% sidewalk at -1.6m."""
    h = 1.6
    # Box parked on road at -1.8m, floating by 25cm
    box = _make_box(z=-1.8 + h / 2.0 + 0.25, h=h)
    rng = np.random.default_rng(303)
    n = 300
    l_half = box.dims[0] / 2.0
    w_half = box.dims[1] / 2.0

    pts_list = []
    for i in range(n):
        side = i % 4
        if side == 0:
            x = box.center[0] + l_half + rng.uniform(0.15, 0.65)
            y = box.center[1] + rng.uniform(-w_half, w_half)
        elif side == 1:
            x = box.center[0] - l_half - rng.uniform(0.15, 0.65)
            y = box.center[1] + rng.uniform(-w_half, w_half)
        elif side == 2:
            x = box.center[0] + rng.uniform(-l_half, l_half)
            y = box.center[1] + w_half + rng.uniform(0.15, 0.65)
        else:
            x = box.center[0] + rng.uniform(-l_half, l_half)
            y = box.center[1] - w_half - rng.uniform(0.15, 0.65)
        gz = -1.6 if y > box.center[1] else -1.8
        gz += rng.normal(0, 0.01)
        pts_list.append([x, y, gz])

    pts = np.array(pts_list, dtype=np.float64)

    delta = compute_box_repair(box, [box], pts, rule="floating")
    _assert_strict_invariants(delta)
    assert 0 < delta.confidence <= 0.75
    assert delta.delta_center[2] < 0.0


@pytest.mark.parametrize("extreme_cz,delta_target", [
    (-1000.0, 0.35),
    (1000.0, -0.35),
    (0.0001, 0.20),
    (-0.0001, -0.20),
])
def test_floating_extreme_elevations_with_finding_details(extreme_cz: float, delta_target: float):
    """Stress test inverted, zero-crossing, and extreme elevations (+/- 1000m) via finding_details."""
    box = _make_box(z=extreme_cz)
    details = {
        "distance": delta_target,
        "track_median_distance": 0.0,
        "num_ground_points": 40,
    }
    delta = compute_box_repair(box, [box], None, rule="floating", finding_details=details)
    _assert_strict_invariants(delta)
    assert delta.delta_center[2] == pytest.approx(-delta_target, abs=1e-4)
    assert delta.repaired_cuboid.center[2] == pytest.approx(extreme_cz - delta_target, abs=1e-4)
    assert 0 < delta.confidence <= 0.75


# ==============================================================================
# SECTION 2: HEADING REPAIR EMPIRICAL STRESS
# ==============================================================================


@pytest.mark.parametrize("ref_yaw,flip_yaw", [
    (0.0, 0.0),
    (0.0, math.pi / 2),
    (0.0, math.pi),
    (0.0, -math.pi),
    (0.0, 2 * math.pi),
    (math.pi, 0.0),
    (math.pi, -math.pi),
    (math.pi - 1e-10, -math.pi + 1e-10),
    (-math.pi + 1e-10, math.pi - 1e-10),
    (math.pi / 4, math.pi / 4 + math.pi),
    (-3 * math.pi / 4, math.pi / 4),
    (100 * math.pi, 101 * math.pi),
])
def test_heading_flip_boundary_and_wraparound_angles(ref_yaw: float, flip_yaw: float):
    """Stress test heading.flip across all boundary angles, periodic multiples, and epsilon crossings."""
    norm_ref = normalize_angle(ref_yaw)
    box = _make_box(yaw=flip_yaw, frame=1)
    peer0 = _make_box(yaw=norm_ref, frame=0)
    peer2 = _make_box(yaw=norm_ref, frame=2)
    track = [peer0, box, peer2]

    delta = compute_box_repair(box, track, points=None, rule="heading.flip", finding_details={"target_yaw_sensor": norm_ref})
    _assert_strict_invariants(delta)
    # The repaired cuboid yaw should align with norm_ref modulo 2pi
    angle_diff = abs(normalize_angle(delta.repaired_cuboid.yaw - norm_ref))
    assert angle_diff == pytest.approx(0.0, abs=1e-4)


def test_heading_flip_antipodal_peers_cancellation():
    """When peer 1 has yaw=pi/2 and peer 2 has yaw=-pi/2, mean vector cancels out to (0, 0).
    atan2(0, 0) in numpy / math evaluates to 0.0. Invariant holds without crash.
    """
    box = _make_box(yaw=math.pi, frame=1)
    peer0 = _make_box(yaw=math.pi / 2, frame=0)
    peer2 = _make_box(yaw=-math.pi / 2, frame=2)
    track = [peer0, box, peer2]

    delta = compute_box_repair(box, track, points=None, rule="heading.flip")
    _assert_strict_invariants(delta)
    assert abs(delta.repaired_cuboid.yaw) <= math.pi


@pytest.mark.parametrize("dx,dy,expected_success", [
    (0.499, 0.0, False),    # Just below 0.5m velocity threshold across 2 adjacent boxes
    (0.501, 0.0, True),     # Just above 0.5m velocity threshold
    (0.0, -0.499, False),   # Below threshold along -Y
    (0.0, -0.501, True),    # Above threshold along -Y (yaw = -pi/2)
    (-1.0, 0.0, True),      # Moving along -X (yaw = pi)
    (0.0, 0.0, False),      # Perfectly stationary
    (1e-12, 1e-12, False),  # Floating point epsilon
])
def test_heading_motion_velocity_threshold_boundary(dx: float, dy: float, expected_success: bool):
    """heading.motion has an explicit 0.5m displacement threshold between peers."""
    b0 = _make_box(x=0.0, y=0.0, yaw=0.0, frame=0)
    b1 = _make_box(x=dx, y=dy, yaw=math.pi / 2.0, frame=1)
    track = [b0, b1]

    delta = compute_box_repair(b1, track, points=None, rule="heading.motion",
        finding_details={"target_yaw_sensor": math.atan2(dy, dx)} if expected_success else {})
    _assert_strict_invariants(delta)

    if expected_success:
        assert delta.confidence >= 0.90
        expected_yaw = math.atan2(dy, dx)
        assert abs(normalize_angle(delta.repaired_cuboid.yaw - expected_yaw)) < 1e-4
    else:
        assert delta.confidence == 0.0
        assert delta.delta_yaw == 0.0


def test_heading_motion_reversing_guard():
    """When maybe_reversing is True, heading.motion must suppress rotation for safety."""
    b0 = _make_box(x=0.0, y=0.0, yaw=0.0, frame=0)
    b1 = _make_box(x=5.0, y=0.0, yaw=math.pi, frame=1)
    b2 = _make_box(x=10.0, y=0.0, yaw=0.0, frame=2)
    track = [b0, b1, b2]

    delta = compute_box_repair(b1, track, points=None, rule="heading.motion", finding_details={"maybe_reversing": True})
    _assert_strict_invariants(delta)
    assert delta.confidence == 0.0
    assert delta.delta_yaw == 0.0


@pytest.mark.parametrize("target_yaw", [0.0, math.pi / 2, math.pi, -math.pi, 2 * math.pi, -1.23])
def test_heading_static_with_target_yaw_sensor(target_yaw: float):
    """heading.static when target_yaw_sensor is present in finding_details."""
    box = _make_box(yaw=0.1)
    delta = compute_box_repair(
        box, [box], points=None, rule="heading.static", finding_details={"target_yaw_sensor": target_yaw}
    )
    _assert_strict_invariants(delta)
    expected_norm = normalize_angle(target_yaw)
    assert abs(normalize_angle(delta.repaired_cuboid.yaw - expected_norm)) < 1e-4
    assert delta.confidence >= 0.90


def test_heading_static_without_target_yaw_is_unavailable():
    """Thiếu hướng sensor thì không đề xuất xoay."""
    box = _make_box()
    delta = compute_box_repair(box, [box], points=None, rule="heading.static")
    assert delta.confidence == 0 and delta.delta_yaw == 0


def test_heading_points_nan_inf_filtering():
    """heading.points with NaNs and Infs in point cloud: points are filtered safely."""
    box = _make_box()
    nan_points = np.array([
        [np.nan, 0.0, 0.0],
        [10.0, np.inf, 0.0],
        [-np.inf, -np.inf, -np.inf],
    ])
    delta = compute_box_repair(box, [box], nan_points, rule="heading.points")
    _assert_strict_invariants(delta)
    assert delta.confidence == 0.0


# ==============================================================================
# SECTION 3: FIT & SIZE REPAIR EMPIRICAL STRESS
# ==============================================================================


@pytest.mark.parametrize("face,expected_axis", [
    ("đầu", 0),
    ("đuôi", 0),
    ("bên trái", 1),
    ("bên phải", 1),
    ("đầu và đuôi", 0),
])
def test_fit_loose_all_valid_faces(face: str, expected_axis: int):
    """fit.loose trims only the specified face using object points."""
    box = _make_box(l=5.0, w=2.2, h=1.6)
    # Generate 50 points inside box, slightly retracted from face
    rng = np.random.default_rng(404)
    local_pts = rng.uniform(-0.8, 0.8, (50, 3))
    # Transform to world
    world_pts = local_pts + np.array(box.center)

    delta = compute_box_repair(box, [box], world_pts, rule="fit.loose", finding_details={"face": face})
    _assert_strict_invariants(delta)
    assert delta.confidence == 0.85
    # The dimension along expected_axis should be tightened
    assert delta.repaired_cuboid.dims[expected_axis] <= box.dims[expected_axis] + 0.1


@pytest.mark.parametrize("invalid_face", ["", "nóc xe", "gầm xe", "invalid_face_xyz"])
def test_fit_loose_invalid_face_graceful_fallback(invalid_face: str):
    """Invalid or missing face name falls back safely without crash."""
    box = _make_box()
    pts = np.random.randn(50, 3) + np.array(box.center)
    delta = compute_box_repair(box, [box], pts, rule="fit.loose", finding_details={"face": invalid_face})
    _assert_strict_invariants(delta)
    assert delta.confidence == 0.0
    assert delta.delta_dims == (0.0, 0.0, 0.0)


def test_fit_outside_extreme_outliers_percentile_trimming():
    """fit.outside uses 1st and 99th percentiles (p1, p99) to reject single distant outliers."""
    box = _make_box(l=4.5, w=1.9, h=1.6)
    rng = np.random.default_rng(505)

    # 200 normal points tightly bounded in 4.0 x 1.8 x 1.5
    normal_local = rng.uniform(-0.9, 0.9, (200, 3))
    normal_pts = normal_local + np.array(box.center)

    # Add 2 extreme outlier points (+/- 1000m)
    outliers = np.array([
        [box.center[0] + 1000.0, box.center[1], box.center[2]],
        [box.center[0] - 1000.0, box.center[1], box.center[2]],
    ])
    pts = np.vstack([normal_pts, outliers])

    # Sửa fit.outside
    delta = compute_box_repair(box, [box], pts, rule="fit.outside")
    _assert_strict_invariants(delta)
    # The repaired box length must NOT be 2000m!
    assert delta.repaired_cuboid.length < 20.0
    assert delta.repaired_cuboid.length > 0.5


def test_fit_outside_tight_point_cluster():
    """100 points concentrated in a 1mm cube."""
    box = _make_box(l=4.5, w=1.9, h=1.6)
    pts = np.full((100, 3), box.center) + np.random.uniform(-0.001, 0.001, (100, 3))

    delta = compute_box_repair(box, [box], pts, rule="fit.outside")
    _assert_strict_invariants(delta)
    # Box dimensions remain positive and valid
    assert delta.repaired_cuboid.length >= 0.1
    assert delta.repaired_cuboid.width >= 0.1
    assert delta.repaired_cuboid.height >= 0.1


def test_size_in_track_bottom_z_preservation_invariant():
    """size.in_track must preserve bottom_z when adjusting height (delta_center[2] == delta_dims[2] / 2.0)."""
    # Track with 4 boxes of height 2.0
    peers = [_make_box(h=2.0, frame=f) for f in [0, 1, 3, 4]]
    # Box at frame 2 has height 1.0 (undersized) with bottom at -0.5 (cz = 0.0, h = 1.0 -> bottom = -0.5)
    target = _make_box(z=0.0, h=1.0, frame=2)
    track = peers[:2] + [target] + peers[2:]

    delta = compute_box_repair(target, track, points=None, rule="size.in_track")
    _assert_strict_invariants(delta)

    # Repaired height should be 2.0
    assert delta.repaired_cuboid.height == pytest.approx(2.0)
    # Bottom Z must remain at -0.5
    assert delta.repaired_cuboid.bottom_z == pytest.approx(-0.5)
    # Invariant: delta_center[2] == (2.0 - 1.0) / 2 = 0.5
    assert delta.delta_center[2] == pytest.approx(0.5)


@pytest.mark.parametrize("label", ["car", "bus", "truck", "pedestrian", "bicycle"])
def test_size_class_range_extreme_dimensions(label: str):
    """size.class_range brings absurdly large dimensions back within standard boundaries."""
    giant_box = _make_box(l=100.0, w=50.0, h=50.0, label=label)
    delta = compute_box_repair(giant_box, [giant_box], points=None, rule="size.class_range")
    _assert_strict_invariants(delta)
    assert delta.repaired_cuboid.length < 50.0
    assert delta.repaired_cuboid.width < 20.0
    assert delta.repaired_cuboid.height < 20.0


# ==============================================================================
# SECTION 4: SCANNER CLEARANCE VERIFICATION ACROSS PERMUTATIONS
# ==============================================================================


@pytest.mark.parametrize("frame_source_type", ["none", "empty_array", "empty_dict", "simple_source"])
def test_verify_repaired_box_passes_scanner_frame_source_types(frame_source_type: str):
    """verify_repaired_box_passes_scanner supports all frame source representations without crash."""
    box = _make_box(z=-1.0)
    track = [_make_box(z=-1.0, frame=f) for f in range(3)]

    if frame_source_type == "none":
        source = None
    elif frame_source_type == "empty_array":
        source = np.zeros((0, 3))
    elif frame_source_type == "empty_dict":
        source = {f: np.zeros((0, 3)) for f in range(3)}
    elif frame_source_type == "simple_source":
        source = SimpleFrameSource({f: np.zeros((0, 3)) for f in range(3)})

    res = verify_repaired_box_passes_scanner(box, track, points=source, rule="heading.flip")
    assert isinstance(res, bool)


def test_scanner_clearance_all_repairable_rules():
    """Verify clearance for floating, heading.flip, and fit.outside sequentially."""
    ground_z = -1.8
    track = [
        Cuboid(center=(f * 5.0, 0.0, ground_z + 0.8), dims=(4.5, 1.9, 1.6), yaw=0.0, label="car", frame=f, track_id=1)
        for f in range(4)
    ]
    pts = _scene_ground_points(track, ground_z=ground_z)

    # Defect frame 1: floating (+0.35m)
    defect_track = list(track)
    defect_track[1] = defect_track[1].replace(center=(5.0, 0.0, ground_z + 0.8 + 0.35))
    # Defect frame 2: heading.flip (pi)
    defect_track[2] = defect_track[2].replace(yaw=math.pi)

    # 1. Before repair: frame 1 fails floating, frame 2 fails heading.flip
    assert verify_repaired_box_passes_scanner(defect_track[1], defect_track, points=pts, rule="floating") is False
    assert verify_repaired_box_passes_scanner(defect_track[2], defect_track, points=pts, rule="heading.flip") is False

    # 2. Repair frame 1 with ground points
    d1 = compute_box_repair(defect_track[1], defect_track, points=pts, rule="floating")
    defect_track[1] = d1.repaired_cuboid
    assert verify_repaired_box_passes_scanner(defect_track[1], defect_track, points=pts, rule="floating") is True

    # 3. Repair frame 2 with heading flip
    d2 = compute_box_repair(defect_track[2], defect_track, points=pts, rule="heading.flip", finding_details={"target_yaw_sensor": 0.0})
    defect_track[2] = d2.repaired_cuboid
    assert verify_repaired_box_passes_scanner(defect_track[2], defect_track, points=pts, rule="heading.flip") is True
