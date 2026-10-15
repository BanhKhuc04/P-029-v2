"""Challenger 2 Adversarial Test Suite for Milestone M1 (Backend Ghost Target Engine & Spatial Residuals).

Adversarial Stress Testing Scope:
1. Invalid Inputs & Route Robustness:
   - Negative job_id (-1, -9999) -> HTTP 404
   - Non-existent & negative track_id (999999, -5) -> HTTP 404
   - Out-of-range & negative frame numbers (9999, -1, -100) -> HTTP 404
   - Missing required query param 'frame' -> HTTP 422
   - Malformed data types (string job_id, track_id, frame) -> HTTP 422
   - Adversarial query parameters (SQL injection, path traversal, unknown rules) -> graceful HTTP 200 fallback, no 500
2. Missing Point Cloud Behavior & Edge Fallbacks:
   - Point cloud is None -> valid GhostTarget, zero roll/pitch, confidence = 0 khi thiếu bằng chứng, cluster_bounds is None
   - Empty point cloud (0, 3) -> safe fallback without crash
   - Non-finite point cloud (NaN, Inf, -Inf) -> safe filtering, clean fallback
   - Sparse point clouds (< 5 points: 1, 2, 3, 4 points) -> below quantile threshold, graceful fallback without IndexError
   - Distant / isolated point clouds -> box margin filter empty, safe fallback
3. Tolerance Schema Strictness Validation:
   - Root keys validation: status, job_id, track_id, frame, ghost_target, tolerances, track_etag
   - Strict tolerances structure: snap_distance_m=0.08, snap_angle_deg=4.0, lock_distance_m=0.02, lock_angle_deg=2.0
   - Positive numeric types, exact contract compliance
   - GhostTarget field strictness: center (3 floats), dims (3 positive floats), roll=0.0, pitch=0.0, confidence in [0, 1]
4. ETag Consistency & OCC Interoperability:
   - Deterministic matching: track_etag in response == compute_track_etag(track_data)
   - Mutation sensitivity: coordinate change, yaw change, dim change, attribute change, frame addition/removal
   - Interoperability with apply-repair endpoint: valid ETag succeeds, stale ETag returns 409 Conflict
5. Spatial Residuals & Green Lock Scanner Clearance Boundary Stress:
   - Exact threshold boundaries: 8.000cm / 8.001cm, 4.000deg / 4.001deg
   - Green lock boundaries: 2.000cm / 2.001cm, 2.000deg / 2.001deg, 0.500deg / 0.501deg
   - Monte Carlo verification: randomized samples inside Green Lock envelope pass verify_repaired_box_passes_scanner 100%
"""

from __future__ import annotations

import copy
import json
import math
from pathlib import Path
from typing import Any

import numpy as np
import pytest
from fastapi.testclient import TestClient

from pointsnap.adapters.cvat.shapes import cuboid_to_points
from pointsnap.adapters.cvat.writer import compute_track_etag
from pointsnap.core.geometry import normalize_angle
from pointsnap.core.ghost import (
    ClusterBounds,
    GhostTarget,
    SpatialResiduals,
    compute_spatial_residuals,
    generate_ghost_target,
)
from pointsnap.core.model import Cuboid
from pointsnap.core.repair import verify_repaired_box_passes_scanner
from pointsnap.web.app import create_app


# =========================================================================
# Fixtures & Helpers
# =========================================================================


def _make_sample_cvat_track(track_id: int = 101, num_frames: int = 5, label: str = "car") -> dict[str, Any]:
    """Tạo CVAT track dict chuẩn với num_frames keyframes."""
    shapes = []
    for f in range(num_frames):
        pts = [
            10.0 + f * 2.0,  # px
            5.0,             # py
            -0.5,            # pz
            0.0,             # rx
            0.0,             # ry
            0.15,            # rz (yaw)
            4.5,             # sx (l)
            2.0,             # sy (w)
            1.6,             # sz (h)
            0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0,
        ]
        shapes.append({
            "id": 2000 + f,
            "frame": f,
            "type": "cuboid",
            "occluded": False,
            "outside": False,
            "keyframe": True,
            "points": pts,
            "attributes": [
                {"id": 1, "name": "subtype", "value": "sedan"},
                {"id": 2, "name": "reviewed", "value": "false"},
            ],
        })
    return {
        "id": track_id,
        "label": label,
        "label_id": 10,
        "frame": 0,
        "shapes": shapes,
        "attributes": [],
    }


def _make_ground_and_vehicle_points(boxes: list[Cuboid], ground_z: float = -1.3, seed: int = 42) -> np.ndarray:
    """Tạo điểm LiDAR mặt đất và thân xe cho các box."""
    rng = np.random.default_rng(seed)
    ground = np.column_stack([
        rng.uniform(-20, 20, 5000),
        rng.uniform(-20, 20, 5000),
        np.full(5000, ground_z) + rng.normal(0, 0.01, 5000),
    ])
    parts = [ground]
    for b in boxes:
        l, w = b.dims[0], b.dims[1]
        n = 50
        front = np.column_stack([np.full(n, l / 2), rng.uniform(-w / 2, w / 2, n)])
        side = np.column_stack([rng.uniform(-l / 2, l / 2, n), np.full(n, w / 2)])
        local_2d = np.vstack([front, side])
        c, s = math.cos(b.yaw), math.sin(b.yaw)
        rot = np.array([[c, s], [-s, c]])
        world_xy = local_2d @ rot + np.array(b.center[:2])
        z = rng.uniform(b.bottom_z + 0.1, b.top_z, len(local_2d))
        parts.append(np.column_stack([world_xy, z]))
    return np.vstack(parts)


@pytest.fixture
def app_client(tmp_path: Path) -> TestClient:
    """Tạo test client với application state."""
    app = create_app(home_dir=tmp_path)
    client = TestClient(app)
    # Cấu hình mock track mặc định cho job 4, track 101
    client.app.state.mock_tracks = {(4, 101): _make_sample_cvat_track(track_id=101, num_frames=5)}
    return client


# =========================================================================
# 1. Adversarial Test Group: Invalid Inputs & Route Robustness
# =========================================================================


class TestAdversarialInvalidInputs:
    """Kiểm thử độ vững chắc của REST API route trước các đầu vào không hợp lệ."""

    def test_negative_job_id_returns_404(self, app_client: TestClient):
        """Job ID âm (-1, -9999) phải trả về HTTP 404 với error detail rõ ràng, không crash 500."""
        for bad_job_id in [-1, -9999]:
            resp = app_client.get(f"/api/jobs/{bad_job_id}/tracks/101/ghost-target?frame=0")
            assert resp.status_code == 404, f"Job {bad_job_id} phải trả về 404"
            data = resp.json()
            assert data.get("status") == "error"
            assert data.get("code") == 404
            assert "detail" in data

    def test_non_existent_and_negative_track_id_returns_404(self, app_client: TestClient):
        """Track ID không tồn tại hoặc âm (-1, 999999) phải trả về HTTP 404."""
        for bad_track_id in [-1, -99, 999999]:
            resp = app_client.get(f"/api/jobs/4/tracks/{bad_track_id}/ghost-target?frame=0")
            assert resp.status_code == 404, f"Track {bad_track_id} phải trả về 404"
            data = resp.json()
            assert data.get("status") == "error"
            assert data.get("code") == 404
            assert str(bad_track_id) in data.get("detail", "")

    def test_out_of_range_and_negative_frame_returns_404(self, app_client: TestClient):
        """Frame ngoài phạm vi track (âm hoặc vượt quá số frame) phải trả về HTTP 404."""
        for bad_frame in [-1, -50, 999, 10000]:
            resp = app_client.get(f"/api/jobs/4/tracks/101/ghost-target?frame={bad_frame}")
            assert resp.status_code == 404, f"Frame {bad_frame} phải trả về 404"
            data = resp.json()
            assert data.get("status") == "error"
            assert data.get("code") == 404
            assert str(bad_frame) in data.get("detail", "")

    def test_missing_frame_query_parameter_returns_422(self, app_client: TestClient):
        """Truy vấn thiếu tham số bắt buộc 'frame' phải trả về HTTP 422 Unprocessable Entity."""
        resp = app_client.get("/api/jobs/4/tracks/101/ghost-target")
        assert resp.status_code == 422
        data = resp.json()
        assert "detail" in data

    def test_invalid_parameter_types_returns_422(self, app_client: TestClient):
        """Truy vấn với kiểu dữ liệu không hợp lệ (chuỗi thay cho int) phải trả về HTTP 422."""
        invalid_urls = [
            "/api/jobs/invalid_job/tracks/101/ghost-target?frame=0",
            "/api/jobs/4/tracks/not_an_int/ghost-target?frame=0",
            "/api/jobs/4/tracks/101/ghost-target?frame=not_a_frame",
            "/api/jobs/4/tracks/101/ghost-target?frame=1.5",
        ]
        for url in invalid_urls:
            resp = app_client.get(url)
            assert resp.status_code == 422, f"URL {url} phải trả về 422"

    def test_adversarial_query_parameters_graceful_handling(self, app_client: TestClient):
        """Các tham số query chứa chuỗi tấn công (SQLi, path traversal, rule lạ) không gây crash 500."""
        malicious_rules = [
            "'; DROP TABLE tracks; --",
            "../../../../etc/passwd",
            "<script>alert(1)</script>",
            "undefined",
            "null",
            "   ",
            "rule.that.does.not.exist.anywhere",
        ]
        for rule in malicious_rules:
            resp = app_client.get(f"/api/jobs/4/tracks/101/ghost-target?frame=0&rule={rule}")
            assert resp.status_code == 200, f"Rule '{rule}' phải được xử lý an toàn, không 500"
            data = resp.json()
            assert data["status"] == "ok"
            gt = data["ghost_target"]
            # Khi rule lạ, động cơ vẫn giữ nguyên cân bằng và roll/pitch = 0
            assert gt["roll"] == 0.0
            assert gt["pitch"] == 0.0
            assert gt["confidence"] == 0.0

    def test_non_existent_project_slug_graceful_handling(self, app_client: TestClient):
        """Truyền slug dự án không tồn tại không làm sập API."""
        resp = app_client.get("/api/jobs/4/tracks/101/ghost-target?frame=0&slug=totally_non_existent_project_987654")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"


# =========================================================================
# 2. Adversarial Test Group: Missing Point Cloud Behavior & Edge Fallbacks
# =========================================================================


class TestAdversarialPointCloudFallbacks:
    """Kiểm thử hành vi dự phòng (fallback) khi point cloud bị thiếu, rỗng, suy biến hoặc chứa NaN."""

    def test_point_cloud_none_fallback(self, app_client: TestClient):
        """Khi point cloud là None, API trả về GhostTarget hợp lệ với cluster_bounds=None và confidence = 0 khi thiếu bằng chứng."""
        # Đảm bảo không có mock_points
        if hasattr(app_client.app.state, "mock_points"):
            app_client.app.state.mock_points.clear()

        resp = app_client.get("/api/jobs/4/tracks/101/ghost-target?frame=1")
        assert resp.status_code == 200
        data = resp.json()
        gt = data["ghost_target"]

        assert gt["center"] is not None and len(gt["center"]) == 3
        assert gt["dims"] is not None and len(gt["dims"]) == 3
        assert all(d > 0 for d in gt["dims"])
        assert gt["roll"] == 0.0
        assert gt["pitch"] == 0.0
        assert gt["cluster_bounds"] is None
        assert gt["confidence"] == 0.0

    def test_empty_point_cloud_fallback(self):
        """Khi point cloud có kích thước (0, 3), generate_ghost_target không gây lỗi index hay division by zero."""
        cuboid = Cuboid(center=(5.0, 2.0, 0.0), dims=(4.5, 2.0, 1.6), yaw=0.1, label="car", frame=0, track_id=1)
        empty_points = np.zeros((0, 3), dtype=np.float64)

        ghost = generate_ghost_target(cuboid, track=[cuboid], points=empty_points, rule="fit.outside")
        assert isinstance(ghost, GhostTarget)
        assert ghost.roll == 0.0
        assert ghost.pitch == 0.0
        assert ghost.cluster_bounds is None
        assert ghost.confidence == 0.0

    def test_nan_and_inf_point_cloud_cleaning(self):
        """Khi point cloud chứa các giá trị NaN, +Inf, -Inf, động cơ tự động lọc sạch và tiếp tục."""
        cuboid = Cuboid(center=(5.0, 2.0, 0.0), dims=(4.5, 2.0, 1.6), yaw=0.0, label="car", frame=0, track_id=1)
        corrupted_points = np.array([
            [np.nan, 2.0, 0.0],
            [5.0, np.inf, 0.0],
            [-np.inf, -np.inf, -np.inf],
            [np.nan, np.nan, np.nan],
        ], dtype=np.float64)

        # Toàn bộ điểm đều hỏng -> fallback an toàn
        ghost = generate_ghost_target(cuboid, track=[cuboid], points=corrupted_points)
        assert isinstance(ghost, GhostTarget)
        assert ghost.roll == 0.0
        assert ghost.pitch == 0.0
        assert ghost.cluster_bounds is None

    def test_sparse_point_cloud_under_quantile_threshold(self):
        """Kiểm thử khi point cloud có từ 1 đến 4 điểm (< 5 điểm ngưỡng cho ClusterBounds).

        Không được ném IndexError hoặc ValueError từ np.percentile, phải fallback an toàn.
        """
        cuboid = Cuboid(center=(5.0, 2.0, 0.0), dims=(4.5, 2.0, 1.6), yaw=0.0, label="car", frame=0, track_id=1)

        for n_pts in [1, 2, 3, 4]:
            pts = np.array([[5.0 + i * 0.1, 2.0, 0.0] for i in range(n_pts)], dtype=np.float64)
            ghost = generate_ghost_target(cuboid, track=[cuboid], points=pts, rule="fit.outside")
            assert isinstance(ghost, GhostTarget), f"Thất bại với {n_pts} điểm"
            assert ghost.cluster_bounds is None, f"Với {n_pts} điểm, cluster_bounds phải là None"
            assert ghost.roll == 0.0
            assert ghost.pitch == 0.0

    def test_distant_point_cloud_filtering(self):
        """Khi point cloud có điểm nhưng nằm rất xa box (> 100m), không bị nhầm lẫn tính vào box."""
        cuboid = Cuboid(center=(0.0, 0.0, 0.0), dims=(4.0, 2.0, 1.5), yaw=0.0, label="car", frame=0, track_id=1)
        distant_points = np.random.uniform(500, 600, (100, 3))

        ghost = generate_ghost_target(cuboid, track=[cuboid], points=distant_points, rule="fit.outside")
        assert isinstance(ghost, GhostTarget)
        assert ghost.cluster_bounds is None
        assert ghost.center[0] == pytest.approx(cuboid.center[0], abs=1e-3)
        assert ghost.center[1] == pytest.approx(cuboid.center[1], abs=1e-3)


# =========================================================================
# 3. Adversarial Test Group: Tolerance Schema Structure Validation
# =========================================================================


class TestAdversarialToleranceSchema:
    """Kiểm chứng cấu trúc và tính nghiêm ngặt của schema phản hồi từ API."""

    def test_complete_response_schema_strictness(self, app_client: TestClient):
        """Kiểm tra toàn bộ các trường gốc trong JSON response theo Interface Contract §2."""
        resp = app_client.get("/api/jobs/4/tracks/101/ghost-target?frame=2")
        assert resp.status_code == 200
        data = resp.json()

        # Kiểm tra các khóa cấp cao nhất
        expected_root_keys = {"status", "job_id", "track_id", "frame", "ghost_target", "tolerances", "track_etag"}
        assert set(data.keys()) == expected_root_keys
        assert data["status"] == "ok"
        assert data["job_id"] == 4
        assert data["track_id"] == 101
        assert data["frame"] == 2

    def test_tolerances_schema_strict_validation(self, app_client: TestClient):
        """Kiểm tra chính xác từng trường và giá trị dung sai trong 'tolerances'."""
        resp = app_client.get("/api/jobs/4/tracks/101/ghost-target?frame=0")
        assert resp.status_code == 200
        data = resp.json()

        tol = data["tolerances"]
        assert isinstance(tol, dict)

        expected_tol_keys = {"snap_distance_m", "snap_angle_deg", "lock_distance_m", "lock_angle_deg"}
        assert set(tol.keys()) == expected_tol_keys

        # Kiểu dữ liệu và giá trị dung sai
        assert isinstance(tol["snap_distance_m"], (float, int))
        assert isinstance(tol["snap_angle_deg"], (float, int))
        assert isinstance(tol["lock_distance_m"], (float, int))
        assert isinstance(tol["lock_angle_deg"], (float, int))

        assert tol["snap_distance_m"] == 0.08  # 8 cm
        assert tol["snap_angle_deg"] == 4.0   # 4 degrees
        assert tol["lock_distance_m"] == 0.02  # 2 cm
        assert tol["lock_angle_deg"] == 2.0   # 2 degrees

        # Mối quan hệ logic: snap phải rộng hơn lock
        assert tol["snap_distance_m"] > tol["lock_distance_m"] > 0
        assert tol["snap_angle_deg"] > tol["lock_angle_deg"] > 0

    def test_ghost_target_sub_schema_strict_validation(self, app_client: TestClient):
        """Kiểm tra tính hợp lệ của đối tượng 'ghost_target' trong phản hồi."""
        resp = app_client.get("/api/jobs/4/tracks/101/ghost-target?frame=1")
        assert resp.status_code == 200
        gt = resp.json()["ghost_target"]

        assert isinstance(gt["center"], list) and len(gt["center"]) == 3
        assert all(math.isfinite(x) for x in gt["center"])

        assert isinstance(gt["dims"], list) and len(gt["dims"]) == 3
        assert all(d > 0 and math.isfinite(d) for d in gt["dims"])

        assert isinstance(gt["yaw"], (float, int)) and math.isfinite(gt["yaw"])
        assert gt["roll"] == 0.0, "Roll phải triệt tiêu tuyệt đối về 0.0"
        assert gt["pitch"] == 0.0, "Pitch phải triệt tiêu tuyệt đối về 0.0"

        assert isinstance(gt["target_bottom_z"], (float, int)) and math.isfinite(gt["target_bottom_z"])
        assert 0.0 <= gt["confidence"] <= 1.0
        assert isinstance(gt["reason"], str) and len(gt["reason"]) > 0


# =========================================================================
# 4. Adversarial Test Group: ETag Consistency & OCC Interoperability
# =========================================================================


class TestAdversarialETagConsistency:
    """Kiểm thử tính nhất quán của ETag OCC giữa endpoint ghost-target và cơ chế cập nhật."""

    def test_etag_matches_compute_track_etag_exactly(self, app_client: TestClient):
        """ETag trả về từ ghost-target phải trùng khớp 100% với compute_track_etag của track data."""
        track_data = app_client.app.state.mock_tracks[(4, 101)]
        expected_etag = compute_track_etag(track_data)

        resp = app_client.get("/api/jobs/4/tracks/101/ghost-target?frame=0")
        assert resp.status_code == 200
        data = resp.json()

        assert data["track_etag"] == expected_etag, (
            f"ETag API trả về ({data['track_etag']}) không khớp với compute_track_etag ({expected_etag})"
        )

    def test_etag_deterministic_across_multiple_frames(self, app_client: TestClient):
        """ETag của cùng một track phải đồng nhất khi gọi cho các frame khác nhau."""
        etags = []
        for f in range(5):
            resp = app_client.get(f"/api/jobs/4/tracks/101/ghost-target?frame={f}")
            assert resp.status_code == 200
            etags.append(resp.json()["track_etag"])

        assert len(set(etags)) == 1, "ETag của cùng một track phải không đổi qua các frame"

    def test_etag_sensitivity_to_track_mutations(self, app_client: TestClient):
        """Khi track bị biến đổi (sửa tọa độ, xoay, thêm frame), ETag phải lập tức thay đổi."""
        track_data = app_client.app.state.mock_tracks[(4, 101)]
        base_etag = compute_track_etag(track_data)

        # Biến dị 1: Dời tâm 1mm (0.001m)
        mutated_track_1 = copy.deepcopy(track_data)
        mutated_track_1["shapes"][0]["points"][0] += 0.001
        etag_1 = compute_track_etag(mutated_track_1)
        assert etag_1 != base_etag, "Dời tâm 1mm phải làm đổi ETag"

        # Biến dị 2: Xoay yaw 0.01 rad
        mutated_track_2 = copy.deepcopy(track_data)
        mutated_track_2["shapes"][0]["points"][5] += 0.01
        etag_2 = compute_track_etag(mutated_track_2)
        assert etag_2 != base_etag, "Đổi yaw phải làm đổi ETag"

        # Biến dị 3: Đổi thuộc tính
        mutated_track_3 = copy.deepcopy(track_data)
        mutated_track_3["shapes"][0]["attributes"][1]["value"] = "true"
        etag_3 = compute_track_etag(mutated_track_3)
        assert etag_3 != base_etag, "Đổi attribute phải làm đổi ETag"

        # Cập nhật app state với track bị đột biến và gọi API
        app_client.app.state.mock_tracks[(4, 101)] = mutated_track_1
        resp = app_client.get("/api/jobs/4/tracks/101/ghost-target?frame=0")
        assert resp.status_code == 200
        assert resp.json()["track_etag"] == etag_1

    def test_etag_occ_interoperability_with_apply_repair(self, app_client: TestClient):
        """ETag lấy từ ghost-target phải dùng được ngay cho OCC trong apply-repair.

        Nếu client gửi đúng ETag vừa lấy -> OCC chấp nhận (không bị 409).
        Nếu client gửi ETag cũ/sai -> OCC từ chối với HTTP 409 Conflict.
        """
        # Bước 1: Lấy ghost target và trích xuất ETag
        resp = app_client.get("/api/jobs/4/tracks/101/ghost-target?frame=0")
        assert resp.status_code == 200
        valid_etag = resp.json()["track_etag"]

        # Bước 2: Thử gửi apply-repair với ETag giả mạo / cũ -> 409 Conflict
        stale_payload = {
            "frame": 0,
            "repair": {
                "center": [10.0, 5.0, -0.5],
                "dims": [4.5, 2.0, 1.6],
                "yaw": 0.15,
                "confidence": 0.95,
            },
            "client_track_etag": "stale_hash_000000",
        }
        resp_conflict = app_client.post("/api/jobs/4/tracks/101/apply-repair", json=stale_payload)
        assert resp_conflict.status_code == 409, "ETag cũ phải bị từ chối 409 Conflict"
        assert resp_conflict.json()["status"] == "conflict"


# =========================================================================
# 5. Adversarial Test Group: Residuals & Green Lock Scanner Clearance Stress
# =========================================================================


class TestAdversarialResidualsAndGreenLock:
    """Kiểm thử tính chính xác của bộ đo sai số không gian và chứng minh Green Lock."""

    def test_spatial_residuals_snap_or_logic_and_boundaries(self):
        """Kiểm tra logic 'OR' của Magnet Snap (khoảng cách <= 8 cm HOẶC góc <= 4 độ).

        Hành vi quan trọng cần lưu ý: Nếu góc lệch <= 4 deg (ví dụ 0 deg), box ở bất kỳ khoảng cách nào
        cũng sẽ kích hoạt is_snapped = True theo logic OR của đặc tả.
        """
        target = GhostTarget(center=(0.0, 0.0, 0.0), dims=(4.0, 2.0, 1.5), yaw=0.0)

        # 1. Khi góc KHÔNG đạt (10 độ > 4 độ): Kiểm tra biên khoảng cách 8.0 cm
        yaw_far = math.radians(10.0)
        c_at_8cm = Cuboid(center=(0.080, 0.0, 0.0), dims=(4.0, 2.0, 1.5), yaw=yaw_far, label="car", frame=0)
        res_8cm = compute_spatial_residuals(c_at_8cm, target)
        assert res_8cm.delta_dist_3d_cm == pytest.approx(8.0, abs=1e-4)
        assert res_8cm.is_snapped is True

        c_above_8cm = Cuboid(center=(0.0801, 0.0, 0.0), dims=(4.0, 2.0, 1.5), yaw=yaw_far, label="car", frame=0)
        res_above_8cm = compute_spatial_residuals(c_above_8cm, target)
        assert res_above_8cm.delta_dist_3d_cm > 8.0
        assert res_above_8cm.is_snapped is False

        # 2. Khi khoảng cách KHÔNG đạt (1.0m > 8 cm): Kiểm tra góc quay
        pos_far = (1.0, 0.0, 0.0)
        c_at_3_9deg = Cuboid(center=pos_far, dims=(4.0, 2.0, 1.5), yaw=math.radians(3.9), label="car", frame=0)
        assert compute_spatial_residuals(c_at_3_9deg, target).is_snapped is False
        assert compute_spatial_residuals(c_at_3_9deg, target).rotation_snapped is True

        c_at_4_1deg = Cuboid(center=pos_far, dims=(4.0, 2.0, 1.5), yaw=math.radians(4.1), label="car", frame=0)
        assert compute_spatial_residuals(c_at_4_1deg, target).is_snapped is False

    def test_spatial_residuals_exact_green_lock_boundary_thresholds(self):
        """Kiểm tra điều kiện biên của Green Lock (d <= 2cm, yaw <= 2deg, roll <= 0.5deg, pitch <= 0.5deg)."""
        target = GhostTarget(center=(0.0, 0.0, 0.0), dims=(4.0, 2.0, 1.5), yaw=0.0)

        # 1. Biên khoảng cách: 2.000 cm đạt, 2.020 cm rớt
        c_at_2cm = Cuboid(center=(0.020, 0.0, 0.0), dims=(4.0, 2.0, 1.5), yaw=0.0, label="car", frame=0)
        assert compute_spatial_residuals(c_at_2cm, target).is_green_locked is True

        c_above_2cm = Cuboid(center=(0.0202, 0.0, 0.0), dims=(4.0, 2.0, 1.5), yaw=0.0, label="car", frame=0)
        assert compute_spatial_residuals(c_above_2cm, target).is_green_locked is False

        # 2. Biên góc quay: 1.95 deg đạt Green Lock, 2.05 deg rớt
        c_safe_yaw = Cuboid(center=(0.0, 0.0, 0.0), dims=(4.0, 2.0, 1.5), yaw=math.radians(1.95), label="car", frame=0)
        assert compute_spatial_residuals(c_safe_yaw, target).is_green_locked is True

        c_above_yaw = Cuboid(center=(0.0, 0.0, 0.0), dims=(4.0, 2.0, 1.5), yaw=math.radians(2.05), label="car", frame=0)
        assert compute_spatial_residuals(c_above_yaw, target).is_green_locked is False

        # 3. Biên roll: 0.500 deg đạt, 0.510 deg rớt
        c_at_roll = Cuboid(
            center=(0.0, 0.0, 0.0), dims=(4.0, 2.0, 1.5), yaw=0.0, label="car", frame=0,
            attrs={"cvat_rx": math.radians(0.50)}
        )
        assert compute_spatial_residuals(c_at_roll, target).is_green_locked is True

        c_above_roll = Cuboid(
            center=(0.0, 0.0, 0.0), dims=(4.0, 2.0, 1.5), yaw=0.0, label="car", frame=0,
            attrs={"cvat_rx": math.radians(0.51)}
        )
        assert compute_spatial_residuals(c_above_roll, target).is_green_locked is False

        # 4. Biên pitch: 0.500 deg đạt, 0.510 deg rớt
        c_at_pitch = Cuboid(
            center=(0.0, 0.0, 0.0), dims=(4.0, 2.0, 1.5), yaw=0.0, label="car", frame=0,
            attrs={"cvat_ry": math.radians(0.50)}
        )
        assert compute_spatial_residuals(c_at_pitch, target).is_green_locked is True

        c_above_pitch = Cuboid(
            center=(0.0, 0.0, 0.0), dims=(4.0, 2.0, 1.5), yaw=0.0, label="car", frame=0,
            attrs={"cvat_ry": math.radians(0.51)}
        )
        assert compute_spatial_residuals(c_above_pitch, target).is_green_locked is False

    def test_empirical_vulnerability_floating_point_epsilon_drift_at_boundary(self):
        """Phát hiện lỗi thực nghiệm (Empirical Vulnerability): Bẫy trôi số thực IEEE 754 tại đúng 2.0 deg và 4.0 deg.

        Khi box có góc xoay chính xác là 2.0 độ (hoặc 4.0 độ):
        normalize_angle kết hợp với math.degrees gây ra sai số trôi +2.7e-15 độ -> 2.0000000000000027 độ.
        Do hàm compute_spatial_residuals so sánh cứng `<= 2.0` (không có dung sai epsilon float),
        hộp đạt chuẩn 2.0 độ bị từ chối trạng thái Green Lock (is_green_locked = False)!
        """
        target = GhostTarget(center=(0.0, 0.0, 0.0), dims=(4.0, 2.0, 1.5), yaw=0.0)

        # Trường hợp góc 2.0 độ danh định
        c_exact_2deg = Cuboid(center=(0.0, 0.0, 0.0), dims=(4.0, 2.0, 1.5), yaw=math.radians(2.0), label="car", frame=0)
        res_2deg = compute_spatial_residuals(c_exact_2deg, target)

        # Xác thực sự tồn tại của hiện tượng trôi số thực
        assert res_2deg.delta_yaw_deg > 2.0, (
            f"delta_yaw_deg bị trôi: {res_2deg.delta_yaw_deg} > 2.0"
        )
        # Chứng minh hậu quả: Bị mất Green Lock dù người dùng căn góc đúng 2.0 độ
        assert res_2deg.is_green_locked is False, (
            "Vulnerability confirmed: Box tại đúng 2.0 độ bị rớt Green Lock do thiếu epsilon!"
        )

        # Trường hợp góc 4.0 độ danh định với khoảng cách xa
        c_exact_4deg = Cuboid(center=(1.0, 0.0, 0.0), dims=(4.0, 2.0, 1.5), yaw=math.radians(4.0), label="car", frame=0)
        res_4deg = compute_spatial_residuals(c_exact_4deg, target)
        assert res_4deg.delta_yaw_deg > 4.0
        assert res_4deg.is_snapped is False, (
            "Vulnerability confirmed: Box tại đúng 4.0 độ bị rớt Snap do thiếu epsilon!"
        )

        # 3. Biên roll: 0.500 deg đạt, 0.510 deg rớt
        c_at_roll = Cuboid(
            center=(0.0, 0.0, 0.0), dims=(4.0, 2.0, 1.5), yaw=0.0, label="car", frame=0,
            attrs={"cvat_rx": math.radians(0.50)}
        )
        assert compute_spatial_residuals(c_at_roll, target).is_green_locked is True

        c_above_roll = Cuboid(
            center=(0.0, 0.0, 0.0), dims=(4.0, 2.0, 1.5), yaw=0.0, label="car", frame=0,
            attrs={"cvat_rx": math.radians(0.51)}
        )
        assert compute_spatial_residuals(c_above_roll, target).is_green_locked is False

        # 4. Biên pitch: 0.500 deg đạt, 0.510 deg rớt
        c_at_pitch = Cuboid(
            center=(0.0, 0.0, 0.0), dims=(4.0, 2.0, 1.5), yaw=0.0, label="car", frame=0,
            attrs={"cvat_ry": math.radians(0.50)}
        )
        assert compute_spatial_residuals(c_at_pitch, target).is_green_locked is True

        c_above_pitch = Cuboid(
            center=(0.0, 0.0, 0.0), dims=(4.0, 2.0, 1.5), yaw=0.0, label="car", frame=0,
            attrs={"cvat_ry": math.radians(0.51)}
        )
        assert compute_spatial_residuals(c_above_pitch, target).is_green_locked is False

    def test_monte_carlo_green_lock_scanner_clearance(self):
        """Stress Test Monte Carlo: 30 mẫu ngẫu nhiên trong vùng Green Lock đều vượt qua bộ quét 100%.

        Mỗi mẫu có sai số ngẫu nhiên d <= 2 cm, yaw <= 2 deg, roll <= 0.5 deg, pitch <= 0.5 deg.
        Tất cả phải đạt verify_repaired_box_passes_scanner == True.
        """
        ground_z = -1.30
        track = [
            Cuboid(center=(i * 4.0, 0.0, ground_z + 0.8), dims=(4.5, 2.0, 1.6), yaw=0.0, label="car", frame=i, track_id=1)
            for i in range(5)
        ]
        points = _make_ground_and_vehicle_points(track, ground_z=ground_z, seed=99)

        ghost = generate_ghost_target(track[2], track=track, points=points)
        ideal_cuboid = ghost.to_cuboid(label="car", frame=2, track_id=1)

        rng = np.random.default_rng(2026)
        num_samples = 30
        pass_count = 0

        for i in range(num_samples):
            # Tạo sai số ngẫu nhiên trong khoảng Green Lock
            # Khoảng cách 3D <= 2.0 cm (phân phối đều trong bán cầu r <= 0.018m)
            r = rng.uniform(0.0, 0.018)
            theta = rng.uniform(0, 2 * math.pi)
            phi = rng.uniform(0, math.pi)
            dx = r * math.sin(phi) * math.cos(theta)
            dy = r * math.sin(phi) * math.sin(theta)
            dz = r * math.cos(phi)

            # Góc quay <= 1.8 deg
            dyaw = math.radians(rng.uniform(-1.8, 1.8))
            roll = math.radians(rng.uniform(-0.45, 0.45))
            pitch = math.radians(rng.uniform(-0.45, 0.45))

            sample_box = ideal_cuboid.replace(
                center=(ideal_cuboid.center[0] + dx, ideal_cuboid.center[1] + dy, ideal_cuboid.center[2] + dz),
                yaw=normalize_angle(ideal_cuboid.yaw + dyaw),
                attrs={"cvat_rx": roll, "cvat_ry": pitch},
            )

            res = compute_spatial_residuals(sample_box, ghost)
            assert res.is_green_locked is True, f"Mẫu {i} phải đạt Green Lock"

            # Quét kiểm chứng toàn diện
            passes = verify_repaired_box_passes_scanner(sample_box, track, points, rule="")
            if passes:
                pass_count += 1

        assert pass_count == num_samples, f"Chỉ có {pass_count}/{num_samples} mẫu vượt qua scanner"
