# Quy trình kiểm thử PointSnap 3D — Khánh, Chiến, Hân

> **Từ 09/10:** danh sách ca, cách ghi kết quả, chuẩn báo lỗi và chuẩn xem tay theo
> [docs/test/CHUAN-KIEM-THU.md](../docs/test/CHUAN-KIEM-THU.md) (toàn app, gồm cả extension). File này giữ lại phần
> phân công và tổng hợp lỗi.

Code đã xong và đã vào `main` (PR #18 – #23), gồm cả **giao diện web** (`pointsnap ui`).
**Ba người làm cùng một quy trình** dưới đây, mỗi người trên máy của mình, ghi kết quả vào file riêng. Sau đó Khánh
tổng hợp lỗi để Việt Anh giao việc sửa cho Việt Anh và Huy.

Làm **sớm nhất có thể**, theo thứ tự:

| Bước | Việc | Ai |
|---|---|---|
| 1 | Xong **Phần 1 — Cài đặt** (TC-01 – TC-04) | Cả 3 |
| 2 | Xong **Phần 2 — Kiểm thử**, đẩy file kết quả `docs/test/<tên>.md` | Cả 3 |
| 3 | Xong **Phần 4 — Tổng hợp lỗi** `docs/test/tong-hop-loi.md` ngay khi đủ 3 file | Khánh |
| 4 | Đọc tổng hợp, giao việc sửa cho Việt Anh và Huy (điền cột "Giao cho") | Việt Anh |

**Quy tắc:**
- Không sửa code. Thấy lỗi thì ghi lại, kể cả lỗi nhỏ, kể cả chỗ README khó hiểu.
- File kết quả làm trên branch riêng `docs/test-<tên>` (vd `docs/test-chien`), mở PR vào `main`; không push thẳng `main`.
- Không gửi token CVAT cho ai, không chụp màn hình có token, không commit file `.env`.
- Kẹt quá 30 phút ở một bước thì nhắn Việt Anh, ghi lỗi lại rồi làm tiếp bước khác.

---

## Phần 1 — Hướng dẫn cài đặt (Windows)

Cần khoảng 15 GB ổ trống, RAM ≥ 8 GB. Bản đầy đủ (có thêm extension và liên kết với web) trong [CAI-DAT.md](../../CAI-DAT.md); chỗ nào hai bản khác nhau thì ghi lỗi.

### 1.1. Phần mềm

- **Git**: https://git-scm.com
- **Python 3.11** (đúng bản 3.11): https://www.python.org/downloads/ — khi cài tích "Add python.exe to PATH".
- **Docker Desktop**: https://www.docker.com/products/docker-desktop/ — cài xong mở Docker Desktop, chờ báo
  "Engine running".

### 1.2. CVAT chạy trên máy (Docker)

Mở PowerShell:

```powershell
git clone https://github.com/cvat-ai/cvat D:\Work\cvat
cd D:\Work\cvat
$env:CVAT_VERSION = "v2.77.0"
docker compose up -d
```

Lần đầu tải image mất 10 – 20 phút. Nếu lỗi mạng khi tải image thì chạy lại `docker compose up -d`.
Tạo tài khoản admin (nhập tên, email, mật khẩu theo lời nhắc):

```powershell
docker exec -it cvat_server bash -ic "python3 ~/manage.py createsuperuser"
```

Mở http://localhost:8080, đăng nhập. Tạo **Access token**: bấm tên tài khoản (góc phải trên) → Profile / Settings →
Access tokens → tạo token mới, chép lại (chỉ hiện một lần).

### 1.3. Dữ liệu nuScenes v1.0-mini (~4 GB)

1. Tải `v1.0-mini.tgz` (4,2 GB) tại https://www.nuscenes.org/data/v1.0-mini.tgz. Nếu link không tải được thì
   đăng ký tài khoản tại https://www.nuscenes.org/nuscenes#download rồi tải bản **Mini**.
2. Giải nén vào một thư mục, ví dụ `D:\data\nuscenes`. Bên trong phải có `samples\`, `sweeps\`, `maps\`, `v1.0-mini\`.

### 1.4. Cài tool PointSnap 3D

```powershell
git clone https://github.com/AI20K-Build-Phase-Cohort-4A/P-029 D:\Work\P-029
cd D:\Work\P-029\source-tool\pointsnap-3d
py -3.11 -m venv .venv
.venv\Scripts\activate
pip install -e ".[dev]"
```

Tạo file `.env` trong `source-tool\pointsnap-3d\` (thay giá trị của mình):

```
CVAT_TOKEN=<token vừa tạo>
NUSCENES_ROOT=D:/data/nuscenes
POINTSNAP_EXPORT_DIR=D:/data/cvat
```

Từ đây mọi lệnh `pointsnap` chạy trong thư mục `source-tool\pointsnap-3d` với venv đã bật (`.venv\Scripts\activate`).

### 1.5. Kiểm tra cài đặt

| Mã | Làm | Mong đợi |
|---|---|---|
| **TC-01** | `python -m pytest -q` | Dòng cuối `... passed`, không có `failed` |
| **TC-02** | `pointsnap --help` | Hiện danh sách lệnh, có `scan`, `gate`, `nuscenes`, `ui` |
| **TC-03** | `pointsnap nuscenes to-cvat --scene scene-0061 --out D:/data/cvat --upload` | Báo tạo task; trong CVAT (Tasks) có task mới |
| **TC-04** | Mở task vừa tạo → mở job | Thấy point cloud, box, và ảnh 6 camera bên cạnh |

---

## Phần 2 — Hướng dẫn kiểm thử

Cả 3 người làm **đủ mọi ca** theo thứ tự. Mỗi ca ghi **Đạt / Lỗi / Không làm được** vào file kết quả (Phần 3).
Ca nào Lỗi thì ghi một mục lỗi, kèm ảnh chụp.

### 2.1. Giao diện web

Chạy `pointsnap ui` → trình duyệt tự mở http://127.0.0.1:8765 (không mở thì tự gõ địa chỉ này).

| Mã | Làm | Mong đợi |
|---|---|---|
| **TC-10** | `pointsnap ui` | Trình duyệt mở giao diện PointSnap 3D, tiếng Việt |
| **TC-11** | **+ Tạo dự án mới**: đặt tên, nhập URL `http://localhost:8080`, token, thư mục nuScenes, thư mục bản xuất `D:/data/cvat` | Dự án hiện ở danh sách bên trái, có nhãn "Có Token" |
| **TC-12** | Tab **Kết nối** → **Kiểm tra kết nối** | Báo kết nối được, hiện phiên bản CVAT (v2.77.0) |
| **TC-13** | Tab **Kết nối**: sửa token thành chuỗi sai → lưu → kiểm tra kết nối. Sau đó nhập lại token đúng | Báo lỗi dễ hiểu (không treo, không lộ token); nhập lại đúng thì kết nối lại được |
| **TC-14** | Tab **Quét**: chọn task scene-0061 và job, **không** tích "Gắn cờ" → **Bắt đầu quét ngay** | Có thanh tiến độ, giao diện không treo; xong tự chuyển sang Kết quả |
| **TC-15** | Tab **Kết quả & Gate** | Có kết luận ĐẠT / KHÔNG ĐẠT kèm lý do; thẻ số Lỗi, Cảnh báo, Thông tin, Tổng số box |
| **TC-16** | Lọc theo mức độ, loại lỗi, class; gõ chữ vào ô tìm kiếm | Bảng lọc đúng, số "Hiển thị x / y" thay đổi theo |
| **TC-17** | Bấm **Mở CVAT** ở 3 dòng khác nhau | Mở đúng job và đúng frame ghi trong dòng đó |
| **TC-18** | **Tải báo cáo HTML** và **Tải file CSV** | Mở được cả hai file; số mục khớp với bảng |
| **TC-19** | **Quét lại & Gắn cờ lên CVAT** → sang CVAT, F5, Filters → Attributes → `pointsnap_error` → is not empty | Chỉ box có Lỗi / Cảnh báo được lọc ra; nội dung cờ khớp với bảng |
| **TC-20** | Trong CVAT sửa 3 box có cờ (kéo đáy chạm đất, chỉnh kích thước), **Save** → quay lại giao diện, quét lại có gắn cờ | Cờ của box đã sửa mất (hoặc đổi mức), số lỗi giảm |
| **TC-21** | Tab **Lịch sử** | Thấy các lần quét theo thời gian, biểu đồ số lỗi; bấm một lần quét cũ mở được kết quả |
| **TC-22** | Tab **Guideline**: tắt luật `track_jump` → lưu → quét lại | Không còn mục `track.jump` trong kết quả |
| **TC-23** | Tab **Guideline**: thêm một class mới vào khoảng kích thước, xóa class `bicycle` → lưu → tải lại trang (F5) | Class mới còn, `bicycle` đã mất |
| **TC-24** | Tab **Guideline** → phần YAML: gõ sai cú pháp (vd xóa dấu `:`) → lưu | Báo lỗi rõ ràng, **không** lưu |
| **TC-25** | Tab **Guideline**: đổi ngưỡng gate (vd cho phép 100 lỗi, 100 cảnh báo) → quét lại | Kết luận đổi sang ĐẠT |
| **TC-26** | Tạo dự án thứ hai với thư mục nuScenes **sai** → quét cùng job | Vẫn quét được, có thông báo thiếu point cloud và bỏ qua luật lơ lửng / lún |
| **TC-27** | Xóa dự án thứ hai (nút **Xóa dự án**) | Phải gõ lại tên mới xóa được; dự án thứ nhất không bị ảnh hưởng |

### 2.2. Dòng lệnh (CLI)

Đóng giao diện (Ctrl+C), chạy trong `source-tool\pointsnap-3d`. `<id>` là số job của task scene-0061.

| Mã | Làm | Mong đợi |
|---|---|---|
| **TC-30** | `pointsnap scan --job <id>` | Tạo báo cáo trong `out\`; số Lỗi / Cảnh báo **giống** lần quét ở giao diện (cùng guideline mặc định) |
| **TC-31** | `pointsnap scan --job <id> --flag` | Gắn cờ như TC-19 |
| **TC-32** | `pointsnap gate --job <id>`, rồi `echo $LASTEXITCODE` | In ĐẠT / KHÔNG ĐẠT kèm lý do; mã thoát 0 khi đạt, 1 khi không đạt |

### 2.3. Xem tay cảnh báo (độ chính xác thật của tool)

Dùng kết quả quét job scene-0061 với guideline mặc định. Mỗi người xem **20 mục mức Lỗi / Cảnh báo** của một loại
lỗi (lọc ở tab Kết quả theo loại lỗi, lấy từ trên xuống):

| Người | Loại lỗi |
|---|---|
| Khánh | Lơ lửng / lún (`floating`) |
| Chiến | Đứt track (`track.*`) |
| Hân | Kích thước (`size.*`); nếu ít hơn 20 mục thì lấy thêm lơ lửng / lún từ mục thứ 21 trở đi |

Mỗi mục: bấm **Mở CVAT**, nhìn point cloud và ảnh camera, kết luận:
- **Đúng**: nhãn thật sự sai như tool báo.
- **Báo nhầm**: nhãn đúng, tool báo sai.
- **Không chắc**: không đủ thông tin để kết luận.

Ghi kèm một câu lý do (vd "đáy box nằm trên bờ vỉa, mặt đường thấp hơn").

---

## Phần 3 — Mẫu file kết quả của từng người

Mỗi người tạo `source-tool/pointsnap-3d/docs/test/<tên>.md` (`khanh.md`, `chien.md`, `han.md`), chép mẫu này:

```markdown
# Kết quả kiểm thử — <Họ tên> (<ngày>)

Máy: Windows <phiên bản>, RAM <x> GB · Python <x> · Docker Desktop <x> · CVAT v2.77.0 · commit main: <7 ký tự đầu>
Thời gian cài đặt (Phần 1): <x> phút

## Kết quả từng ca
| Mã | Kết quả (Đạt / Lỗi / Không làm được) | Mã lỗi | Ghi chú |
|---|---|---|---|
| TC-01 | | | |
| ... (đủ TC-01 – TC-04, TC-10 – TC-27, TC-30 – TC-32) | | | |

## Lỗi
### <TÊN>-01: <tiêu đề ngắn>
- Ca: TC-xx · Nhóm: Cài đặt / README · Giao diện web · CLI · Tích hợp CVAT · Thuật toán
- Mức: Chặn (không làm tiếp được) / Nặng (sai kết quả) / Nhẹ (khó dùng, hiển thị)
- Bước làm: 1. ... 2. ...
- Mong đợi: ...
- Thực tế: ... (kèm thông báo lỗi nguyên văn, ảnh chụp)

## Xem tay cảnh báo
| # | Frame | Track | Class | Quy tắc | Mức | Kết luận (Đúng / Báo nhầm / Không chắc) | Lý do |
|---|---|---|---|---|---|---|---|

Precision xem tay = Đúng / (Đúng + Báo nhầm) = ...

## Góp ý phát triển
- Chỗ khó dùng: ...
- Đề xuất tính năng (vấn đề → đề xuất → lợi ích → ưu tiên Cao / TB / Thấp): ...
```

Mã lỗi dùng tên viết tắt: `KHANH-01`, `CHIEN-01`, `HAN-01`, …

---

## Phần 4 — Tổng hợp lỗi (Khánh)

Khánh gộp 3 file kết quả thành `source-tool/pointsnap-3d/docs/test/tong-hop-loi.md`:
- Lỗi trùng nhau (nhiều người gặp) gộp thành một dòng, ghi đủ người gặp.
- Sắp xếp theo mức: Chặn → Nặng → Nhẹ.
- **Không điền** cột "Giao cho" và "Hạn": Việt Anh điền khi giao việc.

```markdown
# Tổng hợp lỗi kiểm thử PointSnap 3D (<ngày>)

## 1. Tổng quan
| Người | Số ca Đạt / Lỗi / Không làm được | Thời gian cài đặt |
|---|---|---|

Ca lỗi ở cả 3 máy: ... · Ca chỉ lỗi ở một máy: ...

## 2. Danh sách lỗi
| Mã | Mô tả ngắn | Nhóm | Mức | Ca | Gặp bởi | Mã gốc | Đề xuất sửa | Giao cho | Hạn |
|---|---|---|---|---|---|---|---|---|---|
| L01 | | | | | Khánh, Hân | KHANH-02, HAN-01 | | | |

## 3. Độ chính xác xem tay
| Loại lỗi | Số mục | Đúng | Báo nhầm | Không chắc | Precision |
|---|---|---|---|---|---|

Các kiểu báo nhầm hay gặp: ...

## 4. Góp ý phát triển (gộp từ 3 người)
| Đề xuất | Lợi ích | Ưu tiên | Ai đề xuất |
|---|---|---|---|

Top 3 việc nên làm tiếp: 1. ... 2. ... 3. ...
```

Gợi ý chia việc khi điền "Giao cho":
- Nhóm **Thuật toán** (báo nhầm, bỏ sót, ngưỡng): Huy.
- Nhóm **Giao diện web**, **CLI**, **Tích hợp CVAT**, **Cài đặt / README**: Việt Anh.

## Sau khi tổng hợp

- Hân dùng bảng mục 3 để điền độ chính xác xem tay vào `docs/danh-gia.md`.
- Khánh đưa mục 4 vào phần Hướng phát triển của báo cáo kết quả, rồi hoàn thiện báo cáo và slide.
- Chiến quay video demo 3 – 5 phút bằng giao diện web, theo đúng TC-11 → TC-21.
