# 08 — Báo cáo triển khai, tài liệu và tổng hợp

Ngày **12/10/2026**, Asia/Saigon. Nhánh `review/08-deployment-docs-final`, base
`review/07-tests-evaluation-performance` (`5353683`). Code/artifact `94dac32`,
fixture dataset isolation `79849b4`. Nhánh tiếp nối 01→08; chưa merge main.

## Kết quả và phạm vi

**493 pytest đạt, không skip/fail/error trên Windows Python 3.12.14**, dataset
nuScenes mini thật và CVAT 2.78.1 với task test tự dọn; 36 Node tests đạt.
Linux Docker Python3.11.17: **486 pytest đạt,7skip** (4dataset/3live không gắn trong container), pipcheck đạt; installed package smoke7HTTProutes200 từ /work. First build3.11 timeout PyPI, retry bằng Dockerfile tạm chỉ tăng piptimeout thành công.

Có một cảnh báo Starlette TestClient/httpx deprecation. Full lần đầu có 1 test
fixture thất bại vì NUSCENES_ROOT thật ghi đè dataset giả; sửa isolation, 3 focused
pass rồi full 493 pass. Đây là lỗi test, không quy thành lỗi alias production.

Wheel/sdist build từ `git archive 94dac32` ở tool root, không lấy .env/.venv/data/
out của máy tác giả. Cài wheel vào venv riêng, chạy smoke từ `out/review08-final-dist`:
package import từ site-packages, CLI help, config/guideline và bảy HTTP routes đều
đạt. Wheel có 90 files, 27 static files, 21 WOFF2; HTTP kiểm một font, không kiểm
mọi glyph. Sdist có README, hết cảnh báo thiếu README của bản trước.
`pip check`: không có dependency hỏng. Dependency artifact khác workspace ở
NumPy/Pydantic patch version; xem evidence, không tự đổi venv công việc.

## Findings 08

| Mã | Mức | Điều kiện / trước sửa | Sửa và kiểm lại |
|---|---|---|---|
| F08-01 | P2 | Export host ghi URL localhost, API Docker gọi cvat-server; auto manifest đúng task nhưng không khớp URL → cloud unavailable | Alias chỉ cho CVAT_URL↔CVAT_WEB_URL cùng server được khai báo; từ chối project khác/không mapping. 3 regression; live fixture cloud false→true, HTML links về Web URL |
| F08-02 | P2 | Dockerfile.api overlay source mới lên base image cũ, code có thể lệch dependencies khi pyproject đổi | API dùng nguyên base package; ARG base image/tag, tài liệu build CLI trước API. Build/running image riêng cùng source; không chứng minh từng thay đổi dependency giả lập |
| F08-03 | P2 | Docker/Compose/.env.example chỉ local, người clone không có đường chạy theo tài liệu | Đọc/sanitise rồi track từng file; Docker context allowlist không có secrets/data; checkout archive build được |
| F08-04 | P3 | Sdist build cảnh báo README thiếu; package không có README khai báo | README package + pyproject readme; build sdist và wheel, kiểm assets/import/static ngoài source |
| F08-05 | P2, coverage gap | CI chỉ một Python Linux, chưa smoke artifact/Windows | Matrix 3.10/3.11 Ubuntu,3.12 Windows và job build/install wheel ngoài source; đọc YAML/commands. Remote CI chưa chạy; không ghi CI PASS |
| F08-06 | P2 | Docs ghi 3 detector, ~2 giây, chọn đúng box vô điều kiện, snapshot như restore tự động; thiếu operations | Đồng bộ scanner/gate/07 metrics, identity ambiguity, alias/base/build order, local launcher, backup/restore/rollback và giới hạn. Kiểm links/source; không sửa dữ liệu lịch sử thành kết quả mới |

Các sửa ở `94dac32`; fixture isolation `79849b4`. F08-01 giữ guard của
RV-03-007/RV-04-014, không auto ghép server chỉ vì task ID trùng.

## API Docker và vận hành

Task/job **79**, tên `PointSnap review 08 (tự xóa)`, chỉ dùng nuScenes giả ba frame,
bốn box. Container riêng `pointsnap-review08-api`, tag private `pointsnap-api-review:94dac32`.
Service đọc PAT người gọi từ memory; PAT không đưa vào image/evidence. Không thay
image tag 0.1.0/container PointSnap đang dùng. Mount export/dataset chỉ đọc, user
pointsnap UID1000, rootfs read-only, tmpfs /tmp; port thử bind 127.0.0.1:8881.

| Ca live | Trước alias | Sau alias / qua router / sau restart |
|---|---|---|
| JSON / HTML / CSV | 200 | 200 cả ba |
| Box / errors / warnings / info | 4 / 0 / 4 / 0 | 4 / 0 / 1 / 2 |
| point_cloud_available | false | true |
| passed | false | false; INFO no-evidence/coverage vẫn chặn |
| Không PAT / PAT giả | 401 / 401 | 401 / 401 |
| Health | 200 | 200 |
| Annotation digest trước/sau | Bằng nhau | Bằng nhau |
| Cache policy | private, no-store | private, no-store |

Traefik test dùng router/service riêng, Host `pointsnap-review.local`, priority100,
cùng network `cvat_cvat` và backend `cvat-server:8080`. Gửi Host header tới cổng
CVAT 8080; không sửa router hostname localhost đang dùng. HTML links dùng
`http://localhost:8080/tasks/...`, không DNS nội bộ. Counts thay đổi vì cloud/pose
được đọc, không vì sửa nhãn. Restart đúng container riêng rồi lặp GET/auth/report.

Concurrency cap2/429/health khi bận có controlled upstream fixture trong 07 và
unit suite hiện hành; chưa đo throughput CVAT thật. Health không kiểm dataset,
PAT, quyền job hay chất lượng. Không restart CVAT stack công việc.

Backup/restore thử 11 files chứa token giả: byte hashes bằng nhau trước startup,
config/PAT giả/review giữ, run done giữ, queued→failed, bridge online=false.
Runner nguồn phần 04 (`59ef9c4`) đọc run done với dependencies hiện hành; đây không
phải rollback full historical environment hay restore database/nhãn CVAT thật.
Launcher Windows chạy từ repo root khác tool root, HTTP200, từ chối port occupied,
dừng đúng PID. Capturing stdout từ nested pwsh từng treo trong tool harness; gọi
script trong PowerShell hiện hành đã kiểm và là cách tài liệu hướng dẫn.

## 24 ca kế hoạch

| Mã | Trạng thái | Bằng chứng / giới hạn |
|---|---|---|
| R08-01 | Đạt | git archive code commit, build artifact/images, không .env/.venv/dataset |
| R08-02 | Một phần | Ma trận thực tế trong 08-compatibility; remote CI/3.10/CVAT2.77/MV3/BTC chưa kiểm |
| R08-03 | Đạt trong tổ hợp đã kiểm | Wheel Windows venv riêng, CLI/Web/config; editable/Linux ghi ma trận |
| R08-04 | Đạt phạm vi asset | 27 static/21 fonts/config/spec-vn trong wheel; bảy HTTP routes, một WOFF2 |
| R08-05 | Một phần | Docs GET/write PAT phân biệt; live report PAT thật+401 giả, quyền read-only/write refer 03/04 mocks, chưa tạo PAT mọi role |
| R08-06 | Đạt local | Mini thật 07, fake export/mounts 08, sweeps/manifest; máy ≥20GB/8GB là ước lượng cài đặt, không benchmark minimum hardware |
| R08-07 | Một phần | Docs/update/permissions/identity +Node; MV3 browser thật bị chặn |
| R08-08 | Đạt tài liệu/source | diff/restore/missing-object/auto-fix ghi rõ chưa triển khai; CLI help/test từ 01 và package smoke |
| R08-09 | Đạt | CLI→API base cùng source, image IDs/checksums trong evidence |
| R08-10 | Đạt trên stack thử | API thật gọi CVAT qua DNS/network; network configurable |
| R08-11 | Đạt trên router thử | Traefik Host riêng /pointsnap, priority100, Web URL; không redeploy router công việc |
| R08-12 | Đạt API thử | UID1000, read-only/tmpfs/mountRO; CLI write cần quyền host UID1000, chưa nghiệm thu mọi host/Linux permissions |
| R08-13 | Một phần | Live formats/auth/health/cache/nhãn giữ; concurrency controlled/mock, chưa tải đồng thời CVAT thật |
| R08-14 | Một phần | Home restart fixture và API restart; chưa restart CVAT giữa tác vụ |
| R08-15 | Một phần | Home fixture byte-level, token giả; không backup/restore DB/annotation CVAT thật |
| R08-16 | Một phần | Runner04 đọc run done bằng deps hiện hành; chưa rollback full version/config schema |
| R08-17 | Đạt launcher repo | Current PowerShell cwd khác, occupied guard/log/PID; launcher thư mục cha và CVAT checkout ngoài Git không phân phối |
| R08-18 | Đạt kiểm kê | 184 baseline khớp git tree; inventory hiện hành phân biệt source/tests/docs/assets và mức kiểm |
| R08-19 | Đạt tổng hợp | 95 nhóm01–07 +6 nhóm08, nguồn/SHA/owner/related guards; residual RV-03-012 giữ mở |
| R08-20 | Đạt đối chiếu docs | README/cài đặt/operations/review hiện hành; nhật ký/TASKS giữ snapshot lịch sử; links có kiểm |
| R08-21 | Đạt đối chiếu số liệu | Dùng07 seed/config/hash/heldout; không gán metadata mới cho bảng lịch sử |
| R08-22 | Đạt hợp đồng | counts không đủ kết luận; cloud/no-evidence/pose/luật tắt và thiếu dữ liệu có phạm vi |
| R08-23 | Một phần hồ sơ | Báo cáo/test/eval/handoffs có; không có demo/video/slide tracked; PDF local cũ không tính evidence mới |
| R08-24 | Chưa đạt phát hành rộng | Review bàn giao đủ, quality/manual/MV3/race/LAN/compatibility còn hạn chế; chưa có quyết định chấp nhận |

## Tổng hợp và quyết định sử dụng

- [Ma trận tương thích](08-compatibility.md), [sổ findings](08-findings.md),
  [inventory](08-file-coverage.tsv), [checklist vận hành](08-operations-checklist.md).
- 184 files nền đều có phần phụ trách. File added/evidence được kiểm kê thêm;
  asset/historical doc/source inspection không đổi thành đã test mọi nhánh code.
- **Hoàn tất review 01–08 và bàn giao theo phạm vi báo cáo.** Có thể demo và dùng
  CLI/Web/report local trong tổ hợp đã kiểm, với đúng dataset/PAT/coverage và reviewer.
- **Chưa nghiệm thu toàn sản phẩm/phát hành rộng:** false-alarm proxy07 còn vượt
  mục tiêu, manual precision0, MV3 thật thiếu, GET→PATCH race, LAN/HTTPS/BTC và
  recovery/rollback full cần kiểm. Không có thay đổi main hoặc PR tự mở.

Evidence và lệnh giữ tại [index08](evidence/08/README.md). Wheel/dataset/raw output/nhãn ở out
ignored; chỉ metadata/checksums/counts đã kiểm mới đưa vào Git. Xem [bàn giao](08-handoff.md)
cho base PR và SHA.

Đã dọn task/job79 (404), owned API container và Web PIDs; [cleanup](evidence/08/cleanup.json). Các helpers có hai lỗi setup được ghi rõ: test fixture dùng root thật và cleanup giả định thuộc tính status_code của CvatError; đã sửa helper/verification, không che thành lỗi sản phẩm.

Inventory chốt: **309 files tracked**, gồm184 files nền và125 files thêm; không xóa file nền. Kiểm337 local links/44Markdown files, không link thiếu, code fences cân bằng; không kiểm external URL/anchors.
