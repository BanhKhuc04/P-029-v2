import os
import sys,json,hashlib,time
from pathlib import Path
r=Path(__file__).resolve().parents[4]/"source-tool/pointsnap-3d"
sys.path[:0]=[str(r),str(r/'.venv/Lib/site-packages')]
sys.stdout.reconfigure(encoding='utf-8')
from pointsnap.adapters.nuscenes import NuScenesReader
from pointsnap.core.config import load_config
from pointsnap.eval.evaluate import run_evaluation
from pointsnap.eval.split import TUNING_SCENES,TEST_SCENES
root=Path(os.environ['NUSCENES_ROOT'])
out=r/'out/review07/eval'
out.mkdir(parents=True,exist_ok=True)
config=load_config(env={})
fingerprint={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted((root/'v1.0-mini').glob('*.json'))}
(out/'dataset-sha256.json').write_text(json.dumps(fingerprint,indent=2))
(out/'config.json').write_text(json.dumps(config.to_dict(redact=True),ensure_ascii=False,indent=2),encoding='utf-8')
for label,scenes in [('tuning',TUNING_SCENES),('test',TEST_SCENES)]:
    started=time.perf_counter();print(f'START {label}: rounds10 seed0 all, config locked',flush=True)
    run_evaluation(NuScenesReader(root),scenes,config,out/label,rounds=10,seed=0,catalog='all')
    print(f'DONE {label}: {time.perf_counter()-started:.2f}s',flush=True)
