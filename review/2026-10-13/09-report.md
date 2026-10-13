# Báo cáo review 09 — hình học, ground, heading, fit, track

Ngày **13/10/2026**, Asia/Saigon. Nhánh `codex/review-09-geometry`.

## 1. Kết quả

**Hoàn tất review và sửa lỗi của phần 09; còn giới hạn và kiểm tay trước nghiệm thu.**

- Base: `3584000` (main `d18b1a9` cộng bộ kế hoạch).
- Commit mã nguồn đã kiểm: **`f22f2b6`**. Thêm **28 ca hồi quy**, chuyển ca C4 từ XFAIL thành PASS.
- Sửa **4 nhóm lỗi**, gồm 9 ca FAIL tái hiện trước sửa.
- Full suite: **631 PASS, 0 FAIL, 0 ERROR, 5 SKIP, 0 XFAIL**; **37 Node PASS**.
- Coverage dòng thực thi của 7 module hình học: **1.247/1.286 = 96,97%**; toàn package pointsnap **90,48%**. Đây là statement coverage, không phải branch coverage hoặc chứng nhận chất lượng thuật toán.
- NuScenes mini thật: **10 cảnh, 14.104 box**, gồm 8.664 box tuning và 5.440 box held-out. Không ghi CVAT.

Fingerprint mã nguồn được kiểm khớp file ở commit mã nguồn; xem [verification](evidence/09/verification.json). Các probe thực hiện trước commit khi HEAD còn `3584000`, nên dùng hash file để xác minh chính xác mã nguồn sau sửa; không dùng HEAD cũ làm phiên bản code sau sửa.

## 2. Checklist 8 ca

| Mã | Trạng thái | Thực hiện và bằng chứng |
| --- | --- | --- |
| TC-09-001 | Đạt kiểm tự động | Ground đường bằng/dốc dọc/ngang 0–10°, đá, curb, một phía theo suite C4; box xoay theo oracle độc lập. Tìm và sửa caller cắt mất góc vành đai. EV-09-002/003/004. |
| TC-09-002 | Đạt ca tái hiện | Track bằng → dốc 8°, box đúng không báo; frame 7 lún/nâng 25 cm được báo đúng. Ca nâng trước sửa FAIL, sau sửa PASS và bỏ XFAIL. Không kết luận mọi cấu hình C4 đã đạt. EV-09-002/003/004/005. |
| TC-09-003 | Đạt kiểm tự động | Cloud rỗng/1 điểm → floating.no_evidence, gate chặn; giữ kiểm finite/shape/pose của phần 02. Full suite bao gồm gate CLI/Web và reader nuScenes thật. EV-09-003. |
| TC-09-004 | Đạt tính đúng tập điểm | OtherBoxPoints so oracle lọc trực tiếp độc lập ở yaw 0°,45°,-60°, biên x ±3,5 m, box chồng; test hiện có trên 5.000 điểm/13 box. Caller ground/fit dùng bán kính đường chéo. Chưa benchmark tốc độ riêng: phần 15. EV-09-002/003. |
| TC-09-005 | Đạt kiểm tự động | Không có pose/pose một phần không báo motion; pose world/ego quay và ±π từ suite cũ; modulo 90°/reference không chứa outlier từ tests 02 và C1. Heading.points tách class theo ID. EV-09-002/003. |
| TC-09-006 | Đạt kiểm tự động | Nhảy 4 m ở đầu/cuối xa keyframe trên xe đứng yên được bắt; giữ track 3 box, xe chuyển động/ngoại suy xa, thiếu pose/timestamp/gap của suite cũ. Không coi heuristic 3 box là oracle nhận diện vật. EV-09-002/003/004. |
| TC-09-007 | Đạt theo phạm vi luật hiện tại | Reference loose/outside không trộn khác class dù cùng ID; một frame dư được bắt. Dư đều cả track vẫn im lặng theo thiết kế tương đối: RV-09-005 còn mở để nghiệm thu. EV-09-002/003/004. |
| TC-09-008 | Đạt kiểm ngưỡng và probe | Sát biên 12°/30° và single floating 15/30 cm; track 15/22 cm từ tests cũ. YAML mặc định/spec-vn đều 15 cm và 12°. So ngưỡng cũ, GT và perturbation trên tuning; held-out chỉ dùng kiểm sau khi khóa code. EV-09-003/004/005. |

Đạt kiểm tự động không thay kết luận precision của người duyệt. Các thao tác tay còn lại được liệt kê ở mục 7.

## 3. Findings và sửa

### RV-09-001 — P2: median trộn đường bằng và dốc che box lơ lửng

**Trạng thái: đã sửa, xác minh ca tái hiện và hồi quy.** `floating_findings_by_track` dùng chung median distance cho nửa track đường bằng và nửa trên dốc. Box nâng 25 cm trên dốc 8° có median distance gần -6 cm, gần median toàn track, nên không phát sinh finding. Điều kiện suppress bằng contact của sửa #52 chỉ bỏ mục đã báo, không giúp ca này.

Sửa: khi đủ peer, ưu tiên peer có chênh lệch median–contact tương đương, vẫn loại chính box đang kiểm. Giữ median ground và lớp suppress contact; không bật so contact tuyệt đối cho mọi box trong track. Ghi `reference_frames`, `terrain_reference`, `contact_distance` để truy vết. Đủ peer nghĩa là vẫn theo `min_track_boxes`; ít peer giữ fallback cũ.

Ca `test_track_from_flat_onto_slope_floating_frame_flagged` từ FAIL thành PASS. Các ca sạch/lún C4 giữ PASS. GT held-out giữ nguyên danh sách findings; tuning thay đổi bốn identity, chi tiết mục 5. Cần precision tay cho cảnh báo mới, không chứng nhận plane là đúng chỉ vì fit thành công.

### RV-09-002 — P2: outlier làm xe đứng yên bị coi là chuyển động

**Trạng thái: đã sửa, xác minh.** `_segment_jumps` tính moving bằng toàn track, gồm box cần kiểm. Với `(frame,x)=(0,14),(5,10),(6,10),(7,10)`, box đầu bị dời 4 m làm track thành moving; ngưỡng ngoại suy nhân khoảng cách keyframe và không báo.

Sửa: khi ngoại suy một endpoint, xác định moving từ các peer trong giả thuyết leave-one-out. Bắt được cả đầu và cuối 4 m; giữ ngưỡng nới cho xe thực sự chuyển động và ca track 3 box. Không đổi ngưỡng config.

### RV-09-003 — P2: caller cắt mất điểm ground ở góc box xoay

**Trạng thái: đã sửa, xác minh.** `ring_ground_for_box`/OtherBoxPoints đã xử lý yaw, nhưng caller trong `estimate_scene_ground` và `box_point_sets` vẫn cắt theo nửa cạnh dài cộng margin. Box rộng xoay 45° có điểm vành đai ngoài cửa sổ đó; direct estimator có đủ ground nhưng caller trả no_evidence/ground_z=None.

Sửa cả hai caller bằng `hypot` của hai nửa cạnh cộng phần nới. Oracle test tự tính tọa độ điểm và lọc box xoay, không gọi helper cần kiểm để lấy đáp án. Không thay logic RANSAC hoặc convention tọa độ.

### RV-09-004 — P2: reference cùng ID trộn class

**Trạng thái: đã sửa, xác minh.** Floating, heading.points, fit.outside và fit.loose gom reference chỉ theo `track_id`. Input cùng ID nhưng khác label có thể dùng số đo truck che outlier car. Type/model vẫn nhận input này, nên không thể giả định caller luôn loại nó trước.

Sửa bốn reference theo `(track_id,label)`, giữ loại current sample/frame. No-evidence floating cũng tách label để không gán chung kết luận. Không thay định dạng track ID nguồn hoặc helper group_by_track toàn dự án. Thuộc tính subtype trong cùng label và luật heading.flip/motion là phạm vi kiểm nối/spec của 10/14; sửa này không chứng nhận mọi detector đã tách mọi loại reference.

### RV-09-005 — giới hạn fit.loose trên cả track dư đều

**Trạng thái: còn mở để người nghiệm thu đánh giá; không thay thuật toán trong lượt này.** Gap 0,6 m đều cả track không báo vì điều kiện là dư tuyệt đối và tăng so peer. Một frame 1,2 m trong track 0,6 m được báo. Đây là thiết kế chống báo nhầm cho hình dạng vật đặc thù, nhưng không phát hiện mọi box dư đồng loạt.

Phần 15 cần đo theo tình huống này và xem tay. Không ghi đã chấp nhận giới hạn thay cho quyết định của người dùng; không tự nới luật tuyệt đối để làm đẹp recall khi chưa có dữ liệu.

## 4. Test và môi trường

| Evidence | Lệnh/phạm vi | Kết quả |
| --- | --- | --- |
| EV-09-001 | Baseline test_ground/ground_slope/heading_fit/track/size/core_review_regressions | 138 PASS,1 SKIP,1 XFAIL; lúc đó NUSCENES_ROOT chưa đặt |
| EV-09-002 | Tests mới + ground_slope trước sửa; XML review09-red2 | **36 PASS,9 FAIL**; đã sửa lỗi constructor ở fixture nháp trước khi dùng kết quả này |
| EV-09-003a | Geometry tập trung + floating/gate coverage; XML review09-green | **190 PASS,1 SKIP**; skip ground thật ở lượt này được chạy lại trong full suite |
| EV-09-003b | Full pytest với NUSCENES_ROOT và coverage, XML review09-full2 | **631 PASS,5 SKIP,0 FAIL/ERROR/XFAIL**,106,86 s |
| EV-09-003c | node --test tests/*.test.js từ extension | **37 PASS**,0 FAIL/SKIP |
| EV-09-004 | geometry_probe.py trước/sau trên 10 cảnh mini, cộng profile ngưỡng cũ trên 5 tuning | [So sánh GT](evidence/09/quality-comparison.json) |
| EV-09-005 | injection_probe.py: 2 tuning scene, một target/track; so archived floating ở 3584000, fixed và ngưỡng cũ | [Probe chèn lỗi](evidence/09/injection-summary.json) |
| EV-09-006 | Faulthandler cô lập test HTTP bị kẹt; chạy lại ngoài sandbox | [Ghi chẩn đoán](evidence/09/runtime-recovery.md) |

5 SKIP: **2 ca PyTorch** vì chưa có torch (phần 11), **3 ca CVAT live** bị tắt có chủ đích (phần 14). Các ca nuScenes thật đã chạy trong full suite. Có warning Starlette/httpx TestClient deprecation kế thừa; không thay dependency trong phần 09.

Lệnh full từ tool root, dùng đúng môi trường `.venv` hiện có:

```powershell
$env:NUSCENES_ROOT='C:/Users/Han/Downloads/v1.0-mini'
$env:POINTSNAP_LIVE_CVAT='0'
.\.venv\Scripts\python.exe -m coverage run --data-file=out/review09-new.coverage --source=pointsnap -m pytest -q -p no:cacheprovider --basetemp out/review09-new-temp --junitxml=out/review09-new.xml --tb=short
```

Dùng tên output mới. Test HTTP cần loopback socket hoạt động; sandbox của phiên này làm socketpair của asyncio kẹt trước handler. Raw XML/coverage/probe output nằm dưới `out/`, không commit; tóm tắt và SHA256 trong evidence.

## 5. Kết quả GT và giới hạn chất lượng

Chỉ bật geometry/size/track jump, không gồm C5–C8, camera, Critic hoặc learned model. Counts trên nhãn GT là proxy, **không phải số false positive đã xem tay**.

| Split | Box | Warning trước → sau | Error trước → sau | Warning /100 sau | Error /100 sau |
| --- | --- | --- | --- | --- | --- |
| Tuning 5 cảnh | 8.664 | 106 →104 | 24 →24 | 1,200 | 0,277 |
| Held-out 5 cảnh | 5.440 | 142 →142 | 32 →32 | 2,610 | 0,588 |

Held-out giữ nguyên từng identity `(rule,severity,frame,track,label)`. Tuning:

- scene-0916, frame14: bỏ floating warning track652 và thêm warning track644 (motorcycle). Số lượng không đổi, cần kiểm tay mục mới.
- scene-1094: bỏ hai floating warning track804, frame9 và14 (car).

Không gọi các mục bị bỏ là false positive đã được xác nhận. Ngưỡng G7 **≤2 warning,≤0,5 error /100 box** chưa đạt ở held-out ngay cả với subset này; không xác nhận nghiệm thu rộng.

Với mã nguồn fixed, đổi về ngưỡng cũ floating12cm/heading15° trên tuning cho **145 warning/23 error**; ngưỡng hiện tại15cm/12° cho **104/24**. Hai ngưỡng thay đổi đồng thời trong profile này; kết quả không dùng để gán toàn bộ chênh lệch cho một luật. Floating warning100→53; heading.points warning11→17.

## 6. Probe chèn lỗi trên dữ liệu thật

Một frame giữa mỗi track, tối đa20 track/cảnh, hai cảnh tuning scene-0061/0553. Floating chọn track có ≥5 frame đo ground hợp lệ; heading chọn track class dài nhưng chưa loại toàn bộ ca ít điểm/xa. Không dùng held-out để chỉnh ngưỡng.

| Perturbation | Số target | Baseline, ngưỡng hiện tại | Fixed, ngưỡng hiện tại | Fixed, ngưỡng cũ |
| --- | --- | --- | --- | --- |
| Nâng14cm | 27 | 5 | 5 | 18 |
| Nâng25cm | 27 | 26 | 26 | 26 |
| Hạ25cm | 27 | 27 | 27 | 27 |
| Xoay13° | 37 | Không đo baseline riêng | 10 | 2 |

Đây là **target hit count trên mẫu perturbation**, không phải recall toàn bộ mini; có thể có finding sẵn trên target GT. Không trừ clean-hit trong phép đo này, nên không gán mọi hit là phát hiện mới. Kết quả xác nhận không giảm hits ±25cm trong mẫu đã chọn và cho thấy đánh đổi khi nâng ngưỡng floating; còn một target +25cm chưa hit và nhiều target heading chưa hit. Đo độc lập recall/precision đầy đủ và phân nhóm no_evidence thuộc phần 15.

## 7. Kiểm tay và việc bàn giao

1. **Ưu tiên:** scene-0916 frame14 track644 và652; đối chiếu point cloud/camera, ground plane, reference trước/sau. Xác định warning mới có đúng không.
2. Scene-1094 track804 frame9/14: đối chiếu các mục bỏ; không coi bớt finding mặc nhiên tốt hơn.
3. Xem các ca dốc/vỉa hè thật, ít điểm và track dư đều; bổ sung verdict độc lập vào Web theo phần 15. Lượt này có **0 verdict precision tay**.
4. Phần 10 nhận thay đổi fit/track/reference và kiểm subtype/spec/cargo. Phần 14 kiểm export/UI của ground/reference mới và CVAT thật. Phần 15 nhận counts/perturbation, benchmark và quality còn chưa đạt.
5. Phần 11 xử lý hai SKIP torch; không bật CVAT live hoặc ghi lên job công việc để làm sạch số SKIP của phần 09.

## 8. Inventory phần 09

Đã đọc và đối chiếu đủ **13 file owner09** trong [inventory](scope-inventory.tsv):

| File tương đối với tool root | Kết luận |
| --- | --- |
| pointsnap/core/box_points.py | Sửa RV-09-003; oracle và full suite đạt |
| pointsnap/core/ground.py | Không sửa; kiểm RANSAC/plane/contact/ring/index và tọa độ; tests slope/ground/index đạt |
| pointsnap/detectors/fit.py | Sửa RV-09-004; ghi giới hạn RV-09-005 |
| pointsnap/detectors/floating.py | Sửa RV-09-001/003/004; ground/track/no_evidence/gate đạt |
| pointsnap/detectors/heading.py | Sửa reference heading.points RV-09-004; giữ pose/modulo90/flip/motion |
| pointsnap/detectors/size.py | Không sửa; giữ tách class/subtype, manual keyframe và cargo từ main; luật cargo/spec kiểm sâu ở10 |
| pointsnap/detectors/track.py | Sửa RV-09-002; không mở rộng sang luật ID swap/C5 của10 |
| tests/test_floating_detector.py | Đọc và chạy đủ; floating absolute/no_evidence đạt |
| tests/test_ground.py | Đọc/chạy đủ; ground real đã chạy trong full suite |
| tests/test_ground_slope.py | Bỏ XFAIL khi đã tái hiện và sửa; tất cả ca C4 đạt |
| tests/test_heading_fit.py | Đọc/chạy đủ; heading/fit/default/switch/injection đạt |
| tests/test_size_detector.py | Đọc/chạy đủ; ngưỡng/track size đạt |
| tests/test_track_detector.py | Đọc/chạy đủ; nhảy/ngoại suy/3 box/split đạt |

Đọc thêm core/config/scanner/model/gate/geometry và tests hồi quy02/gate coverage để xác minh điểm nối; không sửa toàn bộ các vùng đó. Test mới `tests/test_geometry_review09.py` chứa28 ca đã chạy. Giữ nguyên các file local chưa theo dõi của người dùng.
