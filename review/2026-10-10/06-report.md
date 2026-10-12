# 06 — Kết quả review bảo mật và cấu hình

Ngày **11/10/2026**, Asia/Saigon. Nhánh **`review/06-security-config`**, base **`review/05-frontend-extension` (`43812b9`)**. Đã review, sửa và kiểm các đường dữ liệu dưới đây. Không chứng nhận triển khai LAN hay extension MV3 cài thật.

## Mô hình và trust boundaries

Mô hình được giữ theo CLI hiện tại: **một người dùng local tin cậy**, bind Web `127.0.0.1:8765`. Người quản lý project chủ động chọn server CVAT và dataset/export root. Cho phép CVAT private/loopback vì đó là luồng sản phẩm; không áp denylist IP làm hỏng CVAT Docker/local.

| Boundary | Nguồn → quyền tại sink | Guard và giới hạn |
|---|---|---|
| Website khác → Web | Browser không có PAT nhưng server giữ PAT dự án → reset/scan/flag/files | Host loopback/explicit, Origin cùng scheme/host/port, Sec-Fetch-Site, payload1 MiB; không CORS mở; API no-store; X-Frame-Options DENY |
| Operator/CLI → Web | Local process không Origin → quản lý toàn bộ home | Tin cậy operator và filesystem; chưa auth multiuser; Host/Origin không phải hệ thống tài khoản |
| Extension → service worker → Web | Content script ở CVAT có phiên đăng nhập; worker có host permissions | Sender ID, top frame, CVAT origin đã cấu hình; whitelist method/path; project CVAT và run.job_id đúng trang đang mở; không redirect |
| Report caller → CVAT | PAT Bearer của caller → quyền job do CVAT kiểm | Mỗi request client riêng, không token dịch vụ/cache; 2 slots; origin pagination và redirect guard |
| CVAT response → UI/report | Nhãn/message và URL ngoài → HTML/link/CSV | Text escape, link HTTP(S) không credentials, bảo vệ formula text; lỗi token redacted |
| Dataset metadata → disk/preview | filename/version của dataset → đọc bảng/LiDAR/camera/sweep | Relative path, resolve nằm trong dataroot, kiểm Windows drive/UNC và symlink thoát root |
| Docker/runtime → host | Image user, network, mounts, plaintext secrets | User pointsnap, API không publish port hiện tại; mounts API ro/read_only trong Compose local; chưa rebuild và kiểm deployment cuối |

Chrome extension được operator cài và cấp host permission là thành phần tin cậy của mô hình local. Browser origin `chrome-extension://<32 ký tự a-p>` được Web chấp nhận; website không giả được header Origin này trong fetch thông thường. Local process có thể tự đặt header và vẫn là actor tin cậy theo mô hình này. Không tuyên bố Web chống malware cùng tài khoản hoặc caller LAN khi operator mở bind/proxy.

## Findings và sửa

| Mã | Mức / actor / điều kiện | Đường dữ liệu và tác động đã kiểm | Sửa / bằng chứng |
|---|---|---|---|
| F06-01 | P1, website mở trong browser của operator | POST không JSON đến guideline/reset dùng state server; source app43812b9 trả200 và rule false→true dù Origin evil.example | LocalRequestBoundary chặn403; rule false giữ nguyên. `origin-before-after.json`, TestClient và HTTP thật |
| F06-02 | P1, trang CVAT bị script độc hại hoặc worker message từ content script | Worker chỉ kiểm prefix /api, cho PUT project/guideline và job khác bằng quyền mạng extension | Whitelist; query/path canonical, project CVAT/run.job_id, sender top frame;11 Node regression. Không tuyên bố đã thử exploit trong MV3 thật |
| F06-03 | P2, input token sai kiểu hoặc YAML lỗi có credential | Pydantic/YAML parser echo input/dòng source vào response/toast/CLI | Trả loc/msg/type, YAML chỉ vị trí; test marker TEST-SECRET-06 không xuất hiện; background CVAT message cũng redacted |
| F06-04 | P1, operator đổi destination nhưng để trống PAT | Project địa chỉ mới giữ token cũ; lần check/scan sau có thể gửi PAT cũ tới server khác | Xóa secret trước đổi origin/path; lock effective config cùng update; explicit token mới được lưu;4 ca giữ/xóa/đổi token. Chứng minh qua cấu hình, không gửi PAT thật tới server bên ngoài |
| F06-05 | P2, URL user nhập hoặc metadata cũ chứa credentials/scheme lạ | Project metadata được trả trước khi client kiểm; link có thể mang credentials/javascript | Validate URL trước persist, generic error không echo input; frame_url/safeHttpLink;7 URL ca âm tính và Node link test |
| F06-06 | P2, dataset import có filename ../ hoặc absolute | NuScenes filename nối trực tiếp với dataroot → đọc LiDAR/camera/sweep ngoài root | Relative+resolve containment;3 fixture path âm tính. Dataroot do operator chọn vẫn hợp lệ ngoài export root |
| F06-07 | P2, state/report cũ không tin cậy | Một số history/severity/frame/count và data-id render raw; nhãn chuẩn đã escape | Escape còn thiếu, safe href; Node payload history và report escape hiện có. Payload state là fixture/local import, không gán nhầm thành XSS trực tiếp từ mọi nhãn CVAT |
| F06-08 | P2, caller gửi body lớn hoặc CVAT phân trang vô hạn | Web parse body không giới hạn; pagination next luôn mới không dừng | Cap1 MiB cả chunked; CVAT/client+extension max100 trang, timeouts; queue16/report2 giữ; tests, không stress production |
| F06-09 | P2, operator dùng options URL không HTTP hoặc host mặc định trùng custom | URL.origin của file/javascript có thể thành null; dynamic scripts trùng built-in | Chỉ HTTP(S) origin, không credentials/path/query/hash; dedup built-in/custom; Node tests |
| F06-10 | P2, caller dùng token trong URL / mặc định bind rộng | Report API log request target chứa query; entrypoint bind0.0.0.0 không có lựa chọn local | Reject query ngoài format, log method/status/size, test không log marker; default127.0.0.1, Dockerfile.api explicit0.0.0.0; không restart container người dùng |
| F06-11 | P2, external CSV text có formula và BOM/control đầu | Formula chỉ lstrip whitespace, BOM có thể che ký tự mở đầu | Bỏ BOM/zero-width khi kiểm prefix rồi quote chuỗi;4 ca; giữ cột số âm numeric. Chưa mở thật trong Excel |
| F06-12 | P2, API state/report trong browser cache/nhúng | Web API không có cache policy riêng; iframe cùng site/khác port có thể nhúng UI | API private,no-store; nosniff/referrer-no-referrer/XFrameDENY. HTTP header và TestClient; chưa demo overlay clickjacking |

## Checklist 20 ca

| Ca | Kết quả / bằng chứng và giới hạn |
|---|---|
| R06-01 | Đạt trong phạm vi API/config: has_token, token tách khỏi guideline, tests04+security; so sánh PAT thật với tracked files không có match |
| R06-02 | Đạt: HTTP/network/JSON/background/YAML/request error marker không lộ; không dùng PAT thật trong payload âm tính |
| R06-03 | Đạt tracked/staged scope: .env/data/out không tracked; Dockerfile.api chỉ COPY pointsnap. .dockerignore local dùng allowlist, chưa chứng nhận image build mới |
| R06-04 | Đạt: Bearer/Token client tests; ReportAPI không dùng CVAT_TOKEN privileged service fixture; project effective env không fallback token toàn cục |
| R06-05 | Đạt logic: CvatClient/ReportCvatClient chặn next khác origin và redirects, extension redirect:error, cap100. Mock ghi target/header, không gửi credential ngoài scope |
| R06-06 | Đạt validation/local model: http(s), no userinfo/query/fragment/control/bad port; private/loopback CVAT cố ý được hỗ trợ. Không kết luận SSRF khai thác trên LAN |
| R06-07 | Đạt logic traversal slug/run/index; scope tests03/04 giữ. Không mô phỏng adversary có quyền thay toàn bộ file home trong lúc request |
| R06-08 | Đạt logic và HTTP: project/run scoping + cvat_url bridge, worker own job. Ca2 CVAT server thật/MV3 thật chưa có môi trường |
| R06-09 | Đạt filename/version containment:3 metadata path fixture. Manifest file names dùng đối chiếu frame, không dùng làm path LiDAR. Manifest.dataroot là operator-configured root; sentinel arbitrary path không được đọc qua filename |
| R06-10 | Đạt server: baseline200 mutation→403 giữ guideline; HTTP8766 fake Host403. Browser8767 fetch bị CORS đọc response, guideline false giữ. Form iframe IAB không load nên không lấy nó làm bằng chứng403 |
| R06-11 | Đạt logic: label/message/project escape, bổ sung state fields/data-id, safe links; Node fixture. Browser chưa thực thi mọi payload trong MV3 |
| R06-12 | Một phần: CSV quote =,+,-,@, newline/BOM, số âm numeric; kiểm bytes/parser, chưa Excel GUI |
| R06-13 | Đạt logic11 Node: sender/iframe/path/method/job/project/run/redirect/custom host. Chưa permission dialog/cài MV3 thật (R05-11) |
| R06-14 | Đạt TestClient/report mock + live CVAT suite: thiếu/sai PAT/quyền job, client riêng, không lấy report caller khác; không retest server BTC chưa được cung cấp |
| R06-15 | Đạt: API/private no-store, Report Vary Authorization, temp context cleanup, log không query; marker test. Origin/HTTP live JSON trong evidence |
| R06-16 | Đạt cap chức năng:1 MiB normal/chunked, queue16, report2, pagination100 và request timeout; chưa đo tải/slow-client, chuyển07 |
| R06-17 | Đạt schema: safe_load, khóa/kiểu/finite validation và tests config/storage; lỗi không thay guideline đã lưu; parser error không echo source |
| R06-18 | Một phần: Windows fixture secret ACL có Han/System/Administrators F và CodexSandboxUsers RX. Plaintext, agents cùng tài khoản là trusted. Docker image hiện tại user pointsnap, API không publish port, Compose API ro. Chưa Linux permission/rebuild deployment mới |
| R06-19 | Đạt kiểm kê/tương thích:30 distributions metadata,0 conflict base requirements; pip không được cài nên không ghi pip check đạt. Chưa audit CVE/advisory, không kết luận dependency không có lỗ hổng |
| R06-20 | Đạt logic/live suite kế thừa03/04: job permission, fresh geometry, flag/clear scoped và snapshot; task thử tự xóa. GET→PATCH vẫn không atomic nếu collaborator sửa đúng khoảng đó |

## Kiểm thử, runtime và dọn dữ liệu

- Toàn suite: **467 pytest đạt,0 skip,47,32 s** với CVAT2.78.1 và v1.0-mini, home/temp riêng;1 cảnh báo Starlette/httpx.
- Sau thay đổi cuối cho pagination/log/XFrame: **51 pytest tập trung đạt** (`test_security_review.py`, `test_cvat_client.py`, `test_report_api.py`),6,78 s. Suite đã thêm2 ca sau full run; không gọi số full467 là số testcase cuối toàn repo.
- **35 Node đạt**,0 skip;13 regression security và1 regression follow-up Guideline thêm so với21 của05. Follow-up giữ form inert khi project chưa tải guideline, reset được reload sau khi xác nhận bỏ draft. JS syntax và git diff check đạt.
- Dependency thực tế: [metadata](evidence/06/dependencies.json); numpy2.5.3, PyYAML6.0.3, requests2.34.2, FastAPI0.143.0, Uvicorn0.54.0, Pydantic2.14.0, Starlette1.7.0, pytest9.1.1, httpx0.28.1.
- Live: Origin8767→8766 HTTP403; fake Host403; rule trước/sau false; private,no-store. Browser xác nhận UI cùng Origin vẫn nối CVAT2.78.1, đọc kết quả/preview. [JSON](evidence/06/live-results.json), [ảnh](evidence/06/01-cross-origin-blocked.png).
- Task60 được đối chiếu tên trước delete, GET lại và danh sách review05 rỗng. Không revoke PAT người dùng đã có; chỉ xóa bản sao token trong home thử khi dừng server. Task1/task8 không sửa/xóa.
- File Dockerfile.api trước đây local, được thêm có chủ đích để giữ ReportAPI lắng nghe đúng trong container sau đổi defaultlocal. Base Dockerfile/Compose/.dockerignore/.env.example vẫn local và cần bàn giao08; chưa build/deploy image mới.

## Còn lại

Không mở Web lên LAN như dịch vụ multiuser khi chưa có lớp xác thực riêng. Người có quyền filesystem/token hoặc extension được cấp host permission vẫn thuộc boundary tin cậy. GET/PATCH race CVAT, MV3 thật, reverse proxy HTTPS/path, Docker reproducibility và tài nguyên tải lớn chuyển07/08. Tài liệu vận hành cụ thể: [local-security](../../source-tool/pointsnap-3d/docs/local-security.md).
