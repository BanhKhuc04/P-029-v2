"""Fixed perturbations on two tuning scenes; separate from held-out quality counts."""

import argparse
from collections import defaultdict
import dataclasses
import json
import math
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

TOOL = Path(__file__).resolve().parents[4] / "source-tool" / "pointsnap-3d"
sys.path.insert(0, str(TOOL))

from pointsnap.adapters.nuscenes.reader import NuScenesFrames, NuScenesReader
from pointsnap.core.config import load_config
from pointsnap.core.scanner import check_box_points
from pointsnap.detectors.floating import detect_floating_scene, estimate_scene_ground


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataroot", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    if args.out.exists():
        parser.error("Choose a fresh output path")
    cfg = load_config(env={})
    reader = NuScenesReader(args.dataroot)
    old_code = subprocess.check_output([
        "git", "show", "3584000:source-tool/pointsnap-3d/pointsnap/detectors/floating.py"], cwd=TOOL, text=True,
        encoding="utf-8")
    baseline = {"__name__": "review09_baseline_floating"}
    exec(compile(old_code, "baseline-floating.py", "exec"), baseline)
    profiles = {
        "baseline_current_thresholds": (cfg, baseline["detect_floating_scene"]),
        "fixed_current_thresholds": (cfg, detect_floating_scene),
        "fixed_previous_thresholds": (dataclasses.replace(cfg, floating=dataclasses.replace(cfg.floating, warning_m=0.12),
            heading=dataclasses.replace(cfg.heading, points=dataclasses.replace(cfg.heading.points, warning_deg=15))),
            detect_floating_scene),
    }
    rows = []
    for scene in ("scene-0061", "scene-0553"):
        frames = NuScenesFrames(reader, scene)
        boxes = reader.annotations(scene)
        groups = defaultdict(list)
        for b, estimate in estimate_scene_ground(boxes, frames, cfg.floating):
            if estimate.is_valid:
                groups[(b.track_id, b.label)].append(b)
        # One frame per track prevents injected neighbours from becoming the reference.
        targets = {id(g[len(g) // 2]) for g in groups.values() if len(g) >= 5}
        selected = [b for b in boxes if id(b) in targets][:20]
        selected_ids = {id(b) for b in selected}
        identities = {(b.frame, b.track_id, b.label) for b in selected}
        for offset in (0.14, 0.25, -0.25):
            injected = [b.replace(center=(b.center[0], b.center[1], b.center[2] + offset))
                        if id(b) in selected_ids else b for b in boxes]
            for name, (config, detector) in profiles.items():
                findings = detector(injected, frames, config.floating)
                matched = {(f.frame, f.track_id, f.label) for f in findings if f.rule == "floating"} & identities
                row = {"scene": scene, "kind": "floating", "offset_m": offset, "profile": name,
                       "injected": len(identities), "detected": len(matched),
                       "targets": sorted(identities), "detected_targets": sorted(matched)}
                rows.append(row)
                print(json.dumps({k: v for k, v in row.items() if "targets" not in k}), flush=True)
        long_boxes = defaultdict(list)
        for b in boxes:
            if b.label in cfg.heading.points.classes and b.length >= cfg.heading.points.min_aspect * b.width:
                long_boxes[(b.track_id, b.label)].append(b)
        heading_targets = [g[len(g) // 2] for g in long_boxes.values() if len(g) >= 5][:20]
        heading_ids = {id(b) for b in heading_targets}
        identities = {(b.frame, b.track_id, b.label) for b in heading_targets}
        injected = [b.replace(yaw=b.yaw + math.radians(13)) if id(b) in heading_ids else b for b in boxes]
        for name in ("fixed_current_thresholds", "fixed_previous_thresholds"):
            config = profiles[name][0]
            job = SimpleNamespace(cuboids=injected)
            findings = check_box_points(job, config, frames)
            matched = {(f.frame, f.track_id, f.label) for f in findings if f.rule == "heading.points"} & identities
            row = {"scene": scene, "kind": "heading.points", "offset_deg": 13, "profile": name,
                   "injected": len(identities), "detected": len(matched),
                   "targets": sorted(identities), "detected_targets": sorted(matched)}
            rows.append(row)
            print(json.dumps({k: v for k, v in row.items() if "targets" not in k}), flush=True)
    result = {"baseline_commit": "3584000", "source_commit": subprocess.check_output(
                  ["git", "rev-parse", "HEAD"], cwd=TOOL, text=True).strip(),
              "measurement": "Target hit rate, two tuning scenes, max 20 per scene; not full recall/precision",
              "scope": "Baseline comparison uses archived floating module; core/ground.py unchanged", "rows": rows}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
