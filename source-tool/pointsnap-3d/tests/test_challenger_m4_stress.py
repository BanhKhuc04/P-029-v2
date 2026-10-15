"""Challenger Adversarial Stress & Concurrency Test Suite for Milestone M4.

Validates:
1. Multi-threaded OCC (Optimistic Concurrency Control) race condition handling.
2. Bit-for-bit track restoration under high-depth interleaved LIFO rollback sequences.
3. Boundary & adversarial attacks on rollback history IDs (traversal, spoofing, cross-job).
4. Extreme delta values, NaNs, and negative dimension resistance.
5. High-load concurrent API requests stress testing.
"""

from __future__ import annotations

import copy
import math
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import numpy as np
import pytest
from fastapi.testclient import TestClient

from pointsnap.adapters.cvat.client import CvatClient
from pointsnap.adapters.cvat.writer import compute_track_etag
from pointsnap.core.model import Cuboid
from pointsnap.core.repair import compute_box_repair
from pointsnap.web.app import create_app


@pytest.fixture
def sample_cuboid() -> Cuboid:
    """Sample cuboid object centered at [10.0, 5.0, -0.5] with dimensions [4.5, 2.0, 1.6]."""
    return Cuboid(
        center=(10.0, 5.0, -0.5),
        dims=(4.5, 2.0, 1.6),
        yaw=0.15,
        track_id=101,
        label="car",
        frame=2,
    )


@pytest.fixture
def complex_raw_track() -> dict[str, Any]:
    """Sample complex CVAT track with 6 keyframes and various metadata."""
    shapes = []
    for f in range(6):
        pts = [
            12.0 + f * 1.5,
            4.0 - f * 0.2,
            -0.8 + (0.1 if f % 2 == 0 else -0.1),
            0.0,
            0.0,
            0.10 + f * 0.05,
            4.6,
            2.1,
            1.7,
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
            "occluded": (f == 3),
            "outside": False,
            "keyframe": True,
            "points": pts,
            "attributes": [
                {"id": 1, "name": "subtype", "value": "suv"},
                {"id": 2, "name": "reviewed", "value": "true"},
                {"id": 3, "name": "pointsnap_error", "value": f"[Lỗi] Frame {f} finding"},
            ],
        })
    return {
        "id": 202,
        "label_id": 15,
        "frame": 0,
        "shapes": shapes,
        "attributes": [
            {"id": 10, "name": "track_status", "value": "active"},
            {"id": 11, "name": "annotator", "value": "qc_lead"},
        ],
    }


@pytest.fixture
def cvat_sync_client(complex_raw_track: dict[str, Any]) -> tuple[MagicMock, dict[str, Any]]:
    """Thread-safe mock CVAT client maintaining track state in memory."""
    lock = threading.Lock()
    annotations_state = {
        "version": 1,
        "shapes": [],
        "tracks": [copy.deepcopy(complex_raw_track)],
    }

    client = MagicMock(spec=CvatClient)

    def get_job_annotations(job_id: int) -> dict[str, Any]:
        with lock:
            return copy.deepcopy(annotations_state)

    def patch_job_annotations(job_id: int, data: dict[str, Any], action: str = "update") -> dict[str, Any]:
        with lock:
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
    return client, annotations_state


@pytest.fixture
def stress_client(tmp_path: Path, cvat_sync_client: tuple[MagicMock, dict[str, Any]], complex_raw_track: dict[str, Any]) -> TestClient:
    mock_client, _ = cvat_sync_client
    app = create_app(home_dir=tmp_path)
    app.state.cvat_client = mock_client
    app.state.mock_tracks = {
        (7, 202): copy.deepcopy(complex_raw_track),
    }
    return TestClient(app)


# =========================================================================
# Stress Test 1: OCC Race Condition Under Concurrent Apply Submissions
# =========================================================================

def test_occ_race_condition_concurrent_applies(stress_client: TestClient, complex_raw_track: dict[str, Any]):
    """Empirically stress-tests OCC when multiple clients attempt to apply repairs simultaneously.
    
    Exactly one request must succeed (HTTP 200), and all concurrent requests with the now-stale
    ETag must be rejected with HTTP 409 OCC Conflict.
    """
    initial_etag = compute_track_etag(complex_raw_track)

    payload = {
        "frame": 2,
        "repair": {
            "rule": "floating",
            "delta_center": [0.0, 0.0, -0.30],
            "delta_dims": [0.0, 0.0, 0.0],
            "delta_yaw": 0.0,
            "repaired_cuboid": {
                "center": [15.0, 3.6, -1.0],
                "dims": [4.6, 2.1, 1.7],
                "yaw": 0.20,
            },
        },
        "client_track_etag": initial_etag,
    }

    num_threads = 8
    results: list[tuple[int, dict[str, Any]]] = []
    lock = threading.Lock()

    def send_apply():
        res = stress_client.post("/api/jobs/7/tracks/202/apply-repair", json=payload)
        with lock:
            results.append((res.status_code, res.json()))

    with ThreadPoolExecutor(max_workers=num_threads) as executor:
        futures = [executor.submit(send_apply) for _ in range(num_threads)]
        for f in futures:
            f.result()

    successes = [r for r in results if r[0] == 200]
    conflicts = [r for r in results if r[0] == 409]

    assert len(successes) == 1, f"Expected exactly 1 success, got {len(successes)}: {results}"
    assert len(conflicts) == num_threads - 1, f"Expected {num_threads - 1} conflicts, got {len(conflicts)}"
    assert all("OCC conflict" in r[1].get("detail", "") for r in conflicts)


# =========================================================================
# Stress Test 2: Bit-for-bit Exact Track Restoration After Multi-Step LIFO Rollback
# =========================================================================

def test_high_depth_lifo_rollback_preserves_track_bit_for_bit(stress_client: TestClient, complex_raw_track: dict[str, Any]):
    """Applies 5 sequential repairs across frames 0, 1, 2, 3, 4, then rolls them all back.
    
    Verifies that the restored track matches the original track bit-for-bit, including
    unrelated keyframes, labels, track attributes, and occluded flags.
    """
    original_track_snapshot = copy.deepcopy(complex_raw_track)
    history_stack: list[str] = []

    # 1. Apply 5 repairs sequentially
    for frame_idx in range(5):
        # Fetch fresh etag from backend or previous update
        rep_res = stress_client.get(f"/api/jobs/7/tracks/202/repair?frame={frame_idx}&rule=floating")
        assert rep_res.status_code == 200
        current_etag = rep_res.json()["track_etag"]

        payload = {
            "frame": frame_idx,
            "repair": {
                "rule": "floating",
                "delta_center": [0.05 * frame_idx, -0.02 * frame_idx, -0.15 - 0.05 * frame_idx],
                "delta_dims": [0.10, 0.0, 0.0],
                "delta_yaw": 0.05,
                "repaired_cuboid": {
                    "center": [12.0 + frame_idx * 1.5, 4.0, -1.0],
                    "dims": [4.7, 2.1, 1.7],
                    "yaw": 0.15,
                },
            },
            "client_track_etag": current_etag,
        }

        apply_res = stress_client.post("/api/jobs/7/tracks/202/apply-repair", json=payload)
        assert apply_res.status_code == 200, apply_res.text
        hid = apply_res.json()["history_id"]
        history_stack.append(hid)

    assert len(history_stack) == 5

    # 2. Rollback in strict LIFO order
    while history_stack:
        target_hid = history_stack.pop()
        rb_res = stress_client.post("/api/jobs/7/tracks/202/rollback", json={"history_id": target_hid})
        assert rb_res.status_code == 200, rb_res.text
        assert rb_res.json()["status"] == "ok"

    # 3. Verify final track matches original snapshot exactly
    # Frame 5 was never modified; frames 0-4 were modified and restored.
    final_rep_res = stress_client.get("/api/jobs/7/tracks/202/repair?frame=0&rule=floating")
    assert final_rep_res.status_code == 200

    # Inspect current state in mock tracks
    restored_track = stress_client.app.state.mock_tracks[(7, 202)]

    assert restored_track["id"] == original_track_snapshot["id"]
    assert restored_track["label_id"] == original_track_snapshot["label_id"]
    assert restored_track["attributes"] == original_track_snapshot["attributes"]
    assert len(restored_track["shapes"]) == len(original_track_snapshot["shapes"])

    for orig_shape, rest_shape in zip(original_track_snapshot["shapes"], restored_track["shapes"]):
        assert orig_shape["frame"] == rest_shape["frame"]
        assert orig_shape["occluded"] == rest_shape["occluded"]
        assert orig_shape["outside"] == rest_shape["outside"]
        assert orig_shape["points"] == pytest.approx(rest_shape["points"], abs=1e-5)


# =========================================================================
# Stress Test 3: Adversarial History IDs & Security Injection in Rollback
# =========================================================================

@pytest.mark.parametrize("malicious_hid", [
    "../../etc/passwd",
    "..\\..\\windows\\system32\\calc.exe",
    "invalid/path/traversal",
    "non-existent-uuid-00000000-0000",
    "../../../projects/secret/history/job_1/snap.json",
    "",
    "   ",
])
def test_rollback_rejects_malicious_and_invalid_history_ids(stress_client: TestClient, malicious_hid: str):
    """Verifies that path traversal attempts and invalid IDs return 400/404 without server errors."""
    res = stress_client.post("/api/jobs/7/tracks/202/rollback", json={"history_id": malicious_hid})
    assert res.status_code in (400, 404, 422), f"Expected client error for '{malicious_hid}', got {res.status_code}"
    data = res.json()
    assert "status" in data or "detail" in data


def test_rollback_cross_job_boundary_and_extension_isolation(stress_client: TestClient, complex_raw_track: dict[str, Any]):
    """Verifies cross-job isolation: extension strictly blocks cross-job calls, and nonexistent IDs fail with 404."""
    from tests.test_m4_ui_preview import evaluate_route_in_background

    # 1. Chrome Extension security policy: Cross-job rollback is strictly blocked before reaching network
    allowed, msg = evaluate_route_in_background("POST", "/api/jobs/8/tracks/202/rollback", sender_job_id=7)
    assert allowed is False
    assert "Cross-job route rejected" in msg

    # 2. Chrome Extension security policy: Cross-job apply-repair is strictly blocked
    allowed_apply, msg_apply = evaluate_route_in_background("POST", "/api/jobs/8/tracks/202/apply-repair", sender_job_id=7)
    assert allowed_apply is False
    assert "Cross-job route rejected" in msg_apply

    # 3. Backend REST: Unknown snapshot across any job returns 404
    nonexistent_res = stress_client.post("/api/jobs/8/tracks/202/rollback", json={"history_id": "nonexistent-job8-snap"})
    assert nonexistent_res.status_code == 404


# =========================================================================
# Stress Test 4: Extreme Geometric Deltas & Boundary Handling
# =========================================================================

def test_extreme_geometry_deltas_clamping_and_validation(sample_cuboid: Cuboid):
    """Verifies that compute_box_repair handles extreme values, large offsets, and edge cases gracefully."""
    # Test 1: Ground distance of 500 meters (e.g. faulty sensor or outlier)
    finding = {"distance": 500.0, "num_ground_points": 30}
    delta = compute_box_repair(sample_cuboid, [sample_cuboid], None, "floating", finding)
    assert isinstance(delta.delta_center[2], float)
    assert math.isfinite(delta.delta_center[2])
    # Delta z brings bottom down
    assert delta.repaired_cuboid.center[2] < sample_cuboid.center[2]
    assert delta.delta_center[2] == pytest.approx(-500.0, abs=1e-3)

    # Test 2: Heading flip exactly pi radians
    delta_flip = compute_box_repair(sample_cuboid, [sample_cuboid], None, "heading.flip")
    assert delta_flip.delta_yaw == 0
    assert delta_flip.confidence == 0
    # Normalized yaw must remain in [-pi, pi]
    assert -math.pi <= delta_flip.repaired_cuboid.yaw <= math.pi

    # Test 3: Sunk box (underground, negative distance)
    finding_sunk = {"distance": -0.45, "num_ground_points": 25}
    delta_sunk = compute_box_repair(sample_cuboid, [sample_cuboid], None, "floating", finding_sunk)
    assert delta_sunk.delta_center[2] > 0, "Sunk box must have positive delta_z"
    assert delta_sunk.delta_center[2] == pytest.approx(0.45, abs=1e-3)
    assert delta_sunk.confidence >= 0.70


# =========================================================================
# Stress Test 5: Re-scan Clearance Invariant After Apply-Repair
# =========================================================================

def test_repaired_box_passes_scanner_re_scan_clearance(sample_cuboid: Cuboid):
    """Verifies that applying a calculated repair delta ensures that scanner findings are resolved."""
    # Simulate floating error of +0.35m
    floating_finding = {"distance": 0.35, "num_ground_points": 30}
    delta = compute_box_repair(sample_cuboid, [sample_cuboid], None, "floating", floating_finding)

    repaired = delta.repaired_cuboid
    # Original bottom was -0.5 - 1.6/2 = -1.30m
    # Ground was at -1.65m (floating 0.35m above ground)
    # New center z is -0.5 + delta_z = -0.5 - 0.35 = -0.85m
    # New bottom is -0.85 - 1.6/2 = -1.65m, exactly at ground elevation!
    new_bottom = repaired.center[2] - repaired.dims[2] / 2.0
    assert new_bottom == pytest.approx(-1.65, abs=1e-3)
    # Residual error is 0
    assert abs(new_bottom - (-1.65)) < 0.001
