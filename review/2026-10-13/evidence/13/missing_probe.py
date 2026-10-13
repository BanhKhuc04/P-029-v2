"""Read-only mini deletion probe: targets selected from raw GT, independent spatial matcher."""
import argparse
from collections import defaultdict
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[4]
TOOL = ROOT / "source-tool/pointsnap-3d"
sys.path.insert(0, str(TOOL))
import numpy as np
from pointsnap.adapters.nuscenes.reader import NuScenesReader
from pointsnap.core.config import MissingConfig
from pointsnap.detectors.missing import detect_missing_objects
from pointsnap.eval.split import TUNING_SCENES, TEST_SCENES


def match(finding, truth):
    hits = 0
    boxes = {b.frame:b for b in truth}
    for frame, center in zip(finding.details["frames"], finding.details["centers"]):
        if frame not in boxes:
            continue
        box = boxes[frame]
        delta = np.asarray(center) - box.center[:2]
        c,s = np.cos(box.yaw), np.sin(box.yaw)
        local = np.array([c*delta[0]+s*delta[1], -s*delta[0]+c*delta[1]])
        if np.all(np.abs(local) <= np.asarray(box.dims[:2])/2 + .75):
            hits += 1
    return hits >= 2


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--dataroot",required=True)
    parser.add_argument("--out",type=Path,required=True)
    parser.add_argument("--baseline",type=Path)
    args=parser.parse_args()
    if args.out.exists(): parser.error("Choose a fresh output")
    functions={"current":detect_missing_objects}
    if args.baseline:
        spec=importlib.util.spec_from_file_location("review13_baseline_missing",args.baseline)
        module=importlib.util.module_from_spec(spec);sys.modules[spec.name]=module;spec.loader.exec_module(module)
        functions["baseline"]=module.detect_missing_objects
    reader=NuScenesReader(args.dataroot)
    cfg=MissingConfig()
    output={"evidence_id":"EV-13-003","dataset":"nuScenes v1.0-mini","config":vars(cfg),
            "target_selection":"First two eligible instance tokens per scene, sorted; >=3 frames with raw num_lidar_pts>=15 and raw GT displacement>=3m; no tuning from results",
            "matching":"At least two reported local centers inside corresponding GT yaw footprint expanded .75m; no finding track ID used",
            "limits":["Deleted-label recovery only for this selected subset; not overall recall", "Clean-label candidates are a proxy, not human-confirmed false alarms", "No pretrained/static-camera quality or human verdicts"],
            "source_sha256":hashlib.sha256((TOOL/"pointsnap/detectors/missing.py").read_bytes()).hexdigest(),
            "baseline_sha256":hashlib.sha256(args.baseline.read_bytes()).hexdigest() if args.baseline else None,"scenes":[]}
    raw=reader._table("sample_annotation")
    for scene in list(TUNING_SCENES)+list(TEST_SCENES):
        frames=reader.frames(scene);boxes=reader.annotations(scene)
        tracks=defaultdict(list)
        for box in boxes:
            if box.label in {"car","truck","bus","pedestrian","bicycle","motorcycle"}:
                tracks[box.attrs["nuscenes_instance"]].append(box)
        eligible=[]
        for token,rows in sorted(tracks.items()):
            good=[b for b in rows if b.attrs["num_lidar_pts"]>=15 and np.hypot(*b.center[:2])<=cfg.max_range_m]
            if len(good)<3: continue
            first=raw[good[0].attrs["nuscenes_annotation"]]["translation"]
            last=raw[good[-1].attrs["nuscenes_annotation"]]["translation"]
            displacement=float(np.linalg.norm(np.array(last[:2])-first[:2]))
            if displacement>=3: eligible.append((token,rows,displacement))
        result={"scene":scene,"split":"tuning" if scene in TUNING_SCENES else "test","frames":frames.num_frames,
                "boxes":len(boxes),"eligible_tracks":len(eligible),"targets":[],"clean":{}}
        for version,function in functions.items():
            start=time.perf_counter();found,_=function(boxes,frames,cfg)
            result["clean"][version]={"candidates":len(found),"seconds":time.perf_counter()-start}
        for token,truth,disp in eligible[:2]:
            kept=[b for b in boxes if b.attrs["nuscenes_instance"]!=token]
            target={"instance":token,"label":truth[0].label,"removed_boxes":len(truth),"raw_displacement_m":disp,"results":{}}
            assert len(boxes)-len(kept)==len(truth)
            for version,function in functions.items():
                start=time.perf_counter();found,_=function(kept,frames,cfg)
                target["results"][version]={"recovered":any(match(f,truth) for f in found),"candidates":len(found),"seconds":time.perf_counter()-start}
            result["targets"].append(target)
        output["scenes"].append(result)
        print(json.dumps({"scene":scene,"targets":len(result["targets"]),"clean":result["clean"]}),flush=True)
    output["summary"]={}
    for split in ("tuning","test"):
        scenes=[s for s in output["scenes"] if s["split"]==split]
        targets=[t for s in scenes for t in s["targets"]]
        output["summary"][split]={"scenes":len(scenes),"deleted_objects":len(targets),"versions":{
            v:{"recovered":sum(t["results"][v]["recovered"] for t in targets),
               "clean_candidates":sum(s["clean"][v]["candidates"] for s in scenes)} for v in functions}}
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(output,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(output["summary"]),flush=True)


if __name__=="__main__":main()
