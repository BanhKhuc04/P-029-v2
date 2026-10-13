# Bàn giao 05 — review PR #48

Model review: **gpt-6.1-sol**. Main đối chiếu `7ec580a`; PR head `0dfcfa8`.

[PR #48](https://github.com/AI20K-Build-Phase-Cohort-4A/P-029/pull/48) tách số điểm của vật khỏi số điểm ngoài box (30/15), hạ excess ratio 0,5 → 0,4. GitHub xác nhận mergeable; checks cũ đạt trên head ngày 12/10, không phải gate của main hiện tại.

Số liệu PR là thí nghiệm cũ: co box x0,85 bắt 18% → 36%, finding trên GT 2 → 13 trên tập kiểm tra. Sau đó main thêm hai điều kiện chống vật thò rất ít (<20 cm), nên không dùng số liệu này làm kết quả của phiên bản hiện tại. Đây cũng là số finding trên GT, chưa có verdict tay để gọi là FP.

Kết luận theo quyết định G7 mới: **giữ pending, chưa đề xuất merge tăng độ nhạy mặc định**. Tắt fit.loose không chứng minh chất lượng fit.outside. Cần một mẫu ít nhất 20 finding fit.outside (hoặc toàn bộ nếu ít hơn), chấm Đúng/FP/Không rõ; đo lại baseline và candidate cùng snapshot/config trên tuning và tập đánh giá đã khóa, báo recall lỗi chèn và proxy riêng. Không tự đóng PR, đổi ngưỡng hoặc tạo verdict.

Đã đọc config/parser/validation, outside_measure/outside_findings, eval phạm vi và script của PR. Script cũ thử nhiều ngưỡng trực tiếp trên `test`; không dùng kết quả đó để tiếp tục chọn ngưỡng trên tập test. Các thay đổi kỹ thuật có thể gộp lại sau khi quyết định sensitivity có bằng chứng tay.
