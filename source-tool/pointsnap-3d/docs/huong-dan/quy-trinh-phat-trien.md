# Quy trình phát triển PointSnap 3D

Cách làm để mỗi thay đổi (luật mới, chỉnh ngưỡng, model mới) **đo được là tốt hơn** và không làm hỏng chỗ khác. Đọc cùng
[CONVENTIONS.md](../../CONVENTIONS.md) (hệ tọa độ, mã luật) và [hướng dẫn huấn luyện](huan-luyen-box-critic.md).

## 1. Nhánh, PR, review

- **Không push thẳng `main`**, kể cả tài liệu. Mỗi việc một nhánh: `feat/<mã>-...`, `fix/...`, `tune/...`, `perf/...`,
  `docs/...`. Xong thì mở PR vào `main`, người còn lại review rồi mới merge.
- CI (`.github/workflows/test.yml`) chạy `pytest` và test extension cho mọi PR. **Đỏ thì không merge.**
- Mô tả PR có: việc gì, **số liệu trước / sau** (mục 3), cách kiểm lại, việc chưa làm. PR đổi ngưỡng mà làm tăng báo nhầm
  ghi rõ "**cần nhóm quyết**" trong tiêu đề.
- Không commit token, dữ liệu nuScenes, model `.pt`, file sinh ra (`out/`, `.pcd`, báo cáo).

## 2. Chia dữ liệu: tinh chỉnh và kiểm tra

nuScenes v1.0-mini có 10 cảnh, chia cố định:

| Bộ | Cảnh | Dùng để |
|---|---|---|
| **Tinh chỉnh** (`--scenes tuning`) | scene-0061, 0553, 0757, 0916, 1094 | Chọn ngưỡng, thử ý tưởng, huấn luyện model — **chạy bao nhiêu lần cũng được** |
| **Kiểm tra** (`--scenes test`) | scene-0103, 0655, 0796, 1077, 1100 | Đo **một lần** cho bản cuối, lấy số báo cáo |

Chọn ngưỡng trên cảnh kiểm tra rồi báo cáo số của chính cảnh đó là tự lừa mình: số đẹp nhưng không dùng được trên dữ liệu
mới.

## 3. Đo: `pointsnap eval`

```bash
pointsnap eval --scenes tuning --rounds 10 --errors all --out out/eval/tuning
```

Eval chèn lỗi giả theo [đề xuất mục 8.1](../thiet-ke/de-xuat-de-tai.md#81-bộ-lỗi-chèn-giả) (lơ lửng, kích thước, nhảy, tách
ID, nội suy, xoay / lật, dời / co box, vẽ trùng…) vào từng cảnh, quét, rồi đếm:

| Chỉ số | Ý nghĩa | Mục tiêu |
|---|---|---|
| **Báo nhầm trên nhãn sạch** | Số mục Cảnh báo / Lỗi trên 100 box khi quét nhãn chuẩn chưa chèn lỗi | ≤ 2 / ≤ 0,5 |
| **Tỉ lệ bắt** | % lỗi chèn được báo đúng loại, đúng box, mức Cảnh báo trở lên | ≥ 90% với lỗi lớn |
| **Phân mức đúng** | Lỗi lớn (Z 40 cm, kích thước 30%, nhảy 4 m, lật 180°) báo ở mức Lỗi | ≥ 80% |

Kết quả: `ket-qua.md` (đọc), `summary.json` (máy đọc, dùng để vẽ biểu đồ), `outcomes.json` (từng lỗi chèn, để xem vì sao
sót). Mỗi mức chèn chỉ 6 – 30 mẫu nên một lỗi bắt thêm / sót là 3 – 15 điểm %; với thay đổi nhỏ, dùng **script đo riêng**
với hàng trăm – hàng nghìn mẫu:

| Script | Đo |
|---|---|
| `scripts/eval_heading_points.py` | `heading.points` theo góc xoay |
| `scripts/eval_camera.py` | lớp ảnh camera (Mask R-CNN / Grounding DINO + SAM 2.1) |
| `scripts/verify_ground.py` | sai số ước lượng mặt đất trên box chuẩn |
| `scripts/build_size_stats.py` | thống kê kích thước theo class để đặt `size.manual_ranges` |
| `scripts/ve_hinh_minh_hoa.py` | vẽ lại hình trong báo cáo từ `summary.json` mới |

Quét một cảnh không cần CVAT, có chèn lỗi, để xem tận mắt:

```bash
pointsnap nuscenes scan --scene scene-0103 --inject --rate 0.3 --out out/demo
```

## 4. Thêm một luật mới — checklist

Luật mới phải trỏ được tới **một điều khoản đo được của spec** (bảng truy vết ở
[đề xuất mục 4.7](../thiet-ke/de-xuat-de-tai.md#47-bám-spec-gán-nhãn-giai-đoạn-3)). Những chỗ phải sửa (lấy theo commit C7
`lidar.missing`; lần đó quên extension, phải sửa sau ở PR #50):

| # | Ở đâu | Làm gì |
|---|---|---|
| 1 | `pointsnap/detectors/<loại>.py` | Hàm phát hiện trả `Finding` có `rule`, `severity`, câu `message` nói rõ **sai bao nhiêu, so với ngưỡng nào** |
| 2 | `pointsnap/config.yaml` + `pointsnap/core/config.py` | Ngưỡng (có chú thích đơn vị), cờ bật / tắt trong `RulesConfig` |
| 3 | `pointsnap/core/scanner.py` | Hàm `check_<...>`, thêm vào `_RULE_SWITCH` và danh sách bộ phát hiện |
| 4 | `tests/test_<...>.py` | Test có đáp án: nhãn đúng **không báo**, nhãn sai **báo đúng frame**; dùng `tests/scenario_sim.py` cho tình huống giao thông |
| 5 | `pointsnap/web/static/index.html`, `app.js` | Công tắc ở trang Guideline (`id="rule-<tên>"`), nhãn ngắn, gợi ý sửa (`RULE_FIX_TIPS`) |
| 6 | `extension/src/core.js`, `content.js`, `extension/tests/core.test.js` | Gợi ý sửa, mẫu câu nhận luật từ cờ (`RULE_PATTERNS`), nhãn ngắn, test câu cờ thật |
| 7 | `pointsnap/eval/` | Kiểu lỗi chèn giả tương ứng (nếu có) và ánh xạ luật ↔ lỗi để eval tính tỉ lệ bắt |
| 8 | `CONVENTIONS.md`, đề xuất mục 4.1 / 4.7 | Mã luật, ý nghĩa, điều khoản spec |
| 9 | `docs/ket-qua/` | Số liệu: báo nhầm trên nhãn sạch, tỉ lệ bắt, trên cảnh tinh chỉnh; cảnh kiểm tra một lần |

Kiểm nhanh mục 5 – 6 bằng đoạn sau (đã dùng khi bàn giao 12/10): mọi luật trong `RulesConfig` có công tắc trên web, và mọi
mã luật có gợi ý sửa trong extension.

```bash
grep -o "'[a-z_]*\.[a-z_.]*':" extension/src/core.js | sort -u     # luật extension biết
grep -o 'id="rule-[a-z0-9-]*"' pointsnap/web/static/index.html | sort -u
```

## 5. Chỉnh ngưỡng

1. Xem tay 20 mục báo nhầm trên nhãn sạch của luật (web, màn **Duyệt nhanh**): báo nhầm do đâu (dốc, bờ vỉa, LiDAR thưa,
   vật bị che…)? Sửa nguyên nhân trước, đổi ngưỡng sau.
2. Đổi ngưỡng, chạy `eval --scenes tuning`. Ghi cả hai chiều: báo nhầm và tỉ lệ bắt.
3. Đổi ngưỡng **đánh đổi** (bắt thêm nhưng báo nhầm tăng) → PR riêng, tiêu đề có "cần nhóm quyết" (ví dụ PR #45, #48).
4. Chốt xong mới chạy `eval --scenes test` một lần.

## 6. Trước khi mở PR

- [ ] `python -m pytest -q` xanh (cả `NUSCENES_ROOT=... ` để chạy test dữ liệu thật nếu đụng tới đọc dữ liệu / mặt đất)
- [ ] `cd extension && node --test tests/*.test.js` xanh nếu đụng extension hoặc thêm luật
- [ ] Eval cảnh tinh chỉnh trước / sau, dán bảng vào mô tả PR
- [ ] Đụng hệ tọa độ hay định dạng thì cập nhật `CONVENTIONS.md`
- [ ] Thêm luật: đủ 9 mục ở checklist mục 4
- [ ] Ghi lên CVAT (tạo task, gắn cờ) chỉ khi người phụ trách đồng ý; thử trên job 4 (task tạo lại 12/10)

## 7. Sau khi merge

- Chạy lại `eval --scenes test` một lần cho đợt merge, cập nhật số trong báo cáo và vẽ lại hình:

  ```bash
  pointsnap eval --scenes test --rounds 10 --errors all --out out/eval/test
  python scripts/ve_hinh_minh_hoa.py --dataroot $NUSCENES_ROOT --eval-test out/eval/test/summary.json
  ```

- Cập nhật trạng thái trong [quan-ly/TASKS.md](../../quan-ly/TASKS.md).
