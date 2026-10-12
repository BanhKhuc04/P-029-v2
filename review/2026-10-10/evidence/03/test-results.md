# Bằng chứng kiểm tra phần 03

Ngày 11/10/2026, Asia/Saigon. Mốc trước sửa `82fc8b8`; code `40ac166cbdb17aa9d234a55cfd7944165e588a2a`. Không lưu token/nhãn người dùng vào Git.

## EV-03-001 — tái hiện và kiểm lại

```text
Ca hồi quy đầu trước sửa: 26 failed, 5 passed, 1 warning in 0.90s (exit 1)
Adapter + hồi quy + CVAT live sau sửa: 91 passed in 10.11s (exit 0)
Suite toàn bộ lần đầu: 360 passed, 1 warning in 27.43s (exit 0)
Suite cuối: 367 passed, 0 skipped, 1 warning in 32.45s (exit 0)
```

Suite cuối gồm 317 ca nền phần 02 + **49 hồi quy phần 03** + **1 live mới**. Warning Starlette TestClient/httpx của môi trường được giữ nguyên; không thêm dependency/che warning.

Lệnh chạy từ `source-tool/pointsnap-3d` trên máy review:

```powershell
.\.venv\Scripts\python.exe -c 'import os,sys,runpy,uuid; from pathlib import Path; r=Path.cwd(); sys.path[:0]=[str(r),str(r / ".venv/Lib/site-packages")]; sys.stdout.reconfigure(encoding="utf-8"); sys.stderr.reconfigure(encoding="utf-8"); os.environ["NUSCENES_ROOT"]="C:/Users/Han/Downloads/v1.0-mini"; os.environ["POINTSNAP_LIVE_CVAT"]="1"; sys.argv=["pytest","-q","--ignore=tests/test_report_api.py","-p","no:cacheprovider","--basetemp",str(r / "out" / ("review-03-final-"+uuid.uuid4().hex)),"--tb=short","-ra"]; runpy.run_module("pytest",run_name="__main__")'
```

Đã chạy ngoài sandbox hạn chế để TestClient/local CVAT hoạt động. API/test_report_api local chưa tracked không thuộc suite nguồn được push. Ba test CVAT live tự tạo và xóa task riêng; dataset thật vẫn bật. Bản final chạy trước đổi tên ca live cho chính xác thành `test_flag_tilted_shapes_preserves_all_other_annotations` và dọn import không dùng; không đổi logic/assertion.

## EV-03-002 — round-trip scene thật

NuScenesReader → export_scene (with_images=True) → upload_scene → load_job/ManifestFrames → flag lần một/lần hai → clear → đọc lại. Đường dẫn dữ liệu `C:/Users/Han/Downloads/v1.0-mini`; scene-0061, taxonomy nuscenes, mặc định min_lidar_points=1; output/snapshot đầy đủ ở `out/review-03-real/` ngoài Git.

```json
{
  "cvat_version": "2.78.1",
  "task_id": 27,
  "job_id": 27,
  "frames": 39,
  "images": 234,
  "related_files_per_frame": 6,
  "visible_ground_truth_boxes": 3333,
  "keyframes_including_markers": 3900,
  "tracks": 249,
  "max_center_delta_m": 0.0,
  "max_yaw_delta_rad": 0.0,
  "first_flagged": 1,
  "repeat_flagged": 0,
  "cleared": 1,
  "seconds": 9.938
}
```

Exit 0, dims khớp; helper verify kiểm geometry/state trước/sau cờ. Lượt này dùng bản sửa trước guard metadata pose/time cuối; manifest gốc hợp lệ nên guard không đổi đường chạy. Suite cuối đã kiểm guard mới. Đây là thực thi một scene, không đo precision/recall hoặc benchmark lặp.

## EV-03-003 — trình duyệt và cleanup

- Browser CVAT local đã có phiên đăng nhập, task/job 27.
- URL `/tasks/27/jobs/27?frame=0&type=track&serverID=487` mở đúng `pointcloud/000000.pcd`, chọn 1 CUBOID TRACK pedestrian. DETAILS L/W/H = 0,67/0,62/1,64 m, khớp target API.
- Canvas có point cloud và các góc nhìn Top/Side/Front. Ảnh ngữ cảnh CAM_BACK/BACK_LEFT/BACK_RIGHT hiện ngay; mở bộ chọn và lần lượt chọn FRONT/FRONT_LEFT/FRONT_RIGHT, ảnh thật hiển thị. Danh sách có đủ 6 camera, metadata của cả 39 frame có 6 related_files.
- Không chỉnh geometry/attrs hoặc bấm Save trong trình duyệt. Các screenshot đã xem trong lượt chạy; chưa xuất tệp ảnh vào Git.
- Xóa task 27 qua API, exit 0; search `PointSnap review 03` còn **0**. Ba task fixture của suite tự xóa; kiểm task tồn cuối trước push.
- Shape URL/roll-pitch/attrs được kiểm unit và ca live shape lẻ. UI shape URL riêng/extension và server BTC chưa được nghiệm thu.

## EV-03-004 — Node, diff, cấu trúc tài liệu

```text
node --test extension/tests/core.test.js
7 passed, 0 failed, 0 skipped (exit 0)
git diff --check
exit 0
```

Commit `8d81c20` chỉ đổi xuống dòng 2 file cũ; `git diff --cached --ignore-space-at-eol --exit-code` đạt trước commit. Logic sửa ở commit riêng `40ac166`.

Kiểm bằng Python standard library trước commit tài liệu, exit 0:

```text
PASS: 8 documents; 63 relative links; balanced fences; 18 review cases; 16 findings
```

## EV-03-005 — kiểm lại cả ba nhánh

Cùng lệnh EV-03-001, chạy riêng trên mỗi nhánh sau sửa RV-01-009.

```text
01: 256 passed, 0 skipped, 1 warning in 22.96s (exit 0)
02: 321 passed, 0 skipped, 1 warning in 23.49s (exit 0)
03: 371 passed, 0 skipped, 1 warning in 29.14s (exit 0)
```

Code gate 0727c15; 02 sau merge 744acfe, 03 sau merge b841f63. Full suite của 03 chạy tên ca live đã chỉnh cho chính xác; không file nguồn thay đổi sau lần này, chỉ bổ sung báo cáo.

Kiểm cuối: 7 tài liệu/61 links tương đối/fences cân bằng/không conflict marker đạt; extension tree giống nhau trên 01/02/03 (`dda4545adb29ab1a435a690d6af132fd90853283`). CVAT 2.78.1 trả count=0 cho cả `PointSnap live test` và `PointSnap review 03` sau toàn bộ suite. Merge-base xác nhận chuỗi tổ tiên 01→02→03, exit 0.
