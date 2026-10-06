import math
import pytest

from pointsnap.core.model import Cuboid
from pointsnap.core.synthetic import (
    InjectedError,
    inject_dataset,
    inject_floating,
    inject_size_class_range,
    inject_size_in_track,
    inject_track_interpolation_gap,
    inject_track_jump,
    inject_track_split,
    load_injection_log,
    save_injection_log,
)


def make_track(track_id: int, num_frames: int = 5, label: str = "car") -> list[Cuboid]:
    return [
        Cuboid(
            center=(float(i), 0.0, 1.0),
            dims=(4.5, 2.0, 1.6),
            yaw=0.0,
            label=label,
            frame=i,
            track_id=track_id,
            source_id=100 + i,
        )
        for i in range(num_frames)
    ]


def test_inject_floating():
    boxes = make_track(1)
    mod, log = inject_floating(boxes, track_id=1, frame=2, delta_z_m=0.20)
    assert len(mod) == len(boxes)
    assert math.isclose(mod[2].center[2], 1.20)
    assert math.isclose(boxes[2].center[2], 1.0)
    assert log.error_type == "floating"
    assert log.track_id == 1
    assert log.frame == 2
    assert "20 cm" in log.description


def test_inject_size_in_track():
    boxes = make_track(1)
    mod, log = inject_size_in_track(boxes, track_id=1, frame=2, scale_factor=1.15)
    assert math.isclose(mod[2].dims[0], 4.5 * 1.15)
    assert math.isclose(mod[2].dims[1], 2.0 * 1.15)
    assert log.error_type == "size_in_track"
    assert "+15%" in log.description


def test_inject_size_class_range():
    boxes = make_track(1)
    mod, log = inject_size_class_range(boxes, track_id=1, scale_factor=1.5)
    for b in mod:
        assert math.isclose(b.dims[0], 4.5 * 1.5)
    assert log.error_type == "size_class_range"
    assert log.frame is None


def test_inject_track_jump():
    boxes = make_track(1)
    mod, log = inject_track_jump(boxes, track_id=1, frame=3, shift_dist_m=2.0)
    assert math.isclose(mod[3].center[0], 3.0 + 2.0)
    assert log.error_type == "track_jump"
    assert log.magnitude == 2.0


def test_inject_track_split():
    boxes = make_track(1, num_frames=6)
    mod, log = inject_track_split(boxes, track_id=1, split_at_frame=3, new_track_id=99)
    assert [b.track_id for b in mod] == [1, 1, 1, 99, 99, 99]
    assert log.error_type == "track_split_id"
    assert log.original_value == 1
    assert log.injected_value == 99


def test_inject_track_interpolation_gap():
    boxes = make_track(1, num_frames=6)
    mod, log = inject_track_interpolation_gap(boxes, track_id=1, num_frames=2)
    assert len(mod) == 4
    assert log.error_type == "track_interpolation"
    assert log.magnitude == 2


def test_save_and_load_injection_log(tmp_path):
    log_entry = InjectedError(
        error_type="floating",
        magnitude=0.25,
        track_id=7,
        frame=3,
        source_id=42,
        description="Lơ lửng 25 cm",
        original_value=1.0,
        injected_value=1.25,
    )
    p = tmp_path / "errors.json"
    save_injection_log(p, [log_entry], meta={"scene": "scene-0061"})
    loaded, meta = load_injection_log(p)
    assert len(loaded) == 1
    assert loaded[0] == log_entry
    assert meta["scene"] == "scene-0061"


def test_inject_dataset():
    # Tạo 10 track, mỗi track 5 frame
    all_boxes = []
    for tid in range(10):
        all_boxes.extend(make_track(tid, num_frames=5))

    mod_boxes, logs = inject_dataset(all_boxes, seed=123, error_rate=0.30)
    # Với rate 0.30, khoảng 3 track được chèn lỗi
    assert len(logs) == 3
    # Mỗi track chỉ mang 1 lỗi
    injected_tids = [log.track_id for log in logs]
    assert len(injected_tids) == len(set(injected_tids))
