"""Bộ phát hiện thiếu / sai thuộc tính theo guideline của dự án (việc C2).

Spec 3.1.3: attribute là bắt buộc nếu object thuộc phạm vi attribute (vd `Vehicle` phải có `subtype`, `Pedestrian`
phải có `age_group` và `pose`, `Two-wheels` phải có `rider_state`). Hai luật, đều mức Lỗi:

1. `attr.missing`: box thuộc class có trong `spec.required_attributes` mà thiếu thuộc tính hoặc để trống.
2. `attr.invalid`: giá trị thuộc tính không nằm trong danh sách `spec.allowed_values` của thuộc tính đó (khóa
   `Label.thuộc_tính` cho riêng một class, hoặc `thuộc_tính` dùng chung).

Mỗi track (hoặc box lẻ) báo tối đa một mục cho mỗi thuộc tính, gắn vào keyframe đầu tiên bị sai, kèm số keyframe sai.
Cấu hình rỗng (mặc định, nhãn nuScenes không có thuộc tính) thì không báo gì.
"""

from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING, Iterable

from pointsnap.core.model import Cuboid, ErrorType, Finding, Severity

if TYPE_CHECKING:
    from pointsnap.core.config import SpecConfig


def _problems(box: Cuboid, cfg: SpecConfig) -> list[tuple[str, str, str]]:
    """[(luật, thuộc tính, giá trị)] của một box."""
    found = []
    for name in cfg.required_attributes.get(box.label, ()):
        value = box.attrs.get(name)
        if value is None or str(value).strip() == "":
            found.append(("attr.missing", name, ""))
    for name, value in box.attrs.items():
        allowed = allowed_values_for(box.label, name, cfg)
        if allowed is None or value is None or str(value).strip() == "":
            continue
        if str(value) not in allowed:
            found.append(("attr.invalid", name, str(value)))
    return found


def allowed_values_for(label: str, name: str, cfg: SpecConfig) -> tuple[str, ...] | None:
    """Danh sách giá trị cho phép của thuộc tính `name` ở class `label`: khóa `Label.thuộc_tính` ưu tiên hơn khóa
    `thuộc_tính` dùng chung; `None` nếu guideline không giới hạn giá trị."""
    return cfg.allowed_values.get(f"{label}.{name}", cfg.allowed_values.get(name))


def detect_attribute_errors(cuboids: Iterable[Cuboid], cfg: SpecConfig) -> list[Finding]:
    groups: dict[tuple, list[Cuboid]] = defaultdict(list)
    for box in sorted((c for c in cuboids if not c.outside), key=lambda c: c.frame):
        for rule, name, value in _problems(box, cfg):
            owner = box.track_id if box.track_id is not None else ("shape", box.frame, box.source_id, id(box))
            groups[(owner, rule, name, value)].append(box)
    findings: list[Finding] = []
    for (_, rule, name, value), boxes in groups.items():
        first = boxes[0]
        where = f"{len(boxes)} keyframe, từ frame {first.frame}" if len(boxes) > 1 else f"frame {first.frame}"
        if rule == "attr.missing":
            message = f"{first.label} thiếu thuộc tính bắt buộc `{name}` ({where}); spec 3.1.3: không chắc thì chọn other"
        else:
            allowed = ", ".join(allowed_values_for(first.label, name, cfg) or ())
            message = f"Thuộc tính `{name}` = '{value}' không có trong danh sách cho phép ({allowed}) ({where})"
        findings.append(Finding(
            error_type=ErrorType.ATTRIBUTE, rule=rule, severity=Severity.ERROR, frame=first.frame, label=first.label,
            track_id=first.track_id, source_id=first.source_id, message=message, value=float(len(boxes)),
            details={"attribute": name, "value": value, "frames": [b.frame for b in boxes]},
        ))
    return findings
