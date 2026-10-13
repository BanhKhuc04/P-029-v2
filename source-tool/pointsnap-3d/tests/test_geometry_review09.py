"""Independent boundary/oracle cases for review 09; no model or live CVAT required."""

import dataclasses
import math
from types import SimpleNamespace

import numpy as np
import pytest

from pointsnap.core.box_points import box_point_sets
from pointsnap.core.config import load_config
from pointsnap.core.gate import gate_verdict
from pointsnap.core.ground import GroundEstimate, OtherBoxPoints, ring_ground_for_box
from pointsnap.core.model import Cuboid, FrameData, Severity
from pointsnap.core.scanner import scan_coverage_gaps
from pointsnap.detectors.fit import LooseMeasure, OutsideMeasure, loose_findings, outside_findings
from pointsnap.detectors.floating import estimate_scene_ground, floating_findings_by_track
from pointsnap.detectors.heading import angle_diff_deg, detect_heading_track, heading_points_findings
from pointsnap.detectors.track import detect_track_jumps_for_track


CFG = load_config(env={})
SINGLE = dataclasses.replace(CFG.floating, single_box=True)
"""Luật box lẻ (so tuyệt đối) đã tắt trong config mặc định từ 13/10; các ca dưới kiểm chính thuật toán đó."""


def box(frame=0, **changes):
    return Cuboid((10, 0, 0.8), (4.5, 1.9, 1.6), 0, "car", frame,
                  track_id=1, source_id=100 + frame).replace(**changes)


class Frames:
    def __init__(self, points, pose=True):
        self.points = points
        self.pose = pose

    def frame_data(self, frame, with_points=True):
        return FrameData(frame=frame, points=self.points if with_points else np.empty((0, 3)),
                         sensor_to_world=np.eye(4) if self.pose else None, timestamp=frame * 0.5)


def rotated_corner_ground():
    target = box(dims=(12, 12, 1.6), yaw=math.pi / 4)
    x, y = np.meshgrid(np.linspace(6.3, 6.6, 6), np.linspace(-6.6, -6.3, 6))
    # Explicit local -> world rotation; points are inside the .1-.8 m corner ring.
    points = np.column_stack([10 + (x.ravel() - y.ravel()) / math.sqrt(2),
                              (x.ravel() + y.ravel()) / math.sqrt(2), np.zeros(x.size)])
    return target, points


def test_scene_ground_keeps_rotated_ring_corners():
    target, points = rotated_corner_ground()
    cfg = dataclasses.replace(CFG.floating, sweeps=0)
    direct = ring_ground_for_box(points, target, ring_inner_m=cfg.ring_inner_m,
                                 ring_outer_m=cfg.ring_outer_m, min_ground_points=cfg.min_ground_points)
    assert direct.is_valid and direct.ground_z == pytest.approx(0)
    measured = estimate_scene_ground([target], Frames(points), cfg)[0][1]
    assert measured.is_valid
    assert measured.ground_z == pytest.approx(direct.ground_z)
    assert measured.num_ground_points == direct.num_ground_points


def test_fit_ground_keeps_rotated_ring_corners():
    target, points = rotated_corner_ground()
    item = box_point_sets(points, [target], margin=0.5, clearance=0.25)[0]
    assert item.ground_z == pytest.approx(0)


@pytest.mark.parametrize("rule", ["floating", "heading", "loose", "outside"])
def test_reference_never_mixes_classes_with_same_track_id(rule):
    target = box(2)
    peers = [box(i, label="truck") for i in (0, 1, 3)]
    if rule == "floating":
        estimates = [(b, GroundEstimate(ground_z=0, distance=0.25)) for b in peers + [target]]
        findings = floating_findings_by_track(estimates, SINGLE)
    elif rule == "heading":
        findings = heading_points_findings([(b, 25.0) for b in peers + [target]], CFG.heading.points)
    elif rule == "loose":
        findings = loose_findings([LooseMeasure(b, 0.6, "front", 100) for b in peers + [target]], CFG.fit)
    else:
        findings = outside_findings([OutsideMeasure(b, 90, 100, "front", 0.6) for b in peers + [target]], CFG.fit)
    assert any(f.frame == target.frame and f.label == "car" for f in findings)
    assert not any(f.label == "truck" for f in findings)


@pytest.mark.parametrize("reverse", [False, True])
def test_static_car_four_metre_jump_at_distant_end(reverse):
    positions = [(0, 14.0), (5, 10.0), (6, 10.0), (7, 10.0)]
    if reverse:
        positions = [(7 - f, x) for f, x in reversed(positions)]
    boxes = [box(f, center=(x, 0, 0.8)) for f, x in positions]
    findings = detect_track_jumps_for_track(boxes, CFG.track, {b.frame: np.eye(4) for b in boxes})
    assert [(f.frame, f.value) for f in findings] == [(7 if reverse else 0, pytest.approx(4.0))]
    assert findings[0].details["segment_end"]


@pytest.mark.parametrize("yaw", [0.0, math.pi / 4, -math.pi / 3])
def test_indexed_points_match_independent_oriented_box_oracle(yaw):
    rng = np.random.default_rng(9)
    points = np.vstack([rng.uniform(-5, 5, (1200, 3)), [[3.5, 0, 0], [-3.5, 0, 0]]])
    boxes = [box(center=(0, 0, 0), yaw=yaw), box(center=(1, 0, 0), yaw=-yaw)]
    cloud = OtherBoxPoints(points, boxes)
    reach, margin = 3.5, 0.15
    for i, target in enumerate(boxes):
        blocked = np.zeros(len(points), dtype=bool)
        for j, neighbour in enumerate(boxes):
            if j == i:
                continue
            delta = points - neighbour.center
            c, s = math.cos(neighbour.yaw), math.sin(neighbour.yaw)
            local = np.column_stack([c * delta[:, 0] + s * delta[:, 1],
                                      -s * delta[:, 0] + c * delta[:, 1], delta[:, 2]])
            blocked |= np.all(np.abs(local) <= np.asarray(neighbour.dims) / 2 + margin, axis=1)
        near = (np.abs(points[:, 0] - target.center[0]) <= reach) & (np.abs(points[:, 1] - target.center[1]) <= reach)
        np.testing.assert_array_equal(cloud.near(*target.center[:2], reach), np.flatnonzero(near))
        np.testing.assert_array_equal(cloud.without_others(i, reach), points[near & ~blocked])


@pytest.mark.parametrize("partial", [False, True])
def test_motion_is_suppressed_when_ego_pose_is_missing(partial):
    boxes = [box(f, center=(30 - 5 * f, 5, 0.8)) for f in range(5)]
    poses = {b.frame: np.eye(4) for b in boxes[:-1]} if partial else None
    assert not detect_heading_track(boxes, CFG.heading, sensor_to_world=poses)
    assert angle_diff_deg(math.radians(179), math.radians(-179)) == pytest.approx(2)


@pytest.mark.parametrize("level,delta", [("warning", -1e-6), ("warning", 0), ("warning", 1e-6),
                                         ("error", -1e-6), ("error", 0), ("error", 1e-6)])
def test_heading_points_threshold_boundary(level, delta):
    cfg = CFG.heading.points
    value = (cfg.warning_deg if level == "warning" else cfg.error_deg) + delta
    found = heading_points_findings([(box(track_id=None), value)], cfg)
    expected = None if level == "warning" and delta <= 0 else (
        Severity.ERROR if level == "error" and delta > 0 else Severity.WARNING)
    assert [f.severity for f in found] == ([] if expected is None else [expected])


@pytest.mark.parametrize("level,delta", [("warning", -1e-6), ("warning", 0), ("warning", 1e-6),
                                         ("error", -1e-6), ("error", 0), ("error", 1e-6)])
def test_floating_single_threshold_boundary(level, delta):
    cfg = SINGLE
    distance = (cfg.single_warning_m if level == "warning" else cfg.single_error_m) + delta
    found = floating_findings_by_track([(box(track_id=None), GroundEstimate(ground_z=0, distance=distance))], cfg)
    expected = None if level == "warning" and delta <= 0 else (
        Severity.ERROR if level == "error" and delta > 0 else Severity.WARNING)
    assert [f.severity for f in found] == ([] if expected is None else [expected])


@pytest.mark.parametrize("points", [np.empty((0, 3)), np.array([[0, 0, 0]])])
def test_insufficient_ground_is_evidence_gap_not_clean(points):
    target = box()
    measured = estimate_scene_ground([target], Frames(points), dataclasses.replace(CFG.floating, sweeps=0))
    findings = floating_findings_by_track(measured, CFG.floating)
    assert [f.rule for f in findings] == ["floating.no_evidence"]
    job = SimpleNamespace(cuboids=[target])
    gaps = scan_coverage_gaps(job, CFG, Frames(points))
    assert not gate_verdict(findings, CFG.gate, coverage_gaps=gaps)[0]


def test_loose_steady_track_is_a_known_relative_rule_limit():
    steady = [LooseMeasure(box(i), 0.6, "front", 100) for i in range(5)]
    assert not loose_findings(steady, CFG.fit)
    spike = [dataclasses.replace(m, gap_m=1.2) if m.box.frame == 2 else m for m in steady]
    assert [f.frame for f in loose_findings(spike, CFG.fit)] == [2]
