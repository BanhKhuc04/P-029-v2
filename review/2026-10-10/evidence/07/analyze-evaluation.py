import os
import sys,json,math,hashlib,inspect,subprocess
from pathlib import Path
from dataclasses import replace
r=Path(__file__).resolve().parents[4]/"source-tool/pointsnap-3d";sys.path[:0]=[str(r),str(r/'.venv/Lib/site-packages')]
sys.stdout.reconfigure(encoding='utf-8')
from pointsnap.adapters.nuscenes import NuScenesReader
from pointsnap.core.config import load_config
from pointsnap.core.synthetic import InjectedError
from pointsnap.core.model import add_track_markers
from pointsnap.eval.evaluate import is_applicable, ErrorOutcome, summarize, to_markdown, CATEGORY
reader=NuScenesReader(os.environ['NUSCENES_ROOT']);config=load_config(env={})
out=r/'out/review07'
for group in ['tuning','test']:
    source=out/'eval'/group;target=out/'analysis'/group;target.mkdir(parents=True,exist_ok=True)
    injections=json.loads((source/'injections.json').read_text(encoding='utf-8'))
    records={(x['scene'],x['round'],x['track_id'],x['error_type']):x for x in injections}
    scenes={name:reader.frames(name) for name in json.loads((source/'metadata.json').read_text(encoding='utf-8'))['scenes']}
    boxes={name:add_track_markers(reader.annotations(name),frames.num_frames) for name,frames in scenes.items()}
    outcomes=[];changed=0
    for raw in json.loads((source/'outcomes.json').read_text(encoding='utf-8')):
        old=ErrorOutcome(**raw);record=records[(old.scene,old.round,old.track_id,old.error_type)]
        error=InjectedError(**{k:v for k,v in record.items() if k not in ('scene','round','seed')})
        applicable=is_applicable(error,old.label,boxes[old.scene],config,scenes[old.scene])
        changed+=applicable!=old.applicable;outcomes.append(replace(old,applicable=applicable))
    original=json.loads((source/'summary.json').read_text(encoding='utf-8'))
    summary={**original,**{k:v for k,v in summarize([],outcomes).items() if k in ('recall','large_as_error')}}
    for category,row in summary['precision'].items():
        errors=[o for o in outcomes if CATEGORY[o.error_type]==category]
        row.update(fault_tp=sum(o.detected for o in errors),fault_fn=sum(not o.detected for o in errors),fault_n=len(errors),finding_fp=row['findings']-row['matched'])
    intervals={}
    for key,row in summary['recall'].items():
        n=row['n_applicable'];x=row['detected_applicable']
        if n:
            p=x/n;z=1.9599639845;d=1+z*z/n;mid=(p+z*z/(2*n))/d;radius=z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/d
            intervals[key]={'x':x,'n':n,'wilson95':[round(mid-radius,4),round(mid+radius,4)]}
        else:intervals[key]={'x':0,'n':0,'wilson95':None}
    denominator={name:{'raw_annotations':len(reader.annotations(name)),'visible_boxes':sum(b.visible for b in boxes[name]),'markers_or_occluded':sum(not b.visible for b in boxes[name])} for name in scenes}
    metadata={'original_metadata':json.loads((source/'metadata.json').read_text(encoding='utf-8')),
              'analysis_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=r).decode().strip(),
              'applicability_sha256':hashlib.sha256(inspect.getsource(is_applicable).encode()).hexdigest(),
              'reclassified_outcomes':changed,'detector_config_changed':False,
              'condition':'postprocess only rule-scope class/min_frames/min_keyframes; scans/matches unchanged, preserved originals; no threshold tuning on held-out scenes',
              'confidence':'Wilson95 illustrative binomial interval; repeated same-scene/track samples are clustered, not a proof of independent-sample significance',
              'manual_precision_reviewed_samples':0,'denominators':denominator}
    for filename,data in [('summary.json',summary),('metadata.json',metadata),('recall-intervals.json',intervals)]:
        (target/filename).write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
    (target/'ket-qua.md').write_text(to_markdown(summary,'Review07 '+group+' — scope corrected, original preserved'),encoding='utf-8')
    errors=sum(v for k,v in summary['clean_counts'].items() if k.endswith('|error'))
    warnings=sum(v for k,v in summary['clean_counts'].items() if k.endswith('|warning'))
    print(json.dumps({'group':group,'boxes':summary['boxes'],'warnings':warnings,'errors':errors,'warning_per100':warnings/summary['boxes']*100,'error_per100':errors/summary['boxes']*100,'injections':len(outcomes),'detected':sum(o.detected for o in outcomes),'scope_reclassified':changed,'scan_seconds':summary['scan_seconds']}),flush=True)
