"""Independent regressions from the 13 October review; failures stay visible.

These assertions describe expected behavior, rather than accepting current bugs.
The main branch may fail them until the documented findings are fixed.
"""
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from pointsnap.core.config import CriticConfig, load_config
from pointsnap.core.model import Cuboid
from pointsnap.critic import critic_findings
from pointsnap.detectors.attributes import detect_rider_state, detect_spec_geometry

GUIDELINE = Path(__file__).resolve().parents[1] / "pointsnap/guidelines/spec-vn.yaml"


def test_negative_extreme_model_logit_is_healthy_instead_of_crashing(tmp_path):
    """A confident healthy prediction (-1000) should produce zero findings."""
    torch = pytest.importorskip("torch")

    class Healthy(torch.nn.Module):
        def forward(self, points: torch.Tensor, meta: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
            return torch.full((points.shape[0],), -1000.0), torch.zeros(points.shape[0], 7)

    path = tmp_path / "healthy.pt"
    torch.jit.script(Healthy()).save(str(path))
    box = Cuboid(center=(10.0, 0.0, 1.0), dims=(4.0, 2.0, 2.0), yaw=0.0, label="car", frame=0)
    points = np.random.default_rng(17).uniform((8.5, -0.8, 0.3), (11.5, 0.8, 1.7), (100, 3))
    frames = SimpleNamespace(frame_data=lambda frame: SimpleNamespace(points=points))
    assert critic_findings([box], frames, CriticConfig(model=str(path), min_points=20)) == []


def test_track_zero_inside_vehicle_is_one_track_finding():
    """Track 0 is a valid stable identity, so three frames form one finding."""
    boxes = []
    for frame in range(3):
        boxes += [
            Cuboid(center=(10.0, 0.0, 0.6), dims=(0.6, 0.6, 1.2), yaw=0.0,
                   label="Pedestrian", frame=frame, track_id=0, attrs={"pose": "sitting", "age_group": "adult"}),
            Cuboid(center=(10.0, 0.0, 0.8), dims=(4.5, 1.9, 1.6), yaw=0.0,
                   label="Vehicle", frame=frame, track_id=2, attrs={"subtype": "car"}),
        ]
    findings = detect_spec_geometry(boxes, load_config(GUIDELINE, env={}).spec)
    assert len(findings) == 1
    assert findings[0].track_id == 0 and findings[0].details["frames"] == [0, 1, 2]


def test_rider_motion_without_world_pose_has_insufficient_evidence():
    """Sensor-relative displacement alone cannot establish a rider's speed."""
    boxes = [Cuboid(center=(10.0 + frame * 4, 0.0, 0.6), dims=(1.9, 0.8, 1.2), yaw=0.0,
                    label="Two-wheels", frame=frame, track_id=1, attrs={"rider_state": "without_rider"})
             for frame in range(3)]
    assert detect_rider_state(boxes, load_config(GUIDELINE, env={}).spec, sensor_to_world=None) == []
