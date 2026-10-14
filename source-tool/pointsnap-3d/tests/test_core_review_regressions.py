"""Ca có đáp án độc lập cho các lỗi gây báo nhầm/bỏ sót tìm được trong phần 02."""

import dataclasses
import itertools
import math

import numpy as np
import pytest
import yaml

from pointsnap.adapters.cvat.reader import JobData
from pointsnap.core.config import ConfigError, default_config_text, load_config, parse_config
from pointsnap.core.geometry import corners, invert_pose, points_in_cuboid, quaternion_to_matrix
from pointsnap.core.ground import GroundEstimate, OtherBoxPoints, ring_ground_for_box
from pointsnap.core.model import Cuboid, ErrorType, Finding, FrameData, Severity, add_track_markers
from pointsnap.core.scanner import scan_cuboids
from pointsnap.detectors.floating import detect_floating_for_box, floating_findings_by_track, static_sweep_points
from pointsnap.detectors.heading import detect_heading_track, heading_points_findings
from pointsnap.detectors.size import detect_size, detect_size_class_range_for_box, detect_size_in_track, get_resolved_class_ranges
from pointsnap.detectors.track import detect_long_interpolation, detect_track_jumps_for_track, detect_track_splits


def car(frame=0, **changes):
    return Cuboid((0, 0, 0.8), (4.5, 1.9, 1.6), 0, "car", frame, track_id=1,
                  source_id=100 + frame).replace(**changes)


@pytest.mark.parametrize("path", [("heading", "min_motion_m"), ("floating", "error_min_abs_m"),
                                 ("track", "keyframe_interval_s")])
@pytest.mark.parametrize("value", [float("nan"), float("inf")])
def test_config_rejects_nonfinite_numbers(path, value):
    data = yaml.safe_load(default_config_text())
    data[path[0]][path[1]] = value
    with pytest.raises(ConfigError):
        parse_config(data, env={})


def test_config_rejects_infinite_range_and_zero_frame_interval():
    data = yaml.safe_load(default_config_text())
    data["size"]["manual_ranges"]["bus"]["length"] = [6, float("inf")]
    with pytest.raises(ConfigError):
        parse_config(data, env={})
    data = yaml.safe_load(default_config_text())
    data["track"]["keyframe_interval_s"] = 0
    with pytest.raises(ConfigError):
        parse_config(data, env={})


@pytest.mark.parametrize("points", [np.ones(3), np.ones((2, 2)), np.array([[0, float("nan"), 0]])])
def test_frame_rejects_invalid_point_cloud(points):
    with pytest.raises(ValueError):
        FrameData(0, points)


@pytest.mark.parametrize("points", [np.ones(3), np.ones((2, 1)), np.ones((2, 2))])
def test_geometry_rejects_shapes_that_would_broadcast_to_xyz(points):
    with pytest.raises(ValueError):
        points_in_cuboid(points, car())


@pytest.mark.parametrize("pose", [np.eye(3), np.diag([2, 1, 1, 1]), np.full((4, 4), float("nan"))])
def test_frame_and_inverse_reject_invalid_pose(pose):
    with pytest.raises(ValueError):
        FrameData(0, np.empty((0, 3)), sensor_to_world=pose)
    with pytest.raises(ValueError):
        invert_pose(pose)


def test_frame_rejects_nonfinite_timestamp():
    with pytest.raises(ValueError):
        FrameData(0, np.empty((0, 3)), timestamp=float("nan"))


@pytest.mark.parametrize("scale", [1e-300, 1e300])
def test_quaternion_normalization_is_stable_for_finite_scales(scale):
    # w=z: quay 90 độ quanh z, bất kể độ dài quaternion đầu vào.
    expected = np.array([[0, -1, 0], [1, 0, 0], [0, 0, 1]])
    np.testing.assert_allclose(quaternion_to_matrix([scale, 0, 0, scale]), expected, atol=1e-12)


def test_quaternion_rejects_nonfinite_components():
    with pytest.raises(ValueError):
        quaternion_to_matrix([1, 0, 0, float("nan")])


@pytest.mark.parametrize("yaw", [math.pi / 4, 0.7, -math.pi + 1e-6])
def test_rotated_faces_edges_and_corners_are_inside(yaw):
    box = car(yaw=yaw, dims=(2, 2, 2))
    assert points_in_cuboid(corners(box), box).all()
    # Điểm xa hơn mặt box 0,1 micromet vẫn ở ngoài, không nới dung sai hình học đáng kể.
    outside = np.array([[box.length / 2 + 1e-7, 0, 0]])
    c, s = math.cos(yaw), math.sin(yaw)
    world = outside @ np.array([[c, s, 0], [-s, c, 0], [0, 0, 1]]) + box.center
    assert not points_in_cuboid(world, box).any()


def test_rotated_neighbour_points_are_removed_from_ground():
    target = car(center=(0, 0, 1), dims=(2, 2, 2), yaw=math.pi / 4)
    neighbour = target.replace(track_id=2, source_id=200)
    # Điểm trong hai box ở y=1,3 > nửa cạnh 1 m, nhưng vẫn thuộc footprint xoay 45 độ.
    point = np.array([[0, 1.3, 1]])
    assert points_in_cuboid(point, neighbour).all()
    cloud = OtherBoxPoints(point, [target, neighbour])
    assert len(cloud.without_others(0)) == 0


def test_rotated_ring_keeps_ground_at_its_corners():
    box = car(center=(0, 0, 1), dims=(2, 2, 2), yaw=math.pi / 4)
    # 16 điểm vành đai: local x,y >1,1 và <1,8; sau xoay y >2,3.
    local = np.array([[x, y, 0] for x in np.linspace(1.64, 1.70, 4) for y in np.linspace(1.64, 1.70, 4)])
    c, s = math.cos(box.yaw), math.sin(box.yaw)
    points = local @ np.array([[c, s, 0], [-s, c, 0], [0, 0, 1]])
    result = ring_ground_for_box(points, box, min_ground_points=10)
    assert result.is_valid and result.ground_z == pytest.approx(0)


def test_public_detectors_ignore_occluded_cuboids():
    cfg = load_config(env={})
    box = car(dims=(25, 2, 2), attrs={"occluded": True})
    assert detect_size_class_range_for_box(box, cfg.size, get_resolved_class_ranges(cfg.size)) == []
    assert detect_floating_for_box(box, np.empty((0, 3)), cfg.floating) is None
    boxes = [car(0), car(1), box.replace(frame=2)]
    assert detect_size_in_track(boxes, cfg.size) == []


def test_interpolated_cuboids_do_not_supply_manual_size_keyframes():
    cfg = load_config(env={})
    boxes = [car(0), car(1, dims=(20, 2, 2), keyframe=False), car(2)]
    assert detect_size_in_track(boxes, cfg.size) == []
    assert detect_size(boxes, cfg.size) == []


def test_long_interpolation_uses_manual_keyframes_when_expanded_boxes_are_supplied():
    cfg = load_config(env={})
    boxes = [car(i, center=(2 * i, 0, 0.8), keyframe=i in (0, 5)) for i in range(6)]
    findings = detect_long_interpolation(boxes, cfg.track)
    assert [(f.frame, f.value) for f in findings] == [(0, 4)]


def test_interpolated_positions_and_headings_do_not_create_manual_findings():
    cfg = load_config(env={})
    boxes = [car(0), car(1, center=(100, 0, 0.8), yaw=math.pi, keyframe=False), car(2, center=(4, 0, 0.8))]
    poses = {i: np.eye(4) for i in range(3)}
    assert detect_track_jumps_for_track(boxes, cfg.track, poses) == []
    assert detect_heading_track(boxes, cfg.heading, sensor_to_world=poses) == []


def test_size_track_does_not_mix_different_subtypes():
    cfg = load_config(env={})
    size = dataclasses.replace(cfg.size, key_attributes={"Vehicle": "subtype"}, manual_ranges={
        "Vehicle/car": {"length": (4, 5), "width": (1, 3), "height": (1, 3)},
        "Vehicle/bus": {"length": (10, 14), "width": (1, 3), "height": (1, 3)},
    })
    boxes = [car(i, label="Vehicle", dims=((4.5 if i < 2 else 12), 2, 2),
                 attrs={"subtype": "car" if i < 2 else "bus"}) for i in range(4)]
    # Các kích thước đều hợp lệ theo subtype; không dùng trung vị 8,25 m cho cả hai loại.
    assert detect_size(boxes, size) == []


def test_heading_axis_median_wraps_modulo_90_degrees():
    cfg = load_config(env={})
    measures = [(car(i), angle) for i, angle in enumerate([44, -44, 43, -43])]
    assert heading_points_findings(measures, cfg.heading.points) == []
    outlier = measures + [(car(4), 0)]
    assert {f.frame for f in heading_points_findings(outlier, cfg.heading.points)} == {4}


def test_track_splits_do_not_mix_local_and_world_coordinates():
    cfg = load_config(env={})
    # A ở x=100, B ở x=0, xa nhau trong hệ frame. Pose +100 chỉ có cho B.
    tracks = {1: [car(0, center=(100, 0, 0.8)), car(1, center=(100, 0, 0.8))],
              2: [car(2, center=(0, 0, 0.8), track_id=2)]}
    pose = np.eye(4)
    pose[0, 3] = 100
    assert detect_track_splits(tracks, cfg.track, {2: pose}) == []


def test_findings_order_is_independent_of_shape_input_order():
    cfg = load_config(env={})
    cfg = dataclasses.replace(cfg, rules=dataclasses.replace(cfg.rules, fit_overlap=False))
    boxes = [car(track_id=None, source_id=i, dims=(25, 2, 2)) for i in [20, 10]]
    expected = scan_cuboids(boxes, cfg)
    for order in itertools.permutations(boxes):
        assert scan_cuboids(order, cfg) == expected
        job = JobData("", 1, 1, 0, 0, {}, list(order))
        assert scan_cuboids(job, cfg) == expected


def test_equal_size_overlap_targets_the_same_box_after_reordering():
    cfg = load_config(env={})
    cfg = dataclasses.replace(cfg, rules=dataclasses.replace(cfg.rules, size_class_range=False,
                                                             size_in_track=False))
    boxes = [car(track_id=i, source_id=i) for i in [2, 1]]
    assert scan_cuboids(boxes, cfg) == scan_cuboids(list(reversed(boxes)), cfg)


def test_partial_timestamps_do_not_mix_epoch_and_frame_relative_seconds():
    cfg = load_config(env={})
    boxes = [car(i, center=(2 * i, 0, 0.8), yaw=math.pi) for i in range(4)]
    poses = {i: np.eye(4) for i in range(4)}
    times = {0: 1e9, 1: 1e9 + 0.5, 3: 1e9 + 1.5}  # Thiếu timestamp frame 2.
    assert detect_track_jumps_for_track(boxes, cfg.track, poses, times) == []
    findings = detect_heading_track(boxes, cfg.heading, sensor_to_world=poses, timestamps=times)
    assert {f.frame for f in findings if f.rule == "heading.motion"} == {0, 1, 2, 3}


def split_only_config():
    cfg = load_config(env={})
    rules = dataclasses.replace(cfg.rules, **{
        field.name: field.name == "track_split_id" for field in dataclasses.fields(cfg.rules)
    })
    return dataclasses.replace(cfg, rules=rules)


def test_cvat_track_without_outside_keeps_running_to_job_end():
    cfg = split_only_config()
    boxes = [car(0), car(1, track_id=2)]
    job = JobData("", 1, 1, 0, 5, {}, boxes)
    # Hai track vẫn tiếp tục tới frame 5; keyframe cuối không có nghĩa track đã kết thúc.
    assert scan_cuboids(job, cfg) == []


def test_occluded_last_keyframe_is_counted_until_job_end():
    cfg = split_only_config()
    cfg = dataclasses.replace(cfg, rules=dataclasses.replace(cfg.rules, track_split_id=False,
                                                             track_occluded_long=True))
    job = JobData("", 1, 1, 0, 10, {}, [car(0), car(1, attrs={"occluded": True})])
    findings = scan_cuboids(job, cfg)
    assert [(f.rule, f.frame, f.value) for f in findings] == [("track.occluded_long", 1, 10)]


def test_track_split_requires_the_same_configured_subtype():
    cfg = split_only_config()
    cfg = dataclasses.replace(cfg, size=dataclasses.replace(cfg.size, key_attributes={"car": "subtype"}))
    boxes = [car(0, attrs={"subtype": "sedan"}), car(1, outside=True),
             car(2, track_id=2, attrs={"subtype": "bus"})]
    job = JobData("", 1, 1, 0, 5, {}, boxes)
    assert scan_cuboids(job, cfg) == []
    # Cùng subtype và có outside: vẫn bắt được split thật, không tắt cả luật.
    boxes[-1] = boxes[-1].replace(attrs={"subtype": "sedan"})
    assert [f.rule for f in scan_cuboids(job, cfg)] == ["track.split_id"]


def test_sweep_removes_moving_object_after_sensor_pose_conversion():
    class Sweeps:
        def ground_sweeps(self, frame, count):
            return [(0.5, np.array([[-4, 0, 1], [-4, 3, 0]], dtype=float))]

        def frame_data(self, frame, with_points=True):
            pose = np.eye(4)
            pose[0, 3] = 10 * frame
            return FrameData(frame, np.empty((0, 3)), pose, timestamp=float(frame))

    previous = car(0, center=(0, 0, 1), dims=(2, 2, 2))
    current = car(1, center=(2, 0, 1), dims=(2, 2, 2))
    # World center từ 0 tới 12; ở t=0,5 world=6, trong hệ frame 1 là x=-4.
    result = static_sweep_points(Sweeps(), 1, [current], [previous], 1)
    np.testing.assert_allclose(result, [[-4, 3, 0]])


@pytest.mark.parametrize("missing", [6, 7])
def test_gap_boundary_uses_number_of_missing_frames(missing):
    boxes = add_track_markers([car(0), car(missing + 1)], num_frames=missing + 2)
    if missing == 6:
        assert {b.track_id for b in boxes} == {1}
        assert [b.frame for b in boxes if b.occluded] == [1]
    else:
        assert {b.track_id for b in boxes} == {1, 2}
        assert [b.frame for b in boxes if b.outside] == [1]


def test_short_gap_interpolates_yaw_over_the_pi_boundary():
    boxes = add_track_markers([car(0, yaw=math.radians(179)), car(2, yaw=math.radians(-179))], 3)
    hidden = next(b for b in boxes if b.occluded)
    assert abs(hidden.yaw) == pytest.approx(math.pi, abs=1e-12)


@pytest.mark.parametrize("level,delta", [("warning", -1e-6), ("warning", 0), ("warning", 1e-6),
                                         ("error", -1e-6), ("error", 0), ("error", 1e-6)])
def test_floating_thresholds_have_independent_boundary_answers(level, delta):
    cfg = load_config(env={}).floating
    threshold = cfg.warning_m if level == "warning" else cfg.error_m
    distance = threshold + delta
    estimates = [(car(i), GroundEstimate(ground_z=0, distance=(distance if i == 2 else 0))) for i in range(3)]
    found = [f for f in floating_findings_by_track(estimates, cfg) if f.frame == 2]
    expected = (None if level == "warning" and delta <= 0 else
                Severity.ERROR if level == "error" and delta > 0 else Severity.WARNING)
    assert ([f.severity for f in found] if found else []) == ([] if expected is None else [expected])


RULES = {
    "floating": "floating", "size_class_range": "size.class_range", "size_in_track": "size.in_track",
    "track_jump": "track.jump", "track_split_id": "track.split_id", "track_long_interpolation": "track.long_interpolation",
    "heading_flip": "heading.flip", "heading_motion": "heading.motion", "heading_points": "heading.points",
    "fit_empty": "fit.empty", "fit_outside": "fit.outside", "fit_loose": "fit.loose", "fit_overlap": "fit.overlap",
    "track_reuse_id": "track.reuse_id", "track_occluded_long": "track.occluded_long",
    "attr_missing": "attr.missing", "attr_invalid": "attr.invalid",
}


@pytest.mark.parametrize("switch", list(RULES))
def test_each_switch_removes_only_its_findings(switch):
    cfg = load_config(env={})
    switches = {name: True for name in RULES}
    switches[switch] = False
    cfg = dataclasses.replace(cfg, rules=dataclasses.replace(cfg.rules, **switches))
    findings = [Finding(ErrorType.SIZE, rule, Severity.WARNING, 0, "car", rule) for rule in RULES.values()]
    result = scan_cuboids([car()], cfg, detectors=[lambda *args: findings])
    assert {f.rule for f in result} == set(RULES.values()) - {RULES[switch]}
