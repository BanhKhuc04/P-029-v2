# Giao việc theo ngày — PointSnap 3D

Mỗi ngày một file: ai làm gì, xong khi nào, cuối ngày nghiệm thu gì.
Mở file của **hôm nay**, tìm tên mình, làm hết các ô ☐ trong phần của mình.

| Ngày | Mục tiêu trong ngày | File |
|---|---|---|
| Thứ Ba 06/10 | **G0**: 1 cảnh nuScenes hiển thị đúng trên CVAT | [06/10](2026-10-06.md) |
| Thứ Tư 07/10 | Ground chạy được; adapter CVAT đọc được nhãn | [07/10](2026-10-07.md) |
| Thứ Năm 08/10 | **G1**: kiểm chứng ground; phát hiện lơ lửng/lún và kích thước chạy trên 1 cảnh | [08/10](2026-10-08.md) |
| Thứ Sáu 09/10 | **G2**: demo trọn quy trình `scan --flag` → lọc trong CVAT → `gate` | [09/10](2026-10-09.md) |
| Thứ Hai 12/10 | Bộ lỗi chèn giả + `diff`; bắt đầu đánh giá | [12/10](2026-10-12.md) |
| Thứ Ba 13/10 | **G3**: có số liệu cho mọi chỉ số; chốt ngưỡng | [13/10](2026-10-13.md) |
| Thứ Tư 14/10 | Đóng gói, README, video demo, báo cáo | [14/10](2026-10-14.md) |
| Thứ Năm 15/10 | Dự phòng, nộp | [15/10](2026-10-15.md) |

**Quy tắc chung**

- 15 phút đầu ngày họp nhanh (Khánh chủ trì): hôm qua xong gì, hôm nay làm gì, đang kẹt gì.
- Xong hay bị kẹt việc nào thì cập nhật cột **Trạng thái** trong [`TASKS.md`](../TASKS.md); bị kẹt quá 1 giờ thì báo ngay trong nhóm.
- Code: mỗi việc một branch + Pull Request; người code còn lại review, tester kiểm rồi mới merge. Tài liệu commit thẳng `main`.
- Tài liệu của tester (ca kiểm thử, đặc tả, hướng dẫn, mẫu báo cáo) để trong [`docs/`](../docs/).
- Tiêu chí xong chi tiết của từng mã việc (A1, C3, …): xem [`TASKS.md`](../TASKS.md).
