"""Reproduce clean-GT geometry finding counts on nuScenes mini, without CVAT writes.

Run from the tool root with its Python environment; --out must be a new path.
Counts on clean GT are a quality proxy, not manually verified false positives.
"""

import argparse
from collections import Counter
import dataclasses
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

TOOL = Path(__file__).resolve().parents[4] / "source-tool" / "pointsnap-3d"
sys.path.insert(0, str(TOOL))

from pointsnap.adapters.nuscenes.reader import NuScenesFrames, NuScenesReader
from pointsnap.core.config import load_config
from pointsnap.core.scanner import scan_cuboids
from pointsnap.eval.split import TEST_SCENES, TUNING_SCENES


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataroot", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--scenes", nargs="+")
    parser.add_argument("--previous-thresholds", action="store_true")
    args = parser.parse_args()
    if args.out.exists():
        parser.error("Output already exists; choose a fresh path")
    cfg = load_config(env={})
    enabled = {"floating", "heading_flip", "heading_motion", "heading_points", "fit_empty", "fit_outside",
               "fit_loose", "fit_overlap", "track_jump", "size_class_range", "size_in_track"}
    cfg = dataclasses.replace(cfg, rules=dataclasses.replace(cfg.rules, **{
        f.name: f.name in enabled for f in dataclasses.fields(cfg.rules)
    }))
    if args.previous_thresholds:
        cfg = dataclasses.replace(cfg, floating=dataclasses.replace(cfg.floating, warning_m=0.12),
                                  heading=dataclasses.replace(cfg.heading, points=dataclasses.replace(
                                      cfg.heading.points, warning_deg=15.0)))
    config_json = json.dumps(dataclasses.asdict(cfg), sort_keys=True, ensure_ascii=False)
    reader = NuScenesReader(args.dataroot)
    scenes = args.scenes or list(TUNING_SCENES + TEST_SCENES)
    rows = []
    for scene in scenes:
        start = time.perf_counter()
        boxes = reader.annotations(scene)
        findings = scan_cuboids(boxes, cfg, NuScenesFrames(reader, scene))
        row = {"scene": scene, "split": "tuning" if scene in TUNING_SCENES else "test", "boxes": len(boxes),
               "seconds": round(time.perf_counter() - start, 3),
               "findings": dict(sorted(Counter(f.rule + ":" + f.severity.value for f in findings).items())),
               "identities": [[f.rule, f.severity.value, f.frame, f.track_id, f.label] for f in findings]}
        rows.append(row)
        print(json.dumps({k: v for k, v in row.items() if k != "identities"}), flush=True)
    modules = ["core/ground.py", "core/box_points.py", "detectors/floating.py", "detectors/track.py",
               "detectors/heading.py", "detectors/fit.py"]
    result = {"source_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=TOOL, text=True).strip(),
              "source_hashes": {p: hashlib.sha256((TOOL / "pointsnap" / p).read_bytes()).hexdigest() for p in modules},
              "config_sha256": hashlib.sha256(config_json.encode()).hexdigest(),
              "config": json.loads(config_json), "python": sys.version,
              "dataset": "nuScenes v1.0-mini", "previous_thresholds": args.previous_thresholds,
              "measurement": "Findings on GT; no human precision verdicts; no CVAT writes", "scenes": rows}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
