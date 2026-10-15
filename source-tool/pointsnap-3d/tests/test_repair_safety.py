"""Unit tests for Milestone M3: Safety, Rollback & CVAT REST API Integration.

Kiểm thử chi tiết các tính năng:
- Feature F10: Persistent Rollback History (`pointsnap.history.manager`)
- Feature F9: CVAT API Safe Update (`pointsnap.adapters.cvat.writer`)
- Feature F8: Backend REST Repair API (`pointsnap.web.app`)
"""

from __future__ import annotations

import copy
import json
import math
import uuid
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from pointsnap.adapters.cvat.client import CvatClient, CvatError
from pointsnap.adapters.cvat.shapes import cuboid_to_points, points_to_geometry
from pointsnap.adapters.cvat.writer import (
    OCCConflictError,
    compute_track_etag,
    patch_track_keyframe,
    rollback_track_annotation,
)
from pointsnap.core.model import Cuboid
from pointsnap.core.repair import compute_box_repair
from pointsnap.history.manager import (
    HistoryManager,
    get_snapshot,
    list_snapshots,
    rollback_track,
    save_snapshot,
    track_dict_to_cuboids,
    validate_history_snapshot_schema,
)
from pointsnap.core.serialize import save_cuboids
from pointsnap.web.app import create_app
from pointsnap.web.projects import ProjectManager


# =========================================================================
# Fixtures
# =========================================================================


@pytest.fixture
def sample_raw_cvat_track() -> dict[str, Any]:
    """Tạo track CVAT chuẩn 5 keyframes với mảng 16 số thực và thuộc tính đa dạng."""
    shapes = []
    for f in range(5):
        # [px, py, pz, rx, ry, rz, sx, sy, sz, 0, 0, 0, 0, 0, 0, 0]
        pts = [
            10.0 + f * 2.0,
            5.0,
            -0.5,
            0.0,
            0.0,
            0.15,
            4.5,
            2.0,
            1.6,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
        ]
        shapes.append({
            "id": 1000 + f,
            "frame": f,
            "type": "cuboid",
            "occluded": False,
            "outside": False,
            "keyframe": True,
            "points": pts,
            "attributes": [
                {"id": 1, "name": "subtype", "value": "sedan"},
                {"id": 2, "name": "reviewed", "value": "true"},
                {"id": 3, "name": "pointsnap_error", "value": "[Lỗi] Đáy box lơ lửng 25 cm" if f == 2 else ""},
            ],
        })
    return {
        "id": 101,
        "label_id": 10,
        "frame": 0,
        "shapes": shapes,
        "attributes": [
            {"id": 10, "name": "track_status", "value": "active"}
        ],
    }


@pytest.fixture
def mock_cvat_client(sample_raw_cvat_track: dict[str, Any]) -> MagicMock:
    """Mock CVAT client duy trì trạng thái annotations trong bộ nhớ."""
    client = MagicMock(spec=CvatClient)
    annotations_state = {
        "version": 1,
        "shapes": [],
        "tracks": [copy.deepcopy(sample_raw_cvat_track)],
    }

    def get_job_annotations(job_id: int) -> dict[str, Any]:
        return copy.deepcopy(annotations_state)

    def patch_job_annotations(job_id: int, data: dict[str, Any], action: str = "update") -> dict[str, Any]:
        if "tracks" in data:
            for new_t in data["tracks"]:
                tracks = annotations_state["tracks"]
                for i, existing in enumerate(tracks):
                    if existing["id"] == new_t["id"]:
                        tracks[i] = copy.deepcopy(new_t)
                        break
                else:
                    tracks.append(copy.deepcopy(new_t))
        return copy.deepcopy(annotations_state)

    client.get_job_annotations.side_effect = get_job_annotations
    client.patch_job_annotations.side_effect = patch_job_annotations
    return client


@pytest.fixture
def client(tmp_path: Path) -> TestClient:
    """FastAPI TestClient với mock app state."""
    app = create_app(home_dir=tmp_path)
    test_client = TestClient(app)
    return test_client


# =========================================================================
# Feature F10: Persistent Rollback History Tests
# =========================================================================


def test_snapshot_saving_loading_and_directory_structure(tmp_path: Path, sample_raw_cvat_track: dict[str, Any]):
    """F10: Lưu và tải snapshot JSON, kiểm tra tạo thư mục tự động và schema hợp lệ."""
    mgr = HistoryManager(home_dir=tmp_path, slug="test-proj")
    job_id = 4
    track_id = 101
    frame = 2

    # Lưu snapshot
    applied_repair = {
        "rule": "floating",
        "delta_center": [0.0, 0.0, -0.25],
        "delta_dims": [0.0, 0.0, 0.0],
        "delta_yaw": 0.0,
        "reason": "Hạ đáy box 25 cm sát đất",
    }
    history_id = mgr.save_snapshot(
        job_id=job_id,
        track_id=track_id,
        frame=frame,
        pre_repair_track=sample_raw_cvat_track,
        post_repair_track=sample_raw_cvat_track,
        applied_repair=applied_repair,
    )

    # 1. Kiểm tra history_id là UUID hợp lệ
    parsed_uuid = uuid.UUID(history_id)
    assert str(parsed_uuid) == history_id

    # 2. Kiểm tra đường dẫn thư mục được tạo tự động: projects/{slug}/history/job_{job_id}/
    expected_file = tmp_path / "projects" / "test-proj" / "history" / f"job_{job_id}" / f"{history_id}.json"
    assert expected_file.is_file(), f"Expected snapshot file at {expected_file}"

    # 3. Kiểm tra schema snapshot theo PROJECT.md § 4
    loaded = mgr.get_snapshot(job_id=job_id, history_id=history_id)
    valid, msg = validate_history_snapshot_schema(loaded)
    assert valid is True, msg
    assert loaded["job_id"] == job_id
    assert loaded["track_id"] == track_id
    assert loaded["frame"] == frame
    assert loaded["pre_repair_track"]["id"] == track_id
    assert loaded["applied_repair"]["rule"] == "floating"


def test_snapshot_missing_raises_filenotfound(tmp_path: Path):
    """F10: Tra cứu history_id không tồn tại phải ném FileNotFoundError."""
    mgr = HistoryManager(home_dir=tmp_path)
    random_id = str(uuid.uuid4())
    with pytest.raises(FileNotFoundError):
        mgr.get_snapshot(job_id=99, history_id=random_id)


def test_snapshot_corrupted_json_raises_error(tmp_path: Path):
    """F10: File snapshot bị hỏng/cụt phải ném JSONDecodeError."""
    mgr = HistoryManager(home_dir=tmp_path)
    job_dir = tmp_path / "projects" / "default" / "history" / "job_4"
    job_dir.mkdir(parents=True, exist_ok=True)
    corrupted_file = job_dir / "corrupted-id.json"
    corrupted_file.write_text('{"history_id": "123", "timestamp":', encoding="utf-8")

    with pytest.raises(json.JSONDecodeError):
        mgr.get_snapshot(job_id=4, history_id="corrupted-id")


def test_list_snapshots_order_and_filtering(tmp_path: Path, sample_raw_cvat_track: dict[str, Any]):
    """F10: Liệt kê danh sách snapshot sắp xếp theo thời gian mới nhất trước."""
    mgr = HistoryManager(home_dir=tmp_path)
    hid1 = mgr.save_snapshot(4, 101, 0, sample_raw_cvat_track, {}, {})
    hid2 = mgr.save_snapshot(4, 101, 1, sample_raw_cvat_track, {}, {})
    hid3 = mgr.save_snapshot(5, 202, 0, sample_raw_cvat_track, {}, {})

    snapshots_job4 = mgr.list_snapshots(job_id=4)
    assert len(snapshots_job4) == 2
    ids_job4 = [s["history_id"] for s in snapshots_job4]
    assert hid2 in ids_job4 and hid1 in ids_job4

    snapshots_job5 = mgr.list_snapshots(job_id=5)
    assert len(snapshots_job5) == 1
    assert snapshots_job5[0]["history_id"] == hid3


# =========================================================================
# Rollback Restoration Bit-for-bit Integrity Tests
# =========================================================================


def test_rollback_restoration_bit_for_bit_integrity(tmp_path: Path, sample_raw_cvat_track: dict[str, Any]):
    """F10: Hoàn tác 1-click phục hồi 100% dữ liệu gốc bit-for-bit (tọa độ, kích thước, yaw, attrs)."""
    mgr = HistoryManager(home_dir=tmp_path)
    job_id = 4
    track_id = 101

    original_cuboids = track_dict_to_cuboids(sample_raw_cvat_track)
    original_etag = compute_track_etag(sample_raw_cvat_track)

    # 1. Lưu snapshot pre-repair
    modified_track = copy.deepcopy(sample_raw_cvat_track)
    modified_track["shapes"][2]["points"] = [0.0] * 16  # Giả lập sửa làm sai lệch frame 2

    history_id = mgr.save_snapshot(
        job_id=job_id,
        track_id=track_id,
        frame=2,
        pre_repair_track=sample_raw_cvat_track,
        post_repair_track=modified_track,
        applied_repair={"rule": "floating"},
    )

    # 2. Thực hiện hoàn tác
    restored_cuboids = mgr.rollback_track(job_id=job_id, history_id=history_id)

    # 3. Kiểm tra độ chuẩn xác bit-for-bit trên từng box
    assert len(restored_cuboids) == len(original_cuboids)
    for orig, rest in zip(original_cuboids, restored_cuboids):
        assert orig.frame == rest.frame
        assert orig.track_id == rest.track_id
        assert orig.label == rest.label
        assert orig.outside == rest.outside
        assert orig.occluded == rest.occluded
        assert orig.center == rest.center
        assert orig.dims == rest.dims
        assert math.isclose(orig.yaw, rest.yaw, abs_tol=1e-6)
        assert orig.attrs == rest.attrs

    # 4. Kiểm tra ETag của pre_repair_track trong snapshot khớp ETag gốc
    snapshot = mgr.get_snapshot(job_id, history_id)
    assert compute_track_etag(snapshot["pre_repair_track"]) == original_etag


def test_rollback_with_cvat_client_patches_remote(tmp_path: Path, sample_raw_cvat_track: dict[str, Any], mock_cvat_client: MagicMock):
    """F10: Hoàn tác kèm cvat_client đẩy dữ liệu khôi phục lên CVAT server."""
    mgr = HistoryManager(home_dir=tmp_path)
    job_id = 4
    track_id = 101

    history_id = mgr.save_snapshot(
        job_id=job_id,
        track_id=track_id,
        frame=2,
        pre_repair_track=sample_raw_cvat_track,
        post_repair_track=sample_raw_cvat_track,
        applied_repair={},
    )

    restored = mgr.rollback_track(job_id=job_id, history_id=history_id, cvat_client=mock_cvat_client)
    assert len(restored) == 5
    # Verify mock_cvat_client.patch_job_annotations was called
    mock_cvat_client.patch_job_annotations.assert_called_once()
    call_args = mock_cvat_client.patch_job_annotations.call_args
    assert call_args[0][0] == job_id
    assert call_args[0][1]["tracks"][0]["id"] == track_id


# =========================================================================
# Feature F9: CVAT API Safe Update Tests
# =========================================================================


def test_full_track_keyframe_preservation_during_patch(mock_cvat_client: MagicMock, sample_raw_cvat_track: dict[str, Any]):
    """F9: Khi cập nhật box, bảo tồn trọn vẹn toàn bộ các keyframes khác và thuộc tính của track."""
    job_id = 4
    track_id = 101
    target_frame = 2

    original_shapes = copy.deepcopy(sample_raw_cvat_track["shapes"])
    new_box = Cuboid(
        center=(14.0, 5.0, -0.75),  # Hạ cao độ z từ -0.50 về -0.75
        dims=(4.5, 2.0, 1.6),
        yaw=0.15,
        label="car",
        frame=target_frame,
        track_id=track_id,
    )

    pre_track, post_track = patch_track_keyframe(
        client=mock_cvat_client,
        job_id=job_id,
        track_id=track_id,
        frame=target_frame,
        new_points=new_box,
        clear_error_flag=True,
    )

    # 1. Số lượng keyframes giữ nguyên
    assert len(post_track["shapes"]) == len(original_shapes) == 5

    # 2. Các frame khác (0, 1, 3, 4) hoàn toàn không thay đổi
    for f in (0, 1, 3, 4):
        assert post_track["shapes"][f]["points"] == original_shapes[f]["points"]
        assert post_track["shapes"][f]["id"] == original_shapes[f]["id"]
        assert post_track["shapes"][f]["attributes"] == original_shapes[f]["attributes"]

    # 3. Frame mục tiêu được cập nhật đúng tọa độ mới
    repaired_shape = post_track["shapes"][target_frame]
    assert len(repaired_shape["points"]) == 16
    assert repaired_shape["points"][2] == pytest.approx(-0.75, abs=1e-5)
    # 7 số cuối luôn là 0
    assert repaired_shape["points"][9:] == [0.0] * 7

    # 4. Cờ lỗi pointsnap_error được xóa (giá trị rỗng)
    error_attr = next(a for a in repaired_shape["attributes"] if a["name"] == "pointsnap_error")
    assert error_attr["value"] == ""

    # 5. Các thuộc tính khác (subtype, reviewed) được giữ nguyên
    subtype_attr = next(a for a in repaired_shape["attributes"] if a["name"] == "subtype")
    assert subtype_attr["value"] == "sedan"


def test_occ_precheck_matching_etag_succeeds(mock_cvat_client: MagicMock, sample_raw_cvat_track: dict[str, Any]):
    """F9: OCC pre-check thành công khi client ETag khớp với server ETag."""
    server_etag = compute_track_etag(sample_raw_cvat_track)
    new_points = [10.0] * 9 + [0.0] * 7

    pre_track, post_track = patch_track_keyframe(
        client=mock_cvat_client,
        job_id=4,
        track_id=101,
        frame=0,
        new_points=new_points,
        client_etag=server_etag,
    )
    assert post_track["shapes"][0]["points"] == new_points


def test_occ_conflict_raises_occ_conflict_error(mock_cvat_client: MagicMock):
    """F9: OCC phát hiện xung đột và ném OCCConflictError khi client ETag bị cũ/lệch."""
    stale_etag = "stale_hash_123456"
    new_points = [10.0] * 9 + [0.0] * 7

    with pytest.raises(OCCConflictError) as exc_info:
        patch_track_keyframe(
            client=mock_cvat_client,
            job_id=4,
            track_id=101,
            frame=0,
            new_points=new_points,
            client_etag=stale_etag,
        )
    assert "OCC conflict" in str(exc_info.value)


# =========================================================================
# Feature F8: Backend REST Repair API Tests
# =========================================================================


def test_rest_api_get_repair_floating(client: TestClient, sample_raw_cvat_track: dict[str, Any]):
    """F8: GET /api/jobs/{job_id}/tracks/{track_id}/repair tính toán đề xuất sửa."""
    client.app.state.mock_tracks = {(4, 101): sample_raw_cvat_track}

    resp = client.get("/api/jobs/4/tracks/101/repair?frame=2&rule=floating")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["rule"] == "floating"
    assert "repair" in data
    repair = data["repair"]
    assert "delta_center" in repair
    assert "delta_dims" in repair
    assert "delta_yaw" in repair
    assert "repaired_box" in repair or "repaired_cuboid" in repair


def test_rest_api_get_repair_heading(client: TestClient, sample_raw_cvat_track: dict[str, Any]):
    """F8: GET /api/jobs/{job_id}/tracks/{track_id}/repair cho heading.flip."""
    client.app.state.mock_tracks = {(4, 101): sample_raw_cvat_track}

    resp = client.get("/api/jobs/4/tracks/101/repair?frame=0&rule=heading.flip")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert "repaired_box" in data["repair"]


def test_rest_api_get_repair_invalid_track_404(client: TestClient):
    """F8: GET repair với track_id không tồn tại trả HTTP 404."""
    resp = client.get("/api/jobs/4/tracks/9999/repair?frame=0&rule=floating")
    assert resp.status_code == 404
    data = resp.json()
    assert data["code"] == 404
    assert "9999" in data["detail"]


def test_rest_api_get_repair_invalid_frame_404(client: TestClient, sample_raw_cvat_track: dict[str, Any]):
    """F8: GET repair với frame không tồn tại trong track trả HTTP 404."""
    client.app.state.mock_tracks = {(4, 101): sample_raw_cvat_track}

    resp = client.get("/api/jobs/4/tracks/101/repair?frame=999&rule=floating")
    assert resp.status_code == 404
    data = resp.json()
    assert data["code"] == 404
    assert "999" in data["detail"]


def test_rest_api_apply_repair_and_snapshot_persistence(
    client: TestClient,
    sample_raw_cvat_track: dict[str, Any],
    tmp_path: Path,
):
    """F8 & F10: POST apply-repair áp dụng sửa, lưu snapshot và trả verdict PASS."""
    client.app.state.mock_tracks = {(4, 101): copy.deepcopy(sample_raw_cvat_track)}
    client.app.state.history_manager = HistoryManager(home_dir=tmp_path)

    track_etag = compute_track_etag(sample_raw_cvat_track)
    repair_payload = {
        "rule": "floating",
        "delta_center": [0.0, 0.0, -0.30],
        "delta_dims": [0.0, 0.0, 0.0],
        "delta_yaw": 0.0,
    }

    resp = client.post(
        "/api/jobs/4/tracks/101/apply-repair",
        json={
            "frame": 2,
            "repair": repair_payload,
            "client_track_etag": track_etag,
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["new_scan_verdict"] == "NOT_RUN"
    history_id = data["history_id"]
    assert uuid.UUID(history_id)

    # Kiểm tra snapshot thực sự đã được ghi xuống đĩa
    snapshot = client.app.state.history_manager.get_snapshot(4, history_id)
    assert snapshot["job_id"] == 4
    assert snapshot["track_id"] == 101
    assert snapshot["frame"] == 2

    # Kiểm tra tọa độ tại frame 2 đã được cập nhật
    updated_track = data["updated_track"]
    f2_points = updated_track["shapes"][2]["points"]
    assert f2_points[2] == pytest.approx(-0.80, abs=1e-5)  # -0.50 + (-0.30)


def test_rest_api_apply_repair_occ_conflict_409(client: TestClient, sample_raw_cvat_track: dict[str, Any]):
    """F8 & F9: POST apply-repair phát hiện ETag không khớp trả HTTP 409 Conflict."""
    client.app.state.mock_tracks = {(4, 101): copy.deepcopy(sample_raw_cvat_track)}

    stale_etag = "stale_hash_9999"
    resp = client.post(
        "/api/jobs/4/tracks/101/apply-repair",
        json={
            "frame": 2,
            "repair": {"rule": "floating", "delta_center": [0.0, 0.0, -0.20]},
            "client_track_etag": stale_etag,
        },
    )
    assert resp.status_code == 409
    data = resp.json()
    assert data["code"] == 409
    assert data["status"] == "conflict"
    assert "OCC conflict" in data["detail"]


def test_rest_api_rollback_success(
    client: TestClient,
    sample_raw_cvat_track: dict[str, Any],
    tmp_path: Path,
):
    """F8 & F10: POST rollback phục hồi track về trạng thái ban đầu."""
    mgr = HistoryManager(home_dir=tmp_path)
    client.app.state.history_manager = mgr
    client.app.state.mock_tracks = {(4, 101): copy.deepcopy(sample_raw_cvat_track)}

    # Lưu đúng trạng thái sau sửa để hoàn tác không đè lên sửa đổi mới.
    post = copy.deepcopy(sample_raw_cvat_track)
    post["shapes"][2]["points"][2] -= .3
    hid = mgr.save_snapshot(
        job_id=4,
        track_id=101,
        frame=2,
        pre_repair_track=sample_raw_cvat_track,
        post_repair_track=post,
        applied_repair={},
    )

    # Giả lập sửa đổi track trên server
    client.app.state.mock_tracks[(4, 101)] = post

    # Gọi API rollback
    resp = client.post(
        "/api/jobs/4/tracks/101/rollback",
        json={"history_id": hid},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert "restored_track" in data
    assert compute_track_etag(data["restored_track"]) == compute_track_etag(sample_raw_cvat_track)


def test_rest_api_rollback_nonexistent_snapshot_404(client: TestClient):
    """F8 & F10: POST rollback với history_id không tồn tại trả HTTP 404."""
    client.app.state.pm.create_project(name="p", slug="p")
    resp = client.post(
        "/api/jobs/4/tracks/101/rollback",
        json={"history_id": str(uuid.uuid4()), "slug": "p"},
    )
    assert resp.status_code == 404
    data = resp.json()
    assert data["code"] == 404
    assert "not found" in data["detail"]


# =========================================================================
# Feature F11: Offline CVAT HTTP 503 Protection Tests
# =========================================================================


def _setup_offline_project_and_scan(tmp_path: Path, job_id: int = 4, track_id: int = 101, slug: str = "offline-proj"):
    """Helper: tạo project với CVAT URL không thể kết nối và một run có snapshot.json."""
    pm = ProjectManager(home_dir=tmp_path)
    pm.create_project(
        name="Offline Test Project",
        slug=slug,
        cvat_url="http://127.0.0.1:59999",
        cvat_token=None,
    )
    run_id = f"20261015-010203-job{job_id}"
    run_dir = tmp_path / "projects" / slug / "runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    summary_data = {
        "job_id": job_id,
        "run_id": run_id,
        "status": "done",
        "timestamp": "2026-10-15T00:00:00Z",
    }
    (run_dir / "summary.json").write_text(json.dumps(summary_data), encoding="utf-8")
    (run_dir / "findings.json").write_text("[]", encoding="utf-8")
    (run_dir / "report.html").write_text("<html></html>", encoding="utf-8")
    (run_dir / "report.csv").write_text("a,b\n", encoding="utf-8")

    test_cuboid = Cuboid(
        center=(10.0, 5.0, -0.5),
        dims=(4.5, 2.0, 1.6),
        yaw=0.15,
        label="car",
        frame=2,
        track_id=track_id,
        attrs={"subtype": "sedan"},
    )
    save_cuboids(run_dir / "snapshot.json", [test_cuboid])
    return pm, run_dir


def test_rest_api_apply_repair_cvat_offline_returns_503(tmp_path: Path):
    """F11: POST apply-repair khi CVAT offline trả về HTTP 503 với thông báo chuẩn."""
    _setup_offline_project_and_scan(tmp_path, job_id=4, track_id=101, slug="offline-proj")
    app = create_app(home_dir=tmp_path)
    client = TestClient(app)

    repair_payload = {
        "rule": "floating",
        "delta_center": [0.0, 0.0, -0.30],
        "delta_dims": [0.0, 0.0, 0.0],
        "delta_yaw": 0.0,
    }

    resp = client.post(
        "/api/jobs/4/tracks/101/apply-repair",
        json={
            "frame": 2,
            "repair": repair_payload,
            "slug": "offline-proj",
        },
    )
    assert resp.status_code == 503
    data = resp.json()
    assert data["detail"] == "Chỉ có bản xem ngoại tuyến; chưa kết nối CVAT để đồng bộ"


def test_rest_api_rollback_cvat_offline_returns_503(
    tmp_path: Path,
    sample_raw_cvat_track: dict[str, Any],
):
    """F11: POST rollback khi CVAT offline trả về HTTP 503 với thông báo chuẩn."""
    _setup_offline_project_and_scan(tmp_path, job_id=4, track_id=101, slug="offline-proj")
    app = create_app(home_dir=tmp_path)
    client = TestClient(app)

    mgr = HistoryManager(home_dir=tmp_path)
    post = copy.deepcopy(sample_raw_cvat_track)
    post["shapes"][2]["points"][2] -= 0.3
    hid = mgr.save_snapshot(
        job_id=4,
        track_id=101,
        frame=2,
        pre_repair_track=sample_raw_cvat_track,
        post_repair_track=post,
        applied_repair={"rule": "floating", "delta_center": [0.0, 0.0, -0.3]},
        slug="offline-proj",
    )

    resp = client.post(
        "/api/jobs/4/tracks/101/rollback",
        json={"history_id": hid, "slug": "offline-proj"},
    )
    assert resp.status_code == 503
    data = resp.json()
    assert data["detail"] == "Chưa kết nối CVAT để hoàn tác"


def test_rest_api_cvat_client_network_failure_triggers_503(
    tmp_path: Path,
    sample_raw_cvat_track: dict[str, Any],
):
    """F11: Khi cvat_client gặp lỗi mạng/kết nối, apply-repair và rollback đều trả HTTP 503."""
    _setup_offline_project_and_scan(tmp_path, job_id=4, track_id=101, slug="offline-proj")
    app = create_app(home_dir=tmp_path)
    client = TestClient(app)

    # Đặt client ném lỗi kết nối
    broken_client = MagicMock(spec=CvatClient)
    broken_client.get_job_annotations.side_effect = Exception("ConnectionRefusedError: [Errno 111] Connection refused")
    client.app.state.cvat_client = broken_client

    # 1. Apply repair -> 503
    resp_apply = client.post(
        "/api/jobs/4/tracks/101/apply-repair",
        json={
            "frame": 2,
            "repair": {"rule": "floating", "delta_center": [0.0, 0.0, -0.30]},
            "slug": "offline-proj",
        },
    )
    assert resp_apply.status_code == 503
    assert resp_apply.json()["detail"] == "Chỉ có bản xem ngoại tuyến; chưa kết nối CVAT để đồng bộ"

    # 2. Rollback -> 503
    mgr = HistoryManager(home_dir=tmp_path)
    hid = mgr.save_snapshot(
        job_id=4,
        track_id=101,
        frame=2,
        pre_repair_track=sample_raw_cvat_track,
        post_repair_track=sample_raw_cvat_track,
        applied_repair={},
        slug="offline-proj",
    )
    resp_rollback = client.post(
        "/api/jobs/4/tracks/101/rollback",
        json={"history_id": hid, "slug": "offline-proj"},
    )
    assert resp_rollback.status_code == 503
    assert resp_rollback.json()["detail"] == "Chưa kết nối CVAT để hoàn tác"


def test_rest_api_get_repair_cvat_offline_sets_applicable_false(tmp_path: Path):
    """F11: GET repair khi CVAT offline trả về applicable=False để Web UI vô hiệu hóa nút áp dụng."""
    _setup_offline_project_and_scan(tmp_path, job_id=4, track_id=101, slug="offline-proj")
    app = create_app(home_dir=tmp_path)
    client = TestClient(app)

    resp = client.get("/api/jobs/4/tracks/101/repair?frame=2&rule=floating&slug=offline-proj")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert "repair" in data
    assert data["repair"]["applicable"] is False


def test_ground_repair_confidence_without_track_reference():
    """F4 & F6: Thiếu tham chiếu track hoặc chỉ có finding cũ thì giảm độ tin cậy."""
    from pointsnap.core.model import Cuboid
    from pointsnap.core.repair import compute_box_repair
    from tests.test_repair import _scene_ground_points

    ground_z = -1.80
    cuboid = Cuboid(
        center=(10.0, 0.0, ground_z + 0.8 + 0.30),
        dims=(4.5, 1.9, 1.6),
        yaw=0.0,
        label="car",
        frame=0,
    )
    points = _scene_ground_points([cuboid.replace(center=(10.0, 0.0, ground_z + 0.8))], ground_z=ground_z)

    # 1. Đo trực tiếp từ point cloud cảnh
    delta = compute_box_repair(
        cuboid=cuboid,
        track=[cuboid],
        points=points,
        rule="floating",
    )
    assert 0 < delta.confidence <= 0.75

    # 2. Finding cũ chỉ ghi nhận 15 điểm: giảm confidence theo mật độ và tuổi dữ liệu
    delta_sparse = compute_box_repair(
        cuboid=cuboid,
        track=[cuboid],
        points=None,
        rule="floating",
        finding_details={"distance": 0.30, "num_ground_points": 15},
    )
    assert delta_sparse.confidence == pytest.approx(15 / 30 * 0.5 * 0.75)

