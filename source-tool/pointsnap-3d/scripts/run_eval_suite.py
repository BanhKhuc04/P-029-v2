"""Chạy toàn bộ quy trình đánh giá trên 10 cảnh nuScenes v1.0-mini (việc B7).

- 5 cảnh tinh chỉnh (scene 0..4): chốt ngưỡng tham số.
- 5 cảnh kiểm tra (scene 5..9): chèn lỗi giả theo mục 8.1 và đo chỉ số mục 8.2.
- Xuất báo cáo ra docs/ket-qua/danh-gia.md và in kết quả tổng kết.
"""

import os
import sys
from pathlib import Path

import numpy as np

# Thêm pointsnap-3d vào sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from pointsnap.adapters.nuscenes import NuScenesReader
from pointsnap.core.config import load_config
from pointsnap.detectors.floating import detect_floating
from pointsnap.detectors.size import detect_size
from pointsnap.detectors.track import detect_track_errors
from pointsnap.eval.metrics import EvaluationReport, InjectedFault, evaluate_findings


def _ensure_utf8_output() -> None:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure") and (stream.encoding or "").lower() not in ("utf-8", "utf8"):
            stream.reconfigure(encoding="utf-8")


def main():
    _ensure_utf8_output()
    config = load_config()
    data_dir = os.environ.get("NUSCENES_ROOT", str(ROOT_DIR / "data" / "nuscenes"))

    if not (Path(data_dir) / "v1.0-mini").is_dir():
        print(f"Lỗi: Không tìm thấy dữ liệu nuScenes tại {data_dir}", file=sys.stderr)
        sys.exit(1)

    print("=" * 70)
    print("CHẠY ĐÁNH GIÁ CHỈ SỐ TOÀN BỘ (VIỆC B7 — CỔNG G3)")
    print(f"Thư mục dữ liệu: {data_dir}")
    print("=" * 70)

    reader = NuScenesReader(data_dir)
    all_scenes = reader.scenes()
    tuning_scenes = all_scenes[:5]
    test_scenes = all_scenes[5:]

    print(f"5 cảnh tinh chỉnh: {[s.name for s in tuning_scenes]}")
    print(f"5 cảnh kiểm tra:  {[s.name for s in test_scenes]}")

    # Chạy trên 5 cảnh kiểm tra và chèn lỗi giả
    rng = np.random.default_rng(2026)
    injected_faults: list[InjectedFault] = []
    all_findings = []
    clean_findings = []
    total_clean_boxes = 0

    for s_info in test_scenes:
        print(f"\nĐang quét và kiểm tra {s_info.name} ({s_info.num_frames} frames)...")
        samples = reader.samples(s_info.name)
        anns = reader.annotations(s_info.name)

        anns_by_frame = {}
        for a in anns:
            anns_by_frame.setdefault(a.frame, []).append(a)

        s2w_map = {s.frame: s.sensor_to_world for s in samples if s.sensor_to_world is not None}
        time_map = {s.frame: s.timestamp for s in samples if s.timestamp is not None}

        # 1. Quét nhãn sạch trước để đo tỉ lệ báo động giả
        for s in samples:
            fd = reader.frame_data(s)
            f_boxes = anns_by_frame.get(s.frame, [])
            total_clean_boxes += len(f_boxes)

            clean_findings.extend(detect_floating(f_boxes, fd.points, config.floating))
            clean_findings.extend(detect_size(f_boxes, config.size))

        clean_findings.extend(detect_track_errors(anns, config.track, sensor_to_world_by_frame=s2w_map, timestamps_by_frame=time_map))

        # 2. Tạo bản sao nhãn để chèn lỗi giả
        modified_boxes = []
        for a in anns:
            mod_b = a
            # Chèn ngẫu nhiên lỗi lơ lửng / lún đất trên ~10% box xe
            if a.label in ("car", "truck") and rng.random() < 0.10:
                is_err = rng.random() < 0.6
                delta = float(rng.uniform(0.22, 0.35)) if is_err else float(rng.uniform(0.12, 0.18))
                sign = 1.0 if rng.random() < 0.7 else -1.0
                mod_delta = sign * delta
                mod_b = a.replace(center=(a.center[0], a.center[1], a.center[2] + mod_delta))
                injected_faults.append(
                    InjectedFault(
                        error_type="floating",
                        frame=a.frame,
                        track_id=a.track_id,
                        severity="error" if is_err else "warning",
                        delta=delta,
                    )
                )
            # Chèn ngẫu nhiên lỗi sai kích thước trên ~8% box xe
            elif a.label == "car" and rng.random() < 0.08:
                is_err = rng.random() < 0.6
                scale = float(rng.uniform(1.35, 1.50)) if is_err else float(rng.uniform(1.18, 1.25))
                new_len = a.length * scale
                delta = new_len - a.length
                mod_b = a.replace(dims=(new_len, a.width, a.height))
                injected_faults.append(
                    InjectedFault(
                        error_type="size",
                        frame=a.frame,
                        track_id=a.track_id,
                        severity="error" if is_err else "warning",
                        delta=delta,
                    )
                )

            modified_boxes.append(mod_b)

        # 3. Quét phát hiện trên tập nhãn đã chèn lỗi
        mod_by_frame = {}
        for b in modified_boxes:
            mod_by_frame.setdefault(b.frame, []).append(b)

        for s in samples:
            fd = reader.frame_data(s)
            f_boxes = mod_by_frame.get(s.frame, [])
            all_findings.extend(detect_floating(f_boxes, fd.points, config.floating))
            all_findings.extend(detect_size(f_boxes, config.size))

        all_findings.extend(detect_track_errors(modified_boxes, config.track, sensor_to_world_by_frame=s2w_map, timestamps_by_frame=time_map))

    report = evaluate_findings(
        injected_faults=injected_faults,
        findings=all_findings,
        clean_boxes_total=total_clean_boxes,
        clean_findings=clean_findings,
    )

    md_output = report.to_markdown()
    print("\n" + "=" * 70)
    print(md_output)
    print("=" * 70)

    # Lưu ra docs/ket-qua/danh-gia.md
    out_file = ROOT_DIR / "docs" / "ket-qua" / "danh-gia.md"
    out_file.parent.mkdir(parents=True, exist_ok=True)
    out_file.write_text(md_output, encoding="utf-8")
    print(f"\n=> Đã ghi bảng chỉ số vào: {out_file}")


if __name__ == "__main__":
    main()
