# EV-09-006 — chẩn đoán test runner trên Windows

## Failure capture

- Task: review09; branch codex/review-09-geometry; Python3.12.14, pytest9.1.1.
- Geometry tests và nuScenes probes đạt; full suite dừng sau8 ca đầu, trước handler HTTP.
- Cô lập `tests/test_backend_review_regressions.py::test_memory_run_cannot_be_read_or_flagged_from_other_project`, thêm `faulthandler_timeout=20`.
- Trace thread AnyIO: `socket.accept → socket._fallback_socketpair → asyncio.proactor_events._make_self_pipe → WindowsProactorEventLoop → anyio.run_blocking_portal`.
- Thread test chờ future trong `TestClient._portal_factory`. Test này dùng project/token giả, không gọi CVAT thật.

## Diagnosis and contained recovery

Giả thuyết: sandbox chặn kết nối socketpair nội bộ Windows; không phải handler dự án bị deadlock. Single test không coverage cũng kẹt cùng chỗ, nên không quy lỗi cho coverage.

Dừng các phiên pytest bị kẹt bằng interrupt. Chạy cùng full suite ngoài sandbox, dùng basetemp và coverage file mới; `POINTSNAP_LIVE_CVAT=0`, dataset chỉ đọc, test output trong tool/out.

## Result

**631 PASS,5 SKIP,0 FAIL/ERROR/XFAIL**,106,86s; các test HTTP tiếp tục và hoàn tất. Không sửa TestClient/AnyIO/socket/runtime hoặc code backend để né sandbox. Đây là evidence phục hồi test runner, không thay evidence sửa geometry.

Phòng ngừa: nếu socketpair lại kẹt, lấy faulthandler trước; không lặp toàn suite trong cùng điều kiện. Các lỗi fixture constructor/encoding trong probe nháp đã được sửa trước khi dùng evidence; không tính chúng là lỗi sản phẩm.
