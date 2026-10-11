# Báo cáo review phần 01 — yêu cầu, tổng quan và kiến trúc

## 1. Thông tin và kết luận

| Mục | Giá trị |
|---|---|
| Nhánh bàn giao | `review/01-overview-architecture` |
| Người thực hiện | Codex theo yêu cầu của Nguyễn Văn Hân; chưa có reviewer độc lập |
| Ngày | 11/10/2026, Asia/Saigon |
| Mốc GitHub main đã fetch | `5dcc97f1ffc1751d022e2474c0b50745e348af86` |
| Hướng dẫn nền | `22a01f5` — 8 hướng dẫn review dùng chung |
| Commit sửa runtime/gate | `099d5b795766841b5b0d3b204e23ee5f08391f05` |
| Commit sửa test live | `7eb5421f359fdcdfe762d1f06309fed5d8724d26` |
| Môi trường | Windows; Python 3.12.14; pytest 9.1.1; Node v24.19.0 |
| CVAT thật | Docker local, API version 2.78.1, `http://localhost:8080`; token đã kiểm HTTP 200, không ghi token vào bằng chứng |
| Dataset thật | `C:/Users/Han/Downloads/v1.0-mini`; 10 scene, 404 file LiDAR keyframe, có sweeps |
| Config/data test | Default với `env={}` cho core; FlatGround/mock cho hồi quy; nuScenes thật cho 4 ca và dataset giả upload vào CVAT thật cho 2 ca |
| Seed / số vòng | Hồi quy xác định, không chạy bộ eval chèn lỗi nhiều vòng trong lượt này |
| Báo cáo phần khác | Chưa có báo cáo 02–08 đã commit được tham khảo |
| Hoàn tất phần 01 | Có: 14/14 ca review đã đối chiếu, 8 findings trong phạm vi đã sửa và kiểm lại |
| Kiểm tra cuối | **252 pytest passed, 0 skipped**, 1 warning môi trường; **7 Node tests passed** |
| Nghiệm thu toàn sản phẩm | Chưa: còn kiểm trình duyệt, precision xem tay, metadata đánh giá và phần 02–08 |

Bằng chứng/lệnh đầy đủ: [evidence/01/test-results.md](evidence/01/test-results.md). Sơ đồ và ledger: [01-architecture.md](01-architecture.md).

## 2. Phạm vi và kiểm kê

Inventory [tracked-file-inventory.tsv](tracked-file-inventory.tsv) khớp **184/184 file** của baseline, không thiếu/thừa/trùng. Tại `22a01f5` có 196 file tracked: 184 nền và 12 file hướng dẫn. File mới của lượt này bổ sung vào báo cáo, không sửa inventory lịch sử thành số hiện tại.

| Phần phụ trách sâu | File baseline | Loại kiểm trong 01 |
|---|---:|---|
| 01 | 23 | Đối chiếu tài liệu yêu cầu/tiến độ/kiến trúc |
| 02 | 19 | Đọc model/config/scanner và đường gọi detector; test suite, chưa đo precision từng luật |
| 03 | 13 | Truy vết reader/converter/writer; mock, nuScenes thật, 2 ca API CVAT thật |
| 04 | 19 | Truy vết CLI/Web/report/persistence; hồi quy gate và API mock |
| 05 | 42 | Xác định Web/extension boundary; Node và kiểm cú pháp, chưa thao tác trình duyệt |
| 07 | 64 | Đọc hợp đồng test/eval; chạy suite; kiểm metadata của báo cáo lịch sử |
| 08 | 4 | Đối chiếu packaging/CI và môi trường; chưa cài máy trắng |
| 06 | Cross review | Inventory ghi rõ review bảo mật chéo, không thiếu ownership chỉ vì không có primary 06 |

Phân loại baseline: 87 Python, 36 Markdown, 10 JS, 2 HTML, 2 CSS, 21 font woff2, 17 PNG, 1 JPG, 1 SVG, 1 license TXT, 1 JSON, 1 TOML, 2 YAML, 1 workflow YML, 1 gitignore. Font/license và ảnh là asset, không phải implementation vendor. Dataset, report, snapshot và output generated không thuộc baseline.

Working tree ban đầu có các file local chưa theo dõi: `ARCHITECTURE.md`, `ARCHITECTURE_DIAGRAMS.md`, `pointsnap/api.py`, `tests/test_report_api.py`, Dockerfile/API/Compose/dockerignore/env example, README-Docker, Get-Report.ps1, auto-tests, output và checklist/review-test local. Giữ riêng các file này; không đưa vào commit phần 01. Những claim sai trong bản nháp kiến trúc được đối chiếu bằng tài liệu kiến trúc mới đã tracked.

CVAT ở thư mục cha `cvat-develop` là dependency ngoài kho P-029. Không coi một checkout GitHub là đã chứa CVAT/Docker/report API local hoặc dataset.

## 3. Kết quả 14 ca

Đạt trong bảng này là hoàn thành nội dung review của ca, không phải mọi chức năng được ca nhắc tới đã nghiệm thu.

| Mã | Kết quả cụ thể | Trạng thái | Bằng chứng / phần tiếp tục |
|---|---|---|---|
| R01-01 | 184 file baseline khớp inventory; phân biệt asset/generated/local; phân công đủ 02–08 | Đạt | EV-01-001; mục 2 |
| R01-02 | Truy vết P-010/P-011/P-012 và G0–G8, tách code khỏi nghiệm thu | Đạt | Mục 4; EV-01-003–007 |
| R01-03 | CLI, Web, extension, API report local được phân biệt; `diff` trả 3 vì chưa triển khai | Đạt | tests/test_cli; ledger L01/L02/L16 |
| R01-04 | Sáu nhóm detector và switches: floating, size, track, heading, fit, attributes | Đạt | scanner/check_*; R01-02; EV-01-005/007 |
| R01-05 | Dims/yaw/pose/frame đối chiếu convention; chuyển theo LIDAR_TO_EGO_ROT, manifest và roll/pitch được truy vết | Đạt | architecture mục 5; test reader thật và CVAT live; dấu quay được đính chính trong phần 02 |
| R01-06 | GET nhãn, snapshot, reports, PATCH flag theo tùy chọn; người dùng tự sửa hình học | Đạt | L03/L08/L09; 2 ca CVAT live |
| R01-07 | Thiếu LiDAR/pose/ground evidence không còn gate ĐẠT theo cấu hình mặc định | Đạt sau sửa | RV-01-001/003; EV-01-003/004/007 |
| R01-08 | Out/export vs ~/.pointsnap vs state memory phân biệt; done không có nghĩa gate passed | Đạt | architecture mục 3/5; Web persist test |
| R01-09 | Import JobData từ CVAT reader là coupling thật; sửa claim “core không import CVAT” | Đạt sau sửa | RV-01-005; L06 |
| R01-10 | TASKS/nhật ký/README đã gắn mốc lịch sử và tham chiếu hiện hành; không tự cập nhật nghiệm thu | Đạt sau sửa | RV-01-004 |
| R01-11 | Bảng metadata/số liệu tách snapshot; sửa recall 0/0 thành không xác định | Đạt sau sửa | RV-01-006; mục 5 |
| R01-12 | 3 sơ đồ và 17 quan hệ có nguồn; caller tạo report/PATCH, scanner trả findings | Đạt | 01-architecture.md |
| R01-13 | So CI Python 3.11/Node 22 với local 3.12.14/24.19.0; chạy cả 6 ca từng skip | Đạt | EV-01-007: 252 passed; CI chưa chạy tại lúc lập báo cáo |
| R01-14 | CVAT ngoài repo, local Docker/API/launcher tách khỏi bản công bố và có nhánh tiếp nhận | Đạt | Mục 2/7; EV-01-001/007 |

Tổng: **14 Đạt; 0 Lỗi; 0 Bị chặn; 0 Chưa chạy; 0 Không áp dụng**, trong phạm vi review 01 đã định nghĩa.

## 4. Truy vết yêu cầu và entry points

| Yêu cầu / giai đoạn | Code và hợp đồng | Test / bằng chứng đã chạy | Gap hoặc nhánh tiếp nhận |
|---|---|---|---|
| P-010: lơ lửng/lún | detectors/floating, core/ground, FrameSource, mặt đất/track/sweeps | floating/ground/wiring; ground nuScenes thật | Độ chính xác từng luật và precision xem tay: 02/07 |
| P-011: tiền QA/gate | scanner, gate, CLI gate_cmd, Web runner; snapshot/report/flag | test_scan_gate, test_gate_coverage, Web; gate không pass khi thiếu dữ liệu | Không kiểm đối tượng bị sót; gate chỉ theo rule/config |
| P-012: duyệt có hệ thống | Web preview/reviews, link ExtensionLink, extension core/DOM/API | test_web_a14/a15; Node core | Mức giảm thời gian thao tác và CVAT browser: 05/07 |
| G0: nhập cảnh/chốt tọa độ | NuScenesReader → export_scene/upload_scene → CVAT | test_to_cvat; reader thật; live upload/read-back | Hiển thị bằng mắt và ảnh camera: 03/05 |
| G1: ground/detector/ghi cờ | floating/size + writer/PATCH | ground thật; live flag/clear giữ hình học | Ground test threshold <15 cm khác tiêu chí sản phẩm <5 cm; chưa kết luận sản phẩm đạt threshold <5 cm |
| G2: scan → flag → sửa → gate | CLI/runner/report/writer | mock E2E, live API từng đoạn; 252 test cuối | Chưa chạy một chuỗi sửa nhãn bằng trình duyệt trong lượt này |
| G3: đủ chỉ số/xem tay | eval/metrics; reviews.json | Test metrics và Web reviews | Số xem tay, hồ sơ nộp chưa xác minh: 07/08 |
| G4/G5: extension E1–E6 | manifest/background/content/core + /api/extension | Node 7 ca và A15 API; docs/thu-extension là snapshot 08/10 | Spike/tiêu chí browser không chạy lại: 05 |
| G6: C1/C2 + task spec | heading/fit/attributes; taxonomy/spec-vn/add_track_markers | heading_fit/spec_rules/to_cvat trong suite | Task spec-vn và TC-70–80 bằng mắt: 02/03/05 |
| G7: số liệu cuối/precision | eval split, run_evaluation, 5 tuning/5 test scene | Metrics/synthetic tests; dataset reader thật | Chưa chạy lại eval 10 vòng hoặc xem tay: 07 |
| G8: test/video/report/slide | docs/test và hồ sơ đội | Test code của nhánh này đã đạt | Hồ sơ nộp/slide/video ngoài phạm vi 01: 08 |

| Entry point | Runtime và tác động |
|---|---|
| `pointsnap` / `python -m pointsnap` | pyproject/cli.main; scan/gate/config/nuscenes/eval/ui; diff khai báo nhưng chưa có |
| `pointsnap ui` | uvicorn `pointsnap.web.app:app`, mặc định 127.0.0.1:8765; FastAPI và static Web |
| `pointsnap nuscenes to-cvat --upload` | Xuất PCD/manifest/ground_truth rồi tạo task, upload ZIP và PUT annotation CVAT |
| `pointsnap eval` | Chèn lỗi giả, quét, tổng hợp; không huấn luyện ML |
| Extension Manifest V3 | Service worker gọi /api/ PointSnap; content script đọc cờ/CVAT DOM và chuyển frame |
| `python -m pointsnap.api` | Entry point local chưa tracked; không thuộc bản push phần 01, chuyển 04/06/08 |

## 5. Đối chiếu số liệu

| Tài liệu | Metadata xác định từ file | Thiếu / cách dùng |
|---|---|---|
| docs/danh-gia.md | 92,0% floating, 90,7% error; precision 17,6%/13,5%; báo nhầm 33,83/100 | Không có ngày chạy/commit/config hash/seed hoặc bằng chứng xem tay. Gắn snapshot lịch sử; recall track 0/0 không xác định |
| docs/ket-qua-danh-gia-tu-dong.md | Sau A10, 07/10, mini, 5 scene test/tuning, 10 vòng, config mặc định; 3,80 warning/0,85 error trên 100 box | Config hash/code SHA/seed của lần chạy chưa đủ; không so trực tiếp với số cũ thiếu metadata |
| docs/ket-qua-giai-doan-3.md + eval-giai-doan-3 | 10/10; 5 scene test, 5440 box; 10 vòng; catalog all; default guideline; baseline so sánh 6ed37fe. 3,42 warning/0,55 error trên 100 box | SHA code giai đoạn 3/config hash/seed thực tế không được lưu rõ trong báo cáo; đây là số liệu lịch sử, chưa phải eval chạy lại ở nhánh này |
| docs/thu-extension.md | 08/10; CVAT 2.77 local; job 2; 60 cờ/35 frame; thao tác browser lịch sử | Chưa đo lại trên CVAT 2.78.1 của máy này; không suy ra từ Node tests |
| Evidence review 01 | SHA sửa code/test, máy, config, dataset, lệnh và exit; 252 passed/Node 7 passed | Không phải phép đo precision/rework hay benchmark hiệu năng |

`run_evaluation` có seed mặc định 0 trong code, nhưng không suy ra các báo cáo cũ đã chạy đúng seed đó khi file không ghi. Mục tiêu giai đoạn 3 ≤2 warning/≤0,5 error trên 100 box chưa đạt theo snapshot test 10/10. Không đổi số liệu để làm đẹp kết luận.

## 6. Findings đã sửa và xác minh

Mã vị trí runtime dưới đây theo `099d5b7`, test live theo `7eb5421`; đường dẫn từ tool root. Cả 8 findings là lỗi có bằng chứng, không có finding P0.

### RV-01-001 — gate ĐẠT dù thiếu dữ liệu kiểm tra

- **P1 / Đã xác minh.** R01-07, P-011.
- Vị trí: `core/scanner.py:302`, `core/gate.py:11`, `cli/gate_cmd.py`, `web/runner.py`.
- Trước sửa: default config với box sạch, frames=None → findings trống và gate True; FrameSource có mặt nhưng thiếu pose vẫn có thể pass; `floating.no_evidence` bị bỏ qua khi tính gate.
- Tác động: có thể dùng kết luận chất lượng để nộp dù luật hình học/chuyển động chưa đủ dữ liệu.
- Sửa: helper coverage dùng rules đang bật; CLI/Web truyền gaps vào gate; missing ground evidence chặn verdict nhưng giữ INFO và không flag như lỗi hình học. Web lưu gaps/reasons; UI hướng dẫn bổ sung dữ liệu.
- Tái hiện/kiểm lại: `test_gate_coverage.py` nguồn vắng, NoPose mất pose frame 1, sparse ground; cả CLI và Web; size-only không bị buộc có cloud. EV-01-003/004/007.
- Nhánh tiếp nhận: 04/05/07 tiếp tục dùng hợp đồng này; API local chưa công bố cần áp dụng trước khi phát hành.

### RV-01-002 — iterable generator làm mất số cảnh báo trong gate

- **P2 / Đã xác minh.** Vị trí `core/gate.py:11`; hàm công khai nhận Iterable.
- Trước sửa: generator có 2 warnings, max_warnings=1; lượt lọc errors tiêu thụ generator, lượt lọc warnings rỗng → pass sai.
- Sửa: materialize iterable một lần. `test_gate_counts_warnings_in_a_generator` kiểm count 2 và fail. EV-01-003/007; commit `099d5b7`.

### RV-01-003 — gate CLI văng lỗi khi file frame thiếu sau khi tìm manifest

- **P2 / Đã xác minh.** Vị trí `cli/gate_cmd.py:34–43`.
- Điều kiện: FrameSource được tạo nhưng frame_data phát FileNotFoundError/KeyError/ValueError trong scan.
- Trước sửa: ngoại lệ thoát khỏi CLI, không theo hợp đồng mã runtime 3.
- Sửa: bắt lỗi dữ liệu quanh frames/scan/coverage, in lý do và trả 3. Web đã có trạng thái failed cho exception.
- Kiểm lại: `test_cli_gate_frame_read_failure_is_runtime_error`; EV-01-003/007, commit `099d5b7`.

### RV-01-004 — tài liệu khẳng định hoàn thành toàn sản phẩm quá mức

- **P2 / Đã xác minh tài liệu.** README source-tool khẳng định trọn bộ/G2, trong khi `diff` chưa có, G3/G7/G8 và số liệu/xem tay còn gap; TASKS/nhật ký ở các thời điểm khác nhau.
- Sửa: README tách code/bằng chứng lịch sử/nghiệm thu, bổ sung P-012, mô tả đầu vào LiDAR thực tế và nghĩa gate. TASKS/nhật ký giữ snapshot và link báo cáo hiện hành.
- Kiểm lại: test diff trả 3, bảng truy vết G0–G8, kiểm Markdown links. Không sửa trạng thái người phụ trách thành nghiệm thu mới.

### RV-01-005 — mô tả dependency và data flow sai

- **P2 / Đã xác minh tài liệu.** Đề xuất nói core không import CVAT, chỉ 3 detectors; bản nháp sơ đồ local có cạnh scanner→report/PATCH.
- Sửa tài liệu tracked: đề xuất nêu import JobData, đủ 6 nhóm detector và synthetic ở core; bổ sung `01-architecture.md` với 3 sơ đồ/17 quan hệ có code chứng minh. Bản nháp local không được đưa lên GitHub.
- Kiểm lại: L01–L17 đối chiếu import/lời gọi thật; scanner không gọi report/writer. Không refactor boundary chỉ để đạt sơ đồ lý tưởng.

### RV-01-006 — số liệu thiếu metadata và recall 0/0 ghi thành 0%

- **P2 / Đã xác minh tài liệu.** Vị trí `docs/danh-gia.md`, mục đánh giá trong README.
- Tác động: so sai phiên bản hoặc kết luận detector thất bại từ tập không có mẫu.
- Sửa: 0/0 là không xác định/chưa đủ dữ liệu; đánh dấu snapshot lịch sử, chỉ rõ báo cáo giai đoạn 3 và thiếu metadata. Giữ các số liệu còn lại.
- Kiểm lại: đối chiếu mẫu số, bảng mục 5 và Markdown links. Metadata đánh giá tương lai giao 07; không tự gán commit/seed cho lịch sử.

### RV-01-007 — test dotenv để token giả ảnh hưởng test CVAT thật

- **P2 / Đã xác minh.** Vị trí `tests/test_cli.py:test_load_dotenv_sets_missing_vars_only`.
- Tái hiện: chạy suite với live enabled khi process chưa có CVAT_TOKEN; monkeypatch.delenv không ghi lại key vốn vắng; load_dotenv tự ghi token giả vào env; test live đọc .env bằng setdefault không ghi đè → HTTP 401. Chạy live riêng thì pass.
- Sửa: monkeypatch một bản sao `os.environ` cho test dotenv, không sửa loader/token người dùng.
- Kiểm lại: full suite live **252 passed, 0 skipped**. EV-01-007; commit `7eb5421`.

### RV-01-008 — ground test bỏ qua dataset được cấu hình ngoài tool/data

- **P2 / Đã xác minh.** Vị trí `tests/test_ground.py:test_estimate_ground_real_nuscenes`.
- Trước sửa: hardcode tool/data/nuscenes nên skip dù dataset thật có trong Downloads và NUSCENES_ROOT được đặt.
- Sửa: ưu tiên NUSCENES_ROOT, fallback đường dẫn cũ; giữ threshold/assertions.
- Kiểm lại: ca ground đã chạy trên mini thật cùng 3 reader tests và 2 live CVAT tests; full suite 0 skip. EV-01-007; commit `7eb5421`.

## 7. Quyết định và bàn giao

| Mục | Quyết định / giới hạn | Tiếp nhận |
|---|---|---|
| Gate thiếu dữ liệu | KHÔNG ĐẠT nếu gap được nhận diện theo luật bật; có no_evidence thì chặn. Scan vẫn cung cấp phần findings đã kiểm | 04/05/07 |
| Rule chủ động tắt | ĐẠT chỉ theo config; không chứng nhận phần tắt; không thêm bypass “allow partial” mặc định | 02/04/06 |
| Coverage bảo thủ | Kiểm cấp job/source/pose và no_evidence; không phải tỷ lệ mọi box/luật, không chứng nhận class ngoài phạm vi | 02/07: rà từng rule applicability/low-point/timestamp fallback |
| Frame/world invariants | Convention hiện có, LIDAR_TO_EGO_ROT và metadata khớp reader; giữ roll/pitch và geometry khi PATCH | 02/03 |
| API report local | Có `passed` và danh sách checks riêng trong untracked api.py; trước khi công bố cần dùng chung coverage/gate và đủ 6 nhóm luật | 04/06/08 |
| Local Docker/launcher | Ngoài nội dung push phần 01; không chứng nhận cài máy trắng dựa vào container đang chạy | 08 |
| Hình học/precision | NuScenes reader/ground và CVAT API pass không chứng nhận precision hoặc threshold ground <5 cm | 02/07 |
| Browser/extension | Chưa làm lại spike/visual QA; Node/API mock không thay thế bằng chứng browser | 05 |
| Số liệu eval | Cần commit/config hash/seed/data/catalog/rounds và precision xem tay khi chạy mới | 07 |
| Môi trường | CI 3.11/22 và CVAT chuẩn 2.77 khác local 3.12/24/2.78.1; cần ma trận tương thích | 08 |
| PR | Hân yêu cầu đẩy nhánh không có ngày; người khác mở PR. Main không được merge trong lượt này | Người nhận bàn giao |

## 8. Kết luận bàn giao

Phần 01 đã hoàn tất ở phạm vi yêu cầu/kiến trúc. **9 findings đã sửa; 0 findings mở trong phần 01.** Các gap cần review sâu được bàn giao rõ ở mục 7, không được hiểu là sản phẩm đã sẵn sàng phát hành.

Kết quả ban đầu: **252 Python tests passed, 0 skipped; 7 Node tests passed**. 2 test live đã tạo/xóa task thử; kiểm tra sau chạy tìm `PointSnap live test` trả **0 task còn lại**. 1 warning Starlette/httpx được ghi lại, không tắt hoặc thêm dependency để che warning.

Nhánh giao cho người mở pull request: **`review/01-overview-architecture`**. Code và tài liệu tách commit; chỉ stage file liên quan. `.env`, dataset, output, snapshot và các file local khác được giữ ngoài commit.

## 9. Kiểm lại sau khi hoàn tất ba nhánh

### RV-01-009 — cloud rỗng khi tắt floating vẫn cho gate ĐẠT

- **P1 / Đã xác minh.** `core.scanner.scan_coverage_gaps`: FrameSource tồn tại nhưng points rỗng chưa được tính là thiếu dữ liệu. Khi floating tắt, heading_points/fit_empty/fit_outside/fit_loose có thể không có finding và gate trả ĐẠT.
- Trước sửa: 4 failed, 13 deselected in 0.74s; đủ 4 luật có ca tái hiện độc lập.
- Sửa: đọc points của frame nhìn thấy và báo coverage gap nếu rỗng, chỉ cho luật cần LiDAR đang bật. Lỗi đọc frame vẫn chuyển caller xử lý runtime.
- Commit sửa `0727c15`; kiểm lại nhánh 01: **256 passed, 0 skipped, 1 warning in 22.96s**; bật CVAT và dataset thật. Bản sửa được đưa sang 02/03 theo chuỗi dependency.
- Đính chính dấu quay trong kiến trúc/tài liệu: ma trận thực tế là −90°, không phải +90°. Đây là sửa diễn giải, không đổi code hình học.
