"""Controlled spec/ID-swap perturbations on two tuning scenes, excluding clean hits."""

import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path
import subprocess

import numpy as np

from spec_probe import TOOL, ROOT
from pointsnap.adapters.nuscenes.reader import NuScenesReader, NuScenesFrames
from pointsnap.core.config import load_config
from pointsnap.core.model import group_by_track
from pointsnap.detectors.attributes import detect_attribute_height, detect_rider_state
from pointsnap.detectors.track import detect_id_swaps


def archived(path):
    source = subprocess.check_output(["git", "show", "cbeb41c:source-tool/pointsnap-3d/pointsnap/" + path],
                                     cwd=ROOT, text=True, encoding="utf-8")
    scope = {"__name__": "review10_baseline"}
    exec(compile(source, path, "exec"), scope)
    return scope


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--dataroot", required=True, type=Path)
    p.add_argument("--out", required=True, type=Path)
    args = p.parse_args()
    if args.out.exists():
        p.error("Choose a fresh output path")
    cfg = load_config(TOOL / "pointsnap/guidelines/spec-vn.yaml", env={})
    old_attr, old_track = archived("detectors/attributes.py"), archived("detectors/track.py")
    reader = NuScenesReader(args.dataroot, taxonomy="spec-vn")
    rows = []
    key = lambda b: b.label + "/" + str(b.attrs.get(cfg.size.key_attributes.get(b.label), ""))
    for scene in ("scene-0061", "scene-0553"):
        boxes = reader.annotations(scene)
        frames = NuScenesFrames(reader, scene)
        data = {f: frames.frame_data(f, with_points=False) for f in frames.refs}
        poses = {f: d.sensor_to_world for f, d in data.items()}
        times = {f: d.timestamp for f, d in data.items()}
        tracks = group_by_track(boxes)
        clean_height = {f.track_id for fn in (old_attr["detect_attribute_height"], detect_attribute_height)
                        for f in fn(boxes, cfg.spec)}
        targets = [g[len(g)//2] for tid, g in tracks.items() if tid not in clean_height and len(g) >= 5
                   and g[len(g)//2].label == "Pedestrian" and g[len(g)//2].attrs.get("pose") == "standing"
                   and g[len(g)//2].attrs.get("age_group") == "adult" and 1.65 < g[len(g)//2].height <= 2.2][:12]
        target_ids = {id(b) for b in targets}
        injected = [b.replace(attrs={**b.attrs, "pose": "sitting"}) if id(b) in target_ids else b for b in boxes]
        identities = {(b.track_id, b.frame) for b in targets}
        for name, fn in (("before", old_attr["detect_attribute_height"]), ("after", detect_attribute_height)):
            hits = {(f.track_id, f.frame) for f in fn(injected, cfg.spec)} & identities
            rows.append({"scene":scene, "kind":"standing_to_sitting", "profile":name,
                         "eligible_targets":len(identities), "new_hits":len(hits)})
        ids = [tid for tid,g in tracks.items() if len(g)>=5 and all(b.label=="Two-wheels" and
               b.attrs.get("rider_state")=="with_rider" for b in g)][:12]
        injected = [b.replace(attrs={**b.attrs,"rider_state":"without_rider"}) if b.track_id in ids else b for b in boxes]
        for name, fn in (("before", old_attr["detect_rider_state"]), ("after", detect_rider_state)):
            clean = fn(boxes, cfg.spec, poses)
            found = (fn(injected, cfg.spec, poses, cfg.track.keyframe_interval_s, times) if name=="after"
                     else fn(injected, cfg.spec, poses, cfg.track.keyframe_interval_s))
            clean_ids = {f.track_id for f in clean if f.details.get("kind")=="mount"}
            eligible = set(ids)-clean_ids
            hits = {f.track_id for f in found if f.details.get("kind")=="mount"} & eligible
            rows.append({"scene":scene, "kind":"with_to_without_rider", "profile":name,
                         "eligible_targets":len(eligible), "new_hits":len(hits)})
        pairs = []
        ids = sorted(tracks)
        for i,a in enumerate(ids):
            for b in ids[i+1:]:
                if key(tracks[a][0]) != key(tracks[b][0]):
                    continue
                aa,bb = {c.frame:c for c in tracks[a]}, {c.frame:c for c in tracks[b]}
                shared = sorted(aa.keys() & bb.keys())
                if len(shared)<6:
                    continue
                frame = shared[len(shared)//2]
                m = poses[frame]
                distance = np.linalg.norm((m[:3,:3] @ (np.asarray(aa[frame].center)-bb[frame].center))[:2])
                if .5 < distance <= 3 and key(aa[frame])==key(bb[frame]):
                    pairs.append((a,b,frame))
                if len(pairs)>=12:
                    break
            if len(pairs)>=12:
                break
        for name, fn in (("before", old_track["detect_id_swaps"]), ("after", detect_id_swaps)):
            kwargs = {"class_key":key} if name=="after" else {}
            clean_pairs = {frozenset((f.track_id,f.details["other_track_id"]))
                           for f in fn(boxes,cfg.track,poses,times,**kwargs)}
            eligible=hits=0
            for a,b,start in pairs:
                pair=frozenset((a,b))
                if pair in clean_pairs:
                    continue
                eligible+=1
                injected=[c.replace(track_id=b if c.track_id==a else a)
                          if c.track_id in pair and c.frame>=start else c for c in boxes]
                found=fn(injected,cfg.track,poses,times,**kwargs)
                hits+=any(frozenset((f.track_id,f.details["other_track_id"]))==pair and f.frame>=start for f in found)
            rows.append({"scene":scene,"kind":"same_type_id_swap","profile":name,
                         "eligible_targets":eligible,"new_hits":hits})
        print(json.dumps([r for r in rows if r["scene"]==scene]),flush=True)
    totals=defaultdict(lambda:{"eligible_targets":0,"new_hits":0})
    for r in rows:
        entry=totals[r["kind"]+":"+r["profile"]]
        entry["eligible_targets"]+=r["eligible_targets"]; entry["new_hits"]+=r["new_hits"]
    result={"baseline_commit":"cbeb41c","measurement":"Selected eligible targets on two tuning scenes; clean hits excluded; not full-mini recall",
            "rows":rows,"totals":dict(totals),"source_hashes":{x:hashlib.sha256((TOOL/"pointsnap"/x).read_bytes()).hexdigest()
            for x in ("detectors/attributes.py","detectors/track.py")}}
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(result,indent=2),encoding="utf-8")


if __name__=="__main__":
    main()
