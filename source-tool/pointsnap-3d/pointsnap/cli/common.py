"""Phần dùng chung của các lệnh quét: tìm point cloud cho job CVAT."""

from __future__ import annotations

import os
from pathlib import Path

from pointsnap.adapters.cvat.reader import JobData, ManifestFrames, find_manifest
from pointsnap.core.model import FrameSource

DEFAULT_EXPORT_DIR = Path("data/cvat")


def export_dirs() -> list[Path]:
    """Nơi tìm bản xuất `to-cvat`: biến môi trường `POINTSNAP_EXPORT_DIR` (nhiều thư mục cách nhau bởi `os.pathsep`),
    rồi `data/cvat` (mặc định của `nuscenes to-cvat --out`)."""
    dirs = [Path(p) for p in os.environ.get("POINTSNAP_EXPORT_DIR", "").split(os.pathsep) if p]
    return dirs + [DEFAULT_EXPORT_DIR]


def frames_for_job(job: JobData, manifest: Path | None = None) -> tuple[FrameSource | None, str]:
    """Nguồn point cloud cho job: `manifest` nếu có, không thì tìm bản xuất đã tạo task của job.

    Trả về `(frames, thông báo)`; `frames` là `None` khi không tìm được hoặc frame không khớp, khi đó luật lơ lửng /
    lún bị bỏ qua và luật đứt track chỉ báo mức Cảnh báo.
    """
    path = manifest or find_manifest(job.task_id, export_dirs())
    skipped = "bỏ qua luật lơ lửng / lún, luật đứt track chỉ báo mức Cảnh báo"
    if path is None:
        return None, (f"Không tìm thấy manifest.json của task {job.task_id} ({skipped}). "
                      "Chỉ đường dẫn bằng --manifest hoặc biến môi trường POINTSNAP_EXPORT_DIR.")
    try:
        frames = ManifestFrames(path, dataroot=os.environ.get("NUSCENES_ROOT") or None)
        if job.frame_names:
            frames.check_matches(job.frame_names)
    except (OSError, KeyError, ValueError) as exc:
        return None, f"Không đọc được point cloud từ {path}: {exc} ({skipped})."
    return frames, f"Point cloud: {path}"
