# C6 — Bám spec theo hình học: thuộc tính khớp chiều cao, người trong xe, người lái gán hai lần

Trước C6, luật thuộc tính (`attr.missing`, `attr.invalid`) chỉ kiểm thuộc tính **có** và **đúng danh sách**, không kiểm
thuộc tính có **đúng với vật** không. C6 thêm 3 luật mức Cảnh báo, cấu hình trong mục `spec:` của guideline
(`pointsnap/guidelines/spec-vn.yaml`); guideline không khai thì luật không chạy (bộ class nuScenes mặc định không có
thuộc tính kiểu spec).

| Luật | Spec | Cách làm |
|---|---|---|
| `attr.height` | 3.1.2, 4.3B/C | Trung vị chiều cao box của từng đoạn liền cùng giá trị thuộc tính trong track phải nằm trong `spec.attribute_height` (khóa `Class/giá trị[/giá trị]`, lấy khóa cụ thể nhất) |
| `spec.inside` | 4.3B: không gán người bên trong xe | Tâm box người nằm trong footprint box xe (lùi 10 cm), đáy người cao hơn đáy xe < 0,6 m (đứng trên nóc / thùng xe thì được). Xét cả box `occluded` — người ngồi trong xe hay bị đánh occluded |
| `spec.rider_double` | 4.3C: người lái nằm trong box xe hai bánh | Box người chồng ≥ 50% footprint lên box `Two-wheels/with_rider` cùng frame; xe `without_rider` (người dắt / đứng cạnh) không tính |

## Ngưỡng `attr.height` — đo trên nhãn chuẩn nuScenes (bộ class spec-vn), 10 cảnh

| Thuộc tính | Chiều cao box p1 – p99 | Khoảng chọn |
|---|---|---|
| Người lớn đứng | 1,56 – 2,00 m | 1,45 – 2,20 |
| Người ngồi | 1,28 – 1,52 m | 0,80 – 1,60 |
| Trẻ em | 1,33 – 1,49 m | 0,60 – 1,60 |
| Xe hai bánh có người lái | 1,56 – 1,93 m | 1,45 – 2,20 |
| Xe hai bánh không người | 0,95 – 1,53 m | 0,60 – 1,60 |

## Kết quả (`spec_eval`: nhãn sạch + lỗi chèn, nuScenes spec-vn)

| | 5 cảnh tinh chỉnh | 5 cảnh kiểm tra |
|---|---|---|
| Báo nhầm trên nhãn sạch | 3 mục / 8 759 box (0,03 / 100) | 1 mục / 5 458 box (0,02 / 100) |
| Đổi tư thế đứng → ngồi | 95% (155 / 164) | 91% (69 / 76) |
| Đổi người lớn → trẻ em | 95% (155 / 164) | 96% (69 / 72) |
| Đổi có ↔ không người lái | 83% (5 / 6) · 88% (15 / 17) | 100% (6 / 6) · 100% (7 / 7) |
| Đổi ngồi → đứng, trẻ em → người lớn | 100% (4 / 4) · — | 50% (1 / 2) · 50% (2 / 4) |
| Chèn người ngồi trong xe | 100% (159 / 159) | 100% (294 / 294) |
| Chèn thêm box người lên xe có người lái | 100% (6 / 6) | 100% (6 / 6) |

3 mục "báo nhầm" trên cảnh tinh chỉnh trông là vấn đề thật của nhãn nuScenes (xe máy ghi không người lái mà box cao
1,74 m; người lớn "đứng" box cao 1,15 m; một box người chồng lên xe đạp có người lái) — đúng loại cần người duyệt xem.

## Không làm: ảnh camera kiểm loại xe / loài vật

Đo trên 5 cảnh tinh chỉnh: Mask R-CNN COCO nhận đúng car 98%, truck 95%, bus 88% số lần nhìn rõ. Nhưng nhầm class giữa
car / truck / bus đã bị `size.class_range` bắt 100% (lỗi chèn "class khác"), còn các loại cần phân biệt theo spec VN
(van ↔ car, pickup ↔ truck, xe ba gác, trâu ↔ bò) COCO không có → luật thêm gần như không bắt thêm lỗi.

Test: `tests/test_spec_geometry.py` (gồm một cảnh mô phỏng quét đầu-cuối với guideline spec-vn).

## C8 — lên / xuống xe quên đổi `rider_state` (`attr.rider_state`, spec 4.3C)

Đo trên nhãn chuẩn nuScenes spec-vn: xe hai bánh `without_rider` chạy tối đa **1,0 m/s** (dắt xe), còn `with_rider`
thường chạy trên 2 m/s (tới 15 m/s). Luật (mức Cảnh báo, khai `spec.rider_state` trong guideline):

- **Lên xe quên đổi:** xe `without_rider` chạy > 2,5 m/s ở ≥ 2 bước liền.
- **Xuống xe quên đổi:** xe `with_rider` đứng yên, một track người mới bắt đầu sát xe (≤ 1,2 m), xe vẫn `with_rider` ≥ 2
  keyframe sau đó.

| | 5 cảnh tinh chỉnh | 5 cảnh kiểm tra |
|---|---|---|
| Báo nhầm trên nhãn sạch | 0 | 0 |
| Đổi xe có người lái → `without_rider` cả track | 4 / 6 | 5 / 6 |

Sót: xe có người lái đứng chờ suốt đoạn (không phân biệt được bằng chuyển động). Ca xuống xe kiểm bằng test
(`tests/test_spec_geometry.py`), nuScenes ít tình huống này.
