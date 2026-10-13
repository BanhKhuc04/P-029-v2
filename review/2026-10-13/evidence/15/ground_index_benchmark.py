"""Same-query index vs brute masking on one real frame; not a whole-app benchmark."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import time


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--tool-root',required=True)
    p.add_argument('--out',required=True,type=Path)
    args=p.parse_args()
    sys.path.insert(0,args.tool_root)
    import numpy as np
    from pointsnap.adapters.nuscenes.reader import NuScenesReader
    from pointsnap.core.geometry import points_in_cuboid
    from pointsnap.core.ground import OtherBoxPoints
    reader=NuScenesReader('D:/Vin_uni/data/nuscenes')
    points=reader.frames('scene-0061').frame_data(0).points[:,:3]
    boxes=[b for b in reader.annotations('scene-0061') if b.frame==0 and b.visible]
    start=time.perf_counter();index=OtherBoxPoints(points,boxes);build=time.perf_counter()-start
    def brute(i,reach):
        b=boxes[i]
        near=points[(np.abs(points[:,0]-b.center[0])<=reach)&(np.abs(points[:,1]-b.center[1])<=reach)]
        keep=np.ones(len(near),dtype=bool)
        for j,other in enumerate(boxes):
            if i!=j:keep &= ~points_in_cuboid(near,other,margin=.15)
        return near[keep]
    times={'brute':[],'index':[]}
    queries=[(i,float(np.hypot(b.length/2+.8,b.width/2+.8))) for i,b in enumerate(boxes[:30])]
    for i,reach in queries:
        assert np.array_equal(brute(i,reach),index.without_others(i,reach=reach))
    for _ in range(10):
        for i,reach in queries:
            for name,fn in [('brute',brute),('index',lambda i,r:index.without_others(i,reach=r))]:
                start=time.perf_counter();fn(i,reach);times[name].append(time.perf_counter()-start)
    result={'model':'gpt-6.1-sol','scene':'scene-0061','frame':0,'points':len(points),'boxes':len(boxes),
            'queries':len(queries),'repeats':10,'all_point_sets_equal':True,'build_seconds':build,
            'timings_ms':{k:{'median':float(np.median(v)*1000),'p95':float(np.percentile(v,95)*1000)} for k,v in times.items()},
            'source_sha256':hashlib.sha256((Path(args.tool_root)/'pointsnap/core/ground.py').read_bytes()).hexdigest(),
            'scope':'One frame/30 boxes; concurrent full evaluation; build cost reported separately; not minimum hardware or whole-app speed'}
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_bytes((json.dumps(result,indent=2)+'\n').encode())
    print(json.dumps(result))


if __name__=='__main__':main()
