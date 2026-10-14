# Review kiến trúc và UX: Web + extension

Ngày hoàn tất: 14/10/2026, Asia/Bangkok. Reviewer: **Codex, agent dựa trên GPT-6**; phiên không cung cấp ID model triển khai chi tiết. Không suy ra model của phiên từ cấu hình mặc định của ứng dụng.

## Kết luận

**Web hữu ích cho QA xem bằng chứng và tổng hợp báo cáo; extension hữu ích cho annotator sửa nhãn ngay trong CVAT.** Luồng chính đã hoạt động trong các ca kiểm tra thực tế. Giao diện có tiếng Việt, số đo, ngưỡng và gợi ý sửa; vẫn cần cải thiện thiết lập ban đầu và xem camera ngay trong extension. Chưa có nghiên cứu với người dùng thật để kết luận mọi người đều thấy dễ dùng, hoặc đo thời gian tiết kiệm/SUS.

Đã sửa ba lỗi Web trên nhánh riêng: focus thoát khỏi màn Bắt đầu, thiếu số frame của job và ô Task tràn ngang khi tên dài trên màn hình nhỏ. **31 test backend liên quan đạt**, JavaScript qua syntax check và ba sửa đã kiểm lại bằng trình duyệt.

Sơ đồ: [architecture-system.md](../../source-tool/pointsnap-3d/docs/architecture-system.md), gồm cấu trúc hệ thống, luồng quét–duyệt–sửa và deployment Web/CLI/Report API. Dữ liệu quan sát đã rút gọn: [architecture-ux-observations.json](architecture-ux-observations.json).

## Phạm vi và phiên bản

| Bề mặt | Phiên bản/phạm vi |
|---|---|
| Mã nguồn kiến trúc và Web ban đầu | `main` 7ec580a97fa0cf7eddd553212d06c52873a9057f |
| Web sau sửa | Nhánh `codex/architecture-ux-20261013`, dựa trên main trên; diff trong PR là nguồn xác định ba sửa |
| Web chạy thật | FastAPI local tại 127.0.0.1:8765; source được nạp từ worktree architecture-ux |
| Extension | MV3 đang cài trong Edge; layout quan sát phù hợp nhánh redesign `feat/extension-thiet-ke-lai` tại be1778c, chưa xác minh hash bản cài |
| CVAT | 2.77.0, localhost:8080, task/job 4; metadata kiểm lại: start 0, stop 38, frame_count 39 |
| Dữ liệu | nuScenes mini và manifest xuất scene-0061 trên máy người dùng |
| Dự án thử riêng | `ux-review`, file ở `out/ux-home`; guideline khởi tạo bằng package handoff-check, `fit_loose=false`, `camera.enabled=false` |

Không gộp kết quả này với bộ test toàn repo của bàn giao trước đó. Không coi Web main, extension redesign và Report API đã deploy là cùng một bản build. Lượt UX không nghiệm thu lại các PR sửa detector/model còn chờ merge.

Lượt quét read-only `20261013-235630-469489710783-job4` bắt đầu lúc 23:56 ngày 13/10: 3727 box đang hoạt động theo bộ đếm của runner, **4 Lỗi, 16 Cảnh báo, 103 Thông tin**, tổng 123 phát hiện; `flag=false`, trạng thái `done`. Gate không đạt vì vượt giới hạn 0 Lỗi/10 Cảnh báo và có `floating.no_evidence`. Số này là quan sát vận hành, không phải precision hay chứng nhận chất lượng nhãn.

## Những việc hoạt động tốt

| Tiêu chí | Web | Extension trong CVAT |
|---|---|---|
| Biết ứng dụng đang làm gì | Badge CVAT kết nối, nút quét bị khóa khi chạy, tiến độ, gate nêu lý do | Trạng thái kết nối, frame hiện tại, vị trí trong danh sách lỗi |
| Hiểu và xử lý phát hiện | Số đo/ngưỡng, ảnh camera chiếu box, Top/Side/Front, cách sửa bằng tiếng Việt | Card ghi loại lỗi, frame, class, số đo và phần CÁCH SỬA |
| Tìm mục cần xử lý | Tìm kiếm và lọc mức/class/loại, lịch sử, link report | Danh sách lỗi và điều hướng frame/box ngay trong CVAT |
| Tránh thao tác nhầm | Quét khi chưa chọn job báo rõ cách khắc phục | Quét + gắn cờ cảnh báo việc ghi nhãn và nhắc Save; nút Thôi hủy được |
| Theo dõi thay đổi | Lịch sử hiện lượt quét và 4/16, có Xuất CSV/HTML | Thông báo 17 cờ CVAT không nằm trong lượt quét mới nhất, đề nghị đồng bộ |

Đây là đánh giá qua thao tác và quan sát của reviewer, dùng các tiêu chí trạng thái, ngôn ngữ dễ hiểu, phòng lỗi và hỗ trợ trong [heuristics của Nielsen Norman Group](https://www.nngroup.com/articles/ten-usability-heuristics/). Chưa thử tải xuống CSV/HTML trong phiên UX; sự có mặt của link không được tính là kiểm tra tải thành công.

## Lỗi đã sửa

### UX-01 — Focus bàn phím đi vào ứng dụng phía sau splash

Trước sửa: nhấn Tab từ Bắt đầu làm focus chuyển tới link PointSnap 3D phía sau màn chào. Splash khai báo `aria-modal=true` nhưng không ngăn tương tác nền. Đây là sai khác với cách giữ focus trong modal được mô tả bởi [W3C APG](https://www.w3.org/WAI/ARIA/apg/patterns/dialog-modal/).

Sửa trong `pointsnap/web/static/app.js`: đặt vùng ứng dụng `inert` khi splash mở, giữ Tab/Shift+Tab trong splash, giữ focus trên splash lúc tải và trả focus về nút chọn dự án sau khi đóng. Escape bắt đầu mở ứng dụng như nút Bắt đầu; listener được gỡ khi đóng.

Đã kiểm: Tab và Shift+Tab vẫn focus `splash-start`; Escape chuyển sang tải; Tab khi tải vẫn focus `splash`; khi xong focus là `btn-project-dropdown`, Tab tiếp đi tới `theme-btn-light`. Không còn giữ focus trong splash đã đóng.

### UX-02 — Job có metadata nhưng Web báo chưa rõ số frame

Trước sửa: API `/cvat/tasks` bỏ `start_frame`, `stop_frame`, `frame_count`; job picker chỉ hiện “chưa rõ số frame”. Sửa whitelist ba trường này trong `pointsnap/web/app.py`. Frontend sẵn có logic ưu tiên frame_count, rồi fallback khoảng start/stop.

Đã kiểm với CVAT thật: job 4 hiện **39 frame**, khớp metadata 0–38. Hai regression cases bảo đảm API giữ range khi có/không có frame_count, không trả PAT hoặc thông tin assignee không cần thiết và đóng client session.

### UX-03 — Task tên dài đẩy nút Tải lại ra ngoài màn hình nhỏ

Trước sửa: viewport đặt 390×844 có content width 375 px (trừ scrollbar), nhưng document width 507 px; select Task và nút Tải lại bị đẩy ra ngoài. Sửa `min-width: 0` trên flex select trong `index.html`.

Đã kiểm sau khi danh sách Task tên dài tải xong: ở viewport 390, document/content đều 375 px; nút Tải lại nằm trong card. Ở viewport 320, document/content đều 305 px. Trang Kết quả tại 390 cũng không tràn ngang toàn trang; bảng có vùng cuộn riêng. Đây là kiểm tra reflow ở hai kích thước, chưa phải chứng nhận toàn bộ accessibility.

## Việc nên làm tiếp

Các mục sau là đề xuất từ quan sát, chưa đo bằng người dùng thật.

| Ưu tiên | Vấn đề/ảnh hưởng | Thay đổi đề xuất | Điều kiện nghiệm thu |
|---|---|---|---|
| P1 | Panel extension đang cài không có nút camera cho finding; phải chuyển Web hoặc tự tìm camera trong CVAT | Tích hợp bằng chứng camera vào bản redesign; đối chiếu phần camera của PR #68 trước khi sửa trùng | Chọn lỗi → mở ảnh đúng frame/box; có trạng thái thiếu ảnh rõ ràng |
| P2 | Tạo dự án cần hiểu PAT, thư mục nuScenes và manifest; phần Guideline có nhiều công tắc | Hướng dẫn thiết lập theo bước, kiểm tra kết nối/data và preset trước; gom ngưỡng ít dùng vào Nâng cao | Người mới hoàn tất một lượt read-only qua UI và tự hiểu lỗi thiếu dữ liệu |
| P2 | Sidebar “Kết quả 20” và tab “Tất cả 123” có thể bị hiểu là số không nhất quán | Nêu rõ 20 là Lỗi + Cảnh báo, 103 là Thông tin | Ý nghĩa bộ đếm hiển thị ngay cạnh bộ đếm hoặc khi focus |
| P2 | Tiến độ vẫn ghi cứng “Chạy 3 bộ phát hiện”, trong khi scanner hiện chọn nhiều nhóm theo guideline | Hiển thị “Chạy các luật đang bật” hoặc tên nhóm thực chạy | Nội dung không tạo ấn tượng chỉ có ba nhóm detector |
| P2 | Panel nổi che một phần ô camera trên layout đã kiểm | Cải thiện lựa chọn vị trí/dock; làm cách kéo/thu gọn dễ nhận ra | Người dùng vẫn đối chiếu được camera và 3D khi panel mở |

Bản extension đã có kéo panel bằng header và nút thu gọn trong source redesign; đề xuất cuối liên quan khả năng tìm thấy các thao tác này và vị trí mặc định, không kết luận tính năng kéo bị thiếu.

## Các ca kiểm tra trình duyệt

| ID | Thao tác và kết quả quan sát | Trạng thái |
|---|---|---|
| W01 | Chưa có run: hiển thị trạng thái rỗng cùng đường tới Quét job/Lịch sử | Đạt trong ca kiểm |
| W02 | Bỏ chọn job rồi Bắt đầu: hiện “Vui lòng chọn Job hoặc nhập ID job” | Đạt trong ca kiểm |
| W03 | Job 4, checkbox gắn cờ bỏ chọn: busy → done, 4/16/103, gate có lý do | Đạt trong ca kiểm |
| W04 | Chọn finding bicycle frame 37: hiện ảnh camera và ba mặt cắt LiDAR, số đo/ngưỡng/cách sửa | Đạt trong ca kiểm |
| W05 | Tìm `bicycle`: chỉ còn các dòng bicycle; xóa tìm kiếm khôi phục danh sách | Đạt trong ca kiểm |
| W06 | Lịch sử: thấy run 23:56 job 4, 4 Lỗi/16 Cảnh báo, Không đạt | Đạt trong ca kiểm |
| W07 | Splash: Tab, Shift+Tab, Escape, Tab trong lúc tải, focus sau đóng | Đạt sau sửa UX-01 |
| W08 | Job picker: metadata CVAT 0–38, 39 frame và nhãn 39 frame | Đạt sau sửa UX-02 |
| W09 | Task tên dài tại 390 và 320 px; Kết quả tại 390 px | Đạt kiểm tra tràn ngang sau UX-03 |
| E01 | Panel đã nạp: Lỗi hiện tại, Danh sách 36, thông báo cờ khác lượt quét | Đạt trong ca kiểm |
| E02 | Chọn bicycle frame 37 từ danh sách: CVAT chuyển frame 37, sidebar chọn bicycle client ID 216; finding dùng server track ID 654 | Đạt trong ca kiểm |
| E03 | Quét + gắn cờ: hiện xác nhận/nhắc Save, bấm Thôi hủy | Đạt trong ca kiểm |
| E04 | Tìm thao tác xem camera trong panel đang cài | Chưa có trong UI quan sát |

Không bấm Gắn cờ ở bước xác nhận, không sửa hình học hoặc Save annotation trong lượt UX này. `flag=false` được xác nhận trong run.json/summary.json. Không tuyên bố đã kiểm vòng ghi cờ → sửa box → Save → lỗi biến mất trong phiên này. Cờ CVAT có sẵn không phải cờ do lượt UX này ghi.

Hộp Filters của CVAT có xuất hiện thoáng qua lúc extension khởi động rồi tự đóng; không ghi thành lỗi modal chặn vĩnh viễn. Các nút review là native button với `aria-pressed`; cách tool AX hiển thị như checkbox không đủ để kết luận markup sai.

## Script và bằng chứng

Từ thư mục `source-tool/pointsnap-3d`, dùng Python có dependency dev:

```powershell
python scripts/test_web_ux.py
```

Script chạy `tests/test_web_job_metadata.py`, `tests/test_web.py`, `tests/test_web_a14.py`, rồi `node --check pointsnap/web/static/app.js`. Kết quả thực chạy: **31 passed in 3.44s**, syntax check đạt. Script không tự điều khiển browser; các ca W/E phía trên là kiểm trực tiếp và có bước tái hiện. `git diff --check` đạt.

Ảnh thực được giữ trên máy người dùng tại `source-tool/pointsnap-3d/out/` của worktree architecture-ux, không commit snapshot annotation/PAT/dữ liệu:

| File | Bằng chứng |
|---|---|
| `ux-splash.png`, `ux-splash-fixed.png` | Splash trước/sau sửa; kết quả focus còn được ghi trong JSON |
| `ux-scan.png` | Lượt quét đang chạy |
| `ux-web-results.png`, `ux-web-final.png` | Kết quả, gate và ảnh bằng chứng |
| `ux-job-frames-fixed.png` | Job picker sau bổ sung metadata |
| `ux-mobile-scan.png`, `ux-mobile-scan-fixed.png`, `ux-mobile-320-fixed.png` | Task tên dài trước/sau sửa, reflow |
| `ux-mobile-results.png`, `ux-web-history.png` | Kết quả ở màn hẹp và lịch sử |
| `ux-extension-clean.png`, `ux-extension-bicycle.png` | Panel thực và frame/box được chọn |
| `ux-flag-confirm.png` | Xác nhận ghi cờ; reviewer đã bấm Thôi |

## Model và giới hạn nghiệm thu

Lượt UX dùng luật trong Python, **camera inference tắt**, `critic.model` rỗng và chưa có learned model. Ảnh camera Web vẫn hiện vì lấy ảnh và chiếu cuboid, không cần model detector ảnh. Chưa nghiệm thu Mask R-CNN/Grounding DINO/SAM hoặc Box Critic bằng lượt UX này.

Tiếp tục dùng **precision từ chấm tay theo từng luật** cho G7, báo proxy riêng và giữ chưa nghiệm thu khi thiếu mẫu. Không dùng 31 test phần mềm hoặc 123 phát hiện để suy ra độ chính xác model. `fit.loose` vẫn tắt trong dự án thử theo lựa chọn của người dùng; PR đổi mặc định là phần việc bàn giao riêng.

Để đánh giá dễ dùng bằng người thật, bước tiếp là cho annotator mới tự thiết lập dự án, tìm một lỗi, xem bằng chứng, chọn box trong CVAT và giải thích khi nào nên đánh dấu Báo nhầm. Ghi tỷ lệ hoàn thành, chỗ cần trợ giúp và thời gian thao tác; chưa công bố số đo trước khi có dữ liệu.
