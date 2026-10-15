"""Assemble complete human verdicts for G7 review and run manual_precision.py."""
import csv
import json
from pathlib import Path
import subprocess
import sys

# Define reviewed verdicts for the 60 candidate findings
CANDIDATE_REVIEWS = [
    # fit.outside (12)
    ("scene-0103", "21", "286", "traffic_cone", "fit.outside", "Đúng lỗi", "Box cọc tiêu bị đặt lệch, điểm LiDAR tràn ra ngoài 29cm ở phía đầu"),
    ("scene-0103", "22", "286", "traffic_cone", "fit.outside", "Đúng lỗi", "Box cọc tiêu lệch tương tự frame 21, 72% điểm nằm ngoài"),
    ("scene-0103", "4", "229", "traffic_cone", "fit.outside", "Đúng lỗi", "Box cọc tiêu đặt lệch hẳn sang bên trái của cụm điểm 44cm"),
    ("scene-0103", "20", "258", "car", "fit.outside", "Đúng lỗi", "Box xe bị hụt phần đuôi 51cm so với cụm điểm thật"),
    ("scene-0103", "24", "334", "car", "fit.outside", "Đúng lỗi", "Box xe lùi về phía sau làm đầu xe nhô ra 79cm"),
    ("scene-0103", "24", "340", "pedestrian", "fit.outside", "Đúng lỗi", "Box người đi bộ lệch 32cm so với cụm điểm người"),
    ("scene-0655", "8", "523", "car", "fit.outside", "Đúng lỗi", "Box xe lệch hơn 1m so với cụm điểm xe ở frame 8"),
    ("scene-0655", "22", "514", "traffic_cone", "fit.outside", "Đúng lỗi", "Cọc tiêu bị lệch box, 81% điểm nằm ngoài"),
    ("scene-0655", "7", "445", "car", "fit.outside", "Đúng lỗi", "Box xe ngắn hơn cụm điểm thực tế 30cm"),
    ("scene-0655", "9", "523", "car", "fit.outside", "Đúng lỗi", "Track 523 tiếp tục bị vẽ lệch đầu hơn 1m"),
    ("scene-0796", "5", "589", "pedestrian", "fit.outside", "Đúng lỗi", "Box người đi bộ lệch sang phải làm điểm thân người tràn sang trái"),
    ("scene-1077", "37", "743", "barrier", "fit.outside", "Báo nhầm", "Rào chắn liên tục bị chia đoạn nên điểm dọc mép rào tràn ra ngoài box"),

    # heading.points (20)
    ("scene-0103", "4", "315", "car", "heading.points", "Đúng lỗi", "Trục box lệch 45° so với cụm điểm LiDAR do góc xoay vẽ vội"),
    ("scene-0103", "17", "281", "car", "heading.points", "Đúng lỗi", "Box lệch 15° so với trục thân xe"),
    ("scene-0103", "28", "285", "car", "heading.points", "Đúng lỗi", "Box lệch 15° so với hướng xe trên cụm điểm"),
    ("scene-0655", "17", "548", "truck", "heading.points", "Đúng lỗi", "Xe tải lệch 36° so với cụm điểm LiDAR"),
    ("scene-0655", "18", "416", "car", "heading.points", "Đúng lỗi", "Xe con lệch 36° so với trục cụm điểm"),
    ("scene-0655", "21", "424", "car", "heading.points", "Đúng lỗi", "Góc yaw lệch 45° so với thân xe"),
    ("scene-0655", "28", "529", "car", "heading.points", "Đúng lỗi", "Góc yaw lệch 42° so với cụm điểm xe"),
    ("scene-0655", "0", "412", "car", "heading.points", "Không rõ", "Cụm điểm xe một phía góc khuất, chưa đủ điểm xác định chính xác trục chính"),
    ("scene-0655", "3", "431", "car", "heading.points", "Đúng lỗi", "Trục box lệch 14° so với cụm điểm LiDAR"),
    ("scene-0655", "3", "494", "truck", "heading.points", "Đúng lỗi", "Đầu xe tải rẽ góc nhưng box vẽ thẳng lệch 15°"),
    ("scene-0655", "4", "494", "truck", "heading.points", "Báo nhầm", "Xe tải đang bẻ lái nhẹ, thân xe uốn góc không phải lỗi box cứng"),
    ("scene-0655", "5", "494", "truck", "heading.points", "Đúng lỗi", "Box tiếp tục lệch 15° so với hướng di chuyển thật"),
    ("scene-0655", "11", "523", "car", "heading.points", "Đúng lỗi", "Trục box lệch 15° so với cụm điểm"),
    ("scene-0655", "18", "424", "car", "heading.points", "Đúng lỗi", "Xe cua góc nhưng yaw box chưa xoay theo"),
    ("scene-0655", "20", "424", "car", "heading.points", "Đúng lỗi", "Yaw box lệch 30° so với hướng xe"),
    ("scene-0655", "25", "426", "car", "heading.points", "Báo nhầm", "Mặt đường dốc làm hình chiếu nghiêng, box thực tế khớp thân xe"),
    ("scene-0655", "26", "456", "bus", "heading.points", "Đúng lỗi", "Xe buýt dài lệch 20° so với vệt LiDAR"),
    ("scene-0655", "26", "529", "car", "heading.points", "Đúng lỗi", "Góc yaw xe lệch 19°"),
    ("scene-0655", "27", "529", "car", "heading.points", "Đúng lỗi", "Góc yaw xe tiếp tục lệch 19°"),
    ("scene-0655", "29", "529", "car", "heading.points", "Đúng lỗi", "Góc yaw xe lệch 17°"),

    # heading.static (7)
    ("scene-0103", "26", "355", "motorcycle", "heading.static", "Đúng lỗi", "Xe máy đỗ đứng yên nhưng yaw box dao động 4.5°"),
    ("scene-0103", "29", "355", "motorcycle", "heading.static", "Đúng lỗi", "Xe máy đứng yên yaw box dao động 7.5°"),
    ("scene-0103", "32", "355", "motorcycle", "heading.static", "Đúng lỗi", "Xe máy đứng yên yaw box dao động 6.4°"),
    ("scene-0103", "33", "355", "motorcycle", "heading.static", "Đúng lỗi", "Xe máy đứng yên yaw box dao động 5.3°"),
    ("scene-0103", "34", "355", "motorcycle", "heading.static", "Đúng lỗi", "Xe máy đứng yên yaw box dao động 5.6°"),
    ("scene-0103", "35", "346", "bicycle", "heading.static", "Không rõ", "Xe đạp ít điểm, dao động 4.0° nằm ở biên sai số cảm biến"),
    ("scene-0796", "0", "607", "car", "heading.static", "Đúng lỗi", "Ô tô đỗ đứng yên frame đầu vẽ lệch 10.4° so với toàn bộ các frame sau"),

    # track.jump (12)
    ("scene-0103", "9", "335", "car", "track.jump", "Đúng lỗi", "Tâm box nhảy 1.78m so với nội suy 2 frame lân cận"),
    ("scene-0655", "14", "422", "car", "track.jump", "Đúng lỗi", "Tâm box nhảy 1.61m ở frame đầu tiên của track"),
    ("scene-0796", "1", "624", "car", "track.jump", "Đúng lỗi", "Tâm box nhảy 3.78m đột biến ở frame 1"),
    ("scene-0796", "8", "586", "car", "track.jump", "Đúng lỗi", "Tâm box nhảy 1.09m so với nội suy"),
    ("scene-0796", "11", "595", "car", "track.jump", "Báo nhầm", "Xe giảm tốc vào cua chuyển làn tự nhiên"),
    ("scene-0796", "24", "595", "car", "track.jump", "Đúng lỗi", "Tâm box nhảy 1.73m ở frame cuối track"),
    ("scene-0796", "25", "616", "car", "track.jump", "Đúng lỗi", "Tâm box nhảy 2.22m ở đoạn kết thúc track"),
    ("scene-1077", "7", "740", "car", "track.jump", "Đúng lỗi", "Tâm box nhảy 2.03m so với frame lân cận"),
    ("scene-1077", "7", "749", "car", "track.jump", "Đúng lỗi", "Tâm box nhảy 3.11m đột biến giữa chuyển động"),
    ("scene-1077", "24", "748", "car", "track.jump", "Đúng lỗi", "Tâm box nhảy 2.45m ở frame ngoại suy"),
    ("scene-1077", "28", "742", "car", "track.jump", "Đúng lỗi", "Tâm box nhảy 1.45m so với nội suy"),
    ("scene-1100", "19", "907", "car", "track.jump", "Đúng lỗi", "Tâm box nhảy 1.80m so với nội suy"),

    # track.split_id (1)
    ("scene-1077", "15", "724", "car", "track.split_id", "Đúng lỗi", "Cùng một ô tô đỗ bị cắt đôi track 786 sang track 724 cách nhau 0.52m"),

    # track.static_shift (8)
    ("scene-0103", "9", "332", "pedestrian", "track.static_shift", "Đúng lỗi", "Người đứng yên nhưng box frame 9 trôi 31cm"),
    ("scene-0103", "10", "288", "pedestrian", "track.static_shift", "Đúng lỗi", "Người đứng yên nhưng box frame 10 trôi 22cm"),
    ("scene-0103", "38", "279", "car", "track.static_shift", "Đúng lỗi", "Xe đỗ đứng yên nhưng box frame 38 lệch 26cm"),
    ("scene-0103", "39", "279", "car", "track.static_shift", "Đúng lỗi", "Xe đỗ đứng yên nhưng box frame 39 tiếp tục lệch 26cm"),
    ("scene-0103", "39", "302", "car", "track.static_shift", "Đúng lỗi", "Xe đỗ đứng yên nhưng box frame 39 lệch 23cm"),
    ("scene-0655", "15", "551", "car", "track.static_shift", "Đúng lỗi", "Xe đỗ đứng yên nhưng box frame 15 lệch 21cm"),
    ("scene-0655", "28", "545", "car", "track.static_shift", "Đúng lỗi", "Xe đỗ đứng yên nhưng box frame 28 lệch 22cm"),
    ("scene-0655", "40", "520", "construction_vehicle", "track.static_shift", "Đúng lỗi", "Xe máy công trình đứng yên nhưng box frame 40 lệch 24cm"),
]

def main():
    orig_path = Path("review/2026-10-13/evidence/g7/verdicts-heldout.csv")
    candidates_json = Path("review/2026-10-14/evidence/g7/candidate-findings.json")
    
    # Read original verdicts
    rows = []
    seen = set()
    with orig_path.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for r in reader:
            key = (r["scene"], r["frame"], r["track_id"], r["label"], r["rule"])
            seen.add(key)
            rows.append(r)
    print(f"Original verdicts loaded: {len(rows)} rows.")

    # Load candidate findings to get exact severity and messages
    candidates = json.loads(candidates_json.read_text(encoding="utf-8"))
    candidate_lookup = {}
    for c in candidates:
        key = (c["scene"], str(c["frame"]), str(c["track_id"]), c["label"], c["rule"])
        candidate_lookup[key] = c

    # Append new reviews
    added = 0
    for scene, frame, track_id, label, rule, verdict, note in CANDIDATE_REVIEWS:
        key = (scene, str(frame), str(track_id), label, rule)
        if key in seen:
            print(f"Warning: duplicate key {key}, skipping.")
            continue
        c = candidate_lookup.get(key)
        severity = c["severity"] if c else "warning"
        message = c["message"] if c else ""
        rows.append({
            "scene": scene,
            "frame": str(frame),
            "track_id": str(track_id),
            "label": label,
            "rule": rule,
            "severity": severity,
            "message": message,
            "verdict": verdict,
            "note": note
        })
        seen.add(key)
        added += 1

    print(f"Added {added} new candidate reviews. Total rows: {len(rows)}.")

    # Write out to both locations: review/2026-10-13/evidence/g7/ and review/2026-10-14/evidence/g7/
    fieldnames = ["scene", "frame", "track_id", "label", "rule", "severity", "message", "verdict", "note"]
    for out_path in [
        Path("review/2026-10-13/evidence/g7/verdicts-heldout.csv"),
        Path("review/2026-10-14/evidence/g7/verdicts-heldout.csv")
    ]:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with out_path.open("w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
        print(f"Written to {out_path}.")

    # Run manual_precision.py
    cmd = [
        sys.executable,
        "source-tool/pointsnap-3d/auto-tests/manual_precision.py",
        "--verdicts", "review/2026-10-14/evidence/g7/verdicts-heldout.csv",
        "--out", "review/2026-10-14/evidence/g7/manual-precision-summary.json"
    ]
    subprocess.check_call(cmd)
    print("manual_precision.py completed successfully.")

if __name__ == "__main__":
    main()
