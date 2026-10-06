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
from pathlib import Path
from typing import Any, Iterable, Mapping

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


def build_findings_map(findings: Iterable[Finding]) -> dict[tuple[int | None, int | None, int], str]:
    """Gom các finding theo khóa `(track_id, source_id, frame)`.

    Nếu 1 box có nhiều finding, ghép các câu thông báo bằng `; `.
    """
    grouped: dict[tuple[int | None, int | None, int], list[str]] = {}
    for f in findings:
        key = (f.track_id, f.source_id, f.frame)
        msg = format_finding_message(f)
        if key not in grouped:
            grouped[key] = []
        if msg not in grouped[key]:
            grouped[key].append(msg)
    return {k: "; ".join(msgs) for k, msgs in grouped.items()}


def build_error_patch(
    raw_annotations: dict[str, Any],
    labels: Mapping[int, LabelInfo],
    findings_map: Mapping[tuple[int | None, int | None, int], str],
    flag_attribute: str = DEFAULT_FLAG_ATTR,
) -> tuple[dict[str, Any], int]:
    """Tạo payload PATCH `action=update` cho CVAT.

    Chỉ đưa vào patch những shapes và tracks thực sự có thay đổi.
    Mọi hình học (points, center, rotation, ngoài...) được giữ nguyên 100%.
    Trả về `(patch_data, số box được cập nhật)`.
    """
    modified_shapes: list[dict[str, Any]] = []
    modified_tracks: list[dict[str, Any]] = []
    modified_count = 0

    # 1. Quét box lẻ (shapes)
    for raw_shape in raw_annotations.get("shapes", []):
        if raw_shape.get("type") != "cuboid":
            continue
        shape_id = raw_shape.get("id")
        frame = raw_shape.get("frame")
        label_id = raw_shape.get("label_id")
        label_info = labels.get(label_id)
        if not label_info:
            continue
        spec_id = label_info.attribute_ids.get(flag_attribute)
        if spec_id is None:
            continue

        # Tìm finding khớp: theo (None, shape_id, frame) hoặc (None, shape_id, None) hoặc (None, None, frame)
        matched_err = findings_map.get((None, shape_id, frame))
        if matched_err is None and shape_id is not None:
            matched_err = findings_map.get((None, shape_id, None))  # type: ignore[arg-type]
        if matched_err is None:
            matched_err = findings_map.get((None, None, frame))

        if matched_err is not None:
            shape_copy = copy.deepcopy(raw_shape)
            if _update_shape_attributes(shape_copy, spec_id, matched_err):
                modified_shapes.append(shape_copy)
                modified_count += 1

    # 2. Quét track (tracks)
    for raw_track in raw_annotations.get("tracks", []):
        track_id = raw_track.get("id")
        label_id = raw_track.get("label_id")
        label_info = labels.get(label_id)
        if not label_info:
            continue
        spec_id = label_info.attribute_ids.get(flag_attribute)
        if spec_id is None:
            continue

        track_modified = False
        track_copy = copy.deepcopy(raw_track)
        for shape in track_copy.get("shapes", []):
            if shape.get("type") != "cuboid":
                continue
            shape_id = shape.get("id")
            frame = shape.get("frame")

            # Khớp finding theo (track_id, shape_id, frame) hoặc (track_id, None, frame)
            matched_err = findings_map.get((track_id, shape_id, frame))
            if matched_err is None:
                matched_err = findings_map.get((track_id, None, frame))

            if matched_err is not None:
                if _update_shape_attributes(shape, spec_id, matched_err):
                    track_modified = True
                    modified_count += 1

        if track_modified:
            modified_tracks.append(track_copy)

    patch_data: dict[str, Any] = {}
    if modified_shapes:
        patch_data["shapes"] = modified_shapes
    if modified_tracks:
        patch_data["tracks"] = modified_tracks

    return patch_data, modified_count


def flag_job_errors(
    client: CvatClient,
    job: JobData,
    findings: Iterable[Finding],
    snapshot_path: str | Path | None = None,
    flag_attribute: str = DEFAULT_FLAG_ATTR,
) -> int:
    """Ghi cờ lỗi `pointsnap_error` lên các box trong job trên CVAT.

    - Nếu `snapshot_path` được cung cấp: lưu bản chụp JSON trước khi ghi.
    - Trả về số lượng box được gắn cờ.
    """
    if snapshot_path:
        save_snapshot(job, snapshot_path)

    findings_list = list(findings)
    if not findings_list:
        return 0

    findings_map = build_findings_map(findings_list)
    raw_annos = client.get_job_annotations(job.job_id)
    patch_data, count = build_error_patch(raw_annos, job.labels, findings_map, flag_attribute)

    if count > 0:
        client.patch_job_annotations(job.job_id, patch_data, action="update")

    return count


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

    raw_annos = client.get_job_annotations(job.job_id)
    modified_shapes: list[dict[str, Any]] = []
    modified_tracks: list[dict[str, Any]] = []
    cleared_count = 0

    # 1. Box lẻ
    if track_id is None:
        for raw_shape in raw_annos.get("shapes", []):
            if raw_shape.get("type") != "cuboid":
                continue
            if frame is not None and raw_shape.get("frame") != frame:
                continue
            label_info = job.labels.get(raw_shape.get("label_id"))
            if not label_info:
                continue
            spec_id = label_info.attribute_ids.get(flag_attribute)
            if spec_id is None:
                continue

            shape_copy = copy.deepcopy(raw_shape)
            if _update_shape_attributes(shape_copy, spec_id, None):
                modified_shapes.append(shape_copy)
                cleared_count += 1

    # 2. Tracks
    for raw_track in raw_annos.get("tracks", []):
        curr_track_id = raw_track.get("id")
        if track_id is not None and curr_track_id != track_id:
            continue
        label_info = job.labels.get(raw_track.get("label_id"))
        if not label_info:
            continue
        spec_id = label_info.attribute_ids.get(flag_attribute)
        if spec_id is None:
            continue

        track_modified = False
        track_copy = copy.deepcopy(raw_track)
        for shape in track_copy.get("shapes", []):
            if shape.get("type") != "cuboid":
                continue
            if frame is not None and shape.get("frame") != frame:
                continue
            if _update_shape_attributes(shape, spec_id, None):
                track_modified = True
                cleared_count += 1

        if track_modified:
            modified_tracks.append(track_copy)

    if cleared_count > 0:
        patch_data: dict[str, Any] = {}
        if modified_shapes:
            patch_data["shapes"] = modified_shapes
        if modified_tracks:
            patch_data["tracks"] = modified_tracks
        client.patch_job_annotations(job.job_id, patch_data, action="update")

    return cleared_count


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
