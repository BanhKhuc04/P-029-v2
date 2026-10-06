import math

import pytest

from pointsnap.core.model import Cuboid, ErrorType, Finding, Severity, group_by_frame, group_by_track


def box(frame=0, track_id=None, **kw):
    params = dict(center=(0.0, 0.0, 1.0), dims=(4.0, 2.0, 1.5), yaw=0.0, label="car")
    params.update(kw)
    return Cuboid(frame=frame, track_id=track_id, **params)


def test_cuboid_basic_properties():
    b = box(center=(1, 2, 1.0), dims=(4, 2, 1.5))
    assert b.center == (1.0, 2.0, 1.0)
    assert (b.length, b.width, b.height) == (4.0, 2.0, 1.5)
    assert b.bottom_z == pytest.approx(0.25)
    assert b.top_z == pytest.approx(1.75)


def test_cuboid_normalizes_yaw():
    assert box(yaw=3 * math.pi / 2).yaw == pytest.approx(-math.pi / 2)


@pytest.mark.parametrize("dims", [(4, 2, 0), (4, -1, 1), (4, 2)])
def test_cuboid_rejects_bad_dims(dims):
    with pytest.raises(ValueError):
        box(dims=dims)


def test_cuboid_rejects_non_finite_values():
    with pytest.raises(ValueError):
        box(center=(0, float("nan"), 0))
    with pytest.raises(ValueError):
        box(yaw=float("inf"))


def test_cuboid_is_immutable_and_replace_keeps_validation():
    b = box()
    with pytest.raises(AttributeError):
        b.yaw = 1.0  # type: ignore[misc]
    moved = b.replace(center=(0, 0, 2))
    assert moved.bottom_z == pytest.approx(1.25) and b.bottom_z == pytest.approx(0.25)
    with pytest.raises(ValueError):
        b.replace(dims=(0, 1, 1))


def test_attrs_do_not_affect_equality():
    assert box(attrs={"a": 1}) == box(attrs={"a": 2})
    assert hash(box(attrs={"a": 1})) == hash(box())


def test_group_by_track_sorts_frames_and_skips_untracked():
    boxes = [box(frame=2, track_id=7), box(frame=0, track_id=7), box(frame=1, track_id=3), box(frame=1)]
    tracks = group_by_track(boxes)
    assert list(tracks) == [3, 7]
    assert [b.frame for b in tracks[7]] == [0, 2]


def test_group_by_frame():
    frames = group_by_frame([box(frame=2), box(frame=0), box(frame=2)])
    assert list(frames) == [0, 2]
    assert len(frames[2]) == 2


def test_finding_sort_puts_errors_first():
    def finding(sev, frame):
        return Finding(ErrorType.FLOATING, "floating", sev, frame, "car", "x")

    items = [finding(Severity.INFO, 0), finding(Severity.WARNING, 5), finding(Severity.ERROR, 9)]
    assert [f.severity for f in sorted(items, key=Finding.sort_key)] == [
        Severity.ERROR, Severity.WARNING, Severity.INFO,
    ]
    # track_id = 0 là một track thật, phải xếp sau box không có track (-1)
    by_track = [
        Finding(ErrorType.TRACK, "track.jump", Severity.ERROR, 3, "car", "x", track_id=0),
        Finding(ErrorType.TRACK, "track.jump", Severity.ERROR, 3, "car", "x", track_id=None),
    ]
    assert [f.track_id for f in sorted(by_track, key=Finding.sort_key)] == [None, 0]
    assert Severity.WARNING.label_vi == "Cảnh báo"
    assert ErrorType.TRACK.label_vi == "Đứt track"
