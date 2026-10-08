"""A10: test có đáp án cho phần giảm báo nhầm trong `pointsnap.detectors`."""

import numpy as np
import pytest

from pointsnap.core.config import load_config
from pointsnap.core.model import Cuboid, FrameData, Severity, add_outside_markers
from pointsnap.detectors.floating import detect_floating_scene
from pointsnap.detectors.size import detect_size
from pointsnap.detectors.track import detect_track_errors


@pytest.fixture(scope="module")
def config():
    return load_config()


class FlatGround:
    """Mặt đất phẳng z = 0, lưới điểm 0,1 m; pose đơn vị, 0,5 s mỗi frame."""

    def __init__(self, extent=12.0, step=0.1, extra=None):
        axis = np.arange(-extent, extent, step)
        gx, gy = np.meshgrid(axis, axis)
        self.points = np.column_stack([gx.ravel(), gy.ravel(), np.zeros(gx.size)])
        if extra is not None:
            self.points = np.vstack([self.points, extra])

    def frame_data(self, frame, with_points=True):
        return FrameData(frame, self.points if with_points else np.empty((0, 3)), np.eye(4), timestamp=frame * 0.5)


def car(frame, x=0.0, y=0.0, bottom=0.0, track_id=1, dims=(4.5, 1.9, 1.6), label="car"):
    return Cuboid(center=(x, y, bottom + dims[2] / 2), dims=dims, yaw=0.0, label=label, frame=frame,
                  track_id=track_id, source_id=100 * (track_id or 0) + frame)


# --- Lơ lửng / lún: so với track -------------------------------------------------------------------


def test_floating_scene_flags_only_the_lifted_keyframe(config):
    boxes = [car(f, bottom=0.30 if f == 2 else 0.0) for f in range(5)]
    findings = detect_floating_scene(boxes, FlatGround(), config.floating)
    assert [(f.frame, f.severity) for f in findings] == [(2, Severity.ERROR)]
    assert findings[0].value == pytest.approx(0.30, abs=0.01)


def test_floating_scene_ignores_offset_shared_by_whole_track(config):
    """Cả track lệch đều 13 cm (ví dụ đỗ trên vỉa hè): không báo theo từng frame."""
    boxes = [car(f, bottom=0.13) for f in range(5)]
    assert detect_floating_scene(boxes, FlatGround(), config.floating) == []


def test_floating_scene_single_box_uses_absolute_distance(config):
    box = car(0, bottom=0.35, track_id=None)
    findings = detect_floating_scene([box], FlatGround(), config.floating)
    assert [(f.rule, f.severity) for f in findings] == [("floating", Severity.ERROR)]


def test_floating_scene_ignores_points_of_neighbouring_box(config):
    neighbour = car(0, y=2.2, track_id=2)
    body = np.column_stack([np.linspace(-2, 2, 400), np.full(400, 2.2 - 0.9), np.full(400, 0.5)])
    boxes = [car(0, track_id=None), neighbour]
    findings = detect_floating_scene(boxes, FlatGround(extra=body), config.floating)
    assert [f for f in findings if f.rule == "floating"] == []


def test_floating_scene_no_ground_points_is_one_info_per_track(config):
    class Empty(FlatGround):
        def frame_data(self, frame, with_points=True):
            return FrameData(frame, np.empty((0, 3)), np.eye(4))

    findings = detect_floating_scene([car(f) for f in range(3)], Empty(), config.floating)
    assert [(f.rule, f.severity, f.details["frames"]) for f in findings] == [
        ("floating.no_evidence", Severity.INFO, [0, 1, 2])]


# --- Kích thước: theo track ----------------------------------------------------------------------------


def test_class_range_reports_once_per_track_on_extreme_keyframe(config):
    huge = [car(f, dims=(20.0 + f, 6.0, 5.0)) for f in range(4)]
    findings = [f for f in detect_size(huge, config.size) if f.rule == "size.class_range"]
    assert [(f.frame, f.severity) for f in findings] == [(3, Severity.ERROR)]
    assert "trung vị của 4 keyframe" in findings[0].message


def test_class_range_uses_stats_from_config(config):
    low, high = config.size.class_range.stats["car"]["length"]
    warn = car(0, dims=(high * 1.15, 1.9, 1.6), track_id=None)  # ngoài biên 10%, trong 25%
    assert [(f.rule, f.severity) for f in detect_size([warn], config.size)] == [
        ("size.class_range", Severity.WARNING)]


def test_in_track_reports_one_finding_per_keyframe(config):
    track = [car(f) for f in range(4)] + [car(4, dims=(6.0, 2.6, 2.2))]  # cả 3 chiều cùng lệch
    findings = [f for f in detect_size(track, config.size) if f.rule == "size.in_track"]
    assert [(f.frame, f.severity) for f in findings] == [(4, Severity.ERROR)]


# --- Đứt track -----------------------------------------------------------------------------------------


def moving(n=7, track_id=1, start=0, speed=10.0):
    return [car(start + f, x=speed * 0.5 * (start + f), track_id=track_id) for f in range(n)]


def poses(boxes):
    return {b.frame: np.eye(4) for b in boxes}, {b.frame: b.frame * 0.5 for b in boxes}


def test_jump_reports_only_the_jumped_keyframe(config):
    boxes = moving()
    boxes[3] = boxes[3].replace(center=(boxes[3].center[0], 2.5, boxes[3].center[2]))
    findings = detect_track_errors(boxes, config.track, *poses(boxes))
    assert [(f.rule, f.frame, f.severity) for f in findings] == [("track.jump", 3, Severity.ERROR)]


def test_jump_at_segment_end_uses_extrapolation(config):
    boxes = moving()
    boxes[0] = boxes[0].replace(center=(boxes[0].center[0], 4.0, boxes[0].center[2]))
    findings = detect_track_errors(boxes, config.track, *poses(boxes))
    assert [(f.frame, f.severity) for f in findings] == [(0, Severity.ERROR)]  # 4 m > 2 m × 1,5
    assert "ngoại suy" in findings[0].message


def test_no_interpolation_across_outside_gap(config):
    """Đối tượng vắng 3 frame (có outside): không nội suy qua đoạn vắng, không báo nhảy / nội suy dài."""
    boxes = add_outside_markers([b for b in moving(n=9) if b.frame not in (3, 4, 5)], 9)
    rules = {f.rule for f in detect_track_errors(boxes, config.track, *poses(boxes))}
    assert not rules & {"track.jump", "track.long_interpolation"}


def test_long_interpolation_only_for_moving_objects(config):
    gap = [b for b in moving(n=6) if b.frame not in (2, 3)]
    findings = [f for f in detect_track_errors(gap, config.track, *poses(gap)) if f.rule == "track.long_interpolation"]
    assert [(f.frame, f.value) for f in findings] == [(1, 2.0)]
    parked = [car(f, track_id=5) for f in (0, 1, 4, 5)]
    assert [f for f in detect_track_errors(parked, config.track, *poses(parked))
            if f.rule == "track.long_interpolation"] == []


def test_split_requires_previous_track_to_end_before_last_frame(config):
    first = moving(n=4, track_id=1)
    second = moving(n=4, track_id=2, start=4)
    boxes = add_outside_markers(first + second + [car(9, x=-30, track_id=3)], 10)
    findings = [f for f in detect_track_errors(boxes, config.track, *poses(boxes)) if f.rule == "track.split_id"]
    assert [(f.track_id, f.frame, f.details["previous_track_id"]) for f in findings] == [(2, 4, 1)]
