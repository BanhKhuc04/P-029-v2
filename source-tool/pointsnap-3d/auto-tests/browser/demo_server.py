"""Máy chủ PointSnap demo cho E2E trình duyệt: dự án + 2 lần quét giả, point cloud tổng hợp, ảnh camera,
CVAT giả trong bộ nhớ (áp dụng / hoàn tác sửa box được xác nhận). Không cần CVAT, nuScenes hay GPU.

python auto-tests/browser/demo_server.py HOME_DIR [PORT]
"""
from __future__ import annotations

import copy
import datetime as dt
import json
import math
import random
import sys
from pathlib import Path

import numpy as np
import uvicorn

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from pointsnap.adapters.cvat.shapes import cuboid_to_points  # noqa: E402
from pointsnap.core.camera import CameraView  # noqa: E402
from pointsnap.core.model import Cuboid, FrameData  # noqa: E402
from pointsnap.core.serialize import save_cuboids  # noqa: E402
import pointsnap.web.preview as preview  # noqa: E402
from pointsnap.web.app import create_app  # noqa: E402

HOME = Path(sys.argv[1])
PORT = int(sys.argv[2]) if len(sys.argv) > 2 else 8765
JOB = 2
GROUND = -1.8
rng = random.Random(4)

# Vật thật (đúng) trong hệ cảm biến, xe thu đứng yên.
TRUE = {
    12: dict(label="car", c=(11.0, -3.2), d=(4.6, 1.95, 1.6), yaw=0.05),
    7: dict(label="car", c=(17.5, 4.0), d=(4.4, 1.85, 1.5), yaw=3.1),
    9: dict(label="truck", c=(24.0, -6.5), d=(7.8, 2.5, 3.1), yaw=0.0),
    4: dict(label="pedestrian", c=(8.0, 5.5), d=(0.7, 0.7, 1.75), yaw=1.2),
    15: dict(label="pedestrian", c=(14.0, -1.4), d=(0.6, 0.6, 1.7), yaw=0.0),
    21: dict(label="car", c=(30.0, 2.5), d=(4.5, 1.9, 1.55), yaw=0.02),
}


def box(tid, frame, dz=0.0, dyaw=0.0, scale=1.0):
    t = TRUE[tid]
    d = (t["d"][0] * scale, t["d"][1], t["d"][2])
    return Cuboid(center=(t["c"][0], t["c"][1], GROUND + d[2] / 2 + dz), dims=d, yaw=t["yaw"] + dyaw,
                  label=t["label"], frame=frame, track_id=tid, source_id=1000 + tid)


ERR = {(12, 18): dict(dz=0.26), (7, 23): dict(dyaw=math.pi), (9, 5): dict(scale=1.75)}
snapshot = []
for tid in TRUE:
    for frame in range(0, 40):
        snapshot.append(box(tid, frame, **ERR.get((tid, frame), {})))


def surface_points(t, n=900):
    (cx, cy), (l, w, h), yaw = t["c"], t["d"], t["yaw"]
    pts = []
    c, s = math.cos(yaw), math.sin(yaw)
    for _ in range(n):
        face = rng.random()
        u, v = rng.uniform(-0.5, 0.5), rng.uniform(0, 1)
        if face < 0.45:
            x, y, z = u * l, -w / 2, v * h
        elif face < 0.7:
            x, y, z = -l / 2, u * w, v * h
        else:
            x, y, z = u * l, rng.uniform(-0.5, 0.5) * w, h * (0.6 + 0.4 * rng.random())
        pts.append((cx + x * c - y * s, cy + x * s + y * c, GROUND + z))
    return pts


ground = []
for r in np.arange(3, 40, 0.9):
    for a in np.arange(-math.pi / 2, math.pi / 2, 0.01):
        ground.append((r * math.cos(a), r * math.sin(a), GROUND + rng.gauss(0, 0.015)))
cloud = np.array(ground + [p for t in TRUE.values() for p in surface_points(t)])


class Frames:
    def frame_data(self, frame, with_points=True):
        return FrameData(frame, cloud if with_points else np.zeros((0, 3)), np.eye(4))

    def camera_views(self, frame):
        # Camera nhìn theo +x, đặt ở (0, 0, 1,8) như xe thu đứng yên ở gốc.
        m = np.eye(4)
        m[:3, :3] = np.array([[0.0, 0.0, 1.0], [-1.0, 0.0, 0.0], [0.0, -1.0, 0.0]])
        m[:3, 3] = [0.0, 0.0, 1.8]
        k = np.array([[1000.0, 0.0, 800.0], [0.0, 1000.0, 450.0], [0.0, 0.0, 1.0]])
        return [CameraView("CAM_FRONT", HOME / "cam.jpg", k, m, 1600, 900)]


def make_camera():
    from PIL import Image, ImageDraw
    img = Image.new("RGB", (1600, 900), (70, 80, 92))
    d = ImageDraw.Draw(img)
    for y in range(450, 900):
        g = int(60 + (y - 450) * 0.12)
        d.line([(0, y), (1600, y)], fill=(g, g, g + 6))
    for y in range(0, 450):
        d.line([(0, y), (1600, y)], fill=(120 + y // 12, 150 + y // 10, 190))
    img.save(HOME / "cam.jpg")


preview.find_manifest = lambda *a, **k: HOME / "manifest.json"
preview.ManifestFrames = lambda *a, **k: Frames()
import pointsnap.web.app as web_app_mod  # noqa: E402
web_app_mod.find_manifest = preview.find_manifest
web_app_mod.ManifestFrames = preview.ManifestFrames


def finding(rule, sev, etype, tid, frame, msg, value=None, threshold=None, details=None, conf=None):
    labels = {"error": "Lỗi", "warning": "Cảnh báo", "info": "Thông tin"}
    etl = {"floating": "Lơ lửng / lún", "size": "Sai kích thước", "heading": "Sai hướng box",
           "fit": "Box lệch khỏi vật", "attribute": "Thiếu / sai thuộc tính"}
    label = TRUE[tid]["label"] if tid in TRUE else "car"
    return dict(rule=rule, severity=sev, severity_label=labels[sev], error_type=etype, error_type_label=etl[etype],
                frame=frame, label=label, track_id=tid, source_id=None, message=msg, value=value,
                threshold=threshold, details=details or {}, confidence=conf,
                cvat_link=f"http://localhost:8080/tasks/2/jobs/{JOB}?frame={frame}")


FINDINGS = [
    finding("floating", "error", "floating", 12, 18, "Đáy box cách mặt đất 26 cm (lơ lửng); cao hơn 25 cm so với các frame khác của track",
            0.26, 0.22, {"ground_z": GROUND, "pitch_deg": 0.8}, 0.91),
    finding("heading.flip", "error", "heading", 7, 23, "Hướng box lệch 178° so với các keyframe lân cận của track", 178, 60, None, 0.88),
    finding("size.class_range", "warning", "size", 9, 5, "Chiều dài 13.65 m lớn bất thường so với class truck", 13.65, 12.0),
    finding("fit.outside", "warning", "fit", 4, 30, "40/60 điểm của vật nằm ngoài box", 0.66, 0.4),
    finding("spec.inside", "error", "attribute", 15, 12, "Box Pedestrian nằm bên trong box Vehicle (spec 4.3B)", 3, 1),
    finding("attr.missing", "error", "attribute", 21, 0, "Thiếu thuộc tính bắt buộc vehicle_state ở 4 keyframe (spec 3.1.3)", 4, 0),
    finding("heading.motion", "warning", "heading", 21, 14, "Hướng box ngược 172° so với hướng chuyển động", 172, 90),
    finding("floating.no_evidence", "info", "floating", 4, 2, "Không đủ điểm mặt đất quanh box để kết luận (thiếu bằng chứng)", 3, 10),
    finding("fit.overlap", "error", "fit", 15, 33, "Hai box chồng nhau 72% thể tích: nghi vẽ trùng một vật", 0.72, 0.5),
    finding("heading.points", "warning", "heading", 12, 26, "Trục box lệch 14° so với trục cụm điểm LiDAR", 14, 10),
]
for i in range(22):
    tid = rng.choice(list(TRUE))
    fr = rng.randrange(40)
    FINDINGS.append(finding("size.in_track", "warning" if i % 3 else "info", "size", tid, fr,
                            f"Chiều rộng box lệch {rng.randint(6, 18)}% so với trung vị của track", 0.12, 0.10))
FINDINGS.append(dict(finding("track.jump", "error", "floating", 12, 3, "track cũ — phải bị lọc"), error_type="track"))


def write_run(run_id, ts, findings, flagged):
    run = HOME / "projects/demo/runs" / run_id
    run.mkdir(parents=True, exist_ok=True)
    errs = sum(f["severity"] == "error" and not f["rule"].startswith("track.") for f in findings)
    warns = sum(f["severity"] == "warning" for f in findings)
    infos = sum(f["severity"] == "info" for f in findings)
    (run / "summary.json").write_text(json.dumps(dict(
        job_id=JOB, timestamp=ts, num_boxes=len(snapshot), num_errors=errs, num_warnings=warns, num_info=infos,
        gate_passed=errs == 0 and warns <= 10, gate_reasons=[f"{errs} Lỗi > tối đa 0", f"{warns} Cảnh báo > tối đa 10"],
        flagged=flagged, cvat_url="http://localhost:8080"), ensure_ascii=False), encoding="utf-8")
    (run / "findings.json").write_text(json.dumps(findings, ensure_ascii=False), encoding="utf-8")
    save_cuboids(run / "snapshot.json", snapshot, {"task_id": 2, "url": "http://localhost:8080"})


class FakeCvat:
    """CVAT trong bộ nhớ đủ cho áp dụng / hoàn tác sửa box (đọc lại xác nhận)."""

    def __init__(self):
        tracks = {}
        for c in snapshot:
            t = tracks.setdefault(c.track_id, {"id": c.track_id, "label_id": 1, "frame": 0, "group": 0,
                                               "source": "manual", "attributes": [], "shapes": []})
            t["shapes"].append({"type": "cuboid", "frame": c.frame, "points": cuboid_to_points(c), "occluded": False,
                                "outside": False, "keyframe": True, "attributes": [], "z_order": 0, "rotation": 0.0})
        self.data = {"version": 1, "tags": [], "shapes": [], "tracks": list(tracks.values())}

    def get_job_annotations(self, job_id):
        return copy.deepcopy(self.data)

    def patch_job_annotations(self, job_id, payload, action="update"):
        for nt in payload.get("tracks", []):
            for i, t in enumerate(self.data["tracks"]):
                if t["id"] == nt["id"]:
                    self.data["tracks"][i] = copy.deepcopy(nt)
        self.data["version"] += 1
        return {}


if __name__ == "__main__":
    HOME.mkdir(parents=True, exist_ok=True)
    make_camera()
    app = create_app(HOME)
    pm = app.state.pm
    if not any(p["slug"] == "demo" for p in pm.list_projects()):
        pm.create_project(name="scene-0103 · CVAT local", slug="demo", description="Demo PointSnap")
    now = dt.datetime.now()
    write_run(f"{(now - dt.timedelta(hours=3)):%Y%m%d-%H%M%S}-001-job{JOB}", (now - dt.timedelta(hours=3)).isoformat(),
              FINDINGS + FINDINGS[:8], False)
    write_run(f"{now:%Y%m%d-%H%M%S}-002-job{JOB}", now.isoformat(), FINDINGS, True)
    app.state.cvat_client = FakeCvat()
    uvicorn.run(app, host="127.0.0.1", port=PORT, log_level="warning")
