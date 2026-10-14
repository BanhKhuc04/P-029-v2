# Bàn giao 06 — đưa review 12 lên main hiện tại

Model review: **gpt-6.1-sol**. Base `7ec580a`; nhận `b0cbba8` và `699433b` bằng cherry-pick sạch thành `9c685b6`, `8412bef`. Giữ nguyên tác giả code và báo cáo gốc.

Cache camera có khóa hash ảnh/model/revision/runtime, ghi atomic, kiểm dữ liệu và tự tính lại cache hỏng; runtime thất bại được báo thiếu bằng chứng, hybrid fallback không khai độ phủ DINO khi chỉ chạy COCO. Giữ sửa mới của main ngoài phạm vi camera, gồm missing elevation và caller static hiện tại; static caller được sửa riêng trong PR #63.

Kiểm lại trên Windows/Python 3.11.9: **124 PASS**, 0 FAIL/SKIP/XFAIL cho camera review12/camera/gate coverage/security. Có weights thật trên máy này, khác môi trường báo cáo12 cũ: PyTorch 2.6.0+cu124, torchvision 0.21.0+cu124, transformers 5.19.0, CUDA; chạy mới 3 ảnh CAM_FRONT mỗi mode, offline và cache riêng.

| Mode | Số detection trên 3 ảnh | Cache roundtrip |
|---|---|---|
| Mask R-CNN | 41 / 43 / 38 | PASS |
| Grounding DINO + SAM2 | 35 / 35 / 38 | PASS |
| Hybrid | 41 / 43 / 38 | PASS |

Hashes checkpoint/ảnh và thời gian ở [evidence/handoff-06](evidence/handoff-06). Smoke xác minh pretrained chạy được và cache hợp lệ, không chứng nhận precision camera; không tạo verdict tay. DINO dùng processor/revision đã pin nên không lấy số detection của cache phiên bản trước làm oracle.

Lệnh từ tool root với `PYTHONPATH` là tool root, `HF_HUB_OFFLINE=1`: `python -m pytest -q tests/test_camera_review12.py tests/test_camera.py tests/test_gate_coverage.py tests/test_security_review.py`; `python auto-tests/smoke_model.py --dataset D:/Vin_uni/data/nuscenes --model <mode> --images 3 --out <thu-muc-moi>`.
