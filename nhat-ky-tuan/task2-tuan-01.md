# Nhật ký tuần 01 — Task 2 · 14/09 – 20/09/2026

**Lead tuần này:** @Khúc Việt Anh  
**Dữ liệu / task CVAT:** Task #202 (`W1-SEG-G4-T1`) — [CVAT Task 202](https://cvat.note.transformerlabs.ai/tasks/202)  
**Nhiệm vụ:** Semantic Segmentation (19 class theo guideline AI20K) trên 100 ảnh giao thông

## Thành viên và phân công

| Thành viên | Vị trí | Phân công tuần này |
|---|---|---|
| Khúc Việt Anh | Lead · Reviewer | Điều phối Task #202, phân chia job, theo dõi tiến độ, review Job #1658 và Job #1660 |
| Đặng Văn Huy | Annotator · Reviewer | Gán nhãn Job #1658 (Frame 0–24), cùng review Job #1660 |
| Nguyễn Văn Hân | Annotator | Gán nhãn Job #1659 (Frame 25–49) |
| Nhữ Đình Chiến | Annotator | Gán nhãn Job #1660 (Frame 50–74) |
| Vũ Bảo Khánh | Annotator | Gán nhãn Job #1661 (Frame 75–99) |

## Công việc

| # | Nội dung công việc | Annotator | Reviewer | Hoàn thành | Ghi chú |
|---|---|---|---|---|---|
| 1 | Họp đầu tuần, thống nhất guideline Semantic Segmentation (19 class) và chia job Task #202 | Cả đội | — | ✅ 100% | Phân chia 4 job (mỗi job 25 frame), thống nhất color map và 3 rule cốt lõi |
| 2 | Job #1658 — 25 ảnh (frame 0–24), mask semantic | @Đặng Văn Huy | @Khúc Việt Anh | 🟡 100% | Đã gán xong 246 mask (25/25 frame), chuyển Stage: `validation` (@Khúc Việt Anh đang review) |
| 3 | Job #1659 — 25 ảnh (frame 25–49), mask semantic | @Nguyễn Văn Hân | — | 🟡 70% | Đạt ~70%, chưa sửa các mask vụn bị đè lấn nhau; chưa xong nên chưa cần review |
| 4 | Job #1660 — 25 ảnh (frame 50–74), mask semantic | @Nhữ Đình Chiến | @Đặng Văn Huy, @Khúc Việt Anh | 🟡 70% | Đạt ~70%, chưa sửa các mask vụn bị đè lấn nhau; khi xong sẽ do Huy và Việt Anh review |
| 5 | Job #1661 — 25 ảnh (frame 75–99), mask semantic | @Vũ Bảo Khánh | — | 🟡 70% | Đạt ~70%, chưa sửa các mask vụn bị đè lấn nhau; chưa xong nên chưa cần review |

*Mức hoàn thành:* ✅ xong và đã qua review · 🟡 đang làm (ghi %) · ⛔ bị chặn (ghi lý do) · ⬜ chưa bắt đầu

## Tổng kết

- **Tiến độ gán nhãn:**
  - **Job #1658 (Đặng Văn Huy):** Hoàn thành 100% gán nhãn với 246 mask / 25 ảnh, đã chuyển sang stage `validation` để Lead review.
  - **Job #1659 (Nguyễn Văn Hân):** Hoàn thành khoảng 70% khối lượng, hiện chưa xử lý xong các mẩu mask vụn và tình trạng đè lấn viền mask.
  - **Job #1660 (Nhữ Đình Chiến):** Hoàn thành khoảng 70% khối lượng, hiện chưa xử lý xong các mẩu mask vụn và tình trạng đè lấn viền mask.
  - **Job #1661 (Vũ Bảo Khánh):** Hoàn thành khoảng 70% khối lượng, hiện chưa xử lý xong các mẩu mask vụn và tình trạng đè lấn viền mask.
- **Tiến độ review chất lượng:**
  - Job #1658: @Khúc Việt Anh đang review 246 mask theo checklist, đối soát boundary bám sát ảnh gốc, Rule 01 (không chồng lấn class) và Rule 02 (không có lỗ hổng giả giữa các vùng kề nhau).
  - Các job #1659, #1660, #1661: Do hiện tại chưa hoàn thành (đang ở 70%) và còn tồn đọng lỗi kỹ thuật (mask vụn, đè mask) nên chưa đưa vào review chính thức. Các annotator sẽ tự dọn sạch (clean up) và ghép các mask vụn trước khi bàn giao review.
- **Edge case mới / đang bàn (Task #202):**
  - [P-005](../problem-backlog.md#p-005): Ranh giới `road` vs `sidewalk` tại các đoạn hạ vỉa hè / lối dốc xe ra vào (curb cut / driveway ramp).
  - [P-006](../problem-backlog.md#p-006): Phân định `vegetation` vs `terrain` tại thảm cỏ thấp xen kẽ gốc cây và bồn hoa (nguy cơ tạo nhiều mẩu mask vụn).
  - [P-007](../problem-backlog.md#p-007): Phân loại `person` vs `rider` trong tình huống người đi bộ dắt xe hai bánh trên đường.
- **Quy tắc và điểm cần lưu ý khi gán Semantic Segmentation (bám sát Guideline):**
  - **Các cặp class dễ nhầm:**
    - `road` vs `sidewalk`: `road` chỉ dành cho lòng đường xe chạy; `sidewalk` là vỉa hè/lối đi bộ tách biệt khỏi mặt đường.
    - `building` vs `wall`: `building` là mặt công trình/tòa nhà; `wall` là tường rào/tường ranh giới độc lập không phải mặt chính tòa nhà.
    - `wall` vs `fence`: phân biệt bề mặt kín/đặc (`wall`) với hàng rào có cấu trúc thanh/lưới (`fence`).
    - `vegetation` vs `terrain`: `vegetation` là cây, bụi rậm, tán lá; `terrain` là mặt đất tự nhiên, đất/cỏ phẳng thấp không phải dạng cây/bụi.
    - `person` vs `rider`: người đang điều khiển xe hai bánh là `rider` (chỉ tô pixel người), phương tiện giữ nhãn `motorcycle`/`bicycle`.
  - **Nguyên tắc che khuất & biên ảnh:**
    - `Occlusion`: Chỉ gán pixel nhìn thấy, tuyệt đối không suy đoán tô xuyên qua vật thể khác.
    - `Truncation`: Mask dừng tại mép viền ảnh, không vẽ ước lượng ngoài frame.
    - `Reflection/Shadow`: Không gán bóng đổ hoặc hình phản chiếu thành vật thể thật.

## Vướng mắc

- **Lỗi kỹ thuật về mask vụn và đè lấn:** Cả 3 job đang làm (#1659, #1660, #1661) đang gặp tình trạng phát sinh nhiều mẩu mask vụn li ti (fragmented pixels) và viền mask bị lem đè lên nhau giữa 2 class liền kề khi dùng công cụ Brush/Polygon, vi phạm Rule 01 (Mỗi pixel thuộc tối đa một class). Cần thời gian rà soát, tinh chỉnh cọ và gộp mask trước khi nộp review.
- **Khối lượng thao tác lớn:** Semantic segmentation đòi hỏi vẽ pixel mask tỉ mỉ cho toàn bộ bề mặt ảnh (19 class), tốn nhiều thời gian hơn đáng kể so với Bounding Box (Task 1), đặc biệt ở các vật thể mảnh (`pole`, `traffic_sign`, `traffic_light`) và ranh giới tán cây phức tạp (`vegetation`).
- **Chờ thống nhất 3 edge case mới:** [P-005](../problem-backlog.md#p-005), [P-006](../problem-backlog.md#p-006), [P-007](../problem-backlog.md#p-007) đang được đội thảo luận để đưa ra quyết định chốt, đảm bảo toàn đội gán đồng nhất.

## Kế hoạch tuần sau

- Các annotator xử lý triệt để các mask vụn, sửa các vùng bị chồng lấn mask và hoàn thiện nốt 30% còn lại của Job #1659, #1660, #1661.
- Phân công reviewer chính thức cho các job còn lại khi hoàn thành gán nhãn; @Đặng Văn Huy và Lead @Khúc Việt Anh tiến hành review Job #1660.
- Lead (@Khúc Việt Anh) hoàn tất nghiệm thu Job #1658 trên CVAT.
- Tổ chức họp đội chốt quyết định cho 3 ca khó [P-005], [P-006], [P-007].
- Chạy Quality Checklist trước khi nộp: rà soát ngẫu nhiên ít nhất 10 ảnh/job, đối soát không còn vùng chồng lấn, không có lỗ hổng giả, không sót class ngoài 19 class quy định.
- Nghiệm thu (`acceptance`) và chuyển trạng thái toàn bộ Task #202 sang `completed`, sẵn sàng export dataset segmentation.
