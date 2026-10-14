"""Independent projection oracle on real mini calibration; no model, tuning or CVAT writes."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[4]
TOOL=ROOT/'source-tool/pointsnap-3d'
sys.path.insert(0,str(TOOL))
import numpy as np
from PIL import Image,ImageDraw
from pointsnap.adapters.nuscenes.reader import NuScenesReader
from pointsnap.core.camera import project_box,project_points


def rotation(q):
    w,x,y,z=q
    return np.array([[1-2*(y*y+z*z),2*(x*y-z*w),2*(x*z+y*w)],
                     [2*(x*y+z*w),1-2*(x*x+z*z),2*(y*z-x*w)],
                     [2*(x*z-y*w),2*(y*z+x*w),1-2*(x*x+y*y)]])


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--dataroot',required=True)
    parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--image-out',type=Path,required=True)
    args=parser.parse_args()
    if args.out.exists() or args.image_out.exists():parser.error('Choose fresh paths')
    reader=NuScenesReader(args.dataroot);ref=reader.samples('scene-0061')[0]
    annotations=reader._annotations_by_sample[ref.sample_token]
    points_world=np.array([a['translation'] for a in annotations])
    boxes=[b for b in reader.annotations('scene-0061') if b.frame==0]
    data=reader.frame_data(ref,with_points=False)
    records=reader._camera_records_by_sample[ref.sample_token]
    views=reader.camera_views(ref)
    rows=[];canvas=Image.new('RGB',(1200,3*370),(20,20,20))
    for i,(record,view) in enumerate(zip(records,views)):
        calibration=reader._table('calibrated_sensor')[record['calibrated_sensor_token']]
        ego=reader._table('ego_pose')[record['ego_pose_token']]
        # Quaternion rotations and two inverses computed directly from raw metadata, independently of core poses.
        points_ego=(points_world-np.array(ego['translation']))@rotation(ego['rotation'])
        points_cam=(points_ego-np.array(calibration['translation']))@rotation(calibration['rotation'])
        uvw=points_cam@np.asarray(calibration['camera_intrinsic']).T
        expected=uvw[:,:2]/uvw[:,2:3]
        actual,depth=project_points(points_world,view)
        valid=depth>=.5
        pixel_error=float(np.max(np.abs(actual[valid]-expected[valid])))
        unfiltered_pixel_error=float(np.max(np.abs(actual-expected)))
        depth_error=float(np.max(np.abs(depth-points_cam[:,2])))
        assert pixel_error<1e-6 and depth_error<1e-8
        with Image.open(view.path) as original:
            assert original.size==(view.width,view.height)
            tile=original.convert('RGB').resize((600,338))
        draw=ImageDraw.Draw(tile);projected=0
        for box in boxes:
            p=project_box(box,data.sensor_to_world,view)
            if p is None or p.inside_ratio<.85 or p.depth>45:continue
            projected+=1;x1,y1,x2,y2=p.box
            draw.rectangle((x1*600/view.width,y1*338/view.height,x2*600/view.width,y2*338/view.height),outline=(80,255,80),width=1)
        x,y=(i%2)*600,(i//2)*370;canvas.paste(tile,(x,y));ImageDraw.Draw(canvas).text((x+8,y+343),view.channel,fill='white')
        rows.append({'channel':view.channel,'image_sha256':hashlib.sha256(view.path.read_bytes()).hexdigest(),
                     'image_size':[view.width,view.height],'world_centers_tested':len(points_world),
                     'max_pixel_error':pixel_error,'max_depth_error':depth_error,'projected_boxes':projected,
                     'front_centers_tested':int(valid.sum()),'unfiltered_pixel_error':unfiltered_pixel_error,
                     'camera_lidar_timestamp_difference_s':(record['timestamp']-reader._lidar_by_sample[ref.sample_token]['timestamp'])/1e6})
    assert len(rows)==6
    args.image_out.parent.mkdir(parents=True,exist_ok=True);canvas.save(args.image_out)
    result={'scene':'scene-0061','frame':0,'split':'tuning','sample_token':ref.sample_token,'dataset':'nuScenes v1.0-mini',
            'measurement':'Independent raw-metadata world-center projection; annotated image is a visual QA artifact, not model precision',
            'views':rows,'image_artifact_sha256':hashlib.sha256(args.image_out.read_bytes()).hexdigest(),
            'source_hashes':{p:hashlib.sha256((TOOL/p).read_bytes()).hexdigest() for p in
                             ['pointsnap/core/camera.py','pointsnap/adapters/nuscenes/reader.py']}}
    args.out.parent.mkdir(parents=True,exist_ok=True);args.out.write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result))


if __name__=='__main__':main()
