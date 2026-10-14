"""Build a local human-review packet from current floating findings; create no verdicts or CVAT writes."""
from __future__ import annotations

import argparse
from collections import defaultdict, deque
import csv
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

TOOL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOL))

import numpy as np

from pointsnap.adapters.nuscenes.reader import NuScenesReader
from pointsnap.core.box_points import box_point_sets
from pointsnap.core.camera import project_box
from pointsnap.core.config import load_config
from pointsnap.core.model import Severity
from pointsnap.core.repair_preview import RepairPreviewError, floating_z_preview
from pointsnap.core.scanner import check_floating, scan_cuboids
from pointsnap.web.preview import points_around_box, preview_ground
from pointsnap.web.runner import finding_to_dict

EDGES = ((0,1),(1,2),(2,3),(3,0),(4,5),(5,6),(6,7),(7,4),(0,4),(1,5),(2,6),(3,7))


def select_cases(candidates, count):
    """Deterministic scene round-robin, earliest finding per track; never select by repair eligibility."""
    queues = defaultdict(deque)
    seen = set()
    for item in sorted(candidates, key=lambda x: (x['scene'], x['finding'].frame,
                                                 x['finding'].track_id or -1, x['finding'].label)):
        f = item['finding']
        key = (item['scene'], f.track_id, f.label)
        if key not in seen:
            queues[item['scene']].append(item)
            seen.add(key)
    result = []
    while len(result) < count and any(queues.values()):
        for scene in sorted(queues):
            if queues[scene] and len(result) < count:
                result.append(queues[scene].popleft())
    return result


def packet_id(config_hash, cases, asset_hashes):
    """Keep verdicts bound to this exact evidence, including the rendered images."""
    data={'config':config_hash,'cases':cases,'assets':asset_hashes}
    return hashlib.sha256(json.dumps(data,sort_keys=True,ensure_ascii=False,allow_nan=False).encode()).hexdigest()


def camera_image(box, frames, path):
    """Scientific overlay of the current cuboid; same calibrated pose as the scanner."""
    from PIL import Image, ImageDraw
    pose = frames.frame_data(box.frame, with_points=False).sensor_to_world
    projected = [(view, project_box(box, pose, view)) for view in frames.camera_views(box.frame)]
    projected = [(v,p) for v,p in projected if p is not None and v.path.is_file()]
    if not projected:
        return None
    view, p = max(projected, key=lambda vp: (vp[1].box[2]-vp[1].box[0]) * (vp[1].box[3]-vp[1].box[1]) * vp[1].inside_ratio)
    with Image.open(view.path) as original:
        image = original.convert('RGB')
    draw = ImageDraw.Draw(image)
    for a,b in EDGES:
        draw.line([tuple(map(float,p.polygon[a])), tuple(map(float,p.polygon[b]))], fill=(36,174,255), width=4)
    x1,y1,x2,y2 = p.box
    cx,cy = (x1+x2)/2,(y1+y2)/2
    radius = max(x2-x1,y2-y1,360) * .85
    crop = (max(0,int(cx-radius)),max(0,int(cy-radius)),min(image.width,int(cx+radius)),min(image.height,int(cy+radius)))
    image = image.crop(crop)
    image.thumbnail((1000,800))
    image.save(path, format='JPEG', quality=90)
    return view.channel


def plot_context(reader, scene, box, boxes, destination):
    """Show the earlier/later keyframe of the same track, independently from a proposed correction."""
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.patches import Rectangle
    track = sorted((b for b in boxes if b.track_id==box.track_id and b.label==box.label and b.visible), key=lambda b:b.frame)
    previous = [b for b in track if b.frame<box.frame]
    following = [b for b in track if b.frame>box.frame]
    peers = ([previous[-1]] if previous else []) + ([following[0]] if following else [])
    frames = reader.frames(scene)
    fig, axes = plt.subplots(1, len(peers) or 1, figsize=(10,3.2), squeeze=False)
    for ax, peer in zip(axes[0], peers):
        local = points_around_box(frames.frame_data(peer.frame).points,peer,max_points=2500)
        ax.scatter(local[:,0],local[:,2],s=1.0,color='#536575')
        ax.add_patch(Rectangle((-peer.length/2,-peer.height/2),peer.length,peer.height,fill=False,edgecolor='#087aad',lw=1.7))
        ax.set_title(f'Frame {peer.frame} — side view')
        ax.set_xlabel('local x (m)'); ax.set_ylabel('local z (m)'); ax.set_aspect('equal')
        ax.grid(alpha=.15)
    if not peers:
        axes[0,0].text(.5,.5,'No visible neighbouring keyframe',ha='center',va='center',transform=axes[0,0].transAxes)
    fig.tight_layout(); fig.savefig(destination,dpi=120); plt.close(fig)
    return [b.frame for b in peers]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dataset',type=Path,required=True)
    parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--count',type=int,default=24)
    args = parser.parse_args()
    if not 1 <= args.count <= 100:
        parser.error('--count must be between 1 and 100')
    if args.out.exists():
        parser.error('--out must be a new directory; existing human reviews must not be overwritten')
    args.out.mkdir(parents=True)
    assets=args.out/'assets'; assets.mkdir()
    reader=NuScenesReader(args.dataset)
    config=load_config(env={})
    config=replace(config,camera=replace(config.camera,enabled='false'))
    scenes=sorted(s.name for s in reader.scenes())
    boxes_by_scene={}; candidates=[]
    for scene in scenes:
        boxes=reader.annotations(scene); boxes_by_scene[scene]=boxes
        findings=scan_cuboids(SimpleNamespace(cuboids=boxes),config,reader.frames(scene),detectors=[check_floating])
        matched={(b.frame,b.track_id,b.label):b for b in boxes}
        items=[f for f in findings if f.rule=='floating' and f.severity in (Severity.WARNING,Severity.ERROR)]
        candidates.extend({'scene':scene,'finding':f,'box':matched[(f.frame,f.track_id,f.label)]} for f in items)
        print(f'{scene}: {len(items)} actionable floating findings',flush=True)
    selected=select_cases(candidates,args.count)
    cases=[]
    for i,item in enumerate(selected):
        scene,f,box=item['scene'],item['finding'],item['box']
        frames=reader.frames(scene); boxes=boxes_by_scene[scene]
        points=frames.frame_data(box.frame).points
        in_frame=[b for b in boxes if b.visible and b.frame==box.frame]
        items=box_point_sets(points,in_frame,margin=config.fit.outside_margin_m,clearance=config.fit.ground_clearance_m,
                             margin_rel=config.fit.outside_margin_rel)
        n_points=next(it.num_object_points for it in items if it.box==box)
        proposal=None; why=''
        try:
            p=floating_z_preview(f,box,boxes,config.floating,object_points=n_points)
            proposal={'delta_z_m':p.delta_z_m,'reference_distance_m':p.reference_distance_m,'reference_frames':p.reference_frames,
                      'before_center':p.before.center,'after_center':p.after.center}
        except RepairPreviewError as exc:
            why=str(exc)
        number=f'{i+1:02}'
        channel=camera_image(box,frames,assets/f'{number}-camera.jpg')
        peer_frames=plot_context(reader,scene,box,boxes,assets/f'{number}-context.png')
        case={'number':i+1,'scene':scene,'finding':finding_to_dict(f),'object_points':n_points,
              'box':{'length':box.length,'width':box.width,'height':box.height},
              'points':np.round(points_around_box(points,box),3).tolist(),'ground':preview_ground(finding_to_dict(f),box),
              'camera':f'assets/{number}-camera.jpg' if channel else None,'camera_channel':channel,
              'context':f'assets/{number}-context.png','context_frames':peer_frames,'proposal':proposal,'proposal_reason':why}
        cases.append(case)
        print(f'Case {number}: {scene}/frame {box.frame}/track {box.track_id}, preview={proposal is not None}',flush=True)
    cfg_json=json.dumps(config.to_dict(),sort_keys=True,ensure_ascii=False).encode()
    package_hash=hashlib.sha256()
    for file in sorted((TOOL/'pointsnap').rglob('*.py')):
        package_hash.update(file.relative_to(TOOL).as_posix().encode())
        package_hash.update(file.read_bytes().replace(b'\r\n',b'\n'))
    provenance={'source_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=TOOL,text=True).strip(),
                'package_sha256':package_hash.hexdigest(),
                'working_tree':subprocess.check_output(['git','status','--short'],cwd=TOOL,text=True).strip(),
                'config_sha256':hashlib.sha256(cfg_json).hexdigest(),'scene_count':len(scenes),
                'candidate_findings':len(candidates),'cases':len(cases),'preview_cases':sum(c['proposal'] is not None for c in cases),
                'selection':'Scene round-robin; earliest actionable finding per scene/track/label, no ranking by preview eligibility.',
                'dataset':'nuScenes mini; previously used for tuning/review, not independent held-out.',
                'g7_status':'UNASSESSED','verdicts_created':0,'cvat_writes':0,
                'limits':'Floating-only exploratory review; preview has not been accepted by a human. No Apply endpoint, no automatic repair. Crop and views support manual inspection; not a full scene or sensor visibility proof.'}
    asset_hashes={p.relative_to(args.out).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(assets.iterdir()) if p.is_file()}
    provenance['packet_id']=packet_id(provenance['config_sha256'],cases,asset_hashes)
    provenance['assets_sha256']=asset_hashes
    (args.out/'packet.json').write_bytes((json.dumps({'provenance':provenance,'cases':cases},ensure_ascii=False,allow_nan=False)+'\n').encode())
    (args.out/'provenance.json').write_bytes((json.dumps(provenance,indent=2,ensure_ascii=False)+'\n').encode())
    fields=['scene','frame','track_id','label','rule','severity','message','verdict','note','repair_verdict','repair_note']
    with (args.out/'verdicts-template.csv').open('w',encoding='utf-8-sig',newline='') as handle:
        writer=csv.DictWriter(handle,fieldnames=fields);writer.writeheader()
        for case in cases:
            f=case['finding']
            writer.writerow({**{k:f[k] for k in ('frame','track_id','label','rule','severity','message')},'scene':case['scene']})
    template=(Path(__file__).with_name('floating_review.html')).read_text(encoding='utf-8')
    embedded=json.dumps({'provenance':provenance,'cases':cases},ensure_ascii=False,allow_nan=False).replace('<','\\u003c').replace('>','\\u003e').replace('&','\\u0026')
    (args.out/'index.html').write_bytes(template.replace('__PACKET_JSON__',embedded).encode())
    print(json.dumps(provenance,ensure_ascii=False),flush=True)


if __name__=='__main__':
    main()
