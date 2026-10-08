# PointSnap 3D

**Giải quyết:** [P-010](../problem-backlog.md#p-010) — khó căn đáy cuboid sát mặt đất, box lơ lửng / lún · [P-011](../problem-backlog.md#p-011) — lỗi 3D chỉ phát hiện ở khâu review thủ công, gây rework lớn

> **Trạng thái:** ✅ Đã hoàn thành trọn bộ sản phẩm và tích hợp end-to-end (G2). Xem [bản đề xuất](pointsnap-3d/de-xuat-de-tai.md), [bảng phân việc](pointsnap-3d/TASKS.md) và [giao việc theo ngày](pointsnap-3d/giao-viec/).

## Pain point

Gán nhãn 3D cuboid trên CVAT, thời gian bị mất nhiều nhất không phải lúc vẽ box mà ở vòng **nộp → bị trả về → sửa → nộp lại**. Số liệu dưới đây là quan sát nội bộ của đội:

- **Lơ lửng / lún đất:** CVAT không có mặt đất tham chiếu, annotator phải xoay và zoom camera để căn đáy box bằng mắt. Chỉnh trục Z chiếm **~35–40% thời gian** chỉnh một box; lỗi này chiếm **~30% ca bị trả về**.
  Ví dụ: [Job #4019, frame 12](https://cvat.note.transformerlabs.ai/jobs/4019?frame=12) (đường dốc nhẹ, box lơ lửng hoặc lún), [Job #4021, frame 45](https://cvat.note.transformerlabs.ai/jobs/4021?frame=45) (xe đỗ ở mép đường nghiêng).
- **Sai kích thước:** box quá to hoặc quá nhỏ so với loại xe, hoặc cùng một xe mà mỗi frame một kích thước. Reviewer phải so bằng mắt qua nhiều frame.
- **Đứt track:** track nhảy vị trí, hoặc một đối tượng bị tách thành hai ID.
  Ví dụ: [Job #4020, frame 25](https://cvat.note.transformerlabs.ai/jobs/4020?frame=25) (ID 12 mất ở frame 25, xuất hiện lại thành ID 18 ở frame 26).

Reviewer mất **3–5 phút mỗi frame** để soi thủ công; rework chiếm **25–35% thời lượng** của đội.

## Tool làm gì

PointSnap 3D đọc job 3D cuboid qua REST API của CVAT, tìm 3 loại lỗi trên và chỉ ra box nào sai, ở frame nào, sai bao nhiêu. Lỗi được báo ra file HTML/CSV và **gắn cờ thẳng lên box trong CVAT** (thuộc tính `pointsnap_error`) để annotator lọc ra sửa trước khi nộp. Lệnh `gate` trả ĐẠT / KHÔNG ĐẠT để làm cổng kiểm tra cuối.

| Lỗi | Tool đo gì | Cảnh báo / Lỗi (mặc định) |
|---|---|---|
| Lơ lửng / lún | Khoảng cách đáy box tới mặt đất ước lượng cục bộ quanh box | > 10 cm / > 20 cm |
| Sai kích thước | l, w, h so với khoảng thường gặp của class; độ lệch so với trung vị của track | Theo class; > max(10 cm, 5%) / > max(30 cm, 15%) |
| Đứt track | Tâm box lệch khỏi vị trí nội suy từ hai frame bên cạnh; track kết thúc rồi track cùng class bắt đầu ngay gần đó; đoạn dài chỉ có box nội suy (ngoài phạm vi 4 ngày) | Xe: 1 m / 2 m; tách ID chỉ Cảnh báo |

Ngưỡng nằm trong `config.yaml` và sẽ chốt lại trên dữ liệu. Chi tiết từng luật: [mục 4.1 của bản đề xuất](pointsnap-3d/de-xuat-de-tai.md#41--ba-bộ-phát-hiện).

Tool **chỉ ghi thuộc tính cờ lỗi**: không đổi vị trí, kích thước, class của box nào và không tự tạo box mới.

## Cài đặt và chạy

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

`scan` / `gate` đọc point cloud từ thư mục nuScenes theo `manifest.json` của bản xuất `nuscenes to-cvat` (tự tìm theo id task trong `POINTSNAP_EXPORT_DIR` và `data/cvat`, hoặc chỉ thẳng bằng `--manifest`). Không tìm được thì tool in cảnh báo, bỏ luật lơ lửng / lún và luật đứt track dùng tọa độ của từng frame. `--flag` chỉ gắn cờ mục Lỗi / Cảnh báo.

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
  → ĐẠT thì nộp
```

## Đầu vào / đầu ra

- **Vào:** job 3D cuboid trên CVAT (point cloud + nhãn dạng track), đọc trực tiếp qua REST API, **không cần export file**. Ngưỡng lấy từ `config.yaml`.
- **Ra:**
  - Báo cáo **HTML**: chia mức Lỗi / Cảnh báo / Thông tin, nhóm theo track, mỗi dòng có số đo cụ thể và link mở thẳng frame trên CVAT.
  - File **CSV** cùng nội dung để thống kê.
  - **Bản chụp nhãn** (JSON) lưu mỗi lần quét, dùng để so sánh trước / sau và khôi phục nếu cần.
  - Với `--flag`: thuộc tính `pointsnap_error` trên box lỗi, ví dụ *"LỖI: lơ lửng 22 cm"*. Cờ tự xóa khi box hết lỗi ở lần quét sau.
- **Đưa lại vào CVAT:** không cần import. Cờ lỗi được ghi thẳng qua API; chỉ cần tải lại trang.

## Đã thử trên

Đã kiểm thử trên **nuScenes v1.0-mini** (10 cảnh, ~400 frame có nhãn): 5 cảnh để chỉnh ngưỡng, 5 cảnh để báo cáo kết quả. Chi tiết xem [`docs/danh-gia.md`](pointsnap-3d/docs/danh-gia.md).

| Chỉ số | Mục tiêu | Kết quả |
|---|---|---|
| Recall trên lỗi chèn giả (lơ lửng ≥ 20 cm, kích thước ≥ 15%) | ≥ 90% | **92.0%** (floating error) / 90.7% (error chung) |
| Precision mỗi loại lỗi | ≥ 70% | 17.6% (floating) / 13.5% (size)* |
| Báo động giả trên nhãn chuẩn | ≤ 2 Cảnh báo / 100 box | Có cảnh báo cho các lỗi thật có sẵn trên nhãn nuScenes |
| Sai số ước lượng mặt đất (~200 box chuẩn) | Trung vị < 5 cm | **8.2 cm** (P90: 33.5 cm) |
| Thời gian chạy `scan` | < 2 phút / cảnh | **~2 giây / cảnh** (< 0.1s / frame) |

## Giới hạn

Những chỗ tool **không** kiểm, annotator và reviewer vẫn phải tự soi:

- Chỉ có 3 loại lỗi trên. Ngược yaw 180°, box rỗng điểm, box chồng lấn, thiếu thuộc tính bắt buộc và sót đối tượng **chưa được kiểm**.
- Tool chỉ cảnh báo, **không tự sửa**.
- Mặt đất ước lượng kém ở đoạn dốc, bờ vỉa, chỗ bị che hoặc ở xa (LiDAR thưa). Những box này được ghi "thiếu bằng chứng" ở mức Thông tin, cần tự kiểm.
- Tách ID và khoảng nội suy dài chỉ ở mức Cảnh báo. Đối tượng bị che lâu hoặc ra khỏi tầm cảm biến có thể bị báo nhầm.
- Ngưỡng được thống kê trên nuScenes; dùng với dữ liệu khác cần thống kê lại.
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
