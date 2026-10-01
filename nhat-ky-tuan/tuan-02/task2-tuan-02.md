# Nhật ký tuần 02 — Task 2 · 22/09 – 24/09/2026

**Lead tuần này:** @Nguyễn Văn Hân  
**Dữ liệu / task CVAT:**
- Task #314 (`W2-POSE-G4-T1`) — [CVAT Task 314](https://cvat.note.transformerlabs.ai/tasks/314)
- Task #315 (`W2-POSEPRE-G4-T1`) — [CVAT Task 315](https://cvat.note.transformerlabs.ai/tasks/315)

**Nhiệm vụ:** Gán nhãn pose người dạng skeleton (`person`) trên dữ liệu human-body-keypoints và kiểm tra/chỉnh sửa dữ liệu pose prelabel.

## Thành viên và phân công

| Thành viên | Vị trí | Phân công tuần này |
|---|---|---|
| Nguyễn Văn Hân | Lead · Reviewer | Điều phối hai task (#314, #315), phân chia job, theo dõi tiến độ, review và nghiệm thu |
| Đặng Văn Huy | Annotator | Gán nhãn [Job #2094](https://cvat.note.transformerlabs.ai/tasks/314/jobs/2094), [Job #2098](https://cvat.note.transformerlabs.ai/tasks/315/jobs/2098) (Frame 0–4, 0–9) |
| Khúc Việt Anh | Annotator | Gán nhãn [Job #2095](https://cvat.note.transformerlabs.ai/tasks/314/jobs/2095), [Job #2099](https://cvat.note.transformerlabs.ai/tasks/315/jobs/2099) (Frame 5–9, 10–19) |
| Nhữ Đình Chiến | Annotator | Gán nhãn [Job #2096](https://cvat.note.transformerlabs.ai/tasks/314/jobs/2096), [Job #2100](https://cvat.note.transformerlabs.ai/tasks/315/jobs/2100) (Frame 10–14, 20–29) |
| Vũ Bảo Khánh | Annotator | Gán nhãn [Job #2097](https://cvat.note.transformerlabs.ai/tasks/314/jobs/2097), [Job #2101](https://cvat.note.transformerlabs.ai/tasks/315/jobs/2101) (Frame 15–19, 30–39) |

## Công việc

| # | Nội dung công việc | Annotator | Reviewer | Hoàn thành | Ghi chú |
|---|---|---|---|---|---|
| 1 | Họp đầu tuần, thống nhất guideline và chia job Task #314 & #315 | Cả đội | — | ✅ 100% | Phân chia các job cho các thành viên |
| 2 | Job #2094, #2098 (frame 0–4, 0–9), pose skeleton | @Đặng Văn Huy | @Vũ Bảo Khánh | ✅ 100% | Đã hoàn thành, trạng thái `completed` |
| 3 | Job #2095, #2099 (frame 5–9, 10–19), pose skeleton | @Khúc Việt Anh | @Đặng Văn Huy | ✅ 100% | Đã hoàn thành, trạng thái `completed` |
| 4 | Job #2096, #2100 (frame 10–14, 20–29), pose skeleton | @Nhữ Đình Chiến | @Khúc Việt Anh | ✅ 100% | Đã hoàn thành, trạng thái `completed` |
| 5 | Job #2097, #2101 (frame 15–19, 30–39), pose skeleton | @Vũ Bảo Khánh | @Nhữ Đình Chiến | ✅ 100% | Đã hoàn thành, trạng thái `completed` |

*Mức hoàn thành:* ✅ xong và đã qua review · 🟡 đang làm (ghi %) · ⛔ bị chặn (ghi lý do) · ⬜ chưa bắt đầu

## Tổng kết

- **Tiến độ gán nhãn:** Cả 4 cặp job (`Job #2094, #2098`, `Job #2095, #2099`, `Job #2096, #2100`, `Job #2097, #2101`) của hai task đã hoàn thành 100% và hiển thị trạng thái `completed` trên CVAT.
- **Qua review lần đầu:** Hoàn thành nghiệm thu toàn bộ các job của cả hai task.
- **Edge case mới / đã chốt:** Không có phát sinh.

## Vướng mắc
- Không có.

## Kế hoạch tuần sau

- Lead hoàn tất nghiệm thu toàn bộ trên CVAT và chuyển trạng thái toàn task sang `completed`.
- Export bản dataset cuối cùng sau khi hoàn tất toàn bộ task tuần 02.
