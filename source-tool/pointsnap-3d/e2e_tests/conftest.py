"""Pytest fixtures and test environment setup for PointSnap 3D E2E Test Suite.
"""

from __future__ import annotations

import math
import shutil
import tempfile
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Generator

import numpy as np
import pytest

from pointsnap.core.config import Config, load_config
from pointsnap.core.model import Cuboid, FrameSource, Severity


@pytest.fixture
def base_config() -> Config:
    """Returns standard base configuration."""
    return load_config(env={})


@pytest.fixture
def spec_vn_config() -> Config:
    """Returns configuration with spec-vn taxonomy and guidelines."""
    guideline_path = Path("pointsnap/guidelines/spec-vn.yaml")
    if guideline_path.exists():
        return load_config(path=str(guideline_path), env={})
    return load_config(env={})


@pytest.fixture
def sample_cuboid() -> Cuboid:
    """Returns a representative valid vehicle cuboid."""
    return Cuboid(
        center=(10.0, 5.0, 0.0),
        dims=(4.5, 2.0, 1.6),
        yaw=0.0,
        label="car",
        frame=0,
        track_id=101,
        source_id=1001,
        keyframe=True,
        outside=False,
        attrs={"subtype": "sedan", "occluded": False},
    )


@pytest.fixture
def sample_track() -> list[Cuboid]:
    """Returns a continuous 5-frame moving vehicle track."""
    track = []
    for f in range(5):
        # Moving along +X at 2.0 m/frame
        c = Cuboid(
            center=(10.0 + f * 2.0, 5.0, 0.0),
            dims=(4.5, 2.0, 1.6),
            yaw=0.0,
            label="car",
            frame=f,
            track_id=101,
            source_id=1001 + f,
            keyframe=True,
            outside=False,
            attrs={"subtype": "sedan", "occluded": False},
        )
        track.append(c)
    return track


@pytest.fixture
def floating_cuboid(sample_cuboid: Cuboid) -> Cuboid:
    """Returns a cuboid with +0.35m elevated bottom (triggering floating finding)."""
    return sample_cuboid.replace(
        center=(sample_cuboid.center[0], sample_cuboid.center[1], sample_cuboid.center[2] + 0.35),
        frame=2,
    )


@pytest.fixture
def flipped_cuboid(sample_cuboid: Cuboid) -> Cuboid:
    """Returns a cuboid with 180° inverted yaw."""
    return sample_cuboid.replace(
        yaw=math.pi,
        frame=2,
    )


@pytest.fixture
def oversized_cuboid(sample_cuboid: Cuboid) -> Cuboid:
    """Returns a cuboid with dimensions 30% larger than track median."""
    return sample_cuboid.replace(
        dims=(sample_cuboid.length * 1.30, sample_cuboid.width * 1.30, sample_cuboid.height),
        frame=2,
    )


@pytest.fixture
def sample_ground_points() -> np.ndarray:
    """Generates synthetic ground plane points at z = -0.80m."""
    np.random.seed(42)
    x = np.random.uniform(5.0, 25.0, 1000)
    y = np.random.uniform(-5.0, 15.0, 1000)
    z = np.random.normal(-0.80, 0.02, 1000)
    return np.column_stack([x, y, z]).astype(np.float32)


@pytest.fixture
def sample_car_points(sample_cuboid: Cuboid) -> np.ndarray:
    """Generates synthetic L-shape cluster on vehicle surface."""
    np.random.seed(42)
    c_x, c_y, c_z = sample_cuboid.center
    l, w, h = sample_cuboid.dims
    # Points on front face (x = c_x + l/2) and side face (y = c_y + w/2)
    n_pts = 100
    front_x = np.full(n_pts // 2, c_x + l / 2)
    front_y = np.random.uniform(c_y - w / 2, c_y + w / 2, n_pts // 2)
    front_z = np.random.uniform(c_z - h / 2, c_z + h / 2, n_pts // 2)

    side_x = np.random.uniform(c_x - l / 2, c_x + l / 2, n_pts // 2)
    side_y = np.full(n_pts // 2, c_y + w / 2)
    side_z = np.random.uniform(c_z - h / 2, c_z + h / 2, n_pts // 2)

    pts_x = np.concatenate([front_x, side_x])
    pts_y = np.concatenate([front_y, side_y])
    pts_z = np.concatenate([front_z, side_z])
    return np.column_stack([pts_x, pts_y, pts_z]).astype(np.float32)


@pytest.fixture
def combined_lidar_points(sample_ground_points: np.ndarray, sample_car_points: np.ndarray) -> np.ndarray:
    """Combines ground plane and car surface points."""
    return np.vstack([sample_ground_points, sample_car_points])


@pytest.fixture
def mock_cvat_raw_track() -> dict[str, Any]:
    """Returns a realistic raw CVAT track dictionary with 5 keyframes."""
    shapes = []
    for f in range(5):
        # 16-element float array for 3D cuboid
        pts = [10.0 + f * 2.0, 5.0, 0.0, 0.0, 0.0, 0.0, 4.5, 2.0, 1.6, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
        shapes.append({
            "id": 1000 + f,
            "frame": f,
            "type": "cuboid",
            "occluded": False,
            "outside": False,
            "keyframe": True,
            "points": pts,
            "attributes": [
                {"id": 1, "name": "subtype", "value": "sedan"},
                {"id": 2, "name": "reviewed", "value": "true"},
            ],
        })
    return {
        "id": 101,
        "label_id": 10,
        "frame": 0,
        "shapes": shapes,
        "attributes": [],
    }


@pytest.fixture
def temp_history_storage(tmp_path: Path) -> Path:
    """Provides an isolated directory for rollback history snapshots."""
    history_dir = tmp_path / "history" / "job_4"
    history_dir.mkdir(parents=True, exist_ok=True)
    return history_dir
