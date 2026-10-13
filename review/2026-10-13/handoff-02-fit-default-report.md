# Bàn giao 02 — tắt mặc định fit.loose

Model review: **gpt-6.1-sol**. Mốc đầu: `7ec580a`. Người dùng chốt “Tắt mặc định, chờ chấm tay” ngày 13/10/2026.

Đổi cả mặc định dataclass `RulesConfig` và YAML đóng gói về `fit_loose: false`. Guideline riêng vẫn có thể bật. Không đổi thuật toán fit, ngưỡng hoặc `fit.outside`; PR #48 tiếp tục cần đánh giá riêng. Các dự án đã lưu `fit_loose: true` có cấu hình riêng, cần đổi trong Guideline nếu muốn tắt ở dự án đó.

Validation: 59 PASS, 0 FAIL, 0 SKIP, 0 XFAIL cho config/rules/numeric validation/gate coverage/web. Test catalog được cập nhật theo mặc định mới và kiểm thêm bật riêng. Lệnh: `python -m pytest -q tests/test_config.py tests/test_rules.py tests/test_numeric_config_recheck.py tests/test_gate_coverage.py tests/test_web.py`.

Quyết định này giảm số luật bật mặc định; không phải bằng chứng precision của fit.loose và không chứng nhận luật đạt chất lượng.
