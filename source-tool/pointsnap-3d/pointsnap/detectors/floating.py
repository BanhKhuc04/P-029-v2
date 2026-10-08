"""Bộ phát hiện lỗi lơ lửng / lún đất (việc B3).

Quy ước: CONVENTIONS.md mục 4 (mã luật `floating`, `floating.no_evidence`).
Định nghĩa: d = z_đáy_box - z_ground_cục_bộ (cm).
  d > 0: lơ lửng
  d < 0: lún đất
Chống báo động giả: Ít hơn min_ground_points điểm ground -> mức Thông tin ("thiếu bằng chứng").

Hai cách dùng:
- `detect_floating` / `detect_floating_for_box`: một frame, so |d| tuyệt đối với `warning_m` / `error_m`.
- `detect_floating_scene` (bộ quét dùng, A10): cả job. Nhãn chuẩn nuScenes tự nó đã lệch mặt đất ước lượng khá
  nhiều (bờ vỉa, dốc, LiDAR thưa: trung vị |d| ~8 cm, p90 ~25 cm) nhưng phần lệch đó ổn định trong một track, nên so
  `d` của box với **trung vị d của các box khác cùng track**; mặt đất đo bằng trung vị điểm thấp trong vành đai sát
  box, đã bỏ điểm của box khác (`ring_ground_for_box`). Kiểm chứng: docs/kiem-chung-ground.md.
"""

from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING, Iterable, Sequence

import numpy as np

from pointsnap.core.ground import GroundEstimate, OtherBoxPoints, estimate_ground_for_box, ring_ground_for_box
from pointsnap.core.model import ErrorType, Finding, Severity, group_by_frame

if TYPE_CHECKING:
    from pointsnap.core.config import FloatingConfig
    from pointsnap.core.model import Cuboid, FrameSource


def detect_floating_for_box(
    cuboid: Cuboid,
    points: np.ndarray,
    config: FloatingConfig,
    seed: int | None = 42,
) -> Finding | None:
    """Kiểm tra lỗi lơ lửng / lún đất cho một box 3D."""
    if cuboid.outside or cuboid.label not in config.classes:
        return None

    est: GroundEstimate = estimate_ground_for_box(
        points=points,
        cuboid=cuboid,
        ring_inner_m=config.ring_inner_m,
        ring_outer_m=config.ring_outer_m,
        min_ground_points=config.min_ground_points,
        seed=seed,
    )

    if est.status == "no_evidence":
        return Finding(
            error_type=ErrorType.FLOATING,
            rule="floating.no_evidence",
            severity=Severity.INFO,
            frame=cuboid.frame,
            label=cuboid.label,
            track_id=cuboid.track_id,
            source_id=cuboid.source_id,
            message=(
                f"Vành đai quanh box chỉ có {est.num_ground_points} điểm ground "
                f"(< {config.min_ground_points}), thiếu bằng chứng kết luận"
            ),
            value=float(est.num_ground_points),
            threshold=float(config.min_ground_points),
            details={"num_ground_points": est.num_ground_points},
        )

    if not est.is_valid or est.distance is None:
        return None

    d = est.distance
    abs_d = abs(d)

    if abs_d > config.error_m:
        severity = Severity.ERROR
        thresh = config.error_m
    elif abs_d > config.warning_m:
        severity = Severity.WARNING
        thresh = config.warning_m
    else:
        return None

    d_cm = abs_d * 100.0
    thresh_cm = thresh * 100.0
    direction = "lơ lửng" if d > 0 else "lún đất"

    message = f"Đáy box {direction} {d_cm:.1f} cm so với mặt đất (ngưỡng {thresh_cm:.0f} cm)"

    return Finding(
        error_type=ErrorType.FLOATING,
        rule="floating",
        severity=severity,
        frame=cuboid.frame,
        label=cuboid.label,
        track_id=cuboid.track_id,
        source_id=cuboid.source_id,
        message=message,
        value=float(d),
        threshold=float(thresh),
        details={
            "distance": d,
            "ground_z": est.ground_z,
            "bottom_z": cuboid.bottom_z,
            "num_inliers": est.num_inliers,
            "num_ground_points": est.num_ground_points,
        },
    )


def detect_floating(
    cuboids: Sequence[Cuboid],
    points: np.ndarray,
    config: FloatingConfig,
    seed: int | None = 42,
) -> list[Finding]:
    """Phát hiện lỗi lơ lửng / lún đất trên danh sách box của một frame."""
    findings: list[Finding] = []
    for cuboid in cuboids:
        finding = detect_floating_for_box(cuboid, points, config, seed=seed)
        if finding is not None:
            findings.append(finding)
    return findings


def estimate_scene_ground(
    cuboids: Iterable[Cuboid], frames: FrameSource, config: FloatingConfig,
) -> list[tuple[Cuboid, GroundEstimate]]:
    """Mặt đất sát từng box tiếp đất (không `outside`); đọc point cloud mỗi frame một lần."""
    classes = set(config.classes)
    results: list[tuple[Cuboid, GroundEstimate]] = []
    for frame, boxes in group_by_frame(c for c in cuboids if not c.outside).items():
        if not any(b.label in classes for b in boxes):
            continue
        cloud = OtherBoxPoints(frames.frame_data(frame).points, boxes)
        for index, box in enumerate(boxes):
            if box.label in classes:
                results.append((box, ring_ground_for_box(
                    cloud.without_others(index), box, ring_inner_m=config.ring_inner_m,
                    ring_outer_m=config.ring_outer_m, min_ground_points=config.min_ground_points,
                )))
    return results


def _describe(d: float) -> str:
    if d >= 0:
        return f"Đáy box cách mặt đất {d * 100:.0f} cm (lơ lửng)"
    return f"Đáy box nằm dưới mặt đất {-d * 100:.0f} cm (lún)"


def floating_findings_by_track(
    estimates: Sequence[tuple[Cuboid, GroundEstimate]], config: FloatingConfig,
) -> list[Finding]:
    """Luật lơ lửng / lún so với các frame khác của track.

    - Cảnh báo nếu `|d − trung vị d của các box khác cùng track| > warning_m`; Lỗi nếu `> error_m` và
      `|d| > error_min_abs_m`.
    - Box lẻ, hoặc track có ít hơn `min_track_boxes` box khác đo được: so `|d|` với `single_warning_m` / `single_error_m`.
    - Box không đủ điểm mặt đất: không kết luận, gộp một mục Thông tin cho mỗi track.
    """
    by_track: dict[int, list[int]] = defaultdict(list)
    for i, (box, est) in enumerate(estimates):
        if box.track_id is not None and est.is_valid:
            by_track[box.track_id].append(i)

    findings: list[Finding] = []
    no_evidence: dict[int | None, list[Cuboid]] = defaultdict(list)
    for i, (box, est) in enumerate(estimates):
        if not est.is_valid:
            no_evidence[box.track_id].append(box)
            continue
        d = float(est.distance)
        others = [estimates[j][1].distance for j in by_track.get(box.track_id, []) if j != i]
        details = {"distance": d, "ground_z": est.ground_z, "bottom_z": box.bottom_z,
                   "num_ground_points": est.num_ground_points}
        if len(others) >= config.min_track_boxes:
            reference = float(np.median(others))
            offset = d - reference
            details["track_median_distance"] = reference
            if abs(offset) > config.error_m and abs(d) > config.error_min_abs_m:
                severity, threshold = Severity.ERROR, config.error_m
            elif abs(offset) > config.warning_m:
                severity, threshold = Severity.WARNING, config.warning_m
            else:
                continue
            direction = "cao hơn" if offset > 0 else "thấp hơn"
            message = (f"{_describe(d)}; {direction} {abs(offset) * 100:.0f} cm so với các frame khác của track "
                       f"(trung vị {reference * 100:+.0f} cm)")
            value = offset
        else:
            if abs(d) > config.single_error_m:
                severity, threshold = Severity.ERROR, config.single_error_m
            elif abs(d) > config.single_warning_m:
                severity, threshold = Severity.WARNING, config.single_warning_m
            else:
                continue
            message = _describe(d)
            value = d
        findings.append(Finding(
            error_type=ErrorType.FLOATING, rule="floating", severity=severity, frame=box.frame, label=box.label,
            track_id=box.track_id, source_id=box.source_id, message=message, value=float(value),
            threshold=float(threshold), details=details,
        ))

    for track_id, boxes in no_evidence.items():
        groups = [[b] for b in boxes] if track_id is None else [boxes]
        for group in groups:
            first, frames = group[0], sorted(b.frame for b in group)
            where = f"frame {frames[0]}" if len(frames) == 1 else f"{len(frames)} frame ({frames[0]}–{frames[-1]})"
            findings.append(Finding(
                error_type=ErrorType.FLOATING, rule="floating.no_evidence", severity=Severity.INFO,
                frame=first.frame, label=first.label, track_id=first.track_id,
                source_id=first.source_id if len(group) == 1 else None,
                message=f"Thiếu bằng chứng mặt đất quanh box ở {where}: không kiểm được lơ lửng / lún",
                value=float(len(group)), details={"frames": frames},
            ))
    return findings


def detect_floating_scene(
    cuboids: Iterable[Cuboid], frames: FrameSource, config: FloatingConfig,
) -> list[Finding]:
    """Lơ lửng / lún trên cả job: ước lượng mặt đất từng box rồi so với các frame khác của track."""
    return floating_findings_by_track(estimate_scene_ground(cuboids, frames, config), config)