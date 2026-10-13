# Báo cáo phần 04 — Backend, CLI và báo cáo

Ngày thực hiện: **11/10/2026, Asia/Saigon**. Người thực hiện/kiểm lại: Codex trong chat phần 04.

## 1. Mốc mã nguồn và kết quả

| Mục | Giá trị |
|---|---|
| Nhánh | `review/04-backend-cli-reports` |
| Nền | `f79a85b` của phần 03; tiếp nối các sửa 01–03 |
| Code đã kiểm | `83832f917de185247c9fdc548e4482c8d90b2284` |
| Python / hệ điều hành | 3.12.14 / Windows; môi trường thay thế Python 3.11 chuẩn |
| Node / FastAPI / Pydantic | 24.19.0 / 0.143.0 / 2.14.0 |
| requests / numpy | 2.34.2 / 2.5.3 |
| CVAT / dataset | Docker CVAT 2.78.1; nuScenes mini thật trong full suite; fixture nuScenes tính tay cho parity live |
| Full suite | **436 đạt, 0 lỗi, 0 skip; 38,38 giây; exit 0**, một warning Starlette/httpx |
| Extension logic | **7 Node đạt**; cú pháp hai file JS sửa đạt |
| Ca review | **18 ca có kết quả trong phạm vi bên dưới** |
| Findings phần 04 | **19 findings đã sửa/kiểm lại**; giới hạn liên phần ghi riêng ở mục 7 |

Tham khảo [bàn giao 03](03-handoff.md), [báo cáo 03](03-report.md), các guard gate của 01/02 đã nhận trên nền `f79a85b`. Không dùng kết quả các nhánh cũ theo ngày thay cho mốc này.

Report API `pointsnap/api.py`, `tests/test_report_api.py` và `Get-Report.ps1` trước đây chỉ có local. Phần 04 đã kiểm và đưa **riêng ba file này** vào commit. Docker/Compose/auto-tests/output local chưa được đưa vào nhánh. Mã nguồn được push nay có 371 test nền + **56 hồi quy phần 04 + 9 test API**.

## 2. Phạm vi đã review

- CLI: `main.py`, scan/gate/nuscenes/eval/ui commands, config precedence, exit codes, dotenv và UTF-8.
- Web: `app.py`, `projects.py`, `runner.py`, `preview.py`, `link.py`; routes, trạng thái, filesystem, đồng thời và lỗi.
- Report: HTML, CSV, JSON API; escaping, encoding, deep links, counts và gate.
- API bổ sung: PAT riêng mỗi request, quyền CVAT, formats/errors/concurrency và script lấy báo cáo.
- Adapter: sửa che token ở nguồn thông báo HTTP dùng chung; giữ logic mapping/writer phần 03.
- Web JS và extension content script: chỉ cập nhật URL scope cho bridge; nghiệm thu giao diện đầy đủ thuộc phần 05.

[Hợp đồng API/CLI và trạng thái](04-contracts.md). [Lệnh/bằng chứng](evidence/04/test-results.md).

## 3. Kết quả 18 ca

| Ca | Kết quả / loại bằng chứng | Trạng thái |
|---|---|---|
| R04-01 | Argparse thiếu/sai argument mã 2; config/runtime/diff chưa triển khai mã 3; dotenv và Unicode. CLI lỗi snapshot/frame/report trả mã 3. Get-Report parse PowerShell 5.1/7; tải thật bằng PowerShell 7 | Đạt trong phạm vi nêu |
| R04-02 | CLI scan mã 0; gate 0/1 theo rules/coverage. Fake thiếu cloud/no pose/rule tắt có test; scan CVAT thật thành công, reports khớp Web | Đạt |
| R04-03 | CLI default → env → file; token chỉ env. Web default schema → guideline → URL project + secret project; create/reset không lấy URL cá nhân. Config hiệu lực đã che token được lưu trong summary | Đạt code/test |
| R04-04 | CRUD, slug sai/traversal, duplicate, tên Việt tự tạo slug, tên rỗng; run của A không đọc/flag qua B; update hai trường đồng thời không mất trường | Đạt mock/HTTP |
| R04-05 | YAML/khóa sai/type sai trả 400, giữ guideline cũ. Dynamic manual_ranges/groups xóa thực sự; reset có defaults sạch; raw YAML loại token cũ | Đạt |
| R04-06 | Hai start cùng timestamp tạo ID riêng; mkdir độc quyền chống đè. Hai request live cùng job cho hai run riêng; một worker, tối đa 16 queued/running | Đạt mock/live |
| R04-07 | queued/running được lưu run.json; runner mới chuyển run dở thành failed khi đọc, yêu cầu quét lại. done và failed lưu lại; live runner mới đọc cùng summary | Đạt test/live; không resume tác vụ |
| R04-08 | 401/403/404/422/502, offline, JSON backend sai có mapping; Web lỗi che token và đóng session. Live PAT thiếu/sai 401, không quyền 403. Timeout adapter đã kiểm trong suite nền | Đạt mock/live |
| R04-09 | JSON hỏng/sai kiểu/NaN, thiếu file thiết yếu: 409; lỗi I/O: 503. List không giấu run hỏng hoặc báo done. Atomic replace lỗi giữ file trước; failed state vẫn giữ trong RAM nếu đĩa không ghi được | Đạt fault injection |
| R04-10 | Web/CLI/API cùng gate_verdict và coverage; thiếu cloud/pose, cloud rỗng nhận guard 01. HTML không tuyên bố sẵn sàng nộp khi không có finding | Đạt test/code |
| R04-11 | Live Web/CLI/API cùng 4 box hoạt động, 3 findings = 0 error + 1 warning + 2 info; HTML/CSV bằng byte; JSON trùng rule/frame/IDs/count/gate. Outside marker không tính vào box count | Đạt live |
| R04-12 | Tiếng Việt/comma/newline qua csv.DictReader; HTML text escape; BOM CSV; chuỗi formula được quote, số âm vẫn là số. UTF-8 BOM sửa cho script Windows | Đạt test + tải thật |
| R04-13 | Snapshot origin đưa vào tìm manifest; không chọn box ngẫu nhiên khi thiếu ID. Đọc code fallback keyframe gần nhất và exact_frame; live preview frame 0 exact=true, points đọc được | Đạt code/test/live; hình ảnh thuộc 05 |
| R04-14 | PUT/delete verdict, index sai, verdict sai; 20/40 ghi song song không mất kết luận; JSON nguyên vẹn. Live FP lưu/đọc lại. Precision UI dùng ok/(ok+fp), chưa review không vào mẫu; đọc code, chưa nghiệm thu UI | Đạt backend |
| R04-15 | Live đổi length sau scan, /flag tạo run mới, nhận đúng lỗi mới và flag 1 box; không đổi hình học mới. Run failed hoặc server đã đổi bị từ chối. Guard writer fresh còn từ 03 | Đạt live/test; race sau GET cuối còn giới hạn |
| R04-16 | Bridge khóa theo CVAT URL+job; seq/online 4s/revision, initial poll bỏ lệnh cũ, cursor sau restart tự cập nhật. Hai server trùng ID không nhận chéo; gọi thiếu URL khi nhiều server trả 400 | Đạt HTTP/test; tab/browser thuộc 05 |
| R04-17 | Report API dùng PAT caller mỗi request, không token dịch vụ/cache. Live read_only 200, non-owner worker PAT 403, token sai/thiếu 401; JSON/HTML/CSV và health. Get-Report 7 tải JSON đúng bằng PAT chỉ đọc | Đạt HTTP/CVAT thật |
| R04-18 | Scan live hai lượt riêng; reviews và project update concurrency; report HTTP có 2 slots, ca bận 429 không gọi CVAT và health vẫn 200. Fresh client theo caller, test không dùng service token | Đạt trong một process; chưa benchmark tải |

Các ca Đạt là kết quả ở mức được ghi rõ; không chứng nhận browser, server BTC, mọi phiên bản CVAT hoặc chế độ nhiều process. Mock fault injection không phải thử làm đầy ổ đĩa thật.

## 4. Findings đã sửa

Tất cả findings dưới đây có trạng thái **Đã xác minh** trên code `83832f9`. Bằng chứng chính: EV-04-001/002; ca live EV-04-003; script EV-04-004. Đường dẫn tính từ tool root.

| Mã / mức | Điều kiện và lỗi trước sửa | Sửa / vị trí / kiểm lại |
|---|---|---|
| RV-04-001 / P1 | Run A trong memory được đọc/flag bằng slug B, có thể quét/gắn nhầm job với token B | runner.get_run kiểm project_slug, run_dir kiểm phạm vi; ca A/B 404 và không submit |
| RV-04-002 / P1 | Cùng millisecond+job tạo cùng ID, đè trạng thái/output | runner._start_scan suffix ngẫu nhiên ngắn + mkdir độc quyền; frozen clock và hai request live |
| RV-04-003 / P2 | Restart làm biến mất queue/failed, chỉ summary done còn lại | run.json queued/running/done/failed; run dở sau restart thành failed, không tự flag lại |
| RV-04-004 / P1 | DELETE project trong lúc scan có thể bị worker tạo lại hoặc mất dữ liệu run | runner.delete_project chung lock với start; active trả 409; giữ project |
| RV-04-005 / P2 | JSON hỏng thành exception 500, run biến mất khỏi history hoặc thiếu findings vẫn bị hiểu done | storage.read_json kiểm root/records/finite; runner kiểm outputs; 409 và history failed có lý do |
| RV-04-006 / P2 | CLI lỗi ghi snapshot/report/scan thoát traceback thay mã 3; sessions không được đóng | main wrapper và finally scan/gate/runner/routes; ba lỗi I/O và session.close assertions |
| RV-04-007 / P2 | HTML đếm outside marker và tuyên bố job sạch/sẵn sàng nộp khi không có finding | html count active; gate/coverage hiển thị và empty state có phạm vi; parity 4 box |
| RV-04-008 / P1 | API JSON tự đếm lỗi/cảnh báo để passed, bỏ coverage/no_evidence | API dùng gate_verdict + scan_coverage_gaps; missing LiDAR passed=false; gate/reasons khớp Web |
| RV-04-009 / P2 | checks hardcode luật cũ, vẫn kể rule bị tắt; JSON upstream sai thành 500 | enabled_checks từ switches; checks theo điều kiện cloud/pose; ReportCvatError JSON map 502 |
| RV-04-010 / P2 | Preset thiếu tạo project nửa chừng, tên Việt tạo slug không hợp lệ, update tên rỗng được lưu | projects validate preset trước mkdir; normalize slug Việt; từ chối tên rỗng; retry create được |
| RV-04-011 / P2 | manual_ranges/groups=null gây TypeError 500 | projects kiểm Mapping trước merge; 400 và file cũ giữ nguyên |
| RV-04-012 / P1 | YAML raw của guideline cũ có token, lỗi CVAT echo token có thể đi ra CLI/Web/log | YAML serialize từ clean dict; CvatClient redact payload, Web/runner redact project token; fake sentinel không xuất hiện |
| RV-04-013 / P1 | Bridge chỉ khóa job ID, CVAT khác server cùng ID có thể nhận focus/sai đối tượng | link khóa scope+job; app chuẩn hóa URL; hai caller JS gửi cvat_url; HTTP hai origin không nhận chéo |
| RV-04-014 / P1 | Preview tìm manifest chỉ task ID, có thể dùng cloud khác server; shape thiếu ID chọn box tùy ý | preview dùng snapshot URL và yêu cầu identity; không có box trả lỗi thay vì preview sai |
| RV-04-015 / P2 | CSV CLI/Web để chuỗi label/message dạng formula không bảo vệ; API có logic riêng | csv_rep bảo vệ text chung, giữ numeric âm và quoted newline; API bỏ bản logic trùng |
| RV-04-016 / P2 | Queue scan vô hạn; file tạm/lịch sử chưa có giới hạn vận hành rõ | cap 16 queued/running, 1 worker mặc định; API 2 slots; 429 có test. Chưa giới hạn tổng lịch sử |
| RV-04-017 / P2 | Get-Report URL cố định; thiếu .env gây lỗi khó hiểu; UTF-8 không BOM bị PowerShell 5.1 parse sai tiếng Việt | ApiUrl parameter/validation, check .env có tồn tại, UTF-8 BOM; parse 5.1/7, HTTP download trên 7 |
| RV-04-018 / P1 | Flag run đã fail hoặc scan của server cũ sau khi project đổi CVAT URL | app.flag_scan yêu cầu done, so source URL từ summary/snapshot với project; 409 thay submit |
| RV-04-019 / P2 | Hai update project đọc–sửa–ghi có thể mất trường; ghi trực tiếp dễ để file dở | projects RLock một manager, storage temp unique + replace, reviews giữ lock; concurrent disjoint fields và replace failure |

Lượt red ban đầu chỉ gồm 27 ca: **26 lỗi, 1 đạt**. Các finding khác được thêm trong lượt đọc code/kiểm tiếp; không quy cả 19 finding thành 26 ca red hoặc khẳng định mọi ca thêm đều đã chạy trước sửa.

## 5. Parity và cách đếm

| Kênh trên task/job 56 | Box hoạt động | Error | Warning | Info | Tổng findings | Gate |
|---|---:|---:|---:|---:|---:|---|
| Web summary/findings | 4 | 0 | 1 | 2 | 3 | false |
| CLI HTML/CSV | 4 trong HTML | 0 | 1 | 2 | 3 | false trong HTML |
| API JSON/HTML/CSV | 4 trong JSON/HTML | 0 | 1 | 2 | 3 | false trong JSON/HTML |

HTML và CSV của cả ba kênh giống byte; JSON tương ứng rule/frame/source_id/track_id. Có 5 cuboid gồm 1 outside marker; marker không vào box count. Info floating.no_evidence có thể chặn gate dù coverage_gaps rỗng. CSV là bảng **findings**, không chứa bảng gate/box count và không tự chứng nhận job đạt.

Sau khi tăng length một keyframe lên 25 m trong task thử, flag tạo run mới và gắn 1 box, unmatched=0; geometry sau chỉnh giữ nguyên qua flag. Đây là kiểm chức năng, không phải đo precision/recall trên nhãn thật.

## 6. Phạm vi commit và bằng chứng

- Code/test/script ở `b7f00d0` (20 file) và guard cuối `83832f9` (3 file, 2 file đã sửa ở commit trước); tổng 21 đường dẫn nguồn/script/test, stage cụ thể.
- Báo cáo này, contracts, handoff và evidence nằm ở commit tài liệu tiếp theo.
- Không commit token, secret.json, dataset, PCD, full snapshot hoặc full output.
- Hướng dẫn tái chạy live ở [evidence/04](evidence/04/test-results.md); helper tạo/xóa task, PAT và worker thử riêng.
- Full suite thực sự bật dataset và live CVAT, không skip; warning môi trường được giữ nguyên.

## 7. Giới hạn và bàn giao

| Giới hạn | Ảnh hưởng / việc tiếp theo | Phần nhận |
|---|---|---|
| GET cuối → PATCH CVAT chưa atomic, đã nêu ở 03 | Tránh chỉnh cùng job lúc tool ghi cờ; cần hợp đồng/version lock của CVAT để bảo đảm chống race cuối | 03/06 |
| Một server process cho cùng POINTSNAP_HOME | Locks/queue/bridge là in-process; không chạy nhiều uvicorn workers hoặc nhiều instance chung home; chưa kiểm distributed locking | 06/08 |
| Không resume queue sau restart | Run dở thành failed khi đọc; operator quét lại. Nếu ghi cờ vừa xảy ra trước crash, kiểm CVAT rồi quét lại | 08 |
| Atomic replace từng file, không transaction nhiều file/fsync | Nếu đĩa hết chỗ, trạng thái failed có thể chỉ còn trong RAM; run.json cũ giúp báo gián đoạn sau restart. Backup/restore và power loss thuộc 08 | 08 |
| Legacy run trước 04 không có run.json/source URL trong summary | Đọc summary cũ; flag dùng URL snapshot nếu có. Nếu cả hai thiếu source, endpoint trả 409 và yêu cầu quét mới | 06/08 |
| UI/extension thao tác tab chưa nghiệm thu ở phần này | Backend scope/seq có test; cần reload cả Web/extension, chạy journey và nhiều tab thực tế | 05 |
| API supplementary là process riêng | Không tự dùng guideline/secret/state project Web; config env/default riêng. Entrypoint hiện có thể bind 0.0.0.0:8081; chưa nghiệm thu chia sẻ LAN/multi-user | 06/08 |
| Lịch sử/commands trong RAM và lịch sử trên đĩa chưa có retention | Đã cap tác vụ đồng thời, chưa benchmark hoặc cap tổng dữ liệu lịch sử | 07/08 |
| Python 3.12 / Node 24 / CVAT 2.78.1 | Không chứng nhận Python 3.11/Node 22/CVAT 2.77 hoặc server BTC tương đương | 07/08 |
| Windows PowerShell 5.1 Restricted | Parse đạt sau BOM, thực thi file bị policy máy chặn; smoke dùng PowerShell 7 RemoteSigned. Không đổi policy máy | 08 |

## 8. Kết luận

**Hoàn tất review phần 04** trong mô hình local một process: 18 ca đã ghi kết quả, 19 findings xử lý, 436 Python + 7 Node đạt, có CVAT/PAT thật và parity. Tài liệu không chứng nhận UI, server BTC, mọi tổ hợp phiên bản, vận hành LAN hoặc khả năng phát hành tổng thể. Phần 05 tiếp nối code này và kiểm journey thực tế.
