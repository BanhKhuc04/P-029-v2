# Bàn giao phần 03 — đọc trước khi mở PR

**Nhánh:** `review/03-data-cvat-integrations`, không có ngày. Code phần 03 `40ac166`, đã nhận guard mới qua merge `b841f63`; base ban đầu `82fc8b8` của phần 02, hiện đã nhận bản kiểm lại `7fca827`. Lý do sửa, báo cáo và nội dung PR bằng tiếng Việt.

## 1. Lý do sửa

- Manifest sai frame/sample/pose/time hoặc trùng task ID giữa server có thể khiến tool kiểm point cloud của box khác. Đã kiểm mapping trước scan và tìm bản xuất theo URL+task ID.
- Thuộc tính mutable cần kế thừa tới keyframe đổi giá trị. Reader đã carry đúng; writer reset cờ rõ ở keyframe sau để người gán không sửa nhầm box không lỗi.
- Nhãn đã sửa sau scan không được ghi từ findings cũ. Writer so nhãn mới, kiểm lại trước PATCH và yêu cầu quét lại khi có đổi; ID keyframe cấp lại được khớp có điều kiện.
- PCD/bin corrupt, header sai, NaN/overflow và chuỗi sample/sweep lặp có lỗi rõ. Client không gửi token sang next URL khác origin, không tự theo redirect.
- Snapshot giữ payload API gốc và kiểm bảo toàn roll/pitch/state/attrs; upload fail dọn đúng task mới tạo.

Không thêm dependency hoặc đổi ngưỡng detector. Commit chuẩn hóa xuống dòng `8d81c20` tách riêng; commit sửa code/test `40ac166` có diff logic dễ đọc, tài liệu tách tiếp.

## 2. Kiểm tra và tài liệu

- **371 pytest + 7 Node đạt, 0 skip trong suite mã nguồn bàn giao.** 49 hồi quy mới + 1 live mới và 4 ca cloud rỗng từ phần 01; 1 warning Starlette/httpx.
- CVAT Docker 2.78.1 và nuScenes mini thật; task thử scene-0061: 39 frame, 234 ảnh, 3333 box GT, tâm/yaw đọc lại lệch 0; gắn/gỡ không đổi hình học, lần hai không đổi nội dung.
- Kiểm browser sáu camera ở frame 0 và link track đúng đối tượng; task thật 27 đã xóa, các task suite tự xóa.
- Đọc [báo cáo 18 ca/16 findings](03-report.md), [mapping](03-mapping.md), [lệnh và bằng chứng](evidence/03/test-results.md).

**Giới hạn cần nhớ:** có race giữa GET cuối và PATCH nếu client khác sửa cùng lúc; chưa có bảo đảm atomic. Khi tool ghi cờ, tránh sửa cùng job. Chưa kiểm server BTC, CVAT 2.77 chuẩn, full extension hoặc precision/recall nhãn xem tay. ASCII/compressed không được hỗ trợ.

File token/dataset/ảnh/cloud/snapshot/output và API/Docker local chưa tracked không nằm trong các commit. API local `test_report_api.py` chưa thuộc suite nguồn bàn giao.

## 3. Nhánh gốc PR

Nếu phần 02 chưa merge, base là **`review/02-core-detectors`** để chỉ xem phần 03. Khi 01/02 đã merge main, chuyển base sang **`main`** và kiểm lại diff/CI. Nhánh 03 có chủ đích tiếp nối cả 01 và 02; không mở ba PR vào main rồi coi chúng độc lập.

[So sánh riêng phần 03](https://github.com/AI20K-Build-Phase-Cohort-4A/P-029/compare/review/02-core-detectors...review/03-data-cvat-integrations).

```bash
git fetch origin refs/heads/review/03-data-cvat-integrations:refs/remotes/origin/review/03-data-cvat-integrations
git switch --track origin/review/03-data-cvat-integrations
```

Nếu đã có nhánh trên máy thì switch/pull nhánh đó. Đồng đội tạo PR; lượt làm việc này không merge main.

## 4. Nội dung PR sẵn dùng

**Tiêu đề:** `Review phần 03: sửa mapping dữ liệu và bảo toàn nhãn khi ghi CVAT`

```markdown
## Mục tiêu và lý do
Sửa các nguyên nhân đọc sai frame/thuộc tính, cờ lan sang keyframe khác và ghi findings cũ sau khi người gán đã sửa.

## Thay đổi
- Kiểm manifest/sample/frame/pose/time và nguồn CVAT theo URL+task ID.
- Kế thừa attrs mutable đúng, reset cờ rõ; kiểm nhãn fresh trước PATCH và rebind ID keyframe có điều kiện.
- Kiểm PCD/bin/header/finite, chuỗi sample/sweep; HTTP pagination/origin/JSON/redirect có lỗi rõ.
- Snapshot kèm payload API; so roll/pitch/state/attrs và dọn task upload thất bại.
- Tách commit xuống dòng, code/test và tài liệu; báo cáo/mapping/bàn giao bằng tiếng Việt.

## Kiểm tra
371 pytest + 7 Node đạt, 0 skip trong suite bàn giao. Có 49 hồi quy và 1 ca CVAT live mới; nhận thêm 4 ca coverage từ phần 01.
Scene thật 39 frame, 234 ảnh/6 camera, 3333 box đọc lại tâm/yaw lệch 0; gắn/gỡ bảo toàn hình học.
Task thử đã xóa. 1 warning Starlette/httpx được ghi lại.

## Dependency và giới hạn
Base phần 02 mới nhất tại 7fca827 (ban đầu 82fc8b8); chọn review/02-core-detectors khi chưa merge, sau đó main.
Race sau GET cuối chưa atomic; tránh chỉnh cùng job lúc ghi cờ. Chưa nghiệm thu server BTC/2.77, extension và precision/recall.
ASCII/compressed không hỗ trợ. Không kèm token/dataset/snapshot/output hoặc API/Docker local chưa tracked.

## Tài liệu
review/2026-10-10/03-report.md
review/2026-10-10/03-mapping.md
review/2026-10-10/evidence/03/test-results.md
```
