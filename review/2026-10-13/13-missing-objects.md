# Phần 13 — Sót đối tượng LiDAR và cam.sparse

- **Nhánh:** `codex/review-13-missing-objects`.
- **Thứ tự:** 13 trong chuỗi 09 → 16.
- **Dependency:** Cần bàn giao 12 về camera/model/coverage; nhận sửa 09–11 có ảnh hưởng scanner.
- **Trạng thái hiện hành:** Đã review 8 ca theo [báo cáo 13](13-report.md) / [bàn giao](13-handoff.md), code `ae1d579`; 792 Python + 37 Node PASS, 3 live-CVAT SKIP. Các ca static/pretrained và human precision còn bị chặn hoặc một phần; xem giới hạn từng ca. Checklist dưới đây là yêu cầu gốc.
- **Nguồn chung:** [kế hoạch 09–16](REVIEW-PLAN-09-16.md), [phân nhánh](README.md), [inventory 131 file](scope-inventory.tsv).

## Prompt để thực hiện phần này

> Thực hiện review phần 13 trên nhánh codex/review-13-missing-objects. Đọc review/2026-10-13/13-missing-objects.md và kế hoạch chung. Kiểm tra branch/HEAD và dependency trước khi làm; thực hiện đủ TC-13-001 đến TC-13-008. Truy vết luồng gọi và tái hiện trước khi kết luận lỗi; sửa lỗi có bằng chứng trong phạm vi phần 13, giữ sửa 01–08, kiểm lại bằng test phù hợp. Lưu 13-report.md, 13-handoff.md và evidence/13/. Ghi PASS/FAIL/SKIP/XFAIL riêng, ca bị chặn và thao tác cần tôi kiểm tay; không coi test mock là nghiệm thu dữ liệu/model/giao diện thật.

## Chọn nhánh và xác minh đầu vào

Chạy từ repo root; các lệnh test ở dưới chạy từ `source-tool/pointsnap-3d/`:

```powershell
git status --short
git switch codex/review-13-missing-objects
git log -1 --oneline
```

Nếu phần trước đã merge vào main, chạy `git fetch origin main` rồi `git merge origin/main` trên nhánh này, giải xung đột và ghi SHA sau cập nhật. Nếu còn sửa chưa commit ở checkout, hoàn tất commit đúng phạm vi trước khi switch.

## Phạm vi và checklist

Đọc: `detectors/missing.py`, `detectors/camera.py`, `core/scanner.py`, `core/config.py`; đối chiếu [kết quả missing cũ](../../source-tool/pointsnap-3d/docs/ket-qua/ket-qua-sot-doi-tuong.md).

| Mã | Kiểm tra và tiêu chí |
| --- | --- |
| TC-13-001 | Bỏ box của vật chuyển động trên bản sao nhãn: cụm, pose bù ego, frame association; tìm đúng vị trí và không đếm trùng qua frame. |
| TC-13-002 | Đối tượng đã gán: visible/occluded, box xoay, lớn, mép vùng; mask loại vật đã có nhãn không che luôn vật bị sót bên cạnh. |
| TC-13-003 | Vật đứng yên có/không ảnh xác nhận ban ngày: đúng điều kiện cho C8; thiếu camera ghi giới hạn coverage. |
| TC-13-004 | Người đứng/đi chậm trong nhóm, xe >30 m, xe buýt một phần: đo bỏ sót và ghi giới hạn; không gán recall tổng cho mọi tình huống. |
| TC-13-005 | Mưa/nhiễu/ground/đám cây/ít điểm: phân nhóm và ngưỡng không tạo báo nhầm hàng loạt. |
| TC-13-006 | Cam sparse: số điểm sát ngưỡng, bằng chứng ảnh có/không, tắt camera, đổi model, class không hỗ trợ; ngưỡng P-009 chưa chốt ghi là quyết định còn mở. |
| TC-13-007 | Finding không có box/track ID: frame và vị trí gợi ý, CSV/HTML/API/UI/extension/CVAT chịu được; không chọn nhầm box tồn tại. |
| TC-13-008 | Missing/false alarm đánh giá độc lập: GT vật bị xóa riêng, số vật/số cảnh và mẫu số đúng; đối chiếu tay nhãn sạch và nhóm khó. |

Test đầu: `python -m pytest -q tests/test_missing.py tests/test_camera.py tests/test_scenarios.py tests/test_scan_gate.py`.

## Kết quả phải bàn giao

1. `review/2026-10-13/13-report.md`: SHA khởi đầu/kết thúc; file đã đọc; bảng 8 ca với trạng thái và evidence; findings `RV-13-xxx`; các sửa và test; giới hạn còn mở.
2. `review/2026-10-13/13-handoff.md`: tóm tắt sửa; SHA commit; lệnh đã chạy; PASS/FAIL/SKIP/XFAIL; dependency phần tiếp theo; ca cần người dùng kiểm tay.
3. `review/2026-10-13/evidence/13/`: tóm tắt/probe đã che thông tin nhạy cảm, gắn mã `EV-13-xxx`. Raw dataset, token, weights và output lớn không commit.
4. Inventory: đối chiếu các dòng `owner=13` trong `scope-inventory.tsv`, ghi kết luận cho mỗi file trong báo cáo. File dùng chung thuộc owner khác được tham chiếu và bàn giao nếu đã chạm.
5. Commit theo file cụ thể; xem `git diff --cached --name-only` trước commit. Push/PR/merge thực hiện theo yêu cầu riêng; base PR thường là main khi phần trước đã merge.

Hoàn tất review khi mọi ca có trạng thái và có bằng chứng cho kết luận. Các ca thiếu tài nguyên được bàn giao là Bị chặn; không xác nhận nghiệm thu cho tính năng chưa được kiểm đủ.
