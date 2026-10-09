# Tuần gia hạn 11/10 – 17/10 — Giai đoạn 3: bám spec gán nhãn, sai hướng box, box lệch

🎯 **Mục tiêu:** PointSnap kiểm được các điều khoản **đo được bằng số** của *Annotation Specification* giao thông VN
(spec 3.1.3, 4.2, 4.4), có số liệu đánh giá cho mọi luật mới, demo trên task CVAT có bộ nhãn theo spec. **Nộp 18/10.**

Vẫn giữ góp ý của mentor: **chỉ phát hiện và cảnh báo**, không tự sửa box; không gắn mô hình học máy vào luồng chính.

## Đã xong (code, PR "Giai đoạn 3")

| Mã | Việc | Kết quả |
|---|---|---|
| C1 | Luật **sai hướng box** `heading.flip`, `heading.motion`, `heading.points` (spec 4.2) | Lật 180° / xoay 90° bắt 100%; lật hướng / ngược chiều 0 báo nhầm trên 10 cảnh |
| C1 | Luật **box lệch khỏi vật** `fit.empty`, `fit.outside`, `fit.loose`, `fit.overlap` (spec 4.2) | Vẽ trùng bắt 100%; box dời / co chỉ bắt khi lệch rõ trên vật lớn |
| C1 | **Mặt đất v2**: gộp 4 lượt quét LiDAR, bỏ vệt xe đang chạy | Báo nhầm lơ lửng / lún trên cảnh kiểm tra 3,18 · 0,66 → 2,41 · 0,31 / 100 box |
| C2 | Track theo spec 4.4: `to-cvat` dùng **occluded** cho đoạn vắng ≤ 6 frame, tách track khi vắng lâu; luật `track.reuse_id`, `track.occluded_long` | Box occluded không bị kiểm hình học |
| C2 | Luật **thiếu / sai thuộc tính** `attr.missing`, `attr.invalid` (spec 3.1.3); kích thước theo **Class/thuộc tính** | — |
| C2 | Bộ class **spec-vn** (`--taxonomy spec-vn`) + guideline mẫu `pointsnap/guidelines/spec-vn.yaml` | Demo trên task có label Vehicle / Two-wheels / Pedestrian / Animal / Obstacle |
| — | Web, extension, báo cáo, chèn lỗi giả và `pointsnap eval --errors c1` cho mọi luật mới | Số liệu: `docs/ket-qua-giai-doan-3.md` |

## Việc của từng người

### Khúc Việt Anh · sản phẩm
- [ ] Review và merge PR giai đoạn 3; tạo **lại** task scene-0061 bằng `to-cvat` mới (đoạn vắng thành occluded).
- [ ] Tạo task spec-vn: `pointsnap nuscenes --taxonomy spec-vn to-cvat --scene scene-0061 --out D:/data/cvat-vn --upload`.
- [ ] Cập nhật CAI-DAT.md: bước tạo token **bỏ tích Read-only** (lỗi CHIEN-01), bước tạo task spec-vn.
- [ ] Sửa các lỗi trong `docs/test/tong-hop-loi.md` được giao.

### Đặng Văn Huy · thuật toán
- [ ] Review code `detectors/heading.py`, `detectors/fit.py`, `core/box_points.py`, mặt đất v2 trong `detectors/floating.py`.
- [ ] Xem 20 mục `fit.outside` / `fit.loose` trên nhãn sạch (báo nhầm còn lại): chỉnh ngưỡng nếu cần, chỉ trên 5 cảnh tinh
      chỉnh; chạy lại `pointsnap eval --scenes test --errors all` một lần để chốt số.
- [ ] *(Không bắt buộc, chỉ khi G7 đạt sớm)* thử 1 ngày CenterPoint huấn luyện sẵn làm "ý kiến thứ hai" mức Thông tin.

### Nhữ Đình Chiến · test
- [ ] Hoàn tất PR #36 theo review.
- [ ] Test **TC-70 – TC-80** (mục 5.7 của [chuẩn kiểm thử](../docs/test/CHUAN-KIEM-THU.md)) trên task tạo lại và task spec-vn.
- [ ] Quay video demo: quét → extension đi qua lỗi (có lỗi lật box và vẽ trùng) → sửa → quét lại → `gate` ĐẠT với guideline
      mặc định.

### Nguyễn Văn Hân · đánh giá
- [ ] Xem tay **20 mục mỗi luật mới** (`heading.*`, `fit.*`) trên scene-0061 theo mục 6 của chuẩn kiểm thử; precision
      riêng từng luật.
- [ ] Cập nhật `docs/danh-gia.md` bằng `docs/ket-qua-giai-doan-3.md` và kết quả xem tay.

### Vũ Bảo Khánh · báo cáo
- [ ] Thêm vào báo cáo và slide **bảng truy vết spec ↔ luật** (mục 4.7 của đề xuất): mỗi luật kiểm điều khoản nào.
- [ ] Mục giới hạn: dữ liệu demo là nuScenes, khoảng kích thước của van / xe ba gác / động vật là ước lượng; chưa phát
      hiện sót đối tượng.
- [ ] Tổng hợp lỗi đợt test giai đoạn 3; nộp 18/10.

## Cổng

| Cổng | Khi | Đạt khi |
|---|---|---|
| **G6** | 12/10 12h | PR giai đoạn 3 được review, merge; task CVAT tạo lại chạy được |
| **G7** | 15/10 12h | Có số liệu cuối trên 5 cảnh kiểm tra + precision xem tay của luật mới; báo nhầm tổng ≤ 2 Cảnh báo / ≤ 0,5 Lỗi / 100 box |
| **G8** | 17/10 | Test TC-70 – 80 xong, video, báo cáo, slide |

**Thứ tự cắt nếu trễ:** thử mô hình → task spec-vn trong video → `heading.points` → `fit.loose`.
**Không cắt:** lật box / ngược hướng, vẽ trùng, occluded theo spec, số liệu đánh giá, video, báo cáo.
