"""Lơ lửng / lún trên mặt đất không phẳng (việc C4): dốc dọc / ngang, đoạn chuyển bằng → dốc, đá, bậc vỉa hè, chỉ
thấy điểm một phía.

Box 7-DoF không có pitch / roll nên trên dốc, box đúng spec 4.2 có đáy chạm **điểm tiếp xúc thấp nhất** (bánh / chân phía
dưới dốc); phần còn lại của đáy box nằm dưới mặt dốc. Mỗi ca ghi kết quả mong muốn: báo hay không báo `floating`.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from pointsnap.core.config import load_config
from pointsnap.core.ground import ring_ground_for_box
from pointsnap.core.model import Cuboid
from pointsnap.detectors.floating import floating_findings_by_track

CFG = load_config(None).floating


def _ground(height, step=0.1, x=(4.0, 16.0), y=(-4.0, 4.0), keep=None, seed=0):
    """Điểm mặt đất trên lưới `step`, z = height(x, y) + nhiễu 1,5 cm; `keep(x, y)` để bỏ bớt một phần."""
    rng = np.random.default_rng(seed)
    xs, ys = np.meshgrid(np.arange(*x, step), np.arange(*y, step))
    xs, ys = xs.ravel(), ys.ravel()
    if keep is not None:
        m = keep(xs, ys)
        xs, ys = xs[m], ys[m]
    zs = height(xs, ys) + rng.normal(0.0, 0.015, len(xs))
    return np.column_stack([xs, ys, zs])


def _box(height, offset=0.0, x=10.0, y=0.0, dims=(4.5, 1.9, 1.6), label="car", frame=0, track_id=None):
    """Box đặt đúng spec: đáy = điểm thấp nhất của mặt đất dưới 4 góc đáy, cộng `offset` (dương: lơ lửng)."""
    hx, hy = dims[0] / 2, dims[1] / 2
    contact = min(height(np.array([x + sx * hx]), np.array([y + sy * hy]))[0] for sx in (-1, 1) for sy in (-1, 1))
    return Cuboid(center=(x, y, contact + offset + dims[2] / 2), dims=dims, yaw=0.0, label=label, frame=frame,
                  track_id=track_id)


def _estimate(points, box):
    return ring_ground_for_box(points, box, ring_inner_m=CFG.ring_inner_m, ring_outer_m=CFG.ring_outer_m,
                               min_ground_points=CFG.min_ground_points)


def _flagged(pairs):
    """Các frame bị báo `floating` mức Cảnh báo trở lên."""
    return sorted(f.frame for f in floating_findings_by_track(pairs, CFG) if f.rule == "floating")


def _slope(deg, axis=0):
    t = math.tan(math.radians(deg))
    return (lambda x, y: t * x) if axis == 0 else (lambda x, y: t * y)


def _flat(x, y):
    return np.zeros_like(x)


@pytest.mark.parametrize("deg", [0, 3, 6, 10])
@pytest.mark.parametrize("axis", [0, 1])
def test_correct_box_on_slope_not_flagged(deg, axis):
    """Box lẻ đặt đúng spec trên dốc dọc (axis 0) / ngang (axis 1) 0 – 10°: không báo."""
    h = _slope(deg, axis)
    box = _box(h)
    assert _flagged([(box, _estimate(_ground(h), box))]) == []


@pytest.mark.parametrize("offset", [0.25, -0.25])
def test_floating_or_sunk_box_on_slope_flagged(offset):
    """Box lơ lửng / lún 25 cm trên dốc 6°: phải báo."""
    h = _slope(6)
    box = _box(h, offset=offset)
    est = _estimate(_ground(h), box)
    assert _flagged([(box, est)]) == [0]
    assert est.contact_distance == pytest.approx(offset, abs=0.07)


def _track(heights, offsets=None):
    offsets = offsets or [0.0] * len(heights)
    pairs = []
    for f, (h, off) in enumerate(zip(heights, offsets)):
        box = _box(h, offset=off, frame=f, track_id=1)
        pairs.append((box, _estimate(_ground(h, seed=f), box)))
    return pairs


@pytest.mark.xfail(strict=True, reason="giới hạn đã biết (C4): box thuộc track so trung vị độ cao vành đai với các frame "
                   "khác; mặt phẳng dốc khớp trên LiDAR thật quá nhiễu để dùng cho mọi box (tăng báo nhầm trên nuScenes)")
def test_track_from_flat_onto_slope_not_flagged():
    """Track đi từ đường bằng (frame 0 – 4) lên dốc 8° (frame 5 – 9), mọi box đúng spec: không báo frame nào."""
    assert _flagged(_track([_flat] * 5 + [_slope(8)] * 5)) == []


def test_track_on_slope_one_floating_frame_flagged():
    """Track trên dốc 8°, frame 6 lơ lửng 25 cm: chỉ báo frame 6."""
    assert _flagged(_track([_slope(8)] * 10, [0.25 if f == 6 else 0.0 for f in range(10)])) == [6]


def test_rock_in_ring_not_flagged():
    """Đá cao 15 cm, rộng 40 cm trong vành đai: không báo."""
    def h(x, y):
        return np.where((np.abs(x - 12.6) < 0.2) & (np.abs(y) < 0.2), 0.15, 0.0)
    box = _box(_flat)
    assert _flagged([(box, _estimate(_ground(h), box))]) == []


def test_pedestrian_at_curb_edge_not_flagged():
    """Người đứng trên vỉa hè (cao 15 cm), sát mép bậc: nửa vành đai rơi xuống lòng đường; lòng đường gần LiDAR hơn nên
    nhiều điểm hơn. Không được báo "lơ lửng 15 cm" (đúng spec, hoặc ghi thiếu bằng chứng)."""
    def h(x, y):
        return np.where(y >= 0.0, 0.15, 0.0)
    road = _ground(h, step=0.06, keep=lambda x, y: y < 0.0)
    walk = _ground(h, step=0.15, keep=lambda x, y: y >= 0.0, seed=1)
    box = _box(h, x=10.0, y=0.05, dims=(0.7, 0.7, 1.75), label="pedestrian")
    assert _flagged([(box, _estimate(np.vstack([road, walk]), box))]) == []


def test_one_sided_points_on_lateral_slope_not_flagged():
    """Dốc ngang 6°, LiDAR chỉ thấy phía trên dốc của xe (phía kia bị thân xe che): không báo."""
    h = _slope(6, axis=1)
    box = _box(h)
    pts = _ground(h, keep=lambda x, y: y > 0.95)
    assert _flagged([(box, _estimate(pts, box))]) == []
