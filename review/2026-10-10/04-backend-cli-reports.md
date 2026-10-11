# 04 — Review backend, CLI, tác vụ quét và báo cáo

**Nhánh kết quả:** `review/04-backend-cli-reports`, tiếp nối phần 03 tại `f79a85b`.
**Trạng thái:** đã thực hiện ngày 11/10/2026 trong phạm vi báo cáo.
**Đầu ra:** [báo cáo](04-report.md), [hợp đồng API/CLI và trạng thái](04-contracts.md), [bàn giao](04-handoff.md), [bằng chứng](evidence/04/test-results.md). Các mục dưới là checklist gốc; kết quả thực hiện xem báo cáo.

Đọc [quy trình chung](README.md), [mẫu báo cáo](report-template.md); dùng mapping/giới hạn từ 01–03. Đường dẫn code tính từ tool root.

## 1. Mục tiêu và phạm vi

Review điều phối đúng từ yêu cầu người dùng đến kết quả lưu trữ, lỗi có thể xử lý và tác động lên CVAT. Các đường chạy dùng chung scanner phải thống nhất config, dữ liệu và findings khi so sánh.

| Module | Nội dung |
|---|---|
| `pointsnap/cli/main.py`, các command modules, `__main__.py` | Parse, config/env, UTF-8, exit codes, scan/gate/nuscenes/eval/ui/config/diff |
| `pointsnap/web/app.py`, `projects.py` | Pydantic request, project CRUD, guideline, token tách riêng, CVAT task list, routes |
| `pointsnap/web/runner.py`, `preview.py`, `link.py` | Scan queue, state/results/history, preview, reviews và cầu nối extension |
| `pointsnap/report/html.py`, `csv_rep.py`, core serialize | Report escaping, encoding, metadata, deep link, số lượng và format |
| `pointsnap/api.py`, `tests/test_report_api.py`, `Get-Report.ps1` | Report API bổ sung theo PAT caller; nay tracked trên nhánh 04, không thuộc nền 5dcc97f |

Phân biệt **FastAPI Web server** với **report API cục bộ dùng ThreadingHTTPServer**. Chúng không tự chia sẻ project state/config/token chỉ vì cùng dùng scanner.

## 2. Hợp đồng API cần lập bảng

| Nhóm | Routes đã thấy trong `web/app.py` | Nội dung phải đối chiếu |
|---|---|---|
| Dự án | `/api/projects`, `/api/projects/{slug}` | GET/POST/PUT/DELETE, slug/name/token, không trộn dữ liệu hai dự án |
| Guideline | `/api/projects/{slug}/guideline`, `/guideline/reset` | YAML/config, defaults, khóa dynamic bị xóa, token được loại |
| CVAT | `/api/projects/{slug}/cvat/check`, `/cvat/tasks` | URL/token/quyền, phân trang và thông báo |
| Scan | `/api/projects/{slug}/scans`, `/scans/{run_id}` | 202/start, list/status/results, thuộc đúng project/run |
| Preview/reviews | `/scans/{run_id}/findings/{index}/preview`, `/reviews`, `/reviews/{index}` | Index, snapshot, exact_frame, verdict `ok`/`fp`/null và lưu kết luận |
| Flag | `/scans/{run_id}/flag` | Re-scan trước ghi cờ, trả run mới, không ghi bằng ID cũ |
| Extension | `/api/extension/focus`, `/poll`, `/status`, `/jobs/{job_id}` | Scope job/CVAT, seq, online timeout, reviews revision |
| Báo cáo | `/scans/{run_id}/report.html`, `/report.csv` | Run đúng project, file có thật, download/encoding và trạng thái thiếu file |
| API local | `/pointsnap/jobs/{job_id}/report`, `/pointsnap/health` | JSON/HTML/CSV, PAT caller, error mapping, giới hạn đồng thời |

Các route rút gọn nối với prefix project tương ứng. Bảng báo cáo thực tế phải ghi method, đầy đủ path, input/output schema, status codes và ca test; các route trong bảng chỉ là điểm bắt đầu để kiểm code.

## 3. Trình tự

1. Theo CLI dispatch và FastAPI routes đến core/adapter/report. Lập catalog đầy đủ gồm negative cases.
2. Kiểm config precedence ở CLI và project; so sánh bằng config sạch và mock, không đọc/in token thật.
3. Theo lifecycle `queued → running → done/failed`; xem data trong memory và trên đĩa, cách restart phục hồi.
4. Theo đường report/preview/reviews, đối chiếu ID và metadata; thử hai dự án/run để phát hiện nhầm phạm vi.
5. Kiểm CLI/Web/local API bằng cùng input/config/frame source trước khi kết luận số liệu lệch.
6. Kiểm gate coverage, đồng thời, lỗi đĩa/network; bàn giao UX/security/performance.

## 4. Checklist

| Mã | Ca | Mong đợi / bằng chứng |
|---|---|---|
| R04-01 | CLI thiếu/sai argument, config lỗi, lệnh diff | Mã 2 cho sai cú pháp; lỗi runtime/unimplemented mã 3 theo CLI; diff không bị quảng bá đã dùng được |
| R04-02 | CLI scan thành công và gate pass/fail | Scan mã 0 khi hoàn thành; gate 0/1 theo tiêu chí; lỗi kết nối/config có mã phù hợp |
| R04-03 | Defaults → env → file config → project settings | Ghi từng giá trị hiệu lực/nguồn; web và CLI khác precedence phải được giải thích |
| R04-04 | Project CRUD, duplicate/invalid slug, hai dự án | Không truy cập/sửa/xóa nhầm project; secret không trả qua response |
| R04-05 | YAML sai/khóa sai/reset/dynamic mapping | Không lưu config hỏng; xóa class/group không bị defaults làm sống lại ngoài hợp đồng |
| R04-06 | Scan hai lần nhanh, run IDs và queue | Hai lượt có trạng thái/kết quả riêng; không đè dữ liệu; ghi worker limit thực tế |
| R04-07 | Restart giữa scan và sau scan | Trạng thái còn lại trên đĩa được giải thích; run dở không bị trình bày như hoàn tất |
| R04-08 | Task/job sai, CVAT offline/401/403/timeout | Không treo/hỏng server; lỗi giữ đủ ngữ cảnh và không lộ token |
| R04-09 | Disk write/JSON hỏng/run thiếu file | Không trả report sai hoặc báo done khi output thiết yếu thiếu; ghi đường phục hồi |
| R04-10 | Thiếu LiDAR/manifest/pose | Giới hạn coverage của 01 được thể hiện nhất quán ở summary/gate/CLI/local API |
| R04-11 | Số box và findings HTML/CSV/JSON/UI | Cùng config/data: đúng số errors/warnings/info, frame/rule/IDs, tiêu chí đếm outside/occluded |
| R04-12 | Chuỗi tiếng Việt, dấu phẩy, newline, HTML trong label/message | CSV đọc đúng cột; HTML render text an toàn; UTF-8 trên Windows |
| R04-13 | Preview exact frame hoặc keyframe gần nhất | exact_frame và vị trí được trình bày đúng; thiếu manifest/box/index có lỗi rõ |
| R04-14 | Save/delete review, nhiều request cùng lúc | Không mất kết luận; file JSON đầy đủ sau ghi; precision dùng đúng tập đã review |
| R04-15 | Flag kết quả cũ sau nhãn CVAT thay đổi | Re-scan rồi flag, trả run mới; đối chiếu bảo toàn nhãn với 03 |
| R04-16 | Extension seq/revision/timeout và CVAT khác | Không thực thi lệnh cũ hoặc nhận sai job; reset memory sau restart có hành vi xác định |
| R04-17 | Report API PAT đọc và PAT không có quyền | Đúng quyền caller mỗi request; format/status/checks/metadata theo scanner thực tế |
| R04-18 | Đồng thời tạo report/scan/review | Không lẫn token/data giữa caller; có giới hạn tài nguyên hoặc giới hạn sử dụng được ghi |

## 5. Lệnh kiểm tra tập trung

```powershell
python -m pytest -q tests/test_cli.py tests/test_config.py tests/test_scan_gate.py
python -m pytest -q tests/test_web.py tests/test_web_a14.py tests/test_web_a15.py
```

Nếu file API cục bộ có trong checkout, kiểm riêng:

```powershell
python -m pytest -q tests/test_report_api.py
```

API/test API nay được đưa vào nhánh 04; chưa merge main. Ca HTTP/mock không thay thế review giao diện; ca report token thật đã chạy riêng trên job thử và ghi quyền token, không lưu token vào báo cáo.

## 6. Rủi ro đã được chuyển đến

- **Coverage gate:** phần 01 đã tái hiện gate=True khi không LiDAR với dữ liệu giả; chốt ý nghĩa kết luận trước thay đổi schema/UI.
- **Metadata checks local API:** đối chiếu danh sách `checks` trong JSON với mọi luật hiện tại, luật bật/tắt và dữ liệu sẵn có; chưa ghi đây là finding đã review ở phần 04.
- **Dependency:** ScanRunner dùng helper ở `cli/common.py`; đánh giá có gây khó tái sử dụng/test không, chỉ đề xuất tách nếu có tác động thực tế.
- **Persisted state:** liệt kê file project.json/secret.json/guideline.yaml/runs và dữ liệu in-memory; không giả định có database/queue bền vững ngoài code.

## 7. Bàn giao và hoàn tất

- [ ] Catalog route/CLI đủ entry points, method/schema/status và ca lỗi.
- [ ] Scan lifecycle, restart, project/run isolation có bằng chứng.
- [ ] Bảng parity dùng cùng code/config/data và giải thích khác biệt có chủ đích.
- [ ] Gate, findings count và coverage có hợp đồng rõ cho 05/07.
- [ ] Findings ghi nhầm/lost update đưa 03; secret/origin/path/XSS đưa 06; hiệu năng đưa 07.
- [ ] `04-report.md` tách bản tracked với API local, mock với HTTP/CVAT thật; findings còn mở có nhánh tiếp nhận.
