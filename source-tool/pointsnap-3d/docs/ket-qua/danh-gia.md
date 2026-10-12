# BẢNG CHỈ SỐ ĐÁNH GIÁ (MỤC 8.2)

## 1. Hiệu quả phát hiện (trên lỗi chèn giả)

| Chỉ số | Mục tiêu | Kết quả thực tế | Đánh giá |
|---|---|---|---|
| Recall — floating | ≥ 90% | **92.0%** (242/263) | ĐẠT |
| Recall — size | ≥ 90% | **56.3%** (103/183) | CHƯA ĐẠT |
| Recall — track | ≥ 90% | **0.0%** (0/0) | CHƯA ĐẠT |
| Recall — error | ≥ 90% | **90.7%** (235/259) | ĐẠT |
| Recall — warning | ≥ 80% | **58.8%** (110/187) | CHƯA ĐẠT |
| Precision — floating | ≥ 70% | **17.6%** (TP: 242, FP: 1130) | CHƯA ĐẠT |
| Precision — size | ≥ 70% | **13.5%** (TP: 103, FP: 661) | CHƯA ĐẠT |
| Precision — track | ≥ 70% | **0.0%** (TP: 0, FP: 13) | CHƯA ĐẠT |

## 2. Báo động giả trên nhãn sạch

| Chỉ số | Mục tiêu | Kết quả thực tế | Đánh giá |
|---|---|---|---|
| Báo động giả trên nhãn sạch | ≤ 2 Cảnh báo / 100 box | **33.83** Cảnh báo / 100 box (1853/5478 box) | CHƯA ĐẠT |

## 3. Độ chính xác số đo

| Chỉ số | Mục tiêu | Sai số trung vị | Phân vị 90 (P90) |
|---|---|---|---|
| Sai số đo floating | Trung vị < 3 cm | **25.06 cm** | 584.05 cm |
| Sai số đo size | Trung vị < 3 cm | **475.00 cm** | 515.90 cm |