# Bàn giao 07 và 08 — kết thúc đợt review

## Lượt soát lại để merge ngày 12/10/2026

Xem [báo cáo soát lại các nhánh 01–08](recheck-01-08-report.md) và evidence đi kèm.
Bản sửa được đưa vào chính tám nhánh kết quả hiện có. Đã đồng bộ main `be1778c`
để giải quyết xung đột; tính năng mới trên main ngoài phạm vi review.

Merge các nhánh kết quả vào main theo thứ tự **01 → 08**, giữ ancestry bằng merge
commit hoặc fast-forward. Nhánh 08 chứa kết quả cộng dồn 01–07. Các số liệu và
SHA trong phần bàn giao cũ bên dưới là bằng chứng lịch sử, không thay thế kết quả
test các đầu nhánh mới trong báo cáo soát lại.

Đối chiếu 12/10/2026. Các nhánh tiếp nối phần 06 (`6282f05`):

| Phần | Nhánh | Base PR | Kết quả |
|---|---|---|---|
| 07 | `review/07-tests-evaluation-performance` (`5353683`) | `review/06-security-config` | 10 nhóm sửa; 490 pytest +36 Node; eval10 cảnh×10 vòng và benchmark serial |
| 08 | `review/08-deployment-docs-final` | `review/07-tests-evaluation-performance` | 6 nhóm sửa; 493 pytest Windows +36 Node; 486 pytest Linux/7skip; wheel/sdist/Docker/Traefik/restart/backup fixture |

Mở PR07 vào06, PR08 vào07 để giữ đúng phạm vi thay đổi. Chưa merge main hoặc tự
mở PR. Code08 `94dac32`, fixture isolation `79849b4`; metadata ghi đúng source
artifact/image. Commit báo cáo cuối ở đầu nhánh08 chỉ bổ sung tài liệu/evidence.

## Thay đổi chính

- 07 sửa metrics/scope/mẫu số không xác định, metadata/seed/config hash, evaluator
  canonical, synthetic guard, runner và test fixture; Web box lún khuyên nâng.
- 08 sửa manifest tìm theo alias backend/Web của cùng server được khai báo;
  API dùng nguyên base package cùng version. Build CLI trước API.
- Docker/Compose/.env.example/README/launcher được track từng file; wheel/sdist
  đủ config/guideline/static/21fonts. CI thêm matrix và artifact smoke, chưa có run remote.
- Cài đặt/extension/operations phản ánh giới hạn, backup/restart/rollback và không
  phụ thuộc launcher thư mục cha. Inventory và sổ findings có nguồn/SHA/owner.

## Kết quả và giới hạn

Windows493 PASS,0skip/fail; Linux486 PASS,7skip vì container không gắn mini/CVAT
live. Các ca đó đã chạy trên Windows. Node36 PASS. Build3.11 ban đầu timeout PyPI;
retry với timeout dài hơn thành công. Package smoke Windows và Linux đều chạy
ngoài source từ installed package, bảy HTTP routes200.

Eval held-out07: 5440box,194warning/30error → 3,566/0,551 trên100box, còn vượt mục
tiêu. Finding trênGT là proxy; chưa xác minh mọi finding là báo nhầm. Precision
xem tay0mẫu, MV3 thật chưa nghiệm thu, GET→PATCH chưa atomic. LAN/HTTPS/serverBTC,
restore DB CVAT và rollback toàn deployment cần kiểm.

**Hoàn tất review và bàn giao; chưa nghiệm thu/phát hành rộng.** Có thể demo/dùng
CLI/Web/report local trong tổ hợp đã kiểm, với đúng dataset/PAT/coverage và reviewer.

Task/job79 đã xác minh tên trước xóa, GET sau xóa404; container API và PIDs Web
thử đã dọn. Không sửa/xóa task công việc1/8 hoặc container/image đang dùng.
Private images giữ để tái hiện; output/dataset/PAT/payload nhãn không commit.

## Hồ sơ

- [Báo cáo07](07-report.md), [ma trận test07](07-test-matrix.md).
- [Báo cáo08](08-report.md), [tương thích](08-compatibility.md),
  [findings và việc còn mở](08-findings.md), [coverage](08-file-coverage.tsv),
  [checklist vận hành](08-operations-checklist.md), [evidence08](evidence/08/README.md).
- [Cài đặt](../../source-tool/pointsnap-3d/CAI-DAT.md), [Docker](../../source-tool/pointsnap-3d/README-Docker.md),
  [vận hành](../../source-tool/pointsnap-3d/docs/operations.md).
