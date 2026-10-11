# EV-01 — bằng chứng kiểm tra ngày 11/10/2026 (Asia/Saigon)

Mốc source: `5dcc97f1ffc1751d022e2474c0b50745e348af86`; hướng dẫn review `22a01f5`. Bản sửa trên `review/01-overview-architecture`, commit code ghi trong `01-report.md`.

## EV-01-001 — môi trường và inventory

- Windows, Python 3.12.14, Node v24.19.0, pytest 9.1.1.
- `git fetch origin main`: mã 0; `origin/main` vẫn là `5dcc97f` ngày review.
- Kho Git thực tế là `P-029-main/P-029-main`, thư mục cha chứa thêm CVAT và bản backup.
- Baseline: 184 file; `22a01f5`: 196 file (thêm 12 file hướng dẫn review). Inventory TSV đối chiếu baseline, không được hiểu là toàn bộ file working tree.
- File API/Docker/architecture/auto-tests/output cục bộ chưa theo dõi được liệt kê riêng trong báo cáo. Không dùng chúng để chứng nhận checkout GitHub.

## EV-01-002 — trước sửa

```text
pytest -q tests/test_cli.py tests/test_scan_gate.py tests/test_scan_wiring.py
19 passed in 1.28s (exit 0)
```

Test cũ cho phép job sạch thiếu manifest trả gate 0; scanner không có frames bỏ luật LiDAR. `gate_verdict` duyệt iterable hai lần nên generator bị cạn trước khi đếm warning. Bằng chứng code: `core/scanner.py:check_floating/check_box_points`, `core/gate.py:gate_verdict`, test CLI cũ trong `tests/test_scan_gate.py` tại baseline.

## EV-01-003 — sau sửa tập trung

```text
pytest -q tests/test_cli.py tests/test_scan_gate.py tests/test_scan_wiring.py tests/test_gate_coverage.py
32 passed in 1.58s (exit 0)
```

`test_gate_coverage.py` có 13 ca: nguồn cloud vắng, một frame thiếu pose, có pose, luật size-only, ground thưa, iterable generator, mã CLI 0/1/3 và Web persist coverage/verdict. CVAT mock, FlatGround và thư mục tạm riêng; không ghi CVAT thật.

## EV-01-004 — CLI và Web liên quan

```text
pytest -q tests/test_cli.py tests/test_scan_gate.py tests/test_scan_wiring.py tests/test_gate_coverage.py tests/test_web.py tests/test_web_a14.py tests/test_web_a15.py
61 passed, 1 warning in 4.78s (exit 0)
```

## EV-01-005 — suite mã nguồn sẽ push

```text
pytest -q --ignore=tests/test_report_api.py -p no:cacheprovider --basetemp <thư mục tạm mới dưới out/> --tb=short -ra
246 passed, 6 skipped, 1 warning in 5.40s (exit 0)
```

- `test_report_api.py` là file local chưa theo dõi, không được đưa lên nhánh này nên không tính vào suite công bố.
- 6 skip: 1 ground dùng dữ liệu thật, 2 CVAT live, 3 nuScenes thật. `POINTSNAP_LIVE_CVAT` được bỏ khỏi env test; `NUSCENES_ROOT` đặt vào đường dẫn không có dataset dưới out/ để không đọc `.env` hay chạy dataset của người dùng.
- 1 warning từ Starlette TestClient về httpx của môi trường hiện tại; không thêm dependency hoặc tắt warning để làm đẹp kết quả.
- Lần suite đầu có 1 ca E2E mock kỳ vọng gate ĐẠT dù bật luật LiDAR nhưng fixture không có cloud. Đã sửa ca này dùng cấu hình rõ ràng tắt 5 luật LiDAR; ca hồi quy mới vẫn bảo đảm cấu hình mặc định thiếu dữ liệu bị chặn.

## EV-01-006 — extension và JavaScript

```text
node --test extension/tests/core.test.js
7 passed, 0 failed (exit 0)
node --check pointsnap/web/static/app.js
exit 0
git diff --check
exit 0
```

Test logic thuần, không chạy Chrome/Edge hoặc CVAT UI.

## Cách chạy trong môi trường máy review

Venv launcher không tự nạp `.venv/Lib/site-packages`; thêm root tuyệt đối tránh conftest đổi cwd làm mất namespace `tests`. Với môi trường chuẩn đã cài `.[dev]`, dùng `python -m pytest` trực tiếp. Trong PowerShell máy này:

```powershell
.\.venv\Scripts\python.exe -c 'import os, sys, runpy, uuid; from pathlib import Path; root=Path.cwd(); sys.path[:0]=[str(root),str(root / ".venv/Lib/site-packages")]; os.environ["NUSCENES_ROOT"]=str(root / "out/review-no-real-dataset"); os.environ.pop("POINTSNAP_LIVE_CVAT",None); sys.argv=["pytest", "-q", "--ignore=tests/test_report_api.py", "-p", "no:cacheprovider", "--basetemp", str(root / "out" / ("review-01-"+uuid.uuid4().hex)), "--tb=short", "-ra"]; runpy.run_module("pytest",run_name="__main__")'
```

FastAPI TestClient bị treo trong sandbox hạn chế trên máy này; chạy ngoài sandbox cho kết quả EV-01-004/005. Không sửa code ứng dụng để chữa hạn chế môi trường. Kết quả này chưa chứng nhận Python 3.11/Node 22 của CI.

## EV-01-007 — chạy đủ các ca từng skip sau khi mở Docker

- CVAT Docker local `http://localhost:8080`, API version **2.78.1**; `/api/server/about` và token `/api/users/self`: HTTP 200.
- Dataset thật: `C:/Users/Han/Downloads/v1.0-mini`, 10 scene, 404 file `samples/LIDAR_TOP/*.bin`, có sweeps. Chỉ đọc dataset, không thêm dataset vào Git.
- Test ground sửa để nhận `NUSCENES_ROOT`, vẫn giữ mọi assertion: ≥50 box gần, >60% có ground estimate và trung vị lỗi <0,15 m. Ba test reader thật kiểm số scene và đối chiếu điểm nằm trong box của 2 scene (dung sai max(2 điểm, 10%), tỷ lệ >90%).
- Hai test CVAT live chạy upload/đọc lại annotation và ghi/gỡ cờ, kiểm bảo toàn hình học. Task thử tạo riêng và xóa trong `finally`; kiểm tra sau lượt chạy cuối tìm `PointSnap live test` trả count=0, IDs=[]; không sửa job người dùng.
- Lần đầu 2 test reader bị lỗi in tiếng Việt vì stdout cp1252; chuyển stdout/stderr của tiến trình test sang UTF-8. Khi chạy chung suite, test dotenv để lại token giả gây HTTP 401; đã cô lập `os.environ` trong test đó. Không thay đổi token người dùng hoặc nới assertion.

```text
pytest -q --ignore=tests/test_report_api.py -p no:cacheprovider --basetemp <thư mục mới dưới out/> --tb=short -ra
POINTSNAP_LIVE_CVAT=1, NUSCENES_ROOT=C:/Users/Han/Downloads/v1.0-mini
252 passed, 0 skipped, 1 warning in 22.53s (exit 0)
```

Lệnh thực tế trên máy review, từ tool root:

```powershell
.\.venv\Scripts\python.exe -c 'import os, sys, runpy, uuid; from pathlib import Path; root=Path.cwd(); sys.path[:0]=[str(root),str(root / ".venv/Lib/site-packages")]; sys.stdout.reconfigure(encoding="utf-8"); sys.stderr.reconfigure(encoding="utf-8"); os.environ["NUSCENES_ROOT"]="C:/Users/Han/Downloads/v1.0-mini"; os.environ["POINTSNAP_LIVE_CVAT"]="1"; sys.argv=["pytest", "-q", "--ignore=tests/test_report_api.py", "-p", "no:cacheprovider", "--basetemp", str(root / "out" / ("review-01-full-live-"+uuid.uuid4().hex)), "--tb=short", "-ra"]; runpy.run_module("pytest",run_name="__main__")'
```

Đây là kết quả cuối thay cho trạng thái skip ở EV-01-005. Chưa chạy kiểm tra bằng mắt trong trình duyệt hay đo precision xem tay. CVAT 2.78.1 khác mốc chuẩn 2.77.0/2.77.1 trong tài liệu; kết quả này chứng minh hai luồng API trên phiên bản thực tế của máy, không chứng nhận mọi phiên bản CVAT.

## EV-01-008 — kiểm tra tài liệu bàn giao

Kiểm bằng Python standard library và Git: inventory khớp đúng 184 file baseline, đủ 14 mã ca R01-01–14 và 8 findings RV-01-001–008; các đường dẫn Markdown nội bộ trong tài liệu thay đổi đều tồn tại, code fences cân bằng. Kết quả mã 0; `git diff --check` mã 0. Đây là kiểm tra cấu trúc/tham chiếu, không kiểm nội dung website ngoài repo.
