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
