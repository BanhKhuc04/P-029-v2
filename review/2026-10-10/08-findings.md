# Sổ findings tổng hợp 01–08

Đối chiếu 12/10/2026. Giữ mã gốc và nguồn báo cáo. Có 95 nhóm findings trong 01–07; đây là số dòng báo cáo, không khẳng định 95 nguyên nhân độc lập. Các ca liên quan cùng boundary tham chiếu nhau. Người tiếp nhận là người phụ trách module ở TASKS; người mở PR kiểm phạm vi theo bàn giao.

## Các nhóm đã sửa/kiểm trong phạm vi báo cáo

| Mã | Mức | Phạm vi | Nguồn / SHA bàn giao | Trạng thái / owner |
|---|---|---|---|---|
| RV-01-001 | P1 | gate ĐẠT dù thiếu dữ liệu kiểm tra | [01](01-report.md), `c27d54b` | Đã xác minh theo báo cáo; owner module/nhánh nguồn |
| RV-01-002 | P2 | iterable generator làm mất số cảnh báo trong gate | [01](01-report.md), `c27d54b` | Đã xác minh theo báo cáo; owner module/nhánh nguồn |
| RV-01-003 | P2 | gate CLI văng lỗi khi file frame thiếu sau khi tìm manifest | [01](01-report.md), `c27d54b` | Đã xác minh theo báo cáo; owner module/nhánh nguồn |
| RV-01-004 | P2 | tài liệu khẳng định hoàn thành toàn sản phẩm quá mức | [01](01-report.md), `c27d54b` | Đã xác minh theo báo cáo; owner module/nhánh nguồn |
| RV-01-005 | P2 | mô tả dependency và data flow sai | [01](01-report.md), `c27d54b` | Đã xác minh theo báo cáo; owner module/nhánh nguồn |
| RV-01-006 | P2 | số liệu thiếu metadata và recall 0/0 ghi thành 0% | [01](01-report.md), `c27d54b` | Đã xác minh theo báo cáo; owner module/nhánh nguồn |
| RV-01-007 | P2 | test dotenv để token giả ảnh hưởng test CVAT thật | [01](01-report.md), `c27d54b` | Đã xác minh theo báo cáo; owner module/nhánh nguồn |
| RV-01-008 | P2 | ground test bỏ qua dataset được cấu hình ngoài tool/data | [01](01-report.md), `c27d54b` | Đã xác minh theo báo cáo; owner module/nhánh nguồn |
| RV-01-009 | P1 | cloud rỗng khi tắt floating vẫn cho gate ĐẠT | [01](01-report.md), `c27d54b` | Đã xác minh theo báo cáo; owner module/nhánh nguồn |
| RV-02-001 | P1 | core/config.py _Reader.number/min_max, _parse_track | [02](02-report.md), `7fca827` | Đã xác minh theo báo cáo; owner module/nhánh nguồn |
| RV-02-002 | P1 | core/model.py FrameData; geometry.py validate_pose | [02](02-report.md), `7fca827` | Đã xác minh theo báo cáo; owner module/nhánh nguồn |
| RV-02-003 | P2 | core/geometry.py quaternion_to_matrix, pose_matrix | [02](02-report.md), `7fca827` | Đã xác minh theo báo cáo; owner module/nhánh nguồn |
| RV-02-004 | P2 | core/ground.py estimate_ground_for_box/ring_ground_for_box/OtherBoxPoints | [02](02-report.md), `7fca827` | Đã xác minh theo báo cáo; owner module/nhánh nguồn |
| RV-02-005 | P2 | core/geometry.py to_box_frame/points_in_cuboid | [02](02-report.md), `7fca827` | Đã xác minh theo báo cáo; owner module/nhánh nguồn |
| RV-02-006 | P2 | detectors/floating.py detect_floating_for_box; size.py helper | [02](02-report.md), `7fca827` | Đã xác minh theo báo cáo; owner module/nhánh nguồn |
| RV-02-007 | P2 | detectors/size.py detect_size và class-range track | [02](02-report.md), `7fca827` | Đã xác minh theo báo cáo; owner module/nhánh nguồn |
| RV-02-008 | P2 | detectors/heading.py heading_points_findings | [02](02-report.md), `7fca827` | Đã xác minh theo báo cáo; owner module/nhánh nguồn |
| RV-02-009 | P2 | detectors/track.py detect_track_splits | [02](02-report.md), `7fca827` | Đã xác minh theo báo cáo; owner module/nhánh nguồn |
| RV-02-010 | P2 | track.py jumps/splits; heading.py _times | [02](02-report.md), `7fca827` | Đã xác minh theo báo cáo; owner module/nhánh nguồn |
| RV-02-011 | P2 | scanner.py check_track; track.py splits/spec/errors | [02](02-report.md), `7fca827` | Đã xác minh theo báo cáo; owner module/nhánh nguồn |
| RV-02-012 | P2 | scanner.py _typed_label wiring; track.py class_key | [02](02-report.md), `7fca827` | Đã xác minh theo báo cáo; owner module/nhánh nguồn |
| RV-02-013 | P2 | model.py Finding.sort_key; fit.py overlap_findings; size.py lựa chọn keyframe | [02](02-report.md), `7fca827` | Đã xác minh theo báo cáo; owner module/nhánh nguồn |
| RV-02-014 | P2 | size.py; track.py jumps/long interpolation; heading.py track | [02](02-report.md), `7fca827` | Đã xác minh theo báo cáo; owner module/nhánh nguồn |
| RV-02-015 | P2 | CONVENTIONS, source-tool/README, 01-report/architecture | [02](02-report.md), `7fca827` | Đã xác minh theo báo cáo; owner module/nhánh nguồn |
| RV-03-001 | P1 | Client theo next URL khác origin với Authorization của session | [03](03-report.md), `f79a85b` | Đã xác minh theo báo cáo; owner module/nhánh nguồn |
| RV-03-002 | P2 | Next /api/... ghép sai URL; phân trang lặp có thể treo; lỗi JSON thiếu ngữ cảnh | [03](03-report.md), `f79a85b` | Đã xác minh theo báo cáo; owner module/nhánh nguồn |
| RV-03-003 | P1 | Reader bỏ giá trị mutable tại keyframe sau không ghi lại attr; subtype/cờ có thể sai | [03](03-report.md), `f79a85b` | Đã xác minh theo báo cáo; owner module/nhánh nguồn |
| RV-03-004 | P2 | Roll/pitch NaN lọt vào attrs; lỗi parse points chưa kèm ID/frame | [03](03-report.md), `f79a85b` | Đã xác minh theo báo cáo; owner module/nhánh nguồn |
| RV-03-005 | P1 | Manifest trùng frame/file hoặc swap sample_token vẫn scan point cloud sai box | [03](03-report.md), `f79a85b` | Đã xác minh theo báo cáo; owner module/nhánh nguồn |
| RV-03-006 | P1 | Hệ ego thiếu transform hoặc transform/pose/time sai vẫn được coi có nguồn dữ liệu | [03](03-report.md), `f79a85b` | Đã xác minh theo báo cáo; owner module/nhánh nguồn |
| RV-03-007 | P1 | Auto manifest theo task ID có thể lấy dữ liệu server CVAT khác | [03](03-report.md), `f79a85b` | Đã xác minh theo báo cáo; owner module/nhánh nguồn |
| RV-03-008 | P2 | PCD TYPE/SIZE/COUNT/WIDTH sai vẫn được giải mã float32; export NaN/overflow | [03](03-report.md), `f79a85b` | Đã xác minh theo báo cáo; owner module/nhánh nguồn |
| RV-03-009 | P2 | np.fromfile bỏ byte cuối bị cắt; sweep corrupt bị coi thiếu hợp lệ | [03](03-report.md), `f79a85b` | Đã xác minh theo báo cáo; owner module/nhánh nguồn |
| RV-03-010 | P2 | JSON token trùng, sample/sweep lặp hoặc sai scene/time gây ghép sai/treo | [03](03-report.md), `f79a85b` | Đã xác minh theo báo cáo; owner module/nhánh nguồn |
| RV-03-011 | P1 | Gắn cờ frame đầu rồi không reset có thể báo cờ ở keyframe khác; xóa entry làm cờ trước quay lại | [03](03-report.md), `f79a85b` | Đã xác minh theo báo cáo; owner module/nhánh nguồn |
| RV-03-012 | P1 | Findings của scan cũ gắn/xóa sau khi người gán đã sửa; PATCH track đầy đủ có thể ghi đè thay đổi mới | [03](03-report.md), `f79a85b` | Đã kiểm guard; race atomic còn mở (RV-03-012) |
| RV-03-013 | P2 | ID keyframe mới sau PATCH làm finding cũ unmatched hoặc gỡ sai cờ | [03](03-report.md), `f79a85b` | Đã xác minh theo báo cáo; owner module/nhánh nguồn |
| RV-03-014 | P2 | Snapshot chuẩn hóa thiếu tags/raw metadata; helper verify dùng ID cũ và bỏ roll/pitch | [03](03-report.md), `f79a85b` | Đã xác minh theo báo cáo; owner module/nhánh nguồn |
| RV-03-015 | P2 | Upload fail trước khi trả info để lại task chưa rõ ID/không cleanup | [03](03-report.md), `f79a85b` | Đã xác minh theo báo cáo; owner module/nhánh nguồn |
| RV-03-016 | P2 | Flag immutable vẫn gửi ở shape và có thể không hiển thị đúng từng frame | [03](03-report.md), `f79a85b` | Đã xác minh theo báo cáo; owner module/nhánh nguồn |
| RV-04-001 | P1 | Run A trong memory được đọc/flag bằng slug B, có thể quét/gắn nhầm job với token B | [04](04-report.md), `59ef9c4` | Đã xác minh theo báo cáo; owner module/nhánh nguồn |
| RV-04-002 | P1 | Cùng millisecond+job tạo cùng ID, đè trạng thái/output | [04](04-report.md), `59ef9c4` | Đã xác minh theo báo cáo; owner module/nhánh nguồn |
| RV-04-003 | P2 | Restart làm biến mất queue/failed, chỉ summary done còn lại | [04](04-report.md), `59ef9c4` | Đã xác minh theo báo cáo; owner module/nhánh nguồn |
| RV-04-004 | P1 | DELETE project trong lúc scan có thể bị worker tạo lại hoặc mất dữ liệu run | [04](04-report.md), `59ef9c4` | Đã xác minh theo báo cáo; owner module/nhánh nguồn |
| RV-04-005 | P2 | JSON hỏng thành exception 500, run biến mất khỏi history hoặc thiếu findings vẫn bị hiểu done | [04](04-report.md), `59ef9c4` | Đã xác minh theo báo cáo; owner module/nhánh nguồn |
| RV-04-006 | P2 | CLI lỗi ghi snapshot/report/scan thoát traceback thay mã 3; sessions không được đóng | [04](04-report.md), `59ef9c4` | Đã xác minh theo báo cáo; owner module/nhánh nguồn |
| RV-04-007 | P2 | HTML đếm outside marker và tuyên bố job sạch/sẵn sàng nộp khi không có finding | [04](04-report.md), `59ef9c4` | Đã xác minh theo báo cáo; owner module/nhánh nguồn |
| RV-04-008 | P1 | API JSON tự đếm lỗi/cảnh báo để passed, bỏ coverage/no_evidence | [04](04-report.md), `59ef9c4` | Đã xác minh theo báo cáo; owner module/nhánh nguồn |
| RV-04-009 | P2 | checks hardcode luật cũ, vẫn kể rule bị tắt; JSON upstream sai thành 500 | [04](04-report.md), `59ef9c4` | Đã xác minh theo báo cáo; owner module/nhánh nguồn |
| RV-04-010 | P2 | Preset thiếu tạo project nửa chừng, tên Việt tạo slug không hợp lệ, update tên rỗng được lưu | [04](04-report.md), `59ef9c4` | Đã xác minh theo báo cáo; owner module/nhánh nguồn |
| RV-04-011 | P2 | manual_ranges/groups=null gây TypeError 500 | [04](04-report.md), `59ef9c4` | Đã xác minh theo báo cáo; owner module/nhánh nguồn |
| RV-04-012 | P1 | YAML raw của guideline cũ có token, lỗi CVAT echo token có thể đi ra CLI/Web/log | [04](04-report.md), `59ef9c4` | Đã xác minh theo báo cáo; owner module/nhánh nguồn |
| RV-04-013 | P1 | Bridge chỉ khóa job ID, CVAT khác server cùng ID có thể nhận focus/sai đối tượng | [04](04-report.md), `59ef9c4` | Đã xác minh theo báo cáo; owner module/nhánh nguồn |
| RV-04-014 | P1 | Preview tìm manifest chỉ task ID, có thể dùng cloud khác server; shape thiếu ID chọn box tùy ý | [04](04-report.md), `59ef9c4` | Đã xác minh theo báo cáo; owner module/nhánh nguồn |
| RV-04-015 | P2 | CSV CLI/Web để chuỗi label/message dạng formula không bảo vệ; API có logic riêng | [04](04-report.md), `59ef9c4` | Đã xác minh theo báo cáo; owner module/nhánh nguồn |
| RV-04-016 | P2 | Queue scan vô hạn; file tạm/lịch sử chưa có giới hạn vận hành rõ | [04](04-report.md), `59ef9c4` | Đã xác minh theo báo cáo; owner module/nhánh nguồn |
| RV-04-017 | P2 | Get-Report URL cố định; thiếu .env gây lỗi khó hiểu; UTF-8 không BOM bị PowerShell 5.1 parse sai tiếng Việt | [04](04-report.md), `59ef9c4` | Đã xác minh theo báo cáo; owner module/nhánh nguồn |
| RV-04-018 | P1 | Flag run đã fail hoặc scan của server cũ sau khi project đổi CVAT URL | [04](04-report.md), `59ef9c4` | Đã xác minh theo báo cáo; owner module/nhánh nguồn |
| RV-04-019 | P2 | Hai update project đọc–sửa–ghi có thể mất trường; ghi trực tiếp dễ để file dở | [04](04-report.md), `59ef9c4` | Đã xác minh theo báo cáo; owner module/nhánh nguồn |
| F05-01 | P1 | Form đọc/ghi size.class_range.manual_ranges sai schema; chuyển sang size.manual_ranges | [05](05-report.md), `43812b9` | Đã xác minh theo báo cáo; owner module/nhánh nguồn |
| F05-02 | P2 | Ngưỡng 0 bị thay bằng mặc định do parseFloat(...) | [05](05-report.md), `43812b9` | Đã xác minh theo báo cáo; owner module/nhánh nguồn |
| F05-03 | P1 | Request project/run cũ ghi đè state mới; capture slug/epoch và phiên load run | [05](05-report.md), `43812b9` | Đã xác minh theo báo cáo; owner module/nhánh nguồn |
| F05-04 | P2 | Empty giữ detail cũ; pagination có thể chọn mục ngoài trang | [05](05-report.md), `43812b9` | Đã xác minh theo báo cáo; owner module/nhánh nguồn |
| F05-05 | P2 | Poll scan dùng slug hiện tại, lỗi mạng mắc busy, phần trăm mô phỏng | [05](05-report.md), `43812b9` | Đã xác minh theo báo cáo; owner module/nhánh nguồn |
| F05-06 | P2 | F5 đổi project; history dùng created_at không tồn tại, failed/queued giống gate fail | [05](05-report.md), `43812b9` | Đã xác minh theo báo cáo; owner module/nhánh nguồn |
| F05-07 | P2 | Đổi form/YAML hoặc project mất draft; guideline tải chậm ghi đè edits | [05](05-report.md), `43812b9` | Đã xác minh theo báo cáo; owner module/nhánh nguồn |
| F05-08 | P2 | Modal thiếu focus trap/Escape/return focus; opener nằm trong dropdown đã ẩn | [05](05-report.md), `43812b9` | Đã xác minh theo báo cáo; owner module/nhánh nguồn |
| F05-09 | P1 | Review extension match frame/label/message làm review box khác có cùng cờ | [05](05-report.md), `43812b9` | Đã xác minh theo báo cáo; owner module/nhánh nguồn |
| F05-10 | P2 | Shape outside xuất hiện trong cờ; mutable track flag không carry và keyframe không sort | [05](05-report.md), `43812b9` | Đã xác minh theo báo cáo; owner module/nhánh nguồn |
| F05-11 | P1 | Danh sách nhiều box cùng frame chọn box đầu; focus từ Web không gửi ID | [05](05-report.md), `43812b9` | Đã xác minh theo báo cáo; owner module/nhánh nguồn |
| F05-12 | P2 | Highlight đoán box theo label, có thể trỏ nhầm | [05](05-report.md), `43812b9` | Đã xác minh theo báo cáo; owner module/nhánh nguồn |
| F05-13 | P1 | Scan/review/navigation trả chậm sau đổi job gắn vào job mới | [05](05-report.md), `43812b9` | Đã xác minh theo báo cáo; owner module/nhánh nguồn |
| F05-14 | P2 | Job chưa có attribute bị ẩn nút quét; job không có frame_count hiển thị 0 frame | [05](05-report.md), `43812b9` | Đã xác minh theo báo cáo; owner module/nhánh nguồn |
| F06-01 | P1 | POST không JSON đến guideline/reset dùng state server; source app43812b9 trả200 và rule false→true dù Origin evil.example | [06](06-report.md), `6282f05` | Đã xác minh theo báo cáo; owner module/nhánh nguồn |
| F06-02 | P1 | Worker chỉ kiểm prefix /api, cho PUT project/guideline và job khác bằng quyền mạng extension | [06](06-report.md), `6282f05` | Đã xác minh theo báo cáo; owner module/nhánh nguồn |
| F06-03 | P2 | Pydantic/YAML parser echo input/dòng source vào response/toast/CLI | [06](06-report.md), `6282f05` | Đã xác minh theo báo cáo; owner module/nhánh nguồn |
| F06-04 | P1 | Project địa chỉ mới giữ token cũ; lần check/scan sau có thể gửi PAT cũ tới server khác | [06](06-report.md), `6282f05` | Đã xác minh theo báo cáo; owner module/nhánh nguồn |
| F06-05 | P2 | Project metadata được trả trước khi client kiểm; link có thể mang credentials/javascript | [06](06-report.md), `6282f05` | Đã xác minh theo báo cáo; owner module/nhánh nguồn |
| F06-06 | P2 | NuScenes filename nối trực tiếp với dataroot → đọc LiDAR/camera/sweep ngoài root | [06](06-report.md), `6282f05` | Đã xác minh theo báo cáo; owner module/nhánh nguồn |
| F06-07 | P2 | Một số history/severity/frame/count và data-id render raw; nhãn chuẩn đã escape | [06](06-report.md), `6282f05` | Đã xác minh theo báo cáo; owner module/nhánh nguồn |
| F06-08 | P2 | Web parse body không giới hạn; pagination next luôn mới không dừng | [06](06-report.md), `6282f05` | Đã xác minh theo báo cáo; owner module/nhánh nguồn |
| F06-09 | P2 | URL.origin của file/javascript có thể thành null; dynamic scripts trùng built-in | [06](06-report.md), `6282f05` | Đã xác minh theo báo cáo; owner module/nhánh nguồn |
| F06-10 | P2 | Report API log request target chứa query; entrypoint bind0.0.0.0 không có lựa chọn local | [06](06-report.md), `6282f05` | Đã xác minh theo báo cáo; owner module/nhánh nguồn |
| F06-11 | P2 | Formula chỉ lstrip whitespace, BOM có thể che ký tự mở đầu | [06](06-report.md), `6282f05` | Đã xác minh theo báo cáo; owner module/nhánh nguồn |
| F06-12 | P2 | Web API không có cache policy riêng; iframe cùng site/khác port có thể nhúng UI | [06](06-report.md), `6282f05` | Đã xác minh theo báo cáo; owner module/nhánh nguồn |
| F07-01 | P1 | Metrics legacy tính INFO/no_evidence là TP và bỏ explicit rule. Chỉ warning+, match rule; ca đáp án0TP/1FN, sai rule→FP | [07](07-report.md), `5353683` | Đã xác minh theo báo cáo; owner module/nhánh nguồn |
| F07-02 | P1 | Scene khác trùng frame/track có thể nhận công; wrong log schema thành empty experiment. Scene key và reject schema không đúng; fixtures biết1TP/1FN | [07](07-report.md), `5353683` | Đã xác minh theo báo cáo; owner module/nhánh nguồn |
| F07-03 | P2 | Không mẫu ghi0%, measurement0, false alarms không có clean scan vẫn ĐẠT. Trả None/CHƯA ĐO; error/warning tách; size measurement cần expected quantity rõ | [07](07-report.md), `5353683` | Đã xác minh theo báo cáo; owner module/nhánh nguồn |
| F07-04 | P1 | Script run_eval_suite dùng5cảnh đầu/cuối,3detector cũ và ghi đè docs. Delegate CLI canonical, split eval/split.py, --out mới, giữ docs lịch sử | [07](07-report.md), `5353683` | Đã xác minh theo báo cáo; owner module/nhánh nguồn |
| F07-05 | P2 | error_rate0 vẫn chèn1 lỗi; invalidrate/rounds/scene list thiếu guard. 0→không chèn, rate[0,1], rounds≥1, cảnh không rỗng/trùng; tests | [07](07-report.md), `5353683` | Đã xác minh theo báo cáo; owner module/nhánh nguồn |
| F07-06 | P2 | Canonical denominator bỏ rule switches/class/min_frames/min_keyframes; finding có thể credit2 injection. Guard scope và used set; dữ liệu cũ được postprocess scope, scans/matches giữ | [07](07-report.md), `5353683` | Đã xác minh theo báo cáo; owner module/nhánh nguồn |
| F07-07 | P2 | Experiment thiếu commit/config hash/injection records, có thể đè bằng chứng. metadata.json/injections.json, config hash, seed/rounds/catalog; refuse output đã có metadata | [07](07-report.md), `5353683` | Đã xác minh theo báo cáo; owner module/nhánh nguồn |
| F07-08 | P2 | Runner local chưa Git, subprocess thiếu runtime path/temp quá dài; real-data configured invalid bị skip. Track runner/map/checklist; PYTHONPATH inherited runtime, short temp; explicit bad root fail | [07](07-report.md), `5353683` | Đã xác minh theo báo cáo; owner module/nhánh nguồn |
| F07-09 | P2 | Test đòi semaphore released ngay khi body tới, trước finally; live fixture không close client. Timeout acquire và finally session.close; full/live kiểm lại | [07](07-report.md), `5353683` | Đã xác minh theo báo cáo; owner module/nhánh nguồn |
| F07-10 | P2 | Map phát hiện Web box lún vẫn khuyên hạ đáy. findingFixTip nâng khi lún, khớp extension; Node regression mới và36 tổng đạt, không tính ca chưa chạy | [07](07-report.md), `5353683` | Đã xác minh theo báo cáo; owner module/nhánh nguồn |

## Bổ sung 08

Xem sáu nhóm F08-01…06, mức và ca kiểm lại trong [báo cáo 08](08-report.md). Commit code `94dac32`; test fixture `79849b4`.

## Liên hệ giữa các phần

- RV-01-001/009 → RV-04-008 → F07-03: coverage/gate và mẫu số không được suy thành quality tuyệt đối.
- RV-03-007 → RV-04-014 → F08-01: manifest vẫn giữ scope server+task; alias Docker chỉ cho cặp URL cùng server được operator khai báo.
- RV-04-013 → F05-09/11/13 → F06-02/03: bridge/focus/review phải giữ server/project/run/job/identity; Node/HTTP chưa thay cho MV3 thật.
- RV-01-006 và F07-01…07: tài liệu lịch sử thiếu metadata, metrics runtime đã sửa và eval mới có bằng chứng. Không gán metadata mới cho dữ liệu cũ.
## Findings còn mở và công việc tiếp nhận

| Mã chính / phạm vi | Mức | Điều kiện còn thiếu | Owner tiếp nhận / bước tiếp theo | Ảnh hưởng |
|---|---|---|---|---|
| RV-03-012 | P1, còn giới hạn | GET cuối → PATCH không atomic | Adapter CVAT: kiểm cơ chế concurrency upstream, thử Save đồng thời trên task riêng; giữ phối hợp không sửa cùng job | Chưa bảo đảm ghi cờ khi nhiều người sửa đồng thời |
| QUALITY-07 | P1 với kết luận nghiệm thu | Test proxy 3,566 warning / 0,551 error trên 100 box vượt mục tiêu; manual precision 0 mẫu | Detector/evaluation: xem tay từng nhóm, chốt dataset độc lập, sửa ngưỡng/luật rồi đo lại trên held-out mới | Chưa nghiệm thu chất lượng hoặc tự động chấp nhận nhãn |
| MV3-05 | P2, thiếu bằng chứng | Chrome/Edge thật chưa được kết nối trong phiên kiểm | Frontend/extension: Load unpacked, permissions, worker restart, route change, identity trùng, filter/focus/review theo checklist 05 | Chưa nghiệm thu toàn luồng extension |
| COMPAT-08 | P2, thiếu bằng chứng | Remote CI, Python 3.10, CVAT 2.77.0 chuẩn và server BTC chưa kiểm mới | Maintainer/test: chạy matrix/PR checks và task fixture đúng version | Không quảng bá tương thích mọi version/server |
| DEPLOY-08 | P2, ngoài mô hình đã kiểm | LAN/HTTPS/proxy path/auth nhiều người chưa có bằng chứng | Deployment/security: chốt auth/proxy, kiểm Host/Origin và permission/mounts trên môi trường đích | Chỉ dùng local tin cậy hoặc Report API với PAT trong phạm vi thử |
| OPS-08 | P2, thiếu bằng chứng | Restore database/nhãn CVAT thật, rollback toàn bộ version/dependencies chưa kiểm | Vận hành/test: diễn tập backup CVAT và migration/rollback trên stack riêng | Home fixture đã kiểm không chứng nhận disaster recovery |

Không có quyết định từ người dùng chấp nhận các giới hạn trên để phát hành rộng.
Đợt review hoàn tất về phạm vi và bàn giao; quality/release acceptance là bước riêng.
