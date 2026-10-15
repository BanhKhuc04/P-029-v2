# Bàn giao cho Antigravity — PointSnap 3D (08/10/2026)

> **⏸ TẠM HOÃN (08/10): chưa bắt đầu A12.** Người dùng chờ nhóm test xong, đọc bảng tổng hợp lỗi rồi mới quyết định
> làm gì tiếp. Không code A12 cho tới khi người dùng giao lại.

File này đặt **ngoài repo** (không commit). Đọc hết trước khi làm. Bản 07/10 (việc A11) đã xong, đã bị thay bằng bản này.

## 0a. Việc giao ngay: A13 — làm lại giao diện web theo thiết kế "phần mềm doanh nghiệp"

Người dùng đã duyệt bản thiết kế (Claude vẽ trên design canvas). Bản thiết kế nằm ở **`D:\Vin_uni\P-029\thiet-ke-A13\`**
(ngoài repo, không commit): mỗi file `.dc.html` là một màn hình, phần `<x-dc>` là HTML + style inline, khối
`<script type="text/x-dc">` chứa bảng màu (`palette(dark)`) và dữ liệu mẫu. Đọc để lấy **bố cục, màu, chữ, khoảng cách**;
không chép cú pháp `{{…}}`, `<sc-for>`, `<sc-if>`, `DCLogic` vào code thật.

| File | Màn |
|---|---|
| `Brand.dc.html` | Logo (khối hộp nét mảnh + chấm "snap" xanh ở góc đáy), biểu tượng ứng dụng, bảng màu, chữ |
| `Main.dc.html` | **Kết quả**: bảng phát hiện + bảng chi tiết bên phải (bản tối: `KetQuaToi.dc.html` = cùng màn với `dark=true`) |
| `Quet.dc.html` | **Quét job**: 1. Chọn job → 2. Tùy chọn → nút chạy; tiến độ theo bước; lần quét gần đây |
| `Guideline.dc.html` | **Guideline** dạng trang cài đặt: công tắc luật, tiêu chí đạt, ngưỡng, bảng khoảng kích thước, thanh "Lưu thay đổi" |
| `LichSu.dc.html` | **Lịch sử**: biểu đồ cột Lỗi / Cảnh báo theo lần quét + bảng |
| `Loading.dc.html` | **Logo động khi tải**: khối hộp rơi xuống mặt đất → chấm xanh bật ra + vòng sóng, chu kỳ 1,6 s. CSS `@keyframes` trong `<style>` của file (`ps-drop`, `ps-snap`, `ps-ring`) + bản giảm chuyển động |

**Logo động (bắt buộc dùng thay mọi vòng xoay / chữ "Đang tải" trơn):** làm thành một đoạn SVG dùng lại được (vd hàm
`loaderSvg(size)` trong `app.js` + class CSS `ps-box` / `ps-dot` / `ps-ring`), lấy đúng keyframes trong `Loading.dc.html`.
Dùng ở: nút "Bắt đầu quét" / "Quét lại và gắn cờ" khi đang chạy (18 px, nét trắng), "Kiểm tra kết nối" và tải danh sách
task (20 px cạnh chữ), màn chờ khi mở dự án / đang quét (48 px, kèm chữ trạng thái). Thêm `role="img"` +
`aria-label="Đang tải"` (hoặc `aria-hidden` khi đã có chữ bên cạnh) và tôn trọng `prefers-reduced-motion` (khối hộp đứng
yên, chỉ chấm xanh nhấp nháy). Logo tĩnh ở thanh trên giữ nguyên, không chuyển động.

**Yêu cầu:**
- Viết lại `pointsnap/web/static/index.html`, `styles.css`, `app.js` theo thiết kế. **Không đổi API backend** (dùng các
  endpoint hiện có); giữ đủ mọi chức năng đang có: tạo / sửa / xóa dự án (xóa phải gõ lại tên), kết nối CVAT, chọn task /
  job, quét có / không gắn cờ + theo dõi tiến độ, lọc kết quả, "Quét lại và gắn cờ", tải HTML / CSV, guideline dạng biểu
  mẫu + YAML, lịch sử + biểu đồ.
- **Khung chung:** thanh trên cùng màu navy (logo, nút chọn dự án dạng menu thả xuống — thay danh sách dự án ở thanh bên
  cũ, có mục "Tạo dự án", trạng thái CVAT, nút **Sáng | Tối**); thanh trái 2 nhóm **Kiểm tra** (Quét job, Kết quả + số
  Lỗi + Cảnh báo của lần quét mới nhất, Lịch sử) và **Cấu hình** (Guideline, Kết nối CVAT); breadcrumb; tiêu đề trang với
  nút thao tác bên phải.
- **Kết quả:** chọn một dòng → bảng chi tiết bên phải hiện mức, luật, frame, track · class, giá trị đo (`value`), ngưỡng
  (`threshold`), mô tả, nút **"Mở đúng box trong CVAT"** (dùng `cvat_link` của API, đã có `type` / `serverID` sau PR #27),
  và dòng nhắc "link chỉ đúng với lần quét mới nhất". Mục **"Gợi ý cách sửa"**: không có trong API → dùng bảng chữ cố định
  theo `rule` trong `app.js` (một câu hướng dẫn chung cho mỗi luật, ví dụ `floating`: "Đưa đáy box về sát mặt đất, đối
  chiếu ảnh camera và các frame lân cận của track"). Lọc theo mức bằng tab có số đếm; phân trang phía trình duyệt (50 mục /
  trang). Thông báo cổng kiểm soát dạng dải màu nhạt + lý do.
- **Kết nối CVAT** và hai hộp thoại Tạo / Xóa dự án chưa có trong bản vẽ: làm cùng phong cách với trang Guideline (nhãn +
  mô tả bên trái, ô nhập bên phải).
- **Màu (token CSS trên `:root`, đổi theo `[data-theme="dark"]`):** lấy đúng `palette()` trong `Main.dc.html`. Sáng:
  nền `#F4F6F9`, bề mặt `#FFFFFF`, viền `#DDE2E8`, chữ `#161B22` / `#4A5563` / `#68717D`, xanh chính `#0B63CE` (chữ trên
  nút `#FFFFFF`), nền chọn `#E8F1FC`, thanh trên `#0F2A47`, Lỗi `#B42318`, Cảnh báo `#A35200`. Tối: nền `#0D1117`, bề mặt
  `#151B23`, viền `#2A333F`, chữ `#E6EAF0`, xanh chính `#4C9AFF` (chữ trên nút `#04162E`), thanh trên `#0A0F15`, Lỗi
  `#F38B85`, Cảnh báo `#F0A54A`. Chế độ mặc định theo `prefers-color-scheme`, lựa chọn của người dùng nhớ trong
  `localStorage` (bọc try/catch).
- **Chữ:** IBM Plex Sans (giao diện) + IBM Plex Mono (số, id) từ Google Fonts, **luôn có font hệ thống dự phòng**
  (`system-ui, "Segoe UI", sans-serif` / `ui-monospace, Consolas, monospace`) để máy offline vẫn đọc được tiếng Việt.
- **Phong cách:** góc bo 6 px, nút / ô nhập cao 40 px, bảng gọn (chữ 13 px), **không emoji ở bất kỳ đâu**; icon chỉ là SVG
  nét mảnh một màu (`currentColor`) như trong bản vẽ. Logo: SVG inline trong thanh trên + `favicon.svg` (biểu tượng nền xanh
  ở `Brand.dc.html`).
- **Khả năng truy cập:** dùng `<button>`, `<a href>`, `<label>` thật; công tắc là `<button role="switch" aria-checked>`;
  nút chỉ có icon phải có `aria-label`; tương phản chữ ≥ 4.5:1.
- **Màn hẹp (< 900 px):** thanh trái xếp xuống dưới / thu gọn, bảng cuộn ngang trong khung, không cuộn ngang cả trang.
- Test: `pytest` + CI xanh (test API hiện có không được hỏng). Thêm một test `GET /` trả 200 và có chữ "PointSnap 3D".
- Kiểm bằng tay với CVAT local (dự án trỏ `http://localhost:8080`, job 2): chụp ảnh **từng màn ở cả sáng và tối** + một ảnh
  màn hẹp, đưa vào mô tả PR. Không gắn cờ lên CVAT khi chỉ để chụp ảnh.
- Branch `feat/A13-enterprise-ui` từ `main`, PR base `main`, reviewer `imvhuy`, **không merge** (đợi nhóm test xong).
  `TASKS.md`: thêm dòng A13 → 🔍 khi mở PR. Commit message tiếng Việt có dấu, không BOM.

### 0a-review. Claude review PR #28 (08/10, commit `72ce126`, `310f247`) — **ĐÃ SỬA XONG** (Claude, commit `dc855a6` + merge `ba9d8a4`), không làm lại

Ngoài 7 điểm dưới (điểm 6 là báo nhầm), Claude sửa thêm: theo dõi quét so `status === 'completed'` trong khi backend trả
`'done'` → nút kẹt "Đang quét…"; quét xong không vẽ màn Kết quả.

Đạt: `pytest` 186 passed, CI xanh; bố cục khớp bản vẽ (thanh trên navy, menu 2 nhóm, bảng chi tiết bên phải, Guideline
dạng cài đặt, Lịch sử có biểu đồ); sáng / tối chạy, nhớ lựa chọn; font có dự phòng; chạy thật với CVAT local job 2
(8 Lỗi, 35 Cảnh báo, không lỗi console); commit message có dấu.

**Phải sửa:**
1. **Thiếu logo động khi tải** (mục 0a, `Loading.dc.html`): không có `ps-box` / `ps-dot` / spinner nào trong code. Làm
   đúng yêu cầu: nút quét đang chạy (18 px trắng), kiểm tra kết nối / tải task (20 px), màn chờ (48 px), giảm chuyển động.
2. **`TASKS.md` mất dòng A10** (commit `310f247` thay dòng A10 bằng A11 / A13). Khôi phục dòng A10 nguyên văn từ `main`.
3. **Màn hẹp bị cuộn ngang cả trang:** ở 375 px, `section.findings-list-panel` rộng 698 px (`scrollWidth` 698 >
   `clientWidth` 375). Cho panel `min-width: 0` / flex-basis nhỏ hơn, chỉ bảng bên trong cuộn ngang.
4. **Bảng chi tiết hiện số thô:** "Giá trị đo" `0.26277867184127524`, "Ngưỡng" `0.22`, không đơn vị. Định dạng theo
   `rule`: `floating` → cm, làm tròn (`+26 cm`, ngưỡng `22 cm`); `track.jump` → m, 1 chữ số; `size.*` → m, 2 chữ số
   (hoặc %, theo `details`); `floating.no_evidence` → số điểm; không có giá trị thì ẩn ô.
5. **Dòng meta "· 0 track ·" sai** (job 2 có 219 track): `summary.json` không có số track → bỏ phần "track" khỏi dòng
   này (không đổi backend).
6. Hộp thoại xóa dự án thiếu chữ: "Hành động này sẽ ~~dự án~~ **xóa** dự án cùng toàn bộ…".
7. Còn ký tự `✕` (index.html) và `✓` (app.js): thay bằng SVG nét mảnh hoặc chữ ("Đóng"), theo yêu cầu không biểu tượng
   màu mè / emoji.

**Lưu ý merge:** PR #27 (A11b) và #28 cùng thêm test vào cuối `tests/test_web.py` (cả hai đặt tên "Test 14") nên sẽ xung
đột. Người dùng merge #27 trước; sau đó merge `main` vào `feat/A13-enterprise-ui` (không rebase, không force-push), giữ
cả hai test, đổi tên test A13 thành "Test 15". Link "Mở đúng box" trên giao diện chỉ có `serverID` sau khi #27 vào.

## 0. Đã xong: A11b — nút "Mở CVAT" trỏ thẳng tới box bị báo (PR #27, Claude đã review: đạt)

**Lỗi:** link "Mở CVAT" (giao diện web, báo cáo HTML, CSV) chỉ có dạng `/tasks/<t>/jobs/<j>?frame=<f>`: mở đúng frame
nhưng frame có ~85 box nên người xem không biết box nào bị báo.

**Cách sửa (Claude đã kiểm trong mã nguồn CVAT `D:\Work\cvat\cvat-ui\src\containers\annotation-page\annotation-page.tsx`,
dòng 83–91):** CVAT đọc thêm tham số `type` (`track` / `shape`) và `serverID`, rồi tự đặt bộ lọc chỉ hiện đúng đối
tượng đó — chính là link mà "Copy object URL" của CVAT tạo ra:
`/tasks/<t>/jobs/<j>?frame=<f>&type=track&serverID=<track_id>`.

- `adapters/cvat/reader.py` `frame_url(base_url, task_id, job_id, frame, track_id=None, shape_id=None)`: có `track_id`
  thì thêm `&type=track&serverID=<track_id>`; không có track mà có `shape_id` thì `&type=shape&serverID=<shape_id>`;
  không có gì thì giữ link cũ. **Box thuộc track phải dùng `track_id`**, không dùng `source_id` (đó là id keyframe, không
  phải id đối tượng). Job 2 hiện toàn là track (219 track, 0 shape lẻ).
- Sửa mọi chỗ tạo link dùng chung hàm này: `report/html.py:60`, `report/csv_rep.py:36`, `JobData.frame_url`, và
  `web/runner.py:35` (đang tự ghép chuỗi riêng → đổi sang gọi `frame_url`), truyền `finding.track_id` /
  `finding.source_id`.
- Test: `frame_url` cho 3 ca (track, shape lẻ, không có id); `finding_to_dict` của runner trả link có `serverID`.
- Tài liệu: `CONVENTIONS.md` (file CRLF, giữ CRLF) ghi dạng link mới. README (mục giao diện): link chỉ đúng với **lần quét
  mới nhất**, vì CVAT tạo lại id khi annotation được lưu / gắn cờ → sửa box xong thì quét lại rồi mới bấm link; và nên
  **đăng nhập CVAT trước**, vì trang đăng nhập của CVAT chuyển về job nhưng làm mất `?frame=…`.
- Kiểm trên CVAT local: quét job 2 trên giao diện, bấm "Mở CVAT" ở vài dòng → CVAT mở đúng frame và chỉ hiện đúng một box.
- Branch `fix/A11b-cvat-object-link` từ `main`, PR base `main`, reviewer `imvhuy`, không tự merge. Sửa này không đổi kết
  quả phát hiện nên người dùng có thể merge ngay cả khi nhóm đang test.

## 1. Việc được giao: A12 — giảm báo nhầm lơ lửng / lún, nâng phát hiện nhảy vị trí 4 m

Bối cảnh: theo góp ý của mentor (05/10), nhóm làm tốt **phát hiện + cảnh báo** cho 3 loại lỗi (lơ lửng / lún, kích
thước, đứt track) trước, rồi mới sang tự sửa. A12 là phần còn thiếu để đạt chỉ tiêu phát hiện. Trong lúc làm A12, nhóm
Khánh, Chiến, Hân đang **test bản trên `main`** (`giao-viec/test-va-gop-y.md`), nên `main` phải đứng yên.

### 1.1. Tiêu chí xong

Đo bằng `pointsnap eval --scenes test` (5 cảnh kiểm tra, 10 vòng chèn lỗi, seed mặc định):

| Chỉ số | Hiện tại (`main`) | Phải đạt |
|---|---|---|
| Báo nhầm trên nhãn chuẩn / 100 box | 3,80 Cảnh báo · 0,85 Lỗi | **≤ 2,0 · ≤ 0,5** |
| Nhảy vị trí 4 m (bắt được) | 88% (14/16) | **≥ 90%** |
| Kích thước theo class / tách ID / khoảng nội suy dài / phân mức đúng | 96% / 100% / 100% / 84% | Không giảm |
| Lơ lửng / lún 40 cm bắt được trên box có đủ điểm mặt đất | 100% (9/9) | Không giảm |
| Thời gian quét job scene-0061 (39 frame, 3 333 box) | ~3 giây | ≤ 30 giây |

Số liệu gốc chi tiết: `source-tool/pointsnap-3d/docs/ket-qua-danh-gia-tu-dong.md`.

**Chống học thuộc đề (bắt buộc):** mọi việc chọn tham số / ngưỡng chỉ dùng `--scenes tuning` (scene-0061, 0553, 0757,
0916, 1094). `--scenes test` chỉ chạy ở bước 5 để lấy số báo cáo. Nếu sau bước 5 thấy chưa đạt thì **không** chỉnh ngưỡng
theo cảnh kiểm tra; ghi số thật và báo lại.

### 1.2. Các bước

**Bước 0 — Chuẩn bị.** Branch `feat/A12-reduce-floating-false-alarms` từ `main` mới nhất (đã gồm A6, A2b, A10, A11,
CI). Chạy `pointsnap eval --scenes tuning` và `--scenes test`, lưu số liệu gốc (không commit thư mục `out/`).

**Bước 1 — Chẩn đoán trước khi sửa** (đầu ra: bảng ngắn, đưa vào mô tả PR):
- Tách báo nhầm `floating` trên nhãn sạch (cảnh tinh chỉnh) theo: class, khoảng cách box tới LiDAR, số điểm mặt đất
  (`num_ground_points`), số box có bằng chứng trong track, `|offset|` so với trung vị track. Báo nhầm tập trung ở đâu?
- Liệt kê các lỗi `track_jump` 4 m (và 2 m) bị bỏ sót trên cảnh tinh chỉnh: vị trí trong track (đầu / cuối / giữa), độ
  dài track, có gần khoảng vắng mặt không, class. Bước 4 sửa theo đúng chỗ này.

**Bước 2 — Thí nghiệm gộp sweeps LiDAR cho mặt đất.** Dữ liệu có sẵn: `D:\Vin_uni\data\nuscenes\sweeps\LIDAR_TOP` (3 531
file, ~9 sweep giữa hai keyframe). Gợi ý thiết kế (được chỉnh):
- `NuScenesReader.load_points(ref, sweeps=0)`: khi `sweeps = N > 0`, đọc thêm N sweep liền trước keyframe theo chuỗi
  `sample_data.prev` của `LIDAR_TOP`, đưa từng sweep về hệ LiDAR của keyframe bằng
  `inv(sensor_to_world_keyframe) @ sensor_to_world_sweep` (`_sensor_to_world` đã có). Mặc định 0 → hành vi cũ.
- Đưa tham số xuống `frame_data` của `NuScenesReader`, `NuScenesFrames`, `ManifestFrames` (giữ `transform` của manifest)
  và cập nhật `FrameSource` trong `core/model.py`. Chỉ `estimate_scene_ground` (luật lơ lửng / lún) xin sweeps; luật đứt
  track và chỗ khác giữ keyframe.
- Cấu hình mới `floating.sweeps` (số nguyên ≥ 0) trong `config.yaml` + `FloatingConfig` + `_parse_floating`, **giá trị
  mặc định 0** cho tới khi thí nghiệm chứng minh có lợi; trường mới phải có default để không phá guideline cũ của các dự
  án trên giao diện web (A11) và test cũ.
- So N = 0, 2, 4, 8 trên cảnh tinh chỉnh: % box có bằng chứng (hiện ~1/4), p90 `|d − trung vị track|` trên nhãn sạch
  (hiện 14,7 cm), báo nhầm / 100 box, recall lơ lửng / lún, thời gian. Ghi bảng vào `docs/kiem-chung-ground.md`.
- **Quyết định:** chỉ đặt mặc định N > 0 nếu báo nhầm giảm và % box có bằng chứng tăng mà recall không giảm.
- Rủi ro phải đo, không chỉ đoán:
  - `ego_pose` của nuScenes luôn có z = 0 → gộp sweep khi xe lên / xuống dốc có thể lệch độ cao mặt đất. Giữ cửa sổ ngắn
    (≤ 0,5 s) và kiểm riêng độ lệch.
  - Vật đang chạy để lại vệt điểm trong sweep cũ, có thể bị coi là đất. `OtherBoxPoints` chỉ bỏ điểm trong box của
    keyframe; kiểm báo nhầm theo class sau khi gộp.

**Bước 3 — Chỉnh luật (chỉ khi bước 2 chưa đủ),** theo kết quả bước 1. Ví dụ: ngưỡng nới theo độ tin cậy phép đo (ít
điểm / độ phân tán điểm mặt đất lớn → ngưỡng lớn hơn), bỏ qua box quá xa, không so trung vị khi track quá ít box có bằng
chứng. Tham số mới vào `FloatingConfig` có default, chỉnh trên cảnh tinh chỉnh.

**Bước 4 — Nhảy vị trí 4 m** (`detectors/track.py`): sửa đúng chỗ bước 1 chỉ ra (nghi ở hai đầu track, hệ số ngoại suy
×1,5). Không được làm tăng báo nhầm `track.jump` (hiện 0,24 Cảnh báo · 0,11 Lỗi / 100 box trên cảnh kiểm tra) và không
giảm nhảy 2 m (92%) / tách ID.

**Bước 5 — Đánh giá cuối, test, tài liệu:**
- Chạy `pointsnap eval --scenes test` một lần; cập nhật `docs/ket-qua-danh-gia-tu-dong.md` (thêm cột "Sau A12" vào bảng
  so sánh, giữ số cũ) và `docs/kiem-chung-ground.md`.
- Test có đáp án trong `tests/` (ví dụ `tests/test_detectors_a12.py`): gộp sweep với point cloud giả có pose dịch chuyển
  → điểm về đúng hệ keyframe; `sweeps = 0` giữ nguyên kết quả cũ; ca nhảy 4 m bị bỏ sót trước đây giờ bắt được.
- `pytest` xanh trên máy và **CI GitHub Actions xanh** (`.github/workflows/test.yml`; test cần dữ liệu thật phải tự bỏ
  qua khi không có `NUSCENES_ROOT`).
- Chạy thử `pointsnap ui` hoặc `pointsnap scan --job 2` với CVAT local: số Lỗi / Cảnh báo trên job scene-0061 so với
  hiện tại (8 Lỗi, 35 Cảnh báo), thời gian quét.
- `TASKS.md`: thêm dòng A12 (người làm Khúc Việt Anh, hạn theo PR) → 🔍 khi mở PR. `CONVENTIONS.md` nếu đổi quy ước.

**Bước 6 — PR:** base `main`, reviewer `imvhuy`, mô tả tiếng Việt gồm bảng chẩn đoán (bước 1), bảng thí nghiệm sweeps
(bước 2), bảng trước / sau trên cảnh kiểm tra. **Không merge** (người dùng / Huy merge sau khi nhóm test xong).

### 1.3. Không làm trong A12

Tự sửa / đề xuất sửa (giai đoạn 2), giao diện web, bộ phát hiện kích thước, các lỗi từ đợt test (đang chờ bảng tổng
hợp `docs/test/tong-hop-loi.md`).

## 2. Trạng thái repo (08/10)

- Repo `D:\Vin_uni\P-029\P-029` (GitHub `AI20K-Build-Phase-Cohort-4A/P-029`), tool ở `source-tool/pointsnap-3d/`. Bản
  checkout đang ở `main` mới nhất.
- `gh` đã đăng nhập (tài khoản `BanhKhuc04`). Nếu không thấy lệnh: thêm `C:\Program Files\GitHub CLI` vào `PATH`.
- Đã merge vào `main`: #18 (A6 nối detectors), #19 (A2b ảnh camera), #21 (A10 giảm báo nhầm, `pointsnap eval`), #23 (A11
  giao diện web), #20/#24/#25 (giao việc test), #22 (nhật ký tuần 04), #26 (CI chạy `pytest` mọi PR).
- `pytest` trên `main`: 185 passed, 3 skipped.
- Bộ phát hiện (`pointsnap/detectors/`) là phần của **Huy**; người dùng báo Huy rằng A12 sửa `floating.py`, `track.py`,
  `core/ground.py`, `adapters/nuscenes/reader.py`.

## 3. Quy tắc bắt buộc

- **Không bao giờ push thẳng lên `main`**, kể cả tài liệu. Branch riêng → PR → reviewer `imvhuy`. Không tự merge.
- Trả lời người dùng bằng **tiếng Việt**. Commit message có dấu, không có BOM.
- **Không in, không commit token** (`CVAT_TOKEN` trong `source-tool/pointsnap-3d/.env`, gitignored). Không commit `out/`,
  `.pcd`, dữ liệu nuScenes.
- Line ending **LF** cho file mới / file sửa. Riêng `CONVENTIONS.md`, `adapters/cvat/writer.py`,
  `tests/test_cvat_writer.py`, `tests/test_live_cvat.py` đang CRLF: nếu sửa thì giữ CRLF. Kiểm bằng `git ls-files --eol`.
- Commit message kết thúc bằng dòng `Co-Authored-By:` của agent đang làm.
- Không chạy lệnh ghi vào CVAT (`--flag`, gắn cờ trên giao diện) khi không cần; không xóa task CVAT. Nhóm test đang dùng
  CVAT của máy họ, không phải máy này.

## 4. Môi trường trên máy

- Python 3.11, venv `source-tool/pointsnap-3d/.venv`. Test: `.venv\Scripts\python -m pytest -q`.
- Đánh giá: trong `source-tool/pointsnap-3d`, `.venv\Scripts\pointsnap eval --scenes tuning` (hoặc `test`); tùy chọn
  `--rounds`, `--seed`, `--out` (mặc định `out/eval`). `.env` đã có `NUSCENES_ROOT`.
- Dữ liệu nuScenes mini: `D:\Vin_uni\data\nuscenes\` (`samples`, `sweeps`, `maps`, `v1.0-mini`).
- CVAT 2.77.0 Docker local (`D:\Work\cvat`, `CVAT_VERSION=v2.77.0`, `docker compose up -d`), http://localhost:8080.
  Task 2 / job 2 = scene-0061 kèm ảnh camera; bản xuất `D:\Vin_uni\data\cvat\scene-0061\`.
- PowerShell 5.1: không có `&&`; ghi file UTF-8 không BOM + LF bằng
  `[IO.File]::WriteAllText(path, text, (New-Object Text.UTF8Encoding($false)))`.

## 5. Khi xong

Báo người dùng: link PR, bảng trước / sau trên cảnh kiểm tra, chỉ tiêu nào đạt / chưa đạt, `floating.sweeps` mặc định
cuối cùng là bao nhiêu và vì sao, những gì chưa làm. Claude sẽ review (đọc code, chạy `pytest`, chạy lại `eval`).

## Lưu: A11 đã xong

Giao diện web + guideline theo dự án: PR #23 đã merge ngày 08/10 (sau 2 vòng review: 5 điểm kế hoạch + CORS, xóa class
trong guideline, kiểm `run_id`). Còn để lại: xóa class khỏi `size.class_range.stats` qua tab YAML vẫn bị mặc định điền
lại (form không sửa mục này) — chưa cần sửa.
