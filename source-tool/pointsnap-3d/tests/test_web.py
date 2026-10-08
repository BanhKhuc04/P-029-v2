"""Kiểm thử toàn diện cho hệ thống Web UI và quản lý dự án (A11)."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
import yaml
from fastapi.testclient import TestClient

from pointsnap.adapters.cvat.reader import JobData, labels_from_api
from pointsnap.cli.common import export_dirs, frames_for_job
from pointsnap.core.config import Config, ConfigError, GateConfig
from pointsnap.core.gate import gate_verdict
from pointsnap.core.model import Cuboid, ErrorType, Finding, Severity
from pointsnap.core.scanner import scan_cuboids
from pointsnap.web.app import create_app
from pointsnap.web.projects import ProjectError, ProjectManager, validate_slug


@pytest.fixture
def mock_home(tmp_path: Path) -> Path:
    home = tmp_path / "pointsnap_home"
    home.mkdir()
    return home


@pytest.fixture
def client(mock_home: Path) -> TestClient:
    app = create_app(home_dir=mock_home)
    return TestClient(app)


# --- Test 1: Khóa token trong guideline và không lộ token (Điểm 1 Mục 6) ---

def test_token_never_in_guideline_and_not_leaked(mock_home: Path, client: TestClient):
    pm = ProjectManager(mock_home)
    token_secret = "secret_pat_token_12345"
    proj = pm.create_project(
        name="Test Secret Project",
        slug="test-secret",
        cvat_token=token_secret,
    )

    # 1. API không bao giờ trả token ra
    assert "token" not in proj
    assert "cvat_token" not in proj
    assert proj["has_token"] is True

    api_res = client.get("/api/projects/test-secret")
    assert api_res.status_code == 200
    data = api_res.json()
    assert data["has_token"] is True
    assert "token" not in data
    assert "cvat_token" not in data

    # 2. guideline.yaml không bao giờ chứa khóa token khi sinh từ mặc định
    guideline_path = mock_home / "projects" / "test-secret" / "guideline.yaml"
    assert guideline_path.is_file()
    guideline_content = yaml.safe_load(guideline_path.read_text(encoding="utf-8"))
    assert "token" not in guideline_content.get("cvat", {})

    # 3. Khi lưu guideline qua API dưới dạng dict config kèm token, token bị loại bỏ
    save_res = client.put(
        "/api/projects/test-secret/guideline",
        json={"config": {"cvat": {"url": "http://localhost:8080", "token": "leaked_token"}}},
    )
    assert save_res.status_code == 200
    saved_yaml = yaml.safe_load(guideline_path.read_text(encoding="utf-8"))
    assert "token" not in saved_yaml.get("cvat", {})

    # 4. Khi lưu guideline qua API dưới dạng chuỗi YAML kèm token, token cũng bị loại bỏ
    yaml_with_token = (
        "cvat:\n"
        "  url: http://localhost:8080\n"
        "  flag_attribute: pointsnap_error\n"
        "  token: secret_leak_in_yaml\n"
    )
    save_yaml_res = client.put(
        "/api/projects/test-secret/guideline",
        json={"yaml": yaml_with_token},
    )
    assert save_yaml_res.status_code == 200
    saved_yaml2 = yaml.safe_load(guideline_path.read_text(encoding="utf-8"))
    assert "token" not in saved_yaml2.get("cvat", {})

    # 5. Tạo dự án mới từ preset cũng không bao giờ kế thừa token vào guideline
    preset_proj = pm.create_project(
        name="Preset Project",
        slug="preset-child",
        preset_slug="test-secret",
        cvat_token="child_token_999",
    )
    child_guideline = mock_home / "projects" / "preset-child" / "guideline.yaml"
    child_yaml = yaml.safe_load(child_guideline.read_text(encoding="utf-8"))
    assert "token" not in child_yaml.get("cvat", {})

    # 6. parse_config từ chối nếu có token, nhưng clean_guideline_dict giải quyết được
    from pointsnap.core.config import load_config, parse_config
    from pointsnap.web.projects import clean_guideline_dict
    raw_dict_with_token = load_config().to_dict(redact=False)
    # to_dict mặc định luôn có key cvat.token
    assert "token" in raw_dict_with_token["cvat"]
    with pytest.raises(ConfigError, match="Không ghi token CVAT trong file cấu hình"):
        parse_config(raw_dict_with_token)
    # Sau khi qua clean_guideline_dict, parse_config thành công
    cleaned = clean_guideline_dict(raw_dict_with_token)
    assert "token" not in cleaned["cvat"]
    assert parse_config(cleaned) is not None


def test_token_clearing_and_manual_guideline_clean(mock_home: Path, client: TestClient):
    pm = ProjectManager(mock_home)
    pm.create_project(
        name="Project With Token",
        slug="proj-token",
        cvat_token="initial_secret_token",
    )
    assert pm.get_project("proj-token")["has_token"] is True
    assert pm.get_token("proj-token") == "initial_secret_token"

    # 1. Cập nhật token rỗng -> xóa khỏi secret.json, has_token = False
    client.put("/api/projects/proj-token", json={"cvat_token": ""})
    assert pm.get_project("proj-token")["has_token"] is False
    assert pm.get_token("proj-token") is None

    # 2. Người dùng tự tay ghi token vào guideline.yaml trên đĩa
    g_file = mock_home / "projects" / "proj-token" / "guideline.yaml"
    g_file.write_text(
        "cvat:\n  url: http://localhost:8080\n  token: manual_leak_on_disk\n"
        "floating:\n  classes: [car]\n  warning_m: 0.12\n  error_m: 0.22\n",
        encoding="utf-8",
    )

    # get_guideline và get_effective_config vẫn làm sạch an toàn
    clean_dict, _ = pm.get_guideline("proj-token")
    assert "token" not in clean_dict.get("cvat", {})
    eff_cfg = pm.get_effective_config("proj-token")
    assert eff_cfg.cvat.token is None

    # 3. reset_guideline trả về guideline không token
    reset_res = client.post("/api/projects/proj-token/guideline/reset")
    assert reset_res.status_code == 200
    assert "token" not in reset_res.json()["config"].get("cvat", {})
    reset_yaml = yaml.safe_load(g_file.read_text(encoding="utf-8"))
    assert "token" not in reset_yaml.get("cvat", {})


# --- Test 2: URL CVAT của dự án ưu tiên hơn guideline (Điểm 2 Mục 6) ---

def test_project_cvat_url_precedence(mock_home: Path, client: TestClient):
    pm = ProjectManager(mock_home)
    custom_url = "http://cvat-production.internal:9000"
    pm.create_project(
        name="Custom URL Project",
        slug="custom-url",
        cvat_url=custom_url,
    )

    # 1. Cấu hình guideline mặc định có URL http://localhost:8080
    guideline_data, _ = pm.get_guideline("custom-url")
    assert guideline_data["cvat"]["url"] == "http://localhost:8080"

    # get_effective_config phải trả về URL của project.json (custom_url)
    effective_cfg = pm.get_effective_config("custom-url")
    assert effective_cfg.cvat.url == custom_url

    # 2. Cập nhật URL qua API PUT /api/projects/{slug}
    update_res = client.put(
        "/api/projects/custom-url",
        json={"cvat_url": "http://new-cvat-url:8000"},
    )
    assert update_res.status_code == 200
    effective_cfg_updated = pm.get_effective_config("custom-url")
    assert effective_cfg_updated.cvat.url == "http://new-cvat-url:8000"

    # 3. Kể cả khi sửa guideline YAML có chứa một cvat.url khác, get_effective_config vẫn ưu tiên project.json
    yaml_override_attempt = (
        "cvat:\n"
        "  url: http://should-be-ignored-by-project:7777\n"
        "  flag_attribute: pointsnap_error\n"
    )
    put_guide_res = client.put(
        "/api/projects/custom-url/guideline",
        json={"yaml": yaml_override_attempt},
    )
    assert put_guide_res.status_code == 200
    # get_effective_config vẫn giữ URL từ project.json
    effective_cfg_after_yaml = pm.get_effective_config("custom-url")
    assert effective_cfg_after_yaml.cvat.url == "http://new-cvat-url:8000"


def test_project_cvat_url_overrides_env_var(mock_home: Path, client: TestClient, monkeypatch):
    pm = ProjectManager(mock_home)
    project_url = "http://my-project-cvat:9999"
    pm.create_project(
        name="Env Override Project",
        slug="env-override-proj",
        cvat_url=project_url,
    )

    # Đặt biến môi trường CVAT_URL
    monkeypatch.setenv("CVAT_URL", "http://ignored-env-host:5555")

    # get_effective_config của dự án luôn lấy URL dự án, không bị CVAT_URL đè
    eff = pm.get_effective_config("env-override-proj")
    assert eff.cvat.url == project_url

    # Endpoint check_cvat sử dụng URL của dự án
    check_res = client.get("/api/projects/env-override-proj/cvat/check")
    assert check_res.status_code == 200
    assert check_res.json()["url"] == project_url


# --- Test 3: Đường dẫn dữ liệu độc lập theo dự án, không qua os.environ (Điểm 3 Mục 6) ---

def test_thread_safe_data_paths(tmp_path: Path, monkeypatch):
    custom_dir_1 = tmp_path / "custom_cvat_1"
    custom_dir_2 = tmp_path / "custom_cvat_2"
    custom_dir_1.mkdir()
    custom_dir_2.mkdir()

    # Lưu giá trị env ban đầu
    old_export = os.environ.get("POINTSNAP_EXPORT_DIR")
    old_nuscenes = os.environ.get("NUSCENES_ROOT")

    try:
        # 1. export_dirs() nhận custom_dirs trực tiếp, không phụ thuộc os.environ
        dirs = export_dirs([custom_dir_1, custom_dir_2])
        assert dirs[0] == custom_dir_1
        assert dirs[1] == custom_dir_2

        # 2. Tạo bản xuất giả lập trong custom_dir_1 cho Task 42
        scene_dir = custom_dir_1 / "scene-test"
        scene_dir.mkdir(parents=True)
        (scene_dir / "cvat_task.json").write_text(json.dumps({"task_id": 42}), encoding="utf-8")
        manifest_path = scene_dir / "manifest.json"
        manifest_path.write_text(json.dumps({"task_id": 42, "scene": "scene-test"}), encoding="utf-8")

        mock_dataroot_1 = tmp_path / "nuscenes_project_1"
        mock_dataroot_2 = tmp_path / "nuscenes_project_2"

        # Giả lập ManifestFrames để kiểm tra việc truyền dataroot trực tiếp
        received_args = {}

        class DummyManifestFrames:
            def __init__(self, path, dataroot=None):
                received_args["path"] = Path(path)
                received_args["dataroot"] = dataroot

            def check_matches(self, names):
                pass

        monkeypatch.setattr("pointsnap.cli.common.ManifestFrames", DummyManifestFrames)

        job_42 = JobData(
            url="http://cvat:8080",
            task_id=42,
            job_id=1,
            start_frame=0,
            stop_frame=1,
            labels={},
            cuboids=[],
        )

        # Lần gọi 1: Dùng custom_dir_1 và dataroot 1
        frames1, note1 = frames_for_job(
            job_42,
            custom_export_dirs=[custom_dir_1],
            dataroot=mock_dataroot_1,
        )
        assert frames1 is not None
        assert received_args["path"] == manifest_path
        assert received_args["dataroot"] == str(mock_dataroot_1)
        assert "Point cloud:" in note1

        # Lần gọi 2: Dùng custom_dir_2 (không có manifest của task 42) và dataroot 2
        frames2, note2 = frames_for_job(
            job_42,
            custom_export_dirs=[custom_dir_2],
            dataroot=mock_dataroot_2,
        )
        assert frames2 is None
        assert "Không tìm thấy manifest.json của task 42" in note2

        # 3. Kiểm tra os.environ hoàn toàn không bị đụng tới hay sửa đổi
        assert os.environ.get("POINTSNAP_EXPORT_DIR") == old_export
        assert os.environ.get("NUSCENES_ROOT") == old_nuscenes
    finally:
        if old_export is not None:
            os.environ["POINTSNAP_EXPORT_DIR"] = old_export
        if old_nuscenes is not None:
            os.environ["NUSCENES_ROOT"] = old_nuscenes


def test_thread_safe_concurrent_data_paths(tmp_path: Path, monkeypatch):
    import concurrent.futures

    proj1_export = tmp_path / "export_proj_1"
    proj2_export = tmp_path / "export_proj_2"
    proj1_export.mkdir()
    proj2_export.mkdir()

    (proj1_export / "scene_a").mkdir()
    (proj1_export / "scene_a" / "cvat_task.json").write_text(json.dumps({"task_id": 101}), encoding="utf-8")
    (proj1_export / "scene_a" / "manifest.json").write_text(json.dumps({"task_id": 101}), encoding="utf-8")

    (proj2_export / "scene_b").mkdir()
    (proj2_export / "scene_b" / "cvat_task.json").write_text(json.dumps({"task_id": 202}), encoding="utf-8")
    (proj2_export / "scene_b" / "manifest.json").write_text(json.dumps({"task_id": 202}), encoding="utf-8")

    # Xóa hoàn toàn các biến môi trường
    monkeypatch.delenv("POINTSNAP_EXPORT_DIR", raising=False)
    monkeypatch.delenv("NUSCENES_ROOT", raising=False)

    class ThreadSafeDummyFrames:
        def __init__(self, path, dataroot=None):
            self.path = Path(path)
            self.dataroot = dataroot

        def check_matches(self, names):
            pass

    monkeypatch.setattr("pointsnap.cli.common.ManifestFrames", ThreadSafeDummyFrames)

    job_101 = JobData("http://cvat:8080", 101, 1, 0, 1, {}, [])
    job_202 = JobData("http://cvat:8080", 202, 2, 0, 1, {}, [])

    def worker(task_num: int):
        if task_num == 1:
            frames, note = frames_for_job(
                job_101,
                custom_export_dirs=[proj1_export],
                dataroot=tmp_path / "dataroot_1",
            )
            assert frames is not None
            assert "scene_a" in str(frames.path)
            assert str(tmp_path / "dataroot_1") == str(frames.dataroot)
        else:
            frames, note = frames_for_job(
                job_202,
                custom_export_dirs=[proj2_export],
                dataroot=tmp_path / "dataroot_2",
            )
            assert frames is not None
            assert "scene_b" in str(frames.path)
            assert str(tmp_path / "dataroot_2") == str(frames.dataroot)

    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex:
        futures = [ex.submit(worker, 1 if i % 2 == 0 else 2) for i in range(12)]
        for f in concurrent.futures.as_completed(futures):
            f.result()

    # Kiểm tra biến môi trường vẫn không bị tạo ra
    assert "POINTSNAP_EXPORT_DIR" not in os.environ
    assert "NUSCENES_ROOT" not in os.environ


# --- Test 4: Gắn cờ quét lại để tránh trượt ID (Điểm 4 Mục 6) ---

def test_flag_scan_creates_rescan_run(mock_home: Path, client: TestClient):
    pm = ProjectManager(mock_home)
    pm.create_project(name="Scan Project", slug="scan-proj")

    # Giả lập một run cũ đã hoàn thành
    run_dir = mock_home / "projects" / "scan-proj" / "runs" / "20261007-000000-job5"
    run_dir.mkdir(parents=True)
    summary_data = {
        "run_id": "20261007-000000-job5",
        "job_id": 5,
        "timestamp": "2026-10-07T00:00:00Z",
        "num_boxes": 100,
        "num_errors": 2,
        "num_warnings": 1,
        "gate_passed": False,
        "flagged": False,
    }
    (run_dir / "summary.json").write_text(json.dumps(summary_data), encoding="utf-8")

    # Gọi endpoint flag
    res = client.post("/api/projects/scan-proj/scans/20261007-000000-job5/flag")
    assert res.status_code == 202
    data = res.json()
    assert "run_id" in data
    # run mới phải trỏ đúng job 5
    assert "-job5" in data["run_id"]
    assert "Đã khởi động quét lại và gắn cờ lỗi" in data["message"]


# --- Test 5: Xác thực và xóa dự án an toàn (Điểm 5 Mục 6) ---

def test_project_security_and_safe_delete(mock_home: Path, client: TestClient):
    # 1. Chặn slug độc hại
    with pytest.raises(ProjectError):
        validate_slug("../hack")
    with pytest.raises(ProjectError):
        validate_slug("project/with/slashes")

    # 2. Tạo và xóa dự án an toàn
    client.post("/api/projects", json={"name": "Temp Project", "slug": "temp-proj"})
    assert (mock_home / "projects" / "temp-proj").is_dir()

    del_res = client.delete("/api/projects/temp-proj")
    assert del_res.status_code == 200
    assert not (mock_home / "projects" / "temp-proj").exists()


# --- Test 6: Kiểm tra tính hợp lệ của Guideline (Validation) ---

def test_guideline_validation(mock_home: Path, client: TestClient):
    client.post("/api/projects", json={"name": "Guideline Project", "slug": "g-proj"})

    # Cấu hình sai: warning_m > error_m
    bad_yaml = """
cvat:
  url: http://localhost:8080
  flag_attribute: pointsnap_error
floating:
  warning_m: 0.30
  error_m: 0.10
"""
    res = client.put("/api/projects/g-proj/guideline", json={"yaml": bad_yaml})
    assert res.status_code == 400
    assert "warning_m < error_m" in res.json()["detail"]


# --- Test 7: Bật/tắt luật loại bỏ findings tương ứng ---

def test_rule_toggle_filters_findings():
    # Tạo box sai kích thước class bus (25m > 18.5m)
    bus = Cuboid(center=(0, 0, 0), dims=(25.0, 2.8, 3.2), yaw=0.0, label="bus", frame=0, track_id=1)
    labels = labels_from_api([{"id": 1, "name": "bus", "attributes": []}])
    job = JobData(url="http://cvat:8080", task_id=1, job_id=1, start_frame=0, stop_frame=0, labels=labels, cuboids=[bus])

    # 1. Khi bật luật size_class_range (mặc định)
    cfg_on = Config(
        cvat=None,
        floating=None,
        size=None,
        track=None,
        gate=GateConfig(0, 10),
    )
    # Lấy config chuẩn
    from pointsnap.core.config import load_config
    cfg = load_config()
    findings_on = scan_cuboids(job, cfg)
    assert any(f.rule == "size.class_range" for f in findings_on)

    # 2. Tắt luật size_class_range
    from pointsnap.core.config import RulesConfig
    cfg_off = Config(
        cvat=cfg.cvat,
        floating=cfg.floating,
        size=cfg.size,
        track=cfg.track,
        gate=cfg.gate,
        rules=RulesConfig(size_class_range=False),
    )
    findings_off = scan_cuboids(job, cfg_off)
    assert not any(f.rule == "size.class_range" for f in findings_off)


# --- Test 8: Hàm pure gate_verdict ---

def test_gate_verdict_logic():
    gate_cfg = GateConfig(max_errors=0, max_warnings=2)

    # Đạt: không lỗi, 2 cảnh báo
    warn_findings = [
        Finding(ErrorType.SIZE, "size.in_track", Severity.WARNING, 1, "car", "Lệch nhẹ"),
        Finding(ErrorType.SIZE, "size.in_track", Severity.WARNING, 2, "car", "Lệch nhẹ"),
    ]
    passed, reasons = gate_verdict(warn_findings, gate_cfg)
    assert passed is True
    assert len(reasons) == 0

    # Không đạt: 1 lỗi và 3 cảnh báo
    err_findings = warn_findings + [
        Finding(ErrorType.SIZE, "size.in_track", Severity.WARNING, 3, "car", "Lệch nhẹ"),
        Finding(ErrorType.SIZE, "size.class_range", Severity.ERROR, 4, "bus", "Lệch lớn"),
    ]
    passed, reasons = gate_verdict(err_findings, gate_cfg)
    assert passed is False
    assert len(reasons) == 2
    assert "Số lỗi (1)" in reasons[0]
    assert "Số cảnh báo (3)" in reasons[1]


# --- Test 9: Quét end-to-end với Mock CVAT qua API ---

def test_end_to_end_mock_scan(mock_home: Path, client: TestClient, monkeypatch):
    import time
    from tests.test_scan_gate import MockCvatServer, pts

    job1_annos = {
        "shapes": [
            {"id": 100, "type": "cuboid", "label_id": 1, "frame": 0, "points": pts(0, l=25.0, w=2.8, h=3.2), "attributes": []}
        ],
        "tracks": [],
    }
    server = MockCvatServer({1: job1_annos})
    monkeypatch.setattr("requests.Session.request", server.request)

    # 1. Tạo dự án
    create_res = client.post(
        "/api/projects",
        json={"name": "E2E Project", "slug": "e2e-proj", "cvat_token": "mock_token"},
    )
    assert create_res.status_code == 201

    # 2. Khởi động quét Job 1
    scan_res = client.post("/api/projects/e2e-proj/scans", json={"job_id": 1, "flag": True})
    assert scan_res.status_code == 202
    run_id = scan_res.json()["run_id"]

    # 3. Chờ tác vụ nền hoàn thành
    deadline = time.time() + 5.0
    run_data = {}
    while time.time() < deadline:
        get_res = client.get(f"/api/projects/e2e-proj/scans/{run_id}")
        assert get_res.status_code == 200
        run_data = get_res.json()
        if run_data.get("status") in ("done", "failed"):
            break
        time.sleep(0.1)

    assert run_data["status"] == "done"
    summary = run_data["summary"]
    assert summary["num_boxes"] == 1
    assert summary["num_errors"] == 1
    assert summary["gate_passed"] is False
    assert summary["flagged"] is True

    # 4. Kiểm tra tải file báo cáo
    html_res = client.get(f"/api/projects/e2e-proj/scans/{run_id}/report.html")
    assert html_res.status_code == 200
    assert "Job #1" in html_res.text

    csv_res = client.get(f"/api/projects/e2e-proj/scans/{run_id}/report.csv")
    assert csv_res.status_code == 200
    assert "size.class_range" in csv_res.text


# --- Test 10 (Lỗi bắt buộc 1 — mục 7): Không có CORS header khi gọi từ origin lạ ---

def test_no_cors_header_for_foreign_origin(client: TestClient):
    """Preflight từ origin lạ KHÔNG được trả access-control-allow-origin.

    Mục 7 bắt buộc: CORSMiddleware allow_origins=['*'] bị xóa; giao diện được
    phục vụ cùng origin nên không cần CORS.
    """
    # OPTIONS preflight từ origin độc hại
    res = client.options(
        "/api/projects",
        headers={
            "Origin": "https://evil.example",
            "Access-Control-Request-Method": "GET",
        },
    )
    # Không có header ACAO dù phản hồi thành công hay không
    assert "access-control-allow-origin" not in res.headers
    assert "Access-Control-Allow-Origin" not in res.headers

    # GET thường từ origin lạ cũng không có ACAO
    get_res = client.get(
        "/api/projects",
        headers={"Origin": "https://evil.example"},
    )
    assert "access-control-allow-origin" not in get_res.headers
    assert "Access-Control-Allow-Origin" not in get_res.headers


# --- Test 11 (Lỗi bắt buộc 2 — mục 7): Xóa class trong save_guideline thực sự biến mất ---

def test_delete_class_from_guideline_is_permanent(mock_home: Path, client: TestClient):
    """Sau khi PUT guideline không có 'bicycle', đọc lại thì bicycle không còn.

    Mục 7 bắt buộc: save_guideline phải ghi thay thế (trộn với mặc định),
    không trộn với file cũ.
    """
    pm = ProjectManager(mock_home)
    # 1. Tạo dự án — guideline mặc định chứa sẵn bicycle trong manual_ranges
    pm.create_project(name="Class Delete Project", slug="class-del")
    data, _ = pm.get_guideline("class-del")

    # Đảm bảo mặc định có bicycle
    manual_ranges = data.get("size", {}).get("manual_ranges", {})
    assert "bicycle" in manual_ranges, "Guideline mặc định phải có class 'bicycle'"

    # 2. Gửi PUT guideline với manual_ranges không có bicycle
    new_ranges = {k: v for k, v in manual_ranges.items() if k != "bicycle"}
    new_size = {**data.get("size", {}), "manual_ranges": new_ranges}
    new_config = {**data, "size": new_size}

    put_res = client.put(
        "/api/projects/class-del/guideline",
        json={"config": new_config},
    )
    assert put_res.status_code == 200

    # 3. Đọc lại — bicycle phải thực sự biến mất
    read_res = client.get("/api/projects/class-del/guideline")
    assert read_res.status_code == 200
    saved_ranges = read_res.json()["config"]["size"]["manual_ranges"]
    assert "bicycle" not in saved_ranges, (
        "bicycle vẫn còn trong guideline sau khi xóa — lỗi merge với file cũ!"
    )

    # 4. Kiểm tra trực tiếp trên đĩa
    g_file = mock_home / "projects" / "class-del" / "guideline.yaml"
    on_disk = yaml.safe_load(g_file.read_text(encoding="utf-8"))
    assert "bicycle" not in on_disk.get("size", {}).get("manual_ranges", {})


# --- Test 12 (điểm nhỏ 3 — mục 7): run_id độc hại bị từ chối ---

def test_malicious_run_id_rejected(mock_home: Path, client: TestClient):
    """run_id sai định dạng hoặc cố tình path traversal phải bị từ chối với HTTP 400."""
    pm = ProjectManager(mock_home)
    pm.create_project(name="Path Traversal Test", slug="ptrav")

    bad_ids = [
        "bad-format",
        "12345",
        "2024-01-01-job2",
        "evil..traversal",
        "..%5C..%5Csecret",
        "hack-run-id",
    ]
    for bad_id in bad_ids:
        res = client.get(f"/api/projects/ptrav/scans/{bad_id}")
        assert res.status_code == 400, (
            f"run_id '{bad_id}' phải bị từ chối với 400, nhận {res.status_code}"
        )

        res_html = client.get(f"/api/projects/ptrav/scans/{bad_id}/report.html")
        assert res_html.status_code == 400

        res_csv = client.get(f"/api/projects/ptrav/scans/{bad_id}/report.csv")
        assert res_csv.status_code == 400

    # run_id hợp lệ (với ms suffix) phải qua validation (404 vì run chưa tồn tại trên đĩa)
    valid_id = "20240101-120000-123-job2"
    res = client.get(f"/api/projects/ptrav/scans/{valid_id}")
    assert res.status_code == 404  # không tìm thấy run, nhưng không phải 400 validation


# --- Test 13 (điểm nhỏ 5 — mục 7): check_cvat với slug không tồn tại trả 404 ---

def test_check_cvat_unknown_slug_returns_404(client: TestClient):
    """check_cvat với slug không tồn tại phải trả 404, không phải 500."""
    res = client.get("/api/projects/nonexistent-slug/cvat/check")
    assert res.status_code == 404
    assert "nonexistent-slug" in res.json()["detail"]
