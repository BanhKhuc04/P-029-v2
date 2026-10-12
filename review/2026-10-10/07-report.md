# 07 — Kiểm thử, đánh giá và hiệu năng

Ngày **12/10/2026**, Asia/Saigon. Nhánh `review/07-tests-evaluation-performance`, base06 `6282f05`. Code07: `19157f6`, `38f5f0c`, `43a0f4d`, `edfbed5`. Không đổi ngưỡng/scanner để tối ưu trên held-out test.

## Kết quả kiểm thử

- **490 pytest đạt,0 fail/skip/error**,65,51s,1 cảnh báo Starlette/httpx. Python3.12.14, Windows; dataset v1.0-mini, CVAT2.78.1; temp/home riêng. [Counts](evidence/07/test-summary.json).
- **36 Node đạt**,0 skip. Bao gồm logic Web/content/worker; không thay cho MV3/browser thật.
- Runner đã được tracked và chạy: default486 pass +1 ground-real skip; dataset4 pass; live CVAT3 pass; Node1 command pass; online SKIP. Tổng report494 PASS/0 FAIL/2 SKIP gồm command checks, không gọi494 là số pytest. Sau đó3 regression metrics bổ sung đã nằm trong full490.
- Map41 ca A01–F04: **34 phần code PASS,7 MANUAL**; mọi `full_checklist_passed=false`. [Map quan sát](evidence/07/checklist-map-observed.json). Map là snapshot lần runner đó, trước cập nhật gợi ý Web box lún; Node36 là bằng chứng cập nhật riêng.
- Lượt đầu3 live tests fail vì Docker tắt; bật Docker/CVAT rồi live3 đạt và tự dọn task. Một lượt runner thấy race trong test semaphore; đã sửa wait2s và kiểm lại. Lỗi sandbox temp/spawn và cwd/encoding của helper là lỗi môi trường, không đếm vào finding sản phẩm.

## Findings đã xử lý

| Mã | Mức | Trước sửa → sửa / kiểm lại |
|---|---|---|
| F07-01 | P1 | Metrics legacy tính INFO/no_evidence là TP và bỏ explicit rule. Chỉ warning+, match rule; ca đáp án0TP/1FN, sai rule→FP |
| F07-02 | P1 | Scene khác trùng frame/track có thể nhận công; wrong log schema thành empty experiment. Scene key và reject schema không đúng; fixtures biết1TP/1FN |
| F07-03 | P2 | Không mẫu ghi0%, measurement0, false alarms không có clean scan vẫn ĐẠT. Trả None/CHƯA ĐO; error/warning tách; size measurement cần expected quantity rõ |
| F07-04 | P1 | Script run_eval_suite dùng5cảnh đầu/cuối,3detector cũ và ghi đè docs. Delegate CLI canonical, split eval/split.py, --out mới, giữ docs lịch sử |
| F07-05 | P2 | error_rate0 vẫn chèn1 lỗi; invalidrate/rounds/scene list thiếu guard. 0→không chèn, rate[0,1], rounds≥1, cảnh không rỗng/trùng; tests |
| F07-06 | P2 | Canonical denominator bỏ rule switches/class/min_frames/min_keyframes; finding có thể credit2 injection. Guard scope và used set; dữ liệu cũ được postprocess scope, scans/matches giữ |
| F07-07 | P2 | Experiment thiếu commit/config hash/injection records, có thể đè bằng chứng. metadata.json/injections.json, config hash, seed/rounds/catalog; refuse output đã có metadata |
| F07-08 | P2 | Runner local chưa Git, subprocess thiếu runtime path/temp quá dài; real-data configured invalid bị skip. Track runner/map/checklist; PYTHONPATH inherited runtime, short temp; explicit bad root fail |
| F07-09 | P2 | Test đòi semaphore released ngay khi body tới, trước finally; live fixture không close client. Timeout acquire và finally session.close; full/live kiểm lại |
| F07-10 | P2 | Map phát hiện Web box lún vẫn khuyên hạ đáy. findingFixTip nâng khi lún, khớp extension; Node regression mới và36 tổng đạt, không tính ca chưa chạy |

15 ca regression đầu fail trước sửa, sau qua; bổ sung6 ca scope/seed/log. Các lỗi01–06 vẫn được full suite/Node kiểm. [Ma trận](07-test-matrix.md).

## Đánh giá có thể tái lập

Tuning: scene0061/0553/0757/0916/1094. Test: scene0103/0655/0796/1077/1100. Mỗi tập **10 vòng, seed0, catalogall, error_rate0,10**, config mặc định đã đóng băng trước test; lưu hash các bảng dataset và config. Chạy tuần tự tuning913,02s rồi test634,27s. Không tuning ngưỡng sau xem test.

Các thay đổi evaluator scope được phân tích lại từ log injection và outcome gốc, **không quét lại, không đổi detected/severity/config**;5 outcome mỗi tập đổi applicable do guard min_frames/class/min_keyframes. File gốc giữ trong out; hashes trong evidence. [Tuning](evidence/07/tuning/ket-qua.md), [Test](evidence/07/test/ket-qua.md), [metadata](evidence/07/test/metadata.json).

| Tập | Box visible | Lỗi chèn / bắt được | Warning trên nhãn chuẩn | Error trên nhãn chuẩn | /100 box warning/error |
|---|---|---|---|---|---|
| Tuning | 8.664 | 428 /151 | 172 |29 |1,985 /0,335 |
| Test |5.440 |348 /148 |194 |30 |**3,566 /0,551** |

Số warning/error là **finding trên nhãn chuẩn**, proxy false alarms; nhãn chuẩn có thể có lỗi thật. **Chưa đạt mục tiêu test ≤2 warning và≤0,5 error/100box theo proxy này**. Không suy số này thành precision thật.

### TP/FP/FN và mẫu số

| Loại (test) | TP_fault /FN_fault /N_fault | Finding khớp /không khớp /N_finding |
|---|---|---|
| floating |7 /75 /82 |7 /1.544 /1.551 |
| size |60 /2 /62 |60 /266 /326 |
| track |41 /38 /79 |41 /193 /234 |
| heading |31 /30 /61 |67 /164 /231 |
| fit |9 /55 /64 |9 /263 /272 |

Recall dùng lỗi chèn làm đơn vị; precision synthetic dùng finding làm đơn vị. Một lỗi heading có nhiều finding khớp, vì vậy TP_fault31 khác matched_finding67. Không dùng31 thay67 trong precision hay dùng67 thay31 trong recall. Các finding trên box chèn lỗi loại khác được lưu ở `on_injected`, không tự coi toàn bộ là correct-rule TP.

| Kiểu /mức (test) | Bắt /N toàn bộ | Bắt /N thuộc scope | Điều kiện bằng chứng |
|---|---|---|---|
| floating40cm |4/21 |4/17 |Có ground evidence4/4; không gọi4/4 là recall toàn dataset |
| size_in_track30% |7/7 |7/7 |n nhỏ |
| jump4m |6/6 |6/6 |n nhỏ |
| rotate180° |13/14 |13/13 |scope class/angle/points |
| reverse180° |2/6 |2/2 |vật đủ tốc độ |
| duplicate |5/8 |5/5 |overlap class/allowed pairs |
| interpolation3frame |2/10 |2/3 |moving vàmin_frames |

Large severity30/30 ở mứcerror là subset applicable/có evidence, không phải30/348. Wilson95 có n/N và giới hạn trong [intervals](evidence/07/test/recall-intervals.json): ví dụ2/2 thấp hơn100% đáng kể ở cận dưới. Các vòng tái dùng scene/track có tương quan; khoảng này mô tả binomial tham khảo, không chứng minh khác biệt có ý nghĩa thống kê.

Dataset raw_annotations test5.440, visible5.440; add_track_markers thêm728 marker/occluded, không đưa vào denominator hình học. Con số5.478 trong báo cáo cũ **chưa truy vết được chênh38 box từ metadata cũ thiếu hash**; không tự quy38 box cho occlusion. Snapshot10/10 dùng5.440 nhưng code/config khác nên3,42 warning cũ không bằng3,566 hiện tại. Không sửa bảng lịch sử thành số đo mới.

Precision xem tay độc lập: **0 mẫu trong lượt07**. Review05 index0 fp trên fixture giả không phải ground truth của nuScenes test. Hiệu quả người review tiết kiệm thời gian và missing-object vẫn chưa đo; không tạo verdict hộ reviewer.

## Hiệu năng

Quét sạch trong evaluation: test7,26–16,81s/cảnh, tuning8,51–24,04s; scan gồm point-cloud I/O và detector. Benchmark serial riêng2scene×2sweeps×3 lần sau full tests: [measurements](evidence/07/benchmark-measurements.json), [metadata](evidence/07/benchmark-metadata.json), [min/median/max](evidence/07/benchmark-summary.json). Lượt benchmark overlap full tests được giữ trong out và loại khỏi bảng serial.

Không flush OS cache; “first” chỉ là lần đầu trong process; reader được tạo mới mỗi lần. CPU dùng process_time, RAM GetProcessMemoryInfo PeakWorkingSetSize là peak tích lũy, không phải allocation riêng của mỗi pass. Metadata/LiDAR read pass/report tách thời gian; scan vẫn gồmI/O, không trừ một phép đọc khác để gọi phần còn lại là core time.

| Scene | Box visible | Sweeps | Min / median / max scan (s) |
|---|---|---|---|
| scene-0757 |531 |0 |3,17 /3,33 /3,38 |
| scene-0757 |531 |4 |7,53 /7,98 /8,09 |
| scene-0061 |3.333 |0 |9,13 /9,32 /9,86 |
| scene-0061 |3.333 |4 |24,04 /24,17 /24,62 |

Peak working set toàn process khoảng209,35MiB; keyframe points của scene0061 là1.354.112,39frame. Đây là process PointSnap, không tính RAM của toàn stack Docker/CVAT.

HTTP controlled mock:2report200, requestthứ3=429 khoảng3,3ms, health200 trong lúc slots bận. [Concurrency](evidence/07/concurrency.json). Đây là cap/latency chức năng, không throughput CVAT thật. Queue16/1worker và preview max4000 điểm vẫn có regression; HTTP Docker/report thật chuyển08.

Mục tiêu<2phút/cảnh đạt trong các scan local đã đo, không bảo đảm mọi dataset/hardware. Mục tiêu false alarms trên test chưa đạt. Tránh dùng “~2giây/cảnh” lịch sử làm cam kết giai đoạn hiện tại.

## 23 ca và giới hạn

| Ca | Kết quả |
|---|---|
| R07-01 | Đạt full490/Node36; exact counts+exit trong evidence |
| R07-02 | Đạt logic: tọa độ/marker independent assertions từ01–03; metrics fixtures TP/FP/FN số nguyên rõ |
| R07-03 | Đạt: cwd tạm; live `.env` opt-in; runner clean environment/home riêng |
| R07-04 | Đạt live3, task tự tạo/xóa, sessionclose; task79 riêng giữ cho08, không đụng job1/8 |
| R07-05 | Đạt trường hợp đủ dataset; invalid configuredroot không skip. Không gọi synthetic là real data |
| R07-06 | Đạt full regressions01–06 +21 ca mới; browser/MV3 giữ giới hạn |
| R07-07 | Đạt boundary/rule/occlusion tests kế thừa và applicabilityguards |
| R07-08 | Một phần: CI hiệnUbuntu3.11/Node22; localWindows3.12/Node24, logic/syntax. Chưa remote CI trên PR; matrix cải thiện chuyển08 |
| R07-09 | Đạt runner34 phầncode/7manual, fullmanual false, không tính skip thànhpass |
| R07-10 | Đạt seed/repeat/log injection type/magnitude/frameID vàrawhash |
| R07-11 | Đạt matchesrule/track/frame,onefinding credit1injection, explicitscene legacy |
| R07-12 | Đạt counts/denominators, null chưa đo; fault vàfinding đơn vị khác nhau |
| R07-13 | Đạt proxy cảnh báo/lỗi trên100visiblebox; chưa xem tay để gánfalsealarm thật |
| R07-14 | Đạt công bốscope/evidence/excludedmarkers; không trộn4/4ground vào21full |
| R07-15 | Đạt split5+5 disjoint,configfreeze, không tuningheldout |
| R07-16 | Chưa đo precision độc lập;0mẫu, cần reviewer có camera/nhãn tham chiếu |
| R07-17 | Một phần: rawhash/config mới đủ;5.478 cũ thiếumetadata, chưa giải thích38chênh bằng dữ liệu gốc |
| R07-18 | Đạt n/N vàWilson minh họa, clustered caveat; khôngclaim1/1 tổng quát |
| R07-19 | Đạt serial0/4sweeps,3lần,first/warm theo điều kiệnOScache rõ |
| R07-20 | Đạt2scene cỡ531/3333box,CPU/peakRAM/points; chưap95/load toànmáy |
| R07-21 | Một phần: functional queue/scope/cap +controlledHTTP latency; không2fullscan thật parallel throughput |
| R07-22 | Một phần: report/read stages đo; preview≤4000 vàpollguards tests. Chưapoll/previewbrowser latency ởload lớn |
| R07-23 | Scanlocal<120s; falsealarmproxytest vượt mục tiêu; reviewer time savings chưa đo |

Review07 hoàn tất trong phạm vi bảng; **chưa đủ gate chất lượng để phát hành diện rộng**. Chuyển08 lỗi manifest URLhost/container đã tái hiện, package/runtime/CI/launcher/docs và tổng sổ findings.
