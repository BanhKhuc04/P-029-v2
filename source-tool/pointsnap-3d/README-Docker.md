# PointSnap 3D bằng Docker

Đối chiếu 12/10/2026, nhánh review 08. Xem [cài đặt](../CAI-DAT.md),
[bảo mật](docs/local-security.md) và [vận hành](docs/operations.md).
Docker Desktop/Engine và CVAT là dependency ngoài; checkout này không cài CVAT.

## Chuẩn bị

Chạy từ `source-tool/pointsnap-3d`. Sao chép `.env.example` thành `.env`, điền PAT
của CVAT vào `CVAT_TOKEN` cho CLI. Không đưa token vào URL, Git hay Docker image.
API dùng PAT của từng người gọi, không dùng PAT CLI trong `.env`.

Kiểm `docker network ls` và tên service CVAT trong stack của bạn. Mặc định:

| Biến | Giá trị / ý nghĩa |
|---|---|
| `CVAT_BACKEND_URL` | `http://cvat-server:8080`, container gọi CVAT |
| `CVAT_WEB_URL` | `http://localhost:8080`, link mở trên máy người dùng |
| `CVAT_DOCKER_NETWORK` | `cvat_cvat`, network đã tồn tại của CVAT |
| `CVAT_HOST` | `localhost`, Host mà router Traefik nhận |
| `POINTSNAP_EXPORT_HOST_ROOT` | `./data/cvat`, chứa bản xuất/manifest |
| `NUSCENES_HOST_ROOT` | root dataset đã giải nén; trống dùng `./data/nuscenes` |

Backend và Web URL phải trỏ tới **cùng server CVAT**. Tool chỉ dùng alias này khi
URL của job khớp `CVAT_URL` trong container; không ghép hai server theo task ID.
Manifest xuất trên host vẫn được tìm theo Web URL. Dataset trong container nằm
ở `/work/data/nuscenes`; export nằm ở `/work/data/cvat`.
Root nuScenes cần `samples/`, `v1.0-mini/` và `sweeps/` nếu cấu hình dùng sweeps.
Mount dataset chỉ đọc. Thiếu/corrupt cloud hoặc pose có thể làm gate không đạt.

Tạo `out`, `data/cvat`, `data/nuscenes` nếu chưa có. Trên Linux, các thư mục CLI
cần quyền ghi của UID 1000; cấp quyền cho đúng thư mục dữ liệu. API đọc export/
dataset ở chế độ chỉ đọc, filesystem chỉ đọc và có `/tmp`.

## Build và chạy CLI

```powershell
docker compose config --quiet
docker compose build pointsnap
docker compose run --rm pointsnap --help
docker compose run --rm pointsnap nuscenes scenes
docker compose run --rm pointsnap nuscenes to-cvat --scene scene-0061
# Tạo task mới, cần PAT có quyền ghi:
docker compose run --rm pointsnap nuscenes to-cvat --scene scene-0061 --upload
# Thay 12 bằng job thử riêng:
docker compose run --rm pointsnap scan --job 12
docker compose run --rm pointsnap gate --job 12
```

Báo cáo/snapshot nằm trong `out`. `--flag` ghi thuộc tính `pointsnap_error`, cần
label có thuộc tính text mutable và `reviewed` checkbox mutable. Đóng job khi
 ghi cờ, phối hợp với annotator và giữ snapshot. Tool chưa có giao dịch GET→PATCH
atomic; không bảo đảm an toàn nếu người khác lưu nhãn đồng thời.

Scanner hiện có floating, size, track, heading, fit và thuộc tính/vòng đời track.
`diff`/khôi phục nhãn tự động chưa triển khai. Gate: 0 đạt theo cấu hình/coverage;
1 vượt ngưỡng hoặc thiếu dữ liệu đã xác định; 3 lỗi đọc/quét. Gate không chứng nhận
sót đối tượng hay độ đúng tuyệt đối của nhãn.

## Report API qua Traefik của CVAT

**Build CLI trước API**. Dockerfile.api dùng nguyên package/dependencies của base
image đã build; không chép code mới lên base cũ. Khi đổi code, build cả hai.
Có thể đặt tag riêng qua `POINTSNAP_CLI_IMAGE` và `POINTSNAP_API_IMAGE` để rollback.

```powershell
docker compose build pointsnap
docker compose build pointsnap_api
docker compose up -d pointsnap_api
docker compose ps pointsnap_api
```

API không publish cổng ra host. Traefik phải ở cùng network và bật Docker provider.
Router Host(`CVAT_HOST`) + PathPrefix(`/pointsnap/`) có priority 100. Các endpoint:

```text
GET /pointsnap/health
GET /pointsnap/jobs/12/report?format=json
GET /pointsnap/jobs/12/report?format=html
GET /pointsnap/jobs/12/report?format=csv
Authorization: Bearer <PAT của người gọi>
```

`Get-Report.ps1 -JobId 12 -Format html` đọc PAT từ `.env` và lưu vào `out`.
Mỗi GET đọc nhãn CVAT đã lưu và quét mới, không sửa nhãn. HTML/CSV là file tải xuống;
response dùng `private, no-store`. Tối đa hai báo cáo đồng thời, quá tải trả 429.
Health chỉ chứng minh API sống, không kiểm quyền PAT/dataset/CVAT hay chất lượng.

Mã HTTP: 200 thành công; 400 format sai; 401 thiếu/sai PAT; 403 không có quyền;
404 không có job/endpoint; 422 job không phải 3D; 429 bận; 502 lỗi upstream CVAT.
JSON có `point_cloud_available`, `point_cloud_note`, counts, findings, checks và
`passed`; đọc cả coverage khi kết luận. PAT chỉ đọc đủ cho report; upload/flag
cần quyền ghi.

## Bằng chứng và giới hạn

[Review 08](../../review/2026-10-10/08-report.md) ghi image IDs, runtime và fixture
đã kiểm; [review 07](../../review/2026-10-10/07-report.md) ghi benchmark/evaluation.
Compose có network/backend/Host phụ thuộc stack CVAT. LAN/HTTPS/proxy đường dẫn,
server BTC và extension MV3 thật cần kiểm riêng. Số test đạt không thay thế nghiệm
thu độ chính xác detector; false-alarm proxy hiện còn vượt mục tiêu.
