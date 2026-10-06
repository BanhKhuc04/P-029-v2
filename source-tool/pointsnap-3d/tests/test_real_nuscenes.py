"""Kiểm B1 trên dữ liệu nuScenes thật. Bỏ qua nếu không có dữ liệu (đặt NUSCENES_ROOT hoặc file `.env`).

Ý tưởng: nuScenes ghi sẵn `num_lidar_pts` cho mỗi box chuẩn. Nếu reader đổi tọa độ đúng (pose xe thu, hiệu
chỉnh cảm biến, thứ tự [w, l, h], hướng yaw) thì số điểm LiDAR nằm trong box tính theo hệ LiDAR của ta phải gần
bằng con số đó. Sai một phép quay hay đổi chỗ w / l là lệch rất xa.
"""

import os
from pathlib import Path

import numpy as np
import pytest

from pointsnap.adapters.nuscenes import NuScenesReader
from pointsnap.core.geometry import points_in_cuboid
from pointsnap.core.model import group_by_frame


def _nuscenes_root() -> str | None:
    """NUSCENES_ROOT từ biến môi trường, hoặc từ file `.env` của tool (chỉ đọc khóa này, không nạp token)."""
    if os.environ.get("NUSCENES_ROOT"):
        return os.environ["NUSCENES_ROOT"]
    env_file = Path(__file__).resolve().parents[1] / ".env"
    if env_file.is_file():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            key, _, value = line.partition("=")
            if key.strip() == "NUSCENES_ROOT":
                return value.strip().strip("\"'")
    return None


ROOT = _nuscenes_root()

pytestmark = pytest.mark.skipif(
    not ROOT or not (Path(ROOT) / "v1.0-mini").is_dir(), reason="chưa có dữ liệu nuScenes (NUSCENES_ROOT)"
)


@pytest.fixture(scope="module")
def reader():
    return NuScenesReader(ROOT)


def test_mini_has_ten_scenes_of_about_forty_keyframes(reader):
    scenes = reader.scenes()
    assert len(scenes) == 10
    for scene in scenes:
        assert len(reader.samples(scene.name)) == scene.num_frames


@pytest.mark.parametrize("scene_index", [0, 1])
def test_points_inside_ground_truth_boxes_match_nuscenes_counts(reader, scene_index):
    scene = reader.scenes()[scene_index].name
    refs = reader.samples(scene)
    boxes_by_frame = group_by_frame(reader.annotations(scene))
    ours, theirs = [], []
    for ref in refs:
        points = reader.load_points(ref)
        for box in boxes_by_frame.get(ref.frame, []):
            ours.append(int(points_in_cuboid(points, box).sum()))
            theirs.append(box.attrs["num_lidar_pts"])
    ours, theirs = np.array(ours), np.array(theirs)
    close = np.abs(ours - theirs) <= np.maximum(2, 0.1 * theirs)
    print(f"{scene}: {len(ours)} box, {close.mean():.1%} khớp ±max(2 điểm, 10%), "
          f"trung vị lệch {np.median(np.abs(ours - theirs)):.0f} điểm")
    assert len(ours) > 100
    assert close.mean() > 0.9
