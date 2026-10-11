import sys, os, time, json, csv, io, copy, threading, uuid, subprocess, shutil
from pathlib import Path
root = Path(__file__).resolve().parents[4] / "source-tool" / "pointsnap-3d"
sys.path[:0] = [str(root), str(root / '.venv/Lib/site-packages'), str(root / 'tests')]
sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')
from fastapi.testclient import TestClient
import requests
import fake_nuscenes
from pointsnap.cli.main import load_dotenv, main
from pointsnap.core.config import load_config
from pointsnap.adapters.nuscenes import NuScenesReader
from pointsnap.adapters.cvat.client import CvatClient
from pointsnap.adapters.cvat.reader import load_job
from pointsnap.adapters.cvat.writer import verify_geometry_preserved
from pointsnap.datasets.nuscenes.to_cvat import export_scene, upload_scene
from pointsnap.web.app import create_app
from pointsnap.web.runner import ScanRunner
from pointsnap.api import ReportServer

load_dotenv(root / '.env')
cfg = load_config()
fixture = root / 'out' / ('r04-live-' + uuid.uuid4().hex[:8])
fixture.mkdir()
admin = CvatClient(cfg.cvat.url, cfg.cvat.token)
export = export_scene(NuScenesReader(fake_nuscenes.build(fixture / 'dataset')), 'scene-0001', fixture / 'export')
task_info = upload_scene(admin, export, 'PointSnap review 04 (tự xóa)', 'pointsnap_error')
task_id, jid = task_info['task_id'], task_info['job_ids'][0]
app = create_app(fixture / 'home')
web = TestClient(app)
server = ReportServer(('127.0.0.1', 0), cfg.cvat.url)
worker = threading.Thread(target=server.serve_forever, daemon=True)
worker.start()
base = f'http://127.0.0.1:{server.server_port}'
os.environ['POINTSNAP_EXPORT_DIR'] = str(export.directory)
results = {'cvat_version': admin.server_version(), 'task_id': task_id, 'job_id': jid, 'fixture': str(fixture), 'data': 'nuScenes fixture tính tay, upload CVAT thật'}
temporary_token_ids, temporary_user_id = [], None

def docker_python(code):
    result = subprocess.run(['docker', 'exec', 'cvat_server', 'python', 'manage.py', 'shell', '-c', code], capture_output=True, text=True, encoding='utf-8')
    if result.returncode:
        raise RuntimeError('Docker fixture credential operation failed (' + str(result.returncode) + ')')
    return json.loads(result.stdout.strip().splitlines()[-1])

def wait(run_id):
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        response = web.get(f'/api/projects/live/scans/{run_id}')
        assert response.status_code == 200, response.status_code
        data = response.json()
        if data['status'] in ('done', 'failed'):
            assert data['status'] == 'done', data.get('error')
            return data
        time.sleep(.05)
    raise RuntimeError('Scan timeout')

try:
    project = {'name': 'Review 04', 'slug': 'live', 'cvat_url': cfg.cvat.url, 'cvat_token': cfg.cvat.token,
               'export_dirs': [str(export.directory)], 'nuscenes_root': str(fixture / 'dataset')}
    assert web.post('/api/projects', json=project).status_code == 201
    assert web.get('/api/projects/live/cvat/check').json()['connected']
    tasks = web.get('/api/projects/live/cvat/tasks').json()['tasks']
    assert any(t['id'] == task_id and any(j['id'] == jid for j in t['jobs']) for t in tasks)
    with __import__('concurrent.futures', fromlist=['ThreadPoolExecutor']).ThreadPoolExecutor(2) as pool:
        starts = list(pool.map(lambda _: web.post('/api/projects/live/scans', json={'job_id': jid}), range(2)))
    assert all(res.status_code == 202 for res in starts)
    ids = [res.json()['run_id'] for res in starts]
    assert len(set(ids)) == 2
    runs = [wait(run_id) for run_id in ids]
    first = runs[0]
    summary, findings = first['summary'], first['findings']
    assert len(web.get('/api/projects/live/scans').json()) == 2
    cli_out = fixture / 'cli'
    assert main(['scan', '--job', str(jid), '--manifest', str(export.manifest), '--out', str(cli_out)]) == 0
    csv_web = web.get(f'/api/projects/live/scans/{ids[0]}/report.csv').content
    assert csv_web == (cli_out / f'report_job_{jid}.csv').read_bytes()
    html_web = web.get(f'/api/projects/live/scans/{ids[0]}/report.html').content
    assert html_web == (cli_out / f'report_job_{jid}.html').read_bytes()
    with requests.Session() as report_session:
        report_session.trust_env = False
        auth = {'Authorization': 'Bearer ' + cfg.cvat.token}
        response = report_session.get(base + f'/pointsnap/jobs/{jid}/report', headers=auth, timeout=60)
        assert response.status_code == 200, response.status_code
        payload = response.json()
        assert (payload['boxes'], payload['errors'], payload['warnings'], payload['info'], payload['passed']) == (
            summary['num_boxes'], summary['num_errors'], summary['num_warnings'], summary['num_info'], summary['gate_passed'])
        assert payload['coverage_gaps'] == summary['coverage_gaps']
        assert [(f['rule'], f['frame'], f['source_id'], f['track_id']) for f in payload['findings']] == [
            (f['rule'], f['frame'], f['source_id'], f['track_id']) for f in findings]
        for fmt, expected in [('html', html_web), ('csv', csv_web)]:
            response = report_session.get(base + f'/pointsnap/jobs/{jid}/report?format={fmt}', headers=auth, timeout=60)
            assert response.status_code == 200 and response.content == expected
        assert report_session.get(base + f'/pointsnap/jobs/{jid}/report', timeout=10).status_code == 401
        assert report_session.get(base + f'/pointsnap/jobs/{jid}/report', headers={'Authorization': 'Bearer deliberately-invalid'}, timeout=10).status_code == 401

    # Tạo credential thử ngay trong Docker local; chỉ giữ giá trị trong RAM, không in/lưu token.
    credentials = docker_python("import json; from cvat.apps.engine.models import Task; from cvat.apps.access_tokens.models import AccessToken; from django.contrib.auth import get_user_model; from django.contrib.auth.models import Group; from django.db import transaction; User=get_user_model(); g=Group.objects.get(name='worker'); owner=Task.objects.get(id=" + str(task_id) + ").owner\nwith transaction.atomic():\n a,av=AccessToken.objects.create_key(owner=owner,name='review04-read-only',read_only=True); u=User.objects.create_user(username='review04-" + uuid.uuid4().hex[:8] + "'); u.groups.add(g); b,bv=AccessToken.objects.create_key(owner=u,name='review04-no-job',read_only=True); print(json.dumps({'read_id':a.id,'read_value':av,'denied_id':b.id,'denied_value':bv,'user_id':u.id}))")
    temporary_token_ids = [credentials['read_id'], credentials['denied_id']]
    temporary_user_id = credentials['user_id']
    read_response = requests.get(base + f'/pointsnap/jobs/{jid}/report', headers={'Authorization': 'Bearer ' + credentials['read_value']}, timeout=60)
    denied_response = requests.get(base + f'/pointsnap/jobs/{jid}/report', headers={'Authorization': 'Bearer ' + credentials['denied_value']}, timeout=10)
    assert read_response.status_code == 200
    assert denied_response.status_code in (403, 404)
    ps_output = fixture / 'powershell-report.json'
    ps_env = dict(os.environ, CVAT_TOKEN=credentials['read_value'])
    ps_executable = os.environ.get('POINTSNAP_POWERSHELL') or shutil.which('pwsh') or 'powershell.exe'
    ps_result = subprocess.run([ps_executable, '-NoProfile', '-File', str(root / 'Get-Report.ps1'),
                                '-JobId', str(jid), '-Format', 'json', '-ApiUrl', base, '-OutFile', str(ps_output)],
                               env=ps_env, capture_output=True, text=True, timeout=30)
    assert ps_result.returncode == 0, 'Get-Report.ps1 runtime failed'
    assert json.loads(ps_output.read_text(encoding='utf-8')) == read_response.json()
    results['powershell_report'] = 'Đạt; PAT chỉ đọc; JSON khớp HTTP trực tiếp'
    results['pat'] = {'read_only': read_response.status_code, 'no_job_permission': denied_response.status_code, 'invalid': 401, 'anonymous': 401}
    results['parity'] = {'boxes': summary['num_boxes'], 'findings': len(findings), 'errors': summary['num_errors'],
                         'warnings': summary['num_warnings'], 'info': summary['num_info'], 'gate': summary['gate_passed'],
                         'coverage_gaps': summary['coverage_gaps'], 'html_bytes_equal': True, 'csv_bytes_equal': True,
                         'two_unique_runs': ids}

    # Đổi geometry trên task thử sau scan; /flag phải quét fresh và giữ geometry mới.
    annotations = admin.get_job_annotations(jid)
    track = next(t for t in annotations['tracks'] if any(not s['outside'] for s in t['shapes']))
    shape = next(s for s in track['shapes'] if not s['outside'])
    shape['points'][6] = 25.0
    admin.patch_job_annotations(jid, {'tracks': [track], 'shapes': [], 'tags': []})
    changed = load_job(admin, jid)
    flagged_response = web.post(f'/api/projects/live/scans/{ids[0]}/flag')
    assert flagged_response.status_code == 202
    flagged = wait(flagged_response.json()['run_id'])
    assert flagged['run_id'] not in ids and flagged['summary']['flagged']
    assert flagged['summary']['flag_summary']['flagged'] > 0
    verify_geometry_preserved(changed.cuboids, load_job(admin, jid).cuboids)
    target_index = next(i for i, f in enumerate(flagged['findings']) if f['rule'].startswith('size.'))
    preview = web.get(f"/api/projects/live/scans/{flagged['run_id']}/findings/{target_index}/preview")
    assert preview.status_code == 200, preview.text
    assert preview.json()['exact_frame']
    reviews_url = f"/api/projects/live/scans/{flagged['run_id']}/reviews/{target_index}"
    assert web.put(reviews_url, json={'verdict': 'fp'}).json()['reviews'] == {str(target_index): 'fp'}
    fresh = ScanRunner(app.state.pm)
    try:
        assert fresh.get_run('live', flagged['run_id'], include_findings=True)['summary'] == flagged['summary']
    finally:
        fresh._executor.shutdown()
    results['rescan_flag_preview_review_restart'] = {'new_run': flagged['run_id'], 'flag_summary': flagged['summary']['flag_summary'],
                                                    'geometry_preserved': True, 'preview_frame': preview.json()['frame'],
                                                    'exact_frame': preview.json()['exact_frame'], 'reviews_saved': True, 'done_restored': True}
finally:
    app.state.runner._executor.shutdown(wait=True)
    server.shutdown()
    server.server_close()
    worker.join()
    if temporary_token_ids:
        docker_python("import json; from cvat.apps.access_tokens.models import AccessToken; from django.contrib.auth import get_user_model; AccessToken.objects.filter(id__in=" + repr(temporary_token_ids) + ").delete(); get_user_model().objects.filter(id=" + str(temporary_user_id) + ").delete(); print(json.dumps({'cleanup':True}))")
        results['credentials_cleaned'] = True
    admin.delete_task(task_id)
    results['task_cleaned'] = True
    admin.session.close()
    (fixture / 'result.json').write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(results, ensure_ascii=False, indent=2))
