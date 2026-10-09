"""Xem nhanh point cloud quanh box của một finding, không cần mở CVAT (A14)."""

from __future__ import annotations

import json
import math
import os
import threading
from pathlib import Path
from typing import Any

import numpy as np

from pointsnap.adapters.cvat.reader import ManifestFrames, find_manifest
from pointsnap.cli.common import export_dirs
from pointsnap.core.model import Cuboid
from pointsnap.core.serialize import load_cuboids


class PreviewError(ValueError):
    """Không dựng được bản xem nhanh (thiếu snapshot, manifest, box hoặc point cloud)."""


def points_around_box(
    points: np.ndarray, cuboid: Cuboid, margin_m: float = 2.0, max_points: int = 4000
) -> np.ndarray:
    """Điểm quanh box, đổi sang hệ của box: x dọc chiều dài, y theo chiều rộng, z lên; gốc là tâm box.

    Giữ điểm trong footprint nới thêm `margin_m` và cao từ đáy − 1,5 m tới đỉnh + 1 m; quá `max_points` thì lấy đều.
    """
    pts = np.asarray(points, dtype=np.float64)[:, :3] - np.asarray(cuboid.center, dtype=np.float64)
    c, s = math.cos(-cuboid.yaw), math.sin(-cuboid.yaw)
    local = np.column_stack((c * pts[:, 0] - s * pts[:, 1], s * pts[:, 0] + c * pts[:, 1], pts[:, 2]))
    length, width, height = cuboid.dims
    keep = (
        (np.abs(local[:, 0]) <= length / 2 + margin_m)
        & (np.abs(local[:, 1]) <= width / 2 + margin_m)
        & (local[:, 2] >= -height / 2 - 1.5)
        & (local[:, 2] <= height / 2 + 1.0)
    )
    local = local[keep]
    if len(local) > max_points:
        local = local[np.linspace(0, len(local) - 1, max_points).astype(int)]
    return local


def _find_box(cuboids: list[Cuboid], finding: dict[str, Any]) -> Cuboid | None:
    """Box của finding: cùng frame và track (hoặc id shape lẻ); không có thì keyframe gần nhất của track."""
    frame, track_id, source_id = finding.get("frame"), finding.get("track_id"), finding.get("source_id")
    boxes = [c for c in cuboids if not c.outside]
    if track_id is None:
        return next((c for c in boxes if c.source_id == source_id and c.frame == frame), None)
    same_track = [c for c in boxes if c.track_id == track_id]
    if not same_track:
        return None
    return min(same_track, key=lambda c: abs(c.frame - frame))


def finding_preview(run_dir: Path, project: dict[str, Any], index: int) -> dict[str, Any]:
    findings_path, snapshot_path = run_dir / "findings.json", run_dir / "snapshot.json"
    if not findings_path.is_file() or not snapshot_path.is_file():
        raise PreviewError("Lần quét này thiếu findings.json hoặc snapshot.json")
    findings = json.loads(findings_path.read_text(encoding="utf-8"))
    if not 0 <= index < len(findings):
        raise PreviewError(f"Không có mục số {index}")
    finding = findings[index]

    cuboids, meta = load_cuboids(snapshot_path)
    box = _find_box(cuboids, finding)
    if box is None:
        raise PreviewError("Không tìm thấy box của mục này trong bản chụp nhãn")

    manifest = find_manifest(meta.get("task_id"), export_dirs(project.get("export_dirs") or None))
    if manifest is None:
        raise PreviewError("Không tìm thấy manifest.json của task: kiểm tra thư mục bản xuất ở tab Kết nối CVAT")
    dataroot = project.get("nuscenes_root") or os.environ.get("NUSCENES_ROOT") or None
    try:
        points = ManifestFrames(manifest, dataroot=dataroot).frame_data(box.frame).points
    except (OSError, KeyError, ValueError) as exc:
        raise PreviewError(f"Không đọc được point cloud frame {box.frame}: {exc}") from exc

    local = points_around_box(points, box)
    return {
        "frame": box.frame,
        "exact_frame": box.frame == finding.get("frame"),
        "label": box.label,
        "distance_m": round(math.hypot(box.center[0], box.center[1]), 1),
        "track_id": box.track_id,
        "box": {"length": box.dims[0], "width": box.dims[1], "height": box.dims[2]},
        "points": np.round(local, 2).tolist(),
    }


def load_reviews(run_dir: Path) -> dict[str, str]:
    path = run_dir / "reviews.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}


_REVIEWS_LOCK = threading.Lock()


def save_review(run_dir: Path, index: int, verdict: str | None) -> dict[str, str]:
    """Ghi kết luận xem tay của một mục (`ok` = đúng là lỗi, `fp` = báo nhầm, `None` = bỏ).

    Khóa đọc-sửa-ghi để hai yêu cầu cùng lúc (bấm phím nhanh, nhiều tab, extension) không ghi đè nhau;
    ghi ra file tạm rồi thay thế để file không bao giờ bị ghi dở.
    """
    with _REVIEWS_LOCK:
        reviews = load_reviews(run_dir)
        if verdict is None:
            reviews.pop(str(index), None)
        else:
            reviews[str(index)] = verdict
        tmp = run_dir / "reviews.json.tmp"
        tmp.write_text(json.dumps(reviews, indent=2), encoding="utf-8")
        os.replace(tmp, run_dir / "reviews.json")
        return reviews
