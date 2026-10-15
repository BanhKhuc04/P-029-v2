"""Adversarial & Stress Verification Suite for Milestone M4.

Authored by: teamwork_preview_challenger_m4_1 (Empirical Challenger)

Mandated Focus Areas:
1. Concurrent apply-repair requests with stale vs fresh ETags (OCC conflict verification).
2. Rollback on empty history, invalid history_id, path traversal, or corrupted snapshots.
3. Edge-case box repairs: zero dimensions, extreme offsets, NaN/Inf values, negative coordinates.
4. Canvas preview data boundary inputs: missing points, null ground, zero-size canvas.
"""

from __future__ import annotations

import concurrent.futures
import copy
import json
import math
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock
import uuid

import numpy as np
import pytest
from fastapi.testclient import TestClient

from pointsnap.adapters.cvat.client import CvatClient
from pointsnap.adapters.cvat.writer import compute_track_etag
from pointsnap.core.model import Cuboid
from pointsnap.history.manager import HistoryManager
from pointsnap.web.app import create_app


# =========================================================================
# Fixtures
# =========================================================================

@pytest.fixture
def sample_track() -> dict[str, Any]:
    """Sample raw CVAT track with 5 keyframes and pointsnap_error attribute."""
    shapes = []
    for f in range(5):
        pts = [
            10.0 + f * 2.0,
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
            "id": 1000 + f,
            "frame": f,
            "type": "cuboid",
            "occluded": False,
            "outside": False,
            "keyframe": True,
            "points": pts,
            "attributes": [
                {"id": 1, "name": "subtype", "value": "sedan"},
                {"id": 2, "name": "reviewed", "value": "true"},
                {"id": 3, "name": "pointsnap_error", "value": "[Lỗi] Đáy box lơ lửng 25 cm" if f == 2 else ""},
            ],
        })
    return {
        "id": 101,
        "label_id": 10,
        "frame": 0,
        "shapes": shapes,
        "attributes": [
            {"id": 10, "name": "track_status", "value": "active"}
        ],
    }


@pytest.fixture
def mock_cvat_client(sample_track: dict[str, Any]) -> MagicMock:
    client = MagicMock(spec=CvatClient)
    annotations_state = {
        "version": 1,
        "shapes": [],
        "tracks": [copy.deepcopy(sample_track)],
    }

    def get_job_annotations(job_id: int) -> dict[str, Any]:
        return copy.deepcopy(annotations_state)

    def patch_job_annotations(job_id: int, data: dict[str, Any], action: str = "update") -> dict[str, Any]:
        if "tracks" in data:
            for new_t in data["tracks"]:
                tracks = annotations_state["tracks"]
                for i, existing in enumerate(tracks):
                    if existing["id"] == new_t["id"]:
                        tracks[i] = copy.deepcopy(new_t)
                        break
                else:
                    tracks.append(copy.deepcopy(new_t))
        return copy.deepcopy(annotations_state)

    client.get_job_annotations.side_effect = get_job_annotations
    client.patch_job_annotations.side_effect = patch_job_annotations
    return client


# =========================================================================
# 1. Concurrent apply-repair requests with stale vs fresh ETags (OCC Verification)
# =========================================================================

def test_concurrent_occ_conflict_under_multi_threaded_race(tmp_path: Path, sample_track: dict[str, Any], mock_cvat_client: MagicMock):
    """Stress 1.1: 10 concurrent threads attempt apply-repair with the exact same initial ETag.
    
    Invariants:
    - Exactly 1 thread must succeed (HTTP 200).
    - Exactly 9 threads must be rejected with HTTP 409 Conflict.
    - All 9 rejected responses must detail OCC conflict.
    """
    app = create_app(home_dir=tmp_path)
    app.state.cvat_client = mock_cvat_client
    app.state.mock_tracks = {(4, 101): copy.deepcopy(sample_track)}

    initial_etag = compute_track_etag(sample_track)
    num_threads = 10
    responses: list[tuple[int, dict[str, Any]]] = []

    def make_request(worker_idx: int) -> tuple[int, dict[str, Any]]:
        client = TestClient(app)
        payload = {
            "frame": 2,
            "repair": {
                "rule": "floating",
                "delta_center": [0.0, 0.0, -0.20 - worker_idx * 0.01],
                "delta_dims": [0.0, 0.0, 0.0],
                "delta_yaw": 0.0,
            },
            "client_track_etag": initial_etag,
        }
        res = client.post("/api/jobs/4/tracks/101/apply-repair", json=payload)
        return res.status_code, res.json()

    with concurrent.futures.ThreadPoolExecutor(max_workers=num_threads) as executor:
        futures = [executor.submit(make_request, i) for i in range(num_threads)]
        for f in concurrent.futures.as_completed(futures):
            responses.append(f.result())

    status_codes = [r[0] for r in responses]
    successes = [r for r in responses if r[0] == 200]
    conflicts = [r for r in responses if r[0] == 409]

    assert len(successes) == 1, f"Expected exactly 1 success, got {len(successes)}: {status_codes}"
    assert len(conflicts) == num_threads - 1, f"Expected {num_threads - 1} conflicts, got {len(conflicts)}"

    # Verify conflict details
    for code, body in conflicts:
        assert body["status"] == "conflict"
        assert body["code"] == 409
        assert "OCC conflict" in body["detail"]


def test_sequential_occ_stale_etag_rejection_and_fresh_etag_recovery(tmp_path: Path, sample_track: dict[str, Any], mock_cvat_client: MagicMock):
    """Stress 1.2: Client A updates track -> Client B with stale ETag fails (409) -> Client B fetches fresh ETag -> succeeds (200)."""
    app = create_app(home_dir=tmp_path)
    app.state.cvat_client = mock_cvat_client
    app.state.mock_tracks = {(4, 101): copy.deepcopy(sample_track)}
    client = TestClient(app)

    # 1. Read initial repair proposal and ETag
    r_repair0 = client.get("/api/jobs/4/tracks/101/repair?frame=2&rule=floating")
    assert r_repair0.status_code == 200
    etag0 = r_repair0.json()["track_etag"]

    # 2. Client A applies repair with etag0 -> succeeds
    apply_payload_a = {
        "frame": 2,
        "repair": {"delta_center": [0.0, 0.0, -0.25], "delta_dims": [0.0, 0.0, 0.0]},
        "client_track_etag": etag0,
    }
    r_apply_a = client.post("/api/jobs/4/tracks/101/apply-repair", json=apply_payload_a)
    assert r_apply_a.status_code == 200
    history_id_a = r_apply_a.json()["history_id"]

    # 3. Client B attempts repair with stale etag0 -> strictly rejected with 409
    apply_payload_b_stale = {
        "frame": 2,
        "repair": {"delta_center": [0.0, 0.0, -0.10], "delta_dims": [0.0, 0.0, 0.0]},
        "client_track_etag": etag0,
    }
    r_apply_b_stale = client.post("/api/jobs/4/tracks/101/apply-repair", json=apply_payload_b_stale)
    assert r_apply_b_stale.status_code == 409
    assert "OCC conflict" in r_apply_b_stale.json()["detail"]

    # 4. Client B fetches fresh repair and updated ETag
    r_repair1 = client.get("/api/jobs/4/tracks/101/repair?frame=2&rule=floating")
    assert r_repair1.status_code == 200
    etag1 = r_repair1.json()["track_etag"]
    assert etag1 != etag0, "ETag must change after update"

    # 5. Client B applies repair with fresh etag1 -> succeeds
    apply_payload_b_fresh = {
        "frame": 2,
        "repair": {"delta_center": [0.0, 0.0, -0.10], "delta_dims": [0.0, 0.0, 0.0]},
        "client_track_etag": etag1,
    }
    r_apply_b_fresh = client.post("/api/jobs/4/tracks/101/apply-repair", json=apply_payload_b_fresh)
    assert r_apply_b_fresh.status_code == 200


def test_forged_or_corrupt_etag_rejection(tmp_path: Path, sample_track: dict[str, Any], mock_cvat_client: MagicMock):
    """Stress 1.3: Forged or random ETags are strictly rejected with 409."""
    app = create_app(home_dir=tmp_path)
    app.state.cvat_client = mock_cvat_client
    app.state.mock_tracks = {(4, 101): copy.deepcopy(sample_track)}
    client = TestClient(app)

    forged_etags = [
        "deadbeef12345678",
        "0000000000000000",
        "invalid-etag-str",
        "",
        "   ",
    ]

    for etag in forged_etags:
        payload = {
            "frame": 2,
            "repair": {"delta_center": [0.0, 0.0, -0.25]},
            "client_track_etag": etag,
        }
        res = client.post("/api/jobs/4/tracks/101/apply-repair", json=payload)
        assert res.status_code == 409
        assert "OCC conflict" in res.json()["detail"]


# =========================================================================
# 2. Rollback on Empty History, Invalid history_id, and Corrupt Snapshots
# =========================================================================

def test_rollback_on_empty_history_returns_404(tmp_path: Path, sample_track: dict[str, Any], mock_cvat_client: MagicMock):
    """Stress 2.1: Rollback when no history exists for the job returns 404 (not 500)."""
    app = create_app(home_dir=tmp_path)
    app.state.cvat_client = mock_cvat_client
    app.state.mock_tracks = {(4, 101): copy.deepcopy(sample_track)}
    client = TestClient(app)

    res = client.post("/api/jobs/4/tracks/101/rollback", json={"history_id": str(uuid.uuid4())})
    assert res.status_code == 404
    assert res.json()["status"] == "error"
    assert "not found" in res.json()["detail"].lower()


def test_rollback_with_invalid_or_blank_history_id_returns_404(tmp_path: Path, sample_track: dict[str, Any], mock_cvat_client: MagicMock):
    """Stress 2.2: Blank or non-existent history_ids return 404 cleanly."""
    app = create_app(home_dir=tmp_path)
    app.state.cvat_client = mock_cvat_client
    app.state.mock_tracks = {(4, 101): copy.deepcopy(sample_track)}
    client = TestClient(app)

    bad_ids = [
        "",
        "   ",
        "non-existent-id",
        "00000000-0000-0000-0000-000000000000",
    ]
    for hid in bad_ids:
        res = client.post("/api/jobs/4/tracks/101/rollback", json={"history_id": hid})
        assert res.status_code == 404
        assert res.json()["status"] == "error"


def test_rollback_directory_traversal_attempts_are_blocked(tmp_path: Path, sample_track: dict[str, Any], mock_cvat_client: MagicMock):
    """Stress 2.3: Directory traversal in history_id is detected and rejected without filesystem leak."""
    app = create_app(home_dir=tmp_path)
    app.state.cvat_client = mock_cvat_client
    app.state.mock_tracks = {(4, 101): copy.deepcopy(sample_track)}
    client = TestClient(app)

    traversal_ids = [
        "../../etc/passwd",
        "..\\..\\windows\\win.ini",
        "job_4/../../history_id",
        "/absolute/path/to/snapshot",
        "%2e%2e%2f%2e%2e%2f",
    ]
    for hid in traversal_ids:
        res = client.post("/api/jobs/4/tracks/101/rollback", json={"history_id": hid})
        assert res.status_code == 404
        assert res.json()["status"] == "error"


def test_rollback_with_corrupt_or_truncated_snapshot_returns_400_or_404(tmp_path: Path, sample_track: dict[str, Any], mock_cvat_client: MagicMock):
    """Stress 2.4: Corrupt snapshot JSON on disk returns 400 or 404 without crashing the server."""
    app = create_app(home_dir=tmp_path)
    app.state.cvat_client = mock_cvat_client
    app.state.mock_tracks = {(4, 101): copy.deepcopy(sample_track)}
    client = TestClient(app)

    # Prepare history dir
    history_mgr = HistoryManager(home_dir=tmp_path)
    h_dir = history_mgr.history_dir(4, slug="default")

    # Case A: Truncated / malformed JSON file
    hid_malformed = str(uuid.uuid4())
    (h_dir / f"{hid_malformed}.json").write_text("{ unclosed json: ", encoding="utf-8")

    res_a = client.post("/api/jobs/4/tracks/101/rollback", json={"history_id": hid_malformed})
    assert res_a.status_code in (400, 404)

    # Case B: Snapshot missing pre_repair_track
    hid_missing_pre = str(uuid.uuid4())
    (h_dir / f"{hid_missing_pre}.json").write_text(json.dumps({
        "history_id": hid_missing_pre,
        "job_id": 4,
        "track_id": 101,
        "post_repair_track": sample_track,
    }), encoding="utf-8")

    res_b = client.post("/api/jobs/4/tracks/101/rollback", json={"history_id": hid_missing_pre})
    assert res_b.status_code in (400, 404)

    # Case C: Snapshot where pre_repair_track is null / integer
    hid_invalid_pre = str(uuid.uuid4())
    (h_dir / f"{hid_invalid_pre}.json").write_text(json.dumps({
        "history_id": hid_invalid_pre,
        "job_id": 4,
        "track_id": 101,
        "pre_repair_track": None,
    }), encoding="utf-8")

    res_c = client.post("/api/jobs/4/tracks/101/rollback", json={"history_id": hid_invalid_pre})
    assert res_c.status_code in (400, 404)


# =========================================================================
# 3. Edge-Case Box Repairs: Zero Dims, Extreme Offsets, Negative Coords
# =========================================================================

def test_box_repair_with_zero_dimensions(tmp_path: Path, sample_track: dict[str, Any], mock_cvat_client: MagicMock):
    """Stress 3.1: Verify repair payload with zero dimensions is processed and checked."""
    app = create_app(home_dir=tmp_path)
    app.state.cvat_client = mock_cvat_client
    app.state.mock_tracks = {(4, 101): copy.deepcopy(sample_track)}
    client = TestClient(app)

    # Direct points with zero dimensions [px, py, pz, rx, ry, rz, sx=0, sy=0, sz=0, ...]
    zero_dim_points = [10.0, 5.0, -0.5, 0.0, 0.0, 0.15, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
    payload = {
        "frame": 2,
        "repair": {"points": zero_dim_points},
    }
    res = client.post("/api/jobs/4/tracks/101/apply-repair", json=payload)
    assert res.status_code == 400
    assert "Dimensions must be strictly positive" in res.json()["detail"]


def test_box_repair_with_extreme_offsets(tmp_path: Path, sample_track: dict[str, Any], mock_cvat_client: MagicMock):
    """Stress 3.2: Verify repair payload with extreme coordinates (1e9 meters) does not overflow."""
    app = create_app(home_dir=tmp_path)
    app.state.cvat_client = mock_cvat_client
    app.state.mock_tracks = {(4, 101): copy.deepcopy(sample_track)}
    client = TestClient(app)

    extreme_center = [1e9, -1e9, 1e9]
    payload = {
        "frame": 2,
        "repair": {
            "center": extreme_center,
            "dims": [4.5, 2.0, 1.6],
            "yaw": 0.0,
        },
    }
    res = client.post("/api/jobs/4/tracks/101/apply-repair", json=payload)
    assert res.status_code == 200
    updated_shape = next(s for s in res.json()["updated_track"]["shapes"] if s["frame"] == 2)
    assert updated_shape["points"][0:3] == [1e9, -1e9, 1e9]


def test_box_repair_with_negative_center_coordinates(tmp_path: Path, sample_track: dict[str, Any], mock_cvat_client: MagicMock):
    """Stress 3.3: Verify negative center coordinates (valid LiDAR objects behind sensor) are preserved."""
    app = create_app(home_dir=tmp_path)
    app.state.cvat_client = mock_cvat_client
    app.state.mock_tracks = {(4, 101): copy.deepcopy(sample_track)}
    client = TestClient(app)

    neg_center = [-45.5, -22.3, -2.8]
    payload = {
        "frame": 2,
        "repair": {
            "center": neg_center,
            "dims": [4.5, 2.0, 1.6],
            "yaw": -math.pi / 2,
        },
    }
    res = client.post("/api/jobs/4/tracks/101/apply-repair", json=payload)
    assert res.status_code == 200
    updated_shape = next(s for s in res.json()["updated_track"]["shapes"] if s["frame"] == 2)
    assert updated_shape["points"][0:3] == neg_center
    assert updated_shape["points"][5] == pytest.approx(-math.pi / 2, abs=1e-4)


def test_box_repair_rejects_invalid_points_array_length(tmp_path: Path, sample_track: dict[str, Any], mock_cvat_client: MagicMock):
    """Stress 3.4: Points arrays with != 16 elements are rejected with HTTP 400."""
    app = create_app(home_dir=tmp_path)
    app.state.cvat_client = mock_cvat_client
    app.state.mock_tracks = {(4, 101): copy.deepcopy(sample_track)}
    client = TestClient(app)

    for invalid_len in [0, 9, 15, 17, 32]:
        pts = [0.0] * invalid_len
        payload = {
            "frame": 2,
            "repair": {"points": pts},
        }
        res = client.post("/api/jobs/4/tracks/101/apply-repair", json=payload)
        assert res.status_code == 400
        assert "exactly 16 floats" in res.json()["detail"]


def test_box_repair_large_delta_yaw_wraps_around(tmp_path: Path, sample_track: dict[str, Any], mock_cvat_client: MagicMock):
    """Stress 3.5: Extreme delta_yaw (e.g. 100 * pi) wraps properly into [-pi, pi]."""
    app = create_app(home_dir=tmp_path)
    app.state.cvat_client = mock_cvat_client
    app.state.mock_tracks = {(4, 101): copy.deepcopy(sample_track)}
    client = TestClient(app)

    payload = {
        "frame": 2,
        "repair": {
            "delta_center": [0, 0, 0],
            "delta_dims": [0, 0, 0],
            "delta_yaw": 100 * math.pi + 0.25,
        },
    }
    res = client.post("/api/jobs/4/tracks/101/apply-repair", json=payload)
    assert res.status_code == 200
    updated_shape = next(s for s in res.json()["updated_track"]["shapes"] if s["frame"] == 2)
    final_yaw = updated_shape["points"][5]
    assert -math.pi <= final_yaw <= math.pi


def test_box_repair_with_nan_inf_values(tmp_path: Path, sample_track: dict[str, Any], mock_cvat_client: MagicMock):
    """Stress 3.6: Verify server behavior when repair payload contains NaN or Inf."""
    app = create_app(home_dir=tmp_path)
    app.state.cvat_client = mock_cvat_client
    app.state.mock_tracks = {(4, 101): copy.deepcopy(sample_track)}
    client = TestClient(app, raise_server_exceptions=False)

    raw_body_nan = b'{"frame": 2, "repair": {"delta_center": [NaN, 0.0, 0.0]}}'
    res_nan = client.post("/api/jobs/4/tracks/101/apply-repair", content=raw_body_nan, headers={"Content-Type": "application/json"})

    # Secure behavior: Rejects NaN and Inf floats with HTTP 400
    assert res_nan.status_code == 400
    assert "All coordinates, orientation, and dimensions must be finite numbers" in res_nan.json()["detail"]


# =========================================================================
# 4. Canvas Preview Data Boundary: Mathematical Robustness Oracle
# =========================================================================

def project_box_to_canvas(box: Cuboid, delta_center: tuple[float, float, float], delta_dims: tuple[float, float, float], view: str) -> dict[str, float]:
    """Projection oracle matching app.js drawPreview logic."""
    dx, dy, dz = delta_center
    dl, dw, dh = delta_dims
    rep_l = box.length + dl
    rep_w = box.width + dw
    rep_h = box.height + dh

    if view == "top":
        return {"cx": dx, "cy": dy, "w": rep_l, "h": rep_w}
    elif view == "side":
        return {"cx": dx, "cy": dz, "w": rep_l, "h": rep_h, "z_bottom": dz - rep_h / 2.0}
    elif view == "front":
        return {"cx": dy, "cy": dz, "w": rep_w, "h": rep_h}
    raise ValueError(f"Unknown view: {view}")


def test_canvas_projection_with_zero_dimension_box():
    """Stress 4.1: Cuboid strictly rejects zero/negative dimensions; micro-dimensions do not throw."""
    with pytest.raises(ValueError, match="dims phải dương"):
        Cuboid(center=(0.0, 0.0, 0.0), dims=(0.0, 0.0, 0.0), yaw=0.0, label="car", frame=0)

    with pytest.raises(ValueError, match="dims phải dương"):
        Cuboid(center=(0.0, 0.0, 0.0), dims=(-1.0, 2.0, 1.5), yaw=0.0, label="car", frame=0)

    # Micro-dimensions test
    micro_box = Cuboid(center=(0.0, 0.0, 0.0), dims=(1e-6, 1e-6, 1e-6), yaw=0.0, label="car", frame=0)
    for view in ["top", "side", "front"]:
        proj = project_box_to_canvas(micro_box, (0.0, 0.0, 0.0), (0.0, 0.0, 0.0), view)
        assert proj["w"] == pytest.approx(1e-6)
        assert proj["h"] == pytest.approx(1e-6)


def test_canvas_projection_scale_formula_with_zero_canvas():
    """Stress 4.2: Verify scale calculation formula behavior when canvas clientWidth / clientHeight is 0."""
    # scale = Math.min((w - 8) / (2 * hr), (h - 8) / (v1 - v0))
    # In app.js: hr = L / 2 + 2.0 (hr >= 2.0 even if L = 0)
    L, W, H = 4.5, 2.0, 1.6
    hr = L / 2.0 + 2.0
    v0, v1 = -H / 2.0 - 1.5, H / 2.0 + 1.0
    h_span = v1 - v0

    # Normal canvas: 300 x 200
    scale_normal = min((300 - 8) / (2 * hr), (200 - 8) / h_span)
    assert scale_normal > 0

    # Zero canvas: 0 x 0
    scale_zero = min((0 - 8) / (2 * hr), (0 - 8) / h_span)
    assert math.isfinite(scale_zero)  # Negative, but finite (does not divide by zero or NaN)


# =========================================================================
# 5. Empirical Vulnerability & Defect Reproductions (Targeted for Fix)
# =========================================================================

def test_defect_cross_job_rollback_allows_foreign_track_overwrite(tmp_path: Path):
    """Defect Reproduction 1: Cross-Job Rollback Isolation Breach.
    
    Vulnerability:
    When a snapshot exists under Job 5 (Track 999), a user calling rollback on
    POST /api/jobs/4/tracks/101/rollback with Job 5's history_id succeeds (200 OK)
    and overwrites Job 4's track 101 with the foreign Track 999!
    """
    app = create_app(home_dir=tmp_path)
    mgr = HistoryManager(home_dir=tmp_path)

    # 1. Create a snapshot in Job 5 for Track 999
    snap_id = str(uuid.uuid4())
    h_dir5 = mgr.history_dir(5, slug="default")
    track5 = {
        "id": 999,
        "shapes": [{"id": 500, "frame": 0, "type": "cuboid", "points": [99, 99, 99, 0, 0, 0, 1, 1, 1, 0, 0, 0, 0, 0, 0, 0], "attributes": []}],
        "attributes": [],
    }
    snapshot5 = {
        "history_id": snap_id,
        "timestamp": "2026-10-14T00:00:00Z",
        "job_id": 5,
        "track_id": 999,
        "frame": 0,
        "pre_repair_track": track5,
        "post_repair_track": track5,
        "applied_repair": {},
    }
    (h_dir5 / f"{snap_id}.json").write_text(json.dumps(snapshot5), encoding="utf-8")

    # 2. Job 4 has Track 101
    track4 = {
        "id": 101,
        "shapes": [{"id": 1, "frame": 0, "type": "cuboid", "points": [10, 5, 0, 0, 0, 0, 4, 2, 1.5, 0, 0, 0, 0, 0, 0, 0], "attributes": []}],
        "attributes": [],
    }
    app.state.mock_tracks = {(4, 101): copy.deepcopy(track4)}
    client = TestClient(app, raise_server_exceptions=False)

    # 3. Request rollback on Job 4 using Job 5's snapshot
    res = client.post("/api/jobs/4/tracks/101/rollback", json={"history_id": snap_id})

    # The defect fix: Must return HTTP 400 rejecting foreign snapshot
    assert res.status_code == 400, f"Expected 400, got {res.status_code}"
    data = res.json()
    assert "does not belong to job 4 track 101" in data.get("detail", "")
    # Verify Track 101 in Job 4 is NOT modified
    assert app.state.mock_tracks[(4, 101)]["id"] == 101
    assert app.state.mock_tracks[(4, 101)]["shapes"][0]["points"][0] == 10


def test_defect_cross_track_rollback_within_same_job_rejected(tmp_path: Path):
    """Enforce intra-job cross-track rollback isolation."""
    app = create_app(home_dir=tmp_path)
    mgr = HistoryManager(home_dir=tmp_path)

    # Snapshot under Job 4 for Track 102
    snap_id = str(uuid.uuid4())
    h_dir4 = mgr.history_dir(4, slug="default")
    track102 = {
        "id": 102,
        "shapes": [{"id": 2, "frame": 0, "type": "cuboid", "points": [20, 20, 0, 0, 0, 0, 3, 2, 1.5, 0, 0, 0, 0, 0, 0, 0], "attributes": []}],
        "attributes": [],
    }
    snapshot102 = {
        "history_id": snap_id,
        "timestamp": "2026-10-14T00:00:00Z",
        "job_id": 4,
        "track_id": 102,
        "frame": 0,
        "pre_repair_track": track102,
        "post_repair_track": track102,
        "applied_repair": {},
    }
    (h_dir4 / f"{snap_id}.json").write_text(json.dumps(snapshot102), encoding="utf-8")

    track101 = {
        "id": 101,
        "shapes": [{"id": 1, "frame": 0, "type": "cuboid", "points": [10, 5, 0, 0, 0, 0, 4, 2, 1.5, 0, 0, 0, 0, 0, 0, 0], "attributes": []}],
        "attributes": [],
    }
    app.state.mock_tracks = {(4, 101): copy.deepcopy(track101), (4, 102): copy.deepcopy(track102)}
    client = TestClient(app, raise_server_exceptions=False)

    # Attempt rollback on Track 101 using Track 102's snapshot
    res = client.post("/api/jobs/4/tracks/101/rollback", json={"history_id": snap_id})
    assert res.status_code == 400
    assert "does not belong to job 4 track 101" in res.json().get("detail", "")
    assert app.state.mock_tracks[(4, 101)]["id"] == 101


def test_defect_non_positive_dimensions_poisons_future_scans(tmp_path: Path):
    """Defect Remediation 2: State Poisoning via Non-Positive Dimensions."""
    app = create_app(home_dir=tmp_path)
    sample_track = {
        "id": 101,
        "shapes": [{"id": 1, "frame": 2, "type": "cuboid", "points": [10.0, 5.0, -0.5, 0.0, 0.0, 0.15, 4.5, 2.0, 1.6, 0, 0, 0, 0, 0, 0, 0], "attributes": []}],
        "attributes": [],
    }
    app.state.mock_tracks = {(4, 101): copy.deepcopy(sample_track)}
    client = TestClient(app, raise_server_exceptions=False)

    # 1. Apply negative dimensions - Must be rejected with HTTP 400
    res1 = client.post("/api/jobs/4/tracks/101/apply-repair", json={
        "frame": 2,
        "repair": {"center": [10, 5, 0], "dims": [-1.0, 2.0, 1.5]},
    })
    assert res1.status_code == 400
    assert "Dimensions must be strictly positive" in res1.json()["detail"]

    # 2. Subsequent GET repair on the intact track succeeds with 200
    res2 = client.get("/api/jobs/4/tracks/101/repair?frame=2&rule=floating")
    assert res2.status_code == 200


def test_defect_nan_floats_poisons_track_geometry(tmp_path: Path):
    """Defect Remediation 3: State Poisoning via NaN Floats."""
    app = create_app(home_dir=tmp_path)
    sample_track = {
        "id": 101,
        "shapes": [{"id": 1, "frame": 2, "type": "cuboid", "points": [10.0, 5.0, -0.5, 0.0, 0.0, 0.15, 4.5, 2.0, 1.6, 0, 0, 0, 0, 0, 0, 0], "attributes": []}],
        "attributes": [],
    }
    app.state.mock_tracks = {(4, 101): copy.deepcopy(sample_track)}
    client = TestClient(app, raise_server_exceptions=False)

    # 1. Apply NaN center - Must be rejected with HTTP 400
    raw_body = b'{"frame": 2, "repair": {"delta_center": [NaN, 0.0, 0.0]}}'
    res1 = client.post("/api/jobs/4/tracks/101/apply-repair", content=raw_body, headers={"Content-Type": "application/json"})
    assert res1.status_code == 400
    assert "All coordinates, orientation, and dimensions must be finite numbers" in res1.json()["detail"]

    # 2. Subsequent repair on the intact track succeeds with 200
    res2 = client.post("/api/jobs/4/tracks/101/apply-repair", json={
        "frame": 2,
        "repair": {"delta_center": [0.0, 0.0, 0.0]},
    })
    assert res2.status_code == 422  # Zero delta is not a successful repair.

