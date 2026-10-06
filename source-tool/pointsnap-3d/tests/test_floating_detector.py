"""Kiểm thử bộ phát hiện lơ lửng / lún đất (việc B3)."""

from __future__ import annotations

import numpy as np
import pytest

from pointsnap.core.config import FloatingConfig
from pointsnap.core.model import Cuboid, ErrorType, Severity
from pointsnap.detectors.floating import detect_floating, detect_floating_for_box


@pytest.fixture
def floating_config():
    return FloatingConfig(
        classes=("car", "truck", "bus", "pedestrian"),
        warning_m=0.10,
        error_m=0.20,
        ring_inner_m=0.5,
        ring_outer_m=1.5,
        min_ground_points=10,
    )


def _make_ground_points(z: float = -1.8, num: int = 2000, seed: int = 42) -> np.ndarray:
    rng = np.random.default_rng(seed)
    xs = rng.uniform(-10.0, 10.0, num)
    ys = rng.uniform(-10.0, 10.0, num)
    zs = z + rng.normal(0.0, 0.005, num)
    return np.column_stack([xs, ys, zs])


def test_detect_floating_error_box_raised_25cm(floating_config):
    """Nâng đáy box 25 cm -> Báo lỗi lơ lửng ~25 cm (tiêu chí TASKS.md)."""
    ground_z = -1.80
    pts = _make_ground_points(ground_z)

    # Đáy box ở -1.80 + 0.25 = -1.55. height=1.6 => center_z = -1.55 + 0.8 = -0.75
    car = Cuboid(
        center=(0.0, 0.0, -0.75),
        dims=(4.5, 1.8, 1.6),
        yaw=0.0,
        label="car",
        frame=1,
        track_id=10,
    )

    finding = detect_floating_for_box(car, pts, floating_config)
    assert finding is not None
    assert finding.error_type == ErrorType.FLOATING
    assert finding.rule == "floating"
    assert finding.severity == Severity.ERROR
    assert finding.frame == 1
    assert finding.track_id == 10
    assert finding.threshold == 0.20
    assert finding.value == pytest.approx(0.25, abs=0.02)
    assert "lơ lửng" in finding.message
    assert "25" in finding.message


def test_detect_sunk_warning_box_lowered_15cm(floating_config):
    """Hạ đáy box 15 cm -> Báo Cảnh báo lún đất ~15 cm."""
    ground_z = -1.80
    pts = _make_ground_points(ground_z)

    # Đáy box ở -1.80 - 0.15 = -1.95. height=1.6 => center_z = -1.95 + 0.8 = -1.15
    car = Cuboid(
        center=(0.0, 0.0, -1.15),
        dims=(4.5, 1.8, 1.6),
        yaw=0.0,
        label="car",
        frame=2,
        track_id=12,
    )

    finding = detect_floating_for_box(car, pts, floating_config)
    assert finding is not None
    assert finding.error_type == ErrorType.FLOATING
    assert finding.rule == "floating"
    assert finding.severity == Severity.WARNING
    assert finding.threshold == 0.10
    assert finding.value == pytest.approx(-0.15, abs=0.02)
    assert "lún đất" in finding.message


def test_detect_normal_grounded_box_no_finding(floating_config):
    """Box tiếp đất chuẩn (lệch < 10 cm) -> Không báo lỗi."""
    ground_z = -1.80
    pts = _make_ground_points(ground_z)

    # Đáy box đúng -1.80 (lệch 2 cm do noise). height=1.6 => center_z = -1.00
    car = Cuboid(
        center=(0.0, 0.0, -1.00),
        dims=(4.5, 1.8, 1.6),
        yaw=0.0,
        label="car",
        frame=0,
    )

    finding = detect_floating_for_box(car, pts, floating_config)
    assert finding is None


def test_detect_insufficient_points_reports_no_evidence(floating_config):
    """Vành đai ít điểm ground -> Báo mức Thông tin 'thiếu bằng chứng'."""
    pts = np.array([
        [0.0, 0.0, -1.8],
        [0.1, 0.1, -1.8],
    ])  # Chỉ có 2 điểm

    car = Cuboid(
        center=(0.0, 0.0, -1.0),
        dims=(4.5, 1.8, 1.6),
        yaw=0.0,
        label="car",
        frame=5,
    )

    finding = detect_floating_for_box(car, pts, floating_config)
    assert finding is not None
    assert finding.severity == Severity.INFO
    assert finding.rule == "floating.no_evidence"
    assert "thiếu bằng chứng" in finding.message


def test_detect_skips_outside_and_unsupported_classes(floating_config):
    pts = _make_ground_points(-1.8)

    # outside = True
    car_outside = Cuboid(center=(0, 0, 0), dims=(4, 2, 2), yaw=0, label="car", frame=0, outside=True)
    assert detect_floating_for_box(car_outside, pts, floating_config) is None

    # class không nằm trong floating_config.classes
    cone = Cuboid(center=(0, 0, 0), dims=(0.5, 0.5, 1.0), yaw=0, label="traffic_cone", frame=0)
    assert detect_floating_for_box(cone, pts, floating_config) is None


def test_detect_floating_batch(floating_config):
    pts = _make_ground_points(-1.8)
    car_floating = Cuboid(center=(0, 0, -0.75), dims=(4.5, 1.8, 1.6), yaw=0, label="car", frame=1)
    car_normal = Cuboid(center=(5, 5, -1.0), dims=(4.5, 1.8, 1.6), yaw=0, label="car", frame=1)

    findings = detect_floating([car_floating, car_normal], pts, floating_config)
    assert len(findings) == 1
    assert findings[0].severity == Severity.ERROR
