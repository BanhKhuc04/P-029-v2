"""Đo luật `fit.outside` theo ngưỡng: dời (0,3 / 0,5 m) hoặc co (x0,85 / x0,7) từng box có vật ≥ 30 điểm, giữ nguyên các
box khác, và đếm báo nhầm trên nhãn chuẩn.

    python scripts/eval_fit_outside.py tuning   # hoặc test (chỉ chạy một lần cho bản cuối)
"""
import dataclasses
import math
import os
import sys
from collections import defaultdict
import numpy as np
from pointsnap.adapters.nuscenes import NuScenesReader
from pointsnap.core.box_points import box_point_sets
from pointsnap.core.config import load_config
from pointsnap.core.model import add_track_markers, group_by_frame
from pointsnap.detectors.fit import outside_findings, outside_measure
from pointsnap.eval.split import TUNING_SCENES, TEST_SCENES
scenes = TUNING_SCENES if sys.argv[1] == "tuning" else TEST_SCENES
cfg = load_config(None); fc = dataclasses.replace(load_config(None).fit, outside_min_points=1)
r = NuScenesReader(os.environ["NUSCENES_ROOT"])
rng = np.random.default_rng(0)
clean, pert, visible = [], defaultdict(list), 0
kinds = ("dời 0,3 m", "dời 0,5 m", "co x0,85", "co x0,7")
def perturb(b, k):
    c, s = math.cos(b.yaw), math.sin(b.yaw)
    if k.startswith("dời"):
        d = (0.3 if "0,3" in k else 0.5) * rng.choice([-1, 1]); a = rng.integers(2)
        dx, dy = (d, 0) if a == 0 else (0, d)
        return b.replace(center=(b.center[0] + c*dx - s*dy, b.center[1] + s*dx + c*dy, b.center[2]))
    f = 0.85 if "0,85" in k else 0.7
    return b.replace(dims=(b.dims[0]*f, b.dims[1]*f, b.dims[2]))
for sc in scenes:
    fr = r.frames(sc)
    boxes = [b for b in add_track_markers(r.annotations(sc), fr.num_frames) if b.visible]
    visible += len(boxes)
    for frame, fb in group_by_frame(boxes).items():
        pts = fr.frame_data(frame).points
        items = box_point_sets(pts, fb, margin=fc.outside_margin_m, clearance=fc.ground_clearance_m, margin_rel=fc.outside_margin_rel)
        for i, it in enumerate(items):
            m = outside_measure(it, fc)
            if m is None or m.total < 30: continue
            clean.append(m)
            others = [b for j, b in enumerate(fb) if j != i and math.hypot(b.center[0]-it.box.center[0], b.center[1]-it.box.center[1]) < 15]
            for k in kinds:
                pb = perturb(it.box, k)
                it2 = box_point_sets(pts, [pb, *others], margin=fc.outside_margin_m, clearance=fc.ground_clearance_m, margin_rel=fc.outside_margin_rel)[0]
                pert[k].append(outside_measure(it2, fc))
by_track = defaultdict(list)
for m in clean: by_track[m.box.track_id].append(m)
print(f"{visible} box nhìn thấy, {len(clean)} box trong phạm vi fit.outside (vật ≥ 30 điểm)")
for minp in (30, 15):
    for w in (0.5, 0.4, 0.3, 0.25, 0.2):
        c = dataclasses.replace(fc, outside_min_points=minp, outside_warning_ratio=w, outside_error_ratio=max(w, 0.7))
        fp = len(outside_findings(clean, c))
        rec = []
        for k in kinds:
            hit = 0
            for m in pert[k]:
                if m is None: continue
                tr = [o for o in by_track[m.box.track_id] if o.box.frame != m.box.frame]
                hit += any(f.frame == m.box.frame for f in outside_findings(tr + [m], c))
            rec.append(f"{k} {hit/len(pert[k]):.0%}")
        print(f"min_points {minp} warning {w}: báo nhầm {fp} ({100*fp/visible:.2f} / 100 box) | " + " · ".join(rec))
