"""Sót đối tượng bằng LiDAR (việc C7): cụm điểm di chuyển mà không có box."""

from __future__ import annotations

import math

from pointsnap.core.config import load_config
from pointsnap.detectors.missing import _kind, detect_missing_objects
from scenario_sim import Obj, Scene, SimFrames, labels, parked, straight

CAR = (4.5, 1.9, 1.6)
PED = (0.6, 0.6, 1.75)


def _unlabelled(scene: Scene, *track_ids: int):
    """Nhãn của cảnh nhưng bỏ hẳn các track `track_ids` (người gán quên vẽ)."""
    return [b for b in labels(scene) if b.track_id not in track_ids]


def _missing(scene, boxes):
    return detect_missing_objects(boxes, SimFrames(scene), load_config(None).missing)[0]


def test_unlabelled_moving_car_is_found():
    scene = Scene([Obj(1, "car", CAR, straight(-10, 5, 0, 8)), Obj(2, "car", CAR, parked(12, -5, 0.3))])
    found = _missing(scene, _unlabelled(scene, 1))
    assert len(found) == 1
    f = found[0]
    assert f.rule == "lidar.missing" and f.label == "xe" and f.severity.value == "warning"
    assert len(f.details["frames"]) >= 3 and f.source_id is None


def test_unlabelled_walking_person_is_found():
    scene = Scene([Obj(1, "pedestrian", PED, straight(5, 6, 0.3, 1.3))], num_frames=12)
    found = _missing(scene, _unlabelled(scene, 1))
    assert [f.label for f in found] == ["người"]


def test_clean_labels_and_static_unlabelled_objects_are_quiet():
    scene = Scene([Obj(1, "car", CAR, straight(-10, 5, 0, 8)), Obj(2, "car", CAR, parked(12, -5, 0.3)),
                   Obj(3, "pedestrian", PED, straight(5, 8, 1.2, 1.3))])
    assert _missing(scene, labels(scene)) == []
    # Xe đỗ không gán (có thể là vật ngoài phạm vi gán nhãn): đứng yên nên không báo
    assert _missing(scene, _unlabelled(scene, 2)) == []


def test_static_object_seen_from_moving_ego_is_quiet():
    """Xe thu chạy, vật đứng yên không gán: phần nhìn thấy đổi theo góc nhìn nhưng chỗ đứng vẫn bị chiếm."""
    scene = Scene([Obj(1, "car", CAR, parked(15, 6, 0.4)), Obj(2, "car", CAR, parked(25, -6, 1.2))],
                  ego=lambda t: (5 * t, 0.0, 0.0))
    assert _missing(scene, []) == []


def test_heavy_rain_is_quiet():
    scene = Scene([Obj(1, "car", CAR, straight(-10, 4, 0, 10))], rain=10000)
    assert _missing(scene, labels(scene)) == []


def test_kind_by_size():
    assert _kind(0.6, 0.4, 1.7) == "người"
    assert _kind(1.9, 0.7, 1.5) == "xe hai bánh"
    assert _kind(4.4, 0.3, 1.4) == "xe"  # chỉ thấy hông xe
    assert _kind(12.0, 0.5, 3.2) == "xe dài"
    assert _kind(2.5, 1.0, 3.2) is None  # ngắn mà cao: tán cây, biển báo
    assert _kind(25.0, 0.4, 2.0) is None  # tường dài
    assert math.isclose(load_config(None).missing.min_points_per_cell, 1.2)
