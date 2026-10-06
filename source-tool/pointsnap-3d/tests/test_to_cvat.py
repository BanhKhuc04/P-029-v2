import json
import zipfile

import pytest

import fake_nuscenes
from pointsnap.adapters.nuscenes import NuScenesReader
from pointsnap.core.geometry import LIDAR_TO_EGO_ROT, rotate_points_z90
from pointsnap.core.model import Cuboid
from pointsnap.core.serialize import load_cuboids
from pointsnap.datasets.nuscenes.to_cvat import (
    TASK_CLASSES,
    build_annotations,
    build_tracks,
    export_scene,
    label_specs,
    upload_scene,
)
from pointsnap.datasets.pcd import read_pcd


LABEL_IDS = {name: index + 100 for index, name in enumerate(TASK_CLASSES)}


def box(frame, track_id=1, label="car"):
    return Cuboid(center=(frame, 0.0, 0.0), dims=(4, 2, 1.5), yaw=0.0, label=label, frame=frame, track_id=track_id)


def frames_and_outside(track):
    return [(s["frame"], s["outside"]) for s in track["shapes"]]


def test_label_specs_have_flag_and_reviewed_attributes():
    specs = label_specs("pointsnap_error")
    assert [s["name"] for s in specs] == list(TASK_CLASSES)
    attrs = {a["name"]: a for a in specs[0]["attributes"]}
    assert attrs["pointsnap_error"]["input_type"] == "text" and attrs["pointsnap_error"]["mutable"]
    assert attrs["reviewed"]["input_type"] == "checkbox" and attrs["reviewed"]["default_value"] == "false"


def test_track_ends_with_outside_before_scene_end():
    [track] = build_tracks([box(0), box(1), box(2)], num_frames=10, label_ids=LABEL_IDS)
    assert frames_and_outside(track) == [(0, False), (1, False), (2, False), (3, True)]
    assert (track["frame"], track["label_id"]) == (0, LABEL_IDS["car"])


def test_track_reaching_last_frame_has_no_outside():
    [track] = build_tracks([box(8), box(9)], num_frames=10, label_ids=LABEL_IDS)
    assert frames_and_outside(track) == [(8, False), (9, False)]


def test_gap_in_track_is_closed_with_outside():
    # Đối tượng vắng ở frame 3–4: phải có outside ở frame 3 để CVAT không nội suy qua đoạn đó
    [track] = build_tracks([box(1), box(2), box(5), box(6)], num_frames=7, label_ids=LABEL_IDS)
    assert frames_and_outside(track) == [(1, False), (2, False), (3, True), (5, False), (6, False)]
    assert track["shapes"][2]["points"] == track["shapes"][1]["points"]  # outside giữ hình học của frame trước


def test_track_with_two_classes_is_rejected():
    with pytest.raises(ValueError, match="nhiều class"):
        build_tracks([box(0), box(1, label="truck")], num_frames=5, label_ids=LABEL_IDS)


def test_build_annotations_splits_tracks_and_single_shapes():
    data = build_annotations([box(0), box(0, track_id=None, label="barrier")], num_frames=1, label_ids=LABEL_IDS)
    assert data["version"] == 0 and data["tags"] == []
    assert len(data["tracks"]) == 1
    [shape] = data["shapes"]
    assert shape["label_id"] == LABEL_IDS["barrier"] and shape["type"] == "cuboid" and "outside" not in shape


def test_export_scene_writes_pcd_manifest_ground_truth_and_zip(tmp_path):
    reader = NuScenesReader(fake_nuscenes.build(tmp_path / "nuscenes"))
    export = export_scene(reader, "scene-0001", tmp_path / "out")

    assert (export.num_frames, export.num_boxes) == (3, 4)
    pcd0 = export.directory / "pointcloud" / "000000.pcd"
    expected_pts0 = rotate_points_z90(fake_nuscenes.FRAME0_POINTS)[:, :4]
    assert read_pcd(pcd0).tolist() == expected_pts0.tolist()

    manifest = json.loads(export.manifest.read_text(encoding="utf-8"))
    assert manifest["coordinate_system"] == "ego"
    assert manifest["transform"] == LIDAR_TO_EGO_ROT.tolist()
    assert [f["file"] for f in manifest["frames"]] == ["000000.pcd", "000001.pcd", "000002.pcd"]
    assert [f["sample_token"] for f in manifest["frames"]] == ["smp0", "smp1", "smp2"]

    assert manifest["frames"][2]["sensor_to_world"][0][3] == pytest.approx(10.0)

    cuboids, meta = load_cuboids(export.ground_truth)
    assert meta["num_frames"] == 3 and len(cuboids) == 4

    with zipfile.ZipFile(export.archive) as zf:
        assert sorted(zf.namelist()) == ["000000.pcd", "000001.pcd", "000002.pcd"]


class FakeClient:
    url = "http://cvat.local:8080"

    def __init__(self):
        self.calls = []

    def create_task(self, name, labels):
        self.calls.append(("create_task", name, len(labels)))
        return {"id": 7}

    def upload_task_data(self, task_id, archive):
        self.calls.append(("upload", task_id, archive.name))
        return "rq-7"

    def wait_request(self, rq_id, timeout):
        self.calls.append(("wait", rq_id))

    def task_labels(self, task_id):
        return [{"name": name, "id": i} for name, i in LABEL_IDS.items()]

    def put_task_annotations(self, task_id, data):
        self.calls.append(("put", task_id, data))

    def task_jobs(self, task_id):
        return [{"id": 70}]


def test_upload_scene_creates_task_and_loads_ground_truth(tmp_path):
    reader = NuScenesReader(fake_nuscenes.build(tmp_path / "nuscenes"))
    export = export_scene(reader, "scene-0001", tmp_path / "out")
    fake = FakeClient()

    info = upload_scene(fake, export, "PointSnap scene-0001", "pointsnap_error")

    assert [c[0] for c in fake.calls] == ["create_task", "upload", "wait", "put"]
    assert fake.calls[0] == ("create_task", "PointSnap scene-0001", 10)
    data = fake.calls[3][2]
    tracks = {t["label_id"]: t for t in data["tracks"]}
    car = tracks[LABEL_IDS["car"]]
    assert [s["frame"] for s in car["shapes"]] == [0, 1, 2]  # có mặt tới frame cuối, không cần outside
    ped = tracks[LABEL_IDS["pedestrian"]]
    assert frames_and_outside(ped) == [(0, False), (1, True)]  # frame 1 bị bỏ vì 0 điểm LiDAR
    assert info == {"url": "http://cvat.local:8080", "task_id": 7, "job_ids": [70], "scene": "scene-0001",
                    "num_frames": 3, "num_boxes": 4}
    assert json.loads((export.directory / "cvat_task.json").read_text())["task_id"] == 7
