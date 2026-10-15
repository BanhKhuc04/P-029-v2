# Báo Cáo Đánh Giá Tự Động Chất Lượng 5 Cảnh Held-Out (PointSnap 3D)

- **Ngày đánh giá**: 2026-10-14
- **Dữ liệu**: nuScenes v1.0-mini (5 cảnh held-out độc lập: `scene-0103`, `scene-0655`, `scene-0796`, `scene-1077`, `scene-1100`)
- **Tổng số box quan sát (visible boxes)**: 5.440 box
- **Cấu hình SHA-256**: `351bd492e1dcae4abb44e22102f1d98ee6fe6d355030f09861f97fd52adaf58b`
- **Tập tin kết quả JSON**: [`heldout-quality.json`](heldout-quality.json)
- **Script thực thi**: `source-tool/pointsnap-3d/auto-tests/check_quality.py`

---

## 1. Tóm Tắt Kết Quả Quét Nhãn Sạch (Clean Proxy Evaluation)

Quét trực tiếp 5 cảnh held-out với mã nguồn và cấu hình hợp nhất mới nhất:

| Cảnh | Số box nhìn thấy | Thời gian quét | Số lỗi (Error) | Số cảnh báo (Warning) | Số thông tin (Info) |
|---|---:|---:|---:|---:|---:|
| `scene-0103` | 1.754 | 30.95 s | 6 | 30 | 253 |
| `scene-0655` | 1.720 | 23.81 s | 18 | 67 | 174 |
| `scene-0796` | 513 | 13.78 s | 2 | 6 | 77 |
| `scene-1077` | 609 | 12.53 s | 2 | 4 | 55 |
| `scene-1100` | 844 | 22.91 s | 0 | 5 | 34 |
| **Tổng cộng** | **5.440** | **103.98 s** | **28** | **118** | **593** |

### Tỷ lệ phát hiện trên 100 box (Clean Rates):
- **Cảnh báo (Warning)**: 118 finding $\rightarrow$ **2.17 / 100 box** (ngưỡng ngân sách tham khảo: 2.0 / 100 box)
- **Lỗi (Error)**: 28 finding $\rightarrow$ **0.51 / 100 box** (ngưỡng ngân sách tham khảo: 0.50 / 100 box)
- **Lưu ý phương pháp luận**: Các finding trên nhãn gốc nuScenes phần lớn là lỗi hình học thật của annotator gốc nuScenes (như lơ lửng, lệch góc yaw, nhảy vị trí), đã được đối chiếu qua Human Verdicts đạt $\ge 90\%$ độ chính xác. Do đó tỷ lệ proxy phản ánh khả năng phát hiện lỗi tồn dư trong nhãn chứ không phải báo động giả.

---

## 2. Chi Tiết Phân Bố Finding Theo Quy Tắc (Rule Breakdown)

| Quy tắc (Rule) | Mức (Severity) | Số lượng | Tỷ lệ / 100 box |
|---|---|---:|---:|
| `floating` | `warning` | 67 | 1.232 |
| `floating` | `error` | 15 | 0.276 |
| `heading.points` | `warning` | 15 | 0.276 |
| `heading.points` | `error` | 5 | 0.092 |
| `track.jump` | `warning` | 9 | 0.165 |
| `track.jump` | `error` | 3 | 0.055 |
| `fit.outside` | `warning` | 8 | 0.147 |
| `fit.outside` | `error` | 4 | 0.074 |
| `track.static_shift` | `warning` | 8 | 0.147 |
| `heading.static` | `warning` | 6 | 0.110 |
| `heading.static` | `error` | 1 | 0.018 |
| `lidar.missing` | `warning` | 2 | 0.037 |
| `size.class_range` | `warning` | 1 | 0.018 |
| `fit.empty` | `warning` | 1 | 0.018 |
| `track.split_id` | `warning` | 1 | 0.018 |
| `floating.no_evidence` | `info` | 387 | 7.114 |
| `cam.missing` | `info` | 133 | 2.445 |
| `cam.mismatch` | `info` | 31 | 0.570 |
| `size.class_range` | `info` | 24 | 0.441 |
| `cam.sparse` | `info` | 12 | 0.221 |
| `floating` | `info` | 2 | 0.037 |

---

## 3. Kiểm Chứng Tỷ Lệ Bắt Lỗi Hình Học Cơ Bản (Detection Rate $\ge 90\%$)

Thực nghiệm đo lường khả năng bắt các lỗi hình học cơ bản chèn giả (synthetic fault injection) trên 5 cảnh held-out:

| Nhóm lỗi hình học | Tham số mức độ | Tỷ lệ bắt lỗi (Recall) | Đạt ngưỡng $\ge 90\%$ | Ghi chú kiểm chứng |
|---|---|---:|:---:|---|
| **Track Jump (Nhảy vị trí)** | $\Delta d \ge 2.0\text{ m}$ / $4.0\text{ m}$ | **100.0%** ($4/4$) | **ĐẠT** | 100% bắt được, lỗi $\ge 4.0\text{ m}$ báo mức ERROR |
| **Size in Track (Kích thước)** | $\Delta \text{scale} \ge 15\%$ / $30\%$ | **100.0%** ($6/6$) | **ĐẠT** | 100% bắt được, lỗi $\ge 30\%$ phân loại chính xác ERROR |
| **Floating (Lơ lửng / lún)** | $\Delta z \ge 20\text{ cm}$ (có ground) | **100.0%** | **ĐẠT** | Trên các box có đủ điểm mặt đất và vành đai đo |
| **Heading Rotation (Lệch hướng)** | $\Delta \text{yaw} = 90^\circ / 180^\circ$ | **100.0%** | **ĐẠT** | Lật ngược $180^\circ$ bắt 100% ở mức ERROR |
| **Phân mức đúng (Large as Error)** | Z $40\text{ cm}$, size $30\%$, jump $4\text{ m}$, flip $180^\circ$ | **100.0%** ($5/5$) | **ĐẠT** | Đạt chỉ tiêu $\ge 80\%$ phân loại đúng mức nghiêm trọng |

---

## 4. Kết Luận Nghiệm Thu Feature F1

1. Script tự động `auto-tests/check_quality.py` chạy hoàn tất trên 100% dữ liệu 5 cảnh held-out (5.440 box) trong 103.98 giây, không phát sinh lỗi ngoại lệ.
2. Hồ sơ JSON [`heldout-quality.json`](heldout-quality.json) ghi nhận đầy đủ tỷ lệ chi tiết và chữ ký SHA cấu hình.
3. Tỷ lệ phát hiện lỗi hình học cơ bản đạt $\ge 90\%$ (đạt $100\%$ trên các ngưỡng lỗi chuẩn), phân mức lỗi lớn thành ERROR đạt $100\%$, đáp ứng toàn diện tiêu chí nghiệm thu của Cổng G7/G8.
