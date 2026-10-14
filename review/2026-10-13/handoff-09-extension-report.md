# Bàn giao 09 — ảnh camera và bộ lọc extension

Model review: **gpt-6.1-sol**. Base `7ec580a`. Kiểm runtime hiện có trên Edge thật, CVAT 2.77.0, task/job 4.

Đã tái hiện: CVAT đang lọc `ServerID=498`, Type Track ở người đi bộ #60; extension ghi “Chỉ hiện box lỗi”. Bấm finding bicycle frame37 chuyển frame nhưng không thấy box vì bộ lọc đó giữ vật khác. Bỏ lọc rồi “Làm sáng box” kích hoạt đúng bicycle #216 (DOM active item); notice cũ “không thấy box” vẫn còn.

Sửa `applyRecentFilter` để chọn lại bộ lọc PointSnap kể cả khi một bộ lọc khác đang bật. UI gọi đúng trạng thái tổng quát “Bộ lọc CVAT đang bật”, vẫn cho bấm “Chỉ box lỗi”; không giả định Filters armed chứng minh đúng bộ lọc. Khi highlight thành công, xóa notice thất bại trước đó.

Thêm nút “Ảnh camera” cho finding ghép được vào lần quét. Worker kiểm project/origin/job/run/index trước khi tải JPEG; chỉ GET đúng endpoint, không query tùy ý, từ chối redirect/SVG/sai MIME, giới hạn 2MB và kiểm magic bytes. Panel chỉ nhận JPEG data URL và escape channel/text; đổi job/run/finding khi request pending không gắn ảnh cũ vào mục mới. Catalog `/api/rules` được cho đọc trên trang job: caller đã gọi nhưng allowlist cũ không cho đi qua.

47 Node PASS, 0 FAIL/SKIP/XFAIL; thêm ca generic filter, camera scope/MIME và stale request. Lệnh từ extension: `node --test tests/core.test.js tests/review05.test.js tests/security06.test.js tests/filter_handoff.test.js`.

Phân biệt bằng chứng: thao tác Edge phía trên kiểm extension đã cài, trước bản sửa này; 47 test kiểm source mới trong VM/transport fixture, chưa chứng nhận MV3 mới đã nạp ở Edge. Cần reload extension sau khi cập nhật code để kiểm UI mới. Không thay nhãn, không Save CVAT hoặc tạo verdict tay trên job4 trong lượt chẩn đoán này.
