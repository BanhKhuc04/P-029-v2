# Bàn giao phần 09

- Nhánh: `codex/review-09-geometry`.
- Base: `3584000`; commit code: **`f22f2b6`**; commit sau code chỉ bổ sung báo cáo/evidence.
- **4 nhóm sửa**: C4 reference đường bằng/dốc; moving phân loại từ peer để không che outlier endpoint; bán kính ground giữ góc box xoay; reference tách class theo track ID.
- **631 Python PASS,5 SKIP,0 FAIL/ERROR/XFAIL;37 Node PASS**. Thêm28 ca; C4 XFAIL cũ đã chuyển PASS.
- 5 SKIP gồm2 torch và3 CVAT live; nuScenes mini thật chạy đủ trong full suite. Coverage scope97%, toàn package90,48%.

## Điều cần biết khi tiếp tục phần 10

1. Nhập commit sửa09 trước khi sửa track/fit/spec. Nếu09 đã merge main: switch nhánh10 và merge origin/main. Nếu chưa merge: có thể merge nhánh09 vào10, ghi dependency và base PR; tránh mất ancestry.
2. Reference floating/heading.points/outside/loose hiện tách `(track_id,label)`; không có nghĩa mọi detector/subtype đã tách đầy đủ. Kiểm subtype, cargo, ID swap và luật spec trong10.
3. Dư đều toàn track vẫn không bị fit.loose báo (RV-09-005); cần quyết định nghiệm thu từ người duyệt, không tự coi giới hạn đã được chấp nhận.
4. C4 chọn peer có terrain bias tương đương khi đủ `min_track_boxes`. Không bật contact tuyệt đối cho mọi box; ít peer vẫn có fallback cũ. Đọc details reference khi kiểm precision.

## Chất lượng và việc còn lại

- GT geometry subset: tuning106→104 warning/24 error; held-out giữ142 warning/32 error và giữ nguyên danh sách findings.
- Held-out2,610 warning/0,588 error trên100box vẫn vượt G7. Không chứng nhận chất lượng chỉ vì suite xanh.
- Kiểm tay scene-0916 frame14 track644/652 (motorcycle) và scene-1094 track804 frame9/14 (car). Lượt này0 verdict precision tay.
- Probe ±25cm: nâng26/27,hạ27/27 hits trước/sau; xoay13°10/37 ở ngưỡng12° so2/37 ở15°. Đây là target hit count, chưa trừ clean-hit, không phải recall tổng.
- TestClient kẹt socketpair trong sandbox; đã cô lập bằng faulthandler và full suite đạt ngoài sandbox. Không sửa môi trường/dependency ứng dụng để né sự cố.

[Báo cáo09](09-report.md), [verification](evidence/09/verification.json), [GT comparison](evidence/09/quality-comparison.json), [injection](evidence/09/injection-summary.json).

Phần 09 đã được push lên GitHub ngày 13/10, đầu nhánh `cbeb41c`. Phần 10 đã nhập kết quả 09. Chưa có thao tác tạo PR hoặc merge trong chat này; các nhánh 11–16 cần nhận kết quả theo dependency trước khi làm tiếp.
