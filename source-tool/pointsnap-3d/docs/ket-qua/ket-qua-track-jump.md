# `track.jump`: hai đầu track và track 3 box (11/10/2026)

Đo bằng `pointsnap eval --errors core --rounds 100` với guideline chỉ bật luật `track.jump` (ảnh camera tắt), nên mỗi
mức nhảy có 150 – 200 mẫu thay vì ~10. Chọn cách sửa trên 5 cảnh tinh chỉnh; 5 cảnh kiểm tra chạy một lần.

## 1. Hai lỗi tìm được

**Báo nhầm ở hai đầu track khi keyframe kế tiếp ở xa.** Trên nhãn chuẩn của 5 cảnh tinh chỉnh có 13 mục `track.jump`,
12 mục ở đầu / cuối track; 8 trong số đó box đầu / cuối cách hai keyframe kế tiếp 4 – 7 frame (vd box ở frame 1, hai box
kế tiếp ở frame 5, 6). Vận tốc ước lượng từ hai box cách nhau 1 frame rồi ngoại suy 4 frame thì sai số nhân 4, nhưng
ngưỡng chỉ nhân 1,5. Sửa: ở hai đầu, ngưỡng nhân `1,5 × max(1, khoảng ngoại suy / khoảng giữa hai box dùng để ước lượng)`,
**trừ vật đứng yên** (mọi vị trí của track trong 1 m quanh trung vị): vận tốc ~0 nên ngoại suy xa vẫn chắc.

**Bỏ sót nhảy 4 m trên track 3 box.** Cả 12 / 200 mục nhảy 4 m bị sót đều là track 3 box nhảy ở box giữa: box giữa lệch
4 m kéo vị trí ngoại suy ra hai đầu lệch 8 m, nên tool đổ lỗi cho một đầu (báo sai frame). Bỏ box nào cũng còn 2 box nên
không kiểm được bằng vị trí. Sửa: khi hòa, chọn giả thuyết để 2 box còn lại có tốc độ thấp nhất.

**Đối chiếu với kết luận xem tay (job 2 = scene-0061, cảnh tinh chỉnh; Chiến xem 8 mục `track.jump`).** Bản sửa đầu (nhân
ngưỡng cho mọi vật) bỏ được 2 mục Chiến đánh Báo nhầm (xe frame 1, người chạy nhanh frame 25) nhưng bỏ luôn 4 mục Đúng —
đều là vật đứng yên (3 cọc tiêu bị dời ở đầu track, 1 người đứng yên). Thêm ngoại lệ vật đứng yên:

| | Mục Đúng bắt được | Mục Báo nhầm còn báo |
|---|---|---|
| `main` | 6 / 6 | 2 |
| Nhân ngưỡng cho mọi vật | 2 / 6 | 0 |
| **Nhân ngưỡng, trừ vật đứng yên** | **5 / 6** | **0** |

## 2. Kết quả

| | Tinh chỉnh: `main` | Tinh chỉnh: sau sửa | **Kiểm tra: `main`** | **Kiểm tra: sau sửa** |
|---|---|---|---|---|
| Báo nhầm Cảnh báo / Lỗi trên 100 box | 0,10 / 0,05 | 0,09 / 0 | 0,22 / 0,07 | **0,17 / 0,06** |
| Bắt nhảy 0,5 m | 34% | 38% | 17% | 19% |
| Bắt nhảy 1 m | 75% | 78% | 54% | 56% |
| Bắt nhảy 2 m | 98% | 100% | 94% | **98%** |
| Bắt nhảy 4 m | 94% | 100% | 95% | **100%** |
| Nhảy 4 m báo ở mức Lỗi | 94% | 100% | 95% | **100%** |

Chỉ tiêu "nhảy 4 m ≥ 90%" của A12 / B8 đạt trên cả hai bộ cảnh.

Cột "sau sửa" là bản có ngoại lệ vật đứng yên. Cảnh kiểm tra đã chạy hai lần cho PR này (bản đầu: 0,15 / 0,06, cùng tỉ lệ
bắt); lần sửa thứ hai dựa trên kết luận xem tay ở cảnh tinh chỉnh, không chỉnh theo số của cảnh kiểm tra. "Báo nhầm"
trên nhãn chuẩn tính cả lỗi thật của nhãn nuScenes (3 cọc tiêu ở scene-0061 nằm trong số này).
