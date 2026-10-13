# Test results — 11/10/2026

- Python3.12.14, Node24.19.0, CVAT2.78.1; fake dataset +v1.0-mini; private home/temp dưới ignored out.
- Full pytest:467 passed,0 skipped,47.32s,1 Starlette/httpx warning.
- Sau delta pagination/XFrame/report-log:51 focused pytest passed,6.78s. `tests/test_security_review.py`32 ca, client/report API19 ca.
- Node core +review05 +security06:35 passed,0 skipped (thêm1 follow-up reset draft Guideline ở bước cuối).
- JS syntax và diff check đạt. pip check không chạy được (No module named pip); metadata.Requirement kiểm30 distributions base dependencies,0 conflict; không CVE audit.
- origin-before-after.json dùng app source43812b9, module đăng ký cho Pydantic, cùng current ProjectManager/config. Before200 rulefalse→true; after403 false giữ. Đây là TestClient, không phải browser exploit trước sửa.
- Browser IAB8767 fetch→8766 hiện TypeError vì CORS; iframe form trước đó không load. Live HTTP đo403 riêng và đọc lại guidelinefalse để xác minh không mutate. Screenshot không tự chứng minh mãHTTP403.
- live-results.json ghi Host403/cache/private/cleanup task60/no tracked PAT match. deps JSON không có credentials.
- Fixtures/scripts có dữ liệu riêng và thư viện launcher; log lỗi setup ban đầu gồm sai tên helper, Pydantic forward refs, đường dẫn Windows quá dài do pytest parameter ID; đã sửa helper/module/IDs. Không quy các lỗi setup đó thành lỗi sản phẩm.
