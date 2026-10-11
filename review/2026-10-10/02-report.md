# Báo cáo phần 02 — core, hình học và bộ phát hiện

## 1. Kết quả bàn giao

| Mục | Giá trị |
|---|---|
| Nhánh | `review/02-core-detectors` |
| Người thực hiện | Codex theo yêu cầu của Nguyễn Văn Hân; người nhận nhánh review độc lập và mở PR |
| Ngày | 11/10/2026, Asia/Saigon |
| Mốc main đã fetch | `5dcc97f1ffc1751d022e2474c0b50745e348af86` |
| Dependency phần 01 | `1c3a7612482f8f82e6c1d0e6e987e5f33c1a90d6`; nhánh 02 tiếp nối bản sửa gate, test live và hợp đồng phần 01 |
| Commit sửa code phần 02 | `2e3417db612fdc4442062c7d227bca9f12af064b` |
| Môi trường | Windows, Python 3.12.14, pytest 9.1.1, Node v24.19.0 |
| CVAT thật | Docker local, API version 2.78.1; task thử đã tự xóa, kiểm lại còn 0 task thử |
| Dataset thật | `C:/Users/Han/Downloads/v1.0-mini`; test ground/reader thật và quét scene-0061 |
| Cấu hình | Mặc định, `env={}` cho core; không thay ngưỡng YAML/guideline hoặc chọn ngưỡng trên tập test |
| Test cuối | **317 Python đạt, 0 bỏ qua; 7 Node đạt**; 1 warning Starlette/httpx của môi trường |
| Hoàn tất review | 16/16 ca đã kiểm ở mức ghi trong bảng; 15 nhóm findings đã xử lý |
| Giới hạn nghiệm thu | Chưa đo precision xem tay, recall held-out nhiều vòng hoặc thao tác sửa nhãn trên trình duyệt |

Đọc nhanh: [02-handoff.md](02-handoff.md). Hợp đồng từng luật: [02-rule-matrix.md](02-rule-matrix.md). Lệnh và bằng chứng: [evidence/02/test-results.md](evidence/02/test-results.md).

## 2. Phạm vi đã đọc và kiểm tra

- Model/geometry/serialize: finite values, dims/yaw, pose/quaternion, biên điểm, biến đổi hệ tọa độ, JSON version/round-trip, thứ tự finding.
- Ground/box_points: min-Z, RANSAC/median vành đai, loại điểm của box khác, liên thông điểm vật, mặt box và overlap.
- Config/default/spec-vn: schema, phạm vi class/thuộc tính, ngưỡng, fallback, luật cũ/mới và switches.
- Scanner/gate: đường gọi sáu nhóm luật, prerequisite, dữ liệu thiếu, JobData vs iterable, sort/actionable và contract gate của phần 01.
- Detectors: floating, size, track, heading, fit, attributes; cả luồng thành công và điều kiện skip.
- Test hiện có và **65 ca mới** trong `tests/test_core_review_regressions.py`, có đáp án hình học/tính chất độc lập.

Không stage `.env`, dataset, output, snapshot, Docker/API/auto-tests local chưa theo dõi. Không sửa job gán nhãn của người dùng; test live dùng task thử riêng.

## 3. Kết quả 16 ca review

“Đạt” dưới đây là đã thực hiện ca review với đáp án/bằng chứng tương ứng; không chứng nhận độ chính xác mọi detector trên mọi dữ liệu.

| Ca | Điều kiện và đáp án đã kiểm | Mức kiểm / kết quả | Bằng chứng |
|---|---|---|---|
| R02-01 | Normalize ±π, quay 90°, yaw 179°→−179° nội suy qua π; không đổi dims để bù adapter | Unit, đạt; góc/ma trận dung sai 1e-12 | geometry, spec_rules, hồi quy yaw boundary |
| R02-02 | Điểm mặt/cạnh/góc box xoay thuộc box; điểm cách mặt 1e-7 m vẫn ngoài; shape sai không broadcast thành XYZ; empty `(0,3)` hợp lệ | Unit, đạt sau sửa | RV-02-002/003/005; geometry/model |
| R02-03 | t−1e-6 m, t, t+1e-6 m quanh warning/error floating; dấu bottom−ground và đơn vị | 6 ca độc lập, đạt; toán tử `>` theo code/config | test_floating_thresholds_have_independent_boundary_answers |
| R02-04 | Ground dốc/ít điểm/box lẻ; không biến thiếu bằng chứng thành ground=0; ROI giữ góc vành đai box xoay | Unit và ground thật, đạt | ground/floating_detector/detectors_a10; RV-02-004 |
| R02-05 | Không có sweeps và nguồn có sweeps; world center 0→12, tại t=0,5 là 6, trong sensor mới là −4; loại đúng điểm vật, giữ điểm đất | Unit có đáp án tọa độ; scene thật với sweeps=4, đạt | test_sweep_removes_moving_object_after_sensor_pose_conversion; EV-02-004 |
| R02-06 | Stats/manual/custom precedence, range boundary, class ít mẫu/không có range | Unit + đọc pipeline thống kê, đạt trong hợp đồng hiện có | size_detector; matrix mục fallback. Không chứng nhận class ngoài range |
| R02-07 | Min keyframes thật, pedestrian, occluded và subtype; không dùng median 8,25 m cho nhóm car 4,5 m và bus 12 m | Unit, đạt sau sửa | RV-02-006/007/014; size_detector/spec_rules |
| R02-08 | Pose xe thu, world/local và thiếu timestamp epoch ở 1 frame; xe đi đều không sinh jump giả | Unit và reader thật, đạt sau sửa | RV-02-009/010; track/heading_fit |
| R02-09 | Split đúng có outside; không split track còn kéo tới cuối job; subtype khác không ghép; cùng subtype vẫn bắt split thật | Mock JobData + unit, đạt sau sửa | RV-02-011/012; track_detector và hồi quy mới |
| R02-10 | Gap có 6/7 frame vắng, reuse sau outside, occluded cuối frame 1..10 =10 frame | Unit, đạt sau sửa | spec_rules; RV-02-011; test_gap_boundary_uses_number_of_missing_frames |
| R02-11 | Flip/motion/đứng yên/ít điểm, bỏ proxy nội suy; hướng trục ±44° gần nhau, outlier 0° phải được chỉ đúng | Unit, đạt sau sửa | heading_fit; RV-02-008/014 |
| R02-12 | Empty/outside/loose/overlap trên fixture độc lập; lọc ground/vật khác/occlusion/allowed pairs | Unit + quét scene thật, đạt; không suy ra precision | heading_fit/box_points; RV-02-004/013 |
| R02-13 | Missing/rỗng/giá trị sai/label-specific allowed values; cấu hình spec rỗng không tự tạo luật thuộc tính | Unit, đạt | spec_rules; đọc attributes.py |
| R02-14 | Tắt riêng 17 switches chỉ loại đúng rule; khóa C1/C2 cũ có default theo parser | 17 ca wiring và test config, đạt | test_each_switch_removes_only_its_findings; heading_fit/spec_rules/config |
| R02-15 | Hoán vị input không đổi mục tiêu overlap bằng kích thước, thứ tự shape findings; JobData và iterable khi cùng đủ hợp đồng | Unit, đạt sau sửa; JobData thêm biên job có nghĩa riêng được ghi rõ | RV-02-013; serialization/model tests |
| R02-16 | INFO không actionable; no_evidence vẫn chặn gate; warning/error theo caps; không dùng 0 finding để chứng nhận coverage | Unit/Web/CLI, đạt | gate_coverage, scan_gate, scan_wiring; dependency phần 01 |

Tổng: **16 Đạt, 0 Lỗi còn mở, 0 Bị chặn, 0 Chưa chạy** trong phạm vi review 02. Những phép đo chất lượng chưa thực hiện được ghi riêng ở mục 6.

## 4. Findings, lý do sửa và kiểm lại

Đường dẫn từ tool root; code tại commit `2e3417d`. Toàn bộ findings dưới đây đã sửa và xác minh trong phạm vi ghi rõ. Findings tài liệu được xác minh bằng đối chiếu code và kiểm tham chiếu; không giả là test thuật toán mới.

| Mã / mức | Vị trí | Trước sửa → cách sửa; tác động tới rework | Ca tái hiện / kiểm lại |
|---|---|---|---|
| RV-02-001 / P1 | core/config.py `_Reader.number/min_max`, `_parse_track` | NaN/Inf và interval=0 được nhận; có thể vô hiệu hóa điều kiện đo/cấp lỗi. Từ chối số không hữu hạn và yêu cầu interval>0, không đổi ngưỡng mặc định | test_config_rejects_nonfinite_numbers; test_config_rejects_infinite_range_and_zero_frame_interval |
| RV-02-002 / P1 | core/model.py FrameData; geometry.py validate_pose | Cloud sai shape/NaN, pose scale/NaN và timestamp NaN được coi là dữ liệu có mặt. Kiểm ở biên model/pose để lỗi dữ liệu không biến thành kết luận chất lượng | test_frame_rejects_invalid_point_cloud; test_frame_and_inverse_reject_invalid_pose; timestamp test |
| RV-02-003 / P2 | core/geometry.py quaternion_to_matrix, pose_matrix | Bình phương quaternion 1e300 tràn thành Inf rồi cho ma trận sai; 1e−300 bị coi là quaternion 0. Chuẩn hóa theo scale trước norm; từ chối NaN/Inf và translation sai | test_quaternion_normalization_is_stable_for_finite_scales; nonfinite components; geometry tests |
| RV-02-004 / P2 | core/ground.py estimate_ground_for_box/ring_ground_for_box/OtherBoxPoints | Cắt theo nửa cạnh lớn nhất bỏ góc box xoay; điểm của box khác còn bị tính là đất. Dùng bán kính đường chéo footprint nới để bao mọi góc trước khi lọc chính xác | Điểm y=1,3 trong box vuông xoay 45° phải bị loại nếu thuộc box khác; 16 điểm vành đai phải đo ground=0. Hai test rotated_* |
| RV-02-005 / P2 | core/geometry.py to_box_frame/points_in_cuboid | Shape `(N,1)` có thể broadcast thành XYZ; góc box có thể bị bỏ do sai số floating point. Kiểm shape và dung sai biên 1e−9 m; không nới box theo dung sai vẽ tay | Shape 1D/N×1/N×2 bị từ chối; corners 45° thuộc box; điểm ngoài 1e−7 m không thuộc |
| RV-02-006 / P2 | detectors/floating.py detect_floating_for_box; size.py helper | API detector trực tiếp còn kiểm box occluded dù scanner đã bỏ. Guard visible tại hàm trực tiếp để người dùng không phải sửa hình học ước lượng của vật bị che | test_public_detectors_ignore_occluded_cuboids |
| RV-02-007 / P2 | detectors/size.py detect_size và class-range track | Median trộn subtype/class; car 4,5 m và bus 12 m cùng label tổng bị báo sai bằng median 8,25 m. Nhóm theo track và khóa tra range, giữ đúng fallback class | test_size_track_does_not_mix_different_subtypes; spec_rules |
| RV-02-008 / P2 | detectors/heading.py heading_points_findings | Median tuyến tính của góc modulo 90° có thể báo 4 box chuẩn ±43/44° và bỏ outlier 0°. Unwrap trước median để chỉ đúng box phải sửa | test_heading_axis_median_wraps_modulo_90_degrees |
| RV-02-009 / P2 | detectors/track.py detect_track_splits | A thiếu pose dùng local, B đủ pose dùng world; hai hệ khác nhau vẫn được so và có thể cho khoảng cách 0 giả. Chọn cùng hệ cho toàn bộ ứng viên và ghi has_world_pose | A local x=100, B local x=0, chỉ B có pose +100: phải không split |
| RV-02-010 / P2 | track.py jumps/splits; heading.py `_times` | Một timestamp thiếu khiến epoch ~1e9 trộn với frame×0,5; xe đi đều bị jump và heading motion bỏ sót. Dùng timestamp đủ toàn chuỗi hoặc fallback đều toàn chuỗi | test_partial_timestamps_do_not_mix_epoch_and_frame_relative_seconds |
| RV-02-011 / P2 | scanner.py check_track; track.py splits/spec/errors | CVAT keyframe cuối không có nghĩa kết thúc; occluded cuối cũng kéo tới job stop. Truyền stop_frame, không split A chưa outside, đếm occluded tới cuối job | test_cvat_track_without_outside_keeps_running_to_job_end; test_occluded_last_keyframe_is_counted_until_job_end |
| RV-02-012 / P2 | scanner.py `_typed_label` wiring; track.py class_key | Hai subtype khác nhau trong label tổng vẫn bị gợi ý tách ID. Dùng class/subtype cấu hình khi ghép; cùng subtype và outside vẫn được kiểm | test_track_split_requires_the_same_configured_subtype |
| RV-02-013 / P2 | model.py Finding.sort_key; fit.py overlap_findings; size.py lựa chọn keyframe | Đổi thứ tự đầu vào làm đổi thứ tự shape hoặc box bị flag trong cặp overlap ngang kích thước. Thêm tie-break theo ID/label và thứ tự box xác định | Hai ca permutation: shape findings và equal-size overlap |
| RV-02-014 / P2 | size.py; track.py jumps/long interpolation; heading.py track | Box nội suy bị tính như box nhập tay; vừa sinh lỗi trên keyframe đúng, vừa che khoảng 4 frame thiếu keyframe. Chỉ dùng keyframe thật cho các luật này, giữ outside khi cắt đoạn | Size có proxy kéo dài 20 m phải không tạo lỗi nhập tay; dense 0..5 với manual 0/5 phải báo missing=4; proxy x=100/yaw=π không báo lỗi nhập tay |
| RV-02-015 / P2, tài liệu | CONVENTIONS, source-tool/README, 01-report/architecture | Dấu quay ghi +90° trong báo cáo 01, thực tế `(x,y)→(y,−x)` là −90°; README còn ghi floating 10/20 cm thay vì 12/22 theo track, 15/30 ít mẫu. Đính chính để người đọc không bù sai yaw hoặc hiểu sai ngưỡng | test_rotate_to_ego, default config, 6 ca threshold; kiểm tài liệu |

Những sửa này xử lý nguyên nhân cụ thể gây báo nhầm/bỏ sót và hướng dẫn sai. Không tự sửa hình học hoặc tự ghép/tách track trong CVAT; không chứng nhận mọi warning trên dữ liệu thật là lỗi thật.

## 5. Bằng chứng và dữ liệu thật

| Mã | Thực hiện | Kết quả |
|---|---|---|
| EV-02-001 | Đọc baseline phần 01, 16 ca và module/test; chốt branch/dependency | Main 5dcc97f, base phần 01 1c3a761 |
| EV-02-002 | Chạy ca hồi quy trước sửa | Đợt đầu 26 lỗi/3 đạt; thêm 3 ca track, 1 ca đuôi occluded và 2 ca nội suy đều tái hiện lỗi trước bản sửa tương ứng |
| EV-02-003 | Suite cuối với CVAT/nuScenes thật | **317 passed, 0 skipped, 1 warning in 22.34s**, exit 0; 65 ca mới |
| EV-02-004 | Quét scene-0061, 39 frame, 3333 box visible; default, sweeps=4 | Hoàn tất 19,068 giây; 44 WARNING, 6 ERROR, 102 INFO; số theo rule trong evidence |
| EV-02-005 | Node extension và Git | 7 passed; diff --check đạt; task live còn 0 |
| EV-02-006 | Tài liệu/mã ca/ma trận luật | Đủ 16 mã R02, 15 findings, 18 mã luật; links/code fences được kiểm trước commit |

EV-02-004 là kiểm tra thực thi trên một **scene tuning**, không phải đo precision/recall hoặc benchmark lặp. Không thay ngưỡng để làm ít warning hơn. Full suite có 2 ca CVAT live bảo toàn hình học/ghi-gỡ cờ và 4 ca ground/reader dataset thật; các task thử đều xóa.

## 6. Hợp đồng bàn giao và giới hạn

| Phần tiếp theo | Nội dung cần giữ / kiểm thêm |
|---|---|
| 03 | Pose/FrameData phải hợp lệ, hệ tọa độ −90° theo ma trận; JobData phải có stop_frame đúng; kiểm reader/manifest trên phiên bản và task thử |
| 04 | Truyền metadata biên job và dùng cùng gate coverage; hiển thị rõ lỗi dữ liệu/fallback. API local chưa tracked cần áp dụng contract trước khi đưa vào repo |
| 05 | Không gợi ý sửa proxy nội suy như box nhập tay; thể hiện đúng frame/ID của finding ổn định; kiểm lại thao tác trình duyệt |
| 06 | Parser từ chối NaN/Inf nhưng chưa thay cho review toàn bộ input/secrets/URL/schema; kiểm cùng nhánh phần 06 |
| 07 | Chạy đánh giá có commit/config/data/seed/catalog/rounds, precision xem tay và held-out; đo hiệu năng lặp. Scan 19 giây không chứng nhận hiệu năng mọi job/máy |
| 08 | Ma trận tương thích local Python 3.12/Node 24/CVAT 2.78.1 với CI 3.11/22 và CVAT chuẩn 2.77; packaging/cài mới |

Fallback timestamp giả định lấy mẫu đều theo cấu hình. Cuboid list không có biên job không thể chứng nhận đoạn đuôi CVAT. Class chưa có range và kích thước Việt Nam ước lượng vẫn là giới hạn dữ liệu. Những mục này được ghi rõ, không tự chốt nghiệm thu.

## 7. Kết luận

Review phần 02 đã hoàn tất; **15 nhóm findings đã sửa, không có finding mở trong phạm vi đã review**. Các lỗi gây rework có ca đáp án độc lập chứng minh trước/sau. Kết quả cuối: **317 test Python và 7 test Node đạt; 0 test bị bỏ qua**.

Nhánh **`review/02-core-detectors`** tiếp nối phần 01. Nếu phần 01 chưa merge, người nhận mở PR với base `review/01-overview-architecture` để chỉ thấy diff phần 02; sau khi phần 01 merge có thể chuyển base sang `main`. Không tạo hoặc merge PR trong lượt này theo yêu cầu bàn giao.
