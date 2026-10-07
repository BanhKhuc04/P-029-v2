# Kiểm chứng ước lượng mặt đất (B2 / cổng G1)

Ngày 06/10/2026, trên nuScenes v1.0-mini (10 cảnh), nhãn chuẩn, các class tiếp đất (`floating.classes`).
`d = z_đáy_box − z_mặt_đất`; nhãn chuẩn đúng thì `d ≈ 0`.

## 1. Kết quả theo tiêu chí ban đầu (|d| tuyệt đối)

Tiêu chí G1 trong đề xuất: trung vị |d| < 5 cm, 90% box < 10 cm.

| Cách đo | Box đo được | Trung vị \|d\| | p90 \|d\| | Đạt G1 |
|---|---|---|---|---|
| RANSAC, vành đai 0,5–1,5 m (`estimate_ground_for_box`, `scripts/verify_ground.py`), box ≤ 35 m | 64% / 8270 | 8,5 cm | 33,3 cm | Không |
| Như trên, bỏ điểm thuộc box khác | 59% | 8,1 cm | 26,9 cm | Không |
| Trung vị điểm thấp, vành đai 0,1–0,8 m, bỏ điểm box khác (`ring_ground_for_box`), box ≤ 40 m | 42% / 9075 | 7,9 cm | 22,2 cm | Không |
| Điểm thấp nhất của chính đối tượng trong footprint | 60% | 9,5 cm | 33 cm | Không |

**Kết luận:** không cách đo nào đạt tiêu chí tuyệt đối. Nguyên nhân: LiDAR 32 tia thưa, bờ vỉa và dốc quanh box,
và chính đáy box chuẩn của nuScenes cũng không sát mặt đất tới mức vài cm. Không kiểm được nhãn chuẩn bằng hệ toàn
cục vì `ego_pose` của nuScenes luôn có z = 0.

## 2. Đổi cách đo: so với chính track

Phần lệch ở trên ổn định trong một track (cùng xe, cùng đoạn đường), nên luật B3 so `d` của một box với **trung vị
`d` của các box khác cùng track**. Với cách đo vành đai 0,1–0,8 m:

| | Trung vị | p90 | p99 |
|---|---|---|---|
| \|d − trung vị track\| trên nhãn sạch | 3,4 cm | 14,7 cm | 34 cm |

Thử dịch đáy box chuẩn ±5, 10, 20, 40 cm rồi đo lại (box có ≥ 15 điểm mặt đất, 10 cảnh, 11 531 box tiếp đất):

| Luật | Báo nhầm / 100 box (Cảnh báo, Lỗi) | Bắt được 20 cm | Báo Lỗi ở 40 cm | Box có bằng chứng |
|---|---|---|---|---|
| \|d\| > 10 / 20 cm (ban đầu) | 7,4 · 3,6 | 83% | 94% | 30% |
| Lệch so với track > 10 / 20 cm, Lỗi khi \|d\| > 15 cm; box lẻ \|d\| > 15 / 30 cm | 3,9 · 0,7 | 90% | 94% | 24% |

Việc B7 chạy `pointsnap eval` trên 5 cảnh tinh chỉnh và nâng ngưỡng lệch so với track lên **12 / 22 cm**: báo nhầm
giảm từ 2,5 · 0,40 xuống 1,7 · 0,35 / 100 box (mọi class), độ bắt lỗi 20 / 40 cm trên box có bằng chứng không đổi
(86% / 100%). Tham số đang dùng nằm ở mục `floating` của `pointsnap/config.yaml`; số liệu trên cảnh kiểm tra:
[`ket-qua-danh-gia-tu-dong.md`](ket-qua-danh-gia-tu-dong.md).

## 3. Hạn chế

- Chỉ khoảng **1/4 số box tiếp đất** có đủ điểm mặt đất sát box (≥ 15 điểm trong vành đai 0,1–0,8 m). Box còn lại
  được ghi "thiếu bằng chứng" (mức Thông tin, mỗi track một mục), annotator tự kiểm.
- Box lơ lửng / lún **cả track** (annotator vẽ lệch đều mọi frame) chỉ bị bắt bằng luật box lẻ khi track có ít box đo
  được; track dài lệch đều sẽ lọt. Đây là đánh đổi để giảm báo nhầm.
- Cách đo được chọn bằng thí nghiệm trên cả 10 cảnh trước khi chia tinh chỉnh / kiểm tra; số liệu chính thức lấy từ
  `pointsnap eval` trên 5 cảnh kiểm tra.

Script thí nghiệm: `scripts/verify_ground.py` (RANSAC ban đầu). Số liệu bảng 2 sinh từ phép dịch đáy box như mô tả,
tái lập được bằng `pointsnap eval` (mục lơ lửng / lún).
