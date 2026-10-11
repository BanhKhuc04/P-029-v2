import json
import threading

import pytest
import requests

from pointsnap.adapters.cvat.reader import JobData
from pointsnap.api import ReportCvatClient as CvatClient, ReportCvatError as CvatError, ReportServer, report_bytes
from pointsnap.core.config import load_config
from pointsnap.core.model import Cuboid, ErrorType, Finding, Severity


@pytest.fixture
def report_data():
    job = JobData(
        url="http://localhost:8080", task_id=1, job_id=1, start_frame=0, stop_frame=0,
        labels={}, cuboids=[Cuboid((0, 0, 0), (10, 3.6, 3), 0, "bus", 0, track_id=98)],
    )
    finding = Finding(ErrorType.SIZE, "size.class_range", Severity.ERROR, 0, "bus",
                      "Chiều rộng vượt ngưỡng", track_id=98, value=3.6, threshold=3.2)
    return job, [finding], load_config(env={})


@pytest.fixture
def api_server(monkeypatch, report_data):
    calls = []

    def create(client, job_id):
        authorization = client.session.headers["Authorization"]
        calls.append((authorization, job_id))
        if authorization != "Bearer user-token":
            raise CvatError("backend-secret", status_code=401)
        if job_id != 1:
            raise CvatError("backend-secret", status_code=403)
        return (*report_data, {"point_cloud_available": False})

    monkeypatch.setattr("pointsnap.api.create_report", create)
    monkeypatch.setenv("CVAT_TOKEN", "privileged-service-secret")
    server = ReportServer(("127.0.0.1", 0), "http://cvat-server:8080")
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_port}", calls
    server.shutdown()
    server.server_close()
    thread.join(timeout=2)


def test_anonymous_request_never_uses_service_token(api_server):
    url, calls = api_server
    response = requests.get(f"{url}/pointsnap/jobs/1/report", timeout=5)
    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"].startswith("Bearer")
    assert not calls


@pytest.mark.parametrize("token,job_id,status", [("invalid", 1, 401), ("user-token", 2, 403)])
def test_token_and_job_permissions_fail_closed(api_server, token, job_id, status):
    url, calls = api_server
    response = requests.get(f"{url}/pointsnap/jobs/{job_id}/report",
                            headers={"Authorization": f"Bearer {token}"}, timeout=5)
    assert response.status_code == status
    assert calls == [(f"Bearer {token}", job_id)]
    assert "secret" not in response.text


@pytest.mark.parametrize("report_format,mime", [("json", "application/json"),
                                              ("html", "text/html"), ("csv", "text/csv")])
def test_authenticated_formats_and_private_responses(api_server, report_format, mime):
    url, calls = api_server
    response = requests.get(f"{url}/pointsnap/jobs/1/report?format={report_format}",
                            headers={"Authorization": "Bearer user-token"}, timeout=5)
    assert response.status_code == 200
    assert response.headers["Content-Type"].startswith(mime)
    assert response.headers["Cache-Control"] == "private, no-store"
    assert calls == [("Bearer user-token", 1)]
    assert "user-token" not in response.text and "secret" not in response.text
    if report_format == "json":
        result = response.json()
        assert (result["boxes"], result["errors"], result["passed"]) == (1, 1, False)
        assert "/tasks/1/jobs/1?frame=0" in result["findings"][0]["cvat_url"]
        assert "serverID=98" in result["findings"][0]["cvat_url"]
    else:
        assert "bus" in response.text
        assert f"pointsnap-job-1.{report_format}" in response.headers["Content-Disposition"]


def test_invalid_format_and_write_method(api_server):
    url, calls = api_server
    for query in ("format=pdf", "format=json&format=csv", "format="):
        assert requests.get(f"{url}/pointsnap/jobs/1/report?{query}", timeout=5).status_code == 400
    response = requests.post(f"{url}/pointsnap/jobs/1/report", timeout=5)
    assert response.status_code == 405 and response.headers["Allow"] == "GET"
    assert not calls


def test_csv_label_is_not_an_excel_formula(report_data):
    job, findings, config = report_data
    from dataclasses import replace
    findings = [replace(findings[0], label="=1+1")]
    csv = report_bytes(job, findings, config, "csv").decode("utf-8-sig")
    assert "'=1+1" in csv


def test_pagination_cannot_forward_token_to_other_origin():
    client = CvatClient("http://cvat-server:8080", "private-token")
    with pytest.raises(CvatError, match="ngoài origin"):
        client._request("GET", "https://another-server.invalid/api/labels")
    client.session.close()


def test_token_query_is_rejected_and_not_logged(api_server, capsys):
    url, calls = api_server
    response = requests.get(f'{url}/pointsnap/jobs/1/report?token=TEST-SECRET-URL-06', timeout=5)
    assert response.status_code == 400
    assert 'TEST-SECRET-URL-06' not in capsys.readouterr().err
    assert not calls
