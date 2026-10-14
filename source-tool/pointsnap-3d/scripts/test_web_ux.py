"""Run focused Web UX regressions from any working directory.

Usage: python scripts/test_web_ux.py
Requires the project's dev dependencies and Node.js. Browser checks remain manual;
see review/2026-10-14/architecture-ux-review.md for their steps and evidence.
"""

from pathlib import Path
import shutil
import subprocess
import sys


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    node = shutil.which("node")
    if node is None:
        print("Node.js is required for the Web JavaScript syntax check.", file=sys.stderr)
        return 1
    commands = [
        [sys.executable, "-m", "pytest", "tests/test_web_job_metadata.py",
         "tests/test_web.py", "tests/test_web_a14.py", "-q"],
        [node, "--check", "pointsnap/web/static/app.js"],
    ]
    for command in commands:
        result = subprocess.run(command, cwd=root, check=False)
        if result.returncode:
            return result.returncode
    print("Web UX backend regressions and JavaScript syntax check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
