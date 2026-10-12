# Bộ tài liệu review P-029 / PointSnap 3D

Ngày lập: **10/10/2026, Asia/Saigon**. Mốc mã nguồn: **`5dcc97f1ffc1751d022e2474c0b50745e348af86`**.

Đây là hướng dẫn và kết quả review **01–08**, thực hiện 11–12/10/2026. Xem [bàn giao tổng](08-handoff.md), [07](07-report.md) và [08](08-report.md). Nhánh kết quả tiếp nối 01→08, chưa merge main. Mọi ca có trạng thái và giới hạn; review hoàn tất không đồng nghĩa quality/release đã nghiệm thu. MV3 thật, precision xem tay, atomic CVAT Save và triển khai ngoài local còn thiếu bằng chứng.

## 1. Chọn tài liệu theo nhánh

Tiền tố nhánh hướng dẫn ban đầu: `review/2026-10-10/`. Nhánh kết quả phần 01–03 dùng tên không có ngày theo yêu cầu bàn giao.

| Thứ tự | Nhánh | Hướng dẫn | Trạng thái review |
|---|---|---|---|
| 01 | `review/01-overview-architecture` | [Yêu cầu và kiến trúc](01-overview-architecture.md) | Hoàn tất phần 01; 256 pytest + 7 Node đạt; [bàn giao](01-handoff.md) |
| 02 | `review/02-core-detectors` | [Core và detector](02-core-detectors.md) | Hoàn tất phần 02; 321 pytest + 7 Node đạt; [bàn giao](02-handoff.md) |
| 03 | `review/03-data-cvat-integrations` | [Dữ liệu và CVAT](03-data-cvat-integrations.md) | Hoàn tất phần 03; 371 pytest + 7 Node; [bàn giao](03-handoff.md) |
| 04 | `review/04-backend-cli-reports` | [Backend, CLI và báo cáo](04-backend-cli-reports.md) | Hoàn tất phần 04; xem [báo cáo](04-report.md), [bàn giao](04-handoff.md) |
| 05 | `review/05-frontend-extension` | [Giao diện và extension](05-frontend-extension.md) | Web thật +logic extension; [bàn giao](05-handoff.md); MV3 thật còn thiếu môi trường |
| 06 | `review/06-security-config` | [Bảo mật và cấu hình](06-security-config.md) | Đã review/sửa security local; [bàn giao](06-handoff.md); không chứng nhận LAN/deployment |
| 07 | `review/07-tests-evaluation-performance` | [Kiểm thử, đánh giá và hiệu năng](07-tests-evaluation-performance.md) | 490 pytest +36 Node, eval10×10 và benchmark; [báo cáo](07-report.md) |
| 08 | `review/08-deployment-docs-final` | [Triển khai và tổng hợp](08-deployment-docs-final.md) | 493 pytest Windows,486 Linux/7skip; artifact/Docker/operations; [bàn giao](08-handoff.md) |

Mẫu báo cáo: [report-template.md](report-template.md). Kiểm kê mã nguồn: [tracked-file-inventory.tsv](tracked-file-inventory.tsv). Kế hoạch tổng: [REVIEW-PLAN.md](../../REVIEW-PLAN.md).

## 2. Phạm vi và đường dẫn

- **Kho Git** là thư mục chứa [README gốc](../../README.md), không phải thư mục cha chứa cả CVAT.
- **Tool root**: [source-tool/pointsnap-3d](../../source-tool/pointsnap-3d/). Các đường dẫn `pointsnap/...`, `tests/...`, `extension/...` trong 8 hướng dẫn đều tương đối với tool root.
- **Tài liệu sản phẩm**: [source-tool/README.md](../../source-tool/README.md), [đề xuất](../../source-tool/pointsnap-3d/de-xuat-de-tai.md), [CONVENTIONS](../../source-tool/pointsnap-3d/CONVENTIONS.md), [chuẩn kiểm thử](../../source-tool/pointsnap-3d/docs/test/CHUAN-KIEM-THU.md).
- **Kết quả từng phần**: file sẽ tạo `NN-report.md` trong thư mục này. Bằng chứng đã loại dữ liệu nhạy cảm có thể lưu trong `evidence/NN/`.
- Dataset, point cloud, snapshot nhãn và output đầy đủ giữ tại `out/` hoặc vị trí riêng ngoài Git. Chỉ đưa phần bằng chứng tối thiểu đã kiểm tra vào commit.

## 3. Khởi động mỗi phần

1. Đọc hướng dẫn tương ứng và CONVENTIONS; xác định các quyết định còn mở từ phần trước.
2. Từ kho Git, kiểm tra `git status --short --branch`, rồi chuyển sang đúng nhánh. Nếu có thay đổi chưa commit, xử lý chúng trước khi chuyển; không reset hoặc thêm file hàng loạt.
3. Ghi `git rev-parse HEAD`, `git diff --name-only`, hệ điều hành, Python, Node, CVAT, trình duyệt, dataset, task/job và thời gian. Với code cục bộ, ghi rõ đường dẫn và trạng thái chưa theo dõi.
4. Tạo báo cáo từ mẫu, điền người review/ngày thực hiện. Các ca dự kiến đều bắt đầu ở Chưa chạy.
5. Đọc code theo đường gọi thực tế, chạy kiểm tra phù hợp, lưu kết quả và findings.
6. Khi sửa, tách commit sửa mã nguồn với commit tài liệu; kiểm lại ca tái hiện và luồng liên quan.

Các nhánh hướng dẫn ban đầu độc lập; nhánh kết quả 02/03 đã đưa dependency trước vào có chủ đích. Đọc báo cáo bằng `git show <nhánh>:review/2026-10-10/NN-report.md`; ghi SHA đã tham khảo và chọn đúng base PR trong bàn giao. Không giả định các nhánh đã merge main.

## 4. Môi trường và lệnh kiểm tra

Môi trường kiểm thử chuẩn trong tài liệu dự án dùng **Python 3.11, CVAT v2.77.0**; CI hiện có matrix Ubuntu3.10/3.11, Windows3.12 và Node22, thêm artifact smoke; chưa có run remote nhánh review. Code khai báo Python >=3.10; một số ghi chú adapter dùng CVAT 2.77.1; Docker cục bộ dùng Python 3.12. Xem [ma trận 08](08-compatibility.md); các tổ hợp chưa kiểm không được coi tương đương.

Chạy các lệnh dưới đây từ tool root, trong môi trường đã cài `.[dev]` theo [CAI-DAT.md](../../source-tool/CAI-DAT.md). Không tạo lại môi trường đang dùng chỉ để bắt đầu review.

```powershell
python --version
node --version
python -m pointsnap --help
python -m pytest -q
```

Mỗi hướng dẫn có lệnh test tập trung để tránh chạy lại toàn bộ khi chưa cần. Đọc skip: test CVAT thật cần `POINTSNAP_LIVE_CVAT=1`; test nuScenes thật cần dataset. Các test tạo/ghi/xóa CVAT phải chạy trên task thử riêng.

Trong lượt kiểm tra trước trên máy này, launcher `.venv\Scripts\python.exe` dùng Python 3.12.14 nhưng không tự nhận pytest trong `.venv\Lib\site-packages`. Sau khi nạp đường dẫn thư viện bằng `sys.path.insert`, pytest gặp lỗi tạo thư mục tạm của sandbox. Đã chạy được bằng thư mục tạm mới nằm dưới `out/`. Ghi đây là sự cố môi trường, không quy thành lỗi phần mềm hoặc dấu hiệu môi trường chuẩn đã đạt.

Nếu gặp lỗi đó, có thể chạy test tập trung bằng cách sau; tên thư mục tạm là duy nhất, không dùng lại thư mục đã chứa dữ liệu:

```powershell
.\.venv\Scripts\python.exe -c 'import sys, runpy, uuid; from pathlib import Path; root = Path.cwd().resolve(); temp = (root / "out" / ("review-pytest-" + uuid.uuid4().hex)).resolve(); temp.relative_to(root); assert not temp.exists(); sys.path.insert(0, str(root / ".venv/Lib/site-packages")); sys.argv = ["pytest", "-q", "tests/test_cli.py", "tests/test_scan_gate.py", "tests/test_scan_wiring.py", "-p", "no:cacheprovider", "--basetemp", str(temp), "--tb=short"]; runpy.run_module("pytest", run_name="__main__")'
```

## 5. Chuẩn kết quả và bằng chứng

| Trạng thái ca | Khi dùng |
|---|---|
| Đạt | Đã thực hiện đủ các bước, đủ điều kiện mong đợi, có bằng chứng |
| Lỗi | Có hành vi sai tái hiện được hoặc bằng chứng code cụ thể |
| Bị chặn | Thiếu điều kiện cần để thực hiện; ghi nguyên nhân, ảnh hưởng và cách tiếp tục |
| Chưa chạy | Có trong kế hoạch nhưng chưa thực hiện |
| Không áp dụng | Nêu lý do dựa trên kiến trúc/phạm vi hiện tại |

Phân biệt **đọc code**, **test mock**, **dataset thật**, **CVAT thật**, **thao tác trình duyệt**. Test backend đạt không tự chứng minh giao diện/extension đã hoạt động. Test skip không được tính Đạt. Số liệu từ tài liệu cũ phải ghi ngày, commit/config/data nếu có; thiếu thông tin phải đánh dấu chưa xác định.

Mỗi bằng chứng có mã `EV-NN-xxx`, ca liên quan, commit, lệnh/thao tác, mã thoát hoặc kết quả, ngày và loại kiểm tra. Ca giao diện cần ảnh đã che token; ca đối chiếu số lượng phải ghi số ở từng nơi. Sai số hình học cần đơn vị và dung sai lấy từ convention/yêu cầu, không chỉ ghi “khớp”.

## 6. Chuẩn findings và ưu tiên

| Mức | Ý nghĩa trong đợt review |
|---|---|
| P0 | Sự cố nghiêm trọng đang xảy ra, phạm vi rộng, cần xử lý ngay; phải có bằng chứng phạm vi |
| P1 | Có điều kiện thực tế dẫn đến mất/sai nhãn, lộ token, sai quyết định chất lượng hoặc chặn luồng chính |
| P2 | Sai chức năng trong phạm vi hẹp, thiếu kiểm tra cần thiết, hoặc tài liệu gây thao tác/kết luận sai |
| P3 | Vấn đề trình bày, khả năng bảo trì hoặc cải tiến ít ảnh hưởng |

Mã finding: `RV-NN-xxx`. Ghi điều kiện, file/dòng hoặc luồng thao tác, thực tế, mong đợi, tác động, bằng chứng, hướng sửa, nhánh phụ trách và test cần chạy lại. Đề xuất chưa có bằng chứng lỗi ghi riêng. Cùng một lỗi chỉ có một mã chính; nhánh khác tham chiếu mã đó và thêm bằng chứng.

Trạng thái finding: Mở → Đang xử lý → Đã sửa/chờ kiểm lại → Đã xác minh. Có thể ghi Chấp nhận giới hạn khi người quyết định, lý do và phạm vi sử dụng được lưu rõ. Lỗi đã có trong báo cáo cũ vẫn phải xác nhận có còn trên commit đang review.

## 7. Hoàn tất và bàn giao

**Hoàn tất review** khi mọi ca có trạng thái, mọi kết luận có bằng chứng, findings có người/nhánh tiếp nhận và phần chưa xác minh được ghi rõ. **Đủ điều kiện sử dụng/phát hành** là kết luận riêng, phụ thuộc các lỗi còn mở và phạm vi triển khai. Không đồng nhất hai trạng thái này.

- Commit đúng file theo đường dẫn cụ thể. Kiểm tra `git diff --cached --name-only` trước commit.
- Bản tóm tắt PR gồm mục tiêu, phạm vi, mã nguồn nền, thay đổi, test/skip, findings còn mở, dependency và giới hạn.
- Tài liệu kế hoạch được chuẩn bị trên cả 8 nhánh cục bộ. Push/PR và merge thực hiện khi có yêu cầu; nhánh `main` không bị cập nhật bởi việc tạo bộ hướng dẫn này.
- Phần 08 tổng hợp báo cáo đã commit, kiểm kê toàn bộ file và đưa ra kết luận theo phạm vi đã xác minh.

## 8. Kiểm tra bộ tài liệu

Đã kiểm tra bằng Python standard library ngày 10/10/2026:

- Đủ 8 hướng dẫn, tên nhánh khớp 8 nhánh cục bộ.
- Có **155 ca checklist**, mã theo phần tăng liên tục và không trùng trong mỗi phần.
- Các Markdown links và đường dẫn file nguồn cụ thể được kiểm tra đều tồn tại trong checkout hiện tại; code fences cân bằng.
- Inventory có đúng **184 file** của commit nền `5dcc97f`, không thiếu/thừa/trùng.

Đây là kiểm tra cấu trúc ngày lập kế hoạch, không phải kết quả test phần mềm. Cả 155 ca kế hoạch đã có bảng trạng thái theo báo cáo01–08, gồm đạt/một phần/bị chặn/chưa nghiệm thu, không cộng tất cả thành PASS. Kết quả hiện hành xem [08](08-report.md); inventory và kiểm links mới ở evidence08.

## 9. Soát lại các nhánh để merge ngày 12/10/2026

Kết quả mới: [báo cáo soát và sửa 01–08](recheck-01-08-report.md). Các sửa được đưa vào chính tám nhánh kết quả `review/01-*` đến `review/08-*`; đã đồng bộ main `be1778c` và giải quyết xung đột phục vụ merge. Các tính năng mới trên main ngoài phạm vi review.

Merge theo thứ tự **01 → 08**, giữ ancestry bằng merge commit hoặc fast-forward; 08 chứa kết quả cộng dồn 01–07. Báo cáo mới tách PASS/SKIP/XFAIL, giữ kết quả snapshot cũ và ghi giới hạn chưa nghiệm thu. Nhánh có ngày là snapshot hướng dẫn ban đầu, không dùng thay nhánh kết quả.
