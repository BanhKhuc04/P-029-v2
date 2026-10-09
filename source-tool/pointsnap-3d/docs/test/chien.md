# Kết quả kiểm thử — Nhữ Đình Chiến (09/10/2026)

Máy: Windows 11 Pro, RAM 16 GB · Python 3.11.9 · Docker Desktop 28.3.3 · CVAT v2.77.0 / v2.75.1 · commit main: 7897143
Thời gian cài đặt (Phần 1): 25 phút

---

## Kết quả từng ca

| Mã | Kết quả (Đạt / Lỗi / Không làm được) | Mã lỗi | Ghi chú |
|---|---|---|---|
| **TC-01** | Đạt | | `python -m pytest -q` trả về: 199 passed, 2 skipped trong 25s, không có lỗi. |
| **TC-02** | Đạt | | `pointsnap --help` in đủ các lệnh: `scan`, `gate`, `diff`, `config`, `nuscenes`, `eval`, `ui`. |
| **TC-03** | Đạt | CHIEN-01 | Đã tạo Task 48 (Job 69) từ `scene-0061`, nạp 3.333 box và 234 ảnh camera vào CVAT. Lần đầu bị 403 do token CVAT tạo ra mặc định bật Read-only. |
| **TC-04** | Đạt | | Mở http://localhost:8080/tasks/48/jobs/69 thấy đầy đủ point cloud, 3D box cuboid và cụm ảnh 6 góc camera. |
| **TC-10** | Đạt | | `pointsnap ui` khởi chạy máy chủ tại http://127.0.0.1:8765, giao diện web tiếng Việt trực quan. |
| **TC-11** | Đạt | | Tạo dự án `pointsnap-demo` thành công, danh sách bên trái hiển thị đúng nhãn "Có Token". |
| **TC-12** | Đạt | | Tab Kết nối CVAT kiểm tra thành công, hiển thị kết nối tốt với máy chủ CVAT local. |
| **TC-13** | Đạt | | Điền token sai: hệ thống bắt lỗi chuẩn (HTTP 401: Invalid token), không crash giao diện, không lộ token. Nhập lại token chuẩn thì kết nối lại bình thường. |
| **TC-14** | Đạt | | Tab Quét: chọn Job 69, bấm bắt đầu quét ngay. Có thanh tiến độ cập nhật mượt, hoàn tất sau ~2.3 giây và tự động chuyển sang tab Kết quả. |
| **TC-15** | Đạt | | Màn hình Kết quả & Gate: hiển thị kết luận KHÔNG ĐẠT (8 Lỗi, 35 Cảnh báo, 88 Thông tin, 3.333 box). |
| **TC-16** | Đạt | | Bộ lọc hoạt động tốt: lọc theo mức độ Lỗi/Cảnh báo, theo loại lỗi (`floating`, `track.jump`, `size.class_range`), số lượng hiển thị cập nhật chính xác. |
| **TC-17** | Đạt | | Bấm link mở CVAT ở các dòng kết quả nhảy chính xác tới frame tương ứng và làm sáng box của serverID/track. |
| **TC-18** | Đạt | | Tải file báo cáo HTML (`out/report_job_69.html`) và CSV (`out/report_job_69.csv`) thành công, số lượng và thông tin lỗi khớp 100% với giao diện web. |
| **TC-19** | Đạt | | Tính năng Quét lại & Gắn cờ lên CVAT tự động cập nhật cờ lỗi `pointsnap_error` cho 43 box bị lỗi/cảnh báo trên CVAT. Lọc thuộc tính trên CVAT hiển thị chuẩn xác. |
| **TC-20** | Đạt | | Sửa thủ công 3 box có cờ trên CVAT (nâng đáy box lún chạm mặt đường, chỉnh lại kích thước), nhấn Save (Ctrl+S). Quét lại có gắn cờ: số lỗi giảm xuống, cờ cũ được gỡ bỏ. |
| **TC-21** | Đạt | | Tab Lịch sử: lưu trữ đầy đủ các phiên quét (run_id), có biểu đồ phân bố và xem lại chi tiết kết quả từng lần quét cũ. |
| **TC-22** | Đạt | | Tab Guideline: tắt luật `track_jump` -> Lưu guideline -> Quét lại: không còn lỗi `track.jump` trong danh sách phát hiện. |
| **TC-23** | Đạt | | Tab Guideline: sửa cấu hình class kích thước -> Lưu và F5: các thiết lập tùy biến được giữ nguyên vẹn. |
| **TC-24** | Đạt | | Tab Guideline YAML: nhập sai cú pháp YAML -> hệ thống hiển thị thông báo lỗi chi tiết, chặn lưu cấu hình sai. |
| **TC-25** | Đạt | | Tab Guideline: nới lỏng ngưỡng Gate (cho phép tối đa 100 lỗi, 100 cảnh báo) -> Quét lại: Gate chuyển sang trạng thái ĐẠT. |
| **TC-26** | Đạt | | Tạo dự án thứ hai trỏ thư mục nuScenes sai: hệ thống vẫn quét được lỗi kích thước và track, thông báo rõ thiếu point cloud và bỏ qua luật lơ lửng/lún. |
| **TC-27** | Đạt | | Xóa dự án yêu cầu gõ xác nhận lại tên slug dự án, xóa sạch dữ liệu run mà không ảnh hưởng tới dự án chính. |
| **TC-30** | Đạt | | CLI `pointsnap scan --job 69`: xuất snapshot JSON, report HTML và CSV vào `out/`, thống kê 8 Lỗi, 35 Cảnh báo, 88 Thông tin giống hệt Web UI. |
| **TC-31** | Đạt | | CLI `pointsnap scan --job 69 --flag`: gắn cờ thành công 43 box lỗi lên CVAT trực tiếp từ terminal. |
| **TC-32** | Đạt | | CLI `pointsnap gate --job 69`: in kết quả KHÔNG ĐẠT với `$LASTEXITCODE = 1`. Khi truyền cấu hình nới ngưỡng, trả về ĐẠT với `$LASTEXITCODE = 0`. |

---

## Lỗi phát hiện

### CHIEN-01: Lỗi 403 Forbidden khi tải cảnh nuScenes lên CVAT do token mặc định là Read-only
- **Ca:** TC-03 · **Nhóm:** Cài đặt / Tích hợp CVAT
- **Mức:** Nặng (gây gián đoạn quy trình tạo task nếu không biết cách cấu hình).
- **Bước làm:**
  1. Đăng nhập CVAT trên trình duyệt -> Profile -> Access tokens -> Tạo token mới.
  2. Sao chép token vào `.env` với biến `CVAT_TOKEN`.
  3. Chạy `pointsnap nuscenes to-cvat --scene scene-0061 --out ... --upload`.
- **Mong đợi:** Task và Job được tạo thành công trên CVAT.
- **Thực tế:** Báo lỗi `POST http://localhost:8080/api/tasks → HTTP 403: {"detail":"You do not have permission to perform this action."}`.
- **Nguyên nhân:** Giao diện CVAT khi tạo Access Token mặc định tích chọn checkbox `Read-only`.
- **Đề xuất khắc phục:** Bổ sung ghi chú rõ ràng vào tài liệu `CAI-DAT.md` và `README.md`: *"Khi tạo Access token trên CVAT, bắt buộc phải bỏ chọn (uncheck) ô Read-only để tool có quyền tạo task và gắn cờ lỗi"*.

### CHIEN-02: Lỗi UnicodeEncodeError (cp1252) trên terminal PowerShell của Windows khi in thông báo tiếng Việt
- **Ca:** CLI / Web backend · **Nhóm:** CLI / Môi trường Windows
- **Mức:** Nhẹ (không ảnh hưởng dữ liệu, nhưng gây crash một số lệnh CLI có in tiếng Việt).
- **Bước làm:** Chạy lệnh Python/CLI có in ký tự tiếng Việt Unicode trong terminal Windows với mã hóa mặc định CP1252.
- **Mong đợi:** In chuỗi tiếng Việt bình thường ra màn hình console.
- **Thực tế:** Python văng lỗi `UnicodeEncodeError: 'charmap' codec can't encode character ...`.
- **Đề xuất khắc phục:** Thiết lập `sys.stdout.reconfigure(encoding='utf-8')` trong điểm vào CLI (`pointsnap/cli/main.py`) hoặc hướng dẫn người dùng set biến môi trường `$env:PYTHONIOENCODING = "utf-8"`.

---

## Xem tay cảnh báo (Đứt track, Kích thước & Lơ lửng/lún)

Dưới đây là 20 mục mức **Lỗi / Cảnh báo** được lấy từ kết quả quét Job #69 và đối chiếu trực tiếp trên CVAT 3D:

| # | Frame | Track | Class | Quy tắc | Mức | Kết luận | Lý do |
|---|---|---|---|---|---|---|---|
| 1 | 1 | 177 | car | `track.jump` | Lỗi | Báo nhầm | Xe bắt đầu xuất hiện ở góc rẽ khuất, ngoại suy tuyến tính bị lệch so với góc quay tự nhiên của xe. |
| 2 | 16 | 95 | pedestrian | `track.jump` | Lỗi | Đúng | Người đi bộ đổi hướng đột ngột, annotator đặt box frame 16 bị lệch khỏi vệt điểm LiDAR 1.84 m. |
| 3 | 7 | 121 | bus | `size.class_range` | Cảnh báo | Đúng | Chiều rộng box là 3.52 m, annotator bao cả phần gương và dư khoảng trống hai bên (chuẩn bus ≤ 3.2 m). |
| 4 | 7 | 177 | car | `track.jump` | Cảnh báo | Đúng | Box xe ở frame 7 bị giật sang phải 1.25 m so với frame 6 và frame 8 (lỗi nội suy vị trí). |
| 5 | 13 | 120 | traffic_cone | `track.jump` | Cảnh báo | Đúng | Cọc tiêu là vật thể tĩnh nhưng tâm box bị dịch chuyển 0.48 m giữa 2 frame liên tiếp. |
| 6 | 14 | 137 | traffic_cone | `track.jump` | Cảnh báo | Đúng | Cọc tiêu tĩnh bị dịch chuyển tâm 0.55 m do annotator không cố định tọa độ. |
| 7 | 15 | 131 | traffic_cone | `track.jump` | Cảnh báo | Đúng | Cọc tiêu tĩnh bị nhảy vị trí 0.81 m ở đầu track. |
| 8 | 21 | 162 | pedestrian | `track.jump` | Cảnh báo | Đúng | Người đi bộ đứng yên nhưng annotator xoay chỉnh box làm tâm nhảy 0.85 m. |
| 9 | 25 | 173 | pedestrian | `track.jump` | Cảnh báo | Báo nhầm | Người đi bộ chạy nhanh qua đường ở frame cuối, vận tốc tăng tự nhiên nhưng vượt ngưỡng ngoại suy 0.8 m. |
| 10 | 1 | 64 | truck | `floating` | Lỗi | Báo nhầm | Xe tải đỗ ở lề dốc công trường nghiêng, ít điểm mặt đường quanh bánh do bị khuất góc. |
| 11 | 4 | 168 | pedestrian | `floating` | Lỗi | Đúng | Người đi bộ bước lên bờ vỉa hè, nhưng annotator kéo đáy box lún sâu xuống lòng đường 34 cm. |
| 12 | 21 | 33 | truck | `floating` | Lỗi | Đúng | Xe tải đi qua gờ giảm tốc, annotator đặt đáy box hổng khỏi mặt đất 23 cm. |
| 13 | 23 | 36 | motorcycle | `floating` | Lỗi | Đúng | Xe máy đang di chuyển, annotator vẽ box ôm cả bóng dưới gầm khiến đáy box chìm xuống mặt đường 20 cm. |
| 14 | 24 | 36 | motorcycle | `floating` | Lỗi | Đúng | Cùng xe máy track 36, frame 24 tiếp tục bị lún sâu 21 cm dưới mặt đất. |
| 15 | 25 | 36 | motorcycle | `floating` | Lỗi | Đúng | Tiếp tục bị lún 18 cm ở frame 25. |
| 16 | 0 | 64 | truck | `floating` | Cảnh báo | Báo nhầm | Mặt đường công trường gồ ghề, RANSAC ước lượng mặt phẳng cục bộ bị lệch nhẹ. |
| 17 | 2 | 64 | truck | `floating` | Cảnh báo | Không chắc | Vùng tiếp giáp giữa lòng đường nhựa và lề đất dốc, khó xác định chính xác cao độ chuẩn. |
| 18 | 3 | 64 | truck | `floating` | Cảnh báo | Báo nhầm | Dao động cao độ tự nhiên của hệ thống treo xe tải khi chuyển bánh (lệch ~4 cm). |
| 19 | 5 | 64 | truck | `floating` | Cảnh báo | Đúng | Bánh xe tải đè lên mặt đường, đáy box bị kéo chìm sâu hơn bề mặt lốp xe 19 cm. |
| 20 | 6 | 64 | truck | `floating` | Cảnh báo | Đúng | Đáy box tiếp tục bị kéo chìm dưới mặt lốp xe 21 cm. |

### Thống kê Precision xem tay:
- **Số mục đánh giá:** 20 mục
- **Đúng:** 14 mục
- **Báo nhầm:** 5 mục
- **Không chắc:** 1 mục
- **Precision xem tay** = $\frac{\text{Đúng}}{\text{Đúng} + \text{Báo nhầm}} = \frac{14}{14 + 5} = \frac{14}{19} \approx \mathbf{73.68\%}$.

---

## Góp ý phát triển

1. **Chỗ khó dùng:**
   - Khi chạy lệnh quét có gắn cờ trên CVAT, nếu đang mở tab CVAT thì người dùng cần phải bấm Save và Reload trang (F5) thì cờ mới hiện. Extension có thể hiển thị thêm một tooltip nhắc nhở: *"Nhãn đã được gắn cờ mới từ PointSnap, vui lòng tải lại trang (F5) để hiển thị cờ"*.
   - Trên Web UI, ở bảng danh sách lỗi nên có nút bấm "Copy Link CVAT" nhanh để tiện gửi cho annotator khác trong nhóm.

2. **Đề xuất tính năng:**
   - **Tính năng 1:** Tự động phát hiện phiên bản mã hóa môi trường Windows console và cấu hình stream UTF-8 để hạn chế lỗi `cp1252`. *(Ưu tiên: Cao)*
   - **Tính năng 2:** Thêm nút toggle "Bỏ qua các cảnh báo ở frame đầu/cuối của track" trong guideline để giảm bớt hiện tượng ngoại suy nhảy vị trí tự nhiên khi vật thể mới vào khung nhìn. *(Ưu tiên: Trung bình)*
   - **Tính năng 3:** Hỗ trợ phím tắt trên Web UI để chuyển nhanh giữa các finding (`J`/`K`) và đánh dấu ĐÚNG (`1`) / BÁO NHẦM (`2`) ngay tại chỗ để lưu vào file review. *(Ưu tiên: Trung bình)*

---

## Kịch bản video demo R2 (3–5 phút) — Nhữ Đình Chiến

- **Thời lượng:** 3–4 phút
- **Nội dung các phân đoạn:**
  1. **0:00 – 0:45 (Tổng quan & Khởi động):** Mở giao diện PointSnap Web (http://127.0.0.1:8765), giới thiệu kết nối CVAT local và Task 48 (`scene-0061`).
  2. **0:45 – 1:30 (Quét & Gắn cờ lỗi):** Thực hiện quét Job 69 với tùy chọn "Gắn cờ lên CVAT". Trình bày bảng kết quả 8 Lỗi, 35 Cảnh báo.
  3. **1:30 – 2:45 (Tương tác trên CVAT với Extension):**
     - Mở tab CVAT có cài đặt extension PointSnap 3D.
     - Dùng phím tắt `.` / `,` để nhảy qua các frame có box bị gắn cờ `pointsnap_error`.
     - Chỉ ra box bị lún dưới đất và box nhảy vị trí.
     - Chỉnh sửa 2–3 box: kéo đáy box lên đúng mặt đường tiếp xúc của lốp xe, lưu (Ctrl+S).
  4. **2:45 – 3:30 (Quét lại & Cổng Gate ĐẠT):**
     - Nhấn "Quét lại" từ extension hoặc web UI.
     - Cho thấy số lỗi giảm và cờ của box đã sửa biến mất.
     - Đổi nhẹ ngưỡng hoặc nới Gate -> Kết luận Gate chuyển sang **ĐẠT (Passed)**.
