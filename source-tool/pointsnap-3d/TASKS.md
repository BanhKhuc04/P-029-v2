# PointSnap 3D — Bảng phân việc (4 ngày: 06/10 – 09/10/2026)

Chia nhỏ [kế hoạch 4 ngày](de-xuat-de-tai.md#7-kế-hoạch-triển-khai-4-ngày-có-cổng-kiểm-soát) thành từng việc có người phụ trách, hạn, việc phụ thuộc và tiêu chí xong.
Việc của từng người theo ngày: [`giao-viec/`](giao-viec/). Cập nhật cột **Trạng thái** mỗi khi bắt đầu hoặc xong một việc.

*Trạng thái:* ⬜ chưa làm · 🟡 đang làm · 🔍 chờ tester kiểm · ✅ xong · ⛔ bị chặn (ghi lý do)

## Quy trình làm việc

1. **Mỗi việc code một branch**, đặt tên theo mã việc: `feat/A3-cvat-reader`, `fix/B3-floating-ring`.
2. **Xong việc code thì mở Pull Request.** Người code còn lại đọc code; tester phụ trách chạy ca kiểm thử. Có ✅ của cả hai mới merge vào `main`.
3. **Tài liệu** (README, TASKS, giao việc, nhật ký, `docs/`) được commit thẳng lên `main`.
4. **Họp nhanh 15 phút đầu mỗi ngày:** hôm qua xong gì, hôm nay làm gì, đang kẹt gì. Kẹt quá 1 giờ thì báo ngay trong nhóm.
5. **Không có ngày dự phòng:** trễ thì cắt theo thứ tự ở [mục 7 của đề xuất](de-xuat-de-tai.md#7-kế-hoạch-triển-khai-4-ngày-có-cổng-kiểm-soát), không dời cổng.
6. **Tiêu chí xong chung cho mọi việc code:**
   - `pytest` chạy xanh; việc mới có test đi kèm.
   - Không commit token, dữ liệu nuScenes, file sinh ra (`.pcd`, báo cáo, bản chụp).
   - Đổi quy ước tọa độ hay định dạng thì cập nhật [`CONVENTIONS.md`](CONVENTIONS.md) trong cùng PR.

## Cổng kiểm soát

| Cổng | Hạn | Điều kiện đạt | Người nghiệm thu |
|---|---|---|---|
| **G0** | Tối 06/10 (muộn nhất 10h 07/10) | 1 cảnh nuScenes hiển thị đúng trên CVAT với nhãn chuẩn; `CONVENTIONS.md` đã chốt hệ tọa độ | Khánh |
| **G1** | Cuối ngày 07/10 | Có kết quả kiểm chứng ground (đạt / không đạt); phát hiện lơ lửng/lún và kích thước chạy trên 1 cảnh; ghi được cờ lỗi lên CVAT | Khánh, Hân |
| **G2** | Cuối ngày 08/10 | Demo trọn quy trình `scan --flag` → lọc trong CVAT → `gate` trên 1 cảnh; 3 bộ phát hiện chạy trên cả bản mini; có bộ lỗi chèn giả | Khánh, Chiến |
| **G3** | 12h 09/10 | Có số liệu cho mọi chỉ số ở mục 8 của đề xuất; ngưỡng chốt trong `config.yaml` | Khánh, Hân |
| **Nộp** | Cuối ngày 09/10 | Code, README, video demo, báo cáo kết quả, slide | Khánh |

## Code A — Khúc Việt Anh (phía CVAT)

| Mã | Việc | Hạn | Cần trước | Tiêu chí xong | Trạng thái |
|---|---|---|---|---|---|
| **A1** | Khung dự án: package `pointsnap`, mô hình dữ liệu, hình học, cấu hình, CLI, `CONVENTIONS.md` | 05/10 | — | `pip install -e .`; `pointsnap --help`; test xanh | ✅ [PR #1](https://github.com/AI20K-Build-Phase-Cohort-4A/P-029/pull/1) |
| **B1** | Đọc nuScenes: keyframe, point cloud `LIDAR_TOP`, pose xe thu, nhãn chuẩn → `Cuboid` trong hệ LiDAR (làm thay Huy) | 06/10 | A1 | Số box mỗi frame khớp với nuScenes; box chuẩn nằm trên các điểm của đối tượng | 🔍 chờ Huy review; chờ dữ liệu thật để kiểm |
| **A2** | Chuyển 1 cảnh nuScenes → CVAT: ghi `.pcd`, tạo task 3D, nạp nhãn chuẩn dạng track | 06/10 | B1, C1, C2 | Chiến xác nhận cảnh hiển thị đúng vị trí, kích thước, hướng (G0) | ⬜ |
| **A3** | Adapter CVAT đọc nhãn (shape, track, keyframe, `outside`); point cloud lấy từ thư mục nuScenes theo ánh xạ frame ↔ `sample_token` | 07/10 | A2 | Đọc lại nhãn đã nạp ở A2, so với nhãn gốc: lệch tâm < 1 mm, lệch yaw < 0,001 rad | ⬜ |
| **A4** | Lưu bản chụp JSON; ghi / xóa thuộc tính `pointsnap_error` theo id (PATCH) | 07/10 | A3 | Ghi rồi đọc lại khớp; hình học box không đổi; Chiến lọc được box có cờ (G1) | ⬜ |
| **A5** | `scan` (báo cáo HTML/CSV theo mẫu của Khánh, link mở frame) và `gate` (exit code 0/1) | 08/10 | A3, K2 | Báo cáo mở được, link đúng frame; `gate` trả đúng mã trên job có lỗi và job sạch | ⬜ |
| **A6** | Tích hợp end-to-end trên CVAT | 08/10 | A4, A5, B3–B5 | Demo G2 | ⬜ |
| **A7** | Bộ chèn lỗi giả theo đặc tả của Hân, kèm file log lỗi đã chèn | 08/10 | B1, H2 | Chèn đúng loại, đúng mức; log khớp với nhãn sau khi chèn | ⬜ |
| **A9** | Đóng gói, hướng dẫn cài đặt, dọn code | 09/10 | — | Chiến và Hân cài và chạy được trên máy khác theo README | ⬜ |

## Code B — Đặng Văn Huy (thuật toán)

| Mã | Việc | Hạn | Cần trước | Tiêu chí xong | Trạng thái |
|---|---|---|---|---|---|
| **B2** | Module ground: lưới min-Z + RANSAC, mặt phẳng cục bộ trong vành đai quanh box; kiểm chứng ~200 box chuẩn | Sáng 07/10 | A1; dữ liệu nuScenes trên máy Huy | Test trên point cloud giả: sai số < 2 cm; trên nuScenes: có số trung vị, p90 | ⬜ |
| **B3** | Phát hiện lơ lửng / lún | 07/10 | B2 | Bắt được ca kiểm thử của Hân; ghi "thiếu bằng chứng" khi vành đai ít điểm | ⬜ |
| **B4** | Thống kê kích thước theo class + phát hiện sai kích thước (theo class, trong track) | 07/10 | B1 | Bắt được ca kiểm thử của Hân; không báo người đi bộ ở kiểu trong track | ⬜ |
| **B5** | Phát hiện đứt track: nhảy vị trí, tách ID | 08/10 | B1 | Bắt được ca kiểm thử của Hân; chỉ báo frame lệch lớn nhất trong cụm | ⬜ |
| **B6** | Script precision / recall theo loại lỗi và mức độ | 08/10 | A7 | Ra bảng chỉ số mục 8 từ log lỗi chèn + kết quả quét | ⬜ |
| **B7** | Chốt ngưỡng trên 5 cảnh tinh chỉnh | Sáng 09/10 | B6 | Ngưỡng ghi vào `config.yaml`, có lý do trong PR | ⬜ |

## Tester — Nhữ Đình Chiến (môi trường & CVAT)

| Mã | Việc | Hạn | Cần trước | Tiêu chí xong | Trạng thái |
|---|---|---|---|---|---|
| **C1** | Dựng CVAT Docker local, tạo tài khoản admin, tạo access token | Sáng 06/10 | — | Mở được `localhost:8080`; gửi token cho Việt Anh qua kênh riêng (không commit) | ⬜ |
| **C2** | Tải nuScenes v1.0-mini (~4 GB). Huy và Việt Anh tự tải một bản về máy mình | Sáng 06/10 | — | Thư mục dữ liệu đủ `samples/`, `sweeps/`, `v1.0-mini/` | ⬜ |
| **C5** | Label spec: `pointsnap_error` (văn bản), `reviewed` (checkbox) | 06/10 | C1 | Hai thuộc tính xuất hiện trên mọi label | ⬜ |
| **C4** | Spike trên giao diện: lọc theo thuộc tính, trục và yaw, cờ `outside`, link mở frame | 06/10 | C1 | Kết quả gửi Việt Anh để ghi vào `CONVENTIONS.md` | ⬜ |
| **C3** | Chạy script A2, kiểm bằng mắt 1 cảnh trên CVAT (G0) | Tối 06/10 | A2 | Chụp màn hình 3 box (xe, người, xe đạp) đúng vị trí, hướng; ghi vào PR của A2 | ⬜ |
| **C7** | Kiểm A3, A4: đọc nhãn đúng; cờ lỗi đúng box, lọc được, hình học không đổi | 07/10 | A4 | Ghi kết quả vào PR | ⬜ |
| **C8** | Kiểm toàn quy trình trên CVAT (G2) | 08/10 | A6 | Danh sách lỗi gửi người code | ⬜ |
| **C9** | Cùng Hân xem tay cảnh báo không khớp lỗi chèn nào | Sáng 09/10 | B6 | Điền vào bảng đánh giá | ⬜ |
| **C10** | Làm lại toàn bộ quy trình theo README trên máy khác | Chiều 09/10 | A9 | Ghi lại chỗ README thiếu hoặc sai | ⬜ |

## Tester — Nguyễn Văn Hân (thuật toán & đánh giá)

| Mã | Việc | Hạn | Cần trước | Tiêu chí xong | Trạng thái |
|---|---|---|---|---|---|
| **H1** | Ca kiểm thử có đáp án cho 3 bộ phát hiện (`docs/ca-kiem-thu.md`) | 06/10 | — | Mỗi ca có đầu vào và kết quả mong đợi; người code chuyển thành pytest | ⬜ |
| **H2** | Đặc tả bộ lỗi chèn giả (`docs/dac-ta-loi-chen.md`) | 06/10 | — | Đủ để A7 code không phải hỏi lại | ⬜ |
| **H3** | Đối chiếu ground ước lượng bằng mắt (`docs/kiem-tra-ground.md`) | 07/10 | B2 | Ghi các ca ground sai (dốc, bờ vỉa…) | ⬜ |
| **H4** | Chạy ca kiểm thử cho B3, B4 (07/10) và B5 (08/10) | 08/10 | B3–B5 | Kết quả ghi vào PR tương ứng | ⬜ |
| **H5** | Chủ trì đánh giá: xem tay cảnh báo, điền bảng chỉ số (`docs/danh-gia.md`) | 12h 09/10 | B6 | Bảng chỉ số mục 8 đầy đủ (G3) | ⬜ |

## Tester — Vũ Bảo Khánh (người dùng & tài liệu)

| Mã | Việc | Hạn | Cần trước | Tiêu chí xong | Trạng thái |
|---|---|---|---|---|---|
| **K2** | Mẫu báo cáo HTML (bố cục) và câu chữ cho từng loại thông báo lỗi (`docs/mau-bao-cao.md`) | 06/10 | — | A5 dùng được ngay | ⬜ |
| **K3** | Khoảng kích thước cho class ít mẫu: `bus`, `trailer`, `construction_vehicle` (`docs/kich-thuoc-class-it-mau.md`) | 06/10 | — | Bảng min / max l, w, h có nguồn tham khảo | ⬜ |
| **K5** | Dùng thử như annotator thật, góp ý báo cáo và quy trình | 08/10 | A6 | Danh sách góp ý gửi Việt Anh | ⬜ |
| **K7** | README, hướng dẫn sử dụng, video demo, báo cáo kết quả, slide | 09/10 | G3 | Đủ hồ sơ nộp | ⬜ |
| **K8** | Điều phối hằng ngày; nghiệm thu G0–G3; cập nhật nhật ký tuần | Hằng ngày | — | Mỗi cổng có kết quả đạt / không đạt | ⬜ |

## Đã cắt khỏi kế hoạch 4 ngày

Tự gán nhãn lại một cảnh (K1, K4, C6), lệnh `diff` (A8), đo thời gian review (K6), luật khoảng nội suy dài (B5b), so khớp hai adapter. Xem [Hướng phát triển](de-xuat-de-tai.md#11-hướng-phát-triển).
