# Phát hiện sót đối tượng bằng LiDAR (C7, 12/10/2026)

Spec 4.2: *NÊN gán box khi vật xuất hiện rõ trong point cloud*. Trước C7 chỉ có `cam.missing` (ảnh camera thấy vật mà
không có box, mức Thông tin). C7 thêm `lidar.missing` (Cảnh báo) — thuật toán: [detectors/missing.py](../pointsnap/detectors/missing.py).

## Cách làm

1. Mỗi keyframe: bỏ mặt đất (min z lưới 1 m), bỏ điểm trong box nhãn, gom cụm trên lưới 0,25 m (gần cảm biến chỉ nối
   ô kề nhau để người không dính tường; xa hơn 12 m cho hở 1 ô vì điểm thưa).
2. Giữ cụm **giống vật**: kích thước của người / xe hai bánh / xe / xe dài, chân sát đất, mật độ ≥ 1,2 điểm / ô.
3. **Chỗ cũ trống:** cụm mà sau / trước 1 giây chỗ đứng vẫn còn > 40% ô có điểm là vật đứng yên (tường, cây, cột) → bỏ.
4. Nối cụm qua các keyframe (hệ toàn cục, vận tốc không đổi). Chuỗi **di chuyển đều, cùng hướng** ≥ 3 keyframe, dời
   ≥ 3 m (cỡ người: ≥ 1,5 m qua ≥ 4 keyframe) → `lidar.missing`, kèm tâm cụm từng frame và kích thước để vẽ box.

Vật đứng yên không gán không báo: nuScenes (và spec) không gán mọi vật đứng yên (cột, thùng rác, bụi cây), phân biệt
cần ảnh camera — để sau.

## Quá trình chỉnh (chỉ trên 5 cảnh tinh chỉnh)

Đo bằng cách **xoá hẳn box** của một vật đang di chuyển (≥ 3 keyframe đủ 15 điểm, dời ≥ 3 m; 12 vật / cảnh) rồi xem luật
có tìm lại không; báo nhầm = mục trên nhãn sạch.

| Bước | Báo nhầm (5 cảnh) | Tìm lại |
|---|---|---|
| Lọc theo kích thước + nối cụm | 11 | 38% |
| Siết gom cụm (chỉ ô kề) | 40 (tường vỡ thành mảnh "giống vật") | 40% |
| + phép thử **chỗ cũ trống** | **1** | 36% |
| + so cách 1 giây, nới hình dạng xe nhìn ngang, nối hở 1 ô khi xa, cho xe dài | 6 | 64% |
| + dời ≥ 3 m, ngưỡng riêng cho người, loại cụm ngắn mà cao | **1** | **66%** |

Mật độ điểm / ô (chống nhiễu mưa, bụi) chọn bằng mô phỏng: giá trị thấp nhất mà mưa 10 000 điểm / frame không gây báo
nhầm là 1,2 (1,1 còn 1 mục). Trên cảnh tinh chỉnh 1,2 và 1,4 cho kết quả như nhau.

## Kết quả

| | 5 cảnh tinh chỉnh | 5 cảnh kiểm tra |
|---|---|---|
| Tìm lại vật bị xoá box | **66%** (31 / 47) | **71%** (36 / 51) |
| — ô tô | 14 / 18 | 28 / 37 |
| — người đi bộ | 8 / 15 | 4 / 8 |
| — xe buýt, xe tải | 6 / 11 | 2 / 2 |
| — xe hai bánh | 3 / 3 | 2 / 4 |
| Báo nhầm trên nhãn sạch | 1 mục | 1 mục |
| Thời gian | ~2 giây / cảnh 40 keyframe | |

Trong `pointsnap eval --rounds 10 --errors all` (tính cả `lidar.missing` vào báo nhầm trên nhãn sạch): kiểm tra
2,83 → 2,85, tinh chỉnh 1,36 → 1,38 Cảnh báo / 100 box; recall và phân mức của mọi lỗi chèn khác không đổi.

Còn sót: người đi chậm / đứng lẫn trong nhóm, xe ở xa (> 30 m, điểm thưa), xe buýt chỉ thấy một phần.

Test: `tests/test_missing.py` (xe / người không gán được tìm thấy; nhãn sạch, xe đỗ không gán, xe thu chạy qua vật đứng
yên, mưa dày đều không báo).
