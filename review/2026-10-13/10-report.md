# Báo cáo review 10 — tình huống thực tế và luật spec

Ngày **13/10/2026**, Asia/Saigon. Nhánh `codex/review-10-spec-scenarios`.

## 1. Kết quả và nguồn

- Nhánh 10 nhận phần 09 bằng fast-forward tới **`cbeb41c`**, giữ lịch sử từ main `d18b1a9`.
- Commit mã nguồn: **`c5ac54d`**. Sửa **9 nhóm lỗi**, thêm **31 ca hồi quy**.
- Gate cuối: **662 Python PASS, 0 FAIL/ERROR/XFAIL, 5 SKIP; 37 Node PASS**. Coverage 5 module đã sửa: **1.466/1.536 = 95,44%**; toàn package **90,58%**. Đo statement coverage.
- NuScenes mini thật, taxonomy spec-vn: **10 cảnh, 14.217 box**, gồm 8.759 box tinh chỉnh và 5.458 box held-out. Không ghi CVAT hoặc tải model.
- Hoàn tất review/sửa và bàn giao; **chưa nghiệm thu precision tay hoặc CVAT/MV3 thật**.

[Verification](evidence/10/verification.json) lưu SHA, hash source, hash XML, schema config, kết quả/skip và coverage. Probe chạy trước commit khi HEAD vẫncbeb41c; đã đối chiếu hash file với codec5ac54d để xác nhận đúng phiên bản sau sửa.

## 2. Checklist 8 ca

| Mã | Trạng thái | Thực hiện |
| --- | --- | --- |
| TC-10-001 | Đạt kiểm tự động | ID swap thật cùng subtype vẫn báo; khác subtype không ghép; chỉ keyframe; pair dùng cùng hệ pose/thời gian; giữ overtaking/crossing/U-turn trong scenario suite. Probe thật20/21 targets trước/sau. |
| TC-10-002 | Đạt theo heuristic chiều cao | Height chỉ lấy manual visible keyframes; interpolated boxes không che manual error; thuộc tính optional đã khai vẫn khớp; bộ test standing/sitting/child/run split và GT thật chạy đủ. Chưa có camera/precision verdict xác minh tư thế người thật. |
| TC-10-003 | Đạt kiểm tự động | Inside cùng frame, footprint xoay, người cạnh/đứng trên xe không báo; vẫn xét occluded manual labels như spec. Sửa aggregation track_id0. |
| TC-10-004 | Đạt toán hình học | Overlap49% không thành≥50% bởi lưới; clipped area chính xác, rotated/disjoint/degenerate guard; with/without rider và metadata note được phân biệt theo schema. GT có đổi frame đầu ởscene0061, cần xem tay. |
| TC-10-005 | Đạt logic/ca tái hiện | Rider_state cần đầy đủ world pose, thời gian thật nếu đủ; không dùng interpolation; dismount cần hai quan sát kế tiếp giữstate và xe tiếp tục đứng. Thiếu pose chặn gate khi chỉ bật luật này. Xe có người đứng chờ vẫn là giới hạn. |
| TC-10-006 | Đạt pipeline/API | Cargo không hạ ERROR khi owner shape mơ hồ hoặc note giả subtype; chỉ cohort class/key tương ứng và manual evidence. S1b cargo thật còn WARNING; E1 box phóng rộng còn ERROR. API subtype cần resolver rõ. |
| TC-10-007 | Đạt parser/taxonomy/đọc Web | Rider config phải đủ5 khóa đúng; giữ tên literal Trailer/contruction/Tricycle và allowed_values của taxonomy/guideline. Other chỉ hợp lệ nơi schema cho phép. JS/HTML có5 toggle tương ứng,Node suite đạt; thao tác browser thật thuộc14. |
| TC-10-008 | Đạt oracle/test độc lập | 31 ca không dùng scenario_sim làm oracle; thêm oracle ego90° tính tay kiểm cả labels/points của simulator. Scenario suite cũ vẫn đạt. Vật mang dài>2m và precision tay chưa có được bàn giao. |

## 3. Findings đã sửa

| Mã | Mức | Tái hiện trước sửa | Sửa và xác minh |
| --- | --- | --- | --- |
| RV-10-001 | P2 | Rider motion dùng tọa độ sensor khi thiếu pose; xe đỗ bị báo 10–20 m/s. Scanner bỏ timestamp thực, biến 3 m/3 s thành 6 m/s. Gate thiếu yêu cầu pose cho rider_state. | Chỉ suy motion khi đủ pose; dùng một cơ sở thời gian cho cả track; truyền timestamp và bổ sung coverage vào gate. Ca sai và ca lên xe thật đều đạt. |
| RV-10-002 | P2 | ID swap ghép cả car/truck trong nhóm Vehicle; interpolation tạo swap; timestamp thiếu làm trộn epoch với thời gian tương đối; một track thiếu pose ảnh hưởng pair khác. | Truyền class_key từ scanner, chỉ dùng manual visible, chuẩn hóa pose/time và severity theo pair, kiểm dt dương. Cache quỹ đạo được giữ để tránh tính lại ở mỗi pair. |
| RV-10-003 | P2 | Chiều cao nội suy che lỗi ở manual keyframe; chuyển động nội suy tạo warning rider. Các nhóm thuộc tính đếm box nội suy như keyframe nhập tay. | Thuộc tính/hình học/rider dùng manual keyframes. Height/rider bỏ occluded; spec.inside vẫn xét occluded manual vì người trong xe thường bị che. |
| RV-10-004 | P2 | Note=sitting hoặc with_rider khớp luật hình học dù thuộc tính pose/rider_state khác; cùng ID nhưng khác label bị gộp attr.missing. | Match từ tên thuộc tính required/allowed đã khai, gồm optional attributes; lỗi thuộc tính tách label. Custom schema chưa khai tên vẫn có cách khớp giá trị cũ, được ghi là giới hạn. |
| RV-10-005 | P2 | Footprint 1 m² overlap 0,7×0,7 = 0,49 m²; lưới 7×7 đếm 25/49≈0,5102 và báo rider_double sai ngưỡng. | Dùng clipping/area của core; bảo vệ diện tích bằng 0 do underflow, giới hạn tỷ lệ trong [0,1]. Oracle 49%, box xoay/tách nhau và đối chứng rider đều đạt. |
| RV-10-006 | P2 | track_id=0 bị biểu thức `or id(box)` thay bằng ID bộ nhớ; ba frame thành ba findings. | Kiểm `is not None`, tách track/shape và label; test aggregation track 0 đạt. |
| RV-10-007 | P2 | Dismount lấy bất kỳ 2 with_rider trong 3 quan sát sau, dù đã đổi without ngay sau sự kiện hoặc xe chạy tiếp. | Xét đúng hai quan sát kế tiếp; cả hai giữ with_rider, hai bước sau đều ≤0,5 m/s. Đối chứng xuống xe thật vẫn đạt. |
| RV-10-008 | P2 | Shapes không có ID cùng frame/class làm owner mơ hồ, nhưng được hạ ERROR bằng điểm của shape khác. Vehicle/Tricycle có thể khớp chữ Tricycle trong note; API trực tiếp cũng gặp. | Chỉ hạ khi owner duy nhất, cùng class/type. Subtype cần resolver; không có resolver chỉ dùng class, không đoán từ các attrs tùy ý. Kiểm cả pipeline và API trực tiếp. |
| RV-10-009 | P2 | spec.rider_state thiếu khóa hoặc có typo được parser nhận, rồi detector KeyError hoặc không chạy đúng ý. | Mapping hoạt động cần đúng class, attribute, with, without, person; giá trị không rỗng, with khác without. Empty mapping vẫn tắt luật. ConfigError xuất hiện trước scan. |

Các finding trên đã sửa và có hồi quy. **19 ca FAIL trên baseline** là counterexamples đầu tiên; hai boundary FAIL trong iteration (optional declared attribute/zero area) và một FAIL API cargo được sửa trước gate cuối. Không tính hai guard của implementation thử nghiệm thành hai lỗi baseline riêng.

## 4. Evidence và lệnh

| Evidence | Phạm vi | Kết quả |
| --- | --- | --- |
| EV-10-001 | Baseline: scenarios/spec_geometry/spec_rules/size/config |72 PASS |
| EV-10-002 | test_spec_review10 trước sửa |19 FAIL; không có fixture exception trong lượt này |
| EV-10-003 | Iteration focused,guards và cargo API |91 PASS rồi146 PASS; các boundary/cargo FAIL được giữ trong metadata trước sửa |
| EV-10-004 | Full final pytest với coverage ngoài sandbox |662 PASS,5 SKIP,0 FAIL/ERROR/XFAIL;124,63s |
| EV-10-005 | Node extension suite |37 PASS,0 FAIL/SKIP |
| EV-10-006 | spec_probe.py trước/final trên10 cảnh |[GT comparison](evidence/10/quality-comparison.json) |
| EV-10-007 | injection_probe.py trên2 tuning scenes; archived modulescbeb41c vsfixed |[Injection](evidence/10/injection-summary.json) |

5 SKIP vẫn gồm2 torch và3 CVAT live, không cộngPASS. TestClient cần loopbacksocket; dùng cách chạy ngoài sandbox đã chẩn đoán trong09, không sửa runtime ứng dụng. NuScenes integration đã chạy; warning Starlette/httpx cũ giữ nguyên.

Lệnh gate từ `source-tool/pointsnap-3d/`, dùng output mới:

```powershell
$env:NUSCENES_ROOT='C:/Users/Han/Downloads/v1.0-mini'
$env:POINTSNAP_LIVE_CVAT='0'
.\.venv\Scripts\python.exe -m coverage run --data-file=out/review10-new.coverage --source=pointsnap -m pytest -q -p no:cacheprovider --basetemp out/review10-new-temp --junitxml=out/review10-new.xml --tb=short
```

Raw XML/coverage/probe files nằm dướiout/, không commit. Evidence gồm tóm tắt đã lọc và scripts tái lập.

## 5. GT và probe thật

Chỉ bật subset spec/attribute/ID-swap/size; không bật geometry09,camera,critic,learning hoặcmissing-object. Không dùng counts này thay cho quality toàn sản phẩm/G7.

| Split | Box | Warning trước→sau | Error trước→sau |
| --- | --- | --- | --- |
| Tuning5 cảnh |8.759 |5→5 |2→2 |
| Held-out5 cảnh |5.458 |20→20 |2→2 |

**Held-out giữ từng identity.** Tuning có một identity thay đổi: `spec.rider_double`,Pedestrian track38,scene-0061: frame đầu9→6. Số findings giữ nguyên; đây là thay đổi dooverlap chính xác, chưa được xem tay là đúng hay báo nhầm. Chi tiết/ids/hash config trongEV-10-006.

Chèn lỗi chỉ trênscene-0061/0553, tối đa12targets/type/scene; loạiclean hits trước đếm. Không chỉnh ngưỡng trênheld-out:

| Chèn lỗi | Target mới trước | Target mới sau |
| --- | --- | --- |
| Standing adult cao1,65–2,20m →sitting tại mộtkeyframe |21/21 |21/21 |
| ĐổiID hai track cùngtype gần nhau≤3m, đoạn chung≥6frames |20/21 |20/21 |
| Trackwith_rider →without_rider |1/3 |1/3 |

Đây là hit-rate trên tập nhỏ có điều kiện, **không phải recall toànmini**. Rider targets được chọn theo thuộc tính, chưa lọc đều là xe đang chạy; người ngồi trênxe đứng chờ không suy được chỉ bằngmotion. Không gán hai target khônghit thành hai lỗi thuật toán đã xác nhận. SampleIDs cần mappingmanifest trước khi dùng làmserverIDCVAT.

## 6. Giới hạn và kiểm tay

- **0 verdict precision tay** trong lượt này. Xem4 mục: scene0061/frame1/track159(Two-wheels,height); scene0061/frame6/track38(Pedestrian,rider_double); scene0916/frame6/track708(Pedestrian,height); scene0103/frame0/track301(Pedestrian,height).
- Rider/inside/height làheuristic dựa box/attribute. Camera/người duyệt cần phân biệt người đi cạnh xe, driver,pose/tuổi thật và vật nằmtrên thùng. Hai quan sát sau không chứng minh liên tục trênmọiframe bị thiếu.
- Keys Class/value vẫn làlegacy format; schema khai báo giúp tránhnote, nhưng configcustom không khai tênattrs vẫnvalue-matching. Không tự mở rộngenum/chuẩn hóa tên trái spec. Taxonomy nuScenes giữfallbackpose standing khi thiếuattribute nguồn: không coi mapping này làverdict tư thế thật.
- Dư đều toàntrack củafit.loose từRV-09-005 còn mở. Người vác vật dài>2m khôngbox riêng chưa được bắt. Datasetmini/spec-vn không đại diện mọi tình huống Việt Nam.
- Cargo API có subtype-key phải truyềnclass_key; subtype không xác định hoặcshape mơ hồ giữERROR, tránhdowngrade theo điểm của vật khác.
- Macro metrics/model/precision tay, benchmarkserial và CVAT/browser thật tiếp tục ở11–16. Không xác nhận G7 từ subset nhỏ này.

## 7. Inventory và bàn giao

Đọc/chạy đủ5 fileowner10: `detectors/attributes.py`(sửa); `tests/scenario_sim.py`(oracle độc lập, không sửa); `tests/test_scenarios.py`(giữ scenarios đúng); `tests/test_spec_geometry.py`(positive rider tests truyềnworld pose rõ); `tests/test_spec_rules.py`(required/allowed/taxonomy/trackspec vẫn đạt).

Đọc/sửa thêm5 điểm nối được ghi dependency: core/config,core/scanner,detectors/track,detectors/size và test mới31ca. Đọc thêm taxonomy,guideline,Webtoggle keys,giao việcC5/C6 và bàn giao09.

Phần11 nhận code10 trên09; phần14 kiểmbrowser/config/API/CVAT với requirementpose mới; phần15 nhậnEV-10-006/007 và4 mục precision tay. Nhánh10 chứa ancestry09; nếu09 chưa merge main, PR10 có thể dùngbase09 để chỉ thấy diff10. Không squash chuỗi phụ thuộc khi chưa kiểm lại ancestry.
