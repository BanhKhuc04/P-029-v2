"""Read-only scan/cache experiment; makes no product or CVAT annotation changes."""
from __future__ import annotations

import argparse
from collections import Counter
import dataclasses
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[3]
TOOL = ROOT / "source-tool" / "pointsnap-3d"
sys.path.insert(0, str(TOOL))

from pointsnap.adapters.nuscenes.reader import NuScenesReader
from pointsnap.core.config import load_config
from pointsnap.core.scanner import scan_cuboids
from pointsnap.web.runner import finding_to_dict


class ObservedFrames:
    def __init__(self, source, memoize=False):
        self.source = source
        self.memoize = memoize
        self.requests = Counter()
        self.loads = Counter()
        self.cache = {}

    def __getattr__(self, name):
        return getattr(self.source, name)

    def frame_data(self, frame, with_points=True):
        key = (frame, with_points)
        self.requests[with_points] += 1
        if self.memoize and key in self.cache:
            return self.cache[key]
        self.loads[with_points] += 1
        data = self.source.frame_data(frame, with_points=with_points)
        if self.memoize:
            self.cache[key] = data
        return data


def measure(job, config, source, memoize):
    frames = ObservedFrames(source, memoize=memoize)
    start = time.perf_counter()
    findings = scan_cuboids(job, config, frames)
    seconds = time.perf_counter() - start
    serialized = json.dumps([finding_to_dict(f) for f in findings], sort_keys=True,
                            ensure_ascii=False, allow_nan=False)
    return {
        "scan_seconds": round(seconds, 4),
        "point_requests": frames.requests[True],
        "point_source_loads": frames.loads[True],
        "metadata_requests": frames.requests[False],
        "metadata_source_loads": frames.loads[False],
        "retained_point_bytes": sum(d.points.nbytes for (_, points), d in frames.cache.items() if points),
        "findings": len(findings),
        "findings_sha256": hashlib.sha256(serialized.encode("utf-8")).hexdigest(),
        "counts_by_rule": dict(sorted(Counter(f.rule for f in findings).items())),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    reader = NuScenesReader(args.dataset)
    scene = "scene-0061"
    job = SimpleNamespace(cuboids=reader.annotations(scene), stop_frame=38)
    config = load_config(env={})
    config = dataclasses.replace(config, camera=dataclasses.replace(config.camera, enabled="false"))
    config_hash = hashlib.sha256(json.dumps(config.to_dict(), sort_keys=True).encode()).hexdigest()
    normal = measure(job, config, reader.frames(scene), False)
    experiment = measure(job, config, reader.frames(scene), True)
    normal_repeat = measure(job, config, reader.frames(scene), False)
    result = {
        "source_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "config_sha256": config_hash,
        "scene": scene,
        "boxes": len(job.cuboids),
        "frames": len({b.frame for b in job.cuboids}),
        "normal": normal,
        "experimental_memo": experiment,
        "normal_repeat": normal_repeat,
        "same_findings": normal["findings_sha256"] == experiment["findings_sha256"] == normal_repeat["findings_sha256"],
        "scope": "One scene, default geometry rules, camera disabled and no Critic model. Sequential one-shot runs with OS cache; timings are exploratory, not a performance guarantee. Experiment memoizes per-frame data only inside this script; product is unchanged. Retained bytes exclude Python/index/model/process memory. No network or CVAT writes.",
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_bytes((json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode("utf-8"))
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
