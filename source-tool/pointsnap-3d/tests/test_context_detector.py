"""Kiểm tra DetectionContext và BaseDetector theo kiến trúc DRY."""

from __future__ import annotations

import numpy as np
import pytest

from pointsnap.core.config import load_config
from pointsnap.core.context import DetectionContext, PointCloudCache
from pointsnap.core.model import Cuboid, ErrorType, Finding, FrameData, Severity
from pointsnap.detectors.base import BaseDetector
from pointsnap.detectors.fit import FitDetector
from pointsnap.detectors.floating import FloatingDetector
from pointsnap.detectors.heading import HeadingDetector
from pointsnap.detectors.track import TrackDetector


class DummyFrameSource:
    def __init__(self, num_frames: int = 5):
        self.num_frames = num_frames

    def frame_data(self, frame: int, with_points: bool = True) -> FrameData:
        pts = np.zeros((10, 3), dtype=np.float32) if with_points else np.empty((0, 3), dtype=np.float32)
        s2w = np.eye(4, dtype=np.float64)
        return FrameData(frame=frame, points=pts, sensor_to_world=s2w, timestamp=frame * 0.5)


def test_detection_context_caching():
    config = load_config()
    cuboids = [
        Cuboid(center=(1, 2, 0), dims=(4, 2, 1.5), yaw=0.0, label="car", frame=0, track_id=1),
        Cuboid(center=(2, 2, 0), dims=(4, 2, 1.5), yaw=0.0, label="car", frame=1, track_id=1),
        Cuboid(center=(5, 5, 0), dims=(1, 1, 1.8), yaw=0.0, label="pedestrian", frame=1, track_id=2),
    ]
    source = DummyFrameSource()
    ctx = DetectionContext.from_job(cuboids, config, source)

    # Kiểm tra lazy cached properties
    assert len(ctx.tracks) == 2
    assert len(ctx.tracks[1]) == 2
    assert len(ctx.frames_map[1]) == 2
    assert ctx.unique_frames == [0, 1]

    # Kiểm tra poses
    s2w, ts = ctx.poses
    assert s2w is not None and 0 in s2w and 1 in s2w
    assert ts is not None and ts[1] == 0.5

    # Kiểm tra world centers
    world_pts, has_world = ctx.get_world_centers(cuboids)
    assert has_world is True
    assert world_pts.shape == (3, 3)
    np.testing.assert_allclose(world_pts[0], [1, 2, 0])

    # Kiểm tra point cloud cache
    p0 = ctx.get_points(0)
    assert p0 is not None and p0.shape == (10, 3)
    # Lần thứ hai lấy từ cache
    p0_cached = ctx.get_points(0)
    assert p0_cached is p0


def test_base_detector_subclass():
    class DummyDetector(BaseDetector):
        rule_id = "test.dummy"
        switch_key = "floating"

        def detect(self, ctx: DetectionContext) -> list[Finding]:
            return [
                self.create_finding(
                    rule=self.rule_id,
                    error_type=ErrorType.FLOATING,
                    severity=Severity.WARNING,
                    frame=0,
                    label="car",
                    message="Dummy finding message",
                )
            ]

    detector = DummyDetector()
    assert detector.rule_id == "test.dummy"
    assert detector.switch_key == "floating"

    config = load_config()
    cuboids = [Cuboid(center=(1, 2, 0), dims=(4, 2, 1.5), yaw=0.0, label="car", frame=0)]

    # Gọi theo phong cách callable function cũ: detector(job, config, frames)
    findings = detector(cuboids, config, None)
    assert len(findings) == 1
    assert findings[0].rule == "test.dummy"

    # Khi rule bị tắt
    import dataclasses
    disabled_rules = dataclasses.replace(config.rules, floating=False)
    config_disabled = dataclasses.replace(config, rules=disabled_rules)
    assert detector.is_enabled(config_disabled) is False
    assert len(detector(cuboids, config_disabled, None)) == 0


def test_detector_instances():
    config = load_config()
    cuboids = [
        Cuboid(center=(1, 2, 0), dims=(4, 2, 1.5), yaw=0.0, label="car", frame=0, track_id=1),
        Cuboid(center=(2, 2, 0), dims=(4, 2, 1.5), yaw=0.0, label="car", frame=1, track_id=1),
    ]
    source = DummyFrameSource()
    ctx = DetectionContext.from_job(cuboids, config, source)

    track_det = TrackDetector()
    heading_det = HeadingDetector()
    fit_det = FitDetector()
    floating_det = FloatingDetector()

    assert track_det.is_enabled(config) is False
    assert heading_det.is_enabled(config) is True
    assert fit_det.is_enabled(config) is True
    assert floating_det.is_enabled(config) is True

    # Chạy detect không phát sinh ngoại lệ, track detector luôn trả về rỗng
    track_findings = track_det.detect(ctx)
    assert track_findings == []

    heading_findings = heading_det.detect(ctx)
    assert isinstance(heading_findings, list)
