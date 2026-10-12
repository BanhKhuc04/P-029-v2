"""Bộ mô phỏng cảnh LiDAR đơn giản để tái hiện tình huống giao thông thật trong test (việc C5).

Mỗi vật có quỹ đạo trong hệ toàn cục (`pose(t)` → x, y, yaw), kích thước, class, thuộc tính và có thể có **phần phụ**
(hàng chở, ô, gương…) sinh điểm LiDAR nhưng không thuộc box nhãn. Mỗi frame sinh:

- mặt đất z = `ground(x, y)` (mặc định phẳng), mật độ giảm theo khoảng cách như LiDAR quay, có **bóng** sau vật;
- điểm trên các mặt box nhìn thấy từ cảm biến, mật độ ∝ 1 / r², nhiễu 2 cm;
- nhãn chuẩn: box đặt đúng vật (đáy chạm đất), trong hệ cảm biến của frame.

Xe thu có thể đứng yên hoặc chạy (`ego(t)`), cảm biến cao 1,8 m. `scan(scene)` chạy toàn bộ luật như khi quét thật.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Callable

import numpy as np

from pointsnap.core.config import load_config
from pointsnap.core.model import Cuboid, FrameData, add_track_markers
from pointsnap.core.scanner import scan_cuboids

SENSOR_H = 1.8
DT = 0.5


@dataclass
class Part:
    """Khối phụ gắn vào vật (hệ vật: x về đầu, y sang trái), sinh điểm nhưng không nằm trong nhãn."""

    offset: tuple[float, float, float]
    dims: tuple[float, float, float]


@dataclass
class Obj:
    track_id: int
    label: str
    dims: tuple[float, float, float]
    pose: Callable[[float], tuple[float, float, float]]
    frames: range | list[int] | None = None
    attrs: dict = field(default_factory=dict)
    parts: list[Part] = field(default_factory=list)
    hidden: set[int] = field(default_factory=set)
    """Frame vật bị che hoàn toàn: không sinh điểm (nhãn vẫn có, đánh dấu theo `labelled`)."""
    labelled: Callable[[int, Cuboid], Cuboid | None] | None = None
    """Sửa / bỏ nhãn ở frame (mô phỏng lỗi người gán); None = nhãn đúng."""


@dataclass
class Scene:
    objects: list[Obj]
    num_frames: int = 12
    ego: Callable[[float], tuple[float, float, float]] = lambda t: (0.0, 0.0, 0.0)
    ground: Callable[[np.ndarray, np.ndarray], np.ndarray] = lambda x, y: np.zeros_like(x)
    seed: int = 0
    rain: int = 0
    """Số điểm nhiễu mưa / bụi lơ lửng mỗi frame."""


def _pose_matrix(x: float, y: float, z: float, yaw: float) -> np.ndarray:
    m = np.eye(4)
    c, s = math.cos(yaw), math.sin(yaw)
    m[:3, :3] = [[c, -s, 0], [s, c, 0], [0, 0, 1]]
    m[:3, 3] = [x, y, z]
    return m


def _box_surface(center, dims, yaw, sensor, rng, density=3000.0):
    """Điểm trên các mặt box (hệ toàn cục) nhìn thấy từ `sensor`."""
    l, w, h = dims
    c, s = math.cos(yaw), math.sin(yaw)
    rot = np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]])
    r = max(np.hypot(center[0] - sensor[0], center[1] - sensor[1]), 2.0)
    faces = [((1, 0, 0), (w, h)), ((-1, 0, 0), (w, h)), ((0, 1, 0), (l, h)), ((0, -1, 0), (l, h)), ((0, 0, 1), (l, w))]
    out = []
    for normal, (a, b) in faces:
        n_world = rot @ np.array(normal, dtype=float)
        face_c = np.asarray(center) + rot @ (np.array(normal) * np.array([l, w, h]) / 2)
        if np.dot(n_world, np.asarray(sensor) - face_c) <= 0:
            continue
        k = int(min(density * a * b / r ** 2, 2000))
        if k < 1:
            continue
        u, v = rng.uniform(-0.5, 0.5, k), rng.uniform(-0.5, 0.5, k)
        if normal[0]:
            local = np.column_stack([np.full(k, normal[0] * l / 2), u * w, v * h])
        elif normal[1]:
            local = np.column_stack([u * l, np.full(k, normal[1] * w / 2), v * h])
        else:
            local = np.column_stack([u * l, v * w, np.full(k, h / 2)])
        out.append(local @ rot.T + center)
    return np.vstack(out) if out else np.zeros((0, 3))


def _shadow(points, boxes, sensor):
    """Bỏ điểm mặt đất nằm sau vật nhìn từ cảm biến (bóng LiDAR)."""
    keep = np.ones(len(points), dtype=bool)
    ang = np.arctan2(points[:, 1] - sensor[1], points[:, 0] - sensor[0])
    dist = np.hypot(points[:, 0] - sensor[0], points[:, 1] - sensor[1])
    for center, dims, yaw in boxes:
        l, w, _ = dims
        c, s = math.cos(yaw), math.sin(yaw)
        corners = [(center[0] + c * dx - s * dy, center[1] + s * dx + c * dy) for dx in (-l / 2, l / 2) for dy in (-w / 2, w / 2)]
        a = np.array([math.atan2(y - sensor[1], x - sensor[0]) for x, y in corners])
        mid = math.atan2(center[1] - sensor[1], center[0] - sensor[0])
        rel = (a - mid + math.pi) % (2 * math.pi) - math.pi
        lo, hi = rel.min(), rel.max()
        near = min(math.hypot(x - sensor[0], y - sensor[1]) for x, y in corners)
        r_pts = (ang - mid + math.pi) % (2 * math.pi) - math.pi
        keep &= ~((r_pts >= lo) & (r_pts <= hi) & (dist > near))
    return points[keep]


class SimFrames:
    def __init__(self, scene: Scene):
        self.scene = scene
        self.num_frames = scene.num_frames
        self._cache: dict[int, FrameData] = {}

    def frame_data(self, frame: int, with_points: bool = True) -> FrameData:
        if frame in self._cache:
            return self._cache[frame]
        sc = self.scene
        rng = np.random.default_rng(sc.seed * 1000 + frame)
        t = frame * DT
        ex, ey, eyaw = sc.ego(t)
        sensor = np.array([ex, ey, SENSOR_H])
        to_world = _pose_matrix(ex, ey, SENSOR_H, eyaw)
        # mặt đất: r phân bố đều (mật độ ∝ 1/r) trong 3..45 m
        n = 25000
        r = rng.uniform(3.0, 45.0, n)
        th = rng.uniform(-math.pi, math.pi, n)
        gx, gy = ex + r * np.cos(th), ey + r * np.sin(th)
        ground = np.column_stack([gx, gy, sc.ground(gx, gy) + rng.normal(0, 0.02, n)])
        shapes, pts = [], [ground]
        for o in sc.objects:
            if o.frames is not None and frame not in o.frames:
                continue
            x, y, yaw = o.pose(t)
            zb = float(sc.ground(np.array([x]), np.array([y]))[0])
            center = (x, y, zb + o.dims[2] / 2)
            shapes.append((center, o.dims, yaw))
            if frame in o.hidden:
                continue
            pts.append(_box_surface(center, o.dims, yaw, sensor, rng))
            for p in o.parts:
                c, s = math.cos(yaw), math.sin(yaw)
                pc = (x + c * p.offset[0] - s * p.offset[1], y + s * p.offset[0] + c * p.offset[1], zb + p.offset[2])
                shapes.append((pc, p.dims, yaw))
                pts.append(_box_surface(pc, p.dims, yaw, sensor, rng))
        pts[0] = _shadow(pts[0], shapes, sensor)
        if sc.rain:
            pts.append(np.column_stack([ex + rng.uniform(-20, 20, sc.rain), ey + rng.uniform(-20, 20, sc.rain),
                                        rng.uniform(0.2, 3.0, sc.rain)]))
        world = np.vstack(pts) + rng.normal(0, 0.01, (sum(len(p) for p in pts), 3))
        inv = np.linalg.inv(to_world)
        local = world @ inv[:3, :3].T + inv[:3, 3]
        data = FrameData(frame=frame, points=np.column_stack([local, np.zeros(len(local))]), sensor_to_world=to_world,
                         timestamp=t)
        self._cache[frame] = data
        return data


def labels(scene: Scene) -> list[Cuboid]:
    """Nhãn (hệ cảm biến từng frame) sau khi áp lỗi người gán (`Obj.labelled`)."""
    out = []
    for f in range(scene.num_frames):
        t = f * DT
        ex, ey, eyaw = scene.ego(t)
        inv = np.linalg.inv(_pose_matrix(ex, ey, SENSOR_H, eyaw))
        for o in scene.objects:
            if o.frames is not None and f not in o.frames:
                continue
            x, y, yaw = o.pose(t)
            zb = float(scene.ground(np.array([x]), np.array([y]))[0])
            p = inv @ np.array([x, y, zb + o.dims[2] / 2, 1.0])
            box = Cuboid(center=tuple(p[:3]), dims=o.dims, yaw=yaw - eyaw, label=o.label, frame=f, track_id=o.track_id,
                         attrs=dict(o.attrs))
            if o.labelled is not None:
                box = o.labelled(f, box)
            if box is not None:
                out.append(box)
    return out


def scan(scene: Scene, config_path=None, raw: bool = False):
    """Quét cảnh như quét thật; trả về các mục Cảnh báo / Lỗi (hoặc mọi mục nếu `raw`)."""
    cfg = load_config(config_path)
    boxes = labels(scene)
    if not raw:
        boxes = add_track_markers(boxes, scene.num_frames)
    found = scan_cuboids(boxes, cfg, SimFrames(scene))
    return found if raw else [f for f in found if f.severity.value != "info"]


def straight(x0: float, y0: float, yaw: float, speed: float) -> Callable[[float], tuple[float, float, float]]:
    return lambda t: (x0 + speed * t * math.cos(yaw), y0 + speed * t * math.sin(yaw), yaw)


def parked(x: float, y: float, yaw: float) -> Callable[[float], tuple[float, float, float]]:
    return lambda t: (x, y, yaw)
