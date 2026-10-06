import numpy as np
import pytest

from pointsnap.datasets.pcd import read_pcd, write_pcd

CVAT_HEADER = (
    b"VERSION 0.7\nFIELDS x y z intensity\nSIZE 4 4 4 4\nTYPE F F F F\nCOUNT 1 1 1 1\n"
    b"WIDTH 2\nHEIGHT 1\nVIEWPOINT 0 0 0 1 0 0 0\nPOINTS 2\nDATA binary\n"
)


def test_header_matches_cvat_converter_byte_for_byte(tmp_path):
    # Giống hệt PcdReader.convert_bin_to_pcd_file trong mã nguồn CVAT
    path = tmp_path / "a.pcd"
    write_pcd(path, np.zeros((2, 4)))
    assert path.read_bytes()[: len(CVAT_HEADER)] == CVAT_HEADER
    assert len(path.read_bytes()) == len(CVAT_HEADER) + 2 * 4 * 4


def test_round_trip_keeps_xyz_intensity_and_drops_ring(tmp_path):
    nuscenes_points = np.array([[1.5, -2.0, 0.25, 7.0, 31.0], [100.0, 0.0, -3.0, 0.5, 2.0]], dtype=np.float32)
    path = tmp_path / "b.pcd"
    write_pcd(path, nuscenes_points)
    np.testing.assert_array_equal(read_pcd(path), nuscenes_points[:, :4])


def test_xyz_only_gets_zero_intensity(tmp_path):
    path = tmp_path / "c.pcd"
    write_pcd(path, np.array([[1.0, 2.0, 3.0]]))
    np.testing.assert_array_equal(read_pcd(path), [[1.0, 2.0, 3.0, 0.0]])


def test_empty_cloud(tmp_path):
    path = tmp_path / "d.pcd"
    write_pcd(path, np.zeros((0, 5)))
    assert read_pcd(path).shape == (0, 4)


def test_rejects_bad_input(tmp_path):
    with pytest.raises(ValueError):
        write_pcd(tmp_path / "e.pcd", np.zeros((3, 2)))
    bad = tmp_path / "f.pcd"
    bad.write_bytes(CVAT_HEADER + b"\x00" * 4)  # thiếu dữ liệu
    with pytest.raises(ValueError, match="2 điểm"):
        read_pcd(bad)
