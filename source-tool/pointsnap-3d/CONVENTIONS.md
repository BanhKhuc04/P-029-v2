# Quy ước dùng chung

Mọi module (core, adapter, báo cáo) theo đúng quy ước trong file này. Đổi quy ước thì sửa file này **trong cùng PR**.

Ký hiệu: ✅ đã xác minh · ⬜ chưa xác minh (ghi việc sẽ xác minh)

## 1. Hệ tọa độ trong core

| Mục | Quy ước |
|---|---|
| Đơn vị | Mét, giây, radian |
| Hệ trục | Tay phải, **z hướng lên** |
| Box nằm trong hệ nào | Hệ tọa độ point cloud của chính frame đó. Khi xuất sang CVAT (`to-cvat`, việc A2), point cloud và box được xoay 90° quanh trục z sang hệ **xe thu** (x hướng trước, y sang trái, z hướng lên, [QĐ-008](../../so-quyet-dinh.md#qđ-008)) để xe thu và dòng xe chạy dọc trục +x của canvas 3D (mũi tên đỏ) và camera perspective nhìn thẳng dọc đường |
| `Cuboid.center` | Tâm hình học của box |
| `Cuboid.dims` | `(length, width, height)`. **length nằm dọc trục x local của box** (hướng đầu xe, [QĐ-008](../../so-quyet-dinh.md#qđ-008)), width theo y local, height theo z |
| `Cuboid.yaw` | Góc quay quanh trục z, đi từ trục +x của hệ point cloud tới trục x local của box, ngược chiều kim đồng hồ nhìn từ trên xuống. Luôn chuẩn hóa về [-π, π) |
| Roll, pitch | Core coi bằng 0. Adapter giữ giá trị gốc trong `attrs` để ghi ngược lại không bị mất |
| Đáy box | `bottom_z = center_z − height / 2` |
| Thứ tự 8 góc (`geometry.corners`) | 4 góc đáy rồi 4 góc nóc; mỗi mặt đi ngược chiều kim đồng hồ từ góc trước-trái: (+l, +w), (−l, +w), (−l, −w), (+l, −w) |

## 2. CVAT: cuboid 3D

✅ Xác minh trong mã nguồn CVAT 2.77.1 (commit `4b017e6`, `D:\Work\cvat`):

| Mục | Giá trị | Nguồn |
|---|---|---|
| `points` của shape `cuboid` trong task 3D | 16 số: `[px, py, pz, rx, ry, rz, sx, sy, sz, 0, 0, 0, 0, 0, 0, 0]` | `cvat/apps/dataset_manager/bindings.py` (đọc `dm_points[0:3]`, `[3:6]`, `[6:9]`; ghi thêm 7 số 0) |
| `px, py, pz` | Tâm hình học: box là `BoxGeometry(1, 1, 1)` đặt tại gốc rồi dịch tới position | `cvat-canvas3d/src/typescript/cuboid.ts` |
| `rx, ry, rz` | Góc Euler (radian), thứ tự XYZ mặc định của three.js | `cuboid.ts` (`rotation.set(x, y, z)`) |
| `sx, sy, sz` | Kích thước đầy đủ theo trục x, y, z local | `canvas3dView.ts` (`setScale(points[6], points[7], points[8])`) |

**Ánh xạ sang core:** `Cuboid(center=(px, py, pz), dims=(sx, sy, sz), yaw=rz)`, giữ `rx, ry` trong `attrs` (`cvat_rx`, `cvat_ry`).
Ghi ngược lại: `points = [*center, rx, ry, yaw, *dims, 0, 0, 0, 0, 0, 0, 0]` (`adapters/cvat/shapes.py`).

**Task do `pointsnap nuscenes to-cvat --upload` tạo** (`datasets/nuscenes/to_cvat.py`):
- 10 label kiểu `cuboid`; mỗi label có thuộc tính `pointsnap_error` (text) và `reviewed` (checkbox), cả hai `mutable` (giá trị riêng từng frame).
- Dữ liệu tải lên là một file zip các `.pcd` tên `000000.pcd`, `000001.pcd`, …; CVAT sắp frame theo tên (`sorting_method=lexicographical`), nên frame CVAT = frame trong `manifest.json`.
- Mỗi đối tượng nuScenes là một track. Trong CVAT một track kéo dài tới cuối job cho tới khi gặp keyframe `outside`, nên: sau frame cuối của track thêm một keyframe `outside`; khi track khuyết frame ở giữa thì thêm `outside` ngay sau frame có mặt cuối cùng.
- Bản xuất ghi kèm `manifest.json` (frame ↔ file ↔ `sample_token` ↔ `sensor_to_world`), `ground_truth.json` (nhãn chuẩn) và sau khi tải lên là `cvat_task.json` (id task, id job).

Xác minh trên CVAT 2.77.1 chạy thật (06/10, task thử tạo từ bộ nuScenes giả; `tests/test_live_cvat.py`):
- [x] Gửi box qua API rồi đọc lại: tâm, kích thước, yaw khớp tuyệt đối (lệch 0 mm, 0 rad).
- [x] API chỉ nhận `Accept: application/vnd.cvat+json`; gửi `application/json` bị HTTP 406.
- [x] `GET /api/jobs/<id>/annotations`: mỗi track chỉ chứa **keyframe nhập tay**; mỗi keyframe có `id`, `frame`, `outside`, `points`, `attributes`. Keyframe `outside=true` nằm ở frame đầu tiên đối tượng vắng mặt.
- [x] `GET /api/tasks/<id>/data/meta`: `frames[].name` theo đúng thứ tự frame (`000000.pcd`, …) → dùng để khớp với `manifest.json`.
- [x] Link mở thẳng một frame: `<url>/tasks/<task>/jobs/<job>?frame=<n>` (route `/tasks/:tid/jobs/:jid`, tham số `frame` trong `cvat-ui`).
- [ ] Trục lên của canvas 3D là +z, box nhìn đúng trên point cloud thật (kiểm bằng mắt ở G0).
- [ ] Ghi thuộc tính `pointsnap_error` qua API rồi lọc được trong canvas 3D (A4).
- [ ] Phiên bản CVAT của BTC (`cvat.note.transformerlabs.ai`) có cùng định dạng `points`.

## 3. nuScenes v1.0-mini

Đã cài đặt trong `pointsnap/adapters/nuscenes/reader.py` (B1) và kiểm bằng bộ dữ liệu giả có đáp án tính tay (`tests/fake_nuscenes.py`).
⬜ Còn phải xác minh trên dữ liệu thật: box chuẩn nằm đúng trên các điểm của đối tượng (C3).

| Mục | Giá trị |
|---|---|
| Nhãn `sample_annotation` | `translation` = tâm box, **hệ toàn cục**; `size` = **[width, length, height]**; `rotation` = quaternion **[w, x, y, z]**, hệ toàn cục |
| Đổi nhãn về hệ LiDAR | toàn cục → xe thu (`ego_pose` của `sample_data` LIDAR_TOP) → cảm biến (`calibrated_sensor`) |
| Point cloud `.pcd.bin` | `float32`, 5 giá trị mỗi điểm: x, y, z, intensity, ring index. Không phải PCD chuẩn, phải chuyển đổi |
| Tần số keyframe | 2 Hz, cách nhau ≈ 0,5 giây. Chỉ dùng keyframe của `LIDAR_TOP`, bỏ sweep |
| Thứ tự frame | Đi theo chuỗi `first_sample_token` → `next` của cảnh; frame đánh số từ 0 |
| Track id | Số thứ tự của `instance` trong bảng `instance.json`: cố định giữa các lần chạy và giữa các cảnh |
| Class | Ánh xạ category nuScenes sang 10 class của task theo bảng chuẩn của bài toán detection nuScenes (`CATEGORY_TO_LABEL` trong `reader.py`). Category khác (động vật, xe cấp cứu, xe đẩy, xe lăn, vật cản rời, giá để xe…) bị bỏ qua |
| Box không có điểm | Bỏ box có `num_lidar_pts` < 1 (tham số `min_lidar_points`): người gán không thấy box đó trên point cloud. Vì vậy một track có thể khuyết vài frame ở giữa |
| Box nghiêng | Box nuScenes chỉ quay quanh trục z toàn cục; đổi sang hệ LiDAR có thể nghiêng nhẹ. Core giữ yaw, ghi góc nghiêng vào `attrs["tilt_rad"]` |

## 4. Mã luật và mức

| `rule` | Loại lỗi | Ý nghĩa |
|---|---|---|
| `floating` | Lơ lửng / lún | Khoảng cách đáy box tới mặt đất cục bộ vượt ngưỡng |
| `floating.no_evidence` | Lơ lửng / lún | Vành đai quanh box có quá ít điểm ground; mức Thông tin |
| `size.class_range` | Sai kích thước | l, w hoặc h nằm ngoài khoảng thường gặp của class |
| `size.in_track` | Sai kích thước | Kích thước một keyframe lệch so với trung vị của track |
| `track.jump` | Đứt track | Tâm box lệch khỏi vị trí nội suy từ hai keyframe lân cận |
| `track.split_id` | Đứt track | Track kết thúc rồi một track cùng class bắt đầu ngay gần đó |
| `track.long_interpolation` | Đứt track | Đoạn dài chỉ có box nội suy trong khi đối tượng di chuyển (B5b) |

Mức: `error` (Lỗi) · `warning` (Cảnh báo) · `info` (Thông tin). Câu thông báo luôn có số đo cụ thể, ví dụ *"Đáy box cách mặt đất 22 cm"*.

## 5. Cấu hình và bí mật

- Ngưỡng nằm trong `pointsnap/config.yaml`. Muốn thử ngưỡng khác: tạo file chỉ chứa phần cần đổi, chạy `pointsnap --config <file> ...`. Khóa gõ sai bị báo lỗi ngay.
- Token CVAT chỉ đặt qua biến môi trường `CVAT_TOKEN`; ghi token trong file cấu hình sẽ bị từ chối.
- Thứ tự ưu tiên của URL CVAT, từ thấp tới cao: `config.yaml` mặc định → biến môi trường `CVAT_URL` → file `--config`.
- `CVAT_AUTH_SCHEME`: `Bearer` (mặc định, dùng cho Personal Access Token tạo trong giao diện CVAT) hoặc `Token` (token cũ lấy từ `/api/auth/login`).
- `NUSCENES_ROOT`: thư mục dữ liệu nuScenes, dùng làm mặc định cho `--dataroot`.
- Không commit dữ liệu nuScenes, file `.pcd`, báo cáo hay bản chụp nhãn (đã có trong `.gitignore`).
