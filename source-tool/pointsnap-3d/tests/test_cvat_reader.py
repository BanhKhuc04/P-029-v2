import numpy as np
import pytest

import fake_nuscenes
from pointsnap.adapters.cvat.reader import (
    ManifestFrames,
    annotations_to_cuboids,
    frame_url,
    labels_from_api,
)
from pointsnap.adapters.nuscenes import NuScenesReader
from pointsnap.core.geometry import rotate_points_z90
from pointsnap.datasets.nuscenes.to_cvat import export_scene


# Dạng dữ liệu giống hệt CVAT 2.77.1 trả về (đã đối chiếu với task thử trên CVAT local).
API_LABELS = [
    {"id": 11, "name": "car", "attributes": [{"id": 101, "name": "pointsnap_error"}, {"id": 102, "name": "reviewed"}]},
    {"id": 12, "name": "pedestrian", "attributes": [{"id": 103, "name": "pointsnap_error"}, {"id": 104, "name": "reviewed"}]},
]


def pts(x, y=0.0, z=0.0, yaw=0.0, l=4.0, w=2.0, h=1.5, rx=0.0, ry=0.0):
    return [x, y, z, rx, ry, yaw, l, w, h] + [0.0] * 7


API_ANNOTATIONS = {
    "version": 0,
    "tags": [],
    "shapes": [
        {"id": 5, "type": "cuboid", "label_id": 12, "frame": 1, "points": pts(9.0), "occluded": True,
         "outside": False, "attributes": [{"spec_id": 103, "value": "LỖI: lơ lửng 22 cm"}]},
        {"id": 6, "type": "rectangle", "label_id": 12, "frame": 0, "points": [0, 0, 1, 1], "attributes": []},
    ],
    "tracks": [
        {"id": 31, "label_id": 11, "frame": 0, "group": 0, "source": "manual", "elements": [],
         "attributes": [{"spec_id": 102, "value": "false"}],
         "shapes": [
             {"id": 64, "type": "cuboid", "frame": 0, "points": pts(1.0, yaw=0.5, rx=0.01), "outside": False,
              "occluded": False, "attributes": []},
             {"id": 65, "type": "cuboid", "frame": 2, "points": pts(3.0, yaw=0.5), "outside": False,
              "occluded": False, "attributes": [{"spec_id": 101, "value": "CẢNH BÁO: kích thước"}]},
             {"id": 66, "type": "cuboid", "frame": 3, "points": pts(3.0, yaw=0.5), "outside": True,
              "occluded": False, "attributes": []},
         ]},
    ],
}


def test_labels_from_api():
    labels = labels_from_api(API_LABELS)
    assert labels[11].name == "car"
    assert labels[11].attribute_names == {101: "pointsnap_error", 102: "reviewed"}
    assert labels[12].attribute_ids == {"pointsnap_error": 103, "reviewed": 104}


def test_annotations_to_cuboids_reads_tracks_shapes_and_outside():
    boxes = annotations_to_cuboids(API_ANNOTATIONS, labels_from_api(API_LABELS))
    assert [(b.frame, b.label, b.track_id, b.source_id, b.outside) for b in boxes] == [
        (0, "car", 31, 64, False),
        (1, "pedestrian", None, 5, False),
        (2, "car", 31, 65, False),
        (3, "car", 31, 66, True),
    ]
    first = boxes[0]
    assert first.center == (1.0, 0.0, 0.0) and first.dims == (4.0, 2.0, 1.5) and first.yaw == pytest.approx(0.5)
    assert first.attrs["cvat_rx"] == pytest.approx(0.01)
    assert first.attrs["reviewed"] == "false"  # thuộc tính của track
    assert boxes[2].attrs["pointsnap_error"] == "CẢNH BÁO: kích thước"  # thuộc tính của keyframe
    assert boxes[1].attrs["occluded"] is True and boxes[1].attrs["pointsnap_error"].startswith("LỖI")


def test_invalid_box_reports_its_id_and_frame():
    bad = {"shapes": [{"id": 9, "type": "cuboid", "label_id": 11, "frame": 4, "points": pts(0, l=0.0), "attributes": []}]}
    with pytest.raises(ValueError, match="Box id 9 ở frame 4"):
        annotations_to_cuboids(bad, labels_from_api(API_LABELS))


def test_frame_url():
    # 1. Không có track_id và shape_id: link chỉ có frame
    assert frame_url("http://localhost:8080/", 7, 39, 12) == "http://localhost:8080/tasks/7/jobs/39?frame=12"
    # 2. Có track_id: thêm &type=track&serverID=<track_id>
    assert (
        frame_url("http://localhost:8080/", 7, 39, 12, track_id=45)
        == "http://localhost:8080/tasks/7/jobs/39?frame=12&type=track&serverID=45"
    )
    # 3. Không có track_id nhưng có shape_id: thêm &type=shape&serverID=<shape_id>
    assert (
        frame_url("http://localhost:8080/", 7, 39, 12, shape_id=88)
        == "http://localhost:8080/tasks/7/jobs/39?frame=12&type=shape&serverID=88"
    )
    # 4. Có cả hai (ưu tiên track_id)
    assert (
        frame_url("http://localhost:8080/", 7, 39, 12, track_id=45, shape_id=88)
        == "http://localhost:8080/tasks/7/jobs/39?frame=12&type=track&serverID=45"
    )


def test_manifest_frames_map_cvat_frames_to_nuscenes_points(tmp_path):
    reader = NuScenesReader(fake_nuscenes.build(tmp_path / "nuscenes"))
    export = export_scene(reader, "scene-0001", tmp_path / "out")
    frames = ManifestFrames(export.manifest)

    frames.check_matches(["000000.pcd", "000001.pcd", "000002.pcd"])
    frames.check_matches(["data/000000.pcd", "data/000001.pcd", "data/000002.pcd"])  # chỉ so tên file
    with pytest.raises(ValueError, match="không khớp"):
        frames.check_matches(["000001.pcd", "000000.pcd", "000002.pcd"])

    frame0 = frames.frame_data(0)
    np.testing.assert_array_equal(frame0.points, rotate_points_z90(fake_nuscenes.FRAME0_POINTS))
    assert (frame0.frame, frame0.source_ref) == (0, "smp0")
    assert frames.frame_data(2, with_points=False).sensor_to_world[0, 3] == pytest.approx(10.0)

