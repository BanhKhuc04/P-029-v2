# Extension PointSnap cho CVAT (A15)

Extension Chrome / Edge (Manifest V3) giúp annotator **ở yên trong CVAT** khi sửa các box mà PointSnap đã gắn cờ `pointsnap_error`: tự lọc box lỗi, chuyển frame có lỗi bằng một phím mà không tải lại trang, hiện thông báo lỗi kèm gợi ý sửa.

> Nguyên tắc: extension **không sửa mã nguồn CVAT, không sửa box**. Nó chỉ đọc những gì CVAT hiển thị, đọc nhãn qua REST API chính thức của CVAT (chỉ `GET`, bằng phiên đăng nhập sẵn có của trình duyệt), và bấm hộ các nút có sẵn như người dùng tự bấm.

## Cài đặt (một lần, khoảng 1 phút)

1. Mở `chrome://extensions` (Edge: `edge://extensions`).
2. Bật **Developer mode** (Chế độ nhà phát triển).
3. Bấm **Load unpacked** → chọn thư mục `source-tool/pointsnap-3d/extension`.
4. Ghim biểu tượng PointSnap lên thanh công cụ nếu muốn (bấm vào biểu tượng là mở trang Tùy chọn).

Mặc định extension chạy trên CVAT ở `http://localhost:8080` và gọi PointSnap ở `http://127.0.0.1:8765`. CVAT ở địa chỉ khác: thêm ở trang **Tùy chọn**, bấm **Lưu** và đồng ý cấp quyền.

Cập nhật bản mới: `git pull`, rồi bấm nút tải lại (↻) của extension ở `chrome://extensions`, rồi tải lại trang CVAT.

## Dùng

1. Quét job bằng PointSnap và **Gắn cờ lên CVAT** (giao diện web `pointsnap ui` hoặc `pointsnap scan --job <id> --flag`).
2. Mở job 3D trên CVAT. Bảng **PointSnap** hiện ở góc trái, kéo thanh tiêu đề để dời chỗ, bấm `–` để thu gọn.
3. Extension tự bật bộ lọc của CVAT để **chỉ hiện box có cờ**.
4. Bấm **Tiếp ›** / **‹ Trước** (hoặc phím `]` / `[`) để tới frame có lỗi kế tiếp; box lỗi đầu tiên tự sáng lên.
5. Rê chuột vào box (trên khung 3D hoặc ở danh sách đối tượng bên phải) → mục **Box đang chọn** hiện nội dung lỗi và gợi ý sửa.
6. Sửa box, **Save** (Ctrl+S) như bình thường.
7. Xong cả job: bấm **Quét + gắn cờ** ở chân bảng để kiểm lại, rồi tải lại trang để thấy cờ mới.

| Chức năng | Cần PointSnap chạy? |
|---|---|
| E1 Bảng PointSnap trên trang job | Không |
| E2 Tự bật bộ lọc "chỉ box có cờ" | Không |
| E3 Thông báo lỗi + gợi ý sửa của box đang chọn | Không |
| E4 Lỗi tiếp / trước (nút, phím `[` `]`), không tải lại trang | Không |
| E5 Danh sách mọi lỗi của job, bấm dòng để nhảy tới frame | Không (lấy từ cờ trên CVAT) |
| E6 Quét lại, Quét + gắn cờ, ghi **Đúng là lỗi / Báo nhầm** | Có |

Phím `[` `]` được chọn vì CVAT không dùng chúng; `J` (Join) và `K` (Switch keyframe) đã là phím của CVAT nên extension không dùng.

## Khi có trục trặc

| Hiện tượng | Cách xử lý |
|---|---|
| "CVAT chưa nạp bộ lọc PointSnap" | Lần đầu mở một task: bấm **Tải lại trang** trong bảng (chỉ cần một lần). |
| Bộ lọc không tự bật | Làm tay: **Filters → Add rule → Attributes → nhãn → `pointsnap_error` → is not empty → Submit**. Các nút khác vẫn dùng được. |
| "Job này chưa có thuộc tính pointsnap_error" | Chưa gắn cờ lần nào: quét và gắn cờ bằng PointSnap trước. |
| Chân bảng ghi "PointSnap tắt" | Chạy `pointsnap ui`, rồi bấm **Kiểm tra lại**. E1–E5 vẫn chạy khi PointSnap tắt. |
| Gắn cờ xong mà không thấy cờ mới | CVAT chỉ đọc nhãn khi mở job: **Save** rồi tải lại trang. |
| Bảng không hiện | Kiểm tra extension đang bật ở `chrome://extensions` và địa chỉ CVAT có trong trang Tùy chọn. |

## Cấu trúc

```
extension/
  manifest.json      quyền: storage, scripting; host: PointSnap 127.0.0.1:8765 (CVAT khác: xin quyền khi thêm)
  background.js      service worker: gọi API PointSnap thay content script; đăng ký content script cho CVAT khác
  options.html/.js   địa chỉ PointSnap, CVAT khác, tự bật bộ lọc, tự làm sáng box
  src/core.js        logic thuần (đọc cờ, gợi ý sửa, frame kế tiếp, bộ lọc) — có test Node
  src/cvat-dom.js    đọc giao diện CVAT và bấm hộ nút (tên lớp ổn định của CVAT)
  src/cvat-api.js    GET nhãn của job qua REST API của CVAT; chuẩn bị bộ lọc trong "Recently used"
  src/seed.js        chạy khi trang bắt đầu tải, chuẩn bị bộ lọc trước khi CVAT dựng trang job
  src/content.js     bảng PointSnap (Shadow DOM, không lẫn CSS với CVAT)
  src/panel-css.js   kiểu dáng bảng, sáng / tối theo hệ thống
  tests/core.test.js node --test tests/*.test.js
```

Bộ lọc được chuẩn bị bằng cách thêm một mục vào **lịch sử bộ lọc** của CVAT (`annotationFiltersHistory` trong localStorage của trang CVAT), giống như khi người dùng đã tự tạo bộ lọc đó một lần; sau đó extension bấm hộ **Filters → Recently used → mục PointSnap → Submit**.

API PointSnap dùng: `GET /api/extension/jobs/{job_id}?cvat_url=…` (dự án và lần quét mới nhất của job), `POST /api/projects/{slug}/scans`, `GET /api/projects/{slug}/scans/{run_id}`, `PUT /api/projects/{slug}/scans/{run_id}/reviews/{index}`.

Test:

```bash
node --test tests/*.test.js
```
