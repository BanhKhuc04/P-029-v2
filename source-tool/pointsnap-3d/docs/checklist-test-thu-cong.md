# Checklist test thủ công PointSnap 3D

Ngày lập: 09/10/2026. Đối chiếu code local hiện tại; đây là kế hoạch test, chưa phải kết quả đã chạy.

## 1. Hiểu sản phẩm trước khi test

PointSnap hỗ trợ kiểm chất lượng nhãn 3D cuboid trên CVAT. Luồng chính:

`nuScenes → xuất PCD + manifest + nhãn → task CVAT → người gán nhãn → PointSnap đọc nhãn đã Save → quét → báo cáo / review → gắn cờ → sửa trên CVAT → Save → quét lại → gate`.

- Ba nhóm kiểm tra: lơ lửng/lún, kích thước, track.
- Sáu luật bật/tắt: `floating`, `size.class_range`, `size.in_track`, `track.jump`, `track.split_id`, `track.long_interpolation`.
- Point cloud, pose và timestamp lấy qua bản xuất `manifest.json` và nuScenes. Không đọc point cloud trực tiếp qua API CVAT.
- Web quản lý dự án, guideline, token riêng, lịch sử quét, preview, review và báo cáo.
- Extension Chrome/Edge giúp lọc, chuyển frame/box, đọc cờ và nối review với web.
- API Docker `/pointsnap/jobs/{id}/report` là đường lấy báo cáo riêng; dùng PAT người gọi, cấu hình mặc định, không tự lấy guideline của dự án web.
- Tool chỉ ghi cờ `pointsnap_error`, không tự sửa hình học box. `reviewed` có trong label khi tạo task, nhưng review Đúng/Báo nhầm của web được lưu riêng trong `reviews.json`.
- Gate tính số finding Lỗi/Cảnh báo; chọn Báo nhầm không tự loại finding khỏi gate hoặc khỏi lần gắn cờ.
- Preview đọc snapshot của lần quét, không phải nhãn CVAT đang sửa trực tiếp. Có thể dùng keyframe gần nhất khi không có box đúng frame; cần đọc thông báo này.

## 2. Chuẩn bị và cách ghi kết quả

1. CVAT: `http://localhost:8080`; web: `http://127.0.0.1:8765`.
2. Đăng nhập CVAT, chọn đúng dự án, kiểm tra token, nuScenes root và thư mục bản xuất.
3. Ghi phiên bản code/CVAT, tên guideline, task ID, job ID và run ID. Không lấy số lượng lỗi của lần quét cũ làm đáp án cố định.
4. Dùng bản sao task/job cho mọi ca sửa box, chèn lỗi, đổi label, gắn cờ hoặc xóa dữ liệu. Giữ bản nhãn gốc để đối chiếu.
5. Trước mỗi ca thuật toán: ghi tọa độ/kích thước ban đầu, chỉ thay đổi một yếu tố, Save CVAT rồi quét lại. Khôi phục sau ca hoặc dùng bản sao khác.
6. Chốt ngưỡng trước khi đánh giá. Không tăng ngưỡng để làm biến mất lỗi trong lúc đo kết quả.
7. Gắn cờ: Save và đóng job đang chỉnh; sau khi hoàn tất mở lại/tải lại CVAT. Track/shape ID có thể đổi sau khi CVAT cập nhật nhãn; dùng link của lần quét mới nhất.

Mỗi ca ghi: **Đạt / Không đạt / Chưa chạy / Bị chặn**. Review thuật toán ghi riêng: **Đúng / Báo nhầm / Không chắc**. Không chắc để chưa chọn trên web và ghi lý do ở bảng ngoài, vì web chỉ có hai kết luận.

| Mã ca | Task/job/run | Bước thực hiện | Mong đợi | Thực tế | Kết quả | Ảnh / ghi chú |
|---|---|---|---|---|---|---|
| | | | | | Chưa chạy | |

## 3. Nhóm A — chạy, dữ liệu, kết nối

| Mã | Bước test | Kết quả mong đợi |
|---|---|---|
| A01 | Khởi động CVAT + PointSnap, mở web, bấm Bắt đầu. | Vào được giao diện; không kẹt màn tải; task/job hiện được sau khi kết nối. |
| A02 | Tạo dự án test, nhập URL/token đúng, nuScenes root, thư mục bản xuất; kiểm tra kết nối. | Có phiên bản CVAT, danh sách task/job đúng; chuyển dự án không dùng nhầm token/dữ liệu. |
| A03 | Trong dự án test, thử token sai, URL sai, job không tồn tại hoặc không được cấp quyền. | Báo lỗi rõ, không báo quét thành công và không lấy nhãn của job khác. Khôi phục cấu hình sau ca. |
| A04 | Mở task đã xuất nuScenes; xem đầu, giữa, cuối cảnh và xe/người/xe hai bánh. | Point cloud và box cùng hệ trục, box ôm đúng đối tượng, không quay 90° hoặc tráo dài/rộng; đối tượng đã biến mất không còn box kéo dài tới cuối job. |
| A05 | Kiểm ảnh ngữ cảnh nếu bản xuất/task có kèm camera. | Ảnh đúng thời điểm/đối tượng; nếu thiếu ảnh phải ghi thiếu dữ liệu, không kết luận đã test tính năng camera. |
| A06 | Trên dự án test, đổi đường dẫn bản xuất/dataset thành đường dẫn không có dữ liệu rồi quét. | Báo thiếu/không đọc được point cloud, bỏ kiểm lơ lửng/lún; không diễn giải kết quả là đã kiểm đủ. Size vẫn có thể chạy, track có giới hạn do thiếu pose. |

## 4. Nhóm B — thuật toán: cần các ca có đáp án và các ca dễ báo nhầm

Ngưỡng bên dưới là mặc định trong `pointsnap/config.yaml`. Guideline dự án có thể ghi đè: ghi ngưỡng thực dùng trước khi test. Mục tiêu là kiểm đúng đối tượng, frame, loại lỗi và số đo, không chỉ kiểm tổng số mục.

| Mã | Bước test | Kết quả mong đợi |
|---|---|---|
| B01 | Chọn xe có đủ điểm mặt đường và nhiều keyframe. Giữ nguyên kích thước, nâng một keyframe 40 cm, Save, quét. | Bắt lơ lửng đúng frame/track; số đo phản ánh đáy và chênh với track. Không bắt được khi đủ bằng chứng phải ghi là bỏ sót. |
| B02 | Tương tự B01 nhưng hạ 40 cm. | Bắt lún, dấu/số đo đúng. Gợi ý sửa phải là nâng đáy, không phải hạ tiếp. |
| B03 | Với một cảnh đủ điểm, tạo độ lệch nhỏ rồi tăng dần qua ngưỡng warning/error của guideline. | Phân mức theo ngưỡng và điều kiện hiện hành, không đòi mọi box nâng 20 cm đều phải mức Lỗi. Track mặc định: chênh >12 cm cảnh báo; >22 cm và khoảng cách tuyệt đối >15 cm mới Lỗi. Box lẻ: >15/30 cm. |
| B04 | Review box trên bờ vỉa, đường dốc, xa LiDAR, bị che hoặc ít điểm. | Không ép kết luận dựa vào con số tool. Phân biệt lỗi box với lỗi ước lượng mặt đất; ít bằng chứng có thể là Thông tin/chưa kết luận. |
| B05 | Chọn xe, chỉnh toàn track thành kích thước rõ ràng bất thường, ví dụ chiều rộng 5 m; quét. | Bắt `size.class_range` theo đúng class/chiều đo. Track được xét bằng trung vị, không cần lặp cùng cảnh báo cho mọi frame. |
| B06 | Track xe có >=3 keyframe: tăng một chiều của một keyframe 30%, giữ các frame khác. | Bắt `size.in_track` đúng frame; mặc định lệch phải vượt max(30 cm,15%) để mức Lỗi, max(10 cm,5%) để Cảnh báo. |
| B07 | Người đi bộ đổi tư thế; xe bus/xe công trình có kích thước lớn nhưng box vẫn khớp đối tượng. | `size.in_track` mặc định bỏ pedestrian. Cảnh báo class_range phải review bằng hình, kích thước khác thường không tự chứng minh nhãn sai. |
| B08 | Track xe có nhiều keyframe, dịch ngang một keyframe ở giữa 4 m, giữ các frame khác. | Bắt `track.jump` đúng track/frame hoặc ghi nhận cách detector nhóm cụm; xét độ lệch so nội suy, không lấy khoảng cách di chuyển giữa hai frame làm lỗi trực tiếp. |
| B09 | Xem đầu/cuối track, xe tăng tốc/rẽ, người bị che và cone đứng yên khi xe thu chạy. | Xác nhận bằng chuỗi frame. Khi có pose, vật đứng yên được so trong hệ toàn cục; đầu/cuối đoạn có ngưỡng nhân 1,5 nên không áp ngưỡng giữa đoạn. |
| B10 | Trên bản sao, tách một đối tượng liên tục thành hai ID cùng class, đoạn sau bắt đầu gần vị trí dự kiến trong khoảng gap cho phép. | Có nghi tách ID mức Cảnh báo; kiểm cả ID cũ/mới. Hai vật khác nhau đi gần nhau không được xác nhận là lỗi chỉ vì tool báo. |
| B11 | Trên bản sao, bỏ keyframe ở giữa để có >=2 frame nội suy, đối tượng dịch >1 m giữa hai keyframe còn lại và không có outside ở giữa. | `track.long_interpolation` có Cảnh báo khi bật. Với vật đứng yên hoặc đoạn có outside, không áp cùng kết luận. |
| B12 | Chọn một đoạn chưa xem cảnh báo, kiểm tất cả box bằng mắt rồi đối chiếu báo cáo. | Ghi được lỗi bị bỏ sót và giới hạn phạm vi; không gọi “không có finding” là chắc chắn nhãn đúng. |

## 5. Nhóm C — quét, review, guideline, báo cáo

| Mã | Bước test | Kết quả mong đợi |
|---|---|---|
| C01 | Quét một job đã Save, không bật gắn cờ. | Có tiến độ và kết quả; số box đúng phạm vi đọc; nhãn/thuộc tính CVAT không bị thay đổi. Bấm quét lại không kẹt giao diện. |
| C02 | Lọc từng mức, loại lỗi, class; tìm frame/track; chuyển trang rồi chọn dòng. | Danh sách/số lượng khớp bộ lọc; khung chi tiết đúng dòng được chọn, không nhầm chỉ số review sau lọc/phân trang. |
| C03 | Xem Duyệt nhanh góc trên/ngang; chuyển J/K qua nhiều mục. | Box/point cloud đúng đối tượng và frame snapshot; khi dùng keyframe gần nhất có thông báo; thiếu dữ liệu hiện lỗi rõ, không giữ ảnh cũ giả làm ảnh mới. |
| C04 | Chọn Đúng, Báo nhầm, đổi kết luận, bấm lại để bỏ; F5 và mở lịch sử. | Kết luận và bộ đếm lưu đúng mục/run, không mất sau tải lại. J/K, 1/2 không kích hoạt khi đang nhập ô tìm kiếm/cấu hình. |
| C05 | Tắt một luật rồi quét lại; bật lại. | Chỉ finding của luật tương ứng biến mất/trở lại; các luật còn lại vẫn chạy. Quét cũ không bị viết lại. |
| C06 | Sửa ngưỡng, class ranges và gate trên dự án test; Save, mở lại; thử YAML/giá trị không hợp lệ; reset. | Cấu hình hợp lệ được giữ và ảnh hưởng lần quét mới; cấu hình sai bị từ chối; reset về mặc định. Dự án khác không bị đổi. |
| C07 | Xuất HTML/CSV, đối chiếu vài dòng với web; mở link đúng box ở đầu/giữa/cuối job. | Frame, track, class, mức và tiếng Việt đúng; link dùng địa chỉ CVAT truy cập được. Đăng nhập CVAT trước để tránh mất tham số khi redirect. |
| C08 | Quét lần 1, sửa một box, Save, quét lần 2; xem lại cả hai trong lịch sử. | Lần 2 đọc nhãn mới; lần 1 vẫn giữ snapshot/báo cáo cũ. Review cũ không tự chuyển theo số thứ tự sang run mới. |
| C09 | Với bộ finding cố định, kiểm gate ở đúng giới hạn rồi vượt giới hạn cấu hình. | Mặc định đạt khi 0 Lỗi và <=10 Cảnh báo; Thông tin không tính. Chọn Báo nhầm không tự đổi gate. Nếu thiếu point cloud, ghi rõ phạm vi chưa được kiểm dù gate đạt. |
| C10 | Tạo hai dự án test; chuyển qua lại, đổi tên/mô tả; kiểm token không xuất hiện trong guideline/báo cáo/API trả dự án. Xóa chỉ dự án test rỗng. | Dữ liệu riêng từng dự án; không lộ token. Xóa dự án mất cả lịch sử của chính dự án đó, không xóa task CVAT hoặc dự án khác. |

## 6. Nhóm D — gắn cờ và sửa trên CVAT

| Mã | Bước test | Kết quả mong đợi |
|---|---|---|
| D01 | Trên bản sao có thuộc tính text mutable `pointsnap_error`, Save/đóng job, bấm Gắn cờ rồi mở lại CVAT. | Nút thực hiện lượt quét mới rồi ghi cờ đúng box Lỗi/Cảnh báo; Thông tin không gắn cờ. Tâm, kích thước, yaw, class, outside và nhãn khác giữ nguyên. ID có thể đổi. |
| D02 | Lọc `pointsnap_error is not empty`; chọn vài box và chuyển frame theo bộ lọc. | Box có cờ và nội dung khớp lần quét mới nhất; không nhầm số finding với số box hoặc số frame có cờ. |
| D03 | Sửa 3–5 lỗi đã xác nhận; Save/đóng job; Quét + gắn cờ, mở lại CVAT. | Finding đã hết điều kiện lỗi được bỏ; cờ cũ của box hết mọi finding được xóa. Nếu box còn lỗi khác thì vẫn có cờ tương ứng. |
| D04 | Trên task test thiếu thuộc tính cờ, thử gắn cờ; thử token chỉ đọc. | Báo lỗi rõ; không báo thành công giả và không thay đổi hình học nhãn để lách lỗi. |

## 7. Nhóm E — extension Chrome/Edge (nếu nhóm đưa extension vào demo)

| Mã | Bước test | Kết quả mong đợi |
|---|---|---|
| E01 | Nạp `extension/` trên Chrome/Edge, mở job có cờ. | Bảng PointSnap hiện, bộ lọc được bật; lần đầu thiếu lịch sử lọc có hướng dẫn tải lại. |
| E02 | Chọn 10 box có cờ, gồm frame có nhiều box; xem thẻ và gợi ý sửa. | Đúng box/class/nội dung; box được làm sáng; lún gợi ý nâng, lơ lửng gợi ý hạ. |
| E03 | Bấm trước/sau, dùng `,` `.` và chọn dòng danh sách; thử bấm liên tiếp. | Đến đúng frame thực và box, không tải lại toàn job, không làm thay đổi keyframe/nhãn. Không dùng J/K của web trong CVAT. |
| E04 | Mở đồng thời web và tab CVAT; chọn finding trên web; review ở từng phía. | CVAT chuyển tới đúng box không tải lại; kết luận hai phía đồng bộ sau khoảng 2 giây; không mở nhầm job khác. |
| E05 | Save CVAT, bấm Quét lại/Quét + gắn cờ; sau đó dừng PointSnap. | Khi chạy: tiến độ/kết quả và cờ cập nhật sau reload. Khi dừng: bảng/lọc/chuyển lỗi từ cờ CVAT vẫn dùng được; chức năng quét/review báo không kết nối. |

## 8. Nhóm F — API/CLI và đánh giá bổ sung

| Mã | Bước test | Kết quả mong đợi |
|---|---|---|
| F01 | Dùng `Get-Report.ps1` lấy JSON/HTML/CSV cùng job với PAT hợp lệ; thử thiếu/sai token hoặc job không có quyền. | Báo cáo đúng định dạng; không có quyền không nhận nhãn/báo cáo. Endpoint GET không gắn cờ. So sánh với web chỉ khi cùng nhãn và cùng cấu hình. |
| F02 | Dùng CLI `scan`/`gate` trên cùng job, dữ liệu và cấu hình; đo thời gian quét. | Kết quả nhất quán với web khi cấu hình giống nhau; gate exit 0 Đạt, 1 Không đạt, 3 lỗi chạy. Mục tiêu quét <2 phút/cảnh. |
| F03 | Chạy đánh giá lỗi chèn giả trên 5 cảnh test với ngưỡng đã chốt; review thêm finding không khớp log lỗi chèn. | Có recall theo từng loại/phạm vi và số mẫu; không gộp precision tự động với precision xem tay. Mẫu 0/0 ghi N/A, không kết luận recall 0%. |
| F04 | Nếu muốn chứng minh tiết kiệm thời gian: chia các đoạn tương đương, review thủ công và có tool, đổi thứ tự/người để giảm hiệu ứng nhớ. | Ghi thời gian, số box, lỗi tìm được, bỏ sót. Thời gian chuyển frame/quét không được gọi là thời gian review tiết kiệm. Đây là phép đo bổ sung; kế hoạch 4 ngày ban đầu đã cắt mục này. |

## 9. Test nào làm trước?

1. **Luồng dùng chính:** A01–A04, C01–C04, C07–C09, D01–D03.
2. **Chất lượng phát hiện:** B01–B12; ưu tiên review các mục hiện có, sau đó ca chèn lỗi có đáp án trên bản sao.
3. **Giới hạn và cấu hình:** A06, C05–C06, D04.
4. **Extension:** E01–E05 nếu có demo extension. API/CLI: F01–F02 nếu nhóm bàn giao các đường này.
5. **Số liệu báo cáo:** F03; F04 nếu đủ thời gian.

Chọn khoảng 50 finding để review, lấy từ nhiều cảnh nếu job hiện tại thiếu loại lỗi. Có thể nhắm 20 floating, 15 size, 15 track nhưng ghi số mẫu thật; không bịa đủ quota. Review thêm đoạn không xem trước cảnh báo để tìm bỏ sót.

| Run | Frame | Track/shape | Luật | Mức tool | Xem tay | Lý do / bằng chứng | Người xem |
|---|---|---|---|---|---|---|---|
| | | | | | Đúng / Báo nhầm / Không chắc | | |

- Precision xem tay mỗi loại = Đúng / (Đúng + Báo nhầm), mục tiêu >=70%; báo riêng số Không chắc và số mẫu.
- Recall trên ca có đáp án = số lỗi biết trước bắt đúng / tổng lỗi thuộc phạm vi đã tạo; ghi riêng box floating thiếu bằng chứng mặt đất.
- Báo nhầm /100 box = số finding đã xác nhận báo nhầm / số box được kiểm x100; tách Lỗi và Cảnh báo. Không lấy tất cả finding của nhãn nuScenes làm báo nhầm nếu chưa xác nhận.
- Mục tiêu tài liệu hiện tại: <=2 Cảnh báo và <=0,5 Lỗi /100 box; recall theo class/size trong track/jump theo mục 8.2 đề xuất; không dùng các bảng cũ làm kết quả hiện tại.

## 10. Điểm cần chú ý khi kết luận

- Web hiện dùng gợi ý chung `floating: Hạ đáy box...` trong `pointsnap/web/static/app.js`, kể cả mục lún: B02/E02 cần kiểm và ghi lỗi hướng dẫn nếu gặp. Extension có logic gợi ý riêng.
- `docs/danh-gia.md`, `giao-viec/review-test.md`, README và bảng nhiệm vụ có số liệu/trạng thái khác nhau. `docs/ket-qua-danh-gia-tu-dong.md` ghi đánh giá sau A10; mọi con số vẫn phải gắn với phiên bản/ngưỡng/ngày và lần chạy.
- Luật khoảng nội suy đã có trong code và cấu hình mặc định bật, dù một số tài liệu còn ghi ngoài phạm vi.
- `diff` chưa triển khai. Không coi nó là chức năng phải chạy thành công trong bản này.
- Yaw ngược, box rỗng, box chồng nhau, thiếu thuộc tính bắt buộc, bỏ sót đối tượng không nằm trong ba bộ phát hiện chính; vẫn cần người kiểm theo guideline.
- Gate là kết luận của tool, không khóa nộp job CVAT và không thay thế reviewer.

## 11. Nguồn đối chiếu trong repo

- `pointsnap/config.yaml`: ngưỡng và luật mặc định.
- `pointsnap/core/scanner.py`, `core/gate.py`, `detectors/*.py`: luật thực thi.
- `pointsnap/adapters/cvat/{reader,writer}.py`: đọc nhãn, snapshot, đồng bộ cờ.
- `pointsnap/cli/common.py`, `web/preview.py`: manifest, point cloud và snapshot preview.
- `pointsnap/web/{app,projects,runner,link}.py`, `web/static/app.js`: dự án, review, guideline, lịch sử và cầu nối extension.
- `extension/README.md`, `docs/thu-extension.md`: thao tác extension và thử trước đây.
- `pointsnap/api.py`, `README-Docker.md`: API báo cáo Docker.
- `CONVENTIONS.md`, `de-xuat-de-tai.md`, `giao-viec/review-test.md`, `docs/ket-qua-danh-gia-tu-dong.md`: quy ước, phạm vi và kế hoạch đánh giá.
