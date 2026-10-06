"""Test có đáp án cho ba bộ phát hiện (B3 lơ lửng / lún, B4 kích thước, B5 đứt track)."""

import json
import math

import numpy as np
import pytest

from pointsnap.adapters.cvat.reader import find_manifest
from pointsnap.cli.main import EXIT_OK, main
from pointsnap.core.config import load_config
from pointsnap.core.model import Cuboid, FrameData, Severity, add_outside_markers
from pointsnap.core.scanner import actionable, scan_cuboids
from pointsnap.core.size import check_size_class_range
from pointsnap.core.track import check_track
from pointsnap.core.floating import check_floating
from pointsnap.core.synthetic import InjectedError, inject_dataset
from pointsnap.eval.evaluate import matches
from pointsnap.core.model import ErrorType, Finding


@pytest.fixture(scope="module")
def config():
    return load_config()


class FlatGround:
    """Mặt đất phẳng z = 0, lưới điểm 0,1 m quanh gốc; pose đơn vị, 0,5 s mỗi frame."""

    def __init__(self, extent=12.0, step=0.1):
        axis = np.arange(-extent, extent, step)
        gx, gy = np.meshgrid(axis, axis)
        self.points = np.column_stack([gx.ravel(), gy.ravel(), np.zeros(gx.size)])

    def frame_data(self, frame, with_points=True):
        points = self.points if with_points else np.empty((0, 3))
        return FrameData(frame, points, np.eye(4), timestamp=frame * 0.5)


def car(frame, x=0.0, y=0.0, bottom=0.0, track_id=1, dims=(4.5, 1.9, 1.6), label="car", source_id=None):
    return Cuboid(center=(x, y, bottom + dims[2] / 2), dims=dims, yaw=0.0, label=label, frame=frame,
                  track_id=track_id, source_id=source_id if source_id is not None else 100 * track_id + frame)


# --- B3: lơ lửng / lún -------------------------------------------------------------------------------


def test_floating_lifted_box_is_error_with_measured_height(config):
    boxes = [car(f, bottom=0.25 if f == 2 else 0.0) for f in range(5)]
    findings = check_floating(boxes, config, FlatGround())
    assert [(f.frame, f.severity) for f in findings] == [(2, Severity.ERROR)]
    assert findings[0].value == pytest.approx(0.25, abs=0.01)
    assert "lơ lửng" in findings[0].message and "25 cm" in findings[0].message


def test_floating_sunk_box_is_warning(config):
    boxes = [car(f, bottom=-0.15 if f == 1 else 0.0) for f in range(5)]
    findings = check_floating(boxes, config, FlatGround())
    assert [(f.frame, f.severity) for f in findings] == [(1, Severity.WARNING)]
    assert findings[0].value == pytest.approx(-0.15, abs=0.01)
    assert "lún" in findings[0].message


def test_floating_single_box_uses_absolute_distance(config):
    box = car(0, bottom=0.35, track_id=None, source_id=7)
    box = box.replace(track_id=None)
    findings = check_floating([box], config, FlatGround())
    assert [(f.rule, f.severity) for f in findings] == [("floating", Severity.ERROR)]


def test_floating_ignores_points_of_neighbouring_box(config):
    """Thân xe đậu sát bên không được tính là mặt đất."""
    ground = FlatGround()
    neighbour = car(0, y=2.2, track_id=2)
    body = ground.points[(np.abs(ground.points[:, 0]) < 2.2) & (np.abs(ground.points[:, 1] - 2.2) < 0.9)].copy()
    body[:, 2] = 0.5  # điểm thân xe bên cạnh, cao 50 cm
    cloud = np.vstack([ground.points, body])

    class Source(FlatGround):
        def frame_data(self, frame, with_points=True):
            return FrameData(frame, cloud, np.eye(4), timestamp=frame * 0.5)

    boxes = [car(0, bottom=0.0, track_id=None, source_id=1).replace(track_id=None), neighbour]
    assert [f for f in check_floating(boxes, config, Source()) if f.rule == "floating"] == []


def test_floating_without_ground_points_is_info_per_track(config):
    class Empty(FlatGround):
        def frame_data(self, frame, with_points=True):
            return FrameData(frame, np.empty((0, 3)), np.eye(4))

    findings = check_floating([car(f) for f in range(3)], config, Empty())
    assert [(f.rule, f.severity, f.details["frames"]) for f in findings] == [
        ("floating.no_evidence", Severity.INFO, [0, 1, 2])]


def test_floating_skips_other_classes_and_missing_point_cloud(config):
    cone = car(0, label="traffic_cone", dims=(0.4, 0.4, 0.7), bottom=1.0)
    assert check_floating([cone], config, FlatGround()) == []
    assert check_floating([car(0, bottom=1.0)], config, None) == []


# --- B4: kích thước ----------------------------------------------------------------------------------


def test_size_class_range_uses_stats_with_margins(config):
    low, high = config.size.class_range.stats["car"]["length"]
    ok = car(0, dims=(high * 1.05, 1.9, 1.6), track_id=1)  # trong biên Cảnh báo 10%
    warn = car(1, dims=(high * 1.15, 1.9, 1.6), track_id=2)  # ngoài 10%, trong 25%
    err = car(2, dims=(high * 1.4, 1.9, 1.6), track_id=3)  # ngoài 25%
    findings = check_size_class_range([ok, warn, err], config)
    assert [(f.frame, f.severity) for f in findings] == [(1, Severity.WARNING), (2, Severity.ERROR)]
    assert findings[0].details["dimension"] == "length"


def test_size_class_range_reports_one_finding_per_track(config):
    huge = [car(f, dims=(20.0 + f, 6.0, 5.0)) for f in range(4)]
    findings = check_size_class_range(huge, config)
    assert [(f.frame, f.severity) for f in findings] == [(3, Severity.ERROR)]  # keyframe lệch nhiều nhất
    assert "trung vị của 4 keyframe" in findings[0].message
    # Một keyframe lẻ lệch không làm cả track sai theo class (luật trong track bắt nó)
    track = [car(f) for f in range(4)] + [car(4, dims=(9.0, 1.9, 1.6))]
    assert check_size_class_range(track, config) == []


# --- B5: đứt track -----------------------------------------------------------------------------------


def moving_track(n=7, speed=10.0, track_id=1, label="car", start=0):
    return [car(start + f, x=speed * 0.5 * f, track_id=track_id, label=label) for f in range(n)]


def test_track_clean_motion_has_no_findings(config):
    assert check_track(moving_track(), config, FlatGround()) == []


def test_track_jump_reports_only_the_jumped_keyframe(config):
    boxes = moving_track()
    boxes[3] = boxes[3].replace(center=(boxes[3].center[0], 2.5, boxes[3].center[2]))
    findings = check_track(boxes, config, FlatGround())
    assert [(f.rule, f.frame, f.severity) for f in findings] == [("track.jump", 3, Severity.ERROR)]
    assert findings[0].value == pytest.approx(2.5)


def test_track_jump_without_pose_is_warning_only(config):
    boxes = moving_track()
    boxes[3] = boxes[3].replace(center=(boxes[3].center[0], 2.5, boxes[3].center[2]))
    assert [(f.frame, f.severity) for f in check_track(boxes, config, None)] == [(3, Severity.WARNING)]


def test_track_jump_at_segment_end_uses_extrapolation(config):
    boxes = moving_track()
    boxes[0] = boxes[0].replace(center=(boxes[0].center[0], 4.0, boxes[0].center[2]))
    findings = check_track(boxes, config, FlatGround())
    assert [(f.frame, f.severity) for f in findings] == [(0, Severity.ERROR)]  # 4 m > 2 m × 1,5
    assert "ngoại suy" in findings[0].message


def test_track_split_id_is_warning_on_new_track(config):
    first = moving_track(n=4, track_id=1)
    second = moving_track(n=4, track_id=2, start=4)
    second = [b.replace(center=(10.0 * 0.5 * b.frame, 0.0, b.center[2])) for b in second]
    boxes = add_outside_markers(first + second + [car(9, x=-30, track_id=3)], 10)
    findings = [f for f in check_track(boxes, config, FlatGround()) if f.rule == "track.split_id"]
    assert [(f.track_id, f.frame, f.severity) for f in findings] == [(2, 4, Severity.WARNING)]
    assert findings[0].details["previous_track_id"] == 1


def test_track_split_needs_same_class(config):
    first = moving_track(n=4, track_id=1)
    second = [b.replace(label="truck", frame=b.frame + 4, center=(10.0 * 0.5 * (b.frame + 4), 0.0, b.center[2]))
              for b in moving_track(n=4, track_id=2)]
    boxes = add_outside_markers(first + second + [car(9, x=-30, track_id=3)], 10)
    assert [f for f in check_track(boxes, config, FlatGround()) if f.rule == "track.split_id"] == []


def test_long_interpolation_only_for_moving_objects(config):
    moving = [b for b in moving_track(n=6) if b.frame not in (2, 3)]
    findings = [f for f in check_track(moving, config, FlatGround()) if f.rule == "track.long_interpolation"]
    assert [(f.frame, f.value) for f in findings] == [(1, 2.0)]
    parked = [car(f, track_id=5) for f in (0, 1, 4, 5)]
    assert [f for f in check_track(parked, config, FlatGround()) if f.rule == "track.long_interpolation"] == []


def test_outside_markers_split_segments(config):
    boxes = add_outside_markers([car(0), car(1), car(4), car(5)], 6)
    outside = [b.frame for b in boxes if b.outside]
    assert outside == [2]
    # Hai đoạn tách bởi outside: không coi là khoảng nội suy dài
    assert [f for f in check_track(boxes, config, FlatGround()) if f.rule == "track.long_interpolation"] == []


# --- Quét chung, đánh giá -----------------------------------------------------------------------------


def test_scan_finds_all_three_error_types(config):
    boxes = moving_track(n=7)
    boxes[2] = boxes[2].replace(center=(boxes[2].center[0], boxes[2].center[1], boxes[2].center[2] + 0.3))
    boxes[4] = boxes[4].replace(center=(boxes[4].center[0], 3.0, boxes[4].center[2]))
    boxes[5] = boxes[5].replace(dims=(6.5, 1.9, 1.6))
    rules = {(f.rule, f.frame) for f in actionable(scan_cuboids(boxes, config, FlatGround()))}
    assert {("floating", 2), ("track.jump", 4), ("size.in_track", 5)} <= rules


def test_matches_rules_for_injected_errors():
    def finding(rule, frame, track_id=1, **details):
        error_type = {"floating": ErrorType.FLOATING, "size": ErrorType.SIZE, "track": ErrorType.TRACK}[rule.split(".")[0]]
        return Finding(error_type, rule, Severity.WARNING, frame, "car", "x", track_id=track_id, details=details)

    split = InjectedError("track_split_id", "split", 1, 5, None, "", 1, 1001)
    assert matches(split, finding("track.split_id", 5, track_id=1001))
    assert not matches(split, finding("track.split_id", 5, track_id=1))
    gap = InjectedError("track_interpolation", 2, 1, 3, None, "", 6, 4)
    assert matches(gap, finding("track.long_interpolation", 2, next_keyframe=5))
    jump = InjectedError("track_jump", 2.0, 1, 3, None, "", [], [])
    assert matches(jump, finding("track.jump", 3)) and not matches(jump, finding("track.jump", 4))
    assert not matches(jump, finding("floating", 3))


def test_inject_dataset_offset_rotates_error_types():
    boxes = [car(f, x=f, track_id=t) for t in range(1, 11) for f in range(6)]
    _, first = inject_dataset(boxes, seed=1, error_rate=0.1, offset=0)
    _, later = inject_dataset(boxes, seed=1, error_rate=0.1, offset=10)
    assert first[0].error_type == "floating" and later[0].error_type == "track_jump"


def test_find_manifest_by_task_id(tmp_path):
    export = tmp_path / "scene-0061"
    export.mkdir()
    (export / "manifest.json").write_text("{}", encoding="utf-8")
    (export / "cvat_task.json").write_text(json.dumps({"task_id": 9}), encoding="utf-8")
    assert find_manifest(9, [tmp_path]) == export / "manifest.json"
    assert find_manifest(9, [export]) == export / "manifest.json"
    assert find_manifest(8, [tmp_path, tmp_path / "missing"]) is None


def test_cli_nuscenes_scan_and_eval(tmp_path, capsys):
    import fake_nuscenes

    root = fake_nuscenes.build(tmp_path / "nuscenes")
    out = tmp_path / "out"
    assert main(["nuscenes", "--dataroot", str(root), "scan", "--scene", "scene-0001", "--out", str(out)]) == EXIT_OK
    assert (out / "report_scene-0001.html").is_file()
    assert "TỔNG KẾT QUÉT" in capsys.readouterr().out
    assert main(["eval", "--dataroot", str(root), "--scenes", "scene-0001", "--rounds", "1",
                 "--out", str(out / "eval")]) == EXIT_OK
    assert (out / "eval" / "ket-qua.md").is_file()
