import json

import pytest

from pointsnap.adapters.cvat.shapes import NUM_POINTS, cuboid_to_points, points_to_geometry
from pointsnap.core.model import Cuboid
from pointsnap.core.serialize import load_cuboids, save_cuboids


def box(**kw):
    params = dict(center=(1.0, -2.0, 0.5), dims=(4.5, 2.0, 1.6), yaw=0.75, label="car", frame=3, track_id=7)
    params.update(kw)
    return Cuboid(**params)


def test_cuboid_to_cvat_points_layout():
    points = cuboid_to_points(box())
    assert len(points) == NUM_POINTS == 16
    assert points[:9] == [1.0, -2.0, 0.5, 0.0, 0.0, 0.75, 4.5, 2.0, 1.6]
    assert points[9:] == [0.0] * 7


def test_points_round_trip_and_keep_roll_pitch():
    original = box(attrs={"cvat_rx": 0.01, "cvat_ry": -0.02})
    geometry = points_to_geometry(cuboid_to_points(original))
    assert geometry == {"center": (1.0, -2.0, 0.5), "dims": (4.5, 2.0, 1.6), "yaw": 0.75, "roll": 0.01, "pitch": -0.02}
    with pytest.raises(ValueError):
        points_to_geometry([0.0] * 8)


def test_save_and_load_cuboids(tmp_path):
    boxes = [box(), box(frame=4, keyframe=False, attrs={"num_lidar_pts": 12}), box(track_id=None, outside=True)]
    path = tmp_path / "gt.json"
    save_cuboids(path, boxes, meta={"scene": "scene-0001"})
    loaded, meta = load_cuboids(path)
    assert loaded == boxes
    assert loaded[1].attrs == {"num_lidar_pts": 12}
    assert meta == {"scene": "scene-0001"}


def test_load_rejects_unknown_version(tmp_path):
    path = tmp_path / "old.json"
    path.write_text(json.dumps({"version": 99, "cuboids": []}), encoding="utf-8")
    with pytest.raises(ValueError, match="phiên bản"):
        load_cuboids(path)
