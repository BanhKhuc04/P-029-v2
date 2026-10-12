"""Huấn luyện mẫu Box Critic (lớp 3 của Box Verifier) — điểm xuất phát để nhóm tự cải tiến.

Mạng PointNet nhỏ: mỗi điểm (x, y, z hệ box chuẩn hóa, cờ trong box) qua MLP dùng chung, gộp max, nối với đặc trưng box
(khoảng cách, số điểm, class), ra 2 đầu: logit "box sai" và 7 giá trị sửa (dx, dy, dz, dl, dw, dh, dyaw).
Loss = BCE(box sai) + SmoothL1(sửa) chỉ tính trên mẫu sai. Xuất TorchScript để PointSnap nạp qua `critic.model`.

Ba điều rút ra từ lần huấn luyện đầu (học thuộc: box chuẩn bị báo sai 0,8% trên cảnh đã học nhưng 30% trên cảnh mới):
- **Kiểm tra theo cảnh**, không theo mẫu: mỗi box sinh nhiều mẫu, chia ngẫu nhiên thì box ở cả hai tập và không thấy học
  thuộc. Mặc định để riêng cảnh cuối (`--val-scenes`) và giữ model có loss kiểm tra thấp nhất.
- **Không cho model thấy kích thước tuyệt đối** (`--use-dims` tắt mặc định): mẫu giữ nguyên luôn mang đúng kích thước gốc
  nên model nhớ kích thước từng box thay vì nhìn điểm. Model tự bỏ 3 cột này bên trong, hợp đồng đầu vào giữ nguyên.
- **Tăng dữ liệu**: lật trái / phải, trước / sau (đổi dấu giá trị sửa tương ứng), rung nhẹ điểm.
Script in **ngưỡng gợi ý** để box chuẩn của cảnh kiểm tra bị báo ≤ 1% (dùng cho `critic.min_probability`).

Chạy (cần PyTorch):
    pointsnap critic-data --scenes tuning --out data/critic
    python scripts/train_critic_example.py --data data/critic --epochs 30 --ensemble 5 --out models/critic.pt
`--ensemble 5` huấn luyện 5 model với seed khác nhau rồi lấy trung bình (xuất thành một file TorchScript, cùng hợp đồng):
cùng cấu hình mà đổi seed, tỉ lệ bắt mẫu sai trên cảnh để riêng dao động 19 – 26%; trung bình 5 model ổn định ở ~31%.
Rồi khai trong guideline:  critic: {model: models/critic.pt, min_probability: <ngưỡng gợi ý>}  và đo bằng
pointsnap eval --scenes test
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import torch
from torch import nn


class BoxCritic(nn.Module):
    def __init__(self, meta_dim: int, width: int = 128, use_dims: bool = False, dropout: float = 0.3):
        super().__init__()
        self.use_dims = use_dims
        self.point_mlp = nn.Sequential(
            nn.Linear(4, 64), nn.ReLU(), nn.Linear(64, 128), nn.ReLU(), nn.Linear(128, width), nn.ReLU())
        self.head = nn.Sequential(nn.Linear(width + meta_dim, 128), nn.ReLU(), nn.Dropout(dropout),
                                  nn.Linear(128, 64), nn.ReLU())
        self.cls = nn.Linear(64, 1)
        self.reg = nn.Linear(64, 7)

    def forward(self, points: torch.Tensor, meta: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        if not self.use_dims:  # 3 cột đầu của meta là dài, rộng, cao (m)
            meta = torch.cat([torch.zeros_like(meta[:, :3]), meta[:, 3:]], dim=1)
        feat = self.point_mlp(points).max(dim=1).values
        hidden = self.head(torch.cat([feat, meta], dim=1))
        return self.cls(hidden).squeeze(1), self.reg(hidden)


KEYS = ("points", "meta", "is_error", "target", "track_id", "frame")


def load(files: list[Path]) -> dict[str, np.ndarray]:
    parts = [np.load(p) for p in files]
    return {k: np.concatenate([p[k] for p in parts]) for k in KEYS}


def augment(pts: torch.Tensor, tgt: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
    """Lật trái / phải (y), trước / sau (x) của box và rung điểm; đổi dấu giá trị sửa cho khớp."""
    pts, tgt = pts.clone(), tgt.clone()
    b = len(pts)
    flip_y = torch.rand(b, device=pts.device) < 0.5
    pts[flip_y, :, 1] *= -1
    tgt[flip_y, 1] *= -1
    tgt[flip_y, 6] *= -1
    flip_x = torch.rand(b, device=pts.device) < 0.5
    pts[flip_x, :, 0] *= -1
    tgt[flip_x, 0] *= -1
    tgt[flip_x, 6] *= -1
    pts[:, :, :3] += 0.01 * torch.randn_like(pts[:, :, :3])
    return pts, tgt


class Ensemble(nn.Module):
    """Trung bình logit và giá trị sửa của nhiều model huấn luyện với seed khác nhau: giảm phần lệch ngẫu nhiên theo
    từng vật / cảnh mà một model đơn lẻ học thuộc. Cùng hợp đồng đầu vào / đầu ra với `BoxCritic`."""

    def __init__(self, members: list[BoxCritic]):
        super().__init__()
        self.members = nn.ModuleList(members)

    def forward(self, points: torch.Tensor, meta: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        logits, deltas = [], []
        for m in self.members:
            logit, delta = m(points, meta)
            logits.append(logit)
            deltas.append(delta)
        return torch.stack(logits).mean(dim=0), torch.stack(deltas).mean(dim=0)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--epochs", type=int, default=30)
    parser.add_argument("--batch", type=int, default=512)
    parser.add_argument("--lr", type=float, default=1e-3)
    parser.add_argument("--weight-decay", type=float, default=1e-3)
    parser.add_argument("--width", type=int, default=128, help="số đặc trưng sau lớp gộp max")
    parser.add_argument("--dropout", type=float, default=0.3)
    parser.add_argument("--ensemble", type=int, default=1, help="số model (seed khác nhau) lấy trung bình")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--val-scenes", nargs="*", default=None,
                        help="tên file .npz (không đuôi) để kiểm tra; mặc định file cuối theo thứ tự tên")
    parser.add_argument("--use-dims", action="store_true", help="cho model thấy kích thước tuyệt đối (dễ học thuộc)")
    parser.add_argument("--target-fa", type=float, default=0.01, help="tỉ lệ box chuẩn bị báo để tính ngưỡng gợi ý")
    parser.add_argument("--quiet", action="store_true", help="không in từng epoch")
    parser.add_argument("--out", type=Path, default=Path("models/critic.pt"))
    args = parser.parse_args()

    files = sorted(args.data.glob("*.npz"))
    val_names = set(args.val_scenes) if args.val_scenes else {files[-1].stem}
    train_files = [p for p in files if p.stem not in val_names]
    val_files = [p for p in files if p.stem in val_names]
    if not train_files or not val_files:
        raise SystemExit("Cần ít nhất 2 cảnh: một để huấn luyện, một để kiểm tra (--val-scenes)")
    print("huấn luyện:", [p.stem for p in train_files], "| kiểm tra:", [p.stem for p in val_files])

    device = "cuda" if torch.cuda.is_available() else "cpu"
    train = {k: torch.from_numpy(v.astype(np.float32)) for k, v in load(train_files).items()}
    val_raw = load(val_files)
    val = {k: torch.from_numpy(v.astype(np.float32)) for k, v in val_raw.items()}
    bce, smooth = nn.BCEWithLogitsLoss(), nn.SmoothL1Loss(reduction="none")

    def batches(data, idx):
        for i in range(0, len(idx), args.batch):
            b = idx[i:i + args.batch]
            yield (data["points"][b].to(device), data["meta"][b].to(device), data["is_error"][b].to(device),
                   data["target"][b].to(device))

    def losses(logit, delta, y, tgt):
        reg = (smooth(delta, tgt).mean(dim=1) * y).sum() / y.sum().clamp(min=1)
        return bce(logit, y) + reg

    def predict(model):
        logits, deltas = [], []
        with torch.inference_mode():
            for pts, meta, _, _ in batches(val, np.arange(len(val["is_error"]))):
                logit, delta = model(pts, meta)
                logits.append(logit.cpu())
                deltas.append(delta.cpu())
        return torch.cat(logits), torch.cat(deltas)

    clean_val = (val["target"] == 0).all(dim=1).numpy()
    y_val = val["is_error"].numpy()

    def train_one(seed: int) -> BoxCritic:
        torch.manual_seed(seed)
        rng = np.random.default_rng(seed)
        model = BoxCritic(train["meta"].shape[1], width=args.width, use_dims=args.use_dims,
                          dropout=args.dropout).to(device)
        optim = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=args.weight_decay)
        sched = torch.optim.lr_scheduler.CosineAnnealingLR(optim, args.epochs)
        best, best_state = float("inf"), None
        for epoch in range(args.epochs):
            model.train()
            for pts, meta, y, tgt in batches(train, rng.permutation(len(train["is_error"]))):
                pts, tgt = augment(pts, tgt)
                logit, delta = model(pts, meta)
                loss = losses(logit, delta, y, tgt)
                optim.zero_grad()
                loss.backward()
                optim.step()
            sched.step()
            model.eval()
            logit, delta = predict(model)
            val_loss = float(losses(logit, delta, val["is_error"], val["target"]))
            if not args.quiet:
                p = torch.sigmoid(logit).numpy()
                wrong = y_val == 1
                shift_err = float((delta[wrong][:, :2] - val["target"][wrong][:, :2]).norm(dim=1).median())
                print(f"[seed {seed}] epoch {epoch + 1}: loss kiểm tra {val_loss:.3f}, accuracy "
                      f"{((p > 0.5) == y_val).mean():.3f}, box chuẩn bị báo (p>0.7) {(p[clean_val] > 0.7).mean():.1%}, "
                      f"mẫu sai bắt được (p>0.7) {(p[wrong] > 0.7).mean():.1%}, sai số gợi ý dời {shift_err:.3f} m")
            if val_loss < best:
                best, best_state = val_loss, {k: v.detach().cpu().clone() for k, v in model.state_dict().items()}
        model.load_state_dict(best_state)
        print(f"[seed {seed}] loss kiểm tra tốt nhất {best:.3f}")
        return model.eval().cpu()  # giải phóng GPU trước khi huấn luyện model kế tiếp của ensemble

    members = [train_one(args.seed + i) for i in range(args.ensemble)]
    model = (members[0] if len(members) == 1 else Ensemble(members).eval()).to(device)
    logit, _ = predict(model)
    best_logit = logit.numpy()
    best_p = torch.sigmoid(logit).numpy()
    threshold = float(np.quantile(best_p[clean_val], 1 - args.target_fa))
    print(f"Ngưỡng gợi ý critic.min_probability = {threshold:.2f} (box chuẩn cảnh kiểm tra bị báo {args.target_fa:.0%}; "
          f"mẫu sai bắt được {(best_p[y_val == 1] > threshold).mean():.1%})")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    model.cpu().eval()
    torch.jit.script(model).save(str(args.out))
    rise = track_rise(best_logit, val_raw)
    if rise is not None:
        rises, clean, wrong = rise
        warn, err = np.quantile(rises[clean], 0.995), np.quantile(rises[clean], 0.997)
        print(f"Ngưỡng gợi ý so theo track (box thuộc track): critic.min_logit_rise = {warn:.1f} (box chuẩn bị báo 0,5%, "
              f"mẫu sai bắt được {(rises[wrong] > warn).mean():.1%}), critic.error_logit_rise = {err:.1f} (0,3%)")
    print(f"-> {args.out}")


def track_rise(logit: np.ndarray, data: dict[str, np.ndarray]):
    """Logit của mỗi mẫu trừ trung vị logit các box chuẩn ở frame khác của cùng track (như luật `critic.box`)."""
    clean = np.all(data["target"] == 0, axis=1)
    per_box: dict[tuple[int, int], list[float]] = {}
    for i in np.flatnonzero(clean):
        per_box.setdefault((int(data["track_id"][i]), int(data["frame"][i])), []).append(float(logit[i]))
    by_track: dict[int, dict[int, float]] = {}
    for (t, f), v in per_box.items():
        by_track.setdefault(t, {})[f] = float(np.mean(v))
    rises, keep = [], []
    for i in range(len(logit)):
        others = [v for f, v in by_track.get(int(data["track_id"][i]), {}).items() if f != int(data["frame"][i])]
        if len(others) >= 2:
            rises.append(logit[i] - np.median(others))
            keep.append(i)
    if not keep:
        return None
    keep = np.array(keep)
    return np.array(rises), clean[keep], data["is_error"][keep] == 1


if __name__ == "__main__":
    main()
