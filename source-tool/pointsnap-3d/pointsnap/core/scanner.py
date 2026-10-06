"""Bộ quét kiểm tra chất lượng nhãn 3D (việc A5, A6).

Gom ba bộ phát hiện (lơ lửng / lún, sai kích thước, đứt track) và chạy trên danh sách box của một job hay một cảnh.
Core không phụ thuộc CVAT: nhận `Cuboid` (hoặc đối tượng có thuộc tính `cuboids`, ví dụ `JobData`) và một
`FrameSource` để đọc point cloud + pose. Không có `FrameSource` thì bỏ luật lơ lửng / lún, luật đứt track chỉ báo
mức Cảnh báo.
"""

from __future__ import annotations

from typing import Any, Callable, Iterable, Sequence

from pointsnap.core.config import Config
from pointsnap.core.floating import check_floating
from pointsnap.core.model import Cuboid, Finding, FrameSource, Severity
from pointsnap.core.size import check_size_class_range, check_size_in_track as _check_size_in_track
from pointsnap.core.track import check_track

DetectorFn = Callable[[list[Cuboid], Config, FrameSource | None], list[Finding]]


def _cuboids(source: Any) -> list[Cuboid]:
    return list(getattr(source, "cuboids", source))


def check_size_manual_ranges(source: Any, config: Config, frames: FrameSource | None = None) -> list[Finding]:
    """Sai kích thước so với class (kiểu 1). Giữ tên cũ của A5."""
    return check_size_class_range(_cuboids(source), config, frames)


def check_size_in_track(source: Any, config: Config, frames: FrameSource | None = None) -> list[Finding]:
    """Kích thước dao động trong track (kiểu 2)."""
    return _check_size_in_track(_cuboids(source), config, frames)


DEFAULT_DETECTORS: Sequence[DetectorFn] = (
    check_floating,
    check_size_class_range,
    _check_size_in_track,
    check_track,
)


def scan_cuboids(
    source: Any,
    config: Config,
    frames: FrameSource | None = None,
    detectors: Sequence[DetectorFn] | None = None,
) -> list[Finding]:
    """Chạy mọi bộ phát hiện trên các box của `source` và trả về finding đã sắp xếp."""
    cuboids = _cuboids(source)
    findings: list[Finding] = []
    for detector in detectors if detectors is not None else DEFAULT_DETECTORS:
        findings.extend(detector(cuboids, config, frames))
    return sorted(findings, key=lambda f: f.sort_key())


def actionable(findings: Iterable[Finding]) -> list[Finding]:
    """Finding mức Lỗi / Cảnh báo: những mục được ghi cờ lên CVAT và tính ở `gate`."""
    return [f for f in findings if f.severity is not Severity.INFO]
