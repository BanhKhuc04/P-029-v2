# Báo cáo phần 03 — dữ liệu, nuScenes và CVAT

## 1. Kết quả

- Review ngày 11/10/2026, Asia/Saigon; code `40ac166`, nhánh `review/03-data-cvat-integrations`.
- Base phần 02 `82fc8b8c4b45153c175a89387760796f8746484d`; main đã fetch vẫn `5dcc97f`. Người nhận mở PR độc lập; chưa merge main.
- **367 test Python đạt, 0 skip; 7 test Node đạt.** 49 ca hồi quy mới và 1 ca live mới; 1 warning Starlette/httpx được giữ lại.
- CVAT Docker local 2.78.1, Python 3.12.14, Node 24.19.0; nuScenes mini thật tại `C:/Users/Han/Downloads/v1.0-mini`.
- Scene-0061 thật: 39 frame, 234 ảnh/6 camera, 3333 box chuẩn nhìn thấy; 3900 keyframe gồm markers, 249 track. Đọc lại tâm/yaw lệch **0 m/0 rad**, dims khớp; gắn 1 cờ→lần hai 0 thay đổi→gỡ 1 cờ, bảo toàn hình học. Task/job 27 đã xóa.

Đọc [bàn giao](03-handoff.md), [mapping và hợp đồng](03-mapping.md), [bằng chứng](evidence/03/test-results.md).

## 2. Phạm vi

Đã đọc client/reader/writer/shapes CVAT, nuScenes reader, PCD/taxonomy/converter, CLI common/serialization; đối chiếu caller CLI/Web và test hiện có. Đối chiếu local mã nguồn CVAT dataset_manager: update xóa/tạo lại và mutable attributes kế thừa theo keyframe. Có fixture đáp án tính tay, test mock, dataset thật, task CVAT thử và thao tác trình duyệt.

Chỉ đưa code/test liên quan và tài liệu review vào nhánh. File API/Docker/auto-tests local chưa tracked, token, dataset, cloud/ảnh, snapshot và output giữ ngoài commit. `tests/test_report_api.py` thuộc API local chưa bàn giao nên không tính trong suite này.

## 3. 18 ca review

| Ca | Kết quả và bằng chứng thực hiện |
|---|---|
| R03-01 | Đạt fixture tính tay: global→ego→sensor, `[w,l,h]→[l,w,h]`, yaw/quaternion và đổi tâm ngược world; dataset thật kiểm số điểm trong box. Mô hình yaw có giới hạn tilt đã ghi |
| R03-02 | Đạt: PCD/box cùng R −90°, pose mới bảo toàn world; ManifestFrames cùng phép đổi; không quay lần hai |
| R03-03 | Đạt định dạng được hỗ trợ: binary float32, header/count/stride/byte/finite và empty cloud; ASCII bị từ chối rõ, chưa hỗ trợ ASCII/compressed |
| R03-04 | Đạt: thứ tự tên file/sample/frame/count, thiếu/trùng/swap bị từ chối; metadata toàn task với biên JobData. Không có fixture upload task subsampling/frame_filter ngoài luồng converter hiện tại |
| R03-05 | Đạt scene thật: 234 ảnh, 6 related_files ở mỗi frame; browser hiển thị CAM_BACK/BACK_LEFT/BACK_RIGHT và lần lượt FRONT/FRONT_LEFT/FRONT_RIGHT tại frame 0 |
| R03-06 | Đạt test/đọc bảng 10 class và spec-vn, loại category/min-points có chủ đích; attrs suy ra/default ghi rõ, không coi là nhãn thực tế đã xác minh tay |
| R03-07 | Đạt shape API/mock 16 số và live shape có rx=.1, ry=−.2; tâm/yaw dưới 1 mm/0,001 rad, attrs/points không đổi sau cờ |
| R03-08 | Đạt: keyframe/outside, gap ≤6/>6, occluded và stop_frame theo hợp đồng phần 02; markers thật được giữ khi upload |
| R03-09 | Đạt sau sửa: track attrs→keyframe và carry tới reset, mảng đảo thứ tự không đổi ngữ nghĩa; immutable flag bị từ chối |
| R03-10 | Đạt mock pagination absolute/relative/cycle; token không gửi origin khác; redirects không tự theo; live dùng Bearer/Accept của CVAT. Không chứng nhận toàn bộ bảo mật, phần 06 tiếp tục |
| R03-11 | Đạt mock 401/403/404/406/302, connection/timeout/upload failed/JSON lỗi; upload fail cleanup task mới; live upload/nạp nhãn và jobs hoàn tất |
| R03-12 | Đạt: source ID/track ID/fallback chính xác; thiếu/ID lạ unmatched, không gắn mọi box trong frame; keyframe đổi ID chỉ rebind có điều kiện |
| R03-13 | Đạt mock và CVAT thật: đủ track/keyframe gốc, compare raw payload loại chỉ IDs cấp lại/cờ; giữ dims/yaw/roll/pitch/outside/occluded/attrs khác |
| R03-14 | Đạt live: gắn lần hai không PATCH thay đổi nội dung; xóa cờ sau sửa/scan sạch; reset ngăn kế thừa cờ sang keyframe kế tiếp |
| R03-15 | Đạt guard tái hiện nhãn đổi sau scan hoặc giữa chuẩn bị/ghi: không PATCH và yêu cầu quét lại. Web có đường re-scan trước flag. Còn race sau GET cuối, xem mục 5 |
| R03-16 | Đạt unit các URL shape/track/no ID và browser link track: job 27 frame 0, serverID 487 chọn 1 CUBOID TRACK pedestrian với dims đúng; shape link kiểm API/unit, chưa nghiệm thu thao tác extension phần 05 |
| R03-17 | Đạt UTF-8/JSON version, metadata và snapshot payload API gốc; không token; snapshot đầy đủ ở out/ ngoài Git |
| R03-18 | Đạt dataroot override, manifest thiếu/sai và sweep thiếu/corrupt; caller chuyển thông báo giảm phạm vi và gate coverage phần 01. Không biến thiếu LiDAR thành job đã kiểm đủ |

18 ca có kết quả trong phạm vi nêu trên; không có ca bị bỏ qua do Docker/dataset. Các nội dung chưa nghiệm thu được nêu trực tiếp trong bảng và mục giới hạn.

## 4. Findings đã xử lý

| Mã / mức | Lý do gây rework hoặc mất độ tin cậy | Sửa và kiểm lại |
|---|---|---|
| RV-03-001 / P1 | Client theo next URL khác origin với Authorization của session | Kiểm origin trước request, không tự redirect; test không cho gửi request thứ hai tới foreign URL |
| RV-03-002 / P2 | Next `/api/...` ghép sai URL; phân trang lặp có thể treo; lỗi JSON thiếu ngữ cảnh | urljoin, phát hiện URL lặp/schema sai, CvatError kèm endpoint; HTTP statuses được kiểm |
| RV-03-003 / P1 | Reader bỏ giá trị mutable tại keyframe sau không ghi lại attr; subtype/cờ có thể sai | Sắp theo frame và carry attrs tới lần đổi/reset; test mảng đảo vẫn đúng |
| RV-03-004 / P2 | Roll/pitch NaN lọt vào attrs; lỗi parse points chưa kèm ID/frame | Kiểm hữu hạn cả 9 trường và roll/pitch xuất; bọc lỗi với box ID/frame |
| RV-03-005 / P1 | Manifest trùng frame/file hoặc swap sample_token vẫn scan point cloud sai box | Kiểm frame 0..N−1, uniqueness/count và token đúng vị trí trước scan |
| RV-03-006 / P1 | Hệ ego thiếu transform hoặc transform/pose/time sai vẫn được coi có nguồn dữ liệu | Kiểm quay/giữ z, thiếu transform, metadata khớp dataset với dung sai 1e−6 |
| RV-03-007 / P1 | Auto manifest theo task ID có thể lấy dữ liệu server CVAT khác | Khớp URL+task ID; cập nhật fixture Web theo metadata converter thực tế |
| RV-03-008 / P2 | PCD TYPE/SIZE/COUNT/WIDTH sai vẫn được giải mã float32; export NaN/overflow | Kiểm header/count/finite/float32 trước ghi; ASCII báo không hỗ trợ rõ |
| RV-03-009 / P2 | np.fromfile bỏ byte cuối bị cắt; sweep corrupt bị coi thiếu hợp lệ | Hàm load_points chung kiểm stride 20 byte, finite; keyframe và sweep cùng từ chối corrupt |
| RV-03-010 / P2 | JSON token trùng, sample/sweep lặp hoặc sai scene/time gây ghép sai/treo | Kiểm duplicate/cycle/scene/count/last/time tăng; fixture negative có đáp án |
| RV-03-011 / P1 | Gắn cờ frame đầu rồi không reset có thể báo cờ ở keyframe khác; xóa entry làm cờ trước quay lại | Ghi empty reset rõ, kế thừa trạng thái gốc khi keep; test sparse attrs và live |
| RV-03-012 / P1 | Findings của scan cũ gắn/xóa sau khi người gán đã sửa; PATCH track đầy đủ có thể ghi đè thay đổi mới | So nhãn fresh với scan; GET lại trước PATCH, fail nếu đổi. Thu hẹp lost update, còn race không atomic được ghi rõ |
| RV-03-013 / P2 | ID keyframe mới sau PATCH làm finding cũ unmatched hoặc gỡ sai cờ | Rebind theo track/frame chỉ khi đúng keyframe đã scan và nhãn không đổi; ID lạ vẫn unmatched; live repeat 0 thay đổi |
| RV-03-014 / P2 | Snapshot chuẩn hóa thiếu tags/raw metadata; helper verify dùng ID cũ và bỏ roll/pitch | Lưu payload gốc trong meta; helper so key ổn định, kiểm tilt/state, rel_tol=0; live raw compare |
| RV-03-015 / P2 | Upload fail trước khi trả info để lại task chưa rõ ID/không cleanup | Xóa đúng task mới tạo; cleanup lỗi nêu ID. Test simulated failure; task thử thật được dọn |
| RV-03-016 / P2 | Flag immutable vẫn gửi ở shape và có thể không hiển thị đúng từng frame | Metadata mutable từ labels API; từ chối immutable và báo lý do trước PATCH |

Đợt ca tái hiện đầu: **26 failed, 5 passed** trước sửa. Sau sửa adapter/live tập trung **91 passed**. Suite cuối **367 passed**, gồm 49 hồi quy mới và 1 ca live mới.

## 5. Giới hạn và bàn giao tiếp

- API CVAT update chưa có cơ chế compare-and-swap được xác minh trong adapter; race sau GET cuối vẫn tồn tại. Không sửa cùng job khi tool đang ghi. Nếu cần nhiều client ghi đồng thời, phần 04/06 phải xác minh cơ chế server trước khi tuyên bố bảo đảm atomic.
- Chạy CVAT local 2.78.1; chưa chạy server BTC/CVAT 2.77 chuẩn. Phần 08 đối chiếu phiên bản; không suy từ local sang tất cả server.
- ASCII/compressed không thuộc reader PCD hiện tại. Core là yaw và hệ export quay cố định, không phải full ego calibration/roll/pitch; không chứng nhận chất lượng mọi box tilt.
- Một scene thật và test fixture không đo precision/recall/hiệu năng lặp; phần 07 tiếp tục. Thao tác extension và lọc/điều hướng UI toàn bộ thuộc phần 05.
- Ba task CVAT live trong suite tự xóa; scene real task 27 xóa qua API, không sửa/xóa task người dùng có sẵn. Bằng chứng đầy đủ và snapshot ở out/, bản tóm tắt không nhãn/token ở Git.

Nhánh 03 phụ thuộc 02; base PR là `review/02-core-detectors` nếu chưa merge. Commit chuẩn hóa CRLF→LF tách riêng `8d81c20` để commit code `40ac166` dễ review; commit tài liệu tách tiếp. Đồng đội mở PR theo [bàn giao](03-handoff.md).

## 6. Kiểm lại cả ba nhánh sau push

- Đối chiếu diff 01/02/03, caller CLI/Web, coverage, keyframe/class/time, parser/manifest, writer attrs/IDs/snapshot và giới hạn concurrency.
- Tái hiện thêm RV-01-009: cloud rỗng khi tắt floating vẫn cho gate ĐẠT ở bốn luật LiDAR; 4/4 ca fail trước sửa. Đã sửa trên 01 tại 0727c15 và merge theo chuỗi vào 02/03; không force-push.
- Nhánh 01: **256 passed, 0 skip in 22.96s**; nhánh 02: **321 passed, 0 skip in 23.49s**; nhánh 03 tại merge b841f63: **371 passed, 0 skip in 29.14s**. Mỗi suite có 1 warning Starlette/httpx; Docker/dataset thật bật.
- Không phát hiện thêm lỗi mới trong thay đổi detector 02 hoặc adapter/writer 03 ngoài các findings và giới hạn đã ghi. Đã sửa diễn giải dấu quay của nhánh 01 và cập nhật bàn giao/dependency.
- 367 là kết quả đợt phần 03 ban đầu; 4 ca mới thuộc dependency coverage phần 01. Merge-base xác nhận 01 là tổ tiên 02, 02 là tổ tiên 03; main chưa merge.
- [Báo cáo ngắn ba nhánh](re-review-01-03.md). Race sau GET cuối, server BTC và precision/recall vẫn là giới hạn đã ghi, không được coi là đã nghiệm thu toàn sản phẩm.
