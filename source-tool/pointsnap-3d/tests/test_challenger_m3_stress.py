"""Challenger Stress Test Suite for Milestone M3.

Empirical verification of Snapshot Mutation & Rollback Integrity:
1. Multi-step edit chains: apply repair A -> repair B -> repair C, rollback C -> B -> A.
2. Truncated JSON and graceful error handling.
3. High volume performance: throughput of writing, querying, and listing snapshots.
4. Deep equality check: all 16 point coordinates, rotation, size, attributes, track ID.
5. Empirical reproduction of bugs & vulnerabilities:
   - Bug 1: list_snapshots crashes with AttributeError if non-dict JSON exists in history dir.
   - Bug 2: rollback endpoint crashes with unhandled KeyError (HTTP 500) if pre_repair_track is missing.
   - Bug 3: project rollback endpoint (/api/projects/{slug}/history/{history_id}/rollback) fails with 404 when job_id is omitted.
"""

from __future__ import annotations

import copy
import json
import math
import time
import uuid
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from pointsnap.adapters.cvat.shapes import (
    PITCH_ATTR,
    ROLL_ATTR,
    points_to_geometry,
)
from pointsnap.adapters.cvat.writer import (
    compute_track_etag,
)
from pointsnap.core.geometry import normalize_angle
from pointsnap.history.manager import (
    HistoryManager,
    validate_history_snapshot_schema,
)
from pointsnap.web.projects import ProjectManager
from pointsnap.web.app import create_app


def create_complex_test_track(track_id: int = 777, num_frames: int = 5) -> dict[str, Any]:
    """Tạo track phức tạp với dữ liệu hình học và thuộc tính chi tiết."""
    shapes = []
    for f in range(num_frames):
        pts = [
            12.345 + f * 1.5,
            -6.789 + f * 0.2,
            0.123 - f * 0.05,
            0.015,   # roll (cvat_rx)
            -0.025,  # pitch (cvat_ry)
            0.456,   # yaw
            4.65,    # length
            1.95,    # width
            1.72,    # height
            0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0,
        ]
        shapes.append({
            "id": 5000 + f,
            "frame": f,
            "type": "cuboid",
            "occluded": (f % 2 == 1),
            "outside": False,
            "keyframe": True,
            "points": pts,
            "attributes": [
                {"id": 101, "name": "subtype", "value": "suv"},
                {"id": 102, "name": "confidence", "value": "0.98"},
                {"id": 103, "name": "pointsnap_error", "value": f"[Err] Frame {f} floating 15cm" if f == 2 else ""},
            ],
        })
    return {
        "id": track_id,
        "label_id": 42,
        "frame": 0,
        "shapes": shapes,
        "attributes": [
            {"id": 201, "name": "color", "value": "metallic_blue"},
            {"id": 202, "name": "track_quality", "value": "gold"},
        ],
    }


# =========================================================================
# 1. Multi-Step Edit Chains & Step-by-Step Rollback (A -> B -> C -> B -> A)
# =========================================================================


def test_multistep_edit_chain_single_frame(tmp_path: Path):
    """Stress 1.1: Multi-step edits on a single frame: A -> B -> C, rollback C -> B -> A."""
    mgr = HistoryManager(home_dir=tmp_path, slug="multistep-test")
    job_id = 10
    track_id = 777
    target_frame = 2

    track_s0 = create_complex_test_track(track_id=track_id)
    pts_s0 = list(track_s0["shapes"][target_frame]["points"])

    # --- Step A: Ground / Floating repair (delta z = -0.15) ---
    track_s1 = copy.deepcopy(track_s0)
    pts_s1 = list(pts_s0)
    pts_s1[2] -= 0.15  # z center lowered
    track_s1["shapes"][target_frame]["points"] = pts_s1
    track_s1["shapes"][target_frame]["attributes"][2]["value"] = ""

    repair_a = {
        "rule": "floating",
        "delta_center": [0.0, 0.0, -0.15],
        "delta_dims": [0.0, 0.0, 0.0],
        "delta_yaw": 0.0,
        "reason": "Lower box to ground",
    }
    hid_a = mgr.save_snapshot(
        job_id=job_id,
        track_id=track_id,
        frame=target_frame,
        pre_repair_track=track_s0,
        post_repair_track=track_s1,
        applied_repair=repair_a,
    )

    # --- Step B: Heading flip repair (delta yaw = pi) ---
    track_s2 = copy.deepcopy(track_s1)
    pts_s2 = list(pts_s1)
    pts_s2[5] = normalize_angle(pts_s2[5] + math.pi)  # yaw flipped
    track_s2["shapes"][target_frame]["points"] = pts_s2

    repair_b = {
        "rule": "heading.flip",
        "delta_center": [0.0, 0.0, 0.0],
        "delta_dims": [0.0, 0.0, 0.0],
        "delta_yaw": math.pi,
        "reason": "Flip heading 180 degrees",
    }
    hid_b = mgr.save_snapshot(
        job_id=job_id,
        track_id=track_id,
        frame=target_frame,
        pre_repair_track=track_s1,
        post_repair_track=track_s2,
        applied_repair=repair_b,
    )

    # --- Step C: Dimensions repair (expand l, w, h) ---
    track_s3 = copy.deepcopy(track_s2)
    pts_s3 = list(pts_s2)
    pts_s3[6] += 0.20  # length
    pts_s3[7] += 0.10  # width
    pts_s3[8] += 0.05  # height
    track_s3["shapes"][target_frame]["points"] = pts_s3

    repair_c = {
        "rule": "fit.outside",
        "delta_center": [0.0, 0.0, 0.0],
        "delta_dims": [0.20, 0.10, 0.05],
        "delta_yaw": 0.0,
        "reason": "Expand box to fit LiDAR cluster",
    }
    hid_c = mgr.save_snapshot(
        job_id=job_id,
        track_id=track_id,
        frame=target_frame,
        pre_repair_track=track_s2,
        post_repair_track=track_s3,
        applied_repair=repair_c,
    )

    # --- Verification of Rollback Sequence: C -> B -> A ---

    # 1. Rollback C: Must restore State S2
    cuboids_after_c = mgr.rollback_track(job_id=job_id, history_id=hid_c)
    target_cuboid_c = next(c for c in cuboids_after_c if c.frame == target_frame)
    assert math.isclose(target_cuboid_c.center[2], pts_s2[2], abs_tol=1e-5)
    assert math.isclose(target_cuboid_c.yaw, normalize_angle(pts_s2[5]), abs_tol=1e-5)
    assert math.isclose(target_cuboid_c.dims[0], pts_s2[6], abs_tol=1e-5)

    # 2. Rollback B: Must restore State S1
    cuboids_after_b = mgr.rollback_track(job_id=job_id, history_id=hid_b)
    target_cuboid_b = next(c for c in cuboids_after_b if c.frame == target_frame)
    assert math.isclose(target_cuboid_b.center[2], pts_s1[2], abs_tol=1e-5)
    assert math.isclose(target_cuboid_b.yaw, normalize_angle(pts_s1[5]), abs_tol=1e-5)
    assert math.isclose(target_cuboid_b.dims[0], pts_s1[6], abs_tol=1e-5)

    # 3. Rollback A: Must restore State S0 (initial track with original error attribute)
    cuboids_after_a = mgr.rollback_track(job_id=job_id, history_id=hid_a)
    target_cuboid_a = next(c for c in cuboids_after_a if c.frame == target_frame)
    assert math.isclose(target_cuboid_a.center[2], pts_s0[2], abs_tol=1e-5)
    assert math.isclose(target_cuboid_a.yaw, normalize_angle(pts_s0[5]), abs_tol=1e-5)
    assert math.isclose(target_cuboid_a.dims[0], pts_s0[6], abs_tol=1e-5)
    assert target_cuboid_a.attrs.get("pointsnap_error") == "[Err] Frame 2 floating 15cm"

    # Immutability check: verify snapshot JSON files on disk were not altered or deleted
    snapshots = mgr.list_snapshots(job_id=job_id)
    assert len(snapshots) == 3
    loaded_ids = {s["history_id"] for s in snapshots}
    assert loaded_ids == {hid_a, hid_b, hid_c}


def test_multistep_edit_chain_multi_frame_rest_api(tmp_path: Path):
    """Stress 1.2: Multi-step edits on different frames via REST API with OCC checking."""
    app = create_app(home_dir=tmp_path)
    client = TestClient(app)

    job_id = 20
    track_id = 888
    initial_track = create_complex_test_track(track_id=track_id, num_frames=5)

    app.state.mock_tracks = {
        (job_id, track_id): copy.deepcopy(initial_track)
    }

    # Initial ETag
    etag_0 = compute_track_etag(initial_track)

    # Step 1: Repair frame 0
    resp_1 = client.post(
        f"/api/jobs/{job_id}/tracks/{track_id}/apply-repair",
        json={
            "frame": 0,
            "repair": {
                "rule": "floating",
                "delta_center": [0.0, 0.0, -0.30],
                "delta_dims": [0.0, 0.0, 0.0],
                "delta_yaw": 0.0,
            },
            "client_track_etag": etag_0,
        },
    )
    assert resp_1.status_code == 200, resp_1.text
    hid_1 = resp_1.json()["history_id"]
    track_after_1 = resp_1.json()["updated_track"]
    etag_1 = compute_track_etag(track_after_1)
    assert etag_1 != etag_0

    # Step 2: Attempt repair frame 2 with stale etag_0 -> must 409
    resp_stale = client.post(
        f"/api/jobs/{job_id}/tracks/{track_id}/apply-repair",
        json={
            "frame": 2,
            "repair": {"rule": "heading.flip", "delta_yaw": math.pi},
            "client_track_etag": etag_0,
        },
    )
    assert resp_stale.status_code == 409

    # Step 3: Repair frame 2 with fresh etag_1
    resp_2 = client.post(
        f"/api/jobs/{job_id}/tracks/{track_id}/apply-repair",
        json={
            "frame": 2,
            "repair": {
                "rule": "heading.flip",
                "delta_yaw": math.pi,
            },
            "client_track_etag": etag_1,
        },
    )
    assert resp_2.status_code == 200
    hid_2 = resp_2.json()["history_id"]
    track_after_2 = resp_2.json()["updated_track"]
    etag_2 = compute_track_etag(track_after_2)

    # Step 4: Repair frame 4 with fresh etag_2
    resp_3 = client.post(
        f"/api/jobs/{job_id}/tracks/{track_id}/apply-repair",
        json={
            "frame": 4,
            "repair": {
                "rule": "fit.outside",
                "delta_dims": [0.5, 0.3, 0.2],
            },
            "client_track_etag": etag_2,
        },
    )
    assert resp_3.status_code == 200
    hid_3 = resp_3.json()["history_id"]

    # Now Rollback 3 (frame 4) -> restores track_after_2
    rb_3 = client.post(
        f"/api/jobs/{job_id}/tracks/{track_id}/rollback",
        json={"history_id": hid_3},
    )
    assert rb_3.status_code == 200
    restored_3 = rb_3.json()["restored_track"]
    assert compute_track_etag(restored_3) == etag_2

    # Now Rollback 2 (frame 2) -> restores track_after_1
    rb_2 = client.post(
        f"/api/jobs/{job_id}/tracks/{track_id}/rollback",
        json={"history_id": hid_2},
    )
    assert rb_2.status_code == 200
    restored_2 = rb_2.json()["restored_track"]
    assert compute_track_etag(restored_2) == etag_1

    # Now Rollback 1 (frame 0) -> restores initial_track
    rb_1 = client.post(
        f"/api/jobs/{job_id}/tracks/{track_id}/rollback",
        json={"history_id": hid_1},
    )
    assert rb_1.status_code == 200
    restored_1 = rb_1.json()["restored_track"]
    assert compute_track_etag(restored_1) == etag_0


# =========================================================================
# 2. Corrupted Snapshot On Disk Handling
# =========================================================================


def test_corrupted_snapshot_truncated_json(tmp_path: Path):
    """Stress 2.1: Truncated JSON on disk causes JSONDecodeError; API returns clean 404 without crashing."""
    ProjectManager(home_dir=tmp_path).create_project(name="corrupt", slug="corrupt-test")
    mgr = HistoryManager(home_dir=tmp_path, slug="corrupt-test")
    job_id = 30
    h_dir = mgr.history_dir(job_id=job_id)
    corrupted_id = str(uuid.uuid4())
    bad_file = h_dir / f"{corrupted_id}.json"
    bad_file.write_text('{"history_id": "' + corrupted_id + '", "timestamp": "2026-10-14', encoding="utf-8")

    # Manager get_snapshot raises JSONDecodeError
    with pytest.raises(json.JSONDecodeError):
        mgr.get_snapshot(job_id=job_id, history_id=corrupted_id)

    # API handles gracefully without unhandled 500 error
    app = create_app(home_dir=tmp_path)
    client = TestClient(app)
    resp = client.post(
        f"/api/jobs/{job_id}/tracks/100/rollback",
        json={"history_id": corrupted_id, "slug": "corrupt-test"},
    )
    assert resp.status_code == 404
    assert "not found" in resp.json()["detail"].lower()


def test_corrupted_snapshot_missing_fields_validation(tmp_path: Path):
    """Stress 2.2: Snapshot with missing mandatory fields is detected by schema validator."""
    valid_id = str(uuid.uuid4())
    # Missing 'pre_repair_track' and 'applied_repair'
    incomplete_snapshot = {
        "history_id": valid_id,
        "timestamp": "2026-10-14T12:00:00Z",
        "job_id": 30,
        "track_id": 100,
        "frame": 0,
        "post_repair_track": {},
    }
    valid, msg = validate_history_snapshot_schema(incomplete_snapshot)
    assert valid is False
    assert "Missing required snapshot keys" in msg


# =========================================================================
# 3. High Volume Performance Stress
# =========================================================================


def test_high_volume_snapshots_performance(tmp_path: Path):
    """Stress 3: Save 150 snapshots and test listing and retrieval throughput."""
    mgr = HistoryManager(home_dir=tmp_path, slug="volume-test")
    job_id = 50
    track_id = 999
    base_track = {"id": track_id, "shapes": []}

    num_snapshots = 150
    history_ids = []

    t0 = time.perf_counter()
    for i in range(num_snapshots):
        hid = mgr.save_snapshot(
            job_id=job_id,
            track_id=track_id,
            frame=i % 10,
            pre_repair_track=base_track,
            post_repair_track=base_track,
            applied_repair={"rule": "floating", "step": i},
        )
        history_ids.append(hid)
    t_save = time.perf_counter() - t0

    # 150 writes should finish within reasonable time (< 4.0s on standard disk)
    assert t_save < 4.0, f"Saving {num_snapshots} snapshots took too long: {t_save:.2f}s"

    # Single lookup performance (O(1))
    t1 = time.perf_counter()
    for hid in history_ids[::10]:  # 15 sample lookups
        snap = mgr.get_snapshot(job_id=job_id, history_id=hid)
        assert snap["history_id"] == hid
    t_lookup = time.perf_counter() - t1
    assert t_lookup < 0.5, f"15 snapshot lookups took too long: {t_lookup:.2f}s"

    # Listing performance
    t2 = time.perf_counter()
    all_snaps = mgr.list_snapshots(job_id=job_id)
    t_list = time.perf_counter() - t2
    assert len(all_snaps) == num_snapshots
    assert t_list < 2.0, f"Listing {num_snapshots} snapshots took too long: {t_list:.2f}s"


# =========================================================================
# 4. Deep Equality Check (All 16 Floats, Angles, Dims, Attributes, Track ID)
# =========================================================================


def test_deep_equality_roundtrip_all_16_points_and_attributes(tmp_path: Path):
    """Stress 4: Verify bit-for-bit exact equality of all 16 floats, angles, dims, and attributes after rollback."""
    mgr = HistoryManager(home_dir=tmp_path, slug="deep-equality")
    job_id = 60
    track_id = 12345
    target_frame = 3

    # Tạo track nguyên bản với giá trị số thực chính xác cao
    original_track = {
        "id": track_id,
        "label_id": 99,
        "frame": 0,
        "shapes": [
            {
                "id": 8801,
                "frame": 0,
                "type": "cuboid",
                "occluded": False,
                "outside": False,
                "keyframe": True,
                "points": [10.12345678, -5.87654321, 0.55555555, 0.012, -0.034, 1.57079632, 4.8888, 2.1111, 1.6666, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
                "attributes": [
                    {"id": 1, "name": "vehicle_type", "value": "truck"},
                    {"id": 2, "name": "is_parked", "value": "false"},
                ],
            },
            {
                "id": 8802,
                "frame": target_frame,
                "type": "cuboid",
                "occluded": True,
                "outside": False,
                "keyframe": True,
                "points": [15.98765432, -4.12345678, 0.88888888, 0.025, -0.015, 2.71828182, 5.1234, 2.2345, 1.9876, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
                "attributes": [
                    {"id": 1, "name": "vehicle_type", "value": "truck"},
                    {"id": 2, "name": "is_parked", "value": "false"},
                    {"id": 3, "name": "pointsnap_error", "value": "[Critical] Ground penetration 22cm"},
                    {"id": 4, "name": "custom_annotator_note", "value": "Check LiDAR reflections"},
                ],
            },
        ],
        "attributes": [
            {"id": 901, "name": "dataset", "value": "nuscenes_test"},
            {"id": 902, "name": "annotator_id", "value": "qa_specialist_4"},
        ],
    }

    # Giả lập sửa đổi trên frame mục tiêu
    repaired_track = copy.deepcopy(original_track)
    target_shape = repaired_track["shapes"][1]
    # Sửa tọa độ z, roll, pitch, yaw, dims
    target_shape["points"][2] += 0.22   # fix penetration
    target_shape["points"][5] = 3.14159 # fix yaw
    target_shape["points"][6] = 5.2000  # fix length
    # Clear error attribute
    for attr in target_shape["attributes"]:
        if attr["name"] == "pointsnap_error":
            attr["value"] = ""

    # Lưu snapshot
    history_id = mgr.save_snapshot(
        job_id=job_id,
        track_id=track_id,
        frame=target_frame,
        pre_repair_track=original_track,
        post_repair_track=repaired_track,
        applied_repair={"rule": "floating", "delta_center": [0, 0, 0.22]},
    )

    # 1. Tải lại snapshot thô từ file JSON
    snapshot = mgr.get_snapshot(job_id=job_id, history_id=history_id)
    restored_raw = snapshot["pre_repair_track"]

    # Kiểm tra sâu từng trường track-level
    assert restored_raw["id"] == original_track["id"]
    assert restored_raw["label_id"] == original_track["label_id"]
    assert restored_raw["frame"] == original_track["frame"]
    assert restored_raw["attributes"] == original_track["attributes"]

    # Kiểm tra sâu từng keyframe và mảng 16 số thực
    assert len(restored_raw["shapes"]) == len(original_track["shapes"])
    for idx in range(len(original_track["shapes"])):
        orig_s = original_track["shapes"][idx]
        rest_s = restored_raw["shapes"][idx]

        assert rest_s["id"] == orig_s["id"]
        assert rest_s["frame"] == orig_s["frame"]
        assert rest_s["occluded"] == orig_s["occluded"]
        assert rest_s["outside"] == orig_s["outside"]
        assert rest_s["keyframe"] == orig_s["keyframe"]
        assert rest_s["attributes"] == orig_s["attributes"]

        # 16 float coordinates deep equality
        orig_pts = orig_s["points"]
        rest_pts = rest_s["points"]
        assert len(rest_pts) == 16
        for p_idx in range(16):
            assert orig_pts[p_idx] == rest_pts[p_idx], (
                f"Mismatch at shape {idx} point index {p_idx}: {orig_pts[p_idx]} != {rest_pts[p_idx]}"
            )

    # 2. Hoàn tác thành danh sách Cuboid và kiểm tra deep equality
    restored_cuboids = mgr.rollback_track(job_id=job_id, history_id=history_id)
    assert len(restored_cuboids) == len(original_track["shapes"])

    for idx, cuboid in enumerate(restored_cuboids):
        orig_s = original_track["shapes"][idx]
        expected_geo = points_to_geometry(orig_s["points"])

        assert cuboid.track_id == track_id
        assert cuboid.source_id == orig_s["id"]
        assert cuboid.frame == orig_s["frame"]
        assert cuboid.occluded == orig_s["occluded"]
        assert cuboid.outside == orig_s["outside"]

        # Center (x, y, z)
        for c_i in range(3):
            assert math.isclose(cuboid.center[c_i], expected_geo["center"][c_i], abs_tol=1e-7)

        # Dims (l, w, h)
        for d_i in range(3):
            assert math.isclose(cuboid.dims[d_i], expected_geo["dims"][d_i], abs_tol=1e-7)

        # Yaw
        assert math.isclose(cuboid.yaw, normalize_angle(expected_geo["yaw"]), abs_tol=1e-7)

        # Roll and Pitch in attrs (cvat_rx, cvat_ry)
        assert math.isclose(cuboid.attrs[ROLL_ATTR], expected_geo["roll"], abs_tol=1e-7)
        assert math.isclose(cuboid.attrs[PITCH_ATTR], expected_geo["pitch"], abs_tol=1e-7)

        # Custom shape attributes
        for a in orig_s["attributes"]:
            assert cuboid.attrs.get(a["name"]) == a["value"]

        # Track-level attributes preserved into cuboid
        for ta in original_track["attributes"]:
            assert cuboid.attrs.get(ta["name"]) == ta["value"]


# =========================================================================
# 5. Adversarial Bug Reproductions (Empirical Evidence)
# =========================================================================


def test_adversarial_bug_1_list_snapshots_crashes_on_non_dict_json(tmp_path: Path):
    """Bug 1 Fix: list_snapshots safely ignores non-dict JSON files (array, string, null) without crashing."""
    mgr = HistoryManager(home_dir=tmp_path, slug="bug1-test")
    job_id = 40
    h_dir = mgr.history_dir(job_id=job_id)

    # Valid snapshot
    mgr.save_snapshot(
        job_id=job_id,
        track_id=1,
        frame=0,
        pre_repair_track={"id": 1, "shapes": []},
        post_repair_track={"id": 1, "shapes": []},
        applied_repair={},
    )

    # Non-dict JSON file (array)
    (h_dir / "external_array.json").write_text("[1, 2, 3]", encoding="utf-8")

    snapshots = mgr.list_snapshots(job_id=job_id)
    assert len(snapshots) == 1
    assert snapshots[0]["job_id"] == job_id


def test_adversarial_bug_2_rollback_api_crashes_500_on_missing_pre_repair_track(tmp_path: Path):
    """Bug 2 Fix: POST rollback endpoint rejects missing pre_repair_track with 404/400 without crashing with HTTP 500."""
    mgr = HistoryManager(home_dir=tmp_path, slug="bug2-test")
    job_id = 35
    h_dir = mgr.history_dir(job_id=job_id)
    corrupt_schema_id = str(uuid.uuid4())
    bad_file = h_dir / f"{corrupt_schema_id}.json"
    # Valid JSON, but missing pre_repair_track
    bad_file.write_text(json.dumps({
        "history_id": corrupt_schema_id,
        "job_id": job_id,
        "track_id": 100,
        "frame": 0,
    }), encoding="utf-8")

    app = create_app(home_dir=tmp_path)
    # Using raise_server_exceptions=False to observe HTTP response code from server
    client = TestClient(app, raise_server_exceptions=False)

    resp = client.post(
        f"/api/jobs/{job_id}/tracks/100/rollback",
        json={"history_id": corrupt_schema_id, "slug": "bug2-test"},
    )
    assert resp.status_code in (400, 404)
    assert resp.status_code != 500


def test_adversarial_bug_3_project_rollback_fails_404_when_job_id_omitted(tmp_path: Path):
    """Bug 3 Fix: POST /api/projects/{slug}/history/{history_id}/rollback succeeds via cross-job search when job_id omitted."""
    app = create_app(home_dir=tmp_path)
    client = TestClient(app)
    mgr = app.state.history_manager

    actual_job_id = 4
    track_id = 101
    app.state.mock_tracks = {(actual_job_id, track_id): {"id": track_id, "shapes": []}}

    # Save snapshot under job 4
    hid = mgr.save_snapshot(
        job_id=actual_job_id,
        track_id=track_id,
        frame=0,
        pre_repair_track={"id": track_id, "shapes": []},
        post_repair_track={"id": track_id, "shapes": []},
        applied_repair={},
    )

    # Calling project-level rollback without job_id query param:
    # Cross-job fallback search finds the snapshot under job_4 and restores it successfully!
    resp = client.post(f"/api/projects/default/history/{hid}/rollback")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
    assert resp.json()["restored_track"]["id"] == track_id
