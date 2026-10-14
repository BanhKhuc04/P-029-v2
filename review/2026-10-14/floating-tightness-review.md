# Phản hồi 24 mẫu: phát hiện đúng, box chưa ôm sát

Reviewer kỹ thuật: **Codex, agent dựa trên GPT-6**; phiên không cung cấp ID model triển khai chi tiết. Người chấm chất lượng: **người dùng trong hội thoại này**. Model không tự tạo 24 verdict.

## Kết luận đã ghi nhận

Người dùng nhận xét “đúng lỗi nhưng và box xung quanh trên dưới trái phải chưa sát với box của xe”, sau đó xác nhận phạm vi “tất cả các 24 bộ đó”. Đã ghi **24 Đúng lỗi, 0 Báo nhầm, 0 Không rõ, 0 chưa chấm** vào CSV riêng. Precision mô tả cho 24 finding floating là **100%**. Đây là 24 track khác nhau ở 7 cảnh nuScenes mini đã dùng chỉnh luật/review; không chứng minh precision toàn dự án, recall hoặc nghiệm thu G7 trên tập độc lập.

Ghi chú độ ôm sát được giữ cùng từng dòng CSV. Không chuyển ghi chú này thành 24 verdict của `fit.loose` hoặc `fit.outside`: bộ chấm ban đầu chỉ hỏi về finding floating. Cột chấm gợi ý sửa vẫn để trống vì chưa có gợi ý nào được người dùng kết luận tốt hơn. `fit.loose` tiếp tục tắt mặc định theo quyết định trước đó.

CSV: `source-tool/pointsnap-3d/out/floating-review/verdicts-user-20261014-all24.csv`. Bản tóm tắt và nguyên văn phản hồi nằm cùng thư mục; [evidence rút gọn](evidence/floating-human-review.json) ghi hash CSV và bộ bằng chứng. Template chưa chấm và packet gốc được giữ nguyên; trang bộ gốc không tự thay câu trả lời đã lưu trong trình duyệt.

## Phát hiện kỹ thuật liên quan đến khung chưa sát

`NuScenesReader._to_cuboid` chuyển nhãn vào hệ LiDAR rồi chỉ giữ yaw. Độ nghiêng được lưu ở `attrs.tilt_rad`, nhưng `core.geometry.corners`, `core.camera.project_box` và mặt cắt preview dựng box với roll/pitch bằng 0. Bộ 24 mẫu đã dùng phép dựng này. Do vậy khung trong ảnh không phải toàn bộ hình học của quaternion nhãn nuScenes gốc.

Script `scripts/diagnose_review_geometry.py` đọc đúng annotation gốc của mỗi box, dựng 8 góc bằng quaternion và pose sensor đầy đủ, đối chiếu với khung đã dùng trong bộ chấm. **Không đổi tâm, kích thước, nhãn hoặc dữ liệu CVAT.** Đã đối chiếu lại 24 bộ điểm hiển thị với packet; tất cả khớp.

| Quan sát trên 24 mẫu | Kết quả |
|---|---:|
| Độ nghiêng trục box so với LiDAR | 2,19–5,32° |
| Khoảng khác biệt lớn nhất giữa các góc, theo từng box | 6,0–41,4 cm |
| Trung vị khoảng khác biệt lớn nhất | 16,6 cm |
| Góc thấp nhất của box gốc thấp hơn đáy gần đúng | 4,2–38,3 cm |
| Box được đổi tâm/kích thước | 0 |
| Ghi nhãn CVAT | 0 |

Đây là so sánh biểu diễn hình học, **không phải phép chạy lại detector với thuật toán mới**. Góc thấp nhất của cuboid nghiêng cũng không tự xác định vị trí bánh tiếp xúc đất. Không dùng các khoảng trên để sửa Z hoặc kết luận 24 verdict floating sai. Quan sát này chứng minh có một yếu tố hiển thị/hình học cần xét trước khi tự co box, chưa chứng minh mọi phần dư do nó gây ra.

Bản đối chiếu: `http://127.0.0.1:8776/fit-diagnostic/`. **Xanh dương** là box chỉ giữ yaw; **xanh lá** là hình học nhãn nguồn có đủ độ nghiêng. Cùng camera, cùng tâm/kích thước và cùng bộ điểm tại frame đã chấm. Đủ 24 ảnh camera và 24 ảnh LiDAR Top/Side/Front. Đã kiểm trực quan camera mẫu 02 và LiDAR mẫu 11. Khung xanh lá là nhãn nguồn, chưa được gọi là box đã sửa hoặc box đúng.

Hình chiếu cuboid 3D có thể dư so với đường viền xe 2D; điểm LiDAR cũng không phủ kín mặt khuất. Camera/LiDAR có thể chụp khác thời điểm. Số điểm trong/ngoài trong JSON chỉ là quan sát trên cùng cụm điểm được chọn bằng box gần đúng; không coi là precision fit hoặc đủ căn cứ để tự resize.

## Hướng cải tiến tiếp theo

1. Đối chiếu độ ôm sát bằng hình học có đủ hướng quay; xác định phần dư còn lại là vị trí, kích thước, hướng hay giới hạn quan sát. Cơ chế production hiện vẫn dùng box yaw; script đối chiếu chưa thay đổi core.
2. Chọn một ca rõ và tạo **task CVAT sao chép để thử**. Người dùng chỉnh hoặc xác nhận các mặt cần sửa, xem trước thay đổi rồi mới Apply; lưu before/after để Undo. Không ghi job 4 và không áp dụng cùng một phép co cho cả 24 mẫu.
3. Quét lại và chấm **box đúng hơn** riêng với **finding biến mất**. Việc detector hết báo chưa đủ nghiệm thu sửa đúng. Chỉ cân nhắc tự động sau khi có mẫu sửa được chấm tay và kiểm trên nguồn độc lập.

Prototype dịch Z hiện giữ nguyên kích thước và đều từ chối 24 mẫu vì độ nghiêng. Giữ điều kiện này trong bước thử; không nới ngưỡng để có demo. Nhận xét của người dùng cho thấy chỉ kéo box xuống chưa xử lý đủ bài toán độ ôm sát.

## Kiểm chứng và tái tạo

```powershell
python scripts/diagnose_review_geometry.py --dataset D:/Vin_uni/data/nuscenes --packet out/floating-review/packet.json --out out/floating-review/fit-diagnostic-new
python -m pytest -q tests/test_review_source_geometry.py tests/test_repair_preview.py tests/test_floating_review_sampling.py
python auto-tests/manual_precision.py --verdicts out/floating-review/verdicts-user-20261014-all24.csv --out out/floating-review/manual-summary-recheck.json
```

**34 Python PASS**, gồm 6 kiểm hình học nguồn mới. 8 Node viewer PASS từ lượt trước, HTML bộ chấm không đổi trong cập nhật này. CI 5/5 đã xác minh trên head `23286c2` trước cập nhật script/evidence; cần đọc CI của head mới sau push. Không có browser E2E mới hoặc Apply/Undo test. Script từ chối thư mục đầu ra đã tồn tại và dữ liệu điểm/kích thước khác packet, tránh gán nhận xét cũ cho bằng chứng thay đổi.
