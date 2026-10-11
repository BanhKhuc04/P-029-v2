"""Hồi quy phần 01: gate không chứng nhận lần quét thiếu dữ liệu."""

import argparse
import dataclasses
import json
from types import SimpleNamespace

import numpy as np
import pytest

from pointsnap.adapters.cvat.reader import JobData
from pointsnap.cli import gate_cmd
from pointsnap.core.config import GateConfig, load_config
from pointsnap.core.gate import gate_verdict
from pointsnap.core.model import ErrorType, Finding, Severity
from pointsnap.core.scanner import scan_coverage_gaps, scan_cuboids
from pointsnap.web.projects import ProjectManager
from pointsnap.web.runner import ScanRunner
from test_scan_wiring import FlatGround, car


def job_data():
    return JobData(url="http://cvat", task_id=1, job_id=1, start_frame=0, stop_frame=2,
                   labels={}, cuboids=[car(0), car(1), car(2)])


def size_only_config():
    config = load_config(env={})
    rules = dataclasses.replace(config.rules, **{
        field.name: field.name.startswith("size_") for field in dataclasses.fields(config.rules)
    })
    return dataclasses.replace(config, rules=rules)


class NoPose(FlatGround):
    def frame_data(self, frame, with_points=True):
        data = super().frame_data(frame, with_points)
        return dataclasses.replace(data, sensor_to_world=None if frame == 1 else data.sensor_to_world)


@pytest.mark.parametrize("frames,expected", [(None, "point cloud"), (NoPose(), "pose"), (FlatGround(), None)])
def test_coverage_requires_cloud_and_pose_for_enabled_rules(frames, expected):
    job = job_data()
    config = load_config(env={})
    gaps = scan_coverage_gaps(job, config, frames)
    passed, reasons = gate_verdict([], config.gate, coverage_gaps=gaps)
    assert passed is (expected is None)
    assert (not reasons) if expected is None else any(expected in reason for reason in reasons)


def test_disabled_rules_do_not_require_lidar_or_pose():
    job, config = job_data(), size_only_config()
    assert scan_coverage_gaps(job, config, None) == []
    assert gate_verdict(scan_cuboids(job, config), config.gate) == (True, [])


def test_sparse_ground_blocks_gate_without_becoming_a_cvat_error_flag():
    frames = FlatGround()
    frames.points = np.empty((0, 3))
    config = load_config(env={})
    findings = scan_cuboids(job_data(), config, frames)
    assert any(f.rule == "floating.no_evidence" and f.severity is Severity.INFO for f in findings)
    passed, reasons = gate_verdict(findings, GateConfig(max_errors=100, max_warnings=100))
    assert not passed
    assert any("floating.no_evidence" in reason for reason in reasons)


def test_gate_counts_warnings_in_a_generator():
    findings = (Finding(ErrorType.SIZE, "size.in_track", Severity.WARNING, i, "car", "warning") for i in range(2))
    passed, reasons = gate_verdict(findings, GateConfig(max_errors=0, max_warnings=1))
    assert not passed and "Số cảnh báo (2)" in reasons[0]


@pytest.mark.parametrize("frames,config_factory,expected", [
    (None, lambda: load_config(env={}), 1),
    (NoPose(), lambda: load_config(env={}), 1),
    (None, size_only_config, 0),
])
def test_cli_gate_reports_partial_checks(monkeypatch, capsys, frames, config_factory, expected):
    monkeypatch.setattr(gate_cmd, "CvatClient", lambda *args: object())
    monkeypatch.setattr(gate_cmd, "load_job", lambda *args: job_data())
    monkeypatch.setattr(gate_cmd, "frames_for_job", lambda *args: (frames, "test data"))
    config = dataclasses.replace(config_factory(), gate=GateConfig(max_errors=100, max_warnings=100))
    assert gate_cmd.run(argparse.Namespace(job=1), config) == expected
    output = capsys.readouterr().out
    assert ("Kiểm tra một phần" in output) is (expected == 1)


def test_cli_gate_frame_read_failure_is_runtime_error(monkeypatch, capsys):
    class BrokenFrames:
        def frame_data(self, *args, **kwargs):
            raise FileNotFoundError("missing lidar.bin")

    monkeypatch.setattr(gate_cmd, "CvatClient", lambda *args: object())
    monkeypatch.setattr(gate_cmd, "load_job", lambda *args: job_data())
    monkeypatch.setattr(gate_cmd, "frames_for_job", lambda *args: (BrokenFrames(), "test data"))
    assert gate_cmd.run(argparse.Namespace(job=1), load_config(env={})) == 3
    assert "missing lidar.bin" in capsys.readouterr().err


@pytest.mark.parametrize("frames,config_factory,expected", [
    (None, lambda: load_config(env={}), False),
    (NoPose(), lambda: load_config(env={}), False),
    (None, size_only_config, True),
])
def test_web_gate_persists_coverage_gaps(tmp_path, monkeypatch, frames, config_factory, expected):
    from pointsnap.web import runner as module

    pm = ProjectManager(tmp_path / "home")
    pm.create_project(name="Coverage", slug="coverage")
    config = dataclasses.replace(config_factory(), gate=GateConfig(max_errors=100, max_warnings=100))
    monkeypatch.setattr(pm, "get_effective_config", lambda slug: config)
    monkeypatch.setattr(module, "CvatClient", lambda *args: SimpleNamespace(url="http://cvat"))
    monkeypatch.setattr(module, "load_job", lambda *args: job_data())
    monkeypatch.setattr(module, "frames_for_job", lambda *args, **kwargs: (frames, "test data"))
    runner = ScanRunner(pm)
    run_id = runner.start_scan("coverage", 1)
    runner._executor.shutdown(wait=True)
    run = runner.get_run("coverage", run_id)
    assert run["status"] == "done"
    assert run["summary"]["gate_passed"] is expected
    assert bool(run["summary"]["coverage_gaps"]) is (not expected)
    saved = json.loads((pm.projects_dir / "coverage" / "runs" / run_id / "summary.json").read_text(encoding="utf-8"))
    assert saved == run["summary"]
