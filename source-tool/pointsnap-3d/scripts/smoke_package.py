"""Smoke artifact từ cwd ngoài source; chỉ dùng thư viện chuẩn và package đã cài."""
import os,sys,json,subprocess,socket,time,urllib.request,importlib.metadata
from pathlib import Path
from importlib.resources import files
import pointsnap
from pointsnap.core.config import load_config
root=files('pointsnap')
cfg=load_config(env={})
assert cfg.cvat.token is None
assert (root/'guidelines/spec-vn.yaml').is_file()
static=root/'web/static'
assets=[p.name for p in (static/'fonts').iterdir() if p.name.endswith('.woff2')]
assert len(assets)==21
cli=subprocess.run([sys.executable,'-m','pointsnap','--help'],capture_output=True,text=True,encoding='utf-8',check=True)
assert 'scan' in cli.stdout and 'eval' in cli.stdout
with socket.socket() as s:s.bind(('127.0.0.1',0));port=s.getsockname()[1]
env={k:v for k,v in os.environ.items() if not k.startswith(('CVAT_','NUSCENES_','POINTSNAP_','PYTHONPATH'))}
env['POINTSNAP_HOME']=str(Path.cwd()/'smoke-home')
process=subprocess.Popen([sys.executable,'-m','pointsnap','ui','--no-browser','--port',str(port)],env=env,
                         stdout=subprocess.DEVNULL,stderr=subprocess.PIPE,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
statuses={}
try:
    for _ in range(100):
        try:
            with urllib.request.urlopen(f'http://127.0.0.1:{port}/',timeout=1) as response:
                assert b'PointSnap' in response.read();break
        except OSError:
            if process.poll() is not None:raise RuntimeError(process.stderr.read().decode(errors='replace'))
            time.sleep(.1)
    else:raise RuntimeError('UI startup timeout')
    for route in ['/','/app','/static/app.js','/static/styles.css','/static/landing.css','/static/landing.js','/static/favicon.svg','/static/fonts/fonts.css',
                  '/static/fonts/'+assets[0],'/api/projects']:
        with urllib.request.urlopen(f'http://127.0.0.1:{port}'+route,timeout=5) as response:
            statuses[route]={'status':response.status,'bytes':len(response.read())}
finally:
    process.terminate();process.wait(timeout=10)
print(json.dumps({'python':sys.version.split()[0],'package_path':str(pointsnap.__file__),'cwd':str(Path.cwd()),
                 'fonts':len(assets),'http':statuses,'dependencies':{p:importlib.metadata.version(p) for p in ['numpy','fastapi','pydantic','requests']}}))
