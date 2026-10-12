# PointSnap 3D package

Công cụ hỗ trợ review cuboid CVAT: CLI, Web local, báo cáo HTML/CSV và API report dùng PAT người gọi.

- Cài từ repo: `python -m venv .venv`, rồi `.venv/Scripts/python -m pip install -e ".[dev]"` trên Windows; Linux dùng `.venv/bin/python`.
- Chạy `python -m pointsnap --help`, `python -m pointsnap ui --no-browser`.
- [Cài đặt toàn hệ thống](../CAI-DAT.md), [tính năng và giới hạn](../README.md), [Docker](README-Docker.md), [bảo mật local](docs/local-security.md).
- Python khai báo ≥3.10; các tổ hợp thực tế được ghi trong [review08](../../review/2026-10-10/08-report.md).

Gate chỉ xét luật đang bật và dữ liệu đủ bằng chứng. Không phát hiện missing objects, không tự sửa box; diff/restore/fix chưa triển khai. Precision xem tay và nghiệm thu extension MV3 còn cần xác minh theo báo cáo review.
