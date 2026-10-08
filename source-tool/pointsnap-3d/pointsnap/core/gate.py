"""Cổng kiểm tra chất lượng nhãn: đánh giá findings theo cấu hình gate."""

from __future__ import annotations

from typing import Iterable

from pointsnap.core.config import GateConfig
from pointsnap.core.model import Finding, Severity


def gate_verdict(findings: Iterable[Finding], gate_config: GateConfig) -> tuple[bool, list[str]]:
    """Kiểm tra danh sách finding theo tiêu chí gate.

    Trả về `(passed, reasons)`.
    - `passed`: `True` nếu số lỗi và số cảnh báo không vượt quá ngưỡng cho phép, ngược lại `False`.
    - `reasons`: danh sách lý do nếu không đạt (rỗng nếu đạt).
    """
    errors = [f for f in findings if f.severity is Severity.ERROR]
    warnings = [f for f in findings if f.severity is Severity.WARNING]

    num_errors = len(errors)
    num_warnings = len(warnings)

    max_err = gate_config.max_errors
    max_warn = gate_config.max_warnings

    reasons: list[str] = []
    if num_errors > max_err:
        reasons.append(f"Số lỗi ({num_errors}) vượt quá ngưỡng cho phép ({max_err})")
    if num_warnings > max_warn:
        reasons.append(f"Số cảnh báo ({num_warnings}) vượt quá ngưỡng cho phép ({max_warn})")

    return (len(reasons) == 0, reasons)
