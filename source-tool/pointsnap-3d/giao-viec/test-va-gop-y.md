# Test và góp ý phát triển — Khánh, Chiến, Hân (08/10 – 09/10)

Code đã xong và đã vào `main` (PR #18 – #23), gồm cả **giao diện web** (`pointsnap ui`). Từ giờ tới lúc nộp, phần
test và báo cáo do Khánh, Chiến, Hân làm. Việt Anh và Huy chỉ sửa lỗi khi được báo.

| Hạn | Việc |
|---|---|
| Tối 08/10 | Chiến cài xong môi trường; Khánh có khung báo cáo và slide (R1) |
| **12h 09/10 (G3)** | Test xong: `docs/loi-khi-test.md`, `docs/danh-gia.md` đủ số liệu |
| **16h 09/10** | Chốt **báo cáo góp ý phát triển** `docs/gop-y-phat-trien.md` |
| Cuối ngày 09/10 | Báo cáo, slide, video, nhật ký; nộp |

**Quy tắc:**
- Không sửa code.
- Tài liệu làm trên branch riêng (`docs/test-<tên>`), mở PR, không push thẳng `main`.
- Không gửi token CVAT cho ai, không chụp màn hình có token.
- Kẹt ở đâu nhắn Việt Anh ngay, đừng đợi.

Hướng dẫn cài: [README](../../README.md). Các bước test bằng dòng lệnh (bản cũ): [`review-test.md`](review-test.md).

## Nhữ Đình Chiến — T1: test quy trình, video demo

- [ ] **Cài trên máy mình** theo README: Docker Desktop + CVAT 2.77.0, Python 3.11, nuScenes v1.0-mini, `pip install -e .`.
  Chỗ nào README thiếu hoặc sai thì ghi lại, đó cũng là lỗi.
- [ ] **Tạo task**: `pointsnap nuscenes to-cvat --scene scene-0061 --out <thư mục>/cvat --upload`. Mở task trên CVAT,
  phải thấy point cloud, box và ảnh 6 camera.
- [ ] **Test giao diện web** (`pointsnap ui`, mở http://127.0.0.1:8765):
  1. Tạo dự án; tab **Kết nối**: nhập URL CVAT, token, thư mục nuScenes, thư mục bản xuất → **Kiểm tra kết nối**.
  2. Tab **Quét**: chọn task / job → quét (chưa gắn cờ). Thanh tiến độ chạy, giao diện không treo.
  3. Tab **Kết quả**: kết luận `gate`, thẻ số Lỗi / Cảnh báo; lọc theo mức, loại lỗi, class, chữ; bấm **Mở CVAT** xem
     có nhảy đúng frame; tải báo cáo HTML / CSV.
  4. **Quét lại & Gắn cờ** → trong CVAT: F5, Filters → Attributes → `pointsnap_error` is not empty. Box có cờ có đúng là
     box trong bảng không?
  5. Sửa 3–5 box có cờ trong CVAT, Save → quét lại: cờ của box đã sửa phải mất, số lỗi giảm. Tab **Lịch sử** thấy lỗi
     giảm dần.
  6. Tab **Guideline**: tắt một luật (vd `track_jump`) → quét lại, lỗi loại đó phải biến mất; xóa một class trong khoảng
     kích thước → lưu → tải lại trang, class phải mất; sửa YAML sai cú pháp → phải báo lỗi rõ, không lưu.
  7. Tạo dự án thứ hai, xóa nó (phải gõ lại tên mới xóa được).
- [ ] **So với dòng lệnh**: `pointsnap scan --job <id>` và `pointsnap gate --job <id>` cho cùng số Lỗi / Cảnh báo như
  giao diện không?
- [ ] Ghi mọi lỗi vào `docs/loi-khi-test.md`, mỗi lỗi một mục: bước làm, mong đợi, thực tế, ảnh, mức (Chặn / Nặng / Nhẹ).
  Hạn 12h 09/10.
- [ ] Xong T1 thì phụ Hân xem tay (phần kích thước và đứt track).
- [ ] **Chiều 09/10 — video demo 3–5 phút** bằng giao diện web: tạo dự án → quét → xem kết quả, mở CVAT xem ảnh camera
  → gắn cờ → sửa box → quét lại, cờ mất → `gate` ĐẠT / KHÔNG ĐẠT → tab Lịch sử.

## Nguyễn Văn Hân — T2: xem tay cảnh báo, điền bảng chỉ số (chủ trì)

- [ ] Quét job scene-0061 bằng giao diện (máy Chiến hoặc máy Việt Anh). Tải `report.csv` của lần quét để làm bảng.
- [ ] **Xem tay 50 mục**: khoảng 20 lơ lửng / lún, 15 kích thước, 15 đứt track; ưu tiên mức Lỗi. Mỗi mục:
  - Bấm **Mở CVAT**, nhìn point cloud và ảnh camera.
  - Ghi **Đúng** (nhãn thật sự sai) / **Báo nhầm** / **Không chắc**, kèm một câu lý do (vd "đáy box nằm trên bờ vỉa").
  - Chia việc: Hân làm lơ lửng / lún; Chiến làm kích thước và đứt track sau khi xong T1.
- [ ] Tính **precision xem tay** cho từng loại lỗi = Đúng / (Đúng + Báo nhầm).
- [ ] Điền `docs/danh-gia.md` đủ các chỉ số mục 8.2 của [bản đề xuất](../de-xuat-de-tai.md). Ghi rõ:
  - số nào lấy từ đánh giá tự động (`docs/ket-qua-danh-gia-tu-dong.md`);
  - số nào do nhóm xem tay, kèm số mục đã xem.

  Hạn 12h 09/10 (G3).
- [ ] Ghi các kiểu báo nhầm / bỏ sót hay gặp vào mục 3 của báo cáo góp ý.

## Vũ Bảo Khánh — báo cáo, slide, tổng hợp góp ý

- [ ] **R1 (tối 08/10)**: khung `docs/bao-cao-ket-qua.md` và slide.
  - Nội dung: bối cảnh, vấn đề, giải pháp, cách đánh giá (lấy từ bản đề xuất); để trống số liệu.
  - Chụp giao diện có sẵn ở `docs/screenshots/`.
- [ ] **Đọc README như người mới**: đánh dấu câu khó hiểu, thiếu bước; ghi vào mục 2 của báo cáo góp ý.
- [ ] **Tổng hợp báo cáo góp ý phát triển** (mẫu bên dưới) từ phần của cả ba người. Hạn 16h 09/10.
  Đưa mục 5 (Top 3) vào phần Hướng phát triển của báo cáo kết quả.
- [ ] **Chiều 09/10**:
  - Điền số liệu của Hân vào báo cáo và slide.
  - Chốt nhật ký tuần 04: đổi A2b, A10, A11 thành ✅.
  - Nộp cuối ngày.

## Báo cáo góp ý phát triển — `docs/gop-y-phat-trien.md` (bắt buộc)

Mỗi người viết phần mình đã test, Khánh gộp lại. Viết cụ thể, có ví dụ (job, frame, track id, ảnh).

```markdown
# Góp ý phát triển PointSnap 3D (sau test 09/10)

## 1. Lỗi gặp khi test
| # | Ở đâu (giao diện / CLI / README) | Bước làm | Mong đợi | Thực tế | Mức (Chặn / Nặng / Nhẹ) | Người ghi |

## 2. Chỗ khó dùng
Giao diện, README, thông báo lỗi khó hiểu; mỗi ý: chỗ nào, vì sao khó, nên sửa thế nào.

## 3. Báo nhầm / bỏ sót hay gặp
| Loại lỗi | Ví dụ (job, frame, track) | Tool báo gì | Thực tế thế nào | Vì sao tool sai (đoán) |

## 4. Đề xuất tính năng
| Vấn đề | Đề xuất | Lợi ích cho annotator / reviewer | Ưu tiên (Cao / TB / Thấp) |

## 5. Top 3 việc nên làm tiếp sau khi nộp
1. ... — lý do
2. ...
3. ...
```
