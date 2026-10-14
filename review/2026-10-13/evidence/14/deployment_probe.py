"""Read-only deployed Report API and frozen-config CLI/Web parity on CVAT job 4."""
import argparse
import dataclasses
import contextlib
import csv
import hashlib
import io
import json
import os
from pathlib import Path
import sys
import time
import urllib.error
import urllib.request

ROOT=Path(__file__).resolve().parents[4]
# Use the integrated candidate source, passed explicitly so this report branch can stay based on main.


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--tool-root',required=True)
    p.add_argument('--out',type=Path,required=True)
    p.add_argument('--home',type=Path,required=True)
    args=p.parse_args()
    sys.path.insert(0,args.tool_root)
    from pointsnap.adapters.cvat.client import CvatClient
    from pointsnap.adapters.cvat.reader import load_job,ManifestFrames
    from pointsnap.core.config import load_config
    from pointsnap.core.scanner import scan_cuboids, scan_coverage_gaps
    from pointsnap.core.gate import gate_verdict
    from pointsnap.web.projects import ProjectManager
    from pointsnap.web.runner import ScanRunner
    from pointsnap.web.app import create_app
    from fastapi.testclient import TestClient
    secret=json.loads((Path.home()/'.pointsnap/projects/cvat-local/secret.json').read_text(encoding='utf-8'))['cvat_token']
    cvat=CvatClient('http://localhost:8080',secret)
    cvat.session.trust_env=False
    digest=lambda:hashlib.sha256(json.dumps(cvat.get_job_annotations(4),sort_keys=True).encode()).hexdigest()
    before=digest()
    opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
    def get(path,authenticated=False):
        headers={'Authorization':'Bearer '+secret} if authenticated else {}
        try:
            with opener.open(urllib.request.Request('http://localhost:8080/pointsnap/'+path,headers=headers),timeout=240) as r:
                return r.status,r.headers.get('Content-Type'),r.read()
        except urllib.error.HTTPError as e:
            return e.code,e.headers.get('Content-Type'),e.read()
    rows=[]
    status,mime,body=get('health')
    assert status==200 and mime.startswith('application/json')
    rows.append({'endpoint':'health','status':status,'mime':mime,'json':json.loads(body)})
    status,mime,body=get('jobs/4/report?format=json')
    assert status==401
    rows.append({'endpoint':'report without PAT','status':status})
    remote=None
    for fmt in ('json','html','csv'):
        status,mime,body=get('jobs/4/report?format='+fmt,True)
        assert status==200,(fmt,status)
        rows.append({'endpoint':'report '+fmt,'status':status,'mime':mime,'bytes':len(body)})
        if fmt=='json':remote=json.loads(body)
        if fmt=='csv':remote_csv=body
    assert remote['point_cloud_available'] and remote['pose_available']
    job=load_job(cvat,4)
    frames=ManifestFrames('D:/Vin_uni/data/cvat-v2/scene-0061/manifest.json',dataroot='D:/Vin_uni/data/nuscenes')
    config=load_config(env={})
    config=dataclasses.replace(config,camera=dataclasses.replace(config.camera,enabled='false'))
    local_objects=scan_cuboids(job,config,frames)
    local=[dataclasses.asdict(f) for f in local_objects]
    pm=ProjectManager(args.home)
    pm.create_project('Read-only parity','parity',cvat_url='http://localhost:8080',cvat_token=secret,
                      nuscenes_root='D:/Vin_uni/data/nuscenes',export_dirs=['D:/Vin_uni/data/cvat-v2/scene-0061'])
    guideline,_=pm.get_guideline('parity')
    guideline['camera']['enabled']='false'
    pm.save_guideline('parity',guideline)
    # Run the real CLI entry point, including snapshot and HTML/CSV generation, without --flag.
    import yaml
    from pointsnap.cli.main import main as cli_main
    cfg_path=args.home/'cli-geometry.yaml'
    cfg_path.write_text(yaml.safe_dump({'camera':{'enabled':False},'cvat':{'url':'http://localhost:8080'}}),encoding='utf-8')
    cli_out=args.home/'cli-output'
    old_token=os.environ.get('CVAT_TOKEN'); old_root=os.environ.get('NUSCENES_ROOT')
    try:
        os.environ['CVAT_TOKEN']=secret
        os.environ['NUSCENES_ROOT']='D:/Vin_uni/data/nuscenes'
        with contextlib.redirect_stdout(io.StringIO()),contextlib.redirect_stderr(io.StringIO()):
            cli_status=cli_main(['--config',str(cfg_path),'scan','--job','4',
                '--manifest','D:/Vin_uni/data/cvat-v2/scene-0061/manifest.json','--out',str(cli_out)])
    finally:
        if old_token is None:os.environ.pop('CVAT_TOKEN',None)
        else:os.environ['CVAT_TOKEN']=old_token
        if old_root is None:os.environ.pop('NUSCENES_ROOT',None)
        else:os.environ['NUSCENES_ROOT']=old_root
    assert cli_status==0
    cli_csv=list(csv.DictReader((cli_out/'report_job_4.csv').open(encoding='utf-8-sig',newline='')))
    api_csv=list(csv.DictReader(io.StringIO(remote_csv.decode('utf-8-sig'))))
    assert cli_csv==api_csv
    runner=ScanRunner(pm)
    run=runner.start_scan('parity',4,flag=False)
    while True:
        state=runner.get_run('parity',run)
        if state['status'] in ('done','failed'):break
        time.sleep(.2)
    assert state['status']=='done',state.get('error')
    web=json.loads((runner.run_dir('parity',run)/'findings.json').read_text(encoding='utf-8'))
    # Mechanical API exercise on our isolated project only; these are test inputs, never human precision.
    with TestClient(create_app(args.home)) as app:
        for index,verdict in ((0,'ok'),(1,'fp')):
            response=app.put(f'/api/projects/parity/scans/{run}/reviews/{index}',json={'verdict':verdict})
            assert response.status_code==200
        response=app.post('/api/projects/parity/learn')
        assert response.status_code==200
        learned=response.json()['model']
        assert learned['n_samples']==2 and not learned['use_model']
    def signature(fs):
        return sorted((f['rule'],str(getattr(f['severity'],'value',f['severity'])),f['frame'],
                       f['track_id'] if f['track_id'] is not None else -1,
                       f['source_id'] if f['source_id'] is not None else -1,f['label'],
                       round(f['value'],6) if f['value'] is not None else None) for f in fs)
    same=signature(local)==signature(remote['findings'])==signature(web)
    gaps=scan_coverage_gaps(job,config,frames)
    passed,reasons=gate_verdict(local_objects,config.gate,coverage_gaps=gaps)
    gate_equal=passed==remote['passed']==state['summary']['gate_passed']
    coverage_equal=gaps==remote['coverage_gaps']==state['summary']['coverage_gaps']
    assert gate_equal and coverage_equal
    assert not any(name.startswith('cam.') or name=='critic.box' for name in remote['checks'])
    after=digest()
    result={'model':'gpt-6.1-sol','endpoints':rows,'job_id':4,
            'cloud_available':remote['point_cloud_available'],'pose_available':remote['pose_available'],
            'findings':len(local),'cli_web_api_equal':same,'annotations_unchanged':before==after,
            'real_cli_exit':cli_status,'real_cli_csv_equal':cli_csv==api_csv,
            'gate_equal':gate_equal,'gate_passed':passed,'coverage_equal':coverage_equal,
            'camera_available':remote['camera_available'],'critic_available':remote['critic_available'],
            'before_sha256':before,'after_sha256':after,'api_checks':remote['checks'],
            'review_learn_test_only':{'status':'PASS','samples':learned['n_samples'],'use_model':learned['use_model']},
            'scope':'Geometry parity: CLI/Web explicitly disable camera; base API auto is inactive without vision. Other defaults match; no learned model, no flag writes; not human precision'}
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_bytes((json.dumps(result,ensure_ascii=False,indent=2)+'\n').encode('utf-8'))
    print(json.dumps({k:v for k,v in result.items() if k not in ('api_checks','endpoints')}))
    runner._executor.shutdown(wait=True)
    cvat.session.close()
    assert same and before==after


if __name__=='__main__':main()
