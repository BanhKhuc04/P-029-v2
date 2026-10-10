"""Đánh giá các bộ phát hiện bằng lỗi chèn giả trên nhãn chuẩn nuScenes (việc B6, mục 8 của đề xuất).

Với mỗi cảnh:
1. Quét nhãn chuẩn chưa chèn lỗi → báo động giả trên nhãn sạch (số mục / 100 box theo từng mức).
2. Lặp `rounds` vòng: chèn lỗi vào ~10% số track (`core.synthetic.inject_dataset`), quét lại, ghép finding với lỗi
   đã chèn.

Một lỗi chèn được tính là **bắt được** khi tool báo đúng box (hoặc đúng track, với lỗi cả track) bằng luật cùng loại,
ở mức Cảnh báo trở lên. Finding không khớp lỗi chèn nào được tính là báo nhầm khi tính precision; trong số đó có
cả lỗi thật của nhãn chuẩn, nên người test (T2) cần xem tay trước khi chốt.
"""

from __future__ import annotations

import json
import time
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Iterable, Sequence

import numpy as np

from pointsnap.adapters.nuscenes import NuScenesReader
from pointsnap.core.config import Config
from pointsnap.core.model import Cuboid, Finding, Severity, add_track_markers
from pointsnap.core.scanner import actionable, scan_cuboids
from pointsnap.core.synthetic import InjectedError, inject_dataset

# Luật được tính là "đúng loại" cho từng kiểu lỗi chèn.
RULES_FOR = {
    "floating": ("floating",),
    "size_in_track": ("size.in_track", "size.class_range"),
    "size_class_range": ("size.class_range", "size.in_track"),
    "track_jump": ("track.jump", "track.static_shift", "cam.mismatch"),
    "track_split_id": ("track.split_id",),
    "track_interpolation": ("track.long_interpolation",),
    "heading_rotate": ("heading.flip", "heading.points", "heading.motion", "heading.static", "critic.box"),
    "heading_reverse": ("heading.motion", "heading.flip"),
    "fit_shift": ("fit.outside", "fit.loose", "fit.empty", "track.static_shift", "cam.mismatch", "critic.box"),
    "fit_scale": ("fit.outside", "fit.loose", "cam.mismatch", "critic.box"),
    "fit_duplicate": ("fit.overlap",),
}
CATEGORY = {"floating": "floating", "size_in_track": "size", "size_class_range": "size",
            "track_jump": "track", "track_split_id": "track", "track_interpolation": "track",
            "heading_rotate": "heading", "heading_reverse": "heading",
            "fit_shift": "fit", "fit_scale": "fit", "fit_duplicate": "fit"}
CATEGORIES = ("floating", "size", "track", "heading", "fit")

# Mức chèn được dùng để tính "phân mức đúng" (mục 8.2): phải báo ở mức Lỗi.
LARGE = {("floating", "0.4"), ("size_in_track", "0.3"), ("track_jump", "4.0"), ("heading_rotate", "180")}


def magnitude_key(error: InjectedError) -> str:
    """Nhãn mức độ của lỗi chèn, dùng để gom bảng recall theo mức."""
    if error.error_type == "floating":
        return f"{abs(float(error.magnitude)):.2g}"
    if error.error_type == "size_in_track":
        return f"{float(error.magnitude):.2g}"
    if error.error_type == "size_class_range":
        return "other_class" if error.magnitude == "override" else f"x{float(error.magnitude):g}"
    if error.error_type == "track_jump":
        return f"{float(error.magnitude):.1f}"
    if error.error_type == "track_interpolation":
        return f"{int(error.magnitude)}"
    if error.error_type in ("heading_rotate", "heading_reverse"):
        return f"{float(error.magnitude):.0f}"
    if error.error_type == "fit_shift":
        return f"{float(error.magnitude):.1f}"
    if error.error_type == "fit_scale":
        return f"x{float(error.magnitude):g}"
    return "-"


def _gap_frames(error: InjectedError) -> set[int]:
    start = int(error.frame)
    return set(range(start, start + int(error.magnitude)))


def matches(error: InjectedError, finding: Finding) -> bool:
    """Finding có báo đúng lỗi chèn này không (đúng loại luật, đúng track, đúng box nếu lỗi gắn với một box)."""
    if finding.rule not in RULES_FOR[error.error_type] or finding.severity is Severity.INFO:
        return False
    kind = error.error_type
    if kind == "track_split_id":
        return finding.track_id == error.injected_value and finding.frame == error.frame
    if kind == "fit_duplicate":
        return finding.frame == error.frame and finding.track_id in (error.track_id, error.injected_value)
    if finding.track_id != error.track_id:
        return False
    if kind in ("size_class_range", "heading_reverse"):
        return True
    if kind == "track_interpolation":
        next_keyframe = finding.details.get("next_keyframe", finding.frame + 1)
        return set(range(finding.frame + 1, next_keyframe)) & _gap_frames(error) != set()
    return finding.frame == error.frame


@dataclass
class ErrorOutcome:
    scene: str
    round: int
    error_type: str
    magnitude: str
    track_id: int
    frame: int | None
    label: str
    applicable: bool  # lỗi thuộc phạm vi luật: class được xét; với khoảng nội suy, đối tượng đang di chuyển
    detected: bool
    severity: str | None  # mức cao nhất trong các finding khớp
    measured: float | None  # số đo tool báo (finding khớp đầu tiên)
    expected: float | None  # số đo đúng của lỗi chèn
    has_ground_evidence: bool | None  # chỉ với lơ lửng / lún: box có đủ điểm mặt đất trên nhãn sạch không


@dataclass
class SceneStats:
    scene: str
    boxes: int
    clean: dict[str, int] = field(default_factory=dict)  # "rule|severity" -> số mục trên nhãn sạch
    findings_total: dict[str, int] = field(default_factory=dict)  # category -> số finding (Cảnh báo+) sau chèn
    findings_matched: dict[str, int] = field(default_factory=dict)  # category -> số finding khớp một lỗi chèn
    findings_on_injected: dict[str, int] = field(default_factory=dict)  # category -> số finding nằm trên box bị chèn lỗi
    scan_seconds: float = 0.0


def _expected_value(error: InjectedError) -> float | None:
    if error.error_type == "floating":
        return float(error.injected_value) - float(error.original_value)
    if error.error_type == "size_in_track":
        return float(error.magnitude)
    if error.error_type == "track_jump":
        return float(error.magnitude)
    if error.error_type == "heading_rotate":
        return float(error.magnitude)
    return None


def _world_speeds(track: list[Cuboid], frames) -> list[float]:
    """Tốc độ (m/s) giữa các keyframe liền nhau của track, trong hệ toàn cục."""
    speeds = []
    for a, b in zip(track, track[1:]):
        da, db = (frames.frame_data(x.frame, with_points=False) for x in (a, b))
        wa, wb = (d.sensor_to_world @ np.array([*x.center, 1.0]) for d, x in ((da, a), (db, b)))
        dt = (db.timestamp - da.timestamp) if db.timestamp and da.timestamp else 0.5 * (b.frame - a.frame)
        speeds.append(float(np.linalg.norm(wb[:2] - wa[:2])) / dt if dt > 0 else 0.0)
    return speeds


def on_injected_box(error: InjectedError, finding: Finding) -> bool:
    """Finding nằm trên box (hoặc track, với lỗi cả track) bị chèn lỗi, bất kể luật nào báo.

    Ví dụ dời box 1 m: luật nhảy vị trí và luật box lệch đều báo đúng box sai, nên không tính là báo nhầm.
    """
    if finding.severity is Severity.INFO:
        return False
    tracks = {error.track_id}
    if error.error_type in ("track_split_id", "fit_duplicate"):
        tracks.add(error.injected_value)
    if finding.track_id not in tracks:
        return False
    if error.frame is None or error.error_type in ("size_class_range", "heading_reverse", "track_split_id"):
        return True
    if error.error_type == "track_interpolation":
        return abs(finding.frame - int(error.frame)) <= int(error.magnitude) + 1
    return finding.frame == error.frame


def is_applicable(error: InjectedError, label: str, clean_boxes: list[Cuboid], config: Config, frames) -> bool:
    kind = error.error_type
    if kind.startswith(("heading", "fit")):
        track = sorted((b for b in clean_boxes if b.track_id == error.track_id and not b.outside),
                       key=lambda b: b.frame)
        box = next((b for b in track if b.frame == error.frame), None)
        points = int(box.attrs.get("num_lidar_pts", 0)) if box is not None else 0
        group = config.heading.group_for(label)
        if kind == "heading_reverse":
            return group is not None and any(v >= group.min_speed_mps for v in _world_speeds(track, frames))
        if kind == "heading_rotate":
            by_flip = group is not None and float(error.magnitude) > group.flip_warning_deg and len(track) >= 2
            pc = config.heading.points
            by_points = (label in pc.classes and points >= pc.min_points and box is not None
                         and box.length >= pc.min_aspect * box.width and float(error.magnitude) % 90 > pc.warning_deg
                         and 90 - float(error.magnitude) % 90 > pc.warning_deg)
            return by_flip or by_points
        if kind == "fit_duplicate":
            return (label in config.fit.overlap_classes
                    and frozenset((label, label)) not in {frozenset(p) for p in config.fit.overlap_allowed_pairs})
        return points >= config.fit.outside_min_points
    if error.error_type == "floating":
        return label in config.floating.classes
    if error.error_type == "size_in_track":
        return label not in config.size.in_track.excluded_classes
    if error.error_type == "track_interpolation":
        track = {b.frame: b for b in clean_boxes if b.track_id == error.track_id and not b.outside}
        before, after = track.get(int(error.frame) - 1), track.get(int(error.frame) + int(error.magnitude))
        if before is None or after is None:
            return False
        world = [frames.frame_data(b.frame, with_points=False).sensor_to_world @ np.array([*b.center, 1.0])
                 for b in (before, after)]
        return float(np.linalg.norm(world[1][:2] - world[0][:2])) > config.track.long_interpolation.min_motion_m
    return True


def no_evidence_frames(findings: Iterable[Finding]) -> dict[int | None, set[int]]:
    result: dict[int | None, set[int]] = defaultdict(set)
    for f in findings:
        if f.rule == "floating.no_evidence":
            result[f.track_id].update(f.details.get("frames", [f.frame]))
    return result


def evaluate_scene(
    reader: NuScenesReader, scene: str, config: Config, rounds: int = 10, seed: int = 0, error_rate: float = 0.10,
    catalog: str = "core",
) -> tuple[SceneStats, list[ErrorOutcome]]:
    frames = reader.frames(scene)
    clean_boxes = add_track_markers(reader.annotations(scene), frames.num_frames)
    num_boxes = sum(1 for b in clean_boxes if b.visible)  # không tính box occluded do add_track_markers thêm

    started = time.perf_counter()
    clean_findings = scan_cuboids(clean_boxes, config, frames)
    stats = SceneStats(scene=scene, boxes=num_boxes, scan_seconds=time.perf_counter() - started)
    for f in clean_findings:
        key = f"{f.rule}|{f.severity.value}"
        stats.clean[key] = stats.clean.get(key, 0) + 1
    no_evidence = no_evidence_frames(clean_findings)
    labels = {b.track_id: b.label for b in clean_boxes}

    outcomes: list[ErrorOutcome] = []
    total: dict[str, int] = defaultdict(int)
    matched_count: dict[str, int] = defaultdict(int)
    on_injected: dict[str, int] = defaultdict(int)
    for rnd in range(rounds):
        injected_boxes, errors = inject_dataset(clean_boxes, seed=seed + rnd, error_rate=error_rate, offset=rnd * 7,
                                                catalog=catalog)
        findings = actionable(scan_cuboids(injected_boxes, config, frames))
        used: set[int] = set()
        for error in errors:
            hits = [i for i, f in enumerate(findings) if matches(error, f)]
            used.update(hits)
            best = min((findings[i] for i in hits), key=lambda f: f.severity.rank, default=None)
            primary = next((findings[i] for i in hits if findings[i].rule == RULES_FOR[error.error_type][0]), None)
            evidence = None
            if error.error_type == "floating":
                evidence = (labels[error.track_id] in config.floating.classes
                            and error.frame not in no_evidence.get(error.track_id, set()))
            outcomes.append(ErrorOutcome(
                scene=scene, round=rnd, error_type=error.error_type, magnitude=magnitude_key(error),
                track_id=error.track_id, frame=error.frame, label=labels[error.track_id],
                applicable=is_applicable(error, labels[error.track_id], clean_boxes, config, frames),
                detected=best is not None,
                severity=best.severity.value if best else None,
                measured=primary.value if primary else None, expected=_expected_value(error),
                has_ground_evidence=evidence,
            ))
        for i, f in enumerate(findings):
            category = f.error_type.value
            total[category] += 1
            matched_count[category] += i in used
            on_injected[category] += i in used or any(on_injected_box(e, f) for e in errors)
    stats.findings_total = dict(total)
    stats.findings_matched = dict(matched_count)
    stats.findings_on_injected = dict(on_injected)
    return stats, outcomes


# --- Tổng hợp -------------------------------------------------------------------------------------


def _pct(num: int, den: int) -> str:
    return f"{num / den * 100:.0f}% ({num}/{den})" if den else "—"


def summarize(stats: Sequence[SceneStats], outcomes: Sequence[ErrorOutcome]) -> dict[str, Any]:
    boxes = sum(s.boxes for s in stats)
    clean: dict[str, int] = defaultdict(int)
    for s in stats:
        for key, n in s.clean.items():
            clean[key] += n

    recall: dict[str, dict[str, Any]] = {}
    groups: dict[tuple[str, str], list[ErrorOutcome]] = defaultdict(list)
    for o in outcomes:
        groups[(o.error_type, o.magnitude)].append(o)
    for (kind, mag), items in sorted(groups.items()):
        row = {
            "n": len(items),
            "detected": sum(o.detected for o in items),
            "as_error": sum(o.severity == "error" for o in items),
            "n_applicable": sum(o.applicable for o in items),
            "detected_applicable": sum(o.detected for o in items if o.applicable),
        }
        if kind == "floating":
            with_evidence = [o for o in items if o.has_ground_evidence]
            row["n_evidence"] = len(with_evidence)
            row["detected_evidence"] = sum(o.detected for o in with_evidence)
        recall[f"{kind}|{mag}"] = row

    precision = {}
    for category in CATEGORIES:
        tot = sum(s.findings_total.get(category, 0) for s in stats)
        hit = sum(s.findings_matched.get(category, 0) for s in stats)
        any_hit = sum(s.findings_on_injected.get(category, 0) for s in stats)
        precision[category] = {"findings": tot, "matched": hit, "on_injected": any_hit}

    accuracy = {}
    for kind, unit in (("floating", 100.0), ("size_in_track", 100.0), ("track_jump", 1.0), ("heading_rotate", 1.0)):
        errs = [abs(abs(o.measured) - abs(o.expected)) * unit for o in outcomes
                if o.error_type == kind and o.detected and o.measured is not None and o.expected is not None]
        accuracy[kind] = {"n": len(errs), "median_abs_error": float(np.median(errs)) if errs else None}

    large = [o for o in outcomes if (o.error_type, o.magnitude) in LARGE and o.applicable
             and o.has_ground_evidence is not False]
    return {
        "scenes": [s.scene for s in stats],
        "boxes": boxes,
        "clean_per_100_boxes": {k: round(v / boxes * 100, 3) for k, v in sorted(clean.items())},
        "clean_counts": dict(sorted(clean.items())),
        "recall": recall,
        "large_as_error": {"n": len(large), "as_error": sum(o.severity == "error" for o in large)},
        "precision": precision,
        "measurement_accuracy": accuracy,
        "scan_seconds": {s.scene: round(s.scan_seconds, 2) for s in stats},
    }


def to_markdown(summary: dict[str, Any], title: str) -> str:
    lines = [f"# {title}", "", f"Cảnh: {', '.join(summary['scenes'])} · {summary['boxes']} box nhãn chuẩn", ""]

    lines += ["## Báo động giả trên nhãn sạch (số mục / 100 box)", "", "| Luật | Mức | Số mục | / 100 box |",
              "|---|---|---|---|"]
    for key, n in summary["clean_counts"].items():
        rule, severity = key.split("|")
        lines.append(f"| `{rule}` | {severity} | {n} | {summary['clean_per_100_boxes'][key]:.2f} |")
    for severity, target in (("warning", 2.0), ("error", 0.5)):
        value = sum(v for k, v in summary["clean_per_100_boxes"].items()
                    if k.endswith(f"|{severity}") and not k.startswith("floating.no_evidence"))
        lines.append(f"| **Tổng** | {severity} | | **{value:.2f}** (mục tiêu ≤ {target}) |")

    lines += ["", "## Recall trên lỗi chèn giả", "",
              "Bắt được = báo đúng box / track bằng luật cùng loại, mức Cảnh báo trở lên.", "",
              "Thuộc phạm vi = class mà luật xét (lơ lửng / lún: class tiếp đất; kích thước trong track: trừ người đi bộ) "
              "và, với khoảng nội suy, đối tượng dịch > min_motion_m trong đoạn bị xóa. Sai hướng: xoay đủ lớn để luật "
              "lật hướng xét, hoặc box đủ điểm để so với cụm điểm; ngược cả track: vật có lúc chạy nhanh hơn min_speed. "
              "Box lệch: box có ít nhất outside_min_points điểm (theo nhãn chuẩn).", "",
              "| Kiểu lỗi | Mức chèn | Số lỗi | Bắt được | Bắt được (thuộc phạm vi) | Báo ở mức Lỗi "
              "| Bắt được (box có đủ điểm mặt đất) |",
              "|---|---|---|---|---|---|---|"]
    for key, row in summary["recall"].items():
        kind, mag = key.split("|")
        extra = _pct(row["detected_evidence"], row["n_evidence"]) if "n_evidence" in row else ""
        lines.append(f"| {kind} | {mag} | {row['n']} | {_pct(row['detected'], row['n'])} | "
                     f"{_pct(row['detected_applicable'], row['n_applicable'])} | "
                     f"{_pct(row['as_error'], row['n'])} | {extra} |")
    large = summary["large_as_error"]
    lines += ["", f"**Phân mức đúng** (Z 40 cm, kích thước 30%, nhảy 4 m, lật box 180° báo ở mức Lỗi; lỗi thuộc phạm vi, có bằng chứng): "
                  f"{_pct(large['as_error'], large['n'])} (mục tiêu ≥ 80%)"]

    lines += ["", "## Precision sau khi chèn lỗi", "",
              "Finding không khớp lỗi chèn nào bị tính là báo nhầm; trong đó có cả lỗi thật của nhãn chuẩn, cần xem tay "
              "(việc T2) trước khi chốt. Cột cuối tính cả finding nằm trên box bị chèn lỗi loại khác (vd dời box 1 m: "
              "luật box lệch báo đúng box sai dù lỗi chèn thuộc loại nhảy vị trí).", "",
              "| Loại | Finding (Cảnh báo+) | Khớp lỗi chèn cùng loại | Precision | Trên box bị chèn lỗi bất kỳ |",
              "|---|---|---|---|---|"]
    for category, row in summary["precision"].items():
        lines.append(f"| {category} | {row['findings']} | {row['matched']} | {_pct(row['matched'], row['findings'])} | "
                     f"{_pct(row.get('on_injected', row['matched']), row['findings'])} |")

    acc = summary["measurement_accuracy"]
    lines += ["", "## Độ chính xác của số đo (trung vị sai số tuyệt đối)", "", "| Kiểu lỗi | Số mẫu | Sai số |", "|---|---|---|"]
    for kind, unit in (("floating", "cm"), ("size_in_track", "điểm %"), ("track_jump", "m"), ("heading_rotate", "°")):
        if kind not in acc:
            continue
        value = acc[kind]["median_abs_error"]
        lines.append(f"| {kind} | {acc[kind]['n']} | {value:.2f} {unit} |" if value is not None else f"| {kind} | 0 | — |")

    seconds = summary["scan_seconds"]
    lines += ["", "## Hiệu năng", "", "Thời gian quét nhãn sạch (đọc point cloud + mọi bộ phát hiện), mỗi cảnh:", ""]
    lines += [f"- {scene}: {sec:.1f} s" for scene, sec in seconds.items()]
    return "\n".join(lines) + "\n"


def run_evaluation(
    reader: NuScenesReader, scenes: Sequence[str], config: Config, out_dir: str | Path, rounds: int = 10,
    seed: int = 0, title: str = "Kết quả đánh giá PointSnap 3D", progress=print, catalog: str = "all",
) -> dict[str, Any]:
    stats: list[SceneStats] = []
    outcomes: list[ErrorOutcome] = []
    for scene in scenes:
        s, o = evaluate_scene(reader, scene, config, rounds=rounds, seed=seed, catalog=catalog)
        stats.append(s)
        outcomes.extend(o)
        progress(f"{scene}: {s.boxes} box, {len(o)} lỗi chèn, bắt được {sum(x.detected for x in o)}")
    summary = summarize(stats, outcomes)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")
    (out / "outcomes.json").write_text(json.dumps([asdict(o) for o in outcomes], ensure_ascii=False, indent=1),
                                       encoding="utf-8")
    (out / "ket-qua.md").write_text(to_markdown(summary, title), encoding="utf-8")
    return summary
