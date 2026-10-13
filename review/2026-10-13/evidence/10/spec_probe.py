"""Read-only spec-vn GT comparison; no CVAT writes or model downloads."""

import argparse
from collections import Counter
import dataclasses
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[4]
TOOL = ROOT / "source-tool/pointsnap-3d"
sys.path.insert(0, str(TOOL))

from pointsnap.adapters.nuscenes.reader import NuScenesFrames, NuScenesReader
from pointsnap.core.config import load_config
from pointsnap.core.scanner import scan_cuboids
from pointsnap.eval.split import TUNING_SCENES, TEST_SCENES


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataroot", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--scenes", nargs="+")
    args = parser.parse_args()
    if args.out.exists():
        parser.error("Choose a new output path")
    cfg = load_config(TOOL / "pointsnap/guidelines/spec-vn.yaml", env={})
    active = {"track_id_swap", "attr_missing", "attr_invalid", "attr_height", "spec_inside", "spec_rider_double",
              "attr_rider_state", "size_class_range", "size_in_track"}
    cfg = dataclasses.replace(cfg, rules=dataclasses.replace(cfg.rules, **{
        f.name: f.name in active for f in dataclasses.fields(cfg.rules)
    }))
    cfg_json = json.dumps(dataclasses.asdict(cfg), sort_keys=True)
    modules = ["detectors/attributes.py", "detectors/track.py", "detectors/size.py", "core/scanner.py", "core/config.py"]
    hashes = {p: hashlib.sha256((TOOL / "pointsnap" / p).read_bytes()).hexdigest() for p in modules}
    reader = NuScenesReader(args.dataroot, taxonomy="spec-vn")
    rows = []
    for scene in args.scenes or list(TUNING_SCENES + TEST_SCENES):
        start = time.perf_counter()
        boxes = reader.annotations(scene)
        found = scan_cuboids(boxes, cfg, NuScenesFrames(reader, scene))
        row = {"scene": scene, "split": "tuning" if scene in TUNING_SCENES else "test", "boxes": len(boxes),
               "counts": dict(sorted(Counter(f.rule + ":" + f.severity.value for f in found).items())),
               "identities": [[f.rule, f.severity.value, f.frame, f.track_id, f.label] for f in found],
               "seconds": round(time.perf_counter() - start, 3)}
        rows.append(row)
        print(json.dumps({k: v for k, v in row.items() if k != "identities"}), flush=True)
    result = {"source_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
              "source_hashes": hashes, "config_sha256": hashlib.sha256(cfg_json.encode()).hexdigest(),
              "config": json.loads(cfg_json), "dataset": "nuScenes v1.0-mini, taxonomy spec-vn",
              "measurement": "GT finding counts for spec/ID-swap/size subset; not manual precision", "scenes": rows}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
