"""Linux companion: run the clean archived Python suite in the review image.

Invoked inside an ephemeral container; source is mounted read-only at /source
and results at /results. Optional torch/dataset/live checks remain skipped.
"""
import json
from pathlib import Path
import subprocess
import sys


def main():
    result = subprocess.run([sys.executable, "-m", "pip", "install", "--user", "pytest", "httpx"])
    if result.returncode:
        return result.returncode
    result = subprocess.run([sys.executable, "-m", "pytest", "-q", "-ra", "-p", "no:cacheprovider",
                             "tests", "auto-tests", "--basetemp=/tmp/pytest",
                             "--junitxml=/results/linux.xml"], cwd="/source")
    (Path("/results") / "linux-exit.json").write_text(json.dumps(dict(exit_code=result.returncode, python=sys.version)))
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
