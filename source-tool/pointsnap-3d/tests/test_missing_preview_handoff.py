"""No-ID cluster evidence must survive JSON and render both preview endpoints."""
import dataclasses
import json
import math

import numpy as np
import pytest
from fastapi.testclient import TestClient

from pointsnap.core.model import FrameData
from pointsnap.core.serialize import save_cuboids
from pointsnap.web.app import create_app
from pointsnap.web.preview import PreviewError, _missing_box
from pointsnap.web.runner import _scalar_details
from test_missing import _front_camera

RUN = '20261013-120000-123-job4'


def finding():
    return dict(rule='lidar.missing', frame=2, label='xe', track_id=None, source_id=None,
                details=dict(frames=[2,3], centers=[[15,.5],[16,.5]],
                             centers_3d=[[15,.5,.8],[16,.5,.8]], size_m=[4,1.9,1.6], yaw_rad=[0,0]))


def test_geometry_lists_survive_but_invalid_or_arbitrary_values_do_not():
    details = {**finding()['details'], 'confidence':.8, 'secret_list':['not numeric'],
               'reference_frames':[1,5], 'bad':math.inf}
    saved = _scalar_details(details)
    assert saved['centers_3d'] == [[15,.5,.8],[16,.5,.8]]
    assert saved['reference_frames'] == [1,5]
    assert 'secret_list' not in saved and 'bad' not in saved
    details['centers_3d'][0][0] = math.nan
    assert 'centers_3d' not in _scalar_details(details)
    json.dumps(saved, allow_nan=False)


@pytest.mark.parametrize('change', [{'frames':[3,4]}, {'size_m':[4,-1,1]},
                                  {'centers_3d':[[15,.5]]}, {'yaw_rad':[math.nan,0]}])
def test_missing_geometry_requires_finite_valid_evidence_at_the_exact_frame(change):
    f = finding()
    f['details'].update(change)
    with pytest.raises(PreviewError):
        _missing_box(f)


def test_missing_finding_without_annotation_renders_lidar_and_camera(tmp_path, monkeypatch):
    Image = pytest.importorskip('PIL.Image')
    client = TestClient(create_app(tmp_path))
    assert client.post('/api/projects', json={'name':'preview','slug':'preview'}).status_code == 201
    run = tmp_path/'projects/preview/runs'/RUN
    run.mkdir(parents=True)
    (run/'summary.json').write_text(json.dumps({'job_id':4}), encoding='utf-8')
    f = finding()
    f['details'] = _scalar_details(f['details'])
    (run/'findings.json').write_text(json.dumps([f]), encoding='utf-8')
    save_cuboids(run/'snapshot.json', [], {'task_id':4,'url':'http://cvat'})
    image = tmp_path/'camera.jpg'
    Image.new('RGB',(1600,900),'gray').save(image)
    view = dataclasses.replace(_front_camera(), path=image)
    class Frames:
        def frame_data(self, frame, with_points=True):
            assert frame == 2
            return FrameData(frame, np.array([[15,.5,.8],[15,.5,0]]), np.eye(4))
        def camera_views(self, frame):
            return [view]
    import pointsnap.web.preview as preview
    monkeypatch.setattr(preview, 'find_manifest', lambda *args,**kwargs: tmp_path/'manifest.json')
    monkeypatch.setattr(preview, 'ManifestFrames', lambda *args,**kwargs: Frames())
    url = f'/api/projects/preview/scans/{RUN}/findings/0'
    result = client.get(url+'/preview')
    assert result.status_code == 200
    data = result.json()
    assert data['synthetic_box'] is True and data['track_id'] is None
    assert data['frame'] == 2 and data['box'] == {'length':4,'width':1.9,'height':1.6}
    assert data['points'][0] == [0,0,0]
    photo = client.get(url+'/camera')
    assert photo.status_code == 200 and photo.headers['content-type'] == 'image/jpeg'
    assert photo.content.startswith(bytes([255,216]))
