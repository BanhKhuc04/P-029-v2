# Kế hoạch review toàn bộ P-029 / PointSnap 3D

Ngày lập: 10/10/2026 (Asia/Saigon).

## Mốc review và cách dùng nhánh

- Mã nguồn gốc: `origin/main`, commit `5dcc97f` (merge PR #37).
- Bộ nhánh hướng dẫn ban đầu dùng main và commit tài liệu chung; kết quả sửa lỗi được commit riêng.
- Thực hiện theo thứ tự 01 → 08. Nhánh kết quả **02 tiếp nối 01, 03 tiếp nối 02** có chủ đích; dependency/base PR ghi trong bàn giao. Không coi ba nhánh kết quả là độc lập khi mở PR.
- Trạng thái: **01–03 đã hoàn tất review trong phạm vi báo cáo; 04–08 chưa thực hiện**. 03 đạt 367 pytest + 7 Node, có CVAT/dataset/browser thật; giới hạn đồng thời và server BTC được ghi rõ.
- Mỗi phần ghi kết quả vào `review/2026-10-10/NN-report.md` trên nhánh tương ứng. Chỉ commit file của phần đó bằng đường dẫn cụ thể.
- Nhánh kết quả dùng tên không có ngày: `review/01-overview-architecture`, `review/02-core-detectors`, `review/03-data-cvat-integrations`.
- Theo yêu cầu bàn giao, đẩy từng nhánh; đồng đội mở PR và merge sau review độc lập.

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
| 03 | `review/03-data-cvat-integrations` | `pointsnap/adapters/`, `pointsnap/datasets/`, nuScenes/PCD/taxonomy; CVAT client/reader/writer/shapes. Chuyển tọa độ, frame, ID, nội suy, upload/export, đọc–ghi vòng lại, giữ nhãn và thuộc tính. | Hoàn tất: [bàn giao](review/2026-10-10/03-handoff.md), [báo cáo](review/2026-10-10/03-report.md), [mapping](review/2026-10-10/03-mapping.md); 367 pytest + 7 Node. Base phần 02; race sau GET cuối và server BTC chưa nghiệm thu ghi rõ. |
| 04 | `review/2026-10-10/04-backend-cli-reports` | `pointsnap/web/` phần Python, `pointsnap/cli/`, `pointsnap/report/`, entrypoint và API báo cáo cục bộ. Quản lý dự án, scan jobs, preview, history, trạng thái tiến trình, đường dẫn, lỗi và xuất báo cáo. | Review luồng backend/CLI/report đầu cuối, API contract, xử lý lỗi và nhiều yêu cầu đồng thời. |
| 05 | `review/2026-10-10/05-frontend-extension` | `pointsnap/web/static/`, toàn bộ `extension/`, ảnh và tài nguyên giao diện. Kết nối CVAT, cấu hình, scan, kết quả, lịch sử, điều hướng frame/box, options, messaging, quyền extension; responsive, bàn phím và khả năng tiếp cận. | Kết quả kiểm tra luồng người dùng, bằng chứng giao diện, lỗi đồng bộ trạng thái và tương thích extension. |
| 06 | `review/2026-10-10/06-security-config` | Toàn bộ điểm nhận dữ liệu ngoài, HTTP routes, CVAT credentials, lưu secrets, CORS, URL, filesystem, HTML/report, extension permissions, dependencies, cấu hình môi trường và Git ignore. | Findings bảo mật có đường đi dữ liệu và điều kiện khai thác; không đưa token hoặc dữ liệu nhạy cảm vào báo cáo. |
| 07 | `review/2026-10-10/07-tests-evaluation-performance` | `tests/`, `extension/tests/`, `pointsnap/eval/`, `scripts/`, CI test workflow, tài liệu đánh giá và auto-tests cục bộ. Tính độc lập của test, synthetic/real data, metrics, split, tái lập, hiệu năng và tài nguyên. | Lệnh chạy, môi trường, số pass/fail/skip; khoảng trống kiểm thử; đo hiệu năng trên dữ liệu xác định; phân biệt bằng chứng cũ và kết quả chạy mới. |
| 08 | `review/2026-10-10/08-deployment-docs-final` | `pyproject.toml`, đóng gói static assets, cài đặt, `.github/`, Docker/Compose và script PowerShell cục bộ; toàn bộ hướng dẫn và báo cáo. Kiểm tra cài mới, vận hành, backup/khôi phục và đối chiếu tất cả findings 01–07. | Checklist vận hành, tài liệu sai/thiếu, bảng tổng hợp ưu tiên sửa, phần còn bị chặn; đánh giá hoàn tất dựa trên bằng chứng. |

## Quy tắc ghi findings và hoàn tất

Mỗi finding cần: mức P0/P1/P2/P3, file và dòng hoặc luồng thao tác, hành vi hiện tại, hành vi mong đợi, tác động, cách tái hiện hoặc bằng chứng, hướng sửa ngắn gọn. Ghi đề xuất riêng nếu chưa có bằng chứng lỗi.

Mỗi báo cáo cần ghi phạm vi đã đọc, kiểm tra đã thực hiện, kết quả và phần chưa xác minh. Review có thể hoàn tất với findings còn mở, nhưng không được ghi “đạt” cho kiểm tra chưa chạy. Mỗi file được Git theo dõi phải có phần review phụ trách; bước 08 đối chiếu danh sách `git ls-files` để phát hiện phần bị bỏ sót.

Nếu sửa mã nguồn, giữ sửa đổi trong đúng nhánh và kèm kiểm tra phù hợp. Những sửa đổi cần kết quả nhánh khác phải nêu dependency cụ thể trong báo cáo/PR. Báo cáo tổng hợp cuối lấy kết quả từ từng nhánh; không giả định chúng đã được merge.

## Các file cục bộ cần review thêm

Tại thời điểm lập kế hoạch, các mục sau chưa được Git theo dõi. Chúng đang có trong checkout dùng chung và không nằm trong commit nền của các nhánh. Khi chuyển nhánh trong cùng checkout, Git thường giữ chúng; checkout/worktree khác sẽ không tự có chúng. Đánh giá chúng riêng với mã nguồn đã có trên GitHub.

Các đường dẫn dưới đây tương đối với `source-tool/pointsnap-3d/`:

- Kiến trúc (01): `ARCHITECTURE.md`, `ARCHITECTURE_DIAGRAMS.md`.
- Backend/báo cáo (04): `pointsnap/api.py`, `Get-Report.ps1`.
- Kiểm thử (07): `tests/test_report_api.py`, `auto-tests/`, `docs/checklist-test-thu-cong.md`, `docs/test/review-phan-da-push.md`.
- Triển khai (08, bảo mật ở 06): `.dockerignore`, `.env.example`, `Dockerfile`, `Dockerfile.api`, `compose.yaml`, `README-Docker.md`.
- Bằng chứng hiện có (07/08): `output/pdf/PointSnap-Review-Test-Lan-1-2026-10-10.pdf`. Không coi báo cáo này là kết quả chạy mới.

Ngoài kho Git có `../Start-CVAT-PointSnap.ps1` và `../cvat-develop/`. Bước 08 kiểm tra cách dự án phụ thuộc vào launcher/CVAT này; CVAT là dependency ngoài, không mở rộng phạm vi thành review toàn bộ mã nguồn CVAT.

Không thêm hàng loạt file cục bộ bằng `git add .`. Không commit dataset, point cloud, token, bản chụp nhãn hoặc output chạy test. Nếu cần đưa một file nguồn cục bộ vào nhánh review, kiểm tra nội dung và thêm riêng file đó.
