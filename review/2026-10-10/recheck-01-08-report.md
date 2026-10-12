# Soát và sửa các nhánh review để merge

Ngày **12/10/2026**, Asia/Saigon. Phạm vi: tám nhánh kết quả `review/01-*` đến
`review/08-*`. Các sửa được commit và push vào **chính các nhánh hiện có**.
Các tính năng mới trên main ngoài phạm vi review; main được đồng bộ vào các nhánh
để giải quyết xung đột và kiểm tra khả năng merge. Không merge vào main tự động.

## Kết quả

Đã đọc lại diff, truy vết các luồng gọi và chạy Python/Node suite từ archive sạch
của từng đầu nhánh. Phát hiện và sửa **7 nhóm lỗi**, thêm 15 ca Python và 1 ca Node.
Đã kiểm ba mốc riêng: bản cũ trên remote, bản sửa từng nhánh, bản sau đồng bộ main.
Kết quả lịch sử được giữ nguyên, kể cả một lần FAIL do timing ở nhánh 06.

### Các đầu nhánh sau đồng bộ main

SHA dưới đây là mốc mã nguồn đã chạy test. Nhánh 08 nhận thêm commit báo cáo sau
mốc này; mã nguồn và tests giữ nguyên. PASS, SKIP và XFAIL được đếm riêng.

| Nhánh | SHA đã kiểm | Python PASS / FAIL / SKIP / XFAIL | Node PASS |
|---|---|---|---|
| `review/01-overview-architecture` | `65ee0fe` | 353 / 0 / 4 / 1 | 7 |
| `review/02-core-detectors` | `aa67798` | 420 / 0 / 4 / 1 | 7 |
| `review/03-data-cvat-integrations` | `f0bd5ec` | 469 / 0 / 5 / 1 | 7 |
| `review/04-backend-cli-reports` | `4efee4a` | 542 / 0 / 5 / 1 | 7 |
| `review/05-frontend-extension` | `6bd8984` | 542 / 0 / 5 / 1 | 22 |
| `review/06-security-config` | `7bd5dd2` | 575 / 0 / 5 / 1 | 36 |
| `review/07-tests-evaluation-performance` | `0d5dcb5` | 599 / 0 / 5 / 1 | 37 |
| `review/08-deployment-docs-final` | `1a39b6f` | 602 / 0 / 5 / 1 | 37 |

Gate cuối trên checkout 08 với mini thật và CVAT 2.78.1: **605 Python
PASS, 0 FAIL, 2 SKIP, 1 XFAIL;
37 Node PASS**. Hai ca SKIP cần PyTorch thuộc tính năng main mới;
XFAIL là giới hạn ground slope đã ghi sẵn trên main, không tính PASS.
Ba test CVAT thật tự tạo và xóa task thử riêng. Suite từng archive tắt CVAT live
có chủ đích; không gán kết quả live hồi tố cho mọi nhánh.

## Các sửa trong lượt review

| Mã | Mức | Vấn đề / cách sửa | Nhánh đầu tiên / commit |
|---|---|---|---|
| RRC-01 | P1 | Job xếp hàng từ CVAT-A có thể chạy/ghi ở CVAT-B sau khi đổi URL/PAT. Lưu `source_cvat_url` khi enqueue; URL thiếu hoặc thay đổi làm run thất bại trước khi tạo client. So URL sau bỏ dấu `/` cuối, không phụ thuộc helper của nhánh 06. | 01 / `83d9cc4` |
| RRC-02 | P2 | API report ghép `/api/labels?page=2` thành `/api/api/labels?page=2`. Dùng `urljoin`, kiểm scheme/host/port và từ chối credentials/foreign origin trước request. | 04 / `f0ed40a` |
| RRC-03 | P2 | JSON `1e999` và `-1e999` lọt qua `parse_constant`, trở thành infinity trong state. `parse_float` kiểm hữu hạn tại `read_json`; vẫn giữ số hữu hạn như `1e300`. | 04 / `f0ed40a` |
| RRC-04 | P2 | Integer lớn trong YAML làm `math.isfinite` ném `OverflowError` thay vì `ConfigError`. Bắt overflow trong helper hữu hạn dùng chung cho scalar/range. | 02 / `777d94d` |
| RRC-05 | P2 | Eval so độ lệch kích thước tính mét với injection tính ratio. Lấy `relative_diff`, ghi `measured_unit=ratio`, loại outcome cũ không rõ đơn vị khỏi size accuracy. Fixture 4 m → 5,2 m cho sai số 0 thay vì 90 điểm phần trăm. | 07 / `127e743` |
| RRC-06 | P2 | Response lưu kết nối A tới sau khi chuyển B có thể reload và xóa draft token B. Kiểm project scope trước toast/reload; test deferred giữ nguyên draft B. | 05 / `39006cf` |
| RRC-07 | P2 | Eval archive dưới checkout cha ghi nhầm Git HEAD của cha. Chỉ ghi SHA khi evaluator được track đúng vị trí; ghi hash evaluator và trạng thái dirty. Archive ngoài source ghi `source_commit=None`. | 07 / `127e743` |

Đã đưa sửa timing của test HTTP về 04 (`269b2de`) rồi truyền qua 05–08: chờ cả
hai semaphore slot được giải phóng sau khi client nhận body. Không đổi logic API.
Các sửa phía trước được merge vào nhánh phía sau; ancestry 01 → 08 và ancestry
của toàn bộ đầu nhánh remote cũ đều đã kiểm.

## Giải quyết xung đột phục vụ merge

Mô phỏng ban đầu với main `be1778c` có 3–9 file xung đột tùy
nhánh. Sau đồng bộ, **cả 8 nhánh có main trong lịch sử và `git merge-tree` trả 0,
không còn file xung đột** tại mốc đã kiểm.

- 01: giữ cảnh báo review trong README; sửa liên kết sau khi TASKS chuyển vào
  `quan-ly/`; dùng chung nguồn dataset của test, không nạp PAT vào test dữ liệu.
- 02: giữ tìm điểm theo x của main, kết hợp bán kính đường chéo của sửa review
  cho box xoay; giữ trung vị góc tính từ các box khác để box outlier không tự
  định hướng reference; giữ cả helper size hiện có của main và sửa phân nhóm.
- 07: giữ wrapper dùng evaluator chính, không phục hồi script ghi đè docs lịch sử.
- 08: giữ README/cài đặt đã chuyển đường dẫn, thêm hướng dẫn package và giới hạn
  review; giữ cách chạy Python trực tiếp khi PowerShell chặn activate.

**Merge theo thứ tự 01 → 02 → 03 → 04 → 05 → 06 → 07 → 08**, dùng merge commit
hoặc fast-forward để giữ ancestry của chuỗi. Nếu chỉ cần toàn bộ kết quả cộng dồn,
nhánh 08 chứa các đầu nhánh 01–07. Tránh squash từng nhánh nối tiếp vì làm mất
ancestry và lặp diff ở nhánh sau. Kết luận không xung đột áp dụng với main SHA đã
ghi; nếu main đổi sau đó cần kiểm lại mô phỏng merge.

Các nhánh local `review/2026-10-10/01-*`…`08-*` cùng SHA `22a01f5` là snapshot
hướng dẫn ban đầu; `review/main-2026-10-10` là mốc nền. Chúng không phải tám nhánh
kết quả để merge. Nhánh recheck tạm chưa từng push, đã chuyển sửa vào nhánh gốc
và được dọn khỏi local trước bàn giao.

## Bằng chứng và giới hạn

- [Snapshot remote trước sửa](evidence/recheck-01-08/branch-results.json):
  nhánh 06 có một FAIL `test_local_api_http_error_mapping_and_slot_release[422]`.
- [Từng nhánh sau sửa](evidence/recheck-01-08/repaired-branch-results.json),
  [từng nhánh sau đồng bộ main](evidence/recheck-01-08/merge-ready-branch-results.json),
  [mô phỏng merge trước/sau](evidence/recheck-01-08/merge-check.json),
  [gate cuối](evidence/recheck-01-08/verification.json),
  [probe trước sửa](evidence/recheck-01-08/probes-before.json).
- Regression tests: `test_queue_cvat_scope.py` (01),
  `test_numeric_config_recheck.py` (02), `test_backend_recheck.py` (04),
  `extension/tests/review05.test.js` (05), `test_evaluation_recheck.py` (07).
- `measurement_accuracy.size_in_track` ở output 07 cũ không dùng để kết luận
  vì lệch đơn vị. Giữ raw evidence; không tự quy đổi hoặc gán metadata mới cho
  output lịch sử. Không chạy lại evaluation 10 cảnh × 10 vòng/benchmark trong
  lượt này. Số liệu quality trước đồng bộ main không đại diện main mới.
- Precision xem tay và MV3 thật chưa có kiểm tra mới. GET cuối → PATCH CVAT
  vẫn không nguyên tử; cần phối hợp Save khi dùng tool. LAN/HTTPS, server BTC,
  restore DB và rollback đầy đủ vẫn theo giới hạn trong báo cáo 08 cũ.
- Hai tests PyTorch và XFAIL ground slope là các giới hạn được kế thừa từ main;
  các tính năng mới trên main chưa được review hoặc nghiệm thu trong lượt này.
- Có một warning Starlette TestClient/httpx deprecation. Docker/CVAT đã chạy;
  không cần người dùng bật thêm. Giữ file local của người dùng; không commit
  `.env`, dataset, raw annotations, archive hoặc logs chạy test.
