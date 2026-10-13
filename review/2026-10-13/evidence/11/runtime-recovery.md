# EV-11-005 — runtime và probe recovery

- Python dự án 3.12.14; `.venv` ban đầu thiếu torch. Suite nền: 49 PASS/2 Critic SKIP.
- Kho CPU `download.pytorch.org` bị reset kết nối khi thử torch 2.5.1; không kết luận package không tồn tại từ lỗi mạng này.
- Cài wheel Windows chính thức từ PyPI: torch **2.8.0+cpu** và dependency vào `source-tool/pointsnap-3d/out/review11-runtime`. Không đổi `.venv` hay cài hệ thống.
- Máy thiếu Visual C++ DLL trong search path. Import ban đầu báo WinError 126/c10.dll. Các lượt red bị lỗi DLL không được dùng để chứng minh lỗi runtime Critic.
- Dùng DLL sẵn có trong bundled runtime qua process-local API, giữ handle tới hết process:

```python
import os
handle = os.add_dll_directory(
    "C:/Users/Han/.cache/codex-runtimes/codex-primary-runtime/dependencies/native/jxrlib/jxrlib/bin"
)
import torch
```

Đặt `PYTHONPATH` trỏ tới absolute path `out/review11-runtime`. Import sau recovery trả `2.8.0+cpu`, CUDA unavailable. Không sao DLL vào System32, không thay PATH hệ thống.

Các probe đã sửa và loại khỏi nghiệm thu:

1. Export mini lần đầu ghi scene-0061 rồi stdout cp1252 không in được tiếng Việt. Probe sau reconfigure UTF-8 và dùng output mới; không ghi đè lần trước.
2. Snapshot baseline lần đầu dùng Git pathspec từ sai cwd nên không xuất package, thực tế chạy current source. Lượt đó không được tính baseline. Đã xuất 104 file từ repo root và assert đường dẫn `pointsnap.__file__` chứa baseline source trước pytest; lượt cuối 42 FAIL/5 PASS/2 deselected mới là evidence baseline.
3. TorchScript ModuleList không hỗ trợ iteration trực tiếp sau load; training probe chuyển sang `named_children()`, rồi chạy lại trong thư mục mới. Đây là lỗi probe, không phải lỗi script train/ensemble. Probe cuối xác minh finite/repeat/member equality thành công.

Full suite chạy process ngoài sandbox vì TestClient loopback đã được xác định bị chặn trong phần 09; môi trường này cũng cần process ngoài sandbox để package/runtime truy cập đầy đủ. `POINTSNAP_LIVE_CVAT=0`; 3 test ghi lên CVAT thật vẫn SKIP.

Raw runtime/NPZ/checkpoints/XML/coverage chỉ ở `out/` bị ignore. Metadata đã commit không chứa weights hoặc dữ liệu điểm.
