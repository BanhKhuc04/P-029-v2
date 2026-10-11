# Kết quả Box Verifier (C3, 10/10/2026)

Box Verifier thêm 4 lớp kiểm box ngoài các luật C1 / C2 (thiết kế: [đề xuất 4.1 f](../de-xuat-de-tai.md)). Đo bằng
`pointsnap eval --scenes test|tuning --rounds 10 --errors all` trên nuScenes v1.0-mini, guideline mặc định, cùng cách
đo với [giai đoạn 3](ket-qua-giai-doan-3.md) (so với kết quả PR #37 đã merge). Máy đo: RTX 3050 Laptop 4 GB, PyTorch
2.6 CUDA 12.4, nên lớp 2 (ảnh camera) chạy.

Báo cáo đầy đủ: [kiểm tra](eval-box-verifier/kiem-tra.md) · [tinh chỉnh](eval-box-verifier/tinh-chinh.md) ·
[tinh chỉnh, tắt ảnh camera](eval-box-verifier/tinh-chinh-tat-anh.md) ·
[tinh chỉnh, `cam.mismatch` mức Cảnh báo](eval-box-verifier/tinh-chinh-cam-canh-bao.md).

## 1. Kết quả chính (5 cảnh kiểm tra, 5 440 box)

Bắt được = báo đúng box bị chèn lỗi bằng luật cùng loại, mức Cảnh báo trở lên, tính trên **mọi** lỗi chèn.

| Lỗi chèn | Số lỗi | PR #37 | **Box Verifier** |
|---|---|---|---|
| Dời box ngang 0,3 m | 9 | 0% | **44%** |
| Dời box ngang 0,5 m | 14 | 14% | **36%** |
| Dời box ngang 1,0 m | 14 | 7% | **29%** |
| Xoay box 15° | 14 | 7% | **29%** |
| Xoay box 30° | 11 | 9% | **27%** |
| Xoay box 90° | 8 | 88% | **100%** |
| Nhảy vị trí 0,5 m | 11 | 45% | **55%** |
| Nhảy vị trí 1,0 m | 8 | 50% | **75%** |
| Co / phóng box x0,7 · x1,3 | 11 · 8 | 9% · 0% | 9% · 0% (chưa cải thiện) |
| Các lỗi khác (lơ lửng, kích thước, tách ID, lật 180°, vẽ trùng…) | | | không đổi |

Phân mức đúng 100% (30/30) như trước.

| Báo nhầm trên nhãn sạch / 100 box | Cảnh báo | Lỗi |
|---|---|---|
| Mục tiêu | ≤ 2,0 | ≤ 0,5 |
| PR #37 — 5 cảnh kiểm tra | 3,42 | 0,55 |
| **Box Verifier — 5 cảnh kiểm tra** | **3,67** | **0,57** |
| PR #37 — 5 cảnh tinh chỉnh | 1,92 | 0,35 |
| **Box Verifier — 5 cảnh tinh chỉnh** | **1,99** ✅ | **0,36** ✅ |

Luật mới thêm 0,26 Cảnh báo / 0,02 Lỗi trên 100 box ở cảnh kiểm tra (`track.static_shift` 0,15, `heading.static`
0,11 / 0,02). Cảnh báo vẫn vượt mục tiêu chủ yếu do lơ lửng / lún (2,41), không đổi so với PR #37.

Số lỗi mỗi mức chỉ 8 – 14 nên mỗi lỗi bắt thêm / sót là 7 – 12 điểm %; xu hướng giống nhau ở cả hai bộ cảnh.

## 2. Mỗi lớp đóng góp bao nhiêu (5 cảnh tinh chỉnh)

| Lỗi chèn | PR #37 | + lớp 1 (tắt ảnh) | + lớp 2, `cam.mismatch` mức Cảnh báo |
|---|---|---|---|
| Dời 0,3 / 0,5 / 1,0 m | 8% / 12% / 20% | 54% / 41% / 40% | 54% / 47% / 47% |
| Xoay 15° / 30° | 0% / 8% | 33% / 62% | 33% / 62% |
| Nhảy 0,5 m | 38% | 62% | 77% |
| Báo nhầm Cảnh báo / 100 box | 1,92 | 1,99 | 2,23 |

**Lớp 1 — hình học theo thời gian** tạo gần hết phần cải thiện. Trong hệ toàn cục, vật đứng yên (xe đỗ, cột, rào) có
các keyframe khác tụ trong 10 cm, nên một keyframe dịch 0,3 m hay xoay 15° lộ rõ, điều mà luật theo điểm LiDAR không
thấy được. Giới hạn: chỉ áp dụng cho vật đứng yên. Box dời / co của xe **đang chạy** vẫn khó bắt.

**Lớp 2 — ảnh camera** chỉ bắt thêm 4 / 400 lỗi chèn so với lớp 1 (2 dời box, 2 nhảy vị trí), mà tăng báo nhầm 0,24
(tinh chỉnh) / 0,75 (kiểm tra) Cảnh báo trên 100 box. Vì vậy `cam.mismatch` **mặc định ở mức Thông tin**: hiện như bằng
chứng phụ cho người duyệt, không tính vào báo nhầm, không chặn `gate`. Nhóm có thể đổi
`camera.mismatch_severity: warning` nếu dữ liệu thật cho kết quả tốt hơn.

## 3. Lớp 2 — đã thử gì trên ảnh camera

Mọi phép thử chỉ trên 5 cảnh tinh chỉnh (9 356 box, 2 869 lần nhìn thấy rõ trên ảnh), không chỉnh theo cảnh kiểm tra.
Cùng mức báo nhầm ~1 / 100 box, tỉ lệ bắt (trên box nhìn thấy được):

| Tín hiệu so với trung vị các frame khác của track | Dời 0,5 m | Co x0,7 | Nhảy 1 m |
|---|---|---|---|
| IoU khung chiếu – khung vật trên ảnh | 14% | 2% | 23% |
| Độ lệch từng cạnh khung | 5% | 3% | 15% |
| **Phần mặt nạ vật nằm ngoài khung chiếu 8 góc box** (chọn) | **33%** | **32%** | **33%** |

- Model 2D sót vật (xa, mờ, bị che) làm IoU = 0: lúc đầu báo nhầm 4,86 / 100 box. Đã bỏ: chỉ xét khi model 2D thấy
  vật chồng lên khung chiếu.
- Frame ban đêm: Mask R-CNN COCO kém tin cậy (scene-1094 chiếm 31 / 52 mục báo nhầm). Bỏ frame có **trung vị độ sáng
  6 ảnh** < 90 / 255 (frame ngày 100 – 114, đêm 20 – 88). Xét từng ảnh thì không tách được vì ảnh đêm hướng về đèn
  đường vẫn sáng tới 112.
- Xe đạp / xe máy có người ngồi bị ảnh nhận là người: `cam.class` không tính cặp người ↔ xe hai bánh. Sau đó
  `cam.class` không báo nhầm trên cả 10 cảnh.
- `cam.missing` (ảnh thấy vật, có ≥ 15 điểm LiDAR, không có box 3D): 0,65 / 100 box (tinh chỉnh), 2,44 (kiểm tra), mức
  Thông tin. Chưa xem tay là sót thật hay ảnh nhận nhầm (việc của Hân).

Nhận xét: tín hiệu ảnh 2D thô (một model COCO, khung chiếu 8 góc) có ích như bằng chứng thứ hai nhưng chưa đủ chắc để
tự đứng. Hướng tốt hơn là đưa đặc trưng ảnh vào Box Critic (lớp 3) để model tự học cách kết hợp với điểm LiDAR.

### 3.1. Thử model ảnh theo từ khóa: Grounding DINO + SAM 2.1 (11/10)

`camera.model: gdino-sam2`: Grounding DINO base (tìm vật theo từ khóa, có cọc tiêu / rào chắn) + SAM 2.1 small (mặt nạ từ
khung), thay Mask R-CNN COCO. Không model nào huấn luyện trên nuScenes. Chạy 0,8 s / ảnh trên RTX 3050 4 GB (2,9 GB
VRAM), ~32 phút cho 2 424 ảnh của nuScenes mini; bộ đệm như cũ.

Đo bằng `scripts/eval_camera.py`: làm lệch **từng** box mà luật ảnh đo được (box nhìn thấy, frame ban ngày, model ảnh thấy
vật, track có ≥ 2 lần đo khác), mỗi kiểu lỗi một lần, xem `cam.mismatch` (tính như Cảnh báo) có báo đúng frame không.
"Phủ" = box trong phạm vi / box nhìn thấy. Ngưỡng của Grounding DINO (thang điểm thấp hơn Mask R-CNN: vật rõ 0,4 – 0,7)
chọn trên 5 cảnh tinh chỉnh, cùng mức báo nhầm với Mask R-CNN: `min_score` 0,3, `mask_rise_warning` 0,25,
`class_min_score` 0,6 (`cam.class` không báo nhầm), `missing_min_score` 0,6.

| | Tinh chỉnh: Mask R-CNN | Tinh chỉnh: GDINO + SAM 2.1 | **Kiểm tra: Mask R-CNN** | **Kiểm tra: GDINO + SAM 2.1** |
|---|---|---|---|---|
| Phủ | 18% (1 594 / 8 664) | 22% (1 888) | 25% (1 361 / 5 440) | 25% (1 382) |
| Bắt dời ngang 0,5 m | 20% | 22% | **22%** | 18% |
| Bắt nhảy 1 m | 25% | 24% | **27%** | 23% |
| Bắt co x0,7 | 60% | 49% | **69%** | 59% |
| Bắt phóng x1,3 | 1% | 1% | 2% | 2% |
| `cam.mismatch` báo nhầm / 100 box | 0,24 | 0,21 | 0,75 | **0,64** |
| `cam.missing` (Thông tin) / 100 box | 0,70 | 0,30 | 2,44 | **0,09** |

Box đối chiếu được theo nhóm vật:

| Nhóm | Tinh chỉnh: Mask R-CNN → GDINO | Kiểm tra: Mask R-CNN → GDINO |
|---|---|---|
| Cọc tiêu | 0 → **353** / 578 | 0 → **164** / 225 |
| Rào chắn | 0 → 35 / 1 637 | 0 → 0 / 133 |
| Người | 747 → 695 / 2 824 | **468** → 342 / 1 461 |
| Xe | 781 → 779 / 3 179 | 951 → 938 / 3 471 |
| Xe hai bánh | 120 → 115 / 446 | 23 → 26 / 150 |

Trên cảnh kiểm tra GDINO + SAM 2.1 bắt box lệch kém hơn (nhận người kém hơn), bù lại là cọc tiêu (Mask R-CNN không có) và
ít mục `cam.missing` hơn hẳn. Không chỉnh lại ngưỡng theo cảnh kiểm tra. Rào chắn bê tông của nuScenes model theo từ khóa
gần như không nhận ra.

**`camera.model: hybrid`** ghép hai model: Mask R-CNN cho người / xe như cũ, Grounding DINO + SAM 2.1 **chỉ** cho nhóm COCO
không có (cọc tiêu, rào chắn); dùng chung ngưỡng của Mask R-CNN. Trên cảnh tinh chỉnh, cộng thêm điểm cho vật của Grounding
DINO (0,1 / 0,2) chỉ phủ thêm 1 – 2% box mà bắt đầu báo nhầm `cam.class`, nên không cộng.

| | Tinh chỉnh: Mask R-CNN | Tinh chỉnh: hybrid | **Kiểm tra: Mask R-CNN** | **Kiểm tra: hybrid** |
|---|---|---|---|---|
| Phủ | 18% (1 594) | 21% (1 857) | 25% (1 361) | **28% (1 499)** |
| Bắt dời ngang 0,5 m | 20% | 25% | 22% | **24%** |
| Bắt nhảy 1 m | 25% | 25% | 27% | 25% |
| Bắt co x0,7 | 60% | 64% | 69% | **71%** |
| `cam.mismatch` báo nhầm / 100 box | 0,24 | 0,24 | 0,75 | 0,77 |
| `cam.class` / `cam.missing` | 0 / 0,70 | 0 / 0,70 | 0 / 2,44 | 0 / 2,44 |

Tính trên mọi box nhìn thấy (phủ × bắt được), trên cảnh kiểm tra hybrid bắt thêm ~20% box dời và ~13% box co ở gần như
cùng mức báo nhầm; nhảy 1 m ngang nhau.

Kết luận: **mặc định vẫn là `maskrcnn`** (không cần thêm thư viện, lần quét đầu nhanh hơn ~4 lần); máy có GPU nên đặt
`camera.model: hybrid`. Thiếu `transformers` thì `hybrid` tự lùi về `maskrcnn` (cùng ngưỡng). `gdino-sam2` dùng riêng cần
4 ngưỡng ở trên. Cài: `pip install -e ".[vision]"`; lần quét đầu tải trọng số Grounding DINO + SAM 2.1 từ Hugging Face
(~1 GB) và chạy thêm ~0,8 s / ảnh.

## 4. Lớp 3 — Box Critic

Đã có: `pointsnap critic-data` (box làm nhiễu có đáp án, 256 điểm + 20 đặc trưng mỗi mẫu; 5 cảnh tinh chỉnh,
20 mẫu / box = 72 560 mẫu), `scripts/train_critic_example.py`, notebook Colab `scripts/colab_train_critic.ipynb`, luật
`critic.box` nạp TorchScript qua `critic.model`, báo kèm gợi ý sửa. Model không nằm trong repo; guideline mặc định
`critic.model: ""` (tắt).

**Lần huấn luyện đầu** (Colab, script bản đầu): học thuộc. Box chuẩn bị báo sai 0,8% trên cảnh đã học nhưng 30% trên cảnh
mới; quét 5 cảnh kiểm tra báo **9,45 / 100 box** trên nhãn sạch. Nguyên nhân và cách sửa: [box-critic.md](box-critic.md)
mục 2 (kiểm tra theo cảnh, bỏ kích thước tuyệt đối, tăng dữ liệu, và luật so logit với trung vị track).

**Sau khi sửa** (huấn luyện lại trên 4 cảnh tinh chỉnh, ngưỡng chọn trên scene-0916 để riêng, đo trên 5 cảnh kiểm tra —
[báo cáo](eval-box-verifier/kiem-tra-box-critic.md)):

| Lỗi chèn | Box Verifier không Box Critic | **+ Box Critic** |
|---|---|---|
| Co / phóng x0,7 · x1,3 | 9% · 0% | **27% · 12%** |
| Dời 0,3 / 0,5 / 1,0 m | 44% / 36% / 29% | 44% / **64%** / 29% |
| Xoay 15° / 30° | 29% / 27% | **36% / 55%** |
| Nhảy 0,5 m | 55% | **73%** |
| Báo nhầm Cảnh báo / Lỗi trên 100 box | 3,67 / 0,57 | 3,86 / 0,62 (`critic.box` 0,18 / 0,06) |
| Phân mức đúng | 100% | 100% |

Box Critic là lớp duy nhất bắt được box co / phóng (luật theo điểm LiDAR chỉ bắt khi lệch rõ trên vật lớn). Chỉ 4 – 5 cảnh
huấn luyện nên còn yếu; thêm dữ liệu (nuScenes trainval, dữ liệu Việt Nam) là hướng cải thiện chính.

## 5. Lớp 4 — học từ kết luận người duyệt

Mỗi mục có **độ tin cậy** = precision ước lượng của luật (Beta theo số Đúng / Báo nhầm); khi có ≥ 40 kết luận đủ hai
loại thì thử thêm mô hình logistic (luật, mức, class, độ vượt ngưỡng), chỉ dùng nếu log-loss kiểm chéo 5 lần tốt hơn.
`learning.adjust_severity` (tắt mặc định) hạ Cảnh báo có độ tin cậy < 15% xuống Thông tin khi luật đã có ≥ 20 kết luận.
Kiểm thử trên dữ liệu giả lập; dữ liệu thật hiện mới có 1 kết luận nên chưa có số liệu.

## 6. Hiệu năng

Lần đầu chạy ảnh camera: ~1 phút / cảnh 40 frame × 6 ảnh (RTX 3050), lưu đệm ở `~/.pointsnap/cache/det2d`; các lần quét
sau quét một cảnh mất 7 – 25 giây như trước. Không có GPU / PyTorch thì lớp 2 tự tắt.
