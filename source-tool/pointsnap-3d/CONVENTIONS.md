# Quy ước dùng chung

Mọi module (core, adapter, báo cáo) theo đúng quy ước trong file này. Đổi quy ước thì sửa file này **trong cùng PR**.

Ký hiệu: ✅ đã xác minh · ⬜ chưa xác minh (ghi việc sẽ xác minh)

## 1. Hệ tọa độ trong core

| Mục | Quy ước |
|---|---|
| Đơn vị | Mét, giây, radian |
| Hệ trục | Tay phải, **z hướng lên** |
| Box nằm trong hệ nào | Hệ tọa độ point cloud của chính frame đó (hệ LiDAR). Muốn so giữa các frame (luật đứt track) thì đổi sang hệ toàn cục bằng `FrameData.sensor_to_world` |
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

**Ánh xạ sang core:** `Cuboid(center=(px, py, pz), dims=(sx, sy, sz), yaw=rz)`, giữ `rx, ry` trong `attrs`.
Ghi ngược lại: `points = [*center, rx, ry, yaw, *dims, 0, 0, 0, 0, 0, 0, 0]`.

⬜ Cần xác minh trên CVAT chạy thật (việc C4, A3):
- [ ] Trục lên của canvas 3D là +z; đơn vị trên canvas là mét như trong file point cloud.
- [ ] Đặt một box tại điểm đã biết, đọc lại qua API ra đúng các số trên.
- [ ] Track qua API trả về những frame nào: chỉ keyframe nhập tay hay cả frame nội suy; cờ `outside` nằm ở đâu.
- [ ] Ghi thuộc tính `pointsnap_error` qua API rồi lọc được trong canvas 3D.
- [ ] Định dạng link mở thẳng một frame (dự kiến `<url>/jobs/<job>?frame=<n>`, giống link trong `problem-backlog.md`).
- [ ] Phiên bản CVAT của BTC (`cvat.note.transformerlabs.ai`) có cùng định dạng `points`.

## 3. nuScenes v1.0-mini

⬜ Theo tài liệu nuScenes; xác minh khi làm B1 và A2:

| Mục | Giá trị |
|---|---|
| Nhãn `sample_annotation` | `translation` = tâm box, **hệ toàn cục**; `size` = **[width, length, height]**; `rotation` = quaternion **[w, x, y, z]**, hệ toàn cục |
| Đổi nhãn về hệ LiDAR | toàn cục → xe thu (`ego_pose` của `sample_data` LIDAR_TOP) → cảm biến (`calibrated_sensor`) |
| Point cloud `.pcd.bin` | `float32`, 5 giá trị mỗi điểm: x, y, z, intensity, ring index. Không phải PCD chuẩn, phải chuyển đổi |
| Tần số keyframe | 2 Hz, cách nhau ≈ 0,5 giây |
| Class | Ánh xạ category nuScenes (ví dụ `vehicle.car`, `human.pedestrian.adult`) sang 10 class của task: `car`, `truck`, `bus`, `trailer`, `construction_vehicle`, `pedestrian`, `motorcycle`, `bicycle`, `traffic_cone`, `barrier`. Bảng ánh xạ chốt ở B1 |

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
- Không commit dữ liệu nuScenes, file `.pcd`, báo cáo hay bản chụp nhãn (đã có trong `.gitignore`).
