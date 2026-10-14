# PointSnap 3D — Bảng phân việc (4 ngày: 06/10 – 09/10/2026)

> **Tiến độ hiện hành 14/10/2026:** xem [báo cáo hợp nhất và nghiệm thu](../../../review/2026-10-14/project-progress.md). Các bảng bên dưới giữ mốc lịch sử; code/test tự động và nghiệm thu chất lượng/UI được báo riêng. G7 dùng precision chấm tay theo từng luật, proxy riêng; G8 còn cần luồng MV3 sửa–Save–quét lại và hồ sơ demo.

> Cập nhật 13/10: [bàn giao hiện hành](../../../review/2026-10-13/handoff-final-report.md) phân biệt sửa code, test và nghiệm thu. C4 không còn XFAIL trong bộ hồi quy hợp nhất; số 14/15, 1 XFAIL bên dưới là lịch sử. G7, precision các luật mới và MV3 sau reload vẫn có giới hạn riêng.

> Đối chiếu 11/10/2026: các trạng thái bên dưới là ghi nhận của người phụ trách ở từng thời điểm. Mã nguồn có A14/A15 và C1/C2; trạng thái chờ review không tự chứng minh chưa có code, trạng thái xong không thay thế nghiệm thu. Kết quả kiểm tra hiện hành và phần chưa xác minh: [review phần 01](../../../review/2026-10-10/01-report.md).

Chia nhỏ [kế hoạch 4 ngày](../docs/thiet-ke/de-xuat-de-tai.md#7-kế-hoạch-triển-khai) thành từng việc có người phụ trách, hạn, việc phụ thuộc và tiêu chí xong.
Việc của từng người theo ngày: [`giao-viec/`](giao-viec/). Cập nhật cột **Trạng thái** mỗi khi bắt đầu hoặc xong một việc.

**Phân công:** **Việt Anh và Huy làm toàn bộ sản phẩm** (môi trường, dữ liệu, code, tự kiểm). **Khánh, Chiến, Hân viết báo cáo, và test khi sản phẩm xong** (sau cổng G2).

*Trạng thái:* ⬜ chưa làm · 🟡 đang làm · 🔍 chờ review · ✅ xong · ⛔ bị chặn (ghi lý do)

## Quy trình làm việc

1. **Mỗi việc một branch**, đặt tên theo mã việc: `feat/A3-cvat-reader`, `fix/B3-floating-ring`, `docs/...`.
2. **Xong thì mở Pull Request**; người code còn lại review rồi mới merge vào `main`.
3. **Không ai push thẳng lên `main`**, kể cả tài liệu.
4. **Việt Anh và Huy họp nhanh 10 phút đầu mỗi ngày:** hôm qua xong gì, hôm nay làm gì, đang kẹt gì.
5. **Không có ngày dự phòng:** trễ thì cắt theo thứ tự ở [mục 7 của đề xuất](../docs/thiet-ke/de-xuat-de-tai.md#7-kế-hoạch-triển-khai), không dời cổng.
6. **Tiêu chí xong chung cho mọi việc code:**
   - `pytest` chạy xanh; việc mới có test đi kèm.
   - Không commit token, dữ liệu nuScenes, file sinh ra (`.pcd`, báo cáo, bản chụp).
   - Đổi quy ước tọa độ hay định dạng thì cập nhật [`CONVENTIONS.md`](../CONVENTIONS.md) trong cùng PR.

## Cổng kiểm soát

| Cổng | Hạn | Điều kiện đạt | Người kiểm |
|---|---|---|---|
| **G0** | Tối 06/10 (muộn nhất 10h 07/10) | 1 cảnh nuScenes hiển thị đúng trên CVAT với nhãn chuẩn; `CONVENTIONS.md` đã chốt hệ tọa độ | Việt Anh, Huy |
| **G1** | Cuối ngày 07/10 | Có kết quả kiểm chứng ground (đạt / không đạt); phát hiện lơ lửng/lún và kích thước chạy trên 1 cảnh; ghi được cờ lỗi lên CVAT | Việt Anh, Huy |
| **G2** | Cuối ngày 08/10 | **Sản phẩm xong**: trọn quy trình `scan --flag` → lọc trong CVAT → `gate`; 3 bộ phát hiện chạy trên cả bản mini; có bộ lỗi chèn giả và script đánh giá; README cài đặt chạy được. Báo cho Khánh, Chiến, Hân bắt đầu test | Việt Anh, Huy |
| **G3** | 12h 09/10 | Đã test xong; có số liệu cho mọi chỉ số ở mục 8 của đề xuất | Khánh, Chiến, Hân |
| **Nộp** | Cuối ngày 09/10 | Code, README, video demo, báo cáo kết quả, slide | Khánh |

## Khúc Việt Anh — code phía CVAT + môi trường

| Mã | Việc | Hạn | Cần trước | Tiêu chí xong | Trạng thái |
|---|---|---|---|---|---|
| **A1** | Khung dự án: package `pointsnap`, mô hình dữ liệu, hình học, cấu hình, CLI, `CONVENTIONS.md` | 05/10 | — | `pip install -e .`; `pointsnap --help`; test xanh | ✅ [PR #1](https://github.com/AI20K-Build-Phase-Cohort-4A/P-029/pull/1) |
| **B1** | Đọc nuScenes: keyframe, point cloud `LIDAR_TOP`, pose xe thu, nhãn chuẩn → `Cuboid` trong hệ LiDAR | 06/10 | A1 | Test trên bộ dữ liệu giả xanh; số box mỗi frame khớp nuScenes thật | ✅ [PR #2](https://github.com/AI20K-Build-Phase-Cohort-4A/P-029/pull/2) |
| **E1** | Môi trường: tải nuScenes v1.0-mini (~4 GB); dựng CVAT Docker local, tạo admin và access token | 06/10 | — | Mở được `localhost:8080`; thư mục dữ liệu đủ `samples/`, `v1.0-mini/` | ✅ |
| **A2** | Chuyển 1 cảnh nuScenes → CVAT: `.pcd`, task 3D có sẵn thuộc tính `pointsnap_error` và `reviewed`, nạp nhãn chuẩn dạng track; tự kiểm bằng mắt | 06/10 | B1, E1 | Box xe, người, xe đạp hiển thị đúng vị trí, kích thước, hướng (G0) | ✅ (G0 đạt) |
| **A3** | Adapter CVAT đọc nhãn (shape, track, keyframe, `outside`); point cloud từ thư mục nuScenes theo ánh xạ frame ↔ `sample_token`. Xác minh trên CVAT thật: trục, yaw, `outside`, link mở frame → ghi `CONVENTIONS.md` | 07/10 | A2 | Đọc lại nhãn đã nạp, so với nhãn gốc: lệch tâm < 1 mm, lệch yaw < 0,001 rad | ✅ (làm sớm) |
| **A4** | Lưu bản chụp JSON; ghi / xóa thuộc tính `pointsnap_error` theo id (PATCH) | 07/10 | A3 | Ghi rồi đọc lại khớp; hình học box không đổi; lọc được box có cờ trong màn 3D (G1) | ✅ |
| **A5** | `scan` (báo cáo HTML/CSV, link mở frame) và `gate` (exit code 0/1) | 08/10 | A3 | Báo cáo mở được, link đúng frame; `gate` trả đúng mã trên job có lỗi và job sạch | ✅ |
| **A6** | Tích hợp end-to-end trên CVAT | 08/10 | A4, A5, B3–B5 | Demo G2 | ✅ |
| **A7** | Bộ chèn lỗi giả theo mục 8.1 của đề xuất, kèm file log lỗi đã chèn | 08/10 | B1 | Chèn đúng loại, đúng mức; log khớp với nhãn sau khi chèn | ✅ |
| **A9** | README cài đặt và hướng dẫn chạy cho người test; đóng gói | 08/10 | A6 | Người khác cài và chạy được theo README (G2) | ✅ |
| **A2b** | Kèm ảnh 6 camera làm ảnh ngữ cảnh cho task 3D trên CVAT | 07/10 | A2 | Task 3D hiện ảnh camera cạnh point cloud | ✅ [PR #19](https://github.com/AI20K-Build-Phase-Cohort-4A/P-029/pull/19) |
| **A10** | Giảm báo nhầm của 3 bộ phát hiện (`pointsnap/detectors/`), đánh giá lại | 08/10 | A6, B7 | Nhãn chuẩn: ≤ 2 Cảnh báo, ≤ 0,5 Lỗi / 100 box; recall không giảm | ✅ [PR #21](https://github.com/AI20K-Build-Phase-Cohort-4A/P-029/pull/21) |
| **A11** | Giao diện web (FastAPI + HTML/JS) thay CLI; hồ sơ guideline theo từng dự án (class, ngưỡng, luật bật/tắt, tiêu chí `gate`, kết nối CVAT) | 09/10 | A6 | Tạo dự án, quét job, xem / lọc lỗi, gắn cờ, `gate` trên giao diện | ✅ [PR #23](https://github.com/AI20K-Build-Phase-Cohort-4A/P-029/pull/23) |
| **A13** | Làm lại giao diện web theo thiết kế phần mềm doanh nghiệp (thanh trên navy, dropdown dự án, 2 nhóm menu, bảng chi tiết kết quả, IBM Plex, theme sáng/tối) | 08/10 | A11 | Đầy đủ chức năng, khớp bản vẽ `.dc.html`, chụp ảnh sáng/tối, test xanh | ✅ [PR #28](https://github.com/AI20K-Build-Phase-Cohort-4A/P-029/pull/28) |
| **A14** | Màn chào có nút Bắt đầu (logo động khi tải); Duyệt nhanh: xem point cloud quanh box (từ trên, nhìn ngang), J / K chuyển mục, ghi kết luận Đúng / Báo nhầm (`reviews.json`, precision xem tay); hướng dẫn sửa hàng loạt trong CVAT bằng bộ lọc | 08/10 | A13 | Duyệt hết lỗi của một job mà không mở lại CVAT; test xanh | ✅ [PR #29](https://github.com/AI20K-Build-Phase-Cohort-4A/P-029/pull/29) |
| **A15** | Extension "PointSnap cho CVAT" (Chrome / Edge, Manifest V3): tự bật bộ lọc box có `pointsnap_error`, thông báo lỗi khi chọn box, Lỗi tiếp theo / trước không tải lại trang, danh sách lỗi + Quét lại qua API PointSnap — chỉ đọc giao diện và bấm hộ nút, không đụng nội bộ CVAT (đề xuất mục 4.6) | 11/10 | A14 | Đạt spike S1–S4 (G4) và tiêu chí xong mục 4.6 trên CVAT local job 2 (kết quả: `docs/ket-qua/thu-extension.md`) | ✅ [PR #31](https://github.com/AI20K-Build-Phase-Cohort-4A/P-029/pull/31) |

## Đặng Văn Huy — code thuật toán

| Mã | Việc | Hạn | Cần trước | Tiêu chí xong | Trạng thái |
|---|---|---|---|---|---|
| **B2** | Module ground: lưới min-Z + RANSAC, mặt phẳng cục bộ trong vành đai quanh box; kiểm chứng trên ~200 box chuẩn và xem bằng mắt vài cảnh | Sáng 07/10 | A1, B1; dữ liệu nuScenes trên máy Huy | Point cloud giả: sai số < 2 cm; nuScenes: có trung vị, p90, ghi các chỗ ground sai | ✅ [PR #6](https://github.com/AI20K-Build-Phase-Cohort-4A/P-029/pull/new/feat/B2-ground-module) |
| **B3** | Phát hiện lơ lửng / lún, kèm test có đáp án (vd nâng đáy box 25 cm → Lỗi ~25 cm) | 07/10 | B2 | Test xanh; ghi "thiếu bằng chứng" khi vành đai ít điểm | ✅ [PR #7](https://github.com/AI20K-Build-Phase-Cohort-4A/P-029/pull/new/feat/B3-floating-detector) |
| **B4** | Thống kê kích thước theo class (tự chốt khoảng cho `bus`, `trailer`, `construction_vehicle`) + phát hiện sai kích thước, kèm test có đáp án | 07/10 | B1 | Test xanh; không báo người đi bộ ở kiểu trong track | ✅ [PR #8](https://github.com/AI20K-Build-Phase-Cohort-4A/P-029/pull/new/feat/B4-size-detector) |
| **B5** | Phát hiện đứt track: nhảy vị trí, tách ID, kèm test có đáp án | 08/10 | B1 | Test xanh; chỉ báo frame lệch lớn nhất trong cụm | ✅ [PR #9](https://github.com/AI20K-Build-Phase-Cohort-4A/P-029/pull/new/feat/B5-track-detector) |
| **B6** | Script precision / recall theo loại lỗi và mức độ | 08/10 | A7 | Ra bảng chỉ số mục 8 từ log lỗi chèn + kết quả quét | ✅ [PR #10](https://github.com/AI20K-Build-Phase-Cohort-4A/P-029/pull/new/feat/B6-precision-recall) |
| **B7** | Chốt ngưỡng trên 5 cảnh tinh chỉnh; chạy đánh giá trên 5 cảnh kiểm tra | Sáng 09/10 | B6 | Ngưỡng ghi vào `config.yaml`; bảng số liệu gửi người test | ✅ [PR #11](https://github.com/AI20K-Build-Phase-Cohort-4A/P-029/pull/new/feat/B7-thresholds-and-eval) |
| **B8** | Giảm báo nhầm lơ lửng/lún (thử gộp sweeps LiDAR, chỉnh luật) và nâng phát hiện nhảy 4 m; chỉnh trên cảnh tinh chỉnh, chạy `eval --scenes test` một lần | 11/10 | B7, A10 | Nhãn sạch ≤ 2 Cảnh báo, ≤ 0,5 Lỗi / 100 box; nhảy 4 m ≥ 90%; recall khác không giảm | 🟡 Nhảy 4 m 100% ([PR #41](https://github.com/AI20K-Build-Phase-Cohort-4A/P-029/pull/41)); mặt đất v2 (PR #37) và C4 ([PR #49](https://github.com/AI20K-Build-Phase-Cohort-4A/P-029/pull/49)) giảm lơ lửng / lún. Sau khi merge 12/10: cảnh tinh chỉnh 1,45 / 0,31 đạt; cảnh kiểm tra 2,98 / 0,59 còn vượt (chủ yếu lơ lửng / lún) |

## Giai đoạn 3 — tuần gia hạn 11/10 – 17/10 (nộp 18/10)

Việc từng người và cổng G6 – G8: [`quan-ly/giao-viec/tuan-gia-han.md`](giao-viec/tuan-gia-han.md). Tình trạng bàn giao ngày 12/10,
thứ tự merge và cách kiểm lại: [`quan-ly/ban-giao-12-10.md`](ban-giao-12-10.md).

| Mã | Việc | Tiêu chí xong | Trạng thái |
|---|---|---|---|
| **C1** | Sai hướng box (`heading.*`), box lệch khỏi vật (`fit.*`), mặt đất v2 | Lật / xoay 90° bắt 100%; số liệu `docs/ket-qua/ket-qua-giai-doan-3.md` | ✅ [PR #37](https://github.com/AI20K-Build-Phase-Cohort-4A/P-029/pull/37) |
| **C2** | Track theo spec 4.4 (occluded, `track.reuse_id`), thuộc tính (`attr.*`), bộ class spec-vn | Demo trên task spec-vn | ✅ [PR #37](https://github.com/AI20K-Build-Phase-Cohort-4A/P-029/pull/37) |
| **C3** | Box Verifier 4 lớp: vật đứng yên, ảnh camera, Box Critic, học từ kết luận | Số liệu `docs/ket-qua/ket-qua-box-verifier.md` | ✅ [PR #39](https://github.com/AI20K-Build-Phase-Cohort-4A/P-029/pull/39); ngưỡng lơ lửng 15 cm trong [PR #50](https://github.com/AI20K-Build-Phase-Cohort-4A/P-029/pull/50) |
| **C4** | Lơ lửng / lún trên mặt đất dốc, đá, vỉa hè ([giao việc](giao-viec/C4-mat-dat-nghieng.md)) | Test tổng hợp đúng hết; báo nhầm `floating` trên cảnh tinh chỉnh không tăng; recall không giảm | ✅ [PR #49](https://github.com/AI20K-Build-Phase-Cohort-4A/P-029/pull/49) (14 / 15 ca, 1 xfail đã biết) |
| **C5** | Tình huống giao thông thực tế ([giao việc](giao-viec/C5-tinh-huong-thuc-te.md)): bộ mô phỏng tình huống, `track.id_swap` | Test mô phỏng đúng hết; eval 10 vòng không tăng báo nhầm, không giảm recall | ✅ [PR #50](https://github.com/AI20K-Build-Phase-Cohort-4A/P-029/pull/50) (23 / 23 tình huống; đổi ID bắt 94%, 0 báo nhầm) |
| **C6** | Bám spec theo hình học ([giao việc](giao-viec/C6-bam-spec.md)): `attr.height`, `spec.inside`, `spec.rider_double` | Như C5 | ✅ [PR #50](https://github.com/AI20K-Build-Phase-Cohort-4A/P-029/pull/50) (báo nhầm 0,03 / 0,02 trên 100 box; bắt đổi tư thế 91–95%, người trong xe 100%) |
| **C7** | Sót đối tượng bằng LiDAR `lidar.missing` | Như C5; số liệu `docs/ket-qua/ket-qua-sot-doi-tuong.md` | ✅ [PR #50](https://github.com/AI20K-Build-Phase-Cohort-4A/P-029/pull/50) (tìm lại vật bị xóa box 66% / 71%, 1 mục báo nhầm / 5 cảnh) |
| **C8** | Sót vật đứng yên (LiDAR + ảnh), `attr.rider_state`, `cam.sparse` | Như C5 | ✅ [PR #50](https://github.com/AI20K-Build-Phase-Cohort-4A/P-029/pull/50) (vật đứng yên tìm lại 31% / 15%; eval kiểm tra 2,85 → 2,88) |
| — | Cải tiến sau đánh giá đêm 11/10: camera Grounding DINO + SAM 2.1, `track.jump` hai đầu track, `heading.motion` khi không có pose, Box Critic ensemble, quét nhanh ~3 lần, CAI-DAT token | Mỗi PR có số liệu trước / sau | ✅ [#40](https://github.com/AI20K-Build-Phase-Cohort-4A/P-029/pull/40) · [#41](https://github.com/AI20K-Build-Phase-Cohort-4A/P-029/pull/41) · [#42](https://github.com/AI20K-Build-Phase-Cohort-4A/P-029/pull/42) · [#43](https://github.com/AI20K-Build-Phase-Cohort-4A/P-029/pull/43) · [#44](https://github.com/AI20K-Build-Phase-Cohort-4A/P-029/pull/44) · [#46](https://github.com/AI20K-Build-Phase-Cohort-4A/P-029/pull/46) · [#47](https://github.com/AI20K-Build-Phase-Cohort-4A/P-029/pull/47) |
| — | Đổi ngưỡng lấy tỉ lệ bắt (tăng báo nhầm): `heading.points` 12°, `fit.outside` nhạy hơn | **Nhóm quyết** có merge không | ✅ [#45](https://github.com/AI20K-Build-Phase-Cohort-4A/P-029/pull/45) đã merge (12/10); 🔍 [#48](https://github.com/AI20K-Build-Phase-Cohort-4A/P-029/pull/48) để ngỏ (báo nhầm `fit.outside` 0,04 → 0,24) |

## Khánh, Chiến, Hân — báo cáo và test (khi sản phẩm xong)

**Từ 07/10 phần review và test do Khánh, Hân, Chiến làm** (quy trình đã chạy được trên CVAT). Các bước chi tiết: [`quan-ly/giao-viec/review-test.md`](giao-viec/review-test.md).

| Mã | Việc | Người | Hạn | Cần trước | Tiêu chí xong | Trạng thái |
|---|---|---|---|---|---|---|
| **R1** | Khung báo cáo kết quả và slide: bối cảnh, vấn đề, giải pháp, cách đánh giá (lấy từ bản đề xuất), để trống phần số liệu | Khánh | Tối 08/10 | — | `docs/bao-cao-ket-qua.md` + slide khung | ⬜ |
| **T1** | Test quy trình trên CVAT theo README: cài trên máy khác, `scan --flag`, lọc box lỗi trong CVAT, sửa vài box, `scan` lại, `gate`; ghi lỗi gặp phải | Chiến | Sáng 09/10 | G2 | Danh sách lỗi gửi Việt Anh; README không còn chỗ thiếu | ⬜ |
| **T2** | Test thuật toán: xem tay các cảnh báo không khớp lỗi chèn nào (đúng hay báo nhầm); điền bảng chỉ số | Hân (chủ trì), Chiến | 12h 09/10 | B7 | `docs/ket-qua/danh-gia.md` đủ mọi chỉ số mục 8 (G3) | ⬜ |
| **R2** | Hoàn thiện báo cáo kết quả, slide (điền số liệu từ T2); quay video demo 3–5 phút | Khánh (báo cáo, slide), Chiến (video) | Cuối ngày 09/10 | G3 | Đủ hồ sơ nộp | ⬜ |
| **R3** | Nhật ký tuần 04: ghi kết quả các cổng, việc trễ, việc cắt | Khánh | Cuối ngày 09/10 | — | Nhật ký chốt | ⬜ |

## Đã cắt khỏi kế hoạch 4 ngày

Tự gán nhãn lại một cảnh (bộ lỗi thật), lệnh `diff`, đo thời gian review, luật khoảng nội suy dài, so khớp hai adapter, đọc point cloud qua API của CVAT. Xem [Hướng phát triển](../docs/thiet-ke/de-xuat-de-tai.md#11-hướng-phát-triển).
