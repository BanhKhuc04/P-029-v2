"""Script đánh giá chỉ số Precision, Recall và xuất bảng mục 8.2 (việc B6).

Cách dùng:
python scripts/eval_metrics.py --faults path/to/injected_faults.json --findings path/to/findings.json --out docs/danh-gia.md
"""

import argparse
import json
import sys
from pathlib import Path

# Thêm pointsnap-3d vào sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pointsnap.core.model import ErrorType, Finding, Severity
from pointsnap.eval.metrics import evaluate_findings, load_injected_faults


def _ensure_utf8_output() -> None:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure") and (stream.encoding or "").lower() not in ("utf-8", "utf8"):
            stream.reconfigure(encoding="utf-8")


def parse_args():
    parser = argparse.ArgumentParser(description="Tính toán Precision, Recall và xuất báo cáo đánh giá.")
    parser.add_argument("--faults", required=True, help="Đường dẫn tệp log lỗi đã chèn giả (JSON)")
    parser.add_argument("--findings", required=True, help="Đường dẫn tệp kết quả quét (JSON)")
    parser.add_argument("--clean-boxes", type=int, default=1000, help="Tổng số box nhãn sạch để tính báo động giả")
    parser.add_argument("--out", type=Path, default=None, help="Đường dẫn tệp xuất báo cáo Markdown")
    return parser.parse_args()


def main():
    _ensure_utf8_output()
    args = parse_args()

    faults = load_injected_faults(args.faults)

    with open(args.findings, encoding="utf-8") as f:
        data = json.load(f)

    raw_findings = data if isinstance(data, list) else data.get("findings", [])
    findings = []
    for rf in raw_findings:
        findings.append(
            Finding(
                error_type=ErrorType(rf["error_type"]),
                rule=rf["rule"],
                severity=Severity(rf["severity"]),
                frame=int(rf["frame"]),
                label=rf.get("label", ""),
                message=rf.get("message", ""),
                track_id=int(rf["track_id"]) if rf.get("track_id") is not None else None,
                source_id=int(rf["source_id"]) if rf.get("source_id") is not None else None,
                value=float(rf["value"]) if rf.get("value") is not None else None,
                threshold=float(rf["threshold"]) if rf.get("threshold") is not None else None,
            )
        )

    report = evaluate_findings(faults, findings, clean_boxes_total=args.clean_boxes)
    md_content = report.to_markdown()

    print(md_content)

    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(md_content + "\n")
        print(f"\n-> Đã lưu báo cáo đánh giá vào: {args.out}")


if __name__ == "__main__":
    main()
