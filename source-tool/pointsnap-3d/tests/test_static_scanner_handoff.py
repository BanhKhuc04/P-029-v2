"""A configured static detector must actually run through the scanner."""
import dataclasses
import math
from types import SimpleNamespace

import numpy as np
import pytest

from pointsnap.core.config import load_config
from pointsnap.core.model import Cuboid, FrameData, Severity
from pointsnap.core.scanner import scan_cuboids


class Frames:
    def frame_data(self, frame, with_points=True):
        # Ego translates; the object stays at world (20, 0, 1).
        pose = np.eye(4)
        pose[0, 3] = frame * 2
        return FrameData(frame=frame, timestamp=frame * 0.5, sensor_to_world=pose,
                         points=np.empty((0, 3)))


@pytest.mark.parametrize('shift,rotate,expected', [
    (True, False, [('track.static_shift', Severity.ERROR)]),
    (False, True, [('heading.static', Severity.WARNING)]),
    (True, True, [('track.static_shift', Severity.ERROR), ('heading.static', Severity.WARNING)]),
    (False, False, []),
])
def test_static_switches_execute_independently_through_scanner(shift, rotate, expected):
    cfg = load_config(env={})
    switches = {f.name: False for f in dataclasses.fields(cfg.rules)}
    switches.update(track_static_shift=shift, heading_static=rotate)
    cfg = dataclasses.replace(cfg, rules=dataclasses.replace(cfg.rules, **switches))
    boxes = [Cuboid(center=(20 - 2*f + (0.6 if f == 2 else 0), 0, 1),
                    dims=(4, 2, 2), yaw=math.radians(6) if f == 2 else 0,
                    label='car', frame=f, track_id=0) for f in range(5)]
    findings = scan_cuboids(SimpleNamespace(cuboids=boxes), cfg, Frames())
    assert sorted((f.rule, f.severity) for f in findings) == sorted(expected)
    assert all(f.frame == 2 and f.track_id == 0 for f in findings)
    assert scan_cuboids(SimpleNamespace(cuboids=boxes), cfg, None) == []
