"""Missing review: geometry, independent frame evidence and optional pose boundaries."""
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest

from pointsnap.core.camera import project_box
from pointsnap.core.config import CameraConfig, MissingConfig
from pointsnap.core.model import Cuboid, FrameData
from pointsnap.detectors.missing import (Cluster, _components, _link_static, _static_confirmed,
                                        detect_missing_objects, frame_clusters)
from pointsnap.vision.detector2d import Detections
from test_missing import _front_camera


def cluster(frame, x=15.0):
    return Cluster(frame, np.array([x, .5]), np.array([x, .5]), 4., 1.9, 1.6, 100,
                   frozenset({(int(x * 4), 2)}))


class Frames:
    num_frames = 3

    def frame_data(self, frame, with_points=True):
        return FrameData(frame, np.empty((0, 3)), np.eye(4), frame * .5)

    def camera_views(self, frame):
        return [replace(_front_camera(), path=Path(f"{frame}-front.jpg"))]


class Detector:
    supported_groups = frozenset({"vehicle"})

    def __init__(self, name="car", dark=False):
        self.name = name
        self.dark = dark

    def detect(self, path):
        box = Cuboid((15., .5, .8), (4., 1.9, 1.6), 0., "car", 0)
        rect = project_box(box, np.eye(4), _front_camera()).box
        return Detections(np.array([rect]), np.array([.98]), [self.name], [],
                          10. if self.dark else 120.)


def confirmed(chains=None, frames=None, detector=None, cfg=None):
    return _static_confirmed(chains or [[cluster(i) for i in range(3)]], [], frames or Frames(),
                             detector or Detector(), cfg or MissingConfig(), CameraConfig())


@pytest.mark.parametrize("reverse", [False, True])
def test_cluster_connectivity_does_not_depend_on_point_order(reverse):
    cells = np.array([[0, 0], [2, 0]])
    far = np.array([False, True])
    if reverse:
        cells, far = cells[::-1], far[::-1]
    assert len(_components(cells, far)) == 1


def test_rotated_label_masks_its_corner_points_without_masking_neighbor():
    box = Cuboid((10., 0., 1.), (4., 4., 2.), np.pi / 4, "car", 0)
    # Independent rotation: this corner reaches y=2.69, beyond max(dims)/2+.3.
    points = np.array([[10., 2.69, z] for z in np.linspace(.5, 1.8, 20)] +
                      [[10., 3.5, z] for z in np.linspace(.5, 1.8, 20)] + [[10., 2.69, 0.], [10., 3.5, 0.]])
    occupied = set()
    frame_clusters(points, [box], np.eye(4), MissingConfig(box_margin_m=0), 0, occupied)
    assert (40, 10) not in occupied
    assert (40, 14) in occupied


@pytest.mark.parametrize("name", ["vehicle", "construction vehicle", "CAR", "car truck"])
def test_static_confirmation_uses_model_groups_not_exact_coco_name(name):
    found = confirmed(detector=Detector(name))
    assert len(found) == 1 and found[0].label == "xe"
    assert found[0].details["camera_class"] == name


def test_static_confirmation_ignores_individual_dark_view():
    class MixedFrames(Frames):
        def camera_views(self, frame):
            return [replace(_front_camera(), channel=name, path=Path(name + ".jpg"))
                    for name in ["dark", "light1", "light2"]]

    class MixedDetector(Detector):
        def detect(self, path):
            if path.stem == "dark":
                return Detector(dark=True).detect(path)
            return Detections(np.empty((0, 4)), np.empty(0), [], [], 120.)

    assert confirmed(frames=MixedFrames(), detector=MixedDetector()) == []


def test_static_confirmation_honors_current_supported_groups():
    detector = Detector()
    detector.supported_groups = frozenset({"person"})
    assert confirmed(detector=detector) == []


def test_static_confirmation_needs_consistent_semantic_group_across_frames():
    # A chain changes visible extent; incompatible person/car votes must not be pooled.
    rows = [cluster(0), cluster(1), cluster(2)]
    rows[0].length, rows[0].width, rows[0].height = .7, .6, 1.7
    class Alternating(Detector):
        supported_groups = frozenset({"vehicle", "person"})
        def detect(self, path):
            return Detector("person" if path.name.startswith("0-") else "car" if path.name.startswith("1-") else "dog").detect(path)
    assert confirmed(chains=[rows], detector=Alternating()) == []


def test_static_confirmation_counts_distinct_frames():
    assert confirmed(chains=[[cluster(0), cluster(0), cluster(0)]]) == []


def test_static_link_does_not_follow_gradual_drift():
    rows = {i: [cluster(i, 15 + .6 * i)] for i in range(10)}
    chains = _link_static(rows, MissingConfig())
    assert all(np.linalg.norm(c[-1].world - c[0].world) <= 1 for c in chains)


def test_static_confirmation_does_not_arbitrarily_sample_away_required_frames():
    rows = [cluster(i) for i in range(20)]
    assert len(confirmed(chains=[rows], cfg=MissingConfig(static_min_views=12))) == 1


def test_missing_requires_known_pose_for_world_motion():
    class NoPose(Frames):
        def frame_data(self, frame, with_points=True):
            return FrameData(frame, np.empty((0, 3)))
    # Validate the standalone clustering contract too: identity is an explicit pose.
    occupied = set()
    assert frame_clusters(np.array([[10., 0., 0.], [10., 0., 1.]]), [], None,
                          MissingConfig(min_points=1), 0, occupied) == []
    assert occupied == set()
    assert detect_missing_objects([], NoPose(), MissingConfig())[0] == []


def test_missing_returns_only_accepted_moving_chains_and_distance_units(monkeypatch):
    rows = {i: [cluster(i, 10. + 2 * i)] for i in range(3)}
    import pointsnap.detectors.missing as missing
    monkeypatch.setattr(missing, "frame_clusters", lambda points, boxes, pose, cfg, frame, occupancy: rows[frame])
    monkeypatch.setattr(missing, "_persistence", lambda *args: 0.)
    class Timed(Frames):
        def frame_data(self, frame, with_points=True):
            return FrameData(frame, np.empty((0, 3)), np.eye(4), frame * .2)
    findings, chains = detect_missing_objects([], Timed(), MissingConfig())
    assert len(findings) == len(chains) == 1
    assert findings[0].value == 4. and findings[0].threshold == 3.
    assert findings[0].details["speed_m_s"] == 10.
    findings, chains = detect_missing_objects([], Frames(), MissingConfig(min_motion_m=10.))
    assert findings == [] and chains == []


@pytest.mark.parametrize("occluded,outside,masked", [(False,False,True),(True,False,True),(False,True,False)])
def test_existing_label_mask_respects_outside_but_preserves_occluded(occluded, outside, masked):
    box = Cuboid((10., 0., 1.), (2., 2., 2.), 0., "car", 0, outside=outside, attrs={"occluded":occluded})
    occupied = set()
    frame_clusters(np.array([[10., 0., 0.], [10., 0., 1.]]), [box], np.eye(4),
                   MissingConfig(), 0, occupied)
    assert ((40, 0) not in occupied) == masked


def test_static_confirmation_requires_camera_config_only_when_needed():
    found = _static_confirmed([[cluster(i) for i in range(3)]], [], Frames(), Detector(), MissingConfig(), None)
    assert len(found) == 1


@pytest.mark.parametrize('label_x,expected', [(6., 0), (30., 1)])
def test_foreground_label_cannot_confirm_farther_cluster_from_the_same_image_region(label_x, expected):
    labels = [Cuboid((label_x, .5, .8), (4., 3., 1.6), 0., 'car', f, track_id=9) for f in range(3)]
    found = _static_confirmed([[cluster(i) for i in range(3)]], labels, Frames(), Detector(),
                             MissingConfig(), CameraConfig())
    # The far target has enough matching 2D detections, but they do not establish its depth when hidden.
    assert len(found) == expected


def test_static_dark_images_and_empty_detections_never_confirm():
    assert confirmed(detector=Detector(dark=True)) == []
    class Empty(Detector):
        def detect(self,path):
            return Detections(np.empty((0,4)),np.empty(0),[],[],120.)
    assert confirmed(detector=Empty()) == []


def test_missing_report_opens_frame_without_selecting_an_existing_object(tmp_path):
    import csv
    from pointsnap.report.csv_rep import generate_csv_report
    from pointsnap.report.html import generate_html_report
    from test_gate_coverage import job_data
    finding = confirmed()[0]
    assert finding.track_id is None and finding.source_id is None
    csv_path = generate_csv_report(job_data(), [finding], tmp_path / "missing.csv")
    row = next(csv.DictReader(csv_path.open(encoding="utf-8-sig")))
    assert row["track_id"] == row["source_id"] == ""
    assert "frame=0" in row["cvat_url"] and "objectID" not in row["cvat_url"]
    html = generate_html_report(job_data(), [finding], tmp_path / "missing.html").read_text(encoding="utf-8")
    assert "lidar.missing" in html and "objectID" not in html
