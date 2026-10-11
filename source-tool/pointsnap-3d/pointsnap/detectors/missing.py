"""Phát hiện sót đối tượng bằng LiDAR (việc C7, spec 4.2: NÊN gán box khi vật xuất hiện rõ trong point cloud).

Mỗi keyframe:

1. Ước lượng mặt đất cục bộ (điểm thấp nhất trong lưới 1 m, lấy min của ô và 8 ô quanh), giữ điểm cao hơn mặt đất
   0,3 – 4 m, trong khoảng `min_range_m` – `max_range_m` quanh cảm biến.
2. Bỏ điểm nằm trong box nhãn bất kỳ (nới `box_margin_m`), kể cả box `occluded`.
3. Gom cụm trên lưới nhìn từ trên (`cell_m`), hai ô cách nhau ≤ 1 ô là cùng cụm.
4. Giữ cụm **giống vật**: đủ điểm, kích thước trong khoảng của người / xe hai bánh / ô tô, chân cụm sát đất.

Rồi nối cụm giữa các keyframe liền nhau trong hệ toàn cục (dự đoán vận tốc không đổi, cổng `link_gate_m`). Chuỗi cụm
**di chuyển** (≥ `min_frames` keyframe, dời ≥ `min_motion_m` theo một hướng nhất quán) mà không box nào phủ → `lidar.missing`
(Cảnh báo). Cụm đứng yên rất hay là cột, thùng rác, bụi cây không thuộc class cần gán nên không báo; nếu ảnh camera thấy
vật chắc chắn ở đó (`cam.missing`) thì nâng mục `cam.missing` (Thông tin) thành `lidar.missing` (Cảnh báo).

Không có box nên không gắn cờ lên CVAT được; mục ghi vị trí tâm cụm ở từng frame (hệ point cloud của frame) và kích thước
để người gán vẽ box.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import TYPE_CHECKING, Sequence

import numpy as np

from pointsnap.core.geometry import points_in_cuboid
from pointsnap.core.model import Cuboid, ErrorType, Finding, Severity, group_by_frame

if TYPE_CHECKING:
    from pointsnap.core.config import MissingConfig


@dataclass(eq=False)
class Cluster:
    frame: int
    center: np.ndarray       # (x, y) hệ point cloud của frame
    world: np.ndarray        # (x, y) hệ toàn cục
    length: float
    width: float
    height: float
    num_points: int
    cells: frozenset = frozenset()
    """Ô lưới (hệ toàn cục, cạnh `cell_m`) mà cụm chiếm."""


def _ground(points: np.ndarray, cell: float = 1.0) -> np.ndarray:
    """Độ cao mặt đất cục bộ dưới từng điểm: min z của ô lưới chứa điểm và 8 ô quanh."""
    keys = np.floor(points[:, :2] / cell).astype(np.int64)
    uniq, inverse = np.unique(keys, axis=0, return_inverse=True)
    inverse = inverse.reshape(-1)
    lowest = np.full(len(uniq), np.inf)
    np.minimum.at(lowest, inverse, points[:, 2])
    lookup = {tuple(k): i for i, k in enumerate(uniq)}
    local = lowest.copy()
    for di in (-1, 0, 1):
        for dj in (-1, 0, 1):
            if di == 0 and dj == 0:
                continue
            idx = np.array([lookup.get((i + di, j + dj), -1) for i, j in uniq])
            has = idx >= 0
            local[has] = np.minimum(local[has], lowest[idx[has]])
    return local[inverse]


def _components(cells: np.ndarray, far: np.ndarray) -> list[np.ndarray]:
    """Nhóm chỉ số các ô kề nhau (8 hướng). Gần cảm biến không cho hở ô (người đứng sát tường không bị dính thành một
    cụm); ô ở xa (`far`, điểm thưa) cho hở 1 ô để xe xa không bị vỡ đôi."""
    index: dict[tuple[int, int], list[int]] = {}
    far_cell: set[tuple[int, int]] = set()
    for n, key in enumerate(map(tuple, cells)):
        index.setdefault(key, []).append(n)
        if far[n]:
            far_cell.add(key)
    seen: set[tuple[int, int]] = set()
    groups = []
    for start in index:
        if start in seen:
            continue
        seen.add(start)
        stack, members = [start], []
        while stack:
            i, j = stack.pop()
            members.extend(index[(i, j)])
            reach = (-2, -1, 0, 1, 2) if (i, j) in far_cell else (-1, 0, 1)
            for di in reach:
                for dj in reach:
                    nb = (i + di, j + dj)
                    if nb in index and nb not in seen:
                        seen.add(nb)
                        stack.append(nb)
        groups.append(np.array(members))
    return groups


def frame_clusters(points: np.ndarray, boxes: Sequence[Cuboid], sensor_to_world: np.ndarray | None,
                   cfg: MissingConfig, frame: int, occupancy: set | None = None) -> list[Cluster]:
    """Cụm giống vật của một frame. `occupancy` (nếu có) được điền các ô (hệ toàn cục) có điểm không phải mặt đất,
    ngoài box nhãn — dùng để biết chỗ cụm đứng có còn bị chiếm ở frame kề không."""
    pts = np.asarray(points, dtype=np.float64)[:, :3]
    rng = np.hypot(pts[:, 0], pts[:, 1])
    pts = pts[(rng >= cfg.min_range_m) & (rng <= cfg.max_range_m)]
    if len(pts) == 0:
        return []
    above = pts[:, 2] - _ground(pts)
    keep = (above > 0.3) & (above < 4.0)
    for box in boxes:
        if box.outside:
            continue
        reach = max(box.dims[:2]) / 2 + cfg.box_margin_m
        near = np.flatnonzero((np.abs(pts[:, 0] - box.center[0]) <= reach) & (np.abs(pts[:, 1] - box.center[1]) <= reach))
        if len(near):
            keep[near[points_in_cuboid(pts[near], box, margin=cfg.box_margin_m)]] = False
    pts, above = pts[keep], above[keep]
    m = np.asarray(sensor_to_world) if sensor_to_world is not None else np.eye(4)
    world_xy = (pts @ m[:3, :3].T + m[:3, 3])[:, :2]
    world_cells = np.floor(world_xy / cfg.cell_m).astype(np.int64)
    if occupancy is not None:
        occupancy.update(map(tuple, world_cells))
    if len(pts) < cfg.min_points:
        return []
    clusters = []
    far = np.hypot(pts[:, 0], pts[:, 1]) > 12.0
    for idx in _components(np.floor(pts[:, :2] / cfg.cell_m).astype(np.int64), far):
        if len(idx) < cfg.min_points:
            continue
        xy, h = pts[idx, :2], above[idx]
        center = xy.mean(axis=0)
        cov = np.cov((xy - center).T) if len(idx) > 2 else np.eye(2)
        axes = np.linalg.eigh(cov)[1]
        proj = (xy - center) @ axes
        extent = np.percentile(proj, 98, axis=0) - np.percentile(proj, 2, axis=0)
        width, length = float(min(extent)), float(max(extent))
        height = float(np.percentile(h, 98))
        bottom = float(np.percentile(h, 2))
        cells_used = len({tuple(c) for c in np.floor(xy / cfg.cell_m).astype(np.int64)})
        if (bottom > cfg.max_bottom_m or _kind(length, width, height) is None
                or len(idx) / cells_used < cfg.min_points_per_cell):
            continue  # nhiễu mưa / bụi rải rác: ~1 điểm mỗi ô; mặt vật thật bị nhiều tia quét chồng theo chiều đứng
        world = world_xy[idx].mean(axis=0)
        clusters.append(Cluster(frame, center, world, length, width, height, len(idx),
                                frozenset(map(tuple, world_cells[idx]))))
    return clusters


def _link(by_frame: dict[int, list[Cluster]], cfg: MissingConfig) -> list[list[Cluster]]:
    """Nối cụm giữa các keyframe liền nhau: dự đoán vận tốc không đổi, ghép gần nhất trong cổng."""
    chains: list[list[Cluster]] = []
    active: list[list[Cluster]] = []
    for frame in sorted(by_frame):
        free = list(by_frame[frame])
        next_active = []
        for chain in sorted(active, key=len, reverse=True):
            last = chain[-1]
            if last.frame != frame - 1:
                chains.append(chain)
                continue
            pred = last.world + (last.world - chain[-2].world if len(chain) > 1 else 0.0)
            # Bước đầu chưa biết vận tốc: cổng rộng theo tốc độ tối đa; sau đó dự đoán vận tốc không đổi.
            gate = cfg.link_gate_m if len(chain) > 1 else cfg.first_gate_m
            best = min(free, key=lambda c: np.linalg.norm(c.world - pred), default=None)
            if best is not None and np.linalg.norm(best.world - pred) <= gate:
                chain.append(best)
                free.remove(best)
                next_active.append(chain)
            else:
                chains.append(chain)
        next_active.extend([c] for c in free)
        active = next_active
    return chains + active


def _kind(length: float, width: float, height: float) -> str | None:
    """Loại vật theo kích thước cụm nhìn thấy (LiDAR thường chỉ thấy 1–2 mặt nên bề rộng cụm có thể rất nhỏ);
    `None` nếu không giống vật cần gán (quá dài, quá cao như tán cây, cột đèn)."""
    if length <= 1.3 and width <= 1.0 and 1.0 <= height <= 2.2:
        return "người"
    if length <= 2.8 and width <= 1.3 and 0.8 <= height <= 2.2:
        return "xe hai bánh"
    if 1.5 <= length <= 7.5 and width <= 3.2 and 0.8 <= height <= 3.8 and (height <= 2.5 or length >= 4.0):
        # Nhìn ngang chỉ thấy hông xe nên cụm có thể mỏng (tường mỏng dài bị loại bởi phép thử "chỗ cũ còn bị
        # chiếm"); xe cao > 2,5 m (tải, buýt) thì dài ≥ 4 m — cụm ngắn mà cao thường là tán cây, biển báo.
        return "xe"
    if 7.5 < length <= 18.0 and width <= 3.4 and 1.5 <= height <= 4.5:
        return "xe dài"  # xe buýt, xe tải dài, rơ-moóc: thường chỉ thấy một mặt hông nên bề rộng cụm nhỏ
    return None


def _persistence(cluster: Cluster, occupied: dict[int, set], frame: int, lag: int = 2) -> float:
    """Tỉ lệ ô của cụm vẫn có điểm ở frame cách `lag` keyframe (lấy lớn nhất của trước / sau; thiếu thì dùng frame kề).

    Cách 1 giây thì ô tô 4,5 m chạy ≥ 4 m/s, người đi bộ 1,2 m/s đã rời hẳn chỗ cũ; vật đứng yên vẫn chiếm chỗ."""
    best = 0.0
    for step in (-1, 1):
        other = frame + step * lag if frame + step * lag in occupied else frame + step
        if other in occupied and cluster.cells:
            best = max(best, sum(c in occupied[other] for c in cluster.cells) / len(cluster.cells))
    return best


def _steady(chain: list[Cluster]) -> bool:
    """Chuyển động đều và cùng hướng: mọi bước cùng chiều tổng (cos ≥ 0,5), độ dài bước trong [0,3; 2,5] × trung bình.
    Cụm đứng yên "trôi" theo góc nhìn hay nối nhầm hai vật đứng yên không qua được."""
    world = np.array([c.world for c in chain])
    steps = np.diff(world, axis=0)
    total = world[-1] - world[0]
    norm = np.linalg.norm(steps, axis=1)
    mean = float(norm.mean())
    if mean <= 0:
        return False
    cos = steps @ total / (norm * np.linalg.norm(total) + 1e-9)
    return bool(np.all(cos >= 0.5) and np.all(norm >= 0.3 * mean) and np.all(norm <= 2.5 * mean))


def detect_missing_objects(cuboids: Sequence[Cuboid], frames, cfg: MissingConfig) -> tuple[list[Finding], list[list[Cluster]]]:
    """Mục `lidar.missing` cho chuỗi cụm di chuyển không có box; trả kèm mọi chuỗi cụm (để đối chiếu ảnh camera)."""
    boxes_by_frame = group_by_frame(cuboids)
    num_frames = getattr(frames, "num_frames", None) or (max(boxes_by_frame) + 1 if boxes_by_frame else 0)
    by_frame: dict[int, list[Cluster]] = {}
    occupied: dict[int, set] = {}
    for f in range(num_frames):
        data = frames.frame_data(f)
        occupied[f] = set()
        by_frame[f] = frame_clusters(data.points, boxes_by_frame.get(f, []), data.sensor_to_world, cfg, f, occupied[f])
    # Vật đứng yên vẫn chiếm chỗ cũ ở frame kề; vật di chuyển thì chỗ cũ trống. Bỏ cụm mà chỗ đứng còn bị chiếm.
    for f, clusters in by_frame.items():
        by_frame[f] = [c for c in clusters if _persistence(c, occupied, f) <= cfg.max_persistence]
    chains = [c for c in _link(by_frame, cfg) if len(c) >= cfg.min_frames]
    findings = []
    for chain in chains:
        disp = float(np.linalg.norm(chain[-1].world - chain[0].world))
        size = (float(np.median([c.length for c in chain])), float(np.median([c.width for c in chain])),
                float(np.median([c.height for c in chain])))
        kind = _kind(*size) or "vật"
        # Người đi bộ chậm (~1,3 m/s): cần chuỗi dài hơn nhưng quãng dời ngắn hơn
        need_motion, need_frames = ((cfg.min_motion_person_m, cfg.min_frames + 1) if kind == "người"
                                    else (cfg.min_motion_m, cfg.min_frames))
        if disp < need_motion or len(chain) < need_frames or not _steady(chain):
            continue
        first, last = chain[0], chain[-1]
        dt = (last.frame - first.frame) * cfg.keyframe_interval_s
        findings.append(Finding(
            error_type=ErrorType.FIT, rule="lidar.missing", severity=Severity.WARNING, frame=first.frame, label=kind,
            value=disp / dt if dt > 0 else 0.0, threshold=cfg.min_motion_m,
            message=(f"Cụm điểm LiDAR cỡ {kind} ({size[0]:.1f} × {size[1]:.1f} × {size[2]:.1f} m, ~"
                     f"{int(np.median([c.num_points for c in chain]))} điểm) di chuyển {disp:.1f} m qua {len(chain)} "
                     f"keyframe ({first.frame}–{last.frame}) mà không có box: nghi sót đối tượng (spec 4.2)"),
            details={"frames": [c.frame for c in chain],
                     "centers": [[round(float(v), 2) for v in c.center] for c in chain],
                     "size_m": [round(v, 2) for v in size], "moving": True},
        ))
    return findings, chains
