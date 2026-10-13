# Phân nhánh để thực hiện review 09–16

**8 nhánh**, làm theo thứ tự **09 → 16**. Cả tám bắt đầu từ commit chuẩn bị trên main `d18b1a9`. Phần **09–11 đã review/sửa và push GitHub**, với ancestry tiếp nối. [Báo cáo 11](11-report.md) / [bàn giao 11](11-handoff.md). Phần 12–16 cần nhận kết quả 11 theo dependency trước khi thực hiện. Các giới hạn quality và kiểm tay được ghi riêng trong báo cáo.

## Chọn phần cần làm

| Phần | Nhánh | Việc chính | Hướng dẫn |
| --- | --- | --- | --- |
| 09 | `codex/review-09-geometry` | Ground/C4, heading, fit, track, ngưỡng mới | [Phần 09](09-geometry.md) |
| 10 | `codex/review-10-spec-scenarios` | ID swap, thuộc tính và luật spec, tình huống thực tế | [Phần 10](10-spec-scenarios.md) |
| 11 | `codex/review-11-verifier-learning` | Static verifier, Box Critic ensemble, học từ kết luận | [Phần 11](11-verifier-learning.md) |
| 12 | `codex/review-12-camera-models` | Chiếu camera, Mask R-CNN, DINO/SAM, hybrid và cache | [Phần 12](12-camera-models.md) |
| 13 | `codex/review-13-missing-objects` | Sót đối tượng LiDAR, vật đứng yên, cam.sparse | [Phần 13](13-missing-objects.md) |
| 14 | `codex/review-14-integration` | Config, CLI/Web, extension, CVAT, gate, bảo mật điểm nối mới | [Phần 14](14-integration.md) |
| 15 | `codex/review-15-evaluation-performance` | Eval, precision tay, báo nhầm, benchmark CPU/GPU | [Phần 15](15-evaluation-performance.md) |
| 16 | `codex/review-16-final` | Đóng gói, tài liệu, inventory, tổng hợp nghiệm thu | [Phần 16](16-final.md) |

Mỗi hướng dẫn có prompt có thể dùng trong chat mới, phạm vi đọc, 8 ca, lệnh test và bộ kết quả cần lưu. [Kế hoạch chung](REVIEW-PLAN-09-16.md) là quy chuẩn; [inventory](scope-inventory.tsv) phân 131 file cho các phần. Các file nguồn dùng chung như config/scanner/track/Web cần bàn giao sửa đổi để phần sau kiểm lại.

## Bắt đầu phần 09

Checkout đang ở nhánh 09 sau khi chuẩn bị. Nếu cần chọn lại:

```powershell
git status --short
git switch codex/review-09-geometry
```

Đọc `09-geometry.md`, thực hiện 8 ca của phần 09 và lưu `09-report.md`, `09-handoff.md` cùng evidence. Nếu còn sửa chưa commit của phần khác, hoàn tất commit đúng phạm vi trước khi chuyển nhánh. Không dùng `git add .`; chọn file cụ thể.

## Sang phần tiếp theo

Ưu tiên hoàn tất phần trước, mở PR vào main và merge sau review, rồi cập nhật phần kế tiếp. Ví dụ khi 09 đã merge:

```powershell
git fetch origin main
git switch codex/review-10-spec-scenarios
git merge origin/main
```

Sau đó thực hiện hướng dẫn phần 10. Áp dụng tương tự đến phần 16. Nếu main có thay đổi khác, đọc diff mới và bổ sung phạm vi trước khi kết luận.

Nếu cần làm phần sau khi phần trước chưa merge, nhập kết quả cần thiết từ nhánh trước bằng merge có kiểm soát, ghi SHA dependency và base PR trong bàn giao. Tránh cherry-pick cả chuỗi hoặc squash các nhánh phụ thuộc mà không kiểm lại diff. Với một người thực hiện, cách tuần tự merge từng phần vào main dễ theo dõi nhất.

## Quy tắc bàn giao và Git

- Mỗi phần: đọc code → tái hiện → sửa có bằng chứng → test tập trung → kiểm dữ liệu/model/giao diện thật cần thiết → báo cáo và bàn giao.
- Thiếu tài nguyên: ghi Bị chặn ở đúng ca, tiếp tục phần còn làm được. PASS/SKIP/XFAIL ghi riêng; thiếu evidence không thành PASS.
- Giữ dataset/model weights/token/output lớn ngoài commit. Evidence đưa vào Git phải là tóm tắt đã kiểm và che dữ liệu nhạy cảm.
- Findings dùng `RV-NN-xxx`, evidence dùng `EV-NN-xxx`; mỗi finding có file/dòng, tác động, tái hiện, sửa, trạng thái.
- Sau khi commit kết quả, có thể push nhánh cụ thể: `git push -u origin codex/review-09-geometry` (đổi đúng tên nhánh đang làm). Việc chuẩn bị hiện tại chỉ tạo nhánh local.
- Không mở nhiều chat sửa cùng checkout đồng thời. Nếu cần chạy song song, dùng checkout/worktree riêng và chia trách nhiệm file chung trước.

## Mẫu prompt bắt đầu ngay

> Thực hiện review phần 09 trên nhánh codex/review-09-geometry. Đọc review/2026-10-13/09-geometry.md và kế hoạch chung; làm đủ 8 ca, sửa lỗi có bằng chứng trong phạm vi phần 09, kiểm lại và lưu báo cáo/bàn giao. Bắt đầu từ ca C4 bằng → dốc còn XFAIL. Ghi rõ ca bị chặn và phần cần tôi kiểm tay.

Prompt cho các phần còn lại có trong hướng dẫn tương ứng. Bộ tài liệu không xác nhận tính năng đã được nghiệm thu.
