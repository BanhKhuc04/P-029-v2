# Báo cáo review 12 — camera, model ảnh và cache

Ngày **13/10/2026**, Asia/Saigon. Nhánh `codex/review-12-camera-models`.

## Kết quả

- Nhận phần 09–11 bằng fast-forward tới `5920522`; commit sửa **`b0cbba8`**.
- Sửa **11 nhóm lỗi**, thêm **58 ca hồi quy**. Gate cuối: **771 Python PASS, 0 FAIL/ERROR/XFAIL, 3 live-CVAT SKIP; 37 Node PASS**.
- Coverage 8 module đã sửa: **1.051/1.250 = 84,08%**; package `pointsnap`: **6.717/7.250 = 92,65%**. Statement coverage; riêng `eval_camera.py` 25,21%, chưa kiểm end-to-end với pretrained model.
- 6 camera thật của nuScenes mini, `scene-0061/frame 0`: oracle raw quaternion/ego/calibration độc lập khớp phép chiếu. Sai lệch pixel lớn nhất ở depth hợp lệ **6,905×10⁻⁹ px**, depth **4,122×10⁻¹³ m**.
- Operator Torchvision CPU và processor SAM2 chạy trên ảnh thật; cold/hot cache giữ nguyên kết quả. **Operator smoke dùng random weights, SAM2 dùng synthetic logits; không phải nghiệm thu pretrained.**
- **TC-12-008 bị chặn:** tải weights chính thức timeout/reset/DNS failure; người dùng xác nhận chưa có SAM. Không có pretrained checkpoint hợp lệ để đo inference/precision. GPU, pretrained quality và human precision chưa nghiệm thu.

## Checklist

| Ca | Trạng thái | Kết quả |
| --- | --- | --- |
| TC-12-001 | Đạt toán và visual QA một mẫu thật | Intrinsic/pose/dimensions sai bị từ chối; test box sau camera/ngoài ảnh vẫn đạt. 69 world centers × 6 camera, 213 phép chiếu depth ≥0,5 m; oracle từ metadata không dùng helper pose của core. Đã xem hình chẩn đoán 6 hướng; chưa có human verdict. |
| TC-12-002 | Đạt logic bằng fixture; pretrained chưa kiểm | Detector không thấy không tạo mismatch. Chỉ manual visible keyframes; mỗi camera tối bị loại ngay cả khi các view khác sáng. Reference riêng từng camera/class/track; class vote theo frame độc lập và một nhóm thay thế ổn định. Occlusion tính union diện tích đúng. |
| TC-12-003 | Đạt mapping/capability; một phần | Token boundary tránh `scarf`/`carpet` thành car; normalize hoa/thường/khoảng trắng. Mask R-CNN không đối chiếu cone/barrier; rider pair giữ ngoại lệ. Hybrid chỉ thêm nhóm ngoài COCO; mất DINO/SAM thì capability giảm và báo partial. Chưa kiểm semantic outputs pretrained. |
| TC-12-004 | Đạt wiring/mock | Cả 3 mode đi qua check_camera, sparse và missing bằng effective model. Sparse cập nhật capability sau fallback, bỏ interpolation và không trộn class cùng ID. Camera failure giữ kết quả LiDAR moving bằng chạy lại nhánh LiDAR không camera. |
| TC-12-005 | Đạt CPU contract/recovery; GPU chưa kiểm | PyTorch 2.8 CPU + torchvision 0.23 + Transformers 5.0. Lỗi native import, weights/image/cache/factory hoặc tensor invalid tạo INFO `camera.no_evidence`, chặn gate. Hybrid có COCO vẫn giữ COCO và ghi partial. SAM2 processor thật yêu cầu fast; DINO/SAM pin revision/safetensors. Chưa có CUDA/OOM thực tế. |
| TC-12-006 | Đạt cache và fault injection | Key chứa image hash/mtime_ns, model revision, prompt mapping, processor backend, library versions và mask schema. Cold/hot cả 3 mode kiểm bằng stub; operator Mask R-CNN CPU thật kiểm cache bằng random weights. Cache hỏng/NaN tính lại; file cũ nguyên vẹn khi ghi thất bại. |
| TC-12-007 | Đạt oracle/toán | 29% occlusion không bị lưới thành 31,25%; union không đếm trùng, zero-area không che. Mask giữ partial block mép ảnh và dùng tâm cell theo kích thước ảnh gốc. Sparse window dùng đường chéo box xoay để không bỏ điểm góc. |
| TC-12-008 | **Bị chặn — pretrained weights** | Đã cài runtime, thử tải Mask R-CNN COCO và DINO/SAM từ nguồn chính thức. Chưa có file weights hoàn chỉnh, chưa xác minh hash checkpoint hoặc inference pretrained. Operator/processor smoke và mock không thay thế ca này. |

## Findings đã sửa

| Mã | Mức | Trước sửa | Sửa và bằng chứng |
| --- | --- | --- | --- |
| RV-12-001 | P1 | Camera reader nối filename trực tiếp, bỏ qua containment của dataroot. Calibration/intrinsic/dimensions không được kiểm. | Reuse `_dataset_path`, validate CameraView và sensor pose. Traversal, NaN, shape sai, scale pose và size ≤0 bị từ chối. |
| RV-12-002 | P2 | Lưới 16×16 báo che 31,25% khi thực tế 29%; rectangle zero-width vẫn che một cột. | Exact union rectangles trong target; oracle ngưỡng/overlap/zero-area đạt. |
| RV-12-003 | P2 | Mismatch trộn front/side với bias ổn định thành lỗi; duplicate view làm đủ reference giả; class/interpolation trộn track. | Reference cùng channel, một số đo mỗi manual frame; tách ID/label. Stable side 80% và front 10% không còn false rise. |
| RV-12-004 | P2 | 3 view của một frame đủ class_min_observations; person+animal cộng phiếu thành một kết luận person dù person không đa số. | Một phiếu nhất quán mỗi frame, đủ frame độc lập, một nhóm thắng đạt class_vote. |
| RV-12-005 | P2 | Sparse coi cone không được COCO hỗ trợ là camera không thấy; điểm góc box xoay bị broad phase bỏ; interpolation dense che manual sparse. | Filter effective supported_groups, cập nhật sau hybrid fallback; diagonal window; manual keyframes và class cohort. |
| RV-12-006 | P2 | Cache key dùng mtime làm tròn giây, không có content hash/version backend; prompt mapping hoặc thuật toán mask đổi vẫn dùng cache cũ. | Versioned cache, SHA-256 ảnh, mtime_ns, pin model revisions, processor modes, prompt mapping, library versions và mask scale. Cache cũ được vô hiệu hóa bằng key mới. |
| RV-12-007 | P2 | Tensor/cache arrays không kiểm alignment/finite; cache hỏng crash scan hoặc NaN lọt vào kết quả. | Validate Detections; đóng NPZ, allow_pickle=False; kiểm packed masks; recompute cache invalid; invalid inference thành partial. |
| RV-12-008 | P1 | NPZ ghi trực tiếp có thể làm hỏng file cũ; Windows atomic replace thỉnh thoảng WinError 5, lỗi storage cũ tái hiện trong gate và kiểm riêng. | Temp file + atomic replace; helper chung thử tối đa 4 lần cho WinError 5/32/33, tổng delay 170 ms. Persistent failure vẫn báo và giữ file cũ. Không xác định tác nhân khóa file là antivirus hay process khác. |
| RV-12-009 | P2 | Import native hỏng không được coi là unavailable; hybrid không giữ COCO nếu extra weights lỗi; image/mask partial blocks bị cắt. | Catch optional runtime lỗi, sticky COCO fallback có capability thực; pin safetensors/revisions; processor backend chọn rõ; ceil mask shrink và original image size. |
| RV-12-010 | P1 | Explicit camera thiếu runtime/ảnh/pose vẫn có thể gate ĐẠT; lỗi weights hoặc cache factory làm crash scan và mất kết quả LiDAR. | Coverage gap và `camera.no_evidence`; INFO không gắn cờ box nhưng chặn gate. Catch tại factory/inference; giữ LiDAR khi phần camera không dùng được. |
| RV-12-011 | P2 | Eval script so reference trộn camera/class, khác semantics sau sửa; typo scene tự đi vào test set. | Reuse same-camera reference, class cohort, effective capabilities động; parser choices tuning/test. Chưa chạy eval đầy đủ pretrained. |

Trên snapshot package `5920522` đã assert đường dẫn: **50/56 ca được chọn FAIL, 6 PASS**. Hai ca fixture dùng helper/script mới bị loại; eval channel đã tái hiện riêng trước sửa. Tất cả 58 ca mới có trong gate cuối. Lỗi SAM2 slow và Transformers lazy-import fixture xuất hiện trong quá trình kiểm bản sửa, được sửa trước commit; không quy chúng thành lỗi nguyên bản.

## Dữ liệu thật và runtime

6 ảnh 1600×900 từ một frame tuning được đọc và đối chiếu. Camera và LiDAR lệch thời điểm **0,528–43,107 ms**; oracle dùng ego pose riêng của từng ảnh. Hình `source-tool/pointsnap-3d/out/review12-calibration.png` có 56 projected box/view, đã kiểm bằng mắt trong phiên làm việc. Đây là visual QA, không phải precision label người duyệt.

Oracle ban đầu so cả các world center gần/sau mặt phẳng camera; phép chia depth gần 0 khuếch đại sai số float. Depth error vẫn <4,122×10⁻¹³ m. Probe cuối so pixel tại depth ≥0,5 m và giữ unfiltered error để minh bạch; không thay mã phép chiếu theo lỗi probe này.

Runtime smoke dùng Mask R-CNN network thật khởi tạo ngẫu nhiên seed 12, input resize tối đa 64 px, 5 proposals trên ảnh mini. Output `(5,4)` và 5 masks `(225,400)`; cold **0,830 s**, warm **0,00882 s**, arrays/names/masks bằng nhau. Đây không phải benchmark pretrained. SAM2 processor tại revision pin xử lý ảnh thật và postprocess synthetic logits về `(1,1,900,1600)`; chưa có SAM2 forward với pretrained weights.

## Evidence

| Mã | Artifact |
| --- | --- |
| EV-12-001 | [verification.json](evidence/12/verification.json): code SHA, source hash, XML, PASS/SKIP và coverage. |
| EV-12-002 | [regression-summary.json](evidence/12/regression-summary.json): counterexamples baseline và intermediate failures. |
| EV-12-003 | [calibration-summary.json](evidence/12/calibration-summary.json), [calibration_probe.py](evidence/12/calibration_probe.py): 6-camera oracle, image hashes, time offsets và visual artifact hash. |
| EV-12-004 | [runtime-summary.json](evidence/12/runtime-summary.json), [runtime_probe.py](evidence/12/runtime_probe.py): operator/processor contract, nêu rõ random/synthetic. |
| EV-12-005 | [runtime-recovery.md](evidence/12/runtime-recovery.md), [model-resources.json](evidence/12/model-resources.json): attempts tải weights, revision và ca bị chặn. |

Ảnh chẩn đoán, cache, runtime, XML và output lớn chỉ ở `out/` bị ignore; không commit raw ảnh, data hoặc weights.

## Inventory và dependency

| File owner 12 | Kết luận |
| --- | --- |
| `core/camera.py` | Sửa validation/occlusion; oracle và visual QA mẫu thật đạt. |
| `detectors/camera.py` | Sửa reference/vote/sparse/mask edge; logic có regression. Pretrained precision chưa kiểm. |
| `vision/__init__.py` | Đã đọc; namespace docstring, không cần sửa. |
| `vision/detector2d.py` | Sửa cache/runtime/provenance; CPU operator và processor smoke; pretrained/GPU chưa nghiệm thu. |
| `scripts/eval_camera.py` | Đã đọc và sửa cohort/reference/parser; coverage 25,21%, end-to-end pretrained bị chặn. |
| `tests/test_camera.py` | 17 ca cũ PASS; assertion cache cập nhật vì schema mới vô hiệu hóa cache legacy. |

File dùng chung đã sửa: `adapters/nuscenes/reader.py`, `core/scanner.py`, `core/gate.py`, `web/storage.py`; hướng dẫn training owner 16 được cập nhật. `core/config.py` và `detectors/missing.py` đã đọc caller/capability; không sửa.

## Giới hạn và bàn giao

1. Pretrained inference cho 3 mode, semantic precision, model-assisted missing/class và GPU/OOM còn mở. Không có human verdict hoặc checkpoint mới được nghiệm thu. Thư viện import được không chứng nhận weights sẵn sàng.
2. Chỉ kiểm ảnh/calibration thật một frame của một scene tuning; không đo camera GT cả mini hoặc held-out, không chỉnh ngưỡng từ held-out. Box core chỉ yaw, không mô tả đầy đủ roll/pitch của nuScenes; cần lưu ý khi đo projection fidelity của cuboid nghiêng.
3. Same-camera reference giảm độ phủ ở camera chuyển góc nhìn/track ngắn; median vẫn bị đa số outlier hoặc lệch đều. Class vote bỏ frame có view mâu thuẫn, có thể giảm recall; cần đo với pretrained/human review.
4. Gate coverage ở cấp job không chứng nhận mọi box đủ pixels/points/reference, ảnh tối hoặc model không thấy không được thành bằng chứng box sai. `auto` trên CPU vẫn tắt camera theo cấu hình. Khi explicit true, lỗi runtime/ảnh/pose và fallback được báo partial.
5. Hybrid fallback sticky cho instance; sau bổ sung weights khởi động lại process. Cache cũ không dùng lại, có thể cần dung lượng cho cache mới. Chưa benchmark concurrency/process cache nhiều worker thật; atomic failure và storage thread regression đã kiểm.
6. Windows helper chỉ retry sharing/access denial có giới hạn; không sửa ACL hoặc che lỗi kéo dài. File cũ vẫn giữ khi hết retry.
7. Eval vẫn cho phép người dùng chạy nhiều cấu hình; phải tuân thủ chỉ tuning ngưỡng trên tuning. Phần 15 cần kiểm seed/split/metadata, zero-sample và grid ngưỡng trên held-out trước nghiệm thu số liệu.

Tiếp theo **13 — missing objects**, nhận nhánh 12. Camera-assisted cases của 13 tiếp tục phụ thuộc pretrained weights; LiDAR-only và các sửa scope 13 có thể làm độc lập.
