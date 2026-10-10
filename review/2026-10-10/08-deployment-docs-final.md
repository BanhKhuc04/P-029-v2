# 08 — Review triển khai, tài liệu và tổng hợp cuối

**Nhánh:** `review/2026-10-10/08-deployment-docs-final`.
**Trạng thái:** chưa thực hiện; cần báo cáo đã commit của 01–07 để kết luận tổng thể.
**Đầu ra sẽ tạo:** `08-report.md`, ma trận tương thích/cài mới, sổ tổng findings, checklist vận hành và kết luận theo phạm vi đã xác minh.

Đọc [quy trình chung](README.md), [mẫu báo cáo](report-template.md). Đây là phần đối chiếu toàn đợt, bao gồm khả năng chạy từ checkout sạch và cách vận hành thực tế. Đường dẫn dưới đây tính từ tool root, trừ mục nêu rõ kho Git hoặc thư mục cha.

## 1. Mục tiêu và điều kiện đầu vào

- Người mới có thể cài đúng từ hướng dẫn, thấy rõ thành phần nào có trên GitHub và thành phần nào chỉ có local.
- Artifact cài bằng package chứa đủ config/guideline/static/fonts và chạy được entry points.
- Các bước CVAT/nuScenes/Web/extension/Docker, quyền token và mounts/network phù hợp mô hình sử dụng đã chốt ở 06.
- Báo cáo cuối truy vết mọi file/yêu cầu/finding, không biến tiến độ code hoặc test mock thành nghiệm thu end-to-end.

Cần SHA và giới hạn của từng báo cáo 01–07. Nếu phần chưa hoàn tất, vẫn làm kiểm tài liệu/packaging độc lập; kết luận tổng thể ghi Bị chặn hoặc Chưa xác minh cho phạm vi phụ thuộc đó.

## 2. Phạm vi

| Nhóm | Files/thành phần | Trọng tâm |
|---|---|---|
| Packaging | `pyproject.toml`, package init/main, package-data và assets | Python/dependencies/entry points, wheel/sdist, assets trong package đã cài |
| Cài đặt | `../CAI-DAT.md`, `../README.md`, extension README, hướng dẫn giao việc | Hướng dẫn hiện hành, quyền token, dataset/sweeps và update/reload |
| CI | `.github/workflows/test.yml` ở kho Git | Test đúng commit/artifact, Python/Node, Windows/Linux, skip và thiếu gate |
| Docker local | `Dockerfile`, `Dockerfile.api`, `compose.yaml`, `.dockerignore`, `README-Docker.md`, `.env.example` | Build order, base image, code overlay, non-root, network/Traefik, read-only/tmpfs/mounts |
| Script local | `Get-Report.ps1`; `../Start-CVAT-PointSnap.ps1` và `../cvat-develop/` tính từ kho Git | Đường dẫn máy, token handling, thứ tự khởi động; CVAT là dependency ngoài |
| Tài liệu toàn kho | README/backlog/quyết định/nhật ký/TASKS/giao-viec/docs, bộ hướng dẫn này | Links, version/status, metadata kết quả và nội dung chưa triển khai |

Các Docker/API/script local chưa thuộc mã nguồn nền `5dcc97f`. Không ghi “clone GitHub là có Docker/report API” trước khi chúng thật sự được đưa vào commit phù hợp và xác minh trên checkout sạch.

## 3. Trình tự

1. Thu thập báo cáo từ đúng branch/SHA, hợp nhất findings theo mã chính và giữ nguồn bằng chứng.
2. Đối chiếu inventory nền 184 file với `git ls-tree -r --name-only 5dcc97f`; bổ sung file mới của đợt review/feature vào bảng phụ.
3. Kiểm hướng dẫn cài từ đầu trên môi trường riêng, làm đúng từng bước; ghi mọi bước phải đoán hoặc phụ thuộc file máy cũ.
4. Kiểm package đã cài từ artifact ngoài working tree để phát hiện thiếu static/config/font.
5. Kiểm Docker/Compose khi các file local được đưa vào phạm vi; xác minh mạng CVAT và build base image trước API.
6. Kiểm vận hành restart, dữ liệu project/run, backup/restore và update; không sử dụng dữ liệu công việc thật làm fixture.
7. Chốt ma trận tương thích, yêu cầu chưa đủ bằng chứng, findings mở và quyết định sử dụng/phát hành.

## 4. Checklist cài đặt và artifact

| Mã | Ca | Mong đợi / bằng chứng |
|---|---|---|
| R08-01 | Checkout sạch từ commit được review | Có đúng files/commands mô tả; file local được đánh dấu; không phụ thuộc .venv/data của máy tác giả |
| R08-02 | Python/CVAT/Node/browser compatibility | Phân biệt requires-python>=3.10, CI3.11, Docker3.12 và CVAT2.77.0/2.77.1 notes; ghi tổ hợp đã kiểm |
| R08-03 | Cài editable và artifact | Chạy CLI/UI/config; distribution có đủ package-data; ghi file thiếu/đường dẫn phụ thuộc cwd |
| R08-04 | Static/fonts/guidelines trong package | Load index/app/styles/fonts/spec-vn sau cài ngoài repo; không dựa vào source tree còn trên sys.path |
| R08-05 | Token đọc/ghi và upload/flag | Hướng dẫn phân biệt quyền GET với tạo task/flag; kiểm lỗi read-only đã có ở báo cáo Chiến |
| R08-06 | Dataset layout/manifest/sweeps và disk/RAM | Đúng prerequisite, đường dẫn Windows/Linux và dung lượng; thiếu dữ liệu có cách phát hiện |
| R08-07 | Web và extension cài mới/update | Reload extension/trang khi cần; host/quyền và endpoint rõ; hướng dẫn trùng hành vi 05 |
| R08-08 | CLI diff/restore/fix và giới hạn detector | Chưa triển khai/ngoài phạm vi được ghi; không quảng bá missing-object hoặc auto-fix đã có |

## 5. Checklist Docker và vận hành

| Mã | Ca | Mong đợi / bằng chứng |
|---|---|---|
| R08-09 | Build CLI base và Dockerfile.api | Dockerfile.api FROM `pointsnap:0.1.0` có base phù hợp; build order/cache/source overlay được ghi và kiểm |
| R08-10 | Compose network `cvat_cvat` / backend `cvat-server` | Tên mạng/alias đúng trên stack thử; không giả định mọi CVAT clone có cấu hình đó |
| R08-11 | Traefik router /pointsnap và Web URL | Routing/priority/health đúng; CVAT backend URL khác URL link người dùng được phân biệt |
| R08-12 | UID/non-root, mounts, read_only/tmpfs | Service đọc/ghi được nơi cần; manifest/dataset paths khớp bên container; secret/build context phù hợp 06 |
| R08-13 | API PAT/report formats/health/concurrency | 200/error theo contract 04, không cache nhầm caller, giới hạn 2 report thực tế được kiểm; health có phạm vi rõ |
| R08-14 | Restart Web/API/CVAT | History persisted đúng, scan dở và bridge memory có giới hạn; không mất dữ liệu đã cam kết lưu |
| R08-15 | Backup/restore project config/secrets/runs | Backup thử không đưa secrets vào Git; restore đúng project và liên kết dataset/CVAT; có bằng chứng phục hồi |
| R08-16 | Update/rollback với code/config cũ | Ghi quy trình theo commit/image/config, migration có/không; bản rollback đọc được dữ liệu theo giới hạn đã kiểm |
| R08-17 | Launcher PowerShell và paths cố định | Chạy từ máy/thư mục khác theo hướng dẫn; không yêu cầu đường dẫn cá nhân chưa mô tả |

## 6. Checklist tổng hợp và tài liệu

| Mã | Ca | Mong đợi / bằng chứng |
|---|---|---|
| R08-18 | Coverage file và yêu cầu | Mỗi file nền/new file có phần phụ trách và mức đã kiểm; asset/generated không bị coi là đã review code |
| R08-19 | Findings trùng/liên nhánh | Một mã chính, nguồn bằng chứng/SHA và owner; dependency không bị bỏ khi branches độc lập |
| R08-20 | Báo cáo/README/TASKS/nhật ký | Trạng thái hiện hành có ngày/commit; snapshot lịch sử có nhãn; links tương đối resolve đúng |
| R08-21 | Số liệu hiệu quả/quality/benchmark | Dùng số liệu 07 đã tái lập hoặc ghi rõ lịch sử; ước lượng pain point khác kết quả đo tool |
| R08-22 | Nghĩa của gate và dữ liệu thiếu | Kết luận phù hợp quyết định 01 và triển khai 04/05; cảnh báo/coverage không bị tài liệu bỏ qua |
| R08-23 | Bộ hồ sơ bàn giao | Báo cáo/test/metrics/demo/video/slide có thực sự tồn tại không; thiếu thì ghi chưa có, không suy ra từ TASKS |
| R08-24 | Kết luận sử dụng/phát hành | Findings P0/P1 và ca bị chặn được xử lý hoặc có quyết định/phạm vi chấp nhận rõ; không ghi đạt toàn diện khi chỉ test local/mock |

## 7. Lệnh tham khảo

Từ tool root, sau prerequisite:

```powershell
python -m pip check
python -m pointsnap --help
python -m pytest -q
```

Docker local có mặt, kiểm cấu hình mà không in env/token:

```powershell
docker compose version
docker compose config --quiet
docker network inspect cvat_cvat --format '{{.Name}}'
```

Build/smoke test thực hiện trong môi trường riêng sau kiểm files/mounts/base image. Có thể build CLI trước bằng `docker build -t pointsnap:0.1.0 .`, rồi build service API bằng `docker compose build pointsnap_api`; ghi image IDs và source commit. Không coi compose config hoặc build thành công là service đã chạy end-to-end.

Kiểm wheel dùng môi trường build riêng và công cụ build sẵn có hoặc pip wheel phù hợp; cài artifact vào môi trường khác source tree rồi chạy CLI/UI/static. Ghi lệnh thực tế, artifact/checksum và môi trường; không thêm dependency runtime chỉ để thực hiện review.

## 8. Bảng tổng hợp cần bàn giao

| Finding | Nhánh nguồn / SHA | Mức | Trạng thái | Commit sửa / bằng chứng kiểm lại | Owner | Tác động phạm vi sử dụng |
|---|---|---|---|---|---|---|
| Chưa tổng hợp | Chưa điền | Chưa đánh giá | Chưa điền | Chưa có | Chưa điền | Chưa đánh giá |

| Tổ hợp môi trường | Cài mới | CLI/Web | CVAT round-trip | Extension | Package/Docker | Giới hạn |
|---|---|---|---|---|---|---|
| Chưa kiểm | Chưa chạy | Chưa chạy | Chưa chạy | Chưa chạy | Chưa chạy | Chưa xác minh |

## 9. Hoàn tất

- [ ] Mọi báo cáo 01–07 có SHA/trạng thái và được tham chiếu đúng; phần thiếu chặn kết luận tương ứng.
- [ ] Coverage inventory đủ file nền và file mới; root/shared docs được gán review tài liệu.
- [ ] Cài mới/artifact/runtime có bằng chứng hoặc trạng thái Bị chặn; ma trận tương thích không dựa vào suy đoán.
- [ ] Findings mở có owner, ưu tiên, việc tiếp theo và phạm vi sử dụng bị ảnh hưởng.
- [ ] README/CAI-DAT/kiến trúc/số liệu đã đồng bộ khi thay đổi, hoặc có finding chưa xử lý.
- [ ] `08-report.md` kết luận riêng: hoàn tất review, sẵn sàng demo, sẵn sàng dùng local, sẵn sàng chia sẻ/phát hành; mỗi mức chỉ ghi khi có điều kiện/bằng chứng hỗ trợ.
