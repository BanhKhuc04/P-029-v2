# PointSnap 3D

**Giải quyết:** [P-010](../problem-backlog.md#p-010) — khó căn đáy cuboid sát mặt đất, box lơ lửng / lún · [P-011](../problem-backlog.md#p-011) — lỗi 3D chỉ phát hiện ở khâu review thủ công, gây rework lớn · [P-012](../problem-backlog.md#p-012) — duyệt tuần tự các box có cờ và ghi kết luận qua Web/extension.

> **Trạng thái đối chiếu ngày 11/10/2026:** mã nguồn CLI, Web, extension và luật giai đoạn 3 đã có. Kết quả G2 trong nhật ký là bằng chứng lịch sử trên CVAT local; chưa đủ để kết luận toàn bộ sản phẩm đã nghiệm thu. `diff` chưa triển khai; test mock không chứng nhận CVAT thật hoặc thao tác trình duyệt. Xem [review phần 01](../review/2026-10-10/01-report.md), [bản đề xuất](pointsnap-3d/de-xuat-de-tai.md) và [bảng phân việc](pointsnap-3d/TASKS.md).

## Pain point

Gán nhãn 3D cuboid trên CVAT, thời gian bị mất nhiều nhất không phải lúc vẽ box mà ở vòng **nộp → bị trả về → sửa → nộp lại**. Số liệu dưới đây là quan sát nội bộ của đội:

- **Lơ lửng / lún đất:** CVAT không có mặt đất tham chiếu, annotator phải xoay và zoom camera để căn đáy box bằng mắt. Chỉnh trục Z chiếm **~35–40% thời gian** chỉnh một box; lỗi này chiếm **~30% ca bị trả về**.
  Ví dụ: [Job #4019, frame 12](https://cvat.note.transformerlabs.ai/jobs/4019?frame=12) (đường dốc nhẹ, box lơ lửng hoặc lún), [Job #4021, frame 45](https://cvat.note.transformerlabs.ai/jobs/4021?frame=45) (xe đỗ ở mép đường nghiêng).
- **Sai kích thước:** box quá to hoặc quá nhỏ so với loại xe, hoặc cùng một xe mà mỗi frame một kích thước. Reviewer phải so bằng mắt qua nhiều frame.
- **Đứt track:** track nhảy vị trí, hoặc một đối tượng bị tách thành hai ID.
  Ví dụ: [Job #4020, frame 25](https://cvat.note.transformerlabs.ai/jobs/4020?frame=25) (ID 12 mất ở frame 25, xuất hiện lại thành ID 18 ở frame 26).

Reviewer mất **3–5 phút mỗi frame** để soi thủ công; rework chiếm **25–35% thời lượng** của đội.

## Tool làm gì

PointSnap 3D đọc job 3D cuboid qua REST API của CVAT, tìm 3 loại lỗi trên (giai đoạn 3 thêm sai hướng box, box lệch khỏi vật và các điều khoản track / thuộc tính của spec gán nhãn) và chỉ ra box nào sai, ở frame nào, sai bao nhiêu. Lỗi được báo ra file HTML/CSV và **gắn cờ thẳng lên box trong CVAT** (thuộc tính `pointsnap_error`) để annotator lọc ra sửa trước khi nộp. Lệnh `gate` trả ĐẠT / KHÔNG ĐẠT để làm cổng kiểm tra cuối.

| Lỗi | Tool đo gì | Cảnh báo / Lỗi (mặc định) |
|---|---|---|
| Lơ lửng / lún | Khoảng cách đáy box tới mặt đất ước lượng cục bộ quanh box | > 10 cm / > 20 cm |
| Sai kích thước | l, w, h so với khoảng thường gặp của class; độ lệch so với trung vị của track | Theo class; > max(10 cm, 5%) / > max(30 cm, 15%) |
| Đứt track | Tâm box lệch khỏi vị trí nội suy từ hai frame bên cạnh; track kết thúc rồi track cùng class bắt đầu ngay gần đó; đoạn dài chỉ có box nội suy; dùng lại track sau `outside`, `occluded` quá 6 frame (spec 4.4) | Xe: 1 m / 2 m; tách ID, luật spec chỉ Cảnh báo |
| Sai hướng box (giai đoạn 3) | Hướng box đổi đột ngột giữa hai keyframe; lệch / ngược hướng chuyển động; trục box lệch trục cụm điểm LiDAR (spec 4.2) | Lật / xoay > 45° / > 75°; ngược chiều > 60° / > 135° |
| Box lệch khỏi vật (giai đoạn 3) | Box rỗng; điểm của vật nằm ngoài box; mặt box nhìn thấy cách xa vật; hai box chồng nhau (spec 4.2) | > 50% điểm ngoài box / > 70%; chồng > 20% / > 50% |
| Thiếu / sai thuộc tính (giai đoạn 3) | Thuộc tính bắt buộc theo class, giá trị cho phép (spec 3.1.3), theo guideline của dự án | Lỗi |

Ngưỡng nằm trong `config.yaml` và sẽ chốt lại trên dữ liệu. Chi tiết từng luật: [mục 4.1 của bản đề xuất](pointsnap-3d/de-xuat-de-tai.md#41--ba-bộ-phát-hiện).

Tool **chỉ ghi thuộc tính cờ lỗi**: không đổi vị trí, kích thước, class của box nào và không tự tạo box mới.

## Cài đặt và chạy

> **Cài từ máy trắng (CVAT, dữ liệu nuScenes, PointSnap, extension), từng bước có kiểm tra: xem [CAI-DAT.md](CAI-DAT.md).** Phần dưới đây là tóm tắt.

**Chuẩn bị trên CVAT:** thêm vào label spec thuộc tính văn bản `pointsnap_error` và checkbox `reviewed`. Tạo access token trong CVAT.

```bash
# 1. Khởi tạo môi trường ảo và cài đặt package
cd source-tool/pointsnap-3d
python -m venv .venv

# Kích hoạt môi trường:
# Trên Windows (cmd / PowerShell):
.venv\Scripts\activate
# Trên Linux / macOS:
source .venv/bin/activate

# Cài đặt dạng editable:
pip install -e .
```

### 1. Chạy giao diện Web (Khuyến nghị)

Giao diện Web trực quan (FastAPI + HTML/JS thuần) thay thế hoàn toàn dòng lệnh: tạo dự án, tùy biến guideline riêng, kết nối CVAT, quét nền, xem lỗi trực quan kèm link mở frame CVAT, gắn cờ và theo dõi lịch sử lỗi giảm dần.

```bash
pointsnap ui
```
*Mặc định máy chủ lắng nghe tại `http://127.0.0.1:8765` và tự động mở trình duyệt. Có thể tùy chỉnh `--host 0.0.0.0`, `--port 8765`, hoặc `--no-browser`.*

*Lưu ý khi bấm link "Mở CVAT":*
- Link trỏ thẳng tới đúng đối tượng bị báo (`&type=track&serverID=<id>`), chỉ đúng với **lần quét mới nhất** (do CVAT tạo lại id khi annotation được lưu hoặc gắn cờ). Sau khi sửa box xong, hãy quét lại rồi mới bấm link.
- Nên **đăng nhập CVAT trước** trên trình duyệt, vì trang đăng nhập của CVAT khi chuyển hướng về job sẽ làm mất tham số `?frame=…`.

*Duyệt nhiều lỗi mà không mở lại CVAT:*
- **Kiểm tra đúng / báo nhầm ngay trên PointSnap:** ở màn Kết quả, khung **Duyệt nhanh** hiện point cloud quanh box (nhìn từ trên và nhìn ngang, mặt đất ở dưới). Phím `J` / `K` chuyển mục sau / trước, `1` = đúng là lỗi, `2` = báo nhầm. Kết luận lưu vào `reviews.json` của lần quét và tính luôn precision xem tay.
- **Sửa hàng loạt trong CVAT bằng extension (khuyên dùng):** cài [extension PointSnap cho CVAT](pointsnap-3d/extension/README.md) (Chrome / Edge, Load unpacked, khoảng 1 phút). Mở job là extension tự lọc box có cờ; phím `.` / `,` chuyển tới frame có lỗi kế tiếp / trước, không tải lại trang; rê chuột vào box thấy nội dung lỗi và gợi ý sửa. Kết quả thử: [docs/thu-extension.md](pointsnap-3d/docs/thu-extension.md).
- **Sửa hàng loạt trong CVAT không cần extension (chỉ tải job một lần):** bấm **Gắn cờ lên CVAT**, mở job trên CVAT, đặt bộ lọc `pointsnap_error` *is not empty*, rồi **bấm chuột phải** vào nút Trước hoặc Sau trên thanh điều khiển frame và chọn kiểu nhảy **theo bộ lọc**. Mỗi lần bấm Sau, CVAT nhảy tới frame kế tiếp có box bị gắn cờ; nội dung lỗi nằm trong thuộc tính `pointsnap_error` của box.

### 2. Dùng dòng lệnh (Nâng cao cho CI/CD và Script)

Cấu hình biến môi trường qua file `.env` trong thư mục `source-tool/pointsnap-3d/` (hoặc biến môi trường hệ thống):
- `CVAT_URL=http://localhost:8080`
- `CVAT_TOKEN=<personal_access_token>`
- `NUSCENES_ROOT=D:/Vin_uni/data/nuscenes`
- `POINTSNAP_EXPORT_DIR=D:/Vin_uni/data/cvat`   # nơi có bản xuất to-cvat (manifest.json)

```bash
# Quét job và xuất báo cáo HTML/CSV (mặc định lưu vào thư mục out/)
pointsnap scan --job 12

# Quét và gắn cờ lỗi 'pointsnap_error' trực tiếp lên canvas 3D CVAT
pointsnap scan --job 12 --flag

# Cổng kiểm soát chất lượng trước khi nộp (Exit code 0: ĐẠT, 1: KHÔNG ĐẠT)
pointsnap gate --job 12
```

`scan` / `gate` đọc point cloud từ thư mục nuScenes theo `manifest.json` của bản xuất `nuscenes to-cvat` (tự tìm theo id task trong `POINTSNAP_EXPORT_DIR` và `data/cvat`, hoặc chỉ thẳng bằng `--manifest`). Không tìm được thì tool in cảnh báo, bỏ luật lơ lửng / lún và các luật heading/fit dùng LiDAR; `fit.overlap` vẫn chạy. Luật chuyển động thiếu pose dùng tọa độ từng frame, nên kết quả kém chắc. `--flag` chỉ gắn cờ mục Lỗi / Cảnh báo.

**Ý nghĩa gate:** chỉ ĐẠT khi không vượt ngưỡng của các luật đang bật và không có thiếu dữ liệu đã được kiểm tra. Thiếu point cloud cho luật đang bật trên box nhìn thấy, thiếu pose cho luật track/hướng trên box thuộc track, hoặc có `floating.no_evidence` thì KHÔNG ĐẠT (mã 1), kèm lý do kiểm tra một phần. Lỗi đọc frame khi quét `gate` trả mã 3. Luật được chủ động tắt không yêu cầu dữ liệu; ĐẠT không chứng nhận những luật đó, đối tượng bị sót hoặc độ đúng tuyệt đối của nhãn.

**Chạy thử không cần CVAT** (đọc thẳng nuScenes, cùng 3 bộ phát hiện):

```bash
# Chèn lỗi giả vào 30% số track rồi quét; in lỗi chèn nào có / không có finding đúng loại
pointsnap nuscenes scan --scene scene-0103 --inject --rate 0.3 --out out/demo
```

Trên Windows PowerShell, có thể đặt biến môi trường tạm thời bằng `$env:CVAT_URL = "http://localhost:8080"` và `$env:CVAT_TOKEN = "..."`. Hoặc sử dụng file `.env` được tool tự động nạp.

**Quy trình dùng hằng ngày:**

```
Gán nhãn xong
  → pointsnap scan --job <id> --flag
  → Mở CVAT, tải lại trang (F5), lọc box theo pointsnap_error, sửa theo chỉ dẫn
  → pointsnap scan lại → pointsnap gate --job <id>
  → ĐẠT theo các luật đang bật + reviewer xác nhận phần tool không kiểm → nộp
```

## Đầu vào / đầu ra

- **Vào:** annotation cuboid (track và shape lẻ) đọc qua REST API CVAT, không cần export nhãn. Các luật LiDAR cần point cloud nuScenes cục bộ và manifest khớp thứ tự frame; hiện chưa tải point cloud từ API CVAT. Ngưỡng lấy từ `config.yaml`.
- **Ra:**
  - Báo cáo **HTML**: chia mức Lỗi / Cảnh báo / Thông tin, nhóm theo track, mỗi dòng có số đo cụ thể và link mở thẳng frame trên CVAT.
  - File **CSV** cùng nội dung để thống kê.
  - **Bản chụp nhãn** (JSON) lưu mỗi lần quét, dùng để so sánh trước / sau và khôi phục nếu cần.
  - Với `--flag`: thuộc tính `pointsnap_error` trên box lỗi, ví dụ *"LỖI: lơ lửng 22 cm"*. Cờ tự xóa khi box hết lỗi ở lần quét sau.
- **Đưa lại vào CVAT:** không cần import. Cờ lỗi được ghi thẳng qua API; chỉ cần tải lại trang.

## Đã thử trên

Các tài liệu lịch sử ghi kiểm thử trên **nuScenes v1.0-mini** (10 cảnh, ~400 frame có nhãn): 5 cảnh chỉnh ngưỡng, 5 cảnh báo cáo. Bảng dưới thuộc báo cáo cũ [`docs/danh-gia.md`](pointsnap-3d/docs/danh-gia.md), thiếu commit/config hash/seed nên không coi là đo lại trên phiên bản hiện hành.

Snapshot giai đoạn 3 ngày 10/10/2026: **3,42 Cảnh báo và 0,55 Lỗi / 100 box** trên 5 cảnh kiểm tra (5 440 box), vẫn vượt mục tiêu ≤ 2 và ≤ 0,5. Xem [kết quả giai đoạn 3](pointsnap-3d/docs/ket-qua-giai-doan-3.md). Đây là đánh giá tự động; precision xem tay và metadata tái lập còn phải xác minh ở phần 07.

| Chỉ số | Mục tiêu | Kết quả |
|---|---|---|
| Recall trên lỗi chèn giả (lơ lửng ≥ 20 cm, kích thước ≥ 15%) | ≥ 90% | **92.0%** (floating error) / 90.7% (error chung) |
| Precision mỗi loại lỗi | ≥ 70% | 17.6% (floating) / 13.5% (size)* |
| Báo động giả trên nhãn chuẩn | ≤ 2 Cảnh báo / 100 box | Có cảnh báo cho các lỗi thật có sẵn trên nhãn nuScenes |
| Sai số ước lượng mặt đất (~200 box chuẩn) | Trung vị < 5 cm | **8.2 cm** (P90: 33.5 cm) |
| Thời gian chạy `scan` | < 2 phút / cảnh | **~2 giây / cảnh** (< 0.1s / frame) |

## Giới hạn

Những chỗ tool **không** kiểm, annotator và reviewer vẫn phải tự soi:

- Sót đối tượng (vật có điểm mà chưa gán box) **chưa được kiểm**: cần mô hình phát hiện 3D, để hướng phát triển.
- Luật box lệch chỉ bắt được box lệch rõ (box có từ 30 điểm của vật trở lên); lệch nhỏ vẫn do luật nhảy vị trí / kích thước trong track bắt.
- Box `occluded` (vật bị che) không được kiểm hình học; chỉ kiểm thời gian che theo spec.
- Tool chỉ cảnh báo, **không tự sửa**.
- Mặt đất ước lượng kém ở đoạn dốc, bờ vỉa, chỗ bị che hoặc ở xa (LiDAR thưa). Những box này được ghi "thiếu bằng chứng" ở mức Thông tin, cần tự kiểm.
- Tách ID và khoảng nội suy dài chỉ ở mức Cảnh báo. Đối tượng bị che lâu hoặc ra khỏi tầm cảm biến có thể bị báo nhầm.
- Ngưỡng được thống kê trên nuScenes; dùng với dữ liệu khác cần thống kê lại. Bộ class theo spec giao thông VN có guideline mẫu [`spec-vn.yaml`](pointsnap-3d/pointsnap/guidelines/spec-vn.yaml), một số khoảng kích thước (van, xe ba gác, động vật…) là ước lượng vì chưa có dữ liệu Việt Nam.
- Mới thử trên CVAT local, chưa chạy trên CVAT của BTC.
- CVAT không khóa job khi có người mở: chỉ chạy `--flag` khi không ai đang mở job đó.

## Người viết

| Người | Vai trò | Phụ trách |
|---|---|---|
| @Khúc Việt Anh | Sản phẩm | Môi trường, chuyển nuScenes → CVAT, adapter CVAT, CLI, `scan --flag`, `gate`, báo cáo HTML/CSV, bộ chèn lỗi giả |
| @Đặng Văn Huy | Sản phẩm | Ước lượng mặt đất, 3 bộ phát hiện, đánh giá precision / recall |
| @Vũ Bảo Khánh | Báo cáo | Báo cáo kết quả, slide |
| @Nhữ Đình Chiến | Test | Test quy trình trên CVAT theo README, video demo |
| @Nguyễn Văn Hân | Test | Xem tay cảnh báo, bảng chỉ số đánh giá |

Phân công chi tiết theo ngày: [giao việc theo ngày](pointsnap-3d/giao-viec/) · [mục 7 của bản đề xuất](pointsnap-3d/de-xuat-de-tai.md#7-kế-hoạch-triển-khai-4-ngày-có-cổng-kiểm-soát).
