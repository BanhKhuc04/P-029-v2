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







# =========================================================================
# 2. Rollback on Empty History, Invalid history_id, and Corrupt Snapshots
# =========================================================================









# =========================================================================
# 3. Edge-Case Box Repairs: Zero Dims, Extreme Offsets, Negative Coords
# =========================================================================













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
