"""Kiểm thử lớp 2 của Box Verifier: chiếu box 3D lên ảnh và các luật đối chiếu ảnh camera (việc C3).

Không cần PyTorch: model 2D được thay bằng bộ nhận diện giả trả sẵn khung vật.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pytest

from pointsnap.core.camera import CameraView, covered_fraction, iou_2d, project_box, project_points
from pointsnap.core.config import CameraConfig
from pointsnap.core.model import Cuboid, Severity
from pointsnap.detectors.camera import camera_findings, collect_observations
from pointsnap.vision.detector2d import MASK_SCALE, Detections

F, CX, CY, W, H = 1000.0, 800.0, 450.0, 1600, 900


def _view(channel="CAM_FRONT") -> CameraView:
    """Camera đặt ở gốc, nhìn theo trục +x của hệ toàn cục (x ảnh = -y, y ảnh = -z)."""
    cam_to_world = np.eye(4)
    cam_to_world[:3, :3] = np.array([[0.0, 0.0, 1.0], [-1.0, 0.0, 0.0], [0.0, -1.0, 0.0]])
    intrinsic = np.array([[F, 0.0, CX], [0.0, F, CY], [0.0, 0.0, 1.0]])
    return CameraView(channel, Path(f"{channel}.jpg"), intrinsic, cam_to_world, W, H)


def _car(frame=0, x=20.0, y=0.0, track_id=1, label="car", dims=(4.0, 2.0, 2.0)) -> Cuboid:
    return Cuboid(center=(x, y, 0.0), dims=dims, yaw=0.0, label=label, frame=frame, track_id=track_id)


def test_project_points_center_of_image():
    pixels, depth = project_points(np.array([[10.0, 0.0, 0.0], [10.0, -1.0, 0.0]]), _view())
    assert depth == pytest.approx([10.0, 10.0])
    assert pixels[0] == pytest.approx([CX, CY])
    assert pixels[1] == pytest.approx([CX + 100.0, CY])  # sang phải 1 m ở 10 m = 100 px


def test_project_box_extent_and_depth():
    proj = project_box(_car(), np.eye(4), _view())
    assert proj is not None
    x1, y1, x2, y2 = proj.box
    # mặt gần nhất ở x = 18 m, nửa rộng 1 m → 1000 / 18 ≈ 55.6 px mỗi bên
    assert (x2 - x1) / 2 == pytest.approx(F / 18.0, rel=1e-3)
    assert (x1 + x2) / 2 == pytest.approx(CX)
    assert proj.depth == pytest.approx(20.0)
    assert proj.inside_ratio == pytest.approx(1.0)


def test_project_box_behind_camera_or_outside_image():
    assert project_box(_car(x=-20.0), np.eye(4), _view()) is None
    assert project_box(_car(y=200.0), np.eye(4), _view()) is None  # rất xa về bên trái, ngoài ảnh
    partly = project_box(_car(x=10.0, y=8.5), np.eye(4), _view())
    assert partly is not None and partly.inside_ratio < 0.85


def test_iou_and_covered_fraction():
    assert iou_2d((0, 0, 10, 10), (0, 0, 10, 10)) == pytest.approx(1.0)
    assert iou_2d((0, 0, 10, 10), (5, 0, 15, 10)) == pytest.approx(50 / 150)
    assert iou_2d((0, 0, 10, 10), (20, 20, 30, 30)) == 0.0
    assert covered_fraction((0, 0, 10, 10), []) == 0.0
    assert covered_fraction((0, 0, 10, 10), [(-1, -1, 11, 11)]) == pytest.approx(1.0)
    assert 0.4 < covered_fraction((0, 0, 10, 10), [(0, 0, 5, 10)]) < 0.6


# --- Luật đối chiếu ảnh với bộ nhận diện giả -----------------------------------------------------------------


@dataclass
class _FrameData:
    points: np.ndarray
    sensor_to_world: np.ndarray


class _Frames:
    def __init__(self, num_frames: int):
        self.num_frames = num_frames

    def frame_data(self, frame: int) -> _FrameData:
        return _FrameData(np.zeros((0, 4)), np.eye(4))

    def camera_views(self, frame: int) -> list[CameraView]:
        return [_view()]


class _Detector:
    """Mỗi ảnh trả một vật: khung chiếu đúng của box chuẩn (lệch đi `offsets[frame]` pixel), nhóm `name`."""

    def __init__(self, truth: dict[int, Cuboid], offsets: dict[int, float] | None = None, name="car", score=0.95):
        self.truth, self.offsets, self.name, self.score = truth, offsets or {}, name, score
        self.frame = 0

    def detect(self, path) -> Detections:
        box = self.truth[self.frame]
        x1, y1, x2, y2 = project_box(box, np.eye(4), _view()).box
        dx = self.offsets.get(self.frame, 0.0)
        mask = np.zeros((H // MASK_SCALE, W // MASK_SCALE), dtype=bool)
        mask[int(y1 // MASK_SCALE) + 1:int(y2 // MASK_SCALE) - 1, int((x1 + dx) // MASK_SCALE) + 1:int((x2 + dx) // MASK_SCALE) - 1] = True
        return Detections(np.array([[x1 + dx, y1, x2 + dx, y2]]), np.array([self.score]), [self.name], [mask])


def _scan(boxes: list[Cuboid], detector: _Detector, cfg=CameraConfig()):
    """Chạy từng frame một để bộ nhận diện giả biết frame đang xét."""
    observations, missing = [], []
    for frame in sorted({b.frame for b in boxes}):
        detector.frame = frame
        obs, miss = collect_observations([b for b in boxes if b.frame == frame], _Frames(frame + 1), detector, cfg)
        observations += obs
        missing += miss
    return camera_findings(observations, cfg), missing


def _track(n=6, **kw) -> list[Cuboid]:
    return [_car(frame=f, x=15.0 + f, **kw) for f in range(n)]


def test_camera_clean_track_no_finding():
    boxes = _track()
    findings, missing = _scan(boxes, _Detector({b.frame: b for b in boxes}))
    assert findings == [] and missing == []


def test_camera_mismatch_when_box_shifted_from_object():
    truth = _track()
    labelled = list(truth)
    labelled[3] = truth[3].replace(center=(truth[3].center[0], truth[3].center[1] + 1.5, 0.0))  # dời 1.5 m sang trái
    findings, _ = _scan(labelled, _Detector({b.frame: b for b in truth}))
    hits = [f for f in findings if f.rule == "cam.mismatch"]
    assert [f.frame for f in hits] == [3]
    assert hits[0].severity is Severity.INFO  # mặc định là bằng chứng phụ
    warn, _ = _scan(labelled, _Detector({b.frame: b for b in truth}), CameraConfig(mismatch_severity="warning"))
    assert [f.severity for f in warn if f.rule == "cam.mismatch"] == [Severity.WARNING]
    assert hits[0].details["mask_outside"] > 0.2 + hits[0].details["track_median"]


def test_camera_no_mismatch_when_detector_misses_object():
    """Model 2D không thấy vật ở một frame (xa, mờ, bị che): không có bằng chứng box sai, không báo."""
    boxes = _track()

    class _Missing(_Detector):
        def detect(self, path):
            if self.frame == 3:
                return Detections(np.zeros((0, 4)), np.zeros(0), [], [])
            return super().detect(path)

    findings, _ = _scan(boxes, _Missing({b.frame: b for b in boxes}))
    assert [f for f in findings if f.rule == "cam.mismatch"] == []


def test_camera_class_vote():
    boxes = _track()
    findings, _ = _scan(boxes, _Detector({b.frame: b for b in boxes}, name="person"))
    hits = [f for f in findings if f.rule == "cam.class"]
    assert len(hits) == 1 and hits[0].details["camera_group"] == "person"


def test_camera_missing_object_needs_lidar_points():
    """Ảnh thấy xe mà không có box 3D: cần điểm LiDAR trong khung ảnh mới báo `cam.missing`."""
    ghost = _car(x=20.0)
    det = _Detector({0: ghost})
    other = _car(x=20.0, y=-12.0, track_id=2)  # box khác, không chiếu trùng vật

    obs, missing = collect_observations([other], _Frames(1), det, CameraConfig())
    assert missing == []  # không có điểm LiDAR

    class _WithPoints(_Frames):
        def frame_data(self, frame):
            ys, zs = np.meshgrid(np.linspace(-0.9, 0.9, 6), np.linspace(-0.9, 0.9, 5))
            pts = np.column_stack([np.full(ys.size, 19.0), ys.ravel(), zs.ravel(), np.zeros(ys.size)])
            return _FrameData(pts, np.eye(4))

    _, missing = collect_observations([other], _WithPoints(1), det, CameraConfig())
    assert len(missing) == 1 and missing[0].rule == "cam.missing" and missing[0].severity is Severity.INFO


def test_camera_skips_dark_images():
    """Ảnh đêm (tối hơn `min_brightness`): model COCO kém tin cậy, không xét luật ảnh nào."""
    truth = _track()
    labelled = list(truth)
    labelled[3] = truth[3].replace(center=(truth[3].center[0], truth[3].center[1] + 1.5, 0.0))

    class _Dark(_Detector):
        def detect(self, path):
            import dataclasses

            return dataclasses.replace(super().detect(path), brightness=30.0)

    findings, missing = _scan(labelled, _Dark({b.frame: b for b in truth}))
    assert findings == [] and missing == []


def test_camera_class_ignores_rider_on_two_wheeler():
    """Xe đạp có người ngồi: ảnh nhận là người, không coi là sai class."""
    boxes = _track(label="bicycle", dims=(1.8, 0.6, 1.7))
    findings, _ = _scan(boxes, _Detector({b.frame: b for b in boxes}, name="person"))
    assert [f for f in findings if f.rule == "cam.class"] == []


# --- Model ảnh theo từ khóa (Grounding DINO + SAM 2.1) ------------------------------------------------------


def test_group_of_name_maps_coco_and_prompt_names():
    from pointsnap.vision.detector2d import group_of_name

    assert group_of_name("truck") == "vehicle"
    assert group_of_name("traffic cone") == "traffic_cone"
    assert group_of_name("construction vehicle") == "vehicle"
    assert group_of_name("car truck") == "vehicle"  # Grounding DINO ghép hai từ khóa liền nhau
    assert group_of_name("barrier traffic cone") == "barrier"  # lấy từ khóa đứng đầu
    assert group_of_name("construction") == "vehicle"  # mảnh của "construction vehicle"
    assert group_of_name("traffic light") is None
    assert group_of_name("traffic") is None
    assert group_of_name("") is None


def test_detector_model_choice_and_cache_key(tmp_path):
    import hashlib

    from pointsnap.vision.detector2d import MODEL_NAME, Detector2D

    with pytest.raises(ValueError):
        Detector2D(cache_dir=tmp_path, model="yolo")
    image = tmp_path / "a.jpg"
    image.write_bytes(b"x")
    old = Detector2D(cache_dir=tmp_path)
    new = Detector2D(cache_dir=tmp_path, model="gdino-sam2")
    stat = image.stat()
    raw = f"{MODEL_NAME}|{image.resolve()}|{stat.st_size}|{int(stat.st_mtime)}|0.3"
    assert old._key(image).name == f"{hashlib.sha1(raw.encode('utf-8')).hexdigest()}.npz"  # dùng lại bộ đệm cũ
    assert new._key(image) != old._key(image)
    assert {"traffic_cone", "barrier"} <= new.supported_groups
    assert "traffic_cone" not in old.supported_groups


def test_camera_skips_groups_the_model_cannot_see():
    """Mask R-CNN COCO không có cọc tiêu: box cọc tiêu không được đối chiếu (không có bằng chứng), kể cả khi ảnh có
    vật khác trùng khung."""
    cone = [_car(frame=f, x=15.0 + f, label="traffic_cone", dims=(0.4, 0.4, 0.8)) for f in range(4)]

    class _Coco(_Detector):
        supported_groups = frozenset({"person", "two_wheeler", "vehicle", "animal"})

    class _Open(_Detector):
        supported_groups = frozenset({"person", "two_wheeler", "vehicle", "animal", "traffic_cone", "barrier"})

    truth = {b.frame: b for b in cone}
    coco_obs = []
    open_obs = []
    for frame in truth:
        for cls, sink in ((_Coco, coco_obs), (_Open, open_obs)):
            det = cls(truth, name="traffic cone")
            det.frame = frame
            obs, _ = collect_observations([truth[frame]], _Frames(frame + 1), det, CameraConfig())
            sink += obs
    assert coco_obs == []
    assert len(open_obs) == 4 and all(o.iou > 0.5 for o in open_obs)
