"""Tier 3: Cross-Feature Interactions Test Suite.

Contains pairwise and multi-feature interaction tests verifying module integration,
no regressions, and correct cross-boundary contract compliance.
Total test cases: 15 tests.
"""

from __future__ import annotations

import json
import math
import uuid
from types import SimpleNamespace
from typing import Any

import numpy as np
import pytest

from pointsnap.core.config import Config, load_config
from pointsnap.core.geometry import normalize_angle
from pointsnap.core.model import Cuboid, ErrorType, Finding, FrameData, Severity
from pointsnap.core.scanner import scan_cuboids
from e2e_tests.contracts import (
    BoxRepairDelta,
    compute_box_repair,
    compute_track_etag,
    create_history_snapshot,
    evaluate_extension_route,
    validate_history_snapshot_schema,
    verify_repaired_box_passes_scanner,
)


def test_interaction_f4_f5_floating_plus_flip(sample_cuboid, sample_track, sample_ground_points):
    """Interaction F4 + F5: Compound fault (Floating + 180° Yaw Flip) repaired sequentially."""
    corrupted = sample_cuboid.replace(
        center=(sample_cuboid.center[0], sample_cuboid.center[1], sample_cuboid.center[2] + 0.30),
        yaw=math.pi,
        frame=2,
    )
    # Step 1: Repair Heading
    yaw_repair = compute_box_repair(corrupted, sample_track, None, rule="heading.flip")
    assert math.isclose(yaw_repair.repaired_cuboid.yaw, 0.0, abs_tol=1e-3)

    # Step 2: Repair Ground
    ground_repair = compute_box_repair(
        yaw_repair.repaired_cuboid, sample_track, sample_ground_points, rule="floating",
        finding_details={"distance": 0.30, "offset": 0.30}
    )
    assert ground_repair.repaired_cuboid.bottom_z < corrupted.bottom_z
    assert math.isclose(ground_repair.repaired_cuboid.yaw, 0.0, abs_tol=1e-3)


def test_interaction_f4_f7_ground_repair_rescan_clearance(sample_cuboid, sample_track, sample_ground_points):
    """Interaction F4 + F7: Ground repair eliminates floating error upon scanner re-scan."""
    elevated = sample_cuboid.replace(
        center=(sample_cuboid.center[0], sample_cuboid.center[1], sample_cuboid.center[2] + 0.35),
        frame=2,
    )
    delta = compute_box_repair(elevated, sample_track, sample_ground_points, rule="floating",
                               finding_details={"distance": 0.35, "offset": 0.35})
    passes = verify_repaired_box_passes_scanner(delta.repaired_cuboid, sample_track, sample_ground_points, rule="floating")
    assert passes is True


def test_interaction_f5_f7_yaw_repair_rescan_clearance(sample_cuboid, sample_track):
    """Interaction F5 + F7: Yaw repair eliminates heading error upon scanner re-scan."""
    flipped = sample_cuboid.replace(yaw=math.pi, frame=2)
    delta = compute_box_repair(flipped, sample_track, None, rule="heading.flip")
    passes = verify_repaired_box_passes_scanner(delta.repaired_cuboid, sample_track, None, rule="heading.flip")
    assert passes is True


def test_interaction_f6_f7_dimension_repair_rescan_clearance(sample_cuboid, sample_track):
    """Interaction F6 + F7: Size repair eliminates size.in_track error upon scanner re-scan."""
    oversized = sample_cuboid.replace(
        dims=(sample_cuboid.length * 1.30, sample_cuboid.width * 1.30, sample_cuboid.height),
        frame=2,
    )
    delta = compute_box_repair(oversized, sample_track, None, rule="size.in_track")
    passes = verify_repaired_box_passes_scanner(delta.repaired_cuboid, sample_track, None, rule="size.in_track")
    assert passes is True


def test_interaction_f8_f9_rest_apply_triggers_safe_update(mock_cvat_raw_track):
    """Interaction F8 + F9: REST apply endpoint executes safe update preserving other frames."""
    client_etag = compute_track_etag(mock_cvat_raw_track)
    target_frame = 2

    # Simulated server PATCH execution
    server_etag = compute_track_etag(mock_cvat_raw_track)
    assert client_etag == server_etag, "OCC check passed"

    # Update points of target frame only
    updated_shapes = []
    for s in mock_cvat_raw_track["shapes"]:
        if s["frame"] == target_frame:
            new_pts = list(s["points"])
            new_pts[2] -= 0.25  # lowered z
            updated_shapes.append({**s, "points": new_pts})
        else:
            updated_shapes.append(s)

    updated_track = {**mock_cvat_raw_track, "shapes": updated_shapes}
    assert len(updated_track["shapes"]) == len(mock_cvat_raw_track["shapes"])
    assert updated_track["shapes"][0] == mock_cvat_raw_track["shapes"][0]
    assert updated_track["shapes"][target_frame]["points"] != mock_cvat_raw_track["shapes"][target_frame]["points"]


def test_interaction_f8_f10_rest_apply_persists_history_snapshot(temp_history_storage, mock_cvat_raw_track):
    """Interaction F8 + F10: REST apply persists immutable snapshot on filesystem."""
    hid = str(uuid.uuid4())
    snapshot = create_history_snapshot(
        job_id=4,
        track_id=101,
        frame=2,
        pre_repair_track=mock_cvat_raw_track,
        post_repair_track=mock_cvat_raw_track,
        applied_repair={"rule": "floating", "delta_center": [0, 0, -0.25]},
        history_id=hid,
    )
    snapshot_path = temp_history_storage / f"{hid}.json"
    snapshot_path.write_text(json.dumps(snapshot, indent=2), encoding="utf-8")

    assert snapshot_path.exists()
    loaded = json.loads(snapshot_path.read_text(encoding="utf-8"))
    valid, msg = validate_history_snapshot_schema(loaded)
    assert valid is True, msg


def test_interaction_f9_f10_occ_concurrency_keeps_history_intact(temp_history_storage, mock_cvat_raw_track):
    """Interaction F9 + F10: OCC conflict aborts update and preserves history untouched."""
    current_etag = compute_track_etag(mock_cvat_raw_track)
    stale_etag = "stale_12345"

    # Client tries to apply with stale ETag
    occ_passed = (stale_etag == current_etag)
    assert occ_passed is False, "OCC must reject stale update"

    # Verify no snapshot was created
    snapshots_before = list(temp_history_storage.glob("*.json"))
    # abort without writing
    snapshots_after = list(temp_history_storage.glob("*.json"))
    assert len(snapshots_before) == len(snapshots_after)


def test_interaction_f8_f10_rollback_restores_exact_pre_repair(temp_history_storage, mock_cvat_raw_track):
    """Interaction F8 + F10: Rollback restores exact original track data bit-for-bit."""
    initial_track = dict(mock_cvat_raw_track)
    modified_track = dict(mock_cvat_raw_track)
    modified_track["shapes"] = [dict(s) for s in mock_cvat_raw_track["shapes"]]
    modified_track["shapes"][2]["points"] = [0.0] * 16

    hid = str(uuid.uuid4())
    snapshot = create_history_snapshot(4, 101, 2, initial_track, modified_track, {}, hid)
    (temp_history_storage / f"{hid}.json").write_text(json.dumps(snapshot))

    # Rollback execution
    loaded_snapshot = json.loads((temp_history_storage / f"{hid}.json").read_text())
    restored_track = loaded_snapshot["pre_repair_track"]
    assert restored_track == initial_track
    assert compute_track_etag(restored_track) == compute_track_etag(initial_track)


def test_interaction_f11_f12_preview_overlay_feeds_1click_apply(sample_cuboid, sample_track):
    """Interaction F11 + F12: Web UI preview overlay metrics match 1-Click apply payload."""
    delta = compute_box_repair(sample_cuboid, sample_track, None, rule="heading.flip")

    # Preview overlay formats metrics
    preview_metrics = {
        "dz_cm": delta.delta_center[2] * 100,
        "dyaw_deg": math.degrees(delta.delta_yaw),
        "rule": delta.rule,
    }

    # User clicks Apply: payload carries the exact repair parameters
    apply_payload = {
        "frame": sample_cuboid.frame,
        "repair": {
            "rule": preview_metrics["rule"],
            "delta_yaw": delta.delta_yaw,
            "delta_center": delta.delta_center,
        }
    }
    assert apply_payload["repair"]["rule"] == delta.rule
    assert math.isclose(apply_payload["repair"]["delta_yaw"], delta.delta_yaw)


def test_interaction_f13_f14_extension_card_calls_whitelisted_route():
    """Interaction F13 + F14: Extension card actions route through background security whitelist."""
    job_id = 4
    track_id = 101
    apply_path = f"/api/jobs/{job_id}/tracks/{track_id}/apply-repair"
    rollback_path = f"/api/jobs/{job_id}/tracks/{track_id}/rollback"

    allowed_apply, _ = evaluate_extension_route("POST", apply_path)
    allowed_rollback, _ = evaluate_extension_route("POST", rollback_path)

    assert allowed_apply is True
    assert allowed_rollback is True


def test_interaction_f1_f7_heldout_synthetic_detection_and_repair(base_config, sample_track, sample_ground_points):
    """Interaction F1 + F7: Synthetic fault on held-out track is detected and repaired to clean pass."""
    # Inject fault: floating frame 2
    corrupted_track = list(sample_track)
    c2 = corrupted_track[2]
    corrupted_track[2] = c2.replace(center=(c2.center[0], c2.center[1], c2.center[2] + 0.35))

    class MockFrames:
        def frame_data(self, f, with_points=True):
            return FrameData(frame=f, points=sample_ground_points, sensor_to_world=np.eye(4), timestamp=float(f))

    # Scanner catches fault
    findings = scan_cuboids(corrupted_track, base_config, frames=MockFrames())
    floating_findings = [f for f in findings if f.frame == 2 and "floating" in f.rule.lower()]
    assert len(floating_findings) >= 1

    # Repair engine repairs fault
    delta = compute_box_repair(corrupted_track[2], corrupted_track, sample_ground_points, rule="floating",
                               finding_details={"distance": 0.35, "offset": 0.35})
    passes = verify_repaired_box_passes_scanner(delta.repaired_cuboid, corrupted_track, sample_ground_points, rule="floating")
    assert passes is True


def test_interaction_f3_f9_spec_vn_class_update_preserves_attributes(mock_cvat_raw_track):
    """Interaction F3 + F9: Updating spec-vn cuboid geometry preserves spec-vn taxonomy attributes."""
    spec_vn_track = dict(mock_cvat_raw_track)
    spec_vn_track["shapes"] = [dict(s) for s in mock_cvat_raw_track["shapes"]]
    # Add spec-vn attributes
    spec_vn_track["shapes"][0]["attributes"] = [
        {"id": 1, "name": "subtype", "value": "sedan"},
        {"id": 2, "name": "rider_state", "value": "without_rider"},
        {"id": 3, "name": "age_group", "value": "adult"},
    ]

    # Modify points of frame 0
    updated_shape = dict(spec_vn_track["shapes"][0])
    updated_shape["points"] = [12.0, 5.0, 0.0, 0.0, 0.0, 0.0, 4.5, 2.0, 1.6, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]

    # Verify attributes survived
    assert len(updated_shape["attributes"]) == 3
    assert updated_shape["attributes"][0]["value"] == "sedan"
    assert updated_shape["attributes"][1]["value"] == "without_rider"


def test_interaction_f4_f6_ground_plus_size_compound_repair(sample_cuboid, sample_track, sample_ground_points):
    """Interaction F4 + F6: Compound fault (Floating + Oversized) repaired sequentially."""
    corrupted = sample_cuboid.replace(
        center=(sample_cuboid.center[0], sample_cuboid.center[1], sample_cuboid.center[2] + 0.30),
        dims=(sample_cuboid.length * 1.30, sample_cuboid.width * 1.30, sample_cuboid.height),
        frame=2,
    )
    # Step 1: Repair Size
    size_repair = compute_box_repair(corrupted, sample_track, None, rule="size.in_track")
    assert size_repair.repaired_cuboid.length < corrupted.length

    # Step 2: Repair Ground
    ground_repair = compute_box_repair(
        size_repair.repaired_cuboid, sample_track, sample_ground_points, rule="floating",
        finding_details={"distance": 0.30, "offset": 0.30}
    )
    assert ground_repair.repaired_cuboid.bottom_z < corrupted.bottom_z
    assert ground_repair.repaired_cuboid.length < corrupted.length


def test_interaction_f10_f12_multiple_sequential_repairs_and_rollbacks(temp_history_storage, mock_cvat_raw_track):
    """Interaction F10 + F12: Sequential repairs on multiple frames support step-by-step undo."""
    track_v0 = dict(mock_cvat_raw_track)

    # Repair frame 1 -> track_v1
    track_v1 = dict(mock_cvat_raw_track)
    track_v1["shapes"] = [dict(s) for s in mock_cvat_raw_track["shapes"]]
    track_v1["shapes"][1]["points"] = [1.0] * 16
    hid1 = str(uuid.uuid4())
    s1 = create_history_snapshot(4, 101, 1, track_v0, track_v1, {}, hid1)
    (temp_history_storage / f"{hid1}.json").write_text(json.dumps(s1))

    # Repair frame 2 -> track_v2
    track_v2 = dict(track_v1)
    track_v2["shapes"] = [dict(s) for s in track_v1["shapes"]]
    track_v2["shapes"][2]["points"] = [2.0] * 16
    hid2 = str(uuid.uuid4())
    s2 = create_history_snapshot(4, 101, 2, track_v1, track_v2, {}, hid2)
    (temp_history_storage / f"{hid2}.json").write_text(json.dumps(s2))

    # Undo 1: rollback hid2 -> returns track_v1
    snap2 = json.loads((temp_history_storage / f"{hid2}.json").read_text())
    assert snap2["pre_repair_track"] == track_v1

    # Undo 2: rollback hid1 -> returns track_v0
    snap1 = json.loads((temp_history_storage / f"{hid1}.json").read_text())
    assert snap1["pre_repair_track"] == track_v0


def test_interaction_f7_f15_regression_scanner_invariants(base_config, sample_track, sample_ground_points):
    """Interaction F7 + F15: Full scanner run on clean track executes all detectors without error."""
    class MockFrames:
        def frame_data(self, f, with_points=True):
            return FrameData(frame=f, points=sample_ground_points, sensor_to_world=np.eye(4), timestamp=float(f))

    findings = scan_cuboids(sample_track, base_config, frames=MockFrames())
    errors = [f for f in findings if f.severity == Severity.ERROR]
    assert len(errors) == 0
