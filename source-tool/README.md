# PointSnap 3D

**Giải quyết:** [P-010](../problem-backlog.md#p-010) — khó căn đáy cuboid sát mặt đất, box lơ lửng / lún · [P-011](../problem-backlog.md#p-011) — lỗi 3D chỉ phát hiện ở khâu review thủ công, gây rework lớn

> **Trạng thái (06/10):** code G2 xong: 3 bộ phát hiện, `scan --flag`, `gate`, bộ chèn lỗi giả và `pointsnap eval` chạy trên cả 10 cảnh nuScenes mini (đang chờ review). Còn phải chạy lại trọn quy trình trên CVAT thật. Xem [bản đề xuất](pointsnap-3d/de-xuat-de-tai.md), [bảng phân việc](pointsnap-3d/TASKS.md) và [giao việc theo ngày](pointsnap-3d/giao-viec/).

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
| Lơ lửng / lún | Khoảng cách đáy box tới mặt đất sát box, so với các frame khác của cùng track ([vì sao](pointsnap-3d/docs/kiem-chung-ground.md)) | Lệch > 12 cm / > 22 cm; box lẻ: > 15 cm / > 30 cm |
| Sai kích thước | l, w, h (trung vị của track) so với khoảng thường gặp của class; từng keyframe so với trung vị của track | Ngoài khoảng ±10% / ±25%; > max(10 cm, 5%) / > max(30 cm, 15%) |
| Đứt track | Tâm box lệch khỏi vị trí nội suy (đầu / cuối đoạn: ngoại suy); track kết thúc rồi track cùng class bắt đầu ngay gần đó; ≥ 2 frame liền chỉ có box nội suy khi đối tượng đang chạy | Xe: 1 m / 2 m; tách ID, khoảng nội suy chỉ Cảnh báo |

Ngưỡng nằm trong `config.yaml`, đã chốt trên 5 cảnh tinh chỉnh (việc B7). Chi tiết từng luật: [mục 4.1 của bản đề xuất](pointsnap-3d/de-xuat-de-tai.md#41--ba-bộ-phát-hiện).

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

# 2. Cấu hình biến môi trường
# Tạo file .env trong thư mục source-tool/pointsnap-3d/ (hoặc export biến môi trường):
# CVAT_URL=http://localhost:8080
# CVAT_TOKEN=<personal_access_token>
# NUSCENES_ROOT=D:/Vin_uni/data/nuscenes
# POINTSNAP_EXPORT_DIR=D:/Vin_uni/data/cvat   # nơi có bản xuất to-cvat (manifest.json): để scan đọc được point cloud

# 3. Quét job và xuất báo cáo HTML/CSV (mặc định lưu vào thư mục out/)
pointsnap scan --job 12

# 4. Quét và gắn cờ lỗi 'pointsnap_error' trực tiếp lên canvas 3D CVAT
pointsnap scan --job 12 --flag

# 5. Cổng kiểm soát chất lượng trước khi nộp (Exit code 0: ĐẠT, 1: KHÔNG ĐẠT)
pointsnap gate --job 12
```

`scan` / `gate` đọc point cloud từ thư mục nuScenes theo `manifest.json` của bản xuất `nuscenes to-cvat` (tự tìm theo id task trong `POINTSNAP_EXPORT_DIR`, hoặc chỉ thẳng bằng `--manifest`). Không có point cloud thì luật lơ lửng / lún bị bỏ qua và tool in cảnh báo.

**Chạy thử không cần CVAT** (đọc thẳng nuScenes):

```bash
# Quét nhãn chuẩn của một cảnh, chèn lỗi giả vào 30% số track, in lỗi nào bắt được / bỏ sót và vì sao
pointsnap nuscenes scan --scene scene-0103 --inject --rate 0.3 --out out/demo

# Đánh giá precision / recall trên 5 cảnh kiểm tra (10 vòng chèn lỗi, ~1 phút) -> out/eval/ket-qua.md
pointsnap eval --scenes test
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

**nuScenes v1.0-mini**, quét thẳng nhãn chuẩn (`pointsnap eval --scenes test`): ngưỡng chỉnh trên 5 cảnh tinh chỉnh, số liệu dưới đây lấy trên **5 cảnh kiểm tra** (5 440 box, 10 vòng chèn lỗi, 349 lỗi chèn). Bảng đầy đủ: [`docs/ket-qua-danh-gia-tu-dong.md`](pointsnap-3d/docs/ket-qua-danh-gia-tu-dong.md). Chưa xem tay các mục báo nhầm (việc T2).

| Chỉ số | Mục tiêu | Kết quả |
|---|---|---|
| Recall lơ lửng / lún ≥ 20 cm | ≥ 90% | 92% (12/13) trên box có đủ điểm mặt đất; **chỉ ~1/4 box có đủ điểm**, còn lại ghi `thiếu bằng chứng` |
| Recall kích thước trong track ≥ 15% | ≥ 90% | 100% (24/24) với class được xét (bỏ người đi bộ) |
| Recall kích thước theo class (×0,6; ×1,5; đổi class) | ≥ 90% | 96% (55/57) |
| Recall nhảy vị trí ≥ 2 m | ≥ 90% | 83% (24/29) |
| Recall tách ID / khoảng nội suy ≥ 2 keyframe | ≥ 80% | 100% (21/21) / 100% (6/6) khi đối tượng đang chạy |
| Phân mức đúng (40 cm, 30%, 4 m báo ở mức Lỗi) | ≥ 80% | 81% (30/37) |
| Báo động giả trên nhãn chuẩn | ≤ 2 Cảnh báo, ≤ 0,5 Lỗi / 100 box | 3,7 Cảnh báo, 0,77 Lỗi (chủ yếu lơ lửng / lún: 3,2 và 0,66). Cảnh tinh chỉnh: 1,7 và 0,35 |
| Precision | ≥ 70% / loại | Kích thước 26%, đứt track 38%, lơ lửng 1%: lỗi chèn rất thưa so với số box, chưa trừ lỗi thật của nhãn chuẩn |
| Sai số số đo | < 5 cm (Z), < 5% (kích thước) | 6,1 cm; 0% |
| Sai số ước lượng mặt đất | Trung vị < 5 cm | **Không đạt**: trung vị 7,9 cm (tuyệt đối). Đã đổi sang so với track, xem [kiểm chứng ground](pointsnap-3d/docs/kiem-chung-ground.md) |
| Thời gian chạy `scan` | < 2 phút / cảnh | 0,4–1,6 s / cảnh (chưa tính thời gian gọi API CVAT) |

Chưa đo trên CVAT: bước đọc nhãn và ghi cờ qua API đã có test tự động và đã chạy trên CVAT local ở A3–A4, nhưng trọn quy trình `scan --flag` → lọc trong CVAT → `gate` với 3 bộ phát hiện mới chưa chạy lại.

## Giới hạn

Những chỗ tool **không** kiểm, annotator và reviewer vẫn phải tự soi:

- Chỉ có 3 loại lỗi trên. Ngược yaw 180°, box rỗng điểm, box chồng lấn, thiếu thuộc tính bắt buộc và sót đối tượng **chưa được kiểm**.
- Tool chỉ cảnh báo, **không tự sửa**.
- Mặt đất ước lượng kém ở đoạn dốc, bờ vỉa, chỗ bị che hoặc ở xa (LiDAR thưa): chỉ khoảng 1/4 box tiếp đất có đủ điểm để kết luận. Box còn lại được ghi "thiếu bằng chứng" ở mức Thông tin, cần tự kiểm.
- Luật lơ lửng / lún so với các frame khác của track: box lệch đều ở mọi frame của một track dài sẽ lọt.
- Thống kê kích thước theo class lấy từ 5 cảnh, mới đủ mẫu cho ô tô, người, cọc tiêu, rào chắn; class khác dùng khoảng nhập tay.
- Tách ID và khoảng nội suy dài chỉ ở mức Cảnh báo. Đối tượng bị che lâu hoặc ra khỏi tầm cảm biến có thể bị báo nhầm.
- Ngưỡng được thống kê trên nuScenes; dùng với dữ liệu khác cần thống kê lại.
- Mới thử trên CVAT local, chưa chạy trên CVAT của BTC.
- CVAT không khóa job khi có người mở: chỉ chạy `--flag` khi không ai đang mở job đó.

## Người viết

| Người | Vai trò | Phụ trách |
|---|---|---|
| @Khúc Việt Anh | Sản phẩm | Môi trường, chuyển nuScenes → CVAT, adapter CVAT, CLI, `scan --flag`, `gate`, báo cáo HTML/CSV, bộ chèn lỗi giả |
| @Đặng Văn Huy | Sản phẩm | Ước lượng mặt đất, 3 bộ phát hiện, đánh giá precision / recall (bản G2 do Việt Anh viết, Huy review) |
| @Vũ Bảo Khánh | Báo cáo | Báo cáo kết quả, slide |
| @Nhữ Đình Chiến | Test | Test quy trình trên CVAT theo README, video demo |
| @Nguyễn Văn Hân | Test | Xem tay cảnh báo, bảng chỉ số đánh giá |

Phân công chi tiết theo ngày: [giao việc theo ngày](pointsnap-3d/giao-viec/) · [mục 7 của bản đề xuất](pointsnap-3d/de-xuat-de-tai.md#7-kế-hoạch-triển-khai-4-ngày-có-cổng-kiểm-soát).
