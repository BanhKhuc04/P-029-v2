# Kết quả đánh giá tự động (B6, B7)

Sinh bằng `pointsnap eval` ngày 06/10/2026 trên nuScenes v1.0-mini, cấu hình mặc định trong `pointsnap/config.yaml`.
Tái lập: `pointsnap eval --scenes test` và `pointsnap eval --scenes tuning` (`NUSCENES_ROOT` trỏ tới dữ liệu).

- **Cảnh kiểm tra** (số liệu báo cáo): scene-0103, 0655, 0796, 1077, 1100. **Cảnh tinh chỉnh** (dùng để chọn ngưỡng,
  thống kê kích thước): scene-0061, 0553, 0757, 0916, 1094 (`pointsnap/eval/split.py`).
- Quét thẳng nhãn chuẩn nuScenes trong hệ LiDAR, đã thêm keyframe `outside` như khi nạp lên CVAT. Chưa đo trên CVAT.
- Precision ở đây tính mọi finding không khớp lỗi chèn là báo nhầm. Việc T2 xem tay các mục đó (nhãn chuẩn cũng có lỗi
  thật) rồi ghi số đã chốt vào `danh-gia.md`.
- Ước lượng mặt đất không đạt tiêu chí tuyệt đối của G1; cách xử lý: [`kiem-chung-ground.md`](kiem-chung-ground.md).
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
| `track.jump` | error | 2 | 0.04 |
| `track.jump` | warning | 6 | 0.11 |
| `track.split_id` | warning | 1 | 0.02 |
| **Tổng** | warning | | **3.68** (mục tiêu ≤ 2.0) |
| **Tổng** | error | | **0.77** (mục tiêu ≤ 0.5) |

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
| track_jump | 2.0 | 13 | 85% (11/13) | 85% (11/13) | 23% (3/13) |  |
| track_jump | 4.0 | 16 | 81% (13/16) | 81% (13/16) | 81% (13/16) |  |
| track_split_id | - | 21 | 100% (21/21) | 100% (21/21) | 0% (0/21) |  |

**Phân mức đúng** (Z 40 cm, kích thước 30%, nhảy 4 m báo ở mức Lỗi; lỗi thuộc phạm vi, có bằng chứng): 81% (30/37) (mục tiêu ≥ 80%)

### Precision sau khi chèn lỗi

Finding không khớp lỗi chèn nào bị tính là báo nhầm; trong đó có cả lỗi thật của nhãn chuẩn, cần xem tay (việc T2) trước khi chốt.

| Loại | Finding (Cảnh báo+) | Khớp lỗi chèn | Precision |
|---|---|---|---|
| floating | 2142 | 15 | 1% (15/2142) |
| size | 326 | 86 | 26% (86/326) |
| track | 156 | 60 | 38% (60/156) |

### Độ chính xác của số đo (trung vị sai số tuyệt đối)

| Kiểu lỗi | Số mẫu | Sai số |
|---|---|---|
| floating | 15 | 6.10 cm |
| size_in_track | 30 | 0.00 điểm % |
| track_jump | 33 | 0.00 m |

### Hiệu năng

Thời gian quét nhãn sạch (đọc point cloud + 3 bộ phát hiện), mỗi cảnh:

- scene-0103: 1.6 s
- scene-0655: 1.2 s
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
| `track.jump` | warning | 3 | 0.04 |
| **Tổng** | warning | | **1.74** (mục tiêu ≤ 2.0) |
| **Tổng** | error | | **0.35** (mục tiêu ≤ 0.5) |

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
| track_jump | 0.5 | 14 | 21% (3/14) | 21% (3/14) | 0% (0/14) |  |
| track_jump | 1.0 | 13 | 62% (8/13) | 62% (8/13) | 8% (1/13) |  |
| track_jump | 2.0 | 18 | 94% (17/18) | 94% (17/18) | 78% (14/18) |  |
| track_jump | 4.0 | 22 | 86% (19/22) | 86% (19/22) | 86% (19/22) |  |
| track_split_id | - | 24 | 92% (22/24) | 92% (22/24) | 0% (0/24) |  |

**Phân mức đúng** (Z 40 cm, kích thước 30%, nhảy 4 m báo ở mức Lỗi; lỗi thuộc phạm vi, có bằng chứng): 85% (41/48) (mục tiêu ≥ 80%)

### Precision sau khi chèn lỗi

Finding không khớp lỗi chèn nào bị tính là báo nhầm; trong đó có cả lỗi thật của nhãn chuẩn, cần xem tay (việc T2) trước khi chốt.

| Loại | Finding (Cảnh báo+) | Khớp lỗi chèn | Precision |
|---|---|---|---|
| floating | 1805 | 22 | 1% (22/1805) |
| size | 131 | 93 | 71% (93/131) |
| track | 109 | 76 | 70% (76/109) |

### Độ chính xác của số đo (trung vị sai số tuyệt đối)

| Kiểu lỗi | Số mẫu | Sai số |
|---|---|---|
| floating | 22 | 4.27 cm |
| size_in_track | 34 | 0.00 điểm % |
| track_jump | 47 | 0.00 m |

### Hiệu năng

Thời gian quét nhãn sạch (đọc point cloud + 3 bộ phát hiện), mỗi cảnh:

- scene-0061: 1.9 s
- scene-0553: 0.8 s
- scene-0757: 0.4 s
- scene-0916: 1.5 s
- scene-1094: 1.1 s
