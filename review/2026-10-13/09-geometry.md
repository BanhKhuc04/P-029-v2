# Phần 09 — Hình học, ground/C4, heading, fit, track

- **Nhánh:** `codex/review-09-geometry`.
- **Thứ tự:** 09 trong chuỗi 09 → 16.
- **Dependency:** Không có phần mới phải chờ; đọc bàn giao 01–08 và bắt đầu ca C4 còn XFAIL.
- **Kết quả ngày 13/10:** đã thực hiện 8 ca và sửa 4 nhóm lỗi; code `f22f2b6`. 631 Python +37 Node PASS;5 SKIP,0 XFAIL. Xem [báo cáo09](09-report.md) và [bàn giao09](09-handoff.md) để biết giới hạn và phần cần kiểm tay. Phần hướng dẫn bên dưới giữ quy trình đã dùng.
- **Nguồn chung:** [kế hoạch 09–16](REVIEW-PLAN-09-16.md), [phân nhánh](README.md), [inventory 131 file](scope-inventory.tsv).

## Prompt để thực hiện phần này

> Thực hiện review phần 09 trên nhánh codex/review-09-geometry. Đọc review/2026-10-13/09-geometry.md và kế hoạch chung. Kiểm tra branch/HEAD và dependency trước khi làm; thực hiện đủ TC-09-001 đến TC-09-008. Truy vết luồng gọi và tái hiện trước khi kết luận lỗi; sửa lỗi có bằng chứng trong phạm vi phần 09, giữ sửa 01–08, kiểm lại bằng test phù hợp. Lưu 09-report.md, 09-handoff.md và evidence/09/. Ghi PASS/FAIL/SKIP/XFAIL riêng, ca bị chặn và thao tác cần tôi kiểm tay; không coi test mock là nghiệm thu dữ liệu/model/giao diện thật.

## Chọn nhánh và xác minh đầu vào

Chạy từ repo root; các lệnh test ở dưới chạy từ `source-tool/pointsnap-3d/`:

```powershell
git status --short
git switch codex/review-09-geometry
git log -1 --oneline
```

Nếu phần trước đã merge vào main, chạy `git fetch origin main` rồi `git merge origin/main` trên nhánh này, giải xung đột và ghi SHA sau cập nhật. Nếu còn sửa chưa commit ở checkout, hoàn tất commit đúng phạm vi trước khi switch.

## Phạm vi và checklist

**Ưu tiên cao:** thuật toán thay đổi có thể bỏ sót lỗi nhãn hoặc tăng báo nhầm.

Đọc: `pointsnap/core/ground.py`, `core/box_points.py`, `detectors/floating.py`, `heading.py`, `fit.py`, `track.py`, `size.py`, `core/scanner.py`, `core/config.py`; đối chiếu [CONVENTIONS](../../source-tool/pointsnap-3d/CONVENTIONS.md).

| Mã | Kiểm tra và tiêu chí |
| --- | --- |
| TC-09-001 | Ground đường bằng, dốc dọc/ngang, box xoay, đá/vỉa hè, điểm chỉ một phía: đúng hệ tọa độ, độ cao đáy và dung sai theo config. |
| TC-09-002 | Track bằng → dốc: nhãn đúng không báo; box lún/lơ lửng thật vẫn phát hiện. Tái hiện XFAIL dốc 8°, nâng 25 cm; định lượng phạm vi bỏ sót, không ghi đã sửa hết C4. |
| TC-09-003 | Thiếu/ít điểm, ngoại lai, point cloud rỗng: phân biệt thiếu evidence với sạch; gate phản ánh coverage phù hợp. |
| TC-09-004 | Chỉ mục OtherBoxPoints: đối chiếu tập điểm với cách lọc trực tiếp, gồm biên x, yaw, box chồng, bán kính và dữ liệu bất thường. |
| TC-09-005 | Heading motion thiếu pose/pose một phần; góc ±π và modulo 90°; vật đứng yên/xe quay: không coi chuyển động ego là lỗi vật. |
| TC-09-006 | Track jump đầu/cuối và track ba box, đứng yên, quay thật, timestamp không đều, frame thiếu: nới ngưỡng không làm bỏ sót nhảy 4 m. |
| TC-09-007 | Fit loose so track; một frame dư và cả track dư, thay đổi kích thước thật, ít điểm, cùng ID khác class: reference không tự chứa outlier và không trộn vật. |
| TC-09-008 | Ngưỡng heading 12° và floating 15 cm: kiểm đúng sát biên, severity, config mặc định/spec-vn và thay đổi recall/báo nhầm so ngưỡng cũ. |

Test đầu: `python -m pytest -q tests/test_ground.py tests/test_ground_slope.py tests/test_heading_fit.py tests/test_track_detector.py tests/test_size_detector.py tests/test_core_review_regressions.py`.

## Kết quả phải bàn giao

1. `review/2026-10-13/09-report.md`: SHA khởi đầu/kết thúc; file đã đọc; bảng 8 ca với trạng thái và evidence; findings `RV-09-xxx`; các sửa và test; giới hạn còn mở.
2. `review/2026-10-13/09-handoff.md`: tóm tắt sửa; SHA commit; lệnh đã chạy; PASS/FAIL/SKIP/XFAIL; dependency phần tiếp theo; ca cần người dùng kiểm tay.
3. `review/2026-10-13/evidence/09/`: tóm tắt/probe đã che thông tin nhạy cảm, gắn mã `EV-09-xxx`. Raw dataset, token, weights và output lớn không commit.
4. Inventory: đối chiếu các dòng `owner=09` trong `scope-inventory.tsv`, ghi kết luận cho mỗi file trong báo cáo. File dùng chung thuộc owner khác được tham chiếu và bàn giao nếu đã chạm.
5. Commit theo file cụ thể; xem `git diff --cached --name-only` trước commit. Push/PR/merge thực hiện theo yêu cầu riêng; base PR thường là main khi phần trước đã merge.

Hoàn tất review khi mọi ca có trạng thái và có bằng chứng cho kết luận. Các ca thiếu tài nguyên được bàn giao là Bị chặn; không xác nhận nghiệm thu cho tính năng chưa được kiểm đủ.
