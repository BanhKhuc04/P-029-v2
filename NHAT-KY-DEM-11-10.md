# Nhật ký phát triển PointSnap 3D — đêm 11/10 → 6:00 sáng 12/10

Claude tự chọn việc, tự code, tự kiểm thử. File này ở **ngoài repo** (không commit). Quy tắc giữ suốt đêm:

- Mỗi việc một nhánh + PR vào `main`, reviewer `imvhuy`, **không merge**, không push thẳng `main`.
- Không ghi gì lên CVAT. Không động vào thay đổi của phiên khác trong `D:\Vin_uni\P-029\P-029` (nhánh
  `feat/C3-verifier-geometry`: C4 lơ lửng trên mặt đất không phẳng, C5 tình huống thực tế, C6 bám spec) — mọi việc làm
  trong worktree riêng. Mọi PR dưới đây đều merge sạch với nhánh đó (đã thử `git merge-tree`).
- Chọn tham số chỉ trên 5 cảnh tinh chỉnh; 5 cảnh kiểm tra chạy **một lần** cho bản cuối.
- Không sửa `ring_ground_for_box` (việc C4).

## PR đã mở (giờ = giờ commit)

| Giờ | PR | Việc | Kết quả trên 5 cảnh kiểm tra |
|---|---|---|---|
| 22:08, 22:33 | [#40](https://github.com/AI20K-Build-Phase-Cohort-4A/P-029/pull/40) | Lớp camera: tùy chọn Grounding DINO + SAM 2.1 và `hybrid` (Mask R-CNN + Grounding DINO chỉ cho cọc tiêu); script `scripts/eval_camera.py` | `hybrid`: phủ 25% → 28%, bắt thêm ~20% box dời / ~13% box co, báo nhầm 0,75 → 0,77. Mặc định vẫn `maskrcnn` |
| 22:22, 04:50 | [#41](https://github.com/AI20K-Build-Phase-Cohort-4A/P-029/pull/41) | `track.jump`: ngưỡng hai đầu track theo khoảng ngoại suy (trừ vật đứng yên); track 3 box đổ lỗi đúng box giữa | Báo nhầm 0,22 / 0,07 → 0,17 / 0,06; nhảy 4 m 95% → **100%**, 2 m 94% → 98%. Job 2 so với xem tay của Chiến: Đúng 6/6 → 5/6, Báo nhầm 2 → **0** |
| 22:31 | [#42](https://github.com/AI20K-Build-Phase-Cohort-4A/P-029/pull/42) | `heading.motion` bỏ khi không có pose; `heading.points` so modulo 90° đúng | Job 2 quét không có point cloud: **886 → 0** báo nhầm; eval nuScenes giống hệt `main` |
| 22:48 | [#43](https://github.com/AI20K-Build-Phase-Cohort-4A/P-029/pull/43) | Box Critic huấn luyện ensemble 5 model (`--ensemble`) | Báo nhầm 0,18 → 0,13 / 100 box, bắt 64 → 69 / 436 lỗi chèn |
| 04:08 | [#44](https://github.com/AI20K-Build-Phase-Cohort-4A/P-029/pull/44) | Tăng tốc `OtherBoxPoints` (tìm điểm theo x đã sắp, trả điểm cục bộ quanh box) | Quét 3 cảnh 44,9 s → **13,4 s**, 391 mục giống hệt `main` |
| 04:11 | [#45](https://github.com/AI20K-Build-Phase-Cohort-4A/P-029/pull/45) | `heading.points` cảnh báo từ 12° (trước 15°) — **cần nhóm quyết** vì tăng báo nhầm | Box xoay 15° bắt 38% → **86%**, báo nhầm 0,17 → 0,29 / 100 box |
| 04:12 | [#46](https://github.com/AI20K-Build-Phase-Cohort-4A/P-029/pull/46) | CAI-DAT nhắc bỏ *Read only* khi tạo token (CHIEN-01); slug / run_id dùng `fullmatch` | — |
| 04:18 | [#47](https://github.com/AI20K-Build-Phase-Cohort-4A/P-029/pull/47) | `fit.loose` so khoảng dư với các frame khác của track, ngưỡng 0,5 → 0,4 m | Báo nhầm 0,26 → 0,28, box phóng x1,15 bắt 23% → **37%**, x1,3 49% → 52% |
| 04:25 | [#48](https://github.com/AI20K-Build-Phase-Cohort-4A/P-029/pull/48) | `fit.outside` nhạy hơn (15 điểm ngoài box, vượt trung vị track 40 điểm %); tách `outside_min_object_points` — **cần nhóm quyết** | Báo nhầm 0,04 → 0,24; dời 0,5 m 19% → 30%, co x0,85 18% → **36%**, x0,7 54% → **72%** |

Cả 9 nhánh (PR #40 – #48) và `feat/C3-verifier-geometry`: 45 cặp đều merge sạch; ghép cả 9 PR vào một nhánh tạm (không
push) thì `pytest` 270 passed.

Tạm dừng 22:50 – 04:00 (hết hạn mức sử dụng). CI của PR #40 – #43 xanh lúc 04:04.

## Tổng tác động khi merge (pointsnap eval đầy đủ, mặc định, 10 vòng)

Ghép PR vào nhánh tạm (không push) rồi chạy `pointsnap eval`. Báo nhầm trên nhãn sạch, Cảnh báo / Lỗi trên 100 box:

| | Cảnh kiểm tra | Cảnh tinh chỉnh |
|---|---|---|
| `main` | 3,67 / 0,57 | 1,99 / 0,36 |
| **Bộ an toàn: #40 – #44, #46, #47** | **3,64 / 0,53** | **1,98 / 0,31** |
| Cả 9 PR (thêm #45, #48) | 3,93 / 0,59 | 2,10 / 0,32 |

- **Bộ an toàn** giảm báo nhầm ở cả hai bộ cảnh và tăng bắt lỗi: nhảy 4 m 100%, box phóng x1,15 23% → 37% (`fit.loose`),
  Box Critic báo nhầm ít hơn 28%, quét nhanh gấp ~2,4 – 3,3 lần (job 2: 24 s → 10 s). Nên merge trước.
- **#45, #48** đổi báo nhầm lấy tỉ lệ bắt (xoay 15°: 38% → 86%; co x0,85: 18% → 36%, x0,7: 54% → 72%) — nhóm quyết.
- Phân mức đúng giữ nguyên (100% kiểm tra, 90% tinh chỉnh). Phần lớn báo nhầm còn lại là lơ lửng / lún (2,41 / 100 box
  trên cảnh kiểm tra, việc C4).
- Eval 10 vòng chỉ có 6 – 22 mẫu mỗi mức lỗi; số liệu tỉ lệ bắt chi tiết của từng PR lấy từ các script đo riêng (hàng
  trăm – hàng nghìn mẫu), ghi trong mô tả PR.

## Sáng 12/10 (sau 08:30)

- Xử lý góp ý của bot review (`phoenix-mentor`):
  - #40: chỉ dùng autocast fp16 khi chạy GPU; đọc `text_labels` không chạm khóa `labels` (hết FutureWarning). Đã chạy
    thật Grounding DINO + SAM 2.1 trên GPU (37 vật) và CPU (36 vật).
  - #43: đưa từng model ensemble về CPU sau khi huấn luyện; đã chạy thử ensemble 2 × 2 epoch, xuất TorchScript được.
  - #45, #48: hai script đo báo cách chạy khi thiếu tham số / `NUSCENES_ROOT`.
  - Không sửa: #41 (tốc độ vô cực khi `dt = 0` — hai keyframe khác nhau luôn có `dt > 0`), #44 (`own` tính trên chính
    `idx`, có test so với cách lọc cũ), #47 (bot tự kết luận logic đúng), #48 (`outside_warning_ratio` có được đọc).
- Chạy thử luồng quét của giao diện web (API thật, dự án `cvat-local` sao ra thư mục tạm, không gắn cờ) với code ghép cả
  9 PR, `camera.model: hybrid`, Box Critic v3: job 2 xong sau 20 s, không lỗi; xem trước point cloud, báo cáo HTML / CSV,
  link CVAT đều chạy. 424 / 473 Cảnh báo vẫn là `track.reuse_id` do task 2 được tạo bằng `to-cvat` cũ — cần tạo lại task
  (ghi lên CVAT nên chưa làm).

## Tạo lại task scene-0061 trên CVAT (09:40 – 10:00, được bạn đồng ý)

- CVAT local đang tắt vì Docker Desktop không khởi động được: file socket cũ
  `%LOCALAPPDATA%\docker-secrets-engine\engine.sock` bị khóa (lỗi đã biết của Docker Desktop; máy đã có một thư mục
  `docker-secrets-engine.stale` từ lần trước). Sửa: tắt Docker Desktop, đổi tên thư mục thành
  `docker-secrets-engine.stale-20261012`, mở lại — **không** chọn "Reset to factory defaults". Rồi `docker compose up -d`.
- `pointsnap nuscenes to-cvat --scene scene-0061 --upload` (code `main`) → **task 4 / job 4**, bản xuất ở
  `D:/Vin_uni/data/cvat-v2/scene-0061`. **Task 2 giữ nguyên**, không xóa.
- Quét chỉ đọc: job 2 có 7 Lỗi / 473 Cảnh báo (424 là `track.reuse_id` do task tạo bằng `to-cvat` cũ); **job 4: 8 Lỗi /
  44 Cảnh báo**, không còn `track.reuse_id`. Từ giờ nên test / demo trên **job 4**.
- Dự án `cvat-local` thêm thư mục bản xuất `D:/Vin_uni/data/cvat-v2` (bản cũ: `project.json.bak-before-cvat-v2`).

## C4: lơ lửng / lún trên mặt đất dốc (10:00 – 11:00) — [PR #49](https://github.com/AI20K-Build-Phase-Cohort-4A/P-029/pull/49)

- Test tổng hợp 15 ca (dốc dọc / ngang 0 – 10°, lơ lửng / lún trên dốc, đá, bậc vỉa hè, một phía, đoạn chuyển trong
  track): code cũ sai 7 ca; PR đúng 14, ca đoạn chuyển trong track ghi xfail (giới hạn đã biết).
- Mặt phẳng khớp trên vành đai hẹp rất nhiễu trên LiDAR thật (nuScenes mini, đường gần như bằng: độ dốc khớp được trung
  vị 3°, p90 7°). Dùng mặt phẳng cho mọi box tăng báo nhầm (dốc ≥ 2°: Lỗi 0,24 → 0,55 / 100 box) → chỉ dùng điểm tiếp xúc
  trên mặt phẳng dốc ≥ 5° cho **box không có track để so**.
- Cảnh tinh chỉnh: giống hệt cũ (1,41 / 0,24; bắt 31 / 90 / 99%). Cảnh kiểm tra (một lần): 2,41 / 0,31 → 2,39 / 0,37.
- Ghép với #44: luật lơ lửng trên scene-0061 22,5 s → 4,7 s, cùng 127 mục; `pytest` 272 passed, 1 xfailed.
- Chưa làm: đoạn chuyển bằng → dốc trong track; vật kê dưới bánh (cần điểm của chính vật).

## Thay đổi trên máy (ngoài repo)

- Dự án `cvat-local` (`~/.pointsnap/projects/cvat-local/guideline.yaml`) dùng Box Critic v3
  `D:/Vin_uni/data/models/critic-v3-ens5-holdout0916.pt` (ngưỡng 5,3 / 6,7). Bản trước: `guideline.yaml.bak-before-critic-v3`
  (v2), `guideline.yaml.bak-before-critic` (chưa bật Critic).
- `.venv` cài thêm `transformers` (cho `camera.model: gdino-sam2` / `hybrid`). Trọng số Grounding DINO + SAM 2.1 đã tải về
  bộ đệm Hugging Face; kết quả nhận diện 2 424 ảnh nuScenes mini nằm trong `~/.pointsnap/cache/det2d`.

## Ghi chú cho người review

- PR #45 và #47 cùng tăng nhẹ báo nhầm Cảnh báo; #41 giảm. Tổng Cảnh báo trên nhãn sạch đang 1,99 (tinh chỉnh) / 3,42
  (kiểm tra) so với mục tiêu ≤ 2,0, phần lớn do lơ lửng / lún (việc C4).
- Commit `2482d4e` (ngưỡng lơ lửng 12 → 15 cm) vẫn chỉ nằm trên `feat/C3-verifier-geometry`, chưa có PR vào `main`.
- Lơ lửng / lún còn chậm nhất khi quét (`static_sweep_points`, `ring_ground_for_box`) — để lại cho C4.

## Bàn giao (14:30 – 15:30) — [PR #50](https://github.com/AI20K-Build-Phase-Cohort-4A/P-029/pull/50)

- Nhánh `feat/ban-giao-giai-doan-3` = `feat/C3-verifier-geometry` (C3 15 cm, giao việc C4, C5 – C8 chưa có PR) + extension
  nhận `lidar.missing` / `cam.sparse` + test mặt đất thật đọc `NUSCENES_ROOT` + `docs/ban-giao-12-10.md`, `TASKS.md`,
  `tuan-gia-han.md`.
- Ghép với cả 10 PR #40 – #49: pytest 330 passed, 6 skipped, 1 xfailed; extension 7 / 7; quét scene-0061 31 s đủ các lớp.
- #40 nay xung đột với PR #50 (config.py, test_camera.py — giữ cả hai bên; scanner dùng `effective_model()` cho
  `cam.sparse`, `lidar.missing`). Các PR khác sạch. Thứ tự merge: #50 → #44, #42, #41, #46, #43, #47 → #49 → #40 → #45, #48.
