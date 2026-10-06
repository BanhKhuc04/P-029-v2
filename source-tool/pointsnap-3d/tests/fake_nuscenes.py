"""Bộ nuScenes giả, nhỏ, đã biết đáp án — dùng để test reader mà không cần tải dữ liệu thật.

Một cảnh 3 keyframe. LiDAR gắn trên xe ở (1, 0, 2), quay 90° quanh z so với xe.
Xe thu: frame 0 tại gốc, frame 1 tại (5, 0, 0), frame 2 tại (10, 0, 0) và đã quay 90°.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np


def yaw_quaternion(yaw: float) -> list[float]:
    return [math.cos(yaw / 2), 0.0, 0.0, math.sin(yaw / 2)]


FRAME0_POINTS = np.array(
    [[1.0, 2.0, 3.0, 10.0, 0.0], [4.0, 5.0, 6.0, 20.0, 1.0], [-1.0, 0.0, -1.5, 30.0, 2.0], [0.5, 0.5, 0.5, 40.0, 31.0]],
    dtype=np.float32,
)


def build(root: Path) -> Path:
    tables: dict[str, list[dict]] = {}
    tables["sensor"] = [
        {"token": "sensor_lidar", "channel": "LIDAR_TOP", "modality": "lidar"},
        {"token": "sensor_cam", "channel": "CAM_FRONT", "modality": "camera"},
    ]
    tables["calibrated_sensor"] = [
        {"token": "cs_lidar", "sensor_token": "sensor_lidar", "translation": [1.0, 0.0, 2.0],
         "rotation": yaw_quaternion(math.pi / 2), "camera_intrinsic": []},
        {"token": "cs_cam", "sensor_token": "sensor_cam", "translation": [1.5, 0.0, 1.5],
         "rotation": yaw_quaternion(0.0), "camera_intrinsic": []},
    ]
    tables["ego_pose"] = [
        {"token": "ego0", "translation": [0.0, 0.0, 0.0], "rotation": yaw_quaternion(0.0), "timestamp": 1_000_000},
        {"token": "ego1", "translation": [5.0, 0.0, 0.0], "rotation": yaw_quaternion(0.0), "timestamp": 1_500_000},
        {"token": "ego2", "translation": [10.0, 0.0, 0.0], "rotation": yaw_quaternion(math.pi / 2), "timestamp": 2_000_000},
    ]
    tables["scene"] = [
        {"token": "scene_a", "name": "scene-0001", "description": "cảnh giả", "nbr_samples": 3,
         "first_sample_token": "smp0", "last_sample_token": "smp2", "log_token": "log0"},
    ]
    # Cố ý xáo thứ tự: reader phải đi theo chuỗi `next`.
    tables["sample"] = [
        {"token": "smp2", "timestamp": 2_000_000, "prev": "smp1", "next": "", "scene_token": "scene_a"},
        {"token": "smp0", "timestamp": 1_000_000, "prev": "", "next": "smp1", "scene_token": "scene_a"},
        {"token": "smp1", "timestamp": 1_500_000, "prev": "smp0", "next": "smp2", "scene_token": "scene_a"},
    ]

    def lidar(token, sample, ego, ts, filename, key=True):
        return {"token": token, "sample_token": sample, "ego_pose_token": ego, "calibrated_sensor_token": "cs_lidar",
                "timestamp": ts, "fileformat": "pcd", "is_key_frame": key, "height": 0, "width": 0,
                "filename": filename, "prev": "", "next": ""}

    tables["sample_data"] = [
        lidar("sd0", "smp0", "ego0", 1_000_000, "samples/LIDAR_TOP/f0.pcd.bin"),
        lidar("sd0_sweep", "smp0", "ego0", 1_050_000, "sweeps/LIDAR_TOP/f0b.pcd.bin", key=False),
        lidar("sd1", "smp1", "ego1", 1_500_000, "samples/LIDAR_TOP/f1.pcd.bin"),
        lidar("sd2", "smp2", "ego2", 2_000_000, "samples/LIDAR_TOP/f2.pcd.bin"),
        {"token": "sd0_cam", "sample_token": "smp0", "ego_pose_token": "ego0", "calibrated_sensor_token": "cs_cam",
         "timestamp": 1_000_000, "fileformat": "jpg", "is_key_frame": True, "height": 900, "width": 1600,
         "filename": "samples/CAM_FRONT/f0.jpg", "prev": "", "next": ""},
    ]
    tables["category"] = [
        {"token": "cat_car", "name": "vehicle.car", "description": ""},
        {"token": "cat_ped", "name": "human.pedestrian.adult", "description": ""},
        {"token": "cat_dog", "name": "animal", "description": ""},
    ]
    tables["instance"] = [
        {"token": "inst_car", "category_token": "cat_car", "nbr_annotations": 3},
        {"token": "inst_ped", "category_token": "cat_ped", "nbr_annotations": 2},
        {"token": "inst_dog", "category_token": "cat_dog", "nbr_annotations": 1},
    ]

    def ann(token, sample, instance, translation, size_wlh, yaw, pts):
        return {"token": token, "sample_token": sample, "instance_token": instance, "translation": translation,
                "size": size_wlh, "rotation": yaw_quaternion(yaw), "num_lidar_pts": pts, "num_radar_pts": 0,
                "visibility_token": "4", "attribute_tokens": [], "prev": "", "next": ""}

    tables["sample_annotation"] = [
        ann("a_car0", "smp0", "inst_car", [11.0, 0.0, 0.8], [2.0, 4.5, 1.6], 0.0, 120),
        ann("a_car1", "smp1", "inst_car", [11.0, 2.0, 0.8], [2.0, 4.5, 1.6], math.pi / 4, 100),
        ann("a_car2", "smp2", "inst_car", [11.0, 5.0, 0.8], [2.0, 4.5, 1.6], math.pi / 2, 80),
        ann("a_ped0", "smp0", "inst_ped", [5.0, 3.0, 0.9], [0.6, 0.7, 1.8], 0.0, 15),
        ann("a_ped1", "smp1", "inst_ped", [5.0, 3.5, 0.9], [0.6, 0.7, 1.8], 0.0, 0),  # không có điểm nào
        ann("a_dog0", "smp0", "inst_dog", [3.0, -2.0, 0.3], [0.3, 0.8, 0.5], 0.0, 5),  # category bị bỏ qua
    ]

    table_dir = root / "v1.0-mini"
    table_dir.mkdir(parents=True)
    for name, records in tables.items():
        (table_dir / f"{name}.json").write_text(json.dumps(records), encoding="utf-8")

    lidar_dir = root / "samples" / "LIDAR_TOP"
    lidar_dir.mkdir(parents=True)
    FRAME0_POINTS.tofile(lidar_dir / "f0.pcd.bin")
    for name in ("f1", "f2"):
        np.zeros((2, 5), dtype=np.float32).tofile(lidar_dir / f"{name}.pcd.bin")
    return root
