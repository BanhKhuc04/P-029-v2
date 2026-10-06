"""Ghi và xóa cờ lỗi `pointsnap_error` trên CVAT và lưu bản chụp JSON (việc A4).

Quy ước:
- Lưu bản chụp nhãn trước khi ghi cờ lỗi để có thể hoàn tác hoặc so sánh (`diff`).
- Endpoint PATCH `/api/jobs/<id>/annotations?action=update` của CVAT 2.x cập nhật shapes/tracks.
- Để bảo toàn 100% hình học box (center, dims, yaw, roll, pitch, occluded, outside):
  sử dụng đúng dữ liệu gốc từ `GET /api/jobs/<id>/annotations`, chỉ cập nhật mảng `attributes`
  của shape/keyframe tương ứng với thuộc tính `pointsnap_error`.
- Thuộc tính `pointsnap_error` là `mutable` nên nằm ở từng keyframe của track (hoặc shape lẻ).
"""

from __future__ import annotations

import copy
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping

from pointsnap.adapters.cvat.client import CvatClient
from pointsnap.adapters.cvat.reader import JobData, LabelInfo
from pointsnap.core.model import Cuboid, Finding
from pointsnap.core.serialize import save_cuboids

DEFAULT_FLAG_ATTR = "pointsnap_error"
DEFAULT_REVIEWED_ATTR = "reviewed"


def save_snapshot(job: JobData, path: str | Path, meta: dict[str, Any] | None = None) -> None:
    """Lưu bản chụp JSON của các box trong job trước khi sửa đổi nhãn."""
    default_meta = {
        "url": job.url,
        "task_id": job.task_id,
        "job_id": job.job_id,
        "start_frame": job.start_frame,
        "stop_frame": job.stop_frame,
    }
    if meta:
        default_meta.update(meta)
    save_cuboids(path, job.cuboids, meta=default_meta)


def format_finding_message(finding: Finding) -> str:
    """Định dạng thông báo lỗi hiển thị cho người dán nhãn trong CVAT."""
    return f"[{finding.severity.label_vi}] {finding.message}"


def _update_shape_attributes(
    shape: dict[str, Any],
    spec_id: int,
    error_value: str | None,
) -> bool:
    """Cập nhật thuộc tính `spec_id` trong `shape['attributes']`.

    - Nếu `error_value` có nội dung: gán giá trị mới.
    - Nếu `error_value` là `None` hoặc rỗng `""`: xóa thuộc tính khỏi danh sách hoặc gán rỗng.
    Trả về `True` nếu thuộc tính thay đổi so với giá trị cũ.
    """
    attributes = list(shape.get("attributes", []))
    old_value: str | None = None
    target_idx: int | None = None

    for i, attr in enumerate(attributes):
        if attr.get("spec_id") == spec_id:
            old_value = attr.get("value", "")
            target_idx = i
            break

    new_val = error_value or ""
    if old_value == new_val or (old_value is None and not new_val):
        return False

    if new_val:
        if target_idx is not None:
            attributes[target_idx] = {"spec_id": spec_id, "value": new_val}
        else:
            attributes.append({"spec_id": spec_id, "value": new_val})
    else:
        if target_idx is not None:
            # Xóa thuộc tính cờ lỗi
            attributes.pop(target_idx)

    shape["attributes"] = attributes
    return True


FindingKey = tuple[int | None, int | None, int]

_KEEP = object()  # giá trị trả về của `value_for`: không đụng tới cờ của box này


@dataclass(frozen=True)
class FlagSummary:
    """Kết quả một lần đồng bộ cờ lỗi lên CVAT."""

    flagged: int  # số box được ghi cờ mới hoặc đổi nội dung cờ
    cleared: int  # số box được xóa cờ cũ (box đã hết lỗi)
    unmatched: int  # số khóa finding không khớp box nào trên CVAT (không ghi được cờ)


def build_findings_map(findings: Iterable[Finding]) -> dict[FindingKey, str]:
    """Gom các finding theo khóa `(track_id, source_id, frame)`.

    Nếu 1 box có nhiều finding, ghép các câu thông báo bằng `; `.
    """
    grouped: dict[FindingKey, list[str]] = {}
    for f in findings:
        msgs = grouped.setdefault((f.track_id, f.source_id, f.frame), [])
        msg = format_finding_message(f)
        if msg not in msgs:
            msgs.append(msg)
    return {k: "; ".join(msgs) for k, msgs in grouped.items()}


def _plan_flag_updates(
    raw_annotations: dict[str, Any],
    labels: Mapping[int, LabelInfo],
    flag_attribute: str,
    value_for: Callable[[int | None, int | None, int], Any],
) -> tuple[dict[str, Any], int, int]:
    """Duyệt mọi box cuboid, đặt cờ theo `value_for(track_id, shape_id, frame)`.

    `value_for` trả về chuỗi (ghi cờ), `None` (xóa cờ) hoặc `_KEEP` (giữ nguyên).
    Chỉ đưa vào patch những shape/track thực sự đổi; hình học giữ nguyên vì dùng đúng dữ liệu gốc.
    Trả về `(patch, số box ghi cờ, số box xóa cờ)`.
    """
    patch: dict[str, Any] = {}
    flagged = cleared = 0

    def apply(shape: dict[str, Any], spec_id: int, value: Any) -> bool:
        nonlocal flagged, cleared
        if value is _KEEP or not _update_shape_attributes(shape, spec_id, value):
            return False
        if value:
            flagged += 1
        else:
            cleared += 1
        return True

    def spec_of(label_id: Any) -> int | None:
        info = labels.get(label_id)
        return info.attribute_ids.get(flag_attribute) if info else None

    for raw_shape in raw_annotations.get("shapes", []):
        spec_id = spec_of(raw_shape.get("label_id"))
        if raw_shape.get("type") != "cuboid" or spec_id is None:
            continue
        shape = copy.deepcopy(raw_shape)
        if apply(shape, spec_id, value_for(None, shape.get("id"), shape.get("frame"))):
            patch.setdefault("shapes", []).append(shape)

    for raw_track in raw_annotations.get("tracks", []):
        spec_id = spec_of(raw_track.get("label_id"))
        if spec_id is None:
            continue
        track = copy.deepcopy(raw_track)
        changed = False
        for shape in track.get("shapes", []):
            if shape.get("type") == "cuboid":
                changed |= apply(shape, spec_id, value_for(track.get("id"), shape.get("id"), shape.get("frame")))
        if changed:
            patch.setdefault("tracks", []).append(track)

    return patch, flagged, cleared


def build_error_patch(
    raw_annotations: dict[str, Any],
    labels: Mapping[int, LabelInfo],
    findings_map: Mapping[FindingKey, str],
    flag_attribute: str = DEFAULT_FLAG_ATTR,
    clear_stale: bool = True,
) -> tuple[dict[str, Any], FlagSummary]:
    """Tạo payload PATCH `action=update` để cờ trên CVAT khớp đúng với `findings_map`.

    Khớp box theo đúng id: box lẻ bằng `(None, id shape, frame)`; keyframe của track bằng
    `(id track, id keyframe, frame)` hoặc `(id track, None, frame)`. Không có khớp "mọi box trong frame".
    Với `clear_stale=True`, box không còn finding nào thì xóa cờ cũ (lần quét sau tự gỡ cờ).
    """
    used: set[FindingKey] = set()

    def value_for(track_id: int | None, shape_id: int | None, frame: int) -> Any:
        keys = [(track_id, shape_id, frame)]
        if track_id is not None:
            keys.append((track_id, None, frame))
        for key in keys:
            if key in findings_map:
                used.add(key)
                return findings_map[key]
        return None if clear_stale else _KEEP

    patch, flagged, cleared = _plan_flag_updates(raw_annotations, labels, flag_attribute, value_for)
    unmatched = len(set(findings_map) - used)
    return patch, FlagSummary(flagged=flagged, cleared=cleared, unmatched=unmatched)


def flag_job_errors(
    client: CvatClient,
    job: JobData,
    findings: Iterable[Finding],
    snapshot_path: str | Path | None = None,
    flag_attribute: str = DEFAULT_FLAG_ATTR,
    clear_stale: bool = True,
) -> FlagSummary:
    """Đồng bộ cờ lỗi `pointsnap_error` trên CVAT với danh sách finding.

    - Nếu `snapshot_path` được cung cấp: lưu bản chụp JSON trước khi ghi.
    - Không có finding nào vẫn chạy, để xóa cờ cũ khi `clear_stale=True`.
    """
    if snapshot_path:
        save_snapshot(job, snapshot_path)

    findings_map = build_findings_map(findings)
    raw_annos = client.get_job_annotations(job.job_id)
    patch_data, summary = build_error_patch(raw_annos, job.labels, findings_map, flag_attribute, clear_stale)
    if patch_data:
        client.patch_job_annotations(job.job_id, patch_data, action="update")
    return summary


def clear_job_errors(
    client: CvatClient,
    job: JobData,
    snapshot_path: str | Path | None = None,
    track_id: int | None = None,
    frame: int | None = None,
    flag_attribute: str = DEFAULT_FLAG_ATTR,
) -> int:
    """Xóa cờ lỗi `pointsnap_error` trên CVAT.

    - Nếu `track_id` hoặc `frame` được chỉ định: chỉ xóa box khớp điều kiện.
    - Nếu cả hai là `None`: xóa cờ lỗi của toàn bộ các box trong job.
    - Nếu `snapshot_path` được cung cấp: lưu bản chụp JSON trước khi xóa.
    - Trả về số lượng box được xóa cờ.
    """
    if snapshot_path:
        save_snapshot(job, snapshot_path)

    def value_for(tid: int | None, _shape_id: int | None, f: int) -> Any:
        if (track_id is not None and tid != track_id) or (frame is not None and f != frame):
            return _KEEP
        return None

    raw_annos = client.get_job_annotations(job.job_id)
    patch_data, _, cleared = _plan_flag_updates(raw_annos, job.labels, flag_attribute, value_for)
    if patch_data:
        client.patch_job_annotations(job.job_id, patch_data, action="update")
    return cleared


def verify_geometry_preserved(
    before_cuboids: Iterable[Cuboid],
    after_cuboids: Iterable[Cuboid],
    tolerance: float = 1e-6,
) -> None:
    """Kiểm tra hình học của các box trước và sau khi ghi/xóa cờ lỗi.

    Báo lỗi nếu số lượng box khác nhau hoặc bất kỳ tọa độ tâm, kích thước, yaw nào bị xê dịch.
    """
    before_list = list(before_cuboids)
    after_list = list(after_cuboids)

    if len(before_list) != len(after_list):
        raise ValueError(
            f"Số lượng box không khớp sau khi thao tác: trước {len(before_list)}, sau {len(after_list)}"
        )

    for b, a in zip(before_list, after_list):
        if (b.frame, b.track_id, b.source_id) != (a.frame, a.track_id, a.source_id):
            raise ValueError(f"Thứ tự hoặc định danh box bị thay đổi: {b} vs {a}")

        for i, name in enumerate(("x", "y", "z")):
            if not math.isclose(b.center[i], a.center[i], abs_tol=tolerance):
                raise ValueError(
                    f"Tâm box (frame={b.frame}, track={b.track_id}) bị lệch ở trục {name}: "
                    f"{b.center[i]} -> {a.center[i]}"
                )
            if not math.isclose(b.dims[i], a.dims[i], abs_tol=tolerance):
                raise ValueError(
                    f"Kích thước box (frame={b.frame}, track={b.track_id}) bị thay đổi ở trục {name}: "
                    f"{b.dims[i]} -> {a.dims[i]}"
                )

        if not math.isclose(b.yaw, a.yaw, abs_tol=tolerance):
            raise ValueError(
                f"Yaw của box (frame={b.frame}, track={b.track_id}) bị thay đổi: "
                f"{b.yaw} -> {a.yaw}"
            )
