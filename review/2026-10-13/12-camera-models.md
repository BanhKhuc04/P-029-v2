# Phần 12 — Camera và các model ảnh

- **Nhánh:** `codex/review-12-camera-models`.
- **Thứ tự:** 12 trong chuỗi 09 → 16.
- **Dependency:** Nhận kết quả 09–11; cần ảnh/calibration thật và môi trường model ảnh để nghiệm thu.
- **Trạng thái ban đầu:** 8 ca Chưa chạy. Nhánh hiện mới chứa mã nguồn main d18b1a9 và bộ tài liệu chuẩn bị.
- **Nguồn chung:** [kế hoạch 09–16](REVIEW-PLAN-09-16.md), [phân nhánh](README.md), [inventory 131 file](scope-inventory.tsv).

## Prompt để thực hiện phần này

> Thực hiện review phần 12 trên nhánh codex/review-12-camera-models. Đọc review/2026-10-13/12-camera-models.md và kế hoạch chung. Kiểm tra branch/HEAD và dependency trước khi làm; thực hiện đủ TC-12-001 đến TC-12-008. Truy vết luồng gọi và tái hiện trước khi kết luận lỗi; sửa lỗi có bằng chứng trong phạm vi phần 12, giữ sửa 01–08, kiểm lại bằng test phù hợp. Lưu 12-report.md, 12-handoff.md và evidence/12/. Ghi PASS/FAIL/SKIP/XFAIL riêng, ca bị chặn và thao tác cần tôi kiểm tay; không coi test mock là nghiệm thu dữ liệu/model/giao diện thật.

## Chọn nhánh và xác minh đầu vào

Chạy từ repo root; các lệnh test ở dưới chạy từ `source-tool/pointsnap-3d/`:

```powershell
git status --short
git switch codex/review-12-camera-models
git log -1 --oneline
```

Nếu phần trước đã merge vào main, chạy `git fetch origin main` rồi `git merge origin/main` trên nhánh này, giải xung đột và ghi SHA sau cập nhật. Nếu còn sửa chưa commit ở checkout, hoàn tất commit đúng phạm vi trước khi switch.

## Phạm vi và checklist

Đọc: `core/camera.py`, `vision/detector2d.py`, `detectors/camera.py`, `adapters/nuscenes/reader.py`, `core/config.py`, `core/scanner.py`, `scripts/eval_camera.py`.

| Mã | Kiểm tra và tiêu chí |
| --- | --- |
| TC-12-001 | Chiếu LiDAR → camera: extrinsics/intrinsics, hướng transform, depth, box sau camera, ngoài ảnh và camera nhiều hướng; đối chiếu hình thật. |
| TC-12-002 | Mismatch/class/missing: che khuất, model không thấy, ánh tối, ảnh thiếu, nhiều camera; model không detect không đủ để kết luận box sai. |
| TC-12-003 | Mask R-CNN / gdino-sam2 / hybrid: nhóm class hỗ trợ, tên prompt, cone và rider; lựa chọn model khớp capability thực tế. |
| TC-12-004 | Effective model đi qua cả check_camera, cam.sparse và check_missing; thử từng mode và cấu hình override. |
| TC-12-005 | CPU/GPU/autocast, torchvision/transformers/weights thiếu, offline và model load lỗi: fallback rõ, không crash toàn scan hoặc báo coverage đầy đủ sai. |
| TC-12-006 | Cache: phân biệt model, checkpoint/prompt/ảnh thay đổi, cache cũ/hỏng; chạy lạnh và nóng cho kết quả tương ứng. |
| TC-12-007 | IoU/mask và rescale ảnh: object nhỏ/xa, mép ảnh, resize, nhiều object; đo với oracle độc lập. |
| TC-12-008 | Chạy model thật trên mẫu cố định: ảnh/calibration/config/checkpoint có nguồn; lưu evidence, thời gian và lỗi GPU/OOM. Mock PASS không thay ca này. |

Test đầu: `python -m pytest -q tests/test_camera.py tests/test_config.py tests/test_real_nuscenes.py`. Ca model thật cần chạy riêng vì tests hiện có gồm detector giả.

## Kết quả phải bàn giao

1. `review/2026-10-13/12-report.md`: SHA khởi đầu/kết thúc; file đã đọc; bảng 8 ca với trạng thái và evidence; findings `RV-12-xxx`; các sửa và test; giới hạn còn mở.
2. `review/2026-10-13/12-handoff.md`: tóm tắt sửa; SHA commit; lệnh đã chạy; PASS/FAIL/SKIP/XFAIL; dependency phần tiếp theo; ca cần người dùng kiểm tay.
3. `review/2026-10-13/evidence/12/`: tóm tắt/probe đã che thông tin nhạy cảm, gắn mã `EV-12-xxx`. Raw dataset, token, weights và output lớn không commit.
4. Inventory: đối chiếu các dòng `owner=12` trong `scope-inventory.tsv`, ghi kết luận cho mỗi file trong báo cáo. File dùng chung thuộc owner khác được tham chiếu và bàn giao nếu đã chạm.
5. Commit theo file cụ thể; xem `git diff --cached --name-only` trước commit. Push/PR/merge thực hiện theo yêu cầu riêng; base PR thường là main khi phần trước đã merge.

Hoàn tất review khi mọi ca có trạng thái và có bằng chứng cho kết luận. Các ca thiếu tài nguyên được bàn giao là Bị chặn; không xác nhận nghiệm thu cho tính năng chưa được kiểm đủ.
