# Bàn giao 04 — G7 theo precision tay, proxy báo riêng

Model review: **gpt-6.1-sol**. Người dùng chốt phương án ngày 13/10/2026. Base `7ec580a`.

Cập nhật tiêu chí G7 trong đề xuất: precision chấm tay theo từng luật, mục tiêu ≥70% đã có trong yêu cầu gốc, ghi cả Không rõ và độ phủ. Giữ số finding trên 100 box để so phiên bản; không đồng nhất finding trên nhãn nuScenes với báo nhầm. Bộ scene từng được dùng chỉnh luật không còn là held-out độc lập. Thiếu mẫu cho luật đang cần nghiệm thu thì chưa đạt G7.

`auto-tests/check_quality.py` mặc định xuất `REPORT_ONLY`, `g7_status=UNASSESSED` và `proxy_reference_met`; không trả FAIL chỉ vì finding proxy vượt mức tham khảo. `--enforce-proxy` giữ phép kiểm ngân sách proxy khi muốn chạy riêng. Thành công của script là thành công đo số liệu, không phải chứng nhận G7. Gate chấp nhận một job của sản phẩm vẫn theo guideline dự án.

Thêm `manual_precision.py`: đọc verdict đã có, bỏ Không rõ khỏi mẫu số, deduplicate cùng finding, báo số track có kết luận, từ chối verdict lạ/xung đột; mẫu không có kết luận trả N/A. Script không tạo verdict và không tự chứng nhận G7.

[CSV gốc trong Git](evidence/g7/verdicts-heldout.csv) cho floating **68 Đúng / 2 FP / 25 Không rõ / 4 chưa chấm**, precision 97,14% của 70 finding có kết luận, chỉ 30 track; size 1 Đúng / 0 FP / 22 Không rõ / 2 chưa chấm, mẫu quá nhỏ. [Summary](evidence/handoff-04/manual-summary.json). `g7-cham-tay.md` ghi đợt sau 64/65; hai artifact khác phiên bản verdict, không tự ghi đè bằng suy đoán. Cần xuất verdict cuối từ Web để khóa số liệu cuối.

8 PASS, 0 FAIL/SKIP/XFAIL trong test thống kê tay và runner. Chưa có mẫu tay đầy đủ cho heading/fit/track/camera/Critic; trạng thái nghiệm thu G7 vẫn **chưa đủ bằng chứng**.

Lệnh từ tool root: `python -m pytest -q auto-tests/test_manual_precision.py auto-tests/test_all_runner.py`. Thống kê từ repo root: `python source-tool/pointsnap-3d/auto-tests/manual_precision.py --verdicts review/2026-10-13/evidence/g7/verdicts-heldout.csv --out <file-moi.json>`.
