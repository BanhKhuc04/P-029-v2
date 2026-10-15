"""Adversarial Stress Test Suite for Milestone 1: Track Discontinuity Removal.

Challenger: challenger_m1_track_1 (EMPIRICAL CHALLENGER)
Mission:
1. Subject scanner to aggressive synthetic track discontinuity anomalies (jumps, splits,
   long interpolation, reuse ID, occlusions, ID swaps, static shifts) under default configuration.
   Empirically verify 0 findings with rule.startswith("track.") are emitted by scan_cuboids.
2. Simultaneously inject synthetic geometric defects (floating, fit.outside, heading.flip,
   size.class_range) into the anomalous tracks and verify 100% of geometric defects are detected
   with exact locations, rules, and severities.
3. Test edge cases: bare list vs JobData, detectors=DEFAULT_DETECTORS, subtype attribute presence.
4. Verify explicit enablement restores track findings without regressions.
"""

from __future__ import annotations

import dataclasses
import math
from types import SimpleNamespace
from typing import Sequence

import numpy as np
import pytest

from pointsnap.core.box_points import box_point_sets
from pointsnap.core.config import (
    Config,
    FitConfig,
    FloatingConfig,
    HeadingConfig,
    RulesConfig,
    SizeConfig,
    StaticConfig,
    TrackConfig,
    load_config,
)
from pointsnap.core.geometry import to_box_frame
from pointsnap.adapters.cvat.reader import JobData
from pointsnap.core.model import Cuboid, ErrorType, Finding, FrameData, Severity
from pointsnap.core.repair import SimpleFrameSource
from pointsnap.core.scanner import (
    DEFAULT_DETECTORS,
    check_track,
    is_rule_enabled,
    scan_coverage_gaps,
    scan_cuboids,
)
from pointsnap.detectors.track import (
    detect_id_swaps,
    detect_track_errors,
    detect_track_jumps_for_track,
    detect_track_splits,
)


# ==============================================================================
# Test Helpers & Generators
# ==============================================================================


def _make_ground_and_vehicle_points(
    boxes: Sequence[Cuboid],
    ground_z: float = -1.8,
    seed: int = 42,
) -> np.ndarray:
    """Tạo điểm mặt đất phẳng và điểm L-shape trên thân từng box."""
    rng = np.random.default_rng(seed)
    ground_pts = np.column_stack([
        rng.uniform(-30, 30, 8000),
        rng.uniform(-30, 30, 8000),
        np.full(8000, ground_z) + rng.normal(0, 0.005, 8000),
    ])
    parts = [ground_pts]
    for k, box in enumerate(boxes):
        if box.outside:
            continue
        l, w, h = box.dims
        n_side = 60
        front = np.column_stack([
            np.full(n_side, l / 2),
            rng.uniform(-w / 2, w / 2, n_side),
        ])
        side = np.column_stack([
            rng.uniform(-l / 2, l / 2, n_side),
            np.full(n_side, w / 2),
        ])
        local_2d = np.vstack([front, side]) + rng.normal(0, 0.015, (2 * n_side, 2))
        c, s = math.cos(box.yaw), math.sin(box.yaw)
        rot = np.array([[c, s], [-s, c]])
        world_xy = local_2d @ rot + np.array(box.center[:2])
        z = rng.uniform(box.bottom_z + 0.35, box.top_z - 0.05, len(local_2d))
        # Điểm bên trong xe (để box không bị coi là rỗng khi co kích thước)
        n_in = 60
        in_2d = np.column_stack([
            rng.uniform(-l * 0.3, l * 0.3, n_in),
            rng.uniform(-w * 0.3, w * 0.3, n_in),
        ])
        in_xy = in_2d @ rot + np.array(box.center[:2])
        in_z = rng.uniform(box.bottom_z + 0.35, box.top_z - 0.05, n_in)
        parts.append(np.column_stack([in_xy, in_z]))

        # Điểm viền ngoài L-shape (mặt trước và mặt bên)
        parts.append(np.column_stack([world_xy, z]))
    return np.vstack(parts)


class MultiFrameSource:
    """FrameSource đa khung cung cấp point cloud và pose toàn cục."""

    def __init__(self, points_map: dict[int, np.ndarray], poses: dict[int, np.ndarray] | None = None):
        self.points_map = points_map
        self.poses = poses or {f: np.eye(4) for f in points_map.keys()}

    def frame_data(self, frame: int, with_points: bool = True) -> FrameData:
        pts = self.points_map.get(frame)
        if pts is None or not with_points:
            pts = np.empty((0, 3), dtype=np.float64)
        pose = self.poses.get(frame, np.eye(4))
        return FrameData(frame=frame, points=pts, sensor_to_world=pose, timestamp=frame * 0.5)


# ==============================================================================
# 1. Adversarial Stress: Synthetic Track Discontinuity with Default Config
# ==============================================================================


def test_adversarial_track_jump_yields_zero_track_findings():
    """Adversarial Jump: Vận tốc nhảy đột biến 200 m/s giữa các frame."""
    cfg = load_config(env={})
    # Track 1 di chuyển thẳng, nhưng frame 3 nhảy 40 mét
    boxes = [
        Cuboid(center=(0.0, 0.0, -1.0), dims=(4.5, 1.8, 1.6), yaw=0.0, label="car", frame=0, track_id=1,
               attrs={"subtype": "sedan"}),
        Cuboid(center=(5.0, 0.0, -1.0), dims=(4.5, 1.8, 1.6), yaw=0.0, label="car", frame=1, track_id=1,
               attrs={"subtype": "sedan"}),
        Cuboid(center=(10.0, 0.0, -1.0), dims=(4.5, 1.8, 1.6), yaw=0.0, label="car", frame=2, track_id=1,
               attrs={"subtype": "sedan"}),
        Cuboid(center=(50.0, 0.0, -1.0), dims=(4.5, 1.8, 1.6), yaw=0.0, label="car", frame=3, track_id=1,
               attrs={"subtype": "sedan"}),  # Cú nhảy 40m
        Cuboid(center=(20.0, 0.0, -1.0), dims=(4.5, 1.8, 1.6), yaw=0.0, label="car", frame=4, track_id=1,
               attrs={"subtype": "sedan"}),
    ]
    job = JobData(url="test_jump", job_id=1, task_id=1, start_frame=0, stop_frame=4, labels={}, cuboids=boxes)

    # 1. Kiểm tra scan mặc định trả về 0 track findings
    findings = scan_cuboids(job, cfg)
    track_findings = [f for f in findings if f.rule.startswith("track.")]
    assert track_findings == [], f"Expected 0 track findings, got: {track_findings}"

    # 2. Chứng minh bộ phát hiện track nội tại vẫn bắt được nếu rule được bật thủ công
    cfg_enabled = dataclasses.replace(cfg, rules=dataclasses.replace(cfg.rules, track_jump=True))
    findings_enabled = scan_cuboids(job, cfg_enabled)
    jump_findings = [f for f in findings_enabled if f.rule == "track.jump"]
    assert len(jump_findings) > 0, "When track_jump is enabled, detector should catch the 40m jump"


def test_adversarial_track_split_id_yields_zero_track_findings():
    """Adversarial Split: Track 1 kết thúc và Track 2 cùng subtype nối tiếp ngay gần."""
    cfg = load_config(env={})
    # Track 1 chạy frame 0, 1 với v=10m/s (dt=0.5s -> dx=5m). Frame 2 outside.
    # Vị trí ngoại suy ở frame 3: 5.0 + 10.0 * 1.0s = 15.0m.
    # Track 2 bắt đầu ở frame 3 tại x=15.2m (lệch 0.2m < split_max_dist_m 2.0m).
    boxes = [
        Cuboid(center=(0.0, 0.0, -1.0), dims=(4.5, 1.8, 1.6), yaw=0.0, label="car", frame=0, track_id=1,
               attrs={"subtype": "sedan"}),
        Cuboid(center=(5.0, 0.0, -1.0), dims=(4.5, 1.8, 1.6), yaw=0.0, label="car", frame=1, track_id=1,
               attrs={"subtype": "sedan"}),
        Cuboid(center=(10.0, 0.0, -1.0), dims=(4.5, 1.8, 1.6), yaw=0.0, label="car", frame=2, track_id=1,
               attrs={"subtype": "sedan"}, outside=True),
        Cuboid(center=(15.2, 0.0, -1.0), dims=(4.5, 1.8, 1.6), yaw=0.0, label="car", frame=3, track_id=2,
               attrs={"subtype": "sedan"}),  # Track 2 xuất hiện ngay vị trí ngoại suy của track 1
        Cuboid(center=(20.0, 0.0, -1.0), dims=(4.5, 1.8, 1.6), yaw=0.0, label="car", frame=4, track_id=2,
               attrs={"subtype": "sedan"}),
    ]
    job = JobData(url="test_split", job_id=2, task_id=1, start_frame=0, stop_frame=5, labels={}, cuboids=boxes)

    findings = scan_cuboids(job, cfg)
    track_findings = [f for f in findings if f.rule.startswith("track.")]
    assert track_findings == [], f"Expected 0 track findings on split, got: {track_findings}"

    # Bật track_split_id thủ công để kiểm chứng detector
    cfg_enabled = dataclasses.replace(cfg, rules=dataclasses.replace(cfg.rules, track_split_id=True))
    findings_enabled = scan_cuboids(job, cfg_enabled)
    split_findings = [f for f in findings_enabled if f.rule == "track.split_id"]
    assert len(split_findings) > 0, "When track_split_id is enabled, detector should detect split"


def test_adversarial_track_long_interpolation_yields_zero_track_findings():
    """Adversarial Interpolation: 15 frame liên tiếp nội suy di chuyển xa mà không có keyframe."""
    cfg = load_config(env={})
    boxes = []
    for f in range(16):
        is_kf = (f == 0 or f == 15)
        boxes.append(
            Cuboid(center=(float(f * 3), 0.0, -1.0), dims=(4.5, 1.8, 1.6), yaw=0.0, label="car", frame=f,
                   track_id=1, keyframe=is_kf, attrs={"subtype": "sedan"})
        )
    job = JobData(url="test_interp", job_id=3, task_id=1, start_frame=0, stop_frame=15, labels={}, cuboids=boxes)

    findings = scan_cuboids(job, cfg)
    track_findings = [f for f in findings if f.rule.startswith("track.")]
    assert track_findings == [], f"Expected 0 track findings on long interpolation, got: {track_findings}"


def test_adversarial_track_reuse_and_occluded_long_yields_zero_track_findings():
    """Adversarial Reuse & Occlusion: Dùng lại ID sau 10 frame và occluded liên tục."""
    cfg = load_config(env={})
    boxes = [
        # Track 1 xuất hiện rồi outside
        Cuboid(center=(0.0, 0.0, -1.0), dims=(4.5, 1.8, 1.6), yaw=0.0, label="car", frame=0, track_id=1,
               attrs={"subtype": "sedan"}),
        Cuboid(center=(2.0, 0.0, -1.0), dims=(4.5, 1.8, 1.6), yaw=0.0, label="car", frame=1, track_id=1,
               outside=True, attrs={"subtype": "sedan"}),
        # Track 1 tái xuất hiện sau 8 frame (reuse_id)
        Cuboid(center=(30.0, 0.0, -1.0), dims=(4.5, 1.8, 1.6), yaw=0.0, label="car", frame=9, track_id=1,
               attrs={"subtype": "sedan"}),
        # Track 2 bị occluded 10 frame liền (occluded_long)
    ]
    for f in range(10):
        boxes.append(
            Cuboid(center=(0.0, 10.0 + f, -1.0), dims=(4.5, 1.8, 1.6), yaw=0.0, label="car", frame=f,
                   track_id=2, attrs={"subtype": "sedan", "occluded": True})
        )
    job = JobData(url="test_reuse_occ", job_id=4, task_id=1, start_frame=0, stop_frame=10, labels={}, cuboids=boxes)

    findings = scan_cuboids(job, cfg)
    track_findings = [f for f in findings if f.rule.startswith("track.")]
    assert track_findings == [], f"Expected 0 track findings on reuse/occlusion, got: {track_findings}"


def test_adversarial_track_id_swap_yields_zero_track_findings():
    """Adversarial ID Swap: Hai xe cùng subtype sedan đổi chỗ cho nhau ở frame 2."""
    cfg = load_config(env={})
    boxes = []
    for f in range(4):
        for tid in (1, 2):
            side = tid - 1
            if f >= 2:
                side = 1 - side  # swap
            boxes.append(
                Cuboid(center=(10.0 + 3.0 * f, 4.0 * side, -1.0), dims=(4.5, 1.8, 1.6), yaw=0.0,
                       label="car", frame=f, track_id=tid, attrs={"subtype": "sedan"})
            )
    job = JobData(url="test_swap", job_id=5, task_id=1, start_frame=0, stop_frame=4, labels={}, cuboids=boxes)
    frames = MultiFrameSource({f: np.empty((0, 3)) for f in range(4)})

    findings = scan_cuboids(job, cfg, frames=frames)
    track_findings = [f for f in findings if f.rule.startswith("track.")]
    assert track_findings == [], f"Expected 0 track findings on ID swap, got: {track_findings}"


def test_adversarial_track_static_shift_yields_zero_track_findings():
    """Adversarial Static Shift: Vật đứng yên nhưng 1 frame bị dịch tâm 0.6 m."""
    cfg = load_config(env={})
    boxes = []
    poses = {}
    for f in range(6):
        # Hệ xe dịch chuyển, nhưng vật giữ nguyên tọa độ toàn cục (10, 5, -1.0)
        poses[f] = np.eye(4)
        poses[f][0, 3] = float(f * 2)  # xe chạy
        # Box frame 3 bị dịch 0.6m
        shift = 0.6 if f == 3 else 0.0
        # Tọa độ trong hệ cảm biến: inv(poses[f]) @ world
        bx = 10.0 - f * 2 + shift
        boxes.append(
            Cuboid(center=(bx, 5.0, -1.0), dims=(4.5, 1.8, 1.6), yaw=0.0, label="car", frame=f, track_id=1,
                   keyframe=True, attrs={"subtype": "sedan"})
        )
    job = JobData(url="test_static_shift", job_id=6, task_id=1, start_frame=0, stop_frame=6, labels={}, cuboids=boxes)
    frames = MultiFrameSource({f: np.empty((0, 3)) for f in range(6)}, poses=poses)

    findings = scan_cuboids(job, cfg, frames=frames)
    track_findings = [f for f in findings if f.rule.startswith("track.")]
    assert track_findings == [], f"Expected 0 track findings on static shift, got: {track_findings}"


def test_adversarial_default_detectors_explicit_pass():
    """Adversarial Bypass Test: Pass detectors=DEFAULT_DETECTORS explicitly.
    DEFAULT_DETECTORS contains check_track. Even if cuboids have 'subtype' in attrs,
    is_rule_enabled must rigorously filter out all track findings.
    """
    cfg = load_config(env={})
    # Mix of severe jump and split with subtype attrs
    boxes = [
        Cuboid(center=(0.0, 0.0, -1.0), dims=(4.5, 1.8, 1.6), yaw=0.0, label="car", frame=0, track_id=1,
               attrs={"subtype": "sedan"}),
        Cuboid(center=(100.0, 0.0, -1.0), dims=(4.5, 1.8, 1.6), yaw=0.0, label="car", frame=1, track_id=1,
               attrs={"subtype": "sedan"}),
        Cuboid(center=(0.0, 0.0, -1.0), dims=(4.5, 1.8, 1.6), yaw=0.0, label="car", frame=2, track_id=1,
               attrs={"subtype": "sedan"}),
    ]
    job = JobData(url="test_explicit_detectors", job_id=7, task_id=1, start_frame=0, stop_frame=2,
                  labels={}, cuboids=boxes)

    findings = scan_cuboids(job, cfg, detectors=DEFAULT_DETECTORS)
    track_findings = [f for f in findings if f.rule.startswith("track.")]
    assert track_findings == [], f"DEFAULT_DETECTORS leaked track findings: {track_findings}"


# ==============================================================================
# 2. Simultaneous Injection: Geometric Defects + Track Anomalies
# ==============================================================================


def test_simultaneous_track_anomalies_and_geometric_errors():
    """Adversarial Complex Scene:
    Trong cùng một Job/Scene chứa đầy đủ cả 7 loại bất thường track:
    - Track 1: Track jump (40m) + Long interpolation (10 frames)
    - Track 2: ID Swap với Track 3
    - Track 3: ID Swap với Track 2 + Long occlusion
    - Track 4: Reuse ID sau outside
    - Track 5: Static Shift (0.6m)

    Đồng thời tiêm 4 lỗi hình học 3D độc lập:
    - Error 1: 'floating' trên Track 1 ở frame 4 (nâng z lên +30 cm)
    - Error 2: 'fit.outside' trên Track 2 ở frame 1 (co hẹp dims để point cloud tràn ra ngoài)
    - Error 3: 'heading.flip' trên Track 3 ở frame 1 (yaw lật 180 độ)
    - Error 4: 'size.class_range' trên Track 5 (chiều dài 16.0 m vượt trần xe con)

    Yêu cầu nghiệm thu tuyệt đối:
    1. Số lỗi track.* phát hiện được = CHÍNH XÁC 0.
    2. 100% (4/4) lỗi hình học được phát hiện chính xác về rule, frame, track_id và severity.
    """
    cfg = load_config(env={})
    ground_z = -1.80

    # 1. Khởi tạo các track với các bất thường track
    cuboids: list[Cuboid] = []
    points_map: dict[int, np.ndarray] = {}
    poses = {f: np.eye(4) for f in range(12)}

    # Track 1: Moving car có track jump ở frame 7, long interpolation từ frame 2->6
    for f in range(10):
        # Frame 7 nhảy 40m
        x = float(f * 3) if f != 7 else float(f * 3 + 40.0)
        # Nâng z lên +30 cm ở frame 4 (INJECT FLOATING ERROR)
        z_center = ground_z + 0.8 + (0.30 if f == 4 else 0.0)
        is_kf = (f in (0, 1, 8, 9))  # frames 2..7 interpolated
        cuboids.append(
            Cuboid(center=(x, 0.0, z_center), dims=(4.5, 1.9, 1.6), yaw=0.0, label="car", frame=f,
                   track_id=1, keyframe=is_kf, attrs={"subtype": "sedan"})
        )

    # Track 2 & 3: Moving cars swap vị trí ở frame 1
    for f in range(4):
        # Swap side ở frame 1
        s2 = 1.0 if f != 1 else -1.0
        s3 = -1.0 if f != 1 else 1.0
        # INJECT FIT.OUTSIDE trên Track 2 ở frame 1 (co ngắn l, w để points nằm ngoài)
        dims2 = (3.2, 1.4, 1.6) if f == 1 else (4.5, 1.9, 1.6)
        # INJECT HEADING.FLIP trên Track 3 ở frame 1 (xoay pi rad)
        yaw3 = math.pi if f == 1 else 0.0
        occ3 = (f >= 2)  # Long occlusion trên track 3

        cuboids.append(
            Cuboid(center=(10.0 + f * 2.0, s2 * 3.0, ground_z + 0.8), dims=dims2, yaw=0.0,
                   label="car", frame=f, track_id=2, keyframe=True, attrs={"subtype": "sedan"})
        )
        cuboids.append(
            Cuboid(center=(10.0 + f * 2.0, s3 * 3.0, ground_z + 0.8), dims=(4.5, 1.9, 1.6), yaw=yaw3,
                   label="car", frame=f, track_id=3, keyframe=True,
                   attrs={"subtype": "sedan", "occluded": occ3})
        )

    # Track 4: Outside rồi Reuse ID
    cuboids.append(Cuboid(center=(0.0, 15.0, ground_z + 0.8), dims=(4.5, 1.9, 1.6), yaw=0.0,
                          label="car", frame=0, track_id=4, keyframe=True, attrs={"subtype": "sedan"}))
    cuboids.append(Cuboid(center=(3.0, 15.0, ground_z + 0.8), dims=(4.5, 1.9, 1.6), yaw=0.0,
                          label="car", frame=1, track_id=4, outside=True, attrs={"subtype": "sedan"}))
    cuboids.append(Cuboid(center=(25.0, 15.0, ground_z + 0.8), dims=(4.5, 1.9, 1.6), yaw=0.0,
                          label="car", frame=9, track_id=4, keyframe=True, attrs={"subtype": "sedan"}))

    # Track 5: Static Shift (0.6m dịch tâm ở frame 2) + INJECT SIZE.CLASS_RANGE (dài 16m)
    for f in range(6):
        shift = 0.6 if f == 2 else 0.0
        cuboids.append(
            Cuboid(center=(30.0 + shift, 20.0, ground_z + 0.8), dims=(16.0, 1.9, 1.6), yaw=0.0,
                   label="car", frame=f, track_id=5, keyframe=True, attrs={"subtype": "sedan"})
        )

    # Tạo point cloud chuẩn theo các box đúng thực tế
    # Đối với Track 2 ở frame 1: tạo point cloud của kích thước xe chuẩn (4.5, 1.9, 1.6)
    # để khi box bị co (2.2, 1.1, 1.6), điểm sẽ nằm ngoài box -> kích hoạt fit.outside
    ground_pts_base = _make_ground_and_vehicle_points([], ground_z=ground_z)

    for f in range(12):
        frame_boxes = [c for c in cuboids if c.frame == f and not c.outside]
        # Tạo điểm vật cho frame này
        # Nếu là frame 1, bổ sung box ảo kích thước đầy đủ cho Track 2 để sinh điểm vật
        synth_boxes = list(frame_boxes)
        if f == 1:
            synth_boxes = [c.replace(dims=(4.5, 1.9, 1.6)) if c.track_id == 2 else c for c in synth_boxes]
        pts = _make_ground_and_vehicle_points(synth_boxes, ground_z=ground_z, seed=42 + f)
        points_map[f] = pts

    frames = MultiFrameSource(points_map, poses=poses)
    job = JobData(url="adversarial_complex", job_id=99, task_id=1, start_frame=0, stop_frame=11,
                  labels={}, cuboids=cuboids)

    # Thực thi quét
    findings = scan_cuboids(job, cfg, frames=frames)

    # 1. Nghiệm thu luật track: Phải có ĐÚNG 0 track findings
    track_findings = [f for f in findings if f.rule.startswith("track.")]
    assert track_findings == [], f"VIOLATION: Found track findings under default config: {track_findings}"

    # 2. Nghiệm thu luật hình học: Phải bắt được đủ 4 lỗi hình học đã tiêm
    rules_detected = {f.rule for f in findings}
    print("Detected rules in complex scene:", rules_detected)

    # Kiểm tra Floating
    floating_findings = [f for f in findings if f.rule == "floating"]
    assert len(floating_findings) >= 1, "Failed to detect injected floating error on Track 1"
    flt = next(f for f in floating_findings if f.track_id == 1 and f.frame == 4)
    assert flt.severity in (Severity.WARNING, Severity.ERROR)
    assert pytest.approx(0.30, abs=0.05) == flt.value

    # Kiểm tra Heading Flip
    flip_findings = [f for f in findings if f.rule == "heading.flip"]
    assert len(flip_findings) >= 1, "Failed to detect injected heading.flip error on Track 3"
    flip = next(f for f in flip_findings if f.track_id == 3 and f.frame == 1)
    assert flip.severity == Severity.ERROR
    assert flip.value > 150.0  # ~180 degrees

    # Kiểm tra Size Class Range
    size_findings = [f for f in findings if f.rule == "size.class_range"]
    assert len(size_findings) >= 1, "Failed to detect injected size.class_range error on Track 5"
    sz = next(f for f in size_findings if f.track_id == 5)
    assert sz.severity == Severity.ERROR
    assert sz.details.get("dim") == "length" or "dài" in sz.message

    # Kiểm tra Fit Outside
    outside_findings = [f for f in findings if f.rule == "fit.outside"]
    assert len(outside_findings) >= 1, "Failed to detect injected fit.outside error on Track 2"
    out = next(f for f in outside_findings if f.track_id == 2 and f.frame == 1)
    assert out.severity in (Severity.WARNING, Severity.ERROR)

    print("SUCCESS: 0 track findings and 100% geometric findings accurately detected!")


# ==============================================================================
# 3. Invocation Boundaries & Input Diversity
# ==============================================================================


def test_scan_cuboids_with_bare_cuboid_iterable():
    """Kiểm tra gọi scan_cuboids bằng bare list of Cuboids (không qua JobData)."""
    cfg = load_config(env={})
    # List of cuboids với track jumps và splits
    boxes = [
        Cuboid(center=(0.0, 0.0, 0.0), dims=(4.5, 1.8, 1.6), yaw=0.0, label="car", frame=0, track_id=1,
               attrs={"subtype": "sedan"}),
        Cuboid(center=(50.0, 0.0, 0.0), dims=(4.5, 1.8, 1.6), yaw=0.0, label="car", frame=1, track_id=1,
               attrs={"subtype": "sedan"}),
        Cuboid(center=(50.5, 0.0, 0.0), dims=(4.5, 1.8, 1.6), yaw=0.0, label="car", frame=2, track_id=2,
               attrs={"subtype": "sedan"}),
    ]

    findings = scan_cuboids(boxes, cfg)
    track_findings = [f for f in findings if f.rule.startswith("track.")]
    assert track_findings == [], f"Expected 0 track findings from bare list, got: {track_findings}"


def test_coverage_gaps_skips_pose_when_track_rules_disabled():
    """Kiểm tra scan_coverage_gaps không báo thiếu pose cho các luật track đã tắt."""
    cfg = load_config(env={})
    boxes = [
        Cuboid(center=(0.0, 0.0, 0.0), dims=(4.5, 1.8, 1.6), yaw=0.0, label="car", frame=0, track_id=1),
        Cuboid(center=(2.0, 0.0, 0.0), dims=(4.5, 1.8, 1.6), yaw=0.0, label="car", frame=1, track_id=1),
    ]
    job = JobData(url="test_gaps", job_id=8, task_id=1, start_frame=0, stop_frame=1, labels={}, cuboids=boxes)

    # FrameSource không có pose
    class NoPoseFrames:
        def frame_data(self, frame, with_points=False):
            return FrameData(frame=frame, points=np.zeros((0, 3)), sensor_to_world=None)

    gaps = scan_coverage_gaps(job, cfg, frames=NoPoseFrames())
    # Không được báo thiếu pose cho bất kỳ track rule nào (track_jump, track_split_id, etc.)
    for gap in gaps:
        assert "track_" not in gap, f"Pose gap incorrectly reported disabled track rule: {gap}"


def test_all_track_switches_consistently_false():
    """Kiểm tra toàn bộ 7 track switch keys trong config.rules và catalog đều False mặc định."""
    cfg = load_config(env={})
    expected_disabled = [
        "track_jump",
        "track_split_id",
        "track_long_interpolation",
        "track_reuse_id",
        "track_occluded_long",
        "track_id_swap",
        "track_static_shift",
    ]
    for switch in expected_disabled:
        val = getattr(cfg.rules, switch)
        assert val is False, f"Rule switch {switch} is {val}, expected False"

    # Catalog rule id check
    expected_rule_ids = [
        "track.jump",
        "track.split_id",
        "track.long_interpolation",
        "track.reuse_id",
        "track.occluded_long",
        "track.id_swap",
        "track.static_shift",
    ]
    for rid in expected_rule_ids:
        assert is_rule_enabled(rid, cfg) is False, f"is_rule_enabled({rid}) returned True by default!"
