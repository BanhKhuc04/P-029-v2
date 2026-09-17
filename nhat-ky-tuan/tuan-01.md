# Nhật ký tuần 01 · 14/09 – 20/09/2026

**Lead tuần này:** Đặng Văn Huy
**Dữ liệu / task CVAT:** Task #148 (`W1-BBOX-G4-T1`) — Bounding Box ảnh giao thông (100 frames, 4 jobs)

## Thành viên và phân công

| Thành viên | Vị trí | Phân công tuần này |
|---|---|---|
| Đặng Văn Huy | Lead · Reviewer | Điều phối Task #148, phân chia job, theo dõi tiến độ, chốt edge case, review chất lượng gán nhãn |
| Khúc Việt Anh  | Annotator | Gán nhãn Job #1442 |
| Nguyễn Văn Hân  | Annotator | Gán nhãn Job #1443 |
| Nhữ Đình Chiến  | Annotator | Gán nhãn Job #1444 |
| Vũ Bảo Khánh | Annotator | Gán nhãn Job #1445 |

## Công việc

| # | Nội dung công việc | Annotator | Reviewer | Hoàn thành | Ghi chú |
|---|---|---|---|---|---|
| 1 | Họp đầu tuần, thống nhất guideline và chia job Task #148 | Cả đội | — | ✅ 100% | Phân chia 4 job (mỗi job 25 frame) |
| 2 | Job #1442 — 25 ảnh (frame 0–24), bbox phương tiện | @Khúc Việt Anh  | @Đặng Văn Huy | 🟡 90% | Stage: annotation, State: in progress |
| 3 | Job #1443 — 25 ảnh (frame 25–49), bbox phương tiện | @Nguyễn Văn Hân  | @Khúc Việt Anh | 🟡 50%| Stage: annotation, State: in progress |
| 4 | Job #1444 — 25 ảnh (frame 50–74), bbox phương tiện | @Nhữ Đình Chiến  | @Nguyễn Văn Hân  | 🟡 70% | Stage: annotation, State: in progress |
| 5 | Job #1445 — 25 ảnh (frame 75–99), bbox phương tiện | @Vũ Bảo Khánh | @Khúc Việt Anh | 🟡 80% | Stage: validation, State: in progress |

*Mức hoàn thành:* ✅ xong và đã qua review · 🟡 đang làm (ghi %) · ⛔ bị chặn (ghi lý do) · ⬜ chưa bắt đầu

## Tổng kết (Cập nhật giữa tuần)

- **Tổng số ảnh:** 100 frame chia đều cho 4 job (25 ảnh / job).
- **Tiến độ gán nhãn:** Cả 4 job đang ở trạng thái `in progress` (Stage: `annotation`), các thành viên đang tích cực tiến hành gán nhãn.
- **Tỉ lệ qua review:** Chưa review nghiệm thu (chờ các job hoàn thành stage annotation).
- **Edge case:** Đang gom các trường hợp khó (xe ở xa, xe bị che khuất, bóng phản chiếu trên kính lái) để chuẩn bị thảo luận và ghi nhận vào `problem-backlog.md` nếu cần.

## Vướng mắc

- Các phương tiện ở xa (kích thước nhỏ dưới ngưỡng quy định của guideline) cần thống nhất rõ có gán nhãn hay bỏ qua.

## Kế hoạch hoàn thiện tuần 02

- Hoàn thành gán nhãn 100% cho cả 4 job (#1442, #1443, #1444, #1445) trước hạn.
- Reviewer tiến hành kiểm tra (Stage: validation), phản hồi các box sai lệch hoặc thiếu sót để annotator điều chỉnh.
- Chốt lại số liệu tổng kết tuần, cập nhật backlog và sổ quyết định (nếu có phát sinh quy ước mới).
