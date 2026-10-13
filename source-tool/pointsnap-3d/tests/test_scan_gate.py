import copy
import json
from pathlib import Path
import pytest

from pointsnap.adapters.cvat.reader import JobData, labels_from_api
from pointsnap.cli.main import EXIT_GATE_FAILED, EXIT_OK, main
from pointsnap.core.config import Config, load_config
from pointsnap.core.model import Cuboid, ErrorType, Finding, Severity
from pointsnap.core.scanner import check_size_in_track, check_size_manual_ranges, scan_cuboids
from pointsnap.report.csv_rep import generate_csv_report
from pointsnap.report.html import generate_html_report


API_LABELS = [
    {"id": 1, "name": "bus", "attributes": [{"id": 10, "name": "pointsnap_error"}, {"id": 11, "name": "reviewed"}]},
    {"id": 2, "name": "car", "attributes": [{"id": 20, "name": "pointsnap_error"}, {"id": 21, "name": "reviewed"}]},
]


def test_csv_report_generation(tmp_path):
    labels = labels_from_api(API_LABELS)
    job = JobData(
        url="http://cvat:8080",
        task_id=5,
        job_id=1,
        start_frame=0,
        stop_frame=10,
        labels=labels,
        cuboids=[],
    )
    f = Finding(
        error_type=ErrorType.SIZE,
        rule="size.class_range",
        severity=Severity.ERROR,
        frame=3,
        label="bus",
        track_id=7,
        source_id=99,
        value=20.5,
        threshold=18.5,
        message="Chiều dài 20.5 m vượt quá 18.5 m",
    )
    out_csv = tmp_path / "report.csv"
    generate_csv_report(job, [f], out_csv)

    assert out_csv.is_file()
    lines = out_csv.read_text(encoding="utf-8-sig").splitlines()
    assert len(lines) == 2
    assert "frame,track_id,source_id" in lines[0]
    assert "3,7,99,bus,error,size,size.class_range" in lines[1]
    assert "http://cvat:8080/tasks/5/jobs/1?frame=3" in lines[1]


def test_html_report_generation(tmp_path):
    labels = labels_from_api(API_LABELS)
    job = JobData(
        url="http://cvat:8080",
        task_id=5,
        job_id=1,
        start_frame=0,
        stop_frame=10,
        labels=labels,
        cuboids=[],
    )
    f = Finding(
        error_type=ErrorType.SIZE,
        rule="size.class_range",
        severity=Severity.ERROR,
        frame=3,
        label="bus",
        track_id=7,
        message="Chiều dài 20.5 m vượt quá 18.5 m",
    )
    out_html = tmp_path / "report.html"
    generate_html_report(job, [f], out_html)

    assert out_html.is_file()
    content = out_html.read_text(encoding="utf-8")
    assert "Job #1" in content
    assert "Task #5" in content
    assert "http://cvat:8080/tasks/5/jobs/1?frame=3" in content
    assert "Track #7" in content
    assert "Chiều dài 20.5 m vượt quá 18.5 m" in content


def test_check_size_manual_ranges():
    config = load_config()
    labels = labels_from_api(API_LABELS)
    # Bus quá dài (25.0 m > 18.5 m)
    bad_bus = Cuboid(center=(0, 0, 0), dims=(25.0, 2.8, 3.2), yaw=0.0, label="bus", frame=0, track_id=1)
    # Bus chuẩn (11.0 m)
    good_bus = Cuboid(center=(0, 0, 0), dims=(11.0, 2.8, 3.2), yaw=0.0, label="bus", frame=1, track_id=1)

    job = JobData(
        url="http://cvat:8080",
        task_id=1,
        job_id=1,
        start_frame=0,
        stop_frame=1,
        labels=labels,
        cuboids=[bad_bus, good_bus],
    )
    findings = check_size_manual_ranges(job, config)
    assert len(findings) == 1
    assert findings[0].rule == "size.class_range"
    assert findings[0].frame == 0
    assert findings[0].severity == Severity.ERROR


def test_check_size_in_track():
    config = load_config()
    labels = labels_from_api(API_LABELS)
    # Car track: 3 frame chuẩn (4.5m), 1 frame bị kéo dãn bất thường (6.5m)
    c0 = Cuboid(center=(0, 0, 0), dims=(4.5, 2.0, 1.6), yaw=0.0, label="car", frame=0, track_id=1)
    c1 = Cuboid(center=(1, 0, 0), dims=(4.5, 2.0, 1.6), yaw=0.0, label="car", frame=1, track_id=1)
    c2 = Cuboid(center=(2, 0, 0), dims=(4.5, 2.0, 1.6), yaw=0.0, label="car", frame=2, track_id=1)
    c3 = Cuboid(center=(3, 0, 0), dims=(6.5, 2.0, 1.6), yaw=0.0, label="car", frame=3, track_id=1)

    job = JobData(
        url="http://cvat:8080",
        task_id=1,
        job_id=1,
        start_frame=0,
        stop_frame=3,
        labels=labels,
        cuboids=[c0, c1, c2, c3],
    )
    findings = check_size_in_track(job, config)
    assert len(findings) == 1
    assert findings[0].rule == "size.in_track"
    assert findings[0].frame == 3
    assert findings[0].severity == Severity.ERROR


class MockCvatServer:
    """Mock cho các API gọi bởi CLI scan và gate."""
    def __init__(self, raw_annos_by_job):
        self.raw_annos_by_job = raw_annos_by_job
        self.patch_calls = []

    def request(self, method, url, **kwargs):
        path = url.split("/api/", 1)[-1] if "/api/" in url else url
        base_path = path.split("?")[0]

        class Resp:
            def __init__(self, status, payload):
                self.status_code = status
                self.content = json.dumps(payload).encode()
                self.text = self.content.decode()

            def json(self):
                return json.loads(self.content)

        if base_path.startswith("jobs/"):
            parts = base_path.split("/")
            job_id = int(parts[1])
            if len(parts) == 2 and method == "GET":
                return Resp(200, {"id": job_id, "task_id": 10, "start_frame": 0, "stop_frame": 3})
            if len(parts) == 3 and parts[2] == "annotations":
                if method == "GET":
                    return Resp(200, self.raw_annos_by_job.get(job_id, {"shapes": [], "tracks": []}))
                if method == "PATCH":
                    self.patch_calls.append((job_id, kwargs.get("json", {})))
                    return Resp(200, {"shapes": [], "tracks": []})

        if base_path == "labels":
            return Resp(200, {"results": API_LABELS, "next": None})

        if base_path == "tasks/10/data/meta":
            return Resp(200, {"frames": [{"name": f"{i:06d}.pcd"} for i in range(4)]})

        return Resp(404, {})


def pts(x, y=0.0, z=0.0, yaw=0.0, l=4.0, w=2.0, h=1.5):
    return [x, y, z, 0.0, 0.0, yaw, l, w, h] + [0.0] * 7


def test_cli_scan_and_gate_commands(tmp_path, monkeypatch):
    # Job 1: có lỗi (bus dài 25m)
    job1_annos = {
        "shapes": [
            {"id": 100, "type": "cuboid", "label_id": 1, "frame": 0, "points": pts(0, l=25.0, w=2.8, h=3.2),
             "attributes": []}
        ],
        "tracks": [],
    }
    # Job 2: sạch (car chuẩn 4.5m)
    job2_annos = {
        "shapes": [
            {"id": 200, "type": "cuboid", "label_id": 2, "frame": 0, "points": pts(0, l=4.5, w=2.0, h=1.5),
             "attributes": []}
        ],
        "tracks": [],
    }

    server = MockCvatServer({1: job1_annos, 2: job2_annos})
    monkeypatch.setattr("requests.Session.request", server.request)
    monkeypatch.setenv("CVAT_TOKEN", "mock_token")

    out_dir = tmp_path / "out"

    # 1. Chạy scan --job 1
    code = main(["scan", "--job", "1", "--out", str(out_dir)])
    assert code == EXIT_OK
    assert (out_dir / "snapshot_job_1.json").is_file()
    assert (out_dir / "report_job_1.html").is_file()
    assert (out_dir / "report_job_1.csv").is_file()

    # 2. Chạy gate --job 1 -> KHÔNG ĐẠT (exit code 1)
    code_gate1 = main(["gate", "--job", "1"])
    assert code_gate1 == EXIT_GATE_FAILED

    # 3. Nhãn không có finding nhưng thiếu LiDAR -> KHÔNG ĐẠT
    code_gate2 = main(["gate", "--job", "2"])
    assert code_gate2 == EXIT_GATE_FAILED

    # 4. Chạy scan --job 1 --flag -> gắn cờ lỗi qua PATCH
    code_flag = main(["scan", "--job", "1", "--flag", "--out", str(out_dir)])
    assert code_flag == EXIT_OK
    assert len(server.patch_calls) > 0
    assert server.patch_calls[0][0] == 1
    patched_json = server.patch_calls[0][1]
    assert "shapes" in patched_json
    assert patched_json["shapes"][0]["attributes"][0]["spec_id"] == 10
    assert "lớn bất thường so với class bus" in patched_json["shapes"][0]["attributes"][0]["value"]
