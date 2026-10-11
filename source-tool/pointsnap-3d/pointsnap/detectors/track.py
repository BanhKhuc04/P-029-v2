"""Bộ phát hiện lỗi đứt track (việc B5, chỉnh ở A10).

Ba kiểu phát hiện:
1. Kiểu 1 (`track.jump`): Nhảy vị trí bất thường.
   - Xét mọi keyframe có mặt theo thời gian, nội suy cả qua đoạn đối tượng tạm vắng (`outside`).
   - Box giữa track: lệch so với vị trí nội suy tuyến tính theo thời gian từ 2 keyframe lân cận. Box ở đầu / cuối
     track: so với vị trí ngoại suy từ 2 keyframe kế tiếp, ngưỡng nhân `END_FACTOR` × độ dài khoảng ngoại suy (so với
     khoảng giữa 2 keyframe đó).
   - Một cú nhảy làm lệch cả box kề bên, nên với mỗi cụm vượt ngưỡng chỉ báo box mà khi bỏ đi các box còn lại khớp
     nhất. Track chỉ có 2 box: kiểm thô tốc độ > `v_max_mps`.
   - Ngưỡng theo nhóm class: vehicle (1.0/2.0 m), two_wheeler (0.75/1.5 m), pedestrian (0.5/1.0 m), static (0.3/0.6 m).
   - Nếu không có sensor_to_world, chỉ báo ở mức Cảnh báo.
2. Kiểu 2 (`track.split_id`): Nghi ngờ tách ID khi track A kết thúc (trước frame cuối) và track B cùng class bắt
   đầu ngay gần vị trí ngoại suy của A. Mỗi track B ghép với track A gần nhất. Mức Cảnh báo.
3. Kiểu 3 (`track.long_interpolation`, bật bằng `long_interpolation.enabled`): ≥ `min_frames` frame liền chỉ có box
   nội suy (không có `outside` ở giữa) trong khi đối tượng dịch > `min_motion_m`. Mức Cảnh báo.
4. Theo spec 4.4 (C2, `detect_track_spec`): `track.reuse_id` (dùng lại track sau `outside`), `track.occluded_long`
   (occluded quá `max_occluded_frames` frame). Mức Cảnh báo.
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


def _end_factor(horizon: float) -> float:
    """Hệ số ngưỡng ở đầu / cuối track. `horizon` = khoảng ngoại suy / khoảng giữa hai box dùng để ước lượng vận tốc.

    Sai số vận tốc nhân lên theo khoảng ngoại suy: box đầu ở frame 1 mà hai box kế tiếp ở frame 5, 6 thì vị trí dự đoán
    kém chắc gấp ~4 lần. Trên 5 cảnh tinh chỉnh, 8 / 12 báo nhầm `track.jump` ở hai đầu track là ca này; nhân ngưỡng theo
    `horizon` bỏ 7 mục (cả 4 mục mức Lỗi) mà không mất lỗi nhảy chèn nào (100 vòng chèn lỗi).
    """
    return END_FACTOR * max(1.0, horizon)


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


def _loo_residual(xy: np.ndarray, times: np.ndarray, order: list[int], i: int) -> tuple[float, float] | None:
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
        return float(np.linalg.norm(xy[k] - (xy[a] + (xy[b] - xy[a]) * ratio))), 1.0
    if n < 3:
        return None
    a, b = (order[1], order[2]) if i == 0 else (order[n - 2], order[n - 3])
    dt = times[a] - times[b]
    ratio = (times[k] - times[a]) / dt if dt != 0 else 1.0
    return float(np.linalg.norm(xy[k] - (xy[a] + (xy[a] - xy[b]) * ratio))), _end_factor(abs(ratio))


def _speed(xy: np.ndarray, times: np.ndarray, pair: list[int]) -> float:
    a, b = pair
    dt = abs(times[b] - times[a])
    return float(np.linalg.norm(xy[b] - xy[a])) / dt if dt > 0 else float("inf")


def _normalized(result: tuple[float, float] | None) -> float:
    if result is None:
        return 0.0
    r, factor = result
    return r / factor


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
        # Chọn box mà khi bỏ đi, các box còn lại quanh cụm khớp nhất. Track 3 box: bỏ box nào cũng còn 2 box, không
        # kiểm được; chọn giả thuyết để 2 box còn lại có tốc độ thấp nhất (box giữa nhảy 4 m thì hai đầu "chạy" 8 m mỗi
        # keyframe nếu đổ lỗi cho một đầu).
        best: tuple[float, float, float, int] | None = None
        for c in range(max(0, k - 1), min(n, end + 2)):
            rest = [i for i in order if i != c]
            window = [j for j, i in enumerate(rest) if k - 2 <= i <= end + 2]
            remaining = max((_normalized(_loo_residual(xy, times, rest, j)) for j in window), default=0.0)
            speed = _speed(xy, times, rest) if len(rest) == 2 else 0.0
            candidate = (remaining, speed, -score[c], c)
            if best is None or candidate < best:
                best = candidate
        peak = best[3]
        dev, factor = raw[peak] if raw[peak] is not None else (0.0, 1.0)
        at_end = factor != 1.0
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
    active = [b for b in track_boxes if b.visible]
    if len(active) < 2:
        return []
    grp = config.group_for(active[0].label)
    if grp is None:
        return []

    # Vị trí liên tục theo thời gian kể cả khi đối tượng tạm vắng (keyframe `outside`), nên nội suy qua đoạn vắng:
    # bắt được cú nhảy ngay sát đoạn vắng mà không tăng báo nhầm (đo trên 5 cảnh kiểm tra).
    findings: list[Finding] = []
    for segment in [sorted(active, key=lambda b: b.frame)]:
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
            if a.occluded or b.occluded:
                continue  # đoạn vật bị che: không thêm keyframe được (spec 4.4.5)
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


def detect_track_spec(track_boxes: Sequence[Cuboid], config: TrackConfig) -> list[Finding]:
    """Luật track theo spec 4.4 (C2), mức Cảnh báo.

    - `track.reuse_id`: track đã kết thúc bằng keyframe `outside` rồi lại có box ở frame sau. Spec 4.4.3: sau khi kết
      thúc track_id không gán box cho vật đó nữa; 4.4.4: vật xuất hiện lại sau khi track kết thúc phải có track_id mới.
      Vắng ngắn (≤ `max_occluded_frames`) thường là vật bị che: nên bỏ `outside`, đánh dấu `occluded`.
    - `track.occluded_long`: các frame liên tiếp mang `occluded` dài hơn `max_occluded_frames` (spec: occluded chỉ cho
      che khuất tạm thời ≤ 6 frame; lâu hơn thì kết thúc track).
    """
    limit = config.max_occluded_frames
    boxes = sorted(track_boxes, key=lambda b: b.frame)
    findings: list[Finding] = []
    ended_at: int | None = None
    for box in boxes:
        if box.outside:
            ended_at = box.frame if ended_at is None else ended_at
            continue
        if ended_at is not None:
            gap = box.frame - ended_at
            advice = ("vật chỉ bị che tạm thời thì bỏ outside, đánh dấu occluded (spec 4.4.5)" if gap <= limit
                      else "spec 4.4.3–4.4.4: không dùng lại track_id sau khi đã kết thúc, tách phần sau thành track mới")
            findings.append(Finding(
                error_type=ErrorType.TRACK, rule="track.reuse_id", severity=Severity.WARNING, frame=box.frame,
                label=box.label, track_id=box.track_id, source_id=box.source_id,
                message=f"Track đã kết thúc (outside) ở frame {ended_at} rồi xuất hiện lại ở frame {box.frame} "
                        f"sau {gap} frame vắng: {advice}",
                value=float(gap), threshold=float(limit), details={"ended_at": ended_at},
            ))
            ended_at = None
    start: Cuboid | None = None
    for box in boxes + [None]:
        hidden = box is not None and not box.outside and bool(box.attrs.get("occluded"))
        if hidden and start is None:
            start = box
        elif not hidden and start is not None:
            end = box.frame if box is not None else boxes[-1].frame + 1
            length = end - start.frame
            if length > limit:
                findings.append(Finding(
                    error_type=ErrorType.TRACK, rule="track.occluded_long", severity=Severity.WARNING,
                    frame=start.frame, label=start.label, track_id=start.track_id, source_id=start.source_id,
                    message=f"Box đánh occluded {length} frame liền (frame {start.frame}–{end - 1}), quá {limit} frame: "
                            f"spec 4.4.5 chỉ dùng occluded cho che khuất tạm thời; kết thúc track nếu không còn cơ sở "
                            f"xác định cùng vật",
                    value=float(length), threshold=float(limit), details={"end_frame": end - 1},
                ))
            start = None
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

    # Luật track theo spec 4.4 (C2)
    for track_boxes in tracks.values():
        findings.extend(detect_track_spec(track_boxes, config))

    # Kiểu 2: tách ID
    findings.extend(detect_track_splits(
        tracks, config, sensor_to_world_by_frame=sensor_to_world_by_frame, timestamps_by_frame=timestamps_by_frame,
    ))

    return findings
