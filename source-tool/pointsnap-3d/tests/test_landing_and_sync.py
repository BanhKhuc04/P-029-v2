"""Landing page ở `/`, ứng dụng ở `/app`, và đồng bộ sửa box web ⟷ extension qua `history_rev` (không cần F5)."""

from __future__ import annotations

import copy
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import pointsnap.web.app as web_app
from pointsnap.adapters.cvat.writer import compute_track_etag
from pointsnap.web.app import create_app
from pointsnap.web.link import ExtensionLink


def _track(track_id: int = 101) -> dict:
    shapes = []
    for frame in range(3):
        points = [10.0 + frame, 5.0, -0.5, 0.0, 0.0, 0.1, 4.5, 2.0, 1.6] + [0.0] * 7
        shapes.append({"id": 1000 + frame, "frame": frame, "type": "cuboid", "occluded": False, "outside": False,
                       "keyframe": True, "points": points, "attributes": []})
    return {"id": track_id, "label_id": 10, "frame": 0, "shapes": shapes, "attributes": []}


@pytest.fixture
def client(tmp_path: Path) -> TestClient:
    return TestClient(create_app(tmp_path))


# --- Landing và ứng dụng ---------------------------------------------------------------------------------------

def test_root_serves_team_landing_and_app_moves_to_app(client: TestClient):
    landing = client.get("/")
    assert landing.status_code == 200 and landing.headers["cache-control"] == "no-cache"
    if web_app.LANDING_DIR.joinpath("index.html").is_file():
        assert 'data-app-link' in landing.text and 'href="/app"' in landing.text
        assert "Tải miễn phí" not in landing.text and 'id="tai-ve"' not in landing.text
    app = client.get("/app")
    assert app.status_code == 200 and app.headers["cache-control"] == "no-cache"
    assert 'id="results-content-box"' in app.text and "/static/app.js" in app.text


def test_landing_works_offline_without_cdn(client: TestClient):
    html = client.get("/").text
    for host in ("fonts.googleapis.com", "fonts.gstatic.com", "cdn.jsdelivr.net", "unpkg.com"):
        assert host not in html
    assert "/static/fonts/fonts.css" in html


@pytest.mark.skipif(not web_app.LANDING_DIR.joinpath("index.html").is_file(), reason="không có thư mục landing/")
@pytest.mark.parametrize("path,kind", [
    ("/main.js", "text/javascript"), ("/scenes.js", "text/javascript"), ("/styles.css", "text/css"),
    ("/vendor/three/three.module.min.js", "text/javascript"),
    ("/vendor/three/addons/controls/OrbitControls.js", "text/javascript"), ("/assets/favicon.svg", "image/svg+xml"),
])
def test_landing_assets_have_module_safe_mime_types(client: TestClient, path: str, kind: str):
    res = client.get(path)
    assert res.status_code == 200
    assert res.headers["content-type"].split(";")[0] == kind


def test_landing_falls_back_to_builtin_page_without_team_folder(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(web_app, "LANDING_DIR", tmp_path / "khong-co")
    client = TestClient(create_app(tmp_path / "home"))
    res = client.get("/")
    assert res.status_code == 200 and "PointSnap 3D" in res.text and 'href="/app"' in res.text
    assert client.get("/main.js").status_code == 404


def test_landing_route_does_not_shadow_api_or_static(client: TestClient):
    assert client.get("/api/projects").json() == []
    assert client.get("/static/app.js").status_code == 200


# --- history_rev ------------------------------------------------------------------------------------------------

def test_link_history_event_is_per_job_and_monotonic():
    link = ExtensionLink()
    assert link.status(4)["history_rev"] == 0 and link.status(4)["history_event"] is None
    rev = link.bump_history(4, {"action": "apply", "track_id": 101, "frame": 2, "history_id": "h1"}, scope="s")
    assert rev == 1 == link.history_rev
    status = link.status(4, scope="s")
    assert status["history_rev"] == 1 and status["history_event"]["history_id"] == "h1"
    assert status["history_event"]["rev"] == 1 and status["history_event"]["job_id"] == 4
    assert link.status(5, scope="s")["history_event"] is None
    assert link.status(4, scope="khac")["history_event"] is None
    poll = link.poll(4, -1, scope="s")
    assert poll["history_rev"] == 1 and poll["history_event"]["action"] == "apply"


def test_apply_and_rollback_bump_history_rev_seen_by_status_and_poll(client: TestClient):
    track = _track()
    client.app.state.mock_tracks = {(4, 101): copy.deepcopy(track)}
    rev0 = client.get("/api/extension/status", params={"job_id": 4}).json()["history_rev"]

    applied = client.post("/api/jobs/4/tracks/101/apply-repair", json={
        "frame": 2, "client_track_etag": compute_track_etag(track),
        "repair": {"rule": "floating", "delta_center": [0.0, 0.0, -0.3], "delta_dims": [0, 0, 0], "delta_yaw": 0.0},
    })
    assert applied.status_code == 200
    body = applied.json()
    assert body["history_rev"] == rev0 + 1

    status = client.get("/api/extension/status", params={"job_id": 4}).json()
    assert status["history_rev"] == rev0 + 1
    event = status["history_event"]
    assert event["action"] == "apply" and event["track_id"] == 101 and event["frame"] == 2
    assert event["history_id"] == body["history_id"] and event["rev"] == rev0 + 1
    polled = client.get("/api/extension/poll", params={"job_id": 4, "after": -1}).json()
    assert polled["history_rev"] == rev0 + 1 and polled["history_event"]["history_id"] == body["history_id"]

    rolled = client.post("/api/jobs/4/tracks/101/rollback", json={"history_id": body["history_id"]})
    assert rolled.status_code == 200 and rolled.json()["history_rev"] == rev0 + 2
    event = client.get("/api/extension/status", params={"job_id": 4}).json()["history_event"]
    assert event["action"] == "rollback" and event["history_id"] == body["history_id"]


def test_failed_apply_does_not_bump_history_rev(client: TestClient):
    track = _track()
    client.app.state.mock_tracks = {(4, 101): copy.deepcopy(track)}
    res = client.post("/api/jobs/4/tracks/101/apply-repair", json={
        "frame": 2, "client_track_etag": "cu", "repair": {"rule": "floating", "delta_center": [0, 0, -0.2]},
    })
    assert res.status_code == 409
    assert client.get("/api/extension/status", params={"job_id": 4}).json()["history_rev"] == 0
