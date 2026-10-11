"""Luật bám spec theo hình học (việc C6): thuộc tính khớp chiều cao, người trong xe, người lái gán hai lần."""

from __future__ import annotations

from pathlib import Path

import pytest

from pointsnap.core.config import load_config
from pointsnap.core.model import Cuboid, Severity
from pointsnap.detectors.attributes import detect_attribute_height, detect_spec_geometry
from scenario_sim import Obj, Scene, parked, scan, straight

SPEC_VN = Path(__file__).resolve().parents[1] / "pointsnap" / "guidelines" / "spec-vn.yaml"


@pytest.fixture(scope="module")
def spec():
    return load_config(SPEC_VN).spec


def ped(frame=0, track_id=1, h=1.75, x=10.0, y=0.0, z_bottom=0.0, **attrs):
    attrs = {"age_group": "adult", "pose": "standing", **attrs}
    return Cuboid(center=(x, y, z_bottom + h / 2), dims=(0.6, 0.6, h), yaw=0.0, label="Pedestrian", frame=frame,
                  track_id=track_id, attrs=attrs)


def moto(frame=0, track_id=2, h=1.7, x=10.0, rider="with_rider"):
    return Cuboid(center=(x, 0.0, h / 2), dims=(1.9, 0.8, h), yaw=0.0, label="Two-wheels", frame=frame,
                  track_id=track_id, attrs={"rider_state": rider})


def car(frame=0, track_id=3, x=10.0):
    return Cuboid(center=(x, 0.0, 0.8), dims=(4.5, 1.9, 1.6), yaw=0.0, label="Vehicle", frame=frame, track_id=track_id,
                  attrs={"subtype": "car"})


def test_attribute_height_consistent_labels_pass(spec):
    boxes = [ped(f) for f in range(4)] + [moto(f) for f in range(4)] + [ped(f, 5, h=1.3, pose="sitting") for f in range(4)]
    assert detect_attribute_height(boxes, spec) == []


@pytest.mark.parametrize("box, key", [
    (dict(h=1.3), "Pedestrian/standing/adult"),            # đứng mà box thấp như người ngồi
    (dict(h=1.75, pose="sitting"), "Pedestrian/sitting"),   # ngồi mà box cao như người đứng
    (dict(h=1.75, age_group="child"), "Pedestrian/child"),  # trẻ em cao 1,75 m
])
def test_attribute_height_mismatch(spec, box, key):
    found = detect_attribute_height([ped(f, **box) for f in range(4)], spec)
    assert len(found) == 1 and found[0].details["key"] == key and found[0].severity is Severity.WARNING
    assert found[0].details["frames"] == [0, 1, 2, 3]


def test_rider_state_vs_height_and_run_split(spec):
    # Xe không người lái cao 1,8 m → báo; đổi thuộc tính giữa track thì xét từng đoạn
    boxes = [moto(f, h=1.8, rider="without_rider") for f in range(3)] + [moto(f, h=1.8) for f in range(3, 6)]
    found = detect_attribute_height(boxes, spec)
    assert [f.details["frames"] for f in found] == [[0, 1, 2]]


def test_person_inside_car_but_not_on_truck_bed(spec):
    inside = [car(f) for f in range(3)] + [ped(f, h=1.2, x=10.5, z_bottom=0.3, pose="sitting") for f in range(3)]
    found = detect_spec_geometry(inside, spec)
    assert [f.rule for f in found] == ["spec.inside"] and found[0].value == 3
    on_top = [car(0), ped(0, x=10.5, z_bottom=1.6)]  # đứng trên nóc / thùng xe: spec cho phép
    assert detect_spec_geometry(on_top, spec) == []
    beside = [car(0), ped(0, x=10.0)]
    beside[1] = beside[1].replace(center=(10.0, 1.5, 0.875))  # đứng cạnh xe, ngoài footprint
    assert detect_spec_geometry(beside, spec) == []


def test_rider_double_only_for_with_rider(spec):
    assert [f.rule for f in detect_spec_geometry([moto(0), ped(0)], spec)] == ["spec.rider_double"]
    assert detect_spec_geometry([moto(0, rider="without_rider"), ped(0)], spec) == []  # người dắt / đứng cạnh xe
    assert detect_spec_geometry([moto(0), ped(0, x=12.0)], spec) == []  # người đứng cách xe


def test_rules_inactive_without_spec_config():
    cfg = load_config(None).spec
    boxes = [car(0), ped(0, h=1.2, x=10.5, z_bottom=0.3, pose="sitting")]
    assert detect_attribute_height(boxes, cfg) == [] and detect_spec_geometry(boxes, cfg) == []


def test_scenario_spec_vn_end_to_end():
    """Quét như thật trên cảnh mô phỏng với guideline spec-vn: chỉ báo đúng người ngồi trong xe."""
    scene = Scene([
        Obj(1, "Vehicle", (4.5, 1.9, 1.6), parked(12, 4, 0), attrs={"subtype": "car"}),
        Obj(2, "Pedestrian", (0.6, 0.6, 1.2), parked(12.5, 4.3, 0), hidden=set(range(12)),
            attrs={"age_group": "adult", "pose": "sitting"},
            labelled=lambda f, b: b.replace(center=(b.center[0], b.center[1], b.center[2] + 0.3),
                                            attrs={**b.attrs, "occluded": True})),
        Obj(3, "Pedestrian", (0.6, 0.6, 1.75), straight(5, 8, 0, 1.2), attrs={"age_group": "adult", "pose": "standing"}),
        Obj(4, "Two-wheels", (1.9, 0.8, 1.7), straight(0, -4, 0, 6), attrs={"rider_state": "with_rider"}),
    ])
    found = [f for f in scan(scene, SPEC_VN) if f.rule.startswith(("attr.", "spec."))]
    assert {f.rule for f in found} == {"spec.inside"}
