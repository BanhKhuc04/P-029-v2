# Bàn giao phần 11

- Nhánh: `codex/review-11-verifier-learning`, nhận `8fce666` từ phần 10 bằng fast-forward.
- Code: **`9d11071`**, 10 nhóm sửa, 49 ca hồi quy. [Báo cáo](11-report.md).
- Gate cuối: **713 Python PASS, 0 FAIL/ERROR/XFAIL, 3 live-CVAT SKIP; 37 Node PASS**. Coverage 6 module 92,56%, package 91,75%.
- Hai ca Critic cũ đã chạy bằng **PyTorch 2.8.0 CPU thật**. Runtime cài riêng ở `source-tool/pointsnap-3d/out/review11-runtime`; trên Windows cần thêm DLL directory của bundled runtime cho process kiểm tra. [Chi tiết](evidence/11/runtime-recovery.md).
- Static GT: 10 cảnh/14.104 box; tuning 8 warning/1 error, held-out 15 warning/1 error, danh tính finding giữ nguyên. Không chỉnh ngưỡng bằng held-out.
- Export/train smoke: hai cảnh tuning, frame 0–2, 194 mẫu; ensemble seed 11/12, 2 epoch, split theo scene. Checkpoint thật đúng shape/finite; repeat và trung bình member có sai khác tối đa 0. Chưa chứng minh chất lượng model.
- GitHub: nhánh được đẩy theo yêu cầu tiếp nối; SHA bàn giao cuối xem HEAD remote. Chưa mở PR hoặc merge main.

## Lệnh và tài nguyên

Từ `source-tool/pointsnap-3d`, dùng `.venv/Scripts/python.exe`; đặt `NUSCENES_ROOT=C:/Users/Han/Downloads/v1.0-mini`, `POINTSNAP_LIVE_CVAT=0`, và `PYTHONPATH=<absolute out/review11-runtime>`. Trước khi nạp torch, process kiểm tra dùng `os.add_dll_directory` như evidence; giữ handle sống.

```text
pytest -q -p no:cacheprovider -o faulthandler_timeout=60
node --test tests/*.test.js                         (từ extension/)
python ../../review/2026-10-13/evidence/11/verifier_probe.py --dataroot <mini> --out <fresh.json> --export-dir <fresh-dir>
python ../../review/2026-10-13/evidence/11/training_probe.py --data <export> --out-dir <fresh-dir> --summary <fresh.json>
```

Suite/probe dùng quyền process ngoài sandbox để TestClient loopback và runtime Python hoạt động. XML/coverage/NPZ/model/raw output ở `out/`; evidence nhỏ, hash và script được commit. `verification.json` đối chiếu source với code commit sau chuẩn hóa CRLF/LF.

## Cho người review tiếp

1. Phần 12: chọn `codex/review-12-camera-models`, nhận phần 11 bằng `git merge --ff-only codex/review-11-verifier-learning` nếu chưa merge main. Giữ dependency torch CPU riêng; chuẩn bị torchvision/transformers và checkpoint camera đúng provenance.
2. Phần 14: kiểm các thay đổi coverage static/Critic, web 409 khi dữ liệu học hỏng/busy, identity-frame mơ hồ, latest-snapshot verdict và severity feedback khi bật adjust.
3. Phần 15: kiểm CLI không xuất held-out để học, split scene và actual rates/precision. Human verdict vẫn 0; không dùng checkpoint smoke hoặc ngưỡng gợi ý smoke làm bản triển khai.
4. Kiểm tay cần: verdict thật nhiều job/project, learned history restore khi dừng writer; chất lượng checkpoint chính thức, GPU/Colab và CVAT thật. Hard crash có thể cần dọn lock sau khi xác nhận tiến trình dừng.
