"""Đọc và kiểm tra cấu hình.

Cấu hình mặc định nằm ở `pointsnap/config.yaml`. File người dùng (`--config`) chỉ cần chứa phần muốn
đổi: nó được trộn đè lên mặc định. Khóa lạ bị báo lỗi ngay để tránh gõ sai tên ngưỡng mà không biết.
"""

from __future__ import annotations

import dataclasses
import math
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
class RulesConfig:
    floating: bool = True
    size_class_range: bool = True
    size_in_track: bool = True
    track_jump: bool = True
    track_split_id: bool = True
    track_long_interpolation: bool = True
    heading_flip: bool = True
    heading_motion: bool = True
    heading_points: bool = True
    fit_empty: bool = True
    fit_outside: bool = True
    fit_loose: bool = True
    fit_overlap: bool = True
    track_reuse_id: bool = True
    track_occluded_long: bool = True
    attr_missing: bool = True
    attr_invalid: bool = True


@dataclass(frozen=True)
class FloatingConfig:
    classes: tuple[str, ...]
    warning_m: float
    error_m: float
    ring_inner_m: float
    ring_outer_m: float
    min_ground_points: int
    # Luật so với track (`detect_floating_scene`, A10); mặc định để code cũ tạo FloatingConfig vẫn chạy.
    error_min_abs_m: float = 0.15
    single_warning_m: float = 0.15
    single_error_m: float = 0.30
    min_track_boxes: int = 2
    sweeps: int = 0
    """Số lượt quét LiDAR trung gian gộp thêm trước keyframe để đo mặt đất (C1, mặt đất v2); 0 = chỉ keyframe."""


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
    key_attributes: Mapping[str, str] = dataclasses.field(default_factory=dict)
    """Class → thuộc tính phân loại chi tiết (spec 3.1.2, vd `Vehicle: subtype`): khoảng kích thước tra theo khóa
    `Class/giá trị` (vd `Vehicle/bus`), không có thì theo `Class`."""


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
    max_occluded_frames: int = 6
    """Spec: occluded chỉ dùng cho che khuất tạm thời tối đa 6 frame; lâu hơn thì kết thúc track."""

    def group_for(self, label: str) -> TrackGroupConfig | None:
        """Nhóm ngưỡng của class; `None` nếu class không thuộc nhóm nào."""
        for group in self.groups.values():
            if label in group.classes:
                return group
        return None


@dataclass(frozen=True)
class HeadingGroupConfig:
    classes: tuple[str, ...]
    min_speed_mps: float
    """Chỉ so hướng box với hướng chuyển động khi vật chạy nhanh hơn mức này."""
    motion_warning_deg: float
    motion_error_deg: float
    flip_warning_deg: float
    flip_error_deg: float
    yaw_rate_max_dps: float
    """Tốc độ quay tối đa hợp lý (độ / giây): hướng đổi chậm hơn mức này giữa hai keyframe không bị coi là lật."""


@dataclass(frozen=True)
class HeadingPointsConfig:
    classes: tuple[str, ...]
    min_points: int
    min_aspect: float
    warning_deg: float
    error_deg: float
    max_range_m: float


def _default_heading_groups() -> dict[str, HeadingGroupConfig]:
    return {
        "vehicle": HeadingGroupConfig(("car", "truck", "bus", "trailer", "construction_vehicle"),
                                      2.0, 60.0, 135.0, 45.0, 75.0, 60.0),
        "two_wheeler": HeadingGroupConfig(("motorcycle", "bicycle"), 1.5, 60.0, 135.0, 45.0, 75.0, 90.0),
        "pedestrian": HeadingGroupConfig(("pedestrian",), 1.0, 90.0, 150.0, 120.0, 170.0, 180.0),
    }


@dataclass(frozen=True)
class HeadingConfig:
    """Sai hướng box (C1, spec 4.2: hướng box trùng hướng chuyển động chính; đứng yên thì theo trục dài)."""

    groups: Mapping[str, HeadingGroupConfig] = dataclasses.field(default_factory=_default_heading_groups)
    min_motion_m: float = 1.0
    """Quãng đường tối thiểu giữa hai keyframe lân cận để ước lượng hướng chuyển động."""
    points: HeadingPointsConfig = dataclasses.field(default_factory=lambda: HeadingPointsConfig(
        ("car", "truck", "bus", "trailer"), 60, 1.6, 15.0, 30.0, 40.0))

    def group_for(self, label: str) -> HeadingGroupConfig | None:
        for group in self.groups.values():
            if label in group.classes:
                return group
        return None


@dataclass(frozen=True)
class FitConfig:
    """Box vẽ lệch khỏi vật (C1, spec 4.2: bao trọn vật thể, không dư thừa quá mức; không gán box khi quá ít điểm)."""

    empty_max_points: int = 0
    """Box có số điểm LiDAR (cao hơn đáy box) <= mức này, không đánh `occluded`, là box rỗng: Cảnh báo."""
    sparse_warning_points: int = 0
    """Box có ít điểm hơn mức này: Cảnh báo "quá ít điểm" (spec 4.2). 0 = tắt, đợi chốt P-009."""
    outside_margin_m: float = 0.5
    outside_margin_rel: float = 0.25
    """Vùng xét nới mỗi phía max(`outside_margin_m`, `outside_margin_rel` × cạnh box): xe dài thò ra xa hơn."""
    outside_min_points: int = 30
    outside_warning_ratio: float = 0.5
    outside_error_ratio: float = 0.7
    ground_clearance_m: float = 0.25
    loose_min_points: int = 40
    loose_max_range_m: float = 30.0
    loose_warning_m: float = 0.5
    loose_error_m: float = 1.0
    overlap_warning: float = 0.2
    overlap_error: float = 0.5
    overlap_classes: tuple[str, ...] = (
        "car", "truck", "bus", "trailer", "construction_vehicle", "motorcycle", "bicycle", "pedestrian",
    )
    """Chỉ xét chồng box giữa hai class trong danh sách này (vật cản nhỏ như cọc tiêu, rào chắn hay đặt sát nhau)."""
    overlap_allowed_pairs: tuple[tuple[str, str], ...] = (
        ("pedestrian", "pedestrian"), ("pedestrian", "bicycle"), ("pedestrian", "motorcycle"),
        ("pedestrian", "car"), ("pedestrian", "truck"), ("pedestrian", "construction_vehicle"),
        ("bicycle", "bicycle"), ("motorcycle", "motorcycle"), ("bicycle", "motorcycle"), ("truck", "trailer"), ("car", "trailer"), ("construction_vehicle", "trailer"),
    )


@dataclass(frozen=True)
class SpecConfig:
    """Thuộc tính bắt buộc và giá trị cho phép theo spec của dự án (C2, spec 3.1.2–3.1.3)."""

    required_attributes: Mapping[str, tuple[str, ...]] = dataclasses.field(default_factory=dict)
    """Class → các thuộc tính bắt buộc, vd `Vehicle: [subtype]`."""
    allowed_values: Mapping[str, tuple[str, ...]] = dataclasses.field(default_factory=dict)
    """Thuộc tính (hoặc `Class.thuộc_tính`) → các giá trị cho phép."""


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
    rules: RulesConfig = dataclasses.field(default_factory=RulesConfig)
    heading: HeadingConfig = dataclasses.field(default_factory=HeadingConfig)
    fit: FitConfig = dataclasses.field(default_factory=FitConfig)
    spec: SpecConfig = dataclasses.field(default_factory=SpecConfig)

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
        if not math.isfinite(value):
            raise ConfigError(f"'{self._path}.{key}' phải là số hữu hạn, nhận {value!r}")
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
                or not all(isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)
                           for v in value)):
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


def _parse_rules(r: _Reader) -> RulesConfig:
    cfg = RulesConfig(
        floating=r.boolean("floating"),
        size_class_range=r.boolean("size_class_range"),
        size_in_track=r.boolean("size_in_track"),
        track_jump=r.boolean("track_jump"),
        track_split_id=r.boolean("track_split_id"),
        track_long_interpolation=r.boolean("track_long_interpolation"),
        **{name: r.boolean(name) for name in _NEW_RULES if name in r.keys()},
    )
    r.finish()
    return cfg


_NEW_RULES = ("heading_flip", "heading_motion", "heading_points", "fit_empty", "fit_outside", "fit_loose",
              "fit_overlap", "track_reuse_id", "track_occluded_long", "attr_missing", "attr_invalid")
"""Luật thêm ở giai đoạn 3: file cấu hình cũ không có thì coi là bật."""


def _parse_heading(r: _Reader) -> HeadingConfig:
    gr = r.section("groups")
    groups: dict[str, HeadingGroupConfig] = {}
    seen: dict[str, str] = {}
    for name in gr.keys():
        g = gr.section(name)
        group = HeadingGroupConfig(
            classes=g.strings("classes"),
            min_speed_mps=g.number("min_speed_mps", 0.0),
            motion_warning_deg=g.number("motion_warning_deg", 0.0),
            motion_error_deg=g.number("motion_error_deg", 0.0),
            flip_warning_deg=g.number("flip_warning_deg", 0.0),
            flip_error_deg=g.number("flip_error_deg", 0.0),
            yaw_rate_max_dps=g.number("yaw_rate_max_dps", 0.0),
        )
        g.finish()
        for low, high in (("motion_warning_deg", "motion_error_deg"), ("flip_warning_deg", "flip_error_deg")):
            _require_order(f"heading.groups.{name}", getattr(group, low), getattr(group, high), low, high)
            if getattr(group, high) > 180:
                raise ConfigError(f"'heading.groups.{name}.{high}' phải <= 180")
        for label in group.classes:
            if label in seen:
                raise ConfigError(f"Class '{label}' nằm trong cả nhóm '{seen[label]}' và '{name}' của heading")
            seen[label] = name
        groups[name] = group
    gr.finish()
    pr = r.section("points")
    points = HeadingPointsConfig(
        classes=pr.strings("classes"),
        min_points=pr.integer("min_points", 3),
        min_aspect=pr.number("min_aspect", 1.0),
        warning_deg=pr.number("warning_deg", 0.0),
        error_deg=pr.number("error_deg", 0.0),
        max_range_m=pr.number("max_range_m", 0.0),
    )
    pr.finish()
    _require_order("heading.points", points.warning_deg, points.error_deg, "warning_deg", "error_deg")
    if points.error_deg > 45:
        raise ConfigError("'heading.points.error_deg' phải <= 45 (lệch trục chỉ đo được trong khoảng 0–45°)")
    cfg = HeadingConfig(groups=groups, min_motion_m=r.number("min_motion_m", 0.0), points=points)
    r.finish()
    return cfg


def _parse_spec(r: _Reader) -> SpecConfig:
    def mapping_of_lists(key: str) -> dict[str, tuple[str, ...]]:
        if key not in r.keys():
            return {}
        section = r.section(key)
        result = {name: section.strings(name) for name in section.keys()}
        section.finish()
        return result

    cfg = SpecConfig(required_attributes=mapping_of_lists("required_attributes"),
                     allowed_values=mapping_of_lists("allowed_values"))
    r.finish()
    return cfg


def _parse_fit(r: _Reader) -> FitConfig:
    pairs_raw = r._take("overlap_allowed_pairs")
    if (not isinstance(pairs_raw, list)
            or not all(isinstance(p, list) and len(p) == 2 and all(isinstance(v, str) and v for v in p)
                       for p in pairs_raw)):
        raise ConfigError(f"'fit.overlap_allowed_pairs' phải là danh sách cặp class [a, b], nhận {pairs_raw!r}")
    cfg = FitConfig(
        empty_max_points=r.integer("empty_max_points", 0),
        sparse_warning_points=r.integer("sparse_warning_points", 0),
        outside_margin_m=r.number("outside_margin_m", 0.0),
        outside_margin_rel=r.number("outside_margin_rel", 0.0),
        outside_min_points=r.integer("outside_min_points", 1),
        outside_warning_ratio=r.number("outside_warning_ratio", 0.0),
        outside_error_ratio=r.number("outside_error_ratio", 0.0),
        ground_clearance_m=r.number("ground_clearance_m", 0.0),
        loose_min_points=r.integer("loose_min_points", 1),
        loose_max_range_m=r.number("loose_max_range_m", 0.0),
        loose_warning_m=r.number("loose_warning_m", 0.0),
        loose_error_m=r.number("loose_error_m", 0.0),
        overlap_warning=r.number("overlap_warning", 0.0),
        overlap_error=r.number("overlap_error", 0.0),
        overlap_classes=r.strings("overlap_classes"),
        overlap_allowed_pairs=tuple((a, b) for a, b in pairs_raw),
    )
    r.finish()
    for low, high in (("outside_warning_ratio", "outside_error_ratio"), ("loose_warning_m", "loose_error_m"),
                      ("overlap_warning", "overlap_error")):
        _require_order("fit", getattr(cfg, low), getattr(cfg, high), low, high)
    if cfg.outside_error_ratio > 1 or cfg.overlap_error > 1:
        raise ConfigError("'fit.outside_error_ratio' và 'fit.overlap_error' phải <= 1")
    return cfg


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
        **({"sweeps": r.integer("sweeps", 0)} if "sweeps" in r.keys() else {}),
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
    key_attributes: dict[str, str] = {}
    if "key_attributes" in r.keys():
        kr = r.section("key_attributes")
        key_attributes = {label: kr.string(label) for label in kr.keys()}
        kr.finish()
    r.finish()
    return SizeConfig(class_range=class_range, manual_ranges=manual, in_track=in_track, key_attributes=key_attributes)


def _parse_track(r: _Reader) -> TrackConfig:
    keyframe_interval_s = r.number("keyframe_interval_s", 0.0)
    if keyframe_interval_s == 0:
        raise ConfigError("'track.keyframe_interval_s' phải > 0")
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
        **({"max_occluded_frames": r.integer("max_occluded_frames", 1)} if "max_occluded_frames" in r.keys() else {}),
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
    cvat = _parse_cvat(r.section("cvat"), env)
    rules = _parse_rules(r.section("rules")) if "rules" in r.keys() else RulesConfig()
    cfg = Config(
        cvat=cvat,
        floating=_parse_floating(r.section("floating")),
        size=_parse_size(r.section("size")),
        track=_parse_track(r.section("track")),
        gate=_parse_gate(r.section("gate")),
        rules=rules,
        heading=_parse_heading(r.section("heading")) if "heading" in r.keys() else HeadingConfig(),
        fit=_parse_fit(r.section("fit")) if "fit" in r.keys() else FitConfig(),
        spec=_parse_spec(r.section("spec")) if "spec" in r.keys() else SpecConfig(),
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
