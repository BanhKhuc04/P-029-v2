"""Đọc nhãn của một job CVAT ra `Cuboid` (việc A3).

Đã xác minh trên CVAT 2.77.1 chạy thật (CONVENTIONS.md mục 2):
- `GET /api/jobs/<id>/annotations` trả `shapes` (box lẻ) và `tracks`; mỗi track chỉ chứa các **keyframe**
  nhập tay, mỗi keyframe có `id`, `frame`, `outside`, `points`, `attributes`.
- `GET /api/tasks/<id>/data/meta` trả danh sách frame theo đúng thứ tự (`000000.pcd`, …), dùng để khớp
  frame CVAT với `manifest.json` của bản xuất.

Point cloud không đọc qua API: lấy từ thư mục nuScenes trên máy theo `manifest.json` (đã chốt trong kế hoạch
4 ngày; đọc qua API để dành cho hướng phát triển).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Mapping

import numpy as np

from pointsnap.adapters.cvat.client import CvatClient
from pointsnap.adapters.cvat.shapes import PITCH_ATTR, ROLL_ATTR, points_to_geometry
from pointsnap.adapters.nuscenes.reader import NuScenesReader, SampleRef
from pointsnap.core.model import Cuboid, FrameData



@dataclass(frozen=True)
class LabelInfo:
    id: int
    name: str
    attribute_names: Mapping[int, str]
    """`spec_id` → tên thuộc tính."""

    @property
    def attribute_ids(self) -> dict[str, int]:
        return {name: spec_id for spec_id, name in self.attribute_names.items()}


def labels_from_api(labels: Iterable[Mapping[str, Any]]) -> dict[int, LabelInfo]:
    return {
        label["id"]: LabelInfo(
            id=label["id"],
            name=label["name"],
            attribute_names={a["id"]: a["name"] for a in label.get("attributes", [])},
        )
        for label in labels
    }


def _attribute_values(values: Iterable[Mapping[str, Any]], label: LabelInfo) -> dict[str, str]:
    return {label.attribute_names.get(v["spec_id"], f"spec_{v['spec_id']}"): v["value"] for v in values}


def _to_cuboid(shape: Mapping[str, Any], label: LabelInfo, track_id: int | None, base_attrs: Mapping[str, str]) -> Cuboid:
    geometry = points_to_geometry(shape["points"])
    attrs: dict[str, Any] = {**base_attrs, **_attribute_values(shape.get("attributes", []), label)}
    attrs.update({ROLL_ATTR: geometry["roll"], PITCH_ATTR: geometry["pitch"], "occluded": bool(shape.get("occluded"))})
    try:
        return Cuboid(
            center=geometry["center"],
            dims=geometry["dims"],
            yaw=geometry["yaw"],
            label=label.name,
            frame=shape["frame"],
            track_id=track_id,
            source_id=shape["id"],
            keyframe=True,
            outside=bool(shape.get("outside", False)),
            attrs=attrs,
        )
    except ValueError as exc:
        raise ValueError(f"Box id {shape.get('id')} ở frame {shape.get('frame')} không hợp lệ: {exc}") from None


def annotations_to_cuboids(data: Mapping[str, Any], labels: Mapping[int, LabelInfo]) -> list[Cuboid]:
    """Đổi dữ liệu annotation của CVAT ra `Cuboid`.

    - Box lẻ (`shapes`): `track_id=None`.
    - Track: mỗi keyframe thành một `Cuboid` có `track_id` = id track, `source_id` = id keyframe; keyframe
      `outside` cũng được giữ (với `outside=True`) để biết track dừng ở đâu.
    - Thuộc tính: thuộc tính của track trộn với thuộc tính của keyframe, theo tên.
    Shape không phải `cuboid` bị bỏ qua.
    """
    cuboids: list[Cuboid] = []
    for shape in data.get("shapes", []):
        if shape.get("type") == "cuboid":
            cuboids.append(_to_cuboid(shape, labels[shape["label_id"]], None, {}))
    for track in data.get("tracks", []):
        label = labels[track["label_id"]]
        track_attrs = _attribute_values(track.get("attributes", []), label)
        for shape in track.get("shapes", []):
            if shape.get("type") == "cuboid":
                cuboids.append(_to_cuboid(shape, label, track["id"], track_attrs))
    return sorted(cuboids, key=lambda c: (c.frame, c.track_id if c.track_id is not None else -1, c.source_id or 0))


def frame_url(
    base_url: str,
    task_id: int,
    job_id: int,
    frame: int,
    track_id: int | None = None,
    shape_id: int | None = None,
) -> str:
    """Link mở thẳng một frame và đối tượng trong giao diện CVAT.

    - Có track_id: thêm &type=track&serverID=<track_id> (tương đương 'Copy object URL' trên CVAT).
    - Không có track_id nhưng có shape_id: thêm &type=shape&serverID=<shape_id>.
    - Không có cả hai: link chỉ mở frame.
    """
    url = f"{base_url.rstrip('/')}/tasks/{task_id}/jobs/{job_id}?frame={frame}"
    if track_id is not None:
        return f"{url}&type=track&serverID={track_id}"
    if shape_id is not None:
        return f"{url}&type=shape&serverID={shape_id}"
    return url


class ManifestFrames:
    """Point cloud và pose của từng frame CVAT, đọc từ thư mục nuScenes theo `manifest.json` của bản xuất."""

    def __init__(self, manifest_path: str | Path, dataroot: str | Path | None = None) -> None:
        self.manifest = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
        self.reader = NuScenesReader(dataroot or self.manifest["dataroot"], version=self.manifest["version"])
        by_token = {ref.sample_token: ref for ref in self.reader.samples(self.manifest["scene"])}
        self._refs: dict[int, SampleRef] = {f["frame"]: by_token[f["sample_token"]] for f in self.manifest["frames"]}

    @property
    def file_names(self) -> list[str]:
        return [f["file"] for f in sorted(self.manifest["frames"], key=lambda f: f["frame"])]

    def check_matches(self, cvat_frame_names: list[str]) -> None:
        """Báo lỗi nếu thứ tự frame trên CVAT không khớp bản xuất (task tạo từ dữ liệu khác)."""
        names = [Path(n).name for n in cvat_frame_names]
        if names != self.file_names:
            raise ValueError(
                f"Frame trên CVAT không khớp manifest của cảnh {self.manifest['scene']}: "
                f"{names[:3]}… so với {self.file_names[:3]}…"
            )

    def frame_data(self, frame: int, with_points: bool = True) -> FrameData:
        ref = self._refs[frame]
        data = self.reader.frame_data(ref, with_points=with_points)
        transform = self.manifest.get("transform")
        if transform is not None:
            mat = np.asarray(transform, dtype=np.float64)
            points = data.points.copy()
            if len(points) > 0:
                points[:, :3] = points[:, :3] @ mat.T
            rot4 = np.eye(4, dtype=np.float64)
            rot4[:3, :3] = mat
            sensor_to_world = data.sensor_to_world @ rot4.T
            return FrameData(frame, points, sensor_to_world, data.timestamp, data.source_ref)
        return FrameData(frame, data.points, data.sensor_to_world, data.timestamp, data.source_ref)

    def ground_sweeps(self, frame: int, sweeps: int) -> list[tuple[float, np.ndarray]]:
        """`sweeps` lượt quét LiDAR trung gian trước keyframe, cùng hệ với point cloud trên CVAT: [(thời điểm, điểm)]."""
        chunks = self.reader.load_sweeps(self._refs[frame], sweeps)
        transform = self.manifest.get("transform")
        if transform is None:
            return chunks
        mat = np.asarray(transform, dtype=np.float64)
        return [(t, points @ mat.T) for t, points in chunks]



def find_manifest(task_id: int, search_dirs: Iterable[str | Path]) -> Path | None:
    """Tìm `manifest.json` của bản xuất đã tạo task `task_id` (`cvat_task.json` nằm cạnh, do `to-cvat --upload` ghi).

    Mỗi thư mục trong `search_dirs` là nơi chứa các bản xuất (`<dir>/<scene>/cvat_task.json`) hoặc chính một bản xuất.
    """
    for directory in search_dirs:
        directory = Path(directory)
        if not directory.is_dir():
            continue
        for info_path in [directory / "cvat_task.json", *directory.glob("*/cvat_task.json")]:
            try:
                info = json.loads(info_path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            manifest = info_path.parent / "manifest.json"
            if info.get("task_id") == task_id and manifest.is_file():
                return manifest
    return None


@dataclass
class JobData:
    url: str
    task_id: int
    job_id: int
    start_frame: int
    stop_frame: int
    labels: dict[int, LabelInfo]
    cuboids: list[Cuboid]
    frame_names: list[str] = field(default_factory=list)

    def frame_url(
        self,
        frame: int,
        track_id: int | None = None,
        shape_id: int | None = None,
    ) -> str:
        return frame_url(self.url, self.task_id, self.job_id, frame, track_id=track_id, shape_id=shape_id)


def load_job(client: CvatClient, job_id: int) -> JobData:
    """Đọc thông tin job, label của task, toàn bộ annotation của job và danh sách frame."""
    job = client.get_job(job_id)
    task_id = job["task_id"]
    labels = labels_from_api(client.task_labels(task_id))
    data = client.get_job_annotations(job_id)
    meta = client.get_task_data_meta(task_id)
    return JobData(
        url=client.url,
        task_id=task_id,
        job_id=job_id,
        start_frame=job["start_frame"],
        stop_frame=job["stop_frame"],
        labels=labels,
        cuboids=annotations_to_cuboids(data, labels),
        frame_names=[f["name"] for f in meta.get("frames", [])],
    )
