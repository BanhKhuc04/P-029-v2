# Bàn giao phần 05

- Nhánh `review/05-frontend-extension`, base PR `review/04-backend-cli-reports`.
- Đã sửa 14 nhóm lỗi Web/extension; xem [báo cáo](05-report.md) và [ảnh](evidence/05/06-narrow-600.png).
- Xác minh: 436 pytest +21 Node đạt, không skip; 1 cảnh báo Starlette/httpx; syntax/diff đạt. Fixture job60 không phải dữ liệu production.
- Các ca cần extension MV3 cài thật còn thiếu Chrome/Edge được kết nối. Không tính VM/TestClient là bằng chứng inject/hover/filter thật; bảng R05 ghi từng giới hạn.
- Phần06 tiếp nối nhánh05, giữ patch05. Mở PR05 vào04 để diff chỉ chứa phần05; không squash/drop các patch trước khi các nhánh sau được rebase.
