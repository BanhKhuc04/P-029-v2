"""Chặn kết luận khi box quá ít điểm LiDAR (chấm tay held-out 13/10)."""

from types import SimpleNamespace

import numpy as np
import pytest

from pointsnap.core.config import ConfigError, EvidenceConfig, load_config, parse_config
from pointsnap.core.model import Cuboid, ErrorType, Finding, Severity
from pointsnap.core.scanner import apply_evidence_gate

CFG = load_config(env={})


def _frames(points):
    return SimpleNamespace(frame_data=lambda frame: SimpleNamespace(points=points))


def _finding(rule, track_id, severity=Severity.WARNING):
    return Finding(error_type=ErrorType.FLOATING, rule=rule, severity=severity, frame=0, label="car",
                   message="Đáy box cách mặt đất 20 cm (lơ lửng)", track_id=track_id)


def test_defaults_gate_floating_and_size_at_twenty_points():
    assert CFG.evidence == EvidenceConfig(min_points=20, rules=("floating", "size.class_range"))


def test_sparse_box_is_downgraded_to_info_and_dense_box_kept():
    rng = np.random.default_rng(3)
    dense = rng.uniform((8.5, -0.8, 0.4), (11.5, 0.8, 1.5), (200, 3))
    sparse = rng.uniform((28.5, -0.8, 0.4), (31.5, 0.8, 1.5), (5, 3))
    boxes = [Cuboid(center=(10.0, 0.0, 0.8), dims=(4.0, 2.0, 1.6), yaw=0.0, label="car", frame=0, track_id=1),
             Cuboid(center=(30.0, 0.0, 0.8), dims=(4.0, 2.0, 1.6), yaw=0.0, label="car", frame=0, track_id=2)]
    findings = [_finding("floating", 1), _finding("floating", 2), _finding("track.jump", 2)]
    gated = apply_evidence_gate(findings, boxes, CFG, _frames(np.concatenate([dense, sparse])))
    assert [f.severity for f in gated] == [Severity.WARNING, Severity.INFO, Severity.WARNING]
    assert gated[1].details["evidence_points"] < 20 and gated[1].details["evidence_severity"] == "warning"
    assert gated[1].message.startswith("Ít điểm LiDAR")


def test_gate_off_without_frames_or_threshold():
    findings = [_finding("floating", 1)]
    assert apply_evidence_gate(findings, [], CFG, None) == findings


def test_evidence_section_is_validated():
    data = load_config(env={}).to_dict()
    data["cvat"].pop("token", None)
    data["floating"]["single_box"] = True
    data["evidence"] = {"min_points": 7, "rules": ["floating"]}
    cfg = parse_config(data, env={})
    assert cfg.evidence == EvidenceConfig(min_points=7, rules=("floating",)) and cfg.floating.single_box is True
    data["evidence"] = {"min_points": 7, "unknown": 1}
    with pytest.raises(ConfigError):
        parse_config(data, env={})
