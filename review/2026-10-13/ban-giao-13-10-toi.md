# Bàn giao tối 13/10/2026: việc còn mở

Mốc: `main` = `a405a4c` (đã merge #55, #58, #59 và hai commit của imvhuy). Tài liệu này liệt kê những gì **chưa xong hoặc
chưa chốt**. Mỗi mục ghi bằng chứng, file liên quan và việc cần làm. Đọc kèm [g7-cham-tay.md](g7-cham-tay.md) và
[whole-repo-report.md](whole-repo-report.md).

Quy trình: làm trên nhánh riêng và mở PR vào `main`, không đẩy thẳng. PR đặt base `main`, không xếp chồng lên nhánh PR
khác: khi #55 merge kèm xóa nhánh, GitHub đã tự đóng #57 đang xếp chồng trên nó. Người dùng tự merge bằng
`gh pr merge <số> --repo AI20K-Build-Phase-Cohort-4A/P-029 --merge` trong PowerShell 5.1.

## 1. Cần nhóm quyết (đừng tự sửa trước khi hỏi)

### 1.1 Luật vỉa hè làm mất lỗi lơ lửng đã xác nhận

- Code: `pointsnap/core/ground.py` (`curb_step_m`, `is_curb_supported`) và `pointsnap/detectors/floating.py` (hai chỗ
  `if getattr(est, "is_curb_supported", False): continue`). Commit `4c380f2` của imvhuy.
- Bằng chứng: trên 5 cảnh held-out, so với trước khi gộp, luật này bỏ **16 finding floating mà người dùng đã chấm tay là
  "Đúng lỗi"** (`evidence/g7/verdicts-heldout.csv`). Số floating: tuning 52 → 30, held-out 67 → 48.
- Điều kiện hiện tại coi là "tựa vỉa hè" khi đáy box nằm **bất kỳ đâu** giữa mặt thấp và mặt cao (cộng 8 cm), nên box lơ
  lửng ở bậc vỉa hè cũng bị bỏ.
- Việc cần làm: hỏi imvhuy mục tiêu của luật, rồi siết điều kiện (ví dụ chỉ bỏ khi đáy box khớp một trong hai mặt trong
  ±8 cm). Sau khi sửa, đối chiếu lại với file verdict: không được mất mục "Đúng lỗi".

### 1.2 `fit.loose` bật trong cấu hình mặc định

- `config.yaml` bật `fit_loose` / `fit_outside`; chỉ `guidelines/spec-vn.yaml` tắt. Dự án tạo từ cấu hình mặc định (ví dụ
  `cvat-local` trên máy người dùng) vẫn chạy luật này.
- Sau thay đổi `fit.py` trong `4c380f2`: tuning 13 → **55** finding (26 Lỗi mới), held-out 15 → 29. Chưa có verdict tay
  cho fit.loose.
- Việc cần làm: chốt bật hay tắt mặc định. Nếu bật thì chấm tay một mẫu trước.

### 1.3 `track.static_shift` không còn báo gì

- Sau `4c380f2` / `00e751c`: tuning 6 → 0, held-out 8 → 0, dù `config.yaml` để `track_static_shift: true`.
- Việc cần làm: xác nhận đây là chủ ý hay lỗi gộp (`core/rules.py`, `detectors/static.py`, `core/scanner.py`).

### 1.4 Tiêu chí G7

- Proxy "Cảnh báo / Lỗi trên 100 box nhãn chuẩn" đếm cả lỗi thật của nhãn nuScenes. Theo chấm tay, floating đúng 64/65 mục
  đã kết luận. Đề xuất đổi G7 sang precision từ chấm tay, giữ proxy làm số tham khảo.
- Ngưỡng `evidence.min_points: 20` và `floating.single_box: false` chọn từ chính bộ chấm held-out, nên số held-out không còn
  là phép thử độc lập.
- Số hiện tại (config mặc định, sau gộp): held-out **2,059 / 0,478**, tuning 0,970 / 0,462 trên 100 box.

### 1.5 PR #48 (`tune/fit-outside`)

Tăng độ nhạy fit.outside. Đang giữ lại vì làm tăng số finding; quyết sau mục 1.2.

## 2. Nhánh Codex chưa mở PR

| Nhánh | Commit chưa vào `main` | Ghi chú |
|---|---|---|
| `origin/codex/review-12-camera-models` | 2 (`b0cbba8`, `699433b`) | cache bằng chứng camera, khôi phục runtime |
| `origin/codex/review-13-missing-objects` | 4 (gồm review 12, thêm `ae1d579`, `4dbd91d`) | **xung đột `detectors/missing.py`** với `main` |

Xung đột ở review 13: `main` vừa thêm `missing.max_elevation_m` (commit `468e22f`, bỏ cụm treo cao như mái che, tầng nhà bị
coi là vật đứng sát đất), còn review 13 sửa kiểm tra chuyển động và camera trong cùng file. Khi gộp phải giữ cả hai, rồi
chạy lại:

- `tests/test_missing.py`, trong đó có `test_person_sized_cluster_on_high_roof_is_not_an_object`;
- phép đo "tìm lại vật bị xóa box" theo `docs/ket-qua/ket-qua-sot-doi-tuong.md`. Mốc sau `468e22f`: tìm lại 31/46 tuning,
  36/51 held-out, báo nhầm trên nhãn sạch 0 mỗi tập.

Review 14–16 chưa làm (`review/2026-10-13/14-integration.md` … `16-final.md`).

## 3. Kiểm tra end-to-end trên CVAT thật: mới xong nửa đầu

Sổ lỗi: artifact "Sổ lỗi E2E PointSnap" của người dùng. Bước 1–4 **Đạt**, chưa ghi lỗi nào. Còn:

5. Web: chấm Đúng / Báo nhầm rồi học.
6. CVAT `localhost:8080/tasks/4/jobs/4`: panel extension hiện lượt quét gần nhất.
7. Extension: **Quét + gắn cờ** (ghi `pointsnap_error` lên job 4), lọc chỉ box lỗi, bấm lỗi để nhảy tới box.
8. Sửa box trong CVAT, quét lại, lỗi phải hết.

imvhuy đã đổi extension (tự lọc trong `extension/src/content.js`, `core.js`), nên phải nạp lại extension trước bước 6–7.

## 4. Lỗi và giới hạn đã biết

- **Finding `lidar.missing` không có box**: preview và ảnh camera trả lỗi 422 vì không có box để dựng. `findings.json`
  chỉ ghi phần số đơn của `details` (`web/runner.py::_scalar_details`), nên mất `centers` / `size_m` của cụm. Nên ghi các
  list này rồi dựng box giả từ tâm cụm để preview.
- **Ảnh camera mới có trên web**, chưa có trong panel extension trong CVAT (người dùng có hỏi).
- **Xác nhận bằng camera của `lidar.missing` (vật đứng yên)** có thể bị lừa khi một vật gần hơn đã có box nằm cùng hướng
  nhìn: ở job 4, xe tải #40 sát xe thu được tính là xác nhận cho cụm ở xa 17 m. Bản sửa độ cao đã loại ca đó, nhưng
  chưa có kiểm tra độ sâu hay che khuất cho trường hợp chung.
- **Mặt đất của luật lơ lửng**: người dùng nhận xét về dốc và nhiều lớp mặt đường. Đã thử ba cách đo bằng mặt phẳng (nhiều
  lớp, trung vị trừ dốc về tâm box, quy về góc thấp nhất); cả ba làm mất 53–58 lỗi đã xác nhận nên giữ trung vị vành đai.
  Độ dốc chỉ được ghi vào câu báo (`pitch_deg`). Muốn đổi phép đo thì phải đối chiếu lại với file verdict.
- **Chưa có verdict tay** cho `heading.points`, `fit.loose`, `track.*`, `size.class_range` (25 mục size đều "Không rõ").
- **Triển khai**: `localhost:8080/pointsnap/health` trả HTML của CVAT, chưa phải Report API (theo whole-repo-report).

## 5. Môi trường máy người dùng (Windows)

- Bash (Git Bash) có lúc bị Application Control chặn; dùng PowerShell 5.1.
- PowerShell 5.1: `Set-Content -Encoding utf8` ghi BOM (đã làm hỏng một subject commit). Nên ghi message commit bằng
  `[IO.File]::WriteAllText(path, text, (New-Object Text.UTF8Encoding $false))` rồi `git commit -F`. Chuỗi có dấu ngoặc kép
  truyền cho lệnh native dễ bị cắt.
- Token CVAT nằm trong `~/.pointsnap/projects/cvat-local/secret.json` và `.env`. File có CRLF nên khi đọc bằng shell phải
  bỏ `\r`. Không in token.
- Dữ liệu: nuScenes mini `D:/Vin_uni/data/nuscenes`; bản xuất `D:/Vin_uni/data/cvat-v2/scene-0061` (task 4 / job 4 trên
  CVAT 2.77.0).
- PointSnap Web để test với extension phải chạy cổng **8765** (manifest extension chỉ cho cổng này). Cách chạy:
  `.venv/Scripts/pointsnap.exe ui --port 8765 --no-browser`.
- Thư mục `source-tool/pointsnap-3d/landing/` chưa được git theo dõi; không commit nếu người dùng chưa yêu cầu.
