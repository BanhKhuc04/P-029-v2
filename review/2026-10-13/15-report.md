# Review 15 — Chất lượng, precision và hiệu năng

Model review **gpt-6.1-sol**. Candidate code `3a8bde2`, base main `7ec580a`. G7 theo quyết định người dùng: precision tay từng luật, proxy riêng, thiếu mẫu vẫn chưa nghiệm thu. **Đánh giá checkpointed 10 vòng đang chạy; báo cáo này chưa chốt số recall/proxy mới.**

## Bảng 8 ca

| Ca | Trạng thái | Evidence/giới hạn |
|---|---|---|
| TC-15-001 | PASS truy vết mới; số cũ giữ lịch sử | SHA/config/seed/split/checkpoint/hash ảnh được ghi trong evidence. Bảng 2,98/0,59 và 64/65 không tự đại diện candidate. Lượt eval đầu bị dừng sau 6 scene, không có summary hoàn chỉnh, không báo PASS. |
| TC-15-002 | Đang tổng hợp core/c1; luật mới PARTIAL | Canonical `all` chỉ core+c1; chia error/class/scene và floating evidence riêng từ outcomes. Không gán recall cho camera/missing/spec/critic thiếu injection protocol. Missing dùng phép xóa box riêng ở PR #67. |
| TC-15-003 | PASS tự động | Full evaluation-review/recheck/metrics suites; khớp rule family + track/frame, warning+, finding không được credit cho hai injection. Size accuracy dùng ratio/điểm %, không dùng cm; denominator rỗng N/A. |
| TC-15-004 | PARTIAL — thiếu truth độc lập | CSV hiện có floating 68 đúng/2 FP, 25 Không rõ/4 chưa chấm, precision mô tả 97,14% trên 70 quyết định/30 track. Size chỉ 1 quyết định; các luật khác thiếu ≥20 mẫu. Hai verdict Web thử không phải truth. Không có ≥40 verdict từ ≥2 nguồn độc lập để nghiệm thu học. |
| TC-15-005 | Đang chạy | Mỗi scene 10 vòng, seed 0, canonical catalog all, config giữ cố định; output từng scene để resume. Tách 5 tuning và 5 reviewed-heldout; tập sau từng dùng chỉnh evidence/human review nên không độc lập. |
| TC-15-006 | PARTIAL | A/B curb theo cùng dữ liệu/verdict ở PR #61; missing 98 mục deletion trước/sau ở PR #67 cùng protocol và giữ nguyên kết quả từng target. Chưa A/B human precision đầy đủ cho heading 12°/ensemble/camera/fit-outside mới; giữ #48 chờ mẫu. |
| TC-15-007 | PASS tập điểm/helper, PARTIAL tài nguyên | EV-15-001: OtherBoxPoints trên scene0061 frame0, 34.688 điểm/65 box, 30 query ×10; tập điểm bằng brute force. Build 4,82 ms; brute median/p95 1,184/1,757 ms, index 0,081/0,220 ms. Chưa đo peak RSS riêng, không suy thành tốc độ toàn app/minimum hardware. |
| TC-15-008 | PASS GPU smoke/cache; PARTIAL CPU/long/OOM/quality | EV-15-002–004: Mask R-CNN, DINO+SAM2, hybrid mỗi loại 3 ảnh thật offline pretrained, cache roundtrip PASS. Không human precision, chưa fresh CPU vision install, scan dài/OOM acceptance hay trained Critic ensemble chất lượng mới. Proxy dùng 2,0/0,5 tham khảo; không thay G7. |

## Phương pháp và nguồn

Các file eval/evaluate.py, eval/metrics.py, cli/eval_cmd.py, split.py, scripts/run_eval_suite.py, eval_heading_points.py, eval_metrics.py, verify_ground.py và docs snapshot owner15 có kết luận riêng trong [inventory](evidence/16/inventory.json). Metrics canonical dùng fault-level recall và finding-level matching; finding trên GT có thể là lỗi nhãn thật, không mặc nhiên false positive.

Lượt đầu `out/all-tests/20261013-213721-252975` bị ngắt khi môi trường dừng: log 6 scene/injections được giữ; không có outcomes đầy đủ. [checkpoint_eval.py](evidence/15/checkpoint_eval.py) gọi đúng `run_evaluation` từng scene, 10 vòng/seed 0/offset theo round, không đổi detector/matching. Resume chỉ khi marker đã hoàn tất, package tree và config/dataset/rounds khớp. Hai split dùng thư mục scene riêng; phép tổng hợp chỉ chạy khi cả 10 scene hoàn tất. Không chỉnh ngưỡng sau khi xem kết quả.

EV-15-001: [ground_index_benchmark.py](evidence/15/ground_index_benchmark.py), [ground-index.json](evidence/15/ground-index.json). EV-15-002–004: [Mask](evidence/15/model-maskrcnn.json), [DINO/SAM](evidence/15/model-gdino-sam2.json), [hybrid](evidence/15/model-hybrid.json); Torch2.6.0+cu124/torchvision0.21/transformers5.19, RTX3050 Laptop4GB. 9 ảnh execution/cache không chứng minh độ chính xác của model trên mọi cảnh. Timings có cạnh tranh với pha khác, không benchmark phần cứng tối thiểu.

## Findings/giới hạn

- **RV-15-001 — Thiếu mẫu:** CSV và summary human có mốc khác nhau (68/70 so với bản cập nhật 64/65); không tự sửa verdict nguồn. Đã thống kê CSV hiện có ở PR #64, Không rõ/chưa chấm không nằm mẫu số precision.
- **RV-15-002 — Held-out đã dùng chỉnh:** `evidence.min_points=20`/single_box off dựa trên chấm tay reviewed-heldout; chỉ báo descriptive validation, cần dataset độc lập mới để nghiệm thu.
- **RV-15-003 — Interrupted evaluation:** giữ log đầu; thêm probe checkpoint theo scene thay vì suy số tổng từ 6 dòng progress.

Điều kiện còn thiếu cho nghiệm thu: truth từng luật từ reviewer, nhóm nguồn độc lập, test runtime vision dài và các A/B chất lượng chưa có oracle. Không thay người duyệt bằng verdict tự sinh.
