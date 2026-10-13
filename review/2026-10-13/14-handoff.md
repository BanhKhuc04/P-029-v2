# Bàn giao phần 14

Model: **gpt-6.1-sol**. Candidate code: `3a8bde2`; base main: `7ec580a`. Sửa riêng API JSON `0df421a`, phạm vi checks `fc72ea8`; dependency PR #61–68 được hợp nhất local để test, người dùng tự merge.

Kết quả và bảng 8 ca: [14-report.md](14-report.md). Tự động API/gate/security focused: **66 PASS, 0 FAIL/SKIP/XFAIL**. Full suite và platform: [16-report.md](16-report.md). CLI/Web/API job 4 cùng 127 finding trong phạm vi hình học; nhãn giữ checksum. Health JSON 200, không PAT 401, ba format report 200.

Chạy lại từ tool root với Python/dev và runtime phù hợp:

```powershell
python -m pytest -q tests/test_report_api.py tests/test_gate_coverage.py tests/test_deployment_review.py tests/test_security_review.py
node --test extension/tests/*.test.js
```

Probe thật cần private token trong project home; không đưa token lên command/log. Script [deployment_probe.py](evidence/14/deployment_probe.py) nhận `--tool-root`, `--out`, `--home`; chọn home mới để tách verdict thử khỏi precision tay.

Chuyển sang 15/16: kiểm số liệu trên candidate, không gán trạng thái runtime mới cho extension chưa reload. TC-14-006/007 còn PARTIAL. Dữ liệu Web hai verdict là test cơ chế, không human ground truth.
