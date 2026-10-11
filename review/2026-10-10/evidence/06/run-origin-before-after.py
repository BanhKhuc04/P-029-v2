import os,sys,subprocess,json,types,uuid
from pathlib import Path
r=Path(__file__).resolve().parents[4]/"source-tool/pointsnap-3d"
sys.path[:0]=[str(r),str(r/'.venv/Lib/site-packages')]
os.environ['POINTSNAP_HOME']=str(r/'out/review06-baseline')
from fastapi.testclient import TestClient
from pointsnap.web.app import create_app
source=subprocess.check_output(['git','show','43812b9:source-tool/pointsnap-3d/pointsnap/web/app.py'],cwd=r.parents[1]).decode('utf-8')
module=types.ModuleType('baseline_app');sys.modules['baseline_app']=module
namespace=module.__dict__;namespace['__file__']=str(r/'pointsnap/web/app.py')
exec(compile(source,namespace['__file__'],'exec'),namespace)
results={}
fixture=r/'out'/('r06base-'+uuid.uuid4().hex[:6])
for name,factory in [('before',namespace['create_app']),('after',create_app)]:
    app=factory(fixture/name)
    app.state.pm.create_project('Private baseline fixture',slug='a')
    c=TestClient(app)
    c.put('/api/projects/a/guideline',json={'config':{'rules':{'size_class_range':False}}})
    before=c.get('/api/projects/a/guideline').json()['config']['rules']['size_class_range']
    status=c.post('/api/projects/a/guideline/reset',headers={'Origin':'https://evil.example'}).status_code
    after=c.get('/api/projects/a/guideline').json()['config']['rules']['size_class_range']
    results[name]={'status':status,'rule_before':before,'rule_after':after}
    c.close()
results['method']='App source from 43812b9 vs current; same current ProjectManager/config, in-process TestClient and private fixture home'
(r.parents[1]/'review/2026-10-10/evidence/06/origin-before-after.json').write_text(json.dumps(results,indent=2),encoding='utf-8')
print(json.dumps(results))
