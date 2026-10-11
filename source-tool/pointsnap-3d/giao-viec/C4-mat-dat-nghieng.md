# C4 — Lơ lửng / lún trên mặt đất không phẳng (dốc, đá, bậc vỉa hè)

Spec 4.2: *đáy box đặt trên mặt tiếp xúc với mặt đường / địa hình*. Hiện `ring_ground_for_box`
([core/ground.py](../pointsnap/core/ground.py)) lấy **trung vị độ cao** điểm thấp trong vành đai 0,1–0,8 m quanh đáy box,
tức coi mặt đất **phẳng ngang**. Box là 7-DoF (spec 4.1), không có pitch / roll. Luật `floating`
([detectors/floating.py](../pointsnap/detectors/floating.py)) so `d = đáy box − mặt đất` với trung vị track
(Cảnh báo > 15 cm, Lỗi > 22 cm); box lẻ / track ngắn so `|d|` tuyệt đối (15 / 30 cm).

## Các trường hợp

| Tình huống | Hiện tại | Đánh giá |
|---|---|---|
| Xe trên dốc đều suốt track | `d` lệch cố định (dốc 5°, xe 4,5 m: ~20 cm) nhưng triệt tiêu khi so với trung vị track | ✅ |
| Xe đi từ đường bằng lên dốc (độ dốc đổi trong track) | `d` trôi theo độ dốc, lệch trung vị track | ⚠️ có thể báo nhầm |
| Box lẻ / track ngắn trên dốc | so `|d|` tuyệt đối | ⚠️ có thể báo nhầm |
| Cục đá nhỏ trong vành đai | lưới min-Z 0,4 m + trung vị bị đa số ô mặt đường lấn át | ✅ |
| Bánh xe đè lên đá (xe kênh) | đá nằm dưới xe, ngoài vành đai; đáy box theo bánh đè đá → cao hơn mặt đường | ⚠️ báo "lơ lửng" nhầm (spec: mặt tiếp xúc) |
| Bậc vỉa hè (vành đai lấn xuống lòng đường thấp hơn ~15 cm) | trung vị theo phía nhiều điểm hơn | ⚠️ nhiễu — một nguồn báo nhầm chính đã đo (box xa / ít điểm) |
| LiDAR chỉ thấy một phía vật (phía kia bị thân vật che) | điểm vành đai lệch về một phía; dốc ngang làm lệch thêm | ⚠️ |

nuScenes mini chủ yếu đường bằng nên các trường hợp ⚠️ **chưa được kiểm chứng riêng**.

## Việc cần làm

1. **Test tổng hợp trước** (`tests/test_ground_slope.py`): mặt đất giả có dốc dọc / ngang 3°, 6°, 10°; đoạn chuyển
   bằng → dốc trong một track; đá 10 / 20 cm trong vành đai và dưới một bánh; bậc vỉa hè 15 cm; điểm chỉ ở một phía.
   Mỗi trường hợp ghi kết quả mong muốn (báo / không báo). Chạy với code hiện tại để thấy trường hợp nào sai.
2. **Mặt phẳng cục bộ:** khớp mặt phẳng bền (RANSAC hoặc Huber) trên điểm vành đai **hẹp** (giữ 0,1–0,8 m); so đáy box
   với **điểm tiếp xúc thấp nhất** = độ cao mặt phẳng thấp nhất dưới 4 góc đáy box. Chỉ dùng khi đủ điểm ở ≥ 2 phía và độ
   dốc khớp được rõ (vd > 2°); ngược lại giữ trung vị như cũ. Lưu ý: RANSAC trên vành đai rộng 0,5–1,5 m từng nhiễu hơn
   trung vị (p90 20 so với 15 cm, `docs/kiem-chung-ground.md`).
3. **Bậc / vỉa hè:** độ cao vành đai tách 2 cụm cách nhau > 10 cm → lấy cụm sát chỗ tiếp xúc (sát bánh / chân), hoặc
   ghi `floating.no_evidence` (Thông tin) thay vì kết luận.
4. **Vật dưới bánh:** chỉ báo lơ lửng khi khe hở thấy ở nhiều phía của vật, không khi chỉ một góc bị kênh.
5. **Đo lại** `pointsnap eval --scenes tuning|test --rounds 10 --errors all`: chỉ chỉnh ngưỡng trên 5 cảnh tuning;
   báo nhầm `floating` hiện 0,79 / 0,24 (tuning), 1,56 / 0,31 (test) trên 100 box; recall lơ lửng / lún không được giảm.
6. Cập nhật `docs/ket-qua-box-verifier.md` (hoặc tài liệu kết quả mới), `de-xuat-de-tai.md` mục 4.1 a, `CONVENTIONS.md`.

**Tiêu chí xong:** test tổng hợp đúng hết các trường hợp trên; báo nhầm `floating` trên tuning không tăng; recall không giảm.
