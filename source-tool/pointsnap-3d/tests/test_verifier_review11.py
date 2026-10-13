"""Part 11: provenance, failure recovery, and verifier evidence boundaries."""

import dataclasses
import json
import math
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pytest

from pointsnap.core.config import CriticConfig, StaticConfig, load_config
from pointsnap.core.gate import gate_verdict
from pointsnap.core.model import Cuboid, FrameData, Severity
from pointsnap.core.scanner import scan_coverage_gaps
from pointsnap.critic import _sigmoid, critic_findings
from pointsnap.detectors.static import detect_static_errors
from pointsnap.learn import Sample, collect_reviews, learn_project, load_model, train
from pointsnap.web.storage import StorageError
from test_gate_coverage import job_data


def box(frame=0, **changes):
    args = dict(center=(10, 0, 1), dims=(4, 2, 2), yaw=0, label="car", frame=frame, track_id=0)
    return Cuboid(**{**args, **changes})


def _run(project, name="20261013-run1", reviews=None, findings=None, job=1):
    path = project / "runs" / name
    path.mkdir(parents=True)
    for filename, value in {
        "summary.json": {"job_id": job, "cvat_url": "http://cvat", "timestamp": name},
        "reviews.json": reviews if reviews is not None else {"0": "ok"},
        "findings.json": findings if findings is not None else [
            {"rule": "floating", "severity": "warning", "label": "car", "frame": 0,
             "track_id": 0, "value": 0.3, "threshold": 0.12}],
    }.items():
        (path / filename).write_text(json.dumps(value), encoding="utf-8")
    return path


def test_collect_rescans_count_one_verdict_and_latest_edit_or_delete(tmp_path):
    _run(tmp_path, "20261013-run1")
    latest = _run(tmp_path, "20261013-run2", {"0": "fp"})
    samples = collect_reviews(tmp_path)
    assert [s.verdict for s in samples] == ["fp"]
    (latest / "reviews.json").write_text("{}", encoding="utf-8")
    assert collect_reviews(tmp_path) == []


def test_collect_keeps_different_jobs_and_projects_separate(tmp_path):
    _run(tmp_path / "a", job=1)
    _run(tmp_path / "a", "20261013-run2", job=2)
    _run(tmp_path / "b", reviews={"0": "fp"})
    assert len(collect_reviews(tmp_path / "a")) == 2
    assert [s.verdict for s in collect_reviews(tmp_path / "b")] == ["fp"]


@pytest.mark.parametrize("filename,content", [
    ("reviews.json", '{"bad-index":"ok"}'),
    ("reviews.json", '{"0":"automatic-label"}'),
    ("reviews.json", '[]'),
    ("findings.json", '[{"rule":"floating","value":NaN}]'),
    ("findings.json", '[{"rule":"floating","value":"oops"}]'),
    ("findings.json", '[{}]'),
    ("summary.json", '{broken'),
    ("summary.json", '{"job_id":1,"cvat_url":[] }'),
    ("findings.json", '[{"rule":"floating","track_id":[]} ]'),
])
def test_collect_rejects_corrupt_inputs_with_storage_error(tmp_path, filename, content):
    run = _run(tmp_path)
    (run / filename).write_text(content, encoding="utf-8")
    with pytest.raises(StorageError):
        collect_reviews(tmp_path)


def test_learning_requires_independent_groups_for_cross_validation():
    samples = [Sample("floating", "warning", "car", 3 if i % 2 else 1, 1,
                      "ok" if i % 2 else "fp", group="same-job") for i in range(80)]
    model = train(samples)
    assert not model.use_model and model.cv_logloss_model is None


def test_grouped_cv_never_splits_a_job(monkeypatch):
    import pointsnap.learn as learning
    samples = [Sample("floating", "warning", f"job{g}", i, 1,
                      "ok" if i % 2 else "fp", group=f"job{g}") for g in range(5) for i in range(10)]
    observed = []
    original = learning._fit
    def fit(x, y, **kwargs):
        observed.append(len(x))
        return original(x, y, **kwargs)
    monkeypatch.setattr(learning, "_fit", fit)
    learning._cross_validate(samples)
    assert observed == [40] * 5
    # The held-out class has no training feature column in every fold.
    for test, training in learning._review_folds(samples):
        assert {s.group for s in test}.isdisjoint({s.group for s in training})


def test_failed_learned_write_preserves_active_model_and_history(tmp_path):
    _run(tmp_path)
    learn_project(tmp_path)
    path = tmp_path / "learned.json"
    original = path.read_bytes()
    import pointsnap.web.storage as storage
    replace = storage.os.replace
    def fail_active(source, destination):
        if Path(destination) == path:
            raise OSError("injected disk failure")
        return replace(source, destination)
    with patch.object(storage.os, "replace", side_effect=fail_active):
        with pytest.raises(OSError):
            learn_project(tmp_path)
    assert path.read_bytes() == original
    assert load_model(tmp_path).version == 1
    assert not list(tmp_path.glob(".ps-*.tmp"))


def test_restored_model_gets_new_monotonic_version(tmp_path):
    _run(tmp_path)
    for _ in range(3):
        learn_project(tmp_path)
    first = (tmp_path / "learned-history/learned-v1.json").read_bytes()
    (tmp_path / "learned.json").write_bytes(first)
    assert learn_project(tmp_path).version == 3  # v1 and v2 archived; never reuse v2
    assert (tmp_path / "learned-history/learned-v1.json").read_bytes() == first


@pytest.mark.parametrize("change", [
    {"version": -1}, {"n_samples": "many"}, {"use_model": True, "weights": [1], "vocabulary": {}},
    {"rule_stats": {"floating": {"precision": 2.0}}},
])
def test_load_rejects_invalid_model_schema(tmp_path, change):
    model = train([]).to_dict()
    (tmp_path / "learned.json").write_text(json.dumps({**model, **change}), encoding="utf-8")
    with pytest.raises(StorageError):
        load_model(tmp_path)


def test_static_does_not_count_interpolated_boxes_as_keyframes():
    boxes = [box(0), box(1, keyframe=False), box(2, keyframe=False), box(3, center=(11, 0, 1))]
    assert detect_static_errors(boxes, StaticConfig(), {f: np.eye(4) for f in range(4)}) == []


def test_static_keeps_classes_with_same_track_id_separate():
    boxes = [box(f) for f in range(3)] + [box(3, label="pedestrian", center=(11, 0, 1))]
    assert detect_static_errors(boxes, StaticConfig(), {f: np.eye(4) for f in range(4)}) == []


@pytest.mark.parametrize("rule", ["track_static_shift", "heading_static", "critic_box"])
def test_verifier_missing_evidence_cannot_pass_gate(rule):
    config = load_config(env={})
    config = dataclasses.replace(config, critic=CriticConfig(model="local-checkpoint.pt"),
        rules=dataclasses.replace(config.rules, **{f.name: f.name == rule for f in dataclasses.fields(config.rules)}))
    gaps = scan_coverage_gaps(job_data(), config, None)
    assert gaps and not gate_verdict([], config.gate, coverage_gaps=gaps)[0]


def test_critic_extreme_negative_logit_is_finite():
    assert _sigmoid(-1000) == 0


def _checkpoint(tmp_path, mode="good", score=3.0):
    torch = pytest.importorskip("torch")
    class Checkpoint(torch.nn.Module):
        def forward(self, points, meta):
            logit = points.new_full((points.size(0),), score)
            delta = points.new_zeros((points.size(0), 7))
            if mode == "short":
                logit = logit[:-1]
            elif mode == "matrix":
                logit = logit[:, None]
            elif mode == "delta6":
                delta = delta[:, :6]
            elif mode == "integer":
                logit = logit.to(torch.int64)
            elif mode == "nan":
                delta = delta + float("nan")
            elif mode == "classes":
                logit = meta[:, 5 + 5] * 15  # pedestrian; car stays at zero
            return logit, delta
    path = tmp_path / "critic.pt"
    torch.jit.trace(Checkpoint(), (torch.zeros(2, 256, 4), torch.zeros(2, 20))).save(str(path))
    return str(path)


class DenseFrames:
    def frame_data(self, frame, with_points=True):
        local = np.random.default_rng(7).uniform(-0.8, 0.8, (100, 3))
        return FrameData(frame, local + (10, 0, 1), np.eye(4))


@pytest.mark.parametrize("mode", ["short", "matrix", "delta6", "integer", "nan"])
def test_critic_rejects_invalid_tensor_contract(tmp_path, mode):
    path = _checkpoint(tmp_path, mode)
    with pytest.raises(ValueError, match="Critic"):
        critic_findings([box()], DenseFrames(), CriticConfig(model=path, min_points=1))


def test_critic_reloads_replaced_checkpoint_and_reports_actual_error_threshold(tmp_path):
    path = _checkpoint(tmp_path)
    cfg = CriticConfig(model=path, min_points=1)
    [finding] = critic_findings([box(track_id=None)], DenseFrames(), cfg)
    assert finding.severity is Severity.ERROR and finding.threshold == cfg.error_probability
    _checkpoint(tmp_path, score=-3)
    assert critic_findings([box(track_id=None)], DenseFrames(), cfg) == []


def test_critic_track_references_do_not_cross_classes(tmp_path):
    path = _checkpoint(tmp_path, "classes")
    boxes = [box(f) for f in range(3)] + [box(f, label="pedestrian") for f in range(3, 6)]
    assert critic_findings(boxes, DenseFrames(), CriticConfig(model=path, min_points=1)) == []


def test_critic_does_not_report_interpolated_box(tmp_path):
    path = _checkpoint(tmp_path)
    assert critic_findings([box(keyframe=False, track_id=None)], DenseFrames(),
                           CriticConfig(model=path, min_points=1)) == []


def test_scanner_critic_needs_torch_without_camera_dependencies(tmp_path, monkeypatch):
    from pointsnap.core.scanner import check_critic
    path = _checkpoint(tmp_path)
    monkeypatch.setattr("pointsnap.vision.detector2d.available", lambda: False)
    cfg = dataclasses.replace(load_config(env={}), critic=CriticConfig(model=path, min_points=1))
    job = dataclasses.replace(job_data(), cuboids=[box(track_id=None)])
    assert len(check_critic(job, cfg, DenseFrames())) == 1
    assert scan_coverage_gaps(job, dataclasses.replace(cfg, rules=dataclasses.replace(cfg.rules, **{
        f.name: f.name == "critic_box" for f in dataclasses.fields(cfg.rules)})), DenseFrames()) == []


def training_script():
    pytest.importorskip("torch")
    import importlib.util
    spec = importlib.util.spec_from_file_location("review11_training", Path(__file__).parents[1] / "scripts/train_critic_example.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_training_track_references_are_scoped_to_scene_and_ignore_shapes():
    module = training_script()
    data = {"target": np.zeros((8, 7)), "track_id": np.array([0, 0, 0, 0, -1, -1, -1, -1]),
            "frame": np.arange(8), "scene": np.array(["a", "a", "b", "b", "a", "a", "a", "a"]),
            "is_error": np.zeros(8)}
    assert module.track_rise(np.arange(8, dtype=float), data) is None


def test_training_load_retains_scene_provenance_and_closes_npz(tmp_path):
    module = training_script()
    for scene in ("a", "b"):
        np.savez(tmp_path / f"{scene}.npz", points=np.zeros((2, 256, 4), dtype=np.float32),
                 meta=np.zeros((2, 20), dtype=np.float32), is_error=np.array([0, 1]),
                 target=np.zeros((2, 7)), track_id=np.array([0, 0]), frame=np.array([0, 1]))
    data = module.load(sorted(tmp_path.glob("*.npz")))
    assert data["scene"].tolist() == ["a", "a", "b", "b"]


def test_export_empty_scene_has_valid_tensor_shapes(tmp_path):
    from pointsnap.critic import export_dataset
    class Reader:
        def annotations(self, scene): return []
        def frames(self, scene): return type("Frames", (), {"num_frames": 1})()
    export_dataset(Reader(), ["empty"], tmp_path, progress=lambda _: None)
    with np.load(tmp_path / "empty.npz") as data:
        assert data["points"].shape == (0, 256, 4)
        assert data["meta"].shape == (0, 20)
        assert data["target"].shape == (0, 7)


def test_learning_exclusive_writer_preserves_active_version(tmp_path):
    _run(tmp_path)
    learn_project(tmp_path)
    (tmp_path / ".learn.lock").write_text("other writer", encoding="utf-8")
    with pytest.raises(StorageError, match="đang học"):
        learn_project(tmp_path)
    assert load_model(tmp_path).version == 1


def test_static_world_pose_with_rotating_moving_ego_and_one_bad_box():
    poses, boxes = {}, []
    for f in range(5):
        angle = f * math.pi / 8
        c, s = math.cos(angle), math.sin(angle)
        pose = np.array([[c, -s, 0, 2*f], [s, c, 0, -f], [0, 0, 1, 0], [0, 0, 0, 1]])
        # Independent analytical inverse: fixed world center (20, 4, 1), heading pi/6.
        x, y = 20 - 2*f, 4 + f
        boxes.append(box(f, center=(c*x+s*y, -s*x+c*y, 1), yaw=math.pi/6-angle))
        poses[f] = pose
    assert detect_static_errors(boxes, StaticConfig(), poses) == []
    b = boxes[2]
    boxes[2] = b.replace(center=(b.center[0]+0.6, b.center[1], b.center[2]))
    findings = detect_static_errors(boxes, StaticConfig(), poses)
    assert [(f.frame, f.rule, f.severity) for f in findings] == [(2, "track.static_shift", Severity.ERROR)]
    assert findings[0].value == pytest.approx(0.6)
    assert detect_static_errors(boxes, StaticConfig(), None) == []
    assert detect_static_errors(boxes, StaticConfig(), {0: poses[0], 1: poses[1]}) == []


def test_static_slow_motion_is_not_label_error():
    boxes = [box(f, center=(10 + 0.1*f, 0, 1)) for f in range(8)]
    assert detect_static_errors(boxes, StaticConfig(), {f: np.eye(4) for f in range(8)}) == []


def test_learning_unknown_label_falls_back_to_rule_statistics():
    model = train([Sample("a", "warning", "car", 3 if i%2 else 1, 1,
                          "ok" if i%2 else "fp") for i in range(80)])
    assert model.use_model
    assert model.confidence("a", "warning", "unseen", 100, 1) == model.rule_stats["a"]["precision"]


def test_adjust_severity_boundary_preserves_errors_and_gate():
    from pointsnap.core.config import GateConfig
    from pointsnap.core.model import ErrorType, Finding
    from pointsnap.learn import apply
    model = train([Sample("a", "warning", "car", 1, 1, "fp") for _ in range(20)])
    p = model.rule_stats["a"]["precision"]
    warning = Finding(ErrorType.FIT, "a", Severity.WARNING, 0, "car", "test")
    error = dataclasses.replace(warning, severity=Severity.ERROR)
    assert apply([warning], model, True, p)[0].severity is Severity.WARNING
    assert apply([warning], model, True, p+1e-6, 21)[0].severity is Severity.WARNING
    assert apply([error], model, True, 1)[0].severity is Severity.ERROR
    lowered = apply([warning], model, True, p+1e-6)
    assert gate_verdict(lowered, GateConfig(max_errors=0, max_warnings=0))[0]
    assert not gate_verdict(apply([warning], model, False), GateConfig(max_errors=0, max_warnings=0))[0]


@pytest.mark.parametrize("scenes", [["test"], ["all"], ["scene-0103"]])
def test_training_export_rejects_held_out_scenes(tmp_path, scenes, monkeypatch):
    import argparse
    from pointsnap.cli.eval_cmd import run_critic
    monkeypatch.setattr("pointsnap.cli.eval_cmd.NuScenesReader", lambda _: pytest.fail("held-out reader opened"))
    args = argparse.Namespace(dataroot=tmp_path, scenes=scenes, out=tmp_path / "export", samples_per_box=1, seed=0)
    assert run_critic(args, load_config(env={})) == 3
    assert not args.out.exists()


def test_export_seed_is_independent_of_scene_order_and_does_not_overwrite(tmp_path):
    from pointsnap.critic import export_dataset
    class Reader:
        def annotations(self, scene): return [box()]
        def frames(self, scene):
            frames = DenseFrames()
            frames.num_frames = 1
            return frames
    for name, scenes in (("first", ["a", "b"]), ("second", ["b", "a"])):
        export_dataset(Reader(), scenes, tmp_path / name, samples_per_box=4, seed=11, progress=lambda _: None)
    for scene in ("a", "b"):
        with np.load(tmp_path / f"first/{scene}.npz") as a, np.load(tmp_path / f"second/{scene}.npz") as b:
            for key in a.files:
                np.testing.assert_array_equal(a[key], b[key])
    original = (tmp_path / "first/a.npz").read_bytes()
    with pytest.raises(FileExistsError):
        export_dataset(Reader(), ["a"], tmp_path / "first", progress=lambda _: None)
    assert (tmp_path / "first/a.npz").read_bytes() == original


def test_critic_corrupt_checkpoint_fails_explicitly(tmp_path):
    pytest.importorskip("torch")
    path = tmp_path / "corrupt.pt"
    path.write_bytes(b"not a checkpoint")
    with pytest.raises(RuntimeError):
        critic_findings([box()], DenseFrames(), CriticConfig(model=str(path)))


def test_learning_does_not_compare_cv_loss_from_different_review_dataset():
    samples = [Sample("a", "warning", "car", 3 if i%2 else 1, 1,
                      "ok" if i%2 else "fp") for i in range(80)]
    previous = train(samples)
    previous.cv_logloss_model = 0  # a different older set; incomparable with today's folds
    assert train(samples, previous).use_model


def test_history_collision_refuses_to_discard_active_model(tmp_path):
    _run(tmp_path)
    learn_project(tmp_path)
    active = tmp_path / "learned.json"
    history = tmp_path / "learned-history"
    history.mkdir()
    other = train([]).to_dict()
    (history / "learned-v1.json").write_text(json.dumps(other), encoding="utf-8")
    original = active.read_bytes()
    with pytest.raises(StorageError, match="phiên bản"):
        learn_project(tmp_path)
    assert active.read_bytes() == original
