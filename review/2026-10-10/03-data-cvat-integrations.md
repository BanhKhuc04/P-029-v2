# 03 — Review dữ liệu, nuScenes và tích hợp CVAT

**Nhánh:** `review/03-data-cvat-integrations`.
**Trạng thái:** hoàn tất review phần 03 trong phạm vi [báo cáo](03-report.md); 367 pytest + 7 Node đạt, 0 skip trong suite bàn giao.
**Đầu ra:** [bàn giao](03-handoff.md), [mapping](03-mapping.md), [bằng chứng](evidence/03/test-results.md). Dependency phần 02 tại `82fc8b8`.

Đọc [quy trình chung](README.md), [mẫu báo cáo](report-template.md), CONVENTIONS và invariant phần 02. Đường dẫn dưới đây tính từ tool root.

## 1. Mục tiêu

Chứng minh dữ liệu từ nuScenes/CVAT vào core có tọa độ, frame, ID và thuộc tính đúng; xuất lại hoặc gắn/gỡ cờ không làm hỏng hình học, track và nhãn chưa liên quan. Phân biệt kiểm mock, fixture tính tay và CVAT/dataset thật.

## 2. Phạm vi

| Module | Hợp đồng phải kiểm |
|---|---|
| `pointsnap/adapters/nuscenes/reader.py` | JSON tables, quaternion, pose, keyframe/sweeps, `.pcd.bin`, filtering theo số điểm |
| `pointsnap/datasets/pcd.py`, `taxonomy.py` | Encoding PCD, dims/class/attribute mapping, class bị loại và spec-vn |
| `pointsnap/datasets/nuscenes/to_cvat.py` | PCD/ảnh camera/ZIP, manifest/ground_truth, track markers, upload task |
| `pointsnap/adapters/cvat/client.py` | Auth scheme, media type, pagination, timeout, upload polling và lỗi HTTP |
| `pointsnap/adapters/cvat/reader.py`, `shapes.py` | Shape/track/keyframe, 16 số cuboid, roll/pitch, frame URL, ManifestFrames |
| `pointsnap/adapters/cvat/writer.py` | Snapshot, finding ↔ box, PATCH track đầy đủ, gỡ cờ và idempotency |
| `pointsnap/cli/common.py`, `core/serialize.py` | Tìm manifest, kiểm frame_names, dataroot override và serialization |

## 3. Điều kiện thực hiện

- Fixture nuScenes giả có đáp án tính tay trong `tests/fake_nuscenes.py`; dùng làm kiểm độc lập.
- Dataset thật v1.0-mini có tables/samples/sweeps đầy đủ. Thiếu dataset: chạy mock, ghi ca thật Bị chặn.
- CVAT thử nghiệm với tài khoản/token thích hợp. Token đọc dùng cho GET; upload/gắn cờ cần quyền ghi theo hướng dẫn cài đặt.
- Tạo task thử riêng, lưu task/job/config/phiên bản trước thao tác; không dùng job công việc thật để thử PATCH.
- Với ca ghi, snapshot trước/sau được lưu ngoài Git; so hình học/thuộc tính theo key ổn định, vì CVAT có thể thay ID sau PATCH.

## 4. Thứ tự review

1. Lập bảng mapping trường nuScenes/CVAT ↔ Cuboid/FrameData ↔ PCD/manifest.
2. Kiểm bằng fixture tính tay các phép đổi global → ego → sensor và đổi hệ CVAT; kiểm chiều ngược bằng round-trip.
3. Kiểm track markers, keyframe/interpolation, attrs mutable/immutable và ID.
4. Chạy test adapter/converter/writer mock; kiểm negative cases về metadata và API.
5. Kiểm dataset thật; sau đó chạy ca CVAT thật trên task thử khi môi trường đủ.
6. So dữ liệu trước/sau ghi, kiểm liên kết report/extension và chuyển findings đúng nhánh.

## 5. Checklist

| Mã | Ca | Mong đợi / bằng chứng |
|---|---|---|
| R03-01 | Box nuScenes [w,l,h], quaternion [w,x,y,z], pose | Chuyển đúng sang core [l,w,h], yaw/radian và z-up; đáp án tính tay |
| R03-02 | Point cloud sensor → hệ xuất CVAT | Điểm và box dùng cùng phép đổi; pose manifest tương ứng, không xoay hai lần |
| R03-03 | PCD binary/ASCII và tệp `.pcd.bin` | Đúng header/count/stride/type; dữ liệu thiếu/corrupt có lỗi rõ |
| R03-04 | Frame_names ↔ manifest ↔ sample_token | Đúng thứ tự/offset/job range; mismatch không âm thầm ghép frame sai |
| R03-05 | Ảnh 6 camera và frame context | Ảnh ứng với keyframe, tên file/ZIP đúng; xác minh mắt trên task thử |
| R03-06 | Class/category/taxonomy spec-vn | Class bỏ qua và thuộc tính suy ra được ghi; không mất nhãn ngoài chủ đích |
| R03-07 | Shape cuboid 16 số, roll/pitch và yaw | Đọc–ghi giữ đủ thông tin; tâm <1 mm/yaw <0,001 rad theo tiêu chí TASKS hoặc ghi rõ dung sai thay thế |
| R03-08 | Track keyframe, outside, gap ngắn/dài | Giữ/tách track theo spec; occluded ≤6 frame được phân biệt với outside |
| R03-09 | Attribute ở track và shape | Đúng ưu tiên/giá trị mutable theo frame; cờ không ghi nhầm tất cả keyframe |
| R03-10 | Pagination, next URL, auth/media type | Đủ mọi trang, không gửi token sai origin; chia review quyền/redirect với 06 |
| R03-11 | API 401/403/404/406/timeout/upload failed | Lỗi có ngữ cảnh để thao tác tiếp; không báo thành công khi upload/annotation chưa hoàn tất |
| R03-12 | Writer finding có/thiếu source_id/track_id | Chỉ gắn đúng box; finding không khớp có số đếm, không gắn đại cả frame |
| R03-13 | PATCH và giữ hình học/track | So center/dims/rotation/keyframes/attrs chưa liên quan trước/sau; không so ID mới như ID cũ |
| R03-14 | Gắn cờ lần hai và gỡ lỗi đã sửa | Tính idempotent về nội dung; không giữ cờ cũ hoặc nhân bản track |
| R03-15 | Nhãn thay đổi giữa scan và ghi | Xác định hành vi và nguy cơ lost update; kiểm đường re-scan trước flag của Web |
| R03-16 | Frame URL theo shape/track và serverID | Mở đúng job/frame/đối tượng; đối chiếu bằng thao tác với 05 |
| R03-17 | Snapshot và serialization | Đủ metadata để tái hiện, UTF-8, ngoài Git; không chứa token |
| R03-18 | Manifest/dataroot sai hoặc thiếu sweeps | Có thông báo và phạm vi kiểm giảm đúng; chuyển coverage gate cho 01/04 |

## 6. Lệnh kiểm tra

```powershell
python -m pytest -q tests/test_nuscenes_reader.py tests/test_pcd.py tests/test_to_cvat.py
python -m pytest -q tests/test_cvat_client.py tests/test_cvat_reader.py tests/test_cvat_shapes_and_serialize.py tests/test_cvat_writer.py
python -m pytest -q tests/test_e2e_integration.py
```

Dataset thật, khi thư mục đã cấu hình:

```powershell
python -m pytest -q tests/test_real_nuscenes.py
```

CVAT thật: đọc `tests/test_live_cvat.py` trước. Test được bật qua `POINTSNAP_LIVE_CVAT=1`, tạo task giả riêng và xóa task đó. Chỉ chạy trong môi trường thử đã kiểm token/quyền; ghi task được tạo và kết quả cleanup, kể cả test thất bại. Không gộp lệnh bật chế độ ghi vào lệnh test mặc định.

## 7. Bảng mapping và bảo toàn cần bàn giao

| Trường/đại lượng | Nguồn | Core | Đích CVAT/export | Đơn vị/ưu tiên | Ca/bằng chứng |
|---|---|---|---|---|---|
| center/dims/yaw/roll/pitch | nuScenes global / CVAT points | LiDAR hoặc hệ hiển thị; giữ tilt attrs | PCD/points gốc khi writer | m/rad; [hợp đồng chi tiết](03-mapping.md) | EV-03-001/002 |
| frame/sample_token/pose/time | sample chain đúng scene | 0..N−1, pose cùng điểm | Manifest/metadata toàn task | s; URL+task ID, không bù mismatch | EV-03-001/002 |
| track/source IDs/attrs/markers | instance / IDs CVAT | Keyframe, outside/occluded và attrs carry | Track đầy đủ, flag/reset mutable | ID mới được rebind có kiểm; snapshot raw | EV-03-001/002/003 |

Mỗi ca writer ghi số box/track/keyframe trước và sau; phần nào được phép thay đổi; delta của hình học; danh sách attrs thay đổi và unmatched findings. Xác định có task thử còn sót nếu cleanup không thành công; chỉ cleanup đúng task do lượt test tạo.

## 8. Hoàn tất và bàn giao

- [x] Mapping/fixture tính tay, frame và pose; giới hạn hệ hiển thị/tilt ghi rõ.
- [x] Writer có gắn/gỡ/unmatched/idempotency và bảo toàn raw payload; race không atomic ghi rõ.
- [x] Mock/dataset/CVAT/browser phân biệt trong report; 0 skip suite bàn giao.
- [x] Origin đã sửa; phần 06 tiếp tục audit. Guard đồng thời chuyển 04/06; extension/shape URL UI còn ở 05.
- [x] Scene/config/version ghi trong evidence, precision/recall và CVAT chuẩn vẫn thuộc 07/08.
- [x] Báo cáo ghi task 27, snapshot ngoài Git, cleanup và server BTC chưa kiểm.
