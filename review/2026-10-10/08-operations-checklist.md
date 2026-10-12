# Checklist vận hành và bàn giao 08

Đối chiếu 12/10/2026. Quy trình chạy thực tế: [operations](../../source-tool/pointsnap-3d/docs/operations.md).

| Việc | Kết quả đợt này | Evidence / giới hạn |
|---|---|---|
| Cài artifact ngoài source, CLI/Web/static/config/fonts | Đạt trên Windows 3.12 | package-tests.json, artifact-smoke.json |
| Dataset/export/backend/Web cùng server | Đạt bằng fixture + mini thật ở 07 | API before/after; alias không ghép server khác |
| Report API auth/JSON/HTML/CSV và link Web | Đạt trên container riêng, task 79 | api-after/router/restart.json; nhãn không đổi |
| Non-root/RO/tmpfs/network/Host router | Đạt trong stack thử | docker.json; không thay router/container công việc |
| Web restart/history/queued/bridge | Đạt fixture | operations.json: done giữ, queued thành failed, bridge offline |
| Backup/restore config/token giả/run/review | Đạt fixture byte-level | 11 files; token thật không đưa vào fixture/Git |
| Backup/restore database/nhãn CVAT thật | Chưa kiểm | Cần stack thử riêng và quy trình CVAT |
| Rollback | Một phần | runner 04 đọc run done với deps hiện hành; chưa rollback toàn deployment |
| Windows launcher từ cwd khác/port bị dùng | Đạt | launcher.json; script chạy trong PowerShell hiện hành |
| CVAT restart giữa tác vụ đang chạy | Chưa kiểm | Không restart stack công việc để giả lập sự cố |
| MV3 thật Chrome/Edge | Bị chặn môi trường | Bề mặt đã kết nối chỉ IAB/MCPApps, không có Chrome/Edge |
| Manual precision và quality gate detector | Chưa đạt nghiệm thu | 07 proxy còn vượt mục tiêu, 0 mẫu manual |
| Dọn fixture/task/container/process riêng | Theo bằng chứng cleanup.json | Không xóa task công việc 1/8 |

Trước dùng với dữ liệu thật: xác nhận đúng CVAT/PAT, backup home/export/config,
đóng job khi ghi cờ, kiểm coverage và dùng reviewer. Khi update, giữ commit/tag/
config/home backup, build CLI trước API cùng version. Health chỉ kiểm process API.
