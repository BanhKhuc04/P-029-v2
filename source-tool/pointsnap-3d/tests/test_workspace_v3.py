"""Regression cases for filtered indices, environment gating and scoped manual events."""
from types import SimpleNamespace as NS

from fastapi.testclient import TestClient

from pointsnap.web.app import create_app
from pointsnap.web.environment import model_status, project_catalog
from pointsnap.web.findings import indexed, present_run
from pointsnap.web.link import ExtensionLink
from pointsnap.web.preview import _find_box, load_reviews
from pointsnap.web.storage import write_json
from pointsnap.core.model import Cuboid


def item(rule="floating", severity="warning", kind="floating"):
    return dict(rule=rule, severity=severity, error_type=kind, frame=0, track_id=1)


def test_filtering_never_reindexes_original_records():
    raw=[item("track.jump",kind="track"), item("floating.no_evidence","info"), item()]
    run=present_run({"findings":raw,"summary":{"num_errors":100}})
    assert [f["finding_index"] for f in run["findings"] if f["actionable"]] == [2]
    assert len(run["diagnostics"]) == 2
    assert run["summary"]["num_errors"] == 0
    assert run["summary"]["num_warnings"] == 1


def test_only_five_groups_and_two_severities():
    assert not indexed([item(severity="info")])[0]["actionable"]
    assert not indexed([item(kind="track")])[0]["actionable"]
    assert indexed([item("critic.box",kind="fit")])[0]["actionable"]


def test_preview_never_substitutes_a_nearby_frame():
    box=Cuboid(center=(0,0,1),dims=(4,2,2),yaw=0,label="car",frame=2,track_id=1)
    assert _find_box([box], item()) is None
    assert _find_box([box], {**item(),"frame":2}) is box


def test_scoped_events_ignore_out_of_order_messages():
    link=ExtensionLink()
    assert link.event(1,{"session":"a","sequence":2,"kind":"saved"},scope="cvat-a")
    assert not link.event(1,{"session":"a","sequence":1,"kind":"evaluated"},scope="cvat-a")
    assert link.status(1,scope="cvat-a")["manual_event"]["kind"] == "saved"
    assert link.status(1,scope="cvat-b")["manual_event"] is None


def test_unused_models_require_no_import_or_download(monkeypatch):
    import pointsnap.web.environment as env
    monkeypatch.setattr(env.importlib,"import_module",lambda _: (_ for _ in ()).throw(AssertionError("Must not load optional runtime")))
    cfg=NS(rules=NS(critic_box=False),critic=NS(model=""),camera=NS(enabled="false",model="maskrcnn"))
    assert model_status(cfg)["all_ready"]


def test_missing_model_is_not_ready_even_if_runtime_exists(monkeypatch):
    import pointsnap.web.environment as env
    monkeypatch.setattr(env.importlib,"import_module",lambda _: None)
    cfg=NS(rules=NS(critic_box=True),critic=NS(model=""),camera=NS(enabled="false",model="maskrcnn"))
    assert not model_status(cfg)["all_ready"]


def test_corrupt_critic_blocks_scan(monkeypatch,tmp_path):
    import pointsnap.web.environment as env
    monkeypatch.setattr(env.importlib,"import_module",lambda _: None)
    monkeypatch.setattr(env,"_critic_check",lambda *args:False)
    weights=tmp_path/"broken.pt";weights.write_bytes(b"broken")
    cfg=NS(rules=NS(critic_box=True),critic=NS(model=str(weights)),camera=NS(enabled="false",model="maskrcnn"))
    assert not model_status(cfg)["all_ready"]


def test_api_keeps_raw_indices_and_blocks_unconfigured_models(tmp_path):
    app=create_app(tmp_path);client=TestClient(app)
    assert client.post('/api/projects',json={"name":"Test","slug":"test"}).status_code==201
    folder=tmp_path/'projects/test/runs/20261016-120000-job1';folder.mkdir(parents=True)
    raw=[item("track.jump",kind="track"),item("floating.no_evidence","info"),item()]
    write_json(folder/'findings.json',raw)
    write_json(folder/'summary.json',{"job_id":1})
    response=client.get('/api/projects/test/scans/20261016-120000-job1').json()
    assert response['findings'][2]['finding_index']==2
    assert response['summary']['num_warnings']==1
    assert client.post('/api/projects/test/scans',json={"job_id":1}).status_code==409
    status=client.get('/api/system/status?project_slug=test').json()
    assert not status['scan_ready'] and not status['models']['all_ready']


def test_legacy_ambiguous_reviews_are_not_assigned_to_other_boxes(tmp_path):
    write_json(tmp_path/'findings.json',[item("track.jump",kind="track"),item()])
    write_json(tmp_path/'reviews.json',{"0":"ok"})
    assert load_reviews(tmp_path)=={}
    assert (tmp_path/'reviews.json').read_text()


def test_catalog_excludes_dead_track_and_evidence_controls():
    rules=project_catalog()['rules']
    assert rules and all(r['error_type']!='track' for r in rules)
    assert not any('no_evidence' in r['id'] for r in rules)
    assert len({r['switch_key'] for r in rules})==len(rules)


def test_save_invalidation_survives_later_selection_and_frame_navigation():
    link=ExtensionLink()
    common={"session":"a","run_id":"r","slug":"p"}
    link.event(1,{**common,"sequence":1,"kind":"saved"},scope="cvat")
    link.event(1,{**common,"sequence":2,"kind":"selected"},scope="cvat")
    assert link.status(1,scope="cvat")["manual_runs"]["r"]["saved"]


def test_environment_is_scoped_to_the_selected_project(tmp_path):
    client=TestClient(create_app(tmp_path))
    for slug in ('a','b'):
        client.post('/api/projects',json={"name":slug,"slug":slug})
    client.put('/api/projects/b/guideline',json={"config":{"rules":{"critic_box":False},"camera":{"enabled":False}}})
    a=client.get('/api/system/status?project_slug=a').json()
    b=client.get('/api/system/status?project_slug=b').json()
    assert a['project_slug']=='a' and not a['models']['all_ready']
    assert b['project_slug']=='b' and b['models']['all_ready']
    assert not b['scan_ready']  # CVAT is not configured, even though optional models are unnecessary.
    assert client.get('/api/system/status?project_slug=missing').status_code==404
