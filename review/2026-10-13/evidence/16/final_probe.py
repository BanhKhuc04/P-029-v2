"""Repeat final Python/package/Linux checks from a clean Git archive; no credentials."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile

p = argparse.ArgumentParser()
p.add_argument('--repo', type=Path, required=True)
p.add_argument('--out', type=Path, required=True)
a = p.parse_args()
repo = a.repo.resolve()
root = repo / 'source-tool/pointsnap-3d'
out = a.out.resolve()
out.mkdir(parents=True, exist_ok=False)
spec = importlib.util.spec_from_file_location('handoff_runner', root/'auto-tests/run_all.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
env = dict(os.environ, PYTHONPATH=str(root), OPENBLAS_NUM_THREADS='1', OMP_NUM_THREADS='1', MKL_NUM_THREADS='1')
for key in tuple(env):
    if 'TOKEN' in key or key.startswith('POINTSNAP_'):
        env.pop(key, None)
rows = []
meta = {'model':'gpt-6.1-sol','source_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo).decode().strip()}

def run(name, argv, cwd=root, phase_env=env, timeout=1200):
    print(name, flush=True)
    row = m.command(name, list(map(str,argv)), cwd, phase_env, out, timeout)
    rows.append(row)
    (out/'final.json').write_text(json.dumps({'metadata':meta,'phases':rows},indent=2),encoding='utf-8')
    if row['status'] != 'PASS':
        raise RuntimeError(name+' failed; inspect its log')
    return row

xml = out/'python.xml'
r = run('python', [sys.executable,'-m','pytest','-q','-ra','-p','no:cacheprovider','tests','auto-tests',
                   '--ignore=tests/test_live_cvat.py','--ignore=tests/test_real_nuscenes.py',
                   '--junitxml='+str(xml),'--basetemp='+str(out/'python-tmp')])
r['cases'] = dict(m.junit_counts(xml))
archive = out/'source.tar'
run('archive',['git','archive','--format=tar','--output='+str(archive),'HEAD','source-tool/pointsnap-3d'],cwd=repo)
with tarfile.open(archive) as tar:
    tar.extractall(out/'source',filter='data')
source = out/'source/source-tool/pointsnap-3d'
run('package-build',[sys.executable,'-m','build','--no-isolation','--outdir',out/'dist'],cwd=source)
run('package-venv',[sys.executable,'-m','venv',out/'installed'],cwd=out)
ip = out/'installed/Scripts/python.exe'
ie = {k:v for k,v in env.items() if k != 'PYTHONPATH'}
run('package-install',[ip,'-m','pip','install','--disable-pip-version-check',next((out/'dist').glob('*.whl'))],cwd=out,phase_env=ie)
run('installed-pip-check',[ip,'-m','pip','check'],cwd=out,phase_env=ie)
run('installed-http',[ip,source/'scripts/smoke_package.py'],cwd=out,phase_env=ie)
image = 'pointsnap-review:handoff-final'
run('docker-build',['docker','build','--build-arg','PYTHON_VERSION=3.11','-t',image,'.'],cwd=source)
run('docker-cli',['docker','run','--rm',image,'--help'])
run('docker-pip-check',['docker','run','--rm','--entrypoint','python',image,'-m','pip','check'])
linux = out/'linux'
linux.mkdir()
r = run('docker-pytest',['docker','run','--rm','--entrypoint','python','-v',str(source)+':/source:ro',
                       '-v',str(linux)+':/results','-v',str(root/'auto-tests/docker_pytest.py')+':/runner.py:ro',
                       '-w','/source',image,'/runner.py'])
r['cases'] = dict(m.junit_counts(linux/'linux.xml'))
(out/'final.json').write_text(json.dumps({'metadata':meta,'phases':rows},indent=2),encoding='utf-8')
print(json.dumps({'source_commit':meta['source_commit'],'python':rows[0]['cases'],'linux':r['cases']}),flush=True)
