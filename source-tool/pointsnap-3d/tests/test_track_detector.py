"""Kiểm thử bộ phát hiện đứt track (việc B5)."""

import pytest

from pointsnap.core.config import LongInterpolationConfig, TrackConfig, TrackGroupConfig
from pointsnap.core.model import Cuboid, ErrorType, Severity
from pointsnap.detectors.track import (
    detect_track_errors,
    detect_track_jumps_for_track,
    detect_track_splits,
)


@pytest.fixture
def track_config():
    return TrackConfig(
        keyframe_interval_s=0.5,
        groups={
            "vehicle": TrackGroupConfig(
                classes=("car", "truck", "bus"),
                jump_warning_m=1.0,
                jump_error_m=2.0,
                v_max_mps=30.0,
                split_max_dist_m=2.0,
            ),
            "pedestrian": TrackGroupConfig(
                classes=("pedestrian",),
                jump_warning_m=0.5,
                jump_error_m=1.0,
                v_max_mps=3.0,
                split_max_dist_m=1.0,
            ),
        },
        split_max_gap_frames=3,
        long_interpolation=LongInterpolationConfig(enabled=False, min_frames=2, min_motion_m=1.0),
    )


def test_track_jump_cluster_peaks_only(track_config):
    """Một cú nhảy 2.5 m ở frame 2 làm lệch cả cụm, nhưng CHỈ BÁO FRAME 2 (tiêu chí TASKS.md)."""
    # Xe đi thẳng x = 0, 2, 4, 6, 8 ở frame 0, 1, 2, 3, 4
    # Frame 2 nhảy từ x=4 lên x=6.5 (+2.5 m)
    boxes = [
        Cuboid(center=(0.0, 0.0, 0.0), dims=(4.5, 1.8, 1.6), yaw=0, label="car", frame=0, track_id=1),
        Cuboid(center=(2.0, 0.0, 0.0), dims=(4.5, 1.8, 1.6), yaw=0, label="car", frame=1, track_id=1),
        Cuboid(center=(6.5, 0.0, 0.0), dims=(4.5, 1.8, 1.6), yaw=0, label="car", frame=2, track_id=1),
        Cuboid(center=(6.0, 0.0, 0.0), dims=(4.5, 1.8, 1.6), yaw=0, label="car", frame=3, track_id=1),
        Cuboid(center=(8.0, 0.0, 0.0), dims=(4.5, 1.8, 1.6), yaw=0, label="car", frame=4, track_id=1),
    ]

    findings = detect_track_jumps_for_track(boxes, track_config)
    # Chỉ được báo duy nhất 1 lỗi cho cả cụm
    assert len(findings) == 1
    f = findings[0]
    assert f.error_type == ErrorType.TRACK
    assert f.rule == "track.jump"
    assert f.frame == 2
    assert f.value == pytest.approx(2.5, abs=0.01)
    assert f.severity == Severity.WARNING  # Không có sensor_to_world -> mức Cảnh báo


def test_track_jump_smooth_no_finding(track_config):
    """Xe đi đều mượt mà -> Không báo lỗi."""
    boxes = [
        Cuboid(center=(float(i * 2), 0.0, 0.0), dims=(4.5, 1.8, 1.6), yaw=0, label="car", frame=i, track_id=1)
        for i in range(5)
    ]
    findings = detect_track_jumps_for_track(boxes, track_config)
    assert len(findings) == 0


def test_track_split_id(track_config):
    """Track A dừng ở frame 3, Track B cùng class bắt đầu ở frame 5 cách đó 0.5 m -> Cảnh báo tách ID."""
    track_a = [
        Cuboid(center=(0.0, 0.0, 0.0), dims=(4.5, 1.8, 1.6), yaw=0, label="car", frame=1, track_id=10),
        Cuboid(center=(1.0, 0.0, 0.0), dims=(4.5, 1.8, 1.6), yaw=0, label="car", frame=2, track_id=10),
        Cuboid(center=(2.0, 0.0, 0.0), dims=(4.5, 1.8, 1.6), yaw=0, label="car", frame=3, track_id=10),
    ]
    # Vận tốc track A = 1.0 m / 0.5s = 2.0 m/s. Frame 5 dt=1.0s -> ngoại suy = 2.0 + 2.0*1.0 = 4.0 m
    # Track B ở frame 5 tại x=4.3 m (lệch 0.3 m < 2.0 m)
    track_b = [
        Cuboid(center=(4.3, 0.0, 0.0), dims=(4.5, 1.8, 1.6), yaw=0, label="car", frame=5, track_id=11),
        Cuboid(center=(5.3, 0.0, 0.0), dims=(4.5, 1.8, 1.6), yaw=0, label="car", frame=6, track_id=11),
    ]

    tracks = {10: track_a, 11: track_b}
    findings = detect_track_splits(tracks, track_config)
    assert len(findings) == 1
    f = findings[0]
    assert f.error_type == ErrorType.TRACK
    assert f.rule == "track.split_id"
    assert f.severity == Severity.WARNING
    assert f.frame == 5
    assert f.track_id == 11
    assert "nghi tách ID" in f.message


def test_track_split_id_different_classes_ignored(track_config):
    """Hai track khác class (car vs pedestrian) -> Không báo tách ID."""
    track_car = [Cuboid(center=(0, 0, 0), dims=(4, 2, 2), yaw=0, label="car", frame=1, track_id=1)]
    track_ped = [Cuboid(center=(0.5, 0, 0), dims=(0.6, 0.6, 1.7), yaw=0, label="pedestrian", frame=2, track_id=2)]
    findings = detect_track_splits({1: track_car, 2: track_ped}, track_config)
    assert len(findings) == 0


def test_detect_track_errors_full(track_config):
    """Kiểm thử hàm bao bọc detect_track_errors."""
    track_a = [
        Cuboid(center=(0.0, 0.0, 0.0), dims=(4.5, 1.8, 1.6), yaw=0, label="car", frame=0, track_id=1),
        Cuboid(center=(2.0, 0.0, 0.0), dims=(4.5, 1.8, 1.6), yaw=0, label="car", frame=1, track_id=1),
        Cuboid(center=(6.5, 0.0, 0.0), dims=(4.5, 1.8, 1.6), yaw=0, label="car", frame=2, track_id=1),
        Cuboid(center=(6.0, 0.0, 0.0), dims=(4.5, 1.8, 1.6), yaw=0, label="car", frame=3, track_id=1),
    ]
    findings = detect_track_errors(track_a, track_config)
    assert len(findings) == 1
    assert findings[0].rule == "track.jump"
