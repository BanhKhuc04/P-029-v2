"""Compare an existing review packet with full nuScenes source orientation; never edit labels."""
from __future__ import annotations

import argparse
from dataclasses import replace
import hashlib
import html
import json
import math
from pathlib import Path
import subprocess
import sys

TOOL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOL))

import numpy as np

from pointsnap.adapters.nuscenes.reader import NuScenesReader
from pointsnap.core.box_points import box_point_sets, INSIDE_TOLERANCE_M
from pointsnap.core.camera import MIN_DEPTH_M, project_box, project_points
from pointsnap.core.config import load_config
from pointsnap.core.geometry import corners, invert_pose, pose_matrix, to_box_frame
from pointsnap.core.model import Cuboid
from pointsnap.web.preview import points_around_box

EDGES = ((0,1),(1,2),(2,3),(3,0),(4,5),(5,6),(6,7),(7,4),(0,4),(1,5),(2,6),(3,7))


def source_geometry(annotation, sensor_to_world, box):
    """Recover source corners without changing center, dimensions or annotation quaternion."""
    if annotation['token'] != box.attrs.get('nuscenes_annotation'):
        raise ValueError('Source annotation identity mismatch')
    transform = invert_pose(sensor_to_world) @ pose_matrix(annotation['translation'], annotation['rotation'])
    width, length, height = annotation['size']
    dims = (length, width, height)
    if (not np.allclose(transform[:3,3], box.center, rtol=0, atol=1e-8)
            or not np.allclose(dims, box.dims, rtol=0, atol=1e-8)):
        raise ValueError('Source center/dimensions do not match the reviewed box')
    if not np.isfinite(dims).all() or min(dims) <= 0:
        raise ValueError('Source dimensions must be finite and positive')
    local = corners(Cuboid(center=(0,0,0), dims=dims, yaw=0, label=box.label, frame=box.frame))
    return local @ transform[:3,:3].T + transform[:3,3], transform[:3,:3]


def camera_comparison(box, exact, pose, view, destination):
    from PIL import Image, ImageDraw
    current = project_box(box, pose, view)
    if current is None:
        raise ValueError('The reviewed camera no longer contains the box')
    world = exact @ pose[:3,:3].T + pose[:3,3]
    pixels, depth = project_points(world, view)
    if not np.isfinite(pixels).all() or np.any(depth < MIN_DEPTH_M):
        raise ValueError('Source corners are behind or too close to the camera')
    with Image.open(view.path) as original:
        image = original.convert('RGB')
    draw = ImageDraw.Draw(image)
    for polygon, color in ((current.polygon, '#24aeff'), (pixels, '#08b85c')):
        for a,b in EDGES:
            draw.line([tuple(polygon[a]),tuple(polygon[b])], fill=color, width=4)
    both = np.vstack((current.polygon, pixels))
    lo, hi = both.min(axis=0), both.max(axis=0)
    cx,cy = (lo+hi)/2
    radius = max(*(hi-lo),360) * .85
    image = image.crop((max(0,int(cx-radius)),max(0,int(cy-radius)),
                        min(image.width,int(cx+radius)),min(image.height,int(cy+radius))))
    image.thumbnail((1000,800)); image.save(destination, quality=90)
    return float(np.linalg.norm(pixels-current.polygon,axis=1).max())


def lidar_comparison(case, box, exact, destination):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    points = np.asarray(case['points'])
    reduced, full = to_box_frame(corners(box),box), to_box_frame(exact,box)
    fig, axes = plt.subplots(1,3,figsize=(13,4))
    for ax,(a,b,name) in zip(axes,((0,1,'Top x/y'),(0,2,'Side x/z'),(1,2,'Front y/z'))):
        if points.size:
            ax.scatter(points[:,a],points[:,b],s=1,color='#637586')
        for verts,color in ((reduced,'#24aeff'),(full,'#08b85c')):
            for i,j in EDGES:
                ax.plot(verts[[i,j],a],verts[[i,j],b],color=color,lw=1.6)
        ground=case.get('ground')
        if ground and b==2:
            xs=np.array(ax.get_xlim()); zs=np.full(2,ground['z'],dtype=float)
            if a==0:
                zs+=xs*math.tan(math.radians(ground['pitch_deg']))
            ax.plot(xs,zs,'--',color='#a77513',lw=1)
        ax.set_title(name);ax.set_xlabel('m');ax.set_ylabel('m');ax.set_aspect('equal');ax.grid(alpha=.15)
    fig.tight_layout();fig.savefig(destination,dpi=120);plt.close(fig)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dataset',required=True,type=Path)
    parser.add_argument('--packet',required=True,type=Path)
    parser.add_argument('--out',required=True,type=Path)
    args=parser.parse_args()
    if args.out.exists():
        parser.error('--out must be a new directory; preserve previous evidence and human answers')
    packet=json.loads(args.packet.read_text(encoding='utf-8'))
    cfg=load_config(env={});cfg=replace(cfg,camera=replace(cfg.camera,enabled='false'))
    config_hash=hashlib.sha256(json.dumps(cfg.to_dict(),sort_keys=True,ensure_ascii=False).encode()).hexdigest()
    if config_hash != packet['provenance']['config_sha256']:
        parser.error('Current measurement config differs from the reviewed packet')
    args.out.mkdir(parents=True);assets=args.out/'assets';assets.mkdir()
    reader=NuScenesReader(args.dataset);rows=[];cards=[];cache={};frames_by_scene={};boxes_by_scene={}
    for case in packet['cases']:
        scene=case['scene'];f=case['finding'];number=case['number']
        if scene not in boxes_by_scene:
            boxes_by_scene[scene]=reader.annotations(scene);frames_by_scene[scene]=reader.frames(scene)
        boxes=boxes_by_scene[scene];frames=frames_by_scene[scene]
        matched=[b for b in boxes if (b.frame,b.track_id,b.label)==(f['frame'],f['track_id'],f['label'])]
        if len(matched)!=1:
            raise ValueError('Reviewed box is missing or duplicated')
        box=matched[0]
        if not np.allclose(box.dims,[case['box'][k] for k in ('length','width','height')],rtol=0,atol=1e-8):
            raise ValueError('Dataset dimensions differ from the reviewed packet')
        data=frames.frame_data(box.frame);pose=data.sensor_to_world
        captured=np.asarray(case['points'],dtype=float).reshape(-1,3)
        current_points=np.round(points_around_box(data.points,box),3)
        if captured.shape!=current_points.shape or not np.array_equal(captured,current_points):
            raise ValueError('Displayed point evidence differs from the reviewed packet')
        annotation=reader._table('sample_annotation')[box.attrs['nuscenes_annotation']]
        exact,rotation=source_geometry(annotation,pose,box)
        key=(scene,box.frame)
        if key not in cache:
            cache[key]=box_point_sets(data.points,[b for b in boxes if b.visible and b.frame==box.frame],
                margin=cfg.fit.outside_margin_m,clearance=cfg.fit.ground_clearance_m,margin_rel=cfg.fit.outside_margin_rel)
        item=next(it for it in cache[key] if it.box==box)
        if item.num_object_points != case['object_points']:
            raise ValueError('Observed object point count differs from the reviewed packet')
        c,s=math.cos(box.yaw),math.sin(box.yaw)
        yaw=np.array([[c,-s,0],[s,c,0],[0,0,1]])
        source_local=(item.local @ yaw.T) @ rotation
        source_inside=np.all(np.abs(source_local)<=np.asarray(box.dims)/2+INSIDE_TOLERANCE_M,axis=1)
        image=f'{number:02}-camera.jpg';plot=f'{number:02}-lidar.png'
        view=next(v for v in frames.camera_views(box.frame) if v.channel==case['camera_channel'])
        displacement=camera_comparison(box,exact,pose,view,assets/image)
        lidar_comparison(case,box,exact,assets/plot)
        row={'case':number,'scene':scene,'frame':box.frame,'track_id':box.track_id,'label':box.label,
             'tilt_deg':math.degrees(box.attrs['tilt_rad']),
             'max_corner_difference_m':float(np.linalg.norm(exact-corners(box),axis=1).max()),
             'max_camera_corner_difference_pixels':displacement,
             'source_lowest_corner_minus_reduced_bottom_m':float(exact[:,2].min()-box.bottom_z),
             'observed_connected_points':item.num_object_points,'outside_reduced_box':item.num_outside,
             'outside_source_box_same_points':int((~source_inside).sum()),
             'center_and_dimensions_unchanged':True}
        rows.append(row)
        title=html.escape(f'Mẫu {number:02} · {scene} · frame {box.frame} · track {box.track_id} · {box.label}')
        cards.append(f'<article><h2>{title}</h2><p>Độ nghiêng gốc {row["tilt_deg"]:.2f}°. Góc box lệch tối đa {row["max_corner_difference_m"]*100:.1f} cm / {displacement:.1f} pixel trên ảnh gốc. Tâm và kích thước giữ nguyên.</p><img src="assets/{image}" alt="Khung gần đúng màu xanh dương và nhãn gốc màu xanh lá"><img src="assets/{plot}" alt="Ba mặt LiDAR đối chiếu góc box"></article>')
        print(f'Case {number:02}: tilt {row["tilt_deg"]:.2f} deg, corner difference {row["max_corner_difference_m"]:.3f} m',flush=True)
    summary={'packet_id':packet['provenance']['packet_id'],'detector_source_commit':packet['provenance']['source_commit'],
             'analysis_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=TOOL,text=True).strip(),
             'analysis_script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
             'config_sha256':config_hash,'cases':rows,'cvat_writes':0,'geometry_edits':0,
             'limits':'Source orientation comparison, not repaired geometry or detector rerun. Same connected point subset selected with reduced geometry; outside counts are descriptive. Camera/LiDAR capture times may differ. Does not prove source labels tight or human floating verdicts wrong.'}
    (args.out/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    page='''<!doctype html><html lang="vi"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Đối chiếu độ ôm sát box</title><style>body{max-width:1200px;margin:auto;padding:20px;font:16px/1.6 system-ui;background:#eff4f7;color:#142c3e}article{background:white;border:1px solid #cad6df;border-radius:10px;padding:18px;margin:20px 0}img{display:block;width:100%;max-height:640px;object-fit:contain}h1{font-size:26px}h2{font-size:20px}.notice{padding:14px;background:#fff4d7}</style><h1>Đối chiếu độ ôm sát box — 24 mẫu</h1><p><a href="../">Quay lại bộ chấm ban đầu</a> · <a href="../verdicts-user-20261014-all24.csv">CSV 24 kết luận của bạn</a></p><p class="notice">Xanh dương: box gần đúng chỉ giữ yaw đã dùng trong bộ chấm. Xanh lá: nhãn nuScenes gốc có đủ độ nghiêng. Hai khung dùng cùng tâm và kích thước; chưa sửa nhãn. Kết luận Đúng lỗi của bạn được giữ trong bộ bằng chứng ban đầu. Đối chiếu này giúp tách ảnh hưởng hiển thị khỏi vấn đề kích thước.</p><p>Khung 3D chiếu lên camera có thể dư so với đường viền 2D của xe. Mặt bị che hoặc thiếu điểm chưa đủ căn cứ để co box. Cần xác nhận các mặt thật của xe trước khi chọn kích thước sửa.</p>'''+''.join(cards)+'</html>'
    (args.out/'index.html').write_text(page,encoding='utf-8')
    print(json.dumps({'cases':len(rows),'max_corner_difference_m':max(r['max_corner_difference_m'] for r in rows),'cvat_writes':0}))


if __name__=='__main__':
    main()
