"""Empirical Challenger Test Suite for Milestone M4 Iteration 2.

Focus Areas:
1. Boundary stress tests:
   - Extreme float values near IEEE-754 overflow/underflow (1e308, -1e308, 1e-300, 1e-324, inf, nan).
   - Zero coordinates (center at 0, 0, 0; zero delta adjustments; degenerate zero dimensions).
   - Negative roll and pitch (handling vehicle tilt on sloped terrain).
2. Concurrency stress tests:
   - Interleaved concurrent apply-repair and rollback operations on same and different tracks.
   - Multi-threaded cross-job and cross-track rollback isolation under race conditions.
   - Concurrent barrage of invalid payloads (zero dims, NaNs, malformed arrays) mixed with valid operations.
   - Concurrent duplicate rollback on the same snapshot.
"""

from __future__ import annotations

import concurrent.futures
import copy
import json
import math
from pathlib import Path
import random
import threading
from typing import Any
from unittest.mock import MagicMock
import uuid

import pytest
from fastapi.testclient import TestClient

from pointsnap.adapters.cvat.client import CvatClient
from pointsnap.adapters.cvat.shapes import points_to_geometry, cuboid_to_points
from pointsnap.adapters.cvat.writer import compute_track_etag
from pointsnap.core.model import Cuboid
from pointsnap.history.manager import HistoryManager, SnapshotIsolationError
from pointsnap.web.app import create_app


# =========================================================================
# Fixtures
# =========================================================================

@pytest.fixture
def base_track_factory():
    """Factory creating distinct valid tracks with custom IDs, frames, roll, and pitch."""
    def _create(track_id: int = 101, frame: int = 0, roll: float = 0.0, pitch: float = 0.0, dims: tuple[float, float, float] = (4.5, 2.0, 1.6)):
        pts = [
            10.0, 5.0, -0.5,
            roll, pitch, 0.15,
            dims[0], dims[1], dims[2],
            0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0,
        ]
        return {
            "id": track_id,
            "label_id": 1,
            "frame": frame,
            "shapes": [
                {
                    "id": 1000 + track_id * 10 + frame,
                    "frame": frame,
                    "type": "cuboid",
                    "occluded": False,
                    "outside": False,
                    "keyframe": True,
                    "points": list(pts),
                    "attributes": [
                        {"name": "subtype", "value": "car"},
                        {"name": "pointsnap_error", "value": "floating error"},
                    ],
                }
            ],
            "attributes": [{"name": "track_status", "value": "active"}],
        }
    return _create


@pytest.fixture
def mock_cvat_multi_track():
    """Thread-safe mock CVAT client managing multiple tracks."""
    lock = threading.RLock()
    store: dict[int, dict[int, dict[str, Any]]] = {}  # job_id -> {track_id: track_dict}

    client = MagicMock(spec=CvatClient)

    def get_job_annotations(job_id: int) -> dict[str, Any]:
        with lock:
            job_tracks = store.get(job_id, {})
            return {
                "version": 1,
                "shapes": [],
                "tracks": [copy.deepcopy(t) for t in job_tracks.values()],
            }

    def patch_job_annotations(job_id: int, data: dict[str, Any], action: str = "update") -> dict[str, Any]:
        with lock:
            if job_id not in store:
                store[job_id] = {}
            for t in data.get("tracks", []):
                store[job_id][t["id"]] = copy.deepcopy(t)
            return get_job_annotations(job_id)

    client.get_job_annotations.side_effect = get_job_annotations
    client.patch_job_annotations.side_effect = patch_job_annotations
    client.store = store
    client.lock = lock
    return client


# =========================================================================
# Part 1: Boundary Stress Tests
# =========================================================================

class TestBoundaryExtremeFloats:
    """Stress tests on extreme float values near IEEE-754 overflow/underflow."""

    def test_extreme_large_finite_coordinates_accepted(self, tmp_path: Path, base_track_factory, mock_cvat_multi_track):
        """Values near float max (~1e308) are valid finite floats and must be accepted."""
        app = create_app(home_dir=tmp_path)
        app.state.cvat_client = mock_cvat_multi_track
        track = base_track_factory(track_id=101, frame=0)
        app.state.mock_tracks = {(4, 101): copy.deepcopy(track)}
        for (seed_job, seed_track), seed_data in app.state.mock_tracks.items():
            mock_cvat_multi_track.store.setdefault(seed_job, {})[seed_track] = copy.deepcopy(seed_data)
        client = TestClient(app)

        # Center near float max
        huge_val = 1e308
        payload = {
            "frame": 0,
            "repair": {
                "center": [huge_val, -huge_val, huge_val],
                "dims": [4.5, 2.0, 1.6],
                "yaw": 0.0,
            },
        }
        res = client.post("/api/jobs/4/tracks/101/apply-repair", json=payload)
        assert res.status_code == 200, res.text
        data = res.json()
        assert data["status"] == "ok"
        pts = data["updated_track"]["shapes"][0]["points"]
        assert pts[0] == huge_val
        assert pts[1] == -huge_val
        assert pts[2] == huge_val

    def test_overflow_to_infinity_via_delta_rejected_with_400(self, tmp_path: Path, base_track_factory, mock_cvat_multi_track):
        """When delta addition causes float overflow to infinity, must be rejected with HTTP 400."""
        app = create_app(home_dir=tmp_path)
        app.state.cvat_client = mock_cvat_multi_track
        # Track already has huge center
        track = base_track_factory(track_id=101, frame=0)
        track["shapes"][0]["points"][0] = 1.7e308
        app.state.mock_tracks = {(4, 101): copy.deepcopy(track)}
        for (seed_job, seed_track), seed_data in app.state.mock_tracks.items():
            mock_cvat_multi_track.store.setdefault(seed_job, {})[seed_track] = copy.deepcopy(seed_data)
        client = TestClient(app)

        # Adding delta 1.7e308 will overflow 1.7e308 + 1.7e308 = inf
        payload = {
            "frame": 0,
            "repair": {
                "delta_center": [1.7e308, 0.0, 0.0],
                "delta_dims": [0.0, 0.0, 0.0],
                "delta_yaw": 0.0,
            },
        }
        res = client.post("/api/jobs/4/tracks/101/apply-repair", json=payload)
        assert res.status_code == 400
        assert "finite numbers" in res.json()["detail"]

    def test_subnormal_positive_dimensions_handling(self, tmp_path: Path, base_track_factory, mock_cvat_multi_track):
        """Subnormal positive float (1e-320) is finite and > 0, does not crash."""
        app = create_app(home_dir=tmp_path)
        app.state.cvat_client = mock_cvat_multi_track
        track = base_track_factory(track_id=101, frame=0)
        app.state.mock_tracks = {(4, 101): copy.deepcopy(track)}
        for (seed_job, seed_track), seed_data in app.state.mock_tracks.items():
            mock_cvat_multi_track.store.setdefault(seed_job, {})[seed_track] = copy.deepcopy(seed_data)
        client = TestClient(app)

        # 1e-320 > 0.0 in Python IEEE-754 subnormal
        payload = {
            "frame": 0,
            "repair": {
                "center": [10.0, 5.0, -0.5],
                "dims": [1e-320, 1e-320, 1e-320],
                "yaw": 0.0,
            },
        }
        res = client.post("/api/jobs/4/tracks/101/apply-repair", json=payload)
        # Should succeed or cleanly handle without 500
        assert res.status_code in (200, 400)

    def test_delta_dims_reducing_size_to_zero_rejected_with_400(self, tmp_path: Path, base_track_factory, mock_cvat_multi_track):
        """Delta dims that exactly subtract existing dimensions to 0.0 must be rejected."""
        app = create_app(home_dir=tmp_path)
        app.state.cvat_client = mock_cvat_multi_track
        track = base_track_factory(track_id=101, frame=0, dims=(4.5, 2.0, 1.6))
        app.state.mock_tracks = {(4, 101): copy.deepcopy(track)}
        for (seed_job, seed_track), seed_data in app.state.mock_tracks.items():
            mock_cvat_multi_track.store.setdefault(seed_job, {})[seed_track] = copy.deepcopy(seed_data)
        client = TestClient(app)

        # delta_dims subtracts length exactly: 4.5 + (-4.5) = 0.0
        payload = {
            "frame": 0,
            "repair": {
                "delta_center": [0.0, 0.0, 0.0],
                "delta_dims": [-4.5, 0.0, 0.0],
                "delta_yaw": 0.0,
            },
        }
        res = client.post("/api/jobs/4/tracks/101/apply-repair", json=payload)
        assert res.status_code == 400
        assert "Dimensions must be strictly positive" in res.json()["detail"]


class TestBoundaryZeroCoordinates:
    """Stress tests on zero coordinates and origin boundaries."""

    def test_zero_center_coordinates_accepted(self, tmp_path: Path, base_track_factory, mock_cvat_multi_track):
        """A bounding box at exact sensor origin (0.0, 0.0, 0.0) is mathematically valid."""
        app = create_app(home_dir=tmp_path)
        app.state.cvat_client = mock_cvat_multi_track
        track = base_track_factory(track_id=101, frame=0)
        app.state.mock_tracks = {(4, 101): copy.deepcopy(track)}
        for (seed_job, seed_track), seed_data in app.state.mock_tracks.items():
            mock_cvat_multi_track.store.setdefault(seed_job, {})[seed_track] = copy.deepcopy(seed_data)
        client = TestClient(app)

        payload = {
            "frame": 0,
            "repair": {
                "center": [0.0, 0.0, 0.0],
                "dims": [4.0, 2.0, 1.5],
                "yaw": 0.0,
            },
        }
        res = client.post("/api/jobs/4/tracks/101/apply-repair", json=payload)
        assert res.status_code == 200
        pts = res.json()["updated_track"]["shapes"][0]["points"]
        assert pts[0] == 0.0
        assert pts[1] == 0.0
        assert pts[2] == 0.0

    def test_zero_delta_repair_identity_operation(self, tmp_path: Path, base_track_factory, mock_cvat_multi_track):
        """A zero-delta repair (no changes) preserves track coordinates identically."""
        app = create_app(home_dir=tmp_path)
        app.state.cvat_client = mock_cvat_multi_track
        track = base_track_factory(track_id=101, frame=0)
        initial_pts = list(track["shapes"][0]["points"])
        app.state.mock_tracks = {(4, 101): copy.deepcopy(track)}
        for (seed_job, seed_track), seed_data in app.state.mock_tracks.items():
            mock_cvat_multi_track.store.setdefault(seed_job, {})[seed_track] = copy.deepcopy(seed_data)
        client = TestClient(app)

        payload = {
            "frame": 0,
            "repair": {
                "delta_center": [0.0, 0.0, 0.0],
                "delta_dims": [0.0, 0.0, 0.0],
                "delta_yaw": 0.0,
            },
        }
        res = client.post("/api/jobs/4/tracks/101/apply-repair", json=payload)
        assert res.status_code == 422
        assert app.state.mock_tracks[(4, 101)]["shapes"][0]["points"] == initial_pts

    def test_zero_dimension_individual_axes_rejected(self, tmp_path: Path, base_track_factory, mock_cvat_multi_track):
        """Zero on any single dimension axis (length, width, or height) is rejected."""
        app = create_app(home_dir=tmp_path)
        app.state.cvat_client = mock_cvat_multi_track
        track = base_track_factory(track_id=101, frame=0)
        app.state.mock_tracks = {(4, 101): copy.deepcopy(track)}
        for (seed_job, seed_track), seed_data in app.state.mock_tracks.items():
            mock_cvat_multi_track.store.setdefault(seed_job, {})[seed_track] = copy.deepcopy(seed_data)
        client = TestClient(app)

        for dims_test in [[0.0, 2.0, 1.5], [4.5, 0.0, 1.5], [4.5, 2.0, 0.0]]:
            payload = {
                "frame": 0,
                "repair": {
                    "center": [10.0, 5.0, -0.5],
                    "dims": dims_test,
                    "yaw": 0.0,
                },
            }
            res = client.post("/api/jobs/4/tracks/101/apply-repair", json=payload)
            assert res.status_code == 400
            assert "Dimensions must be strictly positive" in res.json()["detail"]


class TestBoundaryNegativeRollPitch:
    """Stress tests on negative roll and pitch handling (sloped/banked roads)."""

    def test_negative_roll_and_pitch_in_existing_track_preserved_through_delta_repair(
        self, tmp_path: Path, base_track_factory, mock_cvat_multi_track
    ):
        """When track has negative roll and pitch, applying a delta repair preserves them intact."""
        app = create_app(home_dir=tmp_path)
        app.state.cvat_client = mock_cvat_multi_track
        # Track on a steep slope: roll = -0.15 rad, pitch = -0.25 rad
        neg_roll = -0.1523
        neg_pitch = -0.2489
        track = base_track_factory(track_id=101, frame=0, roll=neg_roll, pitch=neg_pitch)
        app.state.mock_tracks = {(4, 101): copy.deepcopy(track)}
        for (seed_job, seed_track), seed_data in app.state.mock_tracks.items():
            mock_cvat_multi_track.store.setdefault(seed_job, {})[seed_track] = copy.deepcopy(seed_data)
        client = TestClient(app)

        payload = {
            "frame": 0,
            "repair": {
                "delta_center": [0.1, -0.2, 0.3],
                "delta_dims": [0.0, 0.0, 0.0],
                "delta_yaw": 0.05,
            },
        }
        res = client.post("/api/jobs/4/tracks/101/apply-repair", json=payload)
        assert res.status_code == 200, res.text
        updated_pts = res.json()["updated_track"]["shapes"][0]["points"]
        # roll is index 3, pitch is index 4
        assert updated_pts[3] == pytest.approx(neg_roll, abs=1e-5)
        assert updated_pts[4] == pytest.approx(neg_pitch, abs=1e-5)

    def test_negative_roll_and_pitch_in_repaired_box_payload_accepted(
        self, tmp_path: Path, base_track_factory, mock_cvat_multi_track
    ):
        """When repair specifies negative roll and pitch directly, server accepts and stores them."""
        app = create_app(home_dir=tmp_path)
        app.state.cvat_client = mock_cvat_multi_track
        track = base_track_factory(track_id=101, frame=0)
        app.state.mock_tracks = {(4, 101): copy.deepcopy(track)}
        for (seed_job, seed_track), seed_data in app.state.mock_tracks.items():
            mock_cvat_multi_track.store.setdefault(seed_job, {})[seed_track] = copy.deepcopy(seed_data)
        client = TestClient(app)

        payload = {
            "frame": 0,
            "repair": {
                "center": [12.0, 6.0, -1.0],
                "dims": [4.6, 2.1, 1.7],
                "yaw": -0.85,
                "roll": -0.314,
                "pitch": -0.157,
            },
        }
        res = client.post("/api/jobs/4/tracks/101/apply-repair", json=payload)
        assert res.status_code == 200, res.text
        updated_pts = res.json()["updated_track"]["shapes"][0]["points"]
        assert updated_pts[3] == pytest.approx(-0.314, abs=1e-5)
        assert updated_pts[4] == pytest.approx(-0.157, abs=1e-5)
        assert updated_pts[5] == pytest.approx(-0.85, abs=1e-5)

    def test_extreme_negative_roll_pitch_boundary_limits(
        self, tmp_path: Path, base_track_factory, mock_cvat_multi_track
    ):
        """Roll and pitch at -pi and -pi/2 are finite and valid orientation angles."""
        app = create_app(home_dir=tmp_path)
        app.state.cvat_client = mock_cvat_multi_track
        track = base_track_factory(track_id=101, frame=0)
        app.state.mock_tracks = {(4, 101): copy.deepcopy(track)}
        for (seed_job, seed_track), seed_data in app.state.mock_tracks.items():
            mock_cvat_multi_track.store.setdefault(seed_job, {})[seed_track] = copy.deepcopy(seed_data)
        client = TestClient(app)

        payload = {
            "frame": 0,
            "repair": {
                "center": [10.0, 5.0, -0.5],
                "dims": [4.5, 2.0, 1.6],
                "yaw": 0.0,
                "roll": -math.pi,
                "pitch": -math.pi / 2,
            },
        }
        res = client.post("/api/jobs/4/tracks/101/apply-repair", json=payload)
        assert res.status_code == 200
        updated_pts = res.json()["updated_track"]["shapes"][0]["points"]
        assert updated_pts[3] == pytest.approx(-math.pi, abs=1e-5)
        assert updated_pts[4] == pytest.approx(-math.pi / 2, abs=1e-5)


# =========================================================================
# Part 2: Concurrency Stress Tests
# =========================================================================

class TestConcurrencyApplyAndRollback:
    """Stress tests for concurrent apply-repair and rollback operations."""

    def test_concurrent_interleaved_applies_and_rollbacks(
        self, tmp_path: Path, base_track_factory, mock_cvat_multi_track
    ):
        """Simultaneous applies and rollbacks across multiple threads maintain track consistency."""
        app = create_app(home_dir=tmp_path)
        app.state.cvat_client = mock_cvat_multi_track
        track = base_track_factory(track_id=101, frame=0)
        app.state.mock_tracks = {(4, 101): copy.deepcopy(track)}
        for (seed_job, seed_track), seed_data in app.state.mock_tracks.items():
            mock_cvat_multi_track.store.setdefault(seed_job, {})[seed_track] = copy.deepcopy(seed_data)
        client = TestClient(app)

        # First, apply 3 repairs to build up history
        history_ids: list[str] = []
        for i in range(3):
            res_rep = client.get("/api/jobs/4/tracks/101/repair?frame=0&rule=floating")
            etag = res_rep.json()["track_etag"]
            apply_res = client.post("/api/jobs/4/tracks/101/apply-repair", json={
                "frame": 0,
                "repair": {
                    "delta_center": [0.1 * (i + 1), 0.0, -0.1 * (i + 1)],
                    "delta_dims": [0.0, 0.0, 0.0],
                    "delta_yaw": 0.0,
                },
                "client_track_etag": etag,
            })
            assert apply_res.status_code == 200
            history_ids.append(apply_res.json()["history_id"])

        # Now launch concurrent requests: 4 threads attempting rollback, 4 threads attempting apply
        results = []
        lock = threading.Lock()

        def do_apply(idx: int):
            # Fetch latest etag or use stale
            rep = client.get("/api/jobs/4/tracks/101/repair?frame=0&rule=floating")
            current_etag = rep.json().get("track_etag")
            res = client.post("/api/jobs/4/tracks/101/apply-repair", json={
                "frame": 0,
                "repair": {
                    "delta_center": [0.01 * idx, 0.0, -0.01 * idx],
                    "delta_dims": [0.0, 0.0, 0.0],
                    "delta_yaw": 0.0,
                },
                "client_track_etag": current_etag,
            })
            with lock:
                results.append(("apply", res.status_code))

        def do_rollback(hid: str):
            res = client.post("/api/jobs/4/tracks/101/rollback", json={"history_id": hid})
            with lock:
                results.append(("rollback", res.status_code))

        threads = []
        for i in range(4):
            threads.append(threading.Thread(target=do_apply, args=(i,)))
            hid_target = random.choice(history_ids)
            threads.append(threading.Thread(target=do_rollback, args=(hid_target,)))

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # None of the requests should crash with 500
        status_codes = [r[1] for r in results]
        assert all(code in (200, 400, 404, 409) for code in status_codes), f"Unexpected status: {results}"
        assert 500 not in status_codes

        # Track state in memory must still be healthy and parsable
        final_track = app.state.mock_tracks[(4, 101)]
        pts = final_track["shapes"][0]["points"]
        assert len(pts) == 16
        assert all(math.isfinite(v) for v in pts)
        assert pts[6] > 0.0 and pts[7] > 0.0 and pts[8] > 0.0

    def test_concurrent_cross_track_and_cross_job_isolation_under_race(
        self, tmp_path: Path, base_track_factory, mock_cvat_multi_track
    ):
        """Under concurrent execution, cross-track and cross-job rollback attempts are 100% rejected."""
        app = create_app(home_dir=tmp_path)
        app.state.cvat_client = mock_cvat_multi_track

        # Set up Job 4 Track 101, Job 4 Track 102, Job 5 Track 101
        track_4_101 = base_track_factory(track_id=101, frame=0)
        track_4_102 = base_track_factory(track_id=102, frame=0)
        track_5_101 = base_track_factory(track_id=101, frame=0)

        app.state.mock_tracks = {
            (4, 101): copy.deepcopy(track_4_101),
            (4, 102): copy.deepcopy(track_4_102),
            (5, 101): copy.deepcopy(track_5_101),
        }
        for (seed_job, seed_track), seed_data in app.state.mock_tracks.items():
            mock_cvat_multi_track.store.setdefault(seed_job, {})[seed_track] = copy.deepcopy(seed_data)
        client = TestClient(app)

        # Create snapshot for Job 4 Track 102
        res_rep_102 = client.get("/api/jobs/4/tracks/102/repair?frame=0&rule=floating")
        apply_102 = client.post("/api/jobs/4/tracks/102/apply-repair", json={
            "frame": 0,
            "repair": {"delta_center": [0, 0, -0.2], "delta_dims": [0, 0, 0], "delta_yaw": 0},
            "client_track_etag": res_rep_102.json()["track_etag"],
        })
        assert apply_102.status_code == 200
        snap_id_4_102 = apply_102.json()["history_id"]

        # Create snapshot for Job 5 Track 101
        res_rep_5_101 = client.get("/api/jobs/5/tracks/101/repair?frame=0&rule=floating")
        apply_5_101 = client.post("/api/jobs/5/tracks/101/apply-repair", json={
            "frame": 0,
            "repair": {"delta_center": [0, 0, -0.3], "delta_dims": [0, 0, 0], "delta_yaw": 0},
            "client_track_etag": res_rep_5_101.json()["track_etag"],
        })
        assert apply_5_101.status_code == 200
        snap_id_5_101 = apply_5_101.json()["history_id"]

        # Record initial points for Job 4 Track 101
        initial_pts_4_101 = list(app.state.mock_tracks[(4, 101)]["shapes"][0]["points"])

        # Bombard Job 4 Track 101 with concurrent cross-track and cross-job rollback requests
        num_attacks = 16
        attack_results = []
        lock = threading.Lock()

        def attack_cross_track():
            res = client.post("/api/jobs/4/tracks/101/rollback", json={"history_id": snap_id_4_102})
            with lock:
                attack_results.append(("cross_track", res.status_code, res.json()))

        def attack_cross_job():
            res = client.post("/api/jobs/4/tracks/101/rollback", json={"history_id": snap_id_5_101})
            with lock:
                attack_results.append(("cross_job", res.status_code, res.json()))

        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
            futures = []
            for i in range(num_attacks // 2):
                futures.append(executor.submit(attack_cross_track))
                futures.append(executor.submit(attack_cross_job))
            for f in concurrent.futures.as_completed(futures):
                f.result()

        # All attacks must return HTTP 400 Bad Request
        assert len(attack_results) == num_attacks
        for attack_type, code, data in attack_results:
            assert code == 400, f"Expected 400, got {code}: {data}"
            assert "does not belong to job 4 track 101" in data["detail"]

        # Job 4 Track 101 must remain completely untouched
        current_pts = app.state.mock_tracks[(4, 101)]["shapes"][0]["points"]
        assert current_pts == initial_pts_4_101

    def test_concurrent_invalid_payload_barrage_does_not_poison_state(
        self, tmp_path: Path, base_track_factory, mock_cvat_multi_track
    ):
        """Concurrent submissions of corrupted payloads (zero dims, NaNs, infs) are rejected without corrupting track."""
        app = create_app(home_dir=tmp_path)
        app.state.cvat_client = mock_cvat_multi_track
        track = base_track_factory(track_id=101, frame=0)
        app.state.mock_tracks = {(4, 101): copy.deepcopy(track)}
        for (seed_job, seed_track), seed_data in app.state.mock_tracks.items():
            mock_cvat_multi_track.store.setdefault(seed_job, {})[seed_track] = copy.deepcopy(seed_data)
        client = TestClient(app, raise_server_exceptions=False)

        bad_payloads = [
            b'{"frame": 0, "repair": {"center": [10.0, 5.0, -0.5], "dims": [0.0, 2.0, 1.5]}}',
            b'{"frame": 0, "repair": {"center": [10.0, 5.0, -0.5], "dims": [-1.0, 2.0, 1.5]}}',
            b'{"frame": 0, "repair": {"delta_dims": [-4.5, 0.0, 0.0]}}',  # reduces dim to 0
            b'{"frame": 0, "repair": {"points": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]}}',  # len = 9 (!= 16)
            b'{"frame": 0, "repair": {"points": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]}}',  # len = 17 (!= 16)
            b'{"frame": 0, "repair": {"delta_center": [Infinity, 0, 0]}}',  # inf
            b'{"frame": 0, "repair": {"delta_center": [NaN, 0, 0]}}',  # nan
        ]

        def send_bad(raw_content: bytes):
            return client.post(
                "/api/jobs/4/tracks/101/apply-repair",
                content=raw_content,
                headers={"Content-Type": "application/json"},
            ).status_code

        with concurrent.futures.ThreadPoolExecutor(max_workers=6) as executor:
            results = list(executor.map(send_bad, bad_payloads * 3))

        # All bad payloads must receive HTTP 400
        assert all(code == 400 for code in results), f"Expected all 400s, got {results}"

        # Track should still be healthy: a valid repair must succeed
        valid_res = client.post("/api/jobs/4/tracks/101/apply-repair", json={
            "frame": 0,
            "repair": {
                "delta_center": [0.1, 0.2, -0.3],
                "delta_dims": [0.0, 0.0, 0.0],
                "delta_yaw": 0.0,
            },
        })
        assert valid_res.status_code == 200

    def test_concurrent_duplicate_rollback_on_same_snapshot_idempotency(
        self, tmp_path: Path, base_track_factory, mock_cvat_multi_track
    ):
        """Simultaneous duplicate rollbacks for the exact same snapshot succeed idempotently."""
        app = create_app(home_dir=tmp_path)
        app.state.cvat_client = mock_cvat_multi_track
        track = base_track_factory(track_id=101, frame=0)
        app.state.mock_tracks = {(4, 101): copy.deepcopy(track)}
        for (seed_job, seed_track), seed_data in app.state.mock_tracks.items():
            mock_cvat_multi_track.store.setdefault(seed_job, {})[seed_track] = copy.deepcopy(seed_data)
        client = TestClient(app)

        # Apply repair
        res_rep = client.get("/api/jobs/4/tracks/101/repair?frame=0&rule=floating")
        apply_res = client.post("/api/jobs/4/tracks/101/apply-repair", json={
            "frame": 0,
            "repair": {"delta_center": [0, 0, -0.4], "delta_dims": [0, 0, 0], "delta_yaw": 0},
            "client_track_etag": res_rep.json()["track_etag"],
        })
        assert apply_res.status_code == 200
        hid = apply_res.json()["history_id"]

        # Run 6 concurrent rollbacks with the same history_id
        rollback_results = []
        lock = threading.Lock()

        def do_rb():
            res = client.post("/api/jobs/4/tracks/101/rollback", json={"history_id": hid})
            with lock:
                rollback_results.append(res.status_code)

        with concurrent.futures.ThreadPoolExecutor(max_workers=6) as executor:
            futures = [executor.submit(do_rb) for _ in range(6)]
            for f in futures:
                f.result()

        # All duplicate rollbacks must succeed with HTTP 200
        assert all(code == 200 for code in rollback_results), f"Results: {rollback_results}"
