# Nhật ký tuần 04 · 05/10 – 11/10/2026

**Lead tuần này:** @Vũ Bảo Khánh
**Dữ liệu / task CVAT:** nuScenes v1.0-mini trên CVAT Docker local, dùng để làm tool **PointSnap 3D** trong 4 ngày 06/10 – 09/10 ([bản đề xuất](../../source-tool/pointsnap-3d/de-xuat-de-tai.md) · [bảng phân việc](../../source-tool/pointsnap-3d/TASKS.md) · [giao việc theo ngày](../../source-tool/pointsnap-3d/giao-viec/))

> Cổng: **G0 (tối 06/10)** 1 cảnh nuScenes hiển thị đúng trên CVAT · **G1 (07/10)** ground có kết quả kiểm chứng, lơ lửng/lún và kích thước chạy được, ghi được cờ lỗi · **G2 (08/10)** demo trọn quy trình `scan --flag` → lọc trong CVAT → `gate` · **G3 (12h 09/10)** có số liệu đánh giá · **Nộp cuối ngày 09/10**.
> Mã việc (B1, C3, …) trùng với [`TASKS.md`](../../source-tool/pointsnap-3d/TASKS.md); tiêu chí xong của từng việc ghi ở đó.
> Nếu tuần này còn job gán nhãn của BTC, Lead bổ sung vào bảng Công việc.

## Thành viên và phân công

| Thành viên | Vị trí | Phân công tuần này |
|---|---|---|
| Vũ Bảo Khánh | Lead · Tester (người dùng & tài liệu) | Điều phối, họp nhanh đầu ngày, nghiệm thu G0–G3; mẫu báo cáo và câu chữ (K2), khoảng kích thước class ít mẫu (K3), dùng thử tool (K5), hồ sơ nộp (K7) |
| Khúc Việt Anh | Code (phía CVAT) | Khung dự án (A1), đọc nuScenes (B1), chuyển nuScenes → CVAT (A2), adapter CVAT (A3, A4), `scan` + `gate` (A5), tích hợp (A6), lỗi chèn giả (A7), đóng gói (A9) |
| Đặng Văn Huy | Code (thuật toán) | Review PR của Việt Anh; module ground (B2), 3 bộ phát hiện (B3–B5), precision/recall (B6), chốt ngưỡng (B7) |
| Nhữ Đình Chiến | Tester (môi trường & CVAT) | Dựng CVAT (C1), tải dữ liệu (C2), spike (C4), label spec (C5), kiểm trên CVAT (C3, C7, C8), xem tay cảnh báo (C9), kiểm README (C10) |
| Nguyễn Văn Hân | Tester (thuật toán & đánh giá) | Ca kiểm thử (H1), đặc tả lỗi chèn (H2), kiểm ground (H3), kiểm bộ phát hiện (H4), chủ trì đánh giá (H5) |

## Công việc

| # | Nội dung công việc | Người làm | Người kiểm | Hoàn thành | Ghi chú |
|---|---|---|---|---|---|
| 1 | A1 — Khung dự án | @Khúc Việt Anh | @Đặng Văn Huy | ✅ 100% | [PR #1](https://github.com/AI20K-Build-Phase-Cohort-4A/P-029/pull/1) đã merge |
| 2 | C1, C2 — Dựng CVAT; tải nuScenes | @Nhữ Đình Chiến | — | ⬜ 0% | Sáng 06/10 · cần cho G0 |
| 3 | B1 — Đọc nuScenes ra `Cuboid` | @Khúc Việt Anh | @Đặng Văn Huy | 🟡 10% | 06/10 · làm thay Huy |
| 4 | A2 — Chuyển 1 cảnh nuScenes → CVAT | @Khúc Việt Anh | @Nhữ Đình Chiến | ⬜ 0% | 06/10 · đường găng G0 |
| 5 | C4, C5 — Spike trên giao diện; label spec | @Nhữ Đình Chiến | @Khúc Việt Anh | ⬜ 0% | 06/10 |
| 6 | C3 — Kiểm 1 cảnh trên CVAT | @Nhữ Đình Chiến | @Vũ Bảo Khánh | ⬜ 0% | Tối 06/10 · **G0** |
| 7 | H1, H2 — Ca kiểm thử; đặc tả lỗi chèn giả | @Nguyễn Văn Hân | @Đặng Văn Huy | ⬜ 0% | 06/10 |
| 8 | K2, K3 — Mẫu báo cáo + câu chữ; kích thước class ít mẫu | @Vũ Bảo Khánh | @Khúc Việt Anh | ⬜ 0% | 06/10 |
| 9 | B2 — Module ground + kiểm chứng ~200 box | @Đặng Văn Huy | @Nguyễn Văn Hân | ⬜ 0% | Sáng 07/10 |
| 10 | B3, B4 — Lơ lửng/lún; sai kích thước | @Đặng Văn Huy | @Nguyễn Văn Hân | ⬜ 0% | 07/10 · **G1** |
| 11 | A3, A4 — Adapter CVAT đọc nhãn; ghi cờ lỗi | @Khúc Việt Anh | @Nhữ Đình Chiến | ⬜ 0% | 07/10 · **G1** |
| 12 | H3, C7 — Kiểm ground bằng mắt; kiểm cờ lỗi trên CVAT | @Nguyễn Văn Hân, @Nhữ Đình Chiến | — | ⬜ 0% | 07/10 |
| 13 | B5, B6 — Đứt track; precision/recall | @Đặng Văn Huy | @Nguyễn Văn Hân | ⬜ 0% | 08/10 |
| 14 | A5, A6, A7 — `scan` + `gate`; tích hợp; lỗi chèn giả | @Khúc Việt Anh | @Nhữ Đình Chiến | ⬜ 0% | 08/10 · **G2** |
| 15 | C8, H4, K5 — Kiểm toàn quy trình; kiểm bộ phát hiện; dùng thử | @Nhữ Đình Chiến, @Nguyễn Văn Hân, @Vũ Bảo Khánh | — | ⬜ 0% | 08/10 · **G2** |
| 16 | B7, H5, C9 — Chốt ngưỡng; đánh giá | @Đặng Văn Huy, @Nguyễn Văn Hân, @Nhữ Đình Chiến | @Vũ Bảo Khánh | ⬜ 0% | 12h 09/10 · **G3** |
| 17 | K7, A9, C10 — Hồ sơ nộp; đóng gói; kiểm README | @Vũ Bảo Khánh, @Khúc Việt Anh, @Nhữ Đình Chiến | — | ⬜ 0% | Cuối ngày 09/10 · **Nộp** |

Mức hoàn thành: ✅ xong **và đã qua review** · 🟡 đang làm (ghi %) · ⛔ bị chặn (ghi lý do) · ⬜ chưa bắt đầu

## Tổng kết

*Chốt sau khi nộp (09/10).*

- Cổng đạt / không đạt:
- Việc xong:
- Việc trễ hoặc phải cắt, lý do:

## Vướng mắc

- Kế hoạch rút từ 1,5 tuần còn 4 ngày (06/10 – 09/10): đã cắt bộ lỗi thật (tự gán nhãn lại), lệnh `diff`, đo thời gian review, luật khoảng nội suy dài. Không có ngày dự phòng.
- Máy Việt Anh tạm hoãn tải nuScenes và chưa chạy CVAT. **G0 phụ thuộc** CVAT và dữ liệu trên máy Chiến, hoặc máy Việt Anh tải xong trong ngày 06/10.

## Kế hoạch tuần sau

- Sau khi nộp: tổng kết, chuyển các phần đã cắt sang hướng phát triển.
