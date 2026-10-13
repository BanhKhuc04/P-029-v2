# Kiểm tra repo và toàn bộ test tự động — 13/10/2026

## Mốc mã nguồn và model

- Repo: `AI20K-Build-Phase-Cohort-4A/P-029`, checkout thực ở `D:/Vin_uni/P-029/P-029`.
- `git fetch origin --prune` và `git pull --ff-only origin main` thành công. `main` đã mới nhất tại thời điểm bắt đầu: **`d18b1a9`**.
- Nhánh kết quả local: **`codex/review-tests-2026-10-13`**. Không merge nhánh review 09–10 chưa được nhập vào main.
- Model thực hiện review: **`gpt-6.1-sol`**, đã xác minh từ `turn_context.model` trong metadata của chính chat này; không suy từ model mặc định của app.
- Windows Python **3.11.9**, pytest **9.1.1**, Node **24.19.0**, PyTorch **2.6.0+cu124**, torchvision **0.21.0+cu124**, transformers **5.19.0**. Docker Engine **29.8.2**, CVAT thật **2.77.0**.
- Mã production trong `pointsnap/` được giữ nguyên để review đúng main. Thư mục `landing/` chưa tracked được giữ nguyên.

## Kết quả kiểm thử

| Lớp kiểm tra | Kết quả | Giới hạn |
|---|---|---|
| Python Windows: core/detectors, adapters, CLI, backend, report, evaluation, security và runner | **617 ca khác nhau PASS, 3 FAIL, 1 XFAIL** | Có 618 lượt PASS vì test ground thật chạy lại ở pha dataset; không cộng thành 618 ca khác nhau |
| Python Linux Docker, source sạch của HEAD | **604 PASS, 9 SKIP, 1 XFAIL, 0 FAIL** | Không có torch, dataset hoặc cấu hình CVAT live; không chạy 7 test mới chưa commit trong archive HEAD |
| Logic extension/frontend trên Node | **37 PASS, 0 FAIL** | Không phải chạy extension MV3 đã cài trên Chrome/CVAT |
| Cú pháp và manifest | Python/JS/PowerShell/manifest PASS | Lượt chính kiểm 130 file Python, 12 JS, 5 PowerShell; helper bổ sung cũng được kiểm cú pháp |
| nuScenes v1.0-mini thật | **4/4 PASS** | Reader, số cảnh/frame, tọa độ/đếm điểm và ground; 13 bảng metadata được hash |
| CVAT thật: upload/read, flag/clear, shape/tilt | **3/3 PASS** | Chỉ task thử riêng, không sửa job sẵn có |
| Report API code hiện tại với CVAT thật | **7/7 PASS** | Instance API riêng, task thử riêng; GET JSON/HTML/CSV giữ nguyên toàn bộ annotations; cleanup xác minh HTTP 404 |
| Wheel/sdist và cài mới | PASS | Build từ `git archive HEAD`, không đưa `.env`, dataset hay file local vào package; venv riêng và pip check đạt |
| Smoke HTTP của wheel đã cài | **7 routes HTTP 200** | Chạy ngoài source; config/guideline/static/font/CLI cũng được kiểm |
| Docker build/CLI/dependency | PASS | Image riêng `pointsnap-review:20261013-142720-451364`; container test tự xóa |
| Trình duyệt | Splash, 5 màn chính, validation quét trống và console đã kiểm | Có lỗi màn kết quả rỗng bên dưới; viewport 522×672 không tràn ngang; chưa có luồng UI đầy đủ với dữ liệu và MV3 |
| Landing local chưa tracked | JS syntax và 6 tham chiếu asset PASS | Chưa kiểm animation/WebGL hoặc bản deploy ngoài máy |
| Đối chiếu riêng nhánh review 10 `8fce666` | **2/3 regression mới PASS, 1 FAIL** | Archive tạm, không merge: track 0 và rider pose đã sửa; Critic overflow vẫn còn |
| Đánh giá 10 cảnh × 10 vòng, seed 0 | **Hoàn tất; 347/776 lỗi chèn được bắt** | 14.104 box GT; không gọi đây là precision hoặc recall đã chấm tay |
| Quality proxy trên 5 cảnh held-out, cùng config | **FAIL: 2,960 warning / 0,588 error trên 100 box** | Mục tiêu ≤2,0 / ≤0,5; finding trên GT chưa được xác nhận false positive bởi reviewer |

Các con số PASS của Python/Node là test phần mềm, không phải tỷ lệ tìm đúng lỗi nhãn. Không có verdict precision thủ công trong lượt này.

## Chất lượng và thời gian quét

Chạy đủ 10 cảnh × 10 vòng chèn, seed 0, catalog `all`: **776 lỗi chèn, 347 được bắt (44,72%)**, 429 chưa được bắt theo matching hiện tại. Đây là tỷ lệ bắt trên toàn bộ catalog chèn, gồm cả lỗi ngoài phạm vi của một số luật; xem `recall` trong summary để tách applicability và ground evidence. Không suy thành recall trên lỗi tự nhiên hoặc chất lượng model ảnh.

| Tập | Box GT visible | Finding warning/error | Warning/error trên 100 box | So ngưỡng 2,0/0,5 |
|---|---|---|---|---|
| Gộp 10 cảnh tuning + test | 14.104 | 274 / 57 | 1,943 / 0,404 | Số gộp thấp hơn ngưỡng, chưa chứng nhận held-out |
| 5 cảnh held-out riêng | 5.440 | 161 / 32 | **2,960 / 0,588** | **Vượt cả hai ngưỡng** |

Held-out được quét sạch riêng sau eval; config hash **khớp** config eval, không sửa ngưỡng sau khi xem kết quả. Hash 13 bảng metadata nuScenes và checkpoint model nằm trong evidence. Cả hai tỷ lệ chỉ là proxy trên GT; không gán verdict Báo nhầm vào ứng dụng.

Phân mức lỗi lớn trong subset applicable có ground evidence: **56/59 ở mức Error (94,92%)**; không gọi 56/59 là recall trên toàn bộ 776 lỗi. Matching precision của evaluator là finding-level đối với lỗi chèn; TP theo lỗi và số finding khớp là hai mẫu số khác nhau, chưa thay thế precision thủ công.

10 lượt quét GT trong eval mất **12,29–42,13 giây/cảnh**; toàn evaluation gồm 100 lượt chèn mất **2.462,30 giây (~41 phút)**. Các lượt clean held-out chạy serial sau đó mất **10,52–30,88 giây/cảnh**, có OS/model cache ấm. Trong các phép đo này clean scan dưới 120 giây/cảnh; chưa phải benchmark cấu hình máy tối thiểu hoặc tải đồng thời.

## Model của ứng dụng đã kiểm

| Model | Bằng chứng chạy | Điều chưa chứng minh |
|---|---|---|
| Mask R-CNN ResNet-50 FPN v2, COCO_V1 | CUDA, inference mới trên 3 ảnh CAM_FRONT; 41/43/38 detections; tensor hữu hạn và cache roundtrip PASS | Precision/recall trên các ảnh chưa được chấm tay |
| Grounding DINO `IDEA-Research/grounding-dino-base` + SAM `facebook/sam2.1-hiera-small` | Inference mới trên cùng 3 ảnh, cache roundtrip PASS; chỉ dùng checkpoint local, Hugging Face offline | Chưa đo precision/recall hoặc chất lượng mask của cả dataset |
| Hybrid | Inference mới của hai nhánh model trên 3 ảnh, cache roundtrip PASS | Smoke contract không chứng nhận chất lượng tổng hợp |
| Box Critic TorchScript | Hai fixture model hiện có PASS; fixture logit cực âm mới tái hiện crash | Config mặc định có `critic.model` rỗng; không có checkpoint Critic triển khai được đánh giá chất lượng trong lượt này |

## Findings còn mở trên main

### RV-13-001 — P2: logit âm lớn làm Box Critic dừng toàn bộ lượt quét

- Vị trí: [`pointsnap/critic.py:201`](../../source-tool/pointsnap-3d/pointsnap/critic.py), nhánh gọi probability ở dòng 182.
- Điều kiện: bật Critic và model trả một logit hữu hạn như `-1000` cho box đơn/track ngắn. Đây là dự đoán rất chắc rằng box khỏe.
- Thực tế: `math.exp(-x)` tính `exp(1000)`, gây `OverflowError: math range error`; không trả về danh sách finding.
- Kỳ vọng: sigmoid ổn định số, xác suất gần 0 và không có finding.
- Tái hiện: `auto-tests/test_review_contracts.py::test_negative_extreme_model_logit_is_healthy_instead_of_crashing`. Test sử dụng TorchScript thực và điểm tổng hợp; **FAIL**.
- Hướng sửa: sigmoid chia nhánh theo dấu, kiểm logit/delta hữu hạn. Lỗi này vẫn hiện diện trong `critic.py` của nhánh review 10.

### RV-13-002 — P2: track ID 0 bị tách thành nhiều finding

- Vị trí: [`pointsnap/detectors/attributes.py`](../../source-tool/pointsnap-3d/pointsnap/detectors/attributes.py), khóa `track_id or id(box)` trong `detect_spec_geometry`.
- Điều kiện: track người ID `0` ở trong cùng track xe trong ba frame.
- Thực tế: `0` bị coi là false, dùng ID object khác nhau cho từng frame; trả **3 finding** thay vì 1 finding chứa `[0,1,2]`.
- Tác động: tăng cảnh báo, ảnh hưởng gate và hàng đợi duyệt.
- Tái hiện: `test_track_zero_inside_vehicle_is_one_track_finding`; **FAIL**.
- Hướng sửa: phân biệt `None` với số 0. Nhánh `origin/codex/review-10-spec-scenarios`, code `c5ac54d`, đã có sửa tương ứng, chưa merge vào main.
- Xác minh bản sửa: cùng regression này **PASS** trên archive nguồn đầu nhánh `8fce666`.

### RV-13-003 — P2: trạng thái người lái suy tốc độ khi không có world pose

- Vị trí: [`pointsnap/detectors/attributes.py`](../../source-tool/pointsnap-3d/pointsnap/detectors/attributes.py), fallback tọa độ sensor trong `detect_rider_state`.
- Điều kiện: không có `sensor_to_world`; tọa độ tương đối của xe hai bánh thay đổi do xe thu LiDAR chuyển động.
- Thực tế: suy tốc độ 8 m/s và báo `attr.rider_state` dù chưa có bằng chứng chuyển động tuyệt đối.
- Tác động: báo nhầm và kết luận gate không phản ánh đủ coverage của luật này.
- Tái hiện: `test_rider_motion_without_world_pose_has_insufficient_evidence`; **FAIL**.
- Hướng sửa: yêu cầu pose phù hợp và dùng timestamp thật khi đầy đủ; báo thiếu coverage nếu thiếu. Review 10 đã có sửa, chưa merge vào main.
- Xác minh bản sửa: cùng regression này **PASS** trên archive nguồn đầu nhánh `8fce666`.

### RV-13-004 — P2: màn chưa quét hiển thị kết luận gate thất bại

- Vị trí: [`web/static/index.html:161`](../../source-tool/pointsnap-3d/pointsnap/web/static/index.html), `results-content-box` khởi tạo `display:flex`; [`app.js:688`](../../source-tool/pointsnap-3d/pointsnap/web/static/app.js), `loadLatestRun` thoát khi chưa có dự án.
- Tái hiện bằng trình duyệt: HOME mới rỗng → Bắt đầu → Kết quả.
- Thực tế: vừa ghi “Chưa có lượt quét nào” vừa hiện dải đỏ “Không đạt cổng kiểm soát / Đang tính toán tiêu chí…”, thống kê 0 và panel finding mẫu.
- Kỳ vọng: chỉ hiện trạng thái chưa quét; gate xuất hiện khi có kết quả thật.
- Bằng chứng: [ảnh màn rỗng](../../source-tool/pointsnap-3d/out/all-tests/20261013-142720-451364/browser-empty-results.png). Không có lỗi console trong lượt kiểm.
- Hướng sửa: ẩn nội dung kết quả ban đầu hoặc gọi `showEmptyResults()` trước nhánh thoát không có dự án; thêm regression browser cho HOME mới.

### Lỗi đã biết còn XFAIL

`tests/test_ground_slope.py::test_track_from_flat_onto_slope_floating_frame_flagged`: track chuyển từ đường bằng lên dốc 8°, một frame lơ lửng 25 cm bị bỏ sót. Cả Windows/Linux vẫn **XFAIL**, không phải PASS. Nhánh review 09–10 đã có sửa geometry tương ứng; lượt này không merge nhánh đó.

## Vận hành và phần chưa xác minh

- Docker Desktop được bật để thực hiện test. CVAT hiện chạy từ các image `v2.77.0`; các container dịch vụ sẵn có được giữ nguyên. Test dùng image/tag riêng và các task riêng; server Web/browser/API tạm đã được dọn.
- Trên địa chỉ đang dùng, `http://localhost:8080/pointsnap/health` trả **HTTP 200 nhưng `text/html` của CVAT SPA**, chưa phải health JSON của PointSnap. Vì vậy chưa chứng nhận API đã được triển khai sau proxy này; API code hiện tại đã được kiểm trên instance riêng với CVAT thật.
- Chưa nghiệm thu extension MV3 cài thật, race GET→PATCH giữa nhiều người sửa, LAN/HTTPS/máy tối thiểu, precision thủ công và thời gian tiết kiệm cho reviewer.
- CI Python 3.10/3.12 và Node 22 chưa được chạy mới trên GitHub trong lượt này. Local chạy Windows 3.11/Node 24 và Docker Linux 3.11.
- Workflow được bổ sung target `auto-tests` bên cạnh `tests`, để regression mới được CI thu thập. Đây là nhánh review có failures thật; chưa đủ điều kiện merge xanh khi production main chưa sửa.

## Cách chạy lại và bằng chứng

```powershell
cd D:\Vin_uni\P-029\P-029\source-tool\pointsnap-3d
.\auto-tests\Run-AllTests.ps1 -Dataset D:\Vin_uni\data\nuscenes -LiveCvat -Docker -ModelSmoke -Evaluate -Rounds 10 -ReviewModel gpt-6.1-sol
```

- Runner và các smoke/regression mới: [auto-tests/README.md](../../source-tool/pointsnap-3d/auto-tests/README.md).
- [Report từng pha](../../source-tool/pointsnap-3d/out/all-tests/20261013-142720-451364/report.md), [results JSON](../../source-tool/pointsnap-3d/out/all-tests/20261013-142720-451364/results.json).
- JUnit: `python.xml`, `dataset.xml`, `live-cvat.xml`, `linux/linux.xml`; Node JUnit trong `extension.log`.
- [CVAT/API và cleanup](../../source-tool/pointsnap-3d/out/all-tests/20261013-142720-451364/services-final/services.json).
- [Đối chiếu ba regression trên review 10](../../source-tool/pointsnap-3d/out/all-tests/20261013-142720-451364/review10-contracts.log), JUnit `review10-contracts.xml`.
- Model: `model/model.json`, `model-gdino-sam2/model.json`, `model-hybrid/model.json` trong thư mục run trên.
- [Kết quả eval đầy đủ](../../source-tool/pointsnap-3d/out/all-tests/20261013-142720-451364/evaluation/ket-qua.md), [proxy held-out](../../source-tool/pointsnap-3d/out/all-tests/20261013-142720-451364/heldout-quality.json).
- [Bằng chứng tổng hợp đã lọc dữ liệu](evidence/whole-repo/verification.json) được lưu cùng báo cáo.
- Log/artifact/dataset thử nằm trong `out/` được Git ignore; không đưa token hoặc point cloud vào báo cáo/commit.

## Kết luận

**Đã hoàn tất lượt kiểm thử/review trong phạm vi báo cáo, chưa toàn bộ đạt.** Main có 3 regression mới thất bại, 1 XFAIL đã biết, lỗi UI xác minh bằng trình duyệt và quality proxy held-out vượt mục tiêu. Model review **`gpt-6.1-sol`**; cả ba chế độ model ảnh đã qua smoke inference, chưa được nghiệm thu precision thủ công. Nhánh review chứa tập lệnh/CI/báo cáo; mã production vẫn ở mốc main đã kiểm.

## Trạng thái sửa sau review (13/10/2026)

Số liệu phía trên giữ nguyên mốc `d18b1a9`. Các finding đã được xử lý như sau:

| Mã | Sửa | Kiểm lại |
|---|---|---|
| RV-13-001 | `stable_sigmoid` trong `core/geometry.py`, dùng cho `critic.py` và `learn.py` (cùng mẫu tràn số); Critic bỏ box có logit/gợi ý sửa không hữu hạn | Contract test Critic PASS; thêm `test_model_confidence_saturates_without_overflow` |
| RV-13-002 | Nhập review 10 (`c5ac54d`) qua PR #55 | Contract test track 0 PASS |
| RV-13-003 | Nhập review 10 (`c5ac54d`) qua PR #55 | Contract test rider pose PASS |
| RV-13-004 | `results-content-box` khởi tạo ẩn; `loadLatestRun` gọi `showEmptyResults()` khi chưa có dự án | Node regression mới PASS; trình duyệt với HOME rỗng: chỉ hiện trạng thái trống, không có dải gate, không lỗi console |
| XFAIL C4 | Nhập review 09 (`f22f2b6`) qua PR #55 | `test_track_from_flat_onto_slope_floating_frame_flagged` PASS |

Windows Python 3.11.9: `pytest tests auto-tests` **678 PASS, 3 SKIP, 0 FAIL, 0 XFAIL**; Node **38 PASS**.

Còn mở: quality proxy held-out (2,960 / 0,588 trên 100 box) không đổi sau review 09/10, cần đo lại và chấm tay precision trước khi chỉnh ngưỡng; chưa kiểm lại luồng màn Kết quả có dữ liệu thật trên trình duyệt trong lượt sửa này.
