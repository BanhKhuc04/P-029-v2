# 05 — Kết quả review Web và extension

Ngày: **11/10/2026**, Asia/Saigon. Nhánh: **`review/05-frontend-extension`**, base `review/04-backend-cli-reports` (`59ef9c4`). Đã review, sửa và xác minh trong phạm vi bên dưới. Các ca extension cài thật còn thiếu môi trường, không tính là đạt.

## Môi trường và kết quả

- Windows, Python 3.12.14, Node 24.19.0; CVAT Docker 2.78.1.
- Browser thực tế: Codex In-app Browser (Chromium; connector không cung cấp số phiên bản). Không có browser Chrome/Edge hoặc native app được kết nối để cài MV3.
- Web thử: `127.0.0.1:8766`, POINTSNAP_HOME riêng trong `out/review05/home`; không dùng dữ liệu dự án người dùng.
- Task/job **60**, tên `PointSnap review 05 (tự xóa)`, scene giả 3 frame, 4 box. nuScenes giả có điểm cho preview nhưng thiếu bằng chứng mặt đất. Mọi token nằm ở thư mục ignored.
- **436 pytest đạt**, không skip, 49,56 s; 1 cảnh báo deprecation Starlette/httpx. **21 Node đạt**, gồm 14 regression mới chạy logic Web/content script thật trong VM. `node --check` và `git diff --check` đạt.
- 10 regression ban đầu đều lỗi trước sửa. Sau sửa đã qua; thêm 4 ca scope/identity của content script. Test cũ được cập nhật theo thuộc tính mutable CVAT carry qua keyframe.

## Findings đã sửa

| Mã | Mức | Hiện tượng / sửa | Xác minh |
|---|---|---|---|
| F05-01 | P1 | Form đọc/ghi `size.class_range.manual_ranges` sai schema; chuyển sang `size.manual_ranges` | Bấm lưu trước sửa báo khóa không hợp lệ; ảnh 02/03, test và lưu thật sau sửa |
| F05-02 | P2 | Ngưỡng 0 bị thay bằng mặc định do `parseFloat(...) || ...`; giữ số 0 | Test; reload UI giữ warning_m=0 |
| F05-03 | P1 | Request project/run cũ ghi đè state mới; capture slug/epoch và phiên load run | Deferred-fetch Node tests, guards ở loaders/poll/reviews |
| F05-04 | P2 | Empty giữ detail cũ; pagination có thể chọn mục ngoài trang | Clear state/preview, clamp lựa chọn; bộ lọc empty và test |
| F05-05 | P2 | Poll scan dùng slug hiện tại, lỗi mạng mắc busy, phần trăm mô phỏng | Poll đúng scope, dừng và báo lỗi, dùng progress backend + aria-valuenow |
| F05-06 | P2 | F5 đổi project; history dùng created_at không tồn tại, failed/queued giống gate fail | Lưu slug; dùng started_at; chỉ run done có kết quả/chart |
| F05-07 | P2 | Đổi form/YAML hoặc project mất draft; guideline tải chậm ghi đè edits | Xác nhận bỏ draft, load không đè dirty; không save khi chưa có config; test cancel |
| F05-08 | P2 | Modal thiếu focus trap/Escape/return focus; opener nằm trong dropdown đã ẩn | Inert nền, trap Tab, Escape, trả focus về project dropdown; thao tác thật xác minh focus |
| F05-09 | P1 | Review extension match frame/label/message làm review box khác có cùng cờ | Match track_id/source_id; ambiguous DOM selection không review; Node tests |
| F05-10 | P2 | Shape outside xuất hiện trong cờ; mutable track flag không carry và keyframe không sort | Bỏ outside, sort, carry đến reset rỗng; Node tests |
| F05-11 | P1 | Danh sách nhiều box cùng frame chọn box đầu; focus từ Web không gửi ID | Gửi ID, row giữ index, chọn theo kind/objectId, từ chối ambiguity; Node tests |
| F05-12 | P2 | Highlight đoán box theo label, có thể trỏ nhầm | Match label+cờ duy nhất; nhiều box trùng thì báo dùng link serverID; không dùng private React state |
| F05-13 | P1 | Scan/review/navigation trả chậm sau đổi job gắn vào job mới | Capture sid/run; bỏ response cũ; chặn scan đôi; Node tests |
| F05-14 | P2 | Job chưa có attribute bị ẩn nút quét; job không có frame_count hiển thị 0 frame | Giữ renderScan, frame count derive start/stop hoặc “chưa rõ số” |

## Journey và checklist

“Một phần” nghĩa là các bước liệt kê đã kiểm; phần còn lại không được suy ra từ unit test. Mapping TC: chuẩn `docs/test/CHUAN-KIEM-THU.md`, nhóm Web A11/A14/A15, extension E1–E6, không tạo mã TC giả.

| Ca | Mục tiêu / thao tác và prerequisite | Kết quả / ma sát / bằng chứng |
|---|---|---|
| R05-01 | Mở UI, chọn project, tải lại | Đạt trên IAB; splash ảnh 01; reload giữ review05/theme |
| R05-02 | Project và kết nối đúng/sai/thiếu token | Một phần: 3 project fixture, valid nối 2.78.1, bad báo mất kết nối; modal tạo/cancel/Escape đã thử. CRUD/validation có pytest; chưa GUI xóa/tạo mới |
| R05-03 | Task/job và quét | Đạt job60 qua UI, busy→done→results; epoch/double scan có test |
| R05-04 | Hiểu gate và dữ liệu thiếu | Đạt: gate “kiểm tra một phần” nêu thiếu bằng chứng; ảnh 06 |
| R05-05 | Lọc/search/empty | Một phần: search không khớp→0 mục, clear trả đủ; chưa thử mọi tổ hợp/sort |
| R05-06 | Xuất và link đúng đối tượng | Một phần: UI 5 finding, CSV HTTP 5 dòng; 3 link đối chiếu dưới đây. Chưa mở cả 3 trong CVAT/GUI download HTML |
| R05-07 | Duyệt J và preview | Một phần: J chuyển frame0→2, preview 2 điểm, đúng track800; ảnh 04/05/07; chưa benchmark load chậm hình học |
| R05-08 | Review và refresh | Đạt: index0 fp, reload giữ, 1/5 mẫu và precision 0% rõ; đổi scope có test |
| R05-09 | History | Một phần: giờ 19:57, job60, 2/1 count; test/source loại unfinished; chưa kiểm mọi config cũ qua GUI |
| R05-10 | Guideline và rule | Một phần: save form/0, size_class_range off rồi quét lỗi giảm2→1; test draft cancel; chưa GUI reset/YAML invalid |
| R05-11 | Cài MV3/host/reload | Bị chặn: chỉ có IAB; không có Chrome/Edge được kết nối. Chuyển R06-13 logic sender/permission |
| R05-12 | Filter/attribute | Một phần: core ngoài cờ/outside/carry có test và sửa giữ nút scan; chưa thao tác filter thật CVAT |
| R05-13 | Nhiều box/frame, điều hướng | Một phần: content VM identity và ambiguity; chưa CVAT navigation DOM thật |
| R05-14 | Web↔tab CVAT focus | Một phần: bridge pytest, payload ID và content match; chưa đo nhận lệnh trên MV3 thật |
| R05-15 | Review hai phía | Một phần: backend bridge/reviews và VM scope; chưa đo poll/latency MV3 thật |
| R05-16 | Save/flag/reload | Chưa GUI CVAT; phần ghi/snapshot/live API được kiểm ở 03/04 và tiếp tục 06 |
| R05-17 | Offline/timeout | Một phần: backend timeout/online tests, poll error guard; chưa shutdown Web/CVAT khi MV3 đang chạy |
| R05-18 | Khác server jobID trùng | Đạt logic bridge theo cvat_url (pytest); chưa 2 CVAT server thật |
| R05-19 | Theme/viewport/zoom | Một phần: sáng/tối 1280×720 và hẹp600×800; bảng cuộn ngang; ảnh04–06; chưa zoom200% thật |
| R05-20 | Keyboard/focus | Một phần: J, modal Escape/returnfocus đã thử; focus trap source; chưa screen reader/trọn journey Tab |
| R05-21 | Phím CVAT/Telex | Một phần: source dùng , . [ ], bỏ input/modals/modifiers; chưa Telex/CVAT thật |
| R05-22 | Text dài/HTML | Source escape + fixture chuyển review06; chưa đủ mọi viewport với text dài |

### Parity và ba link cụ thể

Run `20261011-195735-736658373958-job60`: UI/backend 4 box, 2 lỗi, 1 cảnh báo, 2 info, 5 finding; CSV 5 dòng data. Review `{0: fp}`. Finding count không bằng số box có cờ.

| Dòng | Frame | Rule | Label | ID | Link đã đối chiếu ở UI/backend |
|---|---|---|---|---|---|
| 0 | 0 | size.class_range | car | track800, shape11981 | `/tasks/60/jobs/60?frame=0&type=track&serverID=800` |
| 1 | 2 | size.in_track | car | track800, shape11983 | `/tasks/60/jobs/60?frame=2&type=track&serverID=800` |
| 2 | 0 | heading.motion | car | track800, shape11981 | `/tasks/60/jobs/60?frame=0&type=track&serverID=800` |

Sau tắt size_class_range qua form và lưu, run `20261011-200116-512904348878-job60`: 1 lỗi,1 cảnh báo,2 info,4 finding; rule bị tắt không còn trong rows. Đây là thay guideline, không phải sửa nhãn.

## Giới hạn và bàn giao

MV3 E1–E6 chưa được chứng minh chạy trọn trên Chrome/Edge. Sidebar CVAT 2.78 hiển thị clientID; không có serverID công khai trong DOM. Với các box trùng nhãn+cờ, extension báo ambiguity, dùng link serverID trong report. Cần kiểm cài extension, filter, save/flag/reload và sync trên browser được kết nối trước kết luận nghiệm thu UI/CVAT.

Job60 được giữ tạm cho kiểm phần06 rồi xóa bằng API với đối chiếu tên. Không xóa task1/task8. Dữ liệu và credentials thử không commit. Security DOM/Origin/permissions chuyển06; runtime/benchmark chuyển07; hướng dẫn và kiểm MV3 thật chuyển08.
