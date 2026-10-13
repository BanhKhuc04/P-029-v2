# Bàn giao 03 — nối lại track.static_shift

Model review: **gpt-6.1-sol**. Mốc đầu: `7ec580a`.

Nguyên nhân có thể tái hiện: `check_static` ép `shift=False`; `scan_cuboids` chỉ gọi static khi `heading_static` bật. Switch `track_static_shift` có trong config/catalog nhưng chỉ kéo detector track chung vào chạy, detector đó không sinh luật static này. Commit `4c380f2` đã tắt caller, `00e751c` khôi phục track chung mà chưa khôi phục static.

Sửa caller để đọc hai switch độc lập; gọi static nếu shift hoặc heading bật. Không đổi phép đo/pose/ngưỡng, không bật track chung chỉ để chạy static. Thêm regression qua scanner với ego di chuyển, track ID 0 và một box sai; kiểm cả bốn tổ hợp switch và thiếu pose.

Validation: 87 PASS, 0 FAIL, 0 SKIP, 0 XFAIL trong `test_static_scanner_handoff.py`, `test_verifier_review11.py`, `test_spec_rules.py`, `test_scan_gate.py`, `test_gate_coverage.py`.

[Replay 10 cảnh](evidence/handoff-03/static.json) qua scanner, chỉ bật `track_static_shift`: tuning **8**, reviewed-heldout **8** finding, main cùng đầu vào không phát hiện mục nào. Số tuning khác mốc 6 của bàn giao; báo số thực chạy. Không có verdict tay cho những mục này, nên đây là kiểm chứng luồng bật luật, chưa phải precision.

Lệnh: từ tool root đặt `PYTHONPATH` tới tool root, chạy `python -m pytest -q tests/test_static_scanner_handoff.py tests/test_verifier_review11.py tests/test_spec_rules.py tests/test_scan_gate.py tests/test_gate_coverage.py`. Replay: từ repo root chạy `python review/2026-10-13/evidence/handoff-03/static_probe.py --dataroot D:/Vin_uni/data/nuscenes --out <file-moi.json>`.
