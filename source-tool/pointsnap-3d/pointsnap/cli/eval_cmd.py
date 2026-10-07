"""Lệnh `pointsnap eval`: đánh giá ba bộ phát hiện bằng lỗi chèn giả trên nuScenes (việc B6)."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from pointsnap.adapters.nuscenes import NuScenesReader
from pointsnap.core.config import Config
from pointsnap.eval.evaluate import run_evaluation
from pointsnap.eval.split import TEST_SCENES, TUNING_SCENES

SCENE_SETS = {"test": TEST_SCENES, "tuning": TUNING_SCENES, "all": TUNING_SCENES + TEST_SCENES}


def add_parser(sub: argparse._SubParsersAction) -> None:
    ev = sub.add_parser("eval", help="đánh giá precision / recall bằng lỗi chèn giả trên nuScenes")
    ev.add_argument(
        "--dataroot", type=Path, default=os.environ.get("NUSCENES_ROOT"),
        help="thư mục nuScenes (mặc định: biến môi trường NUSCENES_ROOT)",
    )
    ev.add_argument("--scenes", nargs="+", default=["test"],
                    help="test | tuning | all, hoặc danh sách tên cảnh (mặc định: test = 5 cảnh kiểm tra)")
    ev.add_argument("--rounds", type=int, default=10, help="số vòng chèn lỗi mỗi cảnh (mặc định: 10)")
    ev.add_argument("--seed", type=int, default=0, help="seed của bộ chèn lỗi (mặc định: 0)")
    ev.add_argument("--out", type=Path, default=Path("out/eval"), help="thư mục ghi kết quả (mặc định: out/eval)")


def run(args: argparse.Namespace, config: Config) -> int:
    if args.dataroot is None:
        print("Thiếu --dataroot (hoặc biến môi trường NUSCENES_ROOT).", file=sys.stderr)
        return 3
    scenes: list[str] = []
    for item in args.scenes:
        scenes.extend(SCENE_SETS.get(item, (item,)))
    label = " ".join(args.scenes)
    try:
        reader = NuScenesReader(args.dataroot)
        run_evaluation(reader, scenes, config, args.out, rounds=args.rounds, seed=args.seed,
                       title=f"Kết quả đánh giá PointSnap 3D ({label}, {args.rounds} vòng chèn lỗi)")
    except (FileNotFoundError, KeyError, ValueError) as exc:
        print(f"Lỗi: {exc}", file=sys.stderr)
        return 3
    print(f"-> Kết quả: {args.out / 'ket-qua.md'}")
    return 0
