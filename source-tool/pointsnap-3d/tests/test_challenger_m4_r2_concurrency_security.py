"""Empirical Challenger Test Suite for Concurrency, Rollback Fidelity, Security & Offline Network Failure.

Adversarial Stress Verification for PointSnap Assisted 3D Box Repair (Milestones M2/M4).
Harnesses:
1. High-concurrency race condition on /apply-repair with 10+ and 20+ concurrent requests sharing the same initial ETag.
   Verifies exactly 1 succeeds and all others receive HTTP 409 Conflict.
2. Rollback fidelity stress test: 25 sequential repair-and-rollback cycles.
   Verifies 100% bit-for-bit restoration of track coordinates, orientation, and attributes.
3. Security injection: malicious path traversal in history_id (../../etc/passwd, %2e%2e, null byte, etc.)
   and cross-job snapshot access. Verifies strict HTTP 400 / 404 rejection.
4. Offline CVAT stress: test offline apply and rollback requests, verifying HTTP 503 is returned consistently.
"""

from __future__ import annotations

import concurrent.futures
import copy
import json
import math
from pathlib import Path
import threading
from typing import Any
from unittest.mock import MagicMock
import uuid

import pytest
from fastapi.testclient import TestClient

from pointsnap.adapters.cvat.client import CvatClient
from pointsnap.adapters.cvat.writer import compute_track_etag
from pointsnap.core.model import Cuboid
from pointsnap.core.serialize import save_cuboids
from pointsnap.history.manager import HistoryManager, sanitize_history_id, SnapshotIsolationError
from pointsnap.web.app import create_app
from pointsnap.web.projects import ProjectManager


# =========================================================================
# Fixtures & Helpers
# =========================================================================

@pytest.fixture
def complex_stress_track() -> dict[str, Any]:
    """Track CVAT chuẩn 5 keyframes với đầy đủ thuộc tính và 16 floats per frame."""
    shapes = []
    for f in range(5):
        # [px, py, pz, rx, ry, rz, sx, sy, sz, 0, 0, 0, 0, 0, 0, 0]
        pts = [
            12.345678 + f * 1.5,
            -4.567890,
            -0.789123,
            0.012345,
            -0.023456,
            0.345678,
            4.654321,
            2.109876,
            1.765432,
            0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0,
        ]
        shapes.append({
            "id": 9000 + f,
            "frame": f,
            "type": "cuboid",
            "occluded": (f % 2 == 1),
            "outside": False,
            "keyframe": True,
            "points": list(pts),
            "attributes": [
                {"id": 1, "name": "subtype", "value": "suv"},
                {"id": 2, "name": "pointsnap_error", "value": "floating error" if f == 0 else ""},
                {"id": 3, "name": "quality_grade", "value": "A+"},
            ],
        })
    return {
        "id": 501,
        "label_id": 15,
        "label": "car",
        "frame": 0,
        "shapes": shapes,
        "attributes": [
            {"id": 100, "name": "track_status", "value": "verified"},
            {"id": 101, "name": "sensor_type", "value": "lidar_top"},
        ],
    }


def _setup_offline_project(tmp_path: Path, job_id: int = 10, track_id: int = 501, slug: str = "offline-stress-proj") -> dict[str, Any]:
    """Thiết lập một dự án ngoại tuyến hoàn chỉnh có dữ liệu scan run để track được giải quyết từ snapshot.json."""
    pm = ProjectManager(home_dir=tmp_path)
    pm.create_project(
        name="Offline Stress Project",
        slug=slug,
        cvat_url="http://127.0.0.1:59999",
        cvat_token=None,
    )

    # Tạo scan run có snapshot.json chứa track_id
    run_id = f"20261015-120000-job{job_id}"
    run_dir = tmp_path / "projects" / slug / "runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "summary.json").write_text(json.dumps({"run_id": run_id, "job_id": job_id, "findings_count": 1}), encoding="utf-8")
    (run_dir / "findings.json").write_text("[]", encoding="utf-8")

    cuboid = Cuboid(
        center=(10.0, 5.0, -0.5),
        dims=(4.5, 2.0, 1.6),
        yaw=0.15,
        label="car",
        frame=0,
        track_id=track_id,
        source_id=9000,
        keyframe=True,
        attrs={"subtype": "suv", "pointsnap_error": "floating error"},
    )
    save_cuboids(run_dir / "snapshot.json", [cuboid])
    return {"slug": slug, "job_id": job_id, "track_id": track_id}


# =========================================================================
# 1. High-Concurrency Race Condition on /apply-repair
# =========================================================================

class TestConcurrencyOCCRaceCondition:
    """Stress-test Concurrency OCC race conditions on /apply-repair with 10+ and 20+ threads."""

    def test_high_concurrency_10_concurrent_requests_same_initial_etag_exactly_one_succeeds(
        self, tmp_path: Path, complex_stress_track: dict[str, Any]
    ):
        """10 concurrent threads attempt to apply-repair presenting the EXACT same initial ETag.
        Requirement: Exactly 1 succeeds (HTTP 200), and exactly 9 receive HTTP 409 Conflict.
        Zero 500 errors. No lost updates.
        """
        app = create_app(home_dir=tmp_path)
        job_id = 4
        track_id = 501
        app.state.mock_tracks = {(job_id, track_id): copy.deepcopy(complex_stress_track)}
        client = TestClient(app)

        initial_etag = compute_track_etag(complex_stress_track)
        num_threads = 10
        barrier = threading.Barrier(num_threads)
        responses: list[tuple[int, dict[str, Any]]] = []
        lock = threading.Lock()

        def worker_task(thread_idx: int):
            dz = -0.10 * (thread_idx + 1)
            payload = {
                "frame": 0,
                "repair": {
                    "rule": "floating",
                    "delta_center": [0.0, 0.0, dz],
                    "delta_dims": [0.0, 0.0, 0.0],
                    "delta_yaw": 0.0,
                },
                "client_track_etag": initial_etag,
            }
            # Đồng bộ tất cả các luồng để bắn request cùng một nano-giây
            barrier.wait()
            resp = client.post(f"/api/jobs/{job_id}/tracks/{track_id}/apply-repair", json=payload)
            with lock:
                responses.append((resp.status_code, resp.json()))

        with concurrent.futures.ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(worker_task, i) for i in range(num_threads)]
            for f in concurrent.futures.as_completed(futures):
                f.result()

        status_codes = [r[0] for r in responses]
        success_count = status_codes.count(200)
        conflict_count = status_codes.count(409)

        assert success_count == 1, f"Expected exactly 1 success (200), got {success_count}. Statuses: {status_codes}"
        assert conflict_count == num_threads - 1, f"Expected {num_threads - 1} conflicts (409), got {conflict_count}. Statuses: {status_codes}"
        assert 500 not in status_codes, f"Server crash 500 detected in: {status_codes}"

        # Xác thực chi tiết của 409 Conflict phản hồi đúng OCC
        conflict_responses = [r[1] for r in responses if r[0] == 409]
        for cr in conflict_responses:
            assert cr.get("status") == "conflict"
            assert "OCC conflict" in cr.get("detail", "")

        # Xác thực trạng thái track trong DB/state có đúng 1 sửa đổi
        final_track = app.state.mock_tracks[(job_id, track_id)]
        final_etag = compute_track_etag(final_track)
        assert final_etag != initial_etag

    def test_high_concurrency_20_concurrent_requests_same_initial_etag_exactly_one_succeeds(
        self, tmp_path: Path, complex_stress_track: dict[str, Any]
    ):
        """20 concurrent threads attempt to apply-repair with the same initial ETag.
        Requirement: Exactly 1 succeeds (HTTP 200), and exactly 19 receive HTTP 409 Conflict.
        """
        app = create_app(home_dir=tmp_path)
        job_id = 4
        track_id = 501
        app.state.mock_tracks = {(job_id, track_id): copy.deepcopy(complex_stress_track)}
        client = TestClient(app)

        initial_etag = compute_track_etag(complex_stress_track)
        num_threads = 20
        barrier = threading.Barrier(num_threads)
        responses: list[tuple[int, dict[str, Any]]] = []
        lock = threading.Lock()

        def worker_task(thread_idx: int):
            dz = -0.05 * (thread_idx + 1)
            payload = {
                "frame": 0,
                "repair": {
                    "rule": "floating",
                    "delta_center": [0.0, 0.0, dz],
                    "delta_dims": [0.0, 0.0, 0.0],
                    "delta_yaw": 0.0,
                },
                "client_track_etag": initial_etag,
            }
            barrier.wait()
            resp = client.post(f"/api/jobs/{job_id}/tracks/{track_id}/apply-repair", json=payload)
            with lock:
                responses.append((resp.status_code, resp.json()))

        with concurrent.futures.ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(worker_task, i) for i in range(num_threads)]
            for f in concurrent.futures.as_completed(futures):
                f.result()

        status_codes = [r[0] for r in responses]
        success_count = status_codes.count(200)
        conflict_count = status_codes.count(409)

        assert success_count == 1, f"Expected exactly 1 success (200), got {success_count}. Statuses: {status_codes}"
        assert conflict_count == num_threads - 1, f"Expected {num_threads - 1} conflicts (409), got {conflict_count}"
        assert 500 not in status_codes


# =========================================================================
# 2. Rollback Fidelity Stress: 20+ Sequential Repair-and-Rollback Cycles
# =========================================================================

class TestRollbackFidelitySequentialStress:
    """Stress-test rollback fidelity across 25 sequential cycles with bit-for-bit assertion."""

    def test_rollback_fidelity_25_sequential_cycles_bit_for_bit(
        self, tmp_path: Path, complex_stress_track: dict[str, Any]
    ):
        """Execute 25 sequential repair-and-rollback cycles.
        In each cycle:
        1. Apply a distinct geometric repair (z, yaw, dims).
        2. Verify track is modified and ETag changes.
        3. Execute rollback with the generated history_id.
        4. Assert 100% bit-for-bit restoration of all 16 coordinates across all frames,
           track attributes, shape attributes, and canonical ETag.
        """
        app = create_app(home_dir=tmp_path)
        job_id = 4
        track_id = 501
        app.state.mock_tracks = {(job_id, track_id): copy.deepcopy(complex_stress_track)}
        client = TestClient(app)

        initial_etag = compute_track_etag(complex_stress_track)
        initial_shapes = copy.deepcopy(complex_stress_track["shapes"])
        initial_attrs = copy.deepcopy(complex_stress_track["attributes"])

        num_cycles = 25
        for cycle in range(num_cycles):
            target_frame = cycle % 5
            dz = -0.15 - (cycle * 0.02)
            dyaw = (cycle * 0.1) % (2 * math.pi)

            # ETag trước khi sửa ở chu kỳ này phải trùng khớp với initial_etag
            current_track = app.state.mock_tracks[(job_id, track_id)]
            assert compute_track_etag(current_track) == initial_etag, f"Cycle {cycle}: Pre-repair track is not restored to baseline"

            # 1. Apply repair
            apply_resp = client.post(
                f"/api/jobs/{job_id}/tracks/{track_id}/apply-repair",
                json={
                    "frame": target_frame,
                    "repair": {
                        "rule": "floating",
                        "delta_center": [0.0, 0.0, dz],
                        "delta_dims": [0.0, 0.0, 0.0],
                        "delta_yaw": dyaw,
                    },
                    "client_track_etag": initial_etag,
                },
            )
            assert apply_resp.status_code == 200, f"Cycle {cycle} apply failed: {apply_resp.text}"
            apply_data = apply_resp.json()
            history_id = apply_data["history_id"]
            updated_track = apply_data["updated_track"]
            updated_etag = compute_track_etag(updated_track)

            # Kiểm tra ETag đã thay đổi sau khi sửa
            assert updated_etag != initial_etag, f"Cycle {cycle}: ETag failed to update after repair"

            # 2. Execute rollback
            rollback_resp = client.post(
                f"/api/jobs/{job_id}/tracks/{track_id}/rollback",
                json={"history_id": history_id},
            )
            assert rollback_resp.status_code == 200, f"Cycle {cycle} rollback failed: {rollback_resp.text}"
            rollback_data = rollback_resp.json()
            restored_track = rollback_data["restored_track"]

            # 3. Bit-for-bit assertion across all 5 keyframes (16 floats per frame)
            assert len(restored_track["shapes"]) == len(initial_shapes)
            for f_idx in range(len(initial_shapes)):
                expected_shape = initial_shapes[f_idx]
                actual_shape = restored_track["shapes"][f_idx]

                # Points array bit-for-bit check
                assert actual_shape["points"] == expected_shape["points"], (
                    f"Cycle {cycle}, frame {f_idx}: Points mismatch! "
                    f"Expected {expected_shape['points']}, got {actual_shape['points']}"
                )
                # Attributes check
                assert actual_shape["attributes"] == expected_shape["attributes"]
                assert actual_shape["occluded"] == expected_shape["occluded"]
                assert actual_shape["outside"] == expected_shape["outside"]
                assert actual_shape["keyframe"] == expected_shape["keyframe"]

            # Track-level attributes and ETag bit-for-bit restoration
            assert restored_track["attributes"] == initial_attrs
            assert compute_track_etag(restored_track) == initial_etag

        # Cuối 25 chu kỳ, xác nhận danh sách snapshot trong HistoryManager đúng 25 bản ghi
        history_mgr = app.state.history_manager
        snapshots = history_mgr.list_snapshots(job_id=job_id)
        assert len(snapshots) == num_cycles


# =========================================================================
# 3. Security Injection & Malicious Path Traversal Stress
# =========================================================================

class TestSecurityIsolationAndPathTraversal:
    """Stress-test malicious path traversal payloads and cross-job isolation."""

    @pytest.mark.parametrize(
        "malicious_history_id",
        [
            "../../etc/passwd",
            "..\\..\\windows\\win.ini",
            "%2e%2e/%2e%2e/etc/passwd",
            "..%2f..%2fetc/passwd",
            "../../../../../../../../../../etc/passwd",
            "/etc/shadow",
            "C:\\boot.ini",
            "../job_4/other_snap",
            "test\0hidden",
            "valid-uuid; rm -rf /",
            "valid-uuid' OR '1'='1",
            "<script>alert(1)</script>",
            "   ",
            "",
            "....//....//etc/passwd",
            "..;/..;/etc/passwd",
        ],
    )
    def test_history_id_path_traversal_attacks_strict_rejection(
        self, tmp_path: Path, complex_stress_track: dict[str, Any], malicious_history_id: str
    ):
        """Attempt malicious path traversal payloads in history_id.
        Requirement: Strict rejection with HTTP 400 or HTTP 404.
        Never HTTP 200, never HTTP 500. No filesystem leakage.
        """
        app = create_app(home_dir=tmp_path)
        job_id = 4
        track_id = 501
        app.state.mock_tracks = {(job_id, track_id): copy.deepcopy(complex_stress_track)}
        client = TestClient(app)

        resp = client.post(
            f"/api/jobs/{job_id}/tracks/{track_id}/rollback",
            json={"history_id": malicious_history_id},
        )

        assert resp.status_code in (400, 404, 422), (
            f"Malicious payload '{malicious_history_id}' was not rejected! "
            f"Got status {resp.status_code}: {resp.text}"
        )
        assert resp.status_code != 500, f"Server crashed with 500 on payload '{malicious_history_id}'"

    def test_cross_job_snapshot_access_isolation(
        self, tmp_path: Path, complex_stress_track: dict[str, Any]
    ):
        """Verify cross-job and cross-track snapshot theft is strictly blocked with HTTP 400."""
        app = create_app(home_dir=tmp_path)
        # Thiết lập Job 1 Track 100 và Job 2 Track 200
        track_j1_t100 = copy.deepcopy(complex_stress_track)
        track_j1_t100["id"] = 100
        track_j2_t200 = copy.deepcopy(complex_stress_track)
        track_j2_t200["id"] = 200

        app.state.mock_tracks = {
            (1, 100): copy.deepcopy(track_j1_t100),
            (2, 200): copy.deepcopy(track_j2_t200),
        }
        client = TestClient(app)

        # 1. Tạo snapshot cho Job 1 Track 100
        etag1 = compute_track_etag(track_j1_t100)
        res1 = client.post(
            "/api/jobs/1/tracks/100/apply-repair",
            json={
                "frame": 0,
                "repair": {"rule": "floating", "delta_center": [0, 0, -0.2]},
                "client_track_etag": etag1,
            },
        )
        assert res1.status_code == 200
        snap_id_j1_t100 = res1.json()["history_id"]

        # 2. Cố tình dùng snapshot của Job 1 Track 100 để rollback Job 2 Track 200 (Cross-job & Cross-track)
        theft_resp1 = client.post(
            "/api/jobs/2/tracks/200/rollback",
            json={"history_id": snap_id_j1_t100},
        )
        assert theft_resp1.status_code == 400
        assert "does not belong to job 2 track 200" in theft_resp1.json()["detail"]

        # 3. Cố tình dùng snapshot của Job 1 Track 100 để rollback Job 1 Track 200 (Cross-track same job)
        app.state.mock_tracks[(1, 200)] = copy.deepcopy(track_j2_t200)
        theft_resp2 = client.post(
            "/api/jobs/1/tracks/200/rollback",
            json={"history_id": snap_id_j1_t100},
        )
        assert theft_resp2.status_code == 400
        assert "does not belong to job 1 track 200" in theft_resp2.json()["detail"]

        # 4. Cố tình dùng snapshot của Job 1 Track 100 để rollback Job 999 Track 100 (Cross-job same track)
        app.state.mock_tracks[(999, 100)] = copy.deepcopy(track_j1_t100)
        theft_resp3 = client.post(
            "/api/jobs/999/tracks/100/rollback",
            json={"history_id": snap_id_j1_t100},
        )
        assert theft_resp3.status_code in (400, 404)

    @pytest.mark.parametrize(
        "malicious_slug",
        [
            "../../etc",
            "..\\..\\windows",
            "slug/with/slash",
            "slug\0null",
            "default;rm -rf",
        ],
    )
    def test_slug_path_traversal_injection_rejected(
        self, tmp_path: Path, complex_stress_track: dict[str, Any], malicious_slug: str
    ):
        """Attempt path traversal injection via project slug parameter."""
        app = create_app(home_dir=tmp_path)
        job_id = 4
        track_id = 501
        app.state.mock_tracks = {(job_id, track_id): copy.deepcopy(complex_stress_track)}
        client = TestClient(app)

        resp = client.post(
            f"/api/jobs/{job_id}/tracks/{track_id}/rollback",
            json={"history_id": str(uuid.uuid4()), "slug": malicious_slug},
        )
        assert resp.status_code in (400, 404, 422)
        assert resp.status_code != 500


# =========================================================================
# 4. Offline CVAT Network Failure Stress
# =========================================================================

class TestOfflineCvatNetworkFailureStress:
    """Stress-test offline CVAT network failures and 503 response guarantees."""

    def test_offline_cvat_apply_repair_returns_503_consistently(self, tmp_path: Path):
        """15 sequential apply-repair requests in offline mode consistently return HTTP 503."""
        info = _setup_offline_project(tmp_path, job_id=10, track_id=501, slug="offline-proj-apply")
        app = create_app(home_dir=tmp_path)
        client = TestClient(app)

        for i in range(15):
            resp = client.post(
                f"/api/jobs/{info['job_id']}/tracks/{info['track_id']}/apply-repair",
                json={
                    "frame": 0,
                    "repair": {"rule": "floating", "delta_center": [0.0, 0.0, -0.25]},
                    "slug": info["slug"],
                },
            )
            assert resp.status_code == 503, f"Call {i} expected 503, got {resp.status_code}: {resp.text}"
            assert resp.json()["detail"] == "Chỉ có bản xem ngoại tuyến; chưa kết nối CVAT để đồng bộ"

    def test_offline_cvat_rollback_returns_503_consistently(self, tmp_path: Path, complex_stress_track: dict[str, Any]):
        """15 sequential rollback requests in offline mode consistently return HTTP 503."""
        info = _setup_offline_project(tmp_path, job_id=10, track_id=501, slug="offline-proj-rollback")
        app = create_app(home_dir=tmp_path)
        client = TestClient(app)

        # Lưu sẵn một snapshot hợp lệ
        mgr = HistoryManager(home_dir=tmp_path)
        hid = mgr.save_snapshot(
            job_id=info["job_id"],
            track_id=info["track_id"],
            frame=0,
            pre_repair_track=complex_stress_track,
            post_repair_track=complex_stress_track,
            applied_repair={"rule": "floating"},
            slug=info["slug"],
        )

        for i in range(15):
            resp = client.post(
                f"/api/jobs/{info['job_id']}/tracks/{info['track_id']}/rollback",
                json={"history_id": hid, "slug": info["slug"]},
            )
            assert resp.status_code == 503, f"Call {i} expected 503, got {resp.status_code}: {resp.text}"
            assert resp.json()["detail"] == "Chưa kết nối CVAT để hoàn tác"

    def test_offline_cvat_get_repair_sets_applicable_false(self, tmp_path: Path):
        """GET /repair in offline mode sets applicable=False so UI locks apply button."""
        info = _setup_offline_project(tmp_path, job_id=10, track_id=501, slug="offline-proj-get")
        app = create_app(home_dir=tmp_path)
        client = TestClient(app)

        resp = client.get(f"/api/jobs/{info['job_id']}/tracks/{info['track_id']}/repair?frame=0&rule=floating&slug={info['slug']}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["repair"]["applicable"] is False
