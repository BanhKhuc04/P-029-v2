# Review 16 — Đóng gói và giới hạn nghiệm thu

Model review **gpt-6.1-sol**. Base main `7ec580a`; code hợp nhất được kiểm cuối `3a8bde275a0ecd574eda2dc0275e07c768c34829`. Nhánh test là `codex/handoff-integration-check`; mã vẫn nằm trong PR riêng, người dùng tự merge. Mốc test đầu `0198d0a` được giữ làm lịch sử lỗi, không ghi đè thành xanh.

## Gate kiểm thử phần mềm

| Pha | PASS | FAIL | SKIP | XFAIL | Phạm vi |
|---|---:|---:|---:|---:|---|
| Windows Python cuối | 853 | 0 | 1 | 0 | `tests` + `auto-tests`, tách dataset và live CVAT |
| Dataset thật | 4 | 0 | 0 | 0 | nuScenes mini; gồm ground test bị skip trong unit |
| Live CVAT | 3 | 0 | 0 | 0 | Task thử do test tạo; flag/clear/nhãn; task đã xóa |
| Linux base Python cuối | 827 | 0 | 33 | 0 | Không vision/dataset/CVAT; optional dependency và dữ liệu được skip rõ |
| Node extension | 47 | 0 | 0 | 0 | Logic/source VM; không thay nghiệm thu MV3 đã cài |

Wheel/sdist build, cài wheel trong venv mới ngoài source, `pip check`, HTTP/static/font/API smoke, Docker CLI và `pip check` đều PASS. Base wheel dùng FastAPI 0.143.0; môi trường Windows vision có FastAPI 0.142.2. Linux Python **3.11.17**; Windows **3.11.9**. Không suy thành đã kiểm tất cả Python/OS/dependency combinations.

Full runner ban đầu vẫn giữ **17 FAIL Python** và **27 FAIL Linux** trong log: 16 fixture luật mặc định, một fixture details list, sáu camera tests thiếu Pillow, bốn runner archive-root import. Sửa fixture bật luật rõ ràng, giữ assertion độc lập; geometry list là hành vi mới chủ ý; Pillow optional được skip; runner tìm repo root và hoạt động trong archive. Sau đó chạy full suites lại; hai regression NumPy JSON và hai checks-eligibility mới cũng PASS. [EV-16-001](evidence/16/final-checks.json) lưu cả lỗi đầu và kết quả thay thế, hash log; không cộng các lần chạy lặp thành số test mới.

## Kết quả 8 ca

| Ca | Trạng thái | Kết luận |
|---|---|---|
| TC-16-001 | PASS structural, PARTIAL deep/visual audit | EV-16-002 có đúng 131 đường dẫn duy nhất, owner, tồn tại/hash, kết luận từng file. Ba path đã xóa là có chủ ý; không báo thiếu module. Không nhận là 131 deep review mới độc lập hay đã tái sinh tất cả ảnh. |
| TC-16-002 | PASS phạm vi đường dẫn/lệnh đã kiểm | Sửa 8 link sau chuyển thư mục và checkout hướng dẫn đã lỗi thời; thêm đầu mối report hiện hành. Package entrypoint/HTTP thật ngoài source chạy được. |
| TC-16-003 | PARTIAL | Base không vision cài trong venv/container riêng PASS; GPU vision hiện có chạy 3 model pretrained/3 ảnh mỗi model. Chưa cài mới vision CPU và chưa kiểm mọi phiên bản CUDA/torch. |
| TC-16-004 | PASS môi trường đã ghi | Wheel/sdist sạch từ Git HEAD, fonts/static/config/guidelines/module có trong gói, HTTP smoke ngoài checkout PASS; Linux base 827 PASS. Learn/camera/missing route và fallback có unit/regression; camera runtime GPU có probe riêng. |
| TC-16-005 | PARTIAL | Tách snapshot cũ, nguồn mới gắn SHA/config/seed/split. Hình cũ giữ là minh họa, không phải proof bản mới; chưa tái tạo mọi hình và số liệu lịch sử thiếu raw metadata. |
| TC-16-006 | PASS về minh bạch, chưa nghiệm thu chất lượng | Full suite 0 XFAIL; C4 số cũ đã gắn mốc lịch sử. G7 dùng precision tay từng luật, proxy riêng; missing/camera/heading/track chưa đủ truth và mẫu độc lập. |
| TC-16-007 | PASS tổng hợp trạng thái | Sổ dưới đây liên kết findings 01–16 và PR sửa; giữ lỗi source, chất lượng, môi trường, giới hạn protocol riêng. |
| TC-16-008 | PASS kiểm thử tự động; PARTIAL nghiệm thu rộng | Bảng counts ở trên + pretrained GPU + dataset/CVAT + Web review/learn + Report API job 4 thật. New installed MV3, full Save/rescan và human precision còn thiếu; không gọi toàn sản phẩm đã nghiệm thu. |

## Findings cuối

- **RV-16-001 — Đã sửa/xác minh (`afc1b84`):** `auto-tests/run_all.py` dùng `ROOT.parents[2]`, import trong Docker archive `/source` gây IndexError. Tìm ancestor chứa `.git`, fallback ROOT khi chỉ import helper. Runner tests và Linux full suite xác minh.
- **RV-16-002 — Đã sửa:** 8 link tài liệu hỏng vì source-tool chuyển vào pointsnap-3d; hướng dẫn checkout nhánh review08 đã cũ. Sửa CAI-DAT, danh-gia, de-xuat và thêm report hiện hành; audit lại từng path.
- **RV-16-003 — Giới hạn mở:** cấu hình dependency không pin mọi phiên bản; base install mới và environment vision dùng phiên bản khác nhau. Đã ghi exact runtime và chạy test cả hai môi trường thực tế, không tuyên bố ma trận rộng.

## Sổ hợp nhất và điều kiện sử dụng

| Phạm vi | Trạng thái | Evidence/owner và điều kiện |
|---|---|---|
| Review 01–08 | Đã merge, regression giữ | [Bàn giao 08](../2026-10-10/08-handoff.md); giới hạn security/local deployment/human precision cũ được kiểm lại theo scope mới, không xóa lịch sử |
| Review 09–11 | Đã merge, full regression 0 XFAIL | [09](09-report.md), [10](10-report.md), [11](11-report.md); synthetic correctness không chứng minh mọi terrain/spec/model thật |
| Curb, default fit.loose, static shift | Sửa và kiểm, PR #61–63 | Đối chiếu verdict, static 0→8/8, default off; PR chưa merge thì main chưa có sửa |
| G7 và #48 | Quyết định/pending truth, PR #64 | Precision tay từng luật; không tự merge #48; học từ hai input thử không đạt 40 mẫu độc lập |
| Camera review12 | Sửa code/pretrained smoke, PR #65 | 9 ảnh GPU/cache; không human precision mọi model hay OOM acceptance |
| Missing review13 | Sửa, PR #67 | 98 deletion targets, giữ elevation filter; occlusion conservative. Protocol khác số handoff cũ, không gán superiority/precision tay |
| No-ID preview | Sửa/real render, PR #66 | Khung tham khảo 3D đúng frame; không box nhãn thật và không tự sửa CVAT |
| Extension/filter/camera | Source sửa, PR #68; runtime pending | Reload bản mới, kiểm MV3/CVAT thực tế trước nghiệm thu UI |
| API JSON và checks | Sửa/kiểm thật và suite | RV-14-001/002, Report API local; camera/Critic thiếu được báo đúng scope |
| Precision/long vision/atomic write | Còn mở | Nhóm người duyệt/model/runtime: mẫu tay đủ theo luật, nguồn độc lập, CPU/GPU long scans; CVAT không atomic GET→PATCH |

EV-16-002: [inventory.json](evidence/16/inventory.json), [inventory_probe.py](evidence/16/inventory_probe.py). 59 file owner16 gồm entrypoint/package/docs/management/scripts/ảnh có kết luận riêng; tài liệu lịch sử không tự chuyển sang PASS nghiệm thu. EV-16-003: [services.json](evidence/16/services.json). Lệnh tái chạy final package/platform: [final_probe.py](evidence/16/final_probe.py) (`--repo`, `--out` mới).

Kết luận sử dụng: có thể review và demo local trong scope đã kiểm. **Chưa nghiệm thu chất lượng rộng/G7, model precision và MV3 mới.** Dataset/token/weights/out/landing không nằm trong commit.
