"""A14: xem nhanh point cloud quanh box và lưu kết luận xem tay."""

from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pytest
from fastapi.testclient import TestClient

from pointsnap.core.model import Cuboid
from pointsnap.web.app import create_app
from pointsnap.web.preview import points_around_box

RUN_ID = "20261008-120000-123-job2"


def test_points_around_box_uses_box_frame_and_crops():
    box = Cuboid(center=(10.0, 5.0, 0.0), dims=(4.0, 2.0, 1.5), yaw=math.pi / 2, label="car", frame=0)
    points = np.array([
        [10.0, 6.0, 0.0, 0, 0],   # 1 m phía trước đầu xe (yaw 90°: đầu xe hướng +y)
        [9.0, 5.0, -0.75, 0, 0],  # 1 m bên trái xe, ở đáy box
        [40.0, 5.0, 0.0, 0, 0],   # quá xa, bị bỏ
        [10.0, 5.0, 5.0, 0, 0],   # quá cao, bị bỏ
    ])
    local = points_around_box(points, box)
    assert local.shape == (2, 3)
    np.testing.assert_allclose(local[0], [1.0, 0.0, 0.0], atol=1e-9)
    np.testing.assert_allclose(local[1], [0.0, 1.0, -0.75], atol=1e-9)

    many = np.zeros((10_000, 3)) + np.array([10.0, 5.0, 0.0])
    assert len(points_around_box(many, box, max_points=500)) == 500


@pytest.fixture()
def client_with_run(tmp_path: Path):
    client = TestClient(create_app(tmp_path))
    assert client.post("/api/projects", json={"name": "a14", "slug": "a14"}).status_code == 201
    run_dir = tmp_path / "projects" / "a14" / "runs" / RUN_ID
    run_dir.mkdir(parents=True)
    (run_dir / "summary.json").write_text(json.dumps({"job_id": 2, "timestamp": "2026-10-08T12:00:00"}), encoding="utf-8")
    findings = [{"rule": "floating", "frame": 1, "track_id": 5}, {"rule": "track.jump", "frame": 2, "track_id": 6}]
    (run_dir / "findings.json").write_text(json.dumps(findings), encoding="utf-8")
    return client


def test_review_roundtrip(client_with_run: TestClient):
    url = f"/api/projects/a14/scans/{RUN_ID}"
    assert client_with_run.get(url).json()["reviews"] == {}

    res = client_with_run.put(f"{url}/reviews/1", json={"verdict": "fp"})
    assert res.status_code == 200 and res.json()["reviews"] == {"1": "fp"}
    client_with_run.put(f"{url}/reviews/0", json={"verdict": "ok"})
    assert client_with_run.get(url).json()["reviews"] == {"1": "fp", "0": "ok"}

    assert client_with_run.put(f"{url}/reviews/1", json={"verdict": None}).json()["reviews"] == {"0": "ok"}
    assert client_with_run.put(f"{url}/reviews/5", json={"verdict": "ok"}).status_code == 404
    assert client_with_run.put(f"{url}/reviews/0", json={"verdict": "maybe"}).status_code == 422


def test_preview_without_snapshot_explains(client_with_run: TestClient):
    res = client_with_run.get(f"/api/projects/a14/scans/{RUN_ID}/findings/0/preview")
    assert res.status_code == 422
    assert "snapshot" in res.json()["detail"]


def test_ui_files_are_revalidated(client_with_run: TestClient):
    assert client_with_run.get("/").headers["cache-control"] == "no-cache"
    assert client_with_run.get("/static/app.js").headers["cache-control"] == "no-cache"


def test_concurrent_reviews_are_not_lost(client_with_run: TestClient, tmp_path: Path):
    """Nhiều yêu cầu ghi kết luận cùng lúc không làm mất kết luận nào (góp ý review PR #29)."""
    from concurrent.futures import ThreadPoolExecutor

    from pointsnap.web.preview import load_reviews, save_review

    run_dir = tmp_path / "projects" / "a14" / "runs" / RUN_ID
    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(lambda i: save_review(run_dir, i, "ok" if i % 2 else "fp"), range(40)))
    assert len(load_reviews(run_dir)) == 40
    assert not (run_dir / "reviews.json.tmp").exists()


def test_ui_fonts_are_served_locally(client_with_run: TestClient):
    """Giao diện không tải font từ Google, chạy được khi không có mạng (góp ý review PR #28)."""
    html = client_with_run.get("/").text
    assert "fonts.googleapis.com" not in html and "/static/fonts/fonts.css" in html
    css = client_with_run.get("/static/fonts/fonts.css")
    assert css.status_code == 200 and "IBM Plex Sans" in css.text
    assert client_with_run.get("/static/fonts/ibm-plex-sans-400-vietnamese.woff2").status_code == 200


def test_learn_endpoint_uses_reviews(client_with_run: TestClient):
    """Lớp 4 (C3): học từ kết luận đã ghi, lưu learned.json, GET trả lại bản đang dùng."""
    assert client_with_run.get("/api/projects/a14/learn").json() == {"model": None, "report": None}
    url = f"/api/projects/a14/scans/{RUN_ID}"
    client_with_run.put(f"{url}/reviews/0", json={"verdict": "ok"})
    client_with_run.put(f"{url}/reviews/1", json={"verdict": "fp"})
    res = client_with_run.post("/api/projects/a14/learn")
    assert res.status_code == 200
    model = res.json()["model"]
    assert model["version"] == 1 and model["n_samples"] == 2 and not model["use_model"]
    assert model["rule_stats"]["floating"]["ok"] == 1 and model["rule_stats"]["track.jump"]["fp"] == 1
    assert "Học từ 2 kết luận" in res.json()["report"]
    assert client_with_run.get("/api/projects/a14/learn").json()["model"]["version"] == 1
    assert client_with_run.post("/api/projects/a14/learn").json()["model"]["version"] == 2
    assert client_with_run.post("/api/projects/khong-co/learn").status_code == 404


def test_preview_ground_is_in_box_frame_and_only_for_measured_findings():
    from pointsnap.web.preview import preview_ground

    box = Cuboid(center=(10.0, 0.0, -0.9), dims=(4.0, 2.0, 1.6), yaw=0.0, label="car", frame=0, track_id=1)
    assert preview_ground({"details": {"ground_z": -1.9, "pitch_deg": 2.5}}, box) == {"z": -1.0, "pitch_deg": 2.5}
    assert preview_ground({"details": {"ground_z": -1.9}}, box) == {"z": -1.0, "pitch_deg": 0.0}
    assert preview_ground({"details": {}}, box) is None
    assert preview_ground({"details": {"ground_z": float("nan")}}, box) is None


def test_finding_camera_draws_box_on_best_camera(tmp_path, monkeypatch):
    """Ảnh camera của finding: chọn camera thấy box, trả JPEG kèm tên kênh; box sau mọi camera thì báo rõ."""
    pytest.importorskip("PIL")
    from types import SimpleNamespace

    from PIL import Image

    from pointsnap.core.camera import CameraView
    from pointsnap.web import preview

    img = tmp_path / "front.jpg"
    Image.new("RGB", (1600, 900), (90, 90, 90)).save(img)
    # Camera nhìn theo +x của xe: trục z camera = x thế giới, x camera = -y, y camera = -z.
    cam_to_world = np.eye(4)
    cam_to_world[:3, :3] = np.array([[0, 0, 1], [-1, 0, 0], [0, -1, 0]], dtype=float)
    view = CameraView("CAM_FRONT", img, np.array([[1000, 0, 800], [0, 1000, 450], [0, 0, 1]], float), cam_to_world, 1600, 900)
    frames = SimpleNamespace(frame_data=lambda frame, with_points=True: SimpleNamespace(sensor_to_world=np.eye(4)),
                             camera_views=lambda frame: [view])
    box = Cuboid(center=(10.0, 0.0, 0.0), dims=(4.0, 2.0, 1.6), yaw=0.0, label="car", frame=0, track_id=1)
    monkeypatch.setattr(preview, "_finding_box", lambda run_dir, project, index: ({}, box, frames))
    jpeg, channel = preview.finding_camera(tmp_path, {}, 0)
    assert channel == "CAM_FRONT" and jpeg[:2] == b"\xff\xd8"
    behind = Cuboid(center=(-10.0, 0.0, 0.0), dims=(4.0, 2.0, 1.6), yaw=0.0, label="car", frame=0, track_id=1)
    monkeypatch.setattr(preview, "_finding_box", lambda run_dir, project, index: ({}, behind, frames))
    with pytest.raises(preview.PreviewError, match="Không camera nào"):
        preview.finding_camera(tmp_path, {}, 0)
