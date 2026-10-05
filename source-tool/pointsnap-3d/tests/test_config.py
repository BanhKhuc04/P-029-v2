import pytest
import yaml

from pointsnap.core.config import ConfigError, default_config_text, load_config, parse_config


def default_data():
    return yaml.safe_load(default_config_text())


def test_default_config_loads():
    cfg = load_config(env={})
    assert cfg.cvat.url == "http://localhost:8080"
    assert cfg.cvat.token is None
    assert cfg.floating.warning_m == pytest.approx(0.10)
    assert cfg.floating.error_m == pytest.approx(0.20)
    assert "pedestrian" in cfg.size.in_track.excluded_classes
    assert cfg.size.manual_ranges["bus"]["length"] == (6.0, 18.5)
    assert cfg.track.group_for("car").jump_error_m == pytest.approx(2.0)
    assert cfg.track.group_for("pedestrian").jump_warning_m == pytest.approx(0.5)
    assert cfg.track.group_for("unknown") is None
    assert cfg.track.long_interpolation.enabled is False
    assert cfg.gate.max_errors == 0


def test_env_overrides_url_and_provides_token():
    cfg = load_config(env={"CVAT_URL": "http://cvat.local:9000", "CVAT_TOKEN": "secret"})
    assert cfg.cvat.url == "http://cvat.local:9000"
    assert cfg.cvat.token == "secret"
    assert cfg.to_dict()["cvat"]["token"] == "***"
    assert cfg.to_dict(redact=False)["cvat"]["token"] == "secret"


def test_user_file_overrides_only_given_keys(tmp_path):
    user = tmp_path / "my.yaml"
    user.write_text("floating:\n  error_m: 0.25\ngate:\n  max_warnings: 3\n", encoding="utf-8")
    cfg = load_config(user, env={})
    assert cfg.floating.error_m == pytest.approx(0.25)
    assert cfg.floating.warning_m == pytest.approx(0.10)  # giữ mặc định
    assert cfg.gate.max_warnings == 3


def test_unknown_key_is_rejected(tmp_path):
    user = tmp_path / "typo.yaml"
    user.write_text("floating:\n  eror_m: 0.25\n", encoding="utf-8")
    with pytest.raises(ConfigError, match="floating.eror_m"):
        load_config(user, env={})


def test_token_in_file_is_rejected():
    data = default_data()
    data["cvat"]["token"] = "leak"
    with pytest.raises(ConfigError, match="CVAT_TOKEN"):
        parse_config(data, env={})


@pytest.mark.parametrize(
    "section, key, value, message",
    [
        ("floating", "warning_m", 0.5, "warning_m < error_m"),
        ("floating", "ring_inner_m", 2.0, "ring_inner_m < ring_outer_m"),
        ("floating", "warning_m", "10cm", "phải là số"),
        ("floating", "min_ground_points", 2.5, "số nguyên"),
        ("gate", "max_errors", -1, ">= 0"),
    ],
)
def test_invalid_values_are_rejected(section, key, value, message):
    data = default_data()
    data[section][key] = value
    with pytest.raises(ConfigError, match=message):
        parse_config(data, env={})


def test_class_in_two_track_groups_is_rejected():
    data = default_data()
    data["track"]["groups"]["pedestrian"]["classes"].append("car")
    with pytest.raises(ConfigError, match="'car'"):
        parse_config(data, env={})


def test_manual_range_must_be_ordered():
    data = default_data()
    data["size"]["manual_ranges"]["bus"]["width"] = [3.2, 2.2]
    with pytest.raises(ConfigError, match="min < max"):
        parse_config(data, env={})


def test_missing_file_gives_clear_error(tmp_path):
    with pytest.raises(ConfigError, match="Không mở được"):
        load_config(tmp_path / "nope.yaml", env={})
