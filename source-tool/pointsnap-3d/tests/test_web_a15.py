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
