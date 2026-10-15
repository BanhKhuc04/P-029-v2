"""Comprehensive verification test suite for M2 Iteration 2 Challenger (challenger_m2_r2_1).

Empirically challenges:
1. Direct `track=None` stress across all rules:
   - `heading.flip`
   - `heading.motion`
   - `heading.points`
   - `fit.outside`
   - `size.in_track`
   - `floating`
   under various combinations of `points` (None, empty, noisy, dense) and `finding_details` (None, populated).
2. Deep assertion that returned objects are strictly valid BoxRepairDelta instances with finite numbers.
3. Multi-track scanner clearance across 6 permutations with full scan residual check (0 errors, 0 warnings).
4. Boundary condition check: fit.outside padding does not bleed into size.in_track warning.
"""

from __future__ import annotations

import itertools
import math
import numpy as np
import pytest

from pointsnap.core.config import load_config
from pointsnap.core.model import Cuboid, Severity
from pointsnap.core.repair import (
    BoxRepairDelta,
    SimpleFrameSource,
    compute_box_repair,
    verify_repaired_box_passes_scanner,
)
from pointsnap.core.scanner import scan_cuboids


def _make_sample_box() -> Cuboid:
    return Cuboid(
        center=(10.0, 5.0, -1.0),
        dims=(4.5, 1.9, 1.6),
        yaw=0.25,
        label="car",
        frame=0,
        track_id=1,
    )


def _generate_synthetic_lidar_frame(
    box: Cuboid,
    ground_z: float = -1.8,
    seed: int = 42,
    noise_std: float = 0.01,
) -> np.ndarray:
    rng = np.random.default_rng(seed)
    gx = rng.uniform(box.center[0] - 12, box.center[0] + 12, 5000)
    gy = rng.uniform(box.center[1] - 12, box.center[1] + 12, 5000)
    gz = np.full(5000, ground_z) + rng.normal(0, noise_std, 5000)
    ground = np.column_stack([gx, gy, gz])

    l, w, h = box.dims
    n_pts = 60
    front = np.column_stack([np.full(n_pts, l / 2), rng.uniform(-w / 2, w / 2, n_pts)])
    left = np.column_stack([rng.uniform(-l / 2, l / 2, n_pts), np.full(n_pts, w / 2)])
    local_2d = np.vstack([front, left]) + rng.normal(0, noise_std, (2 * n_pts, 2))

    c, s = math.cos(box.yaw), math.sin(box.yaw)
    rot = np.array([[c, s], [-s, c]])
    world_xy = local_2d @ rot + np.array(box.center[:2])
    z = rng.uniform(ground_z + 0.3, ground_z + h, len(local_2d))
    car_pts = np.column_stack([world_xy, z])

    return np.vstack([ground, car_pts])


def _assert_valid_delta(delta: BoxRepairDelta, expected_rule: str):
    assert isinstance(delta, BoxRepairDelta)
    assert delta.rule == expected_rule
    assert len(delta.delta_center) == 3
    assert len(delta.delta_dims) == 3
    for c in delta.delta_center:
        assert math.isfinite(c)
    for d in delta.delta_dims:
        assert math.isfinite(d)
    assert math.isfinite(delta.delta_yaw)
    assert 0.0 <= delta.confidence <= 1.0
    assert math.isfinite(delta.target_offset_m)
    assert isinstance(delta.reason, str) and len(delta.reason) > 0

    rep = delta.repaired_cuboid
    assert isinstance(rep, Cuboid)
    for c in rep.center:
        assert math.isfinite(c)
    for d in rep.dims:
        assert math.isfinite(d)
        assert d > 0.0
    assert math.isfinite(rep.yaw)


ALL_RULES = [
    "heading.flip",
    "heading.motion",
    "heading.points",
    "fit.outside",
    "size.in_track",
    "floating",
]


@pytest.mark.parametrize("rule", ALL_RULES)
def test_direct_track_none_no_points_no_details(rule: str):
    """Stress test: track=None, points=None, finding_details=None."""
    box = _make_sample_box()
    delta = compute_box_repair(box, None, None, rule=rule, finding_details=None)
    _assert_valid_delta(delta, rule)


@pytest.mark.parametrize("rule", ALL_RULES)
def test_direct_track_none_with_empty_points(rule: str):
    """Stress test: track=None, points=empty array."""
    box = _make_sample_box()
    pts = np.zeros((0, 3), dtype=np.float32)
    delta = compute_box_repair(box, None, pts, rule=rule, finding_details=None)
    _assert_valid_delta(delta, rule)


@pytest.mark.parametrize("rule", ALL_RULES)
def test_direct_track_none_with_dense_points(rule: str):
    """Stress test: track=None, points=dense LiDAR point cloud."""
    box = _make_sample_box()
    pts = _generate_synthetic_lidar_frame(box, ground_z=-1.8, seed=42)
    delta = compute_box_repair(box, None, pts, rule=rule, finding_details=None)
    _assert_valid_delta(delta, rule)


@pytest.mark.parametrize("rule", ALL_RULES)
def test_direct_track_none_with_finding_details(rule: str):
    """Stress test: track=None, populated finding_details."""
    box = _make_sample_box()
    pts = _generate_synthetic_lidar_frame(box, ground_z=-1.8, seed=42)
    details = {
        "track_heading_deg": 45.0,
        "track_median_distance": -0.05,
        "deviation_deg": 15.0,
        "ground_contact_distance": -0.20,
    }
    delta = compute_box_repair(box, None, pts, rule=rule, finding_details=details)
    _assert_valid_delta(delta, rule)


def test_fit_outside_pad_does_not_trigger_size_in_track_warning():
    """Confirms fit.outside expansion doesn't trigger secondary size.in_track warning."""
    dims = (4.5, 1.9, 1.6)
    ground_z = -1.8
    cz = ground_z + dims[2] / 2.0
    track = [
        Cuboid(center=(4.0 * f, 0.0, cz), dims=dims, yaw=0.0, label="car", frame=f, track_id=1)
        for f in range(4)
    ]
    # seed 300 triggers point cloud with span_y ~ 1.905m
    pts_by_frame = {f: _generate_synthetic_lidar_frame(track[f], ground_z=ground_z, seed=300 + f) for f in range(4)}

    defect_track = list(track)
    defect_track[3] = defect_track[3].replace(dims=(4.5, 1.0, 1.6))

    delta = compute_box_repair(defect_track[3], defect_track, pts_by_frame[3], rule="fit.outside")
    repaired_track = list(defect_track)
    repaired_track[3] = delta.repaired_cuboid

    cfg = load_config()
    frames = SimpleFrameSource(pts_by_frame)
    findings = scan_cuboids(repaired_track, config=cfg, frames=frames)

    # 0 warnings, 0 errors
    assert len(findings) == 0


def test_all_6_repair_permutations_zero_residuals():
    """Confirms all 3! = 6 repair permutations result in 0 residual errors & warnings."""
    dims = (4.5, 1.9, 1.6)
    ground_z = -1.8
    cz = ground_z + dims[2] / 2.0
    track = [
        Cuboid(center=(4.0 * f, 0.0, cz), dims=dims, yaw=0.0, label="car", frame=f, track_id=1)
        for f in range(4)
    ]
    pts_by_frame = {f: _generate_synthetic_lidar_frame(track[f], ground_z=ground_z, seed=700 + f) for f in range(4)}

    repair_plan = [(1, "floating"), (2, "heading.flip"), (3, "fit.outside")]
    cfg = load_config()
    frames = SimpleFrameSource(pts_by_frame)

    for perm in itertools.permutations(repair_plan):
        cur_track = list(track)
        cur_track[1] = cur_track[1].replace(
            center=(cur_track[1].center[0], cur_track[1].center[1], cur_track[1].center[2] + 0.35)
        )
        cur_track[2] = cur_track[2].replace(yaw=math.pi)
        cur_track[3] = cur_track[3].replace(dims=(4.5, 1.0, 1.6))

        for frame_idx, rule in perm:
            delta = compute_box_repair(cur_track[frame_idx], cur_track, pts_by_frame[frame_idx], rule=rule, finding_details={"target_yaw_sensor": 0.0, "track_median_distance": 0.0})
            cur_track[frame_idx] = delta.repaired_cuboid

        findings = scan_cuboids(cur_track, config=cfg, frames=frames)
        assert len(findings) == 0, f"Permutation {perm} left residual findings: {findings}"
