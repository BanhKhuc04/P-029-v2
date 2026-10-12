import json
from pathlib import Path

from pointsnap.adapters.cvat.reader import JobData
from pointsnap.adapters.nuscenes import NuScenesReader
from pointsnap.cli.common import frames_for_job
from pointsnap.datasets.nuscenes.to_cvat import export_scene
from tests.fake_nuscenes import build


def exported(tmp_path,monkeypatch):
    export=export_scene(NuScenesReader(build(tmp_path/'dataset')),'scene-0001',tmp_path/'export')
    monkeypatch.setenv('NUSCENES_ROOT',str(tmp_path/'dataset'))
    (export.manifest.parent/'cvat_task.json').write_text(json.dumps({'task_id':7,'url':'http://localhost:8080'}))
    return export


def test_explicit_backend_web_mapping_finds_host_export_in_container(tmp_path,monkeypatch):
    export=exported(tmp_path,monkeypatch)
    monkeypatch.setenv('CVAT_URL','http://cvat-server:8080')
    monkeypatch.setenv('CVAT_WEB_URL','http://localhost:8080')
    job=JobData('http://cvat-server:8080',7,7,0,2,{},[],['000000.pcd','000001.pcd','000002.pcd'])
    frames,note=frames_for_job(job,custom_export_dirs=[export.manifest.parent])
    assert frames is not None and len(frames.file_names)==3


def test_mapping_cannot_take_manifest_for_an_unrelated_project_server(tmp_path,monkeypatch):
    export=exported(tmp_path,monkeypatch)
    monkeypatch.setenv('CVAT_URL','http://cvat-server:8080')
    monkeypatch.setenv('CVAT_WEB_URL','http://localhost:8080')
    job=JobData('http://other-server:8080',7,7,0,2,{},[])
    assert frames_for_job(job,custom_export_dirs=[export.manifest.parent])[0] is None


def test_no_explicit_mapping_does_not_merge_servers_with_same_task_id(tmp_path,monkeypatch):
    export=exported(tmp_path,monkeypatch)
    monkeypatch.delenv('CVAT_WEB_URL',raising=False)
    job=JobData('http://cvat-server:8080',7,7,0,2,{},[])
    assert frames_for_job(job,custom_export_dirs=[export.manifest.parent])[0] is None
