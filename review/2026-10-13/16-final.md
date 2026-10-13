# Phần 16 — Đóng gói, tài liệu và tổng hợp nghiệm thu

- **Nhánh:** `codex/review-16-final`.
- **Thứ tự:** 16 trong chuỗi 09 → 16.
- **Dependency:** Cần báo cáo 09–15 và mã nguồn hợp nhất để chạy gate cuối.
- **Trạng thái ban đầu:** 8 ca Chưa chạy. Nhánh hiện mới chứa mã nguồn main d18b1a9 và bộ tài liệu chuẩn bị.
- **Nguồn chung:** [kế hoạch 09–16](REVIEW-PLAN-09-16.md), [phân nhánh](README.md), [inventory 131 file](scope-inventory.tsv).

## Prompt để thực hiện phần này

> Thực hiện review phần 16 trên nhánh codex/review-16-final. Đọc review/2026-10-13/16-final.md và kế hoạch chung. Kiểm tra branch/HEAD và dependency trước khi làm; thực hiện đủ TC-16-001 đến TC-16-008. Truy vết luồng gọi và tái hiện trước khi kết luận lỗi; sửa lỗi có bằng chứng trong phạm vi phần 16, giữ sửa 01–08, kiểm lại bằng test phù hợp. Lưu 16-report.md, 16-handoff.md và evidence/16/. Ghi PASS/FAIL/SKIP/XFAIL riêng, ca bị chặn và thao tác cần tôi kiểm tay; không coi test mock là nghiệm thu dữ liệu/model/giao diện thật.

## Chọn nhánh và xác minh đầu vào

Chạy từ repo root; các lệnh test ở dưới chạy từ `source-tool/pointsnap-3d/`:

```powershell
git status --short
git switch codex/review-16-final
git log -1 --oneline
```

Nếu phần trước đã merge vào main, chạy `git fetch origin main` rồi `git merge origin/main` trên nhánh này, giải xung đột và ghi SHA sau cập nhật. Nếu còn sửa chưa commit ở checkout, hoàn tất commit đúng phạm vi trước khi switch.

## Phạm vi và checklist

Đọc: `pyproject.toml`, README/cài đặt/Docker, `docs/bao-cao-du-an.md`, `docs/huong-dan/`, hình minh họa và script tạo hình, `quan-ly/ban-giao-12-10.md`, `TASKS.md`, giao việc và các báo cáo 09–15.

| Mã | Kiểm tra và tiêu chí |
| --- | --- |
| TC-16-001 | Inventory 131 file đều có phần phụ trách và evidence/kết luận; đối chiếu lại nếu HEAD thay đổi. Xóa/rename có lý do và link mới hoạt động. |
| TC-16-002 | README repo/source-tool/sản phẩm dẫn đúng entrypoint, cài đặt và lệnh; không đọc hướng dẫn ở đường dẫn đã chuyển. |
| TC-16-003 | Cài base không vision; cài vision trên CPU/GPU trong môi trường tách: dependency/model tải và cách fallback đủ rõ, không sửa môi trường người dùng để thử. |
| TC-16-004 | Wheel/sdist/container có module/config/static mới; smoke ngoài checkout với learn/camera/missing; ghi OS/Python/model combo thực sự kiểm. |
| TC-16-005 | Báo cáo/hình minh họa tái lập từ data và script tương ứng; thông số/ngưỡng/spec/số liệu thống nhất với code và báo cáo15. |
| TC-16-006 | Tài liệu C4 ghi rõ XFAIL còn lại; precision tay, coverage camera/missing và ngưỡng P-009 có trạng thái thật. Không đồng nhất hoàn tất code với nghiệm thu. |
| TC-16-007 | Sổ findings hợp nhất 01–16: còn mở, đã sửa/chờ kiểm, đã xác minh, giới hạn được chấp nhận; owner và điều kiện sử dụng cụ thể. |
| TC-16-008 | Gate cuối trên SHA hợp nhất: full Python/Node, model thật/dataset/CVAT/browser theo phạm vi; báo PASS/FAIL/SKIP/XFAIL riêng, kết luận demo/local và nghiệm thu rộng riêng. |

Test đầu: `python -m pytest -q tests/test_deployment_review.py`; gate cuối `python -m pytest -q` và Node suite sau các thay đổi cuối cùng.

## Kết quả phải bàn giao

1. `review/2026-10-13/16-report.md`: SHA khởi đầu/kết thúc; file đã đọc; bảng 8 ca với trạng thái và evidence; findings `RV-16-xxx`; các sửa và test; giới hạn còn mở.
2. `review/2026-10-13/16-handoff.md`: tóm tắt sửa; SHA commit; lệnh đã chạy; PASS/FAIL/SKIP/XFAIL; dependency phần tiếp theo; ca cần người dùng kiểm tay.
3. `review/2026-10-13/evidence/16/`: tóm tắt/probe đã che thông tin nhạy cảm, gắn mã `EV-16-xxx`. Raw dataset, token, weights và output lớn không commit.
4. Inventory: đối chiếu các dòng `owner=16` trong `scope-inventory.tsv`, ghi kết luận cho mỗi file trong báo cáo. File dùng chung thuộc owner khác được tham chiếu và bàn giao nếu đã chạm.
5. Commit theo file cụ thể; xem `git diff --cached --name-only` trước commit. Push/PR/merge thực hiện theo yêu cầu riêng; base PR thường là main khi phần trước đã merge.

Hoàn tất review khi mọi ca có trạng thái và có bằng chứng cho kết luận. Các ca thiếu tài nguyên được bàn giao là Bị chặn; không xác nhận nghiệm thu cho tính năng chưa được kiểm đủ.
