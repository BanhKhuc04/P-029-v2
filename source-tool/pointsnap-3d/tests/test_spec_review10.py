"""Independent counterexamples for review10; no scenario_sim oracle or live service."""

import dataclasses
import math
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
import yaml

from pointsnap.core.config import ConfigError, SpecConfig, default_config_text, load_config, parse_config
from pointsnap.core.gate import gate_verdict
from pointsnap.core.model import Cuboid, ErrorType, Finding, FrameData, Severity
from pointsnap.core.scanner import check_attributes, check_size, check_track, scan_coverage_gaps
from pointsnap.detectors.attributes import _overlap_fraction, detect_attribute_errors, detect_attribute_height, detect_rider_state, detect_spec_geometry
from pointsnap.detectors.size import relax_filled_oversize
from pointsnap.detectors.track import detect_id_swaps

CFG = load_config(Path(__file__).resolve().parents[1] / "pointsnap/guidelines/spec-vn.yaml", env={})


def vehicle(frame=0, track_id=1, **changes):
    return Cuboid((10, 0, .8), (4.5, 1.9, 1.6), 0, "Vehicle", frame, track_id=track_id,
                  attrs={"subtype": "car"}).replace(**changes)


def bike(frame=0, track_id=2, **changes):
    return Cuboid((10, 0, .7), (1.9, .8, 1.4), 0, "Two-wheels", frame, track_id=track_id,
                  attrs={"rider_state": "without_rider"}).replace(**changes)


def person(frame=0, track_id=3, **changes):
    return Cuboid((10, 0, .875), (.6, .6, 1.75), 0, "Pedestrian", frame, track_id=track_id,
                  attrs={"age_group": "adult", "pose": "standing"}).replace(**changes)


class Frames:
    def __init__(self, points=None, interval=.5, pose=True):
        self.points = np.empty((0, 3)) if points is None else points
        self.interval = interval
        self.pose = pose

    def frame_data(self, frame, with_points=True):
        return FrameData(frame=frame, points=self.points if with_points else np.empty((0, 3)),
                         sensor_to_world=np.eye(4) if self.pose else None, timestamp=frame * self.interval)


def poses(boxes):
    return {b.frame: np.eye(4) for b in boxes}


@pytest.mark.parametrize("partial", [False, True])
def test_rider_motion_needs_complete_world_pose(partial):
    boxes = [bike(f, center=(30 - 5 * f, 0, .7)) for f in range(5)]
    mapping = None
    if partial:
        mapping = {}
        for f in (0, 1):
            mapping[f] = np.eye(4)
            mapping[f][0, 3] = 5 * f
    assert detect_rider_state(boxes, CFG.spec, mapping) == []


def test_rider_speed_uses_actual_frame_timestamps_in_scanner():
    boxes = [bike(f, center=(10 + 3 * f, 0, .7)) for f in range(4)]
    found = check_attributes(SimpleNamespace(cuboids=boxes), CFG, Frames(interval=3))
    assert not any(f.rule == "attr.rider_state" for f in found)  # 1 m/s, not 6 m/s


def test_rider_without_pose_blocks_gate_when_it_is_the_only_rule():
    cfg = dataclasses.replace(CFG, rules=dataclasses.replace(CFG.rules, **{
        f.name: f.name == "attr_rider_state" for f in dataclasses.fields(CFG.rules)
    }))
    job = SimpleNamespace(cuboids=[bike(f) for f in range(3)])
    gaps = scan_coverage_gaps(job, cfg, Frames(pose=False))
    assert any("pose" in gap and "attr_rider_state" in gap for gap in gaps)
    assert not gate_verdict([], cfg.gate, coverage_gaps=gaps)[0]


def test_interpolation_cannot_hide_manual_height_error():
    boxes = [person(f, center=(10, 0, .6), dims=(.6, .6, 1.2)) for f in (0, 4)]
    boxes += [person(f, keyframe=False) for f in (1, 2, 3)]
    found = detect_attribute_height(boxes, CFG.spec)
    assert len(found) == 1 and found[0].details["frames"] == [0, 4]


def test_interpolation_cannot_create_rider_motion_warning():
    boxes = [bike(0), bike(5), bike(1, center=(30, 0, .7), keyframe=False),
             bike(2, center=(60, 0, .7), keyframe=False)]
    assert not detect_rider_state(boxes, CFG.spec, poses(boxes))


def test_notes_cannot_impersonate_spec_attributes():
    p = person(attrs={"age_group": "adult", "pose": "other", "note": "sitting"})
    assert not detect_attribute_height([p], CFG.spec)
    b = bike(attrs={"rider_state": "without_rider", "note": "with_rider"})
    assert not detect_spec_geometry([b, person()], CFG.spec)


def test_attribute_errors_do_not_merge_labels_under_one_id():
    spec = SpecConfig(required_attributes={"A": ("state",), "B": ("state",)})
    boxes = [vehicle(0, label="A", attrs={}), vehicle(1, label="B", attrs={})]
    assert {f.label for f in detect_attribute_errors(boxes, spec)} == {"A", "B"}


def test_rider_overlap_49_percent_is_not_50_percent():
    b = bike(dims=(1, 1, 1.4), attrs={"rider_state": "with_rider"})
    p = person(center=(10.3, .3, .875), dims=(1, 1, 1.75))
    # Rectangles overlap .7 x .7 m, inner area 1 m2: exact fraction .49.
    assert not detect_spec_geometry([b, p], CFG.spec)


def test_zero_track_id_is_aggregated_across_frames():
    boxes = [vehicle(f) for f in range(3)] + [person(f, track_id=0, center=(10.5, 0, .9),
              dims=(.6, .6, 1.2), attrs={"age_group": "adult", "pose": "sitting"}) for f in range(3)]
    found = [f for f in detect_spec_geometry(boxes, CFG.spec) if f.rule == "spec.inside"]
    assert len(found) == 1 and found[0].details["frames"] == [0, 1, 2]


@pytest.mark.parametrize("resume_motion", [False, True])
def test_dismount_requires_continuous_state_and_stopping(resume_motion):
    boxes = [bike(f, attrs={"rider_state": "with_rider"}) for f in range(8)]
    if resume_motion:
        boxes = [b.replace(center=(10 + max(0, b.frame - 4) * 3, 0, .7)) for b in boxes]
    else:
        boxes[5] = boxes[5].replace(attrs={"rider_state": "without_rider"})
    boxes += [person(f, track_id=9, center=(10, .8, .875)) for f in range(4, 8)]
    assert not any(f.details.get("kind") == "dismount" for f in detect_rider_state(boxes, CFG.spec, poses(boxes)))


def swapped_tracks(second_subtype="car", interpolate=False):
    boxes = []
    for f in range(4):
        for tid, subtype in ((1, "car"), (2, second_subtype)):
            side = tid - 1
            if f >= 2:
                side = 1 - side
            boxes.append(vehicle(f, track_id=tid, center=(10 + 2 * f, 3 * side, .8),
                                  attrs={"subtype": subtype}, keyframe=not (interpolate and f >= 2)))
    return boxes


def test_id_swap_scanner_respects_configured_subtypes():
    boxes = swapped_tracks("truck")
    assert not any(f.rule == "track.id_swap" for f in check_track(SimpleNamespace(cuboids=boxes), CFG, Frames()))


def test_id_swap_does_not_infer_manual_changes_from_interpolation():
    boxes = swapped_tracks(interpolate=True)
    assert not detect_id_swaps(boxes, CFG.track, poses(boxes))


def test_id_swap_partial_timestamps_use_one_time_basis():
    boxes = swapped_tracks()
    complete = {f: 1_000_000 + .5 * f for f in range(4)}
    partial = {f: t for f, t in complete.items() if f != 1}
    expected = detect_id_swaps(boxes, CFG.track, poses(boxes), complete)
    found = detect_id_swaps(boxes, CFG.track, poses(boxes), partial)
    assert expected and [(f.frame, f.severity) for f in found] == [(f.frame, f.severity) for f in expected]


@pytest.mark.parametrize("rider_state", [{"class": "Two-wheels"},
    {"class": "Two-wheels", "attribute": "rider_state", "with": "with_rider", "without": "without_rider",
     "person": "Pedestrian", "typo": "bad"}])
def test_active_rider_config_requires_complete_known_keys(rider_state):
    raw = yaml.safe_load(default_config_text())
    raw["spec"] = {"rider_state": rider_state}
    with pytest.raises(ConfigError, match="rider_state"):
        parse_config(raw, env={})


def filled_points(owner):
    return np.column_stack([np.linspace(owner.center[0] - owner.length / 2 + .02,
                                       owner.center[0] + owner.length / 2 - .02, 100),
                            np.linspace(owner.center[1] - owner.width / 2 + .02,
                                        owner.center[1] + owner.width / 2 - .02, 100),
                            np.full(100, owner.center[2])])


def test_cargo_relaxation_refuses_ambiguous_shapes():
    filled = bike(track_id=None, dims=(2.2, 1.6, 1.6), center=(10, 0, .8))
    empty = filled.replace(center=(20, 0, .8))
    finding = Finding(ErrorType.SIZE, "size.class_range", Severity.ERROR, 0, "Two-wheels", "oversize",
                      details={"dimension": "width", "bound_type": "lớn"})
    found = relax_filled_oversize([finding], [filled, empty], Frames(filled_points(filled)), ("Two-wheels",))
    assert found[0].severity is Severity.ERROR


def test_cargo_matches_the_named_subtype_not_notes():
    owner = vehicle(dims=(4.5, 4, 1.6), attrs={"subtype": "car", "note": "Tricycle"})
    found = check_size(SimpleNamespace(cuboids=[owner]), CFG, Frames(filled_points(owner)))
    oversize = [f for f in found if f.rule == "size.class_range" and f.details["bound_type"] == "lớn"]
    assert oversize and all(f.severity is Severity.ERROR for f in oversize)


def test_optional_declared_height_attribute_still_matches():
    cfg = SpecConfig(required_attributes={"Vehicle": ("subtype",)},
                     allowed_values={"Vehicle.pose": ("low",)}, attribute_height={"Vehicle/low": (.2, .6)})
    target = vehicle(attrs={"subtype": "car", "pose": "low"})
    assert len(detect_attribute_height([target], cfg)) == 1


def test_tiny_valid_footprint_does_not_divide_by_zero():
    tiny = person(dims=(1e-200, 1e-200, 1.75))
    assert _overlap_fraction(tiny, vehicle()) == 0


@pytest.mark.parametrize("yaw", [0, math.pi / 4, -math.pi / 3])
def test_exact_overlap_identity_and_disjoint_rotated_boxes(yaw):
    target = person(yaw=yaw)
    assert _overlap_fraction(target, target) == pytest.approx(1)
    assert _overlap_fraction(target, vehicle(center=(100, 100, .8))) == 0


def test_valid_mount_still_warns_with_real_pose_and_time():
    boxes = [bike(f, center=(10 + 3 * f, 0, .7)) for f in range(4)]
    found = check_attributes(SimpleNamespace(cuboids=boxes), CFG, Frames())
    assert any(f.rule == "attr.rider_state" and f.details["kind"] == "mount" for f in found)


def test_real_same_subtype_swap_still_reports():
    boxes = swapped_tracks()
    found = check_track(SimpleNamespace(cuboids=boxes), CFG, Frames())
    assert any(f.rule == "track.id_swap" and f.frame == 2 and f.severity is Severity.ERROR for f in found)


def test_unrelated_partial_pose_does_not_downgrade_valid_pair():
    boxes = swapped_tracks() + [vehicle(f, track_id=3, center=(100 + f, 0, .8)) for f in (0, 1, 2, 10)]
    found = detect_id_swaps(boxes, CFG.track, {f: np.eye(4) for f in range(4)})
    assert any(f.track_id == 1 and f.details["other_track_id"] == 2 and f.severity is Severity.ERROR for f in found)


@pytest.mark.parametrize("yaw", [0, math.pi / 3])
def test_inside_ignores_person_beside_and_above_vehicle(yaw):
    outer = vehicle(yaw=yaw)
    beside = person(center=(10 - math.sin(yaw) * 2, math.cos(yaw) * 2, .875))
    above = person(center=(10, 0, 2.475))  # bottom 1.6, on the roof
    assert not detect_spec_geometry([outer, beside, above], CFG.spec)


def test_scenario_sim_matches_independent_ego_transform_oracle():
    from scenario_sim import Obj, Scene, SimFrames, labels

    scene = Scene([Obj(1, "car", (4, 2, 2), lambda t: (20, 10, math.pi / 3))],
                  num_frames=1, ego=lambda t: (3, -2, math.pi / 2))
    [label] = labels(scene)
    assert label.center == pytest.approx((12, -17, -.8))
    assert label.yaw == pytest.approx(-math.pi / 6)
    points = SimFrames(scene).frame_data(0).points[:, :3]
    # Independent inverse of ego yaw=90deg; use neither sim nor core transform helpers.
    wx, wy, wz = 3 - points[:, 1], -2 + points[:, 0], 1.8 + points[:, 2]
    keep = wz > .3  # remove ground, retain object points
    dx, dy = wx[keep] - 20, wy[keep] - 10
    lx, ly = .5 * dx + math.sqrt(3) / 2 * dy, -math.sqrt(3) / 2 * dx + .5 * dy
    assert len(lx) > 30
    assert np.mean((np.abs(lx) <= 2.1) & (np.abs(ly) <= 1.1) & (wz[keep] <= 2.1)) > .99


def test_direct_cargo_api_does_not_guess_subtype_from_notes():
    owner = vehicle(dims=(4.5, 4, 1.6), attrs={"subtype": "car", "note": "Tricycle"})
    finding = Finding(ErrorType.SIZE, "size.class_range", Severity.ERROR, 0, "Vehicle", "oversize", track_id=1,
                      details={"dimension": "width", "bound_type": "lớn"})
    [found] = relax_filled_oversize([finding], [owner], Frames(filled_points(owner)), ("Vehicle/Tricycle",))
    assert found.severity is Severity.ERROR
