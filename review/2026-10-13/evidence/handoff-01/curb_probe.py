"""Replay the existing human verdicts; never generate new human labels."""
import argparse
import csv
import dataclasses
import json
from pathlib import Path
import sys
import subprocess
import types

ROOT = Path(__file__).resolve().parents[4]
TOOL = ROOT / 'source-tool/pointsnap-3d'
sys.path.insert(0, str(TOOL))
from pointsnap.adapters.nuscenes.reader import NuScenesReader, NuScenesFrames
from pointsnap.core.config import load_config
from pointsnap.core import ground
from pointsnap.detectors import floating
from pointsnap.core.scanner import apply_evidence_gate
from pointsnap.eval.split import TUNING_SCENES, TEST_SCENES


def identity(f):
    return (f.frame, f.track_id, f.label, f.rule)


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--dataroot', required=True)
    p.add_argument('--out', type=Path, required=True)
    args = p.parse_args()
    reader = NuScenesReader(args.dataroot)
    cfg = load_config(env={})
    verdicts = list(csv.DictReader((ROOT/'review/2026-10-13/evidence/g7/verdicts-heldout.csv').open(encoding='utf-8-sig')))
    # Compare the old merged policy and the proposed surface-only tolerance.
    source = subprocess.check_output(['git', 'show', '7ec580a:source-tool/pointsnap-3d/pointsnap/core/ground.py'], cwd=ROOT).decode('utf-8')
    old = 'abs(cuboid.bottom_z - z_high) <= 0.08 or (z_low - 0.05 <= cuboid.bottom_z <= z_high + 0.08)'
    new = 'min(abs(cuboid.bottom_z - z_high), abs(cuboid.bottom_z - z_low)) <= 0.08'
    candidate = types.ModuleType('curb_surface_candidate')
    sys.modules[candidate.__name__] = candidate
    exec(compile(source.replace(old, new), 'candidate_ground.py', 'exec'), candidate.__dict__)
    original_ground = types.ModuleType('curb_original_ground')
    sys.modules[original_ground.__name__] = original_ground
    exec(compile(source, 'original_ground.py', 'exec'), original_ground.__dict__)
    original_floating = types.ModuleType('curb_original_floating')
    old_detector = subprocess.check_output(['git', 'show', '7ec580a:source-tool/pointsnap-3d/pointsnap/detectors/floating.py'], cwd=ROOT).decode('utf-8')
    exec(compile(old_detector, 'original_floating.py', 'exec'), original_floating.__dict__)
    current = floating.ring_ground_for_box
    rows = []
    for scene in TUNING_SCENES + TEST_SCENES:
        boxes = reader.annotations(scene)
        frames = NuScenesFrames(reader, scene)
        floating.ring_ground_for_box = original_ground.ring_ground_for_box
        estimates = floating.estimate_scene_ground(boxes, frames, cfg.floating)
        before = original_floating.floating_findings_by_track(estimates, cfg.floating)
        without_curb = [(b, dataclasses.replace(e, is_curb_supported=False)) for b,e in estimates]
        no_curb = original_floating.floating_findings_by_track(without_curb, cfg.floating)
        # Final policy ignores a nearby curb when there are enough same-track peers.
        # The default disables single-box findings; no ground recomputation is needed.
        after = floating.floating_findings_by_track(estimates, cfg.floating)
        before = apply_evidence_gate(before, boxes, cfg, frames)
        no_curb = apply_evidence_gate(no_curb, boxes, cfg, frames)
        after = apply_evidence_gate(after, boxes, cfg, frames)
        known = {(int(r['frame']), int(r['track_id']), r['label'], r['rule']) for r in verdicts
                 if r['scene'] == scene and r['rule'] == 'floating' and r['verdict'] == 'Đúng lỗi'}
        sig = lambda fs: {identity(f) for f in fs if f.rule == 'floating' and f.severity.value != 'info'}
        baseline = sig(no_curb)
        row = {'scene':scene, 'split':'tuning' if scene in TUNING_SCENES else 'reviewed-heldout',
               'without_curb':len(baseline), 'merged_curb':len(sig(before)), 'fixed':len(sig(after)),
               'confirmed_true':len(known), 'confirmed_true_in_baseline':len(known & baseline),
               'merged_lost_true':sorted((known & baseline)-sig(before)),
               'fixed_lost_true':sorted((known & baseline)-sig(after)),
               'all_verdict_true_not_actionable_after':sorted(known-sig(after))}
        rows.append(row)
        print(json.dumps(row, ensure_ascii=False), flush=True)
    floating.ring_ground_for_box = current
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_bytes((json.dumps({'config':'default; no ground or severity threshold changes', 'rows':rows}, ensure_ascii=False, indent=2)+'\n').encode('utf-8'))
    assert not any(r['fixed_lost_true'] for r in rows), 'Curb policy lost a previously actionable true error'


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    main()
