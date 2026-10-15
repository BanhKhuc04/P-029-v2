"""Empirical Stress & Concurrency Test Suite for Milestone M3.

Adversarial testing of OCC concurrency, safe updates, and race conditions
in `pointsnap.adapters.cvat.writer` and `pointsnap.web.app`.
"""

from __future__ import annotations

import concurrent.futures
import copy
import math
import uuid
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from pointsnap.adapters.cvat.client import CvatClient, CvatError
from pointsnap.adapters.cvat.writer import (
    OCCConflictError,
    compute_track_etag,
    patch_track_keyframe,
)
from pointsnap.history.manager import HistoryManager, track_dict_to_cuboids
from pointsnap.web.app import create_app


@pytest.fixture
def complex_multiframe_track() -> dict[str, Any]:
    """Tạo track CVAT chuẩn với 5 keyframes, đầy đủ 16 floats points và attributes."""
    shapes = []
    for f in range(5):
        # [px, py, pz, rx, ry, rz, sx, sy, sz, 0, 0, 0, 0, 0, 0, 0]
        pts = [
            10.0 + f * 2.5,
            5.0,
            -0.5,
            0.0,
            0.0,
            0.15,
            4.5,
            2.0,
            1.6,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
        ]
        shapes.append({
            "id": 5000 + f,
            "frame": f,
            "type": "cuboid",
            "occluded": False,
            "outside": False,
            "keyframe": True,
            "points": pts,
            "attributes": [
                {"id": 1, "name": "subtype", "value": "truck"},
                {"id": 2, "name": "pointsnap_error", "value": "[Lỗi] Đáy box lơ lửng" if f == 1 else ""},
            ],
        })
    return {
        "id": 202,
        "label_id": 12,
        "frame": 0,
        "shapes": shapes,
        "attributes": [
            {"id": 99, "name": "priority", "value": "high"}
        ],
    }


# =========================================================================
# Scenario 1: Concurrency & Stale ETag Adversarial Tests
# =========================================================================


def test_concurrent_two_annotators_stale_etag_rejection(tmp_path: Path, complex_multiframe_track: dict[str, Any]):
    """Simulate two annotators loading the same track at revision ETag_0.
    Annotator A applies repair first -> succeeds (200 OK) and changes track ETag.
    Annotator B attempts to apply repair with stale ETag_0 -> strictly rejected with 409 Conflict.
    """
    app = create_app(home_dir=tmp_path)
    job_id = 4
    track_id = 202
    app.state.mock_tracks = {(job_id, track_id): copy.deepcopy(complex_multiframe_track)}
    client = TestClient(app)

    initial_etag = compute_track_etag(complex_multiframe_track)

    # Annotator A modifies frame 1 (repair floating)
    repair_a = {
        "rule": "floating",
        "delta_center": [0.0, 0.0, -0.30],
        "delta_dims": [0.0, 0.0, 0.0],
        "delta_yaw": 0.0,
    }
    resp_a = client.post(
        f"/api/jobs/{job_id}/tracks/{track_id}/apply-repair",
        json={
            "frame": 1,
            "repair": repair_a,
            "client_track_etag": initial_etag,
        },
    )
    assert resp_a.status_code == 200, f"Annotator A failed: {resp_a.text}"
    etag_after_a = compute_track_etag(resp_a.json()["updated_track"])
    assert etag_after_a != initial_etag

    # Annotator B attempts to modify frame 3 presenting the stale initial_etag
    repair_b = {
        "rule": "heading.flip",
        "delta_center": [0.0, 0.0, 0.0],
        "delta_dims": [0.0, 0.0, 0.0],
        "delta_yaw": math.pi,
    }
    resp_b = client.post(
        f"/api/jobs/{job_id}/tracks/{track_id}/apply-repair",
        json={
            "frame": 3,
            "repair": repair_b,
            "client_track_etag": initial_etag,  # Stale ETag!
        },
    )
    assert resp_b.status_code == 409, f"Expected 409 Conflict but got {resp_b.status_code}: {resp_b.text}"
    b_data = resp_b.json()
    assert b_data["status"] == "conflict"
    assert "OCC conflict" in b_data["detail"]

    # Ensure Annotator A's modification remains intact and Annotator B didn't corrupt the track
    stored_track = app.state.mock_tracks[(job_id, track_id)]
    assert stored_track["shapes"][1]["points"][2] == pytest.approx(-0.80, abs=1e-5)
    # Frame 3 yaw should NOT be modified
    assert stored_track["shapes"][3]["points"][5] == pytest.approx(0.15, abs=1e-5)


def test_writer_patch_track_keyframe_occ_stale_rejection(complex_multiframe_track: dict[str, Any]):
    """Low-level writer patch_track_keyframe strictly raises OCCConflictError when client_etag is stale."""
    client_mock = MagicMock(spec=CvatClient)
    client_mock.get_job_annotations.return_value = {
        "tracks": [copy.deepcopy(complex_multiframe_track)]
    }

    def patch(job_id, data, action):
        client_mock.get_job_annotations.return_value = copy.deepcopy(data)
    client_mock.patch_job_annotations.side_effect = patch

    initial_etag = compute_track_etag(complex_multiframe_track)
    stale_etag = "stale_etag_deadbeef"

    new_points = [10.0] * 9 + [0.0] * 7

    # Matching ETag succeeds
    pre, post = patch_track_keyframe(
        client=client_mock,
        job_id=4,
        track_id=202,
        frame=0,
        new_points=new_points,
        client_etag=initial_etag,
    )
    assert post["shapes"][0]["points"] == new_points

    # Stale ETag fails with OCCConflictError
    with pytest.raises(OCCConflictError) as exc_info:
        patch_track_keyframe(
            client=client_mock,
            job_id=4,
            track_id=202,
            frame=0,
            new_points=new_points,
            client_etag=stale_etag,
        )
    assert "OCC conflict" in str(exc_info.value)


def test_simultaneous_concurrent_updates_lost_update_prevention(tmp_path: Path, complex_multiframe_track: dict[str, Any]):
    """Adversarial Stress Test: Parallel simultaneous requests from two annotators
    with the same initial ETag must not produce lost updates.
    Either one request fails with 409 Conflict, or both updates are atomically preserved.
    Currently fails because sync FastAPI handler has no lock, allowing both to succeed and one to be overwritten.
    """
    app = create_app(home_dir=tmp_path)
    job_id = 4
    track_id = 202
    app.state.mock_tracks = {(job_id, track_id): copy.deepcopy(complex_multiframe_track)}
    client = TestClient(app)
    etag0 = compute_track_etag(complex_multiframe_track)

    def apply_update(frame: int, dz: float):
        return client.post(
            f"/api/jobs/{job_id}/tracks/{track_id}/apply-repair",
            json={
                "frame": frame,
                "repair": {"rule": "floating", "delta_center": [0.0, 0.0, dz]},
                "client_track_etag": etag0,
            },
        )

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as ex:
        f1 = ex.submit(apply_update, 0, -0.5)
        f2 = ex.submit(apply_update, 1, -0.8)
        r1 = f1.result()
        r2 = f2.result()

    # If both return 200, both updates MUST be in the track (not lost)
    if r1.status_code == 200 and r2.status_code == 200:
        final_track = app.state.mock_tracks[(job_id, track_id)]
        z0 = final_track["shapes"][0]["points"][2]
        z1 = final_track["shapes"][1]["points"][2]
        # Initial z was -0.5. So z0 should be -1.0 and z1 should be -1.3
        assert z0 == pytest.approx(-1.0, abs=1e-5), f"Lost update on frame 0: z0={z0}"
        assert z1 == pytest.approx(-1.3, abs=1e-5), f"Lost update on frame 1: z1={z1}"
    else:
        # At least one must be 409 Conflict
        statuses = {r1.status_code, r2.status_code}
        assert 409 in statuses, f"Expected 409 Conflict among statuses: {statuses}"


# =========================================================================
# Scenario 2: Partial & Malformed Track Payloads
# =========================================================================


def test_partial_track_payload_nonexistent_frame(tmp_path: Path, complex_multiframe_track: dict[str, Any]):
    """Incoming request targeting a non-existent frame must return 404 without mutating track."""
    app = create_app(home_dir=tmp_path)
    job_id = 4
    track_id = 202
    original_copy = copy.deepcopy(complex_multiframe_track)
    app.state.mock_tracks = {(job_id, track_id): copy.deepcopy(complex_multiframe_track)}
    client = TestClient(app)

    etag = compute_track_etag(complex_multiframe_track)

    resp = client.post(
        f"/api/jobs/{job_id}/tracks/{track_id}/apply-repair",
        json={
            "frame": 999,  # Frame does not exist
            "repair": {"rule": "floating", "delta_center": [0, 0, -0.2]},
            "client_track_etag": etag,
        },
    )
    assert resp.status_code == 404
    assert "Frame 999 not found" in resp.json()["detail"]

    # Verify track in state was not modified or corrupted
    assert app.state.mock_tracks[(job_id, track_id)] == original_copy


def test_partial_track_payload_preserves_all_other_keyframes_and_attributes(
    tmp_path: Path, complex_multiframe_track: dict[str, Any]
):
    """Applying repair to one frame preserves all non-target keyframes, custom attributes, and track tags."""
    app = create_app(home_dir=tmp_path)
    job_id = 4
    track_id = 202
    app.state.mock_tracks = {(job_id, track_id): copy.deepcopy(complex_multiframe_track)}
    client = TestClient(app)

    etag = compute_track_etag(complex_multiframe_track)

    # Repair frame 1
    resp = client.post(
        f"/api/jobs/{job_id}/tracks/{track_id}/apply-repair",
        json={
            "frame": 1,
            "repair": {"rule": "floating", "delta_center": [0.0, 0.0, -0.40]},
            "client_track_etag": etag,
        },
    )
    assert resp.status_code == 200
    updated_track = resp.json()["updated_track"]

    # 1. Number of keyframes preserved
    assert len(updated_track["shapes"]) == 5

    # 2. Keyframes 0, 2, 3, 4 unchanged
    for f in (0, 2, 3, 4):
        assert updated_track["shapes"][f]["points"] == complex_multiframe_track["shapes"][f]["points"]
        assert updated_track["shapes"][f]["attributes"] == complex_multiframe_track["shapes"][f]["attributes"]

    # 3. Track-level attributes preserved
    assert updated_track["attributes"] == complex_multiframe_track["attributes"]
    assert updated_track["label_id"] == complex_multiframe_track["label_id"]

    # 4. Keep finding flags until the scanner confirms clearance.
    f1_attrs = {a["name"]: a["value"] for a in updated_track["shapes"][1]["attributes"]}
    assert f1_attrs["subtype"] == "truck"
    assert f1_attrs["pointsnap_error"] == "[Lỗi] Đáy box lơ lửng"


def test_writer_rejects_malformed_points_dimension(complex_multiframe_track: dict[str, Any]):
    """Low-level patch_track_keyframe strictly rejects points with length != 16."""
    client_mock = MagicMock(spec=CvatClient)
    client_mock.get_job_annotations.return_value = {
        "tracks": [copy.deepcopy(complex_multiframe_track)]
    }

    # Points with only 5 elements instead of 16
    invalid_points_5 = [1.0, 2.0, 3.0, 4.0, 5.0]
    with pytest.raises(ValueError) as exc:
        patch_track_keyframe(
            client=client_mock,
            job_id=4,
            track_id=202,
            frame=0,
            new_points=invalid_points_5,
        )
    assert "phải có đúng 16 số thực" in str(exc.value)

    # Points with 9 elements
    invalid_points_9 = [1.0] * 9
    with pytest.raises(ValueError) as exc:
        patch_track_keyframe(
            client=client_mock,
            job_id=4,
            track_id=202,
            frame=0,
            new_points=invalid_points_9,
        )
    assert "phải có đúng 16 số thực" in str(exc.value)


def test_apply_repair_endpoint_rejects_malformed_points_dimension(
    tmp_path: Path, complex_multiframe_track: dict[str, Any]
):
    """Adversarial Test: Submitting an invalid points array (e.g. 5 floats instead of 16)
    must be rejected with HTTP 400/422 and must NOT corrupt stored track.
    Currently fails because apply_track_repair accepts any length points array without validation.
    """
    app = create_app(home_dir=tmp_path)
    job_id = 4
    track_id = 202
    app.state.mock_tracks = {(job_id, track_id): copy.deepcopy(complex_multiframe_track)}
    client = TestClient(app)
    etag = compute_track_etag(complex_multiframe_track)

    resp = client.post(
        f"/api/jobs/{job_id}/tracks/{track_id}/apply-repair",
        json={
            "frame": 0,
            "repair": {"points": [1.0, 2.0, 3.0, 4.0, 5.0]},
            "client_track_etag": etag,
        },
    )
    # Expected behavior: rejection with 400/422
    assert resp.status_code in (400, 422), f"Expected 400/422 but got {resp.status_code}: {resp.text}"
    # Ensure track in state is not corrupted with 5-number points
    stored_pts = app.state.mock_tracks[(job_id, track_id)]["shapes"][0]["points"]
    assert len(stored_pts) == 16, f"Stored points corrupted: length is {len(stored_pts)}"


# =========================================================================
# Scenario 3: Rapid Sequential Updates & ETag Recomputation
# =========================================================================


def test_rapid_sequential_apply_repair_with_etag_chain(
    tmp_path: Path, complex_multiframe_track: dict[str, Any]
):
    """Perform 20 rapid sequential apply-repair updates chaining ETags.
    Ensures ETag is recomputed each time, no deadlocks occur, and all updates accumulate.
    """
    app = create_app(home_dir=tmp_path)
    job_id = 4
    track_id = 202
    app.state.mock_tracks = {(job_id, track_id): copy.deepcopy(complex_multiframe_track)}
    client = TestClient(app)

    current_etag = compute_track_etag(complex_multiframe_track)
    etags_chain = [current_etag]
    history_ids = []

    for step in range(20):
        target_frame = step % 5
        dz = -0.05 * (step + 1)
        resp = client.post(
            f"/api/jobs/{job_id}/tracks/{track_id}/apply-repair",
            json={
                "frame": target_frame,
                "repair": {"rule": "floating", "delta_center": [0.0, 0.0, dz]},
                "client_track_etag": current_etag,
            },
        )
        assert resp.status_code == 200, f"Step {step} failed: {resp.text}"
        data = resp.json()
        assert data["status"] == "ok"
        assert data["new_scan_verdict"] == "NOT_RUN"

        history_ids.append(data["history_id"])
        new_track = data["updated_track"]
        new_etag = compute_track_etag(new_track)

        # Ensure each step produces a distinct ETag
        assert new_etag not in etags_chain, f"Duplicate ETag detected at step {step}"
        etags_chain.append(new_etag)
        current_etag = new_etag

    # Verify all 20 snapshots were recorded
    snapshots = app.state.history_manager.list_snapshots(job_id=job_id)
    assert len(snapshots) == 20

    # Roll back in reverse order; an older snapshot cannot overwrite newer edits.
    assert client.post(f"/api/jobs/{job_id}/tracks/{track_id}/rollback",
                       json={"history_id": history_ids[0]}).status_code == 409
    for hid in reversed(history_ids):
        rollback_resp = client.post(f"/api/jobs/{job_id}/tracks/{track_id}/rollback", json={"history_id": hid})
        assert rollback_resp.status_code == 200
    restored_track = rollback_resp.json()["restored_track"]
    assert compute_track_etag(restored_track) == compute_track_etag(complex_multiframe_track)


def test_sequential_apply_repair_rejection_of_historical_etags(
    tmp_path: Path, complex_multiframe_track: dict[str, Any]
):
    """Verify that after multiple updates, passing ANY historical (outdated) ETag is strictly rejected."""
    app = create_app(home_dir=tmp_path)
    job_id = 4
    track_id = 202
    app.state.mock_tracks = {(job_id, track_id): copy.deepcopy(complex_multiframe_track)}
    client = TestClient(app)

    etag0 = compute_track_etag(complex_multiframe_track)

    # Step 1
    r1 = client.post(
        f"/api/jobs/{job_id}/tracks/{track_id}/apply-repair",
        json={
            "frame": 0,
            "repair": {"rule": "floating", "delta_center": [0, 0, -0.1]},
            "client_track_etag": etag0,
        },
    )
    etag1 = compute_track_etag(r1.json()["updated_track"])

    # Step 2
    r2 = client.post(
        f"/api/jobs/{job_id}/tracks/{track_id}/apply-repair",
        json={
            "frame": 1,
            "repair": {"rule": "floating", "delta_center": [0, 0, -0.2]},
            "client_track_etag": etag1,
        },
    )
    etag2 = compute_track_etag(r2.json()["updated_track"])

    # Attempt to submit using etag0 (2 revisions stale)
    stale_resp0 = client.post(
        f"/api/jobs/{job_id}/tracks/{track_id}/apply-repair",
        json={
            "frame": 2,
            "repair": {"rule": "floating", "delta_center": [0, 0, -0.3]},
            "client_track_etag": etag0,
        },
    )
    assert stale_resp0.status_code == 409
    assert "OCC conflict" in stale_resp0.json()["detail"]

    # Attempt to submit using etag1 (1 revision stale)
    stale_resp1 = client.post(
        f"/api/jobs/{job_id}/tracks/{track_id}/apply-repair",
        json={
            "frame": 2,
            "repair": {"rule": "floating", "delta_center": [0, 0, -0.3]},
            "client_track_etag": etag1,
        },
    )
    assert stale_resp1.status_code == 409
    assert "OCC conflict" in stale_resp1.json()["detail"]

    # Submitting with current etag2 succeeds
    valid_resp = client.post(
        f"/api/jobs/{job_id}/tracks/{track_id}/apply-repair",
        json={
            "frame": 2,
            "repair": {"rule": "floating", "delta_center": [0, 0, -0.3]},
            "client_track_etag": etag2,
        },
    )
    assert valid_resp.status_code == 200
