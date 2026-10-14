# Bàn giao 01 — vỉa hè không che lỗi lệch theo track

Model review: **gpt-6.1-sol**. Mốc đầu: `7ec580a`. Ngày: 13/10/2026.

Luật vỉa hè ở main bỏ qua lỗi floating chỉ vì đáy box nằm giữa hai trung vị độ cao hai bên vành đai. Đây không phải bằng chứng điểm tiếp xúc dưới box. Bản thử chỉ đổi sang ±8 cm quanh một trong hai mặt vẫn làm mất lỗi được chấm đúng, thậm chí có thêm mục mất: không dùng cách này để phủ quyết phép so theo track.

Bản sửa giữ phép đo trung vị, ngưỡng, phép xử lý dốc, `single_box: false` và evidence gate hiện tại. Với track đủ peer, độ lệch vẫn được báo; thông tin bậc vỉa hè được ghi trong details để duyệt. Với box lẻ được bật riêng, chỉ bỏ phép đo tuyệt đối khi đáy gần một mặt đo được trong 8 cm, không chấp nhận khoảng trống giữa hai mặt.

## Kiểm chứng

- Python 3.11.9, Windows, NumPy 2.4.6. 76 PASS, 0 FAIL, 0 SKIP, 0 XFAIL trong ground/floating/slope/review09, gồm dữ liệu nuScenes thật.
- Replay đầy đủ 10 cảnh mini, cấu hình mặc định không đọc `.env`, cùng evidence gate ở cả hai phía: [curb-final.json](evidence/handoff-01/curb-final.json), [script](evidence/handoff-01/curb_probe.py).
- Tuning: main 30 → sửa 53 floating Cảnh báo/Lỗi; reviewed-heldout: main 63 → sửa 82. Đây là số finding, không phải số báo nhầm đã xác nhận.
- CSV gốc có 68 mục floating chấm “Đúng lỗi”. 62 mục còn actionable nếu bỏ riêng veto vỉa hè; main giữ 47/62, bản sửa giữ **62/62**, không mất thêm mục đúng nào do vỉa hè. Sáu mục đã bị bỏ bởi các điều kiện khác nằm trong `all_verdict_true_not_actionable_after`; không tự khôi phục vì bàn giao đã chốt tradeoff box lẻ / ít bằng chứng.
- Mốc bàn giao ghi 16 mục mất và floating 67 → 48. Replay `7ec580a` + config mặc định + CSV trong Git cho **15 mục đúng mất**, 82 → 63. Ghi kết quả tái hiện thực tế; không sửa CSV hoặc ép số cho khớp tài liệu.
- [Thử nghiệm surface-only](evidence/handoff-01/curb-comparison.json) đếm trước evidence gate: mất 18 mục đúng so baseline không veto, trong khi veto main mất 15. Không coi trial này là chất lượng của bản sửa cuối.

Lệnh: từ tool root, đặt `PYTHONPATH` tới tool root và `NUSCENES_ROOT=D:/Vin_uni/data/nuscenes`, chạy `python -m pytest -q tests/test_floating_detector.py tests/test_floating_curb.py tests/test_ground.py tests/test_ground_slope.py tests/test_geometry_review09.py`. Từ repo root chạy `python review/2026-10-13/evidence/handoff-01/curb_probe.py --dataroot D:/Vin_uni/data/nuscenes --out <file-moi.json>`.

Không tạo verdict tay mới. Tập đã dùng chỉnh luật được gọi là reviewed-heldout; không tuyên bố kiểm định độc lập hoặc nghiệm thu G7. PR vào main, người dùng merge.
