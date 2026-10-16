"""Regression tests for real writes, no-op proposals and bounded temporal heading evidence."""

import copy
import math

import numpy as np
import pytest
from fastapi.testclient import TestClient

from pointsnap.core.heading_memory import HeadingMemory
from pointsnap.core.config import HeadingConfig, StaticConfig
from pointsnap.core.model import Cuboid
from pointsnap.core.repair import compute_box_repair
from pointsnap.detectors.heading import detect_heading_track
from pointsnap.detectors.static import detect_static_errors
from pointsnap.web.app import create_app


def track():
    return {"id": 7, "label_id": 1, "frame": 0, "attributes": [], "shapes": [
        {"id": 70 + f, "type": "cuboid", "frame": f, "outside": False, "occluded": False,
         "points": [f * 3., 0., 1., .12, -.21, 0., 4., 2., 2.] + [0.] * 7,
         "attributes": [{"spec_id": 1, "value": "keep"}]} for f in range(3)]}


class Store:
    def __init__(self):
        self.track = track()
        self.fail = False
        self.ignore = False
        self.writes = 0

    def get_job_annotations(self, job):
        return {"version": self.writes, "tracks": [copy.deepcopy(self.track)]}

    def patch_job_annotations(self, job, data, action):
        self.writes += 1
        assert "version" in data
        if self.fail:
            raise RuntimeError("CVAT refused write")
        if not self.ignore:
            self.track = copy.deepcopy(data["tracks"][0])
            for s in self.track["shapes"]:
                s["id"] += 100

    def get_job(self, job):
        return {"task_id": 1}

    def task_labels(self, task):
        return [{"id": 1, "name": "car"}]


@pytest.fixture
def connected(tmp_path):
    app = create_app(tmp_path)
    store = Store()
    app.state.cvat_client = store
    return TestClient(app), store


def apply(client, repair=None):
    return client.post("/api/jobs/1/tracks/7/apply-repair", json={"frame": 1,
        "repair": repair if repair is not None else {"delta_center": [0, 0, -.2]}})












def test_no_evidence_preview_reports_zero_confidence(connected):
    client, _ = connected
    result = client.get("/api/jobs/1/tracks/7/repair?frame=1&rule=fit.empty")
    assert result.status_code == 200
    assert result.json()["repair"]["confidence"] == 0
    assert result.json()["repair"]["applicable"] is False


def test_heading_api_serializes_numpy_predictions(connected):
    from pointsnap.core.model import FrameData
    client, store = connected
    for shape in store.track["shapes"]:
        shape["points"][5] = 1.7
    class Frames:
        def frame_data(self, frame, with_points=True):
            return FrameData(frame, np.zeros((0, 3)), np.eye(4), frame * .5)
    client.app.state.frame_source = Frames()
    result = client.get("/api/jobs/1/tracks/7/repair?frame=1&rule=heading.motion")
    assert result.status_code == 200
    prediction = result.json()["heading_prediction"]
    assert prediction["moving"] is True
    assert prediction["frames_used"] == [0, 1]
    assert result.json()["repair"]["repaired_cuboid"]["yaw"] == pytest.approx(0)


@pytest.mark.parametrize("angle", np.linspace(-math.pi, math.pi, 25))
def test_memory_predicts_motion_in_all_directions(angle):
    memory = HeadingMemory()
    for f in range(30):
        memory.update((1, "car"), f, f * .5, (f * 2 * math.cos(angle), f * 2 * math.sin(angle)), angle)
    p = memory.predict((1, "car"))
    assert len(p.frames) == 5
    assert p.frames == (25, 26, 27, 28, 29)
    assert p.predicted_center == pytest.approx((60 * math.cos(angle), 60 * math.sin(angle)))
    assert abs(math.atan2(math.sin(p.heading - angle), math.cos(p.heading - angle))) < 1e-10


def test_memory_turn_stop_gap_reappearance_and_isolation():
    m = HeadingMemory(max_tracks=2)
    m.update("a", 0, 0, (0, 0), 0)
    m.update("a", 1, .5, (2, 0), 0)
    m.update("a", 2, 1., (2, 2), math.pi / 2)
    assert m.predict("a").heading == pytest.approx(math.pi / 2)
    m.update("a", 3, 1.5, (2, 2), math.pi / 2)
    assert not m.predict("a").moving
    assert m.predict("a").predicted_center == (2, 2)
    m.update("a", 9, 9., (20, 20), 0)
    assert m.predict("a").frames == (9,)
    m.update("a", 10, 9.5, (20, 20), 0, visible=False)
    assert m.predict("a") is None
    for key in ("a", "b", "c"):
        m.update(key, 1, 0, (0, 0), 0)
    assert len(m.tracks) == 2 and m.predict("a") is None
    with pytest.raises(ValueError):
        m.predict("b", 10)


@pytest.mark.parametrize("rotation", [0, .4, 1.2, -2.8])
def test_heading_motion_repair_uses_world_evidence_in_sensor_coordinates(rotation):
    pose = np.eye(4)
    c, s = math.cos(rotation), math.sin(rotation)
    pose[:2, :2] = [[c, -s], [s, c]]
    boxes = [Cuboid(center=(3 * f, 0, 1), dims=(4, 2, 2), yaw=1.7, frame=f, track_id=7, label="car") for f in range(8)]
    findings = detect_heading_track(boxes, HeadingConfig(), sensor_to_world={f: pose for f in range(8)}, flip=False)
    finding = next(f for f in findings if f.frame == 4)
    delta = compute_box_repair(boxes[4], boxes, None, finding.rule, finding.details)
    assert delta.repaired_cuboid.yaw == pytest.approx(0, abs=1e-6)
    assert len(finding.details["heading_prediction"]["frames_used"]) <= 5


def test_stationary_heading_repair_compensates_ego_rotation():
    boxes, poses = [], {}
    for f in range(6):
        a = f * .15
        p = np.eye(4)
        p[:2, :2] = [[math.cos(a), -math.sin(a)], [math.sin(a), math.cos(a)]]
        poses[f] = p
        center = p[:3, :3].T @ np.array([10., 0., 1.])
        boxes.append(Cuboid(center=tuple(center), dims=(4, 2, 2), yaw=-a + (.4 if f == 3 else 0),
                            frame=f, track_id=7, label="car"))
    finding = next(f for f in detect_static_errors(boxes, StaticConfig(), poses) if f.rule == "heading.static" and f.frame == 3)
    delta = compute_box_repair(boxes[3], boxes, None, finding.rule, finding.details)
    assert delta.repaired_cuboid.yaw == pytest.approx(-.45)


@pytest.mark.parametrize("face", ["đầu", "đuôi", "bên trái", "bên phải", "đầu và đuôi"])
def test_loose_repair_actually_shrinks_only_observed_faces(face):
    b = Cuboid(center=(10, 0, 1), dims=(8, 4, 2), yaw=0, label="car", frame=0, track_id=7)
    rng = np.random.default_rng(3)
    pts = rng.uniform([-2, -1, -.5], [2, 1, .5], (500, 3)) + np.asarray(b.center)
    d = compute_box_repair(b, [b], pts, "fit.loose", {"face": face})
    assert min(d.delta_dims) < -.5
    assert d.repaired_cuboid.height == b.height
    axis = 1 if face.startswith("bên") else 0
    assert d.repaired_cuboid.dims[1 - axis] == b.dims[1 - axis]
