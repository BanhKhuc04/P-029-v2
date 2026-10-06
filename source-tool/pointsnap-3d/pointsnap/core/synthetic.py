"""Bộ chèn lỗi giả có kiểm soát theo mục 8.1 của đề xuất (việc A7).

Hỗ trợ 6 loại lỗi:
1. Lơ lửng / lún: dịch Z của box lên hoặc xuống (5, 10, 20, 40 cm).
2. Kích thước trong track: làm lệch (l, w, h) ở một keyframe (5%, 15%, 30%).
3. Kích thước theo class: phóng to/thu nhỏ cả track (x0.6; x1.5) hoặc gán kích thước class khác.
4. Đứt track - nhảy vị trí: dịch tâm một keyframe (0.5, 1.0, 2.0, 4.0 m).
5. Đứt track - tách ID: cắt một track thành 2 ID riêng biệt.
6. Đứt track - khoảng nội suy: xóa 1, 2, 3 keyframe liên tiếp giữa track.

Kèm cơ chế xuất log JSON để script B6 (đo Precision / Recall) so sánh đối chiếu.
"""

from __future__ import annotations

import dataclasses
import json
import math
import random
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable, Sequence

from pointsnap.core.model import Cuboid, group_by_track


@dataclass(frozen=True)
class InjectedError:
    """Bản ghi mô tả chi tiết một lỗi được chèn giả."""

    error_type: str
    """Loại lỗi: 'floating', 'size_in_track', 'size_class_range', 'track_jump', 'track_split_id', 'track_interpolation'."""
    magnitude: float | str
    """Mức độ: số đo (m, tỉ lệ) hoặc chuỗi mô tả."""
    track_id: int
    frame: int | None
    source_id: int | None
    description: str
    original_value: Any
    injected_value: Any


def inject_floating(
    cuboids: list[Cuboid],
    track_id: int,
    frame: int,
    delta_z_m: float,
) -> tuple[list[Cuboid], InjectedError]:
    """Dịch Z của box ở một frame cụ thể lên/xuống `delta_z_m`."""
    res: list[Cuboid] = []
    injected: InjectedError | None = None

    for c in cuboids:
        if c.track_id == track_id and c.frame == frame and not c.outside:
            old_z = c.center[2]
            new_z = old_z + delta_z_m
            new_center = (c.center[0], c.center[1], new_z)
            mod = c.replace(center=new_center)
            res.append(mod)
            direction = "lơ lửng" if delta_z_m > 0 else "lún"
            injected = InjectedError(
                error_type="floating",
                magnitude=abs(delta_z_m),
                track_id=track_id,
                frame=frame,
                source_id=c.source_id,
                description=f"{direction.capitalize()} {abs(delta_z_m)*100:.0f} cm",
                original_value=old_z,
                injected_value=new_z,
            )
        else:
            res.append(c)

    if injected is None:
        raise ValueError(f"Không tìm thấy box track_id={track_id}, frame={frame} để chèn floating")
    return res, injected


def inject_size_in_track(
    cuboids: list[Cuboid],
    track_id: int,
    frame: int,
    scale_factor: float,
) -> tuple[list[Cuboid], InjectedError]:
    """Làm lệch kích thước (l, w, h) của một keyframe trong track theo tỉ lệ `scale_factor`."""
    res: list[Cuboid] = []
    injected: InjectedError | None = None

    for c in cuboids:
        if c.track_id == track_id and c.frame == frame and not c.outside:
            old_dims = c.dims
            new_dims = (old_dims[0] * scale_factor, old_dims[1] * scale_factor, old_dims[2] * scale_factor)
            mod = c.replace(dims=new_dims)
            res.append(mod)
            pct = (scale_factor - 1.0) * 100
            injected = InjectedError(
                error_type="size_in_track",
                magnitude=abs(scale_factor - 1.0),
                track_id=track_id,
                frame=frame,
                source_id=c.source_id,
                description=f"Lệch kích thước keyframe {pct:+.0f}%",
                original_value=list(old_dims),
                injected_value=list(new_dims),
            )
        else:
            res.append(c)

    if injected is None:
        raise ValueError(f"Không tìm thấy box track_id={track_id}, frame={frame} để chèn size_in_track")
    return res, injected


def inject_size_class_range(
    cuboids: list[Cuboid],
    track_id: int,
    scale_factor: float | None = None,
    override_dims: tuple[float, float, float] | None = None,
) -> tuple[list[Cuboid], InjectedError]:
    """Phóng to/thu nhỏ cả track hoặc gán kích thước bất thường theo class."""
    res: list[Cuboid] = []
    sample_box: Cuboid | None = None

    for c in cuboids:
        if c.track_id == track_id:
            if sample_box is None and not c.outside:
                sample_box = c
            if override_dims:
                new_dims = override_dims
            elif scale_factor:
                new_dims = (c.dims[0] * scale_factor, c.dims[1] * scale_factor, c.dims[2] * scale_factor)
            else:
                new_dims = c.dims
            res.append(c.replace(dims=new_dims))
        else:
            res.append(c)

    if sample_box is None:
        raise ValueError(f"Không tìm thấy track_id={track_id}")

    desc = f"Đổi kích thước cả track theo dims {override_dims}" if override_dims else f"Quy mô cả track x{scale_factor}"
    mag = "override" if override_dims else float(scale_factor or 1.0)
    injected = InjectedError(
        error_type="size_class_range",
        magnitude=mag,
        track_id=track_id,
        frame=None,
        source_id=None,
        description=desc,
        original_value=list(sample_box.dims),
        injected_value=list(override_dims) if override_dims else f"x{scale_factor}",
    )
    return res, injected


def inject_track_jump(
    cuboids: list[Cuboid],
    track_id: int,
    frame: int,
    shift_dist_m: float,
    angle_rad: float = 0.0,
) -> tuple[list[Cuboid], InjectedError]:
    """Dịch tâm (X, Y) của một keyframe một khoảng `shift_dist_m`."""
    res: list[Cuboid] = []
    injected: InjectedError | None = None

    dx = shift_dist_m * math.cos(angle_rad)
    dy = shift_dist_m * math.sin(angle_rad)

    for c in cuboids:
        if c.track_id == track_id and c.frame == frame and not c.outside:
            old_c = c.center
            new_c = (old_c[0] + dx, old_c[1] + dy, old_c[2])
            res.append(c.replace(center=new_c))
            injected = InjectedError(
                error_type="track_jump",
                magnitude=shift_dist_m,
                track_id=track_id,
                frame=frame,
                source_id=c.source_id,
                description=f"Nhảy vị trí {shift_dist_m:.1f} m",
                original_value=list(old_c),
                injected_value=list(new_c),
            )
        else:
            res.append(c)

    if injected is None:
        raise ValueError(f"Không tìm thấy box track_id={track_id}, frame={frame} để chèn track_jump")
    return res, injected


def inject_track_split(
    cuboids: list[Cuboid],
    track_id: int,
    split_at_frame: int,
    new_track_id: int,
) -> tuple[list[Cuboid], InjectedError]:
    """Cắt track tại `split_at_frame` thành ID mới `new_track_id`."""
    res: list[Cuboid] = []
    modified_count = 0

    for c in cuboids:
        if c.track_id == track_id and c.frame >= split_at_frame:
            res.append(c.replace(track_id=new_track_id))
            modified_count += 1
        else:
            res.append(c)

    if modified_count == 0:
        raise ValueError(f"Không tìm thấy box nào để split cho track_id={track_id} từ frame={split_at_frame}")

    injected = InjectedError(
        error_type="track_split_id",
        magnitude="split",
        track_id=track_id,
        frame=split_at_frame,
        source_id=None,
        description=f"Tách track #{track_id} thành track mới #{new_track_id} từ frame {split_at_frame}",
        original_value=track_id,
        injected_value=new_track_id,
    )
    return res, injected


def inject_track_interpolation_gap(
    cuboids: list[Cuboid],
    track_id: int,
    num_frames: int = 2,
) -> tuple[list[Cuboid], InjectedError]:
    """Xóa `num_frames` keyframe liên tiếp ở giữa track của đối tượng."""
    tracks = group_by_track(cuboids)
    track_boxes = [b for b in tracks.get(track_id, []) if not b.outside]
    if len(track_boxes) < num_frames + 2:
        raise ValueError(f"Track {track_id} quá ngắn ({len(track_boxes)} keyframe) để xóa {num_frames} frame ở giữa")

    # Chọn khoảng ở giữa
    start_idx = len(track_boxes) // 2 - num_frames // 2
    dropped_frames = {track_boxes[i].frame for i in range(start_idx, start_idx + num_frames)}

    res = [c for c in cuboids if not (c.track_id == track_id and c.frame in dropped_frames)]

    injected = InjectedError(
        error_type="track_interpolation",
        magnitude=num_frames,
        track_id=track_id,
        frame=min(dropped_frames),
        source_id=None,
        description=f"Xóa {num_frames} keyframe liên tiếp ({sorted(dropped_frames)})",
        original_value=len(track_boxes),
        injected_value=len(track_boxes) - num_frames,
    )
    return res, injected


def save_injection_log(path: str | Path, errors: Sequence[InjectedError], meta: dict[str, Any] | None = None) -> None:
    """Lưu danh sách lỗi đã chèn ra file JSON để script đánh giá (B6) sử dụng."""
    payload = {
        "version": 1,
        "meta": meta or {},
        "total_errors": len(errors),
        "injected_errors": [asdict(e) for e in errors],
    }
    Path(path).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def load_injection_log(path: str | Path) -> tuple[list[InjectedError], dict[str, Any]]:
    """Đọc file log lỗi đã chèn."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    errors = [
        InjectedError(
            error_type=e["error_type"],
            magnitude=e["magnitude"],
            track_id=e["track_id"],
            frame=e["frame"],
            source_id=e["source_id"],
            description=e["description"],
            original_value=e["original_value"],
            injected_value=e["injected_value"],
        )
        for e in data.get("injected_errors", [])
    ]
    return errors, data.get("meta", {})


def inject_dataset(
    cuboids: Iterable[Cuboid],
    seed: int = 42,
    error_rate: float = 0.10,
) -> tuple[list[Cuboid], list[InjectedError]]:
    """Tự động chèn lỗi có kiểm soát vào ~10% số track theo mục 8.1.

    Mỗi track được chọn chỉ mang ĐÚNG MỘT lỗi.
    Phân bố đều qua các loại lỗi và các mức độ.
    """
    rng = random.Random(seed)
    cuboid_list = list(cuboids)
    tracks = group_by_track(cuboid_list)

    # Lọc các track hợp lệ có ít nhất 3 frame hoạt động
    valid_tids = [
        tid for tid, boxes in tracks.items()
        if len([b for b in boxes if not b.outside]) >= 3
    ]
    if not valid_tids:
        return cuboid_list, []

    num_to_inject = max(1, int(len(valid_tids) * error_rate))
    chosen_tids = rng.sample(valid_tids, min(num_to_inject, len(valid_tids)))

    # Danh mục lỗi và mức theo bảng mục 8.1
    error_configs = [
        # (loại lỗi, tham số)
        ("floating", 0.05),
        ("floating", 0.10),
        ("floating", 0.20),
        ("floating", 0.40),
        ("size_in_track", 1.05),
        ("size_in_track", 1.15),
        ("size_in_track", 1.30),
        ("size_class_range", 0.6),
        ("size_class_range", 1.5),
        ("track_jump", 0.5),
        ("track_jump", 1.0),
        ("track_jump", 2.0),
        ("track_jump", 4.0),
        ("track_split_id", None),
        ("track_interpolation", 1),
        ("track_interpolation", 2),
    ]

    modified_cuboids = list(cuboid_list)
    injected_errors: list[InjectedError] = []

    next_free_track_id = max(tracks.keys(), default=0) + 1000

    for i, tid in enumerate(chosen_tids):
        active_boxes = [b for b in tracks[tid] if not b.outside]
        mid_box = active_boxes[len(active_boxes) // 2]
        err_type, param = error_configs[i % len(error_configs)]

        try:
            if err_type == "floating":
                modified_cuboids, log = inject_floating(modified_cuboids, tid, mid_box.frame, float(param))
            elif err_type == "size_in_track":
                modified_cuboids, log = inject_size_in_track(modified_cuboids, tid, mid_box.frame, float(param))
            elif err_type == "size_class_range":
                modified_cuboids, log = inject_size_class_range(modified_cuboids, tid, scale_factor=float(param))
            elif err_type == "track_jump":
                modified_cuboids, log = inject_track_jump(modified_cuboids, tid, mid_box.frame, float(param))
            elif err_type == "track_split_id":
                next_free_track_id += 1
                modified_cuboids, log = inject_track_split(modified_cuboids, tid, mid_box.frame, next_free_track_id)
            elif err_type == "track_interpolation":
                modified_cuboids, log = inject_track_interpolation_gap(modified_cuboids, tid, num_frames=int(param))
            else:
                continue
            injected_errors.append(log)
        except Exception:
            # Nếu track không thỏa điều kiện của kiểu lỗi đó, bỏ qua
            continue

    return modified_cuboids, injected_errors
