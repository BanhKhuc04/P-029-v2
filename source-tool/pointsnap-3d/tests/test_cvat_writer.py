import copy
import json
import pytest

from pointsnap.adapters.cvat.client import CvatClient
from pointsnap.adapters.cvat.reader import (
    JobData,
    annotations_to_cuboids,
    labels_from_api,
)
from pointsnap.adapters.cvat.writer import (
    build_error_patch,
    build_findings_map,
    clear_job_errors,
    flag_job_errors,
    format_finding_message,
    save_snapshot,
    verify_geometry_preserved,
)
from pointsnap.core.model import Cuboid, ErrorType, Finding, Severity
from pointsnap.core.serialize import load_cuboids


API_LABELS = [
    {"id": 11, "name": "car", "attributes": [{"id": 101, "name": "pointsnap_error"}, {"id": 102, "name": "reviewed"}]},
    {"id": 12, "name": "pedestrian", "attributes": [{"id": 103, "name": "pointsnap_error"}, {"id": 104, "name": "reviewed"}]},
]


def pts(x, y=0.0, z=0.0, yaw=0.0, l=4.0, w=2.0, h=1.5, rx=0.0, ry=0.0):
    return [x, y, z, rx, ry, yaw, l, w, h] + [0.0] * 7


RAW_ANNOTATIONS = {
    "version": 0,
    "tags": [],
    "shapes": [
        {"id": 5, "type": "cuboid", "label_id": 12, "frame": 1, "points": pts(9.0), "occluded": True,
         "outside": False, "attributes": []},
    ],
    "tracks": [
        {"id": 31, "label_id": 11, "frame": 0, "group": 0, "source": "manual", "elements": [],
         "attributes": [{"spec_id": 102, "value": "false"}],
         "shapes": [
             {"id": 64, "type": "cuboid", "frame": 0, "points": pts(1.0, yaw=0.5, rx=0.01), "outside": False,
              "occluded": False, "attributes": []},
             {"id": 65, "type": "cuboid", "frame": 2, "points": pts(3.0, yaw=0.5), "outside": False,
              "occluded": False, "attributes": []},
             {"id": 66, "type": "cuboid", "frame": 3, "points": pts(3.0, yaw=0.5), "outside": True,
              "occluded": False, "attributes": []},
         ]},
    ],
}


class MockSession:
    def __init__(self, raw_annos):
        self.raw_annos = copy.deepcopy(raw_annos)
        self.headers = {}
        self.calls = []

    def request(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        path = url.split("/api/", 1)[-1] if "/api/" in url else url
        base_path = path.split("?")[0]

        class Resp:
            def __init__(self, status, payload):
                self.status_code = status
                self.content = json.dumps(payload).encode()
                self.text = self.content.decode()

            def json(self):
                return json.loads(self.content)

        if method == "GET" and base_path == "jobs/1/annotations":
            return Resp(200, self.raw_annos)

        if method == "PATCH" and base_path == "jobs/1/annotations":
            # Áp dụng patch cập nhật
            patch_data = kwargs.get("json", {})
            if "shapes" in patch_data:
                for patched_shape in patch_data["shapes"]:
                    for i, s in enumerate(self.raw_annos.get("shapes", [])):
                        if s["id"] == patched_shape["id"]:
                            self.raw_annos["shapes"][i] = copy.deepcopy(patched_shape)
            if "tracks" in patch_data:
                for patched_track in patch_data["tracks"]:
                    for i, t in enumerate(self.raw_annos.get("tracks", [])):
                        if t["id"] == patched_track["id"]:
                            self.raw_annos["tracks"][i] = copy.deepcopy(patched_track)
            return Resp(200, self.raw_annos)

        return Resp(404, {"detail": "Not found"})


def test_format_finding_message():
    f = Finding(
        error_type=ErrorType.FLOATING,
        rule="floating",
        severity=Severity.ERROR,
        frame=0,
        label="car",
        message="Đáy box cách mặt đất 22 cm",
    )
    assert format_finding_message(f) == "[Lỗi] Đáy box cách mặt đất 22 cm"


def test_save_snapshot(tmp_path):
    labels = labels_from_api(API_LABELS)
    cuboids = annotations_to_cuboids(RAW_ANNOTATIONS, labels)
    job = JobData(
        url="http://cvat:8080",
        task_id=10,
        job_id=1,
        start_frame=0,
        stop_frame=3,
        labels=labels,
        cuboids=cuboids,
    )
    snap_path = tmp_path / "snap.json"
    save_snapshot(job, snap_path)

    loaded, meta = load_cuboids(snap_path)
    assert len(loaded) == len(cuboids)
    assert meta["job_id"] == 1
    assert meta["task_id"] == 10


def test_build_findings_map_combines_messages():
    f1 = Finding(
        error_type=ErrorType.FLOATING,
        rule="floating",
        severity=Severity.ERROR,
        frame=2,
        label="car",
        track_id=31,
        source_id=65,
        message="Lơ lửng 25 cm",
    )
    f2 = Finding(
        error_type=ErrorType.SIZE,
        rule="size.class_range",
        severity=Severity.WARNING,
        frame=2,
        label="car",
        track_id=31,
        source_id=65,
        message="Chiều dài quá lớn",
    )
    fmap = build_findings_map([f1, f2])
    assert fmap[(31, 65, 2)] == "[Lỗi] Lơ lửng 25 cm; [Cảnh báo] Chiều dài quá lớn"


def test_flag_and_clear_job_errors_preserves_geometry(tmp_path):
    labels = labels_from_api(API_LABELS)
    cuboids_before = annotations_to_cuboids(RAW_ANNOTATIONS, labels)
    session = MockSession(RAW_ANNOTATIONS)
    client = CvatClient("http://cvat:8080", "secret", session=session)

    job = JobData(
        url="http://cvat:8080",
        task_id=10,
        job_id=1,
        start_frame=0,
        stop_frame=3,
        labels=labels,
        cuboids=cuboids_before,
    )

    # 1. Ghi cờ lỗi lên shape 5 (pedestrian) và track 31 shape 65 (car frame 2)
    f1 = Finding(
        error_type=ErrorType.FLOATING,
        rule="floating",
        severity=Severity.ERROR,
        frame=1,
        label="pedestrian",
        source_id=5,
        message="Lơ lửng 22 cm",
    )
    f2 = Finding(
        error_type=ErrorType.SIZE,
        rule="size.in_track",
        severity=Severity.WARNING,
        frame=2,
        label="car",
        track_id=31,
        source_id=65,
        message="Lệch kích thước track",
    )

    snap_file = tmp_path / "before_flag.json"
    flagged = flag_job_errors(client, job, [f1, f2], snapshot_path=snap_file)
    assert flagged == 2
    assert snap_file.is_file()

    # Đọc lại annotations sau khi ghi cờ
    cuboids_after_flag = annotations_to_cuboids(session.raw_annos, labels)

    # Kiểm tra hình học hoàn toàn không bị thay đổi
    verify_geometry_preserved(cuboids_before, cuboids_after_flag)

    # Kiểm tra cờ lỗi xuất hiện đúng chỗ
    by_key = {(c.frame, c.track_id): c for c in cuboids_after_flag}
    ped = by_key[(1, None)]
    assert ped.attrs.get("pointsnap_error") == "[Lỗi] Lơ lửng 22 cm"

    car_f2 = by_key[(2, 31)]
    assert car_f2.attrs.get("pointsnap_error") == "[Cảnh báo] Lệch kích thước track"

    car_f0 = by_key[(0, 31)]
    assert "pointsnap_error" not in car_f0.attrs or not car_f0.attrs["pointsnap_error"]

    # 2. Xóa cờ lỗi của track 31
    job_updated = JobData(
        url=job.url,
        task_id=job.task_id,
        job_id=job.job_id,
        start_frame=job.start_frame,
        stop_frame=job.stop_frame,
        labels=labels,
        cuboids=cuboids_after_flag,
    )
    cleared = clear_job_errors(client, job_updated, track_id=31)
    assert cleared == 1

    cuboids_after_clear_track = annotations_to_cuboids(session.raw_annos, labels)
    verify_geometry_preserved(cuboids_before, cuboids_after_clear_track)

    by_key2 = {(c.frame, c.track_id): c for c in cuboids_after_clear_track}
    assert "pointsnap_error" not in by_key2[(2, 31)].attrs or not by_key2[(2, 31)].attrs["pointsnap_error"]
    assert by_key2[(1, None)].attrs.get("pointsnap_error") == "[Lỗi] Lơ lửng 22 cm"

    # 3. Xóa cờ lỗi toàn bộ job
    clear_job_errors(client, job_updated)
    cuboids_final = annotations_to_cuboids(session.raw_annos, labels)
    verify_geometry_preserved(cuboids_before, cuboids_final)

    for c in cuboids_final:
        assert "pointsnap_error" not in c.attrs or not c.attrs["pointsnap_error"]


def test_verify_geometry_detects_shifts():
    c1 = Cuboid(center=(1.0, 2.0, 3.0), dims=(4.0, 2.0, 1.5), yaw=0.0, label="car", frame=0)
    c2 = c1.replace(center=(1.001, 2.0, 3.0))
    with pytest.raises(ValueError, match="Tâm box .* bị lệch"):
        verify_geometry_preserved([c1], [c2], tolerance=1e-4)

    c3 = c1.replace(dims=(4.0, 2.01, 1.5))
    with pytest.raises(ValueError, match="Kích thước box .* bị thay đổi"):
        verify_geometry_preserved([c1], [c3], tolerance=1e-4)

    c4 = c1.replace(yaw=0.02)
    with pytest.raises(ValueError, match="Yaw của box .* bị thay đổi"):
        verify_geometry_preserved([c1], [c4], tolerance=1e-4)
