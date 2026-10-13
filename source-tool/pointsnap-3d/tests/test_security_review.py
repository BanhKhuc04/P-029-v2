import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from pointsnap.web.app import create_app
from pointsnap.web.projects import ProjectManager, ProjectError
from pointsnap.adapters.cvat.reader import frame_url
from pointsnap.adapters.nuscenes.reader import NuScenesReader
from tests.fake_nuscenes import build as build_fake_nuscenes


@pytest.fixture
def client(tmp_path):
    app = create_app(tmp_path)
    app.state.pm.create_project('Security fixture', slug='a', cvat_token='TEST-SECRET-06')
    return TestClient(app)


@pytest.mark.parametrize('origin', ['https://evil.example', 'null', 'http://localhost:9999'])
def test_cross_origin_reset_cannot_mutate_guideline(client, origin):
    client.put('/api/projects/a/guideline', json={'config': {'gate': {'max_errors': 3}}})
    before = client.get('/api/projects/a/guideline').json()
    res = client.post('/api/projects/a/guideline/reset', headers={'Origin': origin})
    assert res.status_code == 403
    assert client.get('/api/projects/a/guideline').json() == before


def test_cross_site_without_origin_is_blocked(client):
    assert client.post('/api/projects/a/guideline/reset', headers={'Sec-Fetch-Site': 'cross-site'}).status_code == 403


def test_dns_rebinding_host_is_blocked(client):
    assert client.get('/api/projects', headers={'Host': 'evil.example'}).status_code == 403


def test_allowed_local_and_extension_origins(client):
    assert client.get('/api/projects', headers={'Origin': 'http://testserver'}).status_code == 200
    assert client.get('/api/projects', headers={'Origin': 'chrome-extension://' + 'a'*32}).status_code == 200


@pytest.mark.parametrize('content', ['x'*1_048_577, iter([b'x'*600_000,b'x'*600_000])], ids=['content-length', 'chunked'])
def test_body_limit_before_parsing(client, content):
    assert client.post('/api/projects', content=content).status_code == 413


def test_request_validation_does_not_echo_secret_input(client):
    res=client.post('/api/projects',json={'name':'a','cvat_token':{'secret':'TEST-SECRET-06'}})
    assert res.status_code == 422
    assert 'TEST-SECRET-06' not in res.text


def test_malformed_yaml_does_not_echo_secret_line(client):
    res=client.put('/api/projects/a/guideline',json={'yaml':'cvat:\n  token: [TEST-SECRET-06\n  url: http://localhost:8080\n'})
    assert res.status_code == 400
    assert 'TEST-SECRET-06' not in res.text


@pytest.mark.parametrize('url', ['javascript:alert(1)','file:///tmp','http://u:TEST-SECRET-06@localhost:8080','http://localhost:8080?token=TEST-SECRET-06','http://localhost:8080/#x','http://localhost:bad','http://localhost:8080/\r\nX: bad'])
def test_project_rejects_unsafe_url_before_persistence(client,url):
    res=client.put('/api/projects/a',json={'cvat_url':url})
    assert res.status_code == 400
    assert 'TEST-SECRET-06' not in res.text
    assert client.app.state.pm.get_project('a')['cvat_url']=='http://localhost:8080'


def test_changing_server_does_not_reuse_old_token(client):
    assert client.put('/api/projects/a',json={'cvat_url':'http://other.example:8080'}).status_code==200
    assert client.app.state.pm.get_token('a') is None


def test_changing_server_can_set_explicit_new_token(client):
    assert client.put('/api/projects/a',json={'cvat_url':'http://other.example:8080','cvat_token':'NEW-TEST-06'}).status_code==200
    assert client.app.state.pm.get_token('a')=='NEW-TEST-06'


def test_changing_cvat_proxy_path_clears_old_token(client):
    assert client.put('/api/projects/a',json={'cvat_url':'http://localhost:8080/other-cvat'}).status_code==200
    assert client.app.state.pm.get_token('a') is None


def test_same_origin_spelling_keeps_token(client):
    assert client.put('/api/projects/a',json={'cvat_url':'http://LOCALHOST:8080/'}).status_code==200
    assert client.app.state.pm.get_token('a')=='TEST-SECRET-06'


def test_links_reject_executable_or_credential_url():
    for url in ['javascript:alert(1)', 'http://user:SECRET@localhost:8080']:
        assert frame_url(url,1,1,0)==''


@pytest.mark.parametrize('filename',['../sentinel.bin','/outside/sentinel.bin','C:\\outside\\sentinel.bin'])
def test_dataset_metadata_cannot_escape_root(tmp_path,filename):
    root=build_fake_nuscenes(tmp_path/'dataset')
    path=root/'v1.0-mini'/'sample_data.json'
    rows=json.loads(path.read_text());rows[0]['filename']=filename;path.write_text(json.dumps(rows))
    with pytest.raises(ValueError,match='phạm vi|tương đối'):
        NuScenesReader(root).samples('scene-0001')


def test_private_api_cache_headers(client):
    response=client.get('/api/projects')
    assert 'no-store' in response.headers.get('Cache-Control','')
    assert response.headers.get('X-Content-Type-Options')=='nosniff'
    assert response.headers.get('X-Frame-Options')=='DENY'


@pytest.mark.parametrize('value',['\ufeff=1+1','\t+CMD','\n@SUM(1,2)','-text'])
def test_csv_external_text_cannot_start_a_formula(value):
    from pointsnap.report.csv_rep import _text_cell
    assert _text_cell(value).startswith("'")


def test_cvat_background_failure_does_not_echo_token():
    from pointsnap.adapters.cvat.client import CvatClient, CvatError
    from tests.test_cvat_client import FakeSession, FakeResponse
    c=CvatClient('http://localhost:8080','TEST-SECRET-06',session=FakeSession({('GET','requests/a'):FakeResponse(200,{'status':'failed','message':'TEST-SECRET-06'})}))
    with pytest.raises(CvatError) as exc:
        c.wait_request('a')
    assert 'TEST-SECRET-06' not in str(exc.value)


def test_unique_pagination_is_bounded():
    from pointsnap.adapters.cvat.client import CvatClient, CvatError
    from tests.test_cvat_client import FakeSession, FakeResponse
    session=FakeSession({('GET','tasks'):[FakeResponse(200,{'results':[],'next':'http://localhost:8080/api/tasks?page=2'}),FakeResponse(200,{'results':[],'next':'http://localhost:8080/api/tasks?page=3'})]})
    c=CvatClient('http://localhost:8080','dummy',session=session,max_pages=2)
    with pytest.raises(CvatError,match='giới hạn 2 trang'):
        c.get_tasks()
    assert len(session.calls)==2
