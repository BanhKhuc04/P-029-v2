# Kết quả đánh giá PointSnap 3D (test, 10 vòng chèn lỗi)

Cảnh: scene-0103, scene-0655, scene-0796, scene-1077, scene-1100 · 5440 box nhãn chuẩn

## Báo động giả trên nhãn sạch (số mục / 100 box)

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

## Recall trên lỗi chèn giả

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

## Precision sau khi chèn lỗi

Finding không khớp lỗi chèn nào bị tính là báo nhầm; trong đó có cả lỗi thật của nhãn chuẩn, cần xem tay (việc T2) trước khi chốt.

| Loại | Finding (Cảnh báo+) | Khớp lỗi chèn | Precision |
|---|---|---|---|
| floating | 2142 | 15 | 1% (15/2142) |
| size | 326 | 86 | 26% (86/326) |
| track | 265 | 62 | 23% (62/265) |

## Độ chính xác của số đo (trung vị sai số tuyệt đối)

| Kiểu lỗi | Số mẫu | Sai số |
|---|---|---|
| floating | 15 | 6.10 cm |
| size_in_track | 30 | 25.24 điểm % |
| track_jump | 35 | 0.00 m |

## Hiệu năng

Thời gian quét nhãn sạch (đọc point cloud + 3 bộ phát hiện), mỗi cảnh:

- scene-0103: 1.5 s
- scene-0655: 1.3 s
- scene-0796: 0.6 s
- scene-1077: 0.5 s
- scene-1100: 0.8 s
