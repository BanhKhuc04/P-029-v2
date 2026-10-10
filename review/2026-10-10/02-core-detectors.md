# 02 — Review core, hình học và detector

**Nhánh:** `review/2026-10-10/02-core-detectors`.
**Trạng thái:** chưa thực hiện review phần 02.
**Đầu ra sẽ tạo:** `02-report.md`, ma trận luật/dữ liệu, ca biên có đáp án và findings thuật toán.

Áp dụng [quy trình chung](README.md), [mẫu báo cáo](report-template.md). Đường dẫn code tính từ tool root. Đọc invariant và quyết định coverage từ phần 01; ghi SHA tài liệu đã tham khảo.

## 1. Mục tiêu

Kiểm tra luật đo đúng đại lượng theo CONVENTIONS, xử lý đúng điều kiện được phép kiểm, và trả finding có vị trí/mức/ngưỡng nhất quán. Phân biệt lỗi tính toán, sai thiết kế ngưỡng, hạn chế dữ liệu và báo nhầm trên nhãn chuẩn.

## 2. Phạm vi đọc

| Module | Trách nhiệm | Test cần đối chiếu |
|---|---|---|
| `pointsnap/core/model.py`, `geometry.py`, `serialize.py` | Cuboid/FrameData/Finding, normalize yaw, biến đổi, serialization | model, geometry, cvat_shapes_and_serialize |
| `pointsnap/core/ground.py`, `box_points.py` | Ước lượng ground, tập điểm của vật, điều kiện đủ bằng chứng | ground, heading_fit |
| `pointsnap/core/config.py`, `pointsnap/config.yaml`, guideline spec-vn | Schema/ngưỡng, mặc định, override và rule switches | config, spec_rules |
| `pointsnap/core/scanner.py`, `gate.py` | Wiring, điều kiện chạy luật, lọc/sắp finding, tiêu chí gate | scan_wiring, scan_gate, detectors_a10 |
| `pointsnap/detectors/floating.py` | Sai đáy box, so track, sweep LiDAR và thiếu bằng chứng | floating_detector, ground |
| `pointsnap/detectors/size.py` | Theo class, thống kê/manual range, class/thuộc tính, so track | size_detector, spec_rules |
| `pointsnap/detectors/track.py` | jump, split_id, long_interpolation, reuse_id, occluded_long | track_detector, spec_rules |
| `pointsnap/detectors/heading.py`, `fit.py`, `attributes.py` | Hướng box, box lệch/rỗng/dư/chồng, thuộc tính theo spec | heading_fit, spec_rules |

## 3. Invariants phải giữ

- Mét, giây, radian; dims=(length,width,height), length theo x local; yaw chuẩn hóa [-π,π).
- Tâm box là tâm hình học; bottom_z=center_z-height/2. Không đổi width/length hoặc thêm yaw offset ở core để bù lỗi adapter.
- Số hữu hạn, dims dương; xác định rõ cách xử lý vector sai độ dài, NaN/Inf và point cloud sai shape.
- Phân biệt keyframe/nội suy/outside/occluded. Các luật hình học phải đối chiếu quy tắc bỏ box occluded trong CONVENTIONS.
- Finding giữ rule/severity/frame/label/source_id/track_id/value/threshold và đơn vị chính xác.
- Cấu hình tắt luật phải loại luật đó khỏi findings. Không dùng số lượng finding bằng 0 để suy ra mọi luật đã chạy.

## 4. Trình tự review

1. Lấy config đang review, lập ma trận mỗi luật: đầu vào, class hợp lệ, số điểm/frame tối thiểu, phép đo, ngưỡng, mức và điều kiện bỏ qua.
2. Đọc model/geometry trước detector; tính tay vài fixture để có đáp án độc lập với implementation.
3. Theo đường wiring từ scanner đến từng detector; xác minh bật/tắt và xử lý thiếu Frames/pose/timestamp.
4. Chạy test tập trung; bổ sung ca hồi quy chỉ khi thấy gap hoặc finding cụ thể. Mỗi ca cần có đáp án/tính chất độc lập.
5. Kiểm detector trên ca biên; đo thời gian phần đắt nếu có nghi ngờ cụ thể rồi bàn giao đo đầy đủ cho 07.
6. Ghi riêng kiến nghị đổi ngưỡng. Chỉnh ngưỡng trên tuning; giữ tập test để xác nhận theo quy trình 07.

## 5. Ma trận ca cần thực hiện

| Mã | Ca | Mong đợi / bằng chứng |
|---|---|---|
| R02-01 | Yaw gần -π/π, quay vòng, box quay 90° | Chuẩn hóa/interpolation đi đúng hướng; đáp án tính tay, sai số và dung sai |
| R02-02 | Điểm trên mặt/cạnh/góc, box xoay, point cloud rỗng | Quy tắc inclusion và empty input được xác định; không sinh NaN/crash ngoài hợp đồng |
| R02-03 | Đáy nâng/hạ quanh ngưỡng warn/error | Đúng dấu, đơn vị, điều kiện so track/absolute và boundary thực tế của config |
| R02-04 | Ground dốc, ground ít điểm, box xa, box lẻ | Thiếu bằng chứng không bị coi là ground=0; ghi điều kiện và mức info/skip |
| R02-05 | Ground sweeps=0 và >0, vật di chuyển | Pose/time của sweep và loại vệt vật đúng; không trộn sai hệ tọa độ |
| R02-06 | Size range min/max, ít instance, class chưa biết | Đúng đường stats/manual và fallback; rõ điều kiện không đủ thống kê |
| R02-07 | Size trong track, thiếu keyframe, pedestrian, class/thuộc tính | Đúng baseline, nhóm bị loại, số frame tối thiểu; không trộn loại vật |
| R02-08 | Track di chuyển và xe thu chuyển động | Jump dùng đúng pose/time; thiếu pose có kết luận/giới hạn phù hợp |
| R02-09 | Split ID, cuối job, gap dài/ngắn | Không báo split giả do ranh giới job; đúng ngoại suy và class tương thích |
| R02-10 | Gap 6/7 frame, reuse sau outside, occluded dài | Đúng giới hạn spec và marker; giữ id/đánh dấu/tách track theo hợp đồng |
| R02-11 | Heading flip, motion, đứng yên, ít điểm | Loại được ca ngoài phạm vi; sai hướng khác thiếu bằng chứng hướng |
| R02-12 | Fit empty/outside/loose/overlap | So với hình học/tập điểm độc lập; xử lý ground, vật cạnh nhau, occlusion, cặp class được phép |
| R02-13 | Thuộc tính thiếu/rỗng/sai giá trị/sai class | Theo required_attributes/allowed_values của guideline; rule đúng vị trí |
| R02-14 | Tắt riêng từng rule; config cũ thiếu khóa | Hành vi phù hợp backward compatibility; không bỏ nhầm rule khác |
| R02-15 | JobData và danh sách Cuboid, thay thứ tự input | Kết quả tương đương khi hợp đồng cho phép; sort_key ổn định, không mutation input ngoài dự kiến |
| R02-16 | Finding info, warning, error và gate threshold | Info không actionable; gate và mức findings nhất quán; coverage bàn giao 04 |

Tất cả ca ở trạng thái Chưa chạy cho đến khi có dòng kết quả trong báo cáo.

## 6. Lệnh kiểm tra tập trung

```powershell
python -m pytest -q tests/test_model.py tests/test_geometry.py tests/test_ground.py tests/test_config.py
python -m pytest -q tests/test_floating_detector.py tests/test_size_detector.py tests/test_track_detector.py
python -m pytest -q tests/test_heading_fit.py tests/test_spec_rules.py tests/test_detectors_a10.py tests/test_scan_wiring.py
```

Ghi số pass/fail/skip cho từng lệnh. Không coi test dataset thật hoặc hiệu năng đã được bao phủ bởi các lệnh này. Môi trường đặc biệt của máy hiện tại xem README chung.

## 7. Ca biên và cách ghi đáp án

Với mỗi ngưỡng t, kiểm t−ε, t và t+ε; ε theo đơn vị và độ chính xác phù hợp. Ghi toán tử thực tế (`>`/`>=`) và nguồn yêu cầu; không đặt t là một giá trị cứng khác config. Với yaw kiểm cả hai phía ranh giới ±π. Với gap kiểm số frame vắng, không nhầm với khoảng cách index giữa hai keyframe.

Ma trận luật cần có cột: rule, nguồn yêu cầu/spec, công thức, dữ liệu bắt buộc, trường hợp bỏ qua, điều kiện warn/error, fixture, kết quả, finding. Ngưỡng class/thuộc tính Việt Nam có giá trị ước lượng phải được đánh dấu; chưa có dữ liệu thật thì không chứng nhận độ phù hợp.

## 8. Bàn giao và hoàn tất

- [ ] Mọi luật được scanner gọi đã có dòng ma trận và kết quả/giới hạn.
- [ ] Ca tọa độ/đơn vị/occlusion và rule toggles có đáp án độc lập.
- [ ] Findings có vị trí đúng, điều kiện tái hiện và test sau sửa.
- [ ] Cấu hình/threshold thay đổi có lý do, dataset tuning và mã commit; chuyển đánh giá held-out cho 07.
- [ ] Gap chuyển đổi/pose/data chuyển cho 03; gate coverage và thông báo chuyển cho 04/05.
- [ ] `02-report.md` nêu rõ phần đã đọc, đã chạy, chưa kiểm dữ liệu thật và findings còn mở.
