"""Sót đối tượng bằng LiDAR (việc C7): cụm điểm di chuyển mà không có box."""

from __future__ import annotations

import math

from pointsnap.core.config import load_config
from pointsnap.detectors.missing import _kind, detect_missing_objects
from scenario_sim import Obj, Scene, SimFrames, labels, parked, straight

CAR = (4.5, 1.9, 1.6)
PED = (0.6, 0.6, 1.75)


def _unlabelled(scene: Scene, *track_ids: int):
    """Nhãn của cảnh nhưng bỏ hẳn các track `track_ids` (người gán quên vẽ)."""
    return [b for b in labels(scene) if b.track_id not in track_ids]


def _missing(scene, boxes):
    return detect_missing_objects(boxes, SimFrames(scene), load_config(None).missing)[0]


def test_unlabelled_moving_car_is_found():
    scene = Scene([Obj(1, "car", CAR, straight(-10, 5, 0, 8)), Obj(2, "car", CAR, parked(12, -5, 0.3))])
    found = _missing(scene, _unlabelled(scene, 1))
    assert len(found) == 1
    f = found[0]
    assert f.rule == "lidar.missing" and f.label == "xe" and f.severity.value == "warning"
    assert len(f.details["frames"]) >= 3 and f.source_id is None


def test_unlabelled_walking_person_is_found():
    scene = Scene([Obj(1, "pedestrian", PED, straight(5, 6, 0.3, 1.3))], num_frames=12)
    found = _missing(scene, _unlabelled(scene, 1))
    assert [f.label for f in found] == ["người"]


def test_clean_labels_and_static_unlabelled_objects_are_quiet():
    scene = Scene([Obj(1, "car", CAR, straight(-10, 5, 0, 8)), Obj(2, "car", CAR, parked(12, -5, 0.3)),
                   Obj(3, "pedestrian", PED, straight(5, 8, 1.2, 1.3))])
    assert _missing(scene, labels(scene)) == []
    # Xe đỗ không gán (có thể là vật ngoài phạm vi gán nhãn): đứng yên nên không báo
    assert _missing(scene, _unlabelled(scene, 2)) == []


def test_static_object_seen_from_moving_ego_is_quiet():
    """Xe thu chạy, vật đứng yên không gán: phần nhìn thấy đổi theo góc nhìn nhưng chỗ đứng vẫn bị chiếm."""
    scene = Scene([Obj(1, "car", CAR, parked(15, 6, 0.4)), Obj(2, "car", CAR, parked(25, -6, 1.2))],
                  ego=lambda t: (5 * t, 0.0, 0.0))
    assert _missing(scene, []) == []


def test_heavy_rain_is_quiet():
    scene = Scene([Obj(1, "car", CAR, straight(-10, 4, 0, 10))], rain=10000)
    assert _missing(scene, labels(scene)) == []


def test_kind_by_size():
    assert _kind(0.6, 0.4, 1.7) == "người"
    assert _kind(1.9, 0.7, 1.5) == "xe hai bánh"
    assert _kind(4.4, 0.3, 1.4) == "xe"  # chỉ thấy hông xe
    assert _kind(12.0, 0.5, 3.2) == "xe dài"
    assert _kind(2.5, 1.0, 3.2) is None  # ngắn mà cao: tán cây, biển báo
    assert _kind(25.0, 0.4, 2.0) is None  # tường dài
    assert math.isclose(load_config(None).missing.min_points_per_cell, 1.2)


# --- Vật đứng yên: LiDAR + ảnh camera -------------------------------------------------------------------------

import numpy as np  # noqa: E402

from pointsnap.core.camera import CameraView, project_box  # noqa: E402
from pointsnap.vision.detector2d import Detections  # noqa: E402


def _front_camera() -> CameraView:
    """Camera nhìn theo +x của hệ toàn cục, đặt ở (0, 0, 1,8) — trùng chỗ cảm biến khi xe thu đứng yên ở gốc."""
    m = np.eye(4)
    m[:3, :3] = np.array([[0.0, 0.0, 1.0], [-1.0, 0.0, 0.0], [0.0, -1.0, 0.0]])
    m[:3, 3] = [0.0, 0.0, 1.8]
    k = np.array([[1000.0, 0.0, 800.0], [0.0, 1000.0, 450.0], [0.0, 0.0, 1.0]])
    return CameraView("CAM_FRONT", __import__("pathlib").Path("cam.jpg"), k, m, 1600, 900)


class _CamFrames(SimFrames):
    def camera_views(self, frame):
        return [_front_camera()]


class _FakeDetector:
    """Trả sẵn một vật (tên `name`) trùng khung chiếu của box thật `truth` ở mọi ảnh."""

    def __init__(self, scene, truth_track: int, name: str):
        self.box = None
        self.name = name
        frames = _CamFrames(scene)
        truth = next(b for b in labels(scene) if b.track_id == truth_track and b.frame == 0)
        proj = project_box(truth, frames.frame_data(0).sensor_to_world, _front_camera())
        self.box = np.array([proj.box])

    def detect(self, path):
        if self.name is None:
            return Detections(np.zeros((0, 4)), np.zeros(0), [], [])
        return Detections(self.box, np.array([0.98]), [self.name], [])


def _static_missing(scene, boxes, detector):
    cfg = load_config(None)
    found = detect_missing_objects(boxes, _CamFrames(scene), cfg.missing, detector, cfg.camera)[0]
    return [f for f in found if not f.details["moving"]]


def _parked_scene():
    return Scene([Obj(1, "car", CAR, parked(15, 0.5, 0.0)), Obj(2, "car", CAR, parked(14, -8, 0.2))], num_frames=8)


def test_static_unlabelled_car_confirmed_by_camera():
    scene = _parked_scene()
    found = _static_missing(scene, _unlabelled(scene, 1), _FakeDetector(scene, 1, "car"))
    assert len(found) == 1
    f = found[0]
    assert f.rule == "lidar.missing" and f.label == "xe" and f.details["camera_class"] == "car"
    assert len(f.details["camera_frames"]) >= 2


def test_static_cluster_without_camera_confirmation_is_quiet():
    scene = _parked_scene()
    assert _static_missing(scene, _unlabelled(scene, 1), _FakeDetector(scene, 1, None)) == []
    # ảnh thấy loại vật khác hẳn kích thước cụm (người ở chỗ cụm cỡ xe): không báo
    assert _static_missing(scene, _unlabelled(scene, 1), _FakeDetector(scene, 1, "person")) == []


def test_static_labelled_car_is_quiet():
    scene = _parked_scene()
    assert _static_missing(scene, labels(scene), _FakeDetector(scene, 1, "car")) == []


def _person_cloud(base_z: float, roof: bool):
    """Mặt đất phẳng z = 0 có khoảng trống 6x6 m quanh (10, 0) (đất bị che); `roof`: tấm mái z = base_z trong khoảng
    trống. Cụm cỡ người dày điểm đứng ở (10, 0), chân tại base_z."""
    import numpy as np

    rng = np.random.default_rng(3)
    gx, gy = np.meshgrid(np.arange(-40, 40, 0.5), np.arange(-40, 40, 0.5))
    ground = np.column_stack([gx.ravel(), gy.ravel(), rng.normal(0, 0.02, gx.size)])
    hole = (np.abs(ground[:, 0] - 10) < 3) & (np.abs(ground[:, 1]) < 3)
    parts = [ground[~hole]] if roof else [ground]
    if roof:
        rx, ry = np.meshgrid(np.arange(7.2, 12.8, 0.3), np.arange(-2.8, 2.8, 0.3))
        parts.append(np.column_stack([rx.ravel(), ry.ravel(), np.full(rx.size, base_z)]))
    parts.append(np.column_stack([rng.uniform(9.7, 10.3, 400), rng.uniform(-0.2, 0.2, 400),
                                  rng.uniform(base_z + 0.05, base_z + 1.75, 400)]))
    return np.vstack(parts)


def test_person_sized_cluster_on_high_roof_is_not_an_object():
    """Đất dưới mái bị che: mặt đất cục bộ là chính tấm mái nên cụm trên mái trông như đứng sát đất. So với mặt đất
    chung của frame thì chân cụm cao 3 m: không phải vật cần gán (báo nhầm job 4 scene-0061, 13/10)."""
    from pointsnap.detectors.missing import frame_clusters

    cfg = load_config(None).missing
    assert [c for c in frame_clusters(_person_cloud(0.0, roof=False), [], None, cfg, 0) if abs(c.center[0] - 10) < 1]
    assert not [c for c in frame_clusters(_person_cloud(3.0, roof=True), [], None, cfg, 0) if abs(c.center[0] - 10) < 1]
