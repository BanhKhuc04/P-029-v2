# Bàn giao 08 — preview cụm missing không có box nhãn

Model review: **gpt-6.1-sol**. Base `7ec580a`.

Lỗi 422 có nguyên nhân: `_scalar_details` bỏ list tâm/kích thước và `_finding_box` chỉ tìm box đã gán trong snapshot. Bản sửa ghi thêm tâm 3D/yaw theo frame của cụm, giữ các list hình học hữu hạn trong JSON; dựng khung tham khảo đúng frame từ bằng chứng của `lidar.missing` khi không có ID. Không lấy box của vật khác. Web ghi rõ đây là khung tham khảo của cụm chưa có nhãn.

Giữ `centers` XY để không đổi hợp đồng matcher/evaluation cũ. Chỉ whitelist các key list hình học, không serialize object tùy ý. Dữ liệu thiếu/sai/nonfinite hoặc không có frame chính xác vẫn trả 422 có hướng dẫn quét lại; bản quét cũ không đủ bằng chứng 3D cần quét mới. Preview không tạo hay ghi nhãn CVAT.

27 Python PASS (6 regression mới về serializer, malformed evidence, hai endpoint no-ID) và 41 Node PASS; 0 FAIL/SKIP/XFAIL trên Windows. Test camera dùng projection/JPEG thật trên ảnh fixture, nguồn frame mock; chưa lấy fixture làm nghiệm thu dataset/model/UI thật. Pillow thiếu ở base install thì riêng ca JPEG SKIP có lý do.

Lệnh từ tool root với `PYTHONPATH` là tool root: `python -m pytest -q tests/test_missing_preview_handoff.py tests/test_web_a14.py tests/test_missing.py tests/test_queue_cvat_scope.py`; từ extension: `node --test tests/core.test.js tests/review05.test.js tests/security06.test.js`.

PR độc lập vào main. Khi tích hợp cùng review13, giữ cả chuyển động/đơn vị/occlusion và các trường preview này trong details.

Kiểm thêm dữ liệu thật: xóa một track trong bộ nhớ của scene-0061, chạy missing trên đúng hệ tọa độ của bản xuất CVAT (manifest quay vào ego), serialize rồi dựng preview/camera: **88 điểm quanh cụm**, CAM_FRONT JPEG 23.848 byte, frame 7, không có ID box. [Summary/script](evidence/handoff-08/real-preview.json), ảnh ở out ignored. Đây là một ví dụ được tìm lại để kiểm renderer, không đo precision và không ghi CVAT.
