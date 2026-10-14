# Tiến độ PointSnap 3D — 14/10/2026

Đây là trạng thái **bản hợp nhất #48 và #61–70** đã kiểm trước khi merge. Danh sách nguồn gồm 11 PR người dùng yêu cầu merge; trạng thái merge và CI thực tế xem các PR trên GitHub. Không dùng tỷ lệ test PASS để tính tỷ lệ hoàn thành toàn dự án.

Cập nhật tiếp 14/10: kết nối GitHub đã hoạt động lại; **11/11 PR trong đợt này đã merge**, main local pull tới `44a0623`. Head cuối #69 đạt cả 5 job CI. API Docker đã rebuild/recreate theo main và healthy; bốn file package được lấy mẫu và cấu hình fit khớp main. [Tiến độ kiểm chất lượng/hỗ trợ sửa](assisted-repair-progress.md) ghi bộ 24 mẫu chờ người chấm và prototype xem trước chỉ đọc. Extension cài đặt chưa xác minh lại vì Computer Use chặn URL. Review cải tiến/evidence cũ giữ đúng thời điểm quan sát trước đồng bộ.

## Phần đã hoàn tất trong bản hợp nhất

| Phần | Trạng thái và bằng chứng |
|---|---|
| Ground và floating | #61 giữ outlier track có bằng chứng, siết hỗ trợ vỉa hè; không đổi thành thuật toán mặt đất chưa đối chiếu verdict |
| Cấu hình fit | #62 tắt mặc định fit.loose; #48 tách tối thiểu 30 điểm của vật/15 điểm ngoài và hạ ngưỡng warning rise xuống 0,4. Override riêng của dự án vẫn có hiệu lực |
| Static shift và G7 | #63 khôi phục wiring theo công tắc; #64 chuyển G7 sang precision tay từng luật và giữ proxy báo riêng |
| Camera và missing | #65 kiểm cache/runtime, #67 giữ lọc độ cao và thêm kiểm chuyển động/che khuất |
| Preview và extension | #66 dựng bằng chứng cho finding chưa có box; #68 thêm ảnh camera và sửa filter/scope; source đã có test, bản cài cần kiểm sau reload |
| Report API và release | #69 sửa JSON NumPy, metadata eligibility, runner archive-root và link cài đặt; giữ inventory lịch sử |
| Web UX và kiến trúc | #70 sửa focus splash, số frame, Task tên dài tràn màn hẹp; có ba sơ đồ và review Web/extension |

Các PR: [#48](https://github.com/AI20K-Build-Phase-Cohort-4A/P-029/pull/48), [#61](https://github.com/AI20K-Build-Phase-Cohort-4A/P-029/pull/61), [#62](https://github.com/AI20K-Build-Phase-Cohort-4A/P-029/pull/62), [#63](https://github.com/AI20K-Build-Phase-Cohort-4A/P-029/pull/63), [#64](https://github.com/AI20K-Build-Phase-Cohort-4A/P-029/pull/64), [#65](https://github.com/AI20K-Build-Phase-Cohort-4A/P-029/pull/65), [#66](https://github.com/AI20K-Build-Phase-Cohort-4A/P-029/pull/66), [#67](https://github.com/AI20K-Build-Phase-Cohort-4A/P-029/pull/67), [#68](https://github.com/AI20K-Build-Phase-Cohort-4A/P-029/pull/68), [#69](https://github.com/AI20K-Build-Phase-Cohort-4A/P-029/pull/69), [#70](https://github.com/AI20K-Build-Phase-Cohort-4A/P-029/pull/70).

## Kiểm thử mới cho bản hợp nhất

Candidate kiểm trước merge: `bd58da09f33fdae08430e234d2ca11811acc4438`. Sau cập nhật nhánh #69 với main mới, đã đối chiếu package, extension, tests, scripts và auto-tests với candidate này: không có khác biệt mã nguồn ở các phần đó. Cập nhật sau đó chỉ là báo cáo/evidence và inventory lịch sử.

| Kiểm tra | Kết quả |
|---|---|
| Full Python `tests` + `auto-tests`, Windows Python 3.11, có nuScenes mini | **859 PASS, 3 SKIP, 0 FAIL/XFAIL**; ba SKIP là live CVAT chưa bật trong pha này |
| Live CVAT chạy riêng | **3 PASS**, upload/read và flag/clear/geometry trên task thử do test tạo, đã cleanup; không ghi job 4 |
| Extension Node | **47 PASS, 0 FAIL** |
| Web JavaScript | Syntax check PASS |
| CI GitHub | Ma trận Ubuntu Python 3.10/3.11, Windows 3.12, artifact và extension; đọc trạng thái head mới trên PR #69/main |

859 và 3 là các ca khác nhau: tổng **862 ca Python được xác minh PASS**, không cộng test chạy lặp. [merge-validation.json](merge-validation.json) có JUnit counts và hash log. Lượt test đầu bị ngắt không có XML được giữ là INTERRUPTED. Lượt live đầu có 3 FAIL vì Docker/CVAT tắt, localhost:8080 từ chối kết nối; sau khởi động dịch vụ, cùng test đạt 3/3. Không đổi assertion để làm xanh.

## Chất lượng thuật toán: chưa nghiệm thu G7

Đã xác minh checkpoint **10 cảnh × 10 vòng**, seed 0, đủ metadata/package tree/config hash. Baseline là candidate **3a8bde2 trước PR #48**, không phải phép đo main mới:

| Tập | Box | Bắt / lỗi chèn | Warning/100 | Error/100 |
|---|---:|---:|---:|---:|
| Tuning | 8664 | 136/428 | 0,923 | 0,208 |
| Reviewed-heldout | 5440 | 125/348 | 2,040 | 0,460 |

[evaluation-before-fit-tuning.json](evaluation-before-fit-tuning.json) chứa provenance và số tổng hợp, không chứa raw annotation. Reviewed-heldout từng dùng để chấm tay/chỉnh evidence, nên chưa là nguồn độc lập. Catalog chèn core+c1 không đo recall/precision thật cho mọi luật camera, missing, spec hoặc Critic. #48 tăng độ nhạy fit.outside nên cần đánh giá mới và chấm mẫu trên cấu hình main sau merge.

## Tiến độ nghiệm thu và việc còn lại

| Cổng/phần việc | Trạng thái hiện tại | Điều còn thiếu |
|---|---|---|
| G6 — code và tích hợp cơ bản | Đã có bản hợp nhất, test tự động/dataset/live đạt trong phạm vi trên | Kiểm lại demo trên bộ cài cuối khi chọn cấu hình trình diễn |
| G7 — chất lượng thuật toán | **UNASSESSED** | Chấm tay theo từng luật, mẫu độc lập; đánh giá cấu hình sau #48. Không lấy finding/100 box thay precision |
| Học từ reviewer | Cơ chế đã kiểm | ≥40 verdict thật, đủ hai loại và ≥2 nhóm nguồn độc lập; verdict thử cơ chế không tính truth |
| G8 — UI/demo/hồ sơ | **PARTIAL** | Nạp lại extension đúng source, kiểm gắn cờ → sửa box → Save → quét lại; task spec-vn, video 3–5 phút, slide và báo cáo cuối |
| Model và usability | Có smoke GPU/model và review UX theo mốc đã ghi | Chưa nghiệm thu precision model, mọi cấu hình CPU/GPU, quét dài/OOM hoặc nghiên cứu với người dùng thật |

Theo lịch tuần gia hạn trong repo: G7 ngày **15/10**, G8 ngày **17/10**, nộp **18/10/2026**. Mốc này là kế hoạch, không tự đánh dấu hoàn thành. Bảng TASKS cũ còn R1/T1/T2/R2/R3 chưa chốt; nhánh local redesign extension và nhật ký không phải các PR trong danh sách 11 ở trên.

Sản phẩm hiện ở giai đoạn **nghiệm thu chất lượng và chuẩn bị demo/hồ sơ**, có code và bằng chứng test để demo local trong phạm vi đã kiểm. Các báo cáo 13/10 và review UX ban đầu giữ đúng SHA/runtime lịch sử; [kiến trúc](../../source-tool/pointsnap-3d/docs/architecture-system.md) và [review UX](architecture-ux-review.md) có phạm vi riêng.
