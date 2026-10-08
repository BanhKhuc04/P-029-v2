# Nhật ký tuần 04 · 05/10 – 11/10/2026

**Lead tuần này:** @Vũ Bảo Khánh
**Dữ liệu / task CVAT:** nuScenes v1.0-mini (10 cảnh) trên CVAT 2.77.0 chạy Docker local, dùng để làm tool **PointSnap 3D** trong 4 ngày 06/10 – 09/10 ([bản đề xuất](../../source-tool/pointsnap-3d/de-xuat-de-tai.md) · [bảng phân việc](../../source-tool/pointsnap-3d/TASKS.md) · [giao việc theo ngày](../../source-tool/pointsnap-3d/giao-viec/))

> **Phân công:** Việt Anh và Huy làm sản phẩm. **Từ 07/10 phần review và test chuyển cho Khánh, Hân, Chiến** ([PR #20](https://github.com/AI20K-Build-Phase-Cohort-4A/P-029/pull/20)); Việt Anh chuyển sang giảm báo nhầm (A10) và làm giao diện web (A11).
> Cổng: **G0 (06/10)** ✅ · **G1 (07/10)** ✅ · **G2 (08/10)** 🟡 chạy được trọn quy trình, chờ merge PR · **G3 (12h 09/10)** ⬜ · **Nộp cuối ngày 09/10**.
> Mã việc (B1, T1, …) trùng với [`TASKS.md`](../../source-tool/pointsnap-3d/TASKS.md); tiêu chí xong của từng việc ghi ở đó.
> Cập nhật ngày 08/10/2026.

## Thành viên và phân công

| Thành viên | Vị trí | Phân công tuần này |
|---|---|---|
| Khúc Việt Anh | Sản phẩm (phía CVAT, môi trường) | Khung dự án (A1), đọc nuScenes (B1), dữ liệu + CVAT (E1), chuyển nuScenes → CVAT kèm ảnh 6 camera (A2, A2b), adapter CVAT (A3, A4), `scan` + `gate` (A5), tích hợp (A6), lỗi chèn giả (A7), README (A9); từ 07/10: giảm báo nhầm (A10), giao diện web theo dự án (A11) |
| Đặng Văn Huy | Sản phẩm (thuật toán) | Module ground (B2), 3 bộ phát hiện (B3–B5), precision / recall (B6), chốt ngưỡng và chạy đánh giá (B7); review PR của Việt Anh |
| Vũ Bảo Khánh | Lead · Báo cáo | Khung báo cáo và slide (R1), review README, hoàn thiện báo cáo và slide (R2), nhật ký tuần (R3), nộp |
| Nhữ Đình Chiến | Test | Test quy trình trên CVAT theo README (T1), cùng Hân xem tay cảnh báo (T2), video demo (R2) |
| Nguyễn Văn Hân | Test | Chủ trì xem tay cảnh báo và điền bảng chỉ số (T2), phần kết quả đánh giá trong báo cáo |

## Công việc

| # | Nội dung công việc | Người làm | Người kiểm | Hoàn thành | Ghi chú |
|---|---|---|---|---|---|
| 1 | A1 — Khung dự án | @Khúc Việt Anh | @Đặng Văn Huy | ✅ 100% | [PR #1](https://github.com/AI20K-Build-Phase-Cohort-4A/P-029/pull/1) |
| 2 | B1 — Đọc nuScenes ra `Cuboid` | @Khúc Việt Anh | @Đặng Văn Huy | ✅ 100% | [PR #2](https://github.com/AI20K-Build-Phase-Cohort-4A/P-029/pull/2) |
| 3 | E1 — Tải nuScenes; dựng CVAT | @Khúc Việt Anh | — | ✅ 100% | CVAT 2.77.0 Docker local, nuScenes v1.0-mini |
| 4 | A2, A3 — Chuyển cảnh nuScenes → task 3D CVAT; adapter đọc nhãn | @Khúc Việt Anh | @Đặng Văn Huy | ✅ 100% | [PR #4](https://github.com/AI20K-Build-Phase-Cohort-4A/P-029/pull/4), [#5](https://github.com/AI20K-Build-Phase-Cohort-4A/P-029/pull/5), [#7](https://github.com/AI20K-Build-Phase-Cohort-4A/P-029/pull/7) · **G0 đạt 06/10** |
| 5 | B2 — Module ground + kiểm chứng | @Đặng Văn Huy | @Khúc Việt Anh | ✅ 100% | [PR #6](https://github.com/AI20K-Build-Phase-Cohort-4A/P-029/pull/6); không đạt tiêu chí tuyệt đối (trung vị 7,9 cm, p90 22 cm) nên đổi sang so với trung vị của track |
| 6 | B3, B4 — Lơ lửng / lún; sai kích thước | @Đặng Văn Huy | @Khúc Việt Anh | ✅ 100% | [PR #13](https://github.com/AI20K-Build-Phase-Cohort-4A/P-029/pull/13), [#14](https://github.com/AI20K-Build-Phase-Cohort-4A/P-029/pull/14) |
| 7 | A4 — Ghi / gỡ cờ `pointsnap_error` trên CVAT | @Khúc Việt Anh | @Đặng Văn Huy | ✅ 100% | [PR #8](https://github.com/AI20K-Build-Phase-Cohort-4A/P-029/pull/8), [#12](https://github.com/AI20K-Build-Phase-Cohort-4A/P-029/pull/12) · **G1 đạt** |
| 8 | B5, B6 — Đứt track; precision / recall | @Đặng Văn Huy | @Khúc Việt Anh | ✅ 100% | [PR #15](https://github.com/AI20K-Build-Phase-Cohort-4A/P-029/pull/15), [#16](https://github.com/AI20K-Build-Phase-Cohort-4A/P-029/pull/16) |
| 9 | A5, A7, A9 — `scan` + `gate`; lỗi chèn giả; README | @Khúc Việt Anh | @Đặng Văn Huy | ✅ 100% | [PR #9](https://github.com/AI20K-Build-Phase-Cohort-4A/P-029/pull/9), [#10](https://github.com/AI20K-Build-Phase-Cohort-4A/P-029/pull/10), [#11](https://github.com/AI20K-Build-Phase-Cohort-4A/P-029/pull/11) |
| 10 | B7 — Chốt ngưỡng, chạy đánh giá | @Đặng Văn Huy | @Khúc Việt Anh | ✅ 100% | [PR #17](https://github.com/AI20K-Build-Phase-Cohort-4A/P-029/pull/17); chia 5 cảnh tinh chỉnh / 5 cảnh kiểm tra |
| 11 | A6 — Nối 3 bộ phát hiện vào `scan` / `gate` kèm point cloud | @Khúc Việt Anh | @Đặng Văn Huy | 🟡 95% | [PR #18](https://github.com/AI20K-Build-Phase-Cohort-4A/P-029/pull/18) chờ merge; đã chạy trọn quy trình trên CVAT local (job scene-0061) |
| 12 | A2b — Kèm ảnh 6 camera làm ảnh ngữ cảnh cho task 3D | @Khúc Việt Anh | @Đặng Văn Huy | 🟡 95% | [PR #19](https://github.com/AI20K-Build-Phase-Cohort-4A/P-029/pull/19) chờ merge (xếp chồng trên #18) |
| 13 | A10 — Giảm báo nhầm của 3 bộ phát hiện; lệnh `pointsnap eval` | @Khúc Việt Anh | @Đặng Văn Huy | 🟡 80% | [PR #21](https://github.com/AI20K-Build-Phase-Cohort-4A/P-029/pull/21) chờ merge (xếp chồng trên #19); chưa đạt mục tiêu trên cảnh kiểm tra, xem Vướng mắc |
| 14 | A11 — Giao diện web (FastAPI + HTML/JS), guideline theo từng dự án | @Khúc Việt Anh | @Đặng Văn Huy | 🟡 30% | Ngoài kế hoạch ban đầu; kế hoạch đã review, đang code trên branch `feat/A11-web-ui` |
| 15 | R1 — Khung báo cáo và slide | @Vũ Bảo Khánh | — | ⬜ 0% | Hạn tối 08/10 |
| 16 | T1 — Test quy trình trên CVAT theo README | @Nhữ Đình Chiến | @Khúc Việt Anh | ⬜ 0% | Hạn tối 08/10; các bước ở [PR #20](https://github.com/AI20K-Build-Phase-Cohort-4A/P-029/pull/20) |
| 17 | T2 — Xem tay 50 cảnh báo, điền bảng chỉ số | @Nguyễn Văn Hân, @Nhữ Đình Chiến | @Vũ Bảo Khánh | ⬜ 0% | 12h 09/10 · **G3** |
| 18 | R2, R3 — Báo cáo, slide, video demo; nhật ký | @Vũ Bảo Khánh, @Nhữ Đình Chiến | — | 🟡 10% | Cuối ngày 09/10 · **Nộp**; nhật ký đã cập nhật tới 08/10 |

Mức hoàn thành: ✅ xong **và đã qua review** · 🟡 đang làm (ghi %) · ⛔ bị chặn (ghi lý do) · ⬜ chưa bắt đầu

## Tổng kết

*Tình hình đến 08/10; chốt lại sau khi nộp (09/10).*

- **Cổng đạt:**
  - **G0, G1 đạt ngay 06/10**, sớm hơn kế hoạch 1 ngày: cảnh nuScenes hiển thị đúng trên CVAT; có kết quả kiểm chứng ground; lơ lửng / lún và kích thước chạy được; ghi và gỡ được cờ lỗi.
  - **G2 đạt về chức năng:** 07/10 chạy trọn `scan --flag` → lọc box có cờ trong CVAT → sửa → `scan` lại → `gate` trên CVAT local. Ba bộ phát hiện chạy trên cả 10 cảnh; có bộ lỗi chèn giả và lệnh đánh giá. Còn chờ merge PR #18 → #19 → #21 để `main` có đủ.
- **Việc xong:** A1–A9, B1–B7 (PR #1–#17 đã merge); 169 test chạy xanh trên branch A10.
- **Kết quả đánh giá tự động sau A10** (5 cảnh kiểm tra, 5 440 box, 10 vòng chèn lỗi):

  | Chỉ số | Trước A10 | Sau A10 | Mục tiêu |
  |---|---|---|---|
  | Báo nhầm trên nhãn chuẩn / 100 box | 13,24 Cảnh báo · 11,25 Lỗi | 3,80 Cảnh báo · 0,85 Lỗi | ≤ 2 · ≤ 0,5 |
  | Sai kích thước theo class (×0,6; ×1,5; đổi class) | 96% | 96% | ≥ 90% |
  | Nhảy vị trí 2 m / 4 m | 100% / 100% | 92% / 88% | ≥ 90% |
  | Tách ID | 100% | 100% | ≥ 80% |
  | Khoảng nội suy dài (vật đang chạy) | chưa có luật | 100% (6/6) | ≥ 80% |
  | Phân mức đúng | 85% | 84% | ≥ 80% |

  Trên 5 cảnh tinh chỉnh, báo nhầm đã đạt mục tiêu (1,83 Cảnh báo · 0,38 Lỗi / 100 box).
- **Làm thêm ngoài kế hoạch:**
  - Kèm ảnh 6 camera vào task 3D (A2b).
  - Lệnh `pointsnap eval` (A10).
  - Làm lại luật khoảng nội suy dài, vốn đã cắt khỏi kế hoạch.
  - Giao diện web theo từng dự án (A11, đang làm).
- **Việc trễ:** R1 chưa bắt đầu. T1, T2 chưa bắt đầu vì `main` chưa có bản nối detectors.

## Vướng mắc

- **Báo nhầm còn cao.**
  - Trên job scene-0061 trước A10: 116 Lỗi, 135 Cảnh báo / 3 333 box, nên `gate` gần như luôn KHÔNG ĐẠT trên nhãn chuẩn.
  - Sau A10 đã giảm còn 3,80 Cảnh báo · 0,85 Lỗi / 100 box, nhưng vẫn gấp khoảng 2 lần mục tiêu. Phần lớn đến từ luật lơ lửng / lún (3,18 Cảnh báo / 100 box).
- **Lơ lửng / lún chỉ kết luận được ở khoảng 1/4 số box.** LiDAR 32 tia thưa, có bờ vỉa và dốc quanh box. Đo trên box có đủ điểm mặt đất thì bắt được 100% lỗi 40 cm. Đo trên tất cả box thì chỉ bắt được 26%.
- **Nhảy vị trí 4 m giảm còn 88%** sau khi giảm báo nhầm, dưới mục tiêu 90%.
- **4 PR đang chờ merge** (#18 → #19 → #21 xếp chồng, và #20 giao việc). Cần Huy review và merge theo đúng thứ tự trong sáng 09/10 để người test chạy trên `main`.
- **G3 (12h 09/10) có rủi ro:** T1, T2 chưa bắt đầu. Nếu không kịp xem tay đủ 50 cảnh báo thì báo cáo dùng số liệu tự động, ghi rõ số mục đã xem tay.
- **A11 có thể không kịp trước khi nộp.** Nếu chưa xong thì quay video demo bằng CLI, đưa giao diện web vào hướng phát triển.

## Kế hoạch tuần sau

- **Sáng 09/10:** merge #18 → #19 → #21, #20. Chiến chạy T1, Hân và Chiến xem tay cảnh báo (T2).
- **12h 09/10 (G3):** chốt `docs/danh-gia.md` đủ chỉ số mục 8 của đề xuất.
- **Chiều 09/10:** Khánh điền số liệu vào báo cáo và slide, Chiến quay video demo 3–5 phút, chốt nhật ký và nộp.
- **Sau khi nộp:**
  - Hoàn thiện A11 (giao diện web, guideline theo dự án).
  - Tiếp tục giảm báo nhầm lơ lửng / lún.
  - Các phần đã cắt chuyển sang hướng phát triển: bộ lỗi thật, lệnh `diff`, đo thời gian review, đọc point cloud qua API CVAT.
