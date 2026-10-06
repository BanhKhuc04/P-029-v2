# Nhật ký tuần 04 · 05/10 – 11/10/2026

**Lead tuần này:** @Vũ Bảo Khánh
**Dữ liệu / task CVAT:** nuScenes v1.0-mini trên CVAT Docker local, dùng để làm tool **PointSnap 3D** trong 4 ngày 06/10 – 09/10 ([bản đề xuất](../../source-tool/pointsnap-3d/de-xuat-de-tai.md) · [bảng phân việc](../../source-tool/pointsnap-3d/TASKS.md) · [giao việc theo ngày](../../source-tool/pointsnap-3d/giao-viec/))

> **Phân công:** Việt Anh và Huy làm toàn bộ sản phẩm; Khánh, Chiến, Hân viết báo cáo và test khi sản phẩm xong.
> Cổng: **G0 (tối 06/10)** 1 cảnh nuScenes hiển thị đúng trên CVAT · **G1 (07/10)** ground có kết quả kiểm chứng, lơ lửng/lún và kích thước chạy được, ghi được cờ lỗi · **G2 (08/10)** sản phẩm xong · **G3 (12h 09/10)** test xong, có số liệu · **Nộp cuối ngày 09/10**.
> Mã việc (B1, T1, …) trùng với [`TASKS.md`](../../source-tool/pointsnap-3d/TASKS.md); tiêu chí xong của từng việc ghi ở đó.
> Nếu tuần này còn job gán nhãn của BTC, Lead bổ sung vào bảng Công việc.

## Thành viên và phân công

| Thành viên | Vị trí | Phân công tuần này |
|---|---|---|
| Khúc Việt Anh | Sản phẩm (phía CVAT, môi trường) | Khung dự án (A1), đọc nuScenes (B1), dữ liệu + CVAT (E1), chuyển nuScenes → CVAT (A2), adapter CVAT (A3, A4), `scan` + `gate` (A5), tích hợp (A6), lỗi chèn giả (A7), README cài đặt (A9) |
| Đặng Văn Huy | Sản phẩm (thuật toán) | Module ground (B2), 3 bộ phát hiện (B3–B5), precision/recall (B6), chốt ngưỡng và chạy đánh giá (B7); review PR của Việt Anh |
| Vũ Bảo Khánh | Lead · Báo cáo | Khung báo cáo và slide (R1), hoàn thiện báo cáo và slide (R2), nhật ký tuần (R3), nộp |
| Nhữ Đình Chiến | Test (khi xong sản phẩm) | Test quy trình trên CVAT theo README (T1), cùng Hân xem tay cảnh báo (T2), video demo (R2) |
| Nguyễn Văn Hân | Test (khi xong sản phẩm) | Chủ trì xem tay cảnh báo và bảng chỉ số (T2), phần kết quả đánh giá trong báo cáo |

## Công việc

| # | Nội dung công việc | Người làm | Người kiểm | Hoàn thành | Ghi chú |
|---|---|---|---|---|---|
| 1 | A1 — Khung dự án | @Khúc Việt Anh | @Đặng Văn Huy | ✅ 100% | [PR #1](https://github.com/AI20K-Build-Phase-Cohort-4A/P-029/pull/1) đã merge |
| 2 | B1 — Đọc nuScenes ra `Cuboid` | @Khúc Việt Anh | @Đặng Văn Huy | 🟡 90% | [PR #2](https://github.com/AI20K-Build-Phase-Cohort-4A/P-029/pull/2) chờ review; chưa chạy trên dữ liệu thật |
| 3 | E1 — Tải nuScenes; dựng CVAT | @Khúc Việt Anh | — | ⬜ 0% | 06/10 · cần cho G0 |
| 4 | A2 — Chuyển 1 cảnh nuScenes → CVAT | @Khúc Việt Anh | @Đặng Văn Huy | 🟡 40% | 06/10 · **G0**; phần xuất dữ liệu và gọi API đã viết, chờ CVAT để chạy thử |
| 5 | B2 — Module ground + kiểm chứng ~200 box | @Đặng Văn Huy | @Khúc Việt Anh | ⬜ 0% | Sáng 07/10 |
| 6 | B3, B4 — Lơ lửng/lún; sai kích thước | @Đặng Văn Huy | @Khúc Việt Anh | ⬜ 0% | 07/10 · **G1** |
| 7 | A3, A4 — Adapter CVAT đọc nhãn; ghi cờ lỗi | @Khúc Việt Anh | @Đặng Văn Huy | ⬜ 0% | 07/10 · **G1** |
| 8 | R1 — Khung báo cáo và slide | @Vũ Bảo Khánh | — | ⬜ 0% | 08/10 |
| 9 | B5, B6 — Đứt track; precision/recall | @Đặng Văn Huy | @Khúc Việt Anh | ⬜ 0% | 08/10 |
| 10 | A5, A6, A7, A9 — `scan` + `gate`; tích hợp; lỗi chèn giả; README | @Khúc Việt Anh | @Đặng Văn Huy | ⬜ 0% | 08/10 · **G2** |
| 11 | B7 — Chốt ngưỡng, chạy đánh giá | @Đặng Văn Huy | @Nguyễn Văn Hân | ⬜ 0% | Sáng 09/10 |
| 12 | T1 — Test quy trình trên CVAT | @Nhữ Đình Chiến | — | ⬜ 0% | Sáng 09/10 |
| 13 | T2 — Xem tay cảnh báo, bảng chỉ số | @Nguyễn Văn Hân, @Nhữ Đình Chiến | @Vũ Bảo Khánh | ⬜ 0% | 12h 09/10 · **G3** |
| 14 | R2, R3 — Báo cáo, slide, video; nhật ký | @Vũ Bảo Khánh, @Nhữ Đình Chiến | — | ⬜ 0% | Cuối ngày 09/10 · **Nộp** |

Mức hoàn thành: ✅ xong **và đã qua review** · 🟡 đang làm (ghi %) · ⛔ bị chặn (ghi lý do) · ⬜ chưa bắt đầu

## Tổng kết

*Chốt sau khi nộp (09/10).*

- Cổng đạt / không đạt:
- Việc xong:
- Việc trễ hoặc phải cắt, lý do:

## Vướng mắc

- Kế hoạch rút từ 1,5 tuần còn 4 ngày (06/10 – 09/10): đã cắt bộ lỗi thật (tự gán nhãn lại), lệnh `diff`, đo thời gian review, luật khoảng nội suy dài. Không có ngày dự phòng.
- Chỉ 2 người làm sản phẩm; 3 người còn lại chỉ vào việc khi sản phẩm xong (sau G2).
- Máy Việt Anh chưa tải xong nuScenes và chưa chạy CVAT: **G0 cần xong hai việc này trong ngày 06/10**.

## Kế hoạch tuần sau

- Sau khi nộp: tổng kết, chuyển các phần đã cắt sang hướng phát triển.
