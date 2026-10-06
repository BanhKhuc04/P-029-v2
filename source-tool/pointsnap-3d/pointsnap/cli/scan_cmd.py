"""Lệnh `pointsnap scan`: quét một job trên CVAT, xuất báo cáo HTML/CSV, tùy chọn gắn cờ lỗi (A5)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from pointsnap.adapters.cvat.client import CvatClient, CvatError
from pointsnap.adapters.cvat.reader import load_job
from pointsnap.adapters.cvat.writer import flag_job_errors, save_snapshot
from pointsnap.core.config import Config
from pointsnap.core.model import Severity
from pointsnap.core.scanner import scan_cuboids
from pointsnap.report.csv_rep import generate_csv_report
from pointsnap.report.html import generate_html_report


def run(args: argparse.Namespace, config: Config) -> int:
    try:
        client = CvatClient(config.cvat.url, config.cvat.token)
    except CvatError as exc:
        print(f"Lỗi kết nối CVAT: {exc}", file=sys.stderr)
        return 3

    print(f"Đang tải dữ liệu job #{args.job} từ CVAT ({client.url})...")
    try:
        job = load_job(client, args.job)
    except Exception as exc:
        print(f"Lỗi khi đọc job #{args.job}: {exc}", file=sys.stderr)
        return 3

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    # 1. Tự động lưu bản chụp JSON
    snap_path = out_dir / f"snapshot_job_{args.job}.json"
    save_snapshot(job, snap_path)
    print(f"-> Đã lưu bản chụp nhãn: {snap_path}")

    # 2. Quét kiểm tra chất lượng nhãn
    print(f"Đang quét {len(job.cuboids)} box của job #{args.job}...")
    findings = scan_cuboids(job, config)

    # 3. Xuất báo cáo HTML và CSV
    html_path = out_dir / f"report_job_{args.job}.html"
    csv_path = out_dir / f"report_job_{args.job}.csv"
    generate_html_report(job, findings, html_path)
    generate_csv_report(job, findings, csv_path)
    print(f"-> Báo cáo HTML: {html_path}")
    print(f"-> Báo cáo CSV:  {csv_path}")

    num_errors = sum(1 for f in findings if f.severity == Severity.ERROR)
    num_warnings = sum(1 for f in findings if f.severity == Severity.WARNING)
    num_infos = sum(1 for f in findings if f.severity == Severity.INFO)

    # 4. Gắn cờ lỗi lên CVAT nếu có flag --flag
    if args.flag:
        print("Đang gắn cờ thuộc tính 'pointsnap_error' lên các box bị lỗi trên CVAT...")
        try:
            flagged = flag_job_errors(client, job, findings)
            print(f"-> Đã gắn cờ lỗi lên {flagged} box trên CVAT.")
        except Exception as exc:
            print(f"Lỗi khi gắn cờ lỗi lên CVAT: {exc}", file=sys.stderr)
            return 3

    print("\n--- TỔNG KẾT QUÉT ---")
    print(f"Tổng số box:      {len(job.cuboids)}")
    print(f"Lỗi (cần sửa):    {num_errors}")
    print(f"Cảnh báo:         {num_warnings}")
    print(f"Thông tin:        {num_infos}")
    print("----------------------")

    return 0
