"""Actual CVAT/API roundtrips on an isolated temporary task, never an annotator's job."""

import copy
import math
import os

import pytest
from fastapi.testclient import TestClient

import fake_nuscenes
from pointsnap.adapters.cvat.client import CvatClient
from pointsnap.adapters.cvat.repair_sync import same_track
from pointsnap.datasets.nuscenes.to_cvat import export_scene, upload_scene
from pointsnap.adapters.nuscenes import NuScenesReader
from pointsnap.web.projects import ProjectManager
from pointsnap.web.app import create_app

pytestmark = pytest.mark.skipif(os.environ.get("POINTSNAP_LIVE_CVAT") != "1", reason="Requires local CVAT")


def test_live_project_apply_readback_rollback_thirty_cycles(tmp_path):
    cfg = ProjectManager().get_effective_config("cvat-new")
    client = CvatClient(cfg.cvat.url, cfg.cvat.token)
    exported = export_scene(NuScenesReader(fake_nuscenes.build(tmp_path / "dataset")), "scene-0001", tmp_path / "export")
    info = upload_scene(client, exported, "PointSnap repair audit 2026-10-15 (temporary test)", "pointsnap_error")
    try:
        job_id = info["job_ids"][0]
        before = client.get_job_annotations(job_id)
        original = next(t for t in before["tracks"] if len(t["shapes"]) >= 2)
        frame = original["shapes"][0]["frame"]
        track_id = original["id"]
        # Nonzero tilt makes silent resetting of roll/pitch observable.
        tilted = copy.deepcopy(original)
        tilted["shapes"][0]["points"][3:5] = [.12, -.23]
        client.patch_job_annotations(job_id, {"tracks": [tilted]}, action="update")
        original = next(t for t in client.get_job_annotations(job_id)["tracks"] if t["id"] == track_id)
        app = create_app(tmp_path / "web-home")
        app.state.pm.create_project("Live audit", slug="audit", cvat_url=cfg.cvat.url, cvat_token=cfg.cvat.token)
        web = TestClient(app)
        # Resolves the project connection afresh on every apply AND rollback.
        for step in range(30):
            raw = next(t for t in client.get_job_annotations(job_id)["tracks"] if t["id"] == track_id)
            old = next(s for s in raw["shapes"] if s["frame"] == frame)["points"]
            repair = {"repaired_cuboid": {"center": [old[0] + .01 * (step + 1), old[1], old[2] - .2],
                "dims": old[6:9], "yaw": old[5] + math.radians(5)}}
            from pointsnap.adapters.cvat.writer import compute_track_etag
            applied = web.post(f"/api/jobs/{job_id}/tracks/{track_id}/apply-repair", json={
                "slug": "audit", "frame": frame, "repair": repair, "client_track_etag": compute_track_etag(raw)})
            if applied.status_code != 200:
                import json
                history = app.state.history_manager.history_dir(job_id, slug="audit")
                expected = json.loads(next(history.glob("*.json")).read_text(encoding="utf-8"))["post_repair_track"]
                actual = next(t for t in client.get_job_annotations(job_id)["tracks"] if t["id"] == track_id)
                differences = {k: (expected.get(k), actual.get(k)) for k in set(expected) | set(actual)
                               if expected.get(k) != actual.get(k)}
                pytest.fail(applied.text + "\n" + repr(differences))
            data = applied.json()
            assert data["sync_status"] == "verified"
            assert data["new_scan_verdict"] == "NOT_RUN"
            actual = next(t for t in client.get_job_annotations(job_id)["tracks"] if t["id"] == track_id)
            assert same_track(actual, data["updated_track"])
            changed = next(s for s in actual["shapes"] if s["frame"] == frame)["points"]
            assert changed[:3] == pytest.approx(repair["repaired_cuboid"]["center"])
            assert changed[3:5] == pytest.approx([.12, -.23])
            assert changed[5] == pytest.approx(repair["repaired_cuboid"]["yaw"])
            restored = web.post(f"/api/jobs/{job_id}/tracks/{track_id}/rollback", json={
                "slug": "audit", "history_id": data["history_id"]})
            assert restored.status_code == 200, restored.text
            actual = next(t for t in client.get_job_annotations(job_id)["tracks"] if t["id"] == track_id)
            assert same_track(actual, original)
        final = client.get_job_annotations(job_id)
        for other in before["tracks"]:
            if other["id"] != track_id:
                assert same_track(other, next(t for t in final["tracks"] if t["id"] == other["id"]))
    finally:
        client.delete_task(info["task_id"])
        client.session.close()
