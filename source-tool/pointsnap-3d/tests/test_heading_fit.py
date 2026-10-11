"""Kiểm thử luật sai hướng box và box lệch khỏi vật (việc C1)."""

from __future__ import annotations

import math

import numpy as np
import pytest

from pointsnap.core.box_points import box_point_sets, connected_to_box
from pointsnap.core.config import FitConfig, HeadingConfig, load_config
from pointsnap.core.model import Cuboid, ErrorType, Severity
from pointsnap.core.scanner import scan_cuboids
from pointsnap.core.synthetic import (
    inject_dataset,
    inject_fit_duplicate,
    inject_fit_scale,
    inject_fit_shift,
    inject_heading_reverse,
    inject_heading_rotate,
)
from pointsnap.detectors.fit import empty_finding, loose_finding, outside_finding, overlap_findings
from pointsnap.detectors.heading import (
    angle_diff_deg,
    detect_heading_track,
    heading_points_findings,
    heading_points_measure,
    rectangle_angle,
)

POSES_IDENTITY = {f: np.eye(4) for f in range(20)}


def _car_track(n: int = 8, speed: float = 10.0, yaw: float = 0.0, track_id: int = 1, label: str = "car"):
    """Xe chạy thẳng theo hướng `yaw` với `speed` m/s, keyframe cách 0.5 s."""
    return [Cuboid(center=(math.cos(yaw) * speed * 0.5 * f, math.sin(yaw) * speed * 0.5 * f, 0.0),
                   dims=(4.5, 1.9, 1.6), yaw=yaw, label=label, frame=f, track_id=track_id) for f in range(n)]


# --- heading.flip / heading.motion -------------------------------------------------------------------


def test_clean_moving_track_has_no_heading_finding():
    assert detect_heading_track(_car_track(), HeadingConfig(), sensor_to_world=POSES_IDENTITY) == []


def test_turning_car_is_not_a_flip():
    """Xe rẽ 90° trong 3 giây (30°/s): hướng đổi đều, không phải lật."""
    boxes, x, y = [], 0.0, 0.0
    for f in range(7):
        yaw = math.radians(15.0 * f)
        boxes.append(Cuboid(center=(x, y, 0.0), dims=(4.5, 1.9, 1.6), yaw=yaw, label="car", frame=f, track_id=1))
        x, y = x + 3.0 * math.cos(yaw), y + 3.0 * math.sin(yaw)
    assert detect_heading_track(boxes, HeadingConfig(), sensor_to_world=POSES_IDENTITY) == []


def test_single_flipped_keyframe_is_error():
    boxes = _car_track()
    boxes[4] = boxes[4].replace(yaw=math.pi)
    findings = detect_heading_track(boxes, HeadingConfig(), sensor_to_world=POSES_IDENTITY)
    assert [(f.rule, f.frame, f.severity) for f in findings] == [("heading.flip", 4, Severity.ERROR)]
    assert findings[0].error_type is ErrorType.HEADING
    assert findings[0].value == pytest.approx(180.0, abs=0.5)
    assert "lật box" in findings[0].message


def test_rotated_keyframe_warning_then_error():
    boxes = _car_track()
    boxes[3] = boxes[3].replace(yaw=math.radians(60))
    findings = detect_heading_track(boxes, HeadingConfig(), sensor_to_world=POSES_IDENTITY, motion=False)
    assert [(f.frame, f.severity) for f in findings] == [(3, Severity.WARNING)]
    boxes[3] = boxes[3].replace(yaw=math.radians(90))
    findings = detect_heading_track(boxes, HeadingConfig(), sensor_to_world=POSES_IDENTITY, motion=False)
    assert [(f.frame, f.severity) for f in findings] == [(3, Severity.ERROR)]


def test_flipped_tail_reports_shorter_run():
    """Ba keyframe cuối bị lật: báo cả ba, giữ năm keyframe đầu làm chuẩn."""
    boxes = [b.replace(yaw=math.pi) if b.frame >= 5 else b for b in _car_track()]
    findings = detect_heading_track(boxes, HeadingConfig(), sensor_to_world=POSES_IDENTITY)
    assert sorted(f.frame for f in findings if f.rule == "heading.flip") == [5, 6, 7]
    assert not [f for f in findings if f.rule == "heading.motion"]


def test_whole_track_reversed_is_motion_error():
    boxes = [b.replace(yaw=math.pi) for b in _car_track()]
    findings = detect_heading_track(boxes, HeadingConfig(), sensor_to_world=POSES_IDENTITY)
    assert findings and all(f.rule == "heading.motion" and f.severity is Severity.ERROR for f in findings)
    assert len(findings) == 8


def test_slow_reversing_car_is_not_flagged():
    """Xe lùi chậm (1 m/s) để vào chỗ đỗ: dưới min_speed nên không so với hướng chuyển động."""
    boxes = [b.replace(yaw=math.pi) for b in _car_track(speed=1.0)]
    assert detect_heading_track(boxes, HeadingConfig(), sensor_to_world=POSES_IDENTITY) == []


def test_without_world_pose_only_warnings():
    boxes = _car_track()
    boxes[4] = boxes[4].replace(yaw=math.pi)
    findings = detect_heading_track(boxes, HeadingConfig())
    assert findings and all(f.severity is Severity.WARNING for f in findings)


def test_world_pose_rotation_is_applied():
    """Xe thu quay 90° ở frame 4: hướng box trong hệ cảm biến đổi 90° nhưng hướng thật trong hệ toàn cục không đổi."""
    boxes = _car_track()
    poses = dict(POSES_IDENTITY)
    rot = np.eye(4)
    rot[:2, :2] = [[0.0, -1.0], [1.0, 0.0]]  # cảm biến → toàn cục: quay +90°
    poses[4] = rot
    world_center = np.array(boxes[4].center)
    sensor_center = rot[:3, :3].T @ world_center
    boxes[4] = boxes[4].replace(center=tuple(sensor_center), yaw=-math.pi / 2)
    assert detect_heading_track(boxes, HeadingConfig(), sensor_to_world=poses) == []


def test_angle_diff_wraps():
    assert angle_diff_deg(math.radians(179), math.radians(-179)) == pytest.approx(2.0)


# --- heading.points ----------------------------------------------------------------------------------


def _l_shape(length=4.5, width=1.9, yaw=0.0, n=80, seed=0):
    """Điểm trên hai cạnh nhìn thấy được (hình chữ L) của xe, có nhiễu."""
    rng = np.random.default_rng(seed)
    a = np.column_stack([rng.uniform(-length / 2, length / 2, n), np.full(n, -width / 2)])
    b = np.column_stack([np.full(n // 2, length / 2), rng.uniform(-width / 2, width / 2, n // 2)])
    pts = np.vstack([a, b]) + rng.normal(0, 0.02, (n + n // 2, 2))
    c, s = math.cos(yaw), math.sin(yaw)
    return pts @ np.array([[c, s], [-s, c]])


@pytest.mark.parametrize("yaw_deg", [0.0, 10.0, -25.0, 40.0])
def test_rectangle_angle_recovers_orientation(yaw_deg):
    assert math.degrees(rectangle_angle(_l_shape(yaw=math.radians(yaw_deg)))) == pytest.approx(yaw_deg, abs=2.0)


def _scene_points(boxes, seed=0):
    """Mặt đất phẳng z = -1.8 quanh gốc và điểm trên thân xe của mỗi box (mặt bên dưới và đầu)."""
    rng = np.random.default_rng(seed)
    ground = np.column_stack([rng.uniform(-30, 30, 20000), rng.uniform(-30, 30, 20000), np.full(20000, -1.8)])
    parts = [ground]
    for k, box in enumerate(boxes):
        local = _l_shape(box.length, box.width, 0.0, n=120, seed=seed + k)
        z = rng.uniform(box.bottom_z + 0.3, box.top_z, len(local))
        c, s = math.cos(box.yaw), math.sin(box.yaw)
        world = local @ np.array([[c, s], [-s, c]]) + np.array(box.center[:2])
        parts.append(np.column_stack([world, z]))
    return np.vstack(parts)


def _car(x=10.0, y=0.0, yaw=0.0, frame=0, track_id=1, label="car", dims=(4.5, 1.9, 1.6)):
    return Cuboid(center=(x, y, -1.8 + dims[2] / 2), dims=dims, yaw=yaw, label=label, frame=frame, track_id=track_id)


def test_heading_points_flags_rotated_box_only():
    cfg = HeadingConfig().points
    measures = []
    for f in range(5):
        true_box = _car(frame=f)
        drawn = true_box.replace(yaw=math.radians(25)) if f == 2 else true_box
        item = box_point_sets(_scene_points([true_box], seed=f), [drawn], margin=0.5, clearance=0.25)[0]
        measures.append((drawn, heading_points_measure(item, cfg)))
    findings = heading_points_findings(measures, cfg)
    assert [f.frame for f in findings] == [2]
    assert findings[0].value == pytest.approx(25.0, abs=3.0)


def test_heading_points_ignores_systematic_track_offset():
    """Cả track lệch đều 20° (hình dạng vật đặc thù): so với trung vị track nên không báo."""
    cfg = HeadingConfig().points
    measures = [(_car(frame=f), 20.0 + (f % 2)) for f in range(6)]
    assert heading_points_findings(measures, cfg) == []


# --- fit -------------------------------------------------------------------------------------------


def _items(true_boxes, drawn_boxes):
    return box_point_sets(_scene_points(true_boxes), drawn_boxes, margin=0.5, clearance=0.25, margin_rel=0.25)


def test_clean_box_passes_all_fit_rules():
    box = _car()
    item = _items([box], [box])[0]
    cfg = FitConfig()
    assert empty_finding(item, cfg) is None
    assert outside_finding(item, cfg) is None
    assert loose_finding(item, cfg) is None


def test_empty_box_is_error_unless_occluded():
    item = _items([_car()], [_car(x=-20.0)])[0]
    finding = empty_finding(item, FitConfig())
    assert finding is not None and finding.rule == "fit.empty" and finding.severity is Severity.WARNING
    occluded = _items([_car()], [_car(x=-20.0).replace(attrs={"occluded": True})])[0]
    assert empty_finding(occluded, FitConfig()) is None


def test_sparse_warning_only_when_enabled():
    item = _items([_car()], [_car()])[0]
    assert empty_finding(item, FitConfig(sparse_warning_points=10_000)).severity is Severity.WARNING


def test_shrunk_box_has_points_outside():
    box = _car()
    item = _items([box], [box.replace(dims=(3.2, 1.4, 1.6))])[0]  # co x0.7 theo dài và rộng
    finding = outside_finding(item, FitConfig())
    assert finding is not None and finding.rule == "fit.outside"
    assert finding.value > 0.4


def test_shifted_box_toward_sensor_is_loose():
    """Box dời 0.8 m về phía cảm biến: mặt đuôi (nhìn thấy) cách điểm gần nhất của vật 0.8 m."""
    box = _car(x=10.0)
    item = _items([box], [box.replace(center=(9.2, 0.0, box.center[2]))])[0]
    finding = loose_finding(item, FitConfig())
    assert finding is not None and finding.rule == "fit.loose"
    assert finding.value == pytest.approx(0.8, abs=0.15)


def test_loose_compares_with_rest_of_track():
    """Track dư đều 0,45 m (hình dạng vật / vẽ rộng có chủ ý): không báo. Một frame dư 0,8 m khi các frame khác dư
    0,1 m: báo. Box lẻ dư 0,45 m: chỉ so ngưỡng tuyệt đối (0,4 m) nên báo."""
    from pointsnap.detectors.fit import LooseMeasure, loose_findings

    cfg = FitConfig()
    steady = [LooseMeasure(_car(frame=f), 0.45, "đuôi", 100) for f in range(5)]
    assert loose_findings(steady, cfg) == []
    spike = [LooseMeasure(_car(frame=f), 0.1, "đuôi", 100) for f in range(4)]
    spike.append(LooseMeasure(_car(frame=4), 0.8, "đuôi", 100))
    found = loose_findings(spike, cfg)
    assert [(f.frame, f.severity) for f in found] == [(4, Severity.WARNING)]
    assert found[0].details["track_median_m"] == pytest.approx(0.1)
    single = LooseMeasure(_car(frame=0).replace(track_id=None), 0.45, "đuôi", 100)
    assert [f.rule for f in loose_findings([single], cfg)] == ["fit.loose"]


def test_connected_to_box_drops_separate_clutter():
    half = np.array([1.0, 1.0, 1.0])
    obj = np.array([[0.0, 0.0, 0.0], [0.9, 0.0, 0.0], [1.15, 0.0, 0.0]])  # đầu vật thò ra ngoài box, liền kề
    wall = np.array([[2.4, 0.0, 0.0], [2.5, 0.1, 0.0]])                    # vật khác cách hơn một ô lưới
    mask = connected_to_box(np.vstack([obj, wall]), half)
    assert mask.tolist() == [True, True, True, False, False]


def test_overlap_duplicate_and_allowed_pairs():
    cfg = FitConfig()
    a = _car(track_id=1)
    duplicate = a.replace(center=(10.3, 0.0, a.center[2]), track_id=2)
    findings = overlap_findings([a, duplicate], cfg)
    assert len(findings) == 1 and findings[0].severity is Severity.ERROR and findings[0].rule == "fit.overlap"
    ped1 = _car(track_id=3, label="pedestrian", dims=(0.7, 0.7, 1.7))
    ped2 = ped1.replace(center=(10.2, 0.0, ped1.center[2]), track_id=4)
    assert overlap_findings([ped1, ped2], cfg) == []
    cone = _car(track_id=5, label="traffic_cone", dims=(0.4, 0.4, 0.7))
    assert overlap_findings([a, cone], cfg) == []  # cọc tiêu không thuộc overlap_classes


# --- cấu hình, bộ quét, chèn lỗi ----------------------------------------------------------------------


def test_default_config_has_new_sections_and_rules():
    config = load_config()
    assert config.heading.group_for("car").flip_error_deg == 75
    assert config.fit.overlap_classes and config.rules.heading_flip and config.rules.fit_overlap


def test_rule_switch_filters_new_rules():
    config = load_config()
    boxes = _car_track()
    boxes[4] = boxes[4].replace(yaw=math.pi)
    assert any(f.rule == "heading.flip" for f in scan_cuboids(boxes, config))
    import dataclasses
    off = dataclasses.replace(config, rules=dataclasses.replace(config.rules, heading_flip=False, heading_motion=False))
    assert not any(f.rule.startswith("heading") for f in scan_cuboids(boxes, off))


def test_c1_injections():
    boxes = _car_track()
    rotated, log = inject_heading_rotate(boxes, 1, 3, 90.0)
    assert log.error_type == "heading_rotate" and rotated[3].yaw == pytest.approx(math.pi / 2)
    reversed_, log = inject_heading_reverse(boxes, 1)
    assert all(abs(abs(b.yaw) - math.pi) < 1e-9 for b in reversed_)
    shifted, log = inject_fit_shift(boxes, 1, 2, 0.5)
    assert shifted[2].center[1] == pytest.approx(0.5)
    scaled, log = inject_fit_scale(boxes, 1, 2, 0.7)
    assert scaled[2].dims == pytest.approx((4.5 * 0.7, 1.9 * 0.7, 1.6))
    duplicated, log = inject_fit_duplicate(boxes, 1, 2, 99)
    assert len(duplicated) == len(boxes) + 1 and duplicated[-1].track_id == 99


def test_inject_dataset_catalogs():
    boxes = [b for t in range(30) for b in _car_track(track_id=t)]
    _, core = inject_dataset(boxes, seed=1, error_rate=0.5)
    _, c1 = inject_dataset(boxes, seed=1, error_rate=0.5, catalog="c1")
    assert {e.error_type for e in core}.isdisjoint({"heading_rotate", "fit_shift"})
    assert {e.error_type for e in c1} <= {"heading_rotate", "heading_reverse", "fit_shift", "fit_scale",
                                          "fit_duplicate"}
    with pytest.raises(ValueError):
        inject_dataset(boxes, catalog="nope")
