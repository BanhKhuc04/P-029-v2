# Bàn giao phần 12

- Nhánh `codex/review-12-camera-models`, nhận phần 11 tại `5920522` bằng fast-forward.
- Code **`b0cbba8`**, 11 nhóm sửa, **58 ca mới**. [Báo cáo](12-report.md).
- Gate cuối: **771 Python + 37 Node PASS**, 0 FAIL/ERROR/XFAIL, **3 live-CVAT SKIP**. Coverage 8 module 84,08%; package 92,65%; script eval riêng 25,21%.
- 6-camera mini oracle/visual QA đạt trên `scene-0061/frame 0`. Pixel error hợp lệ ≤6,905×10⁻⁹, depth ≤4,122×10⁻¹³.
- CPU operator/processor smoke đạt; **random weights/synthetic logits, không nghiệm thu pretrained**.
- **TC-12-008 bị chặn do thiếu weights**: tải chính thức reset/timeout/DNS failure; người dùng chưa có SAM. Pretrained quality, GPU và human precision vẫn chưa kiểm.
- Nhánh kết quả được push GitHub theo quy trình; chưa mở PR hoặc merge main. SHA bàn giao cuối xem HEAD remote.

## Chạy lại

Từ `source-tool/pointsnap-3d`, dùng `.venv/Scripts/python.exe`. Runtime camera ở `out/review12-runtime`, torch ở `out/review11-runtime`. Đặt `PYTHONPATH` bằng hai đường dẫn absolute này, camera runtime trước. Giữ process-local DLL handle như [runtime recovery](evidence/12/runtime-recovery.md).

```text
NUSCENES_ROOT=C:/Users/Han/Downloads/v1.0-mini
POINTSNAP_LIVE_CVAT=0
HF_HUB_OFFLINE=1
OMP_NUM_THREADS=1
MKL_NUM_THREADS=1
pytest -q -p no:cacheprovider -o faulthandler_timeout=60
node --test tests/*.test.js              (từ extension/)
```

`calibration_probe.py` và `runtime_probe.py` trong evidence nhận `--dataroot`, output/cache fresh. Runtime probe dùng processor đã cache tại `HF_HOME=<absolute out/review12-hf-home>` và không tải weights. Ảnh visual ở `out/review12-calibration.png`; XML/coverage/cache/runtime cũng chỉ ở `out/`.

## Cho phần sau

1. Phần 13 chọn `codex/review-13-missing-objects`, nhận 12 bằng `git merge --ff-only codex/review-12-camera-models` nếu chưa merge main. Kiểm static LiDAR + camera effective groups/fallback và cam.sparse; pretrained cases vẫn cần weights.
2. Phần 14 kiểm `camera.no_evidence` trong Web/CLI/gate, preserve LiDAR khi camera lỗi, unknown/missing camera coverage, sticky fallback và partial report. INFO không được flag lên CVAT.
3. Phần 15 kiểm full eval script/pretrained quality, same-camera coverage/recall, không tuning held-out và precision tay. Không dùng thời gian 64 px random smoke như benchmark model thật.
4. Shared storage đổi atomic replace có bounded Windows retry; giữ những test fault injection và race cũ khi kiểm learning/backend. Persistent denial vẫn báo lỗi và giữ active file.
