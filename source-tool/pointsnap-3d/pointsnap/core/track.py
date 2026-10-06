"""Phát hiện đứt track (việc B5, mục 4.1c của đề xuất).

Vị trí được đổi về hệ toàn cục bằng pose xe thu của từng frame (`FrameSource`); không có pose thì dùng tọa độ
của chính frame và mọi phát hiện chỉ ở mức Cảnh báo. Chỉ xét trên mặt phẳng x, y.

- `track.jump`: trong mỗi đoạn (không cắt qua keyframe `outside`), `r = ‖p − p̂‖` với `p̂` nội suy tuyến tính theo
  thời gian từ hai keyframe lân cận; ở hai đầu đoạn `p̂` được ngoại suy từ hai keyframe kế tiếp và ngưỡng nhân
  `END_FACTOR`. Một cú nhảy làm lệch cả box kề bên, nên với mỗi cụm vượt ngưỡng chỉ báo box mà khi bỏ đi các box
  còn lại khớp nhất. Đoạn chỉ có 2 box: kiểm thô tốc độ > `v_max_mps`.
- `track.split_id`: track A hết ở frame k, track B cùng class bắt đầu trong k+1 … k+`split_max_gap_frames`, vị trí
  đầu của B cách vị trí ngoại suy của A dưới `split_max_dist_m` → nghi một đối tượng bị tách hai ID (Cảnh báo).
- `track.long_interpolation`: hai keyframe liền nhau cách ≥ `min_frames` frame chỉ có box nội suy (không có
  `outside` ở giữa) trong khi đối tượng dịch > `min_motion_m` → nên thêm keyframe (Cảnh báo).
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass
from typing import Iterable

import numpy as np

from pointsnap.core.config import Config, TrackGroupConfig
from pointsnap.core.model import Cuboid, ErrorType, Finding, FrameSource, Severity, group_by_track


@dataclass(frozen=True)
class _Pose:
    sensor_to_world: np.ndarray | None
    timestamp: float


class _Positions:
    """Vị trí toàn cục (x, y) và thời điểm của box, cache pose theo frame."""

    def __init__(self, frames: FrameSource | None, interval_s: float) -> None:
        self._frames = frames
        self._interval = interval_s
        self._cache: dict[int, _Pose] = {}

    def _pose(self, frame: int) -> _Pose:
        if frame not in self._cache:
            matrix, timestamp = None, frame * self._interval
            if self._frames is not None:
                data = self._frames.frame_data(frame, with_points=False)
                matrix = data.sensor_to_world
                if data.timestamp is not None:
                    timestamp = data.timestamp
            self._cache[frame] = _Pose(matrix, timestamp)
        return self._cache[frame]

    @property
    def has_pose(self) -> bool:
        return self._frames is not None and all(p.sensor_to_world is not None for p in self._cache.values())

    def xy(self, box: Cuboid) -> np.ndarray:
        pose = self._pose(box.frame)
        if pose.sensor_to_world is None:
            return np.asarray(box.center[:2], dtype=np.float64)
        return (pose.sensor_to_world @ np.array([*box.center, 1.0]))[:2]

    def time(self, frame: int) -> float:
        return self._pose(frame).timestamp


def _segments(boxes: list[Cuboid]) -> list[list[Cuboid]]:
    """Cắt track thành các đoạn liên tục: keyframe `outside` kết thúc một đoạn."""
    segments: list[list[Cuboid]] = [[]]
    for box in boxes:
        if box.outside:
            if segments[-1]:
                segments.append([])
        else:
            segments[-1].append(box)
    return [s for s in segments if s]


def _finding(rule: str, severity: Severity, box: Cuboid, message: str, value: float, threshold: float,
             **details) -> Finding:
    return Finding(
        error_type=ErrorType.TRACK, rule=rule, severity=severity, frame=box.frame, label=box.label, message=message,
        track_id=box.track_id, source_id=box.source_id, value=value, threshold=threshold, details=details,
    )


END_FACTOR = 1.5
"""Ở hai đầu đoạn vị trí được ngoại suy (kém chắc hơn nội suy): ngưỡng nhảy nhân thêm hệ số này."""


def _loo_residual(xy: list[np.ndarray], times: list[float], order: list[int], i: int) -> tuple[float, bool] | None:
    """Độ lệch của box `order[i]` so với vị trí dự đoán từ các box lân cận trong `order` (không dùng chính nó).

    Box ở giữa: nội suy tuyến tính theo thời gian từ hai box kề. Box ở đầu / cuối: ngoại suy từ hai box kế tiếp.
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


def _jump_findings(segment: list[Cuboid], group: TrackGroupConfig, pos: _Positions, can_error: bool) -> list[Finding]:
    findings: list[Finding] = []
    n = len(segment)
    xy = [pos.xy(b) for b in segment]
    times = [pos.time(b.frame) for b in segment]
    order = list(range(n))
    raw = [_loo_residual(xy, times, order, i) for i in order]
    score = [_normalized(r) for r in raw]

    k = 0
    while k < n:
        if score[k] <= group.jump_warning_m:
            k += 1
            continue
        end = k
        while end + 1 < n and score[end + 1] > group.jump_warning_m:
            end += 1
        # Một cú nhảy làm lệch cả box kề bên. Chọn box mà khi bỏ đi, các box còn lại quanh cụm khớp nhất.
        best: tuple[float, float, int] | None = None
        for c in range(max(0, k - 1), min(n, end + 2)):
            rest = [i for i in order if i != c]
            window = [j for j, i in enumerate(rest) if k - 2 <= i <= end + 2]
            remaining = max((_normalized(_loo_residual(xy, times, rest, j)) for j in window), default=0.0)
            candidate = (remaining, -score[c], c)
            if best is None or candidate < best:
                best = candidate
        peak = best[2]
        r, at_end = raw[peak] if raw[peak] is not None else (0.0, False)
        factor = END_FACTOR if at_end else 1.0
        if r > group.jump_warning_m * factor:
            severity = Severity.ERROR if can_error and r > group.jump_error_m * factor else Severity.WARNING
            box = segment[peak]
            how = "ngoại suy (đầu/cuối đoạn track)" if at_end else "nội suy từ hai keyframe lân cận"
            findings.append(_finding(
                "track.jump", severity, box,
                f"Tâm box lệch {r:.2f} m khỏi vị trí {how} (nghi nhảy vị trí)",
                r, (group.jump_error_m if severity is Severity.ERROR else group.jump_warning_m) * factor,
            ))
        k = end + 1

    # Đoạn chỉ có 2 box: không dự đoán được, chỉ kiểm thô bằng tốc độ tối đa của class.
    if n == 2:
        dt = abs(times[1] - times[0])
        speed = float(np.linalg.norm(xy[1] - xy[0])) / dt if dt > 0 else 0.0
        if speed > group.v_max_mps:
            box = segment[1]
            findings.append(_finding(
                "track.jump", Severity.WARNING, box,
                f"Box dịch {speed:.1f} m/s so với frame {segment[0].frame} "
                f"(tối đa {group.v_max_mps:.0f} m/s cho {box.label})",
                speed, group.v_max_mps,
            ))
    return findings

def _interpolation_findings(segment: list[Cuboid], config: Config, pos: _Positions) -> list[Finding]:
    cfg = config.track.long_interpolation
    findings: list[Finding] = []
    for a, b in zip(segment, segment[1:]):
        missing = b.frame - a.frame - 1
        if missing < cfg.min_frames:
            continue
        motion = float(np.linalg.norm(pos.xy(b) - pos.xy(a)))
        if motion <= cfg.min_motion_m:
            continue
        findings.append(_finding(
            "track.long_interpolation", Severity.WARNING, a,
            f"{missing} frame liền ({a.frame + 1}–{b.frame - 1}) chỉ có box nội suy trong khi đối tượng dịch "
            f"{motion:.1f} m: nên thêm keyframe",
            float(missing), float(cfg.min_frames), next_keyframe=b.frame,
        ))
    return findings


def _split_findings(segments_by_track: dict[int, list[list[Cuboid]]], config: Config, pos: _Positions,
                    last_frame: int) -> list[Finding]:
    cfg = config.track
    starts: list[tuple[int, Cuboid]] = []  # (track_id, box đầu tiên của track)
    ends: list[tuple[int, list[Cuboid]]] = []  # (track_id, đoạn cuối của track)
    for track_id, segments in segments_by_track.items():
        starts.append((track_id, segments[0][0]))
        if segments[-1][-1].frame < last_frame:
            ends.append((track_id, segments[-1]))

    findings: list[Finding] = []
    for b_id, b_first in starts:
        group = cfg.group_for(b_first.label)
        if group is None:
            continue
        best: tuple[float, int, Cuboid] | None = None
        for a_id, a_segment in ends:
            a_last = a_segment[-1]
            gap = b_first.frame - a_last.frame
            if a_id == b_id or a_last.label != b_first.label or not 1 <= gap <= cfg.split_max_gap_frames:
                continue
            predicted = pos.xy(a_last)
            if len(a_segment) >= 2:
                prev = a_segment[-2]
                dt = pos.time(a_last.frame) - pos.time(prev.frame)
                if dt > 0:
                    velocity = (pos.xy(a_last) - pos.xy(prev)) / dt
                    predicted = predicted + velocity * (pos.time(b_first.frame) - pos.time(a_last.frame))
            distance = float(np.linalg.norm(pos.xy(b_first) - predicted))
            if distance < group.split_max_dist_m and (best is None or distance < best[0]):
                best = (distance, a_id, a_last)
        if best is not None:
            distance, a_id, a_last = best
            findings.append(_finding(
                "track.split_id", Severity.WARNING, b_first,
                f"Track #{b_id} bắt đầu cách vị trí dự đoán của track #{a_id} (hết ở frame {a_last.frame}) "
                f"{distance:.2f} m: nghi cùng một đối tượng bị tách hai ID",
                distance, group.split_max_dist_m, previous_track_id=a_id,
            ))
    return findings


def check_track(cuboids: Iterable[Cuboid], config: Config, frames: FrameSource | None = None) -> list[Finding]:
    cuboids = list(cuboids)
    if not cuboids:
        return []
    pos = _Positions(frames, config.track.keyframe_interval_s)
    tracks = group_by_track(cuboids)
    segments_by_track = {tid: segs for tid, boxes in tracks.items() if (segs := _segments(boxes))}

    findings: list[Finding] = []
    for segments in segments_by_track.values():
        group = config.track.group_for(segments[0][0].label)
        if group is None:
            continue
        for segment in segments:
            findings.extend(_jump_findings(segment, group, pos, can_error=frames is not None))
            if config.track.long_interpolation.enabled:
                findings.extend(_interpolation_findings(segment, config, pos))

    last_frame = max(c.frame for c in cuboids)
    findings.extend(_split_findings(segments_by_track, config, pos, last_frame))
    if frames is not None and not pos.has_pose:
        findings = [dataclasses.replace(f, severity=Severity.WARNING) if f.severity is Severity.ERROR else f
                    for f in findings]
    return findings
