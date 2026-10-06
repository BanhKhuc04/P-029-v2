"""Phát hiện box lơ lửng / lún đất (việc B3, mục 4.1a của đề xuất).

Đại lượng đo: `d = z_đáy_box − z_mặt_đất_sát_box` (`ground.ring_ground_for_box`); d > 0 là lơ lửng, d < 0 là lún.

Nhãn chuẩn nuScenes tự nó đã lệch mặt đất ước lượng khá nhiều (bờ vỉa, dốc, LiDAR thưa): trung vị |d| ~8 cm,
p90 ~25 cm, nên ngưỡng tuyệt đối 10 / 20 cm sẽ báo động giả quá nhiều. Phần lệch đó lại ổn định trong một track,
nên luật chính so `d` của box với **trung vị d của các box khác cùng track**:
- Cảnh báo nếu `|d − trung_vị| > warning_m`; Lỗi nếu `> error_m` và `|d| > error_min_abs_m`.
- Box lẻ hoặc track có ít hơn `min_track_boxes` box khác có bằng chứng: so `|d|` với `single_warning_m` / `single_error_m`.
- Vành đai có ít hơn `min_ground_points` điểm mặt đất: không kết luận; gộp thành một mục Thông tin cho mỗi track.
Số liệu kiểm chứng: docs/kiem-chung-ground.md.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Iterable

import numpy as np

from pointsnap.core.config import Config
from pointsnap.core.ground import GroundEstimate, OtherBoxPoints, ring_ground_for_box
from pointsnap.core.model import Cuboid, ErrorType, Finding, FrameSource, Severity, group_by_frame


def estimate_box_ground(
    cuboids: Iterable[Cuboid], config: Config, frames: FrameSource,
) -> list[tuple[Cuboid, GroundEstimate]]:
    """Ước lượng mặt đất cho mọi box tiếp đất (không `outside`), đọc point cloud từng frame một lần."""
    cfg = config.floating
    classes = set(cfg.classes)
    results: list[tuple[Cuboid, GroundEstimate]] = []
    for frame, boxes in group_by_frame(c for c in cuboids if not c.outside).items():
        if not any(b.label in classes for b in boxes):
            continue
        cloud = OtherBoxPoints(frames.frame_data(frame).points, boxes)
        for index, box in enumerate(boxes):
            if box.label not in classes:
                continue
            estimate = ring_ground_for_box(
                cloud.without_others(index), box,
                ring_inner_m=cfg.ring_inner_m, ring_outer_m=cfg.ring_outer_m, min_ground_points=cfg.min_ground_points,
            )
            results.append((box, estimate))
    return results


def _describe(d: float) -> str:
    if d >= 0:
        return f"Đáy box cách mặt đất {d * 100:.0f} cm (lơ lửng)"
    return f"Đáy box nằm dưới mặt đất {-d * 100:.0f} cm (lún)"


def floating_findings(estimates: list[tuple[Cuboid, GroundEstimate]], config: Config) -> list[Finding]:
    """Áp luật lơ lửng / lún lên kết quả ước lượng mặt đất."""
    cfg = config.floating
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
        details = {"d_m": round(d, 4), "ground_z": round(float(est.ground_z), 4), "ground_points": est.num_ground_points}
        if len(others) >= cfg.min_track_boxes:
            reference = float(np.median(others))
            offset = d - reference
            details["track_median_d_m"] = round(reference, 4)
            if abs(offset) > cfg.error_m and abs(d) > cfg.error_min_abs_m:
                severity, threshold = Severity.ERROR, cfg.error_m
            elif abs(offset) > cfg.warning_m:
                severity, threshold = Severity.WARNING, cfg.warning_m
            else:
                continue
            direction = "cao hơn" if offset > 0 else "thấp hơn"
            message = (f"{_describe(d)}; {direction} {abs(offset) * 100:.0f} cm so với các frame khác của track "
                       f"(trung vị {reference * 100:+.0f} cm)")
            value = offset
        else:
            if abs(d) > cfg.single_error_m:
                severity, threshold = Severity.ERROR, cfg.single_error_m
            elif abs(d) > cfg.single_warning_m:
                severity, threshold = Severity.WARNING, cfg.single_warning_m
            else:
                continue
            message = _describe(d)
            value = d
        findings.append(Finding(
            error_type=ErrorType.FLOATING, rule="floating", severity=severity, frame=box.frame, label=box.label,
            message=message, track_id=box.track_id, source_id=box.source_id, value=value, threshold=threshold,
            details=details,
        ))

    for track_id, boxes in no_evidence.items():
        if track_id is None:
            for box in boxes:
                findings.append(_no_evidence(box, [box]))
        else:
            findings.append(_no_evidence(boxes[0], boxes))
    return findings


def _no_evidence(first: Cuboid, boxes: list[Cuboid]) -> Finding:
    frames = sorted(b.frame for b in boxes)
    where = f"frame {frames[0]}" if len(frames) == 1 else f"{len(frames)} frame ({frames[0]}–{frames[-1]})"
    return Finding(
        error_type=ErrorType.FLOATING, rule="floating.no_evidence", severity=Severity.INFO, frame=first.frame,
        label=first.label, message=f"Thiếu bằng chứng mặt đất quanh box ở {where}: không kiểm được lơ lửng / lún",
        track_id=first.track_id, source_id=first.source_id if len(boxes) == 1 else None,
        value=float(len(boxes)), details={"frames": frames},
    )


def check_floating(cuboids: Iterable[Cuboid], config: Config, frames: FrameSource | None) -> list[Finding]:
    """Bộ phát hiện lơ lửng / lún. Cần point cloud: không có `frames` thì không chạy."""
    if frames is None:
        return []
    return floating_findings(estimate_box_ground(cuboids, config, frames), config)
