"""Ca hồi quy review 03: đọc đúng dữ liệu và bảo toàn nhãn khi ghi CVAT."""

import copy
import json

import numpy as np
import pytest

import fake_nuscenes
from test_cvat_client import FakeResponse, FakeSession
from test_cvat_writer import API_LABELS, RAW_ANNOTATIONS, MockSession, pts
from pointsnap.adapters.cvat.client import CvatClient, CvatError
from pointsnap.adapters.cvat.reader import JobData, ManifestFrames, annotations_to_cuboids, labels_from_api, find_manifest
from pointsnap.adapters.cvat.writer import build_error_patch, build_findings_map, flag_job_errors, verify_geometry_preserved
from pointsnap.adapters.nuscenes import NuScenesReader
from pointsnap.core.model import ErrorType, Finding, Severity
from pointsnap.datasets.nuscenes.to_cvat import export_scene, upload_scene
from pointsnap.datasets.pcd import read_pcd, write_pcd


def test_pagination_never_sends_auth_to_a_foreign_origin():
    class GuardSession(FakeSession):
        def request(self, method, url, **kwargs):
            assert 'other.invalid' not in url, 'Attempted to send token to foreign URL'
            return super().request(method, url, **kwargs)
    session = GuardSession({('GET', 'tasks'): FakeResponse(200, {'results': [], 'next': 'https://other.invalid/api/tasks?page=2'})})
    client = CvatClient('http://cvat.local:8080', 'fake-secret', session=session)
    with pytest.raises(CvatError, match='URL|origin'):
        client.get_tasks()
    assert len(session.calls) == 1


def test_relative_pagination_and_redirect_policy():
    session = FakeSession({('GET', 'tasks'): [FakeResponse(200, {'results': [1], 'next': '/api/tasks?page=2'}),
                                             FakeResponse(200, {'results': [2], 'next': None})]})
    client = CvatClient('http://cvat.local:8080', 'fake', session=session)
    assert client.get_tasks() == [1, 2]
    assert all(call[2].get('allow_redirects') is False for call in session.calls)


@pytest.mark.parametrize('status', [401, 403, 404, 406, 302])
def test_http_failures_are_contextual(status):
    client = CvatClient('http://cvat.local', 'fake', session=FakeSession({('GET', 'jobs/9'): FakeResponse(status, {'detail': 'denied'})}))
    with pytest.raises(CvatError, match=f'jobs/9.*HTTP {status}'):
        client.get_job(9)


def test_invalid_json_is_a_contextual_cvat_error():
    class BadJSON(FakeResponse):
        def json(self):
            raise ValueError('bad JSON')
    client = CvatClient('http://cvat.local', 'fake', session=FakeSession({('GET', 'jobs/9'): BadJSON(200, {})}))
    with pytest.raises(CvatError, match='jobs/9.*JSON'):
        client.get_job(9)


def test_track_mutable_attributes_carry_until_explicit_change():
    raw = copy.deepcopy(RAW_ANNOTATIONS)
    first, second, last = raw['tracks'][0]['shapes']
    first['attributes'] = [{'spec_id': 101, 'value': 'cờ trước'}]
    second['attributes'] = []
    last['attributes'] = [{'spec_id': 101, 'value': ''}]
    raw['tracks'][0]['shapes'].reverse()  # API order must not change time semantics
    boxes = annotations_to_cuboids(raw, labels_from_api(API_LABELS))
    assert [b.attrs.get('pointsnap_error') for b in boxes if b.track_id == 31] == ['cờ trước', 'cờ trước', '']
    assert first['attributes'] == [{'spec_id': 101, 'value': 'cờ trước'}]


@pytest.mark.parametrize('index', [3, 4])
def test_roll_pitch_nan_are_rejected_with_box_context(index):
    raw = copy.deepcopy(RAW_ANNOTATIONS)
    raw['shapes'][0]['points'][index] = float('nan')
    with pytest.raises(ValueError, match='Box id 5 ở frame 1'):
        annotations_to_cuboids(raw, labels_from_api(API_LABELS))


@pytest.mark.parametrize('mutation', ['duplicate_frame', 'duplicate_file', 'swapped_tokens', 'missing_transform', 'bad_transform', 'count', 'pose', 'timestamp'])
def test_invalid_manifest_is_rejected_before_scan(tmp_path, mutation):
    export = export_scene(NuScenesReader(fake_nuscenes.build(tmp_path / 'data')), 'scene-0001', tmp_path / 'out')
    manifest = json.loads(export.manifest.read_text(encoding='utf-8'))
    if mutation == 'duplicate_frame':
        manifest['frames'][1]['frame'] = 0
    elif mutation == 'duplicate_file':
        manifest['frames'][1]['file'] = manifest['frames'][0]['file']
    elif mutation == 'swapped_tokens':
        manifest['frames'][0]['sample_token'], manifest['frames'][1]['sample_token'] = manifest['frames'][1]['sample_token'], manifest['frames'][0]['sample_token']
    elif mutation == 'missing_transform':
        del manifest['transform']
    elif mutation == 'bad_transform':
        manifest['transform'] = (np.eye(3) * 2).tolist()
    elif mutation == 'count':
        manifest['num_frames'] = 99
    elif mutation == 'pose':
        manifest['frames'][0]['sensor_to_world'][0][3] += 1
    else:
        manifest['frames'][0]['timestamp'] += 1
    export.manifest.write_text(json.dumps(manifest), encoding='utf-8')
    with pytest.raises(ValueError, match='manifest|Manifest'):
        ManifestFrames(export.manifest)


@pytest.mark.parametrize('header_change', [('SIZE 4 4 4 4', 'SIZE 8 8 8 8'), ('TYPE F F F F', 'TYPE I I I I'),
                                          ('COUNT 1 1 1 1', 'COUNT 2 1 1 1'), ('WIDTH 1', 'WIDTH 2')])
def test_pcd_header_cannot_reinterpret_wrong_stride_or_type(tmp_path, header_change):
    path = tmp_path / 'cloud.pcd'
    write_pcd(path, np.array([[1, 2, 3, 4]], dtype=np.float32))
    path.write_bytes(path.read_bytes().replace(*(v.encode() for v in header_change)))
    with pytest.raises(ValueError):
        read_pcd(path)


@pytest.mark.parametrize('values', [np.nan, np.inf, 1e100])
def test_export_pcd_rejects_invalid_or_unrepresentable_values(tmp_path, values):
    with pytest.raises(ValueError):
        write_pcd(tmp_path / 'cloud.pcd', np.array([[values, 0, 0, 0]]))
    assert not (tmp_path / 'cloud.pcd').exists()


def test_nuscenes_binary_does_not_ignore_trailing_bytes(tmp_path):
    reader = NuScenesReader(fake_nuscenes.build(tmp_path))
    ref = reader.samples('scene-0001')[0]
    ref.lidar_path.write_bytes(ref.lidar_path.read_bytes() + b'X')
    with pytest.raises(ValueError):
        reader.load_points(ref)


def test_nuscenes_chain_rejects_wrong_scene(tmp_path):
    fake_nuscenes.build(tmp_path)
    path = tmp_path / 'v1.0-mini/sample.json'
    records = json.loads(path.read_text())
    next(r for r in records if r['token'] == 'smp1')['scene_token'] = 'other-scene'
    path.write_text(json.dumps(records))
    with pytest.raises(ValueError):
        NuScenesReader(tmp_path).samples('scene-0001')


def make_job(raw):
    labels = labels_from_api(API_LABELS)
    return JobData(url='http://cvat:8080', task_id=10, job_id=1, start_frame=0, stop_frame=3,
                   labels=labels, cuboids=annotations_to_cuboids(raw, labels))


def finding(source_id=64, frame=0):
    return Finding(error_type=ErrorType.SIZE, rule='size.in_track', severity=Severity.ERROR, frame=frame,
                   label='car', track_id=31, source_id=source_id, message='Kiểm tra kích thước')


def test_writer_refuses_stale_scan_without_patching():
    job = make_job(RAW_ANNOTATIONS)
    fresh = copy.deepcopy(RAW_ANNOTATIONS)
    fresh['tracks'][0]['shapes'][0]['points'][0] += 1
    session = MockSession(fresh)
    with pytest.raises(CvatError, match='thay đổi|quét lại'):
        flag_job_errors(CvatClient(job.url, 'fake', session=session), job, [finding()])
    assert not any(call[0] == 'PATCH' for call in session.calls)


def test_track_flag_does_not_spill_into_next_keyframe():
    raw = copy.deepcopy(RAW_ANNOTATIONS)
    labels = labels_from_api(API_LABELS)
    patch, summary = build_error_patch(raw, labels, build_findings_map([finding()]))
    [track] = patch['tracks']
    # CVAT propagates a mutable value until an explicit reset; deleting it is insufficient.
    assert track['shapes'][1]['attributes'] == [{'spec_id': 101, 'value': ''}]
    assert (summary.flagged, summary.cleared, summary.unmatched) == (1, 0, 0)


def test_clearing_a_later_inherited_flag_writes_an_explicit_empty_value():
    raw = copy.deepcopy(RAW_ANNOTATIONS)
    raw['tracks'][0]['shapes'][0]['attributes'] = [{'spec_id': 101, 'value': 'old'}]
    patch, _ = build_error_patch(raw, labels_from_api(API_LABELS), {(31, None, 0): 'old'})
    assert patch['tracks'][0]['shapes'][1]['attributes'] == [{'spec_id': 101, 'value': ''}]


def test_geometry_verification_accepts_new_ids_but_checks_roll_pitch():
    boxes = annotations_to_cuboids(RAW_ANNOTATIONS, labels_from_api(API_LABELS))
    after = [b.replace(source_id=(b.source_id or 0) + 100) for b in reversed(boxes)]
    verify_geometry_preserved(boxes, after)
    changed = [after[0].replace(attrs={**after[0].attrs, 'cvat_rx': .5}), *after[1:]]
    with pytest.raises(ValueError):
        verify_geometry_preserved(boxes, changed)


def test_upload_failure_cleans_only_its_new_task(tmp_path):
    export = export_scene(NuScenesReader(fake_nuscenes.build(tmp_path / 'data')), 'scene-0001', tmp_path / 'out')
    class FailedUpload:
        url = 'http://cvat.local'
        deleted = []
        def create_task(self, *args): return {'id': 777}
        def upload_task_data(self, *args): raise CvatError('bad pcd')
        def delete_task(self, task_id): self.deleted.append(task_id)
    client = FailedUpload()
    with pytest.raises(CvatError, match='bad pcd'):
        upload_scene(client, export, 'task riêng', 'pointsnap_error')
    assert client.deleted == [777]


def test_writer_checks_for_edits_between_planning_and_patch():
    class ChangingSession(MockSession):
        def request(self, method, url, **kwargs):
            if method == 'GET' and self.calls:
                self.raw_annos['tracks'][0]['shapes'][0]['points'][0] += 2
            return super().request(method, url, **kwargs)
    session = ChangingSession(RAW_ANNOTATIONS)
    job = make_job(RAW_ANNOTATIONS)
    with pytest.raises(CvatError, match='thay đổi|quét lại'):
        flag_job_errors(CvatClient(job.url, 'fake', session=session), job, [finding()])
    assert not any(call[0] == 'PATCH' for call in session.calls)


def test_snapshot_has_original_api_payload_and_content_idempotency(tmp_path):
    job = make_job(RAW_ANNOTATIONS)
    session = MockSession(RAW_ANNOTATIONS)
    client = CvatClient(job.url, 'fake', session=session)
    snap = tmp_path / 'before.json'
    flag_job_errors(client, job, [finding()], snapshot_path=snap)
    assert json.loads(snap.read_text(encoding='utf-8'))['meta']['cvat_annotations'] == RAW_ANNOTATIONS
    after = copy.deepcopy(session.raw_annos)
    summary = flag_job_errors(client, job, [finding()])
    assert (summary.flagged, summary.cleared, summary.unmatched) == (0, 0, 0)
    assert session.raw_annos == after


def test_writer_rebinds_only_scanned_keyframe_after_cvat_changes_ids():
    job = make_job(RAW_ANNOTATIONS)
    raw = copy.deepcopy(RAW_ANNOTATIONS)
    raw['tracks'][0]['shapes'][0]['id'] = 999
    session = MockSession(raw)
    client = CvatClient(job.url, 'fake', session=session)
    summary = flag_job_errors(client, job, [finding()])
    assert (summary.flagged, summary.unmatched) == (1, 0)
    unknown = flag_job_errors(client, make_job(session.raw_annos), [finding(source_id=888)], clear_stale=False)
    assert unknown.unmatched == 1 and unknown.flagged == 0


@pytest.mark.parametrize('edit', ['dims', 'yaw', 'outside', 'occluded', 'attribute'])
def test_writer_rejects_other_stale_label_changes(edit):
    raw = copy.deepcopy(RAW_ANNOTATIONS)
    shape = raw['tracks'][0]['shapes'][0]
    if edit == 'dims': shape['points'][6] = 8
    elif edit == 'yaw': shape['points'][5] = 1
    elif edit == 'attribute': shape['attributes'] = [{'spec_id': 102, 'value': 'true'}]
    else: shape[edit] = True
    session = MockSession(raw)
    with pytest.raises(CvatError, match='quét lại'):
        flag_job_errors(CvatClient('http://cvat:8080', 'fake', session=session), make_job(RAW_ANNOTATIONS), [finding()])


def test_pcd_ascii_is_explicitly_unsupported(tmp_path):
    path = tmp_path / 'ascii.pcd'
    write_pcd(path, np.array([[1., 2., 3.]]))
    path.write_bytes(path.read_bytes().split(b'DATA binary')[0] + b'DATA ascii\n1 2 3 0\n')
    with pytest.raises(ValueError, match='binary'):
        read_pcd(path)


def test_nuscenes_cycle_is_rejected(tmp_path):
    fake_nuscenes.build(tmp_path)
    path = tmp_path / 'v1.0-mini/sample.json'
    samples = json.loads(path.read_text())
    next(r for r in samples if r['token'] == 'smp2')['next'] = 'smp0'
    path.write_text(json.dumps(samples))
    with pytest.raises(ValueError, match='lặp'):
        NuScenesReader(tmp_path).samples('scene-0001')


def test_manifest_search_does_not_mix_same_task_id_on_two_servers(tmp_path):
    for name, url in [('wrong', 'http://other:8080'), ('right', 'http://cvat:8080')]:
        directory = tmp_path / name
        directory.mkdir()
        (directory / 'manifest.json').write_text('{}')
        (directory / 'cvat_task.json').write_text(json.dumps({'task_id': 10, 'url': url}))
    assert find_manifest(10, [tmp_path / 'wrong'], url='http://cvat:8080') is None
    assert find_manifest(10, [tmp_path], url='http://cvat:8080/') == tmp_path / 'right/manifest.json'


def test_missing_sweeps_reduce_coverage_but_corrupt_sweeps_raise(tmp_path):
    fake_nuscenes.build(tmp_path)
    path = tmp_path / 'v1.0-mini/sample_data.json'
    records = json.loads(path.read_text())
    next(r for r in records if r['token'] == 'sd1')['prev'] = 'sd0_sweep'
    path.write_text(json.dumps(records))
    reader = NuScenesReader(tmp_path)
    ref = reader.samples('scene-0001')[1]
    assert reader.load_sweeps(ref, 4) == []  # file absent: documented fallback
    sweep = tmp_path / 'sweeps/LIDAR_TOP/f0b.pcd.bin'
    sweep.parent.mkdir(parents=True)
    sweep.write_bytes(b'bad bytes')
    with pytest.raises(ValueError):
        reader.load_sweeps(ref, 4)


def test_writer_refuses_immutable_flag_attribute():
    specs = copy.deepcopy(API_LABELS)
    specs[0]['attributes'][0]['mutable'] = False
    with pytest.raises(CvatError, match='mutable'):
        build_error_patch(RAW_ANNOTATIONS, labels_from_api(specs), build_findings_map([finding()]))


def test_pagination_cycle_reports_error_instead_of_looping():
    page = FakeResponse(200, {'results': [], 'next': 'http://cvat.local/api/tasks?page=2'})
    client = CvatClient('http://cvat.local', 'fake', session=FakeSession({('GET', 'tasks'): page}))
    with pytest.raises(CvatError, match='lặp'):
        client.get_tasks()


@pytest.mark.parametrize('value', [float('nan'), 100_000])
def test_nuscenes_invalid_frame_time_is_rejected(tmp_path, value):
    fake_nuscenes.build(tmp_path)
    path = tmp_path / 'v1.0-mini/sample_data.json'
    records = json.loads(path.read_text())
    next(r for r in records if r['token'] == 'sd1')['timestamp'] = value
    path.write_text(json.dumps(records))
    with pytest.raises(ValueError, match='Timestamp'):
        NuScenesReader(tmp_path).samples('scene-0001')
