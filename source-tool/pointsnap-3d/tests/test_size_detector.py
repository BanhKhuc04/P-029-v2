"""Kiểm thử bộ phát hiện sai kích thước (việc B4)."""

import pytest

from pointsnap.core.config import ClassRangeConfig, InTrackConfig, SizeConfig
from pointsnap.core.model import Cuboid, ErrorType, Severity
from pointsnap.detectors.size import (
    compute_class_ranges,
    detect_size,
    detect_size_class_range_for_box,
    detect_size_in_track,
    get_resolved_class_ranges,
)


@pytest.fixture
def size_config():
    return SizeConfig(
        class_range=ClassRangeConfig(
            percentile_low=1.0,
            percentile_high=99.0,
            warning_margin=0.05,
            error_margin=0.15,
            min_instances=20,
        ),
        manual_ranges={
            "bus": {"length": (6.0, 18.5), "width": (2.2, 3.2), "height": (2.4, 4.5)},
            "trailer": {"length": (2.0, 18.0), "width": (1.5, 3.2), "height": (1.0, 4.5)},
        },
        in_track=InTrackConfig(
            min_keyframes=3,
            excluded_classes=("pedestrian",),
            warning_abs_m=0.10,
            warning_rel=0.05,
            error_abs_m=0.30,
            error_rel=0.15,
            suspect_id_rel=0.30,
        ),
    )


def test_class_range_normal_box_no_finding(size_config):
    """Box car kích thước bình thường (4.5m x 1.8m x 1.6m) -> Không có lỗi."""
    car = Cuboid(center=(0, 0, 0), dims=(4.5, 1.8, 1.6), yaw=0, label="car", frame=0)
    resolved = get_resolved_class_ranges(size_config)
    findings = detect_size_class_range_for_box(car, size_config, resolved)
    assert len(findings) == 0


def test_class_range_error_box_too_small(size_config):
    """Box car dài 2.0 m (quá nhỏ, dưới p1 - 15% = 2.96m) -> Báo Lỗi."""
    car = Cuboid(center=(0, 0, 0), dims=(2.0, 1.8, 1.6), yaw=0, label="car", frame=1, track_id=5)
    resolved = get_resolved_class_ranges(size_config)
    findings = detect_size_class_range_for_box(car, size_config, resolved)
    assert len(findings) == 1
    f = findings[0]
    assert f.error_type == ErrorType.SIZE
    assert f.rule == "size.class_range"
    assert f.severity == Severity.ERROR
    assert f.details["dimension"] == "length"
    assert "chiều dài" in f.message.lower()


def test_class_range_warning_box_slightly_small(size_config):
    """Box car dài 3.2 m (dưới p1 - 5% = 3.30m nhưng trên p1 - 15%) -> Báo Cảnh báo."""
    car = Cuboid(center=(0, 0, 0), dims=(3.2, 1.8, 1.6), yaw=0, label="car", frame=1)
    resolved = get_resolved_class_ranges(size_config)
    findings = detect_size_class_range_for_box(car, size_config, resolved)
    assert len(findings) == 1
    assert findings[0].severity == Severity.WARNING


def test_in_track_error_length_variation(size_config):
    """Track 3 frame, 1 frame dài hơn trung vị 0.8 m (> 0.3 m) -> Báo Lỗi."""
    boxes = [
        Cuboid(center=(0, 0, 0), dims=(4.5, 1.8, 1.6), yaw=0, label="car", frame=0, track_id=1),
        Cuboid(center=(1, 0, 0), dims=(4.5, 1.8, 1.6), yaw=0, label="car", frame=1, track_id=1),
        Cuboid(center=(2, 0, 0), dims=(5.3, 1.8, 1.6), yaw=0, label="car", frame=2, track_id=1),
    ]
    findings = detect_size_in_track(boxes, size_config)
    assert len(findings) == 1
    f = findings[0]
    assert f.error_type == ErrorType.SIZE
    assert f.rule == "size.in_track"
    assert f.severity == Severity.ERROR
    assert f.frame == 2
    assert f.value == pytest.approx(0.8, abs=0.01)


def test_in_track_warning_minor_variation(size_config):
    """Track 3 frame, 1 frame lệch 0.25 m (> max(0.10, 5%*4.5=0.225m) nhưng < 0.30 m) -> Báo Cảnh báo."""
    boxes = [
        Cuboid(center=(0, 0, 0), dims=(4.5, 1.8, 1.6), yaw=0, label="car", frame=0, track_id=1),
        Cuboid(center=(1, 0, 0), dims=(4.5, 1.8, 1.6), yaw=0, label="car", frame=1, track_id=1),
        Cuboid(center=(2, 0, 0), dims=(4.75, 1.8, 1.6), yaw=0, label="car", frame=2, track_id=1),
    ]
    findings = detect_size_in_track(boxes, size_config)
    assert len(findings) == 1
    assert findings[0].severity == Severity.WARNING


def test_in_track_suspect_id_over_30_percent(size_config):
    """Lệch > 30% so với trung vị track -> Có ghi chú nghi nhầm ID."""
    boxes = [
        Cuboid(center=(0, 0, 0), dims=(4.0, 1.8, 1.6), yaw=0, label="car", frame=0, track_id=2),
        Cuboid(center=(1, 0, 0), dims=(4.0, 1.8, 1.6), yaw=0, label="car", frame=1, track_id=2),
        Cuboid(center=(2, 0, 0), dims=(6.0, 1.8, 1.6), yaw=0, label="car", frame=2, track_id=2),  # +50%
    ]
    findings = detect_size_in_track(boxes, size_config)
    assert len(findings) == 1
    assert findings[0].details["suspect_id"] is True
    assert "nghi nhầm ID" in findings[0].message


def test_in_track_ignores_pedestrian(size_config):
    """Không báo lỗi người đi bộ ở kiểu trong track (tiêu chí TASKS.md)."""
    boxes = [
        Cuboid(center=(0, 0, 0), dims=(0.5, 0.5, 1.6), yaw=0, label="pedestrian", frame=0, track_id=3),
        Cuboid(center=(1, 0, 0), dims=(0.8, 0.6, 1.7), yaw=0, label="pedestrian", frame=1, track_id=3),
        Cuboid(center=(2, 0, 0), dims=(1.1, 0.9, 1.5), yaw=0, label="pedestrian", frame=2, track_id=3),
    ]
    findings = detect_size_in_track(boxes, size_config)
    assert len(findings) == 0


def test_in_track_too_few_keyframes_skipped(size_config):
    """Track chỉ có 2 frame (< 3) -> Bỏ qua."""
    boxes = [
        Cuboid(center=(0, 0, 0), dims=(4.5, 1.8, 1.6), yaw=0, label="car", frame=0, track_id=4),
        Cuboid(center=(1, 0, 0), dims=(5.5, 1.8, 1.6), yaw=0, label="car", frame=1, track_id=4),
    ]
    findings = detect_size_in_track(boxes, size_config)
    assert len(findings) == 0


def test_compute_class_ranges():
    """Kiểm tra hàm tính thống kê phân vị."""
    cars = [
        Cuboid(center=(0, 0, 0), dims=(4.0 + i * 0.05, 1.8, 1.6), yaw=0, label="car", frame=i)
        for i in range(30)
    ]
    ranges = compute_class_ranges(cars, percentile_low=10.0, percentile_high=90.0)
    assert "car" in ranges
    assert ranges["car"]["length"][0] < ranges["car"]["length"][1]
