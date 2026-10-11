# Kết quả đánh giá PointSnap 3D (tuning, 10 vòng chèn lỗi, bộ lỗi all)
> Guideline mặc định sau C5 (ngưỡng lơ lửng / lún 15 cm, sửa tình huống thực tế). Xem [ket-qua-box-verifier.md](../ket-qua-box-verifier.md) và [C5](../giao-viec/C5-tinh-huong-thuc-te.md).

Cảnh: scene-0061, scene-0553, scene-0757, scene-0916, scene-1094 · 8664 box nhãn chuẩn

## Báo động giả trên nhãn sạch (số mục / 100 box)

| Luật | Mức | Số mục | / 100 box |
|---|---|---|---|
| `cam.mismatch` | info | 21 | 0.24 |
| `cam.missing` | info | 61 | 0.70 |
| `fit.empty` | warning | 7 | 0.08 |
| `fit.loose` | error | 1 | 0.01 |
| `fit.loose` | warning | 12 | 0.14 |
| `fit.outside` | error | 2 | 0.02 |
| `fit.outside` | warning | 3 | 0.04 |
| `floating.no_evidence` | info | 350 | 4.04 |
| `floating` | error | 21 | 0.24 |
| `floating` | warning | 68 | 0.79 |
| `heading.points` | warning | 11 | 0.13 |
| `heading.static` | error | 1 | 0.01 |
| `size.class_range` | error | 2 | 0.02 |
| `size.class_range` | warning | 2 | 0.02 |
| `track.jump` | error | 4 | 0.05 |
| `track.jump` | warning | 9 | 0.10 |
| `track.static_shift` | warning | 6 | 0.07 |
| **Tổng** | warning | | **1.36** (mục tiêu ≤ 2.0) |
| **Tổng** | error | | **0.36** (mục tiêu ≤ 0.5) |

## Recall trên lỗi chèn giả

Bắt được = báo đúng box / track bằng luật cùng loại, mức Cảnh báo trở lên.

Thuộc phạm vi = class mà luật xét (lơ lửng / lún: class tiếp đất; kích thước trong track: trừ người đi bộ) và, với khoảng nội suy, đối tượng dịch > min_motion_m trong đoạn bị xóa. Sai hướng: xoay đủ lớn để luật lật hướng xét, hoặc box đủ điểm để so với cụm điểm; ngược cả track: vật có lúc chạy nhanh hơn min_speed. Box lệch: box có ít nhất outside_min_points điểm (theo nhãn chuẩn).

| Kiểu lỗi | Mức chèn | Số lỗi | Bắt được | Bắt được (thuộc phạm vi) | Báo ở mức Lỗi | Bắt được (box có đủ điểm mặt đất) |
|---|---|---|---|---|---|---|
| fit_duplicate | - | 9 | 11% (1/9) | 100% (1/1) | 11% (1/9) |  |
| fit_scale | x0.7 | 13 | 0% (0/13) | 0% (0/1) | 0% (0/13) |  |
| fit_scale | x1.3 | 11 | 0% (0/11) | 0% (0/4) | 0% (0/11) |  |
| fit_shift | 0.3 | 13 | 54% (7/13) | 60% (3/5) | 0% (0/13) |  |
| fit_shift | 0.5 | 17 | 41% (7/17) | 67% (2/3) | 12% (2/17) |  |
| fit_shift | 1.0 | 15 | 40% (6/15) | 33% (1/3) | 20% (3/15) |  |
| floating | 0.05 | 24 | 4% (1/24) | 6% (1/16) | 0% (0/24) | 25% (1/4) |
| floating | 0.1 | 27 | 4% (1/27) | 6% (1/17) | 0% (0/27) | 20% (1/5) |
| floating | 0.2 | 24 | 21% (5/24) | 25% (5/20) | 4% (1/24) | 100% (5/5) |
| floating | 0.4 | 27 | 7% (2/27) | 10% (2/21) | 7% (2/27) | 100% (2/2) |
| heading_reverse | 180 | 8 | 25% (2/8) | 50% (2/4) | 25% (2/8) |  |
| heading_rotate | 15 | 15 | 20% (3/15) | — | 20% (3/15) |  |
| heading_rotate | 180 | 17 | 71% (12/17) | 100% (12/12) | 71% (12/17) |  |
| heading_rotate | 30 | 13 | 54% (7/13) | 67% (2/3) | 54% (7/13) |  |
| heading_rotate | 60 | 11 | 64% (7/11) | 100% (6/6) | 27% (3/11) |  |
| heading_rotate | 90 | 9 | 44% (4/9) | 100% (3/3) | 44% (4/9) |  |
| size_class_range | other_class | 15 | 100% (15/15) | 100% (15/15) | 100% (15/15) |  |
| size_class_range | x0.6 | 13 | 100% (13/13) | 100% (13/13) | 38% (5/13) |  |
| size_class_range | x1.5 | 17 | 88% (15/17) | 88% (15/17) | 47% (8/17) |  |
| size_in_track | 0.05 | 12 | 17% (2/12) | 22% (2/9) | 8% (1/12) |  |
| size_in_track | 0.15 | 10 | 70% (7/10) | 100% (7/7) | 0% (0/10) |  |
| size_in_track | 0.3 | 9 | 67% (6/9) | 100% (6/6) | 33% (3/9) |  |
| track_interpolation | 1 | 17 | 0% (0/17) | 0% (0/5) | 0% (0/17) |  |
| track_interpolation | 2 | 14 | 21% (3/14) | 60% (3/5) | 0% (0/14) |  |
| track_interpolation | 3 | 12 | 33% (4/12) | 100% (4/4) | 0% (0/12) |  |
| track_jump | 0.5 | 13 | 62% (8/13) | 62% (8/13) | 8% (1/13) |  |
| track_jump | 1.0 | 11 | 91% (10/11) | 91% (10/11) | 91% (10/11) |  |
| track_jump | 2.0 | 10 | 100% (10/10) | 100% (10/10) | 90% (9/10) |  |
| track_jump | 4.0 | 9 | 100% (9/9) | 100% (9/9) | 100% (9/9) |  |
| track_split_id | - | 13 | 92% (12/13) | 92% (12/13) | 0% (0/13) |  |

**Phân mức đúng** (Z 40 cm, kích thước 30%, nhảy 4 m, lật box 180° báo ở mức Lỗi; lỗi thuộc phạm vi, có bằng chứng): 90% (26/29) (mục tiêu ≥ 80%)

## Precision sau khi chèn lỗi

Finding không khớp lỗi chèn nào bị tính là báo nhầm; trong đó có cả lỗi thật của nhãn chuẩn, cần xem tay (việc T2) trước khi chốt. Cột cuối tính cả finding nằm trên box bị chèn lỗi loại khác (vd dời box 1 m: luật box lệch báo đúng box sai dù lỗi chèn thuộc loại nhảy vị trí).

| Loại | Finding (Cảnh báo+) | Khớp lỗi chèn cùng loại | Precision | Trên box bị chèn lỗi bất kỳ |
|---|---|---|---|---|
| floating | 897 | 9 | 1% (9/897) | 3% (28/897) |
| size | 106 | 59 | 56% (59/106) | 65% (69/106) |
| track | 295 | 85 | 29% (85/295) | 37% (108/295) |
| heading | 212 | 59 | 28% (59/212) | 36% (76/212) |
| fit | 346 | 7 | 2% (7/346) | 25% (85/346) |

## Độ chính xác của số đo (trung vị sai số tuyệt đối)

| Kiểu lỗi | Số mẫu | Sai số |
|---|---|---|
| floating | 9 | 2.02 cm |
| size_in_track | 15 | 14.44 điểm % |
| track_jump | 33 | 0.00 m |
| heading_rotate | 20 | 0.04 ° |

## Hiệu năng

Thời gian quét nhãn sạch (đọc point cloud + mọi bộ phát hiện), mỗi cảnh:

- scene-0061: 22.9 s
- scene-0553: 10.1 s
- scene-0757: 5.4 s
- scene-0916: 18.2 s
- scene-1094: 13.5 s
