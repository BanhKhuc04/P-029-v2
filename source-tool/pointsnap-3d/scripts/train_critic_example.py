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
    python scripts/train_critic_example.py --data data/critic --epochs 30 --out models/critic.pt
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


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--epochs", type=int, default=30)
    parser.add_argument("--batch", type=int, default=512)
    parser.add_argument("--lr", type=float, default=1e-3)
    parser.add_argument("--weight-decay", type=float, default=1e-3)
    parser.add_argument("--val-scenes", nargs="*", default=None,
                        help="tên file .npz (không đuôi) để kiểm tra; mặc định file cuối theo thứ tự tên")
    parser.add_argument("--use-dims", action="store_true", help="cho model thấy kích thước tuyệt đối (dễ học thuộc)")
    parser.add_argument("--target-fa", type=float, default=0.01, help="tỉ lệ box chuẩn bị báo để tính ngưỡng gợi ý")
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
    model = BoxCritic(train["meta"].shape[1], use_dims=args.use_dims).to(device)
    optim = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=args.weight_decay)
    sched = torch.optim.lr_scheduler.CosineAnnealingLR(optim, args.epochs)
    bce, smooth = nn.BCEWithLogitsLoss(), nn.SmoothL1Loss(reduction="none")
    rng = np.random.default_rng(0)

    def batches(data, idx):
        for i in range(0, len(idx), args.batch):
            b = idx[i:i + args.batch]
            yield (data["points"][b].to(device), data["meta"][b].to(device), data["is_error"][b].to(device),
                   data["target"][b].to(device))

    def losses(logit, delta, y, tgt):
        reg = (smooth(delta, tgt).mean(dim=1) * y).sum() / y.sum().clamp(min=1)
        return bce(logit, y) + reg

    best, best_state, best_p = float("inf"), None, None
    clean_val = (val["target"] == 0).all(dim=1).numpy()
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
        total, probs, logits, err = 0.0, [], [], []
        with torch.inference_mode():
            for pts, meta, y, tgt in batches(val, np.arange(len(val["is_error"]))):
                logit, delta = model(pts, meta)
                total += float(losses(logit, delta, y, tgt)) * len(y)
                probs.append(torch.sigmoid(logit).cpu())
                logits.append(logit.cpu())
                mask = y > 0
                if mask.any():
                    err.append((delta[mask][:, :2] - tgt[mask][:, :2]).norm(dim=1).cpu())
        val_loss = total / len(val["is_error"])
        p = torch.cat(probs).numpy()
        y = val["is_error"].numpy()
        shift_err = float(torch.cat(err).median()) if err else float("nan")
        print(f"epoch {epoch + 1}: loss kiểm tra {val_loss:.3f}, accuracy {((p > 0.5) == y).mean():.3f}, "
              f"box chuẩn bị báo (p>0.7) {(p[clean_val] > 0.7).mean():.1%}, mẫu sai bắt được (p>0.7) "
              f"{(p[y == 1] > 0.7).mean():.1%}, sai số gợi ý dời {shift_err:.3f} m")
        if val_loss < best:
            best, best_p, best_logit = val_loss, p, torch.cat(logits).numpy()
            best_state = {k: v.detach().cpu().clone() for k, v in model.state_dict().items()}

    model.load_state_dict(best_state)
    y = val["is_error"].numpy()
    threshold = float(np.quantile(best_p[clean_val], 1 - args.target_fa))
    print(f"model tốt nhất: loss kiểm tra {best:.3f}. Ngưỡng gợi ý critic.min_probability = {threshold:.2f} "
          f"(box chuẩn cảnh kiểm tra bị báo {args.target_fa:.0%}; mẫu sai bắt được {(best_p[y == 1] > threshold).mean():.1%})")
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
