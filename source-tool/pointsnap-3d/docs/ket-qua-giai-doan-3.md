# Kết quả đánh giá giai đoạn 3 (10/10/2026)

`pointsnap eval --scenes test|tuning --rounds 10 --errors all` trên nuScenes v1.0-mini, guideline mặc định. Nhãn chuẩn
được đánh dấu đoạn vắng theo spec 4.4 (`add_track_markers`); lỗi chỉ chèn vào box nhìn thấy (không `occluded`); số box
chỉ tính box nhìn thấy. So sánh với `main` trước giai đoạn 3 (commit `6ed37fe`, cùng 5 cảnh kiểm tra, bộ lỗi 6 loại cũ).

Báo cáo đầy đủ: [kiểm tra](eval-giai-doan-3/kiem-tra.md) · [tinh chỉnh](eval-giai-doan-3/tinh-chinh.md) ·
[`main` trước giai đoạn 3](eval-giai-doan-3/main-truoc-giai-doan-3.md).

## 1. Báo nhầm trên nhãn sạch (số mục / 100 box)

| | Cảnh báo | Lỗi |
|---|---|---|
| Mục tiêu | ≤ 2,0 | ≤ 0,5 |
| `main` trước giai đoạn 3 — 5 cảnh kiểm tra | 3,80 | 0,85 |
| **Giai đoạn 3 — 5 cảnh kiểm tra** (5 440 box) | **3,42** | **0,55** |
| Giai đoạn 3 — 5 cảnh tinh chỉnh (8 664 box) | 1,92 ✅ | 0,35 ✅ |

Theo luật, 5 cảnh kiểm tra (Cảnh báo / Lỗi):

| Luật | `main` | Giai đoạn 3 |
|---|---|---|
| Lơ lửng / lún `floating` | 3,18 / 0,66 | **2,41 / 0,31** (mặt đất v2, box occluded không kiểm) |
| Kích thước `size.*` | 0,37 / 0,07 | 0,39 / 0,07 |
| Đứt track `track.*` | 0,26 / 0,11 | 0,24 / 0,07 |
| Sai hướng `heading.*` (mới) | — | 0,09 / 0,07 (`heading.flip`, `heading.motion`: **0**) |
| Box lệch `fit.*` (mới) | — | 0,30 / 0,02 |

Cảnh báo vẫn vượt mục tiêu, phần lớn do lơ lửng / lún (2,41). Luật mới thêm tổng 0,39 Cảnh báo / 0,09 Lỗi.

## 2. Recall trên lỗi chèn giả — luật mới (5 cảnh kiểm tra, lỗi thuộc phạm vi)

| Lỗi chèn | Bắt được | Báo ở mức Lỗi |
|---|---|---|
| Lật box 180° (một keyframe) | **100%** (13/13) | 93% |
| Xoay 90° | **100%** (7/7) | 88% |
| Xoay 60° | **100%** (7/7) | 25% (Cảnh báo đúng thiết kế: < 75°) |
| Xoay 30° (chỉ luật trục cụm điểm) | 1/1 | — |
| Xoay 15° | 1/14 (dưới ngưỡng 15°) | — |
| Ngược chiều cả track, xe đang chạy | **100%** (2/2; tinh chỉnh 2/4) | 100% |
| Vẽ trùng một vật | **100%** (5/5) | 100% |
| Dời ngang 0,5 / 1,0 m | 20% / 33% (ít mẫu đủ điểm) | — |
| Co ×0,7 / phóng ×1,3 | 25% / 0% | — |

Box dời / co / phóng chỉ thuộc phạm vi khi vật có ≥ 30 điểm; phần lớn box chọn ngẫu nhiên là người, cọc tiêu ít điểm.
Luật box lệch bắt được box lệch rõ trên vật lớn; lệch nhỏ vẫn chủ yếu do `track.jump` và `size.in_track` bắt.

## 3. Recall — loại lỗi cũ (5 cảnh kiểm tra)

| Lỗi chèn | `main` | Giai đoạn 3 |
|---|---|---|
| Nhảy 2 m / 4 m | 92% / 88% | **100% / 100%** |
| Nhảy 1 m | 70% | 50% (8 mẫu) |
| Tách ID | 100% | 89% |
| Kích thước theo class (khác class / ×0,6 / ×1,5) | 100 / 100 / 89% | 100 / 100 / 100% |
| Kích thước trong track 15% / 30% | 100 / 100% | 100 / 100% |
| Lơ lửng / lún 40 cm (box đủ điểm mặt đất) | 100% (9/9) | 100% (4/4) |
| **Phân mức đúng** (lỗi lớn báo ở mức Lỗi) | 84% | **100%** (30/30) |

Mỗi loại lỗi chỉ có 6–20 mẫu mỗi mức nên chênh lệch vài điểm % chưa có ý nghĩa thống kê.

## 4. Hiệu năng

Quét nhãn sạch 5–35 giây / cảnh (trước: 0,5–1,5 giây), do đọc thêm 4 sweep LiDAR và đo điểm từng box. Vẫn dưới mục
tiêu < 2 phút / cảnh. Tắt mặt đất v2 (`floating.sweeps: 0`) thì nhanh hơn khoảng 3 lần.

## 5. Việc còn lại

- Precision xem tay của luật mới (Hân, 20 mục mỗi luật): bộ chèn lỗi không đo được precision thật vì nhãn chuẩn cũng có lỗi.
- Giảm báo nhầm lơ lửng / lún trên cảnh kiểm tra (Huy).
- Tạo lại task CVAT bằng `to-cvat` mới (đoạn vắng thành `occluded`), nếu không `track.reuse_id` báo hàng loạt.
