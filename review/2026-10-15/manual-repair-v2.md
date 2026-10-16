# PointSnap v2 — triển khai và kiểm chứng 15/10/2026

Đã triển khai tại `D:\Vin_uni\P-029-v2`, phiên bản Python/API/extension **0.2.0**.
Giữ scanner và model; bỏ hút box, cân bằng, chốt vị trí và áp dụng/hoàn tác sửa tự động.
API ghi hình học v1 trả HTTP 410. Lịch sử/snapshot cũ vẫn được giữ.

## Kết quả sử dụng

- Khung tham chiếu, mặt đất/thước khoảng hở, thước Dài–Rộng–Cao, mặt/điểm dư hụt và hướng/góc quay trên cả bốn ô.
- Đọc cuboid/camera thật từ CVAT qua plugin entry point; không suy tọa độ bằng độ dịch con trỏ.
- Kéo bằng CVAT; nhả chuột kiểm lại draft chưa Save với ngữ cảnh nhãn trong bộ nhớ.
- Thiếu điểm/pose/frame tham chiếu hoặc roll/pitch không được bộ kiểm tra hỗ trợ thì không báo hết lỗi.
- Bỏ kết quả trả chậm; gỡ tham chiếu khi Save/đổi frame; phân biệt ID track và shape.
- Các bộ dò có thể đổi mà giao diện công cụ vẫn nhận hợp đồng `GuideContext v1`.

Hướng dẫn cài, thao tác, API và giới hạn: [manual-repair.md](../../source-tool/pointsnap-3d/docs/manual-repair.md).

## Kiểm thử

| Bộ | Kết quả |
|---|---|
| Python `pytest tests auto-tests` | 1.235 đạt, 31 bỏ qua; một test tốc độ lịch sử trượt khi chạy đồng thời, chạy riêng lại **đạt** |
| Kiểm tra hợp đồng v2 | 15 đạt, gồm draft chưa lưu, thiếu bằng chứng, nghiêng, đổi frame/ID, size theo track, không ghi file, API 410 và đồng thời |
| JavaScript extension/web | **95/95 đạt** |
| Web E2E trên máy chủ demo riêng | **47/47 đạt**, gồm màn kết quả/Guideline/kết nối và responsive |
| MV3 + canvas CVAT 3D thật | **28/28 đạt**, không có lỗi JavaScript trên trang |
| Cú pháp Python/JS, `git diff --check` | Đạt |

Bài tốc độ lịch sử yêu cầu liệt kê 150 snapshot dưới 2 giây. Lượt đầy đủ đo 2,41 giây khi nhiều bộ đang chạy;
chạy riêng bài đó đạt toàn bộ ngưỡng. Không thay đổi hoặc nới ngưỡng bài thử này.
Các test chỉ dành cho API tự sửa v1 đã được bỏ/thay bằng hợp đồng sửa tay; không dùng chúng để chứng nhận tính năng đã ngừng.

## CVAT thật và độ trễ

Thử trên Windows, Microsoft Edge **155.0.4283.45**, CVAT API báo phiên bản **2.77.0**.
Bộ tương thích được đối chiếu thêm với nguồn CVAT 2.77.1 local. GPU: Intel Iris Xe, ANGLE Direct3D11.
Canvas là CVAT thật, extension được Load unpacked dưới Manifest V3; point cloud và các lỗi kiểm thử là dữ liệu tổng hợp.

- **23,37 ms p95** từ sự kiện chuột đến cập nhật HUD DOM, 62 mẫu trong lúc kéo.
- **3,48 ms p95** cho dựng lớp hướng dẫn, 573 mẫu.
- Đã thử dịch trên từng ô Top/Side/Front, resize, xoay yaw, roll/pitch, chuyển công cụ trên cùng box,
  zoom/đổi kích thước cửa sổ, Undo/Redo, Save và chuyển frame.
- Trước Save, hình học đọc lại từ CVAT API không đổi. Ghi nhãn của trình duyệt chỉ xuất hiện khi dùng Save của CVAT.
- Task thử được tạo riêng và xóa sau thử; không chỉnh job đang gán của người dùng hoặc mã nguồn CVAT.

Đây là độ trễ tới cập nhật DOM, không phải đo thời gian phát sáng của màn hình. Lượt cưỡng bức dựng phần mềm trước đó
đạt khoảng 86 ms p95 cho chuột → HUD; không chứng nhận mục tiêu 50 ms cho máy không có tăng tốc GPU.
Các bài này kiểm chứng tương tác và tính chỉ đọc, không thay thế đánh giá precision của model trên dữ liệu thực.

## Bằng chứng và chạy lại

- [Báo cáo CVAT thật](../../source-tool/pointsnap-3d/out/manual-v2/live/report.json)
- [Ảnh bốn góc nhìn](../../source-tool/pointsnap-3d/out/manual-v2/live/manual-four-views.png)
- [Ảnh sau kéo sửa](../../source-tool/pointsnap-3d/out/manual-v2/live/manual-after-drag.png)
- [Log Python đầy đủ](../../source-tool/pointsnap-3d/out/manual-v2/python-tests-clean.log),
  [log JS](../../source-tool/pointsnap-3d/out/manual-v2/node-tests.log),
  [log web](../../source-tool/pointsnap-3d/out/manual-v2/web-e2e.log).

Thư mục `out/` là bằng chứng local, nằm ngoài Git. Script tái lập CVAT thật:
`auto-tests/browser/e2e_manual_live.py --project cvat-new`; xem hướng dẫn trước khi chạy trên máy khác.
Sau nâng cấp: khởi động lại PointSnap từ thư mục v2, Reload extension rồi tải lại tab CVAT một lần.
