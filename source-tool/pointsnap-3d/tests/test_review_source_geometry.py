"""Source geometry diagnostic must recover physical corners, not fabricate a resize."""
from importlib.util import module_from_spec, spec_from_file_location
import math
from pathlib import Path

import numpy as np
import pytest

from pointsnap.core.geometry import corners, invert_pose, pose_matrix
from pointsnap.core.model import Cuboid

spec=spec_from_file_location('review_geometry',Path(__file__).parents[1]/'scripts/diagnose_review_geometry.py')
module=module_from_spec(spec);spec.loader.exec_module(module)


def sample(quaternion=(1,0,0,0), pose=None):
    pose=np.eye(4) if pose is None else pose
    annotation={'token':'fixture','translation':[10,3,2],'rotation':quaternion,'size':[2,4,2]}
    source=invert_pose(pose) @ pose_matrix(annotation['translation'],quaternion)
    box=Cuboid(center=tuple(source[:3,3]),dims=(4,2,2),yaw=math.atan2(source[1,0],source[0,0]),
               label='car',frame=0,attrs={'nuscenes_annotation':'fixture'})
    return annotation,pose,box


def test_upright_source_and_reduced_corners_match():
    angle=.4
    annotation,pose,box=sample((math.cos(angle/2),0,0,math.sin(angle/2)))
    recovered,_=module.source_geometry(annotation,pose,box)
    np.testing.assert_allclose(recovered,corners(box),atol=1e-12)


def test_tilt_changes_bottom_and_camera_outline_without_resizing():
    angle=math.radians(10)
    annotation,pose,box=sample((math.cos(angle/2),0,math.sin(angle/2),0))
    recovered,rotation=module.source_geometry(annotation,pose,box)
    # Analytic bottom at z_center - half_length*sin(pitch) - half_height*cos(pitch).
    assert recovered[:,2].min()==pytest.approx(2-2*math.sin(angle)-math.cos(angle))
    assert recovered[:,2].min() < box.bottom_z
    local=(recovered-np.asarray(box.center)) @ rotation
    assert np.max(np.abs(local),axis=0)==pytest.approx(np.asarray(box.dims)/2)
    assert box.dims==(4,2,2) and box.center==(10,3,2)


def test_sensor_pose_recovers_same_corners_in_world():
    angle=.23
    pose=pose_matrix([3,-4,1],(math.cos(angle/2),math.sin(angle/2),0,0))
    annotation,pose,box=sample(pose=pose)
    recovered,_=module.source_geometry(annotation,pose,box)
    world=recovered @ pose[:3,:3].T+pose[:3,3]
    expected=np.array([[12,4,1],[8,4,1],[8,2,1],[12,2,1],
                       [12,4,3],[8,4,3],[8,2,3],[12,2,3]])
    np.testing.assert_allclose(world,expected,atol=1e-12)


@pytest.mark.parametrize('change',[
    {'attrs':{'nuscenes_annotation':'another'}}, {'center':(11,3,2)}, {'dims':(4,3,2)},
])
def test_changed_identity_or_geometry_rejects_source_comparison(change):
    annotation,pose,box=sample()
    with pytest.raises(ValueError):
        module.source_geometry(annotation,pose,box.replace(**change))
