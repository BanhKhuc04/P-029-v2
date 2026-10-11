"""Module ước lượng mặt đất (Ground Module) cục bộ quanh box 3D (việc B2).

Sử dụng kết hợp:
1. Vành đai quanh footprint box (mở rộng [ring_inner_m, ring_outer_m], loại vùng trong box).
2. Lưới min-Z lọc bỏ vật cản trong vành đai.
3. RANSAC fit mặt phẳng cục bộ và tinh chỉnh bằng Least Squares (SVD).
"""

from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass
from typing import TYPE_CHECKING, Sequence

import numpy as np

from pointsnap.core.geometry import footprint_ring_mask

if TYPE_CHECKING:
    from pointsnap.core.config import FloatingConfig
    from pointsnap.core.model import Cuboid


@dataclass(frozen=True)
class GroundEstimate:
    """Kết quả ước lượng mặt đất cho một box 3D.

    - `ground_z`: độ cao mặt đất ước lượng tại tâm (x, y) của box; `None` nếu không ước lượng được.
    - `distance`: khoảng cách đáy box tới mặt đất (mét): d = z_bottom - ground_z.
      d > 0: box lơ lửng; d < 0: box lún đất.
    - `plane`: bộ 4 hệ số (A, B, C, D) của phương trình mặt phẳng Ax + By + Cz + D = 0 (chuẩn hóa A^2+B^2+C^2=1, C > 0).
    - `num_ground_points`: số điểm candidate ground trong vành đai sau khi lọc min-Z.
    - `num_inliers`: số điểm inlier của mặt phẳng RANSAC.
    - `status`: trạng thái ước lượng:
      * "ok": ước lượng thành công.
      * "no_evidence": thiếu bằng chứng (ít hơn min_ground_points trong vành đai).
      * "no_plane": không tìm được mặt phẳng mặt đất hợp lệ.
    """

    ground_z: float | None = None
    distance: float | None = None
    plane: tuple[float, float, float, float] | None = None
    num_ground_points: int = 0
    num_inliers: int = 0
    status: str = "ok"

    @property
    def is_valid(self) -> bool:
        return self.status == "ok" and self.ground_z is not None and self.distance is not None


def filter_min_z_grid(
    points: np.ndarray,
    cell_size: float = 0.5,
    height_threshold: float = 0.15,
) -> np.ndarray:
    """Lọc điểm theo lưới min-Z trong mặt phẳng XY.

    Chia không gian XY thành các ô lưới kích thước `cell_size`. Trong mỗi ô, tìm z_min.
    Chỉ giữ lại các điểm có z <= z_min + height_threshold (loại bỏ phần thân xe, cột đèn, người đứng trong ô).
    Trả về mask boolean cùng kích thước với `points`.
    """
    pts = np.asarray(points)[:, :3]
    if len(pts) == 0:
        return np.zeros(0, dtype=bool)

    gx = np.floor(pts[:, 0] / cell_size).astype(np.int64)
    gy = np.floor(pts[:, 1] / cell_size).astype(np.int64)

    cells: dict[tuple[int, int], list[int]] = defaultdict(list)
    for idx, key in enumerate(zip(gx, gy)):
        cells[key].append(idx)

    mask = np.zeros(len(pts), dtype=bool)
    for cell_indices in cells.values():
        z_vals = pts[cell_indices, 2]
        min_z = float(np.min(z_vals))
        for idx in cell_indices:
            if pts[idx, 2] <= min_z + height_threshold:
                mask[idx] = True

    return mask


def fit_plane_ransac(
    points: np.ndarray,
    distance_threshold: float = 0.05,
    max_iterations: int = 100,
    min_inliers: int = 10,
    max_tilt_rad: float = math.radians(25.0),
    seed: int | None = 42,
) -> tuple[tuple[float, float, float, float] | None, np.ndarray]:
    """Fit mặt phẳng Ax + By + Cz + D = 0 bằng RANSAC và tinh chỉnh bằng SVD.

    - `distance_threshold`: khoảng cách tối đa từ điểm tới mặt phẳng để coi là inlier (mét).
    - `max_tilt_rad`: góc nghiêng tối đa so với phương thẳng đứng (mặt đất đường bộ thường dốc < 20-25 độ).
    - `seed`: seed cho bộ sinh số ngẫu nhiên để kết quả kiểm thử hoàn toàn tái lập.

    Trả về `(plane, inlier_mask)` hoặc `(None, empty_mask)` nếu không đạt.
    """
    pts = np.asarray(points, dtype=np.float64)[:, :3]
    n_pts = len(pts)
    if n_pts < max(3, min_inliers):
        return None, np.zeros(n_pts, dtype=bool)

    rng = np.random.default_rng(seed)
    min_c = math.cos(max_tilt_rad)

    best_inliers_count = 0
    best_inlier_mask = np.zeros(n_pts, dtype=bool)
    best_plane: tuple[float, float, float, float] | None = None

    for _ in range(max_iterations):
        sample_indices = rng.choice(n_pts, size=3, replace=False)
        p1, p2, p3 = pts[sample_indices]

        v1 = p2 - p1
        v2 = p3 - p1
        normal = np.cross(v1, v2)
        norm_val = np.linalg.norm(normal)
        if norm_val < 1e-7:
            continue

        normal /= norm_val
        if normal[2] < 0:
            normal = -normal

        # Ràng buộc pháp tuyến: mặt đất gần thẳng đứng (trục z hướng lên)
        if normal[2] < min_c:
            continue

        d = -float(np.dot(normal, p1))
        distances = np.abs(pts @ normal + d)
        inlier_mask = distances <= distance_threshold
        inliers_count = int(np.sum(inlier_mask))

        if inliers_count > best_inliers_count:
            best_inliers_count = inliers_count
            best_inlier_mask = inlier_mask
            best_plane = (float(normal[0]), float(normal[1]), float(normal[2]), d)

    if best_inliers_count < min_inliers or best_plane is None:
        return None, np.zeros(n_pts, dtype=bool)

    # Tinh chỉnh mặt phẳng bằng SVD Least Squares trên toàn bộ inliers
    inlier_pts = pts[best_inlier_mask]
    centroid = np.mean(inlier_pts, axis=0)
    centered = inlier_pts - centroid
    _, _, vt = np.linalg.svd(centered)
    refined_normal = vt[2]
    refined_normal /= np.linalg.norm(refined_normal)
    if refined_normal[2] < 0:
        refined_normal = -refined_normal

    if refined_normal[2] >= min_c:
        refined_d = -float(np.dot(refined_normal, centroid))
        # Cập nhật lại inlier mask theo mặt phẳng đã tinh chỉnh
        refined_distances = np.abs(pts @ refined_normal + refined_d)
        refined_inlier_mask = refined_distances <= distance_threshold
        refined_plane = (
            float(refined_normal[0]),
            float(refined_normal[1]),
            float(refined_normal[2]),
            refined_d,
        )
        return refined_plane, refined_inlier_mask

    return best_plane, best_inlier_mask


def estimate_ground_for_box(
    points: np.ndarray,
    cuboid: Cuboid,
    ring_inner_m: float = 0.5,
    ring_outer_m: float = 1.5,
    min_ground_points: int = 10,
    cell_size: float = 0.5,
    min_z_threshold: float = 0.15,
    distance_threshold: float = 0.05,
    max_iterations: int = 100,
    seed: int | None = 42,
) -> GroundEstimate:
    """Ước lượng độ cao mặt đất cục bộ cho một box 3D.

    Quy trình:
    1. Cắt lọc sơ bộ các điểm lân cận trong XY quanh tâm box.
    2. Lọc điểm trong vành đai footprint: từ mép footprint + ring_inner_m đến mép + ring_outer_m.
    3. Lọc chiều cao sơ bộ quanh đáy box [bottom_z - 2.0 m, bottom_z + 1.0 m].
    4. Áp dụng lưới min-Z loại bỏ vật cản.
    5. Nếu số điểm còn lại < min_ground_points: trả về trạng thái "no_evidence".
    6. RANSAC fit mặt phẳng cục bộ.
    7. Tính z_ground tại tâm (x, y) của box và khoảng cách d = bottom_z - z_ground.
    """
    pts = np.asarray(points, dtype=np.float64)[:, :3]
    if len(pts) == 0:
        return GroundEstimate(status="no_evidence", num_ground_points=0)

    # Lọc thô XY trong bán kính mở rộng
    max_half = max(cuboid.dims[:2]) / 2.0 + ring_outer_m + 0.5
    dx = np.abs(pts[:, 0] - cuboid.center[0])
    dy = np.abs(pts[:, 1] - cuboid.center[1])
    nearby_mask = (dx <= max_half) & (dy <= max_half)
    nearby_pts = pts[nearby_mask]
    if len(nearby_pts) == 0:
        return GroundEstimate(status="no_evidence", num_ground_points=0)

    # Lấy điểm trong vành đai footprint
    ring_mask = footprint_ring_mask(nearby_pts, cuboid, inner=ring_inner_m, outer=ring_outer_m)
    ring_pts = nearby_pts[ring_mask]
    if len(ring_pts) < min_ground_points:
        return GroundEstimate(status="no_evidence", num_ground_points=len(ring_pts))

    # Lọc sơ bộ độ cao quanh đáy box: loại bỏ điểm tán cây, dây điện trên cao hoặc nhiễu sâu dưới đất
    bottom_z = cuboid.bottom_z
    height_mask = (ring_pts[:, 2] >= bottom_z - 2.0) & (ring_pts[:, 2] <= bottom_z + 1.0)
    ring_pts = ring_pts[height_mask]
    if len(ring_pts) < min_ground_points:
        return GroundEstimate(status="no_evidence", num_ground_points=len(ring_pts))

    # Lọc vật cản bằng lưới min-Z
    min_z_mask = filter_min_z_grid(ring_pts, cell_size=cell_size, height_threshold=min_z_threshold)
    ground_cand_pts = ring_pts[min_z_mask]
    if len(ground_cand_pts) < min_ground_points:
        return GroundEstimate(status="no_evidence", num_ground_points=len(ground_cand_pts))

    # Fit mặt phẳng bằng RANSAC
    plane, inliers_mask = fit_plane_ransac(
        ground_cand_pts,
        distance_threshold=distance_threshold,
        max_iterations=max_iterations,
        min_inliers=min_ground_points,
        seed=seed,
    )

    if plane is None:
        return GroundEstimate(
            status="no_plane",
            num_ground_points=len(ground_cand_pts),
            num_inliers=0,
        )

    a, b, c, d_coeff = plane
    cx, cy = cuboid.center[:2]
    # Mặt phẳng: a*x + b*y + c*z + d = 0 => z = -(a*x + b*y + d) / c
    ground_z = -(a * cx + b * cy + d_coeff) / c
    distance = bottom_z - ground_z

    return GroundEstimate(
        ground_z=float(ground_z),
        distance=float(distance),
        plane=plane,
        num_ground_points=len(ground_cand_pts),
        num_inliers=int(np.sum(inliers_mask)),
        status="ok",
    )


def ring_ground_for_box(
    points: np.ndarray,
    cuboid: Cuboid,
    ring_inner_m: float = 0.1,
    ring_outer_m: float = 0.8,
    min_ground_points: int = 15,
    band_m: float = 0.8,
    cell_size: float = 0.4,
    min_z_threshold: float = 0.08,
) -> GroundEstimate:
    """Ước lượng mặt đất sát box bằng trung vị các điểm thấp trong vành đai (bộ đo dùng cho luật B3).

    Khác `estimate_ground_for_box` (RANSAC trên vành đai 0,5–1,5 m): vành đai hẹp sát footprint, chỉ lấy điểm
    trong khoảng ±`band_m` quanh đáy box, lọc lưới min-Z rồi lấy trung vị z. Trên 10 cảnh nuScenes mini cách này
    cho độ lệch so với trung vị track nhỏ hơn (p90 ~15 cm so với ~20 cm), xem docs/kiem-chung-ground.md.
    `points` nên đã bỏ điểm thuộc các box khác (`OtherBoxPoints`), nếu không thân xe bên cạnh bị tính là đất.
    """
    pts = np.asarray(points, dtype=np.float64)[:, :3]
    reach = max(cuboid.dims[:2]) / 2.0 + ring_outer_m + 0.1
    near = pts[(np.abs(pts[:, 0] - cuboid.center[0]) <= reach) & (np.abs(pts[:, 1] - cuboid.center[1]) <= reach)]
    if len(near) == 0:
        return GroundEstimate(status="no_evidence")
    ring = near[footprint_ring_mask(near, cuboid, inner=ring_inner_m, outer=ring_outer_m)]
    ring = ring[np.abs(ring[:, 2] - cuboid.bottom_z) <= band_m]
    if len(ring) < min_ground_points:
        return GroundEstimate(status="no_evidence", num_ground_points=len(ring))
    ground = ring[filter_min_z_grid(ring, cell_size=cell_size, height_threshold=min_z_threshold)]
    if len(ground) < min_ground_points:
        return GroundEstimate(status="no_evidence", num_ground_points=len(ground))
    ground_z = float(np.median(ground[:, 2]))
    return GroundEstimate(
        ground_z=ground_z,
        distance=cuboid.bottom_z - ground_z,
        num_ground_points=len(ground),
        num_inliers=len(ground),
        status="ok",
    )


class OtherBoxPoints:
    """Point cloud của một frame, cho phép lấy nhanh các điểm không thuộc box nào khác ngoài một box cho trước.

    Điểm nằm trong một box (nới `margin` mét) là điểm của đối tượng, không phải mặt đất. Điểm trong chính box
    đang xét vẫn giữ: box bị lún thì mặt đất thật nằm trong box, không được bỏ.

    Điểm được sắp theo x một lần để tìm nhanh các điểm quanh một box (`near`), thay vì quét cả point cloud cho mỗi box.
    """

    def __init__(self, points: np.ndarray, cuboids: Sequence[Cuboid], margin: float = 0.15) -> None:
        from pointsnap.core.geometry import points_in_cuboid

        self.points = np.asarray(points, dtype=np.float64)[:, :3]
        self._order = np.argsort(self.points[:, 0], kind="stable")
        self._sorted_x = self.points[self._order, 0]
        self._count = np.zeros(len(self.points), dtype=np.int32)
        self._inside: list[np.ndarray] = []
        for cuboid in cuboids:
            idx = self.near(cuboid.center[0], cuboid.center[1], max(cuboid.dims) / 2.0 + margin)
            idx = idx[points_in_cuboid(self.points[idx], cuboid, margin=margin)] if len(idx) else idx
            self._count[idx] += 1
            self._inside.append(idx)
        self._boxes_center = [c.center for c in cuboids]

    def near(self, x: float, y: float, reach: float) -> np.ndarray:
        """Chỉ số (tăng dần) các điểm có |x − `x`| ≤ `reach` và |y − `y`| ≤ `reach`."""
        lo = int(np.searchsorted(self._sorted_x, x - reach, side="left"))
        hi = int(np.searchsorted(self._sorted_x, x + reach, side="right"))
        idx = self._order[lo:hi]
        idx = idx[np.abs(self.points[idx, 1] - y) <= reach]
        return np.sort(idx)

    def without_others(self, index: int, reach: float | None = None) -> np.ndarray:
        """Các điểm không thuộc box nào ngoài box thứ `index` (theo thứ tự `cuboids` lúc tạo).

        `reach`: chỉ trả các điểm trong hình vuông nửa cạnh `reach` quanh tâm box (giữ thứ tự gốc), đủ cho các phép đo
        cục bộ như `ring_ground_for_box` mà không phải chép cả point cloud cho mỗi box.
        """
        if reach is None:
            count = self._count.copy()
            count[self._inside[index]] -= 1
            return self.points[count == 0]
        box = self._boxes_center[index]
        idx = self.near(box[0], box[1], reach)
        own = np.isin(idx, self._inside[index], assume_unique=True)
        return self.points[idx[(self._count[idx] - own) == 0]]

    def belongs_to_others(self, index: int, idx: np.ndarray) -> np.ndarray:
        """Mask cho các điểm có chỉ số `idx` thuộc ít nhất một box khác ngoài box thứ `index`."""
        own = np.isin(idx, self._inside[index])
        return (self._count[idx] - own) > 0


def estimate_ground_for_frame(
    points: np.ndarray,
    cuboids: Sequence[Cuboid],
    config: FloatingConfig | None = None,
    seed: int | None = 42,
) -> dict[Cuboid, GroundEstimate]:
    """Ước lượng mặt đất cho danh sách box trong một frame.

    Nếu cung cấp `config`, chỉ ước lượng cho các box có class thuộc `config.classes`.
    Box không thuộc class tiếp đất được trả về GroundEstimate(status="no_evidence").
    """
    inner = config.ring_inner_m if config is not None else 0.5
    outer = config.ring_outer_m if config is not None else 1.5
    min_pts = config.min_ground_points if config is not None else 10
    classes = set(config.classes) if config is not None else None

    results: dict[Cuboid, GroundEstimate] = {}
    for cuboid in cuboids:
        if classes is not None and cuboid.label not in classes:
            results[cuboid] = GroundEstimate(status="no_evidence", num_ground_points=0)
            continue
        results[cuboid] = estimate_ground_for_box(
            points=points,
            cuboid=cuboid,
            ring_inner_m=inner,
            ring_outer_m=outer,
            min_ground_points=min_pts,
            seed=seed,
        )
    return results
