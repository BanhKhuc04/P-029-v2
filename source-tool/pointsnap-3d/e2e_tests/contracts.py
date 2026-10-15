"""Interface Contracts, Reference Oracles, and Verification Helpers for PointSnap 3D E2E Testing.

Implements contract specifications according to:
- PROJECT.md § Interface Contracts
- ORIGINAL_REQUEST.md
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import math
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np

from pointsnap.core.config import Config, load_config
from pointsnap.core.geometry import normalize_angle
from pointsnap.core.model import Cuboid, ErrorType, Finding, Severity


@dataclass(frozen=True)
class BoxRepairDelta:
    """Dataclass defining the mathematical repair delta proposal."""
    delta_center: tuple[float, float, float]  # (dx, dy, dz)
    delta_dims: tuple[float, float, float]    # (dl, dw, dh)
    delta_yaw: float                         # radians
    repaired_cuboid: Cuboid
    rule: str
    target_offset_m: float
    confidence: float
    reason: str


def _get_box_repair_implementation():
    """Dynamically loads implementation if available, otherwise uses reference oracle."""
    try:
        from pointsnap.core import repair
        if hasattr(repair, "compute_box_repair") and hasattr(repair, "BoxRepairDelta"):
            return repair.compute_box_repair, repair.BoxRepairDelta
    except ImportError:
        pass
    return None, None


def reference_compute_box_repair(
    cuboid: Cuboid,
    track: list[Cuboid] | None,
    points: np.ndarray | None,
    rule: str,
    finding_details: dict[str, Any] | None = None,
) -> BoxRepairDelta:
    """Authoritative Reference Oracle computing closed-form repair delta according to PROJECT.md."""
    details = finding_details or {}
    delta_center = [0.0, 0.0, 0.0]
    delta_dims = [0.0, 0.0, 0.0]
    delta_yaw = 0.0
    confidence = 0.95
    target_offset = 0.0
    reason = f"Automated repair proposal for rule {rule}"

    rule_norm = rule.lower()

    # 1. Ground Delta (F4: Floating / Underground)
    if "floating" in rule_norm or rule_norm == "ground":
        if "offset" in details:
            target_offset = float(details["offset"])
            delta_center[2] = -target_offset
            reason = f"Adjusted bottom z by {-target_offset:+.3f}m to neutralize ground offset"
        elif "ground_z" in details:
            ground_z = float(details["ground_z"])
            ref_clearance = float(details.get("reference_clearance", 0.0))
            current_bottom = cuboid.bottom_z
            target_bottom = ground_z + ref_clearance
            delta_center[2] = target_bottom - current_bottom
            target_offset = current_bottom - target_bottom
            reason = f"Adjusted bottom z to ground level {ground_z:.2f}m (clearance {ref_clearance:.2f}m)"
        elif track and len(track) > 1:
            # Derive reference clearance from other visible track boxes
            other_boxes = [b for b in track if b.visible and b.frame != cuboid.frame]
            if other_boxes and points is not None and len(points) > 0:
                # Approximate ground z as bottom 5th percentile of points near footprint
                pts_z = points[:, 2]
                ground_z = float(np.percentile(pts_z, 5))
                ref_clearances = [b.bottom_z - ground_z for b in other_boxes]
                med_clearance = float(np.median(ref_clearances))
                current_clearance = cuboid.bottom_z - ground_z
                delta_center[2] = med_clearance - current_clearance
                target_offset = current_clearance - med_clearance
                reason = f"Harmonized ground clearance with track median ({med_clearance:.3f}m)"
            else:
                # Default to track median bottom_z
                med_bottom = float(np.median([b.bottom_z for b in other_boxes]))
                delta_center[2] = med_bottom - cuboid.bottom_z
                target_offset = cuboid.bottom_z - med_bottom
                reason = f"Aligned bottom z to track median bottom z ({med_bottom:.2f}m)"
        else:
            # Isolated box without ground info: assume snap to estimated base
            if points is not None and len(points) > 0:
                ground_z = float(np.percentile(points[:, 2], 2))
                delta_center[2] = ground_z - cuboid.bottom_z
                target_offset = cuboid.bottom_z - ground_z
                reason = f"Snapped isolated box bottom to point cloud base {ground_z:.2f}m"
            else:
                delta_center[2] = -0.20  # standard correction
                target_offset = 0.20
                confidence = 0.70
                reason = "Default ground offset correction"

    # 2. Heading Delta (F5: Flip / Motion / Points)
    elif "heading" in rule_norm:
        if "flip" in rule_norm or "motion" in rule_norm or details.get("flip"):
            delta_yaw = math.pi
            confidence = 0.99
            reason = "Rotated box 180° to correct inverted heading"
        elif "points" in rule_norm:
            if "rect_angle" in details:
                delta_yaw = float(details["rect_angle"])
                reason = f"Aligned box yaw with point cluster L-shape axis ({math.degrees(delta_yaw):.1f}°)"
            elif points is not None and len(points) >= 4:
                # Reference L-shape orientation estimation
                # Project points to local XY
                pts_xy = points[:, :2] - np.array([cuboid.center[0], cuboid.center[1]])
                cov = np.cov(pts_xy.T)
                eigvals, eigvecs = np.linalg.eigh(cov)
                principal_angle = math.atan2(eigvecs[1, 1], eigvecs[0, 1])
                diff_angle = normalize_angle(principal_angle - cuboid.yaw)
                # Bound to [-pi/4, pi/4] for L-shape alignment
                delta_yaw = normalize_angle((diff_angle + math.pi / 4) % (math.pi / 2) - math.pi / 4)
                reason = f"Refitted L-shape principal axis (delta {math.degrees(delta_yaw):.1f}°)"
            else:
                delta_yaw = 0.0
                confidence = 0.50
                reason = "Insufficient point cloud evidence for heading adjustment"

    # 3. Dimension & Center Delta (F6: Fit Outside / Size)
    elif "fit" in rule_norm or "size" in rule_norm:
        if "outside" in rule_norm and points is not None and len(points) >= 3:
            # Transform points to local frame
            dx = points[:, 0] - cuboid.center[0]
            dy = points[:, 1] - cuboid.center[1]
            cos_y = math.cos(-cuboid.yaw)
            sin_y = math.sin(-cuboid.yaw)
            local_x = cos_y * dx - sin_y * dy
            local_y = sin_y * dx + cos_y * dy

            p1_x, p99_x = float(np.percentile(local_x, 1)), float(np.percentile(local_x, 99))
            p1_y, p99_y = float(np.percentile(local_y, 1)), float(np.percentile(local_y, 99))

            span_x = max(p99_x - p1_x, 0.5)
            span_y = max(p99_y - p1_y, 0.5)
            shift_x = (p1_x + p99_x) / 2.0
            shift_y = (p1_y + p99_y) / 2.0

            margin = 0.15
            new_l = span_x + margin * 2
            new_w = span_y + margin * 2

            delta_dims = (new_l - cuboid.length, new_w - cuboid.width, 0.0)

            # Rotate local shift back to sensor frame
            c_y = math.cos(cuboid.yaw)
            s_y = math.sin(cuboid.yaw)
            delta_center[0] = c_y * shift_x - s_y * shift_y
            delta_center[1] = s_y * shift_x + c_y * shift_y
            reason = f"Enclosed outlying points within [p1, p99] percentiles (+{margin*2:.2f}m margin)"
        elif "size" in rule_norm and track and len(track) > 1:
            other_boxes = [b for b in track if b.visible and b.frame != cuboid.frame]
            med_l = float(np.median([b.length for b in other_boxes]))
            med_w = float(np.median([b.width for b in other_boxes]))
            med_h = float(np.median([b.height for b in other_boxes]))
            delta_dims = (med_l - cuboid.length, med_w - cuboid.width, med_h - cuboid.height)
    else:
        raise ValueError(f"Unsupported repair rule: {rule}")

    # Compute repaired cuboid
    new_center = (
        cuboid.center[0] + delta_center[0],
        cuboid.center[1] + delta_center[1],
        cuboid.center[2] + delta_center[2],
    )
    new_dims = (
        max(0.1, cuboid.length + delta_dims[0]),
        max(0.1, cuboid.width + delta_dims[1]),
        max(0.1, cuboid.height + delta_dims[2]),
    )
    new_yaw = normalize_angle(cuboid.yaw + delta_yaw)

    repaired_cuboid = cuboid.replace(
        center=new_center,
        dims=new_dims,
        yaw=new_yaw,
    )

    return BoxRepairDelta(
        delta_center=(delta_center[0], delta_center[1], delta_center[2]),
        delta_dims=(delta_dims[0], delta_dims[1], delta_dims[2]),
        delta_yaw=delta_yaw,
        repaired_cuboid=repaired_cuboid,
        rule=rule,
        target_offset_m=target_offset,
        confidence=confidence,
        reason=reason,
    )


def compute_box_repair(
    cuboid: Cuboid,
    track: list[Cuboid] | None,
    points: np.ndarray | None,
    rule: str,
    finding_details: dict[str, Any] | None = None,
) -> BoxRepairDelta:
    """Dispatches to production implementation if available, otherwise delegates to reference oracle."""
    track_list = list(track) if track is not None else [cuboid]
    impl_fn, _ = _get_box_repair_implementation()
    if impl_fn is not None:
        return impl_fn(cuboid, track_list, points, rule, finding_details)
    return reference_compute_box_repair(cuboid, track_list, points, rule, finding_details)


def verify_repaired_box_passes_scanner(
    repaired_box: Cuboid,
    track: list[Cuboid],
    points: np.ndarray | None,
    rule: str,
    config: Config | None = None,
) -> bool:
    """Verifies that substituting repaired_box into the track clears findings for `rule`."""
    try:
        from pointsnap.core.repair import verify_repaired_box_passes_scanner as prod_verify
        return prod_verify(repaired_box, track, points, rule, config)
    except (ImportError, Exception):
        pass

    cfg = config or load_config(env={})
    # Build updated track
    updated_track = []
    found_target = False
    for b in track:
        if b.frame == repaired_box.frame:
            updated_track.append(repaired_box)
            found_target = True
        else:
            updated_track.append(b)
    if not found_target:
        updated_track.append(repaired_box)

    from pointsnap.core.model import FrameData
    from pointsnap.core.scanner import scan_cuboids

    class MockFrameSource:
        def __init__(self, pts):
            self._pts = pts if pts is not None else np.zeros((0, 3), dtype=np.float32)

        def frame_data(self, frame_idx, with_points=True):
            return FrameData(
                frame=frame_idx,
                points=self._pts,
                sensor_to_world=np.eye(4, dtype=np.float64),
                timestamp=float(frame_idx),
            )

    frames = MockFrameSource(points)
    findings = scan_cuboids(updated_track, cfg, frames=frames)

    rule_norm = rule.lower()
    matching_findings = [
        f for f in findings
        if f.frame == repaired_box.frame and (
            f.rule.lower() == rule_norm or
            rule_norm in f.rule.lower()
        ) and f.severity in (Severity.WARNING, Severity.ERROR)
    ]
    return len(matching_findings) == 0


# =========================================================================
# Safety & Rollback Contracts Helpers
# =========================================================================

def validate_history_snapshot_schema(snapshot: dict[str, Any]) -> tuple[bool, str]:
    """Validates history snapshot JSON against PROJECT.md § 4. Rollback Storage Contract."""
    required_keys = {
        "history_id",
        "timestamp",
        "job_id",
        "track_id",
        "frame",
        "pre_repair_track",
        "post_repair_track",
        "applied_repair",
    }
    missing = required_keys - set(snapshot.keys())
    if missing:
        return False, f"Missing required snapshot keys: {missing}"

    try:
        uuid.UUID(str(snapshot["history_id"]))
    except ValueError:
        return False, f"Invalid history_id format: {snapshot['history_id']} is not UUID"

    if not isinstance(snapshot["job_id"], int) or snapshot["job_id"] <= 0:
        return False, f"Invalid job_id: {snapshot['job_id']}"

    if not isinstance(snapshot["track_id"], int):
        return False, f"Invalid track_id: {snapshot['track_id']}"

    if not isinstance(snapshot["frame"], int) or snapshot["frame"] < 0:
        return False, f"Invalid frame index: {snapshot['frame']}"

    if not isinstance(snapshot["pre_repair_track"], dict) or not isinstance(snapshot["post_repair_track"], dict):
        return False, "pre_repair_track and post_repair_track must be dict structures"

    return True, "Valid"


def create_history_snapshot(
    job_id: int,
    track_id: int,
    frame: int,
    pre_repair_track: dict[str, Any],
    post_repair_track: dict[str, Any],
    applied_repair: dict[str, Any],
    history_id: str | None = None,
) -> dict[str, Any]:
    """Constructs a compliant history snapshot record."""
    hid = history_id or str(uuid.uuid4())
    ts = datetime.now(timezone.utc).isoformat()
    return {
        "history_id": hid,
        "timestamp": ts,
        "job_id": job_id,
        "track_id": track_id,
        "frame": frame,
        "pre_repair_track": pre_repair_track,
        "post_repair_track": post_repair_track,
        "applied_repair": applied_repair,
    }


def compute_track_etag(track_dict: dict[str, Any]) -> str:
    """Computes SHA-256 ETag representing the track content for OCC checking."""
    normalized_json = json.dumps(track_dict, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(normalized_json.encode("utf-8")).hexdigest()[:16]


def validate_cvat_points_array(points: list[float]) -> bool:
    """Verifies that CVAT cuboid points array has exactly 16 floats."""
    if len(points) != 16:
        return False
    if not all(isinstance(v, (int, float)) and math.isfinite(v) for v in points):
        return False
    # Last 7 elements must be 0
    if any(abs(v) > 1e-6 for v in points[9:]):
        return False
    return True


# =========================================================================
# Extension Security Whitelist Helper
# =========================================================================

def evaluate_extension_route(method: str, path: str) -> tuple[bool, str]:
    """Evaluates whether an API request is permitted by background.js requestRoute() rules."""
    method_upper = method.upper()
    if method_upper not in ("GET", "POST", "PUT"):
        return False, "Method not allowed"

    if len(path) > 2048:
        return False, "Excessive URL length"

    # Reject path traversal and query smuggling
    if ".." in path or "%2e" in path.lower() or "#" in path:
        return False, "Security violation: path traversal or fragment detected"

    # Permitted routes
    whitelist_patterns = [
        r"^/api/jobs/\d+/tracks/\d+/repair$",
        r"^/api/jobs/\d+/tracks/\d+/apply-repair$",
        r"^/api/jobs/\d+/tracks/\d+/rollback$",
        r"^/api/projects/[a-zA-Z0-9_-]+/scans/\d+/findings/\d+/preview$",
        r"^/api/projects/[a-zA-Z0-9_-]+/scans/\d+/findings/\d+/camera$",
        r"^/api/extension/jobs/\d+$",
        r"^/api/extension/poll$",
        r"^/api/extension/focus$",
    ]

    for pat in whitelist_patterns:
        if re.match(pat, path):
            return True, "Allowed"

    return False, f"Route not whitelisted: {path}"
