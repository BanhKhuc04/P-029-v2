# Tài liệu PointSnap 3D

Đọc trước: **[Báo cáo dự án](bao-cao-du-an.md)** — vấn đề, giải pháp, thuật toán có hình minh họa, kết quả, giới hạn.

| Thư mục | Có gì | Đọc khi |
|---|---|---|
| [`thiet-ke/`](thiet-ke/) | [Đề xuất đề tài](thiet-ke/de-xuat-de-tai.md): thiết kế từng luật, ngưỡng, bảng truy vết spec ↔ luật, kế hoạch, rủi ro | Muốn hiểu vì sao làm thế |
| [`huong-dan/`](huong-dan/) | [Huấn luyện Box Critic và học từ người duyệt](huong-dan/huan-luyen-box-critic.md) · [Quy trình phát triển](huong-dan/quy-trinh-phat-trien.md) (đo, thêm luật, checklist PR) | Sắp sửa code / huấn luyện |
| [`ket-qua/`](ket-qua/) | Số liệu từng giai đoạn; eval thô trong [`ket-qua/eval/`](ket-qua/eval/) | Cần số cho báo cáo, so trước / sau |
| [`test/`](test/) | [Chuẩn kiểm thử](test/CHUAN-KIEM-THU.md) (TC-xx) và kết quả test của từng người | Test toàn app |
| [`hinh/`](hinh/) | [`giao-dien/`](hinh/giao-dien/): ảnh chụp web / extension · [`thuat-toan/`](hinh/thuat-toan/): hình minh họa thuật toán (vẽ lại bằng `scripts/ve_hinh_minh_hoa.py`) | |

## Kết quả

| File | Nội dung |
|---|---|
| [eval/sau-merge-12-10/](ket-qua/eval/sau-merge-12-10/) | **Mới nhất**: eval 10 vòng trên `main` sau khi merge PR #40 – #50 ([kiểm tra](ket-qua/eval/sau-merge-12-10/kiem-tra.md), [tinh chỉnh](ket-qua/eval/sau-merge-12-10/tinh-chinh.md)) |
| [ket-qua-giai-doan-3.md](ket-qua/ket-qua-giai-doan-3.md) | Sai hướng, box lệch, mặt đất v2, luật spec (C1, C2) |
| [ket-qua-box-verifier.md](ket-qua/ket-qua-box-verifier.md) | Box Verifier 4 lớp, ảnh camera, Box Critic, ngưỡng lơ lửng 15 cm (C3) |
| [ket-qua-sot-doi-tuong.md](ket-qua/ket-qua-sot-doi-tuong.md) | Sót đối tượng bằng LiDAR, vật quá ít điểm (C7, C8) |
| [ket-qua-track-jump.md](ket-qua/ket-qua-track-jump.md) | `track.jump` ở hai đầu track (PR #41) |
| [kiem-chung-ground.md](ket-qua/kiem-chung-ground.md) | Kiểm chứng ước lượng mặt đất trên box chuẩn (B2) |
| [thu-extension.md](ket-qua/thu-extension.md) | Thử extension trên CVAT local (A15) |
| [danh-gia.md](ket-qua/danh-gia.md) · [ket-qua-danh-gia-tu-dong.md](ket-qua/ket-qua-danh-gia-tu-dong.md) | Bảng chỉ số giai đoạn 1 |

Quản lý dự án (bảng việc, giao việc, bàn giao) ở [`../quan-ly/`](../quan-ly/).
