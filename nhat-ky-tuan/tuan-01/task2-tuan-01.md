# Nhật ký tuần 01 — Task 2 · 14/09 – 20/09/2026

**Lead tuần này:** @Khúc Việt Anh  
**Dữ liệu / task CVAT:** Task #202 (`W1-SEG-G4-T1`) — [CVAT Task 202](https://cvat.note.transformerlabs.ai/tasks/202)  
**Nhiệm vụ:** Semantic Segmentation (19 class theo guideline AI20K) trên 100 ảnh giao thông

## Thành viên và phân công

| Thành viên | Vị trí | Phân công tuần này |
|---|---|---|
| Khúc Việt Anh | Lead · Reviewer | Điều phối Task #202, phân chia job, theo dõi tiến độ, review chéo Job #1658, #1660, #1661 và nghiệm thu chung |
| Đặng Văn Huy | Annotator · Reviewer | Gán nhãn Job #1658 (Frame 0–24), review chéo Job #1659 |
| Nguyễn Văn Hân | Annotator · Reviewer | Gán nhãn Job #1659 (Frame 25–49), review chéo Job #1658 |
| Nhữ Đình Chiến | Annotator · Reviewer | Gán nhãn Job #1660 (Frame 50–74), review chéo Job #1661 |
| Vũ Bảo Khánh | Annotator · Reviewer | Gán nhãn Job #1661 (Frame 75–99), review chéo Job #1659, #1660 |

## Công việc

| # | Nội dung công việc | Annotator | Reviewer (Random/Chéo) | Hoàn thành | Ghi chú |
|---|---|---|---|---|---|
| 1 | Họp đầu tuần, thống nhất guideline Semantic Segmentation (19 class) và chia job Task #202 | Cả đội | — | ✅ 100% | Phân chia 4 job (mỗi job 25 frame), thống nhất color map và 3 rule cốt lõi |
| 2 | Job #1658 — 25 ảnh (frame 0–24), mask semantic | @Đặng Văn Huy | @Nguyễn Văn Hân, @Khúc Việt Anh | ✅ 100% | Đã gán xong 246 mask (25/25 frame), đã review chéo và nghiệm thu Stage `acceptance` |
| 3 | Job #1659 — 25 ảnh (frame 25–49), mask semantic | @Nguyễn Văn Hân | @Vũ Bảo Khánh, @Đặng Văn Huy | ✅ 100% | Đã gán xong 262 mask (25/25 frame), đã clean mask vụn, review chéo đạt chuẩn |
| 4 | Job #1660 — 25 ảnh (frame 50–74), mask semantic | @Nhữ Đình Chiến | @Khúc Việt Anh, @Vũ Bảo Khánh | ✅ 100% | Đã gán xong 254 mask (25/25 frame), xử lý triệt để đè viền, review chéo đạt chuẩn |
| 5 | Job #1661 — 25 ảnh (frame 75–99), mask semantic | @Vũ Bảo Khánh | @Nhữ Đình Chiến, @Khúc Việt Anh | ✅ 100% | Đã gán xong 278 mask (25/25 frame), xử lý boundary vật thể nhỏ, review chéo đạt chuẩn |

*Mức hoàn thành:* ✅ xong và đã qua review · 🟡 đang làm (ghi %) · ⛔ bị chặn (ghi lý do) · ⬜ chưa bắt đầu

## Tổng kết

- **Tiến độ gán nhãn & Sản phẩm hoàn thành:**
  - **Job #1658 (Đặng Văn Huy):** 246 mask / 25 ảnh — Đã qua review chéo bởi @Nguyễn Văn Hân và Lead @Khúc Việt Anh, chuyển sang stage `acceptance`.
  - **Job #1659 (Nguyễn Văn Hân):** 262 mask / 25 ảnh — Đã xử lý triệt để các mẩu mask vụn và khử lem biên viền, review chéo bởi @Vũ Bảo Khánh và @Đặng Văn Huy.
  - **Job #1660 (Nhữ Đình Chiến):** 254 mask / 25 ảnh — Đã xử lý phân định dải cỏ và cây bụi, review chéo bởi @Khúc Việt Anh và @Vũ Bảo Khánh.
  - **Job #1661 (Vũ Bảo Khánh):** 278 mask / 25 ảnh — Đã hoàn thiện gán nhãn chi tiết vật thể mảnh và người, review chéo bởi @Nhữ Đình Chiến và Lead @Khúc Việt Anh.
  - **Tổng toàn task:** Đạt **1.040 mask semantic / 100 frame** (100% hoàn thành).
- **Tiến độ review chất lượng (Cross-review ngẫu nhiên):**
  - Thực hiện review chéo ngẫu nhiên 100% các job theo ma trận phân công độc lập:
    - Job #1658: @Nguyễn Văn Hân & @Khúc Việt Anh
    - Job #1659: @Vũ Bảo Khánh & @Đặng Văn Huy
    - Job #1660: @Khúc Việt Anh & @Vũ Bảo Khánh
    - Job #1661: @Nhữ Đình Chiến & @Khúc Việt Anh
  - Kiểm tra nghiêm ngặt theo Quality Checklist:
    - [x] Không còn tình trạng 2 mask/class chồng lấn pixel (Rule 01).
    - [x] Không còn lỗ hổng giả giữa các vùng tiếp giáp (road, sidewalk, building, terrain, sky).
    - [x] Boundary bám sát biên nhìn thấy của vật thể, không suy đoán vùng bị che khuất (Occlusion) hoặc ngoài biên (Truncation).
    - [x] Kiểm tra ngẫu nhiên ít nhất 10 ảnh/job trước khi nghiệm thu cuối cùng.
- **Tình trạng giải quyết các vướng mắc / Edge case:**
  - Các edge case [P-005](../../problem-backlog.md#p-005), [P-006](../../problem-backlog.md#p-006), [P-007](../../problem-backlog.md#p-007) đã được đề xuất phương án và đưa vào Sổ quyết định để làm chuẩn cho việc nghiệm thu cuối cùng.
  - Vấn đề mask vụn và lem viền công cụ đã được các thành viên xử lý dứt điểm trước khi bàn giao review.

## Vướng mắc

- Đã giải quyết xong các vướng mắc kỹ thuật về mask vụn và đè viền mask.
- Thao tác gán semantic tốn thời gian hơn BBox gấp 3-4 lần, tuy nhiên nhờ phân công chéo review ngẫu nhiên nên tốc độ phát hiện lỗi và sửa chữa tăng đáng kể, không bị tồn đọng việc.

## Kế hoạch tuần sau

- Lead (@Khúc Việt Anh) nghiệm thu lần cuối trên giao diện CVAT và chuyển trạng thái toàn bộ Task #202 sang `completed`.
- Cập nhật chính thức các quyết định [QĐ-004], [QĐ-005], [QĐ-006], [QĐ-007] vào Sổ quyết định (`so-quyet-dinh.md`) và đóng các issue tương ứng trong Problem Backlog.
- Export toàn bộ dataset Semantic Segmentation (PNG 8-bit mask / CVAT format) kết hợp với Bounding Box tuần 1 để chuẩn bị dữ liệu cho tuần tiếp theo.
