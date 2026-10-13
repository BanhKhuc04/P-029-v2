# Kế hoạch review tiếp phần 09–16 — tính năng mới trên main

Ngày đối chiếu: **13/10/2026, Asia/Saigon**. Cập nhật: **phần 09–11 đã review/sửa, kiểm và push GitHub**; xem [báo cáo 11](11-report.md) / [bàn giao 11](11-handoff.md). Phần 12–16 chưa thực hiện. Các ca và giới hạn bên dưới là kế hoạch gốc; kết quả hiện hành nằm trong báo cáo riêng.

## 1. Chốt lại phạm vi

- Nền review 01–08: `5dcc97f1ffc1751d022e2474c0b50745e348af86` (sau PR #37).
- Main chứa tính năng mới trước khi nhập kết quả review: `be1778c`.
- Mã nguồn phải dùng để review tiếp: **`d18b1a9e915d358ab14d281ce256a87bbaab8855`**, main sau PR #54.
- Đã `git fetch origin main` ngày 13/10: local main và origin/main cùng SHA trên. Không có commit mới hơn PR #54 tại thời điểm đối chiếu.
- Báo cáo [recheck 01–08](../2026-10-10/recheck-01-08-report.md) ghi rõ tính năng mới trên main ngoài phạm vi review. Suite hồi quy đã chạy khi hòa main vào nhánh review không thay thế review tính đúng hoặc nghiệm thu các tính năng mới.

Vì vậy, lấy **`5dcc97f..be1778c`** để nhận diện nội dung mới, rồi đọc và kiểm trên **`d18b1a9`** để bao gồm cách nó kết hợp với sửa review 01–08. Chỉ so `d18b1a9..origin/main` sẽ bỏ sót toàn bộ phạm vi này.

Diff nhận diện có **131 file**, **8.238 dòng thêm / 532 dòng xóa**, gồm mã nguồn, test, tài liệu và đổi vị trí file. [Inventory](scope-inventory.tsv) ghi từng file, trạng thái đổi, phần phụ trách và vùng bị PR #54 chạm lại. File di chuyển nguyên nội dung chỉ cần xác minh đường dẫn và tham chiếu; không tính là một tính năng mới.

Trong 131 file này, **35 file còn được thay đổi bởi đợt review nhập qua PR #54**. Các phần giao nhau phải kiểm trên main hiện tại, nhất là ground/scanner/config/heading/fit/track, adapter, Web và extension; không áp dụng lại nguyên bản patch tính năng cũ lên main.

## 2. PR và nội dung chưa có nghiệm thu trong đợt trước

Các PR dưới đây được xác định từ lịch sử first-parent local sau khi fetch; không phải danh sách PR còn mở trên GitHub.

| PR | Nội dung | Phần review tiếp |
| --- | --- | --- |
| #39 | C3: vật đứng yên, camera, Box Critic, học từ kết luận | 11, 12, 14, 15 |
| #50 | Bàn giao giai đoạn 3; ngưỡng floating 15 cm; C5, C6, C7, C8; extension nhận luật mới | 09–15 |
| #44 | Tìm điểm quanh box nhanh bằng chỉ mục x | 09, 15 |
| #42 | Heading thiếu pose; góc trục modulo 90° | 09 |
| #41 | Track jump ở hai đầu track | 09 |
| #46 | Token CVAT; slug/run_id phải khớp toàn chuỗi | 14, 16; kiểm giao với sửa bảo mật 06 |
| #43 | Box Critic ensemble và giải phóng GPU | 11, 15 |
| #47 | Fit loose so với các frame khác của track | 09, 15 |
| #49 | C4: mặt đất dốc, điểm tiếp xúc thấp nhất | 09 |
| #40 | Grounding DINO + SAM 2.1, hybrid; kết hợp C7/C8 trong scanner | 12, 13, 14, 15 |
| #45 | Heading points hạ ngưỡng 15° → 12° | 09, 15 |
| #51 | Sắp xếp thư mục, báo cáo và hình minh họa, tài liệu huấn luyện | 16 |
| #52 | C4: track đi từ đường bằng lên dốc | 09, 15 |
| #53 | Khôi phục README gốc; README sản phẩm đặt bên trong | 16 |

PR #48 không thuộc lịch sử main tại SHA này. Tài liệu bàn giao ghi để ngỏ; nếu sau này merge, bổ sung phạm vi theo diff mới, không tự đưa ngưỡng đó vào baseline.

## 3. Cách tiến hành

Thứ tự: **09 → 10 → 11 → 12 → 13 → 14 → 15 → 16**. Cần kết quả camera 12 trước khi kết luận missing-object 13; cần kết quả các detector trước khi kết luận số liệu 15.

Mỗi phần thực hiện: đọc diff và luồng gọi → lập ma trận điều kiện → test tập trung → dữ liệu thật/thao tác tay liên quan → ghi findings và bàn giao. Nếu sửa, kiểm trước/sau trên cùng input và giữ nguyên sửa 01–08. Đã chuẩn bị 8 nhánh local theo yêu cầu, mỗi nhánh chứa bộ kế hoạch chung và hướng dẫn riêng; xem [phân nhánh và cách thực hiện](README.md). Mã nguồn khởi đầu của cả tám nhánh là main `d18b1a9` cộng commit tài liệu kế hoạch. Khi phần trước đã merge, cập nhật nhánh tiếp theo từ main trước khi làm. Việc chuẩn bị nhánh chưa thực hiện các ca review hoặc merge kết quả.

### Chuẩn ghi nhận

- Checklist mã `TC-09-001`…`TC-16-008`; tất cả **Chưa chạy** khi lập kế hoạch. Có 64 ca, mỗi ca có thể triển khai thành nhiều test con.
- Trạng thái: Đạt / Lỗi / Bị chặn / Chưa chạy / Không áp dụng (kèm lý do). Không cộng SKIP hoặc XFAIL vào PASS.
- Finding mã `RV-09-001`…; tham chiếu mã cũ nếu cùng lỗi. Ghi mức, điều kiện, file/dòng, cách tái hiện, tác động, hướng sửa, người xử lý và test cần chạy lại.
- Evidence mã `EV-09-001`…: SHA, lệnh/thao tác, config hash, scene/job/frame/track, phiên bản model/checkpoint, seed, môi trường CPU/GPU và kết quả. Phân biệt đọc code, fixture/mock, dataset thật, model thật, CVAT thật và trình duyệt.
- Kết quả mỗi phần: `NN-report.md`, `NN-handoff.md`, `evidence/NN/`. Báo cáo có checklist trạng thái, files đã đọc, findings, test và giới hạn.

### Chuẩn bị chung trước khi thực hiện

1. Ghi lại HEAD và trạng thái workspace. File `.tmp/`, `outputs/`, architecture local và output hiện có không phải bằng chứng mới.
2. Xác minh môi trường Python hiện có; chạy `python -m pointsnap --help`, ghi phiên bản Python/Node. Lệnh bên dưới chạy từ `source-tool/pointsnap-3d/` trong môi trường đã cài project; không giả định Python hệ thống đúng môi trường.
3. Ghi đường dẫn nuScenes mini, ảnh/calibration/pose, model weights và CVAT thử. Thiếu tài nguyên thì ghi Bị chặn ở đúng ca; tiếp tục phần đọc code/fixture.
4. Mọi scan/eval ghi vào thư mục mới riêng, không ghi đè báo cáo lịch sử. Không tự tải model nặng hoặc huấn luyện dài trước khi xác định bộ dữ liệu và runtime cần kiểm.
5. Mọi thao tác ghi CVAT dùng task/job thử riêng có backup và nhận diện trước/sau. Không dùng ID job trong tài liệu cũ làm job đang hoạt động nếu chưa đối chiếu.

## 4. Phần 09 — hình học, ground, heading, fit, track

**Ưu tiên cao:** thuật toán thay đổi có thể bỏ sót lỗi nhãn hoặc tăng báo nhầm.

Đọc: `pointsnap/core/ground.py`, `core/box_points.py`, `detectors/floating.py`, `heading.py`, `fit.py`, `track.py`, `size.py`, `core/scanner.py`, `core/config.py`; đối chiếu [CONVENTIONS](../../source-tool/pointsnap-3d/CONVENTIONS.md).

| Mã | Kiểm tra và tiêu chí |
| --- | --- |
| TC-09-001 | Ground đường bằng, dốc dọc/ngang, box xoay, đá/vỉa hè, điểm chỉ một phía: đúng hệ tọa độ, độ cao đáy và dung sai theo config. |
| TC-09-002 | Track bằng → dốc: nhãn đúng không báo; box lún/lơ lửng thật vẫn phát hiện. Tái hiện XFAIL dốc 8°, nâng 25 cm; định lượng phạm vi bỏ sót, không ghi đã sửa hết C4. |
| TC-09-003 | Thiếu/ít điểm, ngoại lai, point cloud rỗng: phân biệt thiếu evidence với sạch; gate phản ánh coverage phù hợp. |
| TC-09-004 | Chỉ mục OtherBoxPoints: đối chiếu tập điểm với cách lọc trực tiếp, gồm biên x, yaw, box chồng, bán kính và dữ liệu bất thường. |
| TC-09-005 | Heading motion thiếu pose/pose một phần; góc ±π và modulo 90°; vật đứng yên/xe quay: không coi chuyển động ego là lỗi vật. |
| TC-09-006 | Track jump đầu/cuối và track ba box, đứng yên, quay thật, timestamp không đều, frame thiếu: nới ngưỡng không làm bỏ sót nhảy 4 m. |
| TC-09-007 | Fit loose so track; một frame dư và cả track dư, thay đổi kích thước thật, ít điểm, cùng ID khác class: reference không tự chứa outlier và không trộn vật. |
| TC-09-008 | Ngưỡng heading 12° và floating 15 cm: kiểm đúng sát biên, severity, config mặc định/spec-vn và thay đổi recall/báo nhầm so ngưỡng cũ. |

Test đầu: `python -m pytest -q tests/test_ground.py tests/test_ground_slope.py tests/test_heading_fit.py tests/test_track_detector.py tests/test_size_detector.py tests/test_core_review_regressions.py`.

## 5. Phần 10 — tình huống thực tế và luật spec C5/C6/C8

Đọc: `detectors/attributes.py`, `track.py`, `size.py`, `core/config.py`, `guidelines/spec-vn.yaml`, `tests/scenario_sim.py`; đối chiếu [giao việc C5](../../source-tool/pointsnap-3d/quan-ly/giao-viec/C5-tinh-huong-thuc-te.md), [C6](../../source-tool/pointsnap-3d/quan-ly/giao-viec/C6-bam-spec.md).

| Mã | Kiểm tra và tiêu chí |
| --- | --- |
| TC-10-001 | Track ID swap giữa hai vật: bắt đổi ID, không báo khi vượt/giao nhau/quay thật, class và subtype được giữ riêng. |
| TC-10-002 | Attr height theo tư thế: chiều cao box, box xoay, ngồi/nằm/đứng, trẻ em và ít điểm; thiếu chứng cứ không suy thành lỗi chắc chắn. |
| TC-10-003 | Spec inside: người trong xe so với đứng sát xe, bị che hoặc box giao nhau; hình học theo cùng frame và tọa độ. |
| TC-10-004 | Spec rider double: rider + xe hai bánh, box lặp thật so hai người/xe cạnh nhau; không báo lặp chỉ vì overlap hợp lệ. |
| TC-10-005 | Rider state: lên/xuống xe, chuyển tư thế thật và thuộc tính thiếu; xác minh đoạn thay đổi và cửa sổ thời gian. |
| TC-10-006 | Size cargo/xe chở hàng: nới ngưỡng theo evidence, không che một box phóng đại hoặc lệch thật. |
| TC-10-007 | Class/spec-vn, tên thuộc tính, case, giá trị other và taxonomy nuScenes: luật áp dụng đúng nhóm; GUI toggle khớp key config. |
| TC-10-008 | Kiểm độc lập scenario simulator: oracle không lấy cùng helper cần kiểm; thêm phản ví dụ và so tình huống thật. Người mang vật dài còn ngoài khả năng hiện tại phải được ghi rõ. |

Test đầu: `python -m pytest -q tests/test_scenarios.py tests/test_spec_geometry.py tests/test_spec_rules.py tests/test_size_detector.py tests/test_config.py`.

## 6. Phần 11 — Box Verifier, Critic ensemble và học từ kết luận

Đọc: `detectors/static.py`, `pointsnap/critic.py`, `learn.py`, `cli/learn_cmd.py`, `cli/eval_cmd.py`, `web/runner.py`, `scripts/train_critic_example.py`, `scripts/colab_train_critic.ipynb` và [hướng dẫn huấn luyện](../../source-tool/pointsnap-3d/docs/huong-dan/huan-luyen-box-critic.md).

| Mã | Kiểm tra và tiêu chí |
| --- | --- |
| TC-11-001 | Vật đứng yên trong world frame: ego chạy/quay, pose thiếu và vật chuyển động chậm; không nhầm sensor frame với world frame. |
| TC-11-002 | Feature Critic và nhiễu box: đơn vị, chuẩn hóa, point cloud rỗng/ít điểm, seed; target có thể kiểm độc lập. |
| TC-11-003 | Checkpoint đơn/ensemble: shape, dtype, thiết bị, file hỏng/không tin cậy; kiểm cách load và xử lý lỗi, model không có không được thành đã kiểm tốt. |
| TC-11-004 | So logit tương đối track: có/không reference hợp lệ, nhiều outlier, track ngắn; không coi score model là xác suất lỗi đã hiệu chuẩn. |
| TC-11-005 | Train/export: tuning và held-out tách theo scene/track; ensemble seed; giải phóng GPU và tái lập. Không dùng cảnh kiểm tra để chỉnh ngưỡng. |
| TC-11-006 | Learn đọc kết luận: sửa/xóa verdict, trùng run/box, dữ liệu thiếu/hỏng, nhiều project; không trộn mẫu hoặc dùng nhãn tự sinh làm verdict người dùng. |
| TC-11-007 | Cross validation và hạ severity: leakage cùng track/run, mẫu nhỏ/lệch class; bật/tắt adjust_severity, ngưỡng sát biên và ảnh hưởng gate. |
| TC-11-008 | Learned history: version, restore, ghi đồng thời/hỏng giữa chừng, đường dẫn project; giữ được mô hình trước và báo lỗi rõ. |

Test đầu: `python -m pytest -q tests/test_critic.py tests/test_learn.py tests/test_scenarios.py tests/test_web.py`.
Hai test Critic dùng PyTorch từng bị SKIP trong recheck trước. Phải chạy với PyTorch/checkpoint thử hợp lệ trước khi nghiệm thu; test model giả và checkpoint thật ghi riêng.

## 7. Phần 12 — camera và các model ảnh

Đọc: `core/camera.py`, `vision/detector2d.py`, `detectors/camera.py`, `adapters/nuscenes/reader.py`, `core/config.py`, `core/scanner.py`, `scripts/eval_camera.py`.

| Mã | Kiểm tra và tiêu chí |
| --- | --- |
| TC-12-001 | Chiếu LiDAR → camera: extrinsics/intrinsics, hướng transform, depth, box sau camera, ngoài ảnh và camera nhiều hướng; đối chiếu hình thật. |
| TC-12-002 | Mismatch/class/missing: che khuất, model không thấy, ánh tối, ảnh thiếu, nhiều camera; model không detect không đủ để kết luận box sai. |
| TC-12-003 | Mask R-CNN / gdino-sam2 / hybrid: nhóm class hỗ trợ, tên prompt, cone và rider; lựa chọn model khớp capability thực tế. |
| TC-12-004 | Effective model đi qua cả check_camera, cam.sparse và check_missing; thử từng mode và cấu hình override. |
| TC-12-005 | CPU/GPU/autocast, torchvision/transformers/weights thiếu, offline và model load lỗi: fallback rõ, không crash toàn scan hoặc báo coverage đầy đủ sai. |
| TC-12-006 | Cache: phân biệt model, checkpoint/prompt/ảnh thay đổi, cache cũ/hỏng; chạy lạnh và nóng cho kết quả tương ứng. |
| TC-12-007 | IoU/mask và rescale ảnh: object nhỏ/xa, mép ảnh, resize, nhiều object; đo với oracle độc lập. |
| TC-12-008 | Chạy model thật trên mẫu cố định: ảnh/calibration/config/checkpoint có nguồn; lưu evidence, thời gian và lỗi GPU/OOM. Mock PASS không thay ca này. |

Test đầu: `python -m pytest -q tests/test_camera.py tests/test_config.py tests/test_real_nuscenes.py`. Ca model thật cần chạy riêng vì tests hiện có gồm detector giả.

## 8. Phần 13 — sót đối tượng LiDAR và cam.sparse C7/C8

Đọc: `detectors/missing.py`, `detectors/camera.py`, `core/scanner.py`, `core/config.py`; đối chiếu [kết quả missing cũ](../../source-tool/pointsnap-3d/docs/ket-qua/ket-qua-sot-doi-tuong.md).

| Mã | Kiểm tra và tiêu chí |
| --- | --- |
| TC-13-001 | Bỏ box của vật chuyển động trên bản sao nhãn: cụm, pose bù ego, frame association; tìm đúng vị trí và không đếm trùng qua frame. |
| TC-13-002 | Đối tượng đã gán: visible/occluded, box xoay, lớn, mép vùng; mask loại vật đã có nhãn không che luôn vật bị sót bên cạnh. |
| TC-13-003 | Vật đứng yên có/không ảnh xác nhận ban ngày: đúng điều kiện cho C8; thiếu camera ghi giới hạn coverage. |
| TC-13-004 | Người đứng/đi chậm trong nhóm, xe >30 m, xe buýt một phần: đo bỏ sót và ghi giới hạn; không gán recall tổng cho mọi tình huống. |
| TC-13-005 | Mưa/nhiễu/ground/đám cây/ít điểm: phân nhóm và ngưỡng không tạo báo nhầm hàng loạt. |
| TC-13-006 | Cam sparse: số điểm sát ngưỡng, bằng chứng ảnh có/không, tắt camera, đổi model, class không hỗ trợ; ngưỡng P-009 chưa chốt ghi là quyết định còn mở. |
| TC-13-007 | Finding không có box/track ID: frame và vị trí gợi ý, CSV/HTML/API/UI/extension/CVAT chịu được; không chọn nhầm box tồn tại. |
| TC-13-008 | Missing/false alarm đánh giá độc lập: GT vật bị xóa riêng, số vật/số cảnh và mẫu số đúng; đối chiếu tay nhãn sạch và nhóm khó. |

Test đầu: `python -m pytest -q tests/test_missing.py tests/test_camera.py tests/test_scenarios.py tests/test_scan_gate.py`.

## 9. Phần 14 — tích hợp config, CLI, Web, extension, CVAT và gate

Đọc các điểm nối: `core/config.py`, `config.yaml`, `guidelines/spec-vn.yaml`, `core/scanner.py`, `core/gate.py`, `cli/main.py`, `web/app.py`, `web/runner.py`, `web/static/app.js`, `web/static/index.html`, `extension/src/core.js`, `extension/src/content.js`, reader CVAT/nuScenes và report.

| Mã | Kiểm tra và tiêu chí |
| --- | --- |
| TC-14-001 | Tất cả key mới rules/static/camera/missing/critic/learning/spec có validation kiểu, hữu hạn, miền giá trị và quan hệ ngưỡng; giữ sửa parser 02/06/recheck. |
| TC-14-002 | Toggle config/scanner/GUI: từng luật mới bật tắt độc lập, override và round trip guideline; thử cả class nuScenes và spec-vn. |
| TC-14-003 | Cùng input/config: CLI/Web/API xuất cùng findings, severity, coverage và gate; giải thích khác biệt do learned model nếu CLI chưa dùng nó. |
| TC-14-004 | Learn GET/POST, quyền truy cập, slug/run_id, XSS từ dữ liệu/model, đường dẫn model/cache; rà riêng bề mặt mới qua chuẩn bảo mật đã review 06. |
| TC-14-005 | New findings qua preview/report/history/review: sửa verdict, đổi project/job khi request pending, giữ đúng finding và model scope. |
| TC-14-006 | Extension MV3 thật: luật mới, next/prev, frame, track/box không tồn tại và finding chỉ có vị trí; reload tab, service worker restart, server URL/token đổi. |
| TC-14-007 | CVAT ghi cờ/sửa rồi quét lại trên task thử: giữ shape/attrs/ID, phát hiện concurrent Save; race GET cuối → PATCH vẫn phải nêu giới hạn. |
| TC-14-008 | Gate khi thiếu model/ảnh/pose/points hoặc learning hạ severity: không ghi đạt chất lượng đầy đủ khi bỏ luật có yêu cầu hoặc thiếu evidence. |

Test đầu: `python -m pytest -q tests/test_config.py tests/test_numeric_config_recheck.py tests/test_web.py tests/test_web_a14.py tests/test_scan_gate.py tests/test_gate_coverage.py tests/test_queue_cvat_scope.py tests/test_report_api.py tests/test_security_review.py tests/test_data_review_regressions.py`.
Extension: từ `extension/`, chạy `node --test tests/*.test.js`; ngoài suite cần thao tác Chrome + CVAT thật.

## 10. Phần 15 — đánh giá chất lượng, precision tay, hiệu năng

Đọc: `eval/evaluate.py`, `eval/metrics.py`, `eval/split.py`, `cli/eval_cmd.py`, `scripts/run_eval_suite.py`, `scripts/eval_heading_points.py`, `scripts/eval_camera.py`, tài liệu số liệu.

| Mã | Kiểm tra và tiêu chí |
| --- | --- |
| TC-15-001 | Truy vết mỗi claim mới tới SHA/data/config/checkpoint/split/seed/rounds; 2,98/0,59 của tài liệu cũ không đại diện mặc nhiên main d18b1a9. |
| TC-15-002 | Recall theo từng lỗi/lớp/scene; FN do không có evidence ghi riêng; luật mới chưa có injection/GT không được gán recall từ catalog core/c1. |
| TC-15-003 | Đơn vị metrics, severity, mẫu số, match finding ↔ injection, trùng frame/track; giữ sửa size ratio và metadata từ recheck07. |
| TC-15-004 | Precision tay: tối thiểu 20 findings mỗi luật mới có dữ liệu, gồm nhóm khó, và ≥40 kết luận độc lập trên Web; ghi phương pháp lấy mẫu, số đúng/FP/không đủ chứng cứ. Nếu ít hơn ghi toàn bộ mẫu và giới hạn, không bịa kết luận. |
| TC-15-005 | Chạy eval tuning và test tách biệt, 10 vòng, seed cố định; tuning dùng chỉnh ngưỡng rồi khóa trước held-out. Báo cả mẫu nhỏ và CI/khoảng bất định khi phù hợp. |
| TC-15-006 | A/B hình học/ngưỡng 12°/ensemble/camera/missing: dùng cùng nguồn và config chỉ đổi yếu tố cần so; đo recall và báo nhầm cùng nhau. |
| TC-15-007 | Benchmark OtherBoxPoints: cùng tập findings và tập điểm, median/p95, RAM, frame/box count; không suy tốc độ toàn app từ một helper. |
| TC-15-008 | Camera/Critic CPU/GPU, cache lạnh/nóng, scan dài/lặp, RAM/VRAM/OOM; đối chiếu ngưỡng chất lượng G7 ≤2 cảnh báo và ≤0,5 lỗi /100 box, chưa đạt ghi chưa đạt. |

Test đầu: `python -m pytest -q tests/test_evaluation_review.py tests/test_evaluation_recheck.py tests/test_critic.py tests/test_camera.py tests/test_missing.py`.

Sau khi đã xác minh dataset/runtime, từ tool root (đặt biến `NUSCENES_ROOT` tới mini thật):

```powershell
python -m pointsnap eval --scenes tuning --rounds 10 --seed 0 --errors all --out out/review-15-tuning-20261013
python -m pointsnap eval --scenes test --rounds 10 --seed 0 --errors all --out out/review-15-test-20261013
```

Chọn tên output mới nếu đã tồn tại. Catalog `all` hiện là core + c1; phải bổ sung phương pháp riêng cho C5–C8 trước khi báo số liệu của chúng.

## 11. Phần 16 — tài liệu, đóng gói vision, tổng hợp và nghiệm thu

Đọc: `pyproject.toml`, README/cài đặt/Docker, `docs/bao-cao-du-an.md`, `docs/huong-dan/`, hình minh họa và script tạo hình, `quan-ly/ban-giao-12-10.md`, `TASKS.md`, giao việc và các báo cáo 09–15.

| Mã | Kiểm tra và tiêu chí |
| --- | --- |
| TC-16-001 | Inventory 131 file đều có phần phụ trách và evidence/kết luận; đối chiếu lại nếu HEAD thay đổi. Xóa/rename có lý do và link mới hoạt động. |
| TC-16-002 | README repo/source-tool/sản phẩm dẫn đúng entrypoint, cài đặt và lệnh; không đọc hướng dẫn ở đường dẫn đã chuyển. |
| TC-16-003 | Cài base không vision; cài vision trên CPU/GPU trong môi trường tách: dependency/model tải và cách fallback đủ rõ, không sửa môi trường người dùng để thử. |
| TC-16-004 | Wheel/sdist/container có module/config/static mới; smoke ngoài checkout với learn/camera/missing; ghi OS/Python/model combo thực sự kiểm. |
| TC-16-005 | Báo cáo/hình minh họa tái lập từ data và script tương ứng; thông số/ngưỡng/spec/số liệu thống nhất với code và báo cáo15. |
| TC-16-006 | Tài liệu C4 ghi rõ XFAIL còn lại; precision tay, coverage camera/missing và ngưỡng P-009 có trạng thái thật. Không đồng nhất hoàn tất code với nghiệm thu. |
| TC-16-007 | Sổ findings hợp nhất 01–16: còn mở, đã sửa/chờ kiểm, đã xác minh, giới hạn được chấp nhận; owner và điều kiện sử dụng cụ thể. |
| TC-16-008 | Gate cuối trên SHA hợp nhất: full Python/Node, model thật/dataset/CVAT/browser theo phạm vi; báo PASS/FAIL/SKIP/XFAIL riêng, kết luận demo/local và nghiệm thu rộng riêng. |

Test đầu: `python -m pytest -q tests/test_deployment_review.py`; gate cuối `python -m pytest -q` và Node suite sau các thay đổi cuối cùng.

## 12. Tiêu chí kết thúc đợt

**Review hoàn tất** khi 64 ca có trạng thái, inventory có kết luận, findings có bằng chứng/owner và các phần bị chặn được bàn giao cụ thể. **Nghiệm thu** cần chứng cứ cho các tính năng thực dùng: model thật, dữ liệu thật, precision tay, MV3/CVAT và vận hành tương ứng; các mục chưa đạt G7 hoặc XFAIL không được chuyển thành PASS chỉ vì suite xanh.

Ưu tiên mở lượt thực hiện bằng **phần 09**, bắt đầu giới hạn C4 của PR #52 và tương tác với sửa ground/floating/heading/fit/track từ PR #54. Đây là vùng có khả năng ảnh hưởng trực tiếp tới kết luận chất lượng nhãn và có ca tái hiện cụ thể.

## 13. Bằng chứng lập kế hoạch

Đã chạy: `git status --short`, `git fetch origin main`, `git rev-parse main origin/main`, lịch sử first-parent, diff name-status/stat `5dcc97f..be1778c`, diff PR #54 trên file nguồn, đọc báo cáo review cũ/bàn giao và điểm nối scanner/config/learn/camera/Web/tests.

**Chưa chạy suite hoặc nghiệm thu lại trong lượt lập kế hoạch này.** Các con số test trong báo cáo 01–08 giữ là evidence lịch sử. Bộ kế hoạch mới không sửa nội dung Excel lỗi cũ; sau review 09–16 cần bổ sung findings mới vào workbook kiểm lại riêng hoặc phiên bản mới.
