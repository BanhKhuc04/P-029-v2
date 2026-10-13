# Bàn giao 07 — review13 cùng bộ lọc độ cao của main

Model review: **gpt-6.1-sol**. Base `7ec580a`; nhận code `ae1d579` thành `ef16468`, docs `4dbd91d` thành `811d6ad`.

Giải xung đột import bằng cách giữ cả `validate_pose` và `fit_plane_ransac`; giữ toàn bộ `max_elevation_m` / plane filter của main. Review13 kiểm chuyển động trong hệ thế giới có pose, sự kết nối cụm không phụ thuộc thứ tự điểm, mask góc box xoay, timestamp/đơn vị displacement, trả chỉ chain đủ bằng chứng, camera cùng semantic group và các frame độc lập. Backport riêng `group_of_name` chuẩn hóa/word boundary từ review12 để PR này chạy độc lập trên main; phần cache/runtime camera đầy đủ nằm ở PR #65.

Sửa thêm trường hợp camera xác nhận nhầm cụm xa bằng vật đã gán gần hơn: khi box gần che phần lớn khung cụm và hai khoảng độ sâu 3D tách rõ, không dùng view đó để xác nhận cụm. Dùng ngưỡng containment sẵn có; không tuning ngưỡng mới. Đây là kiểm tra bảo thủ, có thể bỏ thêm đối tượng bị che; chưa có precision tay của nhánh static-camera.

33 Python PASS, 0 FAIL/SKIP/XFAIL, gồm regression mái nhà (vật trên đường vẫn được nhận, cụm trên mái bị loại) và foreground/farther-label. Test mái nhà dùng pose identity tường minh theo hợp đồng mới; test thiếu pose vẫn riêng và không suy chuyển động.

Replay raw-GT deletion, tối đa 12 instance đủ điểm/chuyển động mỗi cảnh, cùng target và matcher ở baseline main / bản sửa:

| Split | Target | Main tìm lại | Sửa tìm lại | Finding nhãn sạch |
|---|---:|---:|---:|---:|
| Tuning | 47 | 32 | 32 | 0 / 0 |
| Reviewed-heldout | 51 | 33 | 33 | 0 / 0 |

Không target nào đổi trạng thái recovery. [Chi tiết](evidence/handoff-07/deletion-comparison.json), script [missing_probe.py](evidence/13/missing_probe.py). Các target chọn theo instance token/raw GT, matcher cần ≥2 tâm báo nằm trong footprint GT nới 0,75m. Khác số bàn giao 31/46 và 36/51: không có script/target list cho mốc ấy, không gọi hai protocol là cùng phép đo. Đây là recall subset lỗi xóa nhãn, không phải recall mọi vật; finding trên GT là proxy, không có verdict mới. Camera tắt trong probe LiDAR; ca occlusion được kiểm riêng trong 33 test sau đó.

Lệnh từ tool root: `python -m pytest -q tests/test_missing.py tests/test_missing_review13.py`. Từ repo root: `python review/2026-10-13/evidence/13/missing_probe.py --dataroot D:/Vin_uni/data/nuscenes --targets-per-scene 12 --baseline <main-missing.py> --out <file-moi.json>`.
