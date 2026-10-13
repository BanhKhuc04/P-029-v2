# Phần 11 — Box Verifier, Critic ensemble và học từ kết luận

- **Nhánh:** `codex/review-11-verifier-learning`.
- **Thứ tự:** 11 trong chuỗi 09 → 16.
- **Dependency:** Nhận kết quả 09–10; chuẩn bị PyTorch/checkpoint thử và dữ liệu verdict tách riêng.
- **Trạng thái:** Đã nhận phần 10, review/sửa 8 ca; code `9d11071`, 713 Python + 37 Node PASS, 3 live-CVAT SKIP. [Báo cáo](11-report.md) / [bàn giao](11-handoff.md); quality model, GPU/Colab và precision tay chưa nghiệm thu.
- **Nguồn chung:** [kế hoạch 09–16](REVIEW-PLAN-09-16.md), [phân nhánh](README.md), [inventory 131 file](scope-inventory.tsv).

## Prompt để thực hiện phần này

> Thực hiện review phần 11 trên nhánh codex/review-11-verifier-learning. Đọc review/2026-10-13/11-verifier-learning.md và kế hoạch chung. Kiểm tra branch/HEAD và dependency trước khi làm; thực hiện đủ TC-11-001 đến TC-11-008. Truy vết luồng gọi và tái hiện trước khi kết luận lỗi; sửa lỗi có bằng chứng trong phạm vi phần 11, giữ sửa 01–08, kiểm lại bằng test phù hợp. Lưu 11-report.md, 11-handoff.md và evidence/11/. Ghi PASS/FAIL/SKIP/XFAIL riêng, ca bị chặn và thao tác cần tôi kiểm tay; không coi test mock là nghiệm thu dữ liệu/model/giao diện thật.

## Chọn nhánh và xác minh đầu vào

Chạy từ repo root; các lệnh test ở dưới chạy từ `source-tool/pointsnap-3d/`:

```powershell
git status --short
git switch codex/review-11-verifier-learning
git log -1 --oneline
```

Nếu phần trước đã merge vào main, chạy `git fetch origin main` rồi `git merge origin/main` trên nhánh này, giải xung đột và ghi SHA sau cập nhật. Nếu còn sửa chưa commit ở checkout, hoàn tất commit đúng phạm vi trước khi switch.

## Phạm vi và checklist

Đọc: `detectors/static.py`, `pointsnap/critic.py`, `learn.py`, `cli/learn_cmd.py`, `cli/eval_cmd.py`, `web/runner.py`, `scripts/train_critic_example.py`, `scripts/colab_train_critic.ipynb` và [hướng dẫn huấn luyện](../../source-tool/pointsnap-3d/docs/huong-dan/huan-luyen-box-critic.md).

| Mã | Kiểm tra và tiêu chí |
| --- | --- |
| TC-11-001 | Vật đứng yên trong world frame: ego chạy/quay, pose thiếu và vật chuyển động chậm; không nhầm sensor frame với world frame. |
| TC-11-002 | Feature Critic và nhiễu box: đơn vị, chuẩn hóa, point cloud rỗng/ít điểm, seed; target có thể kiểm độc lập. |
| TC-11-003 | Checkpoint đơn/ensemble: shape, dtype, thiết bị, file hỏng/không tin cậy; kiểm cách load và xử lý lỗi, model không có không được thành đã kiểm tốt. |
| TC-11-004 | So logit tương đối track: có/không reference hợp lệ, nhiều outlier, track ngắn; không coi score model là xác suất lỗi đã hiệu chuẩn. |
| TC-11-005 | Train/export: tuning và held-out tách theo scene/track; ensemble seed; giải phóng GPU và tái lập. Không dùng cảnh kiểm tra để chỉnh ngưỡng. |
| TC-11-006 | Learn đọc kết luận: sửa/xóa verdict, trùng run/box, dữ liệu thiếu/hỏng, nhiều project; không trộn mẫu hoặc dùng nhãn tự sinh làm verdict người dùng. |
| TC-11-007 | Cross validation và hạ severity: leakage cùng track/run, mẫu nhỏ/lệch class; bật/tắt adjust_severity, ngưỡng sát biên và ảnh hưởng gate. |
| TC-11-008 | Learned history: version, restore, ghi đồng thời/hỏng giữa chừng, đường dẫn project; giữ được mô hình trước và báo lỗi rõ. |

Test đầu: `python -m pytest -q tests/test_critic.py tests/test_learn.py tests/test_scenarios.py tests/test_web.py`.
Hai test Critic dùng PyTorch từng bị SKIP trong recheck trước. Phải chạy với PyTorch/checkpoint thử hợp lệ trước khi nghiệm thu; test model giả và checkpoint thật ghi riêng.

## Kết quả phải bàn giao

1. `review/2026-10-13/11-report.md`: SHA khởi đầu/kết thúc; file đã đọc; bảng 8 ca với trạng thái và evidence; findings `RV-11-xxx`; các sửa và test; giới hạn còn mở.
2. `review/2026-10-13/11-handoff.md`: tóm tắt sửa; SHA commit; lệnh đã chạy; PASS/FAIL/SKIP/XFAIL; dependency phần tiếp theo; ca cần người dùng kiểm tay.
3. `review/2026-10-13/evidence/11/`: tóm tắt/probe đã che thông tin nhạy cảm, gắn mã `EV-11-xxx`. Raw dataset, token, weights và output lớn không commit.
4. Inventory: đối chiếu các dòng `owner=11` trong `scope-inventory.tsv`, ghi kết luận cho mỗi file trong báo cáo. File dùng chung thuộc owner khác được tham chiếu và bàn giao nếu đã chạm.
5. Commit theo file cụ thể; xem `git diff --cached --name-only` trước commit. Push/PR/merge thực hiện theo yêu cầu riêng; base PR thường là main khi phần trước đã merge.

Hoàn tất review khi mọi ca có trạng thái và có bằng chứng cho kết luận. Các ca thiếu tài nguyên được bàn giao là Bị chặn; không xác nhận nghiệm thu cho tính năng chưa được kiểm đủ.
