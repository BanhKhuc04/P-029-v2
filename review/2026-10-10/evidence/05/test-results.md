# Bằng chứng phần05 — 11/10/2026

- Trước sửa: 10/10 regression mới fail; lỗi lưu form được tái hiện IAB (ảnh02).
- Sau sửa: `node --test extension/tests/core.test.js extension/tests/review05.test.js`: **21/21 đạt**.
- pytest toàn bộ có `POINTSNAP_LIVE_CVAT=1`, NUSCENES_ROOT v1.0-mini, POINTSNAP_HOME riêng: **436 đạt,0 skip,49,56s**,1 cảnh báo Starlette/httpx. JUnit chứa testcase nằm trong ignored out/review05-tests.xml.
- `node --check` app.js/content.js và `git diff --check` đạt.
- Ảnh01 splash;02 guideline lỗi schema trước sửa;03 ranges sau sửa;04 results dark;06 viewport600×800;07 sau rule off. Ảnh05 fullpage không bảo đảm do screenshot API có lần không capture; dùng ảnh06/07 làm bằng chứng bố cục.
- Browser chỉ IAB, không có Chrome/Edge MV3. Task/job60 CVAT2.78.1,3frame4box,private home. Review index0 fp giữ sau reload; form0 giữ sau reload; size_class_range off làm2 lỗi giảm1. Không kiểm sửa nhãn bằng GUI.
