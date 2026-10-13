# Test tự động PointSnap trong thư mục riêng

## Chạy toàn bộ các lớp kiểm tra

`Run-AllTests.ps1` chạy pytest, các test của runner, dataset thật khi có
`NUSCENES_ROOT`, 37 ca Node, kiểm tra cú pháp Python/JS/PowerShell, manifest,
dependency, build wheel/sdist từ Git HEAD và cài wheel vào môi trường riêng.
Kết quả từng pha, JUnit và log nằm trong `out/all-tests/<thời điểm>/`.

```powershell
# Cài công cụ build vào .venv trước lần chạy đầu
.\.venv\Scripts\python.exe -m pip install build 'setuptools>=68' wheel

.\auto-tests\Run-AllTests.ps1

# Kiểm tra cả CVAT thật, Docker, model ảnh và 10 cảnh × 10 vòng chèn lỗi
.\auto-tests\Run-AllTests.ps1 -Dataset D:\Vin_uni\data\nuscenes -LiveCvat -Docker -ModelSmoke -Evaluate -Rounds 10 -ReviewModel gpt-6.1-sol

# Report API thật: tự tạo và xóa một task thử, so nhãn trước/sau các GET
.\.venv\Scripts\python.exe .\auto-tests\smoke_services.py --out out\service-smoke
```

`-LiveCvat` và `smoke_services.py` chỉ ghi/xóa task thử do chính chúng tạo.
`-Docker` tạo image tag riêng và chạy lại pytest Linux trong container tạm, sau đó
tự xóa container. Linux không có torch/dataset/CVAT nên giữ SKIP tương ứng.
Image/container của dịch vụ đang dùng được giữ nguyên.
`-ModelSmoke` chạy inference mới trên ba ảnh CAM_FRONT cho Mask R-CNN,
Grounding DINO + SAM 2.1 và hybrid bằng checkpoint đã tải; thiếu checkpoint trả
SKIP, Hugging Face ở chế độ offline nên không tự tải model khác. Box Critic được kiểm
bằng các TorchScript fixture trong pytest; không coi đó là kiểm chứng chất lượng
của một model đã huấn luyện để triển khai.

Runner phân biệt PASS/FAIL/SKIP/XFAIL. Pha thất bại không ngăn các pha sau chạy;
exit 1 nếu có FAIL. Thành công của lệnh eval chỉ chứng minh lệnh chạy được:
đọc `evaluation/summary.json` để xem các mục tiêu chất lượng.
Sau eval, runner kiểm riêng 5 cảnh held-out bằng `check_quality.py`, so proxy
cảnh báo/lỗi trên 100 box với ngưỡng 2,0/0,5. Các finding trên GT chưa được chấm
tay nên không được gọi là false positive đã xác nhận; không lấy tập tuning gộp
vào held-out để làm tỷ lệ thấp đi. Proxy vượt ngưỡng làm pha này FAIL.
`-ReviewModel` chỉ ghi lại model đã thực hiện review trong báo cáo; không chọn hoặc
thay model của ứng dụng hay model Codex đang chạy.

`test_review_contracts.py` có ba regression độc lập cho lỗi tìm thấy trên main
ngày 13/10/2026 (logit Critic quá âm, track ID 0, rider motion thiếu pose).
Chúng cố ý giữ assertion đúng kỳ vọng và sẽ FAIL tới khi các lỗi được sửa;
không đánh dấu xfail hoặc nới assertion để báo xanh. Package build lấy Git HEAD,
vì vậy khi kiểm bản sửa production mới cần commit các sửa đó trước khi build.
Workflow GitHub Actions cũng thu thập `tests` và `auto-tests` để các regression
mới không bị bỏ qua; trên main chưa sửa, hai regression track/rider sẽ làm CI
thất bại, còn regression Critic cần môi trường có torch để thực thi.

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
