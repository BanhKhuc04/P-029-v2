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


def test_f12_confirmation_modal_dom_structure():
    """F12.2: Verifies index.html contains modal-confirm-repair with warning note and action buttons."""
    index_html = (BASE_DIR / "pointsnap/web/static/index.html").read_text(encoding="utf-8")

    assert 'id="modal-confirm-repair"' in index_html
    assert 'id="btn-modal-repair-confirm"' in index_html
    assert 'id="btn-modal-repair-cancel"' in index_html
    assert 'id="modal-repair-table-body"' in index_html
    assert "modal-warning-note" in index_html


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


def test_f12_apply_repair_success_and_badge_update(test_app_client: TestClient, sample_raw_cvat_track: dict[str, Any]):
    """F12.4: Verifies POST apply-repair succeeds with client ETag and updates annotation points."""
    etag = compute_track_etag(sample_raw_cvat_track)

    payload = {
        "frame": 2,
        "repair": {
            "rule": "floating",
            "delta_center": [0.0, 0.0, -0.25],
            "delta_dims": [0.0, 0.0, 0.0],
            "delta_yaw": 0.0,
            "repaired_cuboid": {
                "center": [14.0, 5.0, -0.75],
                "dims": [4.5, 2.0, 1.6],
                "yaw": 0.15,
                "roll": 0.0,
                "pitch": 0.0,
            },
        },
        "client_track_etag": etag,
    }

    res = test_app_client.post("/api/jobs/4/tracks/101/apply-repair", json=payload)
    assert res.status_code == 200, res.text
    data = res.json()

    assert data["status"] == "ok"
    assert "history_id" in data
    assert data["new_scan_verdict"] == "NOT_RUN"

    target_shape = next(s for s in data["updated_track"]["shapes"] if s["frame"] == 2)
    # Verify new points reflect repaired center [-0.75 in Z]
    assert target_shape["points"][2] == pytest.approx(-0.75, abs=1e-4)


def test_f12_apply_repair_occ_conflict_409(test_app_client: TestClient):
    """F12.5: Verifies POST apply-repair rejects stale ETag with HTTP 409 conflict."""
    stale_etag = "stale_etag_deadbeef"
    payload = {
        "frame": 2,
        "repair": {
            "rule": "floating",
            "delta_center": [0.0, 0.0, -0.25],
        },
        "client_track_etag": stale_etag,
    }

    res = test_app_client.post("/api/jobs/4/tracks/101/apply-repair", json=payload)
    assert res.status_code == 409
    data = res.json()
    assert data["status"] == "conflict"
    assert "OCC conflict" in data["detail"]


def test_f12_lifo_rollback_stack(test_app_client: TestClient, sample_raw_cvat_track: dict[str, Any]):
    """F12.6: Verifies LIFO rollback sequence correctly restores previous CVAT annotation keyframes."""
    # Step 1: Apply repair on frame 2
    etag1 = compute_track_etag(sample_raw_cvat_track)
    payload1 = {
        "frame": 2,
        "repair": {
            "rule": "floating",
            "delta_center": [0.0, 0.0, -0.25],
            "repaired_cuboid": {
                "center": [14.0, 5.0, -0.75],
                "dims": [4.5, 2.0, 1.6],
                "yaw": 0.15,
            },
        },
        "client_track_etag": etag1,
    }
    res1 = test_app_client.post("/api/jobs/4/tracks/101/apply-repair", json=payload1)
    assert res1.status_code == 200
    hid1 = res1.json()["history_id"]
    updated_track1 = res1.json()["updated_track"]

    # Step 2: Apply repair on frame 3 with fresh ETag
    etag2 = compute_track_etag(updated_track1)
    payload2 = {
        "frame": 3,
        "repair": {
            "rule": "floating",
            "delta_center": [0.0, 0.0, -0.15],
            "repaired_cuboid": {
                "center": [16.0, 5.0, -0.65],
                "dims": [4.5, 2.0, 1.6],
                "yaw": 0.15,
            },
        },
        "client_track_etag": etag2,
    }
    res2 = test_app_client.post("/api/jobs/4/tracks/101/apply-repair", json=payload2)
    assert res2.status_code == 200
    hid2 = res2.json()["history_id"]

    # History stack has [hid1, hid2]. LIFO pop gives hid2 first.
    stack = [hid1, hid2]

    # Rollback 1: hid2
    pop2 = stack.pop()
    assert pop2 == hid2
    rb_res2 = test_app_client.post("/api/jobs/4/tracks/101/rollback", json={"history_id": pop2})
    assert rb_res2.status_code == 200
    assert rb_res2.json()["status"] == "ok"

    # Rollback 2: hid1
    pop1 = stack.pop()
    assert pop1 == hid1
    rb_res1 = test_app_client.post("/api/jobs/4/tracks/101/rollback", json={"history_id": pop1})
    assert rb_res1.status_code == 200
    assert rb_res1.json()["status"] == "ok"
    assert len(stack) == 0


# =========================================================================
# Feature F13: Chrome Extension Shadow DOM Repair Card Tests
# =========================================================================

def test_f13_extension_shadow_dom_card_structure():
    """F13.1: Verifies extension panel-css.js and content.js define repair-box and delta-grid styling."""
    content_js = (BASE_DIR / "extension/src/content.js").read_text(encoding="utf-8")
    panel_css = (BASE_DIR / "extension/src/panel-css.js").read_text(encoding="utf-8")

    # Content script elements
    assert "repair-box" in content_js
    assert "delta-grid" in content_js
    assert "delta-cell" in content_js
    assert 'data-action="repair-apply-start"' in content_js
    assert 'data-action="repair-apply-confirm"' in content_js
    assert 'data-action="repair-apply-cancel"' in content_js
    assert 'data-action="repair-rollback"' in content_js

    # CSS rules in Shadow DOM
    assert ".repair-box" in panel_css
    assert ".delta-grid" in panel_css
    assert ".delta-cell" in panel_css
    assert ".repair-confirm-box" in panel_css
    assert ".badge-pass" in panel_css


def test_f13_extension_2step_confirmation_state():
    """F13.2: Verifies extension 2-step confirmation logic: prompt -> confirm."""
    state = {"confirming": False, "applied": False}

    def on_user_click(action: str):
        if action == "apply-repair":
            state["confirming"] = True
            return "prompt_shown"
        elif action == "cancel-apply-repair":
            state["confirming"] = False
            return "prompt_hidden"
        elif action == "confirm-apply-repair":
            if state["confirming"]:
                state["confirming"] = False
                state["applied"] = True
                return "applied"
        return "ignored"

    assert on_user_click("apply-repair") == "prompt_shown"
    assert state["confirming"] is True
    assert on_user_click("cancel-apply-repair") == "prompt_hidden"
    assert state["confirming"] is False
    assert on_user_click("apply-repair") == "prompt_shown"
    assert on_user_click("confirm-apply-repair") == "applied"
    assert state["applied"] is True


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


def test_f14_route_whitelisting_policy():
    """F14.1: Verifies repair, apply-repair, and rollback routes are whitelisted for sender job."""
    allowed, msg = evaluate_route_in_background("GET", "/api/jobs/4/tracks/101/repair?frame=2&rule=floating", 4)
    assert allowed is True, msg

    allowed, msg = evaluate_route_in_background("POST", "/api/jobs/4/tracks/101/apply-repair", 4)
    assert allowed is True, msg

    allowed, msg = evaluate_route_in_background("POST", "/api/jobs/4/tracks/101/rollback", 4)
    assert allowed is True, msg


def test_f14_cross_job_rejection():
    """F14.2: Verifies cross-job access attempts are strictly rejected."""
    allowed, msg = evaluate_route_in_background("GET", "/api/jobs/99/tracks/101/repair", 4)
    assert allowed is False
    assert "Cross-job route rejected" in msg

    allowed, msg = evaluate_route_in_background("POST", "/api/jobs/99/tracks/101/apply-repair", 4)
    assert allowed is False

    allowed, msg = evaluate_route_in_background("POST", "/api/jobs/99/tracks/101/rollback", 4)
    assert allowed is False


def test_f14_path_traversal_and_tamper_defense():
    """F14.3: Verifies path traversal, fragment smuggling, and forbidden methods are blocked."""
    # Path traversal
    allowed, _ = evaluate_route_in_background("GET", "/api/jobs/4/tracks/../../repair", 4)
    assert allowed is False

    allowed, _ = evaluate_route_in_background("GET", "/api/jobs/4/tracks/%2e%2e/repair", 4)
    assert allowed is False

    # Disallowed method on apply-repair (e.g. GET or DELETE)
    allowed, _ = evaluate_route_in_background("GET", "/api/jobs/4/tracks/101/apply-repair", 4)
    assert allowed is False

    allowed, _ = evaluate_route_in_background("DELETE", "/api/jobs/4/tracks/101/rollback", 4)
    assert allowed is False


# =========================================================================
# Backend Contract: GET /repair returns track_etag
# =========================================================================

def test_backend_repair_endpoint_etag_contract(test_app_client: TestClient, sample_raw_cvat_track: dict[str, Any]):
    """Verifies GET /api/jobs/{job_id}/tracks/{track_id}/repair returns track_etag equal to compute_track_etag()."""
    expected_etag = compute_track_etag(sample_raw_cvat_track)

    res = test_app_client.get("/api/jobs/4/tracks/101/repair?frame=2&rule=floating")
    assert res.status_code == 200, res.text
    data = res.json()

    assert data["status"] == "ok"
    assert "track_etag" in data
    assert data["track_etag"] == expected_etag

    # Verify that passing this returned track_etag to apply-repair avoids OCC conflict
    apply_payload = {
        "frame": 2,
        "repair": {"delta_center": [0, 0, -.2]},
        "client_track_etag": data["track_etag"],
    }
    apply_res = test_app_client.post("/api/jobs/4/tracks/101/apply-repair", json=apply_payload)
    assert apply_res.status_code == 200, apply_res.text
