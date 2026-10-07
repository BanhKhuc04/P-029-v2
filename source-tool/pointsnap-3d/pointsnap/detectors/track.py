"""Bộ phát hiện lỗi đứt track (việc B5, chỉnh ở A10).

Ba kiểu phát hiện:
1. Kiểu 1 (`track.jump`): Nhảy vị trí bất thường.
   - Track được cắt thành các đoạn tại keyframe `outside` (đối tượng vắng mặt): không nội suy qua đoạn vắng.
   - Box giữa đoạn: lệch so với vị trí nội suy tuyến tính theo thời gian từ 2 keyframe lân cận. Box ở đầu / cuối
     đoạn: so với vị trí ngoại suy từ 2 keyframe kế tiếp, ngưỡng nhân `END_FACTOR`.
   - Một cú nhảy làm lệch cả box kề bên, nên với mỗi cụm vượt ngưỡng chỉ báo box mà khi bỏ đi các box còn lại khớp
     nhất. Đoạn chỉ có 2 box: kiểm thô tốc độ > `v_max_mps`.
   - Ngưỡng theo nhóm class: vehicle (1.0/2.0 m), two_wheeler (0.75/1.5 m), pedestrian (0.5/1.0 m), static (0.3/0.6 m).
   - Nếu không có sensor_to_world, chỉ báo ở mức Cảnh báo.
2. Kiểu 2 (`track.split_id`): Nghi ngờ tách ID khi track A kết thúc (trước frame cuối) và track B cùng class bắt
   đầu ngay gần vị trí ngoại suy của A. Mỗi track B ghép với track A gần nhất. Mức Cảnh báo.
3. Kiểu 3 (`track.long_interpolation`, bật bằng `long_interpolation.enabled`): ≥ `min_frames` frame liền chỉ có box
   nội suy (không có `outside` ở giữa) trong khi đối tượng dịch > `min_motion_m`. Mức Cảnh báo.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Mapping, Sequence

import numpy as np

from pointsnap.core.geometry import transform_points
from pointsnap.core.model import Cuboid, ErrorType, Finding, Severity, group_by_track

if TYPE_CHECKING:
    from pointsnap.core.config import TrackConfig, TrackGroupConfig

END_FACTOR = 1.5
"""Ở hai đầu đoạn vị trí được ngoại suy (kém chắc hơn nội suy): ngưỡng nhảy nhân thêm hệ số này."""


def _get_world_centers(
    cuboids: Sequence[Cuboid],
    sensor_to_world_by_frame: Mapping[int, np.ndarray] | None,
) -> tuple[np.ndarray, bool]:
    """Lấy toạ độ tâm (N, 3) trong hệ toàn cục.

    Trả về (points, has_world): has_world=True nếu đổi được sang hệ toàn cục.
    """
    has_world = False
    centers = np.array([c.center for c in cuboids], dtype=np.float64)
    if sensor_to_world_by_frame is not None:
        has_all_transforms = all(c.frame in sensor_to_world_by_frame for c in cuboids)
        if has_all_transforms:
            world_pts = []
            for c in cuboids:
                mat = sensor_to_world_by_frame[c.frame]
                w = transform_points(np.array([c.center]), mat)[0]
                world_pts.append(w)
            centers = np.array(world_pts, dtype=np.float64)
            has_world = True

    return centers, has_world


def _time(frame: int, config: TrackConfig, timestamps_by_frame: Mapping[int, float] | None) -> float:
    if timestamps_by_frame and frame in timestamps_by_frame:
        return float(timestamps_by_frame[frame])
    return float(frame) * config.keyframe_interval_s


def _segments(track_boxes: Sequence[Cuboid]) -> list[list[Cuboid]]:
    """Cắt track (sắp theo frame) thành các đoạn liên tục: keyframe `outside` kết thúc một đoạn."""
    segments: list[list[Cuboid]] = [[]]
    for box in sorted(track_boxes, key=lambda b: b.frame):
        if box.outside:
            if segments[-1]:
                segments.append([])
        else:
            segments[-1].append(box)
    return [s for s in segments if s]


def _loo_residual(xy: np.ndarray, times: np.ndarray, order: list[int], i: int) -> tuple[float, bool] | None:
    """Độ lệch (x, y) của box `order[i]` so với vị trí dự đoán từ các box lân cận trong `order`, không dùng chính nó.

    Box ở giữa: nội suy tuyến tính theo thời gian. Box ở đầu / cuối: ngoại suy từ hai box kế tiếp.
    Trả về `(độ lệch, là_đầu_mút)`, hoặc `None` nếu không đủ box để dự đoán.
    """
    n = len(order)
    k = order[i]
    if 0 < i < n - 1:
        a, b = order[i - 1], order[i + 1]
        span = times[b] - times[a]
        ratio = (times[k] - times[a]) / span if span > 0 else 0.5
        return float(np.linalg.norm(xy[k] - (xy[a] + (xy[b] - xy[a]) * ratio))), False
    if n < 3:
        return None
    a, b = (order[1], order[2]) if i == 0 else (order[n - 2], order[n - 3])
    dt = times[a] - times[b]
    ratio = (times[k] - times[a]) / dt if dt != 0 else 1.0
    return float(np.linalg.norm(xy[k] - (xy[a] + (xy[a] - xy[b]) * ratio))), True


def _normalized(result: tuple[float, bool] | None) -> float:
    if result is None:
        return 0.0
    r, at_end = result
    return r / END_FACTOR if at_end else r


def _segment_jumps(
    segment: list[Cuboid], grp: TrackGroupConfig, xy: np.ndarray, times: np.ndarray, has_world: bool,
) -> list[Finding]:
    n = len(segment)
    order = list(range(n))
    raw = [_loo_residual(xy, times, order, i) for i in order]
    score = [_normalized(r) for r in raw]
    findings: list[Finding] = []

    k = 0
    while k < n:
        if score[k] < grp.jump_warning_m:
            k += 1
            continue
        end = k
        while end + 1 < n and score[end + 1] >= grp.jump_warning_m:
            end += 1
        # Chọn box mà khi bỏ đi, các box còn lại quanh cụm khớp nhất.
        best: tuple[float, float, int] | None = None
        for c in range(max(0, k - 1), min(n, end + 2)):
            rest = [i for i in order if i != c]
            window = [j for j, i in enumerate(rest) if k - 2 <= i <= end + 2]
            remaining = max((_normalized(_loo_residual(xy, times, rest, j)) for j in window), default=0.0)
            candidate = (remaining, -score[c], c)
            if best is None or candidate < best:
                best = candidate
        peak = best[2]
        dev, at_end = raw[peak] if raw[peak] is not None else (0.0, False)
        factor = END_FACTOR if at_end else 1.0
        if dev >= grp.jump_warning_m * factor:
            if dev >= grp.jump_error_m * factor and has_world:
                severity, thresh = Severity.ERROR, grp.jump_error_m * factor
            else:
                severity = Severity.WARNING
                thresh = grp.jump_warning_m * factor if dev < grp.jump_error_m * factor else grp.jump_error_m * factor
            how = "ngoại suy (đầu / cuối đoạn track)" if at_end else "nội suy từ 2 frame lân cận"
            msg = f"Tâm box nhảy vị trí {dev:.2f} m so với vị trí {how} (ngưỡng {thresh:.1f} m)"
            if not has_world:
                msg += " [chưa có toạ độ toàn cục]"
            b = segment[peak]
            findings.append(Finding(
                error_type=ErrorType.TRACK, rule="track.jump", severity=severity, frame=b.frame, label=b.label,
                track_id=b.track_id, source_id=b.source_id, message=msg, value=float(dev), threshold=float(thresh),
                details={"deviation_m": dev, "has_world_pose": has_world, "segment_end": at_end,
                         "cluster_frames": [segment[i].frame for i in range(k, end + 1)]},
            ))
        k = end + 1

    if n == 2:
        dt = abs(times[1] - times[0])
        speed = float(np.linalg.norm(xy[1] - xy[0])) / dt if dt > 0 else 0.0
        if speed > grp.v_max_mps:
            b = segment[1]
            findings.append(Finding(
                error_type=ErrorType.TRACK, rule="track.jump", severity=Severity.WARNING, frame=b.frame,
                label=b.label, track_id=b.track_id, source_id=b.source_id,
                message=(f"Box dịch {speed:.1f} m/s so với frame {segment[0].frame} "
                         f"(tối đa {grp.v_max_mps:.0f} m/s cho {b.label})"),
                value=speed, threshold=grp.v_max_mps, details={"speed_mps": speed, "has_world_pose": has_world},
            ))
    return findings


def detect_track_jumps_for_track(
    track_boxes: Sequence[Cuboid],
    config: TrackConfig,
    sensor_to_world_by_frame: Mapping[int, np.ndarray] | None = None,
    timestamps_by_frame: Mapping[int, float] | None = None,
) -> list[Finding]:
    """Kiểm tra kiểu 1: nhảy vị trí trong một track."""
    active = [b for b in track_boxes if not b.outside]
    if len(active) < 2:
        return []
    grp = config.group_for(active[0].label)
    if grp is None:
        return []

    findings: list[Finding] = []
    for segment in _segments(track_boxes):
        if len(segment) < 2:
            continue
        centers, has_world = _get_world_centers(segment, sensor_to_world_by_frame)
        times = np.array([_time(b.frame, config, timestamps_by_frame) for b in segment])
        findings.extend(_segment_jumps(segment, grp, centers[:, :2], times, has_world))
    return findings


def detect_long_interpolation(
    track_boxes: Sequence[Cuboid],
    config: TrackConfig,
    sensor_to_world_by_frame: Mapping[int, np.ndarray] | None = None,
) -> list[Finding]:
    """Kiểm tra kiểu 3: đoạn dài chỉ có box nội suy trong khi đối tượng đang chạy."""
    cfg = config.long_interpolation
    findings: list[Finding] = []
    for segment in _segments(track_boxes):
        if len(segment) < 2:
            continue
        centers, _ = _get_world_centers(segment, sensor_to_world_by_frame)
        for i in range(len(segment) - 1):
            a, b = segment[i], segment[i + 1]
            missing = b.frame - a.frame - 1
            motion = float(np.linalg.norm(centers[i + 1, :2] - centers[i, :2]))
            if missing < cfg.min_frames or motion <= cfg.min_motion_m:
                continue
            findings.append(Finding(
                error_type=ErrorType.TRACK, rule="track.long_interpolation", severity=Severity.WARNING,
                frame=a.frame, label=a.label, track_id=a.track_id, source_id=a.source_id,
                message=(f"{missing} frame liền ({a.frame + 1}–{b.frame - 1}) chỉ có box nội suy trong khi đối tượng "
                         f"dịch {motion:.1f} m: nên thêm keyframe"),
                value=float(missing), threshold=float(cfg.min_frames),
                details={"next_keyframe": b.frame, "motion_m": motion},
            ))
    return findings


def detect_track_splits(
    tracks: Mapping[int, Sequence[Cuboid]],
    config: TrackConfig,
    sensor_to_world_by_frame: Mapping[int, np.ndarray] | None = None,
    timestamps_by_frame: Mapping[int, float] | None = None,
) -> list[Finding]:
    """Kiểm tra kiểu 2: nghi ngờ tách ID giữa các track cùng class."""
    last_frame = max((b.frame for boxes in tracks.values() for b in boxes), default=0)
    track_summaries = []

    for tid, boxes in tracks.items():
        segments = _segments(boxes)
        if not segments:
            continue
        first_b, tail = segments[0][0], segments[-1]
        last_b = tail[-1]
        centers, _ = _get_world_centers(tail, sensor_to_world_by_frame)
        first_pos = _get_world_centers([first_b], sensor_to_world_by_frame)[0][0]
        t_last = _time(last_b.frame, config, timestamps_by_frame)

        # Vận tốc ước lượng ở cuối track A
        velocity = np.zeros(3)
        if len(tail) >= 2:
            dt = t_last - _time(tail[-2].frame, config, timestamps_by_frame)
            if dt > 0:
                velocity = (centers[-1] - centers[-2]) / dt

        track_summaries.append({
            "track_id": tid,
            "label": first_b.label,
            "first_frame": first_b.frame,
            "last_frame": last_b.frame,
            "first_time": _time(first_b.frame, config, timestamps_by_frame),
            "last_time": t_last,
            "first_pos": first_pos,
            "last_pos": centers[-1],
            "velocity": velocity,
            "first_box": first_b,
        })

    findings: list[Finding] = []
    max_gap = config.split_max_gap_frames

    for b in track_summaries:
        grp = config.group_for(b["label"])
        if grp is None:
            continue
        best: tuple[float, dict] | None = None
        for a in track_summaries:
            if a is b or a["label"] != b["label"] or a["last_frame"] >= last_frame:
                continue
            frame_gap = b["first_frame"] - a["last_frame"]
            if not 1 <= frame_gap <= max_gap:
                continue
            extrapolated_pos = a["last_pos"] + a["velocity"] * (b["first_time"] - a["last_time"])
            dist = float(np.linalg.norm(b["first_pos"][:2] - extrapolated_pos[:2]))
            if dist <= grp.split_max_dist_m and (best is None or dist < best[0]):
                best = (dist, a)
        if best is None:
            continue
        dist, a = best
        first_box = b["first_box"]
        findings.append(Finding(
            error_type=ErrorType.TRACK, rule="track.split_id", severity=Severity.WARNING, frame=first_box.frame,
            label=first_box.label, track_id=b["track_id"], source_id=first_box.source_id,
            message=(f"Track {a['track_id']} kết thúc ở frame {a['last_frame']} và track {b['track_id']} cùng class "
                     f"bắt đầu ở frame {b['first_frame']} cách vị trí ngoại suy {dist:.2f} m (nghi tách ID)"),
            value=dist, threshold=grp.split_max_dist_m,
            details={"previous_track_id": a["track_id"], "extrapolated_dist": dist,
                     "frame_gap": b["first_frame"] - a["last_frame"]},
        ))

    return findings


def detect_track_errors(
    cuboids: Sequence[Cuboid],
    config: TrackConfig,
    sensor_to_world_by_frame: Mapping[int, np.ndarray] | None = None,
    timestamps_by_frame: Mapping[int, float] | None = None,
) -> list[Finding]:
    """Phát hiện lỗi đứt track (nhảy vị trí, tách ID, khoảng nội suy dài) trên tập box."""
    tracks = group_by_track(cuboids)
    findings: list[Finding] = []

    for track_boxes in tracks.values():
        # Kiểu 1: nhảy vị trí
        findings.extend(detect_track_jumps_for_track(
            track_boxes, config, sensor_to_world_by_frame=sensor_to_world_by_frame,
            timestamps_by_frame=timestamps_by_frame,
        ))
        # Kiểu 3: khoảng nội suy dài
        if config.long_interpolation.enabled and config.group_for(track_boxes[0].label) is not None:
            findings.extend(detect_long_interpolation(track_boxes, config, sensor_to_world_by_frame))

    # Kiểu 2: tách ID
    findings.extend(detect_track_splits(
        tracks, config, sensor_to_world_by_frame=sensor_to_world_by_frame, timestamps_by_frame=timestamps_by_frame,
    ))

    return findings
