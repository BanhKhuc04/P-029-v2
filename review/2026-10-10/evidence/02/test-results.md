# Bằng chứng kiểm tra phần 02

Ngày 11/10/2026, Asia/Saigon. Mốc trước sửa `1c3a761`; bản sửa code `2e3417db612fdc4442062c7d227bca9f12af064b`. Nhánh `review/02-core-detectors`. Không lưu token/annotation người dùng vào bằng chứng.

## EV-02-001 — môi trường và phạm vi

- Windows, Python 3.12.14, pytest 9.1.1, Node v24.19.0.
- `git fetch origin main`: exit 0, main vẫn `5dcc97f`; đã tạo branch từ phần 01 để dùng hợp đồng gate và test live.
- CVAT Docker local: API version 2.78.1. Dataset `C:/Users/Han/Downloads/v1.0-mini`, nguồn thật đã dùng ở phần 01.
- Code/API/Docker/auto-tests local chưa tracked được giữ ngoài commit. `tests/test_report_api.py` không thuộc mã nguồn sẽ push nên không tính vào suite này.

## EV-02-002 — tái hiện trước sửa

Các ca mới không nới assertion để đạt. Bằng chứng theo từng bước code:

```text
Đợt hồi quy ban đầu: 26 failed, 3 passed in 2.64s (exit 1)
Sau bản sửa đầu: 29 passed in 1.04s (exit 0)
Thêm timestamp/track còn chạy/subtype: 3 failed, 29 passed in 2.41s (exit 1)
Thêm đuôi occluded: 1 failed in 1.64s (exit 1)
Thêm dữ liệu nội suy: 2 failed, 63 deselected in 1.72s (exit 1)
```

Fixture trước/sau gồm quaternion 1e±300 (ma trận phải vẫn quay 90°), points/pose NaN/sai shape, điểm box xoay, hai subtype có kích thước hợp lệ, hướng trục ở ±44°, pose thiếu ở một track, timestamp epoch thiếu frame, CVAT track chưa outside, đuôi occluded và box nội suy. Các ca biên/switch/permutation bổ sung để kiểm 16 nội dung của phần 02.

## EV-02-003 — kiểm tra cuối

```text
317 passed, 0 skipped, 1 warning in 22.34s (exit 0)
```

Lệnh trên máy review, chạy từ tool root:

```powershell
.\.venv\Scripts\python.exe -c 'import os,sys,runpy,uuid; from pathlib import Path; root=Path.cwd(); sys.path[:0]=[str(root),str(root / ".venv/Lib/site-packages")]; sys.stdout.reconfigure(encoding="utf-8"); sys.stderr.reconfigure(encoding="utf-8"); os.environ["NUSCENES_ROOT"]="C:/Users/Han/Downloads/v1.0-mini"; os.environ["POINTSNAP_LIVE_CVAT"]="1"; sys.argv=["pytest","-q","--ignore=tests/test_report_api.py","-p","no:cacheprovider","--basetemp",str(root / "out" / ("review-02-complete-"+uuid.uuid4().hex)),"--tb=short","-ra"]; runpy.run_module("pytest",run_name="__main__")'
```

- 252 ca nền phần 01 + **65 ca hồi quy/biên/wiring mới**.
- Bật CVAT live và dataset thật; test tạo task thử và tự xóa, không sửa job người dùng.
- TestClient cần chạy ngoài sandbox hạn chế trên máy này; thư mục test tạm duy nhất dưới out/.
- 1 warning Starlette TestClient/httpx của môi trường được giữ nguyên. Không thêm dependency, không che warning.
- Không kèm `test_report_api.py` vì file API/test đó chưa được theo dõi hoặc đẩy lên nhánh.

## EV-02-004 — quét scene thật

Reader nuScenes thật → add_track_markers → scanner sáu nhóm luật, config mặc định với env={}, sweeps=4, không ghi CVAT:

```json
{
  "scene": "scene-0061",
  "frames": 39,
  "visible_boxes": 3333,
  "seconds": 19.068,
  "counts": {
    "fit.empty/warning": 7,
    "fit.loose/warning": 6,
    "fit.outside/error": 2,
    "floating.no_evidence/info": 102,
    "floating/error": 2,
    "floating/warning": 25,
    "heading.points/warning": 1,
    "size.class_range/warning": 1,
    "track.jump/error": 2,
    "track.jump/warning": 4
  }
}
```

Mã 0. Đây là chạy một scene tuning để xác minh code đọc dữ liệu/sweeps và hoàn tất scan; không coi 44 warning/6 error là các lỗi thật đã xem tay. Lượt scan dùng bản đang sửa trước khi bổ sung guard proxy nội suy cuối cùng; nguồn nuScenes/marker ở lượt này đều có keyframe=True nên guard đó không đổi đường chạy. Suite cuối đã kiểm bản code hoàn tất.

## EV-02-005 — extension, diff và dọn task

```text
node --test extension/tests/core.test.js
7 passed, 0 failed (exit 0)
git diff --check
exit 0
CVAT server/about: version 2.78.1
Tìm tasks với search=PointSnap live test: count=0
```

## EV-02-006 — kiểm tra tài liệu

Kiểm bằng Python standard library trước commit tài liệu, exit 0:

```text
PASS: 11 documents; 71 relative links; balanced fences; 16 review cases; 15 findings; 18 rules
git diff --check: exit 0
```

Đủ 16 mã R02-01–16, 15 findings RV-02-001–015 và 18 rule trong ma trận. Các liên kết nội bộ tồn tại; code fences cân bằng.
