# Báo cáo review 13 — sót đối tượng LiDAR và cam.sparse

Ngày 13/10/2026 (Asia/Saigon). Nhánh `codex/review-13-missing-objects`, nhận 09–12 tại `699433b`; sửa **`ae1d579`**.

## Kết quả và phạm vi

- Sửa 9 nhóm lỗi, thêm **21 ca hồi quy**. Gate: **792 Python PASS, 0 FAIL/ERROR/XFAIL, 3 live-CVAT SKIP; 37 Node PASS**.
- Coverage statement module sửa `detectors/missing.py`: **276/285 = 96,84%**.
- Đọc và truy vết missing, camera sparse, scanner, cấu hình, report CSV/HTML, writer CVAT và kết quả C7/C8 cũ. Hai file owner 13: `detectors/missing.py` đã sửa; `tests/test_missing.py` 9 ca cũ vẫn đạt. Camera/scanner và các điểm nối được bàn giao phần 14.
- Probe read-only cả 10 cảnh mini; mỗi cảnh xóa trong bộ nhớ hai track chọn trước từ GT, không sửa dataset/CVAT. **20 vật: 11 car, 8 pedestrian, 1 truck**. Recovery **5/10 tuning, 7/10 test**, bằng baseline. Nhãn sạch có **1 candidate tuning, 1 candidate test** ở cả hai phiên bản; chưa có người duyệt, không khẳng định đây là false positive thật.

## Checklist 8 ca

| Ca | Trạng thái | Bằng chứng và giới hạn |
| --- | --- | --- |
| TC-13-001 | Đạt logic + subset mini | Chuỗi liên tiếp/world pose; pose không biết không giả identity; ego-motion fixture cũ đạt. Một finding cho chuỗi được chấp nhận; return chains không gồm chuỗi bị loại. 20 deleted tracks đối chiếu vị trí độc lập ở ≥2 frame. |
| TC-13-002 | Đạt oracle/fixture | Box 4×4 xoay 45° có điểm góc y=2,69 m phải bị mask; vật kề y=3,5 m được giữ. Occluded vẫn mask, outside không mask. Không sửa margin mặc định. |
| TC-13-003 | Đạt logic; pretrained bị chặn | Static anchor không trôi theo tâm trung bình; bright view riêng, nhóm tên model/capability, ≥static_min_views frame độc lập cùng nhóm. Runtime/model thật của phần 12 vẫn thiếu weights; không nghiệm thu static recall. |
| TC-13-004 | Một phần, giới hạn còn mở | Scenario người đi bộ/moving ego đạt, mẫu mini gồm 8 pedestrian. Chưa đo riêng nhóm đông người, người chậm, xe >30 m hoặc bus một phần; sample không có bus/two-wheeler nên không suy rộng recall. |
| TC-13-005 | Đạt fixtures đã có; dữ liệu thời tiết chưa nghiệm thu | Test heavy rain 10.000 điểm/frame, nhãn sạch, vật đứng yên khi ego chạy vẫn đạt. Không chỉnh cell/density/ground/motion thresholds từ kết quả test split. Cây/rain thật còn cần người duyệt. |
| TC-13-006 | Đạt logic sparse đã kiểm ở 12; semantic còn mở | Camera tắt/sparse_max_points=0, thiếu detection, class không hỗ trợ, đổi effective model, interpolation, dark view và box xoay có regression. INFO vẫn là bằng chứng yếu; P-009 ngưỡng 5 chưa được nhóm chốt. Không dùng detector không thấy để kết luận box sai. |
| TC-13-007 | Đạt CSV/HTML; API/UI/extension chuyển 14 | Finding missing không có track/source ID, CSV để trống ID; link HTML/CSV chỉ mở frame, không chọn box hiện có. Vị trí tâm mỗi frame giữ trong details. Preview/extension/CVAT cần kiểm tích hợp phần 14. |
| TC-13-008 | Đạt deletion probe có mẫu số; human quality chưa nghiệm thu | Chọn sorted instance tokens theo raw GT displacement≥3 m, ≥3 frame có raw num_lidar_pts≥15 trong 40 m; first 2 eligible/scene. Matcher độc lập dùng tọa độ local/yaw GT, không dựa finding track ID. 20 vật/10 cảnh là subset có điều kiện, không phải recall tất cả vật; clean candidate count là proxy. |

## Findings đã sửa

| Mã | Mức | Lỗi tái hiện và sửa |
| --- | --- | --- |
| RV-13-001 | P1 | Broad phase max(length,width)/2 bỏ góc box xoay, giữ điểm vật đã gán như unlabelled. Dùng bán kính đường chéo box đã nới margin trước phép inside chính xác. Vật kề bên không bị mask thêm. |
| RV-13-002 | P2 | Cạnh nối near/far chỉ xét endpoint đang duyệt; đảo thứ tự điểm đổi từ 2 cụm thành 1. Cạnh symmetric: bước hở một ô khi ít nhất một endpoint thuộc vùng far. |
| RV-13-003 | P1 | Pose None tự thành identity, có thể coi chuyển động xe thu là vật di chuyển. Bỏ clustering/world occupancy của frame thiếu pose; identity phải được cung cấp rõ. Gate coverage missing được giao 14. |
| RV-13-004 | P2 | Static anchor trung bình di chuyển theo chain, vật trôi 0,6 m/frame vẫn nối dài thành đứng yên. Anchor cố định tâm đầu, đúng hợp đồng static_gate_m; loại cluster thuộc moving chain đã báo khỏi nhánh static để không báo đôi. |
| RV-13-005 | P2 | Static chỉ nhận exact COCO names; `vehicle`, `construction vehicle`, `CAR`, `car truck` bị bỏ. Reuse group_of_name và effective supported_groups, nhãn semantic ổn định, giữ raw camera_class cho truy vết. |
| RV-13-006 | P1 | Frame trùng hoặc person/car mỗi loại một frame đủ tổng static_min_views. Dedupe frame, view mâu thuẫn không được bỏ phiếu; cùng nhóm phải đủ số frame yêu cầu, tie chọn deterministic. |
| RV-13-007 | P1 | Ảnh dark có detection được dùng khi hai ảnh khác sáng kéo median lên. Filter brightness từng view trước confirmation, ngoài điều kiện median frame. |
| RV-13-008 | P2 | Lấy thưa khoảng 6 frame làm static_min_views=12 không bao giờ đạt dù đủ 20 frame tốt; camera_cfg=None crash. Duyệt frame độc lập đầy đủ, dùng CameraConfig mặc định khi caller bỏ optional config. |
| RV-13-009 | P2 | value m/s nhưng threshold m; threshold người vẫn dùng xe; trả cả chain không đạt như moving. value là displacement m, threshold đúng need_motion; speed/duration ở details dùng timestamp thật khi có, fallback interval cấu hình. Chỉ trả accepted moving chains. |

Baseline ban đầu: **14 FAIL/1 PASS trên 15 ca tái hiện** trước sửa. Thêm 6 ca hợp đồng/report sau đó, tổng 21 có trong gate. Không tính fixture thành kiểm model pretrained. Các thay đổi không chỉnh ngưỡng để làm đẹp recovery.

## Evidence

- EV-13-001: [verification.json](evidence/13/verification.json), SHA nguồn/XML/coverage và gate.
- EV-13-003: [mini-comparison.json](evidence/13/mini-comparison.json), [missing_probe.py](evidence/13/missing_probe.py). Raw XML/runtime/output ở `source-tool/pointsnap-3d/out/`, không commit data/weights.

## Giới hạn và bàn giao

1. Static/pretrained/GPU/human precision bị chặn bởi tài nguyên phần 12; không có SAM trên máy theo người dùng. TC-13-003/008 không được coi nghiệm thu semantic quality.
2. GT yaw-only và margin matcher 0,75 m là proxy vị trí; selection ưu tiên hai token đầu có đủ điểm/displacement, không phải random representative sample. Recovery 60% subset không đạt chứng nhận recall tổng.
3. Trên lượt clean 10 scene cùng process, tổng thời gian current **33,86 s**, baseline **28,27 s** (~20% tăng). Đây là lượt đo đơn, thứ tự current trước baseline và cache/filesystem có thể ảnh hưởng; phần 15 cần benchmark riêng. Static giờ duyệt hết frame để giữ đúng minimum evidence nên có thể tăng chi phí ảnh lạnh.
4. Tracking greedy/constant velocity và lưới ground vẫn có thể merge người sát nhau hoặc tường, split vật mất points, bỏ frame khi pose thiếu. Timestamp dùng cho speed details, predictor/persistence vẫn theo keyframe index.
5. Phần 14 kiểm coverage khi job rỗng nhãn/thiếu points/pose, markers optional camera, learning/gate, preview/report/API/extension và flag missing không có ID. Phần 15 bổ sung hard-group metrics và người duyệt cảnh báo clean.
