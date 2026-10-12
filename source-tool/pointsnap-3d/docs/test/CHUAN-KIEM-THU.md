# Chuẩn kiểm thử toàn app PointSnap 3D

Áp dụng cho **mọi lần kiểm thử** PointSnap 3D (Khánh, Chiến, Hân và người test sau này). Thay thế phần "Mẫu file kết quả"
của [giao-viec/test-va-gop-y.md](../../quan-ly/giao-viec/test-va-gop-y.md) và mở rộng danh sách ca ra **toàn app**: cài đặt, CLI,
giao diện web (gồm màn chào và duyệt nhanh), tích hợp CVAT, extension CVAT, liên kết web ↔ extension.

Cài đặt làm theo [CAI-DAT.md](../../CAI-DAT.md). Chỗ nào CAI-DAT.md thiếu hoặc sai so với thực tế thì ghi thành lỗi
nhóm **Cài đặt / README**.

---

## 1. Năm quy tắc bắt buộc

1. **Đạt nghĩa là đạt hết.** Một ca chỉ ghi **Đạt** khi đã làm **đủ mọi bước** trong cột "Làm" và thấy **đủ mọi điều**
   trong cột "Mong đợi". Thiếu bước nào → ghi **Chưa làm đủ** và nói rõ bước nào. Không có kết quả kiểu "Đạt nhưng…":
   có điểm sai so với mong đợi thì là **Lỗi**.
2. **Mỗi ca phải có bằng chứng** (mục 3). Ghi chú kiểu "hoạt động tốt", "mượt mà", "khớp 100%" mà không có số liệu
   hoặc chi tiết quan sát được thì ca đó **không được tính**.
3. **Tự làm trên máy mình.** Không chép kết quả, số liệu hay kết luận xem tay của người khác, kể cả khi cùng cảnh. Ai
   làm hộ phần nào thì ghi rõ tên người làm ở phần đó.
4. **Lỗi phải tái hiện được.** Ghi lệnh hoặc thao tác **nguyên văn**, thông báo lỗi **nguyên văn**, kèm ảnh chụp.
   Người khác làm lại đúng các bước đó phải thấy cùng lỗi.
5. **Không sửa code, không lộ token.** Không commit `.env`, không chụp màn hình có token. Kết quả nằm trên branch
   `docs/test-<tên>` và vào `main` qua PR. Không push thẳng `main`.

## 2. Thông tin môi trường (bắt buộc ở đầu file)

| Mục | Ghi gì | Lấy ở đâu |
|---|---|---|
| Commit đã test | 7 ký tự đầu | `git rev-parse --short HEAD`; phải là commit có trên GitHub |
| Hệ điều hành, RAM | vd `Windows 11 Pro 23H2, 16 GB` | Settings → System → About |
| Python | đúng **3.11.x** | `python --version` trong venv |
| Docker Desktop | phiên bản | `docker --version` |
| CVAT | **một** phiên bản, đúng **v2.77.0** | tab Kết nối CVAT của web (TC-12) |
| Trình duyệt | Chrome / Edge + phiên bản | `chrome://version` |
| Task / job CVAT | id task, id job của scene-0061 | URL `/tasks/<t>/jobs/<j>` |
| Thời gian cài đặt | số phút của Phần cài đặt | tự bấm giờ |

Khác môi trường chuẩn (vd Python 3.10, CVAT khác 2.77) vẫn được test, nhưng phải ghi rõ ở đây và ghi một lỗi nhóm
**Cài đặt / README** nếu có chỗ không chạy.

## 3. Bằng chứng tối thiểu

| Loại ca | Bằng chứng cần ghi trong cột Ghi chú |
|---|---|
| Lệnh CLI | Lệnh nguyên văn + dòng kết quả chính (vd dòng cuối pytest, số Lỗi / Cảnh báo, mã thoát) |
| Giao diện web / extension | Giá trị nhìn thấy cụ thể (số trên thẻ, tên nút, câu thông báo) + ảnh chụp ở `docs/test/anh/<tên>/TC-xx.png` cho các ca đánh dấu 📷 |
| Thao tác "bấm N dòng" | Liệt kê N dòng đã bấm (frame, class, luật) và kết quả từng dòng |
| So khớp hai nơi | Ghi số của cả hai nơi (vd "web 43 mục, CSV 43 dòng, HTML 43 dòng") |

Ảnh chụp: cắt đúng vùng cần xem, che token và email.

## 4. Chuẩn báo lỗi

```markdown
### <TÊN>-<số>: <tiêu đề ngắn, nói hiện tượng>
- Ca: TC-xx · Nhóm: Cài đặt / README · CLI · Giao diện web · Tích hợp CVAT · Extension · Thuật toán
- Mức: Chặn / Nặng / Nhẹ (theo bảng dưới)
- Môi trường: chỉ ghi nếu khác phần đầu file
- Bước làm: 1. ... 2. ... (lệnh nguyên văn)
- Mong đợi: ...
- Thực tế: ... (thông báo lỗi nguyên văn) · Ảnh: docs/test/anh/<tên>/<mã lỗi>.png
- Tái hiện: Luôn luôn / Thỉnh thoảng (x/y lần) / Một lần
- Cách vượt qua tạm thời (nếu có): ...
```

| Mức | Định nghĩa | Ví dụ |
|---|---|---|
| **Chặn** | Làm theo hướng dẫn thì không đi tiếp được, không có cách vượt nào được ghi trong tài liệu | Upload task báo 403, CAI-DAT.md không nói cách xử lý |
| **Nặng** | Đi tiếp được nhưng kết quả sai hoặc mất dữ liệu | Gắn cờ sai box, số trên web khác CSV, gate sai mã thoát |
| **Nhẹ** | Kết quả đúng nhưng khó dùng, hiển thị xấu, chữ sai | Bộ lọc khó tìm, thiếu dòng nhắc F5 |

Đề xuất sửa là **không bắt buộc**. Nếu đề xuất thì kiểm trước trong code / tài liệu xem đã có chưa.

## 5. Danh sách ca kiểm thử

📷 = cần ảnh chụp. Làm theo thứ tự. `<job>` là id job của scene-0061.

### 5.1. Cài đặt (CAI-DAT.md bước 1–5)

| Mã | Làm | Mong đợi |
|---|---|---|
| **TC-01** | `python -m pytest -q` | Dòng cuối `N passed`, không có `failed` / `error`. Ghi nguyên dòng cuối |
| **TC-02** | `pointsnap --help` | Có `scan`, `gate`, `diff`, `config`, `nuscenes`, `eval`, `ui` |
| **TC-03** | `pointsnap nuscenes to-cvat --scene scene-0061 --out D:/data/cvat --upload` | Báo tạo task. CVAT có task *PointSnap scene-0061*. Ghi id task / job |
| **TC-04** 📷 | Mở job trên CVAT | Thấy point cloud, box, ảnh 6 camera; label có thuộc tính `pointsnap_error` và `reviewed` |
| **TC-05** | `pointsnap config` | In cấu hình, URL CVAT đúng, token hiện dạng ẩn (không lộ chuỗi token) |
| **TC-06** | `pointsnap nuscenes scenes` | Liệt kê 10 cảnh của bản mini, có `scene-0061` |

### 5.2. Giao diện web

Chạy `pointsnap ui`.

| Mã | Làm | Mong đợi |
|---|---|---|
| **TC-10** 📷 | `pointsnap ui` | Trình duyệt mở `http://127.0.0.1:8765`, có **màn chào** và nút **Bắt đầu**, tiếng Việt |
| **TC-11** | **Bắt đầu** → **Tạo dự án**: tên, URL `http://localhost:8080`, token | Dự án hiện ở danh sách bên trái, nhãn "Có Token" |
| **TC-12** 📷 | Tab **Kết nối CVAT**: điền thư mục nuScenes, thư mục bản xuất → **Lưu cài đặt kết nối** → **Kiểm tra kết nối** | Báo kết nối được **và hiện phiên bản CVAT**. Ghi phiên bản |
| **TC-13** | Sửa token thành chuỗi sai → lưu → kiểm tra. Rồi nhập lại token đúng | Báo lỗi dễ hiểu (ghi nguyên văn), không treo, không lộ token; nhập lại đúng thì kết nối lại được |
| **TC-14** | Tab **Quét job**: chọn task / job scene-0061, **không** gắn cờ → **Bắt đầu quét** | Có tiến độ, không treo, xong tự sang Kết quả. Ghi thời gian quét |
| **TC-15** 📷 | Màn **Kết quả** | Kết luận ĐẠT / KHÔNG ĐẠT kèm lý do; thẻ Lỗi / Cảnh báo / Thông tin / Tổng box. Ghi đủ 4 số |
| **TC-16** | Lọc lần lượt theo: mức độ, loại lỗi, **class**, **gõ chữ vào ô tìm kiếm** | Mỗi bộ lọc: bảng lọc đúng, "Hiển thị x / y" đổi theo. Ghi x / y của **từng** bộ lọc |
| **TC-17** | Bấm **Mở trong CVAT** ở **3 dòng khác loại lỗi** (khi chưa mở tab CVAT có extension) | Mở đúng job, đúng frame, đúng box. Liệt kê 3 dòng |
| **TC-18** | **Tải báo cáo HTML**, **Tải file CSV** | Mở được cả hai; số mục bằng nhau ở web, HTML, CSV. Ghi 3 số |
| **TC-19** 📷 | **Gắn cờ lên CVAT** → sang CVAT, F5 → Filters → Add rule → Attributes → `pointsnap_error` → **is not empty** → Submit | Số box lọc ra = số Lỗi + Cảnh báo; mở 2 box, nội dung cờ khớp dòng tương ứng trên web |
| **TC-20** | Trong CVAT sửa 3 box có cờ, **Save** → quét lại có gắn cờ | Cờ của box đã sửa mất hoặc đổi mức, số lỗi giảm. Ghi số trước / sau và 3 box đã sửa |
| **TC-21** | Tab **Lịch sử** | Thấy các lần quét theo thời gian, biểu đồ; bấm một lần quét cũ mở được kết quả của lần đó |
| **TC-22** | Tab **Guideline**: tắt luật `track_jump` → **Lưu thay đổi** → quét lại | Không còn mục `track.jump` |
| **TC-23** | **Thêm class** mới vào khoảng kích thước, **xóa class `bicycle`** → lưu → F5 | Class mới còn, `bicycle` đã mất |
| **TC-24** | Guideline → **YAML**: xóa một dấu `:` → lưu | Báo lỗi rõ ràng (ghi nguyên văn), **không** lưu |
| **TC-25** | Đổi ngưỡng gate (vd 100 lỗi, 100 cảnh báo) → quét lại. Sau đó **Khôi phục mặc định** | Kết luận đổi sang ĐẠT; khôi phục xong quét lại thì về KHÔNG ĐẠT |
| **TC-26** | Tạo dự án thứ hai với thư mục nuScenes **sai** → quét cùng job | Vẫn quét được, báo thiếu point cloud, bỏ qua luật lơ lửng / lún |
| **TC-27** | **Xóa vĩnh viễn** dự án thứ hai | Phải gõ lại tên mới xóa được; dự án thứ nhất còn nguyên |
| **TC-28** 📷 | Màn Kết quả → **Duyệt nhanh** | Hiện point cloud quanh box; `J` / `K` chuyển mục; `1` ghi Đúng là lỗi, `2` ghi Báo nhầm |
| **TC-29** | Ghi Đúng / Báo nhầm cho 3 mục → F5 → mở lại lần quét đó | 3 kết luận vẫn còn |

### 5.3. Dòng lệnh (CLI)

Tắt giao diện (Ctrl+C). Dùng guideline mặc định.

| Mã | Làm | Mong đợi |
|---|---|---|
| **TC-30** | `pointsnap scan --job <job>` | Tạo HTML / CSV trong `out\`; số Lỗi / Cảnh báo **bằng** TC-15. Ghi cả hai |
| **TC-31** | `pointsnap scan --job <job> --flag` | Dòng `Đã gắn cờ lỗi lên N box…`; N = số Lỗi + Cảnh báo |
| **TC-32** | `pointsnap gate --job <job>`; `echo $LASTEXITCODE` | In KHÔNG ĐẠT kèm lý do, mã thoát 1. Với `--config` nới ngưỡng thì ĐẠT, mã thoát 0. Ghi cả hai mã |
| **TC-33** | `pointsnap nuscenes scan --scene scene-0061` | Quét không cần CVAT; số Lỗi / Cảnh báo bằng TC-30 (khi nhãn CVAT chưa sửa) |
| **TC-34** | `pointsnap diff a.json b.json` | Báo lệnh chưa có, mã thoát 3 (không văng traceback) |
| **TC-35** | Chạy TC-30 trong **PowerShell mặc định** (không đặt `PYTHONIOENCODING`) | Tiếng Việt in đúng, không `UnicodeEncodeError` |

### 5.4. Extension CVAT (CAI-DAT.md bước 7)

Cài extension, mở job scene-0061 đã gắn cờ.

| Mã | Làm | Mong đợi |
|---|---|---|
| **TC-40** 📷 | Mở job | Bảng PointSnap hiện ở góc trái khung 3D, chấm xanh khi PointSnap đang chạy |
| **TC-41** | Lần đầu mở task: làm theo thông báo của bảng (nếu có) | Sau tối đa một lần **Tải lại trang**, bộ lọc "chỉ box có cờ" tự bật |
| **TC-42** | Bấm `.` 5 lần, rồi `,` 2 lần | Mỗi lần sang frame có lỗi kế tiếp / trước, **không tải lại trang**, box lỗi sáng lên |
| **TC-43** | Đọc thẻ lỗi của 3 box; ở frame có nhiều box lỗi bấm `1 / 2 ›` | Thẻ có mức, loại lỗi, mô tả, **Cách sửa** khớp web; `1 / 2 ›` chuyển và làm sáng box kế tiếp |
| **TC-44** | Tab **Danh sách**: lọc Lỗi / Cảnh báo, bấm 3 dòng | Số dòng = số trên web; bấm dòng nhảy đúng frame |
| **TC-45** | Ghi **Đúng là lỗi** / **Báo nhầm** cho 2 mục trên extension | Ghi được; xem ở web thấy cùng kết luận |
| **TC-46** | Tắt `pointsnap ui` | Bảng ghi "PointSnap tắt"; TC-42 – TC-44 vẫn chạy; nút Quét lại / Đúng / Báo nhầm báo rõ là cần PointSnap |
| **TC-47** | Sửa 1 box → Save → tab Danh sách **Quét + gắn cờ** → tải lại trang | Cờ của box đã sửa mất hoặc đổi |
| **TC-48** | Gõ trong ô nhập của CVAT (vd ô tìm kiếm) có ký tự `.` `,` | Không bị extension bắt phím, không nhảy frame |

### 5.5. Liên kết web ↔ extension (CAI-DAT.md bước 8)

Mở cùng lúc web PointSnap và tab CVAT đang mở **đúng job** của lần quét.

| Mã | Làm | Mong đợi |
|---|---|---|
| **TC-50** 📷 | Màn Kết quả của web | Nút đổi thành **Chuyển CVAT tới box này**, chấm xanh "CVAT đang mở job này" |
| **TC-51** | Bấm nút ở 3 dòng; chọn dòng bằng `J` / `K` | Tab CVAT nhảy đúng frame, đúng box, **không tải lại trang** |
| **TC-52** | Ghi Đúng / Báo nhầm ở web, chờ 3 giây xem extension; rồi ngược lại | Hai bên thấy cùng kết luận trong khoảng 2 giây |
| **TC-53** | Đóng tab CVAT, chờ 5 giây | Nút trên web về lại **Mở trong CVAT** |

### 5.6. Luồng trọn vẹn (dùng làm kịch bản video demo)

| Mã | Làm | Mong đợi |
|---|---|---|
| **TC-60** | Từ kết quả KHÔNG ĐẠT với guideline **mặc định**: sửa trong CVAT **mọi box mức Lỗi** và đủ số Cảnh báo để còn ≤ ngưỡng → quét + gắn cờ → `pointsnap gate` | Gate **ĐẠT** mà **không** nới ngưỡng. Ghi số Lỗi / Cảnh báo trước và sau |

### 5.7. Luật giai đoạn 3: sai hướng box, box lệch, bám spec

Dùng job scene-0061 (task tạo **lại** bằng bản `to-cvat` mới) và guideline mặc định. Mỗi ca sửa 1 box trên CVAT, Save,
quét lại, ghi mục tool báo, rồi **hoàn tác** (Ctrl+Z, Save) trước khi sang ca sau.

| Mã | Làm | Mong đợi |
|---|---|---|
| **TC-70** | Chọn một ô tô đang chạy, ở **một** keyframe xoay box 180° (mũi tên đỏ quay ngược) | `heading.flip` mức Lỗi ở đúng frame đó |
| **TC-71** | Cùng xe, xoay 90° ở một keyframe | `heading.flip` mức Lỗi (xoay ngang) |
| **TC-72** | Ô tô đỗ gần xe thu (< 20 m, nhiều điểm): xoay box 25° | `heading.points` (Cảnh báo) ở frame đó |
| **TC-73** | Kéo box một ô tô gần sang ngang ~1 m khỏi xe | `fit.outside` hoặc `fit.loose` (và/hoặc `track.jump`) ở frame đó |
| **TC-74** | Vẽ thêm một box ô tô chồng lên đúng xe đã có box (track mới) | `fit.overlap` mức Lỗi ở frame đó |
| **TC-75** | Vẽ một box ô tô vào chỗ trống trên mặt đường gần xe thu | `fit.empty` (Cảnh báo) |
| **TC-76** | Một track: bật **Switch outside** ở frame k, rồi tắt lại ở frame k+3 (track xuất hiện lại) | `track.reuse_id` (Cảnh báo), gợi ý dùng occluded |
| **TC-77** | Một track: bật **occluded** cho 10 frame liên tiếp | `track.occluded_long` (Cảnh báo) |
| **TC-78** | `pointsnap nuscenes --taxonomy spec-vn to-cvat --scene scene-0061 --out D:/data/cvat-vn --upload`, mở job | Label `Vehicle`, `Two-wheels`, `Pedestrian`, `Obstacle`; box có thuộc tính `subtype` / `rider_state` / `age_group` / `pose` / `type` |
| **TC-79** | Dự án mới cho job TC-78 → tab Guideline → YAML: thay toàn bộ nội dung bằng `pointsnap/guidelines/spec-vn.yaml` → lưu → quét | Lưu được (phần thiếu lấy từ mặc định); không có `attr.*`; số Lỗi / Cảnh báo cùng cỡ với job nuScenes |
| **TC-80** | Guideline của TC-79: thêm thuộc tính `color` vào `spec.required_attributes.Vehicle`, rồi bỏ `sitting` khỏi `spec.allowed_values.pose` → lưu → quét | `attr.missing` (mỗi track Vehicle một mục, mức Lỗi); `attr.invalid` ở người đang ngồi (nếu có) |

## 6. Chuẩn xem tay cảnh báo (precision thật)

1. **Chỉ xem đúng loại được giao** (`floating`, `size.*` hoặc `track.*`). Loại được giao có ít hơn 20 mục Lỗi /
   Cảnh báo thì **xem hết số đó và ghi rõ "có N mục"**. Không lấy thêm từ loại của người khác, trừ khi giao việc ghi rõ.
2. **Lấy từ trên xuống** theo bảng Kết quả (lọc theo loại, mức Lỗi + Cảnh báo, sắp mặc định). Không bỏ qua mục nào.
   Mục không xem được thì vẫn ghi dòng, kết luận **Không chắc**, lý do "không xem được vì …".
3. **Ghi đủ để người khác tìm lại được trên CVAT khác:** frame, class, luật, mức và **số đo tool báo** (cột `value`
   trong CSV, vd `0.26` m). Track ID trên CVAT mỗi máy mỗi khác nên chỉ ghi thêm, không dùng để đối chiếu.
4. **Lý do phải dựa trên thứ nhìn thấy** trong point cloud hoặc ảnh camera, và phải khớp câu báo của tool. Ví dụ tốt:
   "đáy box cao hơn các điểm mặt đường quanh bánh khoảng 20 cm ở cả ảnh CAM_FRONT". Không viết lý do suy đoán về ý định
   của annotator.
5. **Nhất quán:** cùng một track, cùng một nguyên nhân thì cùng kết luận. Kết luận khác nhau giữa các frame của cùng
   track thì phải nói rõ frame đó khác gì.
6. **Precision tính riêng cho từng loại:** Precision = Đúng / (Đúng + Báo nhầm). Ghi cả số mục Không chắc.
7. Ghi kết luận vào cả file kết quả **và** web (nút Đúng là lỗi / Báo nhầm) để số liệu lưu lại trong `reviews.json`.

## 7. Mẫu file kết quả `docs/test/<tên>.md`

```markdown
# Kết quả kiểm thử — <Họ tên> (<ngày>)

| Commit | Hệ điều hành, RAM | Python | Docker | CVAT | Trình duyệt | Task / job scene-0061 | Thời gian cài |
|---|---|---|---|---|---|---|---|
| | | | | | | | |

## Tổng quan
Đạt: x · Lỗi: y · Chưa làm đủ: z · Không làm được: w (trên tổng 57 ca)

## Kết quả từng ca
| Mã | Kết quả (Đạt / Lỗi / Chưa làm đủ / Không làm được) | Mã lỗi | Bằng chứng |
|---|---|---|---|
| TC-01 | | | |
| ... đủ TC-01 – 06, 10 – 29, 30 – 35, 40 – 48, 50 – 53, 60, 70 – 80 | | | |

## Lỗi
### <TÊN>-01: ...
(theo mẫu mục 4)

## Xem tay cảnh báo — loại `<loại được giao>` (có N mục Lỗi / Cảnh báo, đã xem M mục)
| # | Frame | Class | Luật | Mức | Số đo tool báo | Track (CVAT) | Kết luận | Lý do (thấy gì) |
|---|---|---|---|---|---|---|---|---|

Đúng: a · Báo nhầm: b · Không chắc: c · **Precision = a / (a + b) = …**

## Góp ý phát triển
| Vấn đề | Đề xuất | Lợi ích | Ưu tiên (Cao / TB / Thấp) |
|---|---|---|---|
```

## 8. Tự kiểm trước khi mở PR

- [ ] Phần đầu đủ 8 mục; commit có trên GitHub; CVAT ghi **một** phiên bản.
- [ ] Đủ 57 ca; không ca nào để trống.
- [ ] Mọi ca **Đạt** đều đã làm đủ bước và có bằng chứng theo mục 3; ca 📷 có ảnh.
- [ ] Mọi ca **Lỗi** có mã lỗi; mọi mã lỗi có bước làm nguyên văn và tái hiện được.
- [ ] Xem tay: đúng loại được giao, lấy từ trên xuống, có số đo tool báo, precision tính riêng cho loại đó.
- [ ] Không có token, email, `.env` trong file và ảnh.
- [ ] PR có tiêu đề tiếng Việt có dấu và phần mô tả tóm tắt: số ca Đạt / Lỗi, số lỗi theo mức, precision.
