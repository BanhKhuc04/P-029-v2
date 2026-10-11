"""Hồi quy phần 04: scope, lưu trữ, CLI, report và cầu nối extension."""
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import Mock
import csv
import io
import json

import pytest
from fastapi.testclient import TestClient

from pointsnap.adapters.cvat.reader import JobData
from pointsnap.cli.main import main
from pointsnap.core.config import ConfigError, load_config
from pointsnap.core.model import Cuboid, ErrorType, Finding, Severity
from pointsnap.report.html import generate_html_report
from pointsnap.web.app import create_app
from pointsnap.web.projects import ProjectError, ProjectManager
from pointsnap.web.runner import ScanRunner

RUN = "20261011-120000-123-job2"


@pytest.fixture
def client(tmp_path):
    app = create_app(tmp_path)
    for slug in ("a", "b"):
        app.state.pm.create_project(slug, slug=slug, cvat_token="fake-token")
    yield TestClient(app)
    app.state.runner._executor.shutdown(wait=True)


def run_files(client, slug="a", findings=None):
    path = client.app.state.pm._project_dir(slug) / "runs" / RUN
    path.mkdir(exist_ok=True)
    (path / "summary.json").write_text(json.dumps({"job_id": 2, "timestamp": "2026-10-11"}))
    (path / "findings.json").write_text(json.dumps(findings or []))
    return path


def job():
    return JobData("http://localhost:8080", 1, 2, 0, 0, {}, [
        Cuboid((0, 0, 0), (4, 2, 1.5), 0, "car", 0, source_id=8),
        Cuboid((0, 0, 0), (4, 2, 1.5), 0, "car", 1, outside=True),
    ])


def test_memory_run_cannot_be_read_or_flagged_from_other_project(client):
    runner = client.app.state.runner
    runner._scans[RUN] = {"run_id": RUN, "project_slug": "a", "job_id": 2, "status": "queued"}
    runner._executor.submit = Mock()
    assert client.get(f"/api/projects/b/scans/{RUN}").status_code == 404
    assert client.post(f"/api/projects/b/scans/{RUN}/flag").status_code == 404
    runner._executor.submit.assert_not_called()


def test_starting_two_scans_at_identical_time_does_not_overwrite(client, monkeypatch):
    import pointsnap.web.runner as module
    real = module.datetime.datetime
    class Frozen(real):
        @classmethod
        def now(cls, tz=None):
            return real(2026, 10, 11, 12, 0, 0, 123000, tzinfo=tz)
    monkeypatch.setattr(module.datetime, "datetime", Frozen)
    runner = client.app.state.runner
    runner._executor.submit = Mock()
    ids = [runner.start_scan("a", 2) for _ in range(2)]
    assert ids[0] != ids[1]
    assert len(runner.list_runs("a")) == 2


def test_queued_run_survives_restart_as_failed(client):
    runner = client.app.state.runner
    runner._executor.submit = Mock()
    run_id = runner.start_scan("a", 2)
    fresh = ScanRunner(client.app.state.pm)
    try:
        restored = fresh.get_run("a", run_id)
        assert restored["status"] == "failed"
        assert "khởi động" in restored["error"].lower()
        assert fresh.list_runs("a")[0]["status"] == "failed"
    finally:
        fresh._executor.shutdown()


def test_active_project_cannot_be_deleted(client):
    runner = client.app.state.runner
    runner._executor.submit = Mock()
    runner.start_scan("a", 2)
    assert client.delete("/api/projects/a").status_code == 409
    assert client.get("/api/projects/a").status_code == 200


@pytest.mark.parametrize("suffix", ["scans", "scans/" + RUN + "/reviews", "scans/" + RUN + "/report.csv"])
def test_unknown_project_is_not_empty_success(client, suffix):
    assert client.get("/api/projects/missing/" + suffix).status_code == 404


def test_unknown_run_reviews_is_not_empty_success(client):
    assert client.get(f"/api/projects/a/scans/{RUN}/reviews").status_code == 404


@pytest.mark.parametrize("filename,payload", [("summary.json", "{"), ("findings.json", "{}"), ("reviews.json", "[]"),
                                              ("findings.json", "[1]"), ("summary.json", '{"job_id": NaN}')])
def test_corrupt_run_files_have_controlled_error(client, filename, payload):
    path = run_files(client)
    (path / filename).write_text(payload)
    assert client.get(f"/api/projects/a/scans/{RUN}").status_code == 409


def test_failed_scan_is_persisted_and_client_is_closed(client, monkeypatch):
    runner = client.app.state.runner
    runner._executor.submit = Mock()
    cvat = Mock(url="http://localhost:8080")
    monkeypatch.setattr("pointsnap.web.runner.CvatClient", lambda *a, **kw: cvat)
    monkeypatch.setattr("pointsnap.web.runner.load_job", Mock(side_effect=RuntimeError("network offline")))
    run_id = runner.start_scan("a", 2)
    runner._execute_scan(run_id, "a", 2, False)
    cvat.session.close.assert_called_once()
    runner._scans.clear()
    assert runner.get_run("a", run_id)["status"] == "failed"


def test_web_cli_reports_agree_on_coverage_and_box_count(client, monkeypatch, tmp_path):
    runner = client.app.state.runner
    runner._executor.submit = Mock()
    data = job()
    cvat = Mock(url=data.url)
    monkeypatch.setattr("pointsnap.web.runner.CvatClient", lambda *a, **kw: cvat)
    monkeypatch.setattr("pointsnap.web.runner.load_job", lambda *a: data)
    monkeypatch.setattr("pointsnap.web.runner.frames_for_job", lambda *a, **kw: (None, "Thiếu LiDAR"))
    run_id = runner.start_scan("a", 2)
    runner._execute_scan(run_id, "a", 2, False)
    result = client.get(f"/api/projects/a/scans/{run_id}").json()
    assert result["status"] == "done"
    assert result["summary"]["num_boxes"] == 1
    assert result["summary"]["gate_passed"] is False
    assert result["summary"]["coverage_gaps"]
    html = client.get(f"/api/projects/a/scans/{run_id}/report.html").text
    assert "Tổng 1 box" in html and "Kiểm tra một phần" in html
    assert "sẵn sàng để nộp" not in html
    for module in ("scan_cmd", "gate_cmd"):
        monkeypatch.setattr(f"pointsnap.cli.{module}.CvatClient", lambda *a, **kw: cvat)
        monkeypatch.setattr(f"pointsnap.cli.{module}.load_job", lambda *a: data)
        monkeypatch.setattr(f"pointsnap.cli.{module}.frames_for_job", lambda *a, **kw: (None, "Thiếu LiDAR"))
    monkeypatch.setenv("CVAT_TOKEN", "fake-token")
    assert main(["scan", "--job", "2", "--out", str(tmp_path / "cli")]) == 0
    assert main(["gate", "--job", "2"]) == 1
    assert "Kiểm tra một phần" in (tmp_path / "cli/report_job_2.html").read_text(encoding="utf-8")
    assert result["summary"]["num_errors"] == len([f for f in result["findings"] if f["severity"] == "error"])


@pytest.mark.parametrize("stage", ["save_snapshot", "frames_for_job", "generate_html_report"])
def test_cli_runtime_failures_return_three(stage, monkeypatch, tmp_path, capsys):
    monkeypatch.setattr("pointsnap.cli.scan_cmd.CvatClient", lambda *a, **kw: Mock(url="http://cvat"))
    monkeypatch.setattr("pointsnap.cli.scan_cmd.load_job", lambda *a: job())
    monkeypatch.setattr("pointsnap.cli.scan_cmd.frames_for_job", lambda *a, **kw: (None, "missing"))
    monkeypatch.setattr("pointsnap.cli.scan_cmd." + stage, Mock(side_effect=OSError("disk or input failure")))
    assert main(["scan", "--job", "2", "--out", str(tmp_path / "cli")]) == 3
    assert "Lỗi" in capsys.readouterr().err


def test_missing_preset_does_not_leave_half_project(client):
    assert client.post("/api/projects", json={"name": "child", "slug": "child", "preset_slug": "missing"}).status_code == 400
    assert client.get("/api/projects/child").status_code == 404
    assert client.post("/api/projects", json={"name": "child", "slug": "child"}).status_code == 201


@pytest.mark.parametrize("section,key", [("size", "manual_ranges"), ("track", "groups")])
def test_bad_dynamic_mapping_returns_400_and_preserves_guideline(client, section, key):
    old = client.get("/api/projects/a/guideline").json()
    assert client.put("/api/projects/a/guideline", json={"config": {section: {key: None}}}).status_code == 400
    assert client.get("/api/projects/a/guideline").json() == old


def test_blank_project_update_is_rejected(client):
    assert client.put("/api/projects/a", json={"name": "   "}).status_code == 400
    assert client.get("/api/projects/a").json()["name"] == "a"


def test_raw_guideline_cannot_leak_legacy_token(client):
    path = client.app.state.pm._project_dir("a") / "guideline.yaml"
    path.write_text(path.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    import yaml
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    data["cvat"]["token"] = "legacy-secret"
    path.write_text(yaml.safe_dump(data))
    assert "legacy-secret" not in client.get("/api/projects/a/guideline").text


def test_reset_does_not_import_personal_cvat_url(client, monkeypatch):
    monkeypatch.setenv("CVAT_URL", "http://personal:8080")
    reset = client.post("/api/projects/a/guideline/reset").json()
    assert reset["config"]["cvat"]["url"] != "http://personal:8080"


def test_preview_manifest_is_scoped_to_snapshot_origin(client, monkeypatch):
    from pointsnap.adapters.cvat.writer import save_snapshot
    from pointsnap.web.preview import finding_preview, PreviewError
    path = run_files(client, findings=[{"frame": 0, "source_id": 8}])
    save_snapshot(job(), path / "snapshot.json")
    captured = {}
    def find(*args, **kwargs):
        captured.update(kwargs)
        return None
    monkeypatch.setattr("pointsnap.web.preview.find_manifest", find)
    with pytest.raises(PreviewError):
        finding_preview(path, client.app.state.pm.get_project("a"), 0)
    assert captured.get("url") == job().url


def test_bridge_does_not_send_commands_to_same_job_on_other_cvat(client):
    client.put("/api/projects/b", json={"cvat_url": "http://other:8080"})
    params = {"job_id": 2, "cvat_url": "http://localhost:8080", "after": -1}
    client.get("/api/extension/poll", params=params)
    sent = client.post("/api/extension/focus", json={"job_id": 2, "frame": 7, "cvat_url": "http://other:8080"}).json()
    assert sent["extension_online"] is False
    params["after"] = 0
    assert client.get("/api/extension/poll", params=params).json()["command"] is None
    params["cvat_url"] = "http://other:8080"
    assert client.get("/api/extension/poll", params=params).json()["command"]["frame"] == 7


def test_csv_unicode_newlines_and_formula_safety(tmp_path):
    from pointsnap.report.csv_rep import generate_csv_report
    finding = Finding(ErrorType.SIZE, "size.class_range", Severity.WARNING, 0, "=1+1", 'Tiếng Việt,\n<b>nhãn</b>', value=-1)
    path = generate_csv_report(job(), [finding], tmp_path / "report.csv")
    rows = list(csv.DictReader(io.StringIO(path.read_text(encoding="utf-8-sig"))))
    assert rows[0]["label"] == "'=1+1"
    assert rows[0]["message"] == finding.message
    assert rows[0]["value"] == "-1"
    html = generate_html_report(job(), [finding], tmp_path / "report.html").read_text(encoding="utf-8")
    assert "&lt;b&gt;nhãn&lt;/b&gt;" in html and "<b>nhãn</b>" not in html


def test_local_api_uses_coverage_gate_and_actual_rule_switches():
    from pointsnap.api import report_bytes
    cfg = load_config(env={})
    payload = json.loads(report_bytes(job(), [], cfg, "json", {"point_cloud_available": False, "coverage_gaps": ["Thiếu LiDAR"]}))
    assert payload["passed"] is False
    assert payload["gate_reasons"] == ["Thiếu LiDAR"]
    assert "fit.overlap" in payload["checks"] and "attr.missing" in payload["checks"]


def test_local_api_rule_checks_do_not_claim_disabled_rules():
    from dataclasses import replace
    from pointsnap.api import report_bytes
    cfg = load_config(env={})
    cfg = replace(cfg, rules=replace(cfg.rules, size_class_range=False))
    payload = json.loads(report_bytes(job(), [], cfg, "json", {"point_cloud_available": False}))
    assert "size.class_range" not in payload["checks"]


def test_queue_limit_returns_429_without_creating_extra_run(client):
    runner = client.app.state.runner
    runner.max_pending = 2
    runner._executor.submit = Mock()
    for _ in range(2):
        assert client.post("/api/projects/a/scans", json={"job_id": 2}).status_code == 202
    assert client.post("/api/projects/a/scans", json={"job_id": 2}).status_code == 429
    assert len(runner.list_runs("a")) == 2


@pytest.mark.parametrize("job_id", [0, -1])
def test_invalid_job_is_rejected_before_queue(client, job_id):
    assert client.post("/api/projects/a/scans", json={"job_id": job_id}).status_code == 422
    assert client.get("/api/projects/a/scans").json() == []


def test_failed_report_cannot_be_downloaded(client):
    path = run_files(client)
    (path / "report.html").write_text("partial output")
    client.app.state.runner._scans[RUN] = {"run_id": RUN, "project_slug": "a", "job_id": 2, "status": "failed"}
    assert client.get(f"/api/projects/a/scans/{RUN}/report.html").status_code == 409
    assert client.post(f"/api/projects/a/scans/{RUN}/flag").status_code == 409


def test_old_run_cannot_flag_job_on_changed_server(client):
    path = run_files(client)
    (path / "summary.json").write_text(json.dumps({"job_id": 2, "cvat_url": "http://original:8080"}))
    client.app.state.runner._executor.submit = Mock()
    assert client.post(f"/api/projects/a/scans/{RUN}/flag").status_code == 409
    client.app.state.runner._executor.submit.assert_not_called()


@pytest.mark.parametrize("location", ["check", "tasks", "scan"])
def test_cvat_error_never_exposes_project_token(client, monkeypatch, caplog, location):
    from pointsnap.adapters.cvat.client import CvatError
    cvat = Mock(url="http://localhost:8080")
    error = CvatError("CVAT echoed fake-token in its body")
    cvat.server_version.side_effect = error
    cvat.get_tasks.side_effect = error
    monkeypatch.setattr("pointsnap.web.app.CvatClient", lambda *a, **kw: cvat)
    if location != "scan":
        response = client.get("/api/projects/a/cvat/" + location)
        assert "fake-token" not in response.text
        cvat.session.close.assert_called_once()
    else:
        runner = client.app.state.runner
        runner._executor.submit = Mock()
        monkeypatch.setattr("pointsnap.web.runner.CvatClient", lambda *a, **kw: cvat)
        monkeypatch.setattr("pointsnap.web.runner.load_job", Mock(side_effect=error))
        run_id = runner.start_scan("a", 2)
        runner._execute_scan(run_id, "a", 2, False)
        assert "fake-token" not in client.get(f"/api/projects/a/scans/{run_id}").text
        assert "fake-token" not in caplog.text


def test_concurrent_project_updates_preserve_both_fields(client):
    pm = client.app.state.pm
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(pm.update_project, "a", update) for update in
                   ({"description": "ghi chú"}, {"nuscenes_root": "dataset"})]
        for future in futures:
            future.result()
    saved = pm.get_project("a")
    assert saved["description"] == "ghi chú" and saved["nuscenes_root"] == "dataset"


def test_vietnamese_project_name_generates_valid_slug(client):
    response = client.post("/api/projects", json={"name": "Dự án Đường phố"})
    assert response.status_code == 201
    assert response.json()["slug"] == "du-an-duong-pho"


def test_atomic_write_failure_preserves_previous_file(tmp_path, monkeypatch):
    from pointsnap.web.storage import write_json
    target = tmp_path / "file.json"
    write_json(target, {"old": 1})
    monkeypatch.setattr("pointsnap.web.storage.os.replace", Mock(side_effect=OSError("disk full")))
    with pytest.raises(OSError):
        write_json(target, {"new": 2})
    assert json.loads(target.read_text()) == {"old": 1}
    assert list(tmp_path.iterdir()) == [target]


def test_bridge_requires_scope_when_multiple_servers_configured(client):
    client.put("/api/projects/b", json={"cvat_url": "http://other:8080"})
    assert client.get("/api/extension/poll", params={"job_id": 2}).status_code == 400
    assert client.get("/api/extension/jobs/2").status_code == 400
    assert client.post("/api/extension/focus", json={"job_id": 2, "frame": 0}).status_code == 400


@pytest.mark.parametrize("url", ["http://localhost:bad", "javascript:alert(1)"])
def test_invalid_bridge_url_is_controlled(client, url):
    assert client.get("/api/extension/jobs/2", params={"cvat_url": url}).status_code == 400


def test_restart_bridge_drops_old_sequence_and_can_receive_next_command():
    from pointsnap.web.link import ExtensionLink
    bridge = ExtensionLink()
    assert bridge.poll(2, 100)["seq"] == 0
    assert bridge.focus(2, {"frame": 3})["extension_online"]
    assert bridge.poll(2, 0)["command"]["frame"] == 3
    assert bridge.poll(2, -1)["command"] is None


def test_review_delete_concurrency_and_precision_denominator(client):
    from pointsnap.web.preview import load_reviews, save_review
    path = run_files(client, findings=[{}, {}])
    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(lambda i: save_review(path, i, "ok" if i % 2 else "fp"), range(20)))
    assert len(load_reviews(path)) == 20
    save_review(path, 1, None)
    reviews = load_reviews(path)
    assert len(reviews) == 19 and "1" not in reviews


def test_preview_without_object_identity_cannot_select_random_box():
    from pointsnap.web.preview import _find_box
    assert _find_box([Cuboid((0, 0, 0), (1, 1, 1), 0, "car", 0)], {"frame": 0}) is None


@pytest.mark.parametrize("code", [401, 403, 404, 422, 500])
def test_local_api_http_error_mapping_and_slot_release(tmp_path, monkeypatch, code):
    import requests
    import threading
    from pointsnap.api import ReportServer, ReportCvatError
    monkeypatch.setattr("pointsnap.api.create_report", Mock(side_effect=ReportCvatError("secret-body", code)))
    server = ReportServer(("127.0.0.1", 0), "http://cvat:8080")
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    try:
        response = requests.get(f"http://127.0.0.1:{server.server_port}/pointsnap/jobs/2/report",
                                headers={"Authorization": "Bearer fake"}, timeout=5)
        assert response.status_code == (code if code != 500 else 502)
        assert "secret-body" not in response.text
        assert server.report_slots.acquire(blocking=False)
        assert server.report_slots.acquire(blocking=False)
        assert not server.report_slots.acquire(blocking=False)
    finally:
        server.shutdown()
        server.server_close()
        worker.join()


def test_local_api_busy_does_not_call_cvat_and_health_remains_available(monkeypatch):
    import requests
    import threading
    from pointsnap.api import ReportServer
    create = Mock()
    monkeypatch.setattr("pointsnap.api.create_report", create)
    server = ReportServer(("127.0.0.1", 0), "http://cvat:8080")
    server.report_slots.acquire()
    server.report_slots.acquire()
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    base = f"http://127.0.0.1:{server.server_port}"
    try:
        assert requests.get(base + "/pointsnap/health", timeout=5).status_code == 200
        assert requests.get(base + "/pointsnap/jobs/2/report", headers={"Authorization": "Bearer fake"}, timeout=5).status_code == 429
        create.assert_not_called()
    finally:
        server.shutdown()
        server.server_close()
        worker.join()


def test_completed_run_with_missing_output_is_not_listed_as_done(client):
    run_files(client)
    client.app.state.runner._scans[RUN] = {"run_id": RUN, "project_slug": "a", "job_id": 2, "status": "done"}
    assert client.get(f"/api/projects/a/scans/{RUN}").status_code == 409
    assert client.get("/api/projects/a/scans").json()[0]["status"] == "failed"


def test_cli_cvat_error_body_is_redacted(monkeypatch, capsys, tmp_path):
    response = Mock(status_code=401, text="body echoed fake-token", content=b"body")
    monkeypatch.setenv("CVAT_TOKEN", "fake-token")
    monkeypatch.setattr("requests.Session.request", lambda *a, **kw: response)
    assert main(["scan", "--job", "2", "--out", str(tmp_path)]) == 3
    assert "fake-token" not in capsys.readouterr().err


def test_report_client_malformed_backend_json_is_upstream_error():
    from pointsnap.api import ReportCvatClient, ReportCvatError
    response = Mock(status_code=200, content=b"bad json")
    response.json.side_effect = ValueError("bad json")
    cvat = ReportCvatClient("http://cvat:8080", "fake")
    cvat.session.request = Mock(return_value=response)
    try:
        with pytest.raises(ReportCvatError, match="JSON"):
            cvat.get_job(2)
    finally:
        cvat.session.close()
