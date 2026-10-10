"""Huấn luyện mẫu Box Critic (lớp 3 của Box Verifier) — điểm xuất phát để nhóm tự cải tiến.

Mạng PointNet nhỏ: mỗi điểm (x, y, z hệ box chuẩn hóa, cờ trong box) qua MLP dùng chung, gộp max, nối với đặc trưng box
(kích thước, khoảng cách, số điểm, class), ra 2 đầu: logit "box sai" và 7 giá trị sửa (dx, dy, dz, dl, dw, dh, dyaw).
Loss = BCE(box sai) + SmoothL1(sửa) chỉ tính trên mẫu sai. Xuất TorchScript để PointSnap nạp qua `critic.model`.

Chạy (cần PyTorch):
    pointsnap critic-data --scenes tuning --out data/critic
    python scripts/train_critic_example.py --data data/critic --epochs 20 --out models/critic.pt
Rồi khai trong guideline:  critic: {model: models/critic.pt}  và đánh giá bằng  pointsnap eval --scenes test
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import torch
from torch import nn


class BoxCritic(nn.Module):
    def __init__(self, meta_dim: int, width: int = 128):
        super().__init__()
        self.point_mlp = nn.Sequential(
            nn.Linear(4, 64), nn.ReLU(), nn.Linear(64, 128), nn.ReLU(), nn.Linear(128, width), nn.ReLU())
        self.head = nn.Sequential(nn.Linear(width + meta_dim, 128), nn.ReLU(), nn.Linear(128, 64), nn.ReLU())
        self.cls = nn.Linear(64, 1)
        self.reg = nn.Linear(64, 7)

    def forward(self, points: torch.Tensor, meta: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        feat = self.point_mlp(points).max(dim=1).values
        hidden = self.head(torch.cat([feat, meta], dim=1))
        return self.cls(hidden).squeeze(1), self.reg(hidden)


def load(folder: Path) -> dict[str, np.ndarray]:
    parts = [np.load(p) for p in sorted(folder.glob("*.npz"))]
    return {k: np.concatenate([p[k] for p in parts]) for k in ("points", "meta", "is_error", "target")}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--epochs", type=int, default=20)
    parser.add_argument("--batch", type=int, default=256)
    parser.add_argument("--lr", type=float, default=1e-3)
    parser.add_argument("--val-fraction", type=float, default=0.15)
    parser.add_argument("--out", type=Path, default=Path("models/critic.pt"))
    args = parser.parse_args()

    data = load(args.data)
    n = len(data["is_error"])
    rng = np.random.default_rng(0)
    order = rng.permutation(n)
    split = int(n * (1 - args.val_fraction))
    device = "cuda" if torch.cuda.is_available() else "cpu"
    tensors = {k: torch.from_numpy(v.astype(np.float32)) for k, v in data.items()}
    model = BoxCritic(tensors["meta"].shape[1]).to(device)
    optim = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=1e-4)
    bce, smooth = nn.BCEWithLogitsLoss(), nn.SmoothL1Loss(reduction="none")

    def batches(idx):
        for i in range(0, len(idx), args.batch):
            b = idx[i:i + args.batch]
            yield (tensors["points"][b].to(device), tensors["meta"][b].to(device),
                   tensors["is_error"][b].to(device), tensors["target"][b].to(device))

    for epoch in range(args.epochs):
        model.train()
        for pts, meta, y, tgt in batches(rng.permutation(order[:split])):
            logit, delta = model(pts, meta)
            reg = (smooth(delta, tgt).mean(dim=1) * y).sum() / y.sum().clamp(min=1)
            loss = bce(logit, y) + reg
            optim.zero_grad()
            loss.backward()
            optim.step()
        model.eval()
        correct = total = 0
        err = []
        with torch.inference_mode():
            for pts, meta, y, tgt in batches(order[split:]):
                logit, delta = model(pts, meta)
                correct += int(((logit > 0).float() == y).sum())
                total += len(y)
                mask = y > 0
                if mask.any():
                    err.append((delta[mask][:, :2] - tgt[mask][:, :2]).norm(dim=1).cpu())
        shift_err = float(torch.cat(err).median()) if err else float("nan")
        print(f"epoch {epoch + 1}: accuracy {correct / max(total, 1):.3f}, sai số gợi ý dời (trung vị) {shift_err:.3f} m")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    model.cpu().eval()
    scripted = torch.jit.script(model)
    scripted.save(str(args.out))
    print(f"-> {args.out}")


if __name__ == "__main__":
    main()
