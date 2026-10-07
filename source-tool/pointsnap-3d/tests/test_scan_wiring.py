"""A6: bộ quét nối ba bộ phát hiện của `pointsnap.detectors` cùng point cloud theo frame."""

import json

import numpy as np

from pointsnap.adapters.cvat.reader import JobData, find_manifest
from pointsnap.cli.common import frames_for_job
from pointsnap.cli.main import EXIT_OK, main
from pointsnap.core.config import load_config
from pointsnap.core.model import Cuboid, FrameData, Severity, add_outside_markers
from pointsnap.core.scanner import actionable, scan_cuboids


class FlatGround:
    """Mặt đất phẳng z = 0, lưới điểm 0,1 m; pose đơn vị, 0,5 s mỗi frame."""

    def __init__(self, extent=10.0, step=0.1):
        axis = np.arange(-extent, extent, step)
        gx, gy = np.meshgrid(axis, axis)
        self.points = np.column_stack([gx.ravel(), gy.ravel(), np.zeros(gx.size)])
        self.calls = []

    def frame_data(self, frame, with_points=True):
        self.calls.append((frame, with_points))
        return FrameData(frame, self.points if with_points else np.empty((0, 3)), np.eye(4), timestamp=frame * 0.5)


def car(frame, bottom=0.0, track_id=1):
    return Cuboid(center=(0.0, 0.0, bottom + 0.8), dims=(4.5, 1.9, 1.6), yaw=0.0, label="car", frame=frame,
                  track_id=track_id, source_id=10 * (track_id or 0) + frame)


def test_scan_runs_floating_only_with_point_cloud():
    config = load_config()
    boxes = [car(0), car(1, bottom=0.4), car(2)]
    frames = FlatGround()
    with_cloud = {(f.rule, f.frame) for f in scan_cuboids(boxes, config, frames)}
    assert ("floating", 1) in with_cloud
    assert any(with_points for _, with_points in frames.calls)  # đã đọc point cloud
    assert not any(f.rule.startswith("floating") for f in scan_cuboids(boxes, config))


def test_scan_accepts_job_or_list_and_info_is_not_actionable():
    config = load_config()
    boxes = [car(0)]
    job = JobData(url="", task_id=1, job_id=1, start_frame=0, stop_frame=0, labels={}, cuboids=boxes)
    assert scan_cuboids(job, config) == scan_cuboids(boxes, config)
    findings = scan_cuboids([car(0, track_id=None)], load_config(), FlatGround())
    assert all(f.severity is not Severity.INFO for f in actionable(findings))


def test_add_outside_markers_like_cvat_upload():
    boxes = add_outside_markers([car(0), car(1), car(4)], 6)
    assert [(b.frame, b.outside) for b in boxes] == [(0, False), (1, False), (2, True), (4, False), (5, True)]


def test_find_manifest_by_task_id(tmp_path):
    export = tmp_path / "scene-0061"
    export.mkdir()
    (export / "manifest.json").write_text("{}", encoding="utf-8")
    (export / "cvat_task.json").write_text(json.dumps({"task_id": 9}), encoding="utf-8")
    assert find_manifest(9, [tmp_path]) == export / "manifest.json"
    assert find_manifest(9, [export]) == export / "manifest.json"
    assert find_manifest(8, [tmp_path, tmp_path / "missing"]) is None


def test_frames_for_job_reports_missing_manifest(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("POINTSNAP_EXPORT_DIR", str(tmp_path / "none"))
    job = JobData(url="", task_id=42, job_id=1, start_frame=0, stop_frame=0, labels={}, cuboids=[])
    frames, note = frames_for_job(job)
    assert frames is None and "task 42" in note


def test_cli_nuscenes_scan_with_injection(tmp_path, capsys):
    import fake_nuscenes

    root = fake_nuscenes.build(tmp_path / "nuscenes")
    out = tmp_path / "out"
    args = ["nuscenes", "--dataroot", str(root), "scan", "--scene", "scene-0001", "--out", str(out)]
    assert main(args) == EXIT_OK
    assert (out / "report_scene-0001.html").is_file()
    assert "TỔNG KẾT QUÉT" in capsys.readouterr().out
    assert main(args + ["--inject", "--rate", "1.0"]) == EXIT_OK
    assert (out / "report_scene-0001_injected.html").is_file()
