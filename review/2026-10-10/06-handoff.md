# Bàn giao phần 06

- Nhánh `review/06-security-config`, base PR `review/05-frontend-extension` (`43812b9`). Review04→05→06 tiếp nối; mở PR06 vào05 để thấy riêng diff06.
- Commit mã nguồn phần06: `08241be`; commit tài liệu tiếp theo ghi ở log nhánh.
- Đã sửa12 nhóm security/config: Host/Origin, scope service worker, token destination, URL/path, output/log, cache và caps. [Báo cáo](06-report.md) nêu actor/điều kiện và20 ca có giới hạn.
- Kiểm:467 pytest toàn bộ +51 ca tập trung sau thay đổi cuối;35 Node;0 skip;1 cảnh báo Starlette/httpx. Dependency metadata0 conflict, chưa CVE audit; không có pip.
- Đã xóa task thử60; không thay task1/task8 hoặc revoke PAT có sẵn của người dùng. Dữ liệu thử/token không commit.
- Dockerfile.api được tracked để explicit bind container; source/image base và Compose local chuyển08. Không restart/deploy container hiện tại.
- Cần Chrome/Edge kết nối để nghiệm thu MV3; GET/PATCH còn race; LAN/proxy/deployment/performance chưa chứng nhận. Tiếp theo07 và08 theo REVIEW-PLAN.
