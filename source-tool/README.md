# source-tool

Công cụ đội tự viết để gỡ pain point khi gán nhãn. Mỗi tool một thư mục con, có README riêng.

| Tool | Giải quyết | Người viết | Trạng thái |
|---|---|---|---|
| [**PointSnap 3D**](pointsnap-3d/) | Phát hiện sớm lỗi nhãn 3D cuboid trên CVAT (lơ lửng / lún, sai kích thước, đứt track, sai hướng, box lệch, sót đối tượng, sai spec) — [P-010](../problem-backlog.md#p-010), [P-011](../problem-backlog.md#p-011) | Khúc Việt Anh, Đặng Văn Huy | Đang hoàn thiện giai đoạn 3; xem kết quả review |

Bắt đầu từ [README của PointSnap 3D](pointsnap-3d/README.md); cài từ máy trắng: [CAI-DAT.md](pointsnap-3d/CAI-DAT.md).

> Đối chiếu review 12/10/2026: mã CLI, Web và extension đã có; kết quả G2 lịch sử không thay thế nghiệm thu toàn sản phẩm. `diff` chưa triển khai. Test mock không chứng minh thao tác trên CVAT hoặc trình duyệt thật. Xem [review phần 01](../review/2026-10-10/01-report.md).

Review 01–08: [bàn giao tổng](../review/2026-10-10/08-handoff.md). Extension MV3 thật và precision xem tay còn thiếu bằng chứng; quality proxy lịch sử còn vượt mục tiêu. `diff` và khôi phục nhãn tự động chưa triển khai.
