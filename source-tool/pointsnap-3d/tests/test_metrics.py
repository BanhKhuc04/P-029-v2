"""Kiểm thử tính toán chỉ số đánh giá Precision, Recall (việc B6)."""

import json
from pointsnap.core.model import ErrorType, Finding, Severity
from pointsnap.eval.metrics import InjectedFault, evaluate_findings, load_injected_faults


def test_evaluate_findings_perfect_match():
    """100% Precision và Recall khi mọi lỗi chèn đều được phát hiện chính xác."""
    faults = [
        InjectedFault(error_type="floating", frame=1, track_id=10, severity="error", delta=0.25),
        InjectedFault(error_type="size", frame=2, track_id=11, severity="warning", delta=0.20),
        InjectedFault(error_type="track", frame=3, track_id=12, severity="error", delta=2.5),
    ]

    findings = [
        Finding(error_type=ErrorType.FLOATING, rule="floating", severity=Severity.ERROR, frame=1, track_id=10, label="car", message="lơ lửng", value=0.248),
        Finding(error_type=ErrorType.SIZE, rule="size.class_range", severity=Severity.WARNING, frame=2, track_id=11, label="car", message="sai kt", value=0.198),
        Finding(error_type=ErrorType.TRACK, rule="track.jump", severity=Severity.ERROR, frame=3, track_id=12, label="car", message="nhảy", value=2.49),
    ]

    report = evaluate_findings(faults, findings, clean_boxes_total=200)

    assert report.overall.recall == 1.0
    assert report.overall.precision == 1.0
    assert report.by_type["floating"].recall == 1.0
    assert report.by_type["size"].recall == 1.0
    assert report.by_type["track"].recall == 1.0
    assert report.by_severity["error"].recall == 1.0
    assert report.by_severity["warning"].recall == 1.0
    # Sai số đo lường trung vị < 3 cm
    assert report.by_type["floating"].median_error < 0.03
    assert report.by_type["size"].median_error < 0.03


def test_evaluate_findings_partial_and_false_alarms():
    """Kiểm tra khi có false negatives và false positives."""
    faults = [
        InjectedFault(error_type="floating", frame=1, track_id=10, severity="error"),
        InjectedFault(error_type="floating", frame=2, track_id=10, severity="error"),  # Bị sót (FN)
    ]

    findings = [
        Finding(error_type=ErrorType.FLOATING, rule="floating", severity=Severity.ERROR, frame=1, track_id=10, label="car", message="lơ lửng"),
        Finding(error_type=ErrorType.FLOATING, rule="floating", severity=Severity.WARNING, frame=5, track_id=99, label="car", message="báo nhầm"),  # FP
    ]

    report = evaluate_findings(faults, findings)
    # Recall = 1 / 2 = 50%
    assert report.by_type["floating"].recall == 0.5
    # Precision = 1 / 2 = 50%
    assert report.by_type["floating"].precision == 0.5


def test_load_injected_faults(tmp_path):
    p = tmp_path / "faults.json"
    p.write_text(json.dumps([
        {"error_type": "floating", "frame": 1, "track_id": 5, "severity": "error", "delta": 0.25}
    ]))
    loaded = load_injected_faults(p)
    assert len(loaded) == 1
    assert loaded[0].error_type == "floating"
    assert loaded[0].delta == 0.25
