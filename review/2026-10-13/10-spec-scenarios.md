# Phần 10 — Tình huống thực tế và luật spec

- **Nhánh:** `codex/review-10-spec-scenarios`.
- **Thứ tự:** 10 trong chuỗi 09 → 16.
- **Dependency:** Nhận kết quả 09, nhất là sửa track/size/ground và thay đổi reference.
- **Kết quả 13/10:** đã thực hiện8ca,sửa9nhóm; code `c5ac54d`,662 Python+37 Node PASS,5 SKIP,0 XFAIL. Xem [báo cáo10](10-report.md)/[bàn giao10](10-handoff.md) và phần cần kiểm tay. Hướng dẫn bên dưới giữ quy trình đã dùng.
- **Nguồn chung:** [kế hoạch 09–16](REVIEW-PLAN-09-16.md), [phân nhánh](README.md), [inventory 131 file](scope-inventory.tsv).

## Prompt để thực hiện phần này

> Thực hiện review phần 10 trên nhánh codex/review-10-spec-scenarios. Đọc review/2026-10-13/10-spec-scenarios.md và kế hoạch chung. Kiểm tra branch/HEAD và dependency trước khi làm; thực hiện đủ TC-10-001 đến TC-10-008. Truy vết luồng gọi và tái hiện trước khi kết luận lỗi; sửa lỗi có bằng chứng trong phạm vi phần 10, giữ sửa 01–08, kiểm lại bằng test phù hợp. Lưu 10-report.md, 10-handoff.md và evidence/10/. Ghi PASS/FAIL/SKIP/XFAIL riêng, ca bị chặn và thao tác cần tôi kiểm tay; không coi test mock là nghiệm thu dữ liệu/model/giao diện thật.

## Chọn nhánh và xác minh đầu vào

Chạy từ repo root; các lệnh test ở dưới chạy từ `source-tool/pointsnap-3d/`:

```powershell
git status --short
git switch codex/review-10-spec-scenarios
git log -1 --oneline
```

Nếu phần trước đã merge vào main, chạy `git fetch origin main` rồi `git merge origin/main` trên nhánh này, giải xung đột và ghi SHA sau cập nhật. Nếu còn sửa chưa commit ở checkout, hoàn tất commit đúng phạm vi trước khi switch.

## Phạm vi và checklist

Đọc: `detectors/attributes.py`, `track.py`, `size.py`, `core/config.py`, `guidelines/spec-vn.yaml`, `tests/scenario_sim.py`; đối chiếu [giao việc C5](../../source-tool/pointsnap-3d/quan-ly/giao-viec/C5-tinh-huong-thuc-te.md), [C6](../../source-tool/pointsnap-3d/quan-ly/giao-viec/C6-bam-spec.md).

| Mã | Kiểm tra và tiêu chí |
| --- | --- |
| TC-10-001 | Track ID swap giữa hai vật: bắt đổi ID, không báo khi vượt/giao nhau/quay thật, class và subtype được giữ riêng. |
| TC-10-002 | Attr height theo tư thế: chiều cao box, box xoay, ngồi/nằm/đứng, trẻ em và ít điểm; thiếu chứng cứ không suy thành lỗi chắc chắn. |
| TC-10-003 | Spec inside: người trong xe so với đứng sát xe, bị che hoặc box giao nhau; hình học theo cùng frame và tọa độ. |
| TC-10-004 | Spec rider double: rider + xe hai bánh, box lặp thật so hai người/xe cạnh nhau; không báo lặp chỉ vì overlap hợp lệ. |
| TC-10-005 | Rider state: lên/xuống xe, chuyển tư thế thật và thuộc tính thiếu; xác minh đoạn thay đổi và cửa sổ thời gian. |
| TC-10-006 | Size cargo/xe chở hàng: nới ngưỡng theo evidence, không che một box phóng đại hoặc lệch thật. |
| TC-10-007 | Class/spec-vn, tên thuộc tính, case, giá trị other và taxonomy nuScenes: luật áp dụng đúng nhóm; GUI toggle khớp key config. |
| TC-10-008 | Kiểm độc lập scenario simulator: oracle không lấy cùng helper cần kiểm; thêm phản ví dụ và so tình huống thật. Người mang vật dài còn ngoài khả năng hiện tại phải được ghi rõ. |

Test đầu: `python -m pytest -q tests/test_scenarios.py tests/test_spec_geometry.py tests/test_spec_rules.py tests/test_size_detector.py tests/test_config.py`.

## Kết quả phải bàn giao

1. `review/2026-10-13/10-report.md`: SHA khởi đầu/kết thúc; file đã đọc; bảng 8 ca với trạng thái và evidence; findings `RV-10-xxx`; các sửa và test; giới hạn còn mở.
2. `review/2026-10-13/10-handoff.md`: tóm tắt sửa; SHA commit; lệnh đã chạy; PASS/FAIL/SKIP/XFAIL; dependency phần tiếp theo; ca cần người dùng kiểm tay.
3. `review/2026-10-13/evidence/10/`: tóm tắt/probe đã che thông tin nhạy cảm, gắn mã `EV-10-xxx`. Raw dataset, token, weights và output lớn không commit.
4. Inventory: đối chiếu các dòng `owner=10` trong `scope-inventory.tsv`, ghi kết luận cho mỗi file trong báo cáo. File dùng chung thuộc owner khác được tham chiếu và bàn giao nếu đã chạm.
5. Commit theo file cụ thể; xem `git diff --cached --name-only` trước commit. Push/PR/merge thực hiện theo yêu cầu riêng; base PR thường là main khi phần trước đã merge.

Hoàn tất review khi mọi ca có trạng thái và có bằng chứng cho kết luận. Các ca thiếu tài nguyên được bàn giao là Bị chặn; không xác nhận nghiệm thu cho tính năng chưa được kiểm đủ.
