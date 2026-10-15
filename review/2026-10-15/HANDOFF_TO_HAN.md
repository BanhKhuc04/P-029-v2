# 📋 BIÊN BẢN BÀN GIAO CÔNG VIỆC — TEST TOÀN BỘ CÁC CHỨC NĂNG CÒN LẠI

> **Người bàn giao:** Antigravity Pairing Agent  
> **Người tiếp nhận:** Hân  
> **Thời điểm:** 15/10/2026  
> **Trạng thái Git:** Commit `6f38c19` trên nhánh `main`  
> **Môi trường:** CVAT Local `http://localhost:8080` · PointSnap Web UI `http://localhost:8765`

---

## 1. Tóm tắt kết quả các phần ĐÃ HOÀN THÀNH

### ✅ Milestone 1: Loại bỏ triệt để nhóm luật nhận diện đứt track (`track.*`)
- **Cấu hình & Scanner:** Đã tắt mặc định toàn bộ 7 luật: `track_jump`, `track_split_id`, `track_long_interpolation`, `track_reuse_id`, `track_occluded_long`, `track_id_swap`, `track_static_shift`.
- **4 tầng phòng thủ (Defense-in-depth):**
  1. `pointsnap.core.scanner`: `check_track` trả về `[]` vô điều kiện khi các cờ track tắt.
  2. `pointsnap.web.runner`: API `get_run()` tự động lọc bỏ mọi finding có tiền tố `track.`.
  3. `pointsnap.web.static.app.js`: Web UI lọc sạch các luật `track.` trong danh sách và thẻ tab.
  4. `extension/src/content.js`: Extension lọc sạch các cờ `track.` khi tải từ CVAT (`loadFlags`) và khi click chọn box (`currentFlag`).
- **Dữ liệu CVAT:** Đã chạy script gỡ sạch **1.282 cờ lỗi đứt track cũ** trong database CVAT (Job 1, 2, 4).
- **Tính toàn vẹn hình học 3D:** Giữ nguyên 100% độ nhạy của các luật `floating`, `fit.*`, `heading.*`, `size.*`.

### ✅ Milestone 2: Kiểm chứng cơ chế đồng bộ 2 chiều (Zero-F5)
- **OCC ETag SHA-256 Conflict (409):** Chặn ghi đè dữ liệu khi nhãn CVAT bị sửa đổi từ phía khác.
- **Offline CVAT Protection (503):** Chặn bấm nhầm khi mất kết nối CVAT.
- **Signal `annotations_changed`:** Lan truyền sự kiện cập nhật tức thời giữa Extension và Web UI qua `link.focus()`.

### ✅ Milestone 3: Báo cáo trực quan & Biểu đồ đồ họa (Visual Analytics Report)
- Đã xuất 3 biểu đồ tĩnh dạng ảnh `.png` tại `review/2026-10-15/`:
  - `error_distribution.png`: Biểu đồ cột phân bố lỗi theo danh mục luật (chính xác 0 track findings).
  - `residuals_distribution.png`: Boxplot & Histogram sai số cao độ $\Delta z$ và góc xoay $\Delta\text{yaw}$.
  - `performance_metrics.png`: Hiệu năng quét, độ trễ API và tỷ lệ pass test suite (99.7%).
- Báo cáo tổng hợp: `review/2026-10-15/ANALYTICS_REPORT.md`.

### ✅ Milestone 4: Kiểm thử hồi quy toàn diện
- **Python Pytest:** 1328 passed, 4 skipped, 0 failed.
- **Extension Node.js:** 156 passed, 0 failed.

---

## 2. Nhiệm vụ BÀN GIAO CHO HÂN: Test toàn bộ chức năng còn lại

Trọng tâm của Hân là **kiểm thử thực tế và nghiệm thu công cụ căn chỉnh Bounding Box 3D bán thủ công (phong cách Lightroom)** trên CVAT 3D Canvas và đánh giá chất lượng mô hình.

### 🎯 Nhiệm vụ 1: Kiểm thử Công cụ Căn chỉnh Bán thủ công (Ghost Target Guides & Magnet Snap)
- **Mã nguồn liên quan:**
  - `source-tool/pointsnap-3d/extension/src/ghost-engine.js`: Thuật toán sinh khung gióng mục tiêu ảo, lực hút nam châm và dung sai.
  - `source-tool/pointsnap-3d/extension/src/telemetry-hud.js`: Bảng đồng hồ HUD hiển thị thông số thời gian thực (60 FPS feel).
  - `source-tool/pointsnap-3d/extension/src/cvat-3d-hook.js`: Hook can thiệp vào Three.js 3D Canvas của CVAT.
  - `source-tool/pointsnap-3d/pointsnap/core/ghost.py`: API backend sinh Ghost Target từ findings.

- **Kịch bản kiểm thử cần thực hiện:**
  1. **Khung gióng mục tiêu ảo (Ghost Target Box):**
     - Mở một box có lỗi (ví dụ `floating` lơ lửng, hoặc `heading.flip` lệch góc) trên CVAT.
     - Kiểm tra khung nét đứt màu xanh/cam (Ghost Box) có xuất hiện tại vị trí mục tiêu tối ưu không.
  2. **Kéo tay chủ động kết hợp Hút nam châm (Magnet Snap):**
     - Dùng chuột kéo/dời box về phía khung mục tiêu.
     - Xác nhận khi khoảng cách $\le 8\text{ cm}$ hoặc góc xoay $\le 4^\circ$, box có tự động "hút" dính khít vào khung mục tiêu không.
     - Khi kéo ra xa ($> 12\text{ cm}$), box có nhả lực hút mượt mà không (hiện tượng trễ hysteresis).
  3. **Phím tắt Cân bằng nhanh (Leveling Hotkey):**
     - Chọn một box bị nghiêng (có góc roll/pitch khác 0).
     - Nhấn phím `L` hoặc `Shift + S`.
     - Xác nhận box có lập tức cân bằng phẳng roll/pitch về $0^\circ$ và hạ đáy chạm sát mặt đất không.
  4. **Bảng đồng hồ HUD Thời gian thực & Đèn báo XANH LÁ (Green Target Lock):**
     - Quan sát thẻ HUD nổi cạnh box khi đang kéo: các số liệu $\Delta z$, $\Delta\text{yaw}$, độ hở cụm điểm có biến thiên mượt mà theo thời gian thực không.
     - Khi box đạt dung sai chuẩn ($\le 2\text{ cm}$ và $\le 2^\circ$): Viền khung và HUD có **BẬT SÁNG ĐÈN XANH LÁ** kèm thông báo `✓ Vị trí hoàn hảo` không.
     - Nhả chuột: Box có tự động khóa vị trí tối ưu không.

---

### 🎯 Nhiệm vụ 2: Kiểm chứng Chất lượng Mô hình & Đo lường Precision
- **Mục tiêu:** Đảm bảo box sau khi được kéo vào vị trí Green Lock sẽ hoàn toàn sạch lỗi khi quét lại và tối đa hóa Precision.
- **Kịch bản kiểm thử:**
  1. Quét lại job sau khi đã chỉnh sửa các box.
  2. Xác nhận 100% các box đã sửa đạt trạng thái PASS (0 errors, 0 warnings).
  3. Chạy đánh giá trên 5 cảnh held-out của nuScenes mini:
     ```powershell
     cd d:\Vin_uni\P-029\P-029\source-tool\pointsnap-3d
     & .venv\Scripts\python.exe auto-tests\manual_precision.py
     ```
     - Xác nhận Precision đạt $\ge 95\%$ trên các lỗi hình học cơ bản.

---

### 🎯 Nhiệm vụ 3: Kiểm tra luồng Hoàn tác (Undo / Rollback) & An toàn dữ liệu
- Khi annotator chỉnh sửa hoặc áp dụng gợi ý:
  - Thử nhấn `Ctrl + Z` hoặc bấm nút **Hoàn tác (Rollback)** trên Extension / Web UI.
  - Xác nhận box được phục hồi chính xác $100\%$ tọa độ, góc xoay và kích thước ban đầu từ snapshot bất biến.
  - Thuộc tính nhãn (label, attributes, track ID) không bị biến dạng hay mất mát.

---

## 3. Lệnh khởi động môi trường để test

### 1. Khởi chạy PointSnap UI Daemon:
```powershell
cd d:\Vin_uni\P-029\P-029\source-tool\pointsnap-3d
& .venv\Scripts\python.exe -m pointsnap ui
```
- Web UI truy cập tại: `http://localhost:8765`

### 2. Truy cập CVAT:
- URL: `http://localhost:8080`
- Job test mẫu: `http://localhost:8080/tasks/2/jobs/2`
- Extension PointSnap: Đã tích hợp sẵn trong Chrome hoặc nạp từ thư mục `source-tool/pointsnap-3d/extension`.

### 3. Chạy toàn bộ test suites kiểm tra hồi quy:
```powershell
# Test Python:
cd d:\Vin_uni\P-029\P-029\source-tool\pointsnap-3d
& .venv\Scripts\python.exe -m pytest tests/ -q

# Test Extension JS:
node --test extension/tests/*.test.js
```

---

## 4. Danh mục File Cốt lõi phục vụ Tiếp quản

| Tính năng | Đường dẫn file |
|---|---|
| **Ghost Guides Engine** | `source-tool/pointsnap-3d/extension/src/ghost-engine.js` |
| **Telemetry HUD & Green Lock** | `source-tool/pointsnap-3d/extension/src/telemetry-hud.js` |
| **CVAT 3D Hook (Three.js)** | `source-tool/pointsnap-3d/extension/src/cvat-3d-hook.js` |
| **Backend Ghost Target API** | `source-tool/pointsnap-3d/pointsnap/core/ghost.py` |
| **Backend Repair Engine** | `source-tool/pointsnap-3d/pointsnap/core/repair.py` |
| **History & Rollback Manager** | `source-tool/pointsnap-3d/pointsnap/history/manager.py` |
| **Báo cáo Phân tích Trực quan** | `review/2026-10-15/ANALYTICS_REPORT.md` |
| **Biểu đồ Phân bố Lỗi (PNG)** | `review/2026-10-15/error_distribution.png` |
| **Biểu đồ Residuals (PNG)** | `review/2026-10-15/residuals_distribution.png` |
| **Biểu đồ Hiệu năng (PNG)** | `review/2026-10-15/performance_metrics.png` |
