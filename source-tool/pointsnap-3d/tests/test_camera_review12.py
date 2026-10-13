"""Camera review: independent geometry, evidence boundaries and cache recovery."""
import dataclasses
import math
import os
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pytest

from pointsnap.core.camera import CameraView, covered_fraction, project_box
from pointsnap.core.config import CameraConfig, GateConfig, load_config
from pointsnap.core.gate import gate_verdict
from pointsnap.core.model import FrameData, Severity
from pointsnap.core.scanner import check_camera, scan_coverage_gaps
from pointsnap.detectors.camera import Observation, camera_findings, collect_observations, sparse_unconfirmed
from pointsnap.vision import detector2d
from pointsnap.vision.detector2d import Detections, Detector2D
from test_camera import _car, _view, _Frames, _FrameData
from test_gate_coverage import job_data


def empty():
    return Detections(np.empty((0, 4)), np.empty(0), [], [], 120)


def observation(frame, channel="front", outside=.1, label="car", other="vehicle", keyframe=True):
    return Observation(_car(frame=frame, track_id=0, label=label).replace(keyframe=keyframe), channel,
                       .8, True, outside, other, .95)


def test_camera_reference_stays_in_same_channel():
    rows = [observation(f, channel, out) for f in range(5) for channel,out in [("front",.1),("side",.8)]]
    assert camera_findings(rows, CameraConfig(), wrong_class=False) == []
    rows[4] = observation(2, "front", .6)
    hits = camera_findings(rows, CameraConfig(), wrong_class=False)
    assert [(f.frame,f.details["camera"]) for f in hits] == [(2,"front")]


def test_camera_reference_requires_independent_frames():
    rows = [observation(0, outside=.7), observation(1), observation(1)]
    assert camera_findings(rows, CameraConfig(), wrong_class=False) == []


def test_camera_does_not_mix_classes_with_same_track_id():
    rows = [observation(f) for f in range(3)] + [observation(f, outside=.7,label="truck") for f in range(3,6)]
    assert camera_findings(rows, CameraConfig(), wrong_class=False) == []


def test_camera_does_not_use_interpolated_evidence():
    rows = [observation(0,outside=.7),observation(1,keyframe=False),observation(2,keyframe=False)]
    assert camera_findings(rows, CameraConfig(), wrong_class=False) == []


def test_class_vote_needs_one_consistent_alternative_group():
    rows = [observation(i,other=g) for i,g in enumerate(["person","person","animal","animal","vehicle"])]
    assert camera_findings(rows,CameraConfig(),mismatch=False) == []


def test_class_vote_counts_frames_and_not_three_views_of_one_frame():
    rows = [observation(0,channel=c,other="animal") for c in ("front","left","right")]
    assert camera_findings(rows,CameraConfig(),mismatch=False) == []


@pytest.mark.parametrize("fraction", [.29,.49,.51])
def test_occlusion_area_is_exact_at_thresholds(fraction):
    assert covered_fraction((0,0,100,100),[(0,0,100*fraction,100)]) == pytest.approx(fraction)


def test_occlusion_union_does_not_double_count_or_include_zero_area():
    assert covered_fraction((0,0,10,10),[(0,0,6,10),(4,0,8,10)]) == pytest.approx(.8)
    assert covered_fraction((0,0,10,10),[(0,0,0,10)]) == 0


@pytest.mark.parametrize("change", [
    {"width":0}, {"height":-1}, {"intrinsic":np.eye(2)},
    {"intrinsic":np.full((3,3),np.nan)}, {"camera_to_world":np.diag([2,1,1,1])},
])
def test_camera_calibration_rejects_invalid_values(change):
    with pytest.raises(ValueError):
        dataclasses.replace(_view(),**change)


def test_projection_rejects_non_rigid_lidar_pose():
    with pytest.raises(ValueError):
        project_box(_car(),np.diag([2,1,1,1]),_view())


@pytest.mark.parametrize("name", ["scarf", "carpet", "barrierless"])
def test_group_name_requires_token_boundaries(name):
    assert detector2d.group_of_name(name) is None


def test_group_name_normalizes_case_and_spacing():
    assert detector2d.group_of_name("  TRAFFIC CONE  ") == "traffic_cone"


def image(path):
    from PIL import Image
    Image.new("RGB",(8,8),(120,120,120)).save(path)
    return path


def test_cache_changes_on_subsecond_image_replacement(tmp_path):
    path=tmp_path/'image.jpg';path.write_bytes(b'x')
    det=Detector2D(cache_dir=tmp_path/'cache')
    os.utime(path,ns=(4_000_000_000,4_000_000_000));first=det._key(path)
    os.utime(path,ns=(4_100_000_000,4_100_000_000))
    assert det._key(path) != first


def test_cache_changes_on_prompt_mapping_and_mask_algorithm(tmp_path,monkeypatch):
    path=tmp_path/'image.jpg';path.write_bytes(b'x')
    det=Detector2D(cache_dir=tmp_path/'cache',model="gdino-sam2")
    first=det._key(path)
    monkeypatch.setitem(detector2d.PROMPTS,"car","new-group")
    assert det._key(path) != first
    first=det._key(path)
    monkeypatch.setattr(detector2d,"MASK_SCALE",8)
    assert det._key(path) != first


@pytest.mark.parametrize("payload", [b'not a zip', None])
def test_corrupt_cache_recomputes_without_accepting_invalid_findings(tmp_path,monkeypatch,payload):
    path=image(tmp_path/'image.png');det=Detector2D(cache_dir=tmp_path/'cache')
    cache=det._key(path)
    if payload is None:
        np.savez(cache,boxes=np.zeros((1,4)),scores=np.array([np.nan]),names=np.array(['car']),
                 masks=np.empty((0,0),np.uint8),shape=np.array([0,0]))
    else: cache.write_bytes(payload)
    calls=[]
    monkeypatch.setattr(det,"_run",lambda _:calls.append(1) or empty())
    assert det.detect(path).names == []
    assert det.detect(path).names == []
    assert calls == [1]


def test_cache_failure_keeps_previous_file_intact(tmp_path,monkeypatch):
    path=tmp_path/'cache.npz';detector2d._save(path,empty());before=path.read_bytes()
    def fail(target,**kwargs):
        if hasattr(target,'write'):target.write(b'partial')
        else:Path(target).write_bytes(b'partial')
        raise OSError('disk failure')
    monkeypatch.setattr(detector2d.np,'savez_compressed',fail)
    with pytest.raises(OSError):detector2d._save(path,empty())
    assert path.read_bytes() == before
    assert not list(tmp_path.glob('*.tmp'))


@pytest.mark.parametrize("change", [
    {"scores":np.array([.9,.8])}, {"boxes":np.array([[0,0,np.nan,1]])},
    {"boxes":np.array([[3,0,1,1]])}, {"scores":np.array([2.0])},
    {"names":[]}, {"masks":[np.ones((1,1)),np.ones((1,1))]},
])
def test_detections_validate_tensor_alignment_and_finiteness(change):
    args=dict(boxes=np.array([[0,0,1,1]]),scores=np.array([.9]),names=['car'],masks=[])
    with pytest.raises(ValueError):Detections(**{**args,**change})


def test_sparse_ignores_unsupported_groups():
    class Coco:
        supported_groups=frozenset({'person','vehicle','two_wheeler','animal'})
        def detect(self,path):return empty()
    cone=_car(label='traffic_cone',dims=(.4,.4,.8))
    assert sparse_unconfirmed([cone],_Frames(1),Coco(),CameraConfig()) == []


def test_sparse_counts_rotated_box_corner_points():
    class Nothing:
        def detect(self,path):return empty()
    box=_car().replace(yaw=math.pi/4)
    c,s=math.cos(box.yaw),math.sin(box.yaw)
    points=np.tile((box.center[0]+c*1.99-s*.99,box.center[1]+s*1.99+c*.99,0),(6,1))
    class Frames(_Frames):
        def frame_data(self,frame):return _FrameData(points,np.eye(4))
    assert sparse_unconfirmed([box],Frames(1),Nothing(),CameraConfig()) == []


def test_sparse_does_not_take_dense_interpolation_as_manual_evidence():
    class Nothing:
        def detect(self,path):return empty()
    boxes=[_car(frame=0),_car(frame=1).replace(keyframe=False)]
    class Frames(_Frames):
        def frame_data(self,frame):
            return _FrameData(np.empty((0,3)) if frame==0 else np.tile((20,0,0),(6,1)),np.eye(4))
    found=sparse_unconfirmed(boxes,Frames(2),Nothing(),CameraConfig())
    assert len(found)==1 and found[0].details['frames']==[0]


def test_dark_view_is_not_evidence_when_other_views_are_bright():
    class Frames(_Frames):
        def camera_views(self,frame):return [_view('dark'),_view('bright1'),_view('bright2')]
    class Detector:
        def detect(self,path):
            if path.stem!='dark':return empty()
            return Detections(np.array([[700,350,900,550]]),np.array([.99]),['person'],[],10)
    obs,_=collect_observations([_car()],Frames(1),Detector(),CameraConfig())
    assert {o.channel for o in obs} == {'bright1','bright2'}


def camera_only():
    cfg=load_config(env={})
    return dataclasses.replace(cfg,camera=CameraConfig(enabled='true'),rules=dataclasses.replace(cfg.rules,**{
        f.name:f.name=='cam_class' for f in dataclasses.fields(cfg.rules)}))


def test_explicit_camera_missing_runtime_cannot_pass_gate(monkeypatch):
    monkeypatch.setattr(detector2d,'available',lambda model='maskrcnn':False)
    cfg=camera_only();gaps=scan_coverage_gaps(job_data(),cfg,None)
    assert gaps and not gate_verdict([],cfg.gate,coverage_gaps=gaps)[0]


def test_weight_or_image_failure_preserves_scan_and_marks_partial(monkeypatch):
    class Broken:
        def detect(self,path):raise OSError('weights unavailable offline')
    monkeypatch.setattr(detector2d,'available',lambda model='maskrcnn':True)
    monkeypatch.setattr('pointsnap.core.scanner._detector',lambda model:Broken())
    found=check_camera(dataclasses.replace(job_data(),cuboids=[_car()]),camera_only(),_Frames(1))
    assert len(found)==1 and found[0].rule=='camera.no_evidence' and found[0].severity is Severity.INFO
    assert not gate_verdict(found,GateConfig(0,0))[0]


def test_mask_shrink_preserves_partial_edge_blocks():
    torch=pytest.importorskip('torch')
    masks=torch.zeros(1,5,5,dtype=torch.bool);masks[:,4,4]=True
    [small]=detector2d._shrink(masks)
    assert small.shape==(2,2) and small[1,1]


def test_mask_outside_uses_partial_cell_center_at_image_edge():
    from pointsnap.detectors.camera import _mask_outside
    mask=np.ones((5,5),dtype=bool)
    polygon=np.array([[0,0],[17,0],[17,17],[0,17]],float)
    assert _mask_outside(mask,polygon,image_size=(17,17)) == 0


def test_camera_dataset_path_cannot_escape_root(tmp_path):
    from pointsnap.adapters.nuscenes.reader import NuScenesReader
    from types import SimpleNamespace
    root=tmp_path/'dataset';root.mkdir();(tmp_path/'escape.jpg').write_bytes(b'x')
    reader=NuScenesReader.__new__(NuScenesReader);reader.dataroot=root.resolve()
    reader._tables={'sensor':{},'calibrated_sensor':{}}
    reader.__dict__['_camera_records_by_sample']={'sample':[{'filename':'../escape.jpg'}]}
    with pytest.raises(ValueError,match='dataroot'):
        reader.camera_views(SimpleNamespace(sample_token='sample'))


def test_camera_evaluation_uses_same_channel_reference():
    import importlib.util
    path=Path(__file__).parents[1]/'scripts/eval_camera.py'
    spec=importlib.util.spec_from_file_location('review12_eval',path);module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    refs=[observation(f,c,out) for f in range(5) for c,out in [('front',.1),('side',.8)]]
    assert module._rises([observation(0,'side',.8)],refs,0,2) == pytest.approx([0])


def test_hybrid_runtime_fallback_preserves_coco_and_reduces_capabilities(tmp_path,monkeypatch):
    det=Detector2D(cache_dir=tmp_path/'cache',model='hybrid')
    coco=Detections(np.array([[0,0,1,1]]),np.array([.9]),['car'],[],120)
    monkeypatch.setattr(det._parts[0],'detect',lambda _:coco)
    calls=[]
    def fail(_):calls.append(1);raise OSError('extra weights unavailable')
    monkeypatch.setattr(det._parts[1],'detect',fail)
    assert det.detect('a') is coco
    assert det.detect('b') is coco
    assert det.supported_groups == detector2d.SUPPORTED_GROUPS['maskrcnn']
    assert det.fallback_reason and calls==[1]


@pytest.mark.parametrize('model',['maskrcnn','gdino-sam2','hybrid'])
def test_effective_model_is_used_by_camera_sparse_and_missing(model,monkeypatch):
    from pointsnap.core.scanner import check_missing
    monkeypatch.setattr(detector2d,'available',lambda model='maskrcnn':True)
    sentinel=object();calls=[]
    def factory(name):calls.append(name);return sentinel
    monkeypatch.setattr('pointsnap.core.scanner._detector',factory)
    seen=[]
    monkeypatch.setattr('pointsnap.detectors.camera.collect_observations',lambda boxes,frames,d,cfg:seen.append(d) or ([],[]))
    monkeypatch.setattr('pointsnap.detectors.camera.sparse_unconfirmed',lambda boxes,frames,d,cfg:seen.append(d) or [])
    monkeypatch.setattr('pointsnap.detectors.missing.detect_missing_objects',lambda boxes,frames,cfg,d,ccfg:seen.append(d) or ([],[]))
    cfg=dataclasses.replace(load_config(env={}),camera=CameraConfig(enabled='true',model=model))
    check_camera(job_data(),cfg,_Frames(1));check_missing(job_data(),cfg,_Frames(1))
    assert all(d is sentinel for d in seen) and len(seen)==3
    assert calls and set(calls)=={model}


@pytest.mark.parametrize('factory_failure',[False,True])
def test_missing_lidar_keeps_moving_results_when_camera_fails(monkeypatch,factory_failure):
    from pointsnap.core.scanner import check_missing
    from pointsnap.core.model import Finding,ErrorType
    detector=object();monkeypatch.setattr(detector2d,'available',lambda model='maskrcnn':True)
    def factory(_):
        if factory_failure:raise OSError('cache directory is unwritable')
        return detector
    monkeypatch.setattr('pointsnap.core.scanner._detector',factory)
    finding=Finding(ErrorType.FIT,'lidar.missing',Severity.WARNING,0,'person','moving cluster')
    def detect(boxes,frames,cfg,d,ccfg):
        if d is detector:raise OSError('camera offline')
        return [finding],[]
    monkeypatch.setattr('pointsnap.detectors.missing.detect_missing_objects',detect)
    found=check_missing(job_data(),camera_only(),_Frames(1))
    assert finding in found and any(f.rule=='camera.no_evidence' for f in found)


def test_available_catches_broken_optional_native_runtime(monkeypatch):
    import builtins
    original=builtins.__import__
    def broken(name,*args,**kwargs):
        if name=='torchvision':raise OSError('native DLL missing')
        return original(name,*args,**kwargs)
    monkeypatch.setattr(builtins,'__import__',broken)
    assert not detector2d.available('maskrcnn')


def test_sparse_updates_supported_groups_after_hybrid_fallback():
    class Fallback:
        supported_groups=detector2d.SUPPORTED_GROUPS['hybrid']
        def detect(self,path):
            self.supported_groups=detector2d.SUPPORTED_GROUPS['maskrcnn']
            return empty()
    assert sparse_unconfirmed([_car(label='traffic_cone')],_Frames(1),Fallback(),CameraConfig()) == []


def test_invalid_model_outputs_are_reported_as_partial_camera_scan(tmp_path,monkeypatch):
    path=image(tmp_path/'image.png');det=Detector2D(cache_dir=tmp_path/'cache')
    monkeypatch.setattr(det,'_run',lambda _:Detections(np.ones((1,4)),np.array([np.nan]),['car'],[]))
    monkeypatch.setattr(detector2d,'available',lambda model='maskrcnn':True)
    monkeypatch.setattr('pointsnap.core.scanner._detector',lambda _:det)
    class Frames(_Frames):
        def camera_views(self,frame):return [dataclasses.replace(_view(),path=path)]
    found=check_camera(dataclasses.replace(job_data(),cuboids=[_car()]),camera_only(),Frames(1))
    assert len(found)==1 and found[0].rule=='camera.no_evidence'


@pytest.mark.parametrize('model',['maskrcnn','gdino-sam2','hybrid'])
def test_camera_cold_and_hot_cache_agree(tmp_path,monkeypatch,model):
    path=image(tmp_path/'image.png');det=Detector2D(cache_dir=tmp_path/'cache',model=model)
    if model=='hybrid':
        for part in det._parts:monkeypatch.setattr(part,'_run',lambda _:empty())
    else:monkeypatch.setattr(det,'_run',lambda _:empty())
    first=det.detect(path);second=det.detect(path)
    assert first.names==second.names
    np.testing.assert_array_equal(first.boxes,second.boxes)
    assert first.brightness==second.brightness==120


def test_grounded_sam_cpu_batch_contract_without_cuda_autocast(monkeypatch):
    torch=pytest.importorskip('torch')
    from types import SimpleNamespace
    from PIL import Image
    engine=detector2d._GroundedSam2.__new__(detector2d._GroundedSam2)
    engine.device='cpu';engine.min_score=.2;engine.text='car.'
    class Inputs(dict):
        def to(self,device):return self
        @property
        def input_ids(self):return self['input_ids']
    class Dino:
        def __call__(self,**kwargs):return None
    class DinoProcessor:
        def __call__(self,**kwargs):return Inputs(input_ids=torch.ones((1,1),dtype=torch.long))
        def post_process_grounded_object_detection(self,*args,**kwargs):
            assert kwargs['target_sizes']==[(8,8)]
            return [{'boxes':torch.tensor([[0.,0.,8.,8.]]*33),'scores':torch.full((33,),.9),
                     'text_labels':['car']*33}]
    counts=[]
    class SamProcessor:
        def __call__(self,images,input_boxes,return_tensors):
            counts.append(len(input_boxes[0]));return Inputs(pixel_values=torch.zeros(1,3,8,8),
                                                          original_sizes=torch.tensor([[8,8]]),count=len(input_boxes[0]))
        def post_process_masks(self,pred,sizes):return [pred[0]]
    class Sam:
        def __call__(self,count,**kwargs):return SimpleNamespace(pred_masks=torch.ones(1,count,1,8,8))
    engine.gdino_proc=DinoProcessor();engine.gdino=Dino();engine.sam_proc=SamProcessor();engine.sam=Sam()
    monkeypatch.setattr(torch,'autocast',lambda *args,**kwargs:pytest.fail('CPU used CUDA autocast'))
    result=engine(Image.new('RGB',(8,8)))
    assert counts==[32,1] and result.boxes.shape==(33,4) and len(result.masks)==33
    assert result.image_size==(8,8) and all(m.shape==(2,2) for m in result.masks)


def test_camera_factory_failure_is_partial_not_a_scan_crash(monkeypatch):
    monkeypatch.setattr(detector2d,'available',lambda model='maskrcnn':True)
    def fail(_):raise OSError('cache directory is unwritable')
    monkeypatch.setattr('pointsnap.core.scanner._detector',fail)
    found=check_camera(job_data(),camera_only(),_Frames(1))
    assert len(found)==1 and found[0].rule=='camera.no_evidence'


def test_atomic_storage_handles_transient_windows_replace_denial(tmp_path,monkeypatch):
    from pointsnap.web import storage
    target=tmp_path/'state.json';storage.write_json(target,{'old':1})
    replace=storage.os.replace;attempts=[]
    def transient(source,destination):
        attempts.append(1)
        if len(attempts)<3:
            exc=PermissionError('Windows transient replace denial');exc.winerror=5;raise exc
        return replace(source,destination)
    monkeypatch.setattr(storage.os,'replace',transient)
    storage.write_json(target,{'new':2})
    assert storage.read_json(target)=={'new':2} and len(attempts)==3
    assert not list(tmp_path.glob('.ps-*.tmp'))


def test_atomic_storage_bounds_retry_and_preserves_old_file(tmp_path,monkeypatch):
    from pointsnap.web import storage
    target=tmp_path/'state.json';storage.write_json(target,{'old':1})
    before=target.read_bytes();attempts=[]
    def denied(source,destination):
        attempts.append(1);exc=PermissionError('Persistent Windows denial');exc.winerror=5;raise exc
    monkeypatch.setattr(storage.os,'replace',denied)
    with pytest.raises(PermissionError):storage.write_json(target,{'new':2})
    assert len(attempts)==4 and target.read_bytes()==before
    assert not list(tmp_path.glob('.ps-*.tmp'))


def test_grounded_processors_pin_revision_and_use_supported_fast_mode(monkeypatch):
    pytest.importorskip('transformers')
    import sys,types
    calls=[]
    class Processor:
        @classmethod
        def from_pretrained(cls,name,**kwargs):
            calls.append((name,kwargs))
            assert kwargs['revision'] in (detector2d.GDINO_REVISION,detector2d.SAM2_REVISION)
            if name==detector2d.SAM2_ID:assert kwargs.get('use_fast') is True
            return object()
    class Model:
        @classmethod
        def from_pretrained(cls,name,**kwargs):
            assert kwargs['use_safetensors'] is True
            assert kwargs['revision'] in (detector2d.GDINO_REVISION,detector2d.SAM2_REVISION)
            return cls()
        def to(self,device):return self
        def eval(self):return self
    # Replace the import boundary: lazy model imports can overwrite individual patched attributes.
    fake=types.ModuleType('transformers')
    for name in ('AutoProcessor','Sam2Processor'):setattr(fake,name,Processor)
    for name in ('AutoModelForZeroShotObjectDetection','Sam2Model'):setattr(fake,name,Model)
    monkeypatch.setitem(sys.modules,'transformers',fake)
    detector2d._GroundedSam2('cpu',.2)
    assert len(calls)==2
