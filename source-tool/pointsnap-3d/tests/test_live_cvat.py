"""Test chạy với CVAT thật. Bỏ qua mặc định; bật bằng biến môi trường POINTSNAP_LIVE_CVAT=1.

Cần CVAT đang chạy và `CVAT_TOKEN` (đặt trong biến môi trường hoặc file `.env` ở thư mục tool).
Test tạo một task nhỏ từ bộ nuScenes giả, đọc lại, so với nhãn gốc, rồi xóa task.
"""

import os
from pathlib import Path

import pytest

import fake_nuscenes
from pointsnap.adapters.cvat.client import CvatClient
from pointsnap.adapters.cvat.reader import ManifestFrames, load_job
from pointsnap.adapters.nuscenes import NuScenesReader
from pointsnap.cli.main import load_dotenv
from pointsnap.core.config import load_config
from pointsnap.core.serialize import load_cuboids
from pointsnap.datasets.nuscenes.to_cvat import export_scene, upload_scene

TOOL_DIR = Path(__file__).resolve().parents[1]

pytestmark = pytest.mark.skipif(os.environ.get("POINTSNAP_LIVE_CVAT") != "1", reason="đặt POINTSNAP_LIVE_CVAT=1 để chạy")


@pytest.fixture
def client():
    load_dotenv(TOOL_DIR / ".env")
    config = load_config()
    return CvatClient(config.cvat.url, config.cvat.token, auth_scheme=os.environ.get("CVAT_AUTH_SCHEME", "Bearer"))


def test_upload_then_read_back_matches_ground_truth(tmp_path, client):
    reader = NuScenesReader(fake_nuscenes.build(tmp_path / "nuscenes"))
    export = export_scene(reader, "scene-0001", tmp_path / "out")
    info = upload_scene(client, export, "PointSnap live test (tự xóa)", "pointsnap_error")
    try:
        [job_id] = info["job_ids"]
        job = load_job(client, job_id)
        ManifestFrames(export.manifest).check_matches(job.frame_names)

        truth = {(b.label, b.frame): b for b in load_cuboids(export.ground_truth)[0]}
        visible = [b for b in job.cuboids if not b.outside]
        assert len(visible) == len(truth)
        for box in visible:
            expected = truth[(box.label, box.frame)]
            assert max(abs(a - e) for a, e in zip(box.center, expected.center)) < 1e-3  # < 1 mm
            assert abs(box.yaw - expected.yaw) < 1e-3
            assert box.dims == pytest.approx(expected.dims)
        assert {(b.label, b.frame) for b in job.cuboids if b.outside} == {("pedestrian", 1)}
        assert job.frame_url(2).endswith(f"/tasks/{info['task_id']}/jobs/{job_id}?frame=2")
    finally:
        client.delete_task(info["task_id"])
