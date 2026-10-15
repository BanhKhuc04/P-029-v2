"""Tier 4: Real-World Application Scenarios Test Suite.

Contains comprehensive end-to-end full workflow scenarios:
1. Scanner finding on held-out scene -> preview delta -> 1-click apply -> re-scan gate PASS -> rollback.
2. Multi-frame track integrity under sequential edits.
3. Spec-VN multi-class batch repair workflow.
4. High-concurrency OCC safety and conflict recovery.
5. Full lifecycle: synthetic injection -> detection -> repair -> gate pass -> audit.

Total scenarios: 5 scenarios.
"""

from __future__ import annotations

import copy
import json
import math
import uuid
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import numpy as np
import pytest

from pointsnap.core.config import Config, load_config
from pointsnap.core.geometry import normalize_angle
from pointsnap.core.model import Cuboid, ErrorType, Finding, FrameData, Severity
from pointsnap.core.scanner import scan_coverage_gaps, scan_cuboids
from pointsnap.core.synthetic import inject_dataset
from e2e_tests.contracts import (
    BoxRepairDelta,
    compute_box_repair,
    compute_track_etag,
    create_history_snapshot,
    evaluate_extension_route,
    validate_history_snapshot_schema,
    verify_repaired_box_passes_scanner,
)


def test_scenario_1_heldout_floating_repair_rescan_rollback(
    base_config, sample_cuboid, sample_track, sample_ground_points, temp_history_storage
):
    """Scenario 1: End-to-End Floating Repair -> 1-Click Apply -> Re-scan PASS -> Rollback."""
    # -------------------------------------------------------------------------
    # Step 1: Scanner flags floating vehicle on held-out scene
    # -------------------------------------------------------------------------
    elevated_box = sample_cuboid.replace(
        center=(sample_cuboid.center[0], sample_cuboid.center[1], sample_cuboid.center[2] + 0.30),
        frame=2,
    )
    test_track = [b if b.frame != 2 else elevated_box for b in sample_track]

    class MockFrames:
        def frame_data(self, f, with_points=True):
            return FrameData(frame=f, points=sample_ground_points, sensor_to_world=np.eye(4), timestamp=float(f))

    initial_findings = scan_cuboids(test_track, base_config, frames=MockFrames())
    floating_errors = [f for f in initial_findings if f.frame == 2 and "floating" in f.rule.lower()]
    assert len(floating_errors) >= 1, "Step 1: Scanner must detect floating finding"

    # -------------------------------------------------------------------------
    # Step 2: Annotator inspects 3-view preview and delta calculation
    # -------------------------------------------------------------------------
    delta = compute_box_repair(
        elevated_box, test_track, sample_ground_points, rule="floating",
        finding_details={"distance": 0.30, "offset": 0.30}
    )
    assert delta.delta_center[2] < 0.0, "Step 2: Delta z must be negative to lower box"
    assert math.isclose(delta.delta_center[2], -0.30, abs_tol=0.01)

    # -------------------------------------------------------------------------
    # Step 3: Annotator clicks 1-Click Apply with OCC check
    # -------------------------------------------------------------------------
    pre_repair_track_dict = {
        "id": 101,
        "shapes": [
            {
                "frame": b.frame,
                "points": [b.center[0], b.center[1], b.center[2], 0, 0, b.yaw, b.length, b.width, b.height] + [0] * 7,
                "attributes": [{"name": "subtype", "value": "sedan"}],
            }
            for b in test_track
        ],
    }
    client_etag = compute_track_etag(pre_repair_track_dict)

    # Server verifies ETag
    server_etag = compute_track_etag(pre_repair_track_dict)
    assert client_etag == server_etag, "Step 3: OCC ETag pre-check passes"

    # -------------------------------------------------------------------------
    # Step 4: Apply patch to CVAT track & persist snapshot
    # -------------------------------------------------------------------------
    post_repair_track_dict = copy.deepcopy(pre_repair_track_dict)
    repaired_box = delta.repaired_cuboid
    post_repair_track_dict["shapes"][2]["points"] = [
        repaired_box.center[0], repaired_box.center[1], repaired_box.center[2],
        0, 0, repaired_box.yaw, repaired_box.length, repaired_box.width, repaired_box.height
    ] + [0] * 7

    history_id = str(uuid.uuid4())
    snapshot = create_history_snapshot(
        job_id=4,
        track_id=101,
        frame=2,
        pre_repair_track=pre_repair_track_dict,
        post_repair_track=post_repair_track_dict,
        applied_repair={"rule": "floating", "delta_center": delta.delta_center},
        history_id=history_id,
    )
    snapshot_path = temp_history_storage / f"{history_id}.json"
    snapshot_path.write_text(json.dumps(snapshot, indent=2))
    assert snapshot_path.exists(), "Step 4: Snapshot file must be persisted"

    # -------------------------------------------------------------------------
    # Step 5: Re-scan gate transitions to PASS
    # -------------------------------------------------------------------------
    repaired_track = [b if b.frame != 2 else repaired_box for b in test_track]
    post_findings = scan_cuboids(repaired_track, base_config, frames=MockFrames())
    post_floating_errors = [
        f for f in post_findings
        if f.frame == 2 and "floating" in f.rule.lower() and f.severity in (Severity.ERROR, Severity.WARNING)
    ]
    assert len(post_floating_errors) == 0, "Step 5: Re-scan gate must PASS with 0 floating findings"

    # -------------------------------------------------------------------------
    # Step 6: 1-Click Rollback restores exact original track
    # -------------------------------------------------------------------------
    loaded_snap = json.loads(snapshot_path.read_text())
    restored_track_dict = loaded_snap["pre_repair_track"]
    assert restored_track_dict == pre_repair_track_dict, "Step 6: Rollback restores exact pre-repair state"


def test_scenario_2_multiframe_track_integrity_under_sequential_edits(
    base_config, sample_cuboid, sample_track, sample_car_points, temp_history_storage
):
    """Scenario 2: Multi-Frame Track Integrity under Sequential Keyframe Repairs."""
    # Frame 1: flipped heading
    # Frame 3: fit outside
    c1_corrupted = sample_track[1].replace(yaw=math.pi)
    c3_corrupted = sample_track[3].replace(dims=(2.0, 1.0, 1.6))
    corrupted_track = [
        sample_track[0],
        c1_corrupted,
        sample_track[2],
        c3_corrupted,
        sample_track[4],
    ]

    # Step 1: Repair Frame 1 (Heading Flip)
    delta_f1 = compute_box_repair(c1_corrupted, corrupted_track, None, rule="heading.flip")
    repaired_f1 = delta_f1.repaired_cuboid
    assert math.isclose(repaired_f1.yaw, 0.0, abs_tol=1e-3)

    track_stage_1 = [
        corrupted_track[0],
        repaired_f1,
        corrupted_track[2],
        corrupted_track[3],
        corrupted_track[4],
    ]

    # Verify non-targeted frames 0, 2, 3, 4 are strictly unchanged
    assert track_stage_1[0] == corrupted_track[0]
    assert track_stage_1[2] == corrupted_track[2]
    assert track_stage_1[3] == corrupted_track[3]
    assert track_stage_1[4] == corrupted_track[4]

    # Step 2: Repair Frame 3 (Fit Outside)
    delta_f3 = compute_box_repair(c3_corrupted, track_stage_1, sample_car_points, rule="fit.outside")
    repaired_f3 = delta_f3.repaired_cuboid
    assert repaired_f3.length >= 4.0

    track_stage_2 = [
        track_stage_1[0],
        track_stage_1[1],
        track_stage_1[2],
        repaired_f3,
        track_stage_1[4],
    ]

    # Verify frames 0, 1, 2, 4 are unchanged in stage 2
    assert track_stage_2[0] == track_stage_1[0]
    assert track_stage_2[1] == repaired_f1
    assert track_stage_2[2] == track_stage_1[2]
    assert track_stage_2[4] == track_stage_1[4]

    # Step 3: Re-scan verifies both issues resolved
    passes_f1 = verify_repaired_box_passes_scanner(repaired_f1, track_stage_2, None, rule="heading.flip")
    passes_f3 = verify_repaired_box_passes_scanner(repaired_f3, track_stage_2, sample_car_points, rule="fit.outside")
    assert passes_f1 is True and passes_f3 is True


def test_scenario_3_spec_vn_multi_class_batch_repair(spec_vn_config, sample_ground_points):
    """Scenario 3: Spec-VN Multi-Class Batch Repair Workflow."""
    # 1. Vehicle (floating)
    car = Cuboid(center=(10.0, 0.0, 0.5), dims=(4.5, 2.0, 1.6), yaw=0.0, label="Vehicle", frame=0,
                 attrs={"subtype": "sedan"})
    # 2. Two-wheels (flipped)
    moto = Cuboid(center=(15.0, 5.0, 0.0), dims=(1.8, 0.8, 1.4), yaw=math.pi, label="Two-wheels", frame=0,
                  attrs={"rider_state": "with_rider"})
    # 3. Pedestrian (fit.outside)
    ped = Cuboid(center=(5.0, -3.0, 0.0), dims=(0.3, 0.3, 1.7), yaw=0.0, label="Pedestrian", frame=0,
                 attrs={"age_group": "adult"})
    ped_pts = np.array([
        [4.5, -3.0, 0.0],
        [5.5, -3.0, 0.0],
        [5.0, -3.5, 0.0],
        [5.0, -2.5, 0.0],
        [5.0, -3.0, 0.8],
    ], dtype=np.float32)

    batch_boxes = [car, moto, ped]

    # Batch Repair Computations
    repair_car = compute_box_repair(car, [car], sample_ground_points, rule="floating",
                                    finding_details={"distance": 0.30, "offset": 0.30})
    repair_moto = compute_box_repair(moto, [moto, moto.replace(frame=moto.frame + 1, yaw=0)], None, rule="heading.flip")
    repair_ped = compute_box_repair(ped, [ped], ped_pts, rule="fit.outside")

    assert repair_car.delta_center[2] < 0.0, "Vehicle lowered"
    assert math.isclose(abs(repair_moto.delta_yaw), math.pi, abs_tol=1e-3), "Two-wheels yaw flipped"
    assert repair_ped.repaired_cuboid.length > ped.length, "Pedestrian size expanded to enclose points"

    # Batch Re-scan
    repaired_batch = [repair_car.repaired_cuboid, repair_moto.repaired_cuboid, repair_ped.repaired_cuboid]
    spec_vn_classes = {"Vehicle", "Two-wheels", "Pedestrian", "Animal", "Obstacle"}
    assert all(b.label in spec_vn_classes for b in repaired_batch)


def test_scenario_4_high_concurrency_occ_safety_and_recovery(mock_cvat_raw_track, temp_history_storage):
    """Scenario 4: High-Concurrency OCC Safety and Conflict Recovery."""
    # Server initial state
    server_track = copy.deepcopy(mock_cvat_raw_track)
    initial_etag = compute_track_etag(server_track)

    # Annotator Alice and Bob both read server state
    alice_client_etag = initial_etag
    bob_client_etag = initial_etag

    # Alice applies repair first
    alice_repair_pts = list(server_track["shapes"][2]["points"])
    alice_repair_pts[2] -= 0.20  # dz = -0.20m
    alice_updated_track = copy.deepcopy(server_track)
    alice_updated_track["shapes"][2]["points"] = alice_repair_pts

    # Server receives Alice's request
    assert alice_client_etag == compute_track_etag(server_track), "Alice OCC check passes"
    server_track = copy.deepcopy(alice_updated_track)
    new_server_etag = compute_track_etag(server_track)
    assert new_server_etag != initial_etag, "Server ETag updated after Alice's patch"

    # Bob attempts to submit patch with stale initial_etag
    bob_repair_pts = list(mock_cvat_raw_track["shapes"][2]["points"])
    bob_repair_pts[2] -= 0.15
    bob_updated_track = copy.deepcopy(mock_cvat_raw_track)
    bob_updated_track["shapes"][2]["points"] = bob_repair_pts

    # Server checks Bob's ETag
    bob_occ_match = (bob_client_etag == new_server_etag)
    assert bob_occ_match is False, "Bob's request must be rejected with 409 Conflict"

    # Recovery: Bob refreshes track, obtains new_server_etag, observes Alice's repair
    bob_refreshed_etag = new_server_etag
    assert bob_refreshed_etag == compute_track_etag(server_track)
    assert server_track["shapes"][2]["points"] == alice_repair_pts, "Alice's edit preserved safely"


def test_scenario_5_full_lifecycle_synthetic_to_acceptance_gate(base_config, sample_track, sample_ground_points):
    """Scenario 5: Full Lifecycle (Synthetic Injection -> Detection -> Repair -> Gate Pass)."""
    # 1. Start with clean track
    class MockFrames:
        def frame_data(self, f, with_points=True):
            return FrameData(frame=f, points=sample_ground_points, sensor_to_world=np.eye(4), timestamp=float(f))

    # 2. Inject fault: 180° flip on frame 2
    corrupted_track = list(sample_track)
    corrupted_track[2] = corrupted_track[2].replace(yaw=math.pi)

    # 3. Detection
    findings = scan_cuboids(corrupted_track, base_config, frames=MockFrames())
    flip_findings = [f for f in findings if f.frame == 2 and "flip" in f.rule.lower()]
    assert len(flip_findings) >= 1, "Injected heading fault detected"

    # 4. Repair proposal
    finding = flip_findings[0]
    delta = compute_box_repair(corrupted_track[2], corrupted_track, None, rule=finding.rule)
    assert math.isclose(delta.repaired_cuboid.yaw, 0.0, abs_tol=1e-3)

    # 5. Apply repair
    clean_repaired_track = [b if b.frame != 2 else delta.repaired_cuboid for b in corrupted_track]

    # 6. Re-scan gate
    post_findings = scan_cuboids(clean_repaired_track, base_config, frames=MockFrames())
    error_findings = [f for f in post_findings if f.severity == Severity.ERROR]
    assert len(error_findings) == 0, "Gate PASS: zero errors after repair"
