"""Read selected public package files in the existing container; never reads credentials."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[3]
NAMES = ["api.py", "config.yaml", "core/scanner.py", "detectors/missing.py"]


def digest(data):
    return hashlib.sha256(data.replace(b"\r\n", b"\n")).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--container", default="pointsnap-handoff-pointsnap_api-1")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    script = """
import hashlib,json
from pathlib import Path
import pointsnap
from pointsnap.core.config import load_config
root=Path(pointsnap.__file__).parent
c=load_config(env={})
names=['api.py','config.yaml','core/scanner.py','detectors/missing.py']
print(json.dumps({
  'sha256_lf':{n:hashlib.sha256((root/n).read_bytes().replace(bytes([13,10]),bytes([10]))).hexdigest() for n in names},
  'default_fit':{'fit_loose':c.rules.fit_loose,'outside_min_points':c.fit.outside_min_points,
    'outside_min_object_points':getattr(c.fit,'outside_min_object_points',None),'outside_warning_ratio':c.fit.outside_warning_ratio}}))
"""
    deployed = json.loads(subprocess.check_output(["docker", "exec", args.container, "python", "-c", script], text=True))
    main_hashes = {n: digest(subprocess.check_output(["git", "show", "origin/main:source-tool/pointsnap-3d/pointsnap/" + n], cwd=ROOT)) for n in NAMES}
    candidate = {n: digest((ROOT / "source-tool/pointsnap-3d/pointsnap" / n).read_bytes()) for n in NAMES}
    image = json.loads(subprocess.check_output(["docker", "inspect", args.container, "--format", "{{json .Config.Image}}"], text=True))
    result = {
        "container": args.container,
        "image": image,
        "observed_main": subprocess.check_output(["git", "rev-parse", "origin/main"], cwd=ROOT, text=True).strip(),
        "candidate_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "deployed": deployed,
        "candidate_sha256_lf": candidate,
        "main_sha256_lf": main_hashes,
        "container_equals_candidate": deployed["sha256_lf"] == candidate,
        "container_equals_main": deployed["sha256_lf"] == main_hashes,
        "scope": "Read-only sample of four package files, normalized LF, and package default fit settings; not a full image/source attestation or effective per-project settings. Container unchanged; no credentials accessed.",
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_bytes((json.dumps(result, indent=2) + "\n").encode("utf-8"))
    print(json.dumps(result))


if __name__ == "__main__":
    main()
