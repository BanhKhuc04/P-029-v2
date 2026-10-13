# Kết quả xử lý bàn giao tối 13/10

Model thực hiện review/sửa: **gpt-6.1-sol**. Base main `7ec580a`; code candidate kiểm cuối `3a8bde2`, nhánh `codex/handoff-integration-check`. **Đánh giá 10 vòng đang chạy lại có checkpoint sau khi phiên đầu bị ngắt; báo cáo chưa chốt phần số liệu đó.** Người dùng tự merge; không sửa main và không commit landing/dataset/token/weights/out.

## Các việc đã xử lý lần lượt

| PR (base main) | Kết quả | Trạng thái kiểm |
|---|---|---|
| [#61](https://github.com/AI20K-Build-Phase-Cohort-4A/P-029/pull/61) | Siết hỗ trợ vỉa hè, giữ outlier track đã có bằng chứng | 76 focused tests; tái hiện khôi phục 15 lỗi tay bị veto, đối chiếu 62/62 actionable true. Mốc 16 trong handoff không tái hiện đúng nên ghi chênh lệch |
| [#62](https://github.com/AI20K-Build-Phase-Cohort-4A/P-029/pull/62) | fit.loose tắt mặc định theo quyết định người dùng | Explicit project override vẫn giữ; fixture toggle bật luật rõ ràng |
| [#63](https://github.com/AI20K-Build-Phase-Cohort-4A/P-029/pull/63) | Sửa static_shift bị hard-disable/wiring | 87 tests; scan chỉ luật này 0→8 tuning/8 heldout, chưa human precision |
| [#64](https://github.com/AI20K-Build-Phase-Cohort-4A/P-029/pull/64) | G7 dùng precision tay, proxy báo riêng; review #48 | REPORT_ONLY/UNASSESSED nếu thiếu mẫu; #48 vẫn mở, cần truth trước quyết |
| [#65](https://github.com/AI20K-Build-Phase-Cohort-4A/P-029/pull/65) | Đưa sửa camera review12 lên main-base PR | Cache/version hash, pinned backend/weights, fallback; 9 GPU ảnh smoke |
| [#66](https://github.com/AI20K-Build-Phase-Cohort-4A/P-029/pull/66) | No-ID missing preview/camera | Geometry list/centers3D theo frame; khung tham khảo thật 88 điểm + JPEG |
| [#67](https://github.com/AI20K-Build-Phase-Cohort-4A/P-029/pull/67) | Gộp missing review13, giữ elevation filter, thêm occlusion | 33 tests; 98 deletion targets, current/main cùng 32/47 và 33/51; clean0. Protocol khác mốc handoff nên không gán tăng chất lượng |
| [#68](https://github.com/AI20K-Build-Phase-Cohort-4A/P-029/pull/68) | Ảnh camera extension + sửa generic filter/scope/race | 47 Node PASS; bản mới cần reload/kiểm MV3 thật |
| `codex/handoff-final-review` | Phần14–16, JSON NumPy 500, checks model, runner archive-root, link docs | [14](14-report.md), [15](15-report.md), [16](16-report.md); PR cuối đang hoàn thiện evidence eval |

PR #61–68 hiện có đủ 5 checks SUCCESS mỗi PR (Ubuntu Python3.10/3.11, Windows3.12, artifact, extension). Đây là CI từng PR, không thay test hợp nhất hay dữ liệu/model acceptance. Main tại lần fetch cuối vẫn `7ec580a`.

## Kết quả kiểm cuối

- Windows Python **853 PASS, 1 SKIP**; dataset thật **4 PASS**; live CVAT **3 PASS**.
- Linux base **827 PASS, 33 SKIP**; Node **47 PASS**. Mọi lần cuối **0 FAIL/XFAIL**.
- Wheel/sdist/isolated install/HTTP/static/fonts và Docker CLI/pip check PASS.
- Report API local health JSON200, thiếu PAT401, JSON/HTML/CSV200. **CLI thật và API CSV giống nhau; CLI/Web/API cùng 127 finding, gate/coverage giống nhau; nhãn job4 không đổi checksum**.
- Web dự án thử lưu/đổi hai verdict rồi học phiên bản2 thành công. Hai input này chỉ kiểm cơ chế, không chấm truth/G7.

Log test đầu FAIL được giữ, có kết quả full suite sau sửa thay thế trong [final-checks.json](evidence/16/final-checks.json). Không tính lại test lặp hay SKIP vào số PASS. Exact runtime và 131-file audit: [16-report.md](16-report.md).

## Chưa nghiệm thu

G7 vẫn **UNASSESSED**: thiếu truth ≥20 findings mỗi luật có dữ liệu, ≥40 kết luận từ ≥2 nhóm nguồn độc lập cho học. CSV floating có precision mô tả cao nhưng scene đã dùng chỉnh evidence, không phải validation độc lập. fit.loose tiếp tục off mặc định; project cũ có override true cần chọn lại trong guideline.

Extension mới chưa reload; bước gắn cờ → sửa box → Save → rescan trên job4 chưa được nhận là PASS. Camera/Critic CPU mới, long-scan/OOM và human precision các luật mới còn thiếu. Các ảnh minh họa/số liệu cũ được giữ đúng mốc lịch sử. Xem từng ca PARTIAL trong báo cáo14–16 để tiếp tục nghiệm thu.
