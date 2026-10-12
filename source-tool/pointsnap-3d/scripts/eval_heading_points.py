"""Đo luật `heading.points` theo ngưỡng `warning_deg`: xoay từng box thuộc phạm vi luật 10° / 15° / 20° (giữ nguyên các
box khác) và đếm báo nhầm trên nhãn chuẩn.

    python scripts/eval_heading_points.py tuning   # hoặc test (chỉ chạy một lần cho bản cuối)
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
from pointsnap.detectors.heading import heading_points_findings, heading_points_measure
from pointsnap.eval.split import TUNING_SCENES, TEST_SCENES
if len(sys.argv) != 2 or sys.argv[1] not in ("tuning", "test") or not os.environ.get("NUSCENES_ROOT"):
    sys.exit(f"Cách chạy: NUSCENES_ROOT=<thư mục nuScenes> python {sys.argv[0]} tuning|test")
scenes = TUNING_SCENES if sys.argv[1] == "tuning" else TEST_SCENES
cfg = load_config(None)
fc, hc = cfg.fit, cfg.heading.points
r = NuScenesReader(os.environ["NUSCENES_ROOT"])
clean, rotated, visible = [], defaultdict(list), 0
rng = np.random.default_rng(0)
for s in scenes:
    fr = r.frames(s)
    boxes = [b for b in add_track_markers(r.annotations(s), fr.num_frames) if b.visible]
    visible += len(boxes)
    for frame, fb in group_by_frame(boxes).items():
        pts = fr.frame_data(frame).points
        items = box_point_sets(pts, fb, margin=fc.outside_margin_m, clearance=fc.ground_clearance_m, margin_rel=fc.outside_margin_rel)
        for i, item in enumerate(items):
            dev = heading_points_measure(item, hc)
            if dev is None:
                continue
            clean.append((item.box, dev))
            others = [b for j, b in enumerate(fb) if j != i and math.hypot(b.center[0]-item.box.center[0], b.center[1]-item.box.center[1]) < 15]
            for deg in (10, 15, 20):
                rot = item.box.replace(yaw=item.box.yaw + math.radians(deg) * rng.choice([-1, 1]))
                it = box_point_sets(pts, [rot, *others], margin=fc.outside_margin_m, clearance=fc.ground_clearance_m, margin_rel=fc.outside_margin_rel)[0]
                d = heading_points_measure(it, hc)
                rotated[deg].append((rot, d))
print(f"{visible} box nhìn thấy, {len(clean)} box trong phạm vi heading.points")
by_track = defaultdict(list)
for b, d in clean:
    by_track[b.track_id].append((b, d))
for w in (8, 10, 12, 15):
    c = dataclasses.replace(hc, warning_deg=float(w))
    fp = len(heading_points_findings(clean, c))
    rec = {}
    for deg, rows in rotated.items():
        hit = n = 0
        for rot, d in rows:
            if d is None:
                n += 1; continue
            track = [(b, dd) for b, dd in by_track[rot.track_id] if b.frame != rot.frame]
            found = heading_points_findings(track + [(rot, d)], c)
            hit += any(f.frame == rot.frame for f in found); n += 1
        rec[deg] = hit / n
    print(f"warning_deg {w:>2}: báo nhầm {fp} mục ({100*fp/visible:.2f} / 100 box) | bắt xoay 10° {rec[10]:.0%} · 15° {rec[15]:.0%} · 20° {rec[20]:.0%}")
