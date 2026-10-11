# Ma trận luật và dữ liệu — phần 02

Mốc bản sửa: `2e3417db612fdc4442062c7d227bca9f12af064b`, nhánh `review/02-core-detectors`. Đường dẫn test/code tính từ `source-tool/pointsnap-3d`. Ngưỡng đọc từ cấu hình thực tế; không chốt lại ngưỡng trên tập kiểm tra.

## 1. Nguyên tắc chung

- Box: mét, yaw radian `[-π,π)`, dims=(length,width,height), tâm hình học, z lên.
- Các luật hình học trong scanner bỏ outside/occluded. Size/jump/heading theo track chỉ dùng keyframe thật; luật vòng đời vẫn cần outside/occluded.
- Tắt rule loại đúng finding của rule; 17 switches đã được kiểm riêng bằng ca tiêm finding vào scanner. `floating.no_evidence` dùng switch floating.
- Nguồn LiDAR/pose/time, ngưỡng và phạm vi class phải được phân biệt. Không có finding không chứng minh mọi class/luật đã được kiểm đủ.
- Dữ liệu sai shape/NaN/Inf hoặc pose không phải quay+tịnh tiến được từ chối; thiếu dữ liệu hợp lệ dùng hợp đồng coverage/fallback đã ghi rõ.

## 2. Ma trận 18 mã luật

| Mã luật | Phép đo / đơn vị | Dữ liệu và điều kiện | Mức / ngưỡng thực tế | Ca và test đối chiếu |
|---|---|---|---|---|
| floating | d=bottom_z−ground_z; đủ box khác: d−median(d khác), mét | Class tiếp đất, visible, cloud; min_ground_points; sweeps và loại điểm box khác | `abs(offset)>warning_m`; ERROR khi `>error_m` và `abs(d)>error_min_abs_m`; ít mẫu dùng single_* | R02-03/04/05; floating_detector, ground, detectors_a10; ca t−ε/t/t+ε mới |
| floating.no_evidence | Số frame thiếu mặt đất / số điểm tùy API | Ground không hợp lệ; gộp theo track, shape lẻ riêng | INFO, không actionable; gate vẫn bị chặn | R02-04/16; scan_wiring, gate_coverage, detectors_a10 |
| size.class_range | Kích thước từng chiều; median theo nhóm track/class/subtype, mét | Visible và keyframe; có resolved range. Ưu tiên default→stats→manual→custom. Class không có range: bỏ qua | Ngoài khoảng nới warning_margin/error_margin; chọn chiều nặng nhất | R02-06/07; size_detector, spec_rules, hồi quy subtype/keyframe |
| size.in_track | `abs(dim−median)` và tỷ lệ so median | Visible/keyframe; ≥min_keyframes cùng khóa range; bỏ excluded_classes | `>max(warning_abs_m,warning_rel×median)`; tương tự ERROR | R02-07; size_detector, detectors_a10, hồi quy subtype/keyframe |
| track.jump | Sai lệch tâm so nội/ngoại suy XY, mét; 2 keyframe dùng m/s | Keyframe visible; group class; pose đủ thì world, thiếu thì local. Time đủ cả chuỗi hoặc fallback đều | `>=jump_warning_m`; ERROR `>=jump_error_m` nếu world; đầu mút nhân 1,5; chỉ 2 box: speed>v_max cảnh báo | R02-08; track_detector, detectors_a10; timestamp epoch thiếu một frame |
| track.split_id | Khoảng cách XY tới vị trí ngoại suy, mét | Cùng class/subtype; gap 1..split_max_gap_frames; với CVAT A phải đã outside. Mọi ứng viên cùng hệ/time | WARNING nếu dist≤split_max_dist_m; không tự ghép ID | R02-09; track_detector; hồi quy world/local, subtype, track vẫn chạy |
| track.long_interpolation | Số frame vắng giữa 2 keyframe và quãng đường XY, mét | Không qua outside; hai đầu không occluded; long_interpolation.enabled, class có group | WARNING khi missing≥min_frames và motion>min_motion_m | R02-09/10/14; detectors_a10; hồi quy danh sách có box nội suy |
| track.reuse_id | Frame xuất hiện lại−frame outside | Keyframe outside rồi xuất hiện lại cùng track | WARNING; gợi ý theo max_occluded_frames, không tự tách track | R02-10; spec_rules |
| track.occluded_long | Số frame liên tục occluded; gồm phần đuôi tới job stop_frame | Box không outside; occluded kéo dài tới keyframe thay trạng thái hoặc cuối job | WARNING khi length>max_occluded_frames (mặc định 6) | R02-10; spec_rules; hồi quy occluded frame 1..10 |
| heading.flip | Chênh lệch hướng world giữa các đoạn; độ | Keyframe visible; ≥2; group class; pose thiếu chỉ WARNING; thời gian nhất quán | Cắt đoạn khi đổi hướng `>max(flip_warning_deg,yaw_rate_max_dps×dt)`; ERROR khi deviation≥flip_error_deg và world | R02-01/11; heading_fit; keyframe nội suy không tạo lỗi nhập tay |
| heading.motion | Góc box so hướng chuyển động và tốc độ | Keyframe visible; distance≥min_motion_m, speed≥min_speed_mps; không báo thêm trên box đã flip | Deviation>motion_warning_deg; ERROR ≥motion_error_deg nếu world | R02-08/11; heading_fit; hồi quy timestamp thiếu frame |
| heading.points | Góc trục cụm điểm modulo 90° trừ median track; độ | Class phù hợp, length≥min_aspect×width; đủ điểm và trong max_range_m; ≥2 box khác để dùng median | WARNING khi deviation>warning_deg; ERROR khi >error_deg | R02-11; heading_fit; +44/−44 và outlier 0° |
| fit.empty | Điểm raw trong box nới 20 cm, bỏ lớp sát đáy | Visible; không có điểm và ground đo được; sparse_warning_points>0 bật kiểm ít điểm | WARNING nếu raw_inside≤empty_max_points với ground; hoặc ít hơn sparse threshold | R02-12; heading_fit |
| fit.outside | Tỷ lệ điểm vật ngoài box trừ median các frame khác | Điểm liên thông quanh box, bỏ ground/box khác; outside và total đủ outside_min_points; ≥2 box khác dùng median | WARNING khi excess>outside_warning_ratio; ERROR khi >outside_error_ratio | R02-12; heading_fit; không đồng nhất tỷ lệ tuyệt đối với độ lệch track |
| fit.loose | Khoảng cách từ mặt nhìn thấy tới percentile 98 của điểm trong box, mét | Gần cảm biến, đủ điểm vật/điểm trong box, mặt không bị vật khác chắn | WARNING gap>loose_warning_m; ERROR >loose_error_m | R02-12; heading_fit; chỉ kiểm mặt nhìn thấy |
| fit.overlap | Diện tích giao BEV / diện tích box nhỏ hơn | Visible, cùng frame, class phù hợp; chồng Z>30% chiều cao nhỏ; loại allowed pairs theo class/subtype | WARNING ratio>overlap_warning; ERROR >overlap_error | R02-02/12/15; geometry, heading_fit; equal-size permutation |
| attr.missing | Số keyframe thiếu/rỗng thuộc tính | Không outside; required_attributes theo label; vẫn kiểm occluded | ERROR, gộp theo owner/attribute/value, gắn frame đầu sai | R02-13; spec_rules |
| attr.invalid | Giá trị ngoài allowed_values | Khóa Label.attribute ưu tiên hơn khóa chung; giá trị rỗng do missing xử lý | ERROR, không đoán lại giá trị đúng | R02-13; spec_rules |

## 3. Các fallback và giới hạn đã chốt

| Tình huống | Cách xử lý / giới hạn |
|---|---|
| Nguồn có pose nhưng thiếu một frame | Split không so local của A với world của B; chuyển toàn bộ ứng viên sang local và ghi has_world_pose=False. Gate thiếu pose vẫn KHÔNG ĐẠT |
| Timestamp thiếu một frame | Cả chuỗi dùng frame×interval. Cần xác minh interval phù hợp nguồn dữ liệu; không suy ra tốc độ chuẩn nếu lấy mẫu không đều |
| Cuboid list không có stop_frame | Không biết đoạn CVAT còn kéo dài sau annotation cuối. Dùng JobData khi quét CVAT; API trực tiếp có thể truyền stop_frame |
| Subtype không có range riêng | Size fallback về class nếu có range class; không tự dùng khoảng của một subtype khác |
| Rất ít instance | Script build_size_stats tính median từng đối tượng và chỉ sinh stats khi đủ instance; helper compute_class_ranges cũ có hợp đồng tính theo box. Không dùng lẫn hai tập thống kê |
| Guide spec-vn | Một số khoảng kích thước được ghi là ước lượng; test logic không chứng nhận độ phù hợp dữ liệu Việt Nam |
| Class/rule ngoài phạm vi | Không có finding không có nghĩa đã kiểm semantic/class đó. Sót đối tượng và quyết định phân loại vẫn cần reviewer |
| Đánh giá chất lượng | Test đáp án độc lập và scan scene thật xác minh logic/thực thi; precision/recall xem tay, hiệu năng trên nhiều máy và đánh giá held-out thuộc phần 07 |
