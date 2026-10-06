"""Chuyển một cảnh nuScenes sang CVAT (việc A2).

Hai bước, tách riêng để bước 1 chạy được khi chưa có CVAT:
1. `export_scene`: ghi `.pcd` cho từng keyframe, `manifest.json` (frame ↔ file ↔ `sample_token` ↔ pose),
   `ground_truth.json` (nhãn chuẩn) và file zip để tải lên CVAT.
2. `upload_scene`: tạo task 3D, tải zip, chờ CVAT xử lý, nạp nhãn chuẩn dạng track.
"""

from __future__ import annotations

import json
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping

from pointsnap.adapters.cvat.client import CvatClient
from pointsnap.adapters.cvat.shapes import cuboid_to_points
from pointsnap.adapters.nuscenes.reader import NuScenesReader
from pointsnap.core.model import Cuboid, group_by_track
from pointsnap.core.serialize import load_cuboids, save_cuboids
from pointsnap.datasets.pcd import write_pcd

TASK_CLASSES = (
    "car", "truck", "bus", "trailer", "construction_vehicle",
    "pedestrian", "motorcycle", "bicycle", "traffic_cone", "barrier",
)
REVIEWED_ATTRIBUTE = "reviewed"


def label_specs(flag_attribute: str) -> list[dict[str, Any]]:
    """10 label của task, mỗi label có thuộc tính cờ lỗi (văn bản) và `reviewed` (checkbox).

    Cả hai là thuộc tính `mutable`: giá trị có thể khác nhau ở từng frame của một track.
    """
    attributes = [
        {"name": flag_attribute, "mutable": True, "input_type": "text", "default_value": "", "values": [""]},
        {"name": REVIEWED_ATTRIBUTE, "mutable": True, "input_type": "checkbox", "default_value": "false",
         "values": ["false"]},
    ]
    return [{"name": name, "type": "cuboid", "attributes": attributes} for name in TASK_CLASSES]


@dataclass(frozen=True)
class SceneExport:
    scene: str
    directory: Path
    archive: Path
    manifest: Path
    ground_truth: Path
    num_frames: int
    num_boxes: int


def export_scene(reader: NuScenesReader, scene: str, out_dir: str | Path) -> SceneExport:
    """Ghi dữ liệu của cảnh vào `out_dir/<scene>/`."""
    directory = Path(out_dir) / scene
    pointcloud_dir = directory / "pointcloud"
    pointcloud_dir.mkdir(parents=True, exist_ok=True)

    refs = reader.samples(scene)
    frames = []
    for ref in refs:
        filename = f"{ref.frame:06d}.pcd"  # CVAT sắp frame theo tên file
        write_pcd(pointcloud_dir / filename, reader.load_points(ref))
        frames.append({
            "frame": ref.frame,
            "file": filename,
            "sample_token": ref.sample_token,
            "timestamp": ref.timestamp,
            "sensor_to_world": ref.sensor_to_world.tolist(),
        })

    manifest = directory / "manifest.json"
    manifest.write_text(json.dumps({
        "scene": scene,
        "dataroot": str(reader.dataroot),
        "version": reader.version,
        "num_frames": len(refs),
        "frames": frames,
    }, ensure_ascii=False, indent=1), encoding="utf-8")

    cuboids = reader.annotations(scene)
    ground_truth = directory / "ground_truth.json"
    save_cuboids(ground_truth, cuboids, meta={"scene": scene, "source": "nuscenes", "num_frames": len(refs)})

    archive = directory / f"{scene}.zip"
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_STORED) as zf:
        for frame in frames:
            zf.write(pointcloud_dir / frame["file"], arcname=frame["file"])

    return SceneExport(scene, directory, archive, manifest, ground_truth, len(refs), len(cuboids))


def _shape(cuboid: Cuboid, outside: bool) -> dict[str, Any]:
    return {
        "type": "cuboid",
        "frame": cuboid.frame,
        "points": cuboid_to_points(cuboid),
        "outside": outside,
        "occluded": False,
        "z_order": 0,
        "rotation": 0.0,
        "attributes": [],
    }


def build_tracks(cuboids: Iterable[Cuboid], num_frames: int, label_ids: Mapping[str, int]) -> list[dict[str, Any]]:
    """Gom box thành track của CVAT.

    Trong CVAT, một track kéo dài tới frame cuối của job cho tới khi gặp keyframe `outside`. Vì vậy:
    - sau frame cuối của track (nếu chưa phải frame cuối cảnh) thêm một keyframe `outside`;
    - khi track khuyết frame ở giữa thêm `outside` ngay sau frame có mặt cuối cùng, để CVAT không nội suy
      qua đoạn đối tượng vắng mặt.
    """
    tracks = []
    for track_id, boxes in group_by_track(cuboids).items():
        labels = {b.label for b in boxes}
        if len(labels) != 1:
            raise ValueError(f"Track {track_id} có nhiều class: {sorted(labels)}")
        shapes = []
        for index, box in enumerate(boxes):
            shapes.append(_shape(box, outside=False))
            next_frame = boxes[index + 1].frame if index + 1 < len(boxes) else num_frames
            if box.frame + 1 < next_frame:
                shapes.append(_shape(box.replace(frame=box.frame + 1), outside=True))
        tracks.append({
            "frame": boxes[0].frame,
            "label_id": label_ids[boxes[0].label],
            "group": 0,
            "source": "manual",
            "attributes": [],
            "shapes": shapes,
        })
    return tracks


def build_annotations(cuboids: list[Cuboid], num_frames: int, label_ids: Mapping[str, int]) -> dict[str, Any]:
    """Dữ liệu cho `PUT /api/tasks/<id>/annotations`: box có track thành track, box lẻ thành shape."""
    shapes = [{**_shape(c, outside=False), "label_id": label_ids[c.label], "group": 0, "source": "manual"}
              for c in cuboids if c.track_id is None]
    shapes = [{k: v for k, v in s.items() if k != "outside"} for s in shapes]
    return {"version": 0, "tags": [], "shapes": shapes, "tracks": build_tracks(cuboids, num_frames, label_ids)}


def upload_scene(
    client: CvatClient,
    export: SceneExport,
    task_name: str,
    flag_attribute: str,
    timeout: float = 900.0,
) -> dict[str, Any]:
    """Tạo task 3D trên CVAT từ bản xuất, nạp nhãn chuẩn. Ghi `cvat_task.json` cạnh bản xuất."""
    task = client.create_task(task_name, label_specs(flag_attribute))
    rq_id = client.upload_task_data(task["id"], export.archive)
    client.wait_request(rq_id, timeout=timeout)

    label_ids = {label["name"]: label["id"] for label in client.task_labels(task["id"])}
    cuboids, _ = load_cuboids(export.ground_truth)
    client.put_task_annotations(task["id"], build_annotations(cuboids, export.num_frames, label_ids))

    info = {
        "url": client.url,
        "task_id": task["id"],
        "job_ids": [job["id"] for job in client.task_jobs(task["id"])],
        "scene": export.scene,
        "num_frames": export.num_frames,
        "num_boxes": len(cuboids),
    }
    (export.directory / "cvat_task.json").write_text(json.dumps(info, indent=1), encoding="utf-8")
    return info
