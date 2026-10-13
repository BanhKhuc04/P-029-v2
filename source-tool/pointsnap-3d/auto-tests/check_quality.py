"""Check clean-label proxies on held-out scenes, separately from tuning.

GT findings are proxies, not human-confirmed false alarms. No threshold tuning
or CVAT writes occur. Returns 1 if the observed proxy exceeds a stated target.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import time


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    from pointsnap.adapters.nuscenes import NuScenesReader
    from pointsnap.core.config import load_config
    from pointsnap.core.model import add_track_markers
    from pointsnap.core.scanner import scan_cuboids
    from pointsnap.eval.split import TEST_SCENES
    cfg = load_config(env={})
    reader = NuScenesReader(args.dataset)
    rows = []
    totals = Counter()
    boxes = 0
    for scene in TEST_SCENES:
        frames = reader.frames(scene)
        cuboids = add_track_markers(reader.annotations(scene), frames.num_frames)
        count = sum(b.visible for b in cuboids)
        started = time.monotonic()
        findings = scan_cuboids(cuboids, cfg, frames)
        elapsed = time.monotonic() - started
        counts = Counter(f.rule + "|" + f.severity.value for f in findings)
        totals.update(counts)
        boxes += count
        rows.append(dict(scene=scene, visible_boxes=count, clean_counts=dict(counts),
                         scan_seconds=round(elapsed, 3)))
        print(f"{scene}: {count} boxes; {elapsed:.2f}s", flush=True)
    rates = {}
    for level in ("warning", "error"):
        n = sum(v for k, v in totals.items() if k.endswith("|" + level) and not k.startswith("floating.no_evidence"))
        rates[level] = dict(count=n, per_100_boxes=n / boxes * 100 if boxes else None)
    thresholds = dict(warning=2.0, error=0.5)
    passed = bool(boxes) and all(rates[k]["per_100_boxes"] <= v for k, v in thresholds.items())
    config = cfg.to_dict(redact=True)
    result = dict(status="PASS" if passed else "FAIL", split="held-out test", scenes=rows, boxes=boxes,
                  clean_counts=dict(totals), rates=rates, thresholds=thresholds,
                  config_sha256=hashlib.sha256(json.dumps(config, sort_keys=True).encode()).hexdigest(),
                  camera_active=cfg.camera.active(), camera_model=cfg.camera.effective_model(),
                  manual_precision=None, false_alarm_proxy=True,
                  timing_context="Serial clean scans after full evaluation; OS/model caches warm; not a hardware minimum benchmark")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(dict(status=result["status"], boxes=boxes, rates=rates), indent=2), flush=True)
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
