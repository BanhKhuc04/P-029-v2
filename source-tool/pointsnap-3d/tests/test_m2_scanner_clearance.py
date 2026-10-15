"""Empirical Challenge Test Suite: Scanner Clearance & Multi-Track Stress (Milestone M2).

Tests:
1. Multi-keyframe track construction with mixed defects:
   - Frame 0: normal
   - Frame 1: floating (+0.35m offset)
   - Frame 2: flipped heading (180° flip)
   - Frame 3: fit.outside (undersized width or points extending outside box)
2. Scanner detector validation on defect track.
3. Sequential repair via compute_box_repair.
4. Scanner clearance verification: 0 errors, 0 warnings on repaired track.
5. Permutation robustness across all sequential repair orders.
6. Edge case stress testing: sunken ground, heading motion, and track=None vulnerability.
"""

from __future__ import annotations

import itertools
import math
import numpy as np
import pytest

from pointsnap.core.config import load_config
from pointsnap.core.model import Cuboid, Severity
from pointsnap.core.repair import (
    BoxRepairDelta,
    SimpleFrameSource,
    compute_box_repair,
    verify_repaired_box_passes_scanner,
)
from pointsnap.core.scanner import scan_cuboids
from pointsnap.core.synthetic import inject_floating, inject_heading_rotate


def _generate_synthetic_lidar_frame(
    box: Cuboid,
    ground_z: float = -1.8,
    seed: int = 42,
    noise_std: float = 0.01,
) -> np.ndarray:
    """Tạo point cloud mặt đất z=ground_z và cụm điểm LiDAR thành xe cho một frame."""
    rng = np.random.default_rng(seed)
    # Ground plane: 5000 điểm bao quanh xe trong phạm vi ±12m
    gx = rng.uniform(box.center[0] - 12, box.center[0] + 12, 5000)
    gy = rng.uniform(box.center[1] - 12, box.center[1] + 12, 5000)
    gz = np.full(5000, ground_z) + rng.normal(0, noise_std, 5000)
    ground = np.column_stack([gx, gy, gz])

    # Thân xe: L-shape (mặt trước và mặt hông trái)
    l, w, h = 4.5, 1.9, 1.6
    n_pts = 60
    front = np.column_stack([np.full(n_pts, l / 2), rng.uniform(-w / 2, w / 2, n_pts)])
    left = np.column_stack([rng.uniform(-l / 2, l / 2, n_pts), np.full(n_pts, w / 2)])
    local_2d = np.vstack([front, left]) + rng.normal(0, noise_std, (2 * n_pts, 2))

    c, s = math.cos(box.yaw), math.sin(box.yaw)
    rot = np.array([[c, s], [-s, c]])
    world_xy = local_2d @ rot + np.array(box.center[:2])
    z = rng.uniform(ground_z + 0.3, ground_z + h, len(local_2d))
    car_pts = np.column_stack([world_xy, z])

    return np.vstack([ground, car_pts])


def _build_test_track(n_frames: int = 4, speed: float = 8.0, ground_z: float = -1.8) -> list[Cuboid]:
    """Tạo track chuẩn (ground truth) di chuyển thẳng theo trục X."""
    dims = (4.5, 1.9, 1.6)
    cz = ground_z + dims[2] / 2.0
    return [
        Cuboid(center=(speed * 0.5 * f, 0.0, cz), dims=dims, yaw=0.0, label="car", frame=f, track_id=1)
        for f in range(n_frames)
    ]


def test_multitrack_mixed_defects_detection():
    """Xác nhận scanner phát hiện chính xác cả 3 lỗi hình học hỗn hợp trên track 4 frame:
    - Frame 0: normal
    - Frame 1: floating (+0.35m offset)
    - Frame 2: flipped heading (180° flip)
    - Frame 3: fit.outside (points extending outside box do width co nhỏ)
    """
    clean_track = _build_test_track(4)
    ground_z = -1.8
    pts_by_frame = {f: _generate_synthetic_lidar_frame(clean_track[f], ground_z=ground_z, seed=100 + f) for f in range(4)}

    defect_track = list(clean_track)
    # Frame 1: floating (+0.35m)
    defect_track[1] = defect_track[1].replace(
        center=(defect_track[1].center[0], defect_track[1].center[1], defect_track[1].center[2] + 0.35)
    )
    # Frame 2: flipped heading (180°)
    defect_track[2] = defect_track[2].replace(yaw=math.pi)
    # Frame 3: fit.outside (undersized width=1.0m vs 1.9m)
    defect_track[3] = defect_track[3].replace(dims=(4.5, 1.0, 1.6))

    cfg = load_config()
    frames = SimpleFrameSource(pts_by_frame)
    findings = scan_cuboids(defect_track, config=cfg, frames=frames)

    # Kiểm tra scanner bắt đủ các lỗi
    frame_rules = {(f.frame, f.rule): f.severity for f in findings}
    assert (1, "floating") in frame_rules
    assert frame_rules[(1, "floating")] == Severity.ERROR

    assert (2, "heading.flip") in frame_rules
    assert frame_rules[(2, "heading.flip")] in (Severity.ERROR, Severity.WARNING)

    assert (3, "fit.outside") in frame_rules
    assert frame_rules[(3, "fit.outside")] in (Severity.ERROR, Severity.WARNING)

    # Frame 0 không có lỗi
    f0_findings = [f for f in findings if f.frame == 0 and f.severity in (Severity.ERROR, Severity.WARNING)]
    assert len(f0_findings) == 0


def test_multitrack_sequential_repair_scanner_clearance():
    """Xác nhận việc áp dụng sửa tuần tự từng box qua compute_box_repair triệt tiêu hoàn toàn lỗi:
    re-scan đạt 0 errors, 0 warnings cho các rule được sửa.
    """
    clean_track = _build_test_track(4)
    ground_z = -1.8
    pts_by_frame = {f: _generate_synthetic_lidar_frame(clean_track[f], ground_z=ground_z, seed=200 + f) for f in range(4)}

    defect_track = list(clean_track)
    defect_track[1] = defect_track[1].replace(
        center=(defect_track[1].center[0], defect_track[1].center[1], defect_track[1].center[2] + 0.35)
    )
    defect_track[2] = defect_track[2].replace(yaw=math.pi)
    defect_track[3] = defect_track[3].replace(dims=(4.5, 1.0, 1.6))

    repaired_track = list(defect_track)

    # 1. Repair Frame 1 (floating)
    d1 = compute_box_repair(repaired_track[1], repaired_track, pts_by_frame[1], rule="floating")
    assert d1.delta_center[2] == pytest.approx(-0.35, abs=0.03)
    repaired_track[1] = d1.repaired_cuboid

    # 2. Repair Frame 2 (heading.flip)
    d2 = compute_box_repair(repaired_track[2], repaired_track, pts_by_frame[2], rule="heading.flip", finding_details={"target_yaw_sensor": 0.0})
    assert abs(abs(d2.delta_yaw) - math.pi) < 0.05
    repaired_track[2] = d2.repaired_cuboid

    # 3. Repair Frame 3 (fit.outside)
    d3 = compute_box_repair(repaired_track[3], repaired_track, pts_by_frame[3], rule="fit.outside")
    assert d3.repaired_cuboid.dims[1] == pytest.approx(1.90, abs=0.05)
    repaired_track[3] = d3.repaired_cuboid

    # Re-scan toàn bộ track
    cfg = load_config()
    frames = SimpleFrameSource(pts_by_frame)
    new_findings = scan_cuboids(repaired_track, config=cfg, frames=frames)

    # Kiểm tra: 0 errors, 0 warnings cho các rule sửa
    repaired_rules = {"floating", "heading.flip", "fit.outside"}
    residual_repaired = [f for f in new_findings if f.severity in (Severity.ERROR, Severity.WARNING) and f.rule in repaired_rules]
    assert len(residual_repaired) == 0

    # Kiểm tra: toàn bộ track không còn bất kỳ lỗi nào
    all_residuals = [f for f in new_findings if f.severity in (Severity.ERROR, Severity.WARNING)]
    assert len(all_residuals) == 0


def test_multitrack_sequential_repair_order_invariance():
    """Kiểm tra tính bất biến theo thứ tự sửa: cả 6 hoán vị thứ tự sửa đều cho kết quả 0 lỗi."""
    clean_track = _build_test_track(4)
    ground_z = -1.8
    pts_by_frame = {f: _generate_synthetic_lidar_frame(clean_track[f], ground_z=ground_z, seed=300 + f) for f in range(4)}

    repair_plan = [(1, "floating"), (2, "heading.flip"), (3, "fit.outside")]
    cfg = load_config()
    frames = SimpleFrameSource(pts_by_frame)

    for perm in itertools.permutations(repair_plan):
        cur_track = list(clean_track)
        cur_track[1] = cur_track[1].replace(
            center=(cur_track[1].center[0], cur_track[1].center[1], cur_track[1].center[2] + 0.35)
        )
        cur_track[2] = cur_track[2].replace(yaw=math.pi)
        cur_track[3] = cur_track[3].replace(dims=(4.5, 1.0, 1.6))

        for frame_idx, rule in perm:
            delta = compute_box_repair(cur_track[frame_idx], cur_track, pts_by_frame[frame_idx], rule=rule, finding_details={"target_yaw_sensor": 0.0, "track_median_distance": 0.0})
            cur_track[frame_idx] = delta.repaired_cuboid

        findings = scan_cuboids(cur_track, config=cfg, frames=frames)
        repaired_rules = {"floating", "heading.flip", "fit.outside"}
        repaired_errs = [f for f in findings if f.severity in (Severity.ERROR, Severity.WARNING) and f.rule in repaired_rules]
        assert len(repaired_errs) == 0, f"Thứ tự {perm} để lại lỗi dư trên rule được sửa: {repaired_errs}"



def test_extended_6frame_track_mixed_defects_clearance():
    """Kiểm tra track 6 frame dài hơn với 2 frame bình thường làm baseline ổn định."""
    clean_track = _build_test_track(6)
    ground_z = -1.8
    pts_by_frame = {f: _generate_synthetic_lidar_frame(clean_track[f], ground_z=ground_z, seed=400 + f) for f in range(6)}

    defect_track = list(clean_track)
    defect_track[1] = defect_track[1].replace(
        center=(defect_track[1].center[0], defect_track[1].center[1], defect_track[1].center[2] + 0.35)
    )
    defect_track[2] = defect_track[2].replace(yaw=math.pi)
    defect_track[3] = defect_track[3].replace(dims=(4.5, 1.0, 1.6))

    repaired_track = list(defect_track)
    for frame_idx, rule in [(1, "floating"), (2, "heading.flip"), (3, "fit.outside")]:
        delta = compute_box_repair(repaired_track[frame_idx], repaired_track, pts_by_frame[frame_idx], rule=rule, finding_details={"target_yaw_sensor": 0.0, "track_median_distance": 0.0})
        repaired_track[frame_idx] = delta.repaired_cuboid

    cfg = load_config()
    frames = SimpleFrameSource(pts_by_frame)
    findings = scan_cuboids(repaired_track, config=cfg, frames=frames)
    errs = [f for f in findings if f.severity in (Severity.ERROR, Severity.WARNING)]
    assert len(errs) == 0


def test_verify_repaired_box_passes_scanner_gate():
    """Kiểm tra trực tiếp hàm trợ giúp verify_repaired_box_passes_scanner:
    trả về False trên box lỗi, True trên box đã sửa.
    """
    clean_track = _build_test_track(4)
    ground_z = -1.8
    pts_by_frame = {f: _generate_synthetic_lidar_frame(clean_track[f], ground_z=ground_z, seed=500 + f) for f in range(4)}

    defect_track = list(clean_track)
    defect_track[1] = defect_track[1].replace(
        center=(defect_track[1].center[0], defect_track[1].center[1], defect_track[1].center[2] + 0.35)
    )

    frames = SimpleFrameSource(pts_by_frame)
    # Chưa sửa -> False
    assert verify_repaired_box_passes_scanner(defect_track[1], defect_track, frames, rule="floating") is False

    # Đã sửa -> True
    delta = compute_box_repair(defect_track[1], defect_track, pts_by_frame[1], rule="floating")
    assert verify_repaired_box_passes_scanner(delta.repaired_cuboid, defect_track, frames, rule="floating") is True


def test_edge_case_sunken_underground_clearance():
    """Kiểm tra sửa box lún sâu -30 cm dưới mặt đất trên multi-frame track."""
    clean_track = _build_test_track(4)
    ground_z = -1.8
    pts_by_frame = {f: _generate_synthetic_lidar_frame(clean_track[f], ground_z=ground_z, seed=600 + f) for f in range(4)}

    defect_track = list(clean_track)
    defect_track[1] = defect_track[1].replace(
        center=(defect_track[1].center[0], defect_track[1].center[1], defect_track[1].center[2] - 0.30)
    )

    delta = compute_box_repair(defect_track[1], defect_track, pts_by_frame[1], rule="floating")
    assert delta.delta_center[2] == pytest.approx(+0.30, abs=0.03)

    repaired_track = list(defect_track)
    repaired_track[1] = delta.repaired_cuboid

    cfg = load_config()
    frames = SimpleFrameSource(pts_by_frame)
    findings = scan_cuboids(repaired_track, config=cfg, frames=frames)
    errs = [f for f in findings if f.severity in (Severity.ERROR, Severity.WARNING) and f.rule == "floating"]
    assert len(errs) == 0


def test_adversarial_track_none_handled_gracefully():
    """Xác nhận tính kháng lỗi khi caller truyền track=None:
    compute_box_repair xử lý an toàn không bị TypeError, trả về BoxRepairDelta hợp lệ.
    """
    box = Cuboid(center=(0.0, 0.0, 0.0), dims=(4.5, 1.9, 1.6), yaw=0.0, label="car", frame=0)

    # heading.flip khi track=None không bị crash, xoay 180°
    d_flip = compute_box_repair(box, None, None, rule="heading.flip")  # type: ignore[arg-type]
    assert d_flip.delta_yaw == 0
    assert d_flip.confidence == 0

    # fit.outside khi track=None không bị crash
    d_fit = compute_box_repair(box, None, None, rule="fit.outside")  # type: ignore[arg-type]
    assert isinstance(d_fit, BoxRepairDelta)


def test_adversarial_fit_outside_pad_does_not_trigger_size_in_track_warning():
    """Xác nhận việc sửa fit.outside không kích hoạt cảnh báo phụ size.in_track:
    Khi cụm điểm có p99 - p1 = 1.905m (xấp xỉ width thật 1.90m), thuật toán neo kích thước theo
    trung vị track (1.90m), triệt tiêu hoàn toàn lỗi fit.outside mà không làm lệch kích thước track.
    """
    clean_track = _build_test_track(4)
    ground_z = -1.8
    # Seed 300 tạo ra cụm điểm có p99 - p1 = 1.905m -> w_pts = 2.005m > 2.00m
    pts_by_frame = {f: _generate_synthetic_lidar_frame(clean_track[f], ground_z=ground_z, seed=300 + f) for f in range(4)}

    defect_track = list(clean_track)
    defect_track[3] = defect_track[3].replace(dims=(4.5, 1.0, 1.6))

    delta = compute_box_repair(defect_track[3], defect_track, pts_by_frame[3], rule="fit.outside")
    repaired_track = list(defect_track)
    repaired_track[3] = delta.repaired_cuboid

    cfg = load_config()
    frames = SimpleFrameSource(pts_by_frame)
    findings = scan_cuboids(repaired_track, config=cfg, frames=frames)

    # fit.outside đã hết (0 error, 0 warning)
    fit_findings = [f for f in findings if f.rule == "fit.outside"]
    assert len(fit_findings) == 0

    # Không xuất hiện cảnh báo size.in_track phụ
    size_warnings = [f for f in findings if f.rule == "size.in_track" and f.frame == 3]
    assert len(size_warnings) == 0
    assert len(findings) == 0


