# Nhật ký tuần 02 — Task 1 · 22/09 – 24/09/2026

**Lead tuần này:** @Nhữ Đình Chiến  
**Dữ liệu / task CVAT:** Task #316 (`W2-FACE-G4-T1`) — [CVAT Task 316](https://cvat.note.transformerlabs.ai/tasks/316)

## Thành viên và phân công

| Thành viên | Vị trí | Phân công tuần này |
|---|---|---|
| Nhữ Đình Chiến | Lead · Reviewer | Điều phối Task #316, phân chia job, theo dõi tiến độ, chốt edge case, review chất lượng gán nhãn |
| Khúc Việt Anh | Annotator | Gán nhãn Job #2104,#2108 (Frame 10-14,26-38) |
| Nguyễn Văn Hân | Annotator | Gán nhãn Job #2102,#2106 (Frame 0-4, 0-12) |
| Đặng Văn Huy | Annotator | Gán nhãn Job #2103,#2107 (Frame 5-9, 13-25) |
| Vũ Bảo Khánh | Annotator | Gán nhãn Job #2105,#2109 (Frame 15-19, 39-49) |

## Công việc

| # | Nội dung công việc | Annotator | Reviewer | Hoàn thành | Ghi chú |
|---|---|---|---|---|---|
| 1 | Họp đầu tuần, thống nhất guideline và chia job Task #316 | Cả đội | — | ✅ 100% | Phân chia 4 job (mỗi job 5 frame) |
| 2 | Job #316 — 18 ảnh (frame 0–4,0-12), face landmark | @Nguyễn Văn Hân | @Đặng Văn Huy | ✅ 100% | Đã gán 968 đối tượng, đang ở Stage: `acceptance` (Lead nghiệm thu) |
| 3 | Job #316 — 18 ảnh (frame 5–9,13-25), face landmark | @Đặng Văn Huy | @Nguyễn Văn Hân | ✅ 100% | Đã gán 984 đối tượng, Stage: `acceptance` (Lead nghiệm thu) |
| 4 | Job #316 — 18 ảnh (frame 10–14,26-38), face landmark | @Khúc Việt Anh | @Vũ Bảo Khánh | ✅ 100% | Đã gán 1006 đối tượng, đang ở Stage: `acceptance` (Lead nghiệm thu) |
| 5 | Job #316 — 16 ảnh (frame 15–19,39-49), face landmark | @Vũ Bảo Khánh | @Khúc Việt Anh | ✅ 100% | Đã gán 991 đối tượng, Stage: `acceptance` (Lead nghiệm thu) |

*Mức hoàn thành:* ✅ xong và đã qua review · 🟡 đang làm (ghi %) · ⛔ bị chặn (ghi lý do) · ⬜ chưa bắt đầu

## Tổng kết

- **Đã gán:** 3949 đối tượng / 70 ảnh (gồm skeleton shape) — trung bình 56,4 đối tượng/ảnh:
  - Job #2102, #2106 (Nguyễn Văn Hân): 968 đối tượng 
  - Job #2103, #2107 (Đặng Văn Huy): 984 đối tượng 
  - Job #2104, #2108 (Khúc Việt Anh): 1006 đối tượng 
  - Job #2105, #2109 (Vũ Bảo Khánh): 991 đối tượng 
- **Qua review lần đầu:** Cả 4 job đã hoàn thành gán nhãn 100% và chuyển sang giai đoạn `acceptance` để Lead nghiệm thu lần cuối.
- **Edge case mới / đã chốt:**
  - Đã chốt: [P-001](../problem-backlog.md#p-001) thành [QĐ-001](../so-quyet-dinh.md#qđ-001), [P-002](../problem-backlog.md#p-002) thành [QĐ-002](../so-quyet-dinh.md#qđ-002), [P-003](../problem-backlog.md#p-003) thành [QĐ-003](../so-quyet-dinh.md#qđ-003), [P-004](../problem-backlog.md#p-004) thành [QĐ-004](../so-quyet-dinh.md#qđ-004).

## Vướng mắc
- Không có.

## Kế hoạch tuần sau

- Lead hoàn tất nghiệm thu (`acceptance`) cho tất cả job và chuyển trạng thái trên CVAT sang `completed`.
- Export bản dataset cuối cùng sau khi hoàn tất toàn bộ task tuần 02.
