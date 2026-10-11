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
from pointsnap.adapters.cvat.writer import flag_job_errors, clear_job_errors, verify_geometry_preserved
from pointsnap.adapters.nuscenes import NuScenesReader
from pointsnap.cli.main import load_dotenv
from pointsnap.core.config import load_config
from pointsnap.core.model import ErrorType, Finding, Severity
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


def test_flag_then_rescan_on_live_cvat(tmp_path, client):
    """A4 trên CVAT thật: ghi cờ, đọc lại, quét lại gỡ cờ; hình học box không đổi suốt quá trình."""
    reader = NuScenesReader(fake_nuscenes.build(tmp_path / "nuscenes"))
    export = export_scene(reader, "scene-0001", tmp_path / "out")
    info = upload_scene(client, export, "PointSnap live test cờ lỗi (tự xóa)", "pointsnap_error")
    try:
        [job_id] = info["job_ids"]
        before = load_job(client, job_id)
        target = next(b for b in before.cuboids if b.track_id is not None and not b.outside)
        finding = Finding(error_type=ErrorType.SIZE, rule="size.in_track", severity=Severity.ERROR,
                          frame=target.frame, label=target.label, track_id=target.track_id,
                          source_id=target.source_id, message="Lệch kích thước (test live)")

        summary = flag_job_errors(client, before, [finding], snapshot_path=tmp_path / "snap.json")
        assert (summary.flagged, summary.cleared, summary.unmatched) == (1, 0, 0)

        flagged = load_job(client, job_id)
        _assert_same_geometry(before.cuboids, flagged.cuboids)
        flags = {(b.track_id, b.frame): b.attrs.get("pointsnap_error") for b in flagged.cuboids}
        assert flags.pop((target.track_id, target.frame)) == "[Lỗi] Lệch kích thước (test live)"
        assert not any(flags.values())

        # Quét lại khi box đã hết lỗi: cờ tự gỡ.
        summary = flag_job_errors(client, flagged, [])
        assert (summary.flagged, summary.cleared) == (0, 1)
        cleared = load_job(client, job_id)
        _assert_same_geometry(before.cuboids, cleared.cuboids)
        assert not any(b.attrs.get("pointsnap_error") for b in cleared.cuboids)
    finally:
        client.delete_task(info["task_id"])


def _assert_same_geometry(before, after):
    """So hình học theo (track, frame, label); không dựa vào id shape vì CVAT có thể cấp id mới khi update."""
    key = lambda b: (b.track_id if b.track_id is not None else -1, b.frame, b.label, b.center)
    before, after = sorted(before, key=key), sorted(after, key=key)
    assert len(before) == len(after)
    for b, a in zip(before, after):
        assert (b.track_id, b.frame, b.label, b.outside) == (a.track_id, a.frame, a.label, a.outside)
        assert a.center == pytest.approx(b.center, abs=1e-6)
        assert a.dims == pytest.approx(b.dims, abs=1e-6)
        assert a.yaw == pytest.approx(b.yaw, abs=1e-6)


def test_flag_tilted_shapes_preserves_all_other_annotations(tmp_path, client):
    """Kiểm shape lẻ, roll/pitch, attrs và idempotency trên API thật; chỉ task thử riêng."""
    import copy
    reader = NuScenesReader(fake_nuscenes.build(tmp_path / 'nuscenes'))
    export = export_scene(reader, 'scene-0001', tmp_path / 'out')
    info = upload_scene(client, export, 'PointSnap live test shape/tilt (tự xóa)', 'pointsnap_error')
    try:
        [job_id] = info['job_ids']
        labels = client.task_labels(info['task_id'])
        label = next(l for l in labels if l['name'] == 'car')
        reviewed = next(a['id'] for a in label['attributes'] if a['name'] == 'reviewed')
        client.patch_job_annotations(job_id, {'shapes': [{'type': 'cuboid', 'label_id': label['id'],
            'frame': 1, 'points': [20, 0, 1, .1, -.2, .3, 4, 2, 1.5] + [0.] * 7,
            'occluded': True, 'rotation': 0, 'z_order': 0, 'attributes': [{'spec_id': reviewed, 'value': 'true'}]}]}, action='create')
        before = load_job(client, job_id)
        target = next(b for b in before.cuboids if b.track_id is None)
        finding = Finding(error_type=ErrorType.SIZE, rule='size.in_track', severity=Severity.ERROR,
                          frame=target.frame, label=target.label, source_id=target.source_id, message='Ca shape lẻ')
        first = flag_job_errors(client, before, [finding])
        after = load_job(client, job_id)
        verify_geometry_preserved(before.cuboids, after.cuboids)
        tilted = next(b for b in after.cuboids if b.track_id is None)
        assert tilted.attrs['reviewed'] == 'true'
        assert (tilted.attrs['cvat_rx'], tilted.attrs['cvat_ry']) == (.1, -.2)
        again = flag_job_errors(client, after, [Finding(error_type=finding.error_type, rule=finding.rule,
            severity=finding.severity, frame=tilted.frame, label=tilted.label, source_id=tilted.source_id, message=finding.message)])
        assert (first.flagged, again.flagged, again.cleared, again.unmatched) == (1, 0, 0, 0)
        assert clear_job_errors(client, load_job(client, job_id)) == 1
        final = load_job(client, job_id)
        verify_geometry_preserved(before.cuboids, final.cuboids)
        def without_ids_and_flags(raw):
            result = copy.deepcopy(raw)
            for shape in [*result['shapes'], *(s for t in result['tracks'] for s in t['shapes'])]:
                shape.pop('id', None)
                shape['attributes'] = [a for a in shape['attributes'] if a['spec_id'] not in {
                    attr['id'] for l in labels for attr in l['attributes'] if attr['name'] == 'pointsnap_error'}]
            return result
        assert without_ids_and_flags(before.raw_annotations) == without_ids_and_flags(final.raw_annotations)
    finally:
        client.delete_task(info['task_id'])
