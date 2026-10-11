# 06 — Review bảo mật, token và cấu hình

**Nhánh:** `review/06-security-config`.
**Trạng thái:** đã review/sửa ngày11/10;12 nhóm findings và20 ca có kết quả/giới hạn trong [báo cáo](06-report.md), [bàn giao](06-handoff.md).
**Đầu ra sẽ tạo:** `06-report.md`, bản đồ trust boundaries, findings có đường đi dữ liệu và ca xác minh sau sửa.

Áp dụng [quy trình chung](README.md), [mẫu báo cáo](report-template.md); checklist được chọn theo skill security-review và kiến trúc Python/local app thực tế. Đường dẫn tính từ tool root. Không áp yêu cầu database/payment/blockchain cho thành phần dự án không có.

## 1. Mô hình sử dụng phải chốt

| Thành phần | Dữ liệu/quyền | Câu hỏi cần xác minh |
|---|---|---|
| Web FastAPI local | Token lưu dự án, guideline, đọc/ghi run, gọi CVAT và flag | Chỉ một người trên máy hay chia sẻ qua LAN? Bind/CORS/Origin và quyền filesystem có phù hợp? |
| CLI | Token env/.env, config, manifest/dataset, snapshot/report | Token/đường dẫn có lọt qua output/error/history? |
| Extension | Phiên đăng nhập CVAT, nội dung nhãn, host permissions, gọi Web | Request/messaging có đúng origin/job và quyền đã cấp? |
| Report API local | PAT từng caller, proxy gọi CVAT, trả report | Mỗi request có kiểm quyền, cache/redirect/error có làm lộ dữ liệu caller khác? |
| Docker/runtime | Env, mounts, network/Traefik, user/temp | Service nào đọc/ghi thư mục nào; có expose rộng hơn mô hình được chấp nhận? |

Loopback là điều kiện triển khai, không tự chứng minh mọi request đến server đáng tin. Mọi finding phải ghi kẻ có thể thực hiện, điều kiện, khả năng tác động và dữ liệu thật sự bị ảnh hưởng.

## 2. Phạm vi code

- `pointsnap/web/app.py`, `projects.py`, `runner.py`, `preview.py`, `link.py`: request validation, path/project/run scoping, secret persistence và state mutation.
- `pointsnap/adapters/cvat/client.py`, writer/reader, `pointsnap/cli/main.py`, config và common: auth, pagination/redirect, `.env`, URL và filesystem.
- `pointsnap/report/html.py`, `csv_rep.py`, `pointsnap/web/static/app.js`: rendering và export dữ liệu ngoài.
- `extension/manifest.json`, background/options và src: quyền host, message sender, fetch và DOM.
- `pointsnap/api.py`, Docker/Compose/.env.example cục bộ: kiểm riêng, không suy ra tương đương với Web API.
- `pyproject.toml`, Git ignore, workflow, installed dependency metadata: phạm vi package và dữ liệu bị đưa vào build/commit.

## 3. Cách thực hiện

1. Lập sơ đồ nguồn dữ liệu → validator → điểm sử dụng → network/file/HTML. Ghi trust boundary, quyền caller và vị trí secret.
2. Chọn ca âm tính từ từng đường dữ liệu; dùng token giả, fixture và server mock để có bằng chứng mà không lộ token thật.
3. Kiểm đúng origin và scope project/CVAT/job/run trước các hành động đọc/ghi.
4. Kiểm nội dung output/response/log/report và file Git bằng đường dẫn, tránh in nguyên file secret.
5. Ca trình duyệt/cross-origin và runtime exposed phải kiểm trong môi trường thử riêng, theo phạm vi đã ghi.
6. Ghi findings tái hiện được, tách thiếu guardrail với lỗ hổng đã chứng minh; chuyển remediation về đúng module.

## 4. Checklist theo ranh giới

| Mã | Ca | Mong đợi / bằng chứng |
|---|---|---|
| R06-01 | Token trong config/API list/detail/guideline | Secret không trả nguyên văn; token tách khỏi guideline/config được công bố |
| R06-02 | Token sai/expired và lỗi CVAT có body/URL | Lỗi giúp xử lý mà không đưa credential vào log/HTML/UI; kiểm bằng token giả có dấu nhận diện |
| R06-03 | Git/build artifacts | Không có .env/secret/snapshot/dataset trong tracked/staged/build context; kiểm tên file trước nội dung |
| R06-04 | CLI/Web auth scheme và token fallback | Không dùng nhầm token caller/service/project, không đổi Bearer/Token ngoài cấu hình được mô tả |
| R06-05 | CVAT pagination `next`, absolute URL, redirect | Authorization không gửi sang origin chưa được phép; đối chiếu CvatClient và ReportCvatClient riêng |
| R06-06 | URL người dùng, loopback/private/network path | Chốt phạm vi CVAT URL hợp lệ theo mô hình local; chứng minh tác động SSRF nếu có đường khai thác |
| R06-07 | Project slug/run_id/index với traversal và giá trị sai | Không đọc/ghi/xóa file ngoài scope; invalid input không biến thành thao tác nguy hiểm |
| R06-08 | Run thuộc project khác, CVAT khác có job ID trùng | Không lẫn kết quả/reviews/extension command hoặc sử dụng token project khác |
| R06-09 | Manifest chứa đường dẫn tuyệt đối/relative thoát scope | Scope đọc dataset được xác định; kiểm path resolution với fixture có file sentinel giả |
| R06-10 | Origin/CORS và request thay đổi state | Website khác không tự dùng browser để thao tác bằng token server giữ; kiểm preflight/form/fetch và middleware thực tế |
| R06-11 | Label/message/project name có HTML/script | Web/report/extension render text đúng; không thực thi payload kiểm thử; kiểm cả thuộc tính/link |
| R06-12 | CSV cell bắt đầu bằng =, +, -, @ | Xác định hành vi khi mở bằng spreadsheet và biện pháp phù hợp; phân biệt số âm hợp lệ với chuỗi từ bên ngoài |
| R06-13 | Extension permissions/sender/path/method | Host quyền tối thiểu cho chức năng; message không gọi tùy ý endpoint/origin ngoài phạm vi |
| R06-14 | Report API thiếu PAT/sai PAT/không có quyền job | Quyền được CVAT kiểm ở mỗi lần gọi; không trả report/cache của caller khác |
| R06-15 | Cache headers, token URL, temporary report và logging | Không đưa token vào URL, không phục vụ report qua static path chưa kiểm quyền; temp cleanup đúng phạm vi |
| R06-16 | Payload lớn, queue vô hạn, scan/report đồng thời | Có giới hạn hoặc giới hạn vận hành rõ; đo tài nguyên trong thử nghiệm nhỏ, chuyển 07 |
| R06-17 | JSON/YAML hỏng, kiểu dữ liệu sai/khóa không biết | Validation đúng schema; không load YAML không an toàn hoặc silently chấp nhận cấu hình sai |
| R06-18 | File secret/run và Docker mounts/network | Quyền và phạm vi truy cập phù hợp deployment; không mở writable mount rộng ngoài nhu cầu |
| R06-19 | Dependencies khai báo và thực tế cài | Lưu phiên bản/nguồn; nếu đánh giá CVE phải có advisory và thời điểm tra cứu, không kết luận từ trí nhớ |
| R06-20 | Sửa/gỡ cờ CVAT và snapshot | Có kiểm job/box/quyền và snapshot cần thiết; không tạo mất nhãn do đường ghi không kiểm |

## 5. Kiểm tra tập trung và bảo quản bằng chứng

```powershell
python -m pytest -q tests/test_config.py tests/test_cvat_client.py tests/test_cvat_writer.py tests/test_web.py
python -m pip check
```

Khi API cục bộ có mặt, chạy `tests/test_report_api.py` riêng. Kết quả pip check chỉ về tính tương thích dependency, không phải kiểm CVE. Hiện extension không có package.json trong phạm vi đã kiểm kê; không đưa npm audit vào checklist như một gate có thể chạy mặc định.

Từ kho Git, kiểm danh sách file mà không in secret:

```powershell
git ls-files
git diff --cached --name-only
```

Dùng credential giả có chuỗi nhận diện để kiểm leakage; bằng chứng giữ request đã loại Authorization và response liên quan. Nếu phát hiện credential thật trong history/output, ghi vị trí/phạm vi và xử lý theo chủ sở hữu; không chép giá trị vào finding hoặc xóa history tự động.

## 6. Mẫu đường khai thác và sửa

Mỗi finding cần: nguồn input → validation thiếu/sai → sink → quyền dùng tại sink → kết quả quan sát được. Nếu chỉ thấy URL tuyệt đối được chấp nhận nhưng chưa xác minh redirect/token, ghi rủi ro cần kiểm, không tự kết luận đã lộ token. Nếu chứng minh bằng mock, ghi rõ mock đo header/target và điều kiện server có thể trả URL đó.

Đề xuất sửa phải giữ được luồng CVAT local được dự án hỗ trợ. Các biện pháp như origin validation, path containment, escaped output, request-size/concurrency limit hoặc rõ bind scope cần gắn với finding cụ thể; không thêm hệ thống auth/permission mới khi chưa xác định mô hình chia sẻ.

## 7. Hoàn tất và bàn giao

- [ ] Trust boundary, nguồn secret và actor/điều kiện triển khai được ghi.
- [ ] Các đường đọc/ghi/render/network có ca âm tính và bằng chứng hoặc lý do bị chặn.
- [ ] Finding có tác động đã chứng minh và severity theo phạm vi; đề xuất ghi riêng.
- [ ] Token/error/schema chuyển 04; CVAT origin/write chuyển 03; DOM/message chuyển 05.
- [ ] Resource cap chuyển 07; mounts/user/bind/build context chuyển 08.
- [ ] `06-report.md` không chứa secret hoặc payload có thể ảnh hưởng môi trường thật; có test kiểm lại từng bản sửa.
