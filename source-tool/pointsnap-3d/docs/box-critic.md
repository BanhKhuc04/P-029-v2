# Box Critic — lớp 3 của Box Verifier (nhóm tự huấn luyện)

Box Critic là model nhỏ học cách nhìn một box giống người duyệt: nhìn điểm LiDAR quanh box và đặc trưng của box, trả
lời **box có sai không** và **cần sửa bao nhiêu**. PointSnap đã có sẵn hai đầu: xuất dữ liệu huấn luyện và chỗ cắm model.
Phần huấn luyện để nhóm tự làm và cải tiến.

## 1. Xuất dữ liệu

```bash
pointsnap critic-data --scenes tuning --samples-per-box 6 --out data/critic
```

Mỗi box nhãn chuẩn nhìn thấy được (≥ 10 điểm LiDAR) sinh `samples-per-box` mẫu: 35% giữ nguyên, còn lại làm nhiễu ngẫu
nhiên (dời ngang ≤ 0,6 m, nâng / hạ ≤ 0,3 m, co / phóng ≤ 25% từng chiều, xoay ≤ 30°). Điểm LiDAR được lấy quanh **box
đã làm nhiễu** đúng như bộ quét thấy (bỏ mặt đất, điểm của box khác, chỉ giữ điểm nối liền với vật).

File `data/critic/<cảnh>.npz`:

| Mảng | Shape | Ý nghĩa |
|---|---|---|
| `points` | (N, 256, 4) | 256 điểm của vật: x, y, z hệ box đã nhiễu **chia nửa kích thước box**, cờ 1 nếu điểm nằm trong box |
| `meta` | (N, 20) | dài, rộng, cao (m), khoảng cách / 50, log(1 + số điểm), one-hot 15 class (`pointsnap.critic.CLASSES`) |
| `is_error` | (N,) | 1 nếu nhiễu vượt dung sai (dời > 15 cm, Z > 8 cm, kích thước > 6%, hướng > 4°) |
| `target` | (N, 7) | sửa từ box nhiễu về box chuẩn: dx, dy, dz (m, hệ box nhiễu), dl, dw, dh (m), dyaw (rad) |
| `track_id`, `frame` | (N,) | để chia tập theo track, xem lại mẫu |

**Chia tập:** huấn luyện trên `--scenes tuning`, giữ nguyên 5 cảnh `test` để đo bằng `pointsnap eval` (không xuất dữ liệu
từ cảnh test, nếu không số liệu bị rò).

## 2. Huấn luyện

Script mẫu `scripts/train_critic_example.py` (PointNet nhỏ ~53 nghìn tham số, chạy được trên RTX 3050 4 GB hoặc CPU):

```bash
python scripts/train_critic_example.py --data data/critic --epochs 30 --out models/critic.pt
```

Script để riêng **cảnh cuối** (theo tên file, đổi bằng `--val-scenes`) làm cảnh kiểm tra, giữ model có loss kiểm tra thấp
nhất, rồi in ngưỡng gợi ý `critic.min_logit_rise` / `critic.error_logit_rise` để điền vào guideline (mục 4).

**Bài học từ lần huấn luyện đầu (10/10).** Model đầu tiên báo sai 0,8% box chuẩn trên cảnh đã học nhưng **30%** trên cảnh
mới (AUC 0,97 → 0,88): học thuộc. Ba nguyên nhân và cách đã sửa trong script:

| Nguyên nhân | Cách sửa |
|---|---|
| Kiểm tra chia ngẫu nhiên theo mẫu: một box sinh 20 mẫu nên có mặt ở cả hai tập, không thấy học thuộc | Kiểm tra theo **cảnh** |
| Mẫu giữ nguyên luôn mang đúng kích thước gốc: model nhớ kích thước của ~3 600 box thay vì nhìn điểm | Model bỏ 3 cột kích thước tuyệt đối (`--use-dims` để bật lại) |
| Ít dữ liệu (4 – 5 cảnh) | Lật trái / phải, trước / sau, rung điểm; dropout; weight decay 1e-3 |

Sau khi sửa, trên cảnh để riêng vẫn còn ~20% box chuẩn có xác suất sai > 0.7: model lệch đều theo từng vật / cảnh. Vì vậy
luật `critic.box` so **logit của box với trung vị các frame khác của cùng track** (như các luật khác của PointSnap): ở mức
0,5% box chuẩn bị báo, bắt được 35% box dời > 0,3 m, 33% box xoay > 10°, 27% box sai kích thước > 0,3 m (scene-0916 để
riêng). Muốn tốt hơn nữa thì cần **thêm dữ liệu** (nuScenes trainval, dữ liệu Việt Nam đã gán).

### Huấn luyện trên Google Colab (GPU miễn phí)

Colab cho GPU T4 16 GB, đủ cho mạng lớn hơn và nhiều dữ liệu hơn RTX 3050 4 GB.

1. Trên máy: `pointsnap critic-data --scenes tuning --samples-per-box 20 --out critic-data`, chép
   `scripts/train_critic_example.py` vào `critic-data/`, nén thành `critic-data.zip`.
2. Tải `critic-data.zip` lên **My Drive** của mình, không chia sẻ công khai (giấy phép nuScenes không cho phân phối lại;
   dữ liệu Việt Nam của nhóm cũng vậy).
3. Mở [colab.research.google.com](https://colab.research.google.com) → *File → Upload notebook* →
   `scripts/colab_train_critic.ipynb`; *Runtime → Change runtime type → T4 GPU*; chạy lần lượt các ô.
4. Notebook kiểm tra `critic.pt` đúng hợp đồng (mục 3), lưu vào My Drive và tải về máy. Khai `critic.model` (mục 4), đo
   bằng `pointsnap eval --scenes test`.

Hướng cải tiến gợi ý:
- Thêm dữ liệu: `--samples-per-box` lớn hơn, thêm cảnh nuScenes trainval, rồi dữ liệu Việt Nam đã gán.
- Thêm **ảnh**: đặc trưng ảnh vùng chiếu (backbone ảnh có sẵn) nối vào `meta`; giữ đúng thứ tự đầu vào ở cả hai đầu.
- Thêm **lỗi thật**: mục người duyệt đánh *Đúng là lỗi* (lớp 4) làm ví dụ khó.
- Thay PointNet bằng PointNet++ / DGCNN khi có GPU mạnh hơn.

## 3. Hợp đồng của model

PointSnap nạp file **TorchScript** và gọi:

```python
logit, delta = model(points, meta)   # points: float32 (B, 256, 4), meta: float32 (B, 20)
# logit: (B,) — sigmoid(logit) là xác suất box sai
# delta: (B, 7) — dx, dy, dz, dl, dw, dh, dyaw như `target`
```

Đặc trưng do `pointsnap.critic.box_features` tạo, dùng chung cho xuất dữ liệu và lúc quét. Đổi đặc trưng thì đổi ở hàm
này và xuất lại dữ liệu.

## 4. Dùng trong PointSnap

Trong guideline của dự án (tab Guideline → YAML, hoặc file `--config`):

```yaml
critic:
  model: D:/models/critic.pt
  min_points: 20          # chỉ chấm box có ≥ 20 điểm của vật
  min_logit_rise: 4.4     # box thuộc track: logit sai cao hơn trung vị các frame khác của track > 4.4: Cảnh báo
  error_logit_rise: 6.0   # > 6.0: Lỗi  (hai số này lấy từ dòng "Ngưỡng gợi ý" của script huấn luyện)
  min_probability: 0.7    # box lẻ không thuộc track: xác suất sai ≥ 0.7: Cảnh báo
  error_probability: 0.9  # ≥ 0.9: Lỗi
```

Luật `critic.box` báo kèm **gợi ý sửa** dạng *"dời (+0.32, −0.05, +0.00) m, kích thước (…), xoay +3.1°"*. Tool không tự
sửa box. Đo hiệu quả bằng `pointsnap eval --scenes test` (luật `critic.box` được tính cho lỗi chèn dời / co / xoay box).
