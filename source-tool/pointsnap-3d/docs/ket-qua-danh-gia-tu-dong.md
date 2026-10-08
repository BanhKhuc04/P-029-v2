# Kết quả đánh giá tự động sau A10

Sinh bằng `pointsnap eval` ngày 07/10/2026 trên nuScenes v1.0-mini (10 vòng chèn lỗi mỗi cảnh), cấu hình mặc định
trong `pointsnap/config.yaml`. Tái lập: `pointsnap eval --scenes test` / `--scenes tuning` (`NUSCENES_ROOT` trỏ
tới dữ liệu).

- **Cảnh kiểm tra** (số liệu báo cáo): scene-0103, 0655, 0796, 1077, 1100. **Cảnh tinh chỉnh** (chọn ngưỡng, thống kê
  kích thước): scene-0061, 0553, 0757, 0916, 1094 (`pointsnap/eval/split.py`).
- Quét thẳng nhãn chuẩn trong hệ LiDAR, đã thêm keyframe `outside` như khi nạp lên CVAT.
- Precision ở đây tính mọi finding không khớp lỗi chèn là báo nhầm; T2 xem tay rồi ghi số đã chốt vào `danh-gia.md`.
- Lỗi lơ lửng / lún chỉ kết luận được ở box có đủ điểm mặt đất (~1/4 số box): xem [`kiem-chung-ground.md`](kiem-chung-ground.md).

## So sánh nhanh trên 5 cảnh kiểm tra

| Chỉ số | Trước A10 (bản B3–B7) | Sau A10 | Mục tiêu |
|---|---|---|---|
| Báo nhầm trên nhãn sạch / 100 box | 13,24 Cảnh báo · 11,25 Lỗi | 3,80 Cảnh báo · 0,85 Lỗi | ≤ 2 · ≤ 0,5 |
| Số finding lơ lửng / lún (10 vòng) | 10 472 | 2 142 | |
| Kích thước theo class (×0,6; ×1,5; đổi class) | 96% | 96% | ≥ 90% |
| Nhảy vị trí 2 m / 4 m | 100% / 100% | 92% / 88% | ≥ 90% |
| Tách ID | 100% | 100% | ≥ 80% |
| Khoảng nội suy ≥ 2 keyframe (vật đang chạy) | 0% (chưa có luật) | 100% (6/6) | ≥ 80% |
| Phân mức đúng | 85% | 84% | ≥ 80% |

Trên 5 cảnh tinh chỉnh sau A10: 1,83 Cảnh báo · 0,38 Lỗi / 100 box, nhảy 2 m / 4 m 100% / 100%.
## Kết quả đánh giá PointSnap 3D (test, 10 vòng chèn lỗi)

Cảnh: scene-0103, scene-0655, scene-0796, scene-1077, scene-1100 · 5440 box nhãn chuẩn

### Báo động giả trên nhãn sạch (số mục / 100 box)

| Luật | Mức | Số mục | / 100 box |
|---|---|---|---|
| `floating.no_evidence` | info | 362 | 6.65 |
| `floating` | error | 36 | 0.66 |
| `floating` | warning | 173 | 3.18 |
| `size.class_range` | error | 4 | 0.07 |
| `size.class_range` | warning | 20 | 0.37 |
| `track.jump` | error | 6 | 0.11 |
| `track.jump` | warning | 13 | 0.24 |
| `track.split_id` | warning | 1 | 0.02 |
| **Tổng** | warning | | **3.80** (mục tiêu ≤ 2.0) |
| **Tổng** | error | | **0.85** (mục tiêu ≤ 0.5) |

### Recall trên lỗi chèn giả

Bắt được = báo đúng box / track bằng luật cùng loại, mức Cảnh báo trở lên.

Thuộc phạm vi = class mà luật xét (lơ lửng / lún: class tiếp đất; kích thước trong track: trừ người đi bộ) và, với khoảng nội suy, đối tượng dịch > min_motion_m trong đoạn bị xóa.

| Kiểu lỗi | Mức chèn | Số lỗi | Bắt được | Bắt được (thuộc phạm vi) | Báo ở mức Lỗi | Bắt được (box có đủ điểm mặt đất) |
|---|---|---|---|---|---|---|
| floating | 0.05 | 33 | 9% (3/33) | 11% (3/27) | 0% (0/33) | 50% (3/6) |
| floating | 0.1 | 33 | 0% (0/33) | 0% (0/29) | 0% (0/33) | 0% (0/1) |
| floating | 0.2 | 33 | 9% (3/33) | 10% (3/30) | 0% (0/33) | 75% (3/4) |
| floating | 0.4 | 34 | 26% (9/34) | 31% (9/29) | 26% (9/34) | 100% (9/9) |
| size_class_range | other_class | 16 | 100% (16/16) | 100% (16/16) | 94% (15/16) |  |
| size_class_range | x0.6 | 22 | 100% (22/22) | 100% (22/22) | 82% (18/22) |  |
| size_class_range | x1.5 | 19 | 89% (17/19) | 89% (17/19) | 47% (9/19) |  |
| size_in_track | 0.05 | 11 | 55% (6/11) | 67% (6/9) | 0% (0/11) |  |
| size_in_track | 0.15 | 14 | 86% (12/14) | 100% (12/12) | 0% (0/14) |  |
| size_in_track | 0.3 | 18 | 72% (13/18) | 100% (12/12) | 44% (8/18) |  |
| track_interpolation | 1 | 18 | 0% (0/18) | 0% (0/5) | 0% (0/18) |  |
| track_interpolation | 2 | 15 | 20% (3/15) | 100% (3/3) | 0% (0/15) |  |
| track_interpolation | 3 | 11 | 27% (3/11) | 100% (3/3) | 0% (0/11) |  |
| track_jump | 0.5 | 12 | 17% (2/12) | 17% (2/12) | 0% (0/12) |  |
| track_jump | 1.0 | 10 | 70% (7/10) | 70% (7/10) | 50% (5/10) |  |
| track_jump | 2.0 | 13 | 92% (12/13) | 92% (12/13) | 31% (4/13) |  |
| track_jump | 4.0 | 16 | 88% (14/16) | 88% (14/16) | 88% (14/16) |  |
| track_split_id | - | 21 | 100% (21/21) | 100% (21/21) | 0% (0/21) |  |

**Phân mức đúng** (Z 40 cm, kích thước 30%, nhảy 4 m báo ở mức Lỗi; lỗi thuộc phạm vi, có bằng chứng): 84% (31/37) (mục tiêu ≥ 80%)

### Precision sau khi chèn lỗi

Finding không khớp lỗi chèn nào bị tính là báo nhầm; trong đó có cả lỗi thật của nhãn chuẩn, cần xem tay (việc T2) trước khi chốt.

| Loại | Finding (Cảnh báo+) | Khớp lỗi chèn | Precision |
|---|---|---|---|
| floating | 2142 | 15 | 1% (15/2142) |
| size | 326 | 86 | 26% (86/326) |
| track | 265 | 62 | 23% (62/265) |

### Độ chính xác của số đo (trung vị sai số tuyệt đối)

| Kiểu lỗi | Số mẫu | Sai số |
|---|---|---|
| floating | 15 | 6.10 cm |
| size_in_track | 30 | 25.24 điểm % |
| track_jump | 35 | 0.00 m |

### Hiệu năng

Thời gian quét nhãn sạch (đọc point cloud + 3 bộ phát hiện), mỗi cảnh:

- scene-0103: 1.5 s
- scene-0655: 1.1 s
- scene-0796: 0.4 s
- scene-1077: 0.4 s
- scene-1100: 0.7 s

## Kết quả đánh giá PointSnap 3D (tuning, 10 vòng chèn lỗi)

Cảnh: scene-0061, scene-0553, scene-0757, scene-0916, scene-1094 · 8664 box nhãn chuẩn

### Báo động giả trên nhãn sạch (số mục / 100 box)

| Luật | Mức | Số mục | / 100 box |
|---|---|---|---|
| `floating.no_evidence` | info | 318 | 3.67 |
| `floating` | error | 28 | 0.32 |
| `floating` | warning | 146 | 1.69 |
| `size.class_range` | error | 2 | 0.02 |
| `size.class_range` | warning | 2 | 0.02 |
| `track.jump` | error | 3 | 0.04 |
| `track.jump` | warning | 11 | 0.13 |
| **Tổng** | warning | | **1.83** (mục tiêu ≤ 2.0) |
| **Tổng** | error | | **0.38** (mục tiêu ≤ 0.5) |

### Recall trên lỗi chèn giả

Bắt được = báo đúng box / track bằng luật cùng loại, mức Cảnh báo trở lên.

Thuộc phạm vi = class mà luật xét (lơ lửng / lún: class tiếp đất; kích thước trong track: trừ người đi bộ) và, với khoảng nội suy, đối tượng dịch > min_motion_m trong đoạn bị xóa.

| Kiểu lỗi | Mức chèn | Số lỗi | Bắt được | Bắt được (thuộc phạm vi) | Báo ở mức Lỗi | Bắt được (box có đủ điểm mặt đất) |
|---|---|---|---|---|---|---|
| floating | 0.05 | 37 | 5% (2/37) | 7% (2/27) | 0% (0/37) | 22% (2/9) |
| floating | 0.1 | 38 | 13% (5/38) | 16% (5/31) | 5% (2/38) | 42% (5/12) |
| floating | 0.2 | 39 | 15% (6/39) | 19% (6/31) | 10% (4/39) | 86% (6/7) |
| floating | 0.4 | 39 | 23% (9/39) | 35% (9/26) | 21% (8/39) | 100% (9/9) |
| size_class_range | other_class | 16 | 100% (16/16) | 100% (16/16) | 100% (16/16) |  |
| size_class_range | x0.6 | 24 | 92% (22/24) | 92% (22/24) | 71% (17/24) |  |
| size_class_range | x1.5 | 20 | 100% (20/20) | 100% (20/20) | 65% (13/20) |  |
| size_in_track | 0.05 | 15 | 40% (6/15) | 67% (6/9) | 0% (0/15) |  |
| size_in_track | 0.15 | 19 | 58% (11/19) | 100% (11/11) | 0% (0/19) |  |
| size_in_track | 0.3 | 22 | 77% (17/22) | 100% (17/17) | 64% (14/22) |  |
| track_interpolation | 1 | 20 | 0% (0/20) | 0% (0/5) | 0% (0/20) |  |
| track_interpolation | 2 | 15 | 20% (3/15) | 100% (3/3) | 0% (0/15) |  |
| track_interpolation | 3 | 13 | 31% (4/13) | 100% (4/4) | 0% (0/13) |  |
| track_jump | 0.5 | 14 | 29% (4/14) | 29% (4/14) | 0% (0/14) |  |
| track_jump | 1.0 | 13 | 69% (9/13) | 69% (9/13) | 23% (3/13) |  |
| track_jump | 2.0 | 18 | 100% (18/18) | 100% (18/18) | 83% (15/18) |  |
| track_jump | 4.0 | 22 | 100% (22/22) | 100% (22/22) | 100% (22/22) |  |
| track_split_id | - | 24 | 92% (22/24) | 92% (22/24) | 0% (0/24) |  |

**Phân mức đúng** (Z 40 cm, kích thước 30%, nhảy 4 m báo ở mức Lỗi; lỗi thuộc phạm vi, có bằng chứng): 92% (44/48) (mục tiêu ≥ 80%)

### Precision sau khi chèn lỗi

Finding không khớp lỗi chèn nào bị tính là báo nhầm; trong đó có cả lỗi thật của nhãn chuẩn, cần xem tay (việc T2) trước khi chốt.

| Loại | Finding (Cảnh báo+) | Khớp lỗi chèn | Precision |
|---|---|---|---|
| floating | 1805 | 22 | 1% (22/1805) |
| size | 131 | 93 | 71% (93/131) |
| track | 222 | 82 | 37% (82/222) |

### Độ chính xác của số đo (trung vị sai số tuyệt đối)

| Kiểu lỗi | Số mẫu | Sai số |
|---|---|---|
| floating | 22 | 4.27 cm |
| size_in_track | 34 | 31.17 điểm % |
| track_jump | 53 | 0.00 m |

### Hiệu năng

Thời gian quét nhãn sạch (đọc point cloud + 3 bộ phát hiện), mỗi cảnh:

- scene-0061: 1.6 s
- scene-0553: 0.9 s
- scene-0757: 0.4 s
- scene-0916: 1.4 s
- scene-1094: 1.1 s

## Trước A10 (detectors gốc của Huy)

Cảnh: scene-0103, scene-0655, scene-0796, scene-1077, scene-1100 · 5440 box nhãn chuẩn

### Báo động giả trên nhãn sạch (số mục / 100 box)

| Luật | Mức | Số mục | / 100 box |
|---|---|---|---|
| `floating.no_evidence` | info | 2712 | 49.85 |
| `floating` | error | 477 | 8.77 |
| `floating` | warning | 550 | 10.11 |
| `size.class_range` | error | 133 | 2.44 |
| `size.class_range` | warning | 161 | 2.96 |
| `track.jump` | error | 2 | 0.04 |
| `track.jump` | warning | 8 | 0.15 |
| `track.split_id` | warning | 1 | 0.02 |
| **Tổng** | warning | | **13.24** (mục tiêu ≤ 2.0) |
| **Tổng** | error | | **11.25** (mục tiêu ≤ 0.5) |

### Recall trên lỗi chèn giả

Bắt được = báo đúng box / track bằng luật cùng loại, mức Cảnh báo trở lên.

Thuộc phạm vi = class mà luật xét (lơ lửng / lún: class tiếp đất; kích thước trong track: trừ người đi bộ) và, với khoảng nội suy, đối tượng dịch > min_motion_m trong đoạn bị xóa.

| Kiểu lỗi | Mức chèn | Số lỗi | Bắt được | Bắt được (thuộc phạm vi) | Báo ở mức Lỗi | Bắt được (box có đủ điểm mặt đất) |
|---|---|---|---|---|---|---|
| floating | 0.05 | 33 | 21% (7/33) | 26% (7/27) | 9% (3/33) | 47% (7/15) |
| floating | 0.1 | 33 | 18% (6/33) | 21% (6/29) | 3% (1/33) | 60% (6/10) |
| floating | 0.2 | 33 | 33% (11/33) | 37% (11/30) | 18% (6/33) | 85% (11/13) |
| floating | 0.4 | 34 | 50% (17/34) | 59% (17/29) | 47% (16/34) | 89% (17/19) |
| size_class_range | other_class | 16 | 100% (16/16) | 100% (16/16) | 94% (15/16) |  |
| size_class_range | x0.6 | 22 | 100% (22/22) | 100% (22/22) | 100% (22/22) |  |
| size_class_range | x1.5 | 19 | 89% (17/19) | 89% (17/19) | 89% (17/19) |  |
| size_in_track | 0.05 | 11 | 55% (6/11) | 67% (6/9) | 0% (0/11) |  |
| size_in_track | 0.15 | 14 | 86% (12/14) | 100% (12/12) | 0% (0/14) |  |
| size_in_track | 0.3 | 18 | 94% (17/18) | 100% (12/12) | 61% (11/18) |  |
| track_interpolation | 1 | 18 | 0% (0/18) | 0% (0/5) | 0% (0/18) |  |
| track_interpolation | 2 | 15 | 0% (0/15) | 0% (0/3) | 0% (0/15) |  |
| track_interpolation | 3 | 11 | 0% (0/11) | 0% (0/3) | 0% (0/11) |  |
| track_jump | 0.5 | 12 | 17% (2/12) | 17% (2/12) | 0% (0/12) |  |
| track_jump | 1.0 | 10 | 70% (7/10) | 70% (7/10) | 50% (5/10) |  |
| track_jump | 2.0 | 13 | 100% (13/13) | 100% (13/13) | 62% (8/13) |  |
| track_jump | 4.0 | 16 | 100% (16/16) | 100% (16/16) | 100% (16/16) |  |
| track_split_id | - | 21 | 100% (21/21) | 100% (21/21) | 0% (0/21) |  |

**Phân mức đúng** (Z 40 cm, kích thước 30%, nhảy 4 m báo ở mức Lỗi; lỗi thuộc phạm vi, có bằng chứng): 85% (40/47) (mục tiêu ≥ 80%)

### Precision sau khi chèn lỗi

Finding không khớp lỗi chèn nào bị tính là báo nhầm; trong đó có cả lỗi thật của nhãn chuẩn, cần xem tay (việc T2) trước khi chốt.

| Loại | Finding (Cảnh báo+) | Khớp lỗi chèn | Precision |
|---|---|---|---|
| floating | 10472 | 41 | 0% (41/10472) |
| size | 5096 | 2192 | 43% (2192/5096) |
| track | 175 | 59 | 34% (59/175) |

### Độ chính xác của số đo (trung vị sai số tuyệt đối)

| Kiểu lỗi | Số mẫu | Sai số |
|---|---|---|
| floating | 41 | 7.97 cm |
| size_in_track | 30 | 34.32 điểm % |
| track_jump | 38 | 0.00 m |

### Hiệu năng

Thời gian quét nhãn sạch (đọc point cloud + 3 bộ phát hiện), mỗi cảnh:

- scene-0103: 4.1 s
- scene-0655: 3.7 s
- scene-0796: 1.2 s
- scene-1077: 0.9 s
- scene-1100: 2.6 s
