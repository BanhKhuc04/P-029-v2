"""Read-only, detector-independent guides and evaluation of unsaved CVAT geometry.

Nothing in this module writes annotations. References are measurements, never repairs.
"""
from __future__ import annotations

from urllib.parse import urlsplit

import math
from types import SimpleNamespace
from typing import Any

import numpy as np
from fastapi import HTTPException
from pydantic import BaseModel, Field, ConfigDict, field_validator

from pointsnap.core.model import Cuboid
from pointsnap.core.serialize import load_cuboids
from pointsnap.core.scanner import (
    check_floating, check_size, check_heading, check_box_points, check_static, is_rule_enabled,
)
from pointsnap.detectors.size import get_resolved_class_ranges, range_key
from pointsnap.adapters.cvat.reader import ManifestFrames, find_manifest
from pointsnap.cli.common import export_dirs


class DraftBox(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    center: tuple[float, float, float]
    dims: tuple[float, float, float]
    rotation: tuple[float, float, float] = (0, 0, 0)
    frame: int = Field(ge=0)
    label: str = Field(min_length=1, max_length=200)
    track_id: int | None = Field(default=None, ge=0)
    source_id: int | None = Field(default=None, ge=0)
    attrs: dict[str, Any] = Field(default_factory=dict)
    outside: bool = False
    keyframe: bool = True

    @field_validator("dims")
    @classmethod
    def positive_dims(cls, value):
        if min(value) <= 0:
            raise ValueError("Kích thước phải dương")
        return value

    def cuboid(self):
        return Cuboid(center=self.center, dims=self.dims, yaw=self.rotation[2], frame=self.frame,
                      label=self.label, track_id=self.track_id, source_id=self.source_id,
                      outside=self.outside, keyframe=self.keyframe,
                      attrs={**self.attrs, "cvat_rx": self.rotation[0], "cvat_ry": self.rotation[1]})


class EvaluateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    box: DraftBox
    context: list[DraftBox] = Field(default_factory=list, max_length=10000)
    context_complete: bool = False
    revision: int = Field(default=0, ge=0)


def geometry(box: Cuboid) -> dict:
    return {"center": list(box.center), "dims": list(box.dims),
            "rotation": [float(box.attrs.get("cvat_rx", 0)), float(box.attrs.get("cvat_ry", 0)), box.yaw]}


def matches(box: Cuboid, finding: dict) -> bool:
    if box.frame != finding.get("frame"):
        return False
    tid, sid = finding.get("track_id"), finding.get("source_id")
    return box.track_id == tid if tid is not None else sid is not None and box.track_id is None and box.source_id == sid


def finite(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


class GuideService:
    def __init__(self, pm, runner, state):
        self.pm, self.runner, self.state = pm, runner, state

    def load(self, slug, run_id, index):
        run = self.runner.get_run(slug, run_id, include_findings=True)
        findings = run.get("findings", [])
        if index < 0 or index >= len(findings):
            raise HTTPException(404, "Không có mục lỗi này")
        project = self.pm.get_project(slug)
        folder = self.runner.run_dir(slug, run_id)
        boxes, meta = [], {}
        if (folder / "snapshot.json").is_file():
            boxes, meta = load_cuboids(folder / "snapshot.json")
        source = (run.get("summary") or {}).get("cvat_url") or meta.get("url")
        def origin(value):
            parts=urlsplit(value)
            host="localhost" if parts.hostname in ("localhost","127.0.0.1","::1") else parts.hostname
            return parts.scheme,host,parts.port or (443 if parts.scheme=="https" else 80),parts.path.rstrip("/")
        if source and origin(source)!=origin(project["cvat_url"]):
            raise HTTPException(409,"Nguồn CVAT đã đổi; quét lại trước khi dùng hướng dẫn cũ.")
        frames = getattr(self.state, "guide_frames", None)
        if frames is None:
            try:
                manifest = find_manifest(meta.get("task_id"), export_dirs(project.get("export_dirs") or None), url=project["cvat_url"])
                if manifest:
                    frames = ManifestFrames(manifest, dataroot=project.get("nuscenes_root") or None)
            except (ValueError, OSError, KeyError):
                pass
        return run, findings[index], boxes, frames, self.pm.get_effective_config(slug), project

    def guide(self, slug, run_id, index):
        run, finding, boxes, frames, cfg, project = self.load(slug, run_id, index)
        box = next((b for b in boxes if matches(b, finding)), None)
        rule = finding.get("rule", "")
        details = finding.get("details") if isinstance(finding.get("details"), dict) else {}
        result = {"schema_version": 1, "identity": {"cvat_origin": project["cvat_url"].rstrip("/"),
                  "job_id": run["job_id"], "frame": finding["frame"], "project_slug": slug, "run_id": run_id, "finding_index": index,
                  "kind": "track" if finding.get("track_id") is not None else "shape",
                  "server_id": finding.get("track_id") if finding.get("track_id") is not None else finding.get("source_id")},
                  "rule": rule, "evidence": "insufficient", "baseline": geometry(box) if box else None,
                  "reference": {}, "thresholds": {}, "points": [], "face": details.get("face") or details.get("side"),
                  "preferred_view": "side" if rule.startswith("floating") else "top",
                  "instruction": "Kéo box bằng CVAT; đối chiếu số đo và ảnh camera.",
                  "message": finding.get("message", ""), "missing": False}
        if box is None:
            # Missing-object evidence has no annotation identity. Display only its measured region.
            from pointsnap.web.preview import _missing_box
            candidate = _missing_box(finding)
            if candidate is not None and candidate.frame == finding["frame"]:
                result.update(baseline=geometry(candidate), missing=True,
                              instruction="Vùng nghi sót đối tượng · dùng công cụ Cuboid của CVAT để vẽ.")
            return result
        peers = [b for b in boxes if box.track_id is not None and b.track_id == box.track_id
                 and b.frame != box.frame and b.visible and b.keyframe and b.label == box.label]
        if rule == "floating" and finite(details.get("ground_z")) and finite(details.get("num_ground_points")) and details["num_ground_points"] >= cfg.floating.min_ground_points:
            ground = float(details["ground_z"])
            target = box.bottom_z - (float(details["distance"]) - float(details.get("track_median_distance", 0))) if finite(details.get("distance")) else ground
            result["reference"] = {"ground_z": ground, "bottom_z": target,
                                   "pitch_deg": details.get("pitch_deg") if finite(details.get("pitch_deg")) else 0}
            result["thresholds"] = {"distance_m": cfg.floating.warning_m}
            result.update(evidence="measured", instruction="Kéo lên/xuống · theo dõi thước đáy và đường mặt đất.")
        elif rule.startswith("size."):
            resolved = get_resolved_class_ranges(cfg.size)
            ranges = resolved.get(range_key(box, cfg.size, resolved), {})
            if rule == "size.in_track" and len(peers) >= cfg.size.in_track.min_keyframes - 1:
                result["reference"]["dims"] = np.median([p.dims for p in peers], axis=0).tolist()
                result["thresholds"]["dims_m"] = [max(cfg.size.in_track.warning_abs_m, cfg.size.in_track.warning_rel*d) for d in result["reference"]["dims"]]
            if rule == "size.class_range" and ranges:
                margin = cfg.size.class_range.warning_margin
                result["reference"]["ranges"] = {k: [lo*(1-margin), hi*(1+margin)] for k, (lo,hi) in ranges.items()}
            if result["reference"]:
                result["evidence"] = "measured"
            result["instruction"] = "Kéo mặt/cạnh box · thước đỏ chỉ chiều đang vượt tham chiếu."
        elif rule.startswith("heading.") and finite(details.get("target_yaw_sensor")) and not details.get("maybe_reversing"):
            result["reference"] = {"yaw": details["target_yaw_sensor"]}
            result.update(evidence="measured", instruction="Xoay box · so trục hiện tại với hướng tham chiếu.")
        elif rule.startswith("attr.") or rule.startswith("spec.") or rule == "cam.class":
            result["instruction"] = "Chọn box · sửa Nhãn/Thuộc tính trong thanh Objects của CVAT."
        if frames is not None and rule.startswith(("fit.", "heading.points")):
            result["thresholds"]["clearance_m"] = cfg.fit.loose_warning_m
            try:
                from pointsnap.core.box_points import box_point_sets
                frame_boxes = [b for b in boxes if b.frame == box.frame and b.visible]
                items = box_point_sets(frames.frame_data(box.frame).points, frame_boxes,
                                      margin=cfg.fit.outside_margin_m, clearance=cfg.fit.ground_clearance_m,
                                      margin_rel=cfg.fit.outside_margin_rel)
                item = next(i for i in items if matches(i.box, finding))
                local = item.local
                if len(local):
                    c, s = math.cos(box.yaw), math.sin(box.yaw)
                    world = local @ np.array([[c, s, 0], [-s, c, 0], [0, 0, 1]]) + box.center
                    step = max(1, math.ceil(len(world) / 4000))
                    result["points"] = np.round(world[::step], 4).tolist()
                    result["evidence"] = "measured"
                    result["instruction"] = "Kéo mặt box · điểm đỏ đang nằm ngoài; thước hiển thị khoảng dư/hụt."
            except (ValueError, OSError, KeyError, StopIteration):
                pass
        return result

    def evaluate(self, slug, run_id, index, request: EvaluateRequest):
        run, finding, baseline, frames, cfg, _ = self.load(slug, run_id, index)
        box = request.box.cuboid()
        output = {"revision": request.revision, "state": "insufficient", "findings": [],
                  "message": "Chưa đủ bằng chứng để kết luận lỗi đang xét."}
        if not matches(box, finding):
            raise HTTPException(409, "Đối tượng/frame không khớp mục lỗi; chọn lại lỗi sau khi Save")
        if not request.context_complete or not box.visible or not box.keyframe:
            return output
        rule = finding.get("rule", "")
        supported = {"floating", "size.class_range", "size.in_track", "heading.flip", "heading.motion",
                     "heading.points", "heading.static", "fit.empty", "fit.outside", "fit.loose", "fit.overlap"}
        if rule not in supported or not is_rule_enabled(rule, cfg):
            return output
        context = [b.cuboid() for b in request.context]
        context = [b for b in context if not matches(b, finding)] + [box]
        # Core rules assume yaw-only geometry; preserve tilt and decline certification.
        if any(abs(float(b.attrs.get(k, 0))) > 1e-6 for b in context for k in ("cvat_rx", "cvat_ry")):
            output["message"] = "Box có roll/pitch · số đo 3D vẫn hiện, chưa kết luận bằng luật chỉ hỗ trợ yaw."
            return output
        peers = [b for b in context if box.track_id is not None and b.track_id == box.track_id and b.visible and b.keyframe]
        if rule == "size.class_range":
            resolved = get_resolved_class_ranges(cfg.size)
            if range_key(box, cfg.size, resolved) not in resolved:
                return output
        if rule == "size.in_track" and (len(peers) < cfg.size.in_track.min_keyframes or box.label in cfg.size.in_track.excluded_classes):
            return output
        if rule.startswith("heading.") and rule != "heading.points" and len(peers) < 3:
            return output
        if rule in ("heading.flip", "heading.motion") and cfg.heading.group_for(box.label) is None:
            return output
        if rule == "heading.static" and (len(peers) < cfg.static.min_keyframes or box.label in cfg.static.yaw_excluded_classes):
            return output
        cloud_required = rule == "floating" or rule.startswith("fit.") and rule != "fit.overlap" or rule == "heading.points"
        if cloud_required:
            if frames is None:
                return output
            try:
                pts = frames.frame_data(box.frame).points
                if pts is None or len(pts) < 15:
                    return output
                from pointsnap.core.ground import ring_ground_for_box
                estimate = ring_ground_for_box(pts, box, min_ground_points=cfg.floating.min_ground_points if rule == "floating" else 15)
                if not estimate.is_valid:
                    return output
                if rule != "floating":
                    from pointsnap.core.box_points import box_point_sets
                    item = next(i for i in box_point_sets(pts, [b for b in context if b.frame == box.frame and b.visible],
                                margin=cfg.fit.outside_margin_m, clearance=cfg.fit.ground_clearance_m,
                                margin_rel=cfg.fit.outside_margin_rel) if matches(i.box, finding))
                    minimum = cfg.heading.points.min_points if rule == "heading.points" else cfg.fit.loose_min_points if rule == "fit.loose" else cfg.fit.outside_min_object_points
                    if rule != "fit.empty" and item.num_object_points < minimum:
                        return output
                    if rule == "heading.points" and (box.label not in cfg.heading.points.classes or box.length < cfg.heading.points.min_aspect*box.width or item.range_m > cfg.heading.points.max_range_m):
                        return output
                    if rule == "fit.loose" and item.range_m > cfg.fit.loose_max_range_m:
                        return output
                if rule == "floating" and box.label not in cfg.floating.classes:
                    return output
            except (OSError, KeyError, ValueError, StopIteration):
                return output
        if rule.startswith("heading.") and rule != "heading.points":
            try:
                if frames is None or any(frames.frame_data(b.frame, with_points=False).sensor_to_world is None for b in peers):
                    return output
                if rule == "heading.motion":
                    group = cfg.heading.group_for(box.label)
                    if group is None or (finding.get("details") or {}).get("maybe_reversing"):
                        return output
                    # A stationary object cannot prove a motion heading correct.
                    from pointsnap.detectors.heading import _world
                    poses = {b.frame: frames.frame_data(b.frame, with_points=False).sensor_to_world for b in peers}
                    centers, _ = _world(peers, poses)
                    if np.ptp(centers, axis=0).max() < 0.5:
                        return output
            except (OSError, ValueError, KeyError):
                return output
        job = SimpleNamespace(cuboids=context)
        detector = check_floating if rule == "floating" else check_size if rule.startswith("size.") else check_static if rule == "heading.static" else check_box_points if rule.startswith("fit.") or rule == "heading.points" else check_heading
        try:
            if rule == "floating":
                from pointsnap.detectors.floating import estimate_scene_ground, floating_findings_by_track
                estimates = estimate_scene_ground(context, frames, cfg.floating)
                current = next((est for candidate, est in estimates if matches(candidate, finding)), None)
                valid_peers = [est for candidate, est in estimates if candidate.track_id == box.track_id
                               and box.track_id is not None and candidate.label == box.label and candidate.frame != box.frame and est.is_valid]
                if current is None or not current.is_valid or not cfg.floating.single_box and len(valid_peers) < cfg.floating.min_track_boxes:
                    return output
                findings = floating_findings_by_track(estimates, cfg.floating)
            else:
                findings = detector(job, cfg, frames)
        except (OSError, ValueError, KeyError) as exc:
            output["message"] = "Không đọc đủ dữ liệu kiểm tra; tiếp tục sửa tay hoặc quét lại."
            return output
        # Class-size findings represent an entire track and may move to another keyframe after an edit.
        active = [f for f in findings if (f.track_id == box.track_id if rule == "size.class_range" and box.track_id is not None else matches(f, finding))
                  and (f.rule == rule or rule == "floating" and f.rule == "floating.no_evidence")]
        if any(f.rule.endswith("no_evidence") for f in active):
            return output
        output.update(state="remaining" if active else "cleared",
                      findings=[{"rule": f.rule, "message": f.message, "severity": f.severity.value} for f in active],
                      message="Còn lỗi đang xét" if active else "Hết lỗi đang xét · chưa Save")
        return output
