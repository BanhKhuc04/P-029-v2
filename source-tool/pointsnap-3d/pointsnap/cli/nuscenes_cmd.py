"""Lệnh `pointsnap nuscenes ...`: liệt kê cảnh, chuyển một cảnh sang CVAT (việc A2)."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from pointsnap.adapters.cvat.client import CvatClient, CvatError
from pointsnap.adapters.cvat.reader import JobData
from pointsnap.adapters.nuscenes import NuScenesReader
from pointsnap.cli.scan_cmd import print_summary
from pointsnap.core.config import Config
from pointsnap.core.model import add_outside_markers
from pointsnap.core.scanner import actionable, scan_cuboids
from pointsnap.core.synthetic import inject_dataset, save_injection_log
from pointsnap.datasets.nuscenes.to_cvat import export_scene, upload_scene
from pointsnap.eval.evaluate import is_applicable, matches, no_evidence_frames
from pointsnap.report.csv_rep import generate_csv_report
from pointsnap.report.html import generate_html_report


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

    scan = actions.add_parser("scan", help="quét thẳng nhãn chuẩn của một cảnh, không cần CVAT (HTML/CSV)")
    scan.add_argument("--scene", required=True, help="tên cảnh, ví dụ scene-0061")
    scan.add_argument("--out", type=Path, default=Path("out"), help="thư mục ghi báo cáo (mặc định: out)")
    scan.add_argument("--inject", action="store_true", help="chèn lỗi giả vào ~10%% số track trước khi quét")
    scan.add_argument("--seed", type=int, default=0, help="seed của bộ chèn lỗi (mặc định: 0)")
    scan.add_argument("--rate", type=float, default=0.10, help="tỉ lệ track được chèn lỗi (mặc định: 0.10)")


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

        if args.nuscenes_command == "scan":
            return _scan(reader, args, config)

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


def _scan(reader: NuScenesReader, args: argparse.Namespace, config: Config) -> int:
    frames = reader.frames(args.scene)
    clean_boxes = boxes = add_outside_markers(reader.annotations(args.scene), frames.num_frames)
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    name = args.scene
    errors = []
    if args.inject:
        boxes, errors = inject_dataset(boxes, seed=args.seed, error_rate=args.rate)
        name = f"{args.scene}_injected"
        log_path = out_dir / f"injected_{args.scene}.json"
        save_injection_log(log_path, errors, meta={"scene": args.scene, "seed": args.seed})
        print(f"-> Đã chèn {len(errors)} lỗi giả, log: {log_path}")

    print(f"Đang quét {sum(1 for b in boxes if not b.outside)} box của {args.scene}...")
    findings = scan_cuboids(boxes, config, frames)
    job = JobData(url="", task_id=0, job_id=0, start_frame=0, stop_frame=frames.num_frames - 1, labels={},
                  cuboids=boxes)
    html_path, csv_path = out_dir / f"report_{name}.html", out_dir / f"report_{name}.csv"
    generate_html_report(job, findings, html_path, source_name=f"nuScenes {name}")
    generate_csv_report(job, findings, csv_path)
    print(f"-> Báo cáo HTML: {html_path}")
    print(f"-> Báo cáo CSV:  {csv_path}")
    print_summary(sum(1 for b in boxes if not b.outside), findings)

    if errors:
        found = actionable(findings)
        no_evidence = no_evidence_frames(findings)
        labels = {b.track_id: b.label for b in clean_boxes}
        print("\n--- LỖI CHÈN GIẢ ---")
        for error in errors:
            label = labels[error.track_id]
            hit = any(matches(error, f) for f in found)
            why = ""
            if not hit and not is_applicable(error, label, clean_boxes, config, frames):
                why = (" (ngoài phạm vi luật: đối tượng đứng yên)" if error.error_type == "track_interpolation"
                       else f" (ngoài phạm vi luật: class {label})")
            elif not hit and error.error_type == "floating" and error.frame in no_evidence.get(error.track_id, ()):
                why = " (thiếu điểm mặt đất quanh box)"
            print(f"  {'[bắt được]' if hit else '[bỏ sót]  '} {label} track {error.track_id}, frame {error.frame}: "
                  f"{error.description}{why}")
    return 0