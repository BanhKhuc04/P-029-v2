import json

import pytest
import requests

from pointsnap.adapters.cvat.client import CvatClient, CvatError


class FakeResponse:
    def __init__(self, status, payload=None):
        self.status_code = status
        self._payload = payload
        self.content = b"" if payload is None else json.dumps(payload).encode()
        self.text = self.content.decode()

    def json(self):
        return self._payload


class FakeSession:
    """Thay requests.Session: trả lời theo bảng (method, đường dẫn) và ghi lại các lần gọi."""

    def __init__(self, routes):
        self.routes = {k: list(v) if isinstance(v, list) else [v] for k, v in routes.items()}
        self.headers = {}
        self.calls = []

    def request(self, method, url, timeout=None, **kwargs):
        path = url.split("/api/", 1)[-1] if "/api/" in url else url
        self.calls.append((method, path, kwargs))
        replies = self.routes.get((method, path.split("?")[0]))
        if not replies:
            raise AssertionError(f"Không có route giả cho {method} {path}")
        return replies.pop(0) if len(replies) > 1 else replies[0]


def client(routes):
    return CvatClient("http://cvat.local:8080/", "secret", session=FakeSession(routes))


def test_requires_token():
    with pytest.raises(CvatError, match="CVAT_TOKEN"):
        CvatClient("http://x", None)


def test_sets_auth_header_and_base_url():
    c = client({})
    assert c.url == "http://cvat.local:8080"
    assert c.session.headers["Authorization"] == "Bearer secret"
    assert c.session.headers["Accept"].startswith("application/vnd.cvat+json")  # application/json → HTTP 406
    legacy = CvatClient("http://x", "abc", auth_scheme="Token", session=FakeSession({}))
    assert legacy.session.headers["Authorization"] == "Token abc"


def test_create_task_posts_name_and_labels():
    c = client({("POST", "tasks"): FakeResponse(201, {"id": 42})})
    assert c.create_task("demo", [{"name": "car"}]) == {"id": 42}
    method, path, kwargs = c.session.calls[0]
    assert kwargs["json"] == {"name": "demo", "labels": [{"name": "car"}]}


def test_upload_task_data_sends_zip_and_returns_rq_id(tmp_path):
    archive = tmp_path / "scene.zip"
    archive.write_bytes(b"PK")
    c = client({("POST", "tasks/42/data"): FakeResponse(202, {"rq_id": "create:task-42"})})
    assert c.upload_task_data(42, archive) == "create:task-42"
    kwargs = c.session.calls[0][2]
    assert kwargs["data"]["sorting_method"] == "lexicographical"
    assert kwargs["files"]["client_files[0]"][0] == "scene.zip"


def test_wait_request_polls_until_finished():
    c = client({("GET", "requests/r1"): [FakeResponse(200, {"status": "queued"}),
                                         FakeResponse(200, {"status": "started"}),
                                         FakeResponse(200, {"status": "finished"})]})
    assert c.wait_request("r1", poll_interval=0)["status"] == "finished"
    assert len(c.session.calls) == 3


def test_wait_request_reports_failure_and_timeout():
    failed = client({("GET", "requests/r2"): FakeResponse(200, {"status": "failed", "message": "bad pcd"})})
    with pytest.raises(CvatError, match="bad pcd"):
        failed.wait_request("r2", poll_interval=0)
    stuck = client({("GET", "requests/r3"): FakeResponse(200, {"status": "started"})})
    with pytest.raises(CvatError, match="chưa xong"):
        stuck.wait_request("r3", timeout=0, poll_interval=0)


def test_list_endpoints_follow_pagination():
    page2 = "http://cvat.local:8080/api/labels?page=2"
    c = client({
        ("GET", "labels"): [FakeResponse(200, {"results": [{"id": 1}], "next": page2}),
                            FakeResponse(200, {"results": [{"id": 2}], "next": None})],
    })
    assert [label["id"] for label in c.task_labels(42)] == [1, 2]
    assert c.session.calls[0][2]["params"] == {"task_id": 42, "page_size": 500}


def test_http_errors_and_connection_errors_become_cvat_error():
    c = client({("PUT", "tasks/1/annotations"): FakeResponse(400, {"detail": "label_id is wrong"})})
    with pytest.raises(CvatError, match="HTTP 400.*label_id"):
        c.put_task_annotations(1, {})

    class Offline(FakeSession):
        def request(self, *args, **kwargs):
            raise requests.ConnectionError("refused")

    offline = CvatClient("http://localhost:8080", "t", session=Offline({}))
    with pytest.raises(CvatError, match="Không kết nối được"):
        offline.server_version()


def test_patch_job_annotations():
    c = client({("PATCH", "jobs/7/annotations"): FakeResponse(200, {"shapes": [], "tracks": []})})
    payload = {"shapes": [{"id": 1, "attributes": [{"spec_id": 10, "value": "err"}]}]}
    res = c.patch_job_annotations(7, payload, action="update")
    assert res == {"shapes": [], "tracks": []}
    method, path, kwargs = c.session.calls[0]
    assert method == "PATCH"
    assert "jobs/7/annotations" in path
    assert kwargs["params"] == {"action": "update"}
    assert kwargs["json"] == payload
