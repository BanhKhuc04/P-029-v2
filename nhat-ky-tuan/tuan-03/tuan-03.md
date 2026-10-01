# Nhật ký tuần 03 · 28/09 – 04/10/2026

**Lead tuần này:** @Vũ Bảo Khánh  
**Dữ liệu / task CVAT:** Task 3D Cuboid Point Cloud + 6 Camera Context Images (4 Job: #4019, #4020, #4021, #4022)  
**Nhiệm vụ:** Gán nhãn 3D Cuboid các đối tượng giao thông (10 class: `car`, `truck`, `bus`, `trailer`, `construction_vehicle`, `pedestrian`, `motorcycle`, `bicycle`, `traffic_cone`, `barrier`) trên dữ liệu Point Cloud LiDAR kết hợp 6 camera context đồng bộ.

## Thành viên và phân công

| Thành viên | Vị trí | Phân công tuần này |
|---|---|---|
| Vũ Bảo Khánh | Lead · Reviewer | Điều phối task 3D Cuboid, phân chia job, theo dõi tiến độ, chốt edge case, review chất lượng và nghiệm thu |
| Nguyễn Văn Hân | Annotator · Reviewer | Gán nhãn [Job #4019](https://cvat.note.transformerlabs.ai/jobs/4019), review chéo Job #4020 |
| Nhữ Đình Chiến | Annotator · Reviewer | Gán nhãn [Job #4020](https://cvat.note.transformerlabs.ai/jobs/4020), review chéo Job #4022 |
| Đặng Văn Huy | Annotator · Reviewer | Gán nhãn [Job #4021](https://cvat.note.transformerlabs.ai/jobs/4021), review chéo Job #4019 |
| Khúc Việt Anh | Annotator · Reviewer | Gán nhãn [Job #4022](https://cvat.note.transformerlabs.ai/jobs/4022), review chéo Job #4021 |

## Công việc

| # | Nội dung công việc | Annotator | Reviewer | Hoàn thành | Ghi chú |
|---|---|---|---|---|---|
| 1 | Họp đầu tuần, thống nhất guideline 3D Cuboid và quy ước hệ tọa độ local từ BTC ([QĐ-008](../../so-quyet-dinh.md#qđ-008)) | Cả đội | — | ✅ 100% | Thống nhất trục X local (dọc/hướng xe), Y (ngang), Z (cao); bật Cuboid Orientation |
| 2 | Phân chia phạm vi frame và 4 job cho thành viên | Vũ Bảo Khánh | — | ✅ 100% | Đã phân chia 4 job cho 4 annotator |
| 3 | Job #4019 — Gán nhãn 3D Cuboid | @Nguyễn Văn Hân | @Đặng Văn Huy, @Vũ Bảo Khánh | 🟡 35% | Đang gán nhãn 3D cuboid, đối chiếu 6 camera |
| 4 | Job #4020 — Gán nhãn 3D Cuboid | @Nhữ Đình Chiến | @Khúc Việt Anh, @Vũ Bảo Khánh | 🟡 30% | Đang gán nhãn 3D cuboid, đối chiếu 6 camera |
| 5 | Job #4021 — Gán nhãn 3D Cuboid | @Đặng Văn Huy | @Vũ Bảo Khánh | 🟡 35% | Đang gán nhãn 3D cuboid, đối chiếu 6 camera |
| 6 | Job #4022 — Gán nhãn 3D Cuboid | @Khúc Việt Anh | @Nhữ Đình Chiến, @Vũ Bảo Khánh | 🟡 30% | Đang gán nhãn 3D cuboid, đối chiếu 6 camera |

*Mức hoàn thành:* ✅ xong và đã qua review · 🟡 đang làm (ghi %) · ⛔ bị chặn (ghi lý do) · ⬜ chưa bắt đầu

## Tổng kết

- **Tiến độ gán nhãn:** Nhóm đã hoàn thành phân chia 4 job (`Job #4019`, `Job #4020`, `Job #4021`, `Job #4022`) cho các thành viên và đạt khoảng **30% – 35%** tiến độ gán nhãn đợt đầu trên dữ liệu 3D Cuboid; đang tiến hành review chéo bước đầu giữa các thành viên và Lead nghiệm thu.
- **Quyết định kỹ thuật / Edge case:**
  - Đã tiếp nhận và áp dụng hướng dẫn từ BTC về hệ tọa độ local của 3D Cuboid: [P-008](../../problem-backlog.md#p-008) $\rightarrow$ [QĐ-008](../../so-quyet-dinh.md#qđ-008).
  - Đang theo dõi và chờ giải đáp cho vấn đề ngưỡng điểm tối thiểu và khoảng cách cut-off: [P-009](../../problem-backlog.md#p-009).

## Vướng mắc

- Không có vướng mắc chặn tiến độ; chỉ đang chờ làm rõ thêm case [P-009](../../problem-backlog.md#p-009) để chuẩn hóa cho các đối tượng ở xa.

## Kế hoạch tuần sau

- Đẩy nhanh tiến độ gán nhãn lên 100% cho tất cả các job.
- Tiến hành nghiệm thu và rà soát lỗi theo Checklist trước khi submit (kiểm tra yaw, grounding mặt đất, không duplicate).
- Cập nhật số liệu và export bản dữ liệu tuần 03 sau khi hoàn tất.
