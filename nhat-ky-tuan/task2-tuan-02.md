# Nhật ký tuần 02 — Task 2

**Lead tuần này:** Nguyễn Văn Hân
**Dữ liệu / task CVAT:**

- Task #314 (`W2-POSE-G4-T1`) — [CVAT Task 314](https://cvat.note.transformerlabs.ai/tasks/314)
- Task #315 (`W2-POSEPRE-G4-T1`) — [CVAT Task 315](https://cvat.note.transformerlabs.ai/tasks/315)

**Nhiệm vụ:** Gán nhãn pose người dạng skeleton (`person`) trên dữ liệu human-body-keypoints và kiểm tra/chỉnh sửa dữ liệu pose prelabel. Phạm vi task theo CVAT: 20 frame ở Task #314 và 40 frame ở Task #315.

## Thành viên và phân công


| Nguyễn Văn Hân | Lead · Reviewer      | Điều phối hai task, theo dõi tiến độ, tổng hợp review và nghiệm thu.                                                                         |
| -------------- | -------------------- | -------------------------------------------------------------------------------------------------------------------------------------------- |
| Đặng Văn Huy   | Annotator · Reviewer | [Job #2098](https://cvat.note.transformerlabs.ai/tasks/315/jobs/2098) [Job #2094](https://cvat.note.transformerlabs.ai/tasks/315/jobs/2098) |
| Khúc Việt Anh  | Annotator · Reviewer | [Job #2099](https://cvat.note.transformerlabs.ai/tasks/315/jobs/2099) [Job #2095](https://cvat.note.transformerlabs.ai/tasks/315/jobs/2099) |
| Nhữ Đình Chiến | Annotator · Reviewer | [Job #2100](https://cvat.note.transformerlabs.ai/tasks/315/jobs/2100) [Job #2096](https://cvat.note.transformerlabs.ai/tasks/315/jobs/2100) |
| Vũ Bảo Khánh   | Annotator · Reviewer | [Job #2097](https://cvat.note.transformerlabs.ai/tasks/314/jobs/2097) [Job #2101](https://cvat.note.transformerlabs.ai/tasks/315/jobs/2101)  |



| #                | Nội dung công việc                                        | Annotator          | Reviewer (Random/Chéo) | Hoàn thành        | Ghi chú                                                                    |
| ---------------- | --------------------------------------------------------- | ------------------ | ---------------------- | ----------------- | -------------------------------------------------------------------------- |
| 1                | Rà soát hai task pose và phân chia phạm vi frame theo job | Cả đội             | Nguyễn Văn Hân         | Xong              | Task #314 có 4 job, mỗi job 5 frame; Task #315 có 4 job, mỗi job 10 frame. |
| 2                | Task #314 — Job #2094, frame 0–4                          | **Đặng Văn Huy**   | **Vũ Bảo Khánh**       | ✅ Job `completed` | 5 frame; stage `annotation`.                                               |
| 3                | Task #314 — Job #2095, frame 5–9                          | **Khúc Việt Anh**  | **Đặng Văn Huy**       | ✅ Job `completed` | 5 frame; stage `annotation`.                                               |
| 4                | Task #314 — Job #2096, frame 10–14                        | **Nhữ Đình Chiến** | **Khúc Việt Anh**      | ✅ Job `completed` | 5 frame; stage `annotation`.                                               |
| 5                | Task #314 — Job #2097, frame 15–19                        | Vũ Bảo Khánh       | **Nhữ Đình Chiến**     | ✅ Job `completed` | 5 frame; stage `annotation`.                                               |
| 6                | Task #315 — Job #2098, frame 0–9                          | **Đặng Văn Huy**   | Vũ Bảo Khánh           | ✅ Job `completed` | 10 frame; stage `annotation`.                                              |
| 7                | Task #315 — Job #2099, frame 10–19                        | **Khúc Việt Anh**  | **Đặng Văn Huy**       | ✅ Job `completed` | 10 frame; stage `annotation`.                                              |
| 8                | Task #315 — Job #2100, frame 20–29                        | **Nhữ Đình Chiến** | **Khúc Việt Anh**      | ✅ Job `completed` | 10 frame; stage `annotation`.                                              |
| 9                | Task #315 — Job #2101, frame 30–39                        | **Vũ bảo Khánh**   | **Nhữ Đình Chiến**     | ✅ Job `completed` | 10 frame; stage `annotation`.                                              |
| đã sửa (nếu có). |                                                           |                    |                        |                   |                                                                            |


*Mức hoàn thành:* ✅ xong và đã qua review · 🟡 đang làm (ghi %) · ⛔ bị chặn (ghi lý do) · ⬜ chưa bắt đầu

## Tổng kết

- **Tiến độ trên CVAT:** Cả 8/8 job của hai task đang hiển thị trạng thái `completed`, stage `annotation`.
- **Phạm vi đã chia:** Task #314 gồm 20 frame (0–19); Task #315 gồm 40 frame (0–39); tổng cộng 60 frame.
- **Nhãn quan sát được khi kiểm tra job:** `SKELETON SHAPE` / `person`. Ảnh Task #314 nằm trong nhóm `human-body-keypoints`; ảnh Task #315 nằm trong nhóm `human-body-keypoints-prelabel`.
- **Trạng thái nghiệm thu toàn task:** **Hoàn Thành .**

## Vướng mắc

Đã giải quyết xong các vướng mắc

## Kế hoạch tuần sau

---
