"""Mô hình dữ liệu dùng chung giữa core, adapter và báo cáo.

Core chỉ nhận và trả các kiểu trong file này, nên đổi nền tảng (CVAT) hay bộ dữ liệu (nuScenes)
chỉ cần viết thêm adapter. Quy ước tọa độ: xem CONVENTIONS.md.
"""

from __future__ import annotations

import dataclasses
import math
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Iterable, Mapping

import numpy as np

from pointsnap.core.geometry import normalize_angle

Vec3 = tuple[float, float, float]


def _vec3(value: Iterable[float], name: str) -> Vec3:
    vec = tuple(float(v) for v in value)
    if len(vec) != 3 or not all(math.isfinite(v) for v in vec):
        raise ValueError(f"{name} phải gồm 3 số hữu hạn, nhận {value!r}")
    return vec  # type: ignore[return-value]


@dataclass(frozen=True)
class Cuboid:
    """Một box 3D tại một frame, trong hệ tọa độ point cloud của frame đó.

    - `center`: tâm hình học (x, y, z).
    - `dims`: (length, width, height); length nằm dọc trục x local của box (hướng đầu xe, QĐ-008).
    - `yaw`: góc quay quanh trục z, chuẩn hóa về [-π, π).
    - `track_id`: id track; `None` nếu box là shape đơn lẻ.
    - `source_id`: id bên hệ thống nguồn (ví dụ id shape trên CVAT), dùng khi ghi ngược lại.
    - `keyframe`: `False` nếu box được nội suy, không do người nhập tay.
    - `outside`: `True` nếu track đánh dấu đối tượng đã ra khỏi khung hình từ frame này.
    """

    center: Vec3
    dims: Vec3
    yaw: float
    label: str
    frame: int
    track_id: int | None = None
    source_id: int | None = None
    keyframe: bool = True
    outside: bool = False
    attrs: Mapping[str, Any] = field(default_factory=dict, compare=False, hash=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "center", _vec3(self.center, "center"))
        dims = _vec3(self.dims, "dims")
        if min(dims) <= 0.0:
            raise ValueError(f"dims phải dương, nhận {dims}")
        object.__setattr__(self, "dims", dims)
        if not math.isfinite(self.yaw):
            raise ValueError(f"yaw phải là số hữu hạn, nhận {self.yaw}")
        object.__setattr__(self, "yaw", normalize_angle(float(self.yaw)))

    @property
    def length(self) -> float:
        return self.dims[0]

    @property
    def width(self) -> float:
        return self.dims[1]

    @property
    def height(self) -> float:
        return self.dims[2]

    @property
    def bottom_z(self) -> float:
        return self.center[2] - self.dims[2] / 2.0

    @property
    def top_z(self) -> float:
        return self.center[2] + self.dims[2] / 2.0

    def replace(self, **changes: Any) -> Cuboid:
        """Bản sao với một số trường thay đổi."""
        return dataclasses.replace(self, **changes)


@dataclass(frozen=True, eq=False)
class FrameData:
    """Point cloud của một frame và thông tin để đổi sang hệ toàn cục.

    - `points`: mảng (N, 3) hoặc (N, ≥3); chỉ dùng 3 cột đầu x, y, z.
    - `sensor_to_world`: ma trận 4x4 đổi từ hệ point cloud sang hệ toàn cục; `None` nếu không có
      vị trí xe thu (khi đó luật nhảy vị trí chỉ báo ở mức Cảnh báo).
    - `timestamp`: thời điểm chụp, giây.
    - `source_ref`: khóa bên nguồn dữ liệu, ví dụ `sample_token` của nuScenes.
    """

    frame: int
    points: np.ndarray
    sensor_to_world: np.ndarray | None = None
    timestamp: float | None = None
    source_ref: str | None = None


class Severity(Enum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"

    @property
    def label_vi(self) -> str:
        return {"error": "Lỗi", "warning": "Cảnh báo", "info": "Thông tin"}[self.value]

    @property
    def rank(self) -> int:
        """Thứ tự sắp xếp: Lỗi trước, Thông tin sau cùng."""
        return {"error": 0, "warning": 1, "info": 2}[self.value]


class ErrorType(Enum):
    FLOATING = "floating"
    SIZE = "size"
    TRACK = "track"

    @property
    def label_vi(self) -> str:
        return {"floating": "Lơ lửng / lún", "size": "Sai kích thước", "track": "Đứt track"}[self.value]


@dataclass(frozen=True)
class Finding:
    """Một phát hiện của tool, gắn với một box (frame + track) cụ thể.

    - `rule`: mã luật, ví dụ `floating`, `size.class_range`, `track.jump` (danh sách ở CONVENTIONS.md).
    - `message`: câu hiển thị cho người dùng, có số đo cụ thể.
    - `value`: số đo chính, đơn vị theo luật (mét hoặc tỉ lệ); `threshold`: ngưỡng đã vượt.
    """

    error_type: ErrorType
    rule: str
    severity: Severity
    frame: int
    label: str
    message: str
    track_id: int | None = None
    source_id: int | None = None
    value: float | None = None
    threshold: float | None = None
    details: Mapping[str, Any] = field(default_factory=dict, compare=False, hash=False)

    def sort_key(self) -> tuple:
        track = self.track_id if self.track_id is not None else -1
        return (self.severity.rank, self.error_type.value, self.frame, track, self.rule)


def group_by_track(cuboids: Iterable[Cuboid]) -> dict[int, list[Cuboid]]:
    """Gom box theo `track_id`, mỗi track sắp theo frame. Bỏ qua box không có track."""
    tracks: dict[int, list[Cuboid]] = defaultdict(list)
    for cuboid in cuboids:
        if cuboid.track_id is not None:
            tracks[cuboid.track_id].append(cuboid)
    return {tid: sorted(boxes, key=lambda c: c.frame) for tid, boxes in sorted(tracks.items())}


def group_by_frame(cuboids: Iterable[Cuboid]) -> dict[int, list[Cuboid]]:
    """Gom box theo frame, sắp theo frame tăng dần."""
    frames: dict[int, list[Cuboid]] = defaultdict(list)
    for cuboid in cuboids:
        frames[cuboid.frame].append(cuboid)
    return dict(sorted(frames.items()))
