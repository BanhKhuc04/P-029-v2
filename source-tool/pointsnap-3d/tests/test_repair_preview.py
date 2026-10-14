"""A correct detection is separate from a proposed correction; never write from previews."""
from dataclasses import replace
import math

import pytest

from pointsnap.core.config import load_config
from pointsnap.core.model import Cuboid, ErrorType, Finding, Severity
from pointsnap.core.repair_preview import RepairPreviewError, floating_z_preview


def case(offset=.2):
    box = Cuboid(center=(10., 2., .85 + offset), dims=(4., 2., 1.6), yaw=.4,
                 label="car", frame=1, track_id=7, source_id=11,
                 attrs={"reviewed": "false", "cvat_rx": 0., "cvat_ry": 0.})
    boxes = [box, box.replace(frame=0, source_id=10, center=(9., 2., .85)),
             box.replace(frame=2, source_id=12, center=(11., 2., .85))]
    finding = Finding(ErrorType.FLOATING, "floating", Severity.WARNING, 1, "car", "test", 7, 11,
                      offset, .08, {"pitch_deg": 0., "curb_step_m": None, "num_ground_points": 100,
                                    "track_median_distance": .05, "distance": .05 + offset,
                                    "ground_z": 0., "bottom_z": .05 + offset, "reference_frames": [0, 2]})
    return finding, box, boxes, load_config(env={}).floating


@pytest.mark.parametrize("offset", [.2, -.2, .5, -.5])
def test_translation_preserves_measured_reference_clearance_and_every_other_field(offset):
    f, b, boxes, cfg = case(offset)
    result = floating_z_preview(f, b, boxes, cfg, object_points=40)
    assert result.after.bottom_z == pytest.approx(.05)  # not blindly snap to ground zero
    assert result.after.center[:2] == b.center[:2]
    assert result.after.dims == b.dims and result.after.yaw == b.yaw and result.after.attrs == b.attrs
    assert result.after.center == pytest.approx((10., 2., .85), abs=1e-9)
    assert result.delta_z_m == pytest.approx(-offset)
    assert boxes[0] == b and b.center[2] == pytest.approx(.85 + offset)


@pytest.mark.parametrize("change", [
    {"pitch_deg": 5.}, {"pitch_deg": None}, {"curb_step_m": .2},
    {"terrain_reference": True}, {"curb_surface_near_bottom": True},
    {"ground_z": math.nan}, {"distance": True}, {"num_ground_points": 0},
    {"reference_frames": [0]}, {"reference_frames": [0, 0]},
    {"reference_frames": [0, 1]}, {"reference_frames": [0, 9]},
    {"bottom_z": .9}, {"distance": .8}, {"track_median_distance": .9},
])
def test_ambiguous_or_inconsistent_evidence_cannot_produce_a_preview(change):
    f, b, boxes, cfg = case()
    with pytest.raises(RepairPreviewError):
        floating_z_preview(replace(f, details={**f.details, **change}), b, boxes, cfg, object_points=40)


@pytest.mark.parametrize("offset", [.01, .51, math.nan])
def test_shift_outside_trial_bounds_is_rejected(offset):
    f, b, boxes, cfg = case()
    f = replace(f, value=offset, details={**f.details, "distance": .05 + offset, "bottom_z": .05 + offset})
    with pytest.raises(RepairPreviewError):
        floating_z_preview(f, b, boxes, cfg, object_points=40)


def test_wrong_identity_hidden_box_and_sparse_points_are_rejected():
    f, b, boxes, cfg = case()
    for new_f, new_b, points in [(replace(f, source_id=99), b, 40),
                                 (replace(f, severity=Severity.INFO), b, 40),
                                 (f, b.replace(outside=True), 40), (f, b, 19), (f, b, True)]:
        with pytest.raises(RepairPreviewError):
            floating_z_preview(new_f, new_b, [new_b, *boxes[1:]], cfg, object_points=points)


def test_duplicate_and_occluded_reference_are_rejected():
    f, b, boxes, cfg = case()
    for bad_boxes in [boxes + [b], [b, boxes[1].replace(attrs={"occluded": True}), boxes[2]]]:
        with pytest.raises(RepairPreviewError):
            floating_z_preview(f, b, bad_boxes, cfg, object_points=40)
