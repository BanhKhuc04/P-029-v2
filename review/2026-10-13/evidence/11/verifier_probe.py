"""Read-only real-mini static comparison and limited tuning-scene Critic export.

No human verdicts are generated. Raw exports remain in ignored out/.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import types

ROOT = Path(__file__).resolve().parents[4]
TOOL = ROOT / "source-tool/pointsnap-3d"
sys.path.insert(0, str(TOOL))

from pointsnap.adapters.nuscenes.reader import NuScenesReader, NuScenesFrames
from pointsnap.core.config import load_config
from pointsnap.critic import export_dataset
from pointsnap.detectors.static import detect_static_errors
from pointsnap.eval.split import TUNING_SCENES, TEST_SCENES


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataroot", required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--export-dir", type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists() or args.export_dir.exists():
        parser.error("Choose fresh output paths")
    cfg = load_config(env={}).static
    reader = NuScenesReader(args.dataroot)
    old = types.ModuleType("review11_baseline_static")
    source = subprocess.check_output(["git", "show", "8fce666:source-tool/pointsnap-3d/pointsnap/detectors/static.py"],
                                     cwd=ROOT).decode("utf-8")
    exec(compile(source, "baseline_static.py", "exec"), old.__dict__)
    rows = []
    for scene in TUNING_SCENES + TEST_SCENES:
        boxes = reader.annotations(scene)
        frames = NuScenesFrames(reader, scene)
        poses = {f: frames.frame_data(f, with_points=False).sensor_to_world for f in {b.frame for b in boxes}}
        before = old.detect_static_errors(boxes, cfg, poses)
        after = detect_static_errors(boxes, cfg, poses)
        identity = lambda fs: sorted([[f.rule, f.severity.value, f.frame, f.track_id, f.label] for f in fs])
        rows.append({"scene": scene, "split": "tuning" if scene in TUNING_SCENES else "held-out", "boxes": len(boxes),
                     "before": dict(Counter(f.rule+":"+f.severity.value for f in before)),
                     "after": dict(Counter(f.rule+":"+f.severity.value for f in after)),
                     "identities_changed": identity(before) != identity(after)})
        print(json.dumps(rows[-1]), flush=True)

    class LimitedReader:
        def annotations(self, scene):
            return [b for b in reader.annotations(scene) if b.frame < 3]
        def frames(self, scene):
            return NuScenesFrames(reader, scene)

    export_scenes = [TUNING_SCENES[0], TUNING_SCENES[1]]
    total = export_dataset(LimitedReader(), export_scenes, args.export_dir, samples_per_box=2, min_points=10, seed=11)
    import numpy as np
    exports = []
    for scene in export_scenes:
        path = args.export_dir / f"{scene}.npz"
        with np.load(path, allow_pickle=False) as data:
            exports.append({"scene": scene, "shapes": {k: list(data[k].shape) for k in data.files},
                            "all_finite": all(np.isfinite(data[k]).all() for k in data.files),
                            "unchanged": int(np.all(data["target"] == 0, axis=1).sum()),
                            "errors": int(data["is_error"].sum()), "frames": sorted(set(data["frame"].tolist())),
                            "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
    result = {"baseline_commit": "8fce666", "dataset": "nuScenes v1.0-mini, default taxonomy",
              "static_scope": "10 full scenes; counts are clean-GT findings, not human precision", "static": rows,
              "export_scope": "two tuning scenes, first three frames only, two samples per eligible box",
              "exports": exports, "totals": total,
              "source_hashes": {p: hashlib.sha256((TOOL/p).read_bytes()).hexdigest() for p in
                                ["pointsnap/detectors/static.py", "pointsnap/critic.py", "scripts/train_critic_example.py"]}}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
