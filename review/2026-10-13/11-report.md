# Báo cáo review 11 — Verifier, Critic và học từ kết luận

Ngày **13/10/2026**, Asia/Saigon. Nhánh `codex/review-11-verifier-learning`.

## Kết quả và nguồn

- Nhận phần 09–10 bằng fast-forward tới `8fce666`; giữ ancestry của main `d18b1a9`.
- Commit sửa: **`9d11071`**. Sửa **10 nhóm lỗi**, thêm **49 ca hồi quy**.
- Gate cuối: **713 Python PASS, 0 FAIL/ERROR/XFAIL, 3 SKIP; 37 Node PASS**. Hai test Critic từng SKIP đã chạy bằng PyTorch CPU thật.
- Coverage 6 module đã sửa: **833/900 = 92,56%**; package `pointsnap`: **6.504/7.089 = 91,75%**. Đây là statement coverage, kết hợp suite và training smoke. Riêng CLI eval 63,64%; coverage không chứng nhận mọi nhánh CLI.
- NuScenes mini thật: **10 cảnh, 14.104 box**; kết quả static trước/sau không đổi danh tính hoặc mức finding. Tuning 8.664 box, held-out 5.440 box.
- Critic export/training thật: **194 mẫu**, chỉ 3 frame đầu của `scene-0061` và `scene-0553`, 2 mẫu/box đủ điểm. Train trên 0061, validation trên 0553; không dùng 5 cảnh held-out để học/chỉnh ngưỡng.
- Ensemble CPU 2 seed (11, 12), 2 epoch, width 16: checkpoint đúng hợp đồng, đầu ra hữu hạn; hai lần học cho cùng đầu ra; ensemble bằng trung bình hai member.
- Hoàn tất review/sửa và bàn giao. **Chưa nghiệm thu chất lượng model chính thức, precision tay, GPU hoặc CVAT thật.**

## Checklist 8 ca

| Mã | Trạng thái | Bằng chứng và giới hạn |
| --- | --- | --- |
| TC-11-001 | Đạt kiểm tự động và GT thật | Oracle tính tay vật world đứng yên khi ego dịch/quay; một box lệch 0,6 m báo ERROR đúng frame; thiếu pose và vật chuyển động chậm không báo. Static bỏ interpolation, tách ID/class. So đủ 10 cảnh mini trước/sau. |
| TC-11-002 | Đạt toán/feature và export | Feature rỗng/ít điểm, chuẩn hóa mét/radian, target nhiễu khôi phục box chuẩn trong test độc lập. Seed riêng theo scene, đổi thứ tự scene giữ nguyên arrays. Empty export có tensor shape hợp lệ. |
| TC-11-003 | Đạt runtime CPU; quality/GPU chưa nghiệm thu | TorchScript scripted test và checkpoint ensemble thực sự huấn luyện đều chạy. Batch thiếu, logit ma trận, delta 6 cột, integer, NaN bị từ chối; file hỏng thất bại rõ; thay file cùng path nạp lại. Không load checkpoint từ nguồn không tin cậy. |
| TC-11-004 | Đạt logic reference hợp lệ | Track có bias đều không báo, box lệch riêng báo; reference tách ID/class, bỏ interpolation; track ngắn dùng sigmoid thô. Threshold finding khớp severity. Score được ghi là chưa hiệu chuẩn; median có giới hạn khi nhiều outlier hoặc lệch đều. |
| TC-11-005 | Đạt export/train/ensemble CPU | Scene được giữ khi tính reference track; shape ID -1 không làm reference. Split theo file scene, 2 seed chạy lại có đầu ra giống nhau, ensemble trung bình đúng; CLI chặn xuất held-out và không ghi đè dataset cũ. Notebook được đọc và kiểm hợp đồng tương ứng, chưa chạy Colab/GPU. |
| TC-11-006 | Đạt storage và verdict synthetic | Sửa/xóa verdict có hiệu lực khi học lại; same observation qua rescan chỉ tính một lần, latest snapshot là bản tham chiếu. Tách job/project, ID 0 hợp lệ; JSON hỏng, verdict tự sinh, metadata sai bị từ chối. Không tạo verdict từ GT hoặc model. |
| TC-11-007 | Đạt grouped CV và severity/gate | Giữ cả nguồn CVAT/job trong một fold, ≥2 nhóm mới thử logistic; mẫu nhỏ/thiếu class dùng Beta. Không so CV loss từ dataset cũ. Class chưa học dùng thống kê luật. Tắt/bật adjust, biên đúng ngưỡng, số verdict tối thiểu và ERROR được kiểm. Hạ WARNING có thể làm gate đạt theo cấu hình. |
| TC-11-008 | Đạt storage/API; hard crash có thao tác phục hồi | Active model còn nguyên khi os.replace thất bại; history sao trước khi thay, version không tái dùng số đã archive, collision khác nội dung bị từ chối. File lock chặn writer CLI/web khác tiến trình; JSON/model schema hỏng trả StorageError (web 409). Sau kill cứng cần xác nhận tiến trình dừng rồi dọn lock. |

## Findings đã sửa

| Mã | Mức | Tái hiện trước sửa | Sửa |
| --- | --- | --- | --- |
| RV-11-001 | P2 | Hai box nội suy làm track đạt min_keyframes giả; class khác cùng ID bị so chung. | Static dùng manual visible keyframes và `(track_id, label)`. |
| RV-11-002 | P1 | Chỉ bật static hoặc Critic, thiếu pose/cloud vẫn có thể gate ĐẠT. | Bổ sung pose requirement cho static và cloud/runtime requirement cho Critic. Model rỗng vẫn là tắt theo guideline. |
| RV-11-003 | P2 | Có PyTorch nhưng thiếu torchvision làm scanner bỏ qua Critic. | Critic có kiểm tra runtime riêng, không dùng dependency camera. |
| RV-11-004 | P2 | `zip` cắt batch sai âm thầm, delta NaN/shape sai lọt vào finding; sigmoid(-1000) tràn; file thay cùng path dùng cache cũ. | Kiểm tensor contract/dtype/finite; sigmoid ổn định; cache theo path tuyệt đối và mtime_ns/size. |
| RV-11-005 | P2 | Reference Critic trộn label/interpolation; ERROR ghi threshold WARNING; message gọi sigmoid là xác suất. | Tách ID/class, chỉ manual; threshold theo severity, ghi rõ score chưa hiệu chuẩn. |
| RV-11-006 | P2 | Empty export shape (0,) sai hợp đồng; có thể ghi đè dữ liệu hoặc xuất held-out để học. Seed phụ thuộc thứ tự scene. | Shape/dtype đúng cả empty; chặn overwrite; CLI chặn 5 held-out; seed riêng theo scene. |
| RV-11-007 | P2 | Calibration trộn ID giữa nhiều scene và gộp shape -1 thành track; file NPZ không được đóng; ngưỡng nhỏ bị in thành 0,0 và tỷ lệ mục tiêu bị diễn đạt như tỷ lệ đã đạt. | Giữ scene/class trong reference, bỏ shape; context manager và schema arrays; validate đầu vào training; in ngưỡng đủ precision và tỷ lệ validation đo được. |
| RV-11-008 | P2 | Same finding từ hai rescan đếm hai verdict trái nhau; parser crash hoặc nhận NaN/nhãn không phải người duyệt. | Dedupe theo nguồn/owner/frame/rule/class/severity/value/threshold và latest snapshot; reuse strict storage/review validator. |
| RV-11-009 | P2 | Cùng job/track vào cả train và test CV; model mới bị từ chối bởi CV loss cũ từ corpus khác; label chưa học vẫn nhận logistic confidence. | Group theo job, CV trên cùng fold với baseline Beta; thiếu nhóm thì không dùng logistic; unknown label/rule fallback và sigmoid ổn định. |
| RV-11-010 | P1 | Chuyển active model vào history trước khi ghi mới có thể làm mất active; writer cạnh tranh/restore tái dùng version; model JSON không kiểm schema. | Atomic JSON write, copy history trước thay, exclusive project lock, version xét history, collision từ chối, strict model load. |

42/47 ca được chọn thất bại trên package baseline `8fce666` đã xác minh đường dẫn; 5 ca giữ hành vi đúng, 2 ca training bị loại vì helper nạp script hiện tại. Hai ca training đó đã được tái hiện FAIL riêng trước sửa. Gate cuối chứa đủ 49 ca mới và các suite cũ.

## Dữ liệu thật và diễn giải

Static tuning: **8 WARNING, 1 ERROR** trước/sau. Held-out: **15 WARNING, 1 ERROR** trước/sau. Đây là finding trên GT, chưa có người duyệt xác nhận báo nhầm. Không chỉnh ngưỡng từ kết quả held-out.

Export có 96 mẫu scene-0061 (55 lỗi chèn, 40 unchanged) và 98 mẫu scene-0553 (65 lỗi chèn, 32 unchanged). Các mảng hữu hạn; frame chỉ 0–2. Nhãn `is_error` là nhãn nhiễu kiểm soát cho training Critic, không phải human verdict của learning.

Training smoke giữ validation theo scene. Checkpoint trả `(98,)` và `(98,7)`. Sai khác tối đa giữa hai lần chạy và giữa ensemble với trung bình member đều **0**. Ngưỡng sigmoid gợi ý khoảng **0,54612**; validation rất nhỏ, raw-score recall ở ngưỡng này là **0%** trong smoke. Không đưa checkpoint hoặc ngưỡng smoke vào guideline, không dùng số liệu này để chọn model chính thức. Logit-relative smoke cũng không chứng minh recall/precision sản phẩm.

## Evidence

| Mã | Artifact |
| --- | --- |
| EV-11-001 | [verification.json](evidence/11/verification.json): SHA, source hash khớp commit sau chuẩn hóa LF, XML hash, PASS/SKIP và coverage. |
| EV-11-002 | [regression-summary.json](evidence/11/regression-summary.json): baseline phản ví dụ và các lượt red liên quan. |
| EV-11-003 | [real-data-summary.json](evidence/11/real-data-summary.json), [verifier_probe.py](evidence/11/verifier_probe.py): static GT và export giới hạn hai cảnh tuning. |
| EV-11-004 | [training-summary.json](evidence/11/training-summary.json), [training_probe.py](evidence/11/training_probe.py): train/validation split, seed, shape, repeat/member equality và checkpoint hash. |
| EV-11-005 | [runtime-recovery.md](evidence/11/runtime-recovery.md): PyTorch riêng, DLL và các lần probe không hợp lệ đã loại khỏi nghiệm thu. |

Export probe chạy trước lần sửa định dạng in ngưỡng cuối; source hash lúc đo được giữ nguyên. Static/Critic không đổi sau đo; training probe cuối lưu hash script sau sửa và verification đối chiếu với code commit.

Raw NPZ, checkpoints, runtime và XML nằm trong `source-tool/pointsnap-3d/out/` bị ignore. Không commit dữ liệu, weights hoặc secret.

## Inventory và file dùng chung

| File owner 11 | Kết luận |
| --- | --- |
| `pointsnap/cli/learn_cmd.py` | Đã đọc đường dẫn ProjectManager; StorageError được outer CLI xử lý. Chưa thao tác project thật của người dùng. |
| `pointsnap/critic.py` | Sửa/export/runtime; test TorchScript, dữ liệu mini và checkpoint trained chạy. |
| `pointsnap/detectors/static.py` | Sửa; oracle world và GT 10 cảnh đạt. |
| `pointsnap/learn.py` | Sửa; verdict/CV/failure/history/schema/gate kiểm bằng fixtures riêng. |
| `scripts/colab_train_critic.ipynb` | Đã đọc flow và hợp đồng; Colab/Drive/GPU chưa chạy. |
| `scripts/train_critic_example.py` | Sửa; CPU ensemble smoke và reproducibility đạt. |
| `tests/test_critic.py` | 5 PASS, gồm 2 test PyTorch trước đây SKIP. |
| `tests/test_learn.py` | 4 PASS; thêm 49 hồi quy ở `tests/test_verifier_review11.py`. |

File dùng chung: `core/scanner.py` giao 14 kiểm gate/runtime; `cli/eval_cmd.py` giao 15 kiểm CLI/export; hướng dẫn training owner 16 đã cập nhật semantics. `web/runner.py`, `web/preview.py`, `web/storage.py`, `web/app.py` đã đọc flow và suite web/API cũ đạt, không sửa trong phần này.

## Giới hạn và bàn giao

1. Cần checkpoint chính thức có provenance/split và human verdict từ nhiều job để nghiệm thu chất lượng; synthetic verdict không chứng minh precision tay. Toàn sản phẩm G7 chưa được chứng minh từ subset static này.
2. Chưa có GPU/Colab, CUDA memory/release, CVAT hoặc extension thật. 3 SKIP còn lại là live-CVAT; không bật vì các ca đó ghi nhãn/cờ lên hệ thống thật.
3. Median track không bắt lệch đều; đa số reference sai làm giảm phát hiện. Đầu vào phải có identity/frame không mơ hồ. Việc kiểm owner/frame trùng và các điểm nối dữ liệu giao phần 14.
4. Checkpoint cache nhận đổi mtime/size thông thường; thay byte nhưng giữ cả mtime và size có thể cần restart tiến trình. Chỉ dùng file từ tác giả tin cậy; TorchScript không có sandbox an toàn cho mã bất kỳ.
5. Gate báo thiếu runtime/cloud/pose ở cấp job; không chứng nhận mọi box đủ điểm hoặc mọi track đủ reference. `min_points`, occlusion và track ngắn vẫn giới hạn coverage.
6. Latest snapshot của cùng observation có thể làm số verdict giảm khi run mới chưa duyệt. Legacy thiếu source/ID không dedupe chắc chắn; khác số đo được giữ như quan sát khác. Learning dùng severity đã lưu trong run, kể cả severity đã hạ; kiểm ảnh hưởng khi bật adjust ở phần 14/15.
7. Hard crash có thể để `.learn.lock`; phải kiểm tiến trình dừng trước dọn. Restore hiện là thao tác file khi không có writer, chưa có nút/API restore riêng. Hai nguồn job là điều kiện tối thiểu cho grouped CV, vẫn quá ít để kết luận generalization.

Tiếp theo: **12 — camera models**, nhận nhánh 11 trước khi làm. Runtime review riêng hiện có torch CPU, chưa có torchvision/transformers/checkpoint camera.
