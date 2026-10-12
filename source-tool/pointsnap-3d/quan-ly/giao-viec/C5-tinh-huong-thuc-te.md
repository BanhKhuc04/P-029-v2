# C5 — Tình huống giao thông thực tế: đối chiếu và sửa

Mỗi tình huống được tái hiện bằng **bộ mô phỏng cảnh** `tests/scenario_sim.py` (LiDAR giả: mặt đất, bóng che sau vật,
điểm trên mặt box nhìn thấy, mật độ ∝ 1/r², nhiễu) rồi quét bằng toàn bộ luật như quét thật. Mỗi tình huống có bản
**nhãn đúng** (không được báo Cảnh báo / Lỗi) và, khi có, bản **nhãn sai** (phải báo). Test: `tests/test_scenarios.py`.

## Kết quả đối chiếu (trước khi sửa)

| # | Tình huống | Kết quả | Ghi chú |
|---|---|---|---|
| S0 | Cảnh cơ bản: xe chạy, xe đỗ, người đi bộ | ✅ sạch | kiểm tra bộ mô phỏng |
| S1a | Xe máy chở hàng cồng kềnh, box không gồm hàng | ✅ | hàng tách khỏi xe > 30 cm thì không tính là điểm của vật |
| S1b | Xe máy chở hàng, box **gồm** hàng (rộng 1,6 m) | ❌ **Lỗi** `size.class_range` | sửa F3 |
| S2 | 8 xe máy đỗ san sát 0,75 m | ✅ | |
| S3 | Xe dừng đèn đỏ rồi chạy (phanh 3 m/s²) | ✅ | phanh gấp phi thực tế (16 m/s²) mới báo nhảy |
| S4a | Xe **lùi** thật 2,5 m/s | ❌ **Lỗi** `heading.motion` ở cả 12 frame | sửa F2 |
| S4b | Xe quay đầu chữ U bán kính 6 m | ✅ | |
| S5 | Đầu kéo + rơ-moóc; xe buýt 18 m | ✅ | |
| S6 | Người dắt xe đạp sát nhau | ✅ | cặp được phép chồng |
| S7 | Người cầm ô (box gồm / không gồm ô); vác cây 3 m không box riêng | ✅ không báo | vác vật dài > 2 m không box riêng (spec 4.3B) chưa bắt: để sau |
| S8 | Cọc tiêu: hướng box đổi tuỳ ý mỗi frame | ❌ **Lỗi** `heading.static` | sửa F1 |
| S9 | 2 xe máy song song bị gán **đổi ID** từ một frame | ❌ **bỏ sót** | sửa F4 |
| S10 | Mưa / bụi: 3 000 điểm nhiễu lơ lửng mỗi frame | ✅ | |
| S11 | Ban đêm, ngược sáng (ảnh camera) | ✅ theo thiết kế | lớp 2 bỏ frame có trung vị độ sáng < 90 |
| S12 | Che 8 frame: không đánh occluded / đánh occluded | ✅ báo đúng spec | `fit.empty`, `track.occluded_long` |
| S13 | Xe xa 42 m, ít điểm | ✅ | |
| S14 | Cầu vượt / hầm, dốc, đá, vỉa hè | → [C4](C4-mat-dat-nghieng.md) | |

## Sửa

| Mã | Sửa | Giữ được |
|---|---|---|
| F1 | `static.yaw_excluded_classes` thêm vật tròn / đối xứng (`traffic_cone`; spec-vn `Obstacle/traffic cone`, `sack`, `trash_bag`, `brick`) — hướng box không có nghĩa | rào chắn (`barrier`) vẫn xét |
| F2 | `heading.motion`: box ngược chiều ≥ 80% đoạn khi vật chạy chậm (≤ `reverse_max_mps`, mặc định 3 m/s xe 4 bánh) → **một** Cảnh báo "có thể đang lùi" cho cả đoạn thay vì Lỗi từng frame | xe chạy nhanh mà box ngược vẫn Lỗi |
| F3 | `size.class_range` "lớn bất thường" với class hay chở hàng (`size.cargo_classes`: xe máy, xe đạp, Two-wheels, xe ba gác): điểm LiDAR của vật **phủ kín** chiều bị vượt (chạm hai đầu trong 7,5%, ≥ 80% đoạn có điểm) → Cảnh báo "có thể chở hàng" thay vì Lỗi | box phóng to vẫn Lỗi. Thử cho mọi class thì người cạnh cột, ô tô cạnh bụi cây bị phóng to cũng "phủ kín" (lẫn điểm vật bên cạnh) → thu hẹp về xe chở hàng |
| F4 | Luật mới `track.id_swap`: hai track cùng nhóm, cùng lúc, mỗi track "nhảy" sang đúng quỹ đạo dự đoán của track kia → nghi đổi nhầm ID | báo nhầm trên nhãn sạch nuScenes ≈ 0 |

**Đo:** `pointsnap eval --scenes tuning|test --rounds 10 --errors all` không tăng báo nhầm, không giảm recall; test mô
phỏng đúng hết bảng trên.

## Kết quả sau khi sửa

- **Mô phỏng:** 23 / 23 tình huống đúng (`tests/test_scenarios.py`, 4 giây).
- **`track.id_swap` trên quỹ đạo thật nuScenes** (đổi ID hai vật cùng nhóm đang cách nhau ≤ 3 m, từ giữa đoạn chung):
  bắt **94%** cặp ở cả cảnh tinh chỉnh (332 / 354) và kiểm tra (128 / 136); **0** báo nhầm trên nhãn sạch 10 cảnh.
- **`pointsnap eval --rounds 10 --errors all`, 5 cảnh kiểm tra:** báo nhầm trên nhãn sạch **không đổi** (2,83 / 0,57);
  phân mức đúng 100%. Thay đổi duy nhất: 3 lỗi chèn "xoay box" rơi vào **cọc tiêu** không còn bị báo — đúng thiết kế
  F1 (xoay box cọc tiêu không phải lỗi), làm recall xoay 15° / 30° giảm từ 29% / 27% xuống 14% / 18% trên bảng chung.
- **5 cảnh tinh chỉnh:** báo nhầm **không đổi** (1,36 / 0,36), phân mức đúng 90% như trước; chỉ 4 lỗi chèn "xoay box" trên cọc tiêu không còn bị báo (cùng lý do).

Chưa làm: người vác vật dài > 2 m không có box riêng (spec 4.3B) — tool chưa bắt.
