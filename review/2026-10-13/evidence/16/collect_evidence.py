"""Collect small credential-free final results; preserve superseded failures explicitly."""
import argparse
import hashlib
import json
from pathlib import Path

p=argparse.ArgumentParser()
p.add_argument('--initial',type=Path,required=True)
p.add_argument('--final',type=Path,required=True)
p.add_argument('--evidence',type=Path,required=True)
a=p.parse_args()
initial=json.loads((a.initial/'results.json').read_text(encoding='utf-8'))
final=json.loads((a.final/'final.json').read_text(encoding='utf-8'))
retained={'dataset','live-cvat','service-smoke','extension','python-syntax','js-syntax','powershell-syntax','extension-manifest','model-maskrcnn','model-gdino-sam2','model-hybrid'}
data={'model':'gpt-6.1-sol','final_source':final['metadata']['source_commit'],
      'initial_source':initial['metadata']['source_commit'],'dependencies_initial':initial['metadata']['dependencies'],
      'initial_failures':[r for r in initial['phases'] if r['status']=='FAIL'],
      'resolution':'Initial Python/Linux failures are retained; corrected explicit rule fixture, preview geometry fixture, optional Pillow skip and archive-root runner; later full results supersede them.',
      'final_phases':final['phases'],'retained_phases':[r for r in initial['phases'] if r['name'] in retained],
      'initial_evaluation':'Interrupted externally after six scene progress lines; no complete summary, not PASS.',
      'evaluation':'See evidence/15/evaluation.json for completed checkpointed evaluation, when available.',
      'limits':['No installed new MV3 runtime acceptance','Human precision per new rule and independent 40-verdict learning sample absent','No fresh CPU vision install or long GPU/OOM acceptance']}
data['log_hashes']={}
for prefix,root in (('initial',a.initial),('final',a.final)):
    for path in root.glob('*.log'):
        data['log_hashes'][prefix+'/'+path.name]=hashlib.sha256(path.read_bytes()).hexdigest()
a.evidence.mkdir(parents=True,exist_ok=True)
(a.evidence/'final-checks.json').write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
services=json.loads((a.initial/'services/services.json').read_text(encoding='utf-8'))
(a.evidence/'services.json').write_text(json.dumps(services,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
vision=a.evidence.parent/'15'; vision.mkdir(parents=True,exist_ok=True)
for model in ('maskrcnn','gdino-sam2','hybrid'):
    result=json.loads((a.initial/('model-'+model)/'model.json').read_text(encoding='utf-8'))
    result.update(review_model='gpt-6.1-sol',source_commit=initial['metadata']['source_commit'],
                  scope='Pretrained offline GPU execution and cache roundtrip; not detector human precision, full CPU/GPU long-scan or OOM acceptance')
    (vision/('model-'+model+'.json')).write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'final_source':data['final_source'],'initial_failed_phases':len(data['initial_failures']),
                  'final_failed_phases':sum(r['status']=='FAIL' for r in data['final_phases'])}))
