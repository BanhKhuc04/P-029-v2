# Cải tiến PointSnap hiện có — 14/10/2026

Reviewer: **Codex, agent dựa trên GPT-6**. Phiên không cung cấp ID model triển khai chi tiết. Các artifact cũ ghi gpt-6.1-sol giữ nguyên tác giả và thời điểm cũ.

## Kết luận

**Có những việc cần cải tiến, ưu tiên độ tin cậy và sự nhất quán của bản đang dùng.** Chưa có bằng chứng cần thêm detector, thay model, viết lại kiến trúc hoặc mở rộng nền tảng. Kiến trúc scanner dùng chung cho CLI/Web/Report API vẫn phù hợp với phạm vi hiện tại.

Lượt này rà soát code và bằng chứng đã có, chạy thêm phép đo pipeline read-only và đối chiếu container. Không thay ngưỡng, tính năng, dữ liệu nhãn hoặc model. Hai script mới bên dưới phục vụ kiểm chứng review.

## Phiên bản và trạng thái tích hợp

- `main` đã cập nhật bằng fast-forward tới bản `origin/main` đã tải và xác minh trước đó: **84988ca26598077afa61ea125377e967c24b54c3**. Thư mục `landing/` chưa theo dõi được giữ nguyên.
- Theo lần xác minh GitHub gần nhất, **10/11 PR trong yêu cầu merge đã vào main**: #48, #61–68 và #70. #69 chưa chốt merge. Đây là tiến độ thao tác merge, không phải tỷ lệ hoàn thành toàn dự án.
- Candidate gồm cả #69 là **1a3364bff2e2f0a2afe97a5cab22c54535362348** trên nhánh local `codex/merge-pr69-20261014`. Phần production/tests/scripts/extension tương đương candidate kiểm tích hợp `bd58da09f33fdae08430e234d2ca11811acc4438`; commit tiếp theo chỉ bổ sung báo cáo.
- Head #69 cuối đã push thành công là `bc3e199`; commit chuẩn hóa JSON `1a3364b` chưa push được. Kết nối GitHub CLI/Git HTTPS bị lỗi chuỗi chứng chỉ **Vingroup Web Gateway**, `SEC_E_UNTRUSTED_ROOT`/`x509: certificate signed by unknown authority`. Không sửa kho CA hoặc tắt kiểm chứng TLS. Vì vậy chưa xác minh lại CI/head/main trên server ở thời điểm kết thúc lượt này.
- Kênh đọc CI qua backend cũng chưa dùng được vì tài khoản GitHub chưa kết nối với connector đó. Trạng thái CI cuối không được suy từ test local.

## Thứ tự cải tiến

| Ưu tiên | Điểm cần cải tiến và bằng chứng | Việc cụ thể trên chức năng hiện có | Điều kiện nghiệm thu |
|---|---|---|---|
| **P1 — chất lượng phát hiện** | G7 vẫn **UNASSESSED**. Verdict floating có 68 Đúng/2 FP/25 Không rõ/4 chưa chấm; size chỉ 1 mục có kết luận. Nhiều luật chưa có mẫu tay. Baseline 10 cảnh ×10 vòng được đo **trước #48**; không đại diện độ chính xác cấu hình mới. | Khóa snapshot/config/source; đo lại sau #48; chấm Đúng/FP/Không rõ theo từng luật, ưu tiên fit.outside, heading và track. Giữ fit.loose tắt mặc định theo quyết định người dùng. Không tiếp tục chọn ngưỡng từ tập đã dùng đánh giá. | Có bảng precision tay, số mẫu có kết luận/Không rõ, độ phủ và nguồn dữ liệu cho từng luật cần nghiệm thu; so mục tiêu ≥70% đã có của dự án. Proxy và recall lỗi chèn báo riêng. Chưa đủ mẫu/phạm vi thì giữ UNASSESSED. |
| **P1 — đồng bộ bản chạy** | Probe mới xác nhận container `pointsnap-api:handoff-final` khác mã main/candidate ở cấu hình fit. Container đang dùng ngưỡng outside 0,5 và minimum 30 chung; main đã tách 30 điểm vật/15 điểm ngoài và ngưỡng 0,4. API trong container lại có bản sửa #69, trong khi main đã fetch chưa có. Extension cài đặt chưa được xác minh hash bản mới. | Hoàn tất #69, chọn một commit chuẩn, build/reload bộ đang có rồi kiểm lại cùng snapshot và guideline. Ghi commit/config hash và image digest vào hồ sơ phát hành hiện có. Không cần xây một hệ thống triển khai mới. | CLI/Web/API đồng nhất khi cùng input/config; extension đúng source #68; vòng tìm lỗi → chọn box → gắn cờ → sửa → Save → quét lại đạt trên task thử. Không coi source merge là deployment đã cập nhật. |
| **P1 — độ ổn định khi ghi cờ đồng thời** | `_patch_if_unchanged` có GET kiểm thay đổi ngay trước PATCH, nhưng hai request vẫn tách biệt; patch chứa cả dữ liệu shape/track. Đây là khoảng tranh chấp còn lại từ code, **chưa phải bằng chứng mất dữ liệu trên CVAT thật**. | Kiểm hai client cùng sửa một task thử giữa GET/PATCH; xác minh cơ chế kiểm version phía CVAT và dùng điều kiện đó nếu được hỗ trợ. Khi phát hiện xung đột, yêu cầu quét lại. Giữ snapshot và phép kiểm geometry hiện có. | Ca sửa đồng thời bị từ chối an toàn hoặc giữ được thay đổi của người khác; geometry/attributes khác cờ không bị ghi đè. Kiểm trên task tạm, không dùng job đang gán nhãn để thử xung đột. |
| **P2 — độ rõ ràng của Web/extension** | `index.html` còn câu “Chạy 3 bộ phát hiện”, trong khi scanner chọn tới 10 nhóm theo công tắc. Sidebar Kết quả cộng Lỗi+Cảnh báo, danh sách Tất cả tính thêm Thông tin; quan sát cũ có 20 và 123, dễ hiểu nhầm. Camera source đã có #68 nhưng bản cài trước đó chưa có nút. | Sửa câu chữ theo các luật đang bật; ghi rõ ý nghĩa bộ đếm; rút gọn giải thích cấu hình ngay trong form có sẵn. Nạp đúng extension và kiểm camera/filter trước khi sửa UI thêm. | Bộ đếm tự giải thích được, câu tiến độ khớp cấu hình; ảnh camera đúng frame/box. Annotator mới hoàn tất luồng chính, ghi chỗ cần trợ giúp và thời gian thực tế; chưa có số đo thì không tuyên bố đạt usability. |
| **P2 — hiệu năng có kiểm chứng** | Probe mới: 3333 box/39 frame, quét 30,77 s và chạy lại 30,66 s. Memo thử giảm đọc point cloud **125→39**, metadata **232→39**, nhưng thời gian chỉ còn **29,85 s**, giữ thêm **27.082.240 byte** điểm. Kết quả finding có cùng hash trong cả ba lượt. | Đo thời gian từng bước và RAM trên workload hiện có trước; ưu tiên nút thắt thực. Nếu dùng cache, giới hạn dung lượng và tách metadata/points; kiểm đầu ra không đổi. Chưa có lý do đưa cache toàn cảnh không giới hạn vào production chỉ từ phép thử này. | Benchmark lặp trên tập/cấu hình đã khóa, báo median/p95 và peak RAM; finding/gate tương đương; không tăng RAM quá ngân sách. Mức giảm khoảng 3% một lần này chưa phải cam kết nhanh hơn toàn sản phẩm. |

Nguồn: [verdict summary](../2026-10-13/evidence/handoff-04/manual-summary.json), [review G7](../2026-10-13/handoff-04-g7-report.md), [baseline trước #48](evaluation-before-fit-tuning.json), [review UX](architecture-ux-review.md), [scanner](../../source-tool/pointsnap-3d/pointsnap/core/scanner.py), [writer](../../source-tool/pointsnap-3d/pointsnap/adapters/cvat/writer.py), [Web](../../source-tool/pointsnap-3d/pointsnap/web/static/index.html).

## Phép đo mới và giới hạn

### Pipeline và thử cache

[improvement-scan.json](evidence/improvement-scan.json) ghi config hash, commit, số lượt đọc, thời gian và hash finding. Chạy từ repo root:

```powershell
python review/2026-10-14/evidence/improvement_probe.py --dataset D:/Vin_uni/data/nuscenes --out <file-moi.json>
```

Thứ tự normal → memo thử → normal lặp. Cùng 156 finding, hash `6a613dfa7f05a9ea63a2cf4a3e7f9ec69414c054bb3ddfafb44949e9471cc1d2`. Dữ liệu là nhãn nuScenes trực tiếp; không phải snapshot CVAT của lượt UX trước. Camera tắt, Critic không có model. Bộ đệm của hệ điều hành, thứ tự chạy và một cảnh khiến số thời gian chỉ có tính thăm dò; số byte chỉ là mảng điểm giữ lại, không phải tổng RAM của process. Memo chỉ tồn tại trong script thử, chưa sửa sản phẩm. Không gọi 156 finding là 156 lỗi thật hoặc suy precision từ đó.

### Container đang chạy

[improvement-runtime.json](evidence/improvement-runtime.json) so hash LF của `api.py`, `config.yaml`, `core/scanner.py`, `detectors/missing.py` giữa container, main đã fetch và candidate. Chạy lại read-only:

```powershell
python review/2026-10-14/evidence/improvement_runtime_probe.py --out <file-moi.json>
```

Bốn file lấy mẫu đủ chứng minh có khác biệt, chưa chứng nhận toàn bộ image/source. Giá trị fit là **mặc định package**, không thay thế guideline hiệu lực của từng project. Probe không đọc token, không rebuild/restart container và không ghi CVAT.

## Đã kiểm và còn mở

[Bản hợp nhất đã kiểm](merge-validation.json): **859 ca Python PASS +3 ca live CVAT PASS =862 ca khác nhau**, **47 ca Node PASS**, Web JavaScript qua syntax check. Ba live case dùng task tạm và cleanup. Lượt đầu Docker tắt bị FAIL môi trường; lượt bị ngắt không có XML không được tính PASS. Lượt audit mới chạy hai probe thành công; không cần chạy lại toàn suite vì chỉ thêm tài liệu/script đo độc lập, không đổi mã sản phẩm.

GPU pretrained smoke/cache của ba mode ảnh đã có bằng chứng lịch sử; chưa có precision tay đầy đủ, fresh CPU pretrained/scan dài/OOM acceptance. Những việc này là kiểm độ vững của các model đang có, chưa cần đổi sang model mới.

Trạng thái dự án: code và test tích hợp có nền tảng sử dụng local; **G7 chưa nghiệm thu, G8 còn một phần**. Nên thực hiện lần lượt: **chốt phiên bản → chấm chất lượng → kiểm vòng sửa trên bản cài → chỉnh câu chữ UX → tối ưu điểm đã đo**. Chưa lấy tỷ lệ PASS hoặc tỷ lệ merge để công bố phần trăm hoàn thành toàn dự án.
