# Nhật ký tuần 04 · 05/10 – 11/10/2026

**Lead tuần này:** @Vũ Bảo Khánh
**Dữ liệu / task CVAT:** nuScenes v1.0-mini trên CVAT Docker local, dùng để làm tool **PointSnap 3D** ([bản đề xuất](../../source-tool/pointsnap-3d/de-xuat-de-tai.md) · [bảng phân việc chi tiết](../../source-tool/pointsnap-3d/TASKS.md))

> Tuần này nhắm 3 cổng: **G0 (06/10)** 1 cảnh nuScenes hiển thị đúng trên CVAT · **G1 (08/10)** ground có kết quả kiểm chứng, phát hiện lơ lửng/lún và kích thước chạy trên 1 cảnh · **G2 (09/10)** demo trọn quy trình `scan --flag` → lọc trong CVAT → `gate`.
> Mã việc (A1, C3, …) trùng với [`TASKS.md`](../../source-tool/pointsnap-3d/TASKS.md); tiêu chí xong của từng việc ghi ở đó.
> Nếu tuần này còn job gán nhãn của BTC, Lead bổ sung vào bảng Công việc.

## Thành viên và phân công

| Thành viên | Vị trí | Phân công tuần này |
|---|---|---|
| Vũ Bảo Khánh | Lead · Tester (người dùng & tài liệu) | Điều phối, họp nhanh đầu ngày, nghiệm thu G0–G2; hướng dẫn tự gán nhãn (K1), mẫu báo cáo và câu chữ (K2), khoảng kích thước class ít mẫu (K3), tự gán nhãn (K4), dùng thử tool (K5) |
| Khúc Việt Anh | Code (phía CVAT) | Khung dự án (A1), đọc nuScenes (B1), chuyển nuScenes → CVAT (A2), adapter CVAT đọc / ghi (A3, A4), `scan` + `gate` (A5), tích hợp (A6) |
| Đặng Văn Huy | Code (thuật toán) | Review PR của Việt Anh; module ground (B2), phát hiện lơ lửng/lún (B3), sai kích thước (B4), đứt track (B5) |
| Nhữ Đình Chiến | Tester (môi trường & CVAT) | Dựng CVAT (C1), tải dữ liệu (C2), kiểm 1 cảnh trên CVAT (C3), spike trên giao diện (C4), label spec (C5), tự gán nhãn (C6), kiểm cờ lỗi (C7), kiểm toàn quy trình (C8) |
| Nguyễn Văn Hân | Tester (thuật toán & đánh giá) | Ca kiểm thử có đáp án (H1), đặc tả lỗi chèn giả (H2), kiểm ground bằng mắt (H3), chạy ca kiểm thử cho 3 bộ phát hiện (H4) |

## Công việc

| # | Nội dung công việc | Người làm | Người kiểm | Hoàn thành | Ghi chú |
|---|---|---|---|---|---|
| 1 | A1 — Khung dự án: package `pointsnap`, mô hình dữ liệu, hình học, cấu hình, CLI | @Khúc Việt Anh | @Đặng Văn Huy | 🟡 95% | [PR #1](https://github.com/AI20K-Build-Phase-Cohort-4A/P-029/pull/1) chờ review; 43 test xanh |
| 2 | K1 — Hướng dẫn tự gán nhãn lại 1 cảnh (class, bán kính 30 m, chia track) | @Vũ Bảo Khánh | — | ⬜ 0% | Hạn 05/10 · nếu đã xong thì cập nhật; chưa thì xong trong sáng 06/10 |
| 3 | C1 — Dựng CVAT Docker local, tạo admin + access token | @Nhữ Đình Chiến | — | ⬜ 0% | Hạn 05/10 · nếu đã xong thì cập nhật · cần cho G0 |
| 4 | C2 — Tải nuScenes v1.0-mini (~4 GB) | @Nhữ Đình Chiến | — | ⬜ 0% | Hạn 05/10 · nếu đã xong thì cập nhật · Huy và Việt Anh tự tải thêm bản trên máy mình |
| 5 | B1 — Đọc nuScenes ra `Cuboid` trong hệ LiDAR | @Khúc Việt Anh | @Đặng Văn Huy | 🟡 10% | Việt Anh làm thay Huy để A2 không phải chờ |
| 6 | A2 — Script chuyển nuScenes → CVAT (`.pcd` + nạp nhãn dạng track) | @Khúc Việt Anh | @Nhữ Đình Chiến | ⬜ 0% | Hạn 06/10 · đường găng của G0 |
| 7 | C3 — Chạy A2, kiểm bằng mắt 1 cảnh trên CVAT | @Nhữ Đình Chiến | @Vũ Bảo Khánh | ⬜ 0% | Hạn 06/10 · **G0** |
| 8 | C4 — Spike trên giao diện: thuộc tính + bộ lọc, trục / yaw, `outside`, link mở frame | @Nhữ Đình Chiến | @Khúc Việt Anh | ⬜ 0% | Hạn 06/10 · ghi kết quả vào `CONVENTIONS.md` |
| 9 | C5 — Label spec `pointsnap_error`, `reviewed`; task trống cho cảnh tự gán | @Nhữ Đình Chiến | — | ⬜ 0% | Hạn 06/10 |
| 10 | H1 — Ca kiểm thử có đáp án cho 3 bộ phát hiện | @Nguyễn Văn Hân | @Đặng Văn Huy | ⬜ 0% | Hạn 06/10 |
| 11 | H2 — Đặc tả bộ lỗi chèn giả | @Nguyễn Văn Hân | @Khúc Việt Anh | ⬜ 0% | Hạn 06/10 |
| 12 | K2 — Mẫu báo cáo HTML + câu chữ thông báo lỗi | @Vũ Bảo Khánh | @Khúc Việt Anh | ⬜ 0% | Hạn 06/10 |
| 13 | K3 — Khoảng kích thước cho class ít mẫu | @Vũ Bảo Khánh | @Đặng Văn Huy | ⬜ 0% | Hạn 06/10 |
| 14 | B2 — Module ground (RANSAC, vành đai quanh box) + kiểm chứng ~200 box | @Đặng Văn Huy | @Nguyễn Văn Hân | ⬜ 0% | Hạn 07/10 · test trên point cloud giả trước |
| 15 | A3 — Adapter CVAT đọc nhãn và point cloud | @Khúc Việt Anh | @Nhữ Đình Chiến | ⬜ 0% | Hạn 07/10 |
| 16 | C6 / K4 — Tự gán nhãn lại 1 cảnh (mỗi người nửa số track) | @Nhữ Đình Chiến, @Vũ Bảo Khánh | @Nguyễn Văn Hân | ⬜ 0% | Chiến 07/10, Khánh 08/10 |
| 17 | B3 — Phát hiện lơ lửng / lún | @Đặng Văn Huy | @Nguyễn Văn Hân | ⬜ 0% | Hạn 08/10 · **G1** |
| 18 | B4 — Thống kê kích thước + phát hiện sai kích thước | @Đặng Văn Huy | @Nguyễn Văn Hân | ⬜ 0% | Hạn 08/10 · **G1** |
| 19 | A4 — Adapter CVAT ghi cờ lỗi + bản chụp | @Khúc Việt Anh | @Nhữ Đình Chiến | ⬜ 0% | Hạn 08/10 |
| 20 | A5 — `scan` (báo cáo HTML/CSV) + `gate` | @Khúc Việt Anh | @Vũ Bảo Khánh | ⬜ 0% | Hạn 08/10 |
| 21 | H3 — Đối chiếu ground ước lượng bằng mắt | @Nguyễn Văn Hân | — | ⬜ 0% | Hạn 08/10 |
| 22 | C7 — Kiểm cờ lỗi: đúng box, lọc được, hình học không đổi | @Nhữ Đình Chiến | — | ⬜ 0% | Hạn 08/10 |
| 23 | B5 — Phát hiện đứt track (nhảy vị trí, tách ID) | @Đặng Văn Huy | @Nguyễn Văn Hân | ⬜ 0% | Hạn 09/10 |
| 24 | A6 — Tích hợp end-to-end trên CVAT | @Khúc Việt Anh | @Nhữ Đình Chiến | ⬜ 0% | Hạn 09/10 · **G2** |
| 25 | C8 — Kiểm toàn quy trình trên CVAT | @Nhữ Đình Chiến | @Vũ Bảo Khánh | ⬜ 0% | Hạn 09/10 · **G2** |
| 26 | H4 — Chạy ca kiểm thử cho B3, B4, B5 | @Nguyễn Văn Hân | — | ⬜ 0% | Hạn 09/10 |
| 27 | K5 — Dùng thử tool như annotator, gửi góp ý | @Vũ Bảo Khánh | — | ⬜ 0% | Hạn 09/10 |

Mức hoàn thành: ✅ xong **và đã qua review** · 🟡 đang làm (ghi %) · ⛔ bị chặn (ghi lý do) · ⬜ chưa bắt đầu

## Tổng kết

*Chốt cuối tuần (11/10).*

- Cổng đạt / không đạt:
- Việc xong:
- Việc trễ, lý do:

## Vướng mắc

- Máy Việt Anh tạm hoãn tải nuScenes (mới tải ~4%) và chưa chạy CVAT. **G0 hôm nay phụ thuộc** CVAT và dữ liệu trên máy Chiến, hoặc máy Việt Anh tải xong trong ngày.
- Chưa thấy cập nhật C1, C2, K1 (hạn 05/10). Nếu chưa xong thì cần xong trong sáng 06/10 để kịp G0.

## Kế hoạch tuần sau

- 12–13/10: đánh giá trên 5 cảnh kiểm tra, chốt ngưỡng (G3). 14/10: đóng gói, README, video demo. 15/10: dự phòng, nộp.
