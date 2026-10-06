"""Lệnh `pointsnap nuscenes ...`: liệt kê cảnh, chuyển một cảnh sang CVAT (việc A2)."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from pointsnap.adapters.cvat.client import CvatClient, CvatError
from pointsnap.adapters.nuscenes import NuScenesReader
from pointsnap.core.config import Config
from pointsnap.datasets.nuscenes.to_cvat import export_scene, upload_scene


def add_parser(sub: argparse._SubParsersAction) -> None:
    nuscenes = sub.add_parser("nuscenes", help="làm việc với dữ liệu nuScenes (liệt kê cảnh, chuyển sang CVAT)")
    nuscenes.add_argument(
        "--dataroot", type=Path, default=os.environ.get("NUSCENES_ROOT"),
        help="thư mục nuScenes chứa samples/ và v1.0-mini/ (mặc định: biến môi trường NUSCENES_ROOT)",
    )
    nuscenes.add_argument("--version", default="v1.0-mini", help="phiên bản bảng nuScenes (mặc định: v1.0-mini)")
    actions = nuscenes.add_subparsers(dest="nuscenes_command", required=True, metavar="VIỆC")

    actions.add_parser("scenes", help="liệt kê các cảnh")

    to_cvat = actions.add_parser("to-cvat", help="xuất một cảnh ra .pcd + nhãn chuẩn; thêm --upload để tạo task CVAT")
    to_cvat.add_argument("--scene", required=True, help="tên cảnh, ví dụ scene-0061")
    to_cvat.add_argument("--out", type=Path, default=Path("data/cvat"), help="thư mục ghi bản xuất (mặc định: data/cvat)")
    to_cvat.add_argument("--upload", action="store_true", help="tạo task 3D trên CVAT và nạp nhãn chuẩn")
    to_cvat.add_argument("--task-name", help="tên task trên CVAT (mặc định: PointSnap <cảnh>)")


def run(args: argparse.Namespace, config: Config) -> int:
    if args.dataroot is None:
        print("Thiếu --dataroot (hoặc biến môi trường NUSCENES_ROOT).", file=sys.stderr)
        return 3
    try:
        reader = NuScenesReader(args.dataroot, version=args.version)
        if args.nuscenes_command == "scenes":
            for scene in reader.scenes():
                print(f"{scene.name}\t{scene.num_frames} frame\t{scene.description}")
            return 0

        export = export_scene(reader, args.scene, args.out)
        print(f"Đã xuất {export.num_frames} frame, {export.num_boxes} box nhãn chuẩn → {export.directory}")
        if not args.upload:
            print("Chưa tải lên CVAT. Thêm --upload để tạo task.")
            return 0

        client = CvatClient(
            config.cvat.url, config.cvat.token, auth_scheme=os.environ.get("CVAT_AUTH_SCHEME", "Bearer")
        )
        info = upload_scene(client, export, args.task_name or f"PointSnap {args.scene}", config.cvat.flag_attribute)
        jobs = ", ".join(str(j) for j in info["job_ids"])
        print(f"Đã tạo task {info['task_id']} (job {jobs}), nạp {info['num_boxes']} box: "
              f"{client.url}/tasks/{info['task_id']}")
        return 0
    except (FileNotFoundError, KeyError, ValueError, CvatError) as exc:
        message = exc.args[0] if isinstance(exc, KeyError) and exc.args else exc
        print(f"Lỗi: {message}", file=sys.stderr)
        return 3
