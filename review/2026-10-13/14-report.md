# Review 14 — Tích hợp và triển khai sau bàn giao

Model review: **gpt-6.1-sol**. Base main `7ec580a`; candidate hợp nhất code `3a8bde2` trên `codex/handoff-integration-check`. Các PR chức năng có base main và chưa được coi là đã merge. Final review dùng nhánh `codex/handoff-final-review`, không thay main.

## Kết quả 8 ca

| Ca | Trạng thái | Bằng chứng và giới hạn |
|---|---|---|
| TC-14-001 | PASS trong bộ tự động | Full config/numeric/parser suites; không nới validation để test xanh. |
| TC-14-002 | PASS trong bộ tự động | Static shift và heading độc lập, ID 0; fixture kiểm toggle chủ động bật từng luật, không phụ thuộc default fit.loose. Guideline/spec round trip được kiểm. |
| TC-14-003 | PASS phạm vi hình học | EV-14-001: job 4 thật có 127 finding giống nhau giữa CLI, Web và Report API khi cùng cấu hình hình học, không learned model. Không phải parity camera trên API base. |
| TC-14-004 | PASS tự động, một phần thật | Security/Web/API suites; API không PAT trả 401; JSON/HTML/CSV có PAT trả 200. Model và cache bị giới hạn scope; không gửi token trong query/log. |
| TC-14-005 | PASS trong phạm vi đã chạy | No-ID preview giữ geometry 3D và dựng khung tham khảo đúng frame; probe thật 88 điểm/JPEG 23.848 byte. UI dự án riêng lưu 2 verdict, đổi verdict rồi học phiên bản 2; không tính chúng là truth. Race project/job/camera kiểm bằng Node/Python, không giả là mọi race đã xảy ra trên trình duyệt. |
| TC-14-006 | PARTIAL | 47 Node PASS. Edge MV3 cũ trên job 4 tái hiện generic filter che box; bỏ filter và highlight chọn bicycle client 216. PR #68 sửa filter/notice và thêm ảnh camera. Extension mới chưa reload trong browser; navigation/restart/token-change E2E còn cần kiểm. |
| TC-14-007 | PARTIAL | 3 live CVAT tests + owned-task service smoke kiểm upload/flag/clear và giữ nhãn. Job 4 chỉ đọc; checksum nhãn trước/sau bằng nhau. Chưa sửa box thật rồi Save/rescan trên job 4. Race giữa GET cuối và PATCH vẫn là giới hạn của CVAT writer, không có atomic compare-and-swap. |
| TC-14-008 | PASS tự động, nghiệm thu rộng chưa đạt | Gate thiếu cloud/pose/model/evidence fail theo config; job 4 Web thực tế KHÔNG ĐẠT (4 lỗi, 20 cảnh báo và floating.no_evidence). `checks` API nay chỉ ghi luật đủ điều kiện tài nguyên; không tuyên bố model chưa chạy đã kiểm. G7 vẫn UNASSESSED, không dùng gate job để chứng nhận precision. |

## Findings và sửa

- **RV-14-001 — Đã xác minh:** JSON Report API job 4 trả 500 vì `details` có `np.bool_`. Commit `0df421a` chuyển NumPy scalar/array về JSON, vẫn từ chối NaN/Inf và object lạ. Hai regression bảo vệ đường thật và strict JSON. Sau sửa, JSON/HTML/CSV 200.
- **RV-14-002 — Đã sửa/kiểm lại:** `checks` lấy từ toggle, nên báo camera/Critic đã kiểm dù không có runtime/model. Commit `fc72ea8` thêm metadata tài nguyên, loại optional model không khả dụng, static/missing không pose; giữ `enabled_checks` để thấy cấu hình. `checks_scope` ghi đây là eligibility, không bảo đảm mọi box/model đúng.
- **RV-14-003 — Đã sửa, chờ runtime:** generic CVAT filter che box khi extension nhảy finding; ảnh camera thiếu trong panel. PR #68 và handoff-09 report có tái hiện, sửa source và test. Chưa xác nhận bản MV3 mới trong Edge.

## Evidence

- **EV-14-001:** [deployment_probe.py](evidence/14/deployment_probe.py), [deployment-parity.json](evidence/14/deployment-parity.json): 127 finding, cloud/pose có, checksum nhãn không đổi. Probe dùng project home riêng; camera tắt rõ ràng cho parity.
- **EV-14-002:** [web-mechanics.json](evidence/14/web-mechanics.json): real Web review/learn trong project `parity` trên cổng 8877. Hai verdict là dữ liệu thử; `use_model=false`; server/tab riêng đã đóng.
- **EV-14-003:** PR #66/#68: no-ID preview thật và extension source tests; xem báo cáo nằm trên nhánh PR tương ứng, không giả đường dẫn tồn tại trên main.
- **EV-14-004:** [final-checks.json](evidence/16/final-checks.json): test cuối trên code candidate; 66 focused tests API/gate/security PASS trước full suite.

Report API local đã được triển khai qua Docker/Traefik trong project `pointsnap-handoff`; `/pointsnap/health` trả JSON. Chỉ mount nuScenes/export read-only. Dịch vụ này là môi trường local; không suy ra deployment production.

## Đối chiếu file

18 file owner 14 trong [inventory đã đối chiếu](evidence/16/inventory.json) đều có kết luận và hash. Config/scanner, adapter CVAT/nuScenes, CLI/Web/projects/runner/static và extension/test được truy vết bằng suites, probe thật và PR chức năng. `api.py`, gate, preview, background extension là file dùng chung bổ sung ngoài inventory cũ. Structural inventory không thay thế deep review độc lập từng file.

Các phần còn lại cần người duyệt: reload extension sau merge; thực hiện E2E gắn cờ → sửa box → Save → rescan trên task thử; chấm truth các luật mới. Không tạo kết luận tay giả để vượt gate nghiệm thu.
