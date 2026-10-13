# EV-12-005 — runtime, tài nguyên và các probe không hợp lệ

Runtime riêng: torch **2.8.0+cpu** từ phần 11, torchvision **0.23.0+cpu**, Transformers **5.0.0**, Pillow **12.3.0**, NumPy **2.5.4**. Không đổi `.venv` hoặc cài hệ thống. `PYTHONPATH` đặt `out/review12-runtime` trước `out/review11-runtime`.

Windows giữ DLL directory handle trước import torch:

```python
handle = os.add_dll_directory(
    "C:/Users/Han/.cache/codex-runtimes/codex-primary-runtime/dependencies/native/jxrlib/jxrlib/bin"
)
```

## Weights và trạng thái bị chặn

- Mask R-CNN COCO_V1 URL chính thức: `https://download.pytorch.org/models/maskrcnn_resnet50_fpn_v2_coco-73cbd019.pth`. PyTorch urllib bị reset. HTTPX với TLS verification lấy được HTTP 200/content-length 185.828.065 byte, nhưng stream dừng và timeout trước hoàn tất; file tạm tự dọn. Chưa kiểm được hash checkpoint.
- DINO revision `12bdfa3120f3e7ec7b434d90674b3396eccf88eb`; SAM2 processor cache revision `ee5bba1d82bb8749febdf90f45e84b687142ba03`. Processor tải được; DINO safetensors timeout rồi DNS failure nhiều lần, model loader báo không nạp được. Byte-range requests tới nguồn chính thức cũng reset.
- Người dùng xác nhận chưa có SAM. Không đổi sang nguồn weights không rõ hoặc bỏ kiểm TLS/hash để thay ca pretrained. TC-12-008 bị chặn; không có pretrained file hoàn chỉnh ở cache review.
- HTTP errors này là lỗi tài nguyên/mạng quan sát được, không phải tự động approval review từ chối hành động.

Nguồn hợp đồng tham khảo: [Torchvision 0.23 Mask R-CNN](https://docs.pytorch.org/vision/0.23/models/generated/torchvision.models.detection.maskrcnn_resnet50_fpn_v2.html), [SAM2 processor](https://huggingface.co/docs/transformers/model_doc/sam2), [Grounding DINO](https://huggingface.co/docs/transformers/model_doc/grounding-dino). Phiên bản/revision cụ thể của phiên làm việc nằm trong metadata; tài liệu online có thể cập nhật.

## Probe recovery

1. Oracle pixel ban đầu gồm điểm gần/sau camera, tạo max error 0,000848 px do phép chia depth gần 0; depth error vẫn ở cỡ 10⁻¹³ m. Sau chẩn đoán, probe so pixel tại depth ≥0,5 m, giữ unfiltered số để không che kết quả. Core projection không được sửa theo sai lệch số học này.
2. Trong bản sửa, thử SAM2 `use_fast=False` thất bại: Transformers 5.0 báo không có slow implementation. Chuyển SAM2 sang fast rõ ràng, giữ DINO slow rõ ràng; processor thật postprocess đúng ảnh 900×1600. Đây là lỗi phát hiện trong bản đang sửa, không gán cho baseline.
3. Fixture patch từng attribute của Transformers lazy module bị late import ghi đè, vô tình gọi loader model thật. Lượt isolated red bị dừng; gate v3 báo thiếu safetensors. Đã sửa fixture tại import boundary, bật offline, 58 ca focused và gate v4 đều đạt. Không tính lượt đó là lỗi sản phẩm.
4. Gate đầu có WinError 5 tại os.replace trong test review concurrency cũ; recheck riêng PASS lần 1, FAIL lần 2. Không khẳng định tác nhân khóa file. Thêm fault injection transient/persistent, bounded retry dùng chung cho JSON/NPZ; gate v2 và v4 đạt. Raw intermediate XML được giữ trong out/ và tóm tắt trong regression-summary.

Operator smoke dùng network Torchvision thật **khởi tạo ngẫu nhiên**, resize tối đa 64 px; SAM2 processor dùng synthetic logits, chưa forward pretrained SAM2. Cold/hot cache equality chỉ kiểm hợp đồng lưu/nạp. Các kết quả đó không xác nhận semantic accuracy hoặc G7 của sản phẩm.
