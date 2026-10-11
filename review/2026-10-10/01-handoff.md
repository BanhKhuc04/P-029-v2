# Bàn giao phần 01 — đọc trước khi mở PR

**Nhánh:** `review/01-overview-architecture` → nhánh đích **`main`**. Phần 01 đã review và sửa xong; người nhận nhánh mở PR và thực hiện review độc lập.

## 1. Đọc theo thứ tự

1. Trang này: thay đổi và lý do trong vài phút.
2. [Báo cáo phần 01](01-report.md): 14 ca review, 8 findings, truy vết yêu cầu và giới hạn.
3. [Kiến trúc](01-architecture.md): 3 sơ đồ, 17 quan hệ được đối chiếu với code.
4. [Bằng chứng kiểm tra](evidence/01/test-results.md): lệnh chạy, môi trường và kết quả trước/sau.

## 2. Những gì đã sửa và vì sao

| Thay đổi | Lý do |
|---|---|
| Gate chặn khi thiếu LiDAR/pose/bằng chứng ground | Không được kết luận ĐẠT khi các luật đang bật chưa đủ dữ liệu để kiểm |
| Gate đếm đúng generator | Trước đây lượt đếm lỗi tiêu thụ generator, khiến cảnh báo bị bỏ sót |
| Gate CLI trả mã 3 khi lỗi đọc frame | Người dùng và script cần nhận lỗi runtime rõ ràng, không bị văng traceback |
| Web lưu thiếu dữ liệu và hiển thị hướng dẫn phù hợp | Người dùng cần biết phải bổ sung dữ liệu hay sửa nhãn |
| Tài liệu phân biệt code, kết quả lịch sử và nghiệm thu | G2 hoặc test mock không chứng minh toàn bộ sản phẩm đã đạt; `diff` còn chưa triển khai |
| Sơ đồ đúng đường gọi và đủ 6 nhóm detector | Scanner trả findings; CLI/runner tạo report và ghi cờ. Core hiện có import CVAT reader |
| Số liệu cũ có ghi chú; recall 0/0 là không xác định | Tránh so nhầm phiên bản hoặc kết luận từ tập không có mẫu |
| Test dotenv cô lập biến môi trường | Token giả của test không được ảnh hưởng các test CVAT thật chạy sau |
| Test ground nhận NUSCENES_ROOT | Dataset được đặt ngoài thư mục tool/data vẫn phải chạy được; giữ nguyên assertion |

## 3. Kết quả kiểm tra

- **252 test Python đạt, 0 bỏ qua**: gồm cả 6 test trước đây skip, chạy với nuScenes mini thật và CVAT Docker 2.78.1.
- **7 test Node extension đạt**; cú pháp JS và `git diff --check` đạt.
- Có **1 cảnh báo Starlette/httpx** của môi trường; không có test lỗi.
- Các task CVAT thử đã tự xóa; kiểm tra sau chạy còn **0 task thử**.
- Chưa chạy lại kiểm tra bằng mắt trong trình duyệt, precision xem tay hoặc eval 10 vòng. Đây là việc của phần 02–08 theo bảng bàn giao, không phải bằng chứng đã nghiệm thu toàn sản phẩm.

## 4. Lấy nhánh và xem thay đổi

```bash
git fetch origin
git switch --track origin/review/01-overview-architecture
git diff origin/main...HEAD --stat
```

Nếu nhánh đã có trên máy, chuyển sang nhánh đó rồi pull bình thường. Bản sửa tách commit code, test live và tài liệu. Không có token, dataset, output, snapshot hay Docker/API local chưa theo dõi trong nội dung bàn giao.

## 5. Nội dung PR có thể dùng ngay

**Tiêu đề:** `Review phần 01: sửa gate thiếu dữ liệu và cập nhật kiến trúc`

**Mô tả:**

```markdown
## Mục tiêu
Review lại yêu cầu và kiến trúc PointSnap; sửa các kết luận chất lượng sai do thiếu dữ liệu.

## Thay đổi và lý do
- Chặn gate khi thiếu LiDAR/pose cho luật bật hoặc có floating.no_evidence để tránh nộp nhãn từ một lần kiểm tra chưa đủ dữ liệu.
- Đếm đúng cảnh báo khi findings là generator; trả mã runtime 3 khi không đọc được frame.
- Web lưu lý do kiểm tra một phần và hướng dẫn bổ sung dữ liệu.
- Cô lập env trong test dotenv, cho test ground dùng NUSCENES_ROOT để chạy đủ test thật.
- Sửa tài liệu trạng thái, số liệu lịch sử, recall 0/0; bổ sung báo cáo và sơ đồ có bằng chứng code.

## Kiểm tra
- Python: 252 passed, 0 skipped; Node: 7 passed.
- CVAT Docker 2.78.1 + nuScenes mini thật; các task thử đã xóa.
- Cú pháp JS và git diff --check đạt; 1 warning Starlette/httpx của môi trường.

## Phạm vi
- Mốc main: 5dcc97f; có commit 22a01f5 chứa bộ hướng dẫn 8 phần đã chuẩn bị trước.
- Phần 01 có 14 ca review hoàn tất và 8 findings đã sửa.
- Chưa nghiệm thu UI bằng mắt, precision xem tay, eval nhiều vòng hoặc cài máy trắng; bàn giao phần 02–08.
- Không kèm token/dataset/output hoặc Docker/API local chưa theo dõi.

## Tài liệu
- review/2026-10-10/01-report.md
- review/2026-10-10/01-architecture.md
- review/2026-10-10/evidence/01/test-results.md
```

So sánh nhánh: [GitHub — main và review/01-overview-architecture](https://github.com/AI20K-Build-Phase-Cohort-4A/P-029/compare/main...review/01-overview-architecture).
