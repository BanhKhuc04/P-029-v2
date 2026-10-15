# Extension PointSnap cho CVAT (A15)

> Đối chiếu 12/10/2026: logic có 36 Node tests trên nhánh review, gồm identity/scope và từ chối ambiguity. Chưa nghiệm thu lại Load unpacked/service worker/DOM trong Chrome hoặc Edge thật. CVAT API 2.78.1 đã kiểm riêng; không suy ra toàn luồng MV3 đã đạt. Xem [phần 05](../../../review/2026-10-10/05-report.md) và [bàn giao tổng](../../../review/2026-10-10/08-handoff.md).

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
2. Mở job 3D trên CVAT. Bảng **PointSnap** hiện ở góc trái (kéo thanh tiêu đề để dời chỗ, bấm `–` để thu gọn) và tự bật bộ lọc của CVAT để **chỉ hiện box có cờ**.
3. Tab **Lỗi hiện tại**: bấm **›** / **‹** (hoặc phím `.` / `,`, cũng nhận `]` / `[`) để tới frame có lỗi kế tiếp; box lỗi được yêu cầu làm sáng khi có ánh xạ duy nhất. Bấm nhiều lần liền thì extension đi lần lượt sau khi CVAT tải xong từng frame.
4. Thẻ lỗi cho biết mức lỗi, loại lỗi, box, mô tả và **Cách sửa**. Frame có nhiều box lỗi thì bấm `1 / 2 ›` trên thẻ để chuyển box kế tiếp; khi sidebar không phân biệt được box trùng nhãn/cờ, dùng link `serverID` trong báo cáo. Rê chuột vào box trên CVAT thì thẻ đổi theo box đó.
5. Ghi kết luận bằng **Đúng là lỗi** / **Báo nhầm** (cần PointSnap chạy).
6. Tab **Danh sách**: mọi lỗi của job, lọc Lỗi / Cảnh báo, bấm dòng để nhảy tới frame; phía dưới là **Quét lại** / **Quét + gắn cờ**. Sửa box xong thì **Save** (Ctrl+S) như bình thường.
7. Xong cả job: bấm **Quét + gắn cờ** ở tab Danh sách để kiểm lại, rồi tải lại trang để thấy cờ mới.

### Liên kết với giao diện web PointSnap

Mở cùng lúc web PointSnap (`127.0.0.1:8765`) và tab CVAT đang mở job:

- Ở màn Kết quả của web, nút **Mở trong CVAT** đổi thành **Chuyển CVAT tới box này** khi có tab CVAT (cài extension) đang mở job đó. Bấm nút: tab CVAT nhảy tới frame và yêu cầu làm sáng box theo identity hợp lệ, rồi được đưa lên trước, **không tải lại trang**. Chưa mở tab CVAT nào thì nút mở link như cũ.
- Chọn mục trên web (bấm dòng, phím J / K) thì tab CVAT tự chuyển theo.
- **Đúng là lỗi / Báo nhầm** ghi ở web hay ở extension đều hiện ở bên kia sau khoảng 2 giây.

Cách hoạt động: web gửi lệnh lên PointSnap (`POST /api/extension/focus`); extension hỏi PointSnap mỗi giây (`GET /api/extension/poll`), lần hỏi đó cũng cho web biết tab CVAT đang mở job nào (`GET /api/extension/status`). Không có kết nối trực tiếp giữa hai tab, dùng host permission được người dùng cấp cho CVAT và PointSnap.

| Chức năng | Cần PointSnap chạy? |
|---|---|
| E1 Bảng PointSnap trên trang job | Không |
| E2 Tự bật bộ lọc "chỉ box có cờ" | Không |
| E3 Thông báo lỗi + gợi ý sửa của box đang chọn | Không |
| E4 Lỗi tiếp / trước (nút, phím `,` `.` hoặc `[` `]`), không tải lại trang | Không |
| E5 Danh sách mọi lỗi của job, bấm dòng để nhảy tới frame | Không (lấy từ cờ trên CVAT) |
| E6 Quét lại, Quét + gắn cờ, ghi **Đúng là lỗi / Báo nhầm** | Có |

Phím `,` `.` và `[` `]` được chọn theo bản CVAT trong tài liệu gốc; kiểm lại nếu bản CVAT khác có shortcut trùng; `J` (Join) và `K` (Switch keyframe) đã là phím của CVAT nên extension không dùng. Gõ tiếng Việt kiểu Telex có thể biến `[` `]` thành `ư` `ơ`, nên dùng `,` `.`.

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

API PointSnap dùng: `GET /api/extension/jobs/{job_id}?cvat_url=…` (dự án và lần quét mới nhất của job), `GET /api/extension/poll`, `POST /api/projects/{slug}/scans`, `GET /api/projects/{slug}/scans/{run_id}`, `GET` / `PUT /api/projects/{slug}/scans/{run_id}/reviews[/{index}]`.

Test:

```bash
node --test tests/*.test.js
```

## Identity, quyền và dữ liệu

API repair/apply/rollback luôn cần `slug` của dự án để chọn đúng server CVAT. Để
chỉ cho phép một số extension ghi qua API local, đặt `POINTSNAP_EXTENSION_IDS` thành
danh sách ID extension (32 ký tự, phân cách bằng dấu phẩy; xem tại `chrome://extensions`)
trước khi chạy `pointsnap ui`; extension ngoài danh sách khi đó chỉ được đọc. Không đặt
biến này thì mọi extension vẫn ghi được như trước.

## Giới hạn kết nối canvas 3D

CVAT hiện không công khai scene Three.js và cầu nối cập nhật box trên canvas.
Panel/HUD hiển thị **Chưa kết nối được canvas 3D của CVAT**. Content script gửi
hình học box đang chọn từ annotations API qua `POINTSNAP_SET_ACTIVE_BOX`; HUD có
thể đo residual từ dữ liệu đã lưu thật. Box chưa lưu hoặc frame nội suy không có
keyframe API thì chưa có hình học để đo; cần Save và chọn lại box.

Vẽ Ghost Target, kéo thả Magnet Snap, phím L và chốt Green Lock trực tiếp trên
canvas cần patch `cvat-canvas3d` để đọc trạng thái chọn/kéo và ghi box qua API
canvas của CVAT. Phần tích hợp sâu này **chưa thực hiện**. Các thao tác trên canvas
không được báo là đã cập nhật CVAT. Nút áp dụng sửa trong panel vẫn dùng endpoint
ghi có OCC và đọc lại xác nhận.

Focus/review được khóa theo origin CVAT, project/run và job. Sidebar DOM không luôn cung cấp serverID; nhiều box cùng nhãn/cờ thì extension từ chối đoán box. Quét lại sau Save/gắn cờ vì CVAT có thể cấp ID mới. Extension nhận origin HTTP(S), không hỗ trợ URL có đường dẫn proxy; không chứa user/password/query/fragment. Cấp host permission ở Tùy chọn và reload extension/trang sau cập nhật. Đổi server/đường dẫn trên Web xóa PAT cũ; nhập PAT của đúng server. Không lưu PAT vào extension. Các request scan/flag vẫn có tác động backend; dùng job thử và phối hợp Save theo [bảo mật local](../docs/local-security.md).
