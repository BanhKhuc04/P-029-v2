# 07 — Review kiểm thử, đánh giá và hiệu năng

**Nhánh:** `review/07-tests-evaluation-performance`.
**Trạng thái:** đã review/sửa ngày12/10;490pytest+36Node, eval10cảnh vàbenchmark; giới hạn quality/manual rõ trong [báo cáo](07-report.md), [bàn giao](07-handoff.md).
**Đầu ra sẽ tạo:** `07-report.md`, ma trận yêu cầu ↔ test, bảng metrics có metadata, khoảng trống kiểm thử và benchmark tái lập.

Đọc [quy trình chung](README.md), [mẫu báo cáo](report-template.md), `docs/test/CHUAN-KIEM-THU.md` và findings 01–06. Đường dẫn code tính từ tool root.

## 1. Mục tiêu

Đánh giá mức tin cậy của bằng chứng kiểm thử và chất lượng rule; kiểm kết quả có tái lập, đo đúng đại lượng và đại diện đúng phạm vi. Test phần mềm đạt, finding nhãn, độ chính xác detector và hiệu quả người dùng là các đại lượng khác nhau, phải có bảng riêng.

## 2. Phạm vi

| Nhóm | File | Cần kiểm |
|---|---|---|
| Test Python | `tests/`, conftest, fake_nuscenes | Fixture độc lập, đáp án, isolation, skip và side effects |
| Test extension | `extension/tests/core.test.js`, code JS và manifest | Logic đã được kiểm, phần DOM/permission chưa được kiểm tự động |
| Evaluation | `pointsnap/core/synthetic.py`, `pointsnap/eval/evaluate.py`, `metrics.py`, `split.py` | Injection, matching, precision/recall, denominator và split |
| Scripts | `scripts/run_eval_suite.py`, `eval_metrics.py`, `verify_ground.py`, `build_size_stats.py` | Tham số, output, dữ liệu/phiên bản được dùng |
| CI | `.github/workflows/test.yml` ở kho Git | Trigger/versions, hai jobs Python/extension, skip, dependency và parity local |
| Bằng chứng | `docs/danh-gia.md`, `ket-qua-danh-gia-tu-dong.md`, `ket-qua-giai-doan-3.md`, `eval-giai-doan-3/`, báo cáo test | Cùng mốc hay snapshot khác; metadata và giới hạn số liệu |
| Runner cục bộ | `auto-tests/`, checklist/map, `tests/test_report_api.py` | Tái dùng test, mapping không khẳng định UI đã đạt; file chưa thuộc baseline |

## 3. Thứ tự

1. Chốt commit/config/guideline/dataset/version; phân nhóm mock, synthetic, dataset thật, CVAT thật và trình duyệt.
2. Lập ma trận yêu cầu ↔ ca ↔ bằng chứng từ findings 01–06, đánh dấu không có test hoặc test yếu.
3. Chạy full suite và Node checks ở môi trường chuẩn hoặc ghi rõ môi trường thay thế; lưu pass/fail/skip/mã thoát.
4. Review logic evaluation bằng fixture biết TP/FP/FN và matching; chạy synthetic nhỏ trước khi dùng dataset thật.
5. Đánh giá trên tuning và test riêng; chốt config trước khi lấy số test, ghi mọi lần tái dùng test để tránh che việc tối ưu trên test.
6. Xem tay finding để đo precision thật; chọn mẫu theo quy trình có thể lặp lại, không chỉ chọn ca rõ nhất.
7. Benchmark đọc data/scanner/report/HTTP riêng và end-to-end; so với mốc cùng máy/config/data, bàn giao giới hạn vận hành.

## 4. Checklist test quality

| Mã | Ca | Mong đợi / bằng chứng |
|---|---|---|
| R07-01 | Thu thập full suite | Ghi số collected/pass/fail/skip/error, duration và exit code; không cộng test chưa chạy |
| R07-02 | Fixture và đáp án độc lập | Không lấy chính function đang test làm oracle; ca hình học/marker có tính tay hoặc tính chất bất biến |
| R07-03 | Isolation môi trường và filesystem | Conftest cwd tạm chặn .env cá nhân; phân biệt các test cố ý đọc .env của tool |
| R07-04 | CVAT thật và cleanup | Switch opt-in, task thử, cleanup ngay cả khi lỗi; skip có lý do, không dùng job công việc |
| R07-05 | Dataset thật thiếu/hỏng | Skip hay error đúng tình huống; không dùng test synthetic làm bằng chứng real data |
| R07-06 | Regression findings 01–06 | Mỗi lỗi quan trọng có ca tái hiện trước sửa và kết quả sau sửa; kiểm scope ảnh hưởng |
| R07-07 | Test boundary/config/rule switches | Bao gồm ngưỡng, thiếu dữ liệu, outside/occluded và backward compatibility |
| R07-08 | CI ↔ local và extension | Python/Node/dependency được ghi; Node logic/syntax/manifest khác test browser thực |
| R07-09 | Auto-tests checklist mapping | Mỗi mã có test thực sự đã chạy; PASS chỉ cho phạm vi code; MANUAL/NOT_RUN không bị đổi thành Đạt |

## 5. Checklist metrics và dữ liệu

| Mã | Ca | Mong đợi / bằng chứng |
|---|---|---|
| R07-10 | Injection log ↔ nhãn lỗi | Đúng loại/magnitude/box/frame/id/seed; lỗi chèn không bị loại ngoài phạm vi mà vẫn tính vào denominator không rõ |
| R07-11 | Matching finding ↔ injected error | Đúng rule/loại/frame/track/tolerance; không đếm lặp TP hoặc nhận công của lỗi khác |
| R07-12 | TP/FP/FN theo loại và severity | Recall=TP/(TP+FN), precision=TP/(TP+FP), cách matching/dedup được ghi; mẫu 0 không báo 0% như kết luận hiệu quả |
| R07-13 | False alarms trên nhãn chuẩn | Ghi finding/100 box hay box có finding/100 box, warning/error tách; nhãn chuẩn có thể có lỗi thật |
| R07-14 | Coverage và đối tượng đủ bằng chứng | Công bố mẫu đủ điểm/pose/class/frame, số excluded/skipped và số toàn bộ; tránh báo recall subset như recall toàn dataset |
| R07-15 | Split tuning/test | Theo `eval/split.py`; stats/ngưỡng chỉ từ tuning; ghi cấu hình trước held-out test |
| R07-16 | Xem tay và precision thật | Số review theo rule/class/scene và cách chọn; verdict rõ; không xem lỗi chưa gán box là đã có detector missing-object |
| R07-17 | So báo cáo khác ngày/commit | Mỗi bảng có version/config/seed/rounds/dataset; khác 5.478 và 5.440 box phải giải thích trước so sánh |
| R07-18 | Ít mẫu và khoảng tin cậy | Ghi n/N thay vì chỉ %; kết quả 1/1 hoặc 2/2 không được suy ra hiệu quả rộng |

Split hiện tại: tuning = scene-0061, scene-0553, scene-0757, scene-0916, scene-1094; test = scene-0103, scene-0655, scene-0796, scene-1077, scene-1100. Kiểm lại file split nếu commit đổi.

## 6. Checklist hiệu năng

| Mã | Ca | Mong đợi / bằng chứng |
|---|---|---|
| R07-19 | Scan cold/warm, có/không sweeps | Cùng dataset/config; ghi từng lần, startup/I/O/core riêng, min/median/max và điều kiện cache |
| R07-20 | RAM/CPU, số box/điểm/frame | Có mẫu nhỏ/lớn và resource measurement; nguyên nhân cost được đối chiếu code |
| R07-21 | Hai scan/report đồng thời và queue | Không lẫn kết quả; ghi throughput/latency/limit/timeouts; chỉ tạo tải trong môi trường thử |
| R07-22 | Chi phí preview/poll/reviews/report | Payload/điểm tối đa/polling và thời gian đọc được đo; không quy mọi chậm về detector |
| R07-23 | Mục tiêu sản phẩm | Đối chiếu mục tiêu <2 phút/cảnh và ≤2 warning/≤0,5 error trên 100 box theo đề xuất; nêu config và phạm vi áp dụng |

Không dùng số ~2 giây/cảnh ở README làm baseline giai đoạn 3 nếu chưa đồng nhất config. Tài liệu `ket-qua-giai-doan-3.md` ghi 5–35 giây/cảnh và false alarms 3,42 warning/0,55 error trên 100 box ở tập test; đây là số lịch sử phải tái lập hoặc ghi rõ chưa tái lập.

## 7. Lệnh dự kiến

```powershell
python -m pytest -q
node --test extension/tests/core.test.js
Get-ChildItem extension\background.js,extension\options.js,extension\src\*.js | ForEach-Object { node --check $_.FullName; if ($LASTEXITCODE -ne 0) { throw 'JS syntax check failed' } }
node -e "JSON.parse(require('fs').readFileSync('extension/manifest.json', 'utf8'))"
```

Dataset/config đã chốt, kết quả ngoài Git:

```powershell
python -m pointsnap eval --scenes tuning --rounds 10 --seed 0 --errors all --out out/review07/tuning
python -m pointsnap eval --scenes test --rounds 10 --seed 0 --errors all --out out/review07/test
```

Chạy từ tool root, với NUSCENES_ROOT đã cấu hình. Config thay thế dùng global `--config` trước subcommand; lưu bản config và checksum ở vị trí bằng chứng riêng. Chạy test held-out sau khi đã chốt thay đổi trên tuning; log mọi lần chạy.

Runner local khi có đủ file: `auto-tests/Run-Tests.ps1` cho chế độ mặc định; Online/Dataset/LiveCvat được chọn riêng theo README của runner. Không mặc định bật LiveCvat. Kết quả runner không thay thế xem tay hoặc test trình duyệt.

## 8. Mẫu bảng số liệu

| Commit/config/data | Rule / lỗi chèn | TP | FP | FN | n đủ điều kiện / N toàn bộ | Precision/recall | Warning/error trên 100 box | Giới hạn |
|---|---|---|---|---|---|---|---|---|
| Chưa điền | Chưa điền | Chưa đo | Chưa đo | Chưa đo | Chưa điền | Chưa đo | Chưa đo | Chưa tái lập |

## 9. Hoàn tất và bàn giao

- [ ] Có test matrix và số pass/fail/skip/error chính xác; skip không được tính Đạt.
- [ ] Metrics có n/N, matching/dedup, coverage, commit/config/seed/data và nguồn của ground truth.
- [ ] Precision xem tay và số liệu synthetic tách rõ; hạn chế mẫu/dataset được công bố.
- [ ] Benchmark có cùng điều kiện so sánh, đo I/O/core/output và tài nguyên.
- [ ] Test hồi quy findings quan trọng được chạy; phần browser/CVAT thật chưa làm có trạng thái rõ.
- [ ] `07-report.md` chuyển 08 bảng chất lượng hiện tại, giới hạn vận hành và gate chưa đạt; không tự xác nhận sản phẩm sẵn sàng.
