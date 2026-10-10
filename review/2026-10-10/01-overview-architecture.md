# 01 — Review yêu cầu, tổng quan và kiến trúc

**Nhánh:** `review/2026-10-10/01-overview-architecture`.
**Trạng thái:** đang thực hiện; mới có kiểm kê và kiểm tra ban đầu.
**Đầu ra sẽ tạo:** `01-report.md`, sơ đồ hiện trạng, bảng truy vết yêu cầu và danh sách quyết định còn mở.

Đọc [quy trình chung](README.md) và [mẫu báo cáo](report-template.md) trước khi thực hiện. Đường dẫn code bên dưới tính từ tool root.

## 1. Mục tiêu và câu hỏi cần trả lời

1. PointSnap giải quyết P-010/P-011/P-012 bằng chức năng nào? Có phần nào đang được quảng bá nhưng chưa triển khai hoặc chưa nghiệm thu?
2. Luồng nuScenes → CVAT → scanner → report/gate → người sửa nhãn đi qua những module nào?
3. Mỗi đầu vào/đầu ra có hợp đồng gì: tọa độ, frame, ID, schema, cấu hình, trạng thái scan và điều kiện dữ liệu?
4. Khi thiếu LiDAR/pose hoặc dịch vụ lỗi, người dùng biết phần nào đã kiểm và phần nào chưa được kiểm không?
5. Các tài liệu tiến độ và số liệu đang nói về cùng phiên bản, cùng config và cùng dữ liệu không?

## 2. Tài liệu và code cần đọc

| Nhóm | Điểm đọc | Nội dung cần rút ra |
|---|---|---|
| Bối cảnh đội | README gốc, `problem-backlog.md`, `so-quyet-dinh.md`, `nhat-ky-tuan/` ở kho Git | Pain point, quyết định guideline, vai trò và bằng chứng tiến độ |
| Cam kết sản phẩm | `../README.md`, `de-xuat-de-tai.md`, `TASKS.md`, `giao-viec/` | Phạm vi từng giai đoạn, điều kiện G0–G8, phần ngoài phạm vi |
| Hợp đồng miền | `CONVENTIONS.md`, `pointsnap/core/model.py`, `pointsnap/core/config.py`, config và guideline | Đơn vị, tọa độ, keyframe/outside/occluded, finding và rule switches |
| Entry points | `pyproject.toml`, `pointsnap/__main__.py`, `pointsnap/cli/main.py`, `pointsnap/web/app.py`, `extension/manifest.json` | CLI, Web API/UI, extension; các tiến trình thật sự chạy |
| Điều phối | `pointsnap/core/scanner.py`, `pointsnap/cli/common.py`, `pointsnap/web/runner.py`, `pointsnap/web/projects.py` | Dependency, data availability, lưu file và scan nền |
| Import và đánh giá | `pointsnap/datasets/nuscenes/to_cvat.py`, `pointsnap/eval/evaluate.py`, `pointsnap/eval/split.py` | Luồng demo và luồng đánh giá, tránh nhầm với huấn luyện |
| Tài liệu cục bộ | `ARCHITECTURE.md`, `ARCHITECTURE_DIAGRAMS.md`, `pointsnap/api.py` chưa theo dõi | Đối chiếu từng claim/edge với code hiện tại; ghi rõ phạm vi local |

## 3. Trình tự thực hiện

1. Chốt mốc review và kiểm kê file từ `git ls-files`; ghi file cục bộ riêng. Bản kiểm kê ban đầu có **184 file nguồn/tài liệu được theo dõi** tại `5dcc97f`.
2. Lập bảng yêu cầu ↔ code ↔ test ↔ tài liệu ↔ bằng chứng thực tế. Đánh dấu riêng “đã có code” và “đã xác minh”.
3. Theo dõi entry point đến module xử lý và tác động bên ngoài. Đọc cả nhánh thành công, lỗi, thiếu dữ liệu và tùy chọn gắn cờ.
4. Ghi ledger mỗi quan hệ trước khi vẽ sơ đồ: nguồn, đích, import/lời gọi/dữ liệu, file/hàm chứng minh.
5. Đối chiếu tài liệu kiến trúc, tiến độ và số liệu. Giữ tài liệu lịch sử nhưng gắn phiên bản/ngày và đường dẫn tài liệu hiện hành.
6. Lập findings, quyết định cần chốt và bàn giao cho phần 02–08. Không mở rộng phần này thành kiểm tra độ đúng mọi detector.

## 4. Checklist và bằng chứng

| Mã | Kiểm tra | Mong đợi / bằng chứng tối thiểu |
|---|---|---|
| R01-01 | Kiểm kê toàn kho | Mỗi file có phần review phụ trách; tài liệu/generated/vendor/asset được phân biệt |
| R01-02 | Truy vết yêu cầu P-010/P-011/P-012 và từng giai đoạn | Mỗi yêu cầu có module, test và trạng thái xác minh; thiếu thì ghi gap |
| R01-03 | Danh sách entry points | CLI/UI/extension và report API local được phân biệt; `diff` ghi đúng là chưa triển khai |
| R01-04 | Các nhóm luật hiện tại | Bản đồ bao gồm floating, size, track, heading, fit và attributes; kiểm rule switches thực tế |
| R01-05 | Quy ước hình học và frame | Tài liệu mô tả dims/yaw/pose/frame theo CONVENTIONS; nhánh chuyển đổi được chỉ ra |
| R01-06 | Luồng đọc và ghi CVAT | Reader, snapshot, report, tùy chọn PATCH và người sửa nhãn được thể hiện đúng |
| R01-07 | Thiếu LiDAR/pose/manifest | Ghi chính xác luật bị bỏ qua hoặc dùng dữ liệu kém chắc; đối chiếu ý nghĩa gate |
| R01-08 | Persistence/runtime | Phân biệt file trong dự án, dữ liệu `~/.pointsnap`, state trong memory và phụ thuộc ngoài |
| R01-09 | Dependency direction | Chỉ ra core/scanner import `JobData` từ CVAT reader; đánh giá tác động, tránh đề xuất tách lớp khi chưa cần |
| R01-10 | Code ↔ tiến độ | So TASKS, nhật ký tuần 04 và hướng dẫn test; ghi snapshot cũ và kết luận được code hiện tại hỗ trợ |
| R01-11 | Code ↔ số liệu | Bảng mỗi báo cáo có commit/config/data/seed; số thiếu metadata chưa được coi là kết quả hiện tại |
| R01-12 | Sơ đồ có bằng chứng | Không có edge vô căn cứ; scanner trả findings, CLI/runner gọi generator báo cáo |
| R01-13 | CI và môi trường | Đối chiếu Python/CVAT/Node và test skip; không suy ra CVAT thật đã đạt từ mock |
| R01-14 | Phạm vi ngoài repo | CVAT là dependency ngoài; launcher cục bộ và Docker/API local có mục bàn giao 08/04 |

Trạng thái từng ca điền vào báo cáo; checklist này không tự đánh dấu Đạt.

## 5. Bảng truy vết cần điền

| Yêu cầu | Nguồn yêu cầu | Module/hợp đồng | Test liên quan | Bằng chứng thật | Trạng thái / gap |
|---|---|---|---|---|---|
| Phát hiện lơ lửng/lún | P-010, đề xuất | floating, ground, FrameSource | floating/ground/wiring | Chưa tổng hợp | Chưa xác minh đầy đủ |
| QA trước review và gate | P-011, đề xuất | scanner, gate, CLI/runner | scan_gate, wiring | Kiểm tra thiếu LiDAR bên dưới | Cần chốt coverage |
| Duyệt tuần tự và ghi kết luận | P-012, A14/A15 | preview/reviews/link/extension | web_a14, web_a15, Node core | Chưa kiểm trình duyệt | Chuyển 05 |
| Import/ghi cờ giữ nhãn | A2–A4 | converter, CVAT adapter/writer | to_cvat, writer, live_cvat | Chưa chạy CVAT thật trong đợt này | Chuyển 03 |
| Đánh giá luật theo spec | C1/C2, đề xuất | heading/fit/attributes/spec-vn/eval | heading_fit, spec_rules, metrics | Báo cáo cũ cần metadata | Chuyển 02/07 |

## 6. Kiểm tra tập trung

```powershell
python -m pytest -q tests/test_cli.py tests/test_scan_gate.py tests/test_scan_wiring.py
```

**Bằng chứng đã có từ lượt trước, 10/10/2026:** trên Python 3.12.14, sau xử lý đường dẫn thư viện và thư mục tạm theo README chung, lệnh tương đương cho kết quả **19 passed in 1.52s**. Đây là 3 file test, không phải toàn bộ suite hoặc môi trường chuẩn Python 3.11.

Kiểm tra dữ liệu giả đã chạy: dùng `car(0)`, `car(1, bottom=0.4)`, `car(2)` và `FlatGround` trong `tests/test_scan_wiring.py`; config mặc định với `env={}`. Có LiDAR: có `floating/error`, gate=False. Không LiDAR: findings=[], gate=True. Dữ liệu mặt đất giả cũng tạo finding `fit.empty`; đây là kiểm tra phạm vi thực thi luật, không đo precision detector trên dữ liệu thật.

**Mục cần chốt, chưa sửa:** gate hiện đánh giá findings và chưa nhận thông tin coverage. Cần xác định kết luận ĐẠT khi thiếu dữ liệu có được dùng để nộp nhãn không, hoặc phải báo kiểm tra một phần. Chủ trì hợp đồng ở 01; triển khai/hiển thị ở 04/05; kiểm luật ở 02; hồi quy ở 07.

## 7. Bàn giao và điều kiện hoàn tất

- [ ] Báo cáo có danh sách entry points, luồng thành công/lỗi và ledger quan hệ.
- [ ] Có sơ đồ context, module và scan flow nhỏ, mọi edge có nguồn chứng minh.
- [ ] Bảng yêu cầu ↔ module/test/bằng chứng không bỏ quên giai đoạn 3 hoặc extension.
- [ ] Tài liệu mâu thuẫn được ghi finding với vị trí và phiên bản.
- [ ] Kết luận gate thiếu dữ liệu và giới hạn product được ghi rõ để phần sau dùng.
- [ ] 184 file nền được kiểm kê; có người/phần phụ trách kiểm sâu cho các file còn lại.
- [ ] `01-report.md` được commit trên nhánh 01; findings còn mở có mã và nhánh tiếp nhận.

Kết quả cần đọc ở phần sau: bảng invariant cho 02/03, bản đồ entry points cho 04/05/06, giới hạn số liệu cho 07, các file local và snapshot tài liệu cho 08. Hoàn tất phần 01 không đồng nghĩa đã nghiệm thu toàn sản phẩm.
