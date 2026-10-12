# Review07 test — scope corrected, original preserved

Cảnh: scene-0103, scene-0655, scene-0796, scene-1077, scene-1100 · 5440 box nhãn chuẩn

## Báo động giả trên nhãn sạch (số mục / 100 box)

| Luật | Mức | Số mục | / 100 box |
|---|---|---|---|
| `fit.empty` | warning | 1 | 0.02 |
| `fit.loose` | warning | 14 | 0.26 |
| `fit.outside` | error | 1 | 0.02 |
| `fit.outside` | warning | 1 | 0.02 |
| `floating.no_evidence` | info | 387 | 7.11 |
| `floating` | error | 16 | 0.29 |
| `floating` | warning | 136 | 2.50 |
| `heading.points` | error | 5 | 0.09 |
| `heading.points` | warning | 8 | 0.15 |
| `size.class_range` | error | 4 | 0.07 |
| `size.class_range` | warning | 21 | 0.39 |
| `track.jump` | error | 4 | 0.07 |
| `track.jump` | warning | 12 | 0.22 |
| `track.split_id` | warning | 1 | 0.02 |
| **Tổng** | warning | | **3.56** (mục tiêu ≤ 2.0) |
| **Tổng** | error | | **0.55** (mục tiêu ≤ 0.5) |

## Recall trên lỗi chèn giả

Bắt được = báo đúng box / track bằng luật cùng loại, mức Cảnh báo trở lên.

Thuộc phạm vi = class mà luật xét (lơ lửng / lún: class tiếp đất; kích thước trong track: trừ người đi bộ) và, với khoảng nội suy, đối tượng dịch > min_motion_m trong đoạn bị xóa. Sai hướng: xoay đủ lớn để luật lật hướng xét, hoặc box đủ điểm để so với cụm điểm; ngược cả track: vật có lúc chạy nhanh hơn min_speed. Box lệch: box có ít nhất outside_min_points điểm (theo nhãn chuẩn).

| Kiểu lỗi | Mức chèn | Số lỗi | Bắt được | Bắt được (thuộc phạm vi) | Báo ở mức Lỗi | Bắt được (box có đủ điểm mặt đất) |
|---|---|---|---|---|---|---|
| fit_duplicate | - | 8 | 62% (5/8) | 100% (5/5) | 62% (5/8) |  |
| fit_scale | x0.7 | 11 | 9% (1/11) | 25% (1/4) | 0% (0/11) |  |
| fit_scale | x1.3 | 8 | 0% (0/8) | 0% (0/2) | 0% (0/8) |  |
| fit_shift | 0.3 | 9 | 0% (0/9) | 0% (0/4) | 0% (0/9) |  |
| fit_shift | 0.5 | 14 | 14% (2/14) | 20% (1/5) | 7% (1/14) |  |
| fit_shift | 1.0 | 14 | 7% (1/14) | 33% (1/3) | 0% (0/14) |  |
| floating | 0.05 | 19 | 0% (0/19) | 0% (0/16) | 0% (0/19) | 0% (0/1) |
| floating | 0.1 | 22 | 5% (1/22) | 5% (1/21) | 5% (1/22) | 25% (1/4) |
| floating | 0.2 | 20 | 10% (2/20) | 11% (2/19) | 5% (1/20) | 100% (2/2) |
| floating | 0.4 | 21 | 19% (4/21) | 24% (4/17) | 19% (4/21) | 100% (4/4) |
| heading_reverse | 180 | 6 | 33% (2/6) | 100% (2/2) | 33% (2/6) |  |
| heading_rotate | 15 | 14 | 7% (1/14) | — | 0% (0/14) |  |
| heading_rotate | 180 | 14 | 93% (13/14) | 100% (13/13) | 93% (13/14) |  |
| heading_rotate | 30 | 11 | 9% (1/11) | 100% (1/1) | 9% (1/11) |  |
| heading_rotate | 60 | 8 | 88% (7/8) | 100% (7/7) | 25% (2/8) |  |
| heading_rotate | 90 | 8 | 88% (7/8) | 100% (7/7) | 88% (7/8) |  |
| size_class_range | other_class | 14 | 100% (14/14) | 100% (14/14) | 100% (14/14) |  |
| size_class_range | x0.6 | 10 | 100% (10/10) | 100% (10/10) | 90% (9/10) |  |
| size_class_range | x1.5 | 14 | 100% (14/14) | 100% (14/14) | 64% (9/14) |  |
| size_in_track | 0.05 | 9 | 78% (7/9) | 88% (7/8) | 0% (0/9) |  |
| size_in_track | 0.15 | 8 | 100% (8/8) | 100% (8/8) | 0% (0/8) |  |
| size_in_track | 0.3 | 7 | 100% (7/7) | 100% (7/7) | 100% (7/7) |  |
| track_interpolation | 1 | 14 | 0% (0/14) | — | 0% (0/14) |  |
| track_interpolation | 2 | 13 | 62% (8/13) | 100% (8/8) | 0% (0/13) |  |
| track_interpolation | 3 | 10 | 20% (2/10) | 67% (2/3) | 0% (0/10) |  |
| track_jump | 0.5 | 11 | 45% (5/11) | 45% (5/11) | 0% (0/11) |  |
| track_jump | 1.0 | 8 | 50% (4/8) | 50% (4/8) | 25% (2/8) |  |
| track_jump | 2.0 | 8 | 100% (8/8) | 100% (8/8) | 62% (5/8) |  |
| track_jump | 4.0 | 6 | 100% (6/6) | 100% (6/6) | 100% (6/6) |  |
| track_split_id | - | 9 | 89% (8/9) | 89% (8/9) | 0% (0/9) |  |

**Phân mức đúng** (Z 40 cm, kích thước 30%, nhảy 4 m, lật box 180° báo ở mức Lỗi; lỗi thuộc phạm vi, có bằng chứng): 100% (30/30) (mục tiêu ≥ 80%)

## Precision sau khi chèn lỗi

Finding không khớp lỗi chèn nào bị tính là báo nhầm; trong đó có cả lỗi thật của nhãn chuẩn, cần xem tay (việc T2) trước khi chốt. Cột cuối tính cả finding nằm trên box bị chèn lỗi loại khác (vd dời box 1 m: luật box lệch báo đúng box sai dù lỗi chèn thuộc loại nhảy vị trí).

| Loại | Finding (Cảnh báo+) | Khớp lỗi chèn cùng loại | Precision | Trên box bị chèn lỗi bất kỳ |
|---|---|---|---|---|
| floating | 1551 | 7 | 0% (7/1551) | 4% (56/1551) |
| size | 326 | 60 | 18% (60/326) | 25% (81/326) |
| track | 234 | 41 | 18% (41/234) | 27% (64/234) |
| heading | 231 | 67 | 29% (67/231) | 40% (92/231) |
| fit | 272 | 9 | 3% (9/272) | 25% (67/272) |

## Độ chính xác của số đo (trung vị sai số tuyệt đối)

| Kiểu lỗi | Số mẫu | Sai số |
|---|---|---|
| floating | 7 | 4.02 cm |
| size_in_track | 22 | 38.39 điểm % |
| track_jump | 23 | 0.00 m |
| heading_rotate | 27 | 0.06 ° |

## Hiệu năng

Thời gian quét nhãn sạch (đọc point cloud + mọi bộ phát hiện), mỗi cảnh:

- scene-0103: 15.9 s
- scene-0655: 16.8 s
- scene-0796: 7.3 s
- scene-1077: 9.4 s
- scene-1100: 13.6 s
