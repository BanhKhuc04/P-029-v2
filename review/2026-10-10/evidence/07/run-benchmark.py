import os
import sys,os,json,time,statistics,ctypes,hashlib,subprocess
from pathlib import Path
from dataclasses import replace
r=Path(__file__).resolve().parents[4]/"source-tool/pointsnap-3d";sys.path[:0]=[str(r),str(r/'.venv/Lib/site-packages')]
sys.stdout.reconfigure(encoding='utf-8')
from pointsnap.adapters.nuscenes import NuScenesReader
from pointsnap.adapters.cvat.reader import JobData
from pointsnap.core.config import load_config
from pointsnap.core.scanner import scan_cuboids
from pointsnap.core.model import add_track_markers
from pointsnap.report.html import generate_html_report
from pointsnap.report.csv_rep import generate_csv_report

class Memory(ctypes.Structure):
    _fields_=[('cb',ctypes.c_ulong),('PageFaultCount',ctypes.c_ulong),*[(n,ctypes.c_size_t) for n in ['PeakWorkingSetSize','WorkingSetSize','QuotaPeakPagedPoolUsage','QuotaPagedPoolUsage','QuotaPeakNonPagedPoolUsage','QuotaNonPagedPoolUsage','PagefileUsage','PeakPagefileUsage']]]
def peak_mb():
    m=Memory();m.cb=ctypes.sizeof(m)
    handle=ctypes.windll.kernel32.GetCurrentProcess
    handle.restype=ctypes.c_void_p
    if not ctypes.windll.psapi.GetProcessMemoryInfo(ctypes.c_void_p(handle()),ctypes.byref(m),ctypes.sizeof(m)): raise ctypes.WinError()
    return round(m.PeakWorkingSetSize/1048576,2)

out=r/'out/review07/benchmark';out.mkdir(parents=True,exist_ok=True)
cfg=load_config(env={});dataset=os.environ['NUSCENES_ROOT']
results=[]
for scene in ['scene-0757','scene-0061']:
    for sweeps in [0,cfg.floating.sweeps]:
        current=replace(cfg,floating=replace(cfg.floating,sweeps=sweeps))
        for repeat in range(3):
            reader=NuScenesReader(dataset)
            start=time.perf_counter();frames=reader.frames(scene);boxes=add_track_markers(reader.annotations(scene),frames.num_frames)
            metadata_seconds=time.perf_counter()-start
            start=time.perf_counter();point_count=sum(len(frames.frame_data(n).points) for n in frames.refs)
            lidar_read_seconds=time.perf_counter()-start
            cpu=time.process_time();start=time.perf_counter();findings=scan_cuboids(boxes,current,frames)
            scan_seconds=time.perf_counter()-start;cpu_seconds=time.process_time()-cpu
            job=JobData('',1,1,0,frames.num_frames-1,{},boxes)
            start=time.perf_counter();html=generate_html_report(job,findings,out/'report.html');csv=generate_csv_report(job,findings,out/'report.csv')
            row={'scene':scene,'sweeps':sweeps,'repeat':repeat,'cache':'first process scan' if repeat==0 else 'warm OS cache (reader recreated)',
                 'visible_boxes':sum(b.visible for b in boxes),'frames':frames.num_frames,'keyframe_points':point_count,
                 'metadata_seconds':metadata_seconds,'lidar_read_seconds':lidar_read_seconds,'scan_wall_seconds':scan_seconds,
                 'scan_cpu_seconds':cpu_seconds,'report_seconds':time.perf_counter()-start,'findings':len(findings),
                 'report_bytes':html.stat().st_size+csv.stat().st_size,'process_peak_working_set_mb':peak_mb()}
            results.append(row);(out/'measurements.json').write_text(json.dumps(results,indent=2),encoding='utf-8')
            print(f'{scene} sweeps{sweeps} #{repeat}: scan {scan_seconds:.2f}s peak {row["process_peak_working_set_mb"]}MiB',flush=True)
metadata={'source_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=r).decode().strip(),
          'python':sys.version.split()[0],'config_sha256':hashlib.sha256(json.dumps(cfg.to_dict(redact=True),sort_keys=True).encode()).hexdigest(),
          'condition':'Windows, same dataset/config except sweeps, sequential after eval; filesystem cache not flushed; scan includes frame I/O/sweeps, separately measured keyframe read pass is not subtracted',
          'ram':'GetProcessMemoryInfo PeakWorkingSetSize; cumulative process peak, not per-pass allocation; CPU process_time'}
(out/'metadata.json').write_text(json.dumps(metadata,indent=2),encoding='utf-8')
