# Phần 15 — Đánh giá chất lượng, precision tay và hiệu năng

- **Nhánh:** `codex/review-15-evaluation-performance`.
- **Thứ tự:** 15 trong chuỗi 09 → 16.
- **Dependency:** Cần mã nguồn hợp nhất 09–14; khóa config/model trước held-out.
- **Trạng thái ban đầu:** 8 ca Chưa chạy. Nhánh hiện mới chứa mã nguồn main d18b1a9 và bộ tài liệu chuẩn bị.
- **Nguồn chung:** [kế hoạch 09–16](REVIEW-PLAN-09-16.md), [phân nhánh](README.md), [inventory 131 file](scope-inventory.tsv).

## Prompt để thực hiện phần này

> Thực hiện review phần 15 trên nhánh codex/review-15-evaluation-performance. Đọc review/2026-10-13/15-evaluation-performance.md và kế hoạch chung. Kiểm tra branch/HEAD và dependency trước khi làm; thực hiện đủ TC-15-001 đến TC-15-008. Truy vết luồng gọi và tái hiện trước khi kết luận lỗi; sửa lỗi có bằng chứng trong phạm vi phần 15, giữ sửa 01–08, kiểm lại bằng test phù hợp. Lưu 15-report.md, 15-handoff.md và evidence/15/. Ghi PASS/FAIL/SKIP/XFAIL riêng, ca bị chặn và thao tác cần tôi kiểm tay; không coi test mock là nghiệm thu dữ liệu/model/giao diện thật.

## Chọn nhánh và xác minh đầu vào

Chạy từ repo root; các lệnh test ở dưới chạy từ `source-tool/pointsnap-3d/`:

```powershell
git status --short
git switch codex/review-15-evaluation-performance
git log -1 --oneline
```

Nếu phần trước đã merge vào main, chạy `git fetch origin main` rồi `git merge origin/main` trên nhánh này, giải xung đột và ghi SHA sau cập nhật. Nếu còn sửa chưa commit ở checkout, hoàn tất commit đúng phạm vi trước khi switch.

## Phạm vi và checklist

Đọc: `eval/evaluate.py`, `eval/metrics.py`, `eval/split.py`, `cli/eval_cmd.py`, `scripts/run_eval_suite.py`, `scripts/eval_heading_points.py`, `scripts/eval_camera.py`, tài liệu số liệu.

| Mã | Kiểm tra và tiêu chí |
| --- | --- |
| TC-15-001 | Truy vết mỗi claim mới tới SHA/data/config/checkpoint/split/seed/rounds; 2,98/0,59 của tài liệu cũ không đại diện mặc nhiên main d18b1a9. |
| TC-15-002 | Recall theo từng lỗi/lớp/scene; FN do không có evidence ghi riêng; luật mới chưa có injection/GT không được gán recall từ catalog core/c1. |
| TC-15-003 | Đơn vị metrics, severity, mẫu số, match finding ↔ injection, trùng frame/track; giữ sửa size ratio và metadata từ recheck07. |
| TC-15-004 | Precision tay: tối thiểu 20 findings mỗi luật mới có dữ liệu, gồm nhóm khó, và ≥40 kết luận độc lập trên Web; ghi phương pháp lấy mẫu, số đúng/FP/không đủ chứng cứ. Nếu ít hơn ghi toàn bộ mẫu và giới hạn, không bịa kết luận. |
| TC-15-005 | Chạy eval tuning và test tách biệt, 10 vòng, seed cố định; tuning dùng chỉnh ngưỡng rồi khóa trước held-out. Báo cả mẫu nhỏ và CI/khoảng bất định khi phù hợp. |
| TC-15-006 | A/B hình học/ngưỡng 12°/ensemble/camera/missing: dùng cùng nguồn và config chỉ đổi yếu tố cần so; đo recall và báo nhầm cùng nhau. |
| TC-15-007 | Benchmark OtherBoxPoints: cùng tập findings và tập điểm, median/p95, RAM, frame/box count; không suy tốc độ toàn app từ một helper. |
| TC-15-008 | Camera/Critic CPU/GPU, cache lạnh/nóng, scan dài/lặp, RAM/VRAM/OOM; đối chiếu ngưỡng chất lượng G7 ≤2 cảnh báo và ≤0,5 lỗi /100 box, chưa đạt ghi chưa đạt. |

Test đầu: `python -m pytest -q tests/test_evaluation_review.py tests/test_evaluation_recheck.py tests/test_critic.py tests/test_camera.py tests/test_missing.py`.

Sau khi đã xác minh dataset/runtime, từ tool root (đặt biến `NUSCENES_ROOT` tới mini thật):

```powershell
python -m pointsnap eval --scenes tuning --rounds 10 --seed 0 --errors all --out out/review-15-tuning-20261013
python -m pointsnap eval --scenes test --rounds 10 --seed 0 --errors all --out out/review-15-test-20261013
```

Chọn tên output mới nếu đã tồn tại. Catalog `all` hiện là core + c1; phải bổ sung phương pháp riêng cho C5–C8 trước khi báo số liệu của chúng.

## Kết quả phải bàn giao

1. `review/2026-10-13/15-report.md`: SHA khởi đầu/kết thúc; file đã đọc; bảng 8 ca với trạng thái và evidence; findings `RV-15-xxx`; các sửa và test; giới hạn còn mở.
2. `review/2026-10-13/15-handoff.md`: tóm tắt sửa; SHA commit; lệnh đã chạy; PASS/FAIL/SKIP/XFAIL; dependency phần tiếp theo; ca cần người dùng kiểm tay.
3. `review/2026-10-13/evidence/15/`: tóm tắt/probe đã che thông tin nhạy cảm, gắn mã `EV-15-xxx`. Raw dataset, token, weights và output lớn không commit.
4. Inventory: đối chiếu các dòng `owner=15` trong `scope-inventory.tsv`, ghi kết luận cho mỗi file trong báo cáo. File dùng chung thuộc owner khác được tham chiếu và bàn giao nếu đã chạm.
5. Commit theo file cụ thể; xem `git diff --cached --name-only` trước commit. Push/PR/merge thực hiện theo yêu cầu riêng; base PR thường là main khi phần trước đã merge.

Hoàn tất review khi mọi ca có trạng thái và có bằng chứng cho kết luận. Các ca thiếu tài nguyên được bàn giao là Bị chặn; không xác nhận nghiệm thu cho tính năng chưa được kiểm đủ.
