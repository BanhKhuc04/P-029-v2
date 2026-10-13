# Kế hoạch review toàn bộ P-029 / PointSnap 3D

Ngày lập: 10/10/2026 (Asia/Saigon).

## Mốc review và cách dùng nhánh

- Mã nguồn gốc: `origin/main`, commit `5dcc97f` (merge PR #37).
- Bộ nhánh hướng dẫn ban đầu dùng main và commit tài liệu chung; kết quả sửa lỗi được commit riêng.
- Thực hiện theo thứ tự 01 → 08. Nhánh kết quả **01 → 02 → 03 → 04 → 05 → 06 → 07 → 08 tiếp nối nhau** có chủ đích; dependency/base PR ghi trong bàn giao. Không coi các nhánh kết quả là độc lập khi mở PR.
- Trạng thái: **01–08 đã review trong phạm vi báo cáo**, ngày11–12/10/2026. [Bàn giao tổng](review/2026-10-10/08-handoff.md) ghi test/artifact/Docker và giới hạn còn mở. Quality proxy còn vượt mục tiêu, precision manual0, MV3 thật/race/LAN/BTC chưa nghiệm thu; không tính ca một phần thành đạt.
- Mỗi phần ghi kết quả vào `review/2026-10-10/NN-report.md` trên nhánh tương ứng. Chỉ commit file của phần đó bằng đường dẫn cụ thể.
- Nhánh kết quả dùng tên không có ngày: `review/01-overview-architecture`, `review/02-core-detectors`, `review/03-data-cvat-integrations`, `review/04-backend-cli-reports`, `review/05-frontend-extension`, `review/06-security-config`, `review/07-tests-evaluation-performance`, `review/08-deployment-docs-final`.
- Theo yêu cầu bàn giao, đẩy từng nhánh; đồng đội mở PR và merge sau review độc lập.

## Review tiếp tính năng mới trên main — 13/10/2026

Đợt 01–08 đã merge qua PR #54, nhưng tính năng mới của main nằm ngoài phạm vi nghiệm thu của đợt đó. [Kế hoạch09–16](review/2026-10-13/REVIEW-PLAN-09-16.md) có64ca/inventory131file. **09–10 đã review/sửa**,10 nhận ancestry09,code10`c5ac54d`:662 Python+37 Node PASS,5 SKIP,0 XFAIL. [Báo cáo09](review/2026-10-13/09-report.md),[báo cáo10](review/2026-10-13/10-report.md)/[bàn giao10](review/2026-10-13/10-handoff.md). Tiếp theo11; quality và kiểm tay còn theo giới hạn từng báo cáo.

## Bộ hướng dẫn chi tiết

Đọc [quy trình chung](review/2026-10-10/README.md) và [mẫu báo cáo](review/2026-10-10/report-template.md). Mỗi hướng dẫn có phạm vi, điểm đọc, ca kiểm tra, bằng chứng, lệnh phù hợp và điều kiện hoàn tất:

1. [01 — Yêu cầu và kiến trúc](review/2026-10-10/01-overview-architecture.md).
2. [02 — Core và detector](review/2026-10-10/02-core-detectors.md).
3. [03 — Dữ liệu và CVAT](review/2026-10-10/03-data-cvat-integrations.md).
4. [04 — Backend, CLI và báo cáo](review/2026-10-10/04-backend-cli-reports.md).
5. [05 — Giao diện và extension](review/2026-10-10/05-frontend-extension.md).
6. [06 — Bảo mật và cấu hình](review/2026-10-10/06-security-config.md).
7. [07 — Kiểm thử, đánh giá và hiệu năng](review/2026-10-10/07-tests-evaluation-performance.md).
8. [08 — Triển khai, tài liệu và tổng hợp](review/2026-10-10/08-deployment-docs-final.md).

Các tài liệu này là kế hoạch thực hiện, không phải chứng nhận các ca đã đạt. Kết quả từng ca được điền trong báo cáo riêng sau khi kiểm tra.

## Thứ tự và phạm vi

| Bước | Nhánh | Phạm vi cần review | Kết quả cần có |
|---|---|---|---|
| 01 | `review/01-overview-architecture` | Toàn bộ cây thư mục; README; đề xuất đề tài; TASKS; CONVENTIONS; nhật ký tuần; problem-backlog; sổ quyết định; giao việc; tài liệu kiến trúc cục bộ. Đối chiếu yêu cầu với luồng nuScenes → CVAT → scan → report → xử lý nhãn. | Đã hoàn tất: [bàn giao ngắn](review/2026-10-10/01-handoff.md), [báo cáo](review/2026-10-10/01-report.md), [kiến trúc](review/2026-10-10/01-architecture.md); 256 pytest và 7 Node đạt. |
| 02 | `review/02-core-detectors` | `pointsnap/core/`, `pointsnap/detectors/`, cấu hình, guidelines. Hệ tọa độ, đơn vị, yaw, ground, box, track, occlusion, ngưỡng và luật phát hiện; tính đúng, trường hợp biên và tính ổn định kết quả. | Đã hoàn tất: [bàn giao](review/2026-10-10/02-handoff.md), [báo cáo](review/2026-10-10/02-report.md), [ma trận luật](review/2026-10-10/02-rule-matrix.md); 321 pytest và 7 Node đạt. Dependency phần 01 được ghi rõ để mở PR đúng phạm vi. |
| 03 | `review/03-data-cvat-integrations` | `pointsnap/adapters/`, `pointsnap/datasets/`, nuScenes/PCD/taxonomy; CVAT client/reader/writer/shapes. Chuyển tọa độ, frame, ID, nội suy, upload/export, đọc–ghi vòng lại, giữ nhãn và thuộc tính. | Hoàn tất: [bàn giao](review/2026-10-10/03-handoff.md), [báo cáo](review/2026-10-10/03-report.md), [mapping](review/2026-10-10/03-mapping.md); 371 pytest + 7 Node. Base phần 02; race sau GET cuối và server BTC chưa nghiệm thu ghi rõ. |
| 04 | `review/04-backend-cli-reports` | `pointsnap/web/` phần Python, `pointsnap/cli/`, `pointsnap/report/`, entrypoint và API báo cáo bổ sung. Quản lý dự án, scan jobs, preview, history, trạng thái tiến trình, đường dẫn, lỗi và xuất báo cáo. | Hoàn tất: [báo cáo](review/2026-10-10/04-report.md), [contracts](review/2026-10-10/04-contracts.md), [bàn giao](review/2026-10-10/04-handoff.md); có parity/CVAT/PAT thật. |
| 05 | `review/05-frontend-extension` | `pointsnap/web/static/`, toàn bộ `extension/`, ảnh và tài nguyên giao diện. Kết nối CVAT, cấu hình, scan, kết quả, lịch sử, điều hướng frame/box, options, messaging, quyền extension; responsive, bàn phím và khả năng tiếp cận. | Kết quả kiểm tra luồng người dùng, bằng chứng giao diện, lỗi đồng bộ trạng thái và tương thích extension. |
| 06 | `review/06-security-config` | Toàn bộ điểm nhận dữ liệu ngoài, HTTP routes, CVAT credentials, lưu secrets, CORS, URL, filesystem, HTML/report, extension permissions, dependencies, cấu hình môi trường và Git ignore. | Findings bảo mật có đường đi dữ liệu và điều kiện khai thác; không đưa token hoặc dữ liệu nhạy cảm vào báo cáo. |
| 07 | `review/07-tests-evaluation-performance` | `tests/`, `extension/tests/`, `pointsnap/eval/`, `scripts/`, CI test workflow, tài liệu đánh giá và auto-tests cục bộ. Tính độc lập của test, synthetic/real data, metrics, split, tái lập, hiệu năng và tài nguyên. | Đã review: [báo cáo07](review/2026-10-10/07-report.md);490pytest+36Node,eval10×10,benchmark;quality proxy chưa đạt mục tiêu. |
| 08 | `review/08-deployment-docs-final` | `pyproject.toml`, đóng gói static assets, cài đặt, `.github/`, Docker/Compose và script PowerShell cục bộ; toàn bộ hướng dẫn và báo cáo. Kiểm tra cài mới, vận hành, backup/khôi phục và đối chiếu tất cả findings 01–07. | Đã review: [báo cáo08](review/2026-10-10/08-report.md),[bàn giao](review/2026-10-10/08-handoff.md);493pytestWindows,486Linux/7skip,package/Docker/operations vàtổng findings. |

## Quy tắc ghi findings và hoàn tất

Mỗi finding cần: mức P0/P1/P2/P3, file và dòng hoặc luồng thao tác, hành vi hiện tại, hành vi mong đợi, tác động, cách tái hiện hoặc bằng chứng, hướng sửa ngắn gọn. Ghi đề xuất riêng nếu chưa có bằng chứng lỗi.

Mỗi báo cáo cần ghi phạm vi đã đọc, kiểm tra đã thực hiện, kết quả và phần chưa xác minh. Review có thể hoàn tất với findings còn mở, nhưng không được ghi “đạt” cho kiểm tra chưa chạy. Mỗi file được Git theo dõi phải có phần review phụ trách; bước 08 đối chiếu danh sách `git ls-files` để phát hiện phần bị bỏ sót.

Nếu sửa mã nguồn, giữ sửa đổi trong đúng nhánh và kèm kiểm tra phù hợp. Những sửa đổi cần kết quả nhánh khác phải nêu dependency cụ thể trong báo cáo/PR. Báo cáo tổng hợp cuối lấy kết quả từ từng nhánh; không giả định chúng đã được merge.

## Các file cục bộ cần review thêm

Tại thời điểm lập kế hoạch, các mục sau chưa được Git theo dõi. Chúng đang có trong checkout dùng chung và không nằm trong commit nền của các nhánh. Khi chuyển nhánh trong cùng checkout, Git thường giữ chúng; checkout/worktree khác sẽ không tự có chúng. Đánh giá chúng riêng với mã nguồn đã có trên GitHub.

Các đường dẫn dưới đây tương đối với `source-tool/pointsnap-3d/`:

- Kiến trúc (01): `ARCHITECTURE.md`, `ARCHITECTURE_DIAGRAMS.md`.
- Backend/báo cáo (04): `pointsnap/api.py`, `Get-Report.ps1` **đã được review và tracked trên nhánh 04**, không còn là file chỉ local của nhánh kết quả.
- Kiểm thử: `tests/test_report_api.py` **đã tracked ở 04**; `auto-tests/` và `docs/checklist-test-thu-cong.md` đã tracked ở07; `docs/test/review-phan-da-push.md` vẫn local, không dùng làm kết quả chạy mới.
- Triển khai (08, bảo mật ở 06): `Dockerfile.api` đã tracked ở06 để explicit bind container. `.dockerignore`, `.env.example`, `Dockerfile`, `compose.yaml`, `README-Docker.md` đã reviewed/tracked ở08; image thử riêng build và kiểm, không redeploy service công việc.
- Bằng chứng hiện có (07/08): `output/pdf/PointSnap-Review-Test-Lan-1-2026-10-10.pdf`. Không coi báo cáo này là kết quả chạy mới.

Ngoài kho Git có `../Start-CVAT-PointSnap.ps1` và `../cvat-develop/`. Bước08 đã làm rõ dependency ngoài và thêm Start-PointSnap.ps1 vào repo để bật Web; CVAT là dependency ngoài, không mở rộng phạm vi thành review toàn bộ mã nguồn CVAT.

Không thêm hàng loạt file cục bộ bằng `git add .`. Không commit dataset, point cloud, token, bản chụp nhãn hoặc output chạy test. Nếu cần đưa một file nguồn cục bộ vào nhánh review, kiểm tra nội dung và thêm riêng file đó.

## Soát lại để merge — 12/10/2026

Xem [báo cáo soát lại 01–08](review/2026-10-10/recheck-01-08-report.md) và bằng chứng theo từng SHA. Các sửa nằm trong chính nhánh kết quả hiện có; đã đồng bộ main `be1778c` để xử lý xung đột, không mở rộng review sang tính năng mới của main. Merge 01 → 08 với merge commit hoặc fast-forward để giữ ancestry; nhánh 08 chứa kết quả cộng dồn.
