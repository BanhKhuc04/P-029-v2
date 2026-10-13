"""Kiểm tra khử False Alarm khi xe đỗ gác bánh vỉa hè (curb step ground)."""

from __future__ import annotations

import numpy as np
import pytest

from pointsnap.core.config import load_config
from pointsnap.core.ground import ring_ground_for_box
from pointsnap.core.model import Cuboid
from pointsnap.detectors.floating import detect_floating_scene


class MockGroundFrames:
    def __init__(self, points: np.ndarray):
        self._pts = points

    def frame_data(self, frame: int, with_points: bool = True):
        from pointsnap.core.model import FrameData
        return FrameData(frame=frame, points=self._pts if with_points else None)


def test_ring_ground_detects_curb_support():
    """Kiểm tra ring_ground_for_box nhận diện địa hình vỉa hè và đáy box tựa vỉa hè."""
    # Xe dài 4m, rộng 2m, cao 1.5m. Đáy box ở z = 0.15m (tựa vỉa hè)
    box = Cuboid(
        center=(0.0, 0.0, 0.9),  # bottom_z = 0.9 - 1.5/2 = 0.15m
        dims=(4.0, 2.0, 1.5),
        yaw=0.0,
        label="car",
        frame=0,
        track_id=1,
    )

    # Tạo point cloud mặt đất xung quanh:
    # Bên phải (y < -1.0): lòng đường z = 0.0m
    # Bên trái (y > 1.0): vỉa hè z = 0.15m
    pts_road = []
    for x in np.linspace(-3, 3, 20):
        for y in np.linspace(-2.5, -1.2, 10):
            pts_road.append([x, y, 0.0])

    pts_curb = []
    for x in np.linspace(-3, 3, 20):
        for y in np.linspace(1.2, 2.5, 10):
            pts_curb.append([x, y, 0.15])

    points = np.array(pts_road + pts_curb, dtype=np.float32)

    est = ring_ground_for_box(points, box)
    assert est.curb_step_m is not None
    assert est.curb_step_m >= 0.10  # Chênh lệch vỉa hè ~15 cm
    assert est.is_curb_supported is True  # Đáy box tựa đúng độ cao vỉa hè


def test_floating_detector_no_false_alarm_on_curb():
    """Bộ phát hiện floating không báo nhầm khi xe đỗ vỉa hè."""
    config = load_config()

    box = Cuboid(
        center=(0.0, 0.0, 0.9),
        dims=(4.0, 2.0, 1.5),
        yaw=0.0,
        label="car",
        frame=0,
        track_id=1,
    )

    pts_road = [[x, y, 0.0] for x in np.linspace(-3, 3, 20) for y in np.linspace(-2.5, -1.2, 10)]
    pts_curb = [[x, y, 0.15] for x in np.linspace(-3, 3, 20) for y in np.linspace(1.2, 2.5, 10)]
    points = np.array(pts_road + pts_curb, dtype=np.float32)

    frames = MockGroundFrames(points)
    findings = detect_floating_scene([box], frames, config.floating)

    # Không được báo lỗi lơ lửng
    assert len(findings) == 0
