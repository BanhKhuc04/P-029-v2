# Bàn giao phần 04 — đọc trước khi mở PR

**Nhánh:** `review/04-backend-cli-reports`, không có ngày. **Base:** `review/03-data-cvat-integrations` tại `f79a85b`. **Code:** `83832f9`. Báo cáo, lý do sửa và nội dung PR bằng tiếng Việt.

## Kết quả

- **436 pytest + 7 Node đạt, 0 skip trong full suite**; một warning Starlette/httpx.
- Review 18 ca, sửa/kiểm lại 19 findings; có 56 hồi quy mới và nhận thêm 9 test API trước đây local.
- CVAT 2.78.1 thật: Web/CLI/API cùng counts/rule/frame/IDs/gate, HTML/CSV giống byte.
- PAT chỉ đọc 200; PAT worker không có quyền job 403; token sai/thiếu 401. Không token dịch vụ/cache.
- Đổi length trên task thử sau scan, flag quét fresh, gắn đúng 1 box và giữ geometry mới; preview exact, review FP và history done sau restart đạt.
- Get-Report.ps1 tải thật trên PowerShell 7; UTF-8 BOM và parse Windows PowerShell 5.1 được sửa/kiểm.
- Task thử, PAT và worker thử đã xóa; dataset/snapshot/token/full output không vào Git.

## Vì sao sửa

Run ID trùng, đọc run khác project, bridge/preview không scope CVAT có thể khiến người dùng xử lý nhầm dữ liệu. Restart và file hỏng không được biến thành kết quả done. Report API/HTML phải giữ ý nghĩa gate khi thiếu bằng chứng, counts không tính outside marker. Input guideline/project lỗi phải có phản hồi rõ. Token không đi vào YAML raw/lỗi HTTP; text CSV được bảo vệ tại exporter chung.

Đọc [báo cáo](04-report.md), [contracts/state/parity](04-contracts.md), [lệnh/bằng chứng](evidence/04/test-results.md). Các sửa tập trung theo lỗi, không đổi threshold detector hoặc thêm dependency runtime.

## Phạm vi được push

Hai commit code `b7f00d0` và `83832f9`, tổng 21 đường dẫn code/script/test; commit tài liệu riêng. `pointsnap/api.py`, `tests/test_report_api.py`, `Get-Report.ps1` nay tracked trên nhánh 04. Docker/Compose/auto-tests/architecture local/output chưa tracked vẫn ngoài commit. Không dùng git add toàn workspace.

## Giới hạn cần giữ khi review tiếp

- Một process/home; 1 scan worker, cap 16 queued/running; API cap 2 report. Không chứng nhận nhiều workers hoặc tải lớn.
- Run dở sau restart thành failed, không tự resume/flag. Atomic replace từng file không phải transaction nhiều file hoặc bảo đảm mất điện.
- Race GET cuối/PATCH CVAT từ 03 còn tồn tại; tránh chỉnh cùng job lúc ghi cờ.
- Web/extension phải reload cùng bản để gửi cvat_url. Journey nhiều tab/keyboard/UX thuộc 05; auth/CORS/deployment thuộc 06/08.
- API process riêng dùng env/default; chưa chia sẻ guideline/secret Web. Entrypoint API hiện bind 0.0.0.0:8081, chưa nghiệm thu expose LAN.
- Python 3.12/Node 24/CVAT 2.78.1 là tổ hợp đã kiểm; không chứng nhận server BTC/2.77.
- PowerShell 5.1 Restricted trên máy review chặn chạy file; smoke dùng 7 RemoteSigned, không đổi policy máy.

## Base PR và nhánh tiếp theo

Nếu 03 chưa merge, base PR **`review/03-data-cvat-integrations`** để diff chỉ phần 04. Sau khi 01–03 đã merge main, đổi base sang main và kiểm lại diff/CI. Phần 05 bắt đầu từ nhánh 04 này.

[So sánh riêng phần 04](https://github.com/AI20K-Build-Phase-Cohort-4A/P-029/compare/review/03-data-cvat-integrations...review/04-backend-cli-reports).

## Nội dung PR sẵn dùng

**Tiêu đề:** `Review phần 04: sửa scope, trạng thái scan và tính nhất quán báo cáo`

```markdown
## Mục tiêu và lý do
Ngăn đọc/gắn cờ nhầm project/CVAT; giữ history và trạng thái rõ khi restart/lỗi; thống nhất counts/gate giữa CLI, Web và API.

## Thay đổi
- Run ID riêng, scope project/path, không xóa project đang scan; run.json persisted và queue cap.
- JSON/YAML có validation/atomic replace; lỗi runtime CLI mã 3; sessions đóng sau dùng.
- Gate/coverage/counts HTML/JSON dùng chung; CSV text safety; report API theo PAT caller.
- Bridge scope URL CVAT+job, cập nhật hai caller JS; preview tìm đúng nguồn/identity.
- Che token raw YAML/lỗi; project preset/name/update/default sạch env.
- Đưa riêng API/test API/Get-Report từ local vào Git, sửa Get-Report URL và encoding.

## Kiểm tra
436 pytest + 7 Node đạt, 0 skip; 1 warning môi trường.
CVAT thật: HTML/CSV ba kênh giống byte, JSON counts/rule/frame/IDs/gate khớp.
PAT read_only 200, không quyền 403, token sai/thiếu 401.
Fresh scan/flag sau chỉnh nhãn bảo toàn geometry, preview/reviews/history đạt.
Get-Report tải thật bằng PowerShell 7; parse 5.1 sau BOM đạt.
Task/PAT/worker thử tự dọn, không credential/dataset/snapshot/output trong commit.

## Dependency và giới hạn
Base review/03-data-cvat-integrations tại f79a85b; code 83832f9.
Một process/home; GET/PATCH CVAT chưa atomic; chưa nghiệm thu UI đầy đủ/LAN/server BTC và các version khác.
API là process riêng, Docker/Compose local chưa được đưa vào nhánh.
```

Lượt này chỉ push nhánh; chưa mở/merge PR hoặc cập nhật main.
