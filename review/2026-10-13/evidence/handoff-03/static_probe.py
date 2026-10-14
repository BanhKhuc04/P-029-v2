"""Read-only static-shift scanner replay on all ten nuScenes mini scenes."""
import argparse
from collections import Counter
import dataclasses
import json
from pathlib import Path
import sys
import subprocess
import types
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT/'source-tool/pointsnap-3d'))
from pointsnap.adapters.nuscenes.reader import NuScenesReader, NuScenesFrames
from pointsnap.core.config import load_config
from pointsnap.core.scanner import scan_cuboids
from pointsnap.eval.split import TUNING_SCENES, TEST_SCENES


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--dataroot', required=True)
    p.add_argument('--out', required=True, type=Path)
    args = p.parse_args()
    cfg = load_config(env={})
    switches = {f.name: False for f in dataclasses.fields(cfg.rules)}
    switches['track_static_shift'] = True
    cfg = dataclasses.replace(cfg, rules=dataclasses.replace(cfg.rules, **switches))
    reader = NuScenesReader(args.dataroot)
    original = types.ModuleType('original_static_scanner')
    source = subprocess.check_output(['git','show','7ec580a:source-tool/pointsnap-3d/pointsnap/core/scanner.py'], cwd=ROOT).decode('utf-8')
    exec(compile(source, 'original_scanner.py', 'exec'), original.__dict__)
    rows = []
    for scene in TUNING_SCENES + TEST_SCENES:
        job = SimpleNamespace(cuboids=reader.annotations(scene))
        frames = NuScenesFrames(reader, scene)
        before = original.scan_cuboids(job, cfg, frames)
        findings = scan_cuboids(job, cfg, frames)
        rows.append({'scene':scene, 'split':'tuning' if scene in TUNING_SCENES else 'reviewed-heldout',
                     'before_counts':dict(Counter(f.severity.value for f in before)),
                     'counts':dict(Counter(f.severity.value for f in findings)),
                     'findings':[[f.frame, f.track_id, f.label, f.rule, f.value] for f in findings]})
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_bytes((json.dumps({'model':'gpt-6.1-sol','source_base':'7ec580a','rows':rows}, indent=2)+'\n').encode())
    print(json.dumps({s:sum(len(r['findings']) for r in rows if r['split']==s) for s in ['tuning','reviewed-heldout']}))


if __name__ == '__main__':
    main()
