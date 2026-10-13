"""Run canonical 10-round evaluation per scene, preserving completed scene outputs for resume.

No detector, injection seed/round offset, config or matching changes. Output directories
are immutable after completion. Resume requires exactly the same package Git tree.
"""
import argparse
import json
from pathlib import Path
import subprocess
import sys

p=argparse.ArgumentParser()
p.add_argument('--tool-root',type=Path,required=True)
p.add_argument('--dataset',type=Path,required=True)
p.add_argument('--out',type=Path,required=True)
p.add_argument('--rounds',type=int,default=10)
p.add_argument('--scenes',choices=('all','tuning','test'),default='all')
a=p.parse_args()
root=a.tool_root.resolve()
sys.path.insert(0,str(root))
from pointsnap.adapters.nuscenes import NuScenesReader
from pointsnap.core.config import load_config
from pointsnap.eval.evaluate import ErrorOutcome, SceneStats, run_evaluation, summarize, to_markdown
from pointsnap.eval.split import TUNING_SCENES, TEST_SCENES
cfg=load_config(env={})
reader=NuScenesReader(a.dataset)
out=a.out.resolve(); out.mkdir(parents=True,exist_ok=True)
tree=subprocess.check_output(['git','rev-parse','HEAD:source-tool/pointsnap-3d/pointsnap'],cwd=root).decode().strip()
selected = {'all':(*TUNING_SCENES,*TEST_SCENES),'tuning':TUNING_SCENES,'test':TEST_SCENES}[a.scenes]
for scene in selected:
    sd=out/scene
    marker=sd/'completed.json'
    if marker.exists():
        saved=json.loads(marker.read_text(encoding='utf-8'))
        assert saved['package_tree']==tree and saved['rounds']==a.rounds and saved['dataset']==str(a.dataset.resolve())
        assert json.loads((sd/'metadata.json').read_text(encoding='utf-8'))['config']==cfg.to_dict(redact=True)
        print(scene+': resume completed scene',flush=True)
        continue
    if (sd/'metadata.json').exists():
        # Preserve an interrupted attempt and choose a fresh canonical output directory.
        n=1
        while (out/(scene+'-interrupted-'+str(n))).exists():n+=1
        sd.rename(out/(scene+'-interrupted-'+str(n)))
    run_evaluation(reader,[scene],cfg,sd,rounds=a.rounds,seed=0,catalog='all')
    marker.write_text(json.dumps({'package_tree':tree,'rounds':a.rounds,'dataset':str(a.dataset.resolve())}),encoding='utf-8')
    print(scene+': checkpoint complete',flush=True)

if not all((out/scene/'completed.json').exists() for scene in (*TUNING_SCENES,*TEST_SCENES)):
    print('Selected split complete; aggregate awaits the other split.',flush=True)
    sys.exit(0)

stats=[]; outcomes=[]
for scene in (*TUNING_SCENES,*TEST_SCENES):
    sd=out/scene; summary=json.loads((sd/'summary.json').read_text(encoding='utf-8'))
    precision=summary['precision']
    stats.append(SceneStats(scene,summary['boxes'],summary['clean_counts'],
        {k:v['findings'] for k,v in precision.items()},
        {k:v['matched'] for k,v in precision.items()},
        {k:v['on_injected'] for k,v in precision.items()},summary['scan_seconds'][scene]))
    outcomes.extend(ErrorOutcome(**r) for r in json.loads((sd/'outcomes.json').read_text(encoding='utf-8')))
for split,scenes in (('tuning',TUNING_SCENES),('reviewed-heldout',TEST_SCENES),('all',(*TUNING_SCENES,*TEST_SCENES))):
    summary=summarize([s for s in stats if s.scene in scenes],[o for o in outcomes if o.scene in scenes])
    (out/(split+'-summary.json')).write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    (out/(split+'-report.md')).write_text(to_markdown(summary,'Canonical evaluation: '+split),encoding='utf-8')
metadata=json.loads((out/TUNING_SCENES[0]/'metadata.json').read_text(encoding='utf-8'))
metadata.update(scenes=list((*TUNING_SCENES,*TEST_SCENES)),package_tree=tree,review_model='gpt-6.1-sol',
                status='COMPLETE',g7_status='UNASSESSED',heldout_independent=False,
                split_note='Reviewed-heldout scenes were previously used for human verdicts/evidence tuning; not independent acceptance data')
(out/'metadata.json').write_text(json.dumps(metadata,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print('COMPLETE: 10 scenes, '+str(a.rounds)+' rounds each; G7 UNASSESSED',flush=True)
