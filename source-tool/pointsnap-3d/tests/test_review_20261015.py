"""Hồi quy các phát hiện trong review ngày 15/10/2026."""
import copy
import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
from fastapi.testclient import TestClient

from pointsnap.core.model import Cuboid
from pointsnap.core.repair import compute_box_repair
from pointsnap.core.ghost import generate_ghost_target, compute_spatial_residuals
from pointsnap.history.manager import HistoryManager
from pointsnap.web.app import create_app
from pointsnap.web.projects import ProjectManager
from pointsnap.web.runner import ScanRunner
from test_repair_sync_heading_memory import Store


def box(frame=0):
    return Cuboid(center=(0., 0., 2.), dims=(4., 2., 2.), yaw=0., label="car", frame=frame, track_id=7)


@pytest.mark.parametrize("branch", ["summary", "disk", "memory"])
def test_p1_1_original_indices_across_run_branches(tmp_path, branch):
    pm = ProjectManager(tmp_path)
    pm.create_project(name="p", slug="p")
    runner = ScanRunner(pm)
    rid = "20261015-100000-job1"
    rd = pm._project_dir("p") / "runs" / rid
    rd.mkdir(parents=True)
    raw = [{"rule": r, "frame": i} for i, r in enumerate(["floating", "track.jump", "fit.loose"])]
    (rd / "findings.json").write_text(json.dumps(raw), encoding="utf-8")
    (rd / "summary.json").write_text('{"job_id":1}', encoding="utf-8")
    for name in ["snapshot.json", "report.html", "report.csv"]:
        (rd / name).write_text("{}", encoding="utf-8")
    state = dict(project_slug="p", run_id=rid, status="done", job_id=1)
    if branch == "disk":
        (rd / "run.json").write_text(json.dumps(state), encoding="utf-8")
    if branch == "memory":
        runner._scans[rid] = state
    findings = runner.get_run("p", rid, include_findings=True)["findings"]
    assert [f["index"] for f in findings] == [0, 2]
    client = TestClient(create_app(tmp_path))
    assert client.put(f"/api/projects/p/scans/{rid}/reviews/2", json={"verdict": "fp"}).status_code == 200
    assert client.put(f"/api/projects/p/scans/{rid}/reviews/1", json={"verdict": "fp"}).status_code == 404
    from pointsnap.learn import collect_reviews
    samples = collect_reviews(pm._project_dir("p"))
    assert [(s.rule, s.verdict) for s in samples] == [("fit.loose", "fp")]


@pytest.mark.parametrize("endpoint,payload", [("apply-repair", {"frame": 1, "repair": {"delta_center": [0, 0, -.2]}}),
                                               ("rollback", {"history_id": "missing"})])
def test_p1_3_write_requires_project(tmp_path, endpoint, payload):
    app = create_app(tmp_path)
    store = Store()
    app.state.cvat_client = store
    response = TestClient(app).post(f"/api/jobs/1/tracks/7/{endpoint}", json=payload)
    assert response.status_code == 400
    assert store.writes == 0


@pytest.mark.parametrize("mode", ["fail", "ignore", "conflict"])
def test_p1_4_failed_write_has_no_history(tmp_path, mode):
    app = create_app(tmp_path)
    ProjectManager(tmp_path).create_project(name="p", slug="p")
    store = Store()
    setattr(store, mode, True)
    if mode == "conflict":
        read = store.get_job_annotations
        reads = []
        def annotations(job):
            result = read(job)
            reads.append(job)
            if len(reads) > 1:
                result["tracks"][0]["shapes"][0]["points"][0] += 1
            return result
        store.get_job_annotations = annotations
    app.state.cvat_client = store
    response = TestClient(app).post("/api/jobs/1/tracks/7/apply-repair",
        json={"slug": "p", "frame": 1, "repair": {"delta_center": [0, 0, -.2]}})
    assert response.status_code == (409 if mode == "conflict" else 502)
    assert HistoryManager(home_dir=tmp_path).list_snapshots(job_id=1, slug="p") == []


def test_p2_1_never_measure_peer_with_current_cloud(monkeypatch):
    calls = []
    def ground(points, cuboid):
        calls.append(cuboid.frame)
        return SimpleNamespace(is_valid=True, num_ground_points=30, contact_distance=.5,
                               distance=.5, ground_z=.5)
    monkeypatch.setattr("pointsnap.core.repair.ring_ground_for_box", ground)
    monkeypatch.setattr("pointsnap.core.ghost.ring_ground_for_box", ground)
    track = [box(i) for i in range(3)]
    pts = np.zeros((30, 3))
    repair = compute_box_repair(track[0], track, pts, "floating")
    ghost = generate_ghost_target(track[0], track, pts, "floating")
    assert calls == [0, 0]
    assert repair.delta_center[2] == pytest.approx(-.5)
    assert ghost.target_bottom_z == pytest.approx(.5)


def test_p2_2_stale_ground_and_sparse_cluster_have_low_confidence():
    assert compute_box_repair(box(), [], None, "floating", {"distance": .5}).confidence < .5
    pts = np.array([[i * .1, 0, 2] for i in range(5)])
    assert generate_ghost_target(box(), [], pts, "fit.outside").confidence < .5
    outside = generate_ghost_target(box(), [], pts, "fit.outside")
    loose = generate_ghost_target(box(), [], pts, "fit.loose", {"face": "đầu"})
    assert outside.confidence == pytest.approx(.92 * 5 / 30)
    assert loose.confidence == pytest.approx(.88 * 5 / 30)


def test_p2_3_public_routes_have_no_internal_parameters(tmp_path):
    schema = TestClient(create_app(tmp_path)).get("/openapi.json").json()
    for endpoint in ["repair", "ghost-target"]:
        route = schema["paths"][f"/api/jobs/{{job_id}}/tracks/{{track_id}}/{endpoint}"]["get"]
        assert "requestBody" not in route
        assert {p["name"] for p in route["parameters"]} == {"job_id", "track_id", "frame", "rule", "slug"}


@pytest.mark.parametrize("rule", ["heading.flip", "heading.motion", "heading.static", "heading.points"])
def test_p2_4_no_cross_frame_sensor_heading_fallback(rule):
    target = box().replace(yaw=1.)
    track = [target, box(1), box(2)]
    details = {"track_heading_deg": 180.}
    repair = compute_box_repair(target, track, None, rule, details)
    ghost = generate_ghost_target(target, track, None, rule, details)
    assert repair.delta_yaw == 0 and repair.confidence == 0
    assert ghost.yaw == target.yaw and ghost.confidence == 0


def test_p2_5_history_filters_track(tmp_path):
    mgr = HistoryManager(home_dir=tmp_path)
    for tid in [7, 8]:
        mgr.save_snapshot(1, tid, 0, {}, {}, {}, slug="p")
    assert [s["track_id"] for s in mgr.list_snapshots(job_id=1, slug="p", track_id=7)] == [7]


def test_p2_6_history_cannot_escape_configured_home(tmp_path, monkeypatch):
    other = tmp_path / "real"
    monkeypatch.setattr(Path, "home", lambda: other)
    real = HistoryManager(home_dir=other / ".pointsnap")
    hid = real.save_snapshot(1, 7, 0, {}, {}, {}, slug="p")
    mgr = HistoryManager(home_dir=tmp_path / "isolated")
    with pytest.raises(FileNotFoundError):
        mgr.get_snapshot(1, hid, slug="p")
    directory = mgr.history_dir(1, slug="p")
    (directory / f"prefix-{hid}.json").write_text(json.dumps(real.get_snapshot(1, hid, slug="p")), encoding="utf-8")
    with pytest.raises(FileNotFoundError):
        mgr.get_snapshot(1, hid, slug="p")


def test_p2_7_poll_does_not_reopen_runs_on_each_request(tmp_path, monkeypatch):
    client = TestClient(create_app(tmp_path))
    client.post("/api/projects", json={"name": "p", "slug": "p"})
    calls = []
    original = ScanRunner.list_runs
    def listing(self, slug):
        calls.append(slug)
        return original(self, slug)
    monkeypatch.setattr(ScanRunner, "list_runs", listing)
    client.get("/api/extension/poll?job_id=1")
    calls.clear()
    client.get("/api/extension/poll?job_id=1")
    assert calls == []


def test_p2_8_yaw_alone_is_not_snapped():
    target = generate_ghost_target(box())
    residuals = compute_spatial_residuals(box().replace(center=(4., 0., 2.)), target)
    assert not residuals.is_snapped


@pytest.mark.parametrize("endpoint,method", [("repair", "get"), ("apply-repair", "post")])
def test_p3_1_unknown_finding_project_is_404(tmp_path, endpoint, method):
    client = TestClient(create_app(tmp_path))
    url = f"/api/projects/missing/scans/20261015-100000-job1/findings/0/{endpoint}"
    kwargs = {"json": {"frame": 0, "repair": {}}} if method == "post" else {}
    assert getattr(client, method)(url, **kwargs).status_code == 404


def test_p3_2_request_closes_owned_client_on_early_return(tmp_path, monkeypatch):
    from unittest.mock import MagicMock
    app = create_app(tmp_path)
    app.state.pm.create_project(name="p", slug="p", cvat_token="test-only")
    cvat = MagicMock()
    cvat.get_job_annotations.return_value = {"tracks": []}
    monkeypatch.setattr("pointsnap.web.app.CvatClient", lambda *a, **kw: cvat)
    response = TestClient(app).get("/api/jobs/1/tracks/7/repair?frame=0&slug=p")
    assert response.status_code == 404
    cvat.session.close.assert_called_once()


def test_p3_7_only_configured_extension_may_write(tmp_path, monkeypatch):
    monkeypatch.setenv("POINTSNAP_EXTENSION_IDS", "a" * 32)
    client = TestClient(create_app(tmp_path))
    for extension_id, status in [("a" * 32, 201), ("b" * 32, 403)]:
        response = client.post("/api/projects", json={"name": extension_id, "slug": extension_id},
            headers={"Origin": f"chrome-extension://{extension_id}"})
        assert response.status_code == status


def test_p3_7_unconfigured_extension_ids_keep_extension_writes(tmp_path, monkeypatch):
    monkeypatch.delenv("POINTSNAP_EXTENSION_IDS", raising=False)
    client = TestClient(create_app(tmp_path))
    response = client.post("/api/projects", json={"name": "c" * 32, "slug": "c" * 32},
        headers={"Origin": f"chrome-extension://{'c' * 32}"})
    assert response.status_code == 201


def test_p3_3_legacy_writer_verifies_and_rejects_stale_rollback():
    from pointsnap.adapters.cvat.writer import patch_track_keyframe, rollback_track_annotation, OCCConflictError
    store = Store()
    points = list(store.track["shapes"][1]["points"])
    points[2] -= .2
    before, after = patch_track_keyframe(store, 1, 7, 1, points)
    assert after == store.track
    store.track["shapes"][0]["points"][0] += 1
    with pytest.raises(OCCConflictError):
        rollback_track_annotation(store, 1, before, after)
    assert store.writes == 1


def test_p1_1_finding_repair_uses_original_index_for_frame_and_preview(tmp_path, monkeypatch):
    app = create_app(tmp_path)
    app.state.pm.create_project(name="p", slug="p")
    store = Store()
    app.state.mock_tracks = {(1, 7): copy.deepcopy(store.track)}
    rid = "20261015-100000-job1"
    rd = tmp_path / "projects/p/runs" / rid
    rd.mkdir(parents=True)
    (rd / "summary.json").write_text('{"job_id":1}', encoding="utf-8")
    findings = [{"rule": rule, "frame": frame, "track_id": 7, "details": {"distance": .2}}
                for rule, frame in [("floating", 0), ("track.jump", 1), ("floating", 2)]]
    (rd / "findings.json").write_text(json.dumps(findings), encoding="utf-8")
    seen = []
    def finding_box(run_dir, project, index):
        seen.append(index)
        return {}, box(2), SimpleNamespace(frame_data=lambda f: SimpleNamespace(points=None))
    monkeypatch.setattr("pointsnap.web.app._finding_box", finding_box)
    client = TestClient(app)
    response = client.get(f"/api/projects/p/scans/{rid}/findings/2/repair")
    assert response.status_code == 200
    assert response.json()["frame"] == 2
    assert seen == [2]


@pytest.mark.parametrize("rule", ["heading.flip", "heading.motion", "heading.static"])
@pytest.mark.parametrize("num_points", [None, 4, 30])
def test_ghost_sensor_heading_confidence_is_independent_of_lidar(rule, num_points):
    target = box().replace(yaw=1.)
    points = None if num_points is None else np.zeros((num_points, 3)) + [0, 0, 2]
    details = {"target_yaw_sensor": .25}
    repair = compute_box_repair(target, [target], points, rule, details)
    ghost = generate_ghost_target(target, [target], points, rule, details)
    assert ghost.yaw == pytest.approx(repair.repaired_cuboid.yaw)
    assert ghost.confidence == pytest.approx(repair.confidence) == .92
    assert "thiếu hướng chuẩn" not in ghost.reason
    if num_points is None or num_points < 5:
        assert "LiDAR" in ghost.reason


@pytest.mark.parametrize("rule", ["heading.flip", "heading.motion", "heading.static"])
def test_ghost_missing_sensor_heading_is_unavailable(rule):
    ghost = generate_ghost_target(box().replace(yaw=1.), points=None, rule=rule)
    assert ghost.confidence == 0
    assert ghost.yaw == 1.
    assert "thiếu hướng chuẩn" in ghost.reason


def test_extension_poll_uses_started_at_instead_of_random_run_suffix(tmp_path):
    app = create_app(tmp_path)
    for slug, suffix, fraction in [("older", "900000000000", "100000"), ("newer", "100000000000", "900000")]:
        app.state.pm.create_project(name=slug, slug=slug)
        rid = f"20261015-100000-{suffix}-job1"
        rd = tmp_path / "projects" / slug / "runs" / rid
        rd.mkdir(parents=True)
        stamp = f"2026-10-15T10:00:00.{fraction}+00:00"
        state = dict(run_id=rid, project_slug=slug, job_id=1, status="done", started_at=stamp, finished_at=stamp)
        files = {"run.json": state, "summary.json": {"job_id": 1, "cvat_url": "http://localhost:8080"},
                 "findings.json": [], "snapshot.json": {}}
        for name, value in files.items():
            (rd / name).write_text(json.dumps(value), encoding="utf-8")
        for name in ["report.html", "report.csv"]:
            (rd / name).write_text("ok", encoding="utf-8")
    client = TestClient(app)
    expected = "20261015-100000-100000000000-job1"
    for _ in range(2):  # Also exercise the cached latest run.
        poll = client.get("/api/extension/poll?job_id=1&cvat_url=http://localhost:8080")
        jobs = client.get("/api/extension/jobs/1?cvat_url=http://localhost:8080")
        assert poll.status_code == jobs.status_code == 200
        assert poll.json()["latest_run_id"] == jobs.json()["run"]["run_id"] == expected

