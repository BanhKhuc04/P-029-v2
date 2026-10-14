# Kiểm chất lượng và xem thử hỗ trợ sửa — 14/10/2026

Reviewer: **Codex, agent dựa trên GPT-6**. Phiên không cung cấp ID model triển khai chi tiết.

## Đã làm và việc đang chờ

| Bước | Trạng thái | Bằng chứng/phạm vi |
|---|---|---|
| Chốt mã và API | **Đã hoàn tất đợt 11 PR** | #48, #61–70 đã merge; main local pull `44a06236eedf412a884f27a67561af62c9f541fa`. Head cuối #69 `07a8b58` đạt 5 job CI trước merge. API Docker build/recreate thành `pointsnap-api:44a0623`, healthy; bốn file package và mặc định fit khớp main. Thư mục landing chưa theo dõi được giữ nguyên. |
| Kiểm Web/extension bản cài | **Chưa xác minh lại** | Computer Use chặn thao tác mở trang extension vì không xác định chắc URL. Không đổi quyền trình duyệt hoặc tìm cách vượt chặn. Nút bấm/phiên bản MV3 hiện cài chưa được nghiệm thu trong lượt này. |
| Chuẩn bị chấm detector | **Bộ 24 mẫu đã tạo** | Quét riêng floating trên 10 cảnh nuScenes mini: 135 finding Cảnh báo/Lỗi; chọn 24 track khác nhau từ 7 cảnh, lần lượt theo cảnh và frame đầu của track. Mỗi mẫu có camera chiếu box, LiDAR ba mặt và keyframe lân cận. Không ưu tiên mẫu có thể sửa. |
| Kết luận chất lượng | **Đã nhận kết luận cho 24/24 mẫu** | Người dùng xác nhận cả 24 mẫu Đúng lỗi, đồng thời nhận xét box chưa sát xe ở trên/dưới/trái/phải. Precision mô tả floating của bộ này 24/24 = 100%; G7 vẫn UNASSESSED vì mini đã dùng chỉnh luật/review. Không suy ra verdict cho luật fit hoặc chất lượng sửa. |
| Đối chiếu độ ôm sát | **Có bản so sánh chỉ đọc** | Cả 24 mẫu được dựng lại từ quaternion gốc nuScenes và đối chiếu với box chỉ giữ yaw trong bộ chấm. Góc khung khác 6,0–41,4 cm, trung vị 16,6 cm; tâm/kích thước giữ nguyên. Chưa sửa detector hoặc kết luận nhãn gốc ôm sát. |
| Xem trước hỗ trợ sửa | **Có prototype chỉ đọc** | `floating_z_preview` tính `delta_z = -(distance - track_median_distance)`, giữ độ lệch mặt đất tham chiếu của track, không mặc định kéo đáy box về 0. Không đổi kích thước/yaw/nhãn; không có endpoint Apply/PATCH hoặc tự sửa. |
| Áp dụng và hoàn tác CVAT | **Chưa bật** | Cần chấm chất lượng và xác minh gợi ý trên task thử trước. 24 mẫu thật hiện đều không qua điều kiện độ nghiêng trong hệ dữ liệu của prototype đầu; giữ sửa tay, không nới ngưỡng để tạo demo. Metadata tilt của nuScenes là độ nghiêng tương đối với trục LiDAR, chưa chứng minh bản thân nhãn sai vì nghiêng. |

[Bằng chứng API sau đồng bộ](evidence/runtime-main44.json). Mẫu hash bốn file chưa phải attestation toàn image. API Docker không phải bản Web đang chạy hay chứng nhận extension đã reload.

[Bằng chứng bộ mẫu đã tạo](evidence/floating-review-summary.json) có commit detector/viewer, hash package/config/bộ bằng chứng, 24 định danh độc lập, đủ ảnh và CSV chưa chấm. Trang và ảnh mẫu được phục vụ qua HTTP local với status 200. Mã xem trước và script ở [PR #72 draft](https://github.com/AI20K-Build-Phase-Cohort-4A/P-029/pull/72); chưa hợp nhất thành tính năng Apply của sản phẩm.

Cập nhật sau phản hồi: đã ghi kết luận vào CSV riêng `out/floating-review/verdicts-user-20261014-all24.csv`, giữ template và packet gốc. [Bằng chứng chấm tay](evidence/floating-human-review.json) lưu phạm vi người dùng xác nhận, hash CSV và giới hạn. [Review độ ôm sát](floating-tightness-review.md) giải thích ảnh hưởng của phép dựng khung chỉ giữ yaw. Bản đối chiếu local ở `out/floating-review/fit-diagnostic/index.html`, có đủ 24 ảnh camera và 24 ảnh LiDAR; không làm mất hoặc chuyển verdict sang một bộ bằng chứng khác.

## Người dùng làm gì tiếp

Phần chấm phát hiện 24 mẫu đã nhận qua hội thoại và ghi thành CSV riêng. Bước tiếp theo là xem bản đối chiếu `http://127.0.0.1:8776/fit-diagnostic/`, xác định phần dư còn lại khi khung có đủ độ nghiêng, rồi chọn một ca chỉnh tay có người duyệt trên task sao chép. Không yêu cầu chấm lại 24 finding chỉ để hoàn thành bước ghi nhận.

Quy trình dưới đây dùng khi muốn chấm thêm hoặc đổi kết luận trong bộ gốc. Trang bộ gốc không tự đọc kết luận qua hội thoại hoặc thay đổi localStorage; vì vậy số câu trả lời của trang có thể khác CSV riêng vừa ghi:

1. Đối chiếu ảnh, mặt cắt và frame lân cận. Chọn **Đúng lỗi / Báo nhầm / Không rõ**, ghi lý do khi cần.
2. Chỉ sau khi chọn Đúng lỗi, trang mới cho xem phần gợi ý. Nếu bị chặn, mục ghi rõ giữ sửa tay; không có thao tác ghi CVAT.
3. Bấm **Tải CSV kết quả**, giữ file rồi cung cấp đường dẫn file đã tải để tổng hợp. Công cụ không đọc câu trả lời từ trạng thái ẩn của trình duyệt.

Câu trả lời được lưu localStorage theo hash của đúng bộ bằng chứng (case/config/ảnh); bộ mẫu đổi không tự mang theo verdict cũ. Nếu trình duyệt cho phép, câu trả lời được giữ local; khi lưu thất bại, trang báo rõ và vẫn cho tải CSV. CSV là bản lưu có thể mang sang máy/phiên khác. Precision của bộ mẫu chỉ là mô tả; Không rõ báo riêng và không nằm trong mẫu số. Chất lượng phát hiện và chất lượng gợi ý có hai cột kết luận riêng.

## Script và kiểm thử

Từ tool root, Python có package/dev, Pillow và Matplotlib để tạo ảnh review:

```powershell
python scripts/prepare_floating_review.py --dataset D:/Vin_uni/data/nuscenes --out out/floating-review --count 24
python -m pytest -q tests/test_repair_preview.py tests/test_floating_review_sampling.py
node --test scripts/tests/floating_review.test.js
python auto-tests/manual_precision.py --verdicts out/floating-review/verdicts-template.csv --out out/floating-review/manual-summary.json
```

Script từ chối ghi đè thư mục đã có để giữ câu trả lời của người chấm. Ảnh, point cloud lấy mẫu và CSV thô nằm trong `out/` bị Git ignore. Chỉ commit script, tests và evidence đã rút gọn; không commit token, nhãn thô hoặc ảnh nuScenes.

Kiểm kỹ thuật mới: **34 Python PASS** (24 ca proposal, 4 ca chọn mẫu/định danh/CSV, 6 ca hình học nguồn), **8 Node PASS** cho viewer từ lượt trước; viewer không đổi trong cập nhật chấm tay. Sáu ca mới kiểm khung upright, đáy nghiêng theo công thức độc lập, khôi phục đúng góc trong hệ world và từ chối sai identity/tâm/kích thước. Các test viewer dùng fixture synthetic, không ghi verdict vào bộ mẫu thật. Ca proposal kiểm hướng nâng/hạ, giữ khoảng đáy–mặt đất tham chiếu khác 0, bảo toàn hình học khác, chặn thiếu/sai evidence, slope/curb, ID/frame lệch, điểm thưa và dịch quá lớn. Node kiểm chưa chấm mặc định, Không rõ, tách precision, xem trước sau kết luận, CSV và lỗi lưu local. JavaScript syntax check đạt; đã xem ảnh camera/context được render, kiểm ảnh camera so sánh mẫu 02 và LiDAR mẫu 11. Chưa có kiểm browser E2E mới cho viewer.

Lượt kiểm đầu proposal có ba assertion so float chính xác thất bại ở sai số biểu diễn khoảng `1e-16`; đã dùng dung sai `1e-9` cho tâm Z, các trường không đổi vẫn so chính xác. Hai lượt chuẩn bị đầu gọi sai API `reader.scenes` được sửa theo `SceneInfo.name`; không tính lượt dở là bộ mẫu hoàn thành. Bộ cuối đã kiểm đủ 24 định danh độc lập, asset tồn tại, CSV blank và JSON hữu hạn.

Không cộng bộ test mới vào kết quả toàn suite cũ để tuyên bố main có coverage mới. Prototype độc lập chưa được nối vào đường quét/ghi nhãn của Web/API/extension. Bước tiếp theo sau phản hồi là xem lại điều kiện hình học và triển khai Apply/Undo có người duyệt trên bản sao task; chưa có chứng cứ cho tự sửa production.
