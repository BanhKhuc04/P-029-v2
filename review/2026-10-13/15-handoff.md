# Bàn giao phần 15

Model **gpt-6.1-sol**, candidate code `3a8bde2`. [15-report.md](15-report.md) có trạng thái từng ca, phương pháp và giới hạn. Đánh giá 10 vòng checkpointed còn đang chạy; chưa chốt số tổng mới.

Chạy/resume từ repo root (chọn out mới nếu đổi code/config/dataset):

```powershell
python review/2026-10-13/evidence/15/checkpoint_eval.py --tool-root <candidate-tool> --dataset <nuscenes-mini> --out <checkpoint-output> --rounds 10
```

`--scenes tuning` / `--scenes test` có thể chạy từng tập; chỉ tổng hợp khi 10 marker hoàn tất. Không dùng output ngắt giữa scene làm PASS. G7 giữ UNASSESSED khi thiếu truth; proxy báo riêng. TC-15-004/006/008 chưa đủ bằng chứng nghiệm thu rộng. Helper point sets và 9 GPU pretrained/cache smoke PASS, không gán human precision.
