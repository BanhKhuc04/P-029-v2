# PointSnap 3D

**Giải quyết:** [P-010](../problem-backlog.md#p-010) — khó căn đáy cuboid sát mặt đất, box lơ lửng / lún · [P-011](../problem-backlog.md#p-011) — lỗi 3D chỉ phát hiện ở khâu review thủ công, gây rework lớn

> **Trạng thái:** 🛠️ Đang làm (05/10 – 15/10/2026). Hiện mới có [bản đề xuất](pointsnap-3d/de-xuat-de-tai.md), chưa có source code.
> Lệnh trong mục "Cài đặt và chạy" là **dự kiến**; mục "Đã thử trên" sẽ điền khi có số đo thật.

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
| Đứt track | Tâm box lệch khỏi vị trí nội suy từ hai frame bên cạnh; track kết thúc rồi track cùng class bắt đầu ngay gần đó; đoạn dài chỉ có box nội suy (nếu kịp) | Xe: 1 m / 2 m; tách ID chỉ Cảnh báo |

Ngưỡng nằm trong `config.yaml` và sẽ chốt lại trên dữ liệu. Chi tiết từng luật: [mục 4.1 của bản đề xuất](pointsnap-3d/de-xuat-de-tai.md#41--ba-bộ-phát-hiện).

Tool **chỉ ghi thuộc tính cờ lỗi**: không đổi vị trí, kích thước, class của box nào và không tự tạo box mới.

## Cài đặt và chạy

**Chuẩn bị trên CVAT:** thêm vào label spec thuộc tính văn bản `pointsnap_error` và checkbox `reviewed`. Tạo access token trong CVAT.

```bash
# Cài (dự kiến)
cd source-tool/pointsnap-3d
pip install -e .

# Cấu hình: URL và token qua biến môi trường, không commit token
export CVAT_URL=http://localhost:8080
export CVAT_TOKEN=<token của bạn>

# Quét job, xuất báo cáo HTML/CSV
pointsnap scan --job 12

# Quét và gắn cờ lỗi lên box trong CVAT (chỉ chạy khi không ai đang mở job)
pointsnap scan --job 12 --flag

# Cổng trước khi nộp: exit code 0 = ĐẠT, 1 = KHÔNG ĐẠT
pointsnap gate --job 12

# So hai phiên bản nhãn (dùng khi đánh giá)
pointsnap diff <bản-cũ> <bản-mới>
```

Trên Windows PowerShell, đặt biến môi trường bằng `$env:CVAT_URL = "http://localhost:8080"`.

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

*Chưa có số đo.* Kế hoạch kiểm thử trên **nuScenes v1.0-mini** (10 cảnh, ~400 frame có nhãn) chạy trên CVAT Docker local: 5 cảnh để chỉnh ngưỡng, 5 cảnh để báo cáo kết quả. Chi tiết: [mục 8 của bản đề xuất](pointsnap-3d/de-xuat-de-tai.md#8-đo-lường--tiêu-chí-chấp-nhận).

| Chỉ số | Mục tiêu | Kết quả |
|---|---|---|
| Recall trên lỗi chèn giả (lơ lửng ≥ 20 cm, kích thước ≥ 15%, nhảy ≥ 2 m) | ≥ 90% | — |
| Precision mỗi loại lỗi | ≥ 70% | — |
| Báo động giả trên nhãn chuẩn | ≤ 2 Cảnh báo / 100 box | — |
| Sai số ước lượng mặt đất (~200 box chuẩn) | Trung vị < 5 cm | — |
| Thời gian chạy `scan` | < 2 phút / cảnh | — |
| Thời gian review có / không có tool | Tham khảo | — |

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
| @Khúc Việt Anh | Code | Chuyển nuScenes → CVAT, adapter CVAT, CLI, `scan --flag`, `gate`, báo cáo HTML/CSV, bộ chèn lỗi giả, `diff` |
| @Đặng Văn Huy | Code | Ước lượng mặt đất, 3 bộ phát hiện, tính precision / recall |
| @Nhữ Đình Chiến | Tester | Dựng CVAT, cấu hình label spec, kiểm toàn quy trình trên CVAT |
| @Nguyễn Văn Hân | Tester | Ca kiểm thử có đáp án, đặc tả lỗi chèn giả, chủ trì đánh giá |
| @Vũ Bảo Khánh | Tester | Dùng thử như annotator, điều phối, tài liệu và video demo |

Phân công chi tiết theo ngày: [mục 7 của bản đề xuất](pointsnap-3d/de-xuat-de-tai.md#7-kế-hoạch-triển-khai-15-tuần-có-cổng-kiểm-soát).
