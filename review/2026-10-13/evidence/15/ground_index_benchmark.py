"""Same-query index vs brute masking on one real frame; not a whole-app benchmark."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import time
import tracemalloc


def peak_rss_bytes():
    if sys.platform != 'win32':
        return None
    import ctypes
    from ctypes import wintypes
    class Counters(ctypes.Structure):
        _fields_ = [('cb',wintypes.DWORD),('PageFaultCount',wintypes.DWORD)] + [
            (name,ctypes.c_size_t) for name in ('PeakWorkingSetSize','WorkingSetSize','QuotaPeakPagedPoolUsage',
            'QuotaPagedPoolUsage','QuotaPeakNonPagedPoolUsage','QuotaNonPagedPoolUsage','PagefileUsage','PeakPagefileUsage')]
    counters=Counters(); counters.cb=ctypes.sizeof(counters)
    get_handle=ctypes.windll.kernel32.GetCurrentProcess; get_handle.restype=wintypes.HANDLE
    get_info=ctypes.windll.psapi.GetProcessMemoryInfo
    get_info.argtypes=[wintypes.HANDLE,ctypes.POINTER(Counters),wintypes.DWORD]
    if not get_info(get_handle(),ctypes.byref(counters),counters.cb):
        raise ctypes.WinError()
    return int(counters.PeakWorkingSetSize)


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--tool-root',required=True)
    p.add_argument('--out',required=True,type=Path)
    p.add_argument('--memory',action='store_true',help='Trace allocations; timing includes instrumentation overhead')
    args=p.parse_args()
    sys.path.insert(0,args.tool_root)
    import numpy as np
    from pointsnap.adapters.nuscenes.reader import NuScenesReader
    from pointsnap.core.geometry import points_in_cuboid
    from pointsnap.core.ground import OtherBoxPoints
    reader=NuScenesReader('D:/Vin_uni/data/nuscenes')
    points=reader.frames('scene-0061').frame_data(0).points[:,:3]
    boxes=[b for b in reader.annotations('scene-0061') if b.frame==0 and b.visible]
    rss_before=peak_rss_bytes()
    if args.memory:tracemalloc.start()
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
    traced_current,traced_peak=tracemalloc.get_traced_memory() if args.memory else (None,None)
    if args.memory:tracemalloc.stop()
    result={'model':'gpt-6.1-sol','scene':'scene-0061','frame':0,'points':len(points),'boxes':len(boxes),
            'queries':len(queries),'repeats':10,'all_point_sets_equal':True,'build_seconds':build,
            'timings_ms':{k:{'median':float(np.median(v)*1000),'p95':float(np.percentile(v,95)*1000)} for k,v in times.items()},
            'source_sha256':hashlib.sha256((Path(args.tool_root)/'pointsnap/core/ground.py').read_bytes()).hexdigest(),
            'memory':{'process_peak_rss_before_bytes':rss_before,'process_peak_rss_after_bytes':peak_rss_bytes(),
                      'traced_current_bytes':traced_current,'traced_peak_bytes':traced_peak,
                      'scope':'Process RSS includes imports and dataset reader; traced allocation around helper/query; not full-app RAM or minimum hardware'},
            'scope':'One frame/30 boxes; concurrent full evaluation; build cost reported separately; not minimum hardware or whole-app speed'}
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_bytes((json.dumps(result,indent=2)+'\n').encode())
    print(json.dumps(result))


if __name__=='__main__':main()
