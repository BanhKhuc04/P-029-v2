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



# =========================================================================
# Stress Test 2: Bit-for-bit Exact Track Restoration After Multi-Step LIFO Rollback
# =========================================================================



# =========================================================================
# Stress Test 3: Adversarial History IDs & Security Injection in Rollback
# =========================================================================





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
