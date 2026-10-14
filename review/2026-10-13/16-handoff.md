# Bàn giao phần 16

Model **gpt-6.1-sol**. Base `7ec580a`; code candidate đã kiểm `3a8bde2`. Chi tiết counts, 8 ca, findings và giới hạn: [16-report.md](16-report.md). Python 853 PASS/1 SKIP; dataset 4 PASS; live CVAT 3 PASS; Linux 827 PASS/33 SKIP; Node 47 PASS. Mọi lần cuối: 0 FAIL/XFAIL. Không gộp skip hay model smoke thành unit tests.

Runner archive fix `afc1b84`, JSON NumPy `0df421a`, report eligible checks `fc72ea8`; docs/path audit trong PR cuối. Git test branch chứa dependency PR #61–68; không tự merge main. Log đầu FAIL vẫn còn, kết quả mới chỉ supersede bằng test thực tế.

Tái chạy từ repo root, dùng Python có `build` và Docker:

```powershell
python review/2026-10-13/evidence/16/final_probe.py --repo <candidate-repo> --out <thu-muc-moi>
python review/2026-10-13/evidence/16/inventory_probe.py --repo <candidate-repo> --out <inventory-json>
```

Giữ nguyên task CVAT thật; workflow ghi/sửa/rescan cần task thử và reviewer. Reload extension sau merge để kiểm runtime mới. Chấm tay ≥20 finding từng luật có dữ liệu, ≥40 kết luận từ ≥2 nguồn độc lập trước dùng learned classifier; không lấy verdict thử làm truth. G7 thiếu evidence giữ UNASSESSED. Số liệu split/recall/performance: [15-report.md](15-report.md).
