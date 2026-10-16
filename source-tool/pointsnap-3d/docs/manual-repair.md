# PointSnap v2: sửa tay trực tiếp trong CVAT

Giữ bộ quét/model báo lỗi. Extension chỉ đọc hình học đang thao tác và vẽ thước/đường gióng;
không hút box, cân bằng, áp dụng đề xuất hoặc ghi sửa nhãn qua PointSnap.

## Cài và sử dụng

1. Chạy `pointsnap ui` từ môi trường Python của thư mục này; mở `/app`, kiểm tra **Hệ thống**, cấu hình dự án CVAT và quét job. Bản 0.3 chặn quét nếu thiếu model của luật đang bật; xem [hướng dẫn bản mới](workspace-v3.md).
2. Chrome/Edge → Extensions → Developer mode → Load unpacked → chọn `extension/`.
   Dùng phiên bản **0.3.0**. Nếu đã nạp đúng thư mục này: bấm Reload extension, rồi tải lại tab CVAT sau khi Save để thay script. Nếu đang trỏ thư mục dự án cũ, dùng Load unpacked với thư mục bản mới.
3. Mở job 3D. Chọn một lỗi trong bảng PointSnap; box được chọn đúng ID tại đúng frame.
4. Dùng các nút **Cao độ / Kích thước / Hướng / Vị trí** để đổi lỗi trên cùng box.
   Kéo bằng tay nắm và công cụ có sẵn của CVAT. Không cần đọc phần Chi tiết cảnh báo để thao tác.
5. Xem tọa độ/tâm, Dài–Rộng–Cao, yaw, roll/pitch và biến thiên từ lúc bắt đầu kéo.
   Nhả chuột để kiểm lại lỗi đang xét. **Save / Undo / Redo vẫn là thao tác của CVAT.**

Công tắc **Đo trực tiếp / Khung / Thước / Điểm** điều khiển lớp hướng dẫn trên cả bốn ô.
Nhìn trên thể hiện Dài/Rộng, bên hông thể hiện Dài/Cao, phía trước thể hiện Rộng/Cao theo camera CVAT;
tọa độ X/Y/Z trong HUD là hệ dữ liệu của frame. Tọa độ/kích thước dùng mét, độ lệch dùng cm, góc dùng độ.
Đường gióng đi theo camera khi zoom, xoay, phóng to ô hoặc thay bố cục.

Lọc box có cờ mặc định tắt để giữ các box xung quanh làm ngữ cảnh. Có thể bật thủ công khi đã gắn cờ.
Nếu bộ lọc đang giấu box cần chọn, bấm **Hiện tất cả** trước khi chọn lại lỗi.

## Hiểu đúng phản hồi

- **Số đo tham khảo**: hình học hiện tại và bằng chứng của lần quét. Khung xanh nét đứt là tham chiếu,
  không phải vị trí đúng tuyệt đối. Đường xanh lá là mặt đất đo được; mặt/điểm đỏ chỉ vùng dư hoặc hụt.
- **Còn lỗi đang xét**: bộ kiểm tra vẫn tìm thấy lỗi đó trên dữ liệu nhãn trong bộ nhớ CVAT.
- **Hết lỗi đang xét · chưa Save**: đã kiểm tra lại lỗi đang chọn; không chứng nhận toàn bộ box/job hoặc các luật khác.
- **Chưa đủ bằng chứng**: thiếu điểm/pose, ít frame tham chiếu, luật chưa hỗ trợ, mất backend hoặc có roll/pitch
  mà bộ kiểm tra hiện tại chỉ hỗ trợ yaw. Người dùng vẫn sửa được và vẫn thấy số đo 3D đầy đủ.

Sau Save, hướng dẫn cũ được gỡ vì CVAT có thể cấp lại ID. Quét lại để nhận lỗi và tham chiếu mới.
Khi đổi frame/box hoặc kéo tiếp, kết quả kiểm tra trả chậm không được gắn vào lần sửa mới.
Lỗi nhãn/thuộc tính dẫn đến thanh Objects; vùng nghi sót đối tượng chỉ là tham chiếu để vẽ bằng Cuboid của CVAT.

## Giao diện lập trình

- `GET /api/projects/{slug}/scans/{run_id}/findings/{index}/guide`: `GuideContext` phiên bản 1 gồm định danh,
  hình học gốc, luật, bằng chứng, tham chiếu, ngưỡng, điểm liên quan và góc nhìn ưu tiên.
- `POST .../evaluate`: nhận `box`, `context`, `context_complete`, `revision`; trả trạng thái
  `remaining`, `cleared` hoặc `insufficient` cùng revision. Đây là phép tính chỉ đọc, không phải lệnh lưu.
- `apply-repair` và `rollback` ở cấp job/project đã ngừng, trả **HTTP 410**. Snapshot/lịch sử v1 vẫn được giữ.
  Các GET đề xuất v1 chỉ phục vụ tương thích đọc, không có khả năng áp dụng.
- Bộ tương thích ưu tiên CVAT 2.77.1: lấy store bằng `cvatUI.registerComponent`, đọc cuboid/camera hiện hành.
  Truy cập camera nội bộ được cô lập trong `cvat-compat.js`; thiếu khả năng tương thích thì không đoán tọa độ.

## Chạy kiểm thử

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests auto-tests
node --test extension/tests/*.test.js
.\.venv\Scripts\python.exe -m playwright install chromium
.\.venv\Scripts\python.exe auto-tests\browser\e2e_manual_live.py --project cvat-new
```

E2E thật mặc định dùng Microsoft Edge đã cài, MV3 và CVAT tại URL của dự án được chỉ định.
Đọc PAT trong cấu hình local, không in PAT; tạo một task kiểm thử riêng với point cloud tổng hợp rồi xóa task đó.
Backend thử riêng chạy cổng 8766, không sửa dự án đang làm. Bản extension sao chép cho bài thử chỉ thêm quyền truy cập
cổng backend này. Dùng `--browser chromium` nếu bản Chromium trên máy chạy được.

Kết quả, ảnh và loại GPU được ghi tại `out/manual-v2/live/`. Đo riêng thời gian dựng lớp hướng dẫn và thời gian
từ sự kiện chuột đến cập nhật HUD DOM trong lúc kéo. `--software-rendering` dùng để kiểm tra máy không có GPU;
độ trễ của CVAT/WebGL khi dựng bằng phần mềm có thể vượt mục tiêu 50 ms.

Các kiểm thử dành riêng cho API tự sửa v1 đã được thay bằng hợp đồng chỉ đọc/HTTP 410 và kiểm tra thao tác tay.
Các kiểm thử scanner/model, hình học, đọc CVAT, cấu hình, lưu kết luận và lịch sử độc lập vẫn được giữ.
