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




def test_writer_patch_track_keyframe_occ_stale_rejection(complex_multiframe_track: dict[str, Any]):
    """Low-level writer patch_track_keyframe strictly raises OCCConflictError when client_etag is stale."""
    client_mock = MagicMock(spec=CvatClient)
    client_mock.get_job_annotations.return_value = {
        "tracks": [copy.deepcopy(complex_multiframe_track)]
    }

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




# =========================================================================
# Scenario 2: Partial & Malformed Track Payloads
# =========================================================================






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




# =========================================================================
# Scenario 3: Rapid Sequential Updates & ETag Recomputation
# =========================================================================
