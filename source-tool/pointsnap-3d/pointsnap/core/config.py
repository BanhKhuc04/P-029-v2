"""Đọc và kiểm tra cấu hình.

Cấu hình mặc định nằm ở `pointsnap/config.yaml`. File người dùng (`--config`) chỉ cần chứa phần muốn
đổi: nó được trộn đè lên mặc định. Khóa lạ bị báo lỗi ngay để tránh gõ sai tên ngưỡng mà không biết.
"""

from __future__ import annotations

import dataclasses
import os
from dataclasses import dataclass
from importlib import resources
from pathlib import Path
from typing import Any, Mapping

import yaml

DIMENSIONS = ("length", "width", "height")


class ConfigError(ValueError):
    """Cấu hình sai: thiếu khóa, sai kiểu, khóa lạ hoặc ngưỡng mâu thuẫn."""


@dataclass(frozen=True)
class CvatConfig:
    url: str
    flag_attribute: str
    token: str | None = None


@dataclass(frozen=True)
class FloatingConfig:
    classes: tuple[str, ...]
    warning_m: float
    error_m: float
    error_min_abs_m: float
    single_warning_m: float
    single_error_m: float
    min_track_boxes: int
    ring_inner_m: float
    ring_outer_m: float
    min_ground_points: int


@dataclass(frozen=True)
class ClassRangeConfig:
    percentile_low: float
    percentile_high: float
    warning_margin: float
    error_margin: float
    min_instances: int
    stats: Mapping[str, Mapping[str, tuple[float, float]]] = dataclasses.field(default_factory=dict)
    """Khoảng [p_low, p_high] của từng class theo `length`, `width`, `height`."""


@dataclass(frozen=True)
class InTrackConfig:
    min_keyframes: int
    excluded_classes: tuple[str, ...]
    warning_abs_m: float
    warning_rel: float
    error_abs_m: float
    error_rel: float
    suspect_id_rel: float


@dataclass(frozen=True)
class SizeConfig:
    class_range: ClassRangeConfig
    manual_ranges: Mapping[str, Mapping[str, tuple[float, float]]]
    in_track: InTrackConfig


@dataclass(frozen=True)
class TrackGroupConfig:
    classes: tuple[str, ...]
    jump_warning_m: float
    jump_error_m: float
    v_max_mps: float
    split_max_dist_m: float


@dataclass(frozen=True)
class LongInterpolationConfig:
    enabled: bool
    min_frames: int
    min_motion_m: float


@dataclass(frozen=True)
class TrackConfig:
    keyframe_interval_s: float
    groups: Mapping[str, TrackGroupConfig]
    split_max_gap_frames: int
    long_interpolation: LongInterpolationConfig

    def group_for(self, label: str) -> TrackGroupConfig | None:
        """Nhóm ngưỡng của class; `None` nếu class không thuộc nhóm nào."""
        for group in self.groups.values():
            if label in group.classes:
                return group
        return None


@dataclass(frozen=True)
class GateConfig:
    max_errors: int
    max_warnings: int


@dataclass(frozen=True)
class Config:
    cvat: CvatConfig
    floating: FloatingConfig
    size: SizeConfig
    track: TrackConfig
    gate: GateConfig

    def to_dict(self, redact: bool = True) -> dict[str, Any]:
        """Dạng dict thuần (list thay cho tuple) để in hoặc lưu kèm báo cáo. Mặc định ẩn token."""
        data = _plain(dataclasses.asdict(self))
        if redact and data["cvat"].get("token"):
            data["cvat"]["token"] = "***"
        return data


def _plain(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {k: _plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(v) for v in value]
    return value


class _Reader:
    """Đọc một mục YAML, kiểm kiểu từng khóa, báo lỗi nếu còn khóa lạ."""

    def __init__(self, data: Any, path: str) -> None:
        if not isinstance(data, Mapping):
            raise ConfigError(f"'{path}' phải là một mục (mapping), nhận {type(data).__name__}")
        self._data = dict(data)
        self._path = path

    def _take(self, key: str) -> Any:
        if key not in self._data:
            raise ConfigError(f"Thiếu khóa '{self._path}.{key}'")
        return self._data.pop(key)

    def number(self, key: str, minimum: float | None = None) -> float:
        value = self._take(key)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ConfigError(f"'{self._path}.{key}' phải là số, nhận {value!r}")
        if minimum is not None and value < minimum:
            raise ConfigError(f"'{self._path}.{key}' phải >= {minimum}, nhận {value}")
        return float(value)

    def integer(self, key: str, minimum: int | None = None) -> int:
        value = self._take(key)
        if isinstance(value, bool) or not isinstance(value, int):
            raise ConfigError(f"'{self._path}.{key}' phải là số nguyên, nhận {value!r}")
        if minimum is not None and value < minimum:
            raise ConfigError(f"'{self._path}.{key}' phải >= {minimum}, nhận {value}")
        return value

    def boolean(self, key: str) -> bool:
        value = self._take(key)
        if not isinstance(value, bool):
            raise ConfigError(f"'{self._path}.{key}' phải là true/false, nhận {value!r}")
        return value

    def string(self, key: str) -> str:
        value = self._take(key)
        if not isinstance(value, str) or not value:
            raise ConfigError(f"'{self._path}.{key}' phải là chuỗi khác rỗng, nhận {value!r}")
        return value

    def strings(self, key: str) -> tuple[str, ...]:
        value = self._take(key)
        if not isinstance(value, list) or not all(isinstance(v, str) and v for v in value):
            raise ConfigError(f"'{self._path}.{key}' phải là danh sách chuỗi, nhận {value!r}")
        return tuple(value)

    def min_max(self, key: str) -> tuple[float, float]:
        value = self._take(key)
        if (not isinstance(value, list) or len(value) != 2
                or not all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in value)):
            raise ConfigError(f"'{self._path}.{key}' phải là [min, max], nhận {value!r}")
        _require_order(f"{self._path}.{key}", value[0], value[1], "min", "max")
        return float(value[0]), float(value[1])

    def section(self, key: str) -> _Reader:
        return _Reader(self._take(key), f"{self._path}.{key}")

    def keys(self) -> list[str]:
        return list(self._data)

    def finish(self) -> None:
        if self._data:
            extra = ", ".join(f"'{self._path}.{k}'" for k in self._data)
            raise ConfigError(f"Khóa không hợp lệ: {extra}")


def _require_order(path: str, low: float, high: float, low_name: str, high_name: str) -> None:
    if not low < high:
        raise ConfigError(f"'{path}': cần {low_name} < {high_name}, nhận {low} và {high}")


def _parse_cvat(r: _Reader, env: Mapping[str, str]) -> CvatConfig:
    url = r.string("url")
    flag_attribute = r.string("flag_attribute")
    if "token" in r.keys():
        raise ConfigError("Không ghi token CVAT trong file cấu hình; đặt biến môi trường CVAT_TOKEN")
    r.finish()
    return CvatConfig(url=url, flag_attribute=flag_attribute, token=env.get("CVAT_TOKEN") or None)


def _parse_floating(r: _Reader) -> FloatingConfig:
    cfg = FloatingConfig(
        classes=r.strings("classes"),
        warning_m=r.number("warning_m", 0.0),
        error_m=r.number("error_m", 0.0),
        error_min_abs_m=r.number("error_min_abs_m", 0.0),
        single_warning_m=r.number("single_warning_m", 0.0),
        single_error_m=r.number("single_error_m", 0.0),
        min_track_boxes=r.integer("min_track_boxes", 1),
        ring_inner_m=r.number("ring_inner_m", 0.0),
        ring_outer_m=r.number("ring_outer_m", 0.0),
        min_ground_points=r.integer("min_ground_points", 1),
    )
    r.finish()
    _require_order("floating", cfg.warning_m, cfg.error_m, "warning_m", "error_m")
    _require_order("floating", cfg.single_warning_m, cfg.single_error_m, "single_warning_m", "single_error_m")
    _require_order("floating", cfg.ring_inner_m, cfg.ring_outer_m, "ring_inner_m", "ring_outer_m")
    return cfg


def _parse_size(r: _Reader) -> SizeConfig:
    cr = r.section("class_range")
    percentile_low = cr.number("percentile_low", 0.0)
    percentile_high = cr.number("percentile_high", 0.0)
    warning_margin = cr.number("warning_margin", 0.0)
    error_margin = cr.number("error_margin", 0.0)
    min_instances = cr.integer("min_instances", 1)
    sr = cr.section("stats")
    stats: dict[str, dict[str, tuple[float, float]]] = {}
    for label in sr.keys():
        lr = sr.section(label)
        stats[label] = {dim: lr.min_max(dim) for dim in DIMENSIONS}
        lr.finish()
    sr.finish()
    cr.finish()
    class_range = ClassRangeConfig(
        percentile_low=percentile_low,
        percentile_high=percentile_high,
        warning_margin=warning_margin,
        error_margin=error_margin,
        min_instances=min_instances,
        stats=stats,
    )
    _require_order("size.class_range", class_range.percentile_low, class_range.percentile_high,
                   "percentile_low", "percentile_high")
    if class_range.percentile_high > 100:
        raise ConfigError("'size.class_range.percentile_high' phải <= 100")
    _require_order("size.class_range", class_range.warning_margin, class_range.error_margin,
                   "warning_margin", "error_margin")

    mr = r.section("manual_ranges")
    manual: dict[str, dict[str, tuple[float, float]]] = {}
    for label in mr.keys():
        lr = mr.section(label)
        manual[label] = {dim: lr.min_max(dim) for dim in DIMENSIONS}
        lr.finish()
    mr.finish()

    tr = r.section("in_track")
    in_track = InTrackConfig(
        min_keyframes=tr.integer("min_keyframes", 2),
        excluded_classes=tr.strings("excluded_classes"),
        warning_abs_m=tr.number("warning_abs_m", 0.0),
        warning_rel=tr.number("warning_rel", 0.0),
        error_abs_m=tr.number("error_abs_m", 0.0),
        error_rel=tr.number("error_rel", 0.0),
        suspect_id_rel=tr.number("suspect_id_rel", 0.0),
    )
    tr.finish()
    _require_order("size.in_track", in_track.warning_abs_m, in_track.error_abs_m, "warning_abs_m", "error_abs_m")
    _require_order("size.in_track", in_track.warning_rel, in_track.error_rel, "warning_rel", "error_rel")
    r.finish()
    return SizeConfig(class_range=class_range, manual_ranges=manual, in_track=in_track)


def _parse_track(r: _Reader) -> TrackConfig:
    keyframe_interval_s = r.number("keyframe_interval_s", 0.0)
    gr = r.section("groups")
    groups: dict[str, TrackGroupConfig] = {}
    seen: dict[str, str] = {}
    for name in gr.keys():
        g = gr.section(name)
        group = TrackGroupConfig(
            classes=g.strings("classes"),
            jump_warning_m=g.number("jump_warning_m", 0.0),
            jump_error_m=g.number("jump_error_m", 0.0),
            v_max_mps=g.number("v_max_mps", 0.0),
            split_max_dist_m=g.number("split_max_dist_m", 0.0),
        )
        g.finish()
        _require_order(f"track.groups.{name}", group.jump_warning_m, group.jump_error_m,
                       "jump_warning_m", "jump_error_m")
        for label in group.classes:
            if label in seen:
                raise ConfigError(f"Class '{label}' nằm trong cả nhóm '{seen[label]}' và '{name}'")
            seen[label] = name
        groups[name] = group
    gr.finish()

    li = r.section("long_interpolation")
    long_interpolation = LongInterpolationConfig(
        enabled=li.boolean("enabled"),
        min_frames=li.integer("min_frames", 1),
        min_motion_m=li.number("min_motion_m", 0.0),
    )
    li.finish()
    cfg = TrackConfig(
        keyframe_interval_s=keyframe_interval_s,
        groups=groups,
        split_max_gap_frames=r.integer("split_max_gap_frames", 1),
        long_interpolation=long_interpolation,
    )
    r.finish()
    return cfg


def _parse_gate(r: _Reader) -> GateConfig:
    cfg = GateConfig(max_errors=r.integer("max_errors", 0), max_warnings=r.integer("max_warnings", 0))
    r.finish()
    return cfg


def _deep_merge(base: Mapping[str, Any], override: Mapping[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in override.items():
        if isinstance(value, Mapping) and isinstance(merged.get(key), Mapping):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def _read_yaml(text: str, source: str) -> dict[str, Any]:
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise ConfigError(f"Không đọc được YAML từ {source}: {exc}") from exc
    if data is None:
        return {}
    if not isinstance(data, Mapping):
        raise ConfigError(f"{source} phải chứa một mapping ở cấp ngoài cùng")
    return dict(data)


def parse_config(data: Mapping[str, Any], env: Mapping[str, str] | None = None) -> Config:
    """Kiểm tra dict cấu hình đầy đủ và trả về `Config`."""
    env = os.environ if env is None else env
    r = _Reader(data, "config")
    cfg = Config(
        cvat=_parse_cvat(r.section("cvat"), env),
        floating=_parse_floating(r.section("floating")),
        size=_parse_size(r.section("size")),
        track=_parse_track(r.section("track")),
        gate=_parse_gate(r.section("gate")),
    )
    r.finish()
    return cfg


def default_config_text() -> str:
    return resources.files("pointsnap").joinpath("config.yaml").read_text(encoding="utf-8")


def load_config(path: str | Path | None = None, env: Mapping[str, str] | None = None) -> Config:
    """Đọc cấu hình theo thứ tự ưu tiên tăng dần: mặc định → biến môi trường → file `path`.

    `CVAT_URL` ghi đè URL mặc định, nhưng URL ghi rõ trong file `--config` được ưu tiên hơn,
    vì file đó do người dùng chỉ định riêng cho lần chạy này.
    """
    env = os.environ if env is None else env
    data = _read_yaml(default_config_text(), "config.yaml mặc định")
    if env.get("CVAT_URL"):
        data = _deep_merge(data, {"cvat": {"url": env["CVAT_URL"]}})
    if path is not None:
        path = Path(path)
        try:
            text = path.read_text(encoding="utf-8")
        except OSError as exc:
            raise ConfigError(f"Không mở được file cấu hình {path}: {exc}") from exc
        data = _deep_merge(data, _read_yaml(text, str(path)))
    return parse_config(data, env)
