"""v2 contract: live drafts are read-only; absence of evidence never certifies a repair."""
import copy
import json

import numpy as np
import pytest
from fastapi.testclient import TestClient

from pointsnap.core.model import Cuboid, FrameData
from pointsnap.core.serialize import save_cuboids
from pointsnap.web.app import create_app
from pointsnap.web.guides import DraftBox, EvaluateRequest

RUN = "20261015-120000-job2"
BASE = f"/api/projects/manual/scans/{RUN}/findings"


@pytest.fixture
def setup(tmp_path):
    app = create_app(tmp_path)
    client = TestClient(app)
    assert client.post('/api/projects', json={'name':'Manual','slug':'manual'}).status_code == 201
    folder = tmp_path/'projects'/'manual'/'runs'/RUN
    folder.mkdir(parents=True)
    (folder/'summary.json').write_text(json.dumps({'job_id':2}), encoding='utf-8')
    findings = [dict(rule='floating', frame=0, track_id=5, details={'ground_z':0, 'distance':.3, 'num_ground_points':100}),
                dict(rule='size.class_range', frame=0, track_id=5),
                dict(rule='critic.box', frame=0, track_id=5),
                dict(rule='floating', frame=9, track_id=5),
                dict(rule='size.class_range', frame=0, source_id=7)]
    (folder/'findings.json').write_text(json.dumps(findings), encoding='utf-8')
    boxes = [Cuboid(center=(0,0,1.3), dims=(8,2,2), yaw=0,label='car',frame=0,track_id=5),
             Cuboid(center=(20,0,1), dims=(4,2,2), yaw=0,label='car',frame=0,source_id=7)]
    save_cuboids(folder/'snapshot.json', boxes, {'task_id':2})
    # Use the public config endpoint, just as the project UI does.
    response=client.put('/api/projects/manual/guideline', json={'config':{'size':{'manual_ranges':{'car':{'length':[3,5],'width':[1,3],'height':[1,3]}}}}})
    assert response.status_code == 200, response.text
    return app,client,folder


def draft(**changes):
    value=dict(center=[0,0,1],dims=[4,2,2],rotation=[0,0,0],label='car',frame=0,track_id=5,
               source_id=None,attrs={},outside=False,keyframe=True)
    value.update(changes)
    return {'box':value,'context':[copy.deepcopy(value)],'context_complete':True,'revision':7}


def test_guide_has_exact_identity_and_never_falls_back_to_nearby_frame(setup):
    _,c,_=setup
    g=c.get(f'{BASE}/0/guide').json()
    assert g['schema_version']==1 and g['evidence']=='measured'
    assert g['identity']==dict(cvat_origin='http://localhost:8080',job_id=2,frame=0,kind='track',server_id=5,project_slug='manual',run_id='20261015-120000-job2',finding_index=0)
    assert g['reference']['bottom_z']==pytest.approx(0)
    assert c.get(f'{BASE}/3/guide').json()['baseline'] is None
    assert c.get(f'{BASE}/4/guide').json()['identity']['kind']=='shape'


def test_draft_recheck_uses_unsaved_box_and_changes_no_files(setup):
    _,c,folder=setup
    before={p.name:p.read_bytes() for p in folder.iterdir()}
    r=c.post(f'{BASE}/1/evaluate',json=draft(dims=[8,2,2])).json()
    assert r['state']=='remaining'
    r=c.post(f'{BASE}/1/evaluate',json=draft()).json()
    assert r['state']=='cleared' and r['revision']==7
    assert before=={p.name:p.read_bytes() for p in folder.iterdir()}


@pytest.mark.parametrize('change',[{'rotation':[.01,0,0]},{'rotation':[0,-.1,0]}])
def test_tilt_is_preserved_and_not_certified_by_yaw_only_rules(setup,change):
    _,c,_=setup
    assert c.post(f'{BASE}/1/evaluate',json=draft(**change)).json()['state']=='insufficient'


def test_missing_cloud_unknown_rule_and_incomplete_context_never_clear(setup):
    _,c,_=setup
    assert c.post(f'{BASE}/0/evaluate',json=draft()).json()['state']=='insufficient'
    assert c.post(f'{BASE}/2/evaluate',json=draft()).json()['state']=='insufficient'
    body=draft();body['context_complete']=False
    assert c.post(f'{BASE}/1/evaluate',json=body).json()['state']=='insufficient'


def test_wrong_object_frame_and_invalid_geometry_are_rejected(setup):
    _,c,_=setup
    for change in [{'track_id':6},{'frame':1},{'track_id':None,'source_id':5}]:
        assert c.post(f'{BASE}/1/evaluate',json=draft(**change)).status_code==409
    for change in [{'dims':[0,2,2]},{'center':[0,0,None]},{'rotation':[0,0]}]:
        assert c.post(f'{BASE}/1/evaluate',json=draft(**change)).status_code==422


def test_all_geometry_write_routes_are_retired(setup):
    _,c,folder=setup
    before={p.name:p.read_bytes() for p in folder.iterdir()}
    for path,body in [('/api/jobs/2/tracks/5/apply-repair',{'frame':0,'repair':{}}),
                      ('/api/jobs/2/tracks/5/rollback',{'history_id':'old'}),
                      (f'{BASE}/0/apply-repair',{'frame':0,'repair':{}}),
                      ('/api/projects/manual/history/old/rollback',{})]:
        assert c.post(path,json=body).status_code==410,path
    assert before=={p.name:p.read_bytes() for p in folder.iterdir()}


def test_no_false_ground_reference_without_evidence(setup):
    _,c,folder=setup
    path=folder/'findings.json';data=json.loads(path.read_text(encoding='utf-8'))
    data[0]['details']['num_ground_points']=0
    path.write_text(json.dumps(data),encoding='utf-8')
    g=c.get(f'{BASE}/0/guide').json()
    assert g['reference']=={} and g['evidence']=='insufficient'


def test_floating_recheck_uses_cloud_and_current_unsaved_height(setup):
    app,c,_=setup
    class Frames:
        def frame_data(self,frame,with_points=True):
            grid=np.array([(x,y,0) for x in np.linspace(-8,8,100) for y in np.linspace(-6,6,80)])
            return FrameData(frame=frame,points=grid,sensor_to_world=np.eye(4),timestamp=frame*.5)
    app.state.guide_frames=Frames()
    for height,expected in [(1.3,'remaining'),(1,'cleared')]:
        body=draft(center=[0,0,height])
        body['context']=[{**body['box'],'frame':i,'center':[0,0,1]} for i in [1,2]]
        assert c.post(f'{BASE}/0/evaluate',json=body).json()['state']==expected
    assert c.post(f'{BASE}/0/evaluate',json=draft()).json()['state']=='insufficient'


def test_size_track_finding_moving_to_another_frame_is_still_remaining(setup):
    _,c,_=setup
    body=draft()
    body['context']=[{**body['box'],'frame':i,'dims':[9,2,2]} for i in [1,2,3]]
    result=c.post(f'{BASE}/1/evaluate',json=body).json()
    assert result['state']=='remaining'


def test_unknown_class_and_disabled_rule_cannot_be_certified(setup):
    _,c,_=setup
    assert c.post(f'{BASE}/1/evaluate',json=draft(label='unknown class')).json()['state']=='insufficient'
    assert c.put('/api/projects/manual/guideline',json={'config':{'rules':{'size_class_range':False}}}).status_code==200
    assert c.post(f'{BASE}/1/evaluate',json=draft()).json()['state']=='insufficient'


def test_shape_draft_uses_shape_id_without_confusing_track_id(setup):
    _,c,_=setup
    payload=draft(track_id=None,source_id=7,center=[20,0,1])
    assert c.post(f'{BASE}/4/evaluate',json=payload).json()['state']=='cleared'
    assert c.post(f'{BASE}/4/evaluate',json=draft(track_id=7)).status_code==409


def test_default_class_ranges_are_available_without_project_overrides(setup):
    _,c,_=setup
    assert c.post('/api/projects/manual/guideline/reset').status_code==200
    guide=c.get(f'{BASE}/1/guide').json()
    assert guide['reference']['ranges']['length'][1]>5
    assert guide['evidence']=='measured'


def test_retired_routes_return_410_even_when_the_old_payload_is_absent(setup):
    _,c,_=setup
    assert c.post('/api/jobs/2/tracks/5/apply-repair').status_code==410
    assert c.post('/api/jobs/2/tracks/5/rollback',json={'arbitrary':'old client'}).status_code==410


def test_concurrent_draft_checks_do_not_create_snapshots_or_mutate_annotations(setup):
    from concurrent.futures import ThreadPoolExecutor
    _,c,folder=setup
    before={p.name:p.read_bytes() for p in folder.iterdir()}
    with ThreadPoolExecutor(max_workers=4) as pool:
        results=list(pool.map(lambda i:c.post(f'{BASE}/1/evaluate',json={**draft(),'revision':i}).json(),range(12)))
    assert {r['revision'] for r in results}==set(range(12))
    assert all(r['state']=='cleared' for r in results)
    assert before=={p.name:p.read_bytes() for p in folder.iterdir()}
