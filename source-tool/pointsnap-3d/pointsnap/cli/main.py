"""Dòng lệnh `pointsnap`.

Mã thoát: 0 = thành công / ĐẠT, 1 = KHÔNG ĐẠT, 2 = sai cú pháp lệnh, 3 = lỗi khi chạy hoặc lệnh chưa có.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml

from pointsnap import __version__
from pointsnap.core.config import ConfigError, load_config

EXIT_OK = 0
EXIT_GATE_FAILED = 1
EXIT_RUNTIME_ERROR = 3

# Lệnh đã khai báo nhưng chưa viết, kèm mã việc trong TASKS.md.
_NOT_IMPLEMENTED = {"scan": "A5", "gate": "A5", "diff": "A8"}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pointsnap",
        description="Phát hiện và cảnh báo sớm lỗi nhãn 3D cuboid trên CVAT.",
        epilog="Mã thoát: 0 = thành công / ĐẠT, 1 = KHÔNG ĐẠT, 2 = sai cú pháp lệnh, 3 = lỗi khi chạy.",
    )
    parser.add_argument("--version", action="version", version=f"pointsnap {__version__}")
    parser.add_argument("--config", type=Path, metavar="FILE", help="file YAML ghi đè cấu hình mặc định")
    sub = parser.add_subparsers(dest="command", required=True, metavar="LỆNH")

    scan = sub.add_parser("scan", help="quét một job, xuất báo cáo HTML/CSV")
    scan.add_argument("--job", type=int, required=True, help="id job trên CVAT")
    scan.add_argument("--flag", action="store_true",
                      help="gắn cờ lỗi lên box trong CVAT (chỉ chạy khi không ai đang mở job)")
    scan.add_argument("--out", type=Path, default=Path("out"), help="thư mục ghi báo cáo (mặc định: out)")

    gate = sub.add_parser("gate", help="cổng kiểm tra trước khi nộp: ĐẠT (0) / KHÔNG ĐẠT (1)")
    gate.add_argument("--job", type=int, required=True, help="id job trên CVAT")

    diff = sub.add_parser("diff", help="so hai phiên bản nhãn")
    diff.add_argument("old", type=Path, help="bản chụp nhãn cũ (JSON)")
    diff.add_argument("new", type=Path, help="bản chụp nhãn mới (JSON)")
    diff.add_argument("--out", type=Path, default=Path("out"), help="thư mục ghi kết quả (mặc định: out)")

    sub.add_parser("config", help="in cấu hình đang dùng (token được ẩn)")
    return parser


def _ensure_utf8_output() -> None:
    """Tránh lỗi in tiếng Việt khi stdout bị chuyển hướng trên Windows (bảng mã cp1252)."""
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure") and (stream.encoding or "").lower() not in ("utf-8", "utf8"):
            stream.reconfigure(encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    _ensure_utf8_output()
    args = build_parser().parse_args(argv)
    try:
        config = load_config(args.config)
    except ConfigError as exc:
        print(f"Lỗi cấu hình: {exc}", file=sys.stderr)
        return EXIT_RUNTIME_ERROR

    if args.command == "config":
        print(yaml.safe_dump(config.to_dict(), allow_unicode=True, sort_keys=False), end="")
        return EXIT_OK

    task = _NOT_IMPLEMENTED[args.command]
    print(f"Lệnh '{args.command}' chưa có (việc {task} trong TASKS.md).", file=sys.stderr)
    return EXIT_RUNTIME_ERROR


if __name__ == "__main__":
    raise SystemExit(main())
