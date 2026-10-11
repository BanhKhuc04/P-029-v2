# Bàn giao phần 02 — đọc trước khi mở PR

**Nhánh:** `review/02-core-detectors`. **Lý do sửa, báo cáo và nội dung PR đều bằng tiếng Việt.**

## 1. Vì sao cần bản sửa này

Các lỗi dưới đây khiến người gán nhãn có thể sửa lại box/track đúng hoặc bỏ qua lỗi thật:

| Lỗi gây rework | Cách đã sửa |
|---|---|
| Box xoay làm mất điểm ground và lấy nhầm điểm xe bên cạnh | ROI bao đủ footprint xoay trước khi lọc điểm chính xác |
| Subtype khác nhau dùng chung median kích thước | Chia baseline đúng khóa class/subtype; giữ fallback đã cấu hình |
| Hướng gần +45°/−45° báo sai box chuẩn, bỏ box lệch | Trung vị hướng theo modulo 90° |
| Trộn local/world hoặc epoch/thời gian tương đối | Dùng cùng hệ tọa độ/thời gian cho toàn phép đo |
| Keyframe cuối bị coi là hết track | Với CVAT, dùng stop_frame và outside để xác định kết thúc |
| Đuôi occluded bị đếm thiếu | Đếm đến cuối job khi chưa có keyframe đổi trạng thái |
| Box nội suy tạo lỗi nhập tay hoặc che khoảng thiếu keyframe | Size/jump/heading theo track dùng keyframe thật; đo gap giữa keyframe thật |
| Gợi ý tách ID giữa subtype khác nhau | So class/subtype đã cấu hình; vẫn bắt split thật cùng subtype |
| Kết quả đổi box/thứ tự khi đảo input | Thứ tự và mục tiêu finding được chọn ổn định |
| Dữ liệu hoặc cấu hình NaN/Inf vẫn được kiểm như dữ liệu hợp lệ | Từ chối rõ; kiểm pose, cloud, timestamp và quaternion |

Không đổi ngưỡng phát hiện để làm giảm số cảnh báo. Những sửa này có ca tái hiện và đáp án độc lập; tool vẫn báo lỗi để người dùng xác minh, không tự sửa hình học trong CVAT.

## 2. Kết quả và tài liệu nên đọc

- **317 test Python đạt, 0 skip; 7 test Node đạt.** Có 65 ca mới; đã chạy CVAT Docker 2.78.1 và nuScenes mini thật.
- Task thử đã tự xóa, còn 0 task thử; 1 warning Starlette/httpx được ghi lại.
- Quét scene-0061 thật: 39 frame/3333 box, hoàn tất; số cảnh báo không được coi là precision xem tay.
- [Báo cáo phần 02](02-report.md): 16 ca, 15 nhóm findings, điều kiện trước/sau và giới hạn.
- [Ma trận 18 mã luật](02-rule-matrix.md): dữ liệu cần, công thức, ngưỡng, skip/fallback.
- [Bằng chứng và lệnh test](evidence/02/test-results.md).

## 3. Nhánh gốc khi mở PR

Phần 02 tiếp nối commit **1c3a761 của phần 01** để dùng bản sửa gate và hợp đồng dữ liệu đã chốt.

- Nếu phần 01 chưa merge: chọn base **`review/01-overview-architecture`** để PR chỉ hiện phần 02.
- Khi phần 01 đã merge: chuyển base sang **`main`**, kiểm lại diff và CI.
- Commit code phần 02: **2e3417d**; tài liệu tách commit. Main chưa được merge bởi lượt làm việc này.

[So sánh riêng phần 02 trên GitHub](https://github.com/AI20K-Build-Phase-Cohort-4A/P-029/compare/review/01-overview-architecture...review/02-core-detectors).

Lấy đúng nhánh, kể cả máy cấu hình remote fetch chỉ một vài nhánh:

```bash
git fetch origin refs/heads/review/02-core-detectors:refs/remotes/origin/review/02-core-detectors
git switch --track origin/review/02-core-detectors
```

Nếu nhánh đã có trên máy thì chuyển sang nhánh đó và pull. Token/dataset/output và Docker/API local chưa theo dõi không nằm trong các commit phần 02.

## 4. Nội dung PR có thể dùng

**Tiêu đề:** `Review phần 02: sửa lỗi core và detector gây rework nhãn 3D`

```markdown
## Mục tiêu
Review core/hình học và các bộ phát hiện; sửa các nguyên nhân báo nhầm, bỏ sót và gợi ý sửa sai cho người gán nhãn.

## Thay đổi và lý do
- Ground/điểm box xoay được lấy đúng để không nhầm điểm xe bên cạnh là đất.
- Kích thước dùng đúng class/subtype; size/jump/heading theo track dùng keyframe thật.
- Hướng trục dùng trung vị modulo 90°, không báo nhầm quanh ranh giới góc.
- Track dùng cùng hệ tọa độ/thời gian; CVAT track chưa outside kéo đến cuối job, kể cả trạng thái occluded.
- Split ID so đúng subtype; finding và box overlap mục tiêu ổn định khi đổi thứ tự input.
- Từ chối dữ liệu/cấu hình không hữu hạn, pose sai; chuẩn hóa quaternion ổn định và kiểm biên cuboid.
- Đính chính dấu quay −90° và ngưỡng floating; báo cáo/ma trận/bằng chứng bàn giao bằng tiếng Việt.

## Kiểm tra
317 pytest đạt, 0 skip; 7 Node đạt. Có 65 ca mới và test CVAT/nuScenes thật. Task thử đã xóa. 1 warning Starlette/httpx của môi trường.

## Dependency và giới hạn
Phụ thuộc phần 01 tại 1c3a761; base PR là review/01-overview-architecture nếu chưa merge, sau đó main.
Giữ ngưỡng mặc định, không thêm dependency. Chưa đo precision xem tay/held-out nhiều vòng hoặc nghiệm thu UI.
Không kèm token, dataset, output hay Docker/API local chưa theo dõi.

## Tài liệu
review/2026-10-10/02-report.md
review/2026-10-10/02-rule-matrix.md
review/2026-10-10/evidence/02/test-results.md
```
