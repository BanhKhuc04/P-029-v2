"""Hình học cho cuboid 3D.

Đơn vị mét và radian, hệ tay phải, z hướng lên (xem CONVENTIONS.md).
Box chỉ có yaw: roll và pitch được coi bằng 0.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from pointsnap.core.model import Cuboid


def normalize_angle(angle: float) -> float:
    """Đưa góc về khoảng [-π, π)."""
    return (angle + math.pi) % (2.0 * math.pi) - math.pi


def to_box_frame(points: np.ndarray, cuboid: Cuboid) -> np.ndarray:
    """Đổi điểm (N, 3) sang hệ local của box: gốc ở tâm box, trục x theo hướng đầu box."""
    rel = np.asarray(points, dtype=np.float64)[:, :3] - np.asarray(cuboid.center)
    c, s = math.cos(cuboid.yaw), math.sin(cuboid.yaw)
    return np.column_stack((c * rel[:, 0] + s * rel[:, 1], -s * rel[:, 0] + c * rel[:, 1], rel[:, 2]))


def _from_box_frame(local: np.ndarray, cuboid: Cuboid) -> np.ndarray:
    c, s = math.cos(cuboid.yaw), math.sin(cuboid.yaw)
    x = c * local[:, 0] - s * local[:, 1]
    y = s * local[:, 0] + c * local[:, 1]
    return np.column_stack((x, y, local[:, 2])) + np.asarray(cuboid.center)


def corners(cuboid: Cuboid) -> np.ndarray:
    """8 góc của box, shape (8, 3).

    Thứ tự: 4 góc đáy rồi 4 góc nóc, mỗi mặt đi ngược chiều kim đồng hồ nhìn từ trên xuống,
    bắt đầu từ góc trước-trái: (+l, +w), (-l, +w), (-l, -w), (+l, -w).
    """
    hl, hw, hh = (d / 2.0 for d in cuboid.dims)
    xy = [(hl, hw), (-hl, hw), (-hl, -hw), (hl, -hw)]
    local = np.array([(x, y, -hh) for x, y in xy] + [(x, y, hh) for x, y in xy])
    return _from_box_frame(local, cuboid)


def footprint(cuboid: Cuboid, margin: float = 0.0) -> np.ndarray:
    """4 góc đáy nhìn từ trên xuống (BEV), shape (4, 2), ngược chiều kim đồng hồ.

    `margin` nới rộng footprint ra mỗi phía (mét).
    """
    hl, hw = cuboid.dims[0] / 2.0 + margin, cuboid.dims[1] / 2.0 + margin
    local = np.array([(hl, hw, 0.0), (-hl, hw, 0.0), (-hl, -hw, 0.0), (hl, -hw, 0.0)])
    return _from_box_frame(local, cuboid)[:, :2]


def points_in_cuboid(points: np.ndarray, cuboid: Cuboid, margin: float = 0.0) -> np.ndarray:
    """Mask bool cho các điểm nằm trong box (nới thêm `margin` mét mỗi phía)."""
    local = to_box_frame(points, cuboid)
    half = np.asarray(cuboid.dims) / 2.0 + margin
    return np.all(np.abs(local) <= half, axis=1)


def footprint_ring_mask(points: np.ndarray, cuboid: Cuboid, inner: float, outer: float) -> np.ndarray:
    """Mask bool cho các điểm thuộc vành đai quanh footprint, chỉ xét x, y.

    Vành đai là vùng nằm trong footprint nới `outer` mét nhưng ngoài footprint nới `inner` mét.
    """
    if not 0.0 <= inner < outer:
        raise ValueError(f"Cần 0 <= inner < outer, nhận inner={inner}, outer={outer}")
    local = np.abs(to_box_frame(points, cuboid)[:, :2])
    half = np.asarray(cuboid.dims[:2]) / 2.0
    in_outer = np.all(local <= half + outer, axis=1)
    in_inner = np.all(local <= half + inner, axis=1)
    return in_outer & ~in_inner


def transform_points(points: np.ndarray, matrix: np.ndarray) -> np.ndarray:
    """Áp ma trận đồng nhất 4x4 lên điểm (N, 3)."""
    pts = np.asarray(points, dtype=np.float64)[:, :3]
    m = np.asarray(matrix, dtype=np.float64)
    if m.shape != (4, 4):
        raise ValueError(f"Ma trận phải có shape (4, 4), nhận {m.shape}")
    return pts @ m[:3, :3].T + m[:3, 3]


def polygon_area(polygon: np.ndarray) -> float:
    """Diện tích đa giác 2D (công thức shoelace), không phụ thuộc chiều đi."""
    if len(polygon) < 3:
        return 0.0
    x, y = polygon[:, 0], polygon[:, 1]
    return 0.5 * abs(float(np.dot(x, np.roll(y, -1)) - np.dot(y, np.roll(x, -1))))


def _cross(o: np.ndarray, a: np.ndarray, b: np.ndarray) -> float:
    return float((a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0]))


def _clip_convex(subject: np.ndarray, clip: np.ndarray) -> np.ndarray:
    """Cắt đa giác `subject` bằng đa giác lồi `clip` (ngược chiều kim đồng hồ), Sutherland–Hodgman."""
    output = [p for p in subject]
    for i in range(len(clip)):
        a, b = clip[i], clip[(i + 1) % len(clip)]
        candidates, output = output, []
        if not candidates:
            break
        prev = candidates[-1]
        side_prev = _cross(a, b, prev)
        for cur in candidates:
            side_cur = _cross(a, b, cur)
            if (side_cur >= 0.0) != (side_prev >= 0.0):
                # Hai đầu nằm hai phía của cạnh nên side_prev − side_cur luôn khác 0.
                t = side_prev / (side_prev - side_cur)
                output.append(prev + t * (cur - prev))
            if side_cur >= 0.0:
                output.append(cur)
            prev, side_prev = cur, side_cur
    return np.array(output).reshape(-1, 2)


def bev_iou(a: Cuboid, b: Cuboid) -> float:
    """IoU của hai box nhìn từ trên xuống (BEV)."""
    fa, fb = footprint(a), footprint(b)
    inter = polygon_area(_clip_convex(fa, fb))
    union = polygon_area(fa) + polygon_area(fb) - inter
    return inter / union if union > 0.0 else 0.0
