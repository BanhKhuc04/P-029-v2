"""Adversarial challenge tests for Milestone 1: Track Discontinuity Removal.

Challenger: challenger_m1_track_2
Scope:
1. Verify behavior via API coordinator (pointsnap.api.scan_cuboids and pointsnap.web.runner)
   - Default config: ensure NO track findings appear in scan results or Finding objects.
   - Custom config with track_jump: true: ensure track detector runs and detects the jump.
   - Geometric rules (floating, fit, heading, size) are NEVER suppressed or mutated.
2. Verify gate verdict and report serialization (json, html, csv) under default vs custom config.
3. Edge cases: extreme kinematics, supersonic speed, untracked boxes, empty jobs, outside boxes.
"""

from __future__ import annotations

import dataclasses
import json
import math
from pathlib import Path
from unittest.mock import Mock

import numpy as np
import pytest

from pointsnap.adapters.cvat.reader import JobData
from pointsnap.api import report_bytes, scan_cuboids as api_scan_cuboids
from pointsnap.core.config import GateConfig, load_config
from pointsnap.core.gate import gate_verdict
from pointsnap.core.model import Cuboid, ErrorType, Finding, FrameData, Severity
from pointsnap.core.scanner import is_rule_enabled, scan_cuboids
from pointsnap.web.projects import ProjectManager
from pointsnap.web.runner import ScanRunner, finding_to_dict


class MockFrames:
    """Mock FrameSource with flat ground plane at z=0 and sensor_to_world identity."""

    def __init__(self, step_s: float = 0.5):
        self.step_s = step_s
        # Dense ground grid covering -30 to 30m
        axis = np.arange(-30.0, 30.0, 0.15)
        gx, gy = np.meshgrid(axis, axis)
        self.points = np.column_stack([gx.ravel(), gy.ravel(), np.zeros(gx.size)])

    def frame_data(self, frame: int, with_points: bool = True) -> FrameData:
        pts = self.points if with_points else np.empty((0, 3))
        return FrameData(frame, pts, np.eye(4), timestamp=frame * self.step_s)


def make_jumping_track():
    """Track with a distinct kinematic jump at frame 2 (moves from x=2 to x=6.5, delta=2.5m > 2.0m jump threshold)."""
    return [
        Cuboid(center=(0.0, 0.0, 0.8), dims=(4.5, 1.8, 1.6), yaw=0.0, label="car", frame=0, track_id=1),
        Cuboid(center=(2.0, 0.0, 0.8), dims=(4.5, 1.8, 1.6), yaw=0.0, label="car", frame=1, track_id=1),
        Cuboid(center=(6.5, 0.0, 0.8), dims=(4.5, 1.8, 1.6), yaw=0.0, label="car", frame=2, track_id=1),
        Cuboid(center=(6.0, 0.0, 0.8), dims=(4.5, 1.8, 1.6), yaw=0.0, label="car", frame=3, track_id=1),
        Cuboid(center=(8.0, 0.0, 0.8), dims=(4.5, 1.8, 1.6), yaw=0.0, label="car", frame=4, track_id=1),
    ]


def make_split_track():
    """Two tracks within split distance and short time gap."""
    return [
        Cuboid(center=(0.0, 0.0, 0.8), dims=(4.5, 1.8, 1.6), yaw=0.0, label="car", frame=0, track_id=10),
        Cuboid(center=(1.0, 0.0, 0.8), dims=(4.5, 1.8, 1.6), yaw=0.0, label="car", frame=1, track_id=10),
        # Track 10 stops, Track 11 appears right next to it at frame 2
        Cuboid(center=(1.2, 0.0, 0.8), dims=(4.5, 1.8, 1.6), yaw=0.0, label="car", frame=2, track_id=11),
        Cuboid(center=(2.2, 0.0, 0.8), dims=(4.5, 1.8, 1.6), yaw=0.0, label="car", frame=3, track_id=11),
    ]


def make_geometric_violation_boxes():
    """A collection of boxes explicitly violating geometric rules within ground bounds:
    - size.class_range: bus with excessive width (4.5m > 3.2m limit)
    - size.in_track: car length shrinking from 4.5m to 2.2m within track 20
    - heading.flip: car yaw flipping by pi between frame 0 and 1 in track 30
    - fit.overlap: two cars at identical position in frame 0
    - floating: car bottom elevated +0.8m above ground at frame 1 in track 40 (within ground radius)
    """
    return [
        # size.class_range (bus width 4.5m)
        Cuboid(center=(5.0, 0.0, 1.5), dims=(10.0, 4.5, 3.0), yaw=0.0, label="bus", frame=0, track_id=5),
        # size.in_track (track 20)
        Cuboid(center=(10.0, 0.0, 0.8), dims=(4.5, 1.8, 1.6), yaw=0.0, label="car", frame=0, track_id=20),
        Cuboid(center=(12.0, 0.0, 0.8), dims=(2.2, 1.8, 1.6), yaw=0.0, label="car", frame=1, track_id=20),
        # heading.flip (track 30)
        Cuboid(center=(15.0, 0.0, 0.8), dims=(4.5, 1.8, 1.6), yaw=0.0, label="car", frame=0, track_id=30),
        Cuboid(center=(17.0, 0.0, 0.8), dims=(4.5, 1.8, 1.6), yaw=math.pi, label="car", frame=1, track_id=30),
        # fit.overlap (frame 0)
        Cuboid(center=(20.0, 0.0, 0.8), dims=(4.5, 1.8, 1.6), yaw=0.0, label="car", frame=0, track_id=41),
        Cuboid(center=(20.0, 0.0, 0.8), dims=(4.5, 1.8, 1.6), yaw=0.0, label="car", frame=0, track_id=42),
        # floating (track 50, frame 0 bottom=0.0, frame 1 bottom=+0.8m, frame 2 bottom=0.0)
        Cuboid(center=(25.0, 0.0, 0.8), dims=(4.5, 1.8, 1.6), yaw=0.0, label="car", frame=0, track_id=50),
        Cuboid(center=(25.0, 0.0, 1.6), dims=(4.5, 1.8, 1.6), yaw=0.0, label="car", frame=1, track_id=50),
        Cuboid(center=(25.0, 0.0, 0.8), dims=(4.5, 1.8, 1.6), yaw=0.0, label="car", frame=2, track_id=50),
    ]


# ==============================================================================
# 1. API Coordinator & Scanner Behavior Tests
# ==============================================================================

def test_api_coordinator_default_config_suppresses_all_track_findings():
    """Verify pointsnap.api.scan_cuboids produces ZERO track findings under default config."""
    config = load_config(env={})
    frames = MockFrames()

    # Combine jumping, splitting, and geometric boxes
    all_boxes = make_jumping_track() + make_split_track() + make_geometric_violation_boxes()
    job = JobData(url="http://cvat", task_id=1, job_id=1, start_frame=0, stop_frame=4,
                  labels={}, cuboids=all_boxes)

    findings = api_scan_cuboids(job, config, frames)

    # Strictly check that NO finding starts with track.
    track_findings = [f for f in findings if f.rule.startswith("track.")]
    assert track_findings == [], f"Expected 0 track findings, got: {track_findings}"

    # Confirm that geometric findings ARE still found
    geom_rules = {f.rule for f in findings}
    assert any(r.startswith("size.") for r in geom_rules), "Expected size findings to be present"
    assert any(r.startswith("heading.") for r in geom_rules), "Expected heading findings to be present"
    assert any(r.startswith("fit.") for r in geom_rules), "Expected fit findings to be present"
    assert any(r.startswith("floating") for r in geom_rules), "Expected floating findings to be present"


def test_api_coordinator_custom_config_track_jump_triggers_cleanly():
    """When custom configuration with track_jump=True is passed, track detector detects the jump."""
    base_config = load_config(env={})
    custom_rules = dataclasses.replace(base_config.rules, track_jump=True)
    custom_config = dataclasses.replace(base_config, rules=custom_rules)
    frames = MockFrames()

    jumping_boxes = make_jumping_track()
    job = JobData(url="http://cvat", task_id=1, job_id=1, start_frame=0, stop_frame=4,
                  labels={}, cuboids=jumping_boxes)

    findings = api_scan_cuboids(job, custom_config, frames)

    # Must find track.jump
    jump_findings = [f for f in findings if f.rule == "track.jump"]
    assert len(jump_findings) >= 1, f"Expected track.jump finding, got: {findings}"
    jf = jump_findings[0]
    assert jf.error_type == ErrorType.TRACK
    assert jf.frame == 2
    assert jf.track_id == 1
    assert jf.value == pytest.approx(2.5, abs=0.1)

    # Must NOT find other track rules since only track_jump was enabled
    other_track_findings = [f for f in findings if f.rule.startswith("track.") and f.rule != "track.jump"]
    assert other_track_findings == [], f"Only track.jump should be enabled, got other: {other_track_findings}"


def test_api_report_bytes_serialization_default_vs_custom_track_jump():
    """Verify pointsnap.api.report_bytes JSON/HTML/CSV under default and custom config."""
    default_config = load_config(env={})
    frames = MockFrames()
    boxes = make_jumping_track()
    job = JobData(url="http://cvat", task_id=1, job_id=1, start_frame=0, stop_frame=4,
                  labels={}, cuboids=boxes)

    # --- 1. Default config ---
    findings_default = api_scan_cuboids(job, default_config, frames)
    metadata_default = {"point_cloud_available": True, "pose_available": True, "coverage_gaps": []}
    json_bytes = report_bytes(job, findings_default, default_config, "json", metadata_default)
    data = json.loads(json_bytes.decode("utf-8"))

    # Enabled checks & checks must not contain any track.* rule
    assert not any(rule.startswith("track.") for rule in data["enabled_checks"]), \
        f"Track rules found in enabled_checks: {data['enabled_checks']}"
    assert not any(rule.startswith("track.") for rule in data["checks"]), \
        f"Track rules found in checks: {data['checks']}"
    assert not any(f["rule"].startswith("track.") for f in data["findings"]), \
        f"Track findings in JSON report: {data['findings']}"

    # CSV report must have zero track findings
    csv_bytes = report_bytes(job, findings_default, default_config, "csv", metadata_default)
    csv_text = csv_bytes.decode("utf-8-sig")
    assert "track." not in csv_text

    # HTML report must have zero track findings
    html_bytes = report_bytes(job, findings_default, default_config, "html", metadata_default)
    html_text = html_bytes.decode("utf-8")
    assert "track.jump" not in html_text
    assert "track.split_id" not in html_text

    # --- 2. Custom config with track_jump: true ---
    custom_rules = dataclasses.replace(default_config.rules, track_jump=True)
    custom_config = dataclasses.replace(default_config, rules=custom_rules)
    findings_custom = api_scan_cuboids(job, custom_config, frames)

    json_custom_bytes = report_bytes(job, findings_custom, custom_config, "json", metadata_default)
    data_custom = json.loads(json_custom_bytes.decode("utf-8"))

    assert "track.jump" in data_custom["enabled_checks"]
    assert "track.jump" in data_custom["checks"]
    assert any(f["rule"] == "track.jump" for f in data_custom["findings"])


# ==============================================================================
# 2. Web Runner Execution Tests
# ==============================================================================

def test_web_runner_scan_default_project_config_produces_zero_track_findings(tmp_path, monkeypatch):
    """Verify pointsnap.web.runner.ScanRunner emits 0 track findings under default project configuration."""
    from pointsnap.web import runner as runner_mod

    pm = ProjectManager(tmp_path / "home")
    pm.create_project(name="Default Track Test", slug="default-track-test")

    jumping_job = JobData(url="http://cvat", task_id=1, job_id=101, start_frame=0, stop_frame=4,
                          labels={}, cuboids=make_jumping_track())
    frames = MockFrames()

    monkeypatch.setattr(runner_mod, "CvatClient", lambda *args, **kwargs: Mock(url="http://cvat"))
    monkeypatch.setattr(runner_mod, "load_job", lambda *args, **kwargs: jumping_job)
    monkeypatch.setattr(runner_mod, "frames_for_job", lambda *args, **kwargs: (frames, "test frames"))

    runner = ScanRunner(pm)
    run_id = runner.start_scan("default-track-test", 101, flag=False)
    runner._executor.shutdown(wait=True)

    run = runner.get_run("default-track-test", run_id, include_findings=True)
    assert run["status"] == "done"

    # Verify findings.json
    run_dir = pm._project_dir("default-track-test") / "runs" / run_id
    findings_file = run_dir / "findings.json"
    assert findings_file.is_file()
    saved_findings = json.loads(findings_file.read_text(encoding="utf-8"))

    track_findings = [f for f in saved_findings if f["rule"].startswith("track.")]
    assert track_findings == [], f"Expected 0 track findings in runner output, got: {track_findings}"

    # Verify summary.json
    summary_file = run_dir / "summary.json"
    assert summary_file.is_file()
    summary = json.loads(summary_file.read_text(encoding="utf-8"))
    assert summary["num_errors"] == 0
    # Any warnings present must NOT be track warnings
    assert not any(f["rule"].startswith("track.") for f in saved_findings)


def test_web_runner_scan_custom_project_config_detects_track_jump(tmp_path, monkeypatch):
    """Verify pointsnap.web.runner.ScanRunner runs track detector and saves finding when track_jump is enabled in guideline."""
    from pointsnap.web import runner as runner_mod

    pm = ProjectManager(tmp_path / "home")
    pm.create_project(name="Custom Jump Test", slug="custom-jump-test")

    # Explicitly activate track_jump in project guideline
    pm.save_guideline("custom-jump-test", {"rules": {"track_jump": True}})
    effective_cfg = pm.get_effective_config("custom-jump-test")
    assert effective_cfg.rules.track_jump is True
    assert effective_cfg.rules.track_split_id is False

    jumping_job = JobData(url="http://cvat", task_id=1, job_id=102, start_frame=0, stop_frame=4,
                          labels={}, cuboids=make_jumping_track())
    frames = MockFrames()

    monkeypatch.setattr(runner_mod, "CvatClient", lambda *args, **kwargs: Mock(url="http://cvat"))
    monkeypatch.setattr(runner_mod, "load_job", lambda *args, **kwargs: jumping_job)
    monkeypatch.setattr(runner_mod, "frames_for_job", lambda *args, **kwargs: (frames, "test frames"))

    runner = ScanRunner(pm)
    run_id = runner.start_scan("custom-jump-test", 102, flag=False)
    runner._executor.shutdown(wait=True)

    run = runner.get_run("custom-jump-test", run_id, include_findings=True)
    assert run["status"] == "done"

    run_dir = pm._project_dir("custom-jump-test") / "runs" / run_id
    findings_file = run_dir / "findings.json"
    saved_findings = json.loads(findings_file.read_text(encoding="utf-8"))

    jump_findings = [f for f in saved_findings if f["rule"] == "track.jump"]
    assert len(jump_findings) >= 1, f"Expected track.jump in runner findings.json, got: {saved_findings}"

    jf = jump_findings[0]
    assert jf["error_type"] == "track"
    assert jf["frame"] == 2
    assert jf["track_id"] == 1
    assert "details" in jf and isinstance(jf["details"], dict)

    # Confirm other track rules were not emitted
    other_track = [f for f in saved_findings if f["rule"].startswith("track.") and f["rule"] != "track.jump"]
    assert other_track == []


# ==============================================================================
# 3. Geometric Rules Integrity & Non-Suppression Tests
# ==============================================================================

def test_geometric_rules_are_never_suppressed_or_mutated():
    """Verify that disabling track rules does NOT change geometric findings count, severity, or values."""
    default_config = load_config(env={})

    # Enable all track rules for comparison
    all_track_rules = dataclasses.replace(
        default_config.rules,
        track_jump=True,
        track_split_id=True,
        track_long_interpolation=True,
        track_reuse_id=True,
        track_occluded_long=True,
        track_id_swap=True,
        track_static_shift=True,
    )
    all_track_config = dataclasses.replace(default_config, rules=all_track_rules)

    frames = MockFrames()
    boxes = make_geometric_violation_boxes()
    job = JobData(url="http://cvat", task_id=1, job_id=1, start_frame=0, stop_frame=4,
                  labels={}, cuboids=boxes)

    findings_default = api_scan_cuboids(job, default_config, frames)
    findings_all_track = api_scan_cuboids(job, all_track_config, frames)

    # Filter out any track findings from all_track
    geom_default = [f for f in findings_default if not f.rule.startswith("track.")]
    geom_all_track = [f for f in findings_all_track if not f.rule.startswith("track.")]

    assert len(geom_default) > 0, "Geometric findings should be non-empty"
    assert len(geom_default) == len(geom_all_track), \
        f"Geometric findings count mismatch: {len(geom_default)} vs {len(geom_all_track)}"

    # Check each geometric finding matches identically
    def finding_key(f: Finding):
        return (f.rule, f.severity.value, f.frame, f.track_id or -1, f.source_id or -1, str(f.value), str(f.threshold), f.message)

    keys_default = sorted(finding_key(f) for f in geom_default)
    keys_all_track = sorted(finding_key(f) for f in geom_all_track)

    assert keys_default == keys_all_track, "Geometric findings differed between default and track-enabled config!"


def test_extreme_kinematics_does_not_corrupt_geometric_rules():
    """Adversarial stress: supersonic teleportation (10,000m jump) does not crash or corrupt geometric scans."""
    default_config = load_config(env={})
    frames = MockFrames()

    # Supersonic teleportation box with oversized dimension (violating size.class_range)
    teleporting_boxes = [
        Cuboid(center=(0.0, 0.0, 0.8), dims=(4.5, 1.8, 1.6), yaw=0.0, label="car", frame=0, track_id=99),
        Cuboid(center=(10000.0, 5000.0, 0.8), dims=(25.0, 1.8, 1.6), yaw=0.0, label="car", frame=1, track_id=99),
    ]
    job = JobData(url="http://cvat", task_id=1, job_id=1, start_frame=0, stop_frame=1,
                  labels={}, cuboids=teleporting_boxes)

    findings = api_scan_cuboids(job, default_config, frames)

    # Teleportation jump should NOT be reported under default config
    assert not any(f.rule.startswith("track.") for f in findings)

    # Geometric error (size.class_range: length 25.0m, track median 14.75m) MUST be caught cleanly
    size_findings = [f for f in findings if f.rule == "size.class_range"]
    assert len(size_findings) == 1
    assert size_findings[0].frame == 1
    assert size_findings[0].value == 14.75
    assert size_findings[0].value > size_findings[0].threshold


# ==============================================================================
# 4. Edge Cases: Empty Jobs, Untracked Cuboids, Outside Cuboids
# ==============================================================================

def test_edge_case_empty_job_and_untracked_cuboids():
    """Verify empty job and untracked cuboids (track_id=None) behave safely."""
    config = load_config(env={})
    frames = MockFrames()

    # Empty job
    empty_job = JobData(url="http://cvat", task_id=1, job_id=1, start_frame=0, stop_frame=0,
                        labels={}, cuboids=[])
    findings_empty = api_scan_cuboids(empty_job, config, frames)
    assert findings_empty == []

    passed, reasons = gate_verdict(findings_empty, config.gate)
    assert passed is True

    # Untracked cuboid
    untracked_job = JobData(url="http://cvat", task_id=1, job_id=1, start_frame=0, stop_frame=0,
                            labels={}, cuboids=[Cuboid(center=(0, 0, 0.8), dims=(4.5, 1.8, 1.6),
                                                       yaw=0.0, label="car", frame=0, track_id=None)])
    findings_untracked = api_scan_cuboids(untracked_job, config, frames)
    assert not any(f.rule.startswith("track.") for f in findings_untracked)


def test_is_rule_enabled_catalog_consistency():
    """Stress test is_rule_enabled for every known rule catalog item."""
    cfg = load_config(env={})

    # All track rules must return False under default config
    for rule in [
        "track.jump", "track.split_id", "track.long_interpolation",
        "track.reuse_id", "track.occluded_long", "track.id_swap", "track.static_shift"
    ]:
        assert is_rule_enabled(rule, cfg) is False, f"Rule {rule} should be False by default"

    # Default-enabled geometric rules must return True
    for rule in [
        "floating", "size.class_range", "size.in_track",
        "heading.flip", "heading.motion", "heading.points",
        "fit.empty", "fit.outside", "fit.overlap"
    ]:
        assert is_rule_enabled(rule, cfg) is True, f"Rule {rule} should be True by default"

    # fit.loose is False by default in config.yaml, but is enabled when set to True
    assert is_rule_enabled("fit.loose", cfg) is False
    custom_cfg = dataclasses.replace(cfg, rules=dataclasses.replace(cfg.rules, fit_loose=True))
    assert is_rule_enabled("fit.loose", custom_cfg) is True
