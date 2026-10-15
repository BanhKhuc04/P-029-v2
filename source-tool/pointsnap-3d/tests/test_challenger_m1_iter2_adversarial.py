"""Adversarial Challenge Test Suite for Milestone 1 Iteration 2.

Challenger: challenger_m1_iter2_1 (EMPIRICAL CHALLENGER)
Focus: Adversarial verification of the subtype bypass elimination in check_track and scan_cuboids.

Mission:
1. Construct test cuboids WITH attrs={'subtype': 'car'} having aggressive track anomalies:
   - 50m / 100m track jump
   - Swapped IDs between tracks
   - Long occlusion (> 8 frames) and long interpolation
   - Track splits, reuse ID, and static shifts
2. Scan with default configuration (`load_config()`) and `spec-vn.yaml` configuration.
3. Verify that `check_track` and `scan_cuboids` return EXACTLY 0 track findings across both configurations.
4. Verify that geometric errors on the same boxes (`floating`, `heading.flip`, `fit.outside`) are 100% detected.
5. Include positive controls demonstrating that enabling track rules detects all anomalies, confirming
   that the test harness is active and zero findings are solely due to rule suppression.
"""

from __future__ import annotations

import dataclasses
import math
from pathlib import Path
from types import SimpleNamespace
from typing import Sequence

import numpy as np
import pytest

from pointsnap.adapters.cvat.reader import JobData
from pointsnap.core.config import Config, load_config
from pointsnap.core.model import Cuboid, FrameData, Severity
from pointsnap.core.scanner import DEFAULT_DETECTORS, check_track, scan_cuboids


# ==============================================================================
# Helper Generators and Fixtures
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
    for box in boxes:
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
        n_in = 60
        in_2d = np.column_stack([
            rng.uniform(-l * 0.3, l * 0.3, n_in),
            rng.uniform(-w * 0.3, w * 0.3, n_in),
        ])
        in_xy = in_2d @ rot + np.array(box.center[:2])
        in_z = rng.uniform(box.bottom_z + 0.35, box.top_z - 0.05, n_in)
        parts.append(np.column_stack([in_xy, in_z]))
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


@pytest.fixture
def cfg_default() -> Config:
    return load_config(env={})


@pytest.fixture
def cfg_spec_vn() -> Config:
    spec_path = Path(__file__).resolve().parents[1] / "pointsnap/guidelines/spec-vn.yaml"
    return load_config(spec_path, env={})


# ==============================================================================
# 1. Adversarial Track Jump with attrs={'subtype': 'car'}
# ==============================================================================


@pytest.mark.parametrize("jump_distance", [50.0, 100.0, 500.0])
def test_adversarial_subtype_jump_zero_track_findings(cfg_default, cfg_spec_vn, jump_distance):
    """Adversarial Jump (50m, 100m, 500m) trên cuboid có attrs={'subtype': 'car'}.

    Kiểm chứng:
    - check_track() trên cfg_default và cfg_spec_vn đều trả về đúng []
    - scan_cuboids() trên cfg_default và cfg_spec_vn đều trả về đúng 0 track findings
    - Positive control: Bật track_jump=True phát hiện chính xác track.jump
    """
    boxes = [
        Cuboid((0.0, 0.0, 0.0), (4.5, 1.8, 1.5), 0.0, "car", 0, track_id=1, attrs={"subtype": "car"}),
        Cuboid((jump_distance, 0.0, 0.0), (4.5, 1.8, 1.5), 0.0, "car", 1, track_id=1, attrs={"subtype": "car"}),
    ]
    job = SimpleNamespace(cuboids=boxes)

    # 1. check_track trả về []
    assert check_track(job, cfg_default) == []
    assert check_track(job, cfg_spec_vn) == []

    # 2. scan_cuboids trả về 0 track findings
    findings_def = scan_cuboids(job, cfg_default)
    assert [f for f in findings_def if f.rule.startswith("track.")] == []

    findings_vn = scan_cuboids(job, cfg_spec_vn)
    assert [f for f in findings_vn if f.rule.startswith("track.")] == []

    # 3. Positive control: Khi bật track_jump, lỗi nhảy track phải được phát hiện
    cfg_jump = dataclasses.replace(cfg_default, rules=dataclasses.replace(cfg_default.rules, track_jump=True))
    findings_jump = check_track(job, cfg_jump)
    assert any(f.rule == "track.jump" for f in findings_jump), "Positive control failed: track.jump not detected!"


# ==============================================================================
# 2. Adversarial Track ID Swap with attrs={'subtype': 'car'}
# ==============================================================================


def test_adversarial_subtype_id_swap_zero_track_findings(cfg_default, cfg_spec_vn):
    """Adversarial ID Swap giữa 2 xe cùng có attrs={'subtype': 'car'}.

    Kiểm chứng:
    - check_track() trả về [] trên cả cfg_default và cfg_spec_vn
    - scan_cuboids() trả về 0 track findings trên cả cfg_default và cfg_spec_vn
    - Positive control: Bật track_id_swap=True phát hiện chính xác track.id_swap
    """
    points_map = {f: np.empty((0, 3)) for f in range(4)}
    frames = MultiFrameSource(points_map)

    boxes = []
    for f in range(4):
        for tid, subtype in ((1, "car"), (2, "car")):
            side = tid - 1 if f < 2 else 2 - tid
            boxes.append(Cuboid((10.0 + 2.0 * f, 3.0 * side, 0.8), (4.5, 1.9, 1.6), 0.0,
                                "Vehicle", f, track_id=tid, attrs={"subtype": subtype}))
    job = SimpleNamespace(cuboids=boxes)

    # 1. check_track trả về []
    assert check_track(job, cfg_default, frames) == []
    assert check_track(job, cfg_spec_vn, frames) == []

    # 2. scan_cuboids trả về 0 track findings
    assert [f for f in scan_cuboids(job, cfg_default, frames=frames) if f.rule.startswith("track.")] == []
    assert [f for f in scan_cuboids(job, cfg_spec_vn, frames=frames) if f.rule.startswith("track.")] == []

    # 3. Positive control: Bật track_id_swap=True phát hiện lỗi track.id_swap
    cfg_swap = dataclasses.replace(cfg_spec_vn, rules=dataclasses.replace(cfg_spec_vn.rules, track_id_swap=True))
    findings_swap = check_track(job, cfg_swap, frames)
    assert any(f.rule == "track.id_swap" and f.frame == 2 and f.severity is Severity.ERROR for f in findings_swap)


# ==============================================================================
# 3. Adversarial Long Occlusion & Interpolation with attrs={'subtype': 'car'}
# ==============================================================================


def test_adversarial_subtype_long_occlusion_and_interpolation_zero_findings(cfg_default, cfg_spec_vn):
    """Adversarial Long Occlusion (8 frame liên tiếp) và nội suy dài trên box có attrs={'subtype': 'car'}.

    Kiểm chứng:
    - check_track() và scan_cuboids() đều trả về 0 track findings
    - Positive control: Bật track_occluded_long=True phát hiện lỗi
    """
    points_map = {f: np.empty((0, 3)) for f in range(10)}
    frames = MultiFrameSource(points_map)

    boxes = [
        Cuboid((10.0 + f * 2.0, 0.0, 0.8), (4.5, 1.9, 1.6), 0.0, "Vehicle", f, track_id=1,
               attrs={"subtype": "car", "occluded": (1 <= f <= 8)})
        for f in range(10)
    ]
    job = SimpleNamespace(cuboids=boxes)

    assert check_track(job, cfg_default, frames) == []
    assert check_track(job, cfg_spec_vn, frames) == []
    assert [f for f in scan_cuboids(job, cfg_default, frames=frames) if f.rule.startswith("track.")] == []
    assert [f for f in scan_cuboids(job, cfg_spec_vn, frames=frames) if f.rule.startswith("track.")] == []

    # Positive control: Bật track_occluded_long=True
    cfg_occ = dataclasses.replace(cfg_spec_vn, rules=dataclasses.replace(cfg_spec_vn.rules, track_occluded_long=True))
    findings_occ = check_track(job, cfg_occ, frames)
    assert any(f.rule == "track.occluded_long" and f.severity is Severity.WARNING for f in findings_occ)


# ==============================================================================
# 4. Simultaneous Complex Scene: 0 Track Findings + 100% Geometric Errors Detected
# ==============================================================================


def test_adversarial_subtype_simultaneous_track_anomalies_and_geometric_errors(cfg_default, cfg_spec_vn):
    """Stress test đa track kết hợp đồng thời:
    - Bất thường track dữ dội:
      * Track 1: Nhảy vị trí 50m tại frame 7
      * Track 2 & 3: Hoán đổi ID (swapped IDs) tại frame 1
      * Track 3: Bị che khuất kéo dài (long occlusion) từ frame 2..4
      * Track 4: Tách track / tái sử dụng ID (split / reuse ID)
      * Track 5: Dịch chuyển tĩnh (static shift 0.6m)
      * TẤT CẢ CUBOID đều mang attrs={'subtype': 'car'}
    - Lỗi hình học cố ý cấy trên các box đó:
      * Track 1 (frame 4): Lỗi 'floating' (+30cm so với mặt đất)
      * Track 3 (frame 1): Lỗi 'heading.flip' (xoay 180 độ pi rad)
      * Track 2 (frame 1): Lỗi 'fit.outside' (box bị co nhỏ khiến điểm rơi ra ngoài)

    Kiểm chứng tuyệt đối:
    1. EXACTLY 0 track findings (không một lỗi track.* nào bị lọt)
    2. 100% lỗi hình học (floating, heading.flip, fit.outside) được phát hiện chính xác
    """
    ground_z = -1.80
    cuboids: list[Cuboid] = []
    points_map: dict[int, np.ndarray] = {}

    # Track 1: Moving car có 50m jump ở frame 7, floating ở frame 4
    for f in range(10):
        x = float(f * 3) if f != 7 else float(f * 3 + 50.0)
        z_center = ground_z + 0.8 + (0.30 if f == 4 else 0.0)
        is_kf = (f in (0, 1, 8, 9))
        cuboids.append(Cuboid(center=(x, 0.0, z_center), dims=(4.5, 1.9, 1.6), yaw=0.0,
                              label="car", frame=f, track_id=1, keyframe=is_kf, attrs={"subtype": "car"}))

    # Track 2 & 3: Moving cars swap vị trí ở frame 1, fit.outside trên Track 2, heading.flip trên Track 3
    for f in range(4):
        s2 = 1.0 if f != 1 else -1.0
        s3 = -1.0 if f != 1 else 1.0
        dims2 = (3.2, 1.4, 1.6) if f == 1 else (4.5, 1.9, 1.6)
        yaw3 = math.pi if f == 1 else 0.0
        occ3 = (f >= 2)
        cuboids.append(Cuboid(center=(10.0 + f * 2.0, s2 * 3.0, ground_z + 0.8), dims=dims2, yaw=0.0,
                              label="car", frame=f, track_id=2, keyframe=True, attrs={"subtype": "car"}))
        cuboids.append(Cuboid(center=(10.0 + f * 2.0, s3 * 3.0, ground_z + 0.8), dims=(4.5, 1.9, 1.6), yaw=yaw3,
                              label="car", frame=f, track_id=3, keyframe=True,
                              attrs={"subtype": "car", "occluded": occ3}))

    # Track 4: Reuse ID
    cuboids.append(Cuboid(center=(0.0, 15.0, ground_z + 0.8), dims=(4.5, 1.9, 1.6), yaw=0.0,
                          label="car", frame=0, track_id=4, keyframe=True, attrs={"subtype": "car"}))
    cuboids.append(Cuboid(center=(3.0, 15.0, ground_z + 0.8), dims=(4.5, 1.9, 1.6), yaw=0.0,
                          label="car", frame=1, track_id=4, outside=True, attrs={"subtype": "car"}))
    cuboids.append(Cuboid(center=(25.0, 15.0, ground_z + 0.8), dims=(4.5, 1.9, 1.6), yaw=0.0,
                          label="car", frame=9, track_id=4, keyframe=True, attrs={"subtype": "car"}))

    # Track 5: Static Shift (0.6m)
    for f in range(6):
        shift = 0.6 if f == 2 else 0.0
        cuboids.append(Cuboid(center=(30.0 + shift, 20.0, ground_z + 0.8), dims=(4.5, 1.9, 1.6), yaw=0.0,
                              label="car", frame=f, track_id=5, keyframe=True, attrs={"subtype": "car"}))

    # Tạo point cloud
    for f in range(10):
        frame_boxes = [c for c in cuboids if c.frame == f and not c.outside]
        synth_boxes = list(frame_boxes)
        if f == 1:
            synth_boxes = [c.replace(dims=(4.5, 1.9, 1.6)) if c.track_id == 2 else c for c in synth_boxes]
        points_map[f] = _make_ground_and_vehicle_points(synth_boxes, ground_z=ground_z, seed=42 + f)

    frames = MultiFrameSource(points_map)
    job = JobData(url="adversarial_complex", job_id=99, task_id=1, start_frame=0, stop_frame=9,
                  labels={}, cuboids=cuboids)

    # 1. Quét với cấu hình mặc định (Default Config)
    findings_def = scan_cuboids(job, cfg_default, frames=frames)

    # 1a. Kiểm chứng luật track: Phải có ĐÚNG 0 track findings
    track_findings_def = [f for f in findings_def if f.rule.startswith("track.")]
    assert track_findings_def == [], f"LEAK DETECTED in default config: {track_findings_def}"

    # 1b. Kiểm chứng luật hình học: Phải bắt được ĐỦ 100% 3 lỗi hình học đã cấy
    # Floating: Track 1, frame 4
    floating_findings = [f for f in findings_def if f.rule == "floating"]
    assert len(floating_findings) >= 1, "Failed to detect injected floating error on Track 1"
    flt = next(f for f in floating_findings if f.track_id == 1 and f.frame == 4)
    assert flt.severity in (Severity.WARNING, Severity.ERROR)
    assert pytest.approx(0.30, abs=0.05) == flt.value

    # Heading Flip: Track 3, frame 1
    flip_findings = [f for f in findings_def if f.rule == "heading.flip"]
    assert len(flip_findings) >= 1, "Failed to detect injected heading.flip error on Track 3"
    flip = next(f for f in flip_findings if f.track_id == 3 and f.frame == 1)
    assert flip.severity == Severity.ERROR
    assert flip.value > 150.0

    # Fit Outside: Track 2, frame 1
    outside_findings = [f for f in findings_def if f.rule == "fit.outside"]
    assert len(outside_findings) >= 1, "Failed to detect injected fit.outside error on Track 2"
    out = next(f for f in outside_findings if f.track_id == 2 and f.frame == 1)
    assert out.severity in (Severity.WARNING, Severity.ERROR)

    # 2. Quét với spec-vn.yaml
    findings_vn = scan_cuboids(job, cfg_spec_vn, frames=frames)
    track_findings_vn = [f for f in findings_vn if f.rule.startswith("track.")]
    assert track_findings_vn == [], f"LEAK DETECTED in spec-vn config: {track_findings_vn}"

    # 3. Quét với spec-vn.yaml khi bật floating và fit_outside (được kích hoạt theo guideline)
    cfg_vn_geo = dataclasses.replace(cfg_spec_vn, rules=dataclasses.replace(cfg_spec_vn.rules, floating=True, fit_outside=True))
    # Thay đổi label sang 'Vehicle' để match taxonomy spec-vn
    job_vn = JobData(url="adversarial_complex_vn", job_id=100, task_id=1, start_frame=0, stop_frame=9,
                     labels={}, cuboids=[c.replace(label="Vehicle") for c in cuboids])
    findings_vn_geo = scan_cuboids(job_vn, cfg_vn_geo, frames=frames)
    assert [f for f in findings_vn_geo if f.rule.startswith("track.")] == []
    assert any(f.rule == "floating" and f.track_id == 1 and f.frame == 4 for f in findings_vn_geo)
    assert any(f.rule == "heading.flip" and f.track_id == 3 and f.frame == 1 for f in findings_vn_geo)
    assert any(f.rule == "fit.outside" and f.track_id == 2 and f.frame == 1 for f in findings_vn_geo)


# ==============================================================================
# 5. Boundary Variations: Diversity of Subtypes and Invocation Forms
# ==============================================================================


@pytest.mark.parametrize("subtype_value", [
    "car", "sedan", "suv", "truck", "bus", "van", "pickup", "trailer",
    "construction_vehicle", "motorcycle", "bicycle", "", None
])
def test_adversarial_subtype_parameter_diversity(cfg_default, cfg_spec_vn, subtype_value):
    """Kiểm tra toàn diện tất cả các giá trị subtype khác nhau kết hợp gọi qua:
    - check_track(job, cfg)
    - scan_cuboids(job, cfg)
    - scan_cuboids(bare_list, cfg)
    - scan_cuboids(..., detectors=DEFAULT_DETECTORS)
    Đảm bảo không một trường hợp nào làm rò rỉ lỗi track.
    """
    attrs = {"subtype": subtype_value} if subtype_value is not None else {}
    boxes = [
        Cuboid((0.0, 0.0, 0.0), (4.5, 1.8, 1.5), 0.0, "car", 0, track_id=1, attrs=attrs),
        Cuboid((100.0, 0.0, 0.0), (4.5, 1.8, 1.5), 0.0, "car", 1, track_id=1, attrs=attrs),
    ]
    job = SimpleNamespace(cuboids=boxes)

    # 1. Direct check_track
    assert check_track(job, cfg_default) == []
    assert check_track(job, cfg_spec_vn) == []

    # 2. scan_cuboids with JobData
    assert not any(f.rule.startswith("track.") for f in scan_cuboids(job, cfg_default))
    assert not any(f.rule.startswith("track.") for f in scan_cuboids(job, cfg_spec_vn))

    # 3. scan_cuboids with bare list
    assert not any(f.rule.startswith("track.") for f in scan_cuboids(boxes, cfg_default))
    assert not any(f.rule.startswith("track.") for f in scan_cuboids(boxes, cfg_spec_vn))

    # 4. scan_cuboids with explicit DEFAULT_DETECTORS
    assert not any(f.rule.startswith("track.") for f in scan_cuboids(job, cfg_default, detectors=DEFAULT_DETECTORS))
    assert not any(f.rule.startswith("track.") for f in scan_cuboids(job, cfg_spec_vn, detectors=DEFAULT_DETECTORS))
