"""A15: API cho extension PointSnap trên trang CVAT."""

from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from pointsnap.web.app import _same_cvat, create_app


def _write_run(home: Path, slug: str, run_id: str, job_id: int, timestamp: str, findings: list) -> None:
    run_dir = home / "projects" / slug / "runs" / run_id
    run_dir.mkdir(parents=True)
    (run_dir / "summary.json").write_text(json.dumps({"job_id": job_id, "timestamp": timestamp}), encoding="utf-8")
    (run_dir / "findings.json").write_text(json.dumps(findings), encoding="utf-8")


def test_same_cvat_ignores_trailing_slash_and_loopback_name():
    assert _same_cvat("http://localhost:8080/", "http://127.0.0.1:8080")
    assert not _same_cvat("http://localhost:8080", "http://localhost:8081")
    assert not _same_cvat("http://cvat.example.com", "http://localhost")


def test_extension_job_returns_latest_done_run_of_matching_project(tmp_path: Path):
    client = TestClient(create_app(tmp_path))
    client.post("/api/projects", json={"name": "local", "slug": "local", "cvat_url": "http://localhost:8080"})
    client.post("/api/projects", json={"name": "other", "slug": "other", "cvat_url": "http://cvat.example.com"})
    _write_run(tmp_path, "local", "20261008-100000-job2", 2, "2026-10-08T10:00:00+00:00", [{"frame": 1}])
    _write_run(tmp_path, "local", "20261008-110000-job2", 2, "2026-10-08T11:00:00+00:00", [{"frame": 2}, {"frame": 3}])
    _write_run(tmp_path, "local", "20261008-120000-job5", 5, "2026-10-08T12:00:00+00:00", [])
    _write_run(tmp_path, "other", "20261008-130000-job2", 2, "2026-10-08T13:00:00+00:00", [])
    client.put("/api/projects/local/scans/20261008-110000-job2/reviews/1", json={"verdict": "fp"})

    data = client.get("/api/extension/jobs/2", params={"cvat_url": "http://127.0.0.1:8080/"}).json()
    assert data["project"] == {"slug": "local", "name": "local"}
    assert data["run"]["run_id"] == "20261008-110000-job2"
    assert len(data["run"]["findings"]) == 2
    assert data["run"]["reviews"] == {"1": "fp"}
    assert data["active"] is None


def test_extension_job_without_scan_still_names_project(tmp_path: Path):
    client = TestClient(create_app(tmp_path))
    client.post("/api/projects", json={"name": "local", "slug": "local", "cvat_url": "http://localhost:8080"})
    data = client.get("/api/extension/jobs/9", params={"cvat_url": "http://localhost:8080"}).json()
    assert data == {"project": {"slug": "local", "name": "local"}, "run": None, "active": None}
    assert client.get("/api/extension/jobs/9", params={"cvat_url": "http://nowhere:1"}).json()["project"] is None


def test_link_relays_focus_from_web_to_extension(tmp_path: Path):
    """Web gửi lệnh mở mục; extension đang mở job nhận đúng một lần, không nhận lệnh cũ khi vừa mở trang."""
    client = TestClient(create_app(tmp_path))
    old = client.post("/api/extension/focus", json={"job_id": 2, "frame": 3}).json()
    assert old["extension_online"] is False  # chưa có tab CVAT nào hỏi

    first = client.get("/api/extension/poll", params={"job_id": 2}).json()
    assert first["command"] is None and first["seq"] == old["seq"]  # vừa mở trang: bỏ lệnh cũ

    sent = client.post("/api/extension/focus", json={"job_id": 2, "frame": 7, "label": "bus", "message": "m", "bring": True}).json()
    assert sent["extension_online"] is True
    got = client.get("/api/extension/poll", params={"job_id": 2, "after": first["seq"]}).json()
    assert got["command"]["frame"] == 7 and got["command"]["label"] == "bus" and got["command"]["bring"] is True
    again = client.get("/api/extension/poll", params={"job_id": 2, "after": got["seq"]}).json()
    assert again["command"] is None
    assert client.get("/api/extension/poll", params={"job_id": 5, "after": 0}).json()["command"] is None  # job khác


def test_link_goes_offline_and_tracks_review_versions(tmp_path: Path):
    from pointsnap.web.link import ONLINE_SECONDS, ExtensionLink

    now = [100.0]
    link = ExtensionLink(clock=lambda: now[0])
    link.poll(2, -1)
    assert link.status(2)["extension_online"] is True
    now[0] += ONLINE_SECONDS + 0.1
    assert link.status(2)["extension_online"] is False

    client = TestClient(create_app(tmp_path))
    client.post("/api/projects", json={"name": "local", "slug": "local"})
    _write_run(tmp_path, "local", "20261008-100000-job2", 2, "2026-10-08T10:00:00+00:00", [{"frame": 1}])
    url = "/api/projects/local/scans/20261008-100000-job2/reviews"
    rev0 = client.get(url).json()["rev"]
    client.put(f"{url}/0", json={"verdict": "ok"})
    data = client.get(url).json()
    assert data == {"reviews": {"0": "ok"}, "rev": rev0 + 1}
    assert client.get("/api/extension/status", params={"job_id": 2}).json()["reviews_rev"] == rev0 + 1
