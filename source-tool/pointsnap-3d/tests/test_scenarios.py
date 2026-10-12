"""Tình huống giao thông thực tế (việc C5, `quan-ly/giao-viec/C5-tinh-huong-thuc-te.md`) trên bộ mô phỏng `scenario_sim`.

Mỗi tình huống ghi rõ các luật được phép báo (Cảnh báo / Lỗi) và mức; "sạch" nghĩa là không có mục Cảnh báo / Lỗi nào.
"""

from __future__ import annotations

import math

import pytest

from scenario_sim import Obj, Part, Scene, parked, scan, straight

CAR = (4.5, 1.9, 1.6)
MOTO = (1.9, 0.8, 1.5)
PED = (0.6, 0.6, 1.75)


def _dist(t, v=8.0, a=3.0, t_brake=1.0, t_go=4.5):
    """Chạy v m/s, phanh a m/s² tới khi dừng, đứng tới t_go rồi tăng tốc a."""
    t_stop = t_brake + v / a
    if t <= t_brake:
        return v * t
    d_brake = v * t_brake + v * v / (2 * a)
    if t <= t_stop:
        u = t - t_brake
        return v * t_brake + v * u - a * u * u / 2
    if t <= t_go:
        return d_brake
    u = t - t_go
    return d_brake + min(a * u * u / 2, v * u)


def _uturn(t):
    if t <= 6.0:
        a = t / 6.0 * math.pi
        return (15 + 6 * math.sin(a), 6 - 6 * math.cos(a), a)
    return (15 - math.pi * (t - 6.0), 12.0, math.pi)


def _swap(f, b):
    return b.replace(track_id=3 - b.track_id) if f >= 6 else b


CARGO = [Part((-0.6, 0.0, 0.95), (0.8, 1.6, 0.6))]

SCENARIOS = {
    "S0 xe chạy, xe đỗ, người đi bộ": (lambda: Scene([
        Obj(1, "car", CAR, straight(-10, 4, 0, 10)), Obj(2, "car", CAR, parked(12, -5, 0.3)),
        Obj(3, "pedestrian", PED, straight(6, 8, 1.2, 1.3))]), {}),
    "S1a xe máy chở hàng, box không gồm hàng": (lambda: Scene([
        Obj(1, "motorcycle", MOTO, straight(0, 5, 0, 6), parts=CARGO)]), {}),
    "S1b xe máy chở hàng, box gồm hàng: chỉ Cảnh báo": (lambda: Scene([
        Obj(1, "motorcycle", (2.2, 1.6, 1.6), straight(0, 5, 0, 6))]), {"size.class_range": "warning"}),
    "E1 box xe máy phóng rộng, không chở hàng: Lỗi": (lambda: Scene([
        Obj(1, "motorcycle", MOTO, straight(0, 5, 0, 6), labelled=lambda f, b: b.replace(dims=(2.2, 1.6, 1.6)))]),
        {"size.class_range": "error"}),
    "S2 8 xe máy đỗ san sát": (lambda: Scene([
        Obj(10 + i, "motorcycle", (1.9, 0.7, 1.1), parked(6 + 0.75 * i, 4, math.pi / 2)) for i in range(8)]), {}),
    "S3 xe dừng đèn đỏ rồi chạy": (lambda: Scene([Obj(1, "car", CAR, lambda t: (5 + _dist(t), 4.0, 0.0))],
                                                num_frames=16), {}),
    "S4a xe lùi chậm: một Cảnh báo cho cả đoạn": (lambda: Scene([
        Obj(1, "car", CAR, lambda t: (20 - 2.5 * t, 4.0, 0.0))]), {"heading.motion": "warning"}),
    "E4 xe chạy nhanh, box ngược cả track: Lỗi": (lambda: Scene([
        Obj(1, "car", CAR, straight(-10, 4, 0, 10), labelled=lambda f, b: b.replace(yaw=b.yaw + math.pi))]),
        {"heading.motion": "error"}),
    "S4b xe quay đầu chữ U": (lambda: Scene([Obj(1, "car", CAR, _uturn)], num_frames=14), {}),
    "S5a đầu kéo + rơ-moóc": (lambda: Scene([
        Obj(1, "truck", (6.0, 2.5, 3.2), straight(0, 5, 0, 8)),
        Obj(2, "trailer", (10.0, 2.5, 3.6), lambda t: (8 * t - 7.9, 5, 0))]), {}),
    "S5b xe buýt 18 m": (lambda: Scene([Obj(1, "bus", (18.0, 2.6, 3.2), straight(-5, 6, 0, 6))]), {}),
    "S6 người dắt xe đạp": (lambda: Scene([
        Obj(1, "pedestrian", (0.6, 0.6, 1.7), straight(4, 6, 0, 1.2)),
        Obj(2, "bicycle", (1.7, 0.5, 1.0), lambda t: (4 + 1.2 * t, 5.55, 0))]), {}),
    "S7 người cầm ô": (lambda: Scene([
        Obj(1, "pedestrian", (0.6, 0.6, 1.7), straight(4, 6, 0, 1.2), parts=[Part((0, 0, 2.0), (1.0, 1.0, 0.05))])]),
        {}),
    "S8 cọc tiêu, hướng box tuỳ ý": (lambda: Scene([
        Obj(1, "traffic_cone", (0.4, 0.4, 0.7), parked(9, 3, 0),
            labelled=lambda f, b: b.replace(yaw=b.yaw + math.radians((f * 37) % 90 - 45)))]), {}),
    "E8 rào chắn đứng yên bị xoay 30°: Lỗi": (lambda: Scene([
        Obj(1, "barrier", (0.5, 2.5, 1.0), parked(9, 3, 0.2),
            labelled=lambda f, b: b.replace(yaw=b.yaw + math.radians(30)) if f == 5 else b)]),
        {"heading.static": "error"}),
    "S9 hai xe máy song song bị đổi ID: Lỗi": (lambda: Scene([
        Obj(1, "motorcycle", MOTO, straight(0, 4.0, 0, 7), labelled=_swap),
        Obj(2, "motorcycle", MOTO, straight(0, 5.2, 0, 7), labelled=_swap)]), {"track.id_swap": "error"}),
    "N9a xe máy vượt nhau": (lambda: Scene([
        Obj(1, "motorcycle", MOTO, straight(0, 4.0, 0, 9)), Obj(2, "motorcycle", MOTO, straight(4, 5.2, 0, 6))]), {}),
    "N9b hai người đi cắt chéo": (lambda: Scene([
        Obj(1, "pedestrian", PED, straight(4, 4, 0.5, 1.3)), Obj(2, "pedestrian", PED, straight(4, 7, -0.5, 1.3))]),
        {}),
    "S10 mưa / bụi": (lambda: Scene([
        Obj(1, "car", CAR, straight(-10, 4, 0, 10)), Obj(2, "car", CAR, parked(12, -5, 0.3))], rain=3000), {}),
    "S12a che 8 frame, không đánh occluded": (lambda: Scene([
        Obj(1, "car", CAR, parked(14, 4, 0), hidden=set(range(2, 10)))]), {"fit.empty": "warning"}),
    "S12b che 8 frame, đánh occluded": (lambda: Scene([
        Obj(1, "car", CAR, parked(14, 4, 0), hidden=set(range(2, 10)),
            labelled=lambda f, b: b.replace(attrs={**b.attrs, "occluded": True}) if 2 <= f < 10 else b)]),
        {"track.occluded_long": "warning"}),
    "S13 xe xa 42 m": (lambda: Scene([Obj(1, "car", CAR, straight(42, 3, math.pi / 2, 5))]), {}),
}


@pytest.mark.parametrize("name", list(SCENARIOS))
def test_scenario(name):
    build, expected = SCENARIOS[name]
    found = scan(build())
    got: dict[str, set[str]] = {}
    for f in found:
        got.setdefault(f.rule, set()).add(f.severity.value)
    assert set(got) == set(expected), f"{name}: {[(f.rule, f.severity.value, f.message) for f in found]}"
    for rule, severity in expected.items():
        assert got[rule] == {severity}, f"{name}: {rule} {got[rule]}"


def test_reversing_is_one_finding():
    found = scan(SCENARIOS["S4a xe lùi chậm: một Cảnh báo cho cả đoạn"][0]())
    assert len(found) == 1 and found[0].details["maybe_reversing"]
