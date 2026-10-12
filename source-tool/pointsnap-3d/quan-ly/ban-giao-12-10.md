# Bàn giao PointSnap 3D — 12/10/2026

Tình trạng sản phẩm giữa tuần gia hạn (giai đoạn 3, nộp 18/10): việc nào đã xong, PR nào đang chờ, merge theo thứ tự nào,
kiểm lại thế nào, còn lại việc gì. Kế hoạch tuần và cổng G6 – G8: [`quan-ly/giao-viec/tuan-gia-han.md`](giao-viec/tuan-gia-han.md).

## 0. Cập nhật sau khi merge (12/10, chiều)

Đã merge vào `main` theo đúng thứ tự mục 3: [#50](https://github.com/AI20K-Build-Phase-Cohort-4A/P-029/pull/50), [#44](https://github.com/AI20K-Build-Phase-Cohort-4A/P-029/pull/44), [#42](https://github.com/AI20K-Build-Phase-Cohort-4A/P-029/pull/42), [#41](https://github.com/AI20K-Build-Phase-Cohort-4A/P-029/pull/41), [#46](https://github.com/AI20K-Build-Phase-Cohort-4A/P-029/pull/46),
[#43](https://github.com/AI20K-Build-Phase-Cohort-4A/P-029/pull/43), [#47](https://github.com/AI20K-Build-Phase-Cohort-4A/P-029/pull/47), [#49](https://github.com/AI20K-Build-Phase-Cohort-4A/P-029/pull/49), [#40](https://github.com/AI20K-Build-Phase-Cohort-4A/P-029/pull/40) (xung đột giải như mục 3, kèm sửa `scanner.py`) và
[#45](https://github.com/AI20K-Build-Phase-Cohort-4A/P-029/pull/45). **#48 để ngỏ** vì làm báo nhầm `fit.outside` tăng 0,04 → 0,24 / 100 box trong khi cảnh kiểm tra chưa đạt
G7. `main` sau khi merge: `pytest` 334 passed, 2 skipped, 1 xfailed; extension 7 / 7. Số eval sau khi merge: mục 5.

Các mục 2 – 4 dưới đây giữ nguyên để tra lại quá trình.

## 1. Đã có trên `main`

Giai đoạn 1 – 2 (A1 – A15, B1 – B7: CVAT, quét, gắn cờ, `gate`, web, extension) và giai đoạn 3 đến C3
([PR #37](https://github.com/AI20K-Build-Phase-Cohort-4A/P-029/pull/37), [PR #39](https://github.com/AI20K-Build-Phase-Cohort-4A/P-029/pull/39)):
sai hướng box, box lệch khỏi vật, mặt đất v2, track và thuộc tính theo spec, bộ class spec-vn, Box Verifier 4 lớp.

## 2. Chờ merge

| PR | Nội dung | Ghi chú |
|---|---|---|
| **PR bàn giao** (nhánh `feat/ban-giao-giai-doan-3`) | Ngưỡng lơ lửng 15 cm (C3), giao việc C4, C5 – C8, extension nhận `lidar.missing` / `cam.sparse`, tài liệu này | Gồm toàn bộ commit của `feat/C3-verifier-geometry` sau PR #39 |
| [#44](https://github.com/AI20K-Build-Phase-Cohort-4A/P-029/pull/44) | Quét nhanh ~3,3 lần, kết quả giống hệt | An toàn |
| [#42](https://github.com/AI20K-Build-Phase-Cohort-4A/P-029/pull/42) | Bỏ `heading.motion` khi không có pose (job 2: 886 → 0 báo nhầm) | An toàn |
| [#41](https://github.com/AI20K-Build-Phase-Cohort-4A/P-029/pull/41) | `track.jump` hai đầu track: nhảy 4 m bắt 100% | An toàn |
| [#46](https://github.com/AI20K-Build-Phase-Cohort-4A/P-029/pull/46) | CAI-DAT bỏ *Read only* khi tạo token (CHIEN-01) | An toàn |
| [#43](https://github.com/AI20K-Build-Phase-Cohort-4A/P-029/pull/43) | Box Critic ensemble: báo nhầm giảm 28% | An toàn |
| [#47](https://github.com/AI20K-Build-Phase-Cohort-4A/P-029/pull/47) | `fit.loose` so với track: box phóng x1,15 bắt 23% → 37% | Báo nhầm tăng nhẹ |
| [#49](https://github.com/AI20K-Build-Phase-Cohort-4A/P-029/pull/49) | C4: lơ lửng / lún trên mặt đất dốc | 14 / 15 ca tổng hợp, 1 xfail đã biết |
| [#40](https://github.com/AI20K-Build-Phase-Cohort-4A/P-029/pull/40) | Camera: tùy chọn Grounding DINO + SAM 2.1, `hybrid` | **Xung đột với PR bàn giao**, xem mục 3 |
| [#45](https://github.com/AI20K-Build-Phase-Cohort-4A/P-029/pull/45), [#48](https://github.com/AI20K-Build-Phase-Cohort-4A/P-029/pull/48) | `heading.points` 12°, `fit.outside` nhạy hơn | **Nhóm quyết**: tăng tỉ lệ bắt nhưng tăng báo nhầm |

CI (pytest + extension) của #40 – #49 đều xanh lúc 12/10 14:30.

## 3. Thứ tự merge đề xuất

1. PR bàn giao.
2. Nhóm an toàn: #44, #42, #41, #46, #43, #47 — đã thử ghép, không xung đột với nhau và với PR bàn giao.
3. #49 (C4).
4. #40 — sau PR bàn giao sẽ xung đột ở hai file, cả hai bên đều chỉ **thêm** code nên giữ cả hai:
   - `pointsnap/core/config.py`: giữ `sparse_max_points` + `MissingConfig` (C7, C8) và `model` / `effective_model()` (#40);
     trong `_parse_camera` giữ cả khối đọc `sparse_max_points` lẫn khối đọc `model`.
   - `tests/test_camera.py`: giữ cả test `cam.sparse` lẫn các test model ảnh theo từ khóa.
   - Thêm một sửa nhỏ trong `pointsnap/core/scanner.py` để `cam.sparse` và `lidar.missing` dùng cùng model ảnh với
     `camera.model`: đổi `_detector()` thành `_detector(config.camera.effective_model())` ở `check_camera` (dòng
     `sparse_unconfirmed`) và `check_missing`. Mặc định `maskrcnn` nên kết quả không đổi.
5. #45, #48 nếu nhóm đồng ý.

## 4. Đã kiểm lại hôm nay

Ghép PR bàn giao với cả 10 PR #40 – #49 (giải xung đột như mục 3) trên một nhánh tạm, không push:

| Kiểm tra | Kết quả |
|---|---|
| `pytest` | 330 passed, 6 skipped, 1 xfailed (C4, giới hạn đã biết) |
| Test chạy trên nuScenes thật (`NUSCENES_ROOT=...`) | 13 passed; test mặt đất trên dữ liệu thật trước luôn bị bỏ qua, nay chạy được |
| Extension (`node --test`, `node --check`) | 7 / 7 passed, cú pháp đúng |
| `pointsnap nuscenes scan --scene scene-0061` | 3 727 box, 31 giây: 6 Lỗi, 36 Cảnh báo, 204 Thông tin; đủ các lớp (`floating`, `fit.*`, `heading.*`, `track.*`, `cam.*`, `lidar.missing`) |
| `--taxonomy spec-vn` + `--config pointsnap/guidelines/spec-vn.yaml` + `--inject` (scene-0103) | Chạy hết; lỗi lún / lơ lửng bỏ sót đều rơi vào box thiếu bằng chứng mặt đất (`floating.no_evidence`), giống bộ class nuScenes |
| Giao diện web (`pointsnap ui`) | Mở được, đọc dự án `cvat-local`; 30 / 30 luật trong guideline có công tắc trên trang Guideline |

Không ghi gì lên CVAT trong lúc kiểm.

## 5. Chỉ số so với mục tiêu G7

Eval 10 vòng mới nhất (`pointsnap eval --rounds 10 --errors all`, sau C8, chưa có #40 – #49), Cảnh báo / Lỗi trên
100 box nhãn sạch:

| | Mục tiêu | Cảnh tinh chỉnh | Cảnh kiểm tra |
|---|---|---|---|
| Báo nhầm | ≤ 2 / ≤ 0,5 | **1,39 / 0,36** (đạt) | **2,88 / 0,57** (chưa đạt) |

Phần lớn báo nhầm còn lại trên cảnh kiểm tra là lơ lửng / lún. Bộ PR an toàn giảm thêm một chút (đo ngày 11/10 trên
`main` cũ: 3,67 / 0,57 → 3,64 / 0,53); cần chạy lại eval một lần sau khi merge để chốt số cho báo cáo.

## 6. Việc còn lại

| Việc | Người | Ghi chú |
|---|---|---|
| Review, merge theo mục 3; quyết #45, #48 | Việt Anh, Huy | Claude không tự merge |
| Chạy lại `pointsnap eval --scenes test --rounds 10 --errors all` **một lần** sau khi merge, ghi số vào `docs/ket-qua/ket-qua-giai-doan-3.md` | Huy | Cổng G7 |
| Hỏi mentor về model làm bằng chứng phụ (Box Verifier lớp 2, 3; Grounding DINO) | Việt Anh | Trước khi đưa vào demo |
| Tạo task spec-vn trên CVAT, cập nhật CAI-DAT bước tạo task spec-vn | Việt Anh | Ghi lên CVAT nên chưa làm |
| Demo / test trên **job 4** (task 4, scene-0061 tạo lại 12/10), không dùng job 2 | Chiến | Job 2 tạo bằng `to-cvat` cũ: 424 / 473 Cảnh báo là `track.reuse_id` |
| TC-70 – TC-80, video demo; hoàn tất [PR #36](https://github.com/AI20K-Build-Phase-Cohort-4A/P-029/pull/36) | Chiến | |
| Xem tay 20 mục mỗi luật mới (`heading.*`, `fit.*`, `lidar.missing`, `attr.height`, `spec.*`); ≥ 40 kết luận Đúng / Báo nhầm trên web | Hân | Precision từng luật |
| Bảng truy vết spec ↔ luật, mục giới hạn, báo cáo, slide | Khánh | Thêm `track.id_swap`, `attr.height`, `spec.inside`, `spec.rider_double`, `attr.rider_state`, `lidar.missing`, `cam.sparse` |

Giới hạn kỹ thuật đã biết (để vào báo cáo, chưa làm):

- Lơ lửng / lún: đoạn chuyển từ đường bằng sang dốc trong một track; vật kê dưới bánh (C4).
- Người vác vật dài > 2 m không có box riêng (spec 4.3B) (C5).
- Sót đối tượng: người đi chậm / đứng lẫn trong nhóm, xe ở xa > 30 m, xe buýt chỉ thấy một phần; vật đứng yên chỉ báo
  khi ảnh camera ban ngày xác nhận (C7, C8).
- Ngưỡng "vật quá ít điểm" của `cam.sparse` chờ nhóm chốt (P-009).

## 7. Cách kiểm lại

```bash
cd source-tool/pointsnap-3d
python -m pytest -q
NUSCENES_ROOT=D:/Vin_uni/data/nuscenes python -m pytest -q tests/test_real_nuscenes.py tests/test_ground.py
cd extension && node --test tests/*.test.js && cd ..
pointsnap nuscenes --dataroot D:/Vin_uni/data/nuscenes scan --scene scene-0061 --out out
pointsnap --config pointsnap/guidelines/spec-vn.yaml nuscenes --taxonomy spec-vn scan --scene scene-0103 --out out --inject
pointsnap ui
```
