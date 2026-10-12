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

## 4. Mặt đất không phẳng (C4, 12/10)

Spec 4.2: đáy box đặt trên **mặt tiếp xúc**. Box 7-DoF không có pitch / roll nên trên dốc, box đúng spec chạm mặt đất ở
góc thấp nhất; trung vị độ cao vành đai (≈ mặt đất ở tâm box) cao hơn điểm đó tan(dốc) × nửa chiều dài box (dốc 6°, xe
4,5 m: 24 cm), nên box lẻ bị báo lún nhầm.

**Test tổng hợp** `tests/test_ground_slope.py` (15 ca, box đặt đúng spec, ghi kết quả mong muốn):

| Ca | Code trước C4 | Sau C4 |
|---|---|---|
| Box lẻ trên dốc dọc / ngang 0 – 10° (8 ca) | sai 3 (dọc 6°, 10°; ngang 10°: báo lún) | đúng |
| Box lẻ lơ lửng / lún 25 cm trên dốc 6° | báo, nhưng đo lệch ~24 cm | đúng, đo đúng ±7 cm |
| Track trên dốc 8°, một frame lơ lửng 25 cm | đúng | đúng |
| Đá 15 cm trong vành đai | đúng | đúng |
| Người đứng sát mép vỉa hè 15 cm | đúng | đúng |
| Dốc ngang 6°, chỉ thấy điểm phía trên dốc | sai (báo lún) | đúng |
| Track từ đường bằng lên dốc 8° | sai (báo các frame trên dốc) | **vẫn sai** (xfail, xem dưới) |

**Cách làm:** khớp mặt phẳng bền (RANSAC, ngưỡng 6 cm) trên điểm mặt đất của vành đai (dải độ cao ±1,2 m quanh đáy box,
lọc lưới min-Z); dùng được khi ≥ 60% điểm nằm trên mặt phẳng (bậc vỉa hè / nhiều tầng thì không), điểm trải ≥ 0,5 m theo
cả hai trục box và dốc ≥ 5°. Khi đó `contact_distance` = đáy box − điểm thấp nhất của mặt phẳng dưới 4 góc đáy.
**Chỉ box không có track để so** (so `|d|` tuyệt đối) dùng `contact_distance`; box thuộc track giữ trung vị.

**Vì sao không dùng mặt phẳng cho mọi box:** trên nuScenes mini (đường gần như bằng), mặt phẳng khớp trên vành đai hẹp
rất nhiễu — điểm quanh box xa chỉ nằm trên vài vạch quét: độ dốc khớp được trung vị 3°, p90 7° (gộp 4 sweep: 3,1° / 6,4°).
So trên nhãn chuẩn 5 cảnh tinh chỉnh (báo nhầm Cảnh báo / Lỗi trên 100 box; bắt nâng / hạ box 10 / 20 / 40 cm):

| Cách đo mặt đất | Báo nhầm | Bắt 10 / 20 / 40 cm |
|---|---|---|
| Trung vị (cũ) | 1,41 / 0,24 | 31 / 90 / 99% |
| Mặt phẳng cho mọi box, dốc ≥ 2° | 1,44 / 0,55 | 33 / 88 / 99% |
| Mặt phẳng cho mọi box, dốc ≥ 6° | 1,30 / 0,31 | 31 / 90 / 99% |
| Mặt phẳng cho mọi box, dốc ≥ 10° | 1,42 / 0,24 | 31 / 89 / 99% |
| Mặt phẳng vành đai rộng 1,5 m, dốc ≥ 6° | 1,78 / 0,48 | 33 / 87 / 99% |
| **Chọn: mặt phẳng chỉ cho box không có track, dốc ≥ 5°** | **1,41 / 0,24** | **31 / 90 / 99%** |

5 cảnh kiểm tra (chạy một lần, không chỉnh theo): báo nhầm 2,41 / 0,31 → 2,39 / **0,37** (thêm ~3 mục Lỗi trên 5 440 box,
đều là box không có track để so đứng trên vành đai khớp ra "dốc" ≥ 5°); bắt 10 / 20 / 40 cm 38 / 82 / 99% → 38 / 83 / 99%.
Thời gian luật lơ lửng / lún trên scene-0061: 21,9 → 22,5 s.

**Chưa làm:**
- Track đi từ đường bằng lên dốc: box thuộc track so trung vị độ cao với các frame khác, độ lệch tan(dốc) × nửa chiều dài
  xuất hiện ở các frame trên dốc. Cần mặt phẳng chắc hơn (ví dụ bản đồ mặt đất gộp nhiều keyframe trong hệ toàn cục —
  nuScenes không có pitch trong pose nên chưa làm được) hoặc dữ liệu có dốc thật để chỉnh.
- Vật kê dưới bánh: đá nằm dưới xe, ngoài vành đai; cần dùng điểm của chính vật (bánh xe) để biết box chạm đâu.

Script thí nghiệm: `scripts/verify_ground.py` (RANSAC ban đầu). Số liệu bảng 2 sinh từ phép dịch đáy box như mô tả,
tái lập được bằng `pointsnap eval` (mục lơ lửng / lún).
