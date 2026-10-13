# Bằng chứng kiểm tra phần 04

11/10/2026, Asia/Saigon. Base `f79a85b`; code `83832f917de185247c9fdc548e4482c8d90b2284`. Bằng chứng không chứa token/dataset/snapshot nhãn.

## EV-04-001 — hồi quy và full suite

```text
Red đầu (27 ca): 26 failed, 1 passed, 1 warning in 4.86s; exit 1
Focused sau sửa: 65 passed, 1 warning in 12.15s; exit 0
Full lượt đầu: 4 failed, 426 passed in 49.61s; mock cũ không có session.close
Full sau sửa mock: 430 passed, 1 warning in 51.26s; exit 0
Full thêm 5 guard: 1 failed, 434 passed in 42.75s; token giả một ký tự che cả câu thông báo
Full sau guard JSON/token: 435 passed, 0 skipped, 1 warning in 38.61s; exit 0
Full cuối thêm guard nguồn legacy: 436 passed, 0 skipped, 1 warning in 38.38s; exit 0
```

Đã sửa mock cho đúng client có session, không giảm assertion gate. Redaction cuối chỉ che dữ liệu ngoài/URL, giữ câu thông báo chuẩn. Suite cuối gồm 371 ca nền + 56 hồi quy phần 04 + 9 test report API. Warning Starlette/httpx của môi trường được giữ nguyên.

Lệnh từ tool root:

```powershell
.\.venv\Scripts\python.exe -u -c 'import os,sys,runpy,uuid; from pathlib import Path; r=Path.cwd(); sys.path[:0]=[str(r),str(r/".venv/Lib/site-packages")]; os.environ["POINTSNAP_HOME"]=str(r/"out/review04-home"); os.environ["NUSCENES_ROOT"]="C:/Users/Han/Downloads/v1.0-mini"; os.environ["POINTSNAP_LIVE_CVAT"]="1"; sys.stdout.reconfigure(encoding="utf-8"); sys.stderr.reconfigure(encoding="utf-8"); sys.argv=["pytest","-q","-p","no:cacheprovider","--basetemp",str(r/"out"/("r04-"+uuid.uuid4().hex[:8])),"--tb=line","-ra"]; runpy.run_module("pytest",run_name="__main__")'
```

Đây là đường dẫn dataset của máy review, cần thay trên máy khác. Python 3.12.14, Node 24.19.0, CVAT Docker 2.78.1. Không tạo lại venv. TestClient/local HTTP chạy ngoài sandbox hạn chế; trong sandbox lượt đầu bị treo và đã dừng. Tên temp ngắn tránh MAX_PATH Windows; mỗi lượt mới có UUID suffix, không dùng lại thư mục có dữ liệu.

## EV-04-002 — negative cases, concurrency và lưu trữ

Trong `tests/test_backend_review_regressions.py` (56 ca khi expand parameterization):

- A/B run scope, frozen-clock run IDs, queue cap/invalid job, active delete và run failed/source đổi không flag.
- queued/failed restart, done missing output/list failed, corrupt JSON/root/records/NaN và atomically replace failure.
- CLI snapshot/frames/report failures; Web/CLI gate thiếu cloud, counts active; CSV Unicode/newline/formula/numeric.
- Bad preset/name/dynamic mapping; env reset; raw legacy token; disjoint project updates concurrency.
- Preview manifest URL/missing identity; bridge origin/seq/timeout/revision và caller cũ thiếu scope.
- Reviews concurrent/delete; local API HTTP statuses, slots release/busy, health, malformed backend JSON, rule switches/coverage.
- Token giả bị upstream echo không xuất hiện trong CLI/Web/runner logs.

`tests/test_report_api.py` có 9 ca HTTP actual loopback với CVAT mock; xác minh không dùng service token, formats, headers, token/quyền job, CSV và origin. CVAT HTTP status thật ở EV-04-003.

## EV-04-003 — parity và PAT trên CVAT thật

[Helper tái chạy](run-live-check.py) dùng fixture nuScenes tính tay, upload task riêng, TestClient Web gọi CVAT thật, CLI source và ReportServer actual HTTP loopback. Không có thao tác browser trong lượt này.

Lượt hoàn chỉnh cuối: **task/job 56**, output ngoài Git `out/r04-live-d85e7022/`, exit 0. Lượt live này chạy code tương ứng `b7f00d0`; guard legacy bổ sung ở `83832f9` chỉ từ chối history thiếu URL, không đổi luồng fixture có đủ URL. Full suite cuối kiểm cả guard mới trên `83832f9`.

```json
{
  "cvat_version": "2.78.1",
  "task_id": 56,
  "job_id": 56,
  "pat": {"read_only": 200, "no_job_permission": 403, "invalid": 401, "anonymous": 401},
  "parity": {"boxes": 4, "findings": 3, "errors": 0, "warnings": 1, "info": 2,
             "gate": false, "coverage_gaps": [], "html_bytes_equal": true, "csv_bytes_equal": true},
  "flag_summary": {"flagged": 1, "cleared": 0, "unmatched": 0},
  "geometry_preserved": true,
  "preview_frame": 0,
  "exact_frame": true,
  "reviews_saved": true,
  "done_restored": true,
  "credentials_cleaned": true,
  "task_cleaned": true
}
```

Hai run nhanh: `20261011-162707-096360444487-job56`, `20261011-162707-091367666601-job56`. Run flag fresh sau đổi length: `20261011-162713-526310852677-job56`.

So byte HTML/CSV Web/CLI/API, so JSON fields và counts; 5 cuboid gồm 1 outside marker. `floating.no_evidence` INFO giải thích gate=false khi coverage_gaps rỗng. Đổi một length lên 25 m qua PATCH task thử, rồi endpoint flag từ run cũ tạo scan mới; writer giữ hình học đã sửa, gắn 1 box. Preview frame 0 exact, review FP được lưu, runner mới đọc cùng summary.

PAT thử read_only của chủ task và PAT worker mới không sở hữu task được tạo trong Docker bằng model user đúng, không dùng PAT dịch vụ thay caller. Token chỉ ở RAM; revoke/xóa cả credential và worker sau lượt chạy. Task thử xóa trong finally. Dataset mini thật được chạy trong full suite, không dùng fixture nhỏ thay cho số liệu real dataset/precision.

Lượt task 47 đã hoàn tất parity/flag/preview/reviews/restart; task 43/51/55 dừng tại helper/PowerShell và đã dọn. Không tính các lượt dừng là end-to-end đạt.

## EV-04-004 — Get-Report và chẩn đoán môi trường

- Parse source Windows PowerShell 5.1 trước BOM: Unexpected token / missing string terminator do đọc UTF-8 như ANSI. Sau BOM parse **đạt**.
- 5.1 trên máy có policy Restricted, không chạy được file. Không chỉnh policy hoặc dùng Bypass. PowerShell 7 sẵn có có policy RemoteSigned.
- Lượt task 56 chạy Get-Report.ps1 bằng PowerShell 7 với PAT read_only trong env, ApiUrl actual loopback, JSON bằng response HTTP trực tiếp; exit 0.
- Helper đầu dùng `django.contrib.auth.models.User`, nhưng CVAT dùng `iam.User`. Chẩn đoán manager swapped; đổi helper sang get_user_model và transaction. PAT dở ID 2 do lượt này tạo đã xóa; không có fixture user dở. Đây là lỗi helper kiểm tra, không phải finding PointSnap.

Chạy lại helper từ tool root khi đã có CVAT Docker local/token:

```powershell
# Chọn PowerShell đang chạy nếu phù hợp policy hiện có, không thay policy.
$env:POINTSNAP_POWERSHELL = (Get-Process -Id $PID).Path
.\.venv\Scripts\python.exe -u ..\..\review\2026-10-10\evidence\04\run-live-check.py
```

Helper cần container `cvat_server`, quyền docker exec/Django shell, group worker và tài khoản tạo task. Nó tạo/xóa task, hai PAT và một user thử; không chạy vào server BTC hoặc database production. Full fixture/output nằm ở `out/r04-live-*`, không Git.

## EV-04-005 — Node, diff, cleanup và tài liệu

```text
node --test extension/tests/core.test.js: 7 passed, 0 failed, 0 skipped; exit 0
node --check pointsnap/web/static/app.js: exit 0
node --check extension/src/content.js: exit 0
PowerShell parser Get-Report.ps1 (7 và 5.1): exit 0 sau BOM
git diff --cached --check: exit 0
PASS: 7 tài liệu, 66 links tương đối, 18 ca, 19 findings, 23 method API đầy đủ; fences/helper AST đạt
```

Cleanup kiểm độc lập bằng Django/CVAT: **review04_tasks=0, review04_tokens=0, review04_users=0, suite_live_tasks=0**. Các files mới chỉ source/script/test/evidence tối thiểu, không chứa credential hoặc point cloud.
