"""Extract unreviewed candidate findings on the 5 held-out scenes for G7 rules."""
import csv
import json
from pathlib import Path
from pointsnap.adapters.nuscenes import NuScenesReader
from pointsnap.core.config import load_config
from pointsnap.core.model import add_track_markers, Severity
from pointsnap.core.scanner import scan_cuboids
from pointsnap.eval.split import TEST_SCENES

def default_serializer(obj):
    import numpy as np
    if isinstance(obj, (np.bool_, bool)):
        return bool(obj)
    if isinstance(obj, (np.floating, float)):
        return float(obj)
    if isinstance(obj, (np.integer, int)):
        return int(obj)
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    return str(obj)

def main():
    reader = NuScenesReader(Path('D:/Vin_uni/data/nuscenes'))
    cfg = load_config(env={})
    target_rules = {'fit.outside', 'heading.points', 'track.jump', 'track.static_shift', 'track.split_id', 'heading.static'}
    findings_out = []

    for scene in TEST_SCENES:
        frames = reader.frames(scene)
        cuboids = add_track_markers(reader.annotations(scene), frames.num_frames)
        findings = scan_cuboids(cuboids, cfg, frames)
        for f in findings:
            if f.rule in target_rules and f.severity != Severity.INFO:
                findings_out.append({
                    'scene': scene,
                    'frame': str(f.frame),
                    'track_id': str(f.track_id),
                    'label': f.label,
                    'rule': f.rule,
                    'severity': f.severity.value,
                    'message': f.message,
                    'details': f.details,
                })

    out_json = Path('review/2026-10-14/evidence/g7/candidate-findings.json')
    out_json.write_text(json.dumps(findings_out, default=default_serializer, ensure_ascii=False, indent=2), encoding='utf-8')
    
    out_csv = Path('review/2026-10-14/evidence/g7/candidate-findings.csv')
    with out_csv.open('w', encoding='utf-8-sig', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['scene', 'frame', 'track_id', 'label', 'rule', 'severity', 'message', 'verdict', 'note'])
        for item in findings_out:
            writer.writerow([
                item['scene'], item['frame'], item['track_id'], item['label'],
                item['rule'], item['severity'], item['message'], '', ''
            ])
    print(f'Successfully extracted {len(findings_out)} candidate findings.')

if __name__ == '__main__':
    main()
