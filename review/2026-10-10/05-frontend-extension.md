# 05 — Review giao diện Web và extension CVAT

**Nhánh:** `review/05-frontend-extension`.
**Trạng thái:** đã review/sửa ngày11/10; Web thật +logic extension đạt, ca MV3 cần Chrome/Edge còn bị chặn. Xem [báo cáo](05-report.md), [bàn giao](05-handoff.md).
**Đầu ra sẽ tạo:** `05-report.md`, bảng hành trình người dùng, ảnh bằng chứng và findings UX/chức năng.

Áp dụng [quy trình chung](README.md), [mẫu báo cáo](report-template.md), `docs/test/CHUAN-KIEM-THU.md`. Đường dẫn code tính từ tool root. Các test Node/TestClient là bằng chứng logic, ca trình duyệt cần thao tác riêng.

## 1. Mục tiêu và điều kiện

Chứng minh người dùng làm được trọn luồng kết nối → chọn job → quét → hiểu kết quả → mở đúng box CVAT → sửa/save → quét lại → ghi kết luận; nhận biết thiếu dữ liệu, lỗi dịch vụ và kết quả cũ.

Cần PointSnap Web, CVAT thử nghiệm và extension unpacked theo `extension/README.md`. Ghi phiên bản Chrome/Edge/CVAT, task/job, số frame/box, theme và viewport. Chuẩn bị một job có nhiều finding, một job không có finding, một project thiếu LiDAR và một project có token không hợp lệ. Các ca sửa/save/flag dùng task thử riêng.

## 2. Phạm vi code và tài liệu

| Nhóm | File | Trọng tâm |
|---|---|---|
| Web | `pointsnap/web/static/index.html`, `app.js`, `styles.css`, assets/fonts | State, fetch, render, lọc, form, keyboard, theme và tải assets |
| Extension setup | `extension/manifest.json`, `background.js`, `options.html`, `options.js` | Host permissions, service worker, options và messaging |
| Extension CVAT | `extension/src/core.js`, `cvat-dom.js`, `cvat-api.js`, `seed.js`, `content.js`, `panel-css.js` | Đọc cờ/nhãn, filter history, điều hướng, highlight và Shadow DOM |
| Bridge backend | `pointsnap/web/link.py`, routes extension/reviews trong `web/app.py` | Seq/poll/online timeout và đồng bộ kết luận |
| Bằng chứng cũ | `docs/screenshots/`, `docs/thu-extension.md`, chuẩn kiểm thử | Tham khảo các ca đã mô tả; ảnh cũ không chứng minh phiên bản hiện tại |

## 3. Trình tự

1. Đọc journey và checklist TC trong chuẩn kiểm thử, đối chiếu UI hiện tại; lập mã R05 liên kết TC tương ứng.
2. Chụp màn hình ban đầu các màn chính trước nhận xét UX. Ghi theme, kích thước viewport và dữ liệu hiển thị.
3. Chạy journey Web và CVAT/extension, kể cả thao tác nhanh và dữ liệu thiếu/lỗi.
4. Kiểm Web ↔ extension từ cả hai phía, thêm tab/job/project để phát hiện nhầm scope.
5. Kiểm keyboard, focus, labels và responsive; xác minh code render/messaging khi có lỗi quan sát được.
6. Ghi findings có bước lặp lại, ảnh và backend response liên quan đã loại thông tin nhạy cảm.

## 4. Checklist journey

| Mã | Thao tác/điều kiện | Mong đợi / bằng chứng |
|---|---|---|
| R05-01 | Mở UI, màn chào, chuyển project | Không mắc ở loading; project đang chọn rõ; F5 giữ state theo thiết kế |
| R05-02 | Tạo/sửa/xóa project, token đúng/sai/thiếu | Validation và lỗi có cách tiếp tục; không lộ token; xóa đúng project có xác nhận theo UI |
| R05-03 | Chọn task/job, bắt đầu scan | Job/config đúng; queued/running/progress/done/failed rõ; bấm hai lần không lẫn run |
| R05-04 | Đọc kết quả và gate | Số box/error/warning/info có nghĩa rõ; thiếu LiDAR không bị hiểu là mọi luật đã đạt |
| R05-05 | Lọc/sort/search, kết hợp bộ lọc, không có kết quả | Count khớp tập đang hiển thị; reset được; empty state khác service failure |
| R05-06 | Download HTML/CSV, link CVAT | Số lượng khớp UI; mở đúng job/frame/shape hoặc track; nêu 3 dòng cụ thể đã thử |
| R05-07 | Duyệt nhanh J/K, điểm và nhiều finding cùng box | Frame/box đúng; exact_frame/không đủ dữ liệu rõ; không mất lựa chọn khi load chậm |
| R05-08 | Ghi Đúng/Báo nhầm/bỏ kết luận | Lưu đúng run/index, refresh giữ; precision có số mẫu đã review và số chưa review |
| R05-09 | History và kết quả cũ | Mở đúng run; config/version/context đủ phân biệt với scan mới |
| R05-10 | Guideline form/YAML, tắt rule, reset | Error không làm mất nội dung hợp lệ; xác minh rule bị tắt ở scan tiếp theo |
| R05-11 | Extension cài lần đầu, thêm CVAT host, reload | Options/permission state rõ; content scripts chạy đúng host/job, không tạo hai panel |
| R05-12 | Filter pointsnap_error và job không có attribute/cờ | Chỉ lọc mục đúng; có hướng dẫn fallback; không ẩn nhầm box không liên quan |
| R05-13 | Lỗi tiếp/trước, nhiều lỗi một frame, bấm liên tục | Đi đủ danh sách, chọn đúng box; không reload cả trang hay nhận nhầm lỗi |
| R05-14 | Web focus ↔ tab CVAT đang mở | Nhảy đúng frame/đối tượng; tab chưa mở/offline có fallback; ca nhiều tab/job được ghi |
| R05-15 | Review từ extension ↔ Web | Cùng verdict/run/index ở hai phía sau thời gian poll thực tế; không ghi đè mục khác |
| R05-16 | Save nhãn, quét + gắn cờ, tải lại CVAT | Cờ phản ánh nhãn đã save; số lỗi thay đổi có số trước/sau; cảnh báo kết quả cũ rõ |
| R05-17 | Tắt Web hoặc CVAT, timeout, permission bị từ chối | Extension E1–E5 vẫn theo giới hạn tài liệu; ca cần Web báo trạng thái/cách khôi phục |
| R05-18 | Web ↔ extension ↔ CVAT khác server có job ID trùng | Không lẫn project/finding/lệnh; chuyển thêm bằng chứng cho 04/06 |
| R05-19 | Theme sáng/tối, viewport hẹp, zoom 200% | Văn bản/nút/bảng quan trọng không bị che; cuộn và thao tác vẫn thực hiện được |
| R05-20 | Chỉ dùng bàn phím và đọc labels | Tab order/focus rõ; dialog đóng/khôi phục focus; phím tắt không chạy khi nhập văn bản |
| R05-21 | CVAT phím J/K và bàn phím Telex | Extension dùng phím theo README; không chặn phím native hoặc nhập liệu |
| R05-22 | Label/message rất dài, HTML và ký tự đặc biệt | Hiển thị text an toàn, layout đọc được; payload security giả lập chuyển 06 |

## 5. Bằng chứng bắt buộc

- Mỗi màn chính: ảnh trước nhận xét, dữ liệu/job/run/theme/viewport.
- Mỗi lỗi: các bước, hiện tượng nhìn thấy, screenshot, tần suất, console/network đã loại token nếu cần.
- Ca “bấm N dòng”: liệt kê frame, rule, label, ID và mục CVAT thực tế nhận được ở từng dòng.
- Ca parity: ghi số UI/HTML/CSV/CVAT và phương pháp đếm; finding count có thể khác số box có cờ.
- Ca đồng bộ: ghi timestamp tương đối gửi/nhận và run/index hai phía; không chỉ ghi “đồng bộ tốt”.

Bảng journey cần cột mục tiêu người dùng, màn/thao tác, prerequisite, kết quả, ma sát, ca/ảnh và finding. Findings về UI chỉ dựa vào ảnh/thao tác hiện tại; ảnh trong docs là bằng chứng lịch sử.

## 6. Kiểm tra logic tập trung

Từ tool root:

```powershell
node --test extension/tests/core.test.js
python -m pytest -q tests/test_web_a14.py tests/test_web_a15.py
```

Kiểm JS/manifest theo CI bằng Node ở phần 07/08. Các lệnh trên không chứng minh content script đã được inject, nút CVAT đã hoạt động hoặc hình học preview nhìn đúng. Các ca đó phải thực hiện trong trình duyệt và giữ bằng chứng.

## 7. Hoàn tất và bàn giao

- [ ] Journey chính và ca lỗi/empty/offline có kết quả cùng bằng chứng.
- [ ] Extension E1–E6 và bridge Web/CVAT được phân biệt theo điều kiện dịch vụ.
- [ ] Có ca nhiều tab/job/project, keyboard/form và viewport/theme.
- [ ] Findings có ảnh, bước tái hiện và tác động đến thao tác người dùng.
- [ ] API/state chuyển 04, nhãn/link/frame chuyển 03, token/XSS/host chuyển 06.
- [ ] `05-report.md` ghi browser/CVAT thực tế và các ca chưa kiểm; chuyển nội dung sửa hướng dẫn cho 08.
