import pytest
import yaml

from pointsnap.cli.main import EXIT_OK, EXIT_RUNTIME_ERROR, main


def test_help_lists_all_commands(capsys):
    with pytest.raises(SystemExit) as exc:
        main(["--help"])
    assert exc.value.code == 0
    out = capsys.readouterr().out
    for command in ("scan", "gate", "diff", "config"):
        assert command in out


def test_config_command_prints_effective_config_without_token(capsys, monkeypatch):
    monkeypatch.setenv("CVAT_TOKEN", "super-secret")
    assert main(["config"]) == EXIT_OK
    out = capsys.readouterr().out
    assert "super-secret" not in out
    assert yaml.safe_load(out)["cvat"]["token"] == "***"


def test_bad_config_file_returns_runtime_error(tmp_path, capsys):
    bad = tmp_path / "bad.yaml"
    bad.write_text("gate:\n  max_errors: many\n", encoding="utf-8")
    assert main(["--config", str(bad), "config"]) == EXIT_RUNTIME_ERROR
    assert "gate.max_errors" in capsys.readouterr().err


def test_unimplemented_command_points_to_task(capsys):
    assert main(["scan", "--job", "12"]) == EXIT_RUNTIME_ERROR
    assert "A5" in capsys.readouterr().err


def test_missing_required_argument_is_usage_error():
    with pytest.raises(SystemExit) as exc:
        main(["scan"])
    assert exc.value.code == 2


def test_nuscenes_scenes_and_export(tmp_path, capsys):
    import fake_nuscenes

    root = fake_nuscenes.build(tmp_path / "nuscenes")
    assert main(["nuscenes", "--dataroot", str(root), "scenes"]) == EXIT_OK
    assert "scene-0001\t3 frame" in capsys.readouterr().out

    out = tmp_path / "export"
    assert main(["nuscenes", "--dataroot", str(root), "to-cvat", "--scene", "scene-0001", "--out", str(out)]) == EXIT_OK
    assert "3 frame, 4 box" in capsys.readouterr().out
    assert (out / "scene-0001" / "scene-0001.zip").is_file()


def test_nuscenes_errors_are_reported(tmp_path, capsys, monkeypatch):
    import fake_nuscenes

    monkeypatch.delenv("NUSCENES_ROOT", raising=False)
    monkeypatch.delenv("CVAT_TOKEN", raising=False)
    assert main(["nuscenes", "scenes"]) == EXIT_RUNTIME_ERROR
    assert "NUSCENES_ROOT" in capsys.readouterr().err

    root = fake_nuscenes.build(tmp_path / "nuscenes")
    args = ["nuscenes", "--dataroot", str(root), "to-cvat", "--out", str(tmp_path / "o")]
    assert main(args + ["--scene", "scene-9999"]) == EXIT_RUNTIME_ERROR
    assert "Không có cảnh 'scene-9999'" in capsys.readouterr().err
    assert main(args + ["--scene", "scene-0001", "--upload"]) == EXIT_RUNTIME_ERROR
    assert "CVAT_TOKEN" in capsys.readouterr().err
