"""Bộ phát hiện lỗi đứt track (việc B5).

Hai kiểu phát hiện:
1. Kiểu 1 (`track.jump`): Nhảy vị trí bất thường so với nội suy tuyến tính từ 2 frame lân cận.
   - Gom các frame lệch liên tiếp thành cụm, chỉ báo frame có độ lệch lớn nhất trong cụm.
   - Ngưỡng theo nhóm class: vehicle (1.0/2.0 m), two_wheeler (0.75/1.5 m), pedestrian (0.5/1.0 m), static (0.3/0.6 m).
   - Nếu không có sensor_to_world, chỉ báo ở mức Cảnh báo.
2. Kiểu 2 (`track.split_id`): Nghi ngờ tách ID khi track A kết thúc và track B cùng class bắt đầu ngay gần đó.
   - Mức Cảnh báo.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Iterable, Mapping, Sequence

import numpy as np

from pointsnap.core.geometry import transform_points
from pointsnap.core.model import Cuboid, ErrorType, Finding, Severity, group_by_track

if TYPE_CHECKING:
    from pointsnap.core.config import TrackConfig, TrackGroupConfig


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


def detect_track_jumps_for_track(
    track_boxes: Sequence[Cuboid],
    config: TrackConfig,
    sensor_to_world_by_frame: Mapping[int, np.ndarray] | None = None,
    timestamps_by_frame: Mapping[int, float] | None = None,
) -> list[Finding]:
    """Kiểm tra kiểu 1: nhảy vị trí trong một track."""
    active = [b for b in track_boxes if not b.outside]
    if len(active) < 3:
        return []

    label = active[0].label
    grp = config.group_for(label)
    if grp is None:
        return []

    centers, has_world = _get_world_centers(active, sensor_to_world_by_frame)

    times = []
    for b in active:
        if timestamps_by_frame and b.frame in timestamps_by_frame:
            times.append(timestamps_by_frame[b.frame])
        else:
            times.append(float(b.frame) * config.keyframe_interval_s)
    times = np.array(times)

    n = len(active)
    deviations = np.zeros(n)

    # Tính độ lệch nội suy cho các frame bên trong (1 .. n-2)
    for i in range(1, n - 1):
        dt_total = times[i + 1] - times[i - 1]
        if dt_total <= 0.0:
            continue
        alpha = (times[i] - times[i - 1]) / dt_total
        interp_pos = centers[i - 1] + alpha * (centers[i + 1] - centers[i - 1])
        deviations[i] = float(np.linalg.norm(centers[i] - interp_pos))

    # Gom các frame liên tiếp bị lệch >= jump_warning_m thành cụm
    warn_thresh = grp.jump_warning_m
    err_thresh = grp.jump_error_m

    clusters: list[list[int]] = []
    current_cluster: list[int] = []

    for i in range(1, n - 1):
        if deviations[i] >= warn_thresh:
            current_cluster.append(i)
        else:
            if current_cluster:
                clusters.append(current_cluster)
                current_cluster = []
    if current_cluster:
        clusters.append(current_cluster)

    findings: list[Finding] = []

    # Với mỗi cụm, chỉ báo frame có độ lệch lớn nhất
    for cluster in clusters:
        peak_idx = max(cluster, key=lambda idx: deviations[idx])
        dev = deviations[peak_idx]
        b = active[peak_idx]

        if dev >= err_thresh and has_world:
            severity = Severity.ERROR
            thresh = err_thresh
        else:
            # Không có toạ độ thế giới hoặc chỉ vượt ngưỡng cảnh báo -> Severity.WARNING
            severity = Severity.WARNING
            thresh = warn_thresh if dev < err_thresh else err_thresh

        msg = (
            f"Tâm box nhảy vị trí {dev:.2f} m so với vị trí nội suy từ 2 frame lân cận "
            f"(ngưỡng {thresh:.1f} m)"
        )
        if not has_world:
            msg += " [chưa có toạ độ toàn cục]"

        findings.append(
            Finding(
                error_type=ErrorType.TRACK,
                rule="track.jump",
                severity=severity,
                frame=b.frame,
                label=b.label,
                track_id=b.track_id,
                source_id=b.source_id,
                message=msg,
                value=float(dev),
                threshold=float(thresh),
                details={
                    "deviation_m": dev,
                    "has_world_pose": has_world,
                    "cluster_frames": [active[c].frame for c in cluster],
                },
            )
        )

    return findings


def detect_track_splits(
    tracks: Mapping[int, Sequence[Cuboid]],
    config: TrackConfig,
    sensor_to_world_by_frame: Mapping[int, np.ndarray] | None = None,
    timestamps_by_frame: Mapping[int, float] | None = None,
) -> list[Finding]:
    """Kiểm tra kiểu 2: nghi ngờ tách ID giữa các track cùng class."""
    track_summaries = []

    for tid, boxes in tracks.items():
        active = [b for b in boxes if not b.outside]
        if not active:
            continue
        first_b, last_b = active[0], active[-1]
        centers, has_world = _get_world_centers(active, sensor_to_world_by_frame)
        t_first = timestamps_by_frame.get(first_b.frame, first_b.frame * config.keyframe_interval_s) if timestamps_by_frame else first_b.frame * config.keyframe_interval_s
        t_last = timestamps_by_frame.get(last_b.frame, last_b.frame * config.keyframe_interval_s) if timestamps_by_frame else last_b.frame * config.keyframe_interval_s

        # Vận tốc ước lượng ở cuối track A
        if len(active) >= 2:
            t_prev = timestamps_by_frame.get(active[-2].frame, active[-2].frame * config.keyframe_interval_s) if timestamps_by_frame else active[-2].frame * config.keyframe_interval_s
            dt = t_last - t_prev
            velocity = (centers[-1] - centers[-2]) / dt if dt > 0 else np.zeros(3)
        else:
            velocity = np.zeros(3)

        track_summaries.append({
            "track_id": tid,
            "label": first_b.label,
            "first_frame": first_b.frame,
            "last_frame": last_b.frame,
            "first_time": t_first,
            "last_time": t_last,
            "first_pos": centers[0],
            "last_pos": centers[-1],
            "velocity": velocity,
            "first_box": first_b,
        })

    findings: list[Finding] = []
    max_gap = config.split_max_gap_frames

    for i, a in enumerate(track_summaries):
        grp = config.group_for(a["label"])
        if grp is None:
            continue
        max_dist = grp.split_max_dist_m

        for j, b in enumerate(track_summaries):
            if i == j or a["label"] != b["label"]:
                continue

            frame_gap = b["first_frame"] - a["last_frame"]
            if 1 <= frame_gap <= max_gap:
                dt = b["first_time"] - a["last_time"]
                extrapolated_pos = a["last_pos"] + a["velocity"] * dt
                dist = float(np.linalg.norm(b["first_pos"] - extrapolated_pos))

                if dist <= max_dist:
                    first_box = b["first_box"]
                    msg = (
                        f"Track {a['track_id']} kết thúc ở frame {a['last_frame']} và "
                        f"track {b['track_id']} cùng class bắt đầu ở frame {b['first_frame']} "
                        f"cách vị trí ngoại suy {dist:.2f} m (nghi tách ID)"
                    )
                    findings.append(
                        Finding(
                            error_type=ErrorType.TRACK,
                            rule="track.split_id",
                            severity=Severity.WARNING,
                            frame=first_box.frame,
                            label=first_box.label,
                            track_id=b["track_id"],
                            source_id=first_box.source_id,
                            message=msg,
                            value=dist,
                            threshold=max_dist,
                            details={
                                "previous_track_id": a["track_id"],
                                "extrapolated_dist": dist,
                                "frame_gap": frame_gap,
                            },
                        )
                    )

    return findings


def detect_track_errors(
    cuboids: Sequence[Cuboid],
    config: TrackConfig,
    sensor_to_world_by_frame: Mapping[int, np.ndarray] | None = None,
    timestamps_by_frame: Mapping[int, float] | None = None,
) -> list[Finding]:
    """Phát hiện lỗi đứt track (cả nhảy vị trí và tách ID) trên tập box."""
    tracks = group_by_track(cuboids)
    findings: list[Finding] = []

    # Kiểu 1: nhảy vị trí
    for track_boxes in tracks.values():
        findings.extend(
            detect_track_jumps_for_track(
                track_boxes,
                config,
                sensor_to_world_by_frame=sensor_to_world_by_frame,
                timestamps_by_frame=timestamps_by_frame,
            )
        )

    # Kiểu 2: tách ID
    findings.extend(
        detect_track_splits(
            tracks,
            config,
            sensor_to_world_by_frame=sensor_to_world_by_frame,
            timestamps_by_frame=timestamps_by_frame,
        )
    )

    return findings
