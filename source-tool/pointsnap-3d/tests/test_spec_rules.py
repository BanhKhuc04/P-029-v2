"""Kiểm thử luật bám spec gán nhãn (việc C2): track theo spec 4.4, thuộc tính bắt buộc, kích thước theo thuộc tính."""

from __future__ import annotations

import dataclasses

import numpy as np
import pytest

from pointsnap.core.config import SpecConfig, load_config
from pointsnap.core.model import Cuboid, ErrorType, Severity, add_track_markers
from pointsnap.core.scanner import scan_cuboids
from pointsnap.detectors.attributes import detect_attribute_errors
from pointsnap.detectors.size import detect_size, range_key
from pointsnap.detectors.track import detect_track_spec


def car(frame, track_id=1, x=None, **kw):
    return Cuboid(center=(frame * 2.0 if x is None else x, 0.0, 0.0), dims=(4.5, 1.9, 1.6), yaw=0.0, label="car",
                  frame=frame, track_id=track_id, **kw)


@pytest.fixture
def track_config():
    return load_config().track


# --- add_track_markers -------------------------------------------------------------------------------


def test_short_gap_becomes_occluded_keyframe_with_interpolated_pose():
    boxes = add_track_markers([car(0), car(1), car(4), car(5)], num_frames=8)
    hidden = [b for b in boxes if b.attrs.get("occluded")]
    assert [(b.frame, b.track_id, b.center[0]) for b in hidden] == [(2, 1, pytest.approx(4.0))]
    assert not any(b.outside for b in boxes if b.frame < 5)
    assert [b.frame for b in boxes if b.outside] == [6]  # track hết ở frame 5, cảnh dài 8 frame


def test_long_gap_ends_track_and_new_id_for_rest():
    boxes = add_track_markers([car(0), car(1), car(10), car(11), car(0, track_id=7, x=50.0)], num_frames=12)
    by_track = {}
    for b in boxes:
        by_track.setdefault(b.track_id, []).append((b.frame, b.outside))
    assert by_track[1] == [(0, False), (1, False), (2, True)]
    assert by_track[8] == [(10, False), (11, False)]  # id mới = id lớn nhất (7) + 1
    assert by_track[7] == [(0, False), (1, True)]


def test_markers_produce_no_spec_findings(track_config):
    boxes = add_track_markers([car(0), car(1), car(4), car(5), car(15), car(16)], num_frames=20)
    assert detect_track_spec([b for b in boxes if b.track_id == 1], track_config) == []


# --- track.reuse_id / track.occluded_long -----------------------------------------------------------


def test_reuse_after_outside_is_flagged_with_advice(track_config):
    short = [car(0), car(1), car(2, outside=True), car(4)]
    [finding] = detect_track_spec(short, track_config)
    assert finding.rule == "track.reuse_id" and finding.severity is Severity.WARNING and finding.frame == 4
    assert "occluded" in finding.message
    long = [car(0), car(1), car(2, outside=True), car(12)]
    [finding] = detect_track_spec(long, track_config)
    assert "track mới" in finding.message and finding.value == 10


def test_occluded_longer_than_limit_is_flagged(track_config):
    boxes = [car(0), car(1, attrs={"occluded": True}), car(9), car(10)]
    [finding] = detect_track_spec(boxes, track_config)
    assert finding.rule == "track.occluded_long" and finding.frame == 1 and finding.value == 8
    ok = [car(0), car(1, attrs={"occluded": True}), car(5)]
    assert detect_track_spec(ok, track_config) == []


# --- thuộc tính ---------------------------------------------------------------------------------------


SPEC = SpecConfig(
    required_attributes={"Vehicle": ("subtype",), "Pedestrian": ("age_group", "pose")},
    allowed_values={"subtype": ("car", "bus", "other"), "Pedestrian.pose": ("standing", "sitting", "bending")},
)


def veh(frame, track_id=1, **attrs):
    return Cuboid(center=(0, 0, 0), dims=(4.5, 1.9, 1.6), yaw=0.0, label="Vehicle", frame=frame, track_id=track_id,
                  attrs=attrs)


def test_missing_attribute_reported_once_per_track():
    findings = detect_attribute_errors([veh(0), veh(1), veh(2, subtype="car")], SPEC)
    [finding] = findings
    assert (finding.rule, finding.severity, finding.error_type) == ("attr.missing", Severity.ERROR, ErrorType.ATTRIBUTE)
    assert finding.frame == 0 and finding.details["frames"] == [0, 1] and "subtype" in finding.message


def test_invalid_value_and_label_specific_list():
    ped = Cuboid(center=(0, 0, 0), dims=(0.7, 0.7, 1.7), yaw=0.0, label="Pedestrian", frame=0, track_id=2,
                 attrs={"age_group": "adult", "pose": "walking"})
    findings = detect_attribute_errors([veh(0, subtype="tank"), ped], SPEC)
    assert sorted((f.rule, f.details["attribute"], f.details["value"]) for f in findings) == [
        ("attr.invalid", "pose", "walking"), ("attr.invalid", "subtype", "tank")]


def test_empty_spec_reports_nothing():
    assert detect_attribute_errors([veh(0)], SpecConfig()) == []


def test_attribute_rules_wired_into_scanner():
    config = dataclasses.replace(load_config(), spec=SPEC)
    assert any(f.rule == "attr.missing" for f in scan_cuboids([veh(0)], config))
    off = dataclasses.replace(config, rules=dataclasses.replace(config.rules, attr_missing=False))
    assert not any(f.rule == "attr.missing" for f in scan_cuboids([veh(0)], off))


# --- kích thước theo thuộc tính phân loại --------------------------------------------------------------


def test_size_range_keyed_by_subtype():
    size = dataclasses.replace(load_config().size, key_attributes={"Vehicle": "subtype"},
                               manual_ranges={"Vehicle/car": {"length": (3.5, 5.8), "width": (1.6, 2.4),
                                                              "height": (1.3, 2.3)},
                                              "Vehicle/bus": {"length": (6.0, 18.5), "width": (2.2, 3.2),
                                                              "height": (2.4, 4.5)}})
    bus = veh(0, track_id=None, subtype="bus")
    assert range_key(bus, size, size.manual_ranges) == "Vehicle/bus"
    assert range_key(veh(0, subtype="van"), size, size.manual_ranges) == "Vehicle"
    # Box dài 4.5 m: đúng cỡ ô tô, quá ngắn so với xe buýt.
    assert detect_size([veh(0, track_id=None, subtype="car")], size) == []
    findings = detect_size([bus], size)
    assert findings and "Vehicle/bus" in findings[0].message


# --- vật đứng yên (C3) -------------------------------------------------------------------------------


def _parked(changes=None, n=6):
    boxes = [Cuboid(center=(10.0, 5.0, 0.0), dims=(4.5, 1.9, 1.6), yaw=0.3, label="car", frame=f, track_id=1)
             for f in range(n)]
    for frame, kw in (changes or {}).items():
        boxes[frame] = boxes[frame].replace(**kw)
    return boxes


POSES = {f: np.eye(4) for f in range(10)}


def test_static_shift_and_rotation_detected():
    from pointsnap.core.config import StaticConfig
    from pointsnap.detectors.static import detect_static_errors

    cfg = StaticConfig()
    assert detect_static_errors(_parked(), cfg, POSES) == []
    shifted = _parked({3: {"center": (10.3, 5.0, 0.0)}})
    [f] = detect_static_errors(shifted, cfg, POSES)
    assert (f.rule, f.frame, f.severity) == ("track.static_shift", 3, Severity.WARNING)
    rotated = _parked({2: {"yaw": 0.3 + 0.25}})  # ~14°
    [f] = detect_static_errors(rotated, cfg, POSES)
    assert (f.rule, f.frame, f.severity) == ("heading.static", 2, Severity.ERROR)
    assert detect_static_errors(rotated, cfg, None) == []  # không có pose xe thu thì không xét


def test_static_rules_skip_moving_and_pedestrian_yaw():
    from pointsnap.core.config import StaticConfig
    from pointsnap.detectors.static import detect_static_errors

    moving = [b.replace(center=(10.0 + 2 * b.frame, 5.0, 0.0)) for b in _parked()]
    moving[3] = moving[3].replace(center=(16.4, 5.0, 0.0))
    assert detect_static_errors(moving, StaticConfig(), POSES) == []
    ped = [b.replace(label="pedestrian", dims=(0.7, 0.7, 1.7)) for b in _parked({2: {"yaw": 1.5}})]
    assert detect_static_errors(ped, StaticConfig(), POSES) == []
