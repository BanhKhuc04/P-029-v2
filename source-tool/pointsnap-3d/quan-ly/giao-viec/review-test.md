# Review và test sản phẩm — Khánh, Hân, Chiến (từ 07/10)

Sản phẩm đã chạy được trọn quy trình trên CVAT local (07/10): `scan --flag` → lọc box có cờ trong CVAT → `gate`,
task 3D có kèm ảnh 6 camera. Từ hôm nay **phần review và test do Khánh, Hân, Chiến làm**; Việt Anh chuyển sang
giảm báo nhầm và làm giao diện web, Huy chỉnh ngưỡng.

Lỗi hay chỗ khó hiểu nào cũng ghi lại (bước làm, kết quả mong đợi, kết quả thật, ảnh chụp) vào file của mình trong
[`docs/`](../../docs/) và nhắn Việt Anh. Không sửa code, không push lên `main`: tài liệu cũng làm trên branch rồi mở PR.

## Trạng thái code cần biết

| PR | Nội dung | Trạng thái |
|---|---|---|
| [#18](https://github.com/AI20K-Build-Phase-Cohort-4A/P-029/pull/18) | Nối 3 bộ phát hiện vào `scan` / `gate`, đọc point cloud theo `manifest.json` | Chờ merge |
| [#19](https://github.com/AI20K-Build-Phase-Cohort-4A/P-029/pull/19) | Kèm ảnh 6 camera vào task 3D (xếp chồng trên #18) | Chờ merge |

Cho tới khi #18, #19 được merge, chạy thử trên branch `feat/A2-context-images` (đã gồm cả hai).
**Đã biết:** trên nhãn chuẩn tool còn báo nhầm nhiều (job scene-0061: 116 Lỗi, 135 Cảnh báo / 3 333 box), nên
`gate` gần như luôn KHÔNG ĐẠT. Việt Anh đang sửa; khi test, ghi lại báo nhầm nhưng không cần báo đây là lỗi mới.

## Nhữ Đình Chiến — T1: test quy trình trên máy mình

Mục tiêu: một người chưa từng dùng tool làm theo README mà chạy được. Mọi chỗ README thiếu là lỗi cần báo.

- [ ] **Cài môi trường**
  - Docker Desktop, Python 3.11, Git.
  - Dữ liệu nuScenes v1.0-mini (~4 GB, đăng ký tại nuscenes.org) giải nén vào một thư mục, ví dụ `D:/data/nuscenes`
    (bên trong có `samples/`, `v1.0-mini/`).
  - CVAT: `git clone https://github.com/cvat-ai/cvat`, trong thư mục đó đặt biến `CVAT_VERSION=v2.77.0` rồi chạy
    `docker compose up -d`; tạo admin bằng
    `docker exec -it cvat_server bash -ic "python3 ~/manage.py createsuperuser"`; đăng nhập http://localhost:8080,
    tạo Access token.
  - Cài tool theo [README](../../README.md#cài-đặt-và-chạy) (`pip install -e .`), tạo file `.env` với `CVAT_TOKEN`,
    `NUSCENES_ROOT`, `POINTSNAP_EXPORT_DIR`.
- [ ] **Tạo task**: `pointsnap nuscenes to-cvat --scene scene-0061 --out <thư mục>/cvat --upload`
  (`POINTSNAP_EXPORT_DIR` trỏ tới `<thư mục>/cvat`). Mở task trên CVAT: thấy point cloud, box và ảnh camera.
- [ ] **Quét và gắn cờ**: `pointsnap scan --job <id> --flag`. Mở báo cáo `out/report_job_<id>.html`, bấm vài link
  "Mở frame" xem có nhảy đúng frame không.
- [ ] **Lọc trong CVAT**: F5, Filters → Attributes → `pointsnap_error` → is not empty. Box có cờ có đúng là box trong
  báo cáo không?
- [ ] **Sửa rồi quét lại**: sửa 3–5 box có cờ (kéo đáy chạm đất, chỉnh kích thước), Save, chạy lại
  `pointsnap scan --job <id> --flag`: cờ của box đã sửa phải biến mất. Chạy `pointsnap gate --job <id>`.
- [ ] Ghi kết quả vào `docs/loi-khi-test.md`: mỗi lỗi một mục (bước, mong đợi, thực tế, ảnh). Hạn: tối 08/10.

## Nguyễn Văn Hân — T2: xem tay cảnh báo, điền bảng chỉ số (chủ trì)

Mục tiêu: biết cảnh báo nào đúng, cảnh báo nào báo nhầm, để có số liệu thật cho báo cáo.

- [ ] Nhờ Việt Anh mở task scene-0061 trên máy Việt Anh (hoặc dùng task Chiến tạo ở T1). Lấy báo cáo
  `report_job_<id>.csv` của lần `scan` mới nhất.
- [ ] **Xem tay 50 mục** (lấy đều: ~20 lơ lửng / lún, ~15 kích thước, ~15 đứt track; ưu tiên mức Lỗi). Với mỗi mục:
  mở frame trong CVAT, nhìn point cloud và ảnh camera, ghi **Đúng** (nhãn thật sự sai) / **Báo nhầm** /
  **Không chắc**, kèm một câu lý do (ví dụ "đáy box nằm trên bờ vỉa, mặt đường thấp hơn").
  Ghi vào bảng trong `docs/ket-qua/danh-gia.md` (thêm cột "Xem tay").
- [ ] Từ bảng trên tính **precision đã xem tay** cho từng loại lỗi = Đúng / (Đúng + Báo nhầm).
- [ ] Điền các chỉ số mục 8.2 của [bản đề xuất](../../docs/thiet-ke/de-xuat-de-tai.md#82-chỉ-số-và-kết-quả-hiện-tại) vào `docs/ket-qua/danh-gia.md`, ghi rõ số nào
  lấy từ script tự động (Huy, Việt Anh) và số nào do mình xem tay. Hạn: 12h 09/10 (G3); khi Việt Anh báo đã giảm báo
  nhầm thì chạy lại `scan` và cập nhật.

## Nhữ Đình Chiến — hỗ trợ T2 và video

- [ ] Sau T1: cùng Hân xem tay, chia theo loại lỗi (Hân lơ lửng / lún, Chiến kích thước và đứt track).
- [ ] **R2 — video demo 3–5 phút** (chiều 09/10): mở task trên CVAT → `scan --flag` → lọc box có cờ, xem ảnh camera
  → sửa box → `scan` lại, cờ biến mất → `gate`. Nếu giao diện web đã xong thì quay bằng giao diện.

## Vũ Bảo Khánh — báo cáo, slide, review tài liệu

- [ ] **R1** — khung `docs/bao-cao-ket-qua.md` và slide: bối cảnh, vấn đề, giải pháp, cách đánh giá (lấy từ
  [bản đề xuất](../../docs/thiet-ke/de-xuat-de-tai.md)), để trống số liệu. Hạn: tối 08/10.
- [ ] **Review tài liệu**: đọc [README của tool](../../README.md) như người mới, đánh dấu câu khó hiểu, thiếu bước;
  góp ý trong PR hoặc nhắn Việt Anh.
- [ ] **R2, R3** (09/10): điền số liệu từ Hân vào báo cáo và slide; chốt nhật ký tuần 04; nộp cuối ngày.
