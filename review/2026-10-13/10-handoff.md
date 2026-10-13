# Bàn giao phần 10

- Nhánh: `codex/review-10-spec-scenarios`; base phần 09 `cbeb41c`; code phần 10 **`c5ac54d`**.
- Sửa 9 nhóm: rider pose/time/gate; ID swap; manual attributes; match thuộc tính theo schema; overlap chính xác; track ID 0; điều kiện dismount; owner/type cargo; validation rider config.
- **662 Python PASS, 5 SKIP, 0 FAIL/ERROR/XFAIL; 37 Node PASS**. Thêm 31 ca. Coverage module sửa 95,44%, toàn package 90,58%.
- Hai SKIP torch thuộc 11, ba SKIP CVAT live thuộc 14; dataset mini thật đã được kiểm. Không ghi CVAT hoặc tải model.

## Tiếp phần 11

Nếu 10 chưa merge main, nhập nhánh 10 vào `codex/review-11-verifier-learning` bằng merge/fast-forward và ghi SHA dependency. Nhánh 10 đã chứa 09; giữ ancestry của chuỗi. Nếu đã merge, cập nhật 11 từ origin/main.

Lưu ý:

1. `detect_rider_state` không suy chuyển động khi thiếu pose; scanner/gate đã phản ánh. Timestamp đủ thì dùng thật; thiếu một phần thì fallback đồng nhất.
2. Height/spec/rider dùng manual keyframes; spec.inside còn xét occluded manual. Learning/critic không được coi derived samples là verdict của người duyệt.
3. Cargo subtype cần resolver rõ; owner mơ hồ không được hạ severity. Giữ quy tắc này khi learned model thay severity/gate.
4. Pattern Class/value có legacy fallback khi config không khai tên attrs; kiểm model/features/validation cần lưu ý dữ liệu note tùy ý.

## Chất lượng còn cần kiểm

- GT subset: tuning 5 warnings/2 errors trên 8.759 box; held-out 20/2 trên 5.458 box. Counts và held-out identities không đổi. Rider_double track 38 ở scene-0061 đổi frame đầu 9→6.
- Chèn lỗi trên hai cảnh tuning: posture 21/21, IDs 20/21, rider_state 1/3 trước/sau. Không suy recall toàn mini; rider đứng chờ là giới hạn của motion.
- Bốn mục cần xem tay và các giới hạn khác ở [báo cáo 10](10-report.md). Lượt này có 0 precision verdict; G7 toàn sản phẩm chưa được chứng nhận.

[Verification](evidence/10/verification.json),[GT](evidence/10/quality-comparison.json),[injections](evidence/10/injection-summary.json).
