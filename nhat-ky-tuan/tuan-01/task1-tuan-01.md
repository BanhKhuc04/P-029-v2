# Nhật ký tuần 01 — Task 1 · 14/09 – 20/09/2026

**Lead tuần này:** @Đặng Văn Huy  
**Dữ liệu / task CVAT:** Task #148 (`W1-BBOX-G4-T1`) — [CVAT Task 148](https://cvat.note.transformerlabs.ai/tasks/148)

## Thành viên và phân công

| Thành viên | Vị trí | Phân công tuần này |
|---|---|---|
| Đặng Văn Huy | Lead · Reviewer | Điều phối Task #148, phân chia job, theo dõi tiến độ, chốt edge case, review chất lượng gán nhãn |
| Khúc Việt Anh | Annotator | Gán nhãn Job #1442 (Frame 0–24) |
| Nguyễn Văn Hân | Annotator | Gán nhãn Job #1443 (Frame 25–49) |
| Nhữ Đình Chiến | Annotator | Gán nhãn Job #1444 (Frame 50–74) |
| Vũ Bảo Khánh | Annotator | Gán nhãn Job #1445 (Frame 75–99) |

## Công việc

| # | Nội dung công việc | Annotator | Reviewer | Hoàn thành | Ghi chú |
|---|---|---|---|---|---|
| 1 | Họp đầu tuần, thống nhất guideline và chia job Task #148 | Cả đội | — | ✅ 100% | Phân chia 4 job (mỗi job 25 frame) |
| 2 | Job #1442 — 25 ảnh (frame 0–24), bbox phương tiện | @Khúc Việt Anh | @Đặng Văn Huy | ✅ 100% | Đã gán 285 đối tượng, đang ở Stage: `acceptance` (Lead nghiệm thu) |
| 3 | Job #1443 — 25 ảnh (frame 25–49), bbox phương tiện | @Nguyễn Văn Hân | @Khúc Việt Anh | ✅ 100% | Đã gán 246 đối tượng, Stage: `acceptance` (Lead nghiệm thu) |
| 4 | Job #1444 — 25 ảnh (frame 50–74), bbox phương tiện | @Nhữ Đình Chiến | @Nguyễn Văn Hân | ✅ 100% | Đã gán 229 đối tượng, đang ở Stage: `acceptance` (Lead nghiệm thu) |
| 5 | Job #1445 — 25 ảnh (frame 75–99), bbox phương tiện | @Vũ Bảo Khánh | @Khúc Việt Anh | ✅ 100% | Đã gán 299 đối tượng, Stage: `acceptance` (Lead nghiệm thu) |

*Mức hoàn thành:* ✅ xong và đã qua review · 🟡 đang làm (ghi %) · ⛔ bị chặn (ghi lý do) · ⬜ chưa bắt đầu

## Tổng kết

- **Đã gán:** 1.059 đối tượng / 100 ảnh (gồm 909 Bounding Box và 150 Polygon) — trung bình 10.6 đối tượng/ảnh:
  - Job #1442 (Khúc Việt Anh): 285 đối tượng (234 bbox, 51 polygon)
  - Job #1443 (Nguyễn Văn Hân): 246 đối tượng (221 bbox, 25 polygon)
  - Job #1444 (Nhữ Đình Chiến): 229 đối tượng (202 bbox, 27 polygon)
  - Job #1445 (Vũ Bảo Khánh): 299 đối tượng (252 bbox, 47 polygon)
- **Qua review lần đầu:** Cả 4 job đã hoàn thành gán nhãn 100% và chuyển sang giai đoạn `acceptance` để Lead nghiệm thu lần cuối.
- **Edge case mới / đã chốt:**
  - Đã chốt: [P-001](../../problem-backlog.md#p-001) thành [QĐ-001](../../so-quyet-dinh.md#qđ-001), [P-002](../../problem-backlog.md#p-002) thành [QĐ-002](../../so-quyet-dinh.md#qđ-002), [P-003](../../problem-backlog.md#p-003) thành [QĐ-003](../../so-quyet-dinh.md#qđ-003), [P-004](../../problem-backlog.md#p-004) thành [QĐ-004](../../so-quyet-dinh.md#qđ-004).

## Vướng mắc

- Đã giải quyết xong sự không đồng nhất về gán nhãn `area/alternative` bằng quyết định [QĐ-004](../../so-quyet-dinh.md#qđ-004).

## Kế hoạch tuần sau

- Lead hoàn tất nghiệm thu (`acceptance`) cho cả 4 job và chuyển trạng thái trên CVAT sang `completed`.
- Rà soát các polygon bổ sung theo [QĐ-004](../../so-quyet-dinh.md#qđ-004) (`area/alternative`).
- Export bản dataset cuối cùng sau khi hoàn tất toàn bộ task tuần 01.
