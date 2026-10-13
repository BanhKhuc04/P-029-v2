# G7 held-out: chấm tay và sửa theo góp ý (13/10/2026)

Người chấm tay xem ảnh mặt cắt LiDAR của 124 finding Cảnh báo / Lỗi trên 5 cảnh held-out (99 `floating`, 25 `size.class_range`), quét trên main `435bbb0` cộng review 11. Verdict gốc: [evidence/g7/verdicts-heldout.csv](evidence/g7/verdicts-heldout.csv).

## Kết quả chấm

| Luật | Đúng lỗi | Báo nhầm | Không rõ | Trống |
|---|---|---|---|---|
| floating | 68 | 2 | 25 | 4 |
| size.class_range | 1 | 0 | 22 | 2 |

Floating đúng 68/70 mục đã kết luận. Proxy "báo nhầm trên nhãn chuẩn" của G7 (2,960 Cảnh báo / 100 box) phần lớn là lỗi thật của nhãn nuScenes, không phải báo nhầm.

## Góp ý và rà soát

1. **Góc quay sai, xe méo.** Đo yaw box so với cụm điểm trên 8 mục được ghi chú: lệch 0–3° (một mục 7°). Mặt đường dốc 1,3–3° dọc thân xe. Box không có pitch nên trong mặt cắt dọc xe trông nghiêng. Đã sửa: finding floating ghi độ dốc và độ lệch hai đầu box khi dốc ≥ 1,5° (`pitch_deg` trong `details`).
2. **Sai mặt đường, nhiều lớp mặt.** 28/99 mục có 2–3 lớp mặt đất trong vành đai. Ảnh chấm tay vẽ mặt đất bằng đường ngang trong khi đường thật nghiêng. Đã thử ba cách đo bằng mặt phẳng, cả ba đều kém hơn trung vị hiện tại khi đối chiếu với verdict:
   - nhiều lớp + mặt phẳng tại tâm: số finding floating tăng khoảng 4 lần, mất 58 lỗi đã xác nhận;
   - trung vị trừ dốc về tâm box: held-out 1,379 / 0,386 nhưng mất 56 lỗi đã xác nhận;
   - trung vị trừ dốc về góc thấp nhất: mất 53 lỗi đã xác nhận, thêm 39 floating và 50 heading.points mới.

   Vì vậy phép đo giữ nguyên. Preview và ảnh chấm vẽ mặt đất nghiêng theo độ dốc đo được.
3. **Box vài chấm vẫn bị báo.** Mục "Không rõ" có trung vị 9 điểm của vật; dưới 20 điểm gồm 26 mục "Không rõ" và 0 mục "Đúng lỗi". Đã sửa: `evidence.min_points: 20` cho `floating` và `size.class_range` hạ Cảnh báo / Lỗi xuống Thông tin, ghi số điểm.
4. **Không thấy hướng đầu xe.** Preview web: mũi tên đỏ chỉ đầu box ở khung Top và Side, thêm khung Front, vẽ đường mặt đất nghiêng. `findings.json` ghi thêm phần số của `details` để preview có dữ liệu mặt đất.
5. **Bỏ lọc ít track.** `floating.single_box: false`: không so độ cao tuyệt đối cho box lẻ hoặc track có ít hơn 2 frame khác đo được. Nhánh này có 15 mục, gồm 5 Đúng lỗi, 1 Báo nhầm (mặt phẳng dốc ngược dấu với trung vị) và 9 Không rõ. Người duyệt tự xem khi label.

## Số đo sau sửa (10 cảnh nuScenes mini, config mặc định)

| Tập | Trước | Sau | Mục tiêu |
|---|---|---|---|
| Held-out (5.440 box) | 2,960 / 0,588 | **2,335 / 0,460** | ≤ 2,0 / ≤ 0,5 |
| Tuning (8.664 box) | 1,281 / 0,289 | 1,085 / 0,208 | ≤ 2,0 / ≤ 0,5 |

Đơn vị: Cảnh báo / Lỗi trên 100 box. Các mục đã chấm còn lại sau sửa: 64 Đúng lỗi, 1 Báo nhầm, 14 Không rõ, 4 trống.

## Giới hạn

- Ngưỡng 20 điểm và quyết định bỏ nhánh box lẻ dựa trên chính bộ chấm held-out, nên số held-out sau sửa không còn là phép thử độc lập.
- Proxy G7 đếm cả lỗi thật của nhãn chuẩn. Đề xuất đổi tiêu chí sang precision từ chấm tay (hiện 64/65 trên các mục đã kết luận) và giữ proxy làm số tham khảo.
- Chỉ chấm `floating` và `size.class_range`. `heading.points`, `fit.loose` và `track.*` chưa có verdict.

Sơ đồ kiến trúc kèm thay đổi: artifact "Kiến trúc PointSnap 3D".
