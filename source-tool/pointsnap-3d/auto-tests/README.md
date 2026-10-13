# Test tự động PointSnap trong thư mục riêng

Chạy từ thư mục `source-tool/pointsnap-3d` bằng PowerShell:

```powershell
# Test thuật toán, API web qua TestClient, review, gate, writer giả lập và logic extension.
.\auto-tests\Run-Tests.ps1

# Thêm kiểm tra dịch vụ thật + báo cáo job 1, chỉ GET, không sửa nhãn.
.\auto-tests\Run-Tests.ps1 -Online -JobId 1

# Thêm kiểm tra tọa độ/điểm của dataset thật.
.\auto-tests\Run-Tests.ps1 -Online -Dataset 'C:\Users\Han\Downloads\v1.0-mini'

# Tùy chọn kiểm tra upload, ghi/xóa cờ CVAT thật trên task tạm do test tự tạo rồi xóa.
# Các task/job sẵn có không được dùng cho thao tác ghi.
.\auto-tests\Run-Tests.ps1 -LiveCvat
```

Cần `.venv` và package dev (đã cài trên máy hiện tại): `pip install -e ".[dev]"`.
Node cần nằm trên PATH để chạy test logic extension; có thể dùng `run.py --node <đường dẫn node>`.
CVAT token đọc từ `.env`; không đưa token vào command hoặc báo cáo. Online cần web 8765 và API report qua CVAT 8080 đang chạy.

Kết quả mỗi lần lưu riêng ở `out/auto-tests/<thời điểm>/`:
- `report.md`: từng ca PASS/FAIL/SKIP.
- `results.json`: kết quả có thể xử lý bằng code.
- `checklist-review.md` / `.json`: đối chiếu 41 mã A01–F04 với test thực sự đã chạy; ghi rõ phần chưa kiểm.
- `python.xml`, `dataset.xml`, `live-cvat.xml` khi chạy pha tương ứng: JUnit.
- log từng pha và báo cáo job JSON/HTML/CSV khi chạy online.

Exit 0 = không ca chạy nào thất bại; vẫn phải đọc SKIP. Exit 1 = có thất bại. Log không bị ghi đè giữa các lần chạy.

Runner gọi lại bộ test hiện có, không sao chép chúng. Test writer mặc định dùng dữ liệu/CVAT giả. `-LiveCvat` là chế độ có ghi, chỉ trên task thử tạm. Không tự gọi chế độ này trong mặc định.

Đây không phải test bấm nút trên trình duyệt. Chưa thay thế việc xem camera/point cloud, xác nhận precision thật, kiểm extension đã cài, hoặc giao diện hiển thị đúng. Một job có lỗi nhãn vẫn có thể PASS kiểm thử phần mềm: finding lỗi được lưu trong báo cáo job, không bị đánh đồng với lỗi code.

`checklist-map.json` ghi test nào kiểm phần code của từng ca. `PASS` ở bảng checklist chỉ áp dụng cho phần code đó; phần UI/CVAT thật/chất lượng ảnh còn lại được ghi bên cạnh. Test thiếu hoặc skip sẽ là `NOT_RUN`, mục chưa có test là `MANUAL`. Khi sửa checklist cần cập nhật map; runner báo lỗi nếu thiếu/thừa mã. Không tự ghi kết luận Đúng/Báo nhầm vào PointSnap.
