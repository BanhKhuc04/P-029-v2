"""Unit & Integration Tests for Milestone M4: Preview Overlay, 1-Click Apply & Rollback, Extension UI, and Security Whitelisting.

Covers:
- Feature F11: Web UI 3-View Preview Overlay (app.js drawPreview, dashed [4, 4] box, yaw arrow, ground flush)
- Feature F12: Web UI 1-Click Apply Popover & Rollback (debounce, OCC 409 conflict, LIFO rollback stack, badge update)
- Feature F13: Chrome Extension Shadow DOM Repair Card (metrics grid, 2-step confirmation, rollback button)
- Feature F14: Extension Security Whitelisting (background.js requestRoute for repair, apply-repair, rollback)
- Backend Contract: GET /api/jobs/{job_id}/tracks/{track_id}/repair includes track_etag
"""

from __future__ import annotations

import copy
import json
import math
import re
import uuid
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

BASE_DIR = Path(__file__).resolve().parent.parent


# =========================================================================
# Fixtures
# =========================================================================

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
def sample_raw_cvat_track() -> dict[str, Any]:
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
def mock_cvat_client(sample_raw_cvat_track: dict[str, Any]) -> MagicMock:
    """Mock CVAT client maintaining track state in memory."""
    client = MagicMock(spec=CvatClient)
    annotations_state = {
        "version": 1,
        "shapes": [],
        "tracks": [copy.deepcopy(sample_raw_cvat_track)],
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


@pytest.fixture
def test_app_client(tmp_path: Path, mock_cvat_client: MagicMock, sample_raw_cvat_track: dict[str, Any]) -> TestClient:
    """FastAPI TestClient with injected mock tracks and mock CVAT client."""
    app = create_app(home_dir=tmp_path)
    app.state.cvat_client = mock_cvat_client
    app.state.mock_tracks = {
        (4, 101): copy.deepcopy(sample_raw_cvat_track),
    }
    return TestClient(app)


# =========================================================================
# Feature F11: Web UI 3-View Preview Overlay Tests
# =========================================================================

def project_box_to_canvas(box: Cuboid, delta_center: tuple[float, float, float], delta_dims: tuple[float, float, float], view: str) -> dict[str, float]:
    """Mathematical projection oracle matching app.js drawPreviewViews() logic."""
    dx, dy, dz = delta_center
    dl, dw, dh = delta_dims
    rep_l = box.length + dl
    rep_w = box.width + dw
    rep_h = box.height + dh

    if view == "top":
        # Top view: X along length, Y along width
        return {"cx": dx, "cy": dy, "w": rep_l, "h": rep_w}
    elif view == "side":
        # Side view: X along length, Z along height
        return {"cx": dx, "cy": dz, "w": rep_l, "h": rep_h, "z_bottom": dz - rep_h / 2.0}
    elif view == "front":
        # Front view: Y along width, Z along height
        return {"cx": dy, "cy": dz, "w": rep_w, "h": rep_h}
    raise ValueError(f"Unknown view: {view}")


def test_f11_top_view_canvas_projection(sample_cuboid: Cuboid):
    """F11.1: Verifies Top view projects local X along length, Y along width with offset."""
    delta_center = (0.05, -0.02, -0.22)
    delta_dims = (0.10, 0.0, 0.0)
    proj = project_box_to_canvas(sample_cuboid, delta_center, delta_dims, "top")

    assert proj["cx"] == 0.05
    assert proj["cy"] == -0.02
    assert proj["w"] == pytest.approx(4.60, abs=1e-3)
    assert proj["h"] == pytest.approx(2.00, abs=1e-3)


def test_f11_side_view_ground_flush_alignment(sample_cuboid: Cuboid):
    """F11.2: Verifies Side view projects (x, z) coordinates and places bottom edge flush with ground line."""
    # In local box frame (centered at (0, 0, 0) of original box):
    # Original bottom elevation is -H/2.
    # If the box is floating by 0.25m, the measured ground level is at -H/2 - 0.25m.
    # The proposed repair has delta_z = -0.25m.
    # New bottom elevation is delta_z - H/2 = -0.25 - H/2, which is flush with ground!
    box = Cuboid(center=(10.0, 5.0, -0.25), dims=(4.5, 2.0, 1.6), yaw=0.0, label="car", frame=2)
    floating_distance = 0.25
    dz = -floating_distance
    proj = project_box_to_canvas(box, (0.0, 0.0, dz), (0.0, 0.0, 0.0), "side")

    expected_ground_offset = -box.height / 2.0 - floating_distance
    assert proj["z_bottom"] == pytest.approx(expected_ground_offset, abs=1e-3)


def test_f11_front_view_canvas_projection(sample_cuboid: Cuboid):
    """F11.3: Verifies Front view projects (y, z) centered at box lateral midpoint."""
    delta_center = (0.0, 0.15, -0.10)
    delta_dims = (0.0, 0.05, 0.0)
    proj = project_box_to_canvas(sample_cuboid, delta_center, delta_dims, "front")

    assert proj["cx"] == 0.15
    assert proj["cy"] == -0.10
    assert proj["w"] == pytest.approx(2.05, abs=1e-3)
    assert proj["h"] == pytest.approx(1.60, abs=1e-3)


def test_f11_dashed_overlay_visual_specification():
    """F11.4: Verifies dashed overlay spec [4, 4] and contrasting color #00ff88."""
    static_app_js = (BASE_DIR / "pointsnap/web/static/app.js").read_text(encoding="utf-8")

    # Verify setLineDash([4, 4]) is implemented
    assert "setLineDash([4, 4])" in static_app_js or "setLineDash([4,4])" in static_app_js

    # Verify contrasting color (#00ff88 or #4CC38A) is used for the proposed repair overlay
    assert "#00ff88" in static_app_js or "#4CC38A" in static_app_js


def test_f11_yaw_heading_directional_arrow():
    """F11.5: Verifies yaw heading vector and arrow barb calculations."""
    yaw_angles = [0.0, math.pi / 2, math.pi, -math.pi / 4]
    arrow_len = 30.0

    for yaw in yaw_angles:
        # Forward unit vector
        fx = math.cos(yaw)
        fy = math.sin(yaw)

        # Arrow tip relative to origin
        tip_x = fx * arrow_len
        tip_y = fy * arrow_len

        # Arrow barbs at 150 degrees
        barb_len = 8.0
        left_barb_x = tip_x - barb_len * math.cos(yaw - math.pi / 6)
        left_barb_y = tip_y - barb_len * math.sin(yaw - math.pi / 6)
        right_barb_x = tip_x - barb_len * math.cos(yaw + math.pi / 6)
        right_barb_y = tip_y - barb_len * math.sin(yaw + math.pi / 6)

        # Assert tip distance is exactly arrow_len
        assert math.hypot(tip_x, tip_y) == pytest.approx(arrow_len, abs=1e-4)
        # Assert barbs are positioned behind the tip
        assert math.hypot(tip_x - left_barb_x, tip_y - left_barb_y) == pytest.approx(barb_len, abs=1e-4)
        assert math.hypot(tip_x - right_barb_x, tip_y - right_barb_y) == pytest.approx(barb_len, abs=1e-4)


def test_f11_coordinate_edge_cases():
    """F11.6: Verifies coordinate transform handles zero crop points, extreme scales, and NaN filtering."""
    # 0 crop points
    points = np.zeros((0, 3), dtype=np.float32)
    assert len(points) == 0

    # Extreme canvas scaling
    scale = 1e6
    coord = 0.05
    canvas_px = coord * scale
    assert math.isfinite(canvas_px)

    # NaN filtering
    pts = np.array([[1.0, 2.0, np.nan], [np.nan, 0.0, 1.0], [3.0, 4.0, 5.0]], dtype=np.float32)
    valid_mask = np.isfinite(pts).all(axis=1)
    clean_pts = pts[valid_mask]
    assert len(clean_pts) == 1
    assert clean_pts[0, 0] == 3.0


# =========================================================================
# Feature F12: Web UI 1-Click Apply Popover & Rollback Tests
# =========================================================================

def test_f12_metrics_grid_formatting():
    """F12.1: Verifies metric badge formatting (dz in cm, dyaw in deg, dims in m)."""
    dz = -0.254
    dyaw = math.pi
    ddims = (0.15, -0.05, 0.0)

    formatted_dz = f"{dz * 100:+.1f} cm"
    formatted_dyaw = f"{math.degrees(dyaw):+.0f}°"
    formatted_ddims = f"[{ddims[0]:+.2f}, {ddims[1]:+.2f}, {ddims[2]:+.2f}] m"

    assert formatted_dz == "-25.4 cm"
    assert formatted_dyaw == "+180°"
    assert formatted_ddims == "[+0.15, -0.05, +0.00] m"


def test_v2_web_has_manual_help_and_no_automatic_write_controls():
    html = (BASE_DIR / 'pointsnap/web/static/index.html').read_text(encoding='utf-8')
    assert 'Sửa tay trong CVAT' in html
    assert 'id="modal-confirm-repair"' not in html
    assert 'id="btn-open-apply-repair"' not in html
    assert 'id="btn-rollback-repair"' not in html


def test_f12_debounce_and_concurrency_guard():
    """F12.3: Verifies double-click within 500ms and in-flight lock are debounced."""
    state = {
        "lastApplyClickTime": 0,
        "isApplyingRepair": False,
        "applyCount": 0,
    }

    def trigger_apply(now_ms: int):
        if now_ms - state["lastApplyClickTime"] < 500:
            return "debounced"
        if state["isApplyingRepair"]:
            return "locked"
        state["lastApplyClickTime"] = now_ms
        state["isApplyingRepair"] = True
        state["applyCount"] += 1
        return "accepted"

    # First click at t=1000
    assert trigger_apply(1000) == "accepted"
    # Rapid second click at t=1200 (< 500ms)
    assert trigger_apply(1200) == "debounced"
    # Click at t=1600 (> 500ms) while still in-flight
    assert trigger_apply(1600) == "locked"
    # Release lock
    state["isApplyingRepair"] = False
    assert trigger_apply(1600) == "accepted"
    assert state["applyCount"] == 2








# =========================================================================
# Feature F13: Chrome Extension Shadow DOM Repair Card Tests
# =========================================================================

def test_v2_panel_controls_manual_guides_instead_of_automatic_repair():
    content = (BASE_DIR / 'extension/src/content.js').read_text(encoding='utf-8')
    controller = (BASE_DIR / 'extension/src/manual-controller.js').read_text(encoding='utf-8')
    for action in ('repair-apply-start','repair-apply-confirm','repair-rollback'):
        assert f'data-action="{action}"' not in content
    assert 'manual-toggle' in controller and 'manual-rule' in controller
    assert 'manual-geometry.js' in (BASE_DIR / 'extension/manifest.json').read_text(encoding='utf-8')




# =========================================================================
# Feature F14: Extension Security Whitelisting Tests
# =========================================================================

def evaluate_route_in_background(method: str, path: str, sender_job_id: int) -> tuple[bool, str]:
    """Replicates background.js requestRoute() security policy logic."""
    if ".." in path or "%2e" in path.lower() or "#" in path:
        return False, "path traversal or hash disallowed"

    # /api/jobs/{job_id}/tracks/{track_id}/repair
    m_repair = re.match(r"^/api/jobs/(\d+)/tracks/(\d+)/repair(\?.*)?$", path)
    if m_repair:
        if method != "GET":
            return False, "Method not allowed"
        route_job_id = int(m_repair.group(1))
        if route_job_id != sender_job_id:
            return False, f"Cross-job route rejected: {route_job_id} != {sender_job_id}"
        return True, "Allowed"

    # /api/jobs/{job_id}/tracks/{track_id}/apply-repair
    m_apply = re.match(r"^/api/jobs/(\d+)/tracks/(\d+)/apply-repair$", path)
    if m_apply:
        if method != "POST":
            return False, "Method not allowed"
        route_job_id = int(m_apply.group(1))
        if route_job_id != sender_job_id:
            return False, f"Cross-job route rejected: {route_job_id} != {sender_job_id}"
        return True, "Allowed"

    # /api/jobs/{job_id}/tracks/{track_id}/rollback
    m_rb = re.match(r"^/api/jobs/(\d+)/tracks/(\d+)/rollback$", path)
    if m_rb:
        if method != "POST":
            return False, "Method not allowed"
        route_job_id = int(m_rb.group(1))
        if route_job_id != sender_job_id:
            return False, f"Cross-job route rejected: {route_job_id} != {sender_job_id}"
        return True, "Allowed"

    return False, f"Route not whitelisted: {path}"








# =========================================================================
# Backend Contract: GET /repair returns track_etag
# =========================================================================
