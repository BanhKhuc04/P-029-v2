"""Kiểm thử lớp 3 của Box Verifier: đặc trưng, dữ liệu huấn luyện và chỗ cắm Box Critic (việc C3)."""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
import pytest

from pointsnap.core.config import CriticConfig
from pointsnap.core.model import Cuboid, Severity
from pointsnap.critic import CLASSES, NUM_POINTS, TARGETS, _perturb, box_features, critic_findings


def _car(**kw) -> Cuboid:
    args = dict(center=(10.0, 5.0, 0.8), dims=(4.5, 1.9, 1.6), yaw=0.4, label="car", frame=0, track_id=1)
    args.update(kw)
    return Cuboid(**args)


def test_box_features_shape_and_scaling():
    box = _car()
    rng = np.random.default_rng(0)
    pts = np.array([[2.25, 0.0, 0.0], [0.0, 0.95, 0.0], [3.0, 0.0, 0.0]])  # 2 điểm trên mặt box, 1 điểm ngoài
    cloud, meta = box_features(pts, box, 25.0, rng)
    assert cloud.shape == (NUM_POINTS, 4) and cloud.dtype == np.float32
    assert meta.shape == (5 + len(CLASSES),)
    assert np.all(np.abs(cloud[cloud[:, 3] == 1, :3]) <= 1.0 + 1e-6)  # trong box: toạ độ chuẩn hoá trong [-1, 1]
    assert np.all(np.min(np.abs(cloud[:, :1] - np.array([1.0, 0.0, 3.0 / 2.25])), axis=1) < 1e-5)
    assert meta[3] == pytest.approx(0.5) and meta[4] == pytest.approx(math.log1p(3))
    assert meta[5 + CLASSES.index("car")] == 1.0 and meta[5:].sum() == 1.0


def test_box_features_empty_cloud():
    cloud, _ = box_features(np.zeros((0, 3)), _car(), 10.0, np.random.default_rng(0))
    assert cloud.shape == (NUM_POINTS, 4) and not cloud.any()


def test_perturb_target_recovers_true_box():
    """Áp `target` (hệ box đã nhiễu) lên box nhiễu phải ra đúng box chuẩn."""
    rng = np.random.default_rng(3)
    box = _car()
    errors = 0
    for _ in range(200):
        noisy, target, wrong = _perturb(box, rng)
        dx, dy, dz, dl, dw, dh, dyaw = (float(v) for v in target)
        c, s = math.cos(noisy.yaw), math.sin(noisy.yaw)
        center = (noisy.center[0] + c * dx - s * dy, noisy.center[1] + s * dx + c * dy, noisy.center[2] + dz)
        assert center == pytest.approx(box.center, abs=1e-4)
        assert (noisy.dims[0] + dl, noisy.dims[1] + dw, noisy.dims[2] + dh) == pytest.approx(box.dims, abs=1e-4)
        assert noisy.yaw + dyaw == pytest.approx(box.yaw, abs=1e-5)
        errors += wrong
        if not wrong:
            assert abs(math.degrees(dyaw)) <= 4.0 and math.hypot(dx, dy) <= 0.15 + 1e-6
    assert 0.3 < errors / 200 < 0.8
    assert len(TARGETS) == 7


@dataclass
class _FrameData:
    points: np.ndarray


class _Frames:
    def __init__(self, box: Cuboid):
        rng = np.random.default_rng(1)
        local = rng.uniform(-1, 1, (300, 3)) * np.asarray(box.dims) / 2
        c, s = math.cos(box.yaw), math.sin(box.yaw)
        world = np.column_stack([box.center[0] + c * local[:, 0] - s * local[:, 1],
                                 box.center[1] + s * local[:, 0] + c * local[:, 1], box.center[2] + local[:, 2]])
        ground = np.column_stack([rng.uniform(0, 20, 2000), rng.uniform(-5, 15, 2000), np.zeros(2000)])
        self.points = np.column_stack([np.vstack([world, ground]), np.zeros(2300)])

    def frame_data(self, frame):
        return _FrameData(self.points)


def test_critic_findings_with_scripted_model(tmp_path):
    torch = pytest.importorskip("torch")

    class Always(torch.nn.Module):
        """Model giả: luôn cho xác suất sai 0.95 và gợi ý dời +0.3 m theo trục box."""

        def forward(self, points: torch.Tensor, meta: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
            b = points.shape[0]
            delta = torch.zeros(b, 7)
            delta[:, 0] = 0.3
            return torch.full((b,), 2.944), delta

    path = tmp_path / "critic.pt"
    torch.jit.script(Always()).save(str(path))
    box = _car()
    findings = critic_findings([box], _Frames(box), CriticConfig(model=str(path), min_points=20))
    assert len(findings) == 1
    f = findings[0]
    assert f.rule == "critic.box" and f.severity is Severity.ERROR and f.value == pytest.approx(0.95, abs=1e-3)
    assert f.details["suggested_fix"]["dx"] == pytest.approx(0.3)
    assert "dời (+0.30" in f.message

    few = critic_findings([box], _Frames(box), CriticConfig(model=str(path), min_points=100_000))
    assert few == []


def test_critic_track_relative(tmp_path):
    """Box thuộc track: so logit với trung vị các frame khác của track, gợi ý sửa cũng trừ trung vị của track."""
    torch = pytest.importorskip("torch")

    class MeanX(torch.nn.Module):
        """Logit = 20 × trung bình x (hệ box chuẩn hoá) của điểm trong box + 3: lệch đều 3 ở mọi box (như model lệch
        theo cảnh), box dời khỏi vật thì trung bình x đổi."""

        def forward(self, points: torch.Tensor, meta: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
            inside = points[:, :, 3]
            mean_x = (points[:, :, 0] * inside).sum(1) / inside.sum(1).clamp(min=1.0)
            delta = torch.zeros(points.shape[0], 7)
            delta[:, 0] = -mean_x
            return 20.0 * mean_x.abs() + 3.0, delta

    path = tmp_path / "critic.pt"
    torch.jit.script(MeanX()).save(str(path))
    truth = _car(yaw=0.0)
    frames = _Frames(truth)

    class _Same:
        def frame_data(self, frame):
            return frames.frame_data(0)

    track = [truth.replace(frame=f) for f in range(5)]
    cfg = CriticConfig(model=str(path), min_points=20, min_logit_rise=4.0, error_logit_rise=6.0)
    # Logit thô ~3 (xác suất 95%) ở mọi frame nhưng không frame nào khác track: không báo.
    assert critic_findings(track, _Same(), cfg) == []
    track[2] = track[2].replace(center=(truth.center[0] + 1.5, truth.center[1], truth.center[2]))
    findings = critic_findings(track, _Same(), cfg)
    assert [f.frame for f in findings] == [2]
    assert "cao hơn các frame khác của track" in findings[0].message
    assert findings[0].details["suggested_fix"]["dx"] > 0  # gợi ý dời về phía vật (âm của độ lệch trung bình x)
