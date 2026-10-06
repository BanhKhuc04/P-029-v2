import math

import numpy as np
import pytest

import fake_nuscenes
from pointsnap.adapters.nuscenes import CATEGORY_TO_LABEL, NuScenesReader
from pointsnap.core.geometry import transform_points


@pytest.fixture
def reader(tmp_path):
    return NuScenesReader(fake_nuscenes.build(tmp_path))


def by_annotation(cuboids):
    return {c.attrs["nuscenes_annotation"]: c for c in cuboids}


def test_scenes(reader):
    [scene] = reader.scenes()
    assert (scene.name, scene.num_frames, scene.description) == ("scene-0001", 3, "cảnh giả")


def test_samples_follow_next_chain_and_use_lidar_keyframes(reader, tmp_path):
    refs = reader.samples("scene-0001")
    assert [r.sample_token for r in refs] == ["smp0", "smp1", "smp2"]
    assert [r.frame for r in refs] == [0, 1, 2]
    assert [r.lidar_token for r in refs] == ["sd0", "sd1", "sd2"]  # không lấy sweep hay ảnh camera
    assert [r.timestamp for r in refs] == pytest.approx([1.0, 1.5, 2.0])
    assert refs[0].lidar_path == tmp_path / "samples" / "LIDAR_TOP" / "f0.pcd.bin"


def test_sensor_to_world_combines_ego_and_calibration(reader):
    refs = reader.samples("scene-0001")
    # Frame 0: xe tại gốc, LiDAR tại (1, 0, 2) quay 90°.
    np.testing.assert_allclose(refs[0].sensor_to_world[:3, 3], [1.0, 0.0, 2.0], atol=1e-12)
    np.testing.assert_allclose(refs[0].sensor_to_world[:2, 0], [0.0, 1.0], atol=1e-12)  # trục x LiDAR = +y thế giới
    # Frame 2: xe tại (10, 0, 0) quay 90° → LiDAR tại (10, 1, 2), tổng quay 180°.
    np.testing.assert_allclose(refs[2].sensor_to_world[:3, 3], [10.0, 1.0, 2.0], atol=1e-12)
    np.testing.assert_allclose(refs[2].sensor_to_world[:2, 0], [-1.0, 0.0], atol=1e-12)


def test_annotations_are_converted_to_lidar_frame(reader):
    boxes = by_annotation(reader.annotations("scene-0001"))
    # Đáp án tính tay: (11, 0, 0.8) − (1, 0, 2) = (10, 0, −1.2), quay −90° → (0, −10, −1.2)
    car0 = boxes["a_car0"]
    np.testing.assert_allclose(car0.center, [0.0, -10.0, -1.2], atol=1e-9)
    assert car0.yaw == pytest.approx(-math.pi / 2)
    assert car0.dims == (4.5, 2.0, 1.6)  # nuScenes [w, l, h] → core (l, w, h)
    assert (car0.label, car0.frame, car0.track_id) == ("car", 0, 0)
    # Frame 2: (11, 5, 0.8) − (10, 1, 2) = (1, 4, −1.2), quay −180° → (−1, −4, −1.2); yaw 90° − 180° = −90°
    car2 = boxes["a_car2"]
    np.testing.assert_allclose(car2.center, [-1.0, -4.0, -1.2], atol=1e-9)
    assert car2.yaw == pytest.approx(-math.pi / 2)
    # Người đi bộ: (5, 3, 0.9) − (1, 0, 2) = (4, 3, −1.1), quay −90° → (3, −4, −1.1)
    ped0 = boxes["a_ped0"]
    np.testing.assert_allclose(ped0.center, [3.0, -4.0, -1.1], atol=1e-9)
    assert (ped0.label, ped0.track_id, ped0.dims) == ("pedestrian", 1, (0.7, 0.6, 1.8))


def test_lidar_frame_boxes_map_back_to_global(reader):
    refs = {r.frame: r for r in reader.samples("scene-0001")}
    for box in reader.annotations("scene-0001"):
        world = transform_points(np.array([box.center]), refs[box.frame].sensor_to_world)[0]
        expected = {"a_car0": [11, 0, 0.8], "a_car1": [11, 2, 0.8], "a_car2": [11, 5, 0.8], "a_ped0": [5, 3, 0.9]}
        np.testing.assert_allclose(world, expected[box.attrs["nuscenes_annotation"]], atol=1e-9)


def test_filters_unmapped_categories_and_empty_boxes(reader, tmp_path):
    tokens = set(by_annotation(reader.annotations("scene-0001")))
    assert tokens == {"a_car0", "a_car1", "a_car2", "a_ped0"}  # bỏ a_ped1 (0 điểm), a_dog0 (animal)
    keep_empty = NuScenesReader(tmp_path, min_lidar_points=0)
    assert "a_ped1" in by_annotation(keep_empty.annotations("scene-0001"))


def test_box_attrs_keep_nuscenes_references(reader):
    car1 = by_annotation(reader.annotations("scene-0001"))["a_car1"]
    assert car1.attrs["nuscenes_instance"] == "inst_car"
    assert car1.attrs["nuscenes_category"] == "vehicle.car"
    assert car1.attrs["num_lidar_pts"] == 100
    assert car1.attrs["tilt_rad"] == pytest.approx(0.0, abs=1e-9)


def test_load_points_and_frame_data(reader):
    ref = reader.samples("scene-0001")[0]
    frame = reader.frame_data(ref)
    np.testing.assert_array_equal(frame.points, fake_nuscenes.FRAME0_POINTS)
    assert (frame.frame, frame.source_ref, frame.timestamp) == (0, "smp0", pytest.approx(1.0))
    assert reader.frame_data(ref, with_points=False).points.shape == (0, 5)


def test_corrupted_point_file_is_rejected(reader):
    ref = reader.samples("scene-0001")[1]
    np.zeros(7, dtype=np.float32).tofile(ref.lidar_path)
    with pytest.raises(ValueError, match="không chia hết cho 5"):
        reader.load_points(ref)


def test_clear_errors_for_missing_data(tmp_path, reader):
    with pytest.raises(FileNotFoundError, match="thư mục bảng"):
        NuScenesReader(tmp_path / "nope")
    with pytest.raises(KeyError, match="scene-0001"):
        reader.samples("scene-9999")


def test_category_mapping_covers_the_ten_task_classes():
    assert set(CATEGORY_TO_LABEL.values()) == {
        "car", "truck", "bus", "trailer", "construction_vehicle",
        "pedestrian", "motorcycle", "bicycle", "traffic_cone", "barrier",
    }
