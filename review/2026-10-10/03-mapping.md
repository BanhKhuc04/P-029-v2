# Mapping và hợp đồng bảo toàn dữ liệu — phần 03

Code được kiểm: `40ac166`; nhánh `review/03-data-cvat-integrations`, tiếp nối `82fc8b8` của phần 02. Đường dẫn module tính từ `source-tool/pointsnap-3d`.

## 1. Tọa độ và trường dữ liệu

| Nguồn | Core | CVAT / bản xuất | Đơn vị, ưu tiên và kiểm tra |
|---|---|---|---|
| nuScenes `translation`, quaternion `[w,x,y,z]` toàn cục | `T_sensor_world⁻¹ × T_box_world`; center trong LiDAR, yaw từ trục x quay | Quay `(x,y,z)→(y,−x,z)` và yaw−π/2 cho box/điểm; pose mới `T_sensor_world × R⁻¹` | Mét/radian. Fixture frame 0: center `(0,−10,−1.2)`; quay xuất thành `(−10,0,−1.2)`. Đổi ngược world phải là `(11,0,0.8)` |
| nuScenes `size=[w,l,h]` | `dims=(l,w,h)` | `points[6:9]=[l,w,h]` | Không đổi dims để bù yaw; fixture `(4.5,2,1.6)` |
| CVAT `points[0:3]`, `[3:6]`, `[6:9]` | center, yaw=`rz`; `rx/ry` trong `cvat_rx/cvat_ry` | Writer giữ toàn bộ points gốc, kể cả 7 số đuôi | 16 số theo CVAT 2.78.1 đã chạy; parser còn nhận tối thiểu 9 số để tương thích. Tâm/góc/dims phải hữu hạn; dims dương |
| nuScenes `.pcd.bin` | `(N,5)` float32: XYZ/intensity/ring | PCD binary little endian `(N,4)`, bỏ ring | Số byte chia hết 20; XYZ/intensity hữu hạn. PCD SIZE=4, TYPE=F, COUNT=1; WIDTH×HEIGHT=POINTS. ASCII/compressed được từ chối rõ, không phải tính năng đã hỗ trợ |
| `sample_data` LIDAR_TOP keyframe | SampleRef theo chuỗi sample của đúng scene | frame 0..N−1; tên `000000.pcd` trong ZIP `pointcloud/` | Không lấy camera/sweep làm keyframe; từ chối token trùng, chuỗi lặp/sai scene, sai số lượng/cuối cảnh và timestamp không tăng |
| Timestamp µs | giây trong FrameData | timestamp manifest | Không dùng thời gian camera thay cho LiDAR. Metadata timestamp/pose manifest phải khớp dataset hiện tại |
| Calibration + ego_pose tại mỗi LiDAR | `T_ego_world × T_sensor_ego` | pose manifest khớp cùng transform với điểm xuất | Transform phải quay 3×3 hợp lệ, giữ z lên. Manifest ghi hệ ego nhưng thiếu transform bị từ chối |
| Sweep trước keyframe | `T_key_world⁻¹ × T_sweep_world`, điểm trong LiDAR keyframe | Quay bằng cùng R như PCD/keyframe | File thiếu: dùng số sweep có; file corrupt: lỗi rõ. Đây là giảm số mẫu mặt đất, không khẳng định đã có đủ sweep yêu cầu |
| Sáu camera, cùng `sample_token` | Không vào core detector | `related_images/000000_pcd/CAM_*.jpg`; manifest `images` | Chỉ ảnh keyframe; file ảnh không có được bỏ qua và thể hiện qua count. Scene-0061 đủ 234 ảnh/39 frame, CVAT meta có 6 related_files/frame |

Tên `coordinate_system="ego"` là tên đã dùng cho **hệ hiển thị quay cố định −90°**, giữ gốc LiDAR. Nó không có nghĩa đã đổi đầy đủ về gốc xe thu bằng calibration và loại bỏ roll/pitch. Tọa độ world vẫn đúng nhờ pose đi kèm. Core detector dùng mô hình yaw; nghiêng của nuScenes được lưu `tilt_rad`, không được coi là hình học Euler đầy đủ đã nghiệm thu.

## 2. Frame, nguồn dữ liệu, taxonomy và ID

| Nội dung | Hợp đồng |
|---|---|
| Manifest | Bản xuất toàn scene: đủ frame 0..N−1, tên file không trùng; sample_token đúng thứ tự của dataset; count/pose/time/transform hợp lệ trước scan |
| CVAT job nằm giữa task | `JobData.start_frame/stop_frame` dùng frame của task; danh sách tên frame lấy từ metadata toàn task. So tên basename theo thứ tự; không tự cộng offset để che mismatch |
| Auto tìm manifest | Khớp **URL CVAT và task_id** trong cvat_task.json. Hai server có cùng task ID không dùng chung point cloud. Bản cũ thiếu URL cần tạo lại metadata hoặc chỉ manifest rõ sau khi xác minh |
| Dataroot | Tham số dự án/CLI ưu tiên, sau đó NUSCENES_ROOT, sau đó dataroot manifest. Chuyển máy được nếu tables/sample metadata vẫn khớp |
| nuScenes ID | instance_token→số thứ tự instance.json; ổn định với cùng tables. CVAT cấp track/shape ID riêng; không so hai loại ID như một |
| CVAT ID | Track dùng track_id và frame, source_id là ID keyframe; shape lẻ dùng shape ID và frame. Finding thiếu ID không được gắn đại cả frame |
| Track markers | Vắng ≤6 frame: thêm occluded, nội suy vị trí; >6: outside và track mới; hết trước cuối scene: thêm outside. 0 finding không chứng minh không sót đối tượng |
| Keyframe | API job trả các keyframe lưu trong CVAT; core giữ outside/occluded. Không tái tạo toàn bộ box nội suy để coi là nhãn nhập tay |
| Thuộc tính | Track base→giá trị keyframe theo thời gian→giữ tới lần ghi giá trị mới; rỗng là reset rõ. Không phụ thuộc thứ tự mảng API |
| Taxonomy | `nuscenes`: 10 class, category ngoài bảng bỏ chủ đích; min_lidar_points mặc định 1. `spec-vn`: 5 class, subtype/rider_state/age_group/pose… theo bảng taxonomy; một số giá trị pose/rider suy ra/default, cần xem tay khi dùng làm ground truth thật |

## 3. Ghi cờ, snapshot và bảo toàn

- Cờ phải là thuộc tính mutable. Ghi chuỗi ở keyframe mục tiêu và reset rỗng ở keyframe kế tiếp nếu cần; không xóa entry rồi để cờ trước đó kế thừa lại. Giữa hai keyframe, CVAT vẫn kế thừa thuộc tính theo cách hiển thị của nó.
- Writer GET mới, so geometry/state/attrs chưa liên quan với JobData đã scan; nếu đổi thì yêu cầu quét lại. Chỉ khớp lại source_id mới của track khi finding thuộc keyframe đã scan và chữ ký nhãn chưa đổi; ID lạ được đếm unmatched.
- Trước PATCH, GET lần nữa và yêu cầu payload chưa đổi. **Còn cửa sổ race giữa GET cuối và PATCH** vì adapter/API này chưa có điều kiện ghi atomic được xác minh. Tránh sửa cùng job trong lúc tool ghi cờ; không khẳng định đã giải quyết đồng thời nhiều client.
- PATCH gửi đủ track gốc; ngoài cờ/reset không đổi points, roll/pitch, outside, occluded, keyframes, attrs khác, group/source/elements. GET sau thao tác có thể cấp ID keyframe mới.
- `save_snapshot`: JSON version 1 UTF-8, metadata job/task/range/URL, cuboids chuẩn hóa; khi load từ CVAT có thêm `meta.cvat_annotations` là payload gốc gồm tags/shapes/tracks/version. Snapshot không chứa token và giữ ngoài Git; đây là dữ liệu khôi phục/đối chiếu, chưa thêm nút rollback tự động.
- `verify_geometry_preserved`: so theo frame/track/label và hình học, không dùng source ID mới như ID cũ. Kiểm center/dims/yaw/roll/pitch và các trạng thái với dung sai tuyệt đối 1e−6 m/rad.
- Upload chỉ nạp nhãn vào task mới tạo. Nếu upload/nạp nhãn/lấy job thất bại thì xóa đúng task vừa tạo; nếu cleanup thất bại, lỗi nêu task ID để xử lý. Không xóa task làm việc có sẵn.

Kiểm thật, lệnh và giới hạn: [bằng chứng](evidence/03/test-results.md). Findings và 18 ca: [báo cáo](03-report.md).
