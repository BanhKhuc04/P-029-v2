"""Compatibility entry point: evaluator/split/config như pointsnap eval.

Dùng --scenes tuning|test, --rounds, --seed, --dataroot và --out; không ghi đè docs lịch sử.
Global --config đặt trước subcommand eval ở CLI chính.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pointsnap.cli.main import main

if __name__ == '__main__':
    raise SystemExit(main(['eval', *sys.argv[1:]]))