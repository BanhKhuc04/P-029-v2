# Báo cáo ngắn — kiểm lại ba nhánh 01, 02, 03

Ngày 11/10/2026, Asia/Saigon; theo yêu cầu kiểm lại sau khi push phần 03. Đã đọc diff theo phạm vi từng phần, đối chiếu caller/hợp đồng và chạy suite riêng ở từng nhánh.

| Nhánh | Kết quả mới | Kết luận trong phạm vi review |
|---|---|---|
| review/01-overview-architecture | 256 pytest, 0 skip, 1 warning; head c27d54b | Tìm và sửa RV-01-009: cloud rỗng khi tắt floating vẫn có thể cho gate ĐẠT. Đính chính dấu quay −90° và cách fetch riêng nhánh |
| review/02-core-detectors | 321 pytest, 0 skip, 1 warning; head 7fca827 | Không tìm thêm lỗi mới trong sửa detector. Nhận guard coverage mới từ 01; 65 hồi quy detector tiếp tục đạt |
| review/03-data-cvat-integrations | 371 pytest, 0 skip, 1 warning; code merge b841f63 | Không tìm thêm lỗi mới trong bản sửa adapter/writer đã kiểm; nhận 01/02. 49 hồi quy dữ liệu + 3 live CVAT đạt; task thử đã xóa |

- Node extension **7/7 đạt**; source và tests extension giống nhau trên cả ba nhánh. Không có skip vì thiếu Docker/dataset.
- Ca gate mới: 4 failed trước sửa; sau sửa đạt. Bản sửa `0727c15` được merge theo 01→02→03, giữ lịch sử; không force-push và không merge main.
- Phần 03 đã kiểm scene thật 39 frame/234 ảnh/3333 box; đọc lại tâm/yaw lệch 0, gắn/gỡ cờ giữ hình học và lặp lại không đổi nội dung. Browser thấy đủ camera và link track đúng frame/đối tượng.
- Chỉ stage code/test/tài liệu thuộc phạm vi. Token, dataset, snapshot/output và Docker/API local chưa tracked nằm ngoài các commit.

## Còn cần lưu ý

1. Writer phát hiện nhãn đổi sau scan và trước PATCH, **còn race sau GET cuối** nếu client khác sửa cùng lúc; chưa có bảo đảm atomic phía server. Tránh chỉnh cùng job khi tool ghi cờ. Đây là giới hạn chưa được loại bỏ, tiếp tục 04/06.
2. Chưa nghiệm thu server BTC/CVAT 2.77 chuẩn, full extension, precision/recall xem tay hoặc cài máy mới. API/Docker local chưa tracked không thuộc suite bàn giao; PCD ASCII/compressed chưa hỗ trợ.
3. Các nhánh có dependency: PR 01→main, PR 02→01, PR 03→02 khi phần trước chưa merge. Chuyển base về main sau khi dependency đã merge và kiểm lại diff/CI. Các lỗi adapter/writer được sửa trong 03; chỉ dùng 01/02 chưa có những sửa đó.

Bàn giao: [01](01-handoff.md), [02](02-handoff.md), [03](03-handoff.md). Kết luận review giới hạn theo bằng chứng; không chứng nhận toàn bộ sản phẩm đã sẵn sàng phát hành.
