"""Vẽ hình minh họa thuật toán cho báo cáo (docs/bao-cao-du-an.md) từ dữ liệu nuScenes thật.

Mỗi hình chạy đúng code của PointSnap (ước lượng mặt đất, luật nhảy vị trí, sót đối tượng, chiếu box lên ảnh) trên
scene-0061, nên hình khớp với cách tool làm thật. Biểu đồ kết quả đọc `summary.json` của `pointsnap eval`.

    python scripts/ve_hinh_minh_hoa.py --dataroot D:/data/nuscenes --eval-test out/eval/test/summary.json
    # ra docs/hinh/thuat-toan/*.png

Cần matplotlib (`pip install matplotlib`).
"""

from __future__ import annotations

import argparse
import json
import math
import os
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from matplotlib.patches import FancyArrowPatch, Polygon  # noqa: E402

from pointsnap.adapters.nuscenes.reader import NuScenesReader  # noqa: E402
from pointsnap.core.camera import project_box  # noqa: E402
from pointsnap.core.config import load_config  # noqa: E402
from pointsnap.core.geometry import footprint, footprint_ring_mask, points_in_cuboid, to_box_frame  # noqa: E402
from pointsnap.core.ground import OtherBoxPoints, filter_min_z_grid, ring_ground_for_box  # noqa: E402
from pointsnap.detectors.missing import detect_missing_objects  # noqa: E402
from pointsnap.detectors.track import detect_track_jumps_for_track  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "hinh" / "thuat-toan"
SCENE = "scene-0061"

C_POINT, C_GROUND, C_BOX, C_BAD, C_OK, C_GOAL = "#9aa4b2", "#2e8b57", "#1f5fbf", "#d62728", "#2ca02c", "#7f7f7f"
plt.rcParams.update({"figure.dpi": 110, "savefig.dpi": 140, "font.size": 10, "axes.titlesize": 11,
                     "axes.spines.top": False, "axes.spines.right": False})


def _save(fig, name: str) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT / name, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print("->", OUT / name)


def _poly(ax, box, **kw):
    ax.add_patch(Polygon(footprint(box), closed=True, fill=False, **kw))


def _arrow(ax, box, color, length=None, **kw):
    length = length or box.dims[0] * 0.6
    x, y = box.center[:2]
    ax.add_patch(FancyArrowPatch((x, y), (x + length * math.cos(box.yaw), y + length * math.sin(box.yaw)),
                                 arrowstyle="-|>", mutation_scale=14, color=color, lw=2, **kw))


def _to_world(m, xy):
    xy = np.atleast_2d(xy)
    pts = np.column_stack([xy[:, 0], xy[:, 1], np.zeros(len(xy))])
    return (pts @ m[:3, :3].T + m[:3, 3])[:, :2]


class Scene:
    def __init__(self, dataroot: str):
        self.reader = NuScenesReader(dataroot)
        self.frames = self.reader.frames(SCENE)
        self.boxes = self.reader.annotations(SCENE)
        self.cfg = load_config(None)
        self._points = {}
        self._best = {}

    def points(self, frame):
        if frame not in self._points:
            self._points[frame] = np.asarray(self.frames.frame_data(frame).points, dtype=float)[:, :3]
        return self._points[frame]

    def pose(self, frame):
        return self.frames.frame_data(frame, with_points=False).sensor_to_world

    def at(self, frame):
        return [b for b in self.boxes if b.frame == frame and b.visible]

    def track(self, tid):
        return sorted((b for b in self.boxes if b.track_id == tid and b.visible), key=lambda b: b.frame)

    def best_car(self, max_range=30.0, min_points=150, max_ground_offset=0.06):
        """Xe gần, nhiều điểm, đáy sát mặt đất ước lượng (|d| nhỏ) — dùng cho hình mặt đất / hướng / box lệch."""
        key = (max_range, min_points, max_ground_offset)
        if key in self._best:
            return self._best[key]
        fc = self.cfg.floating
        best, score = None, -1
        for frame in range(0, self.frames.num_frames, 2):
            pts = self.points(frame)
            boxes = self.at(frame)
            for i, b in enumerate(boxes):
                if b.label != "car" or np.hypot(*b.center[:2]) > max_range:
                    continue
                n = int(points_in_cuboid(pts, b).sum())
                if n < min_points:
                    continue
                clean = OtherBoxPoints(pts, boxes).without_others(i, reach=8.0)
                est = ring_ground_for_box(clean, b, ring_inner_m=fc.ring_inner_m, ring_outer_m=fc.ring_outer_m,
                                          min_ground_points=fc.min_ground_points)
                if not est.is_valid or abs(est.distance) > max_ground_offset:
                    continue
                if n + est.num_ground_points > score:
                    best, score = b, n + est.num_ground_points
        self._best[key] = best
        return best

    def moving_car_track(self, min_frames=20, min_motion=15.0):
        best, dist = None, 0.0
        for tid in {b.track_id for b in self.boxes if b.label == "car"}:
            tr = self.track(tid)
            if len(tr) < min_frames:
                continue
            w = np.vstack([_to_world(self.pose(b.frame), b.center[:2]) for b in tr])
            d = float(np.linalg.norm(w[-1] - w[0]))
            if d > max(dist, min_motion):
                best, dist = tid, d
        return best


# --------------------------------------------------------------------------------------------- 1. mặt đất vành đai


def fig_ground(sc: Scene) -> None:
    box = sc.best_car()
    pts = sc.points(box.frame)
    boxes = sc.at(box.frame)
    clean = OtherBoxPoints(pts, boxes).without_others(boxes.index(box), reach=8.0)
    fc = sc.cfg.floating
    est = ring_ground_for_box(clean, box, ring_inner_m=fc.ring_inner_m, ring_outer_m=fc.ring_outer_m,
                              min_ground_points=fc.min_ground_points)
    ring = clean[footprint_ring_mask(clean, box, inner=fc.ring_inner_m, outer=fc.ring_outer_m)]
    ring = ring[np.abs(ring[:, 2] - box.bottom_z) <= 0.8]
    ground = ring[filter_min_z_grid(ring, cell_size=0.4, height_threshold=0.08)]

    fig, (a, b) = plt.subplots(1, 2, figsize=(12, 5), gridspec_kw={"width_ratios": [1, 1.25]})
    near = clean[(np.abs(clean[:, 0] - box.center[0]) < 6) & (np.abs(clean[:, 1] - box.center[1]) < 6)]
    a.scatter(near[:, 0], near[:, 1], s=1.5, c=C_POINT, label="điểm LiDAR")
    a.scatter(ground[:, 0], ground[:, 1], s=4, c=C_GROUND, label="điểm mặt đất trong vành đai")
    _poly(a, box, color=C_BOX, lw=2, label="box nhãn")
    a.add_patch(Polygon(footprint(box, margin=fc.ring_outer_m), closed=True, fill=False, ls="--", color=C_GROUND, lw=1))
    a.add_patch(Polygon(footprint(box, margin=fc.ring_inner_m), closed=True, fill=False, ls=":", color=C_GROUND, lw=1))
    a.set_aspect("equal")
    a.set_title(f"Nhìn từ trên: vành đai {fc.ring_inner_m:.1f}–{fc.ring_outer_m:.1f} m quanh đáy box")
    a.set_xlabel("x (m)")
    a.set_ylabel("y (m)")
    a.legend(loc="lower left", fontsize=8, markerscale=3)

    local = to_box_frame(near, box)
    side = near[np.abs(local[:, 1]) < box.dims[1] / 2 + 1.0]
    sl = to_box_frame(side, box)
    gl = to_box_frame(ground, box)
    b.scatter(sl[:, 0], side[:, 2], s=2, c=C_POINT)
    b.scatter(gl[:, 0], ground[:, 2], s=6, c=C_GROUND)
    L, H = box.dims[0], box.dims[2]
    bottom = box.bottom_z
    b.add_patch(Polygon([(-L / 2, bottom), (L / 2, bottom), (L / 2, bottom + H), (-L / 2, bottom + H)],
                        closed=True, fill=False, color=C_BOX, lw=2))
    lift = 0.25
    b.add_patch(Polygon([(-L / 2, bottom + lift), (L / 2, bottom + lift), (L / 2, bottom + lift + H),
                         (-L / 2, bottom + lift + H)], closed=True, fill=False, color=C_BAD, lw=1.5, ls="--"))
    b.axhline(est.ground_z, color=C_GROUND, lw=1.5, ls="-")
    b.annotate("", xy=(L / 2 + 0.35, est.ground_z), xytext=(L / 2 + 0.35, bottom + lift),
               arrowprops={"arrowstyle": "<->", "color": C_BAD})
    b.text(L / 2 + 0.5, (est.ground_z + bottom + lift) / 2,
           f"d = đáy box − mặt đất\nbox đỏ (nâng 25 cm): d ≈ {(bottom + lift - est.ground_z) * 100:.0f} cm → Lỗi",
           color=C_BAD, va="center", fontsize=9)
    b.text(-L / 2, est.ground_z - 0.18, f"mặt đất = trung vị điểm xanh ({len(ground)} điểm); box nhãn: d = "
           f"{est.distance * 100:+.0f} cm", color=C_GROUND, fontsize=9)
    b.set_xlim(-L / 2 - 1.5, L / 2 + 3.6)
    b.set_ylim(est.ground_z - 0.4, bottom + H + 0.6)
    b.set_title("Nhìn ngang (dọc thân xe)")
    b.set_xlabel("dọc thân box (m)")
    b.set_ylabel("z (m)")
    fig.suptitle(f"Lơ lửng / lún: đo đáy box so với mặt đất cục bộ — {SCENE}, frame {box.frame}, ô tô "
                 f"{box.dims[0]:.1f} m", fontsize=12)
    _save(fig, "1-mat-dat-vanh-dai.png")


# ---------------------------------------------------------------------------------------------------- 2. mặt dốc


def fig_slope() -> None:
    deg, L, H = 8.0, 4.5, 1.6
    t = math.tan(math.radians(deg))
    fig, axes = plt.subplots(1, 2, figsize=(13, 4.2), sharey=True)
    for ax, slope, title in ((axes[0], 0.0, "Đường bằng"), (axes[1], t, f"Dốc {deg:.0f}° (box không có pitch / roll)")):
        xs = np.linspace(-4, 5.4, 50)
        ax.fill_between(xs, -1, slope * xs, color="#e9ecef")
        ax.plot(xs, slope * xs, color=C_GROUND, lw=2)
        contact = slope * (-L / 2)
        ax.add_patch(Polygon([(-L / 2, contact), (L / 2, contact), (L / 2, contact + H), (-L / 2, contact + H)],
                             closed=True, fill=False, color=C_BOX, lw=2))
        ring = np.r_[np.linspace(-L / 2 - 0.8, -L / 2 - 0.1, 6), np.linspace(L / 2 + 0.1, L / 2 + 0.8, 6)]
        ax.scatter(ring, slope * ring, color=C_GROUND, zorder=3, s=18)
        median = float(np.median(slope * ring))
        ax.axhline(median, color=C_BAD, ls="--", lw=1)
        ax.plot([-L / 2], [contact], "o", color=C_OK, ms=8, zorder=4)
        if slope:
            ax.annotate("", xy=(L / 2 + 0.25, median), xytext=(L / 2 + 0.25, contact),
                        arrowprops={"arrowstyle": "<->", "color": C_BAD})
            ax.text(L / 2 + 0.4, contact - 0.55, f"đáy box thấp hơn trung vị vành đai\n{abs(contact - median) * 100:.0f} cm"
                    " = tan(dốc) × nửa chiều dài\n→ so trung vị: báo nhầm \"lún\"", color=C_BAD, fontsize=8.5,
                    va="center")
            ax.text(-L / 2, contact - 0.75, "điểm tiếp xúc thấp nhất\n(C4 so với điểm này: 0 cm)", color=C_OK,
                    fontsize=8.5, ha="center")
        else:
            ax.text(0.2, median + 0.08, "trung vị vành đai = mặt đất", color=C_BAD, fontsize=9)
        ax.set_title(title)
        ax.set_aspect("equal")
        ax.set_xlim(-4, 5.4)
        ax.set_ylim(-1.3, 2.0)
        ax.set_xlabel("m")
    fig.suptitle("C4 — Trên dốc, đáy box đúng spec chạm mặt đường ở góc thấp nhất; so trung vị sẽ báo nhầm \"lún\"",
                 fontsize=12)
    _save(fig, "2-mat-doc-diem-tiep-xuc.png")


# ------------------------------------------------------------------------------------------------- 3. nhảy track


def fig_track_jump(sc: Scene) -> None:
    tid = sc.moving_car_track()
    tr = sc.track(tid)
    k = len(tr) // 2
    jumped = list(tr)
    shift = 2.0
    b = tr[k]
    jumped[k] = b.replace(center=(b.center[0] + shift * -math.sin(b.yaw), b.center[1] + shift * math.cos(b.yaw),
                                  b.center[2]))
    poses = {x.frame: sc.pose(x.frame) for x in tr}
    findings = detect_track_jumps_for_track(jumped, sc.cfg.track, poses)
    w = np.vstack([_to_world(poses[x.frame], x.center[:2]) for x in jumped])
    w0 = np.vstack([_to_world(poses[x.frame], x.center[:2]) for x in tr])

    fig, ax = plt.subplots(figsize=(10, 5.2))
    ax.plot(w0[:, 0], w0[:, 1], "-", color=C_GOAL, lw=1, label="quỹ đạo nhãn chuẩn")
    ax.scatter(w[:, 0], w[:, 1], s=22, c=C_BOX, zorder=3, label="tâm box từng keyframe")
    ax.scatter([w[k, 0]], [w[k, 1]], s=90, c=C_BAD, zorder=4, label=f"frame {b.frame}: box bị dời {shift:.0f} m")
    pred = (w[k - 1] + w[k + 1]) / 2
    ax.scatter([pred[0]], [pred[1]], s=90, facecolors="none", edgecolors=C_OK, lw=2, zorder=4,
               label="vị trí nội suy từ hai frame bên cạnh")
    ax.annotate("", xy=w[k], xytext=pred, arrowprops={"arrowstyle": "->", "color": C_BAD, "lw": 1.5})
    msg = next((f for f in findings if f.frame == b.frame), None)
    if msg:
        ax.text(0.01, 0.02, f"PointSnap: [{msg.severity.value}] {msg.message}", transform=ax.transAxes, fontsize=8.5,
                color=C_BAD, wrap=True)
    ax.set_aspect("equal")
    ax.set_xlabel("x toàn cục (m)")
    ax.set_ylabel("y toàn cục (m)")
    ax.legend(fontsize=8, loc="upper left")
    ax.set_title(f"Đứt track — nhảy vị trí: {SCENE}, ô tô track {tid} ({len(tr)} keyframe), hệ toàn cục (đã bù "
                 "chuyển động xe thu)")
    _save(fig, "3-track-nhay-vi-tri.png")


# ---------------------------------------------------------------------------------------- 4–5. hướng box, box lệch


def _car_points(sc: Scene, box, margin=0.4):
    pts = sc.points(box.frame)
    inside = pts[points_in_cuboid(pts, box, margin=margin)]
    return inside[inside[:, 2] > box.bottom_z + 0.2]


def fig_heading(sc: Scene) -> None:
    box = sc.best_car()
    car = _car_points(sc, box)
    tr = sc.track(box.track_id)
    i = next(j for j, x in enumerate(tr) if x.frame == box.frame)
    fig, axes = plt.subplots(1, 3, figsize=(13, 4.4))
    cases = [(box, C_OK, "Đúng: mũi tên trùng đầu xe"),
             (box.replace(yaw=box.yaw + math.pi), C_BAD, "heading.flip / heading.motion:\nlật 180°, ngược chiều chạy"),
             (box.replace(yaw=box.yaw + math.radians(25)), C_BAD, "heading.points: trục box lệch 25°\nso với trục cụm điểm")]
    for ax, (b, color, title) in zip(axes, cases):
        ax.scatter(car[:, 0], car[:, 1], s=3, c=C_POINT)
        _poly(ax, b, color=color, lw=2)
        _arrow(ax, b, color)
        if len(tr) > i + 1:
            nxt = tr[i + 1]
            m = np.linalg.inv(sc.pose(box.frame)) @ sc.pose(nxt.frame)
            p = m[:3, :3] @ np.asarray(nxt.center) + m[:3, 3]
            v = p[:2] - np.asarray(box.center[:2])
            if np.linalg.norm(v) > 0.2:
                v = v / np.linalg.norm(v) * 2.2
                ax.add_patch(FancyArrowPatch(box.center[:2], tuple(np.asarray(box.center[:2]) + v), arrowstyle="-|>",
                                             mutation_scale=12, color=C_GOAL, lw=1.5, ls="--"))
        ax.set_title(title, fontsize=10)
        ax.set_aspect("equal")
        ax.set_xlim(box.center[0] - 3.8, box.center[0] + 3.8)
        ax.set_ylim(box.center[1] - 3.8, box.center[1] + 3.8)
        ax.set_xticks([])
        ax.set_yticks([])
    fig.suptitle("Sai hướng box (spec 4.2) — mũi tên màu: hướng box; mũi tên xám đứt: hướng chuyển động của track",
                 fontsize=12)
    _save(fig, "4-huong-box.png")


def fig_fit(sc: Scene) -> None:
    box = sc.best_car()
    pts = sc.points(box.frame)
    car = _car_points(sc, box, margin=0.6)
    others = [b for b in sc.at(box.frame) if b is not box]
    empty_spot = None
    for dx in np.arange(4, 15, 0.5):
        cand = box.replace(center=(box.center[0] + dx, box.center[1] + 4.0, box.center[2]))
        if points_in_cuboid(pts, cand).sum() == 0 and not any(np.hypot(*(np.asarray(o.center[:2]) -
                                                                          cand.center[:2])) < 3 for o in others):
            empty_spot = cand
            break
    small = box.replace(dims=(box.dims[0] * 0.7, box.dims[1] * 0.7, box.dims[2]))
    big = box.replace(dims=(box.dims[0] * 1.3, box.dims[1] * 1.3, box.dims[2]))
    fig, axes = plt.subplots(1, 3, figsize=(13, 4.4))
    out = car[~points_in_cuboid(car, small)]
    axes[0].scatter(car[:, 0], car[:, 1], s=3, c=C_POINT)
    axes[0].scatter(out[:, 0], out[:, 1], s=4, c=C_BAD)
    _poly(axes[0], small, color=C_BAD, lw=2)
    axes[0].set_title(f"fit.outside: box co x0,7\n{len(out)}/{len(car)} điểm của vật nằm ngoài box", fontsize=10)
    axes[1].scatter(car[:, 0], car[:, 1], s=3, c=C_POINT)
    _poly(axes[1], big, color=C_BAD, lw=2)
    _poly(axes[1], box, color=C_OK, lw=1, ls="--")
    axes[1].set_title("fit.loose: box phóng x1,3\nmặt box cách xa điểm gần nhất của vật", fontsize=10)
    for ax in axes[:2]:
        ax.set_xlim(box.center[0] - 4, box.center[0] + 4)
        ax.set_ylim(box.center[1] - 4, box.center[1] + 4)
    if empty_spot is not None:
        near = pts[(np.abs(pts[:, 0] - empty_spot.center[0]) < 5) & (np.abs(pts[:, 1] - empty_spot.center[1]) < 5)]
        axes[2].scatter(near[:, 0], near[:, 1], s=2, c=C_POINT)
        _poly(axes[2], empty_spot, color=C_BAD, lw=2)
        axes[2].set_xlim(empty_spot.center[0] - 5, empty_spot.center[0] + 5)
        axes[2].set_ylim(empty_spot.center[1] - 5, empty_spot.center[1] + 5)
    axes[2].set_title("fit.empty: box vẽ vào chỗ trống\n0 điểm LiDAR trong box", fontsize=10)
    for ax in axes:
        ax.set_aspect("equal")
        ax.set_xticks([])
        ax.set_yticks([])
    fig.suptitle("Box lệch khỏi vật (spec 4.2: box bao trọn vật, không dư) — điểm đỏ: điểm của vật ngoài box",
                 fontsize=12)
    _save(fig, "5-box-lech-khoi-vat.png")


# ----------------------------------------------------------------------------------------------- 6. sót đối tượng


def _found_chain(sc: Scene, tid):
    """Xóa box của track rồi quét: mục lidar.missing có chuỗi cụm bám quỹ đạo thật của vật (trung vị lệch ≤ 2 m)."""
    truth = {b.frame: _to_world(sc.pose(b.frame), b.center[:2])[0] for b in sc.track(tid)}
    kept = [b for b in sc.boxes if b.track_id != tid]
    for f in detect_missing_objects(kept, sc.frames, sc.cfg.missing, None, sc.cfg.camera)[0]:
        if f.rule != "lidar.missing" or not f.details.get("moving"):
            continue
        d = [np.linalg.norm(_to_world(sc.pose(fr), c[:2])[0] - truth[fr])
             for fr, c in zip(f.details["frames"], f.details["centers"]) if fr in truth]
        if len(d) >= 3 and np.median(d) < 2.0:
            return f
    return None


def fig_missing(sc: Scene) -> None:
    hit = tid = None
    tracks = {b.track_id for b in sc.boxes if b.label in ("car", "truck", "bus")}
    for t in sorted(tracks, key=lambda t: -len(sc.track(t))):
        tr = sc.track(t)
        w = np.vstack([_to_world(sc.pose(b.frame), b.center[:2]) for b in tr])
        if len(tr) < 8 or np.linalg.norm(w[-1] - w[0]) < 10:
            continue
        hit = _found_chain(sc, t)
        if hit is not None:
            tid = t
            break
    if hit is None:
        print("Không có ví dụ lidar.missing tìm lại được xe bị xóa box: bỏ hình 6")
        return
    truth = sc.track(tid)
    ref = hit.details["frames"][len(hit.details["frames"]) // 2]
    m_ref = sc.pose(ref)
    pts = sc.points(ref)
    world = pts @ m_ref[:3, :3].T + m_ref[:3, 3]
    fig, ax = plt.subplots(figsize=(10, 6))
    tw = np.vstack([_to_world(sc.pose(b.frame), b.center[:2]) for b in truth])
    lo, hi = tw.min(axis=0) - 15, tw.max(axis=0) + 15
    sel = (world[:, 0] > lo[0]) & (world[:, 0] < hi[0]) & (world[:, 1] > lo[1]) & (world[:, 1] < hi[1]) & \
          (pts[:, 2] > -1.3)
    ax.scatter(world[sel, 0], world[sel, 1], s=0.6, c=C_POINT)
    for b in sc.at(ref):
        if b.track_id == tid:
            continue
        fp = _to_world(m_ref, footprint(b))
        ax.add_patch(Polygon(fp, closed=True, fill=False, color=C_BOX, lw=1))
    ax.plot(tw[:, 0], tw[:, 1], "--", color=C_OK, lw=2, label=f"xe bị xóa box (track {tid}, {len(truth)} keyframe)")
    cw = np.vstack([_to_world(sc.pose(f), c[:2]) for f, c in zip(hit.details["frames"], hit.details["centers"])])
    ax.plot(cw[:, 0], cw[:, 1], "o-", color=C_BAD, ms=5, lw=1.5,
            label=f"cụm LiDAR PointSnap tìm được ({len(cw)} keyframe)")
    fig.text(0.02, -0.02, f"PointSnap: [{hit.severity.value}] {hit.message}", fontsize=8.5, color=C_BAD, wrap=True)
    ax.plot([], [], color=C_BOX, label="box đã gán của vật khác")
    ax.set_aspect("equal")
    ax.set_xlim(lo[0], hi[0])
    ax.set_ylim(lo[1], hi[1])
    ax.legend(fontsize=8, loc="upper right")
    ax.set_xlabel("x toàn cục (m)")
    ax.set_ylabel("y toàn cục (m)")
    ax.set_title(f"lidar.missing (C7): xóa hết box của một xe đang chạy rồi quét — {SCENE}, point cloud frame {ref}")
    _save(fig, "6-sot-doi-tuong.png")


# ----------------------------------------------------------------------------------------------- 7. chiếu lên ảnh


def fig_camera(sc: Scene) -> None:
    box = sc.best_car(max_range=20.0)
    pose = sc.pose(box.frame)
    views = sc.frames.camera_views(box.frame)
    best = None
    for v in views:
        p = project_box(box, pose, v)
        if p is not None and p.inside_ratio > 0.95 and (best is None or p.depth < best[1].depth):
            best = (v, p)
    if best is None:
        return
    view, proj = best
    moved = box.replace(center=(box.center[0] + 1.0 * math.cos(box.yaw), box.center[1] + 1.0 * math.sin(box.yaw),
                                box.center[2]))
    proj2 = project_box(moved, pose, view)
    img = plt.imread(view.path)
    fig, ax = plt.subplots(figsize=(11, 6.4))
    ax.imshow(img)
    edges = [(0, 1), (1, 2), (2, 3), (3, 0), (4, 5), (5, 6), (6, 7), (7, 4), (0, 4), (1, 5), (2, 6), (3, 7)]
    for p, color, label in ((proj, C_OK, "box nhãn chiếu lên ảnh"), (proj2, C_BAD, "box dời dọc thân xe 1 m")):
        if p is None:
            continue
        for i, j in edges:
            ax.plot(*zip(p.polygon[i], p.polygon[j]), color=color, lw=1.6)
        ax.plot([], [], color=color, label=label)
    x1, y1, x2, y2 = proj.box
    pad = 220
    ax.set_xlim(max(0, x1 - pad), min(view.width, x2 + pad))
    ax.set_ylim(min(view.height, y2 + pad * 0.6), max(0, y1 - pad * 0.6))
    ax.axis("off")
    ax.legend(loc="lower right", fontsize=9)
    ax.set_title(f"Box Verifier lớp 2 — đối chiếu ảnh camera ({view.channel}, {SCENE} frame {box.frame}): box lệch "
                 "khỏi thân xe trên ảnh → cam.mismatch", fontsize=11)
    _save(fig, "7-chieu-box-len-anh.png")


# --------------------------------------------------------------------------------------------------- 8. kết quả


RULE_NAMES = {"floating": "Lơ lửng / lún", "heading.points": "Lệch trục cụm điểm", "size.class_range": "Kích thước / class",
              "fit.loose": "Box dư", "track.jump": "Nhảy vị trí", "track.static_shift": "Vật đứng yên: dịch",
              "heading.static": "Vật đứng yên: xoay", "lidar.missing": "Sót đối tượng", "fit.outside": "Điểm ngoài box",
              "fit.empty": "Box rỗng", "track.split_id": "Tách ID"}

# (nhãn, khóa "kiểu|mức" trong summary.json, trường: "" = mọi lỗi, "applicable" = thuộc phạm vi luật,
#  "evidence" = box có đủ điểm mặt đất)
RECALL_GROUPS = [
    ("Sai class (kích thước)", ["size_class_range|other_class"], ""),
    ("Kích thước cả track x0,6 / x1,5", ["size_class_range|x0.6", "size_class_range|x1.5"], ""),
    ("Kích thước 1 frame ≥ 15%", ["size_in_track|0.15", "size_in_track|0.3"], ""),
    ("Nhảy vị trí ≥ 2 m", ["track_jump|2.0", "track_jump|4.0"], ""),
    ("Nhảy vị trí 0,5 – 1 m", ["track_jump|0.5", "track_jump|1.0"], ""),
    ("Tách ID", ["track_split_id|-"], ""),
    ("Lật / xoay box 60 – 180°", ["heading_rotate|60", "heading_rotate|90", "heading_rotate|180"], ""),
    ("Xoay box 15 – 30°", ["heading_rotate|15", "heading_rotate|30"], ""),
    ("Vẽ trùng", ["fit_duplicate|-"], ""),
    ("Lơ lửng / lún 20 – 40 cm, đủ điểm mặt đất", ["floating|0.2", "floating|0.4"], "evidence"),
    ("Lơ lửng / lún 20 – 40 cm, mọi box", ["floating|0.2", "floating|0.4"], ""),
    ("Dời box 0,3 – 1 m", ["fit_shift|0.3", "fit_shift|0.5", "fit_shift|1.0"], ""),
    ("Co / phóng box x0,7 / x1,3", ["fit_scale|x0.7", "fit_scale|x1.3"], ""),
]


def fig_results(summary_path: str) -> None:
    s = json.loads(Path(summary_path).read_text(encoding="utf-8"))
    per = s["clean_per_100_boxes"]
    rules = {}
    for key, v in per.items():
        rule, level = key.split("|")
        if level in ("warning", "error"):
            rules.setdefault(rule, {"warning": 0.0, "error": 0.0})[level] += v
    order = sorted(rules, key=lambda r: rules[r]["warning"] + rules[r]["error"])
    fig, (a, b) = plt.subplots(1, 2, figsize=(14, 5.6), gridspec_kw={"width_ratios": [1, 1.2], "wspace": 0.75})
    y = np.arange(len(order))
    a.barh(y, [rules[r]["warning"] for r in order], color="#f0ad4e", label="Cảnh báo")
    a.barh(y, [rules[r]["error"] for r in order], left=[rules[r]["warning"] for r in order], color=C_BAD, label="Lỗi")
    a.set_yticks(y, [RULE_NAMES.get(r, r) for r in order])
    a.set_xlabel("số mục / 100 box trên nhãn sạch")
    tw = sum(v["warning"] for v in rules.values())
    te = sum(v["error"] for v in rules.values())
    a.set_title(f"Báo nhầm trên nhãn sạch — tổng {tw:.2f} Cảnh báo / {te:.2f} Lỗi\n(mục tiêu ≤ 2 / ≤ 0,5)")
    a.legend(fontsize=8)

    recall = s["recall"]
    groups = []
    for label, keys, field in RECALL_GROUPS:
        hit = sum(recall[k][f"detected_{field}"] if field else recall[k]["detected"] for k in keys if k in recall)
        n = sum(recall[k][f"n_{field}"] if field else recall[k]["n"] for k in keys if k in recall)
        if n:
            groups.append((label, hit, n))
    groups.reverse()
    vals = [h / n * 100 for _, h, n in groups]
    yy = np.arange(len(groups))
    b.barh(yy, vals, color=[C_OK if v >= 70 else ("#f0ad4e" if v >= 40 else C_BAD) for v in vals])
    for i, ((_, h, n), v) in enumerate(zip(groups, vals)):
        b.text(v + 1, i, f"{v:.0f}% ({h}/{n})", va="center", fontsize=8)
    b.set_yticks(yy, [g[0] for g in groups], fontsize=9)
    b.set_xlim(0, 120)
    b.set_xlabel("% lỗi chèn giả được báo đúng loại, đúng box (Cảnh báo trở lên)")
    b.set_title("Tỉ lệ bắt lỗi chèn giả")
    fig.suptitle(f"Kết quả trên 5 cảnh kiểm tra nuScenes ({s['boxes']} box, 10 vòng chèn lỗi)", fontsize=12, y=1.04)
    _save(fig, "8-ket-qua-eval.png")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--dataroot", default=os.environ.get("NUSCENES_ROOT"))
    ap.add_argument("--eval-test", help="summary.json của pointsnap eval --scenes test")
    args = ap.parse_args()
    if args.eval_test:
        fig_results(args.eval_test)
    if not args.dataroot:
        print("Thiếu --dataroot / NUSCENES_ROOT: chỉ vẽ hình không cần dữ liệu.")
        fig_slope()
        return
    sc = Scene(args.dataroot)
    fig_ground(sc)
    fig_slope()
    fig_track_jump(sc)
    fig_heading(sc)
    fig_fit(sc)
    fig_missing(sc)
    fig_camera(sc)


if __name__ == "__main__":
    main()
