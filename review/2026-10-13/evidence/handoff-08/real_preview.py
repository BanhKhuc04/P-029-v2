"""Render a recovered deleted-object example; not a precision or recovery benchmark."""
import argparse
from collections import defaultdict
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT/'source-tool/pointsnap-3d'))
import numpy as np
from pointsnap.adapters.nuscenes.reader import NuScenesReader
from pointsnap.adapters.cvat.reader import ManifestFrames, find_manifest
from pointsnap.core.config import load_config
from pointsnap.core.serialize import save_cuboids
from pointsnap.detectors.missing import detect_missing_objects
from pointsnap.web.runner import finding_to_dict
from pointsnap.web.preview import finding_preview, finding_camera


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--dataroot',required=True)
    p.add_argument('--export-dir',required=True)
    p.add_argument('--out',required=True,type=Path)
    p.add_argument('--summary',required=True,type=Path)
    args=p.parse_args()
    reader=NuScenesReader(args.dataroot)
    boxes=reader.annotations('scene-0061')
    manifest=find_manifest(4,[Path(args.export_dir)],url='http://localhost:8080')
    frames=ManifestFrames(manifest,dataroot=args.dataroot)
    # The CVAT export is rotated into ego axes. Produce evidence in exactly that source's coordinates.
    matrix=np.asarray(frames.manifest.get('transform',np.eye(3)))
    turn=float(np.arctan2(matrix[1,0],matrix[0,0]))
    boxes=[b.replace(center=tuple(matrix@np.asarray(b.center)),yaw=b.yaw+turn) for b in boxes]
    tracks=defaultdict(list)
    for b in boxes:
        if b.attrs['num_lidar_pts']>=15:
            tracks[b.track_id].append(b)
    raw=reader._table('sample_annotation')
    targets=[]
    for tid, rows in tracks.items():
        if len(rows)<3:continue
        first=raw[rows[0].attrs['nuscenes_annotation']]['translation']
        last=raw[rows[-1].attrs['nuscenes_annotation']]['translation']
        if np.linalg.norm(np.array(last[:2])-first[:2])>=3:targets.append(tid)
    cfg=load_config(env={})
    selected=None
    for tid in targets:
        kept=[b for b in boxes if b.track_id!=tid]
        findings,_=detect_missing_objects(kept,frames,cfg.missing)
        if findings:
            selected=(tid,kept,findings[0]);break
    if selected is None:raise RuntimeError('No recovered moving example available')
    tid,kept,f=selected
    args.out.mkdir(parents=True,exist_ok=False)
    save_cuboids(args.out/'snapshot.json',kept,{'task_id':4,'url':'http://localhost:8080'})
    (args.out/'findings.json').write_bytes(json.dumps([finding_to_dict(f)]).encode())
    project={'export_dirs':[args.export_dir],'nuscenes_root':args.dataroot}
    preview=finding_preview(args.out,project,0)
    image,channel=finding_camera(args.out,project,0)
    assert preview['synthetic_box'] and preview['track_id'] is None and len(preview['points'])>=15
    (args.out/'camera.jpg').write_bytes(image)
    result={'model':'gpt-6.1-sol','scene':'scene-0061','deleted_track_id':tid,
            'finding_frame':f.frame,'rule':f.rule,'preview_points':len(preview['points']),
            'synthetic_box':preview['synthetic_box'],'camera_channel':channel,'jpeg_bytes':len(image),
            'scope':'One selected recovered deletion example; no CVAT writes or human verdicts'}
    args.summary.parent.mkdir(parents=True,exist_ok=True)
    args.summary.write_bytes((json.dumps(result,indent=2)+'\n').encode())
    print(json.dumps(result))


if __name__=='__main__':main()
