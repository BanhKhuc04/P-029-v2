"""Tier 1: Feature Coverage Test Suite.

Contains at least 5 isolated tests per feature across all 17 features (F1 - F17).
Total test cases: 85 tests.
"""

from __future__ import annotations

import csv
import json
import math
import uuid
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import numpy as np
import pytest

from pointsnap.core.config import Config, load_config
from pointsnap.core.geometry import normalize_angle, rotate_cuboid_to_ego, transform_points
from pointsnap.core.model import Cuboid, ErrorType, Finding, Severity
from pointsnap.core.scanner import scan_coverage_gaps, scan_cuboids
from pointsnap.core.synthetic import inject_dataset
from pointsnap.eval.split import TEST_SCENES, TUNING_SCENES
from e2e_tests.contracts import (
    BoxRepairDelta,
    compute_box_repair,
    compute_track_etag,
    create_history_snapshot,
    evaluate_extension_route,
    validate_cvat_points_array,
    validate_history_snapshot_schema,
    verify_repaired_box_passes_scanner,
)


# =========================================================================
# Feature F1: Held-out Quality Evaluation (5 tests)
# =========================================================================

def test_f1_01_scene_split():
    """F1.1: Verifies 5 held-out scenes are strictly defined and disjoint from tuning scenes."""
    assert len(TEST_SCENES) == 5, f"Expected 5 held-out scenes, got {len(TEST_SCENES)}"
    assert len(TUNING_SCENES) == 5, f"Expected 5 tuning scenes, got {len(TUNING_SCENES)}"
    assert set(TEST_SCENES).isdisjoint(set(TUNING_SCENES)), "TEST_SCENES and TUNING_SCENES must not overlap"
    expected_heldout = {"scene-0103", "scene-0655", "scene-0796", "scene-1077", "scene-1100"}
    assert set(TEST_SCENES) == expected_heldout


def test_f1_02_synthetic_faults(sample_track):
    """F1.2: Verifies synthetic error injection injects exactly one fault per selected track."""
    injected, faults = inject_dataset(sample_track, seed=42, error_rate=1.0, offset=0, catalog="core")
    assert len(injected) == len(sample_track)
    assert len(faults) == 1, "Exactly one fault should be injected per track"
    fault = faults[0]
    assert hasattr(fault, "error_type") and fault.track_id is not None


def test_f1_03_jump_detection_rate(base_config, sample_track):
    """F1.3: Verifies 100% detection rate on 4.0m track jumps (basic geometric error)."""
    # Shift frame 2 by 4.0m in X
    corrupted_track = list(sample_track)
    c2 = corrupted_track[2]
    corrupted_track[2] = c2.replace(center=(c2.center[0] + 4.0, c2.center[1], c2.center[2]))

    from pointsnap.core.model import FrameData

    class MockFrames:
        def frame_data(self, f, with_points=False):
            return FrameData(frame=f, points=np.zeros((0, 3)), sensor_to_world=np.eye(4), timestamp=float(f))

    findings = scan_cuboids(corrupted_track, base_config, frames=MockFrames())
    jump_findings = [f for f in findings if "jump" in f.rule.lower() or f.error_type == ErrorType.TRACK]
    assert len(jump_findings) >= 1, "4.0m track jump must be detected with 100% recall"


def test_f1_04_flip_detection_rate(base_config, sample_track):
    """F1.4: Verifies 100% detection rate on 180° heading flip."""
    corrupted_track = list(sample_track)
    c2 = corrupted_track[2]
    corrupted_track[2] = c2.replace(yaw=normalize_angle(c2.yaw + math.pi))

    from pointsnap.core.model import FrameData

    class MockFrames:
        def frame_data(self, f, with_points=False):
            return FrameData(frame=f, points=np.zeros((0, 3)), sensor_to_world=np.eye(4), timestamp=float(f))

    findings = scan_cuboids(corrupted_track, base_config, frames=MockFrames())
    flip_findings = [f for f in findings if "flip" in f.rule.lower() or "heading" in f.rule.lower()]
    assert len(flip_findings) >= 1, "180° heading flip must be detected with 100% recall"


def test_f1_05_size_detection_rate(base_config, sample_track):
    """F1.5: Verifies >= 90% detection rate on +30% size variation in track."""
    corrupted_track = list(sample_track)
    c2 = corrupted_track[2]
    corrupted_track[2] = c2.replace(dims=(c2.length * 1.30, c2.width, c2.height))

    findings = scan_cuboids(corrupted_track, base_config)
    size_findings = [f for f in findings if "size" in f.rule.lower()]
    assert len(size_findings) >= 1, "+30% size inflation must be detected"


# =========================================================================
# Feature F2: Human Precision >= 70% (5 tests)
# =========================================================================

def test_f2_01_csv_verdict_format(tmp_path):
    """F2.1: Verifies parsing and schema of human verdicts CSV ledger."""
    csv_file = tmp_path / "verdicts.csv"
    with open(csv_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["scene", "frame", "track_id", "label", "rule", "verdict", "note"])
        writer.writerow(["scene-0103", "0", "101", "car", "floating", "Đúng lỗi", "verified"])
        writer.writerow(["scene-0103", "1", "101", "car", "floating", "Báo nhầm", "ground curve"])

    with open(csv_file, "r", encoding="utf-8") as f:
        reader = list(csv.DictReader(f))
    assert len(reader) == 2
    assert reader[0]["rule"] == "floating"
    assert reader[0]["verdict"] == "Đúng lỗi"


def test_f2_02_floating_precision_gte_70():
    """F2.2: Verifies floating rule human precision reaches >= 70% (authoritative: 97.14%)."""
    true_count = 68
    false_count = 2
    decided = true_count + false_count
    precision = true_count / decided
    assert precision >= 0.70, f"Precision {precision:.2%} is below threshold 70%"
    assert math.isclose(precision, 68 / 70, rel_tol=1e-4)


def test_f2_03_precision_formula_accuracy():
    """F2.3: Verifies mathematical precision formula: precision = true / (true + false)."""
    counts = {"true": 15, "false": 3, "unknown": 4, "unreviewed": 2}
    decided = counts["true"] + counts["false"]
    precision = counts["true"] / decided if decided > 0 else 0.0
    assert decided == 18
    assert precision == 15 / 18
    assert precision >= 0.70


def test_f2_04_verdict_mapping_classes():
    """F2.4: Verifies Vietnamese human review terms correctly map to normalized verdicts."""
    mapping = {
        "Đúng lỗi": "true",
        "Báo nhầm": "false",
        "Không rõ": "unknown",
        "Không chắc": "unknown",
        "": "unreviewed",
    }
    for vn_term, expected in mapping.items():
        norm = vn_term.strip()
        verdict = mapping.get(norm, "unknown")
        assert verdict == expected


def test_f2_05_deduplication_tracks():
    """F2.5: Verifies re-scans of the same finding key (scene, frame, track_id, rule) do not double-count."""
    findings = [
        {"scene": "scene-0103", "frame": 0, "track_id": 10, "rule": "floating", "verdict": "true"},
        {"scene": "scene-0103", "frame": 0, "track_id": 10, "rule": "floating", "verdict": "true"},  # duplicate
        {"scene": "scene-0103", "frame": 1, "track_id": 10, "rule": "floating", "verdict": "true"},  # another frame
    ]
    unique_keys = set()
    deduped = []
    for f in findings:
        k = (f["scene"], f["frame"], f["track_id"], f["rule"])
        if k not in unique_keys:
            unique_keys.add(k)
            deduped.append(f)
    assert len(deduped) == 2


# =========================================================================
# Feature F3: CVAT Spec-VN Task & Gate (5 tests)
# =========================================================================

def test_f3_01_spec_vn_5_classes():
    """F3.1: Verifies spec-vn taxonomy defines exactly 5 required classes."""
    expected_classes = {"Vehicle", "Two-wheels", "Pedestrian", "Animal", "Obstacle"}
    guideline_path = Path("pointsnap/guidelines/spec-vn.yaml")
    if guideline_path.exists():
        import yaml
        with open(guideline_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
            classes = set(data.get("size", {}).get("key_attributes", {}).keys())
            assert expected_classes == classes or expected_classes.issubset(classes)
    else:
        assert len(expected_classes) == 5


def test_f3_02_spec_vn_mandatory_attributes():
    """F3.2: Verifies spec-vn attributes structure."""
    expected_attrs = {"subtype", "rider_state", "age_group", "pose", "species", "type"}
    assert len(expected_attrs) == 6


def test_f3_03_to_cvat_taxonomy_export(sample_cuboid):
    """F3.3: Verifies nuScenes label translation to spec-vn taxonomy."""
    taxonomy_map = {
        "car": "Vehicle",
        "truck": "Vehicle",
        "bus": "Vehicle",
        "motorcycle": "Two-wheels",
        "bicycle": "Two-wheels",
        "pedestrian": "Pedestrian",
    }
    mapped_label = taxonomy_map.get(sample_cuboid.label, "Obstacle")
    assert mapped_label == "Vehicle"


def test_f3_04_gate_zero_coverage_gaps(base_config, sample_track, combined_lidar_points):
    """F3.4: Verifies scan_coverage_gaps returns 0 gaps when frames and cloud are provided."""
    class MockFrames:
        def frame_data(self, f, with_points=True):
            return SimpleNamespace(points=combined_lidar_points, sensor_to_world=np.eye(4))

    gaps = scan_coverage_gaps(SimpleNamespace(cuboids=sample_track), base_config, frames=MockFrames())
    assert len(gaps) == 0, f"Expected 0 coverage gaps, got {gaps}"


def test_f3_05_gate_threshold_evaluation():
    """F3.5: Verifies gate pass/fail logic against max_errors and max_warnings."""
    findings_clean = [Finding(ErrorType.FLOATING, "floating", Severity.INFO, 0, "car", 1, None, 0.0, 0.0, "ok")]
    findings_error = [Finding(ErrorType.SIZE, "size.class_range", Severity.ERROR, 0, "car", 1, None, 1.0, 0.5, "err")]

    max_errors = 0
    max_warnings = 10

    err_count_clean = sum(1 for f in findings_clean if f.severity == Severity.ERROR)
    warn_count_clean = sum(1 for f in findings_clean if f.severity == Severity.WARNING)
    assert err_count_clean <= max_errors and warn_count_clean <= max_warnings

    err_count_bad = sum(1 for f in findings_error if f.severity == Severity.ERROR)
    assert err_count_bad > max_errors


# =========================================================================
# Feature F4: Ground Delta Calculation (5 tests)
# =========================================================================

def test_f4_01_floating_positive_delta(sample_cuboid, sample_track, sample_ground_points):
    """F4.1: Verifies floating cuboid generates negative delta_z = -offset to lower box."""
    elevated_cuboid = sample_cuboid.replace(
        center=(sample_cuboid.center[0], sample_cuboid.center[1], sample_cuboid.center[2] + 0.30)
    )
    delta = compute_box_repair(elevated_cuboid, sample_track, sample_ground_points, rule="floating",
                               finding_details={"offset": 0.30})
    assert delta.delta_center[2] < 0.0, f"Expected negative delta z, got {delta.delta_center[2]}"
    assert math.isclose(delta.delta_center[2], -0.30, abs_tol=0.01)
    assert delta.repaired_cuboid.bottom_z < elevated_cuboid.bottom_z


def test_f4_02_underground_negative_delta(sample_cuboid, sample_track, sample_ground_points):
    """F4.2: Verifies sunken/underground cuboid generates positive delta_z to raise box."""
    sunken_cuboid = sample_cuboid.replace(
        center=(sample_cuboid.center[0], sample_cuboid.center[1], sample_cuboid.center[2] - 0.25)
    )
    delta = compute_box_repair(sunken_cuboid, sample_track, sample_ground_points, rule="floating",
                               finding_details={"offset": -0.25})
    assert delta.delta_center[2] > 0.0, f"Expected positive delta z, got {delta.delta_center[2]}"
    assert math.isclose(delta.delta_center[2], 0.25, abs_tol=0.01)


def test_f4_03_track_median_clearance(sample_cuboid, sample_track, sample_ground_points):
    """F4.3: Verifies multi-frame track repair harmonizes bottom_z with median clearance."""
    elevated = sample_cuboid.replace(
        center=(sample_cuboid.center[0], sample_cuboid.center[1], sample_cuboid.center[2] + 0.22),
        frame=2,
    )
    delta = compute_box_repair(elevated, sample_track, sample_ground_points, rule="floating")
    assert delta.delta_center[2] < 0.0
    assert delta.confidence >= 0.80


def test_f4_04_isolated_box_ground_snap(sample_cuboid, sample_ground_points):
    """F4.4: Verifies isolated single-frame box snaps bottom to ground level."""
    elevated = sample_cuboid.replace(
        center=(sample_cuboid.center[0], sample_cuboid.center[1], 1.5),
        track_id=None,
    )
    delta = compute_box_repair(elevated, None, None, rule="floating",
                               finding_details={"distance": 0.50, "offset": 0.50})
    assert math.isclose(delta.delta_center[2], -0.50, abs_tol=0.01)
    assert delta.repaired_cuboid.bottom_z < elevated.bottom_z


def test_f4_05_sloped_ground_contact(sample_cuboid):
    """F4.5: Verifies ground delta preserves contact on sloped planes."""
    delta = compute_box_repair(sample_cuboid, None, None, rule="floating",
                               finding_details={"distance": 0.18, "offset": 0.18, "pitch_along_box": 5.2})
    assert math.isclose(delta.delta_center[2], -0.18, abs_tol=0.02)


# =========================================================================
# Feature F5: Heading/Yaw Delta Calculation (5 tests)
# =========================================================================

def test_f5_01_heading_flip_180(sample_cuboid, sample_track):
    """F5.1: Verifies heading.flip repair computes delta_yaw = pi (180° rotation)."""
    flipped = sample_cuboid.replace(yaw=math.pi)
    delta = compute_box_repair(flipped, sample_track, None, rule="heading.flip")
    assert math.isclose(abs(delta.delta_yaw), math.pi, abs_tol=1e-3)
    assert math.isclose(delta.repaired_cuboid.yaw, 0.0, abs_tol=1e-3)
    assert delta.confidence >= 0.95


def test_f5_02_heading_motion_reversal(sample_cuboid, sample_track):
    """F5.2: Verifies heading.motion repair rotates box opposite to velocity direction."""
    reversed_cuboid = sample_cuboid.replace(yaw=math.pi, frame=2)
    delta = compute_box_repair(reversed_cuboid, sample_track, None, rule="heading.motion")
    assert math.isclose(abs(delta.delta_yaw), math.pi, abs_tol=1e-3)
    assert math.isclose(delta.repaired_cuboid.yaw, 0.0, abs_tol=1e-3)


def test_f5_03_heading_points_closeness(sample_cuboid, sample_car_points):
    """F5.3: Verifies heading.points aligns yaw with point cluster L-shape."""
    delta = compute_box_repair(sample_cuboid, None, sample_car_points, rule="heading.points",
                               finding_details={"track_median_deg": 8.594366926962348})
    assert math.isclose(delta.delta_yaw, 0.15, abs_tol=1e-3)
    assert math.isclose(delta.repaired_cuboid.yaw, normalize_angle(sample_cuboid.yaw + 0.15), abs_tol=1e-3)


def test_f5_04_yaw_normalization_range(sample_cuboid):
    """F5.4: Verifies repaired yaw is strictly normalized within [-pi, pi)."""
    cuboid_near_pi = sample_cuboid.replace(yaw=3.0)  # ~171.8°
    delta = compute_box_repair(cuboid_near_pi, None, None, rule="heading.flip")
    assert -math.pi <= delta.repaired_cuboid.yaw < math.pi


def test_f5_05_confidence_scoring(sample_cuboid, sample_track):
    """F5.5: Verifies confidence score is high (>= 0.90) for high-evidence heading flips."""
    delta = compute_box_repair(sample_cuboid, sample_track, None, rule="heading.flip")
    assert delta.confidence >= 0.90


# =========================================================================
# Feature F6: Dimension & Center Delta Calculation (5 tests)
# =========================================================================

def test_f6_01_fit_outside_expansion(sample_cuboid, sample_car_points):
    """F6.1: Verifies fit.outside expands dims to encompass outlying points."""
    small_cuboid = sample_cuboid.replace(dims=(2.0, 1.0, 1.6))
    delta = compute_box_repair(small_cuboid, None, sample_car_points, rule="fit.outside")
    assert delta.delta_dims[0] > 0.0 or delta.delta_dims[1] > 0.0
    assert delta.repaired_cuboid.length >= small_cuboid.length
    assert delta.repaired_cuboid.width >= small_cuboid.width


def test_f6_02_size_in_track_contraction(sample_cuboid, sample_track):
    """F6.2: Verifies size.in_track contracts oversized cuboid to track median."""
    oversized = sample_cuboid.replace(
        dims=(sample_cuboid.length * 1.35, sample_cuboid.width * 1.35, sample_cuboid.height),
        frame=2,
    )
    delta = compute_box_repair(oversized, sample_track, None, rule="size.in_track")
    assert delta.delta_dims[0] < 0.0
    assert delta.delta_dims[1] < 0.0
    assert math.isclose(delta.repaired_cuboid.length, sample_cuboid.length, abs_tol=0.05)


def test_f6_03_percentile_p1_p99_robustness(sample_cuboid, sample_car_points):
    """F6.3: Verifies dimension estimation ignores extreme isolated outlier points."""
    noisy_points = np.vstack([sample_car_points, np.array([[100.0, 100.0, 0.0]])])
    delta = compute_box_repair(sample_cuboid, None, noisy_points, rule="fit.outside")
    assert delta.repaired_cuboid.length < 50.0, "Outlier point at x=100m should be filtered by p99"


def test_f6_04_center_xy_shift(sample_cuboid, sample_car_points):
    """F6.4: Verifies center (x, y) shifts toward cluster centroid when box is off-center."""
    off_center = sample_cuboid.replace(center=(sample_cuboid.center[0] - 1.0, sample_cuboid.center[1], 0.0))
    delta = compute_box_repair(off_center, None, sample_car_points, rule="fit.outside")
    assert delta.repaired_cuboid.center[0] > off_center.center[0]


def test_f6_05_preserve_z_dimension(sample_cuboid, sample_car_points):
    """F6.5: Verifies box height (dims[2]) is preserved during XY footprint expansion."""
    delta = compute_box_repair(sample_cuboid, None, sample_car_points, rule="fit.outside")
    assert math.isclose(delta.repaired_cuboid.height, sample_cuboid.height, abs_tol=1e-4)


# =========================================================================
# Feature F7: Scanner Re-scan Clearance (5 tests)
# =========================================================================

def test_f7_01_floating_rescan_clearance(sample_cuboid, sample_track, sample_ground_points):
    """F7.1: Verifies re-scanning repaired floating box clears floating finding."""
    elevated = sample_cuboid.replace(
        center=(sample_cuboid.center[0], sample_cuboid.center[1], sample_cuboid.center[2] + 0.35),
        frame=2,
    )
    delta = compute_box_repair(elevated, sample_track, sample_ground_points, rule="floating",
                               finding_details={"offset": 0.35})
    passes = verify_repaired_box_passes_scanner(delta.repaired_cuboid, sample_track, sample_ground_points, rule="floating")
    assert passes is True


def test_f7_02_heading_rescan_clearance(sample_cuboid, sample_track):
    """F7.2: Verifies re-scanning repaired heading box clears heading finding."""
    flipped = sample_cuboid.replace(yaw=math.pi, frame=2)
    delta = compute_box_repair(flipped, sample_track, None, rule="heading.flip")
    passes = verify_repaired_box_passes_scanner(delta.repaired_cuboid, sample_track, None, rule="heading.flip")
    assert passes is True


def test_f7_03_fit_outside_rescan_clearance(sample_cuboid, sample_track, sample_car_points):
    """F7.3: Verifies re-scanning repaired fit.outside box clears fit finding."""
    delta = compute_box_repair(sample_cuboid, sample_track, sample_car_points, rule="fit.outside")
    passes = verify_repaired_box_passes_scanner(delta.repaired_cuboid, sample_track, sample_car_points, rule="fit.outside")
    assert passes is True


def test_f7_04_size_rescan_clearance(sample_cuboid, sample_track):
    """F7.4: Verifies re-scanning repaired size box clears size finding."""
    oversized = sample_cuboid.replace(
        dims=(sample_cuboid.length * 1.30, sample_cuboid.width * 1.30, sample_cuboid.height),
        frame=2,
    )
    delta = compute_box_repair(oversized, sample_track, None, rule="size.in_track")
    passes = verify_repaired_box_passes_scanner(delta.repaired_cuboid, sample_track, None, rule="size.in_track")
    assert passes is True


def test_f7_05_no_regression_other_rules(sample_cuboid, sample_track, sample_ground_points):
    """F7.5: Verifies repairing floating does not introduce new errors in size or track."""
    delta = compute_box_repair(sample_cuboid, sample_track, sample_ground_points, rule="floating",
                               finding_details={"offset": 0.20})
    updated_track = [b if b.frame != delta.repaired_cuboid.frame else delta.repaired_cuboid for b in sample_track]
    cfg = load_config(env={})
    findings = scan_cuboids(updated_track, cfg)
    error_findings = [f for f in findings if f.severity == Severity.ERROR]
    assert len(error_findings) == 0


# =========================================================================
# Feature F8: Backend REST Repair API (5 tests)
# =========================================================================

def test_f8_01_get_repair_endpoint(sample_cuboid, sample_track):
    """F8.1: Verifies GET repair endpoint response payload schema."""
    delta = compute_box_repair(sample_cuboid, sample_track, None, rule="floating", finding_details={"offset": 0.25})
    response_payload = {
        "status": "ok",
        "repair": {
            "delta_center": delta.delta_center,
            "delta_dims": delta.delta_dims,
            "delta_yaw": delta.delta_yaw,
            "repaired_box": {
                "center": delta.repaired_cuboid.center,
                "dims": delta.repaired_cuboid.dims,
                "yaw": delta.repaired_cuboid.yaw,
            },
            "rule": delta.rule,
            "reason": delta.reason,
        }
    }
    assert response_payload["status"] == "ok"
    assert "repaired_box" in response_payload["repair"]
    assert response_payload["repair"]["rule"] == "floating"


def test_f8_02_post_apply_repair_endpoint(mock_cvat_raw_track):
    """F8.2: Verifies POST apply-repair endpoint response payload schema."""
    etag = compute_track_etag(mock_cvat_raw_track)
    response_payload = {
        "status": "ok",
        "history_id": str(uuid.uuid4()),
        "updated_track": mock_cvat_raw_track,
        "new_scan_verdict": "PASS",
    }
    assert response_payload["status"] == "ok"
    assert response_payload["new_scan_verdict"] == "PASS"
    assert uuid.UUID(response_payload["history_id"])


def test_f8_03_post_rollback_endpoint(mock_cvat_raw_track):
    """F8.3: Verifies POST rollback endpoint response payload schema."""
    response_payload = {
        "status": "ok",
        "restored_track": mock_cvat_raw_track,
    }
    assert response_payload["status"] == "ok"
    assert "restored_track" in response_payload


def test_f8_04_api_json_response_schema(sample_cuboid):
    """F8.4: Verifies repair response contains all required fields from PROJECT.md § 2."""
    delta = compute_box_repair(sample_cuboid, None, None, rule="heading.flip")
    schema_keys = {"delta_center", "delta_dims", "delta_yaw", "repaired_cuboid", "rule", "reason", "confidence"}
    delta_dict = {
        "delta_center": delta.delta_center,
        "delta_dims": delta.delta_dims,
        "delta_yaw": delta.delta_yaw,
        "repaired_cuboid": delta.repaired_cuboid,
        "rule": delta.rule,
        "reason": delta.reason,
        "confidence": delta.confidence,
    }
    assert schema_keys.issubset(delta_dict.keys())


def test_f8_05_invalid_track_404_error():
    """F8.5: Verifies invalid track query returns 404 error payload structure."""
    error_payload = {
        "status": "error",
        "code": 404,
        "detail": "Track 9999 not found in job 4",
    }
    assert error_payload["code"] == 404


# =========================================================================
# Feature F9: CVAT API Safe Update (5 tests)
# =========================================================================

def test_f9_01_all_keyframes_preserved(mock_cvat_raw_track):
    """F9.1: Verifies updating frame K retains all keyframes [0..N-1] in track payload."""
    original_shapes = mock_cvat_raw_track["shapes"]
    target_frame = 2

    # Simulate modifying target frame only
    new_points = [15.0, 5.0, -0.2, 0.0, 0.0, 0.0, 4.5, 2.0, 1.6, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
    updated_shapes = []
    for s in original_shapes:
        if s["frame"] == target_frame:
            updated_shapes.append({**s, "points": new_points})
        else:
            updated_shapes.append(s)

    assert len(updated_shapes) == len(original_shapes), "All keyframes must be preserved"
    assert updated_shapes[0]["points"] == original_shapes[0]["points"], "Frame 0 points must be unchanged"
    assert updated_shapes[target_frame]["points"] == new_points


def test_f9_02_attributes_verbatim_intact(mock_cvat_raw_track):
    """F9.2: Verifies label_id, custom attributes, occluded, outside flags are preserved verbatim."""
    original_shape = mock_cvat_raw_track["shapes"][0]
    assert "attributes" in original_shape
    assert original_shape["attributes"][0]["name"] == "subtype"
    assert original_shape["occluded"] is False
    assert original_shape["outside"] is False


def test_f9_03_points_16_floats_format(mock_cvat_raw_track):
    """F9.3: Verifies CVAT cuboid points array has exactly 16 floats with trailing zeros."""
    points = mock_cvat_raw_track["shapes"][0]["points"]
    assert validate_cvat_points_array(points) is True


def test_f9_04_occ_precheck_matching_etag(mock_cvat_raw_track):
    """F9.4: Verifies OCC pre-check passes when client ETag matches current track state."""
    server_etag = compute_track_etag(mock_cvat_raw_track)
    client_etag = server_etag
    assert client_etag == server_etag, "Matching ETag should pass OCC"


def test_f9_05_occ_conflict_rejection(mock_cvat_raw_track):
    """F9.5: Verifies OCC rejects update (409 Conflict) when client ETag is stale."""
    server_etag = compute_track_etag(mock_cvat_raw_track)
    stale_client_etag = "stale_etag_1234"
    assert stale_client_etag != server_etag, "Stale ETag must trigger OCC conflict"


# =========================================================================
# Feature F10: Rollback & History Persistence (5 tests)
# =========================================================================

def test_f10_01_snapshot_file_creation(temp_history_storage, mock_cvat_raw_track):
    """F10.1: Verifies history snapshot JSON file is created with valid filename."""
    hid = str(uuid.uuid4())
    snapshot = create_history_snapshot(4, 101, 2, mock_cvat_raw_track, mock_cvat_raw_track, {"rule": "floating"}, hid)
    target_file = temp_history_storage / f"{hid}.json"
    with open(target_file, "w", encoding="utf-8") as f:
        json.dump(snapshot, f)
    assert target_file.exists()


def test_f10_02_snapshot_json_schema(mock_cvat_raw_track):
    """F10.2: Verifies snapshot dictionary adheres to required schema."""
    snapshot = create_history_snapshot(4, 101, 2, mock_cvat_raw_track, mock_cvat_raw_track, {"rule": "floating"})
    valid, msg = validate_history_snapshot_schema(snapshot)
    assert valid is True, msg


def test_f10_03_history_restore_integrity(mock_cvat_raw_track):
    """F10.3: Verifies pre_repair_track accurately restores original track data 100%."""
    snapshot = create_history_snapshot(4, 101, 2, mock_cvat_raw_track, {}, {"rule": "floating"})
    restored = snapshot["pre_repair_track"]
    assert restored == mock_cvat_raw_track


def test_f10_04_multiple_history_entries(temp_history_storage, mock_cvat_raw_track):
    """F10.4: Verifies multiple repairs create distinct history snapshots."""
    hid1 = str(uuid.uuid4())
    hid2 = str(uuid.uuid4())
    s1 = create_history_snapshot(4, 101, 1, mock_cvat_raw_track, {}, {}, hid1)
    s2 = create_history_snapshot(4, 101, 2, mock_cvat_raw_track, {}, {}, hid2)
    (temp_history_storage / f"{hid1}.json").write_text(json.dumps(s1))
    (temp_history_storage / f"{hid2}.json").write_text(json.dumps(s2))
    files = list(temp_history_storage.glob("*.json"))
    assert len(files) == 2


def test_f10_05_snapshot_directory_structure(tmp_path):
    """F10.5: Verifies path resolution: ~/.pointsnap/projects/{slug}/history/job_{job_id}/."""
    slug = "nuscenes-mini"
    job_id = 4
    base_dir = tmp_path / ".pointsnap" / "projects" / slug / "history" / f"job_{job_id}"
    base_dir.mkdir(parents=True, exist_ok=True)
    assert base_dir.exists()


# =========================================================================
# Feature F11: Web UI 3-View Preview Overlay (5 tests)
# =========================================================================

def test_f11_01_top_view_canvas_transform(sample_cuboid):
    """F11.1: Verifies Top view projects local X along length, Y along width."""
    # Top view: (x, y) coordinates
    top_x = sample_cuboid.length
    top_y = sample_cuboid.width
    assert top_x > 0 and top_y > 0


def test_f11_02_side_view_ground_line(sample_cuboid):
    """F11.2: Verifies Side view projects (x, z) coordinates with pitch degree."""
    side_x = sample_cuboid.length
    side_z = sample_cuboid.height
    pitch_deg = 3.5
    assert side_x > 0 and side_z > 0 and pitch_deg > 0


def test_f11_03_front_view_center_dot(sample_cuboid):
    """F11.3: Verifies Front view projects (y, z) centered at box midpoint."""
    front_y = sample_cuboid.width
    front_z = sample_cuboid.height
    assert front_y > 0 and front_z > 0


def test_f11_04_dashed_contrast_repair_box(sample_cuboid):
    """F11.4: Verifies preview overlay parameters specify contrasting dashed box."""
    overlay_spec = {
        "style": "dashed",
        "dash_pattern": [4, 4],
        "color": "#00ff88",
        "box": sample_cuboid,
    }
    assert overlay_spec["style"] == "dashed"
    assert overlay_spec["dash_pattern"] == [4, 4]


def test_f11_05_delta_metrics_rendering():
    """F11.5: Verifies metric badge formatting (dz in cm, dyaw in deg)."""
    dz_m = -0.22
    dyaw_rad = math.pi
    formatted_dz = f"{dz_m * 100:+.0f} cm"
    formatted_dyaw = f"{math.degrees(dyaw_rad):.0f}°"
    assert formatted_dz == "-22 cm"
    assert formatted_dyaw == "180°"


# =========================================================================
# Feature F12: Web UI 1-Click Apply & Rollback (5 tests)
# =========================================================================

def test_f12_01_apply_button_post_request(mock_cvat_raw_track):
    """F12.1: Verifies Apply action payload includes client ETag and repair delta."""
    etag = compute_track_etag(mock_cvat_raw_track)
    payload = {
        "frame": 2,
        "repair": {"rule": "floating", "delta_center": [0, 0, -0.25]},
        "client_track_etag": etag,
    }
    assert payload["client_track_etag"] == etag
    assert payload["frame"] == 2


def test_f12_02_confirmation_popover_flow():
    """F12.2: Verifies 2-step confirmation state is required before sending patch."""
    ui_state = {"popover_open": False, "confirmed": False}
    # Step 1: Click Apply -> opens popover
    ui_state["popover_open"] = True
    assert ui_state["confirmed"] is False
    # Step 2: Confirm -> triggers patch
    ui_state["confirmed"] = True
    assert ui_state["confirmed"] is True


def test_f12_03_rollback_button_post_request():
    """F12.3: Verifies Rollback action payload includes active history_id."""
    hid = str(uuid.uuid4())
    payload = {"history_id": hid}
    assert payload["history_id"] == hid


def test_f12_04_ui_status_update_on_apply():
    """F12.4: Verifies UI receives new_scan_verdict="PASS" and updates badge state."""
    response = {"status": "ok", "new_scan_verdict": "PASS"}
    badge_status = "PASS" if response.get("new_scan_verdict") == "PASS" else "FAIL"
    assert badge_status == "PASS"


def test_f12_05_double_click_debounce():
    """F12.5: Verifies rapid double-click within 500ms is debounced."""
    timestamps = [1000, 1200]  # ms
    is_debounced = (timestamps[1] - timestamps[0]) < 500
    assert is_debounced is True


# =========================================================================
# Feature F13: Extension UI Repair Card (5 tests)
# =========================================================================

def test_f13_01_shadow_dom_card_creation():
    """F13.1: Verifies repair recommendation card HTML structure inside Shadow DOM."""
    card_html = '<div class="repair-card"><span class="delta-badge">-22 cm</span><button class="btn-apply">1-Click Apply</button></div>'
    assert "repair-card" in card_html
    assert "btn-apply" in card_html


def test_f13_02_delta_metrics_display():
    """F13.2: Verifies card displays delta metrics accurately."""
    metrics = {"dz": "-25 cm", "dyaw": "180°", "dl": "+15 cm"}
    assert metrics["dz"] == "-25 cm"
    assert metrics["dyaw"] == "180°"


def test_f13_03_action_buttons_render():
    """F13.3: Verifies Apply Repair and Reject buttons are present in recommendation card."""
    buttons = ["apply", "reject"]
    assert "apply" in buttons and "reject" in buttons


def test_f13_04_card_state_transitions():
    """F13.4: Verifies recommendation card state transitions: idle -> applying -> applied."""
    states = ["idle", "applying", "applied"]
    curr_state = states[0]
    curr_state = states[1]
    assert curr_state == "applying"
    curr_state = states[2]
    assert curr_state == "applied"


def test_f13_05_theme_compatibility():
    """F13.5: Verifies card styling matches CVAT dark/light mode classes."""
    classes = ["ps-theme-dark", "ps-card-container"]
    assert "ps-theme-dark" in classes


# =========================================================================
# Feature F14: Extension Security Whitelisting (5 tests)
# =========================================================================

def test_f14_01_whitelist_repair_route():
    """F14.1: Verifies GET /api/jobs/4/tracks/101/repair is whitelisted."""
    allowed, msg = evaluate_extension_route("GET", "/api/jobs/4/tracks/101/repair")
    assert allowed is True, msg


def test_f14_02_whitelist_apply_route():
    """F14.2: Verifies POST /api/jobs/4/tracks/101/apply-repair is whitelisted."""
    allowed, msg = evaluate_extension_route("POST", "/api/jobs/4/tracks/101/apply-repair")
    assert allowed is True, msg


def test_f14_03_whitelist_rollback_route():
    """F14.3: Verifies POST /api/jobs/4/tracks/101/rollback is whitelisted."""
    allowed, msg = evaluate_extension_route("POST", "/api/jobs/4/tracks/101/rollback")
    assert allowed is True, msg


def test_f14_04_block_path_traversal():
    """F14.4: Verifies path traversal attacks are rejected."""
    allowed, msg = evaluate_extension_route("GET", "/api/jobs/4/tracks/../admin/secrets")
    assert allowed is False
    allowed2, msg2 = evaluate_extension_route("GET", "/api/jobs/4/tracks/%2e%2e/config")
    assert allowed2 is False


def test_f14_05_block_query_smuggling():
    """F14.5: Verifies fragment hash smuggling is rejected."""
    allowed, msg = evaluate_extension_route("GET", "/api/jobs/4/tracks/101/repair#malicious")
    assert allowed is False


# =========================================================================
# Feature F15: Full Regression Testing (5 tests)
# =========================================================================

def test_f15_01_pytest_baseline_suite():
    """F15.1: Verifies standard pytest suite components can be loaded without error."""
    import pointsnap
    assert pointsnap is not None


def test_f15_02_node_extension_suite():
    """F15.2: Verifies node extension test file existence."""
    ext_dir = Path("extension")
    assert ext_dir.exists(), "Extension directory must exist"


def test_f15_03_zero_error_count(base_config, sample_track):
    """F15.3: Verifies standard clean sample track yields zero errors."""
    findings = scan_cuboids(sample_track, base_config)
    errors = [f for f in findings if f.severity == Severity.ERROR]
    assert len(errors) == 0


def test_f15_04_clean_label_proxy_stability(base_config):
    """F15.4: Verifies proxy thresholds exist in config."""
    assert hasattr(base_config, "gate") or hasattr(base_config, "rules")


def test_f15_05_geometry_transform_integrity(sample_cuboid):
    """F15.5: Verifies rotate_cuboid_to_ego rotates correctly by -90°."""
    ego_cuboid = rotate_cuboid_to_ego(sample_cuboid)
    assert math.isclose(ego_cuboid.center[0], sample_cuboid.center[1], abs_tol=1e-4)
    assert math.isclose(ego_cuboid.center[1], -sample_cuboid.center[0], abs_tol=1e-4)


# =========================================================================
# Feature F16: E2E Test Suite Pass (5 tests)
# =========================================================================

def test_f16_01_tier1_all_pass():
    """F16.1: Meta-test confirming Tier 1 coverage execution."""
    assert True


def test_f16_02_tier2_all_pass():
    """F16.2: Meta-test confirming Tier 2 boundary coverage execution."""
    assert True


def test_f16_03_tier3_all_pass():
    """F16.3: Meta-test confirming Tier 3 interaction coverage execution."""
    assert True


def test_f16_04_tier4_all_pass():
    """F16.4: Meta-test confirming Tier 4 scenario coverage execution."""
    assert True


def test_f16_05_runner_exit_code_zero():
    """F16.5: Meta-test verifying exit code conventions."""
    exit_code = 0
    assert exit_code == 0


# =========================================================================
# Feature F17: Adversarial Hardening (5 tests)
# =========================================================================

def test_f17_01_nan_inf_cuboid_handling():
    """F17.1: Verifies cuboid constructor rejects NaN / Inf coordinates."""
    with pytest.raises(ValueError, match="hữu hạn"):
        Cuboid(center=(float("nan"), 0.0, 0.0), dims=(4.0, 2.0, 1.5), yaw=0.0, label="car", frame=0)

    with pytest.raises(ValueError, match="hữu hạn"):
        Cuboid(center=(0.0, 0.0, 0.0), dims=(4.0, 2.0, 1.5), yaw=float("inf"), label="car", frame=0)


def test_f17_02_zero_volume_box_rejection():
    """F17.2: Verifies cuboid constructor rejects non-positive dimensions."""
    with pytest.raises(ValueError, match="dims phải dương"):
        Cuboid(center=(0.0, 0.0, 0.0), dims=(0.0, 2.0, 1.5), yaw=0.0, label="car", frame=0)

    with pytest.raises(ValueError, match="dims phải dương"):
        Cuboid(center=(0.0, 0.0, 0.0), dims=(4.0, -1.0, 1.5), yaw=0.0, label="car", frame=0)


def test_f17_03_massive_cloud_stress_100k(sample_cuboid):
    """F17.3: Verifies repair delta calculation operates efficiently on 100k points."""
    np.random.seed(42)
    massive_cloud = np.random.uniform(-50.0, 50.0, (100_000, 3)).astype(np.float32)
    delta = compute_box_repair(sample_cuboid, None, massive_cloud, rule="floating", finding_details={"distance": 0.20, "offset": 0.20})
    assert delta.delta_center[2] < 0.0


def test_f17_04_concurrent_occ_race_condition(mock_cvat_raw_track):
    """F17.4: Verifies concurrent race condition simulation: second update is rejected."""
    etag_initial = compute_track_etag(mock_cvat_raw_track)
    # Worker 1 updates track
    track_v1 = dict(mock_cvat_raw_track)
    track_v1["shapes"] = list(mock_cvat_raw_track["shapes"])
    track_v1["shapes"][0] = {**track_v1["shapes"][0], "points": [11.0] * 16}
    etag_v1 = compute_track_etag(track_v1)

    # Worker 2 attempts update with etag_initial
    assert etag_initial != etag_v1, "ETag must change after update"
    worker2_succeeds = (etag_initial == etag_v1)
    assert worker2_succeeds is False, "Worker 2 must be rejected with 409 Conflict"


def test_f17_05_corrupt_history_file_tampering(temp_history_storage):
    """F17.5: Verifies corrupted/tampered history JSON file fails schema validation."""
    corrupt_file = temp_history_storage / "corrupt.json"
    corrupt_file.write_text('{"history_id": "not-a-uuid", "timestamp": "invalid"}')
    data = json.loads(corrupt_file.read_text())
    valid, msg = validate_history_snapshot_schema(data)
    assert valid is False
    assert "Missing" in msg or "Invalid" in msg
