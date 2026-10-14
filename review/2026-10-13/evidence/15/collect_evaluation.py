"""Aggregate completed canonical per-scene outputs without raw labels/track geometry."""
import argparse
from collections import defaultdict
import hashlib
import json
import math
from pathlib import Path

p=argparse.ArgumentParser()
p.add_argument('--input',type=Path,required=True)
p.add_argument('--out',type=Path,required=True)
p.add_argument('--dataset',type=Path,required=True)
a=p.parse_args()
meta=json.loads((a.input/'metadata.json').read_text(encoding='utf-8'))
assert meta['status']=='COMPLETE' and len(meta['scenes'])==10 and meta['rounds']==10
splits={'tuning':meta['scenes'][:5],'reviewed-heldout':meta['scenes'][5:]}
groups=defaultdict(list); scene_rows=[]; provenance=[]
for scene in meta['scenes']:
    directory=a.input/scene
    marker=json.loads((directory/'completed.json').read_text(encoding='utf-8'))
    assert marker['package_tree']==meta['package_tree']
    sm=json.loads((directory/'metadata.json').read_text(encoding='utf-8'))
    assert sm['config_sha256']==meta['config_sha256'] and sm['rounds']==10 and sm['seed']==0
    summary=json.loads((directory/'summary.json').read_text(encoding='utf-8'))
    outcomes=json.loads((directory/'outcomes.json').read_text(encoding='utf-8'))
    split=next(k for k,v in splits.items() if scene in v)
    for row in outcomes:
        for dimension,key in (('split',split),('error',split+'|'+row['error_type']),
                              ('class',split+'|'+row['label']),('scene',scene)):
            groups[dimension,key].append(row)
    provenance.append({'scene':scene,'source_commit':sm['source_commit'],'source_dirty':sm['source_dirty'],
                       'evaluator_sha256':sm['evaluator_sha256'],'summary_sha256':hashlib.sha256((directory/'summary.json').read_bytes()).hexdigest(),
                       'outcomes_sha256':hashlib.sha256((directory/'outcomes.json').read_bytes()).hexdigest()})
    scene_rows.append({'scene':scene,'split':split,'boxes':summary['boxes'],'clean_counts':summary['clean_counts'],
                       'clean_scan_seconds':summary['scan_seconds'][scene]})

def aggregate(rows):
    n=len(rows); detected=sum(r['detected'] for r in rows)
    applicable=[r for r in rows if r['applicable']]
    evidence=[r for r in rows if r['has_ground_evidence'] is True]
    result={'n':n,'detected':detected,'recall':detected/n if n else None,
            'applicable_n':len(applicable),'applicable_detected':sum(r['detected'] for r in applicable),
            'ground_evidence_n':len(evidence),'ground_evidence_detected':sum(r['detected'] for r in evidence),
            'fn_without_ground_evidence':sum(not r['detected'] and r['has_ground_evidence'] is False for r in rows)}
    if n:
        z=1.959963984540054; rate=detected/n; den=1+z*z/n
        center=(rate+z*z/(2*n))/den
        radius=z*math.sqrt(rate*(1-rate)/n+z*z/(4*n*n))/den
        result['wilson_descriptive_95']=[center-radius,center+radius]
    return result

dimension_rows={dimension:{key:aggregate(rows) for (d,key),rows in sorted(groups.items()) if d==dimension}
                for dimension in ('split','error','class','scene')}
proxy={}
for split in splits:
    summary=json.loads((a.input/(split+'-summary.json')).read_text(encoding='utf-8'))
    counts={level:sum(v for k,v in summary['clean_counts'].items() if k.endswith('|'+level)) for level in ('warning','error')}
    proxy[split]={'boxes':summary['boxes'],'counts':counts,
                 'per_100':{k:v/summary['boxes']*100 for k,v in counts.items()},
                 'reference_met':counts['warning']/summary['boxes']*100<=2 and counts['error']/summary['boxes']*100<=.5,
                 'status':'REPORT_ONLY','g7_status':'UNASSESSED','false_positive_truth':False,
                 'clean_counts':summary['clean_counts'],'recall_by_magnitude':summary['recall'],
                 'large_as_error':summary['large_as_error'],'measurement_accuracy':summary['measurement_accuracy'],
                 'synthetic_finding_matching':summary['precision']}
data={'review_model':'gpt-6.1-sol','metadata':meta,'provenance':provenance,'groups':dimension_rows,
      'scene_rows':scene_rows,'proxy':proxy,
      'uncertainty_note':'Wilson intervals are descriptive iid approximations; injected rounds reuse tracks and scenes, so not independent acceptance confidence intervals.',
      'scope':'Canonical core+c1 injection only; not recall/human precision for missing, camera, critic or spec. Reviewed-heldout is not independent.'}
data['dataset_table_sha256']={}
for name in ('scene.json','sample.json','sample_annotation.json','ego_pose.json','calibrated_sensor.json'):
    path=a.dataset/'v1.0-mini'/name
    data['dataset_table_sha256'][name]=hashlib.sha256(path.read_bytes()).hexdigest()
a.out.mkdir(parents=True,exist_ok=True)
(a.out/'evaluation.json').write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
lines=['# Kết quả canonical 10 vòng, seed 0','','Chỉ core+c1. Proxy riêng, G7 UNASSESSED. Reviewed-heldout đã dùng chấm tay/chỉnh evidence.','',
       '| Tập | Box sạch | Bắt / lỗi chèn | Recall mô tả | Warning /100 | Error /100 | Proxy tham khảo |',
       '|---|---:|---:|---:|---:|---:|---|']
for split in splits:
    r=dimension_rows['split'][split]; q=proxy[split]
    lines.append(f"| {split} | {q['boxes']} | {r['detected']}/{r['n']} | {100*r['recall']:.2f}% | {q['per_100']['warning']:.3f} | {q['per_100']['error']:.3f} | {'Trong mức' if q['reference_met'] else 'Vượt mức'} |")
lines += ['','## Theo loại lỗi','','| Tập / loại | Bắt / chèn | Thuộc phạm vi | FN thiếu ground evidence |','|---|---:|---:|---:|']
for key,r in dimension_rows['error'].items():
    lines.append(f"| {key} | {r['detected']}/{r['n']} | {r['applicable_detected']}/{r['applicable_n']} | {r['fn_without_ground_evidence']} |")
lines += ['','## Theo scene','','| Scene | Bắt / chèn |','|---|---:|']
for key,r in dimension_rows['scene'].items():lines.append(f"| {key} | {r['detected']}/{r['n']} |")
(a.out/'evaluation-tables.md').write_text('\n'.join(lines)+'\n',encoding='utf-8',newline='\n')
print(json.dumps({'split':dimension_rows['split'],'proxy':{k:{x:v[x] for x in ('boxes','per_100','reference_met')} for k,v in proxy.items()}},indent=2))
