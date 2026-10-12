"""Tính toán các chỉ số đánh giá Precision, Recall, False Alarms (việc B6).

Theo đặc tả mục 8.2 của docs/thiet-ke/de-xuat-de-tai.md:
- Recall theo loại lỗi (floating, size, track) và theo mức độ (error, warning).
- Precision theo từng loại lỗi.
- Sai số đo đạc: median và p90 của sai số số đo so với lỗi chèn.
- Tạo bảng markdown kết quả đánh giá cho docs/ket-qua/danh-gia.md.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np

from pointsnap.core.model import Finding, Severity


@dataclass(frozen=True)
class InjectedFault:
    """Một lỗi được chèn giả vào dữ liệu kiểm tra."""

    error_type: str  # "floating" | "size" | "track"
    frame: int
    track_id: int | None = None
    severity: str = "error"  # "error" | "warning"
    rule: str = ""
    delta: float = 0.0
    details: Mapping[str, Any] = field(default_factory=dict)


@dataclass
class MetricSummary:
    total_injected: int = 0
    true_positives: int = 0
    false_positives: int = 0
    false_negatives: int = 0
    measurement_errors: list[float] = field(default_factory=list)

    @property
    def recall(self) -> float:
        return (self.true_positives / self.total_injected) if self.total_injected > 0 else 0.0

    @property
    def precision(self) -> float:
        total_detected = self.true_positives + self.false_positives
        return (self.true_positives / total_detected) if total_detected > 0 else 0.0

    @property
    def median_error(self) -> float:
        return float(np.median(self.measurement_errors)) if self.measurement_errors else 0.0

    @property
    def p90_error(self) -> float:
        return float(np.percentile(self.measurement_errors, 90)) if self.measurement_errors else 0.0


@dataclass
class EvaluationReport:
    overall: MetricSummary = field(default_factory=MetricSummary)
    by_type: dict[str, MetricSummary] = field(default_factory=dict)
    by_severity: dict[str, MetricSummary] = field(default_factory=dict)
    clean_boxes_total: int = 0
    clean_false_alarms: int = 0

    @property
    def false_alarm_rate_per_100(self) -> float:
        if self.clean_boxes_total == 0:
            return 0.0
        return (self.clean_false_alarms / self.clean_boxes_total) * 100.0

    def to_markdown(self) -> str:
        lines = [
            "# BẢNG CHỈ SỐ ĐÁNH GIÁ (MỤC 8.2)",
            "",
            "## 1. Hiệu quả phát hiện (trên lỗi chèn giả)",
            "",
            "| Chỉ số | Mục tiêu | Kết quả thực tế | Đánh giá |",
            "|---|---|---|---|",
        ]

        # Recall theo loại lỗi
        for et in ("floating", "size", "track"):
            s = self.by_type.get(et, MetricSummary())
            target = 0.90
            status = "ĐẠT" if s.recall >= target else "CHƯA ĐẠT"
            lines.append(
                f"| Recall — {et} | ≥ 90% | **{s.recall*100:.1f}%** ({s.true_positives}/{s.total_injected}) | {status} |"
            )

        # Recall theo mức độ
        for sev, target in (("error", 0.90), ("warning", 0.80)):
            s = self.by_severity.get(sev, MetricSummary())
            status = "ĐẠT" if s.recall >= target else "CHƯA ĐẠT"
            lines.append(
                f"| Recall — {sev} | ≥ {target*100:.0f}% | **{s.recall*100:.1f}%** ({s.true_positives}/{s.total_injected}) | {status} |"
            )

        # Precision mỗi loại
        for et in ("floating", "size", "track"):
            s = self.by_type.get(et, MetricSummary())
            target = 0.70
            status = "ĐẠT" if s.precision >= target else "CHƯA ĐẠT"
            lines.append(
                f"| Precision — {et} | ≥ 70% | **{s.precision*100:.1f}%** (TP: {s.true_positives}, FP: {s.false_positives}) | {status} |"
            )

        lines.extend([
            "",
            "## 2. Báo động giả trên nhãn sạch",
            "",
            "| Chỉ số | Mục tiêu | Kết quả thực tế | Đánh giá |",
            "|---|---|---|---|",
            f"| Báo động giả trên nhãn sạch | ≤ 2 Cảnh báo / 100 box | **{self.false_alarm_rate_per_100:.2f}** Cảnh báo / 100 box ({self.clean_false_alarms}/{self.clean_boxes_total} box) | {'ĐẠT' if self.false_alarm_rate_per_100 <= 2.0 else 'CHƯA ĐẠT'} |",
            "",
            "## 3. Độ chính xác số đo",
            "",
            "| Chỉ số | Mục tiêu | Sai số trung vị | Phân vị 90 (P90) |",
            "|---|---|---|---|",
        ])

        for et in ("floating", "size"):
            s = self.by_type.get(et, MetricSummary())
            lines.append(
                f"| Sai số đo {et} | Trung vị < 3 cm | **{s.median_error*100:.2f} cm** | {s.p90_error*100:.2f} cm |"
            )

        return "\n".join(lines)


def evaluate_findings(
    injected_faults: Sequence[InjectedFault],
    findings: Sequence[Finding],
    clean_boxes_total: int = 0,
    clean_findings: Sequence[Finding] | None = None,
) -> EvaluationReport:
    """So khớp kết quả quét findings với tập lỗi chèn giả."""
    report = EvaluationReport()

    # Nhóm findings theo (error_type, frame, track_id)
    findings_by_key: dict[tuple[str, int, int | None], list[Finding]] = {}
    for f in findings:
        key = (f.error_type.value, f.frame, f.track_id)
        findings_by_key.setdefault(key, []).append(f)

    matched_finding_ids = set()

    # Khởi tạo metrics
    for et in ("floating", "size", "track"):
        report.by_type[et] = MetricSummary()
    for sev in ("error", "warning"):
        report.by_severity[sev] = MetricSummary()

    # Đếm và so khớp từng lỗi chèn
    for fault in injected_faults:
        report.overall.total_injected += 1
        t_sum = report.by_type.setdefault(fault.error_type, MetricSummary())
        s_sum = report.by_severity.setdefault(fault.severity, MetricSummary())
        t_sum.total_injected += 1
        s_sum.total_injected += 1

        key = (fault.error_type, fault.frame, fault.track_id)
        candidates = findings_by_key.get(key, [])

        # Tìm candidate khớp severity trước, nếu không lấy candidate bất kỳ cùng loại
        matched: Finding | None = None
        for c in candidates:
            if id(c) not in matched_finding_ids and c.severity.value == fault.severity:
                matched = c
                break
        if matched is None and candidates:
            for c in candidates:
                if id(c) not in matched_finding_ids:
                    matched = c
                    break

        if matched is not None:
            matched_finding_ids.add(id(matched))
            report.overall.true_positives += 1
            t_sum.true_positives += 1
            s_sum.true_positives += 1

            if fault.delta > 0.0 and matched.value is not None:
                err = abs(abs(matched.value) - fault.delta)
                report.overall.measurement_errors.append(err)
                t_sum.measurement_errors.append(err)
        else:
            report.overall.false_negatives += 1
            t_sum.false_negatives += 1
            s_sum.false_negatives += 1

    # Đếm False Positives (các finding không khớp lỗi chèn nào)
    for f in findings:
        if id(f) not in matched_finding_ids and f.severity != Severity.INFO:
            report.overall.false_positives += 1
            t_sum = report.by_type.setdefault(f.error_type.value, MetricSummary())
            t_sum.false_positives += 1

    # Báo động giả trên nhãn sạch
    report.clean_boxes_total = clean_boxes_total
    if clean_findings:
        report.clean_false_alarms = sum(1 for f in clean_findings if f.severity in (Severity.WARNING, Severity.ERROR))

    return report


def load_injected_faults(path: str | Path) -> list[InjectedFault]:
    """Đọc file JSON chứa log lỗi đã chèn."""
    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    faults = []
    items = data if isinstance(data, list) else data.get("injected_faults", [])
    for it in items:
        faults.append(
            InjectedFault(
                error_type=it["error_type"],
                frame=int(it["frame"]),
                track_id=int(it["track_id"]) if it.get("track_id") is not None else None,
                severity=it.get("severity", "error"),
                rule=it.get("rule", ""),
                delta=float(it.get("delta", 0.0)),
                details=it.get("details", {}),
            )
        )
    return faults
