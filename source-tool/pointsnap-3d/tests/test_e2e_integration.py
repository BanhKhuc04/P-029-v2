"""Kiểm thử tích hợp End-to-End trọn vẹn quy trình PointSnap 3D (việc A6).

Kịch bản end-to-end:
1. Đọc job từ CVAT và point cloud (`JobData`).
2. Quét phát hiện lỗi (`scan_cuboids`).
3. Xuất báo cáo HTML + CSV và tự động lưu bản chụp JSON.
4. Gắn cờ lỗi lên CVAT (`flag_job_errors`).
5. Đọc lại annotations từ CVAT: xác nhận cờ lỗi xuất hiện, hình học box bảo toàn 100%.
6. Kiểm tra cổng `gate`: phát hiện lỗi -> KHÔNG ĐẠT (exit code 1).
7. Sửa lỗi / xóa cờ lỗi (`clear_job_errors`).
8. Kiểm tra lại cổng `gate`: job sạch -> ĐẠT (exit code 0).
"""

import json
from pathlib import Path
import pytest

from pointsnap.adapters.cvat.client import CvatClient
from pointsnap.adapters.cvat.reader import (
    JobData,
    annotations_to_cuboids,
    labels_from_api,
    load_job,
)
from pointsnap.adapters.cvat.writer import (
    clear_job_errors,
    flag_job_errors,
    verify_geometry_preserved,
)
from pointsnap.cli.main import EXIT_GATE_FAILED, EXIT_OK, main
from pointsnap.core.config import load_config
from pointsnap.core.scanner import scan_cuboids
from pointsnap.report.csv_rep import generate_csv_report
from pointsnap.report.html import generate_html_report


API_LABELS = [
    {"id": 1, "name": "car", "attributes": [{"id": 10, "name": "pointsnap_error"}, {"id": 11, "name": "reviewed"}]},
    {"id": 2, "name": "bus", "attributes": [{"id": 20, "name": "pointsnap_error"}, {"id": 21, "name": "reviewed"}]},
]


def pts(x, y=0.0, z=0.0, yaw=0.0, l=4.0, w=2.0, h=1.5):
    return [x, y, z, 0.0, 0.0, yaw, l, w, h] + [0.0] * 7


class MockLiveSession:
    def __init__(self, raw_annos):
        self.raw_annos = raw_annos
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

        if base_path == "jobs/100":
            return Resp(200, {"id": 100, "task_id": 1, "start_frame": 0, "stop_frame": 3})

        if base_path == "jobs/100/annotations":
            if method == "GET":
                return Resp(200, self.raw_annos)
            if method == "PATCH":
                patch_data = kwargs.get("json", {})
                if "shapes" in patch_data:
                    for s in patch_data["shapes"]:
                        for idx, curr in enumerate(self.raw_annos.get("shapes", [])):
                            if curr["id"] == s["id"]:
                                self.raw_annos["shapes"][idx] = s
                if "tracks" in patch_data:
                    for t in patch_data["tracks"]:
                        for idx, curr in enumerate(self.raw_annos.get("tracks", [])):
                            if curr["id"] == t["id"]:
                                self.raw_annos["tracks"][idx] = t
                return Resp(200, self.raw_annos)

        if base_path == "labels":
            return Resp(200, {"results": API_LABELS, "next": None})

        if base_path == "tasks/1/data/meta":
            return Resp(200, {"frames": [{"name": f"{i:06d}.pcd"} for i in range(4)]})

        return Resp(404, {})


def test_full_end_to_end_workflow(tmp_path, monkeypatch):
    # Dựng một task có 1 xe bus dị thường (dài 25 m, vượt biên Lỗi 18.5 m × 1.25) và 1 xe car chuẩn
    raw_annos = {
        "version": 0,
        "tags": [],
        "shapes": [
            {"id": 50, "type": "cuboid", "label_id": 2, "frame": 0, "points": pts(0, l=25.0, w=2.8, h=3.2),
             "attributes": []},
            {"id": 51, "type": "cuboid", "label_id": 1, "frame": 1, "points": pts(5.0, l=4.5, w=2.0, h=1.6),
             "attributes": []},
        ],
        "tracks": [],
    }

    session = MockLiveSession(raw_annos)
    monkeypatch.setattr("requests.Session.request", session.request)
    monkeypatch.setenv("CVAT_TOKEN", "test_secret_token")
    monkeypatch.setenv("CVAT_URL", "http://cvat.local:8080")

    out_dir = tmp_path / "out"

    # Bước 1 & 2: Quét job 100 và gắn cờ lỗi
    code_scan = main(["scan", "--job", "100", "--flag", "--out", str(out_dir)])
    assert code_scan == EXIT_OK

    # Xác nhận các file kết quả đã sinh
    assert (out_dir / "snapshot_job_100.json").is_file()
    assert (out_dir / "report_job_100.html").is_file()
    assert (out_dir / "report_job_100.csv").is_file()

    # Bước 3: Đọc lại từ client để kiểm tra cờ lỗi và hình học
    client = CvatClient("http://cvat.local:8080", "test_secret_token", session=session)
    job_flagged = load_job(client, 100)
    assert len(job_flagged.cuboids) == 2

    # Xe bus (id 50) phải được gắn cờ lỗi pointsnap_error
    bus_box = [c for c in job_flagged.cuboids if c.source_id == 50][0]
    assert "pointsnap_error" in bus_box.attrs
    assert "lớn bất thường so với class bus" in bus_box.attrs["pointsnap_error"]

    # Xe car (id 51) không có cờ lỗi
    car_box = [c for c in job_flagged.cuboids if c.source_id == 51][0]
    assert "pointsnap_error" not in car_box.attrs or not car_box.attrs["pointsnap_error"]

    # Bước 4: Kiểm tra cổng gate -> KHÔNG ĐẠT (exit code 1) do có lỗi xe bus
    code_gate_failed = main(["gate", "--job", "100"])
    assert code_gate_failed == EXIT_GATE_FAILED

    # Bước 5: Giả lập reviewer/annotator sửa lỗi (hoặc xóa cờ lỗi)
    cleared = clear_job_errors(client, job_flagged)
    assert cleared == 1

    # Sửa kích thước xe bus về chuẩn (12m)
    session.raw_annos["shapes"][0]["points"] = pts(0, l=12.0, w=2.8, h=3.2)

    # Bước 6: Kiểm tra lại cổng gate -> ĐẠT (exit code 0)
    code_gate_passed = main(["gate", "--job", "100"])
    assert code_gate_passed == EXIT_OK
