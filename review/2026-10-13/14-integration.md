# Phần 14 — Tích hợp config, CLI/Web, extension, CVAT và gate

- **Nhánh:** `codex/review-14-integration`.
- **Thứ tự:** 14 trong chuỗi 09 → 16.
- **Dependency:** Cần kết quả 09–13; kiểm điểm nối của các detector đã sửa.
- **Trạng thái ban đầu:** 8 ca Chưa chạy. Nhánh hiện mới chứa mã nguồn main d18b1a9 và bộ tài liệu chuẩn bị.
- **Nguồn chung:** [kế hoạch 09–16](REVIEW-PLAN-09-16.md), [phân nhánh](README.md), [inventory 131 file](scope-inventory.tsv).

## Prompt để thực hiện phần này

> Thực hiện review phần 14 trên nhánh codex/review-14-integration. Đọc review/2026-10-13/14-integration.md và kế hoạch chung. Kiểm tra branch/HEAD và dependency trước khi làm; thực hiện đủ TC-14-001 đến TC-14-008. Truy vết luồng gọi và tái hiện trước khi kết luận lỗi; sửa lỗi có bằng chứng trong phạm vi phần 14, giữ sửa 01–08, kiểm lại bằng test phù hợp. Lưu 14-report.md, 14-handoff.md và evidence/14/. Ghi PASS/FAIL/SKIP/XFAIL riêng, ca bị chặn và thao tác cần tôi kiểm tay; không coi test mock là nghiệm thu dữ liệu/model/giao diện thật.

## Chọn nhánh và xác minh đầu vào

Chạy từ repo root; các lệnh test ở dưới chạy từ `source-tool/pointsnap-3d/`:

```powershell
git status --short
git switch codex/review-14-integration
git log -1 --oneline
```

Nếu phần trước đã merge vào main, chạy `git fetch origin main` rồi `git merge origin/main` trên nhánh này, giải xung đột và ghi SHA sau cập nhật. Nếu còn sửa chưa commit ở checkout, hoàn tất commit đúng phạm vi trước khi switch.

## Phạm vi và checklist

Đọc các điểm nối: `core/config.py`, `config.yaml`, `guidelines/spec-vn.yaml`, `core/scanner.py`, `core/gate.py`, `cli/main.py`, `web/app.py`, `web/runner.py`, `web/static/app.js`, `web/static/index.html`, `extension/src/core.js`, `extension/src/content.js`, reader CVAT/nuScenes và report.

| Mã | Kiểm tra và tiêu chí |
| --- | --- |
| TC-14-001 | Tất cả key mới rules/static/camera/missing/critic/learning/spec có validation kiểu, hữu hạn, miền giá trị và quan hệ ngưỡng; giữ sửa parser 02/06/recheck. |
| TC-14-002 | Toggle config/scanner/GUI: từng luật mới bật tắt độc lập, override và round trip guideline; thử cả class nuScenes và spec-vn. |
| TC-14-003 | Cùng input/config: CLI/Web/API xuất cùng findings, severity, coverage và gate; giải thích khác biệt do learned model nếu CLI chưa dùng nó. |
| TC-14-004 | Learn GET/POST, quyền truy cập, slug/run_id, XSS từ dữ liệu/model, đường dẫn model/cache; rà riêng bề mặt mới qua chuẩn bảo mật đã review 06. |
| TC-14-005 | New findings qua preview/report/history/review: sửa verdict, đổi project/job khi request pending, giữ đúng finding và model scope. |
| TC-14-006 | Extension MV3 thật: luật mới, next/prev, frame, track/box không tồn tại và finding chỉ có vị trí; reload tab, service worker restart, server URL/token đổi. |
| TC-14-007 | CVAT ghi cờ/sửa rồi quét lại trên task thử: giữ shape/attrs/ID, phát hiện concurrent Save; race GET cuối → PATCH vẫn phải nêu giới hạn. |
| TC-14-008 | Gate khi thiếu model/ảnh/pose/points hoặc learning hạ severity: không ghi đạt chất lượng đầy đủ khi bỏ luật có yêu cầu hoặc thiếu evidence. |

Test đầu: `python -m pytest -q tests/test_config.py tests/test_numeric_config_recheck.py tests/test_web.py tests/test_web_a14.py tests/test_scan_gate.py tests/test_gate_coverage.py tests/test_queue_cvat_scope.py tests/test_report_api.py tests/test_security_review.py tests/test_data_review_regressions.py`.
Extension: từ `extension/`, chạy `node --test tests/*.test.js`; ngoài suite cần thao tác Chrome + CVAT thật.

## Kết quả phải bàn giao

1. `review/2026-10-13/14-report.md`: SHA khởi đầu/kết thúc; file đã đọc; bảng 8 ca với trạng thái và evidence; findings `RV-14-xxx`; các sửa và test; giới hạn còn mở.
2. `review/2026-10-13/14-handoff.md`: tóm tắt sửa; SHA commit; lệnh đã chạy; PASS/FAIL/SKIP/XFAIL; dependency phần tiếp theo; ca cần người dùng kiểm tay.
3. `review/2026-10-13/evidence/14/`: tóm tắt/probe đã che thông tin nhạy cảm, gắn mã `EV-14-xxx`. Raw dataset, token, weights và output lớn không commit.
4. Inventory: đối chiếu các dòng `owner=14` trong `scope-inventory.tsv`, ghi kết luận cho mỗi file trong báo cáo. File dùng chung thuộc owner khác được tham chiếu và bàn giao nếu đã chạm.
5. Commit theo file cụ thể; xem `git diff --cached --name-only` trước commit. Push/PR/merge thực hiện theo yêu cầu riêng; base PR thường là main khi phần trước đã merge.

Hoàn tất review khi mọi ca có trạng thái và có bằng chứng cho kết luận. Các ca thiếu tài nguyên được bàn giao là Bị chặn; không xác nhận nghiệm thu cho tính năng chưa được kiểm đủ.
