# Review mã nguồn PointSnap 3D — 15/10/2026

Người review: Claude Code. Phạm vi: `source-tool/pointsnap-3d/` (package `pointsnap/`, `extension/`, Docker/Compose, script khởi động) trên `main` `863a4cc`.
`cvat-develop/` là CVAT upstream nên không review.

## Kết quả chạy kiểm thử trước khi sửa

| Bộ test | Lệnh | Kết quả |
|---|---|---|
| Python | `.venv\Scripts\python.exe -m pytest -q` | 1324 passed, 8 skipped (4 phút 11 giây) |
| Extension | `cd extension && node --test tests/*.test.js` | **151 passed, 5 failed** (Node 24, checkout Windows CRLF) |

Biên bản bàn giao `review/2026-10-15/HANDOFF_TO_HAN.md` ghi "156 passed, 0 failed". Trên máy này có 5 test fail, xem mục P3-4.

## Mức độ

- **P1**: dữ liệu sai, ghi nhầm lên CVAT hoặc tính năng không chạy được.
- **P2**: kết quả sai trong một số trường hợp, độ tin cậy bị thổi phồng, lỗi 500 hoặc hiệu năng.
- **P3**: dọn dẹp, phòng thủ, test.

---

## P1 — cần sửa trước khi nghiệm thu

### P1-1. Chỉ số finding bị lệch giữa danh sách đã lọc `track.*` và `findings.json` gốc

- `pointsnap/web/runner.py:336` và `:355`: `get_run(include_findings=True)` bỏ các finding `track.*` rồi trả về. Web (`app.js:1004` `runFindingIndex`) và extension dùng vị trí trong danh sách **đã lọc** làm `index`.
- Các chỗ sau lại dùng vị trí trong `findings.json` **gốc**:
  - `pointsnap/web/preview.py:102-105` (`_finding_box`): preview point cloud, ảnh camera, và điểm cho `get_finding_repair`.
  - `pointsnap/learn.py:74-92`: `reviews.get(str(i))` với `i` là chỉ số gốc.
- `runner.py:376` (nhánh chỉ có `summary.json`) **không** lọc, nên ba nhánh của `get_run` không nhất quán với nhau.
- **Tác động:** với mọi lần quét có finding `track.*` (các run cũ trước khi tắt luật track, hoặc dự án bật lại luật track trong guideline), mọi mục sau finding `track.*` đầu tiên sẽ hiện preview/ảnh camera của box khác. Kết luận Đúng/Báo nhầm bị gán sang finding khác, nên mô hình học (lớp 4) học sai nhãn.
- **Hướng sửa:** dùng một chỉ số ổn định duy nhất. Khuyến nghị: mỗi finding trả về giữ `index` gốc trong `findings.json` (ví dụ trường `"index"`). Web, extension, reviews, preview, camera và repair đều dùng giá trị đó. Lọc `track.*` ở một hàm dùng chung. `put_review` (`app.py:400`) kiểm tra theo chỉ số gốc. Thêm test hồi quy với `findings.json` có `track.*` xen giữa.

### P1-2. Hook 3D (Ghost box, Magnet Snap, phím `L`, HUD) không kết nối được canvas CVAT thật

- `extension/src/cvat-3d-hook.js:45-67` tìm scene qua `window.__THREE_SCENE__`, `canvas.__three_scene__` hoặc `window.cvat.canvas3d`. CVAT (`cvat-canvas3d`) không đưa ra các biến này (grep `cvat-develop` không có), và cũng không có `THREE` toàn cục. Vì vậy `updateGhostMesh` trả `null` và không vẽ được khung.
- `setActiveBox` (`:255`) không được gọi ở đâu trong trình duyệt (chỉ test gọi). Hệ quả là `handlePointerMove` và `handleHotkey` luôn thoát sớm: không có telemetry, không snap, phím `L` không làm gì, HUD không nhận dữ liệu.
- Kể cả khi snap được, box kết quả không bao giờ được ghi lại vào CVAT.
- Listener chuột được gắn một lần lúc `document_idle` (`:417-428`). CVAT là SPA, canvas 3D mount sau, nên listener thường không được gắn.
- **Tác động:** Nhiệm vụ 1 trong bàn giao (Ghost Target, Magnet Snap, Leveling, Green Lock) không thể đạt trên CVAT thật. Test Node chỉ chạy với mock nên vẫn xanh.
- **Hướng sửa trong đợt này** (không giả lập tính năng):
  1. Khi không tìm thấy scene hoặc box đang chọn, phát sự kiện trạng thái `POINTSNAP_3D_UNAVAILABLE` kèm lý do. Panel/HUD hiển thị rõ "Chưa kết nối được canvas 3D của CVAT", không im lặng.
  2. Gắn listener theo `MutationObserver` hoặc ủy quyền sự kiện ở `document`, để canvas mount muộn vẫn hoạt động.
  3. Content script gửi box đang chọn (center/dims/yaw/roll/pitch lấy từ annotations CVAT API mà content.js đã có) sang MAIN world bằng `postMessage` `POINTSNAP_SET_ACTIVE_BOX`. Nhờ vậy residual/HUD tính được từ dữ liệu thật dù chưa vẽ được mesh.
  4. Ghi rõ trong README/bàn giao: vẽ khung và kéo thả hút trực tiếp trên canvas cần tích hợp sâu với CVAT (patch cvat-canvas3d), chưa làm.

### P1-3. Ghi/hoàn tác có thể nhắm nhầm dự án hoặc server CVAT khi thiếu `slug`

- `pointsnap/web/app.py:613-619` (`_resolve_track`): khi không có `slug`, code lấy `projects[0]`. Phần chặn `len(projects) > 1 and not allow_snapshot` không bao giờ chạy với ghi, vì `apply_track_repair` (`:1017`) và `rollback_track_repair` (`:1249`) đều truyền `allow_snapshot=True`.
- Tương tự ở `:796-800` và `:948-951` (nạp point cloud của dự án đầu tiên).
- Khi `slug` vắng, history ghi vào slug `"default"` (`:1154`, `:1207`), không thuộc dự án nào.
- `extension/background.js` cho phép GET `/repair` không kèm `slug`, khi đó bỏ qua bước kiểm dự án cùng origin CVAT.
- **Tác động:** có nhiều dự án hoặc nhiều server CVAT thì `apply-repair` có thể đọc và ghi track cùng ID trên server khác. Track ID của các server khác nhau trùng nhau là bình thường.
- **Hướng sửa:** với `apply-repair` và `rollback`, bắt buộc có `slug` hợp lệ (400 nếu thiếu), trừ track test (`mock_tracks`). Chỉ dùng CVAT của dự án đó. Bỏ fallback `projects[0]`. Extension luôn gửi `slug` (background trả lỗi nếu không có `slug` cho repair/apply/rollback).

### P1-4. Snapshot lịch sử được lưu trước khi ghi CVAT thành công

- `app.py:1153-1172`: `save_snapshot` chạy trước `write_verified_track`. Nếu ghi trả 409 hoặc 502, lịch sử vẫn có bản ghi "đã sửa" dù CVAT không đổi. Hoàn tác bản ghi đó sau này sẽ báo `already_rolled_back`, gây hiểu nhầm.
- **Hướng sửa:** lưu snapshot sau khi `write_verified_track` xác nhận, dùng `post_repair_track` do CVAT trả về. Nếu muốn giữ dấu vết ý định, ghi trường `status: "pending"` rồi cập nhật thành `"verified"`/`"failed"`. Thêm test: ghi CVAT lỗi thì không có snapshot `verified`.

---

## P2

### P2-1. Mốc mặt đất tham chiếu của track dùng point cloud của frame hiện tại cho box ở frame khác

- `pointsnap/core/repair.py:117-128` và `pointsnap/core/ghost.py:200-214`: `ring_ground_for_box(points, p)` với `p` là box của frame khác, nhưng `points` là point cloud của frame đang sửa. Tọa độ sensor đổi theo frame khi xe chạy, nên `reference` (và `Δz` đề xuất) bị lệch.
- **Hướng sửa:** chỉ tính tham chiếu từ peer khi có point cloud đúng frame của peer (truyền `frame_source`) hoặc lấy `track_median_distance` từ finding. Không đủ dữ liệu thì dùng `reference = 0` và giảm confidence.

### P2-2. Confidence bị nâng sàn và ghi đè

- `ghost.py:387` ghi đè confidence riêng theo luật (0.92/0.88/0.98) và luôn ≥ 0.80 kể cả khi chỉ có 5 điểm.
- `repair.py:140`: `max(0.80, ...)` kể cả khi `d` lấy từ `details["distance"]` cũ, với `num_ground_points` mặc định 20.
- **Tác động:** đề xuất kém tin cậy vẫn hiện `applicable` (`app.py:833` chỉ cần `confidence > 0`).
- **Hướng sửa:** confidence tính từ số điểm thật, không đặt sàn cố định. Nếu dùng dữ liệu cũ thì giảm confidence. Giữ hệ số theo luật thay vì ghi đè.

### P2-3. Endpoint GET để lộ tham số nội bộ

- `app.py:705-715` (`get_track_repair`) và `:872-882` (`get_track_ghost_target`) khai báo `points: Any`, `finding_details: dict`, `frame_source: Any` làm tham số route. Client gửi được `?frame_source=x&rule=heading.flip`, dẫn tới `"x".frame_data` và lỗi 500 (`AttributeError`, không được bắt ở `:760`/`:928`). `finding_details` thành body của GET và cho phép chèn `target_yaw_sensor` tùy ý.
- **Hướng sửa:** tách logic thành hàm nội bộ `_compute_track_repair(...)` và `_compute_ghost_target(...)`. Route chỉ nhận `frame`, `rule`, `slug`. `get_finding_repair` gọi hàm nội bộ.

### P2-4. Fallback hướng dùng góc toàn cục như góc sensor

- `track_heading_deg` (`detectors/heading.py:115`) là hướng trong hệ world. `ghost.py:230-231` và `repair.py:182-184` dùng trực tiếp nó làm yaw sensor khi thiếu `target_yaw_sensor`.
- `app.py:940` xóa `target_yaw_sensor` khỏi details nhưng không đặt lại khi không có finding mới, nên endpoint ghost-target đi vào nhánh sai. Các nhánh dùng trung bình yaw sensor của peer ở frame khác cũng gặp lỗi này khi xe quay đầu.
- **Hướng sửa:** khi không có `target_yaw_sensor`, không đề xuất xoay (confidence 0, kèm lý do) thay vì đổi hệ tọa độ sai. Làm như `get_track_repair` ở `:785-786`.

### P2-5. Fallback lịch sử trong `_resolve_track` là code chết

- `app.py:693` gọi `list_snapshots(..., track_id=track_id)` nhưng `HistoryManager.list_snapshots` không có tham số `track_id`, nên luôn `TypeError` và bị `except Exception: pass` nuốt mất. Nếu chạy được thì `snaps[0]` cũng có thể thuộc track khác.
- **Hướng sửa:** thêm lọc `track_id` vào `list_snapshots` (kèm test), hoặc bỏ fallback này.

### P2-6. `HistoryManager.get_snapshot` đọc ngoài `home_dir` đã cấu hình

- `pointsnap/history/manager.py:328` và `:344` luôn tìm thêm `Path.home()/.pointsnap` kể cả khi `home_dir`/`POINTSNAP_HOME` khác. Test hoặc một instance khác có thể đọc và hoàn tác snapshot của dữ liệu thật.
- Glob `*{history_id}.json` khớp cả tên file chỉ kết thúc bằng id.
- **Hướng sửa:** chỉ tìm trong `self.home_dir` (và `base_dir` nếu truyền). Glob khớp chính xác `f"{history_id}.json"`.

### P2-7. `/api/extension/poll` đọc toàn bộ lần quét mỗi giây

- `app.py:495-509`: mỗi lần poll (1 lần/giây/tab), code duyệt mọi dự án, gọi `list_runs` rồi `get_run` cho từng run. Mỗi `get_run` chạy `_check_outputs`, đọc `summary.json` và `findings.json`, có thể ghi `run.json`.
- **Hướng sửa:** dùng trạng thái trong bộ nhớ của `ScanRunner` cho `active`. Cache `latest_run_id` theo `(slug, job_id)` và chỉ làm mới khi có run mới hoàn tất.

### P2-8. Magnet Snap thay kích thước box kể cả khi không snap; "SNAPPED" chỉ vì yaw gần

- `extension/src/ghost-engine.js:262-264`: `newDims` luôn lấy `targetBox.dims`, nên mỗi lần `handlePointerMove` kích thước box bị thay âm thầm.
- `ghost-engine.js:174-177` và `pointsnap/core/ghost.py:528`: `isSnapped = dist ≤ 8 cm OR |Δyaw| ≤ 4°`. Một box cách mục tiêu 4 m nhưng cùng hướng vẫn hiện `SNAPPED`.
- **Hướng sửa:** chỉ đổi dims khi `translationSnapped`. Trạng thái tổng `SNAPPED` chỉ bật khi tịnh tiến đã snap. Báo riêng `rotationSnapped`. Đồng bộ Python và JS, cập nhật test.

---

## P3

- **P3-1.** `app.py:1293` và `:1336`: `get_finding_repair`/`apply_finding_repair` không bắt `ProjectError` từ `runner.get_run`, nên slug hoặc run sai trả 500. Cần trả 404 như các route khác.
- **P3-2.** `app.py:624`: `CvatClient` tạo trong `_resolve_track` không bao giờ `session.close()`. Sửa bằng cách đóng trong `finally` khi không trả client ra ngoài, hoặc để caller đóng.
- **P3-3.** Các đường ghi CVAT không có OCC/verify và không được dùng: `adapters/cvat/writer.py` `patch_track_keyframe`, `rollback_track_annotation`; `history/manager.py` `HistoryManager.rollback_track` và các hàm module-level. Nên xóa (và test tương ứng), hoặc chuyển qua `write_verified_track`.
- **P3-4.** `extension/tests/test_challenger_m4_adversarial.test.js:299`: regex `/function\s+drawPreview\s*\([\s\S]*?\n\s{2}\}\n/` không khớp khi checkout có CRLF (`core.autocrlf=true`), gây 5 test fail. Sửa regex sang `\r?\n` và thêm `.gitattributes` (`*.js text eol=lf`, `*.py text eol=lf`) hoặc ít nhất làm test không phụ thuộc EOL.
- **P3-5.** `compute_track_etag` bị lặp ở `writer.py:203` và `history/manager.py:85`. Chỉ giữ một bản.
- **P3-6.** `cvat-3d-hook.js:402` và `content.js:1246` nhận `message` từ mọi nguồn. Cần thêm `if (e.source !== window) return;` để iframe hoặc script khác không đặt ghost target hay giả telemetry.
- **P3-7.** `web/security.py:455` chấp nhận mọi Origin `chrome-extension://[a-p]{32}`. Nên cho phép cấu hình ID extension (`POINTSNAP_EXTENSION_IDS`) và chỉ cho các ID đó gọi API ghi (POST/PUT/DELETE).

---

## Điều kiện hoàn tất cho đợt sửa

1. Mỗi mục P1/P2 có test hồi quy tái hiện lỗi trước khi sửa.
2. `.venv\Scripts\python.exe -m pytest -q` không fail.
3. `cd extension && node --test tests/*.test.js` 0 fail trên checkout Windows.
4. Không thay đổi hành vi đã đúng ngoài phạm vi trên. Không commit dữ liệu hay token.
5. P1-2 không được "giả lập đạt": khi chưa vẽ được trên canvas CVAT thật, giao diện phải báo rõ.
