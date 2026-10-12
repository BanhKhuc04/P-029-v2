# BẢNG CHỈ SỐ ĐÁNH GIÁ (MỤC 8.2)

> **Snapshot lịch sử, đối chiếu 11/10/2026:** bảng gốc không ghi ngày chạy, commit, config hash, seed hoặc bằng chứng xem tay. Giữ số liệu để truy vết; chưa dùng để chứng nhận phiên bản hiện hành. Báo cáo mới hơn: [giai đoạn 3 ngày 10/10](ket-qua-giai-doan-3.md). Xem [review phần 01](../../../review/2026-10-10/01-report.md) và bàn giao metadata cho phần 07.

## 1. Hiệu quả phát hiện (trên lỗi chèn giả)

| Chỉ số | Mục tiêu | Kết quả thực tế | Đánh giá |
|---|---|---|---|
| Recall — floating | ≥ 90% | **92.0%** (242/263) | ĐẠT |
| Recall — size | ≥ 90% | **56.3%** (103/183) | CHƯA ĐẠT |
| Recall — track | ≥ 90% | **Không xác định** (0/0, không có mẫu lỗi chèn) | CHƯA ĐỦ DỮ LIỆU |
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
