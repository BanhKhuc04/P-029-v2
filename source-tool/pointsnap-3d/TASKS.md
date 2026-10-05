# PointSnap 3D — Bảng phân việc

Chia nhỏ [kế hoạch 1,5 tuần](de-xuat-de-tai.md#7-kế-hoạch-triển-khai-15-tuần-có-cổng-kiểm-soát) thành từng việc có người phụ trách, hạn, việc phụ thuộc và tiêu chí xong.
Cập nhật cột **Trạng thái** mỗi khi bắt đầu hoặc xong một việc.

*Trạng thái:* ⬜ chưa làm · 🟡 đang làm · 🔍 chờ tester kiểm · ✅ xong · ⛔ bị chặn (ghi lý do)

## Quy trình làm việc

1. **Mỗi việc code một branch**, đặt tên theo mã việc: `feat/A3-cvat-reader`, `fix/B3-floating-ring`.
2. **Xong việc code thì mở Pull Request.** Người code còn lại đọc code; tester phụ trách chạy ca kiểm thử. Có ✅ của cả hai mới merge vào `main`.
3. **Tài liệu** (README, TASKS, nhật ký) được commit thẳng lên `main`.
4. **Họp nhanh 15 phút đầu mỗi ngày:** hôm qua xong gì, hôm nay làm gì, đang kẹt gì. Ghi việc kẹt vào cột Trạng thái.
5. **Tiêu chí xong chung cho mọi việc code:**
   - `pytest` chạy xanh; việc mới có test đi kèm.
   - Không commit token, dữ liệu nuScenes, file sinh ra (`.pcd`, báo cáo, bản chụp).
   - Đổi quy ước tọa độ hay định dạng thì cập nhật [`CONVENTIONS.md`](CONVENTIONS.md) trong cùng PR.

## Cổng kiểm soát

| Cổng | Ngày | Điều kiện đạt | Người nghiệm thu |
|---|---|---|---|
| **G0** | 06/10 | 1 cảnh nuScenes hiển thị đúng trên CVAT với nhãn chuẩn; `CONVENTIONS.md` đã chốt hệ tọa độ | Khánh |
| **G1** | 08/10 | Có kết quả kiểm chứng ground (đạt / không đạt); bộ phát hiện lơ lửng/lún và kích thước chạy trên 1 cảnh | Khánh, Hân |
| **G2** | 09/10 | Demo trọn quy trình `scan --flag` → lọc trong CVAT → `gate` trên 1 cảnh; 3 bộ phát hiện chạy trên cả bản mini | Khánh, Chiến |
| **G3** | 13/10 | Có số liệu cho mọi chỉ số ở mục 8 của đề xuất; ngưỡng chốt trong `config.yaml` | Khánh, Hân |

## Code A — Khúc Việt Anh (phía CVAT)

| Mã | Việc | Hạn | Cần trước | Tiêu chí xong | Trạng thái |
|---|---|---|---|---|---|
| **A1** | Khung dự án: package `pointsnap`, mô hình `Cuboid` / `Finding`, hình học cơ bản, đọc `config.yaml`, khung CLI, `CONVENTIONS.md` bản đầu | 05/10 | — | `pip install -e .` chạy được; `pointsnap --help` hiện đủ lệnh; test hình học và config xanh | ✅ |
| **A2** | Script chuyển nuScenes → CVAT: xuất `.pcd` cho keyframe `LIDAR_TOP`, đổi nhãn chuẩn về hệ LiDAR, tạo task 3D và nạp nhãn dạng track qua API | 06/10 | A1, B1, C1 | Chiến xác nhận 1 cảnh hiển thị đúng vị trí, kích thước, hướng (G0) | ⬜ |
| **A3** | Adapter CVAT — đọc: nhãn (shape, track, keyframe, `outside`), point cloud từng frame, ánh xạ frame ↔ `sample_token` | 07/10 | A2 | Đọc lại nhãn vừa nạp ở A2, so với nhãn gốc: lệch tâm < 1 mm, lệch yaw < 0,001 rad | ⬜ |
| **A4** | Adapter CVAT — ghi: lưu bản chụp JSON, ghi / xóa thuộc tính `pointsnap_error` theo id (PATCH) | 08/10 | A3 | Ghi rồi đọc lại khớp; hình học box không đổi; Chiến lọc được box có cờ trong canvas 3D | ⬜ |
| **A5** | `scan` (báo cáo HTML/CSV theo mẫu của Khánh, link mở frame) và `gate` (exit code 0/1) | 08/10 | A3, K2 | Báo cáo mở được, link đúng frame; `gate` trả đúng mã trên job có lỗi và job sạch | ⬜ |
| **A6** | Tích hợp end-to-end trên CVAT | 09/10 | A4, A5, B3, B4 | Demo G2 | ⬜ |
| **A7** | Bộ chèn lỗi giả theo đặc tả của Hân, có file log lỗi đã chèn | 12/10 | H2 | Chèn đúng loại, đúng mức; log khớp với nhãn sau khi chèn | ⬜ |
| **A8** | `diff`: so hai phiên bản nhãn, ghép box theo BEV IoU từng frame | 12/10 | A3 | Ra danh sách lỗi thật của cảnh tự gán | ⬜ |
| **A9** | Đóng gói, hướng dẫn cài đặt, dọn code | 14/10 | — | Chiến và Hân cài và chạy được trên máy khác theo README | ⬜ |

## Code B — Đặng Văn Huy (thuật toán)

| Mã | Việc | Hạn | Cần trước | Tiêu chí xong | Trạng thái |
|---|---|---|---|---|---|
| **B1** | Adapter nuScenes: đọc keyframe, point cloud `LIDAR_TOP`, pose xe thu, nhãn chuẩn → `Cuboid` trong hệ LiDAR | 05/10 | A1 | Số box mỗi frame khớp với nuScenes; box chuẩn nằm trên các điểm của đối tượng khi vẽ thử | ⬜ |
| **B2** | Module ground: lưới min-Z + RANSAC, mặt phẳng cục bộ trong vành đai quanh box | 07/10 | B1 | Chạy được trên cả bản mini; có số đo kiểm chứng ~200 box (trung vị, p90) | ⬜ |
| **B3** | Bộ phát hiện lơ lửng / lún | 08/10 | B2 | Bắt được ca kiểm thử của Hân; ghi "thiếu bằng chứng" khi vành đai ít điểm | ⬜ |
| **B4** | Thống kê kích thước theo class + bộ phát hiện sai kích thước (theo class, trong track) | 08/10 | B1 | Bắt được ca kiểm thử của Hân; không báo người đi bộ ở kiểu 2 | ⬜ |
| **B5** | Bộ phát hiện đứt track: nhảy vị trí, tách ID | 09/10 | B1 | Bắt được ca kiểm thử của Hân; chỉ báo frame lệch lớn nhất trong cụm | ⬜ |
| **B5b** | *(nếu kịp)* Luật khoảng nội suy dài | 13/10 | B5 | Như trên | ⬜ |
| **B6** | Script precision / recall theo loại lỗi và mức độ | 12/10 | A7 | Ra bảng chỉ số mục 8 từ log lỗi chèn + kết quả quét | ⬜ |
| **B7** | Chốt ngưỡng trên 5 cảnh tinh chỉnh | 13/10 | B6 | Ngưỡng ghi vào `config.yaml`, có lý do trong PR | ⬜ |

## Tester — Nhữ Đình Chiến (môi trường & CVAT)

| Mã | Việc | Hạn | Cần trước | Tiêu chí xong | Trạng thái |
|---|---|---|---|---|---|
| **C1** | Dựng CVAT Docker local, tạo tài khoản admin, tạo access token | 05/10 | — | Mở được `localhost:8080`; gửi token cho người code qua kênh riêng (không commit) | ⬜ |
| **C2** | Tải nuScenes v1.0-mini (~4 GB), đọc điều khoản sử dụng | 05/10 | — | Thư mục dữ liệu đủ `samples/`, `sweeps/`, `v1.0-mini/` | ⬜ |
| **C3** | Chạy script A2, kiểm bằng mắt 1 cảnh trên CVAT | 06/10 | A2 | Chụp màn hình 3 box (xe, người, xe đạp) đúng vị trí, hướng; ghi vào PR của A2 | ⬜ |
| **C4** | Spike trên giao diện: thuộc tính + bộ lọc, trục và yaw, cờ `outside`, link mở frame (mục 10 của đề xuất) | 06/10 | C1 | Kết quả ghi vào `CONVENTIONS.md` | ⬜ |
| **C5** | Cấu hình label spec: `pointsnap_error` (văn bản), `reviewed` (checkbox); tạo task trống cho cảnh tự gán | 06/10 | C1 | Hai thuộc tính xuất hiện trên mọi label | ⬜ |
| **C6** | Tự gán nhãn lại 1 cảnh (nửa số track) | 07/10 | C5 | Gán xong theo hướng dẫn K1 | ⬜ |
| **C7** | Kiểm A4: cờ lỗi ghi đúng box, lọc được, hình học không đổi | 08/10 | A4 | Ghi kết quả vào PR của A4 | ⬜ |
| **C8** | Kiểm toàn quy trình trên CVAT (G2) | 09/10 | A6 | Danh sách lỗi gửi người code | ⬜ |
| **C9** | Xem tay cảnh báo (cùng Hân); so khớp hai adapter trên 1 cảnh | 13/10 | B6 | Điền vào bảng đánh giá | ⬜ |
| **C10** | Làm lại toàn bộ quy trình theo README trên máy khác | 14/10 | A9 | Ghi lại chỗ README thiếu hoặc sai | ⬜ |

## Tester — Nguyễn Văn Hân (thuật toán & đánh giá)

| Mã | Việc | Hạn | Cần trước | Tiêu chí xong | Trạng thái |
|---|---|---|---|---|---|
| **H1** | Ca kiểm thử có đáp án cho 3 bộ phát hiện (ví dụ: box nâng Z thêm 25 cm → phải báo Lỗi ~25 cm) | 06/10 | — | Bảng ca kiểm thử: đầu vào, kết quả mong đợi; người code chuyển thành pytest | ⬜ |
| **H2** | Đặc tả bộ lỗi chèn giả: loại, mức, tỷ lệ, cách chọn track (mục 8.1 của đề xuất) | 06/10 | — | Đặc tả đủ để A7 code không phải hỏi lại | ⬜ |
| **H3** | Đối chiếu ground ước lượng bằng mắt trên một số box | 08/10 | B2 | Ghi các ca ground sai (dốc, bờ vỉa…) | ⬜ |
| **H4** | Chạy ca kiểm thử cho B3, B4, B5 | 09/10 | B3, B4, B5 | Kết quả ghi vào PR tương ứng | ⬜ |
| **H5** | Chủ trì đánh giá: xem tay từng cảnh báo (đúng / báo nhầm), điền bảng chỉ số | 13/10 | B6 | Bảng chỉ số mục 8 đầy đủ (G3) | ⬜ |

## Tester — Vũ Bảo Khánh (người dùng & tài liệu)

| Mã | Việc | Hạn | Cần trước | Tiêu chí xong | Trạng thái |
|---|---|---|---|---|---|
| **K1** | Hướng dẫn tự gán nhãn lại: cảnh nào, class nào, bán kính 30 m, chia track cho 2 người | 05/10 | — | Chiến và Khánh gán được mà không phải hỏi | ⬜ |
| **K2** | Mẫu báo cáo HTML (bố cục) và câu chữ cho từng loại thông báo lỗi | 06/10 | — | File mẫu + bảng câu chữ, A5 dùng được ngay | ⬜ |
| **K3** | Khoảng kích thước cho class ít mẫu (xe buýt, trailer, xe công trình…) | 06/10 | — | Bảng min / max l, w, h có nguồn tham khảo | ⬜ |
| **K4** | Tự gán nhãn lại 1 cảnh (nửa số track còn lại) | 08/10 | C5, K1 | Gán xong | ⬜ |
| **K5** | Dùng thử như annotator thật, góp ý báo cáo và quy trình | 09/10 | A6 | Danh sách góp ý gửi người code | ⬜ |
| **K6** | Đo thời gian review có / không có tool | 13/10 | A6 | Số liệu vào bảng chỉ số | ⬜ |
| **K7** | README, hướng dẫn sử dụng, video demo, báo cáo kết quả, slide | 14/10 | G3 | Đủ hồ sơ nộp | ⬜ |
| **K8** | Điều phối hằng ngày; nghiệm thu G0–G3; cập nhật nhật ký tuần | Hằng ngày | — | Mỗi cổng có biên bản đạt / không đạt | ⬜ |
