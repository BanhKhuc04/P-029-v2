"""Run the repository suites, source checks, package smoke and optional integrations.

Each phase keeps its own log. FAIL, SKIP and XFAIL remain distinct; one failing
phase does not prevent the remaining checks from running.
"""
from __future__ import annotations

import argparse
import ast
from collections import Counter
from datetime import datetime, timedelta, timezone
import importlib.metadata
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import time
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
REPO = next((p for p in (ROOT, *ROOT.parents) if (p / '.git').exists()), ROOT)


def junit_counts(path):
    counts = Counter()
    if not path.is_file():
        return counts
    for case in ET.parse(path).iter("testcase"):
        skipped = case.find("skipped")
        if case.find("failure") is not None or case.find("error") is not None:
            status = "FAIL"
        elif skipped is not None:
            status = "XFAIL" if skipped.get("type") == "pytest.xfail" else "SKIP"
        else:
            status = "PASS"
        counts[status] += 1
    return counts


def command(name, argv, cwd, env, out, timeout=900):
    started = time.monotonic()
    log = out / (name + ".log")
    try:
        with log.open("w", encoding="utf-8") as stream:
            result = subprocess.run(argv, cwd=cwd, env=env, stdout=stream,
                                    stderr=subprocess.STDOUT, timeout=timeout)
        row = dict(name=name, status="PASS" if result.returncode == 0 else "FAIL",
                   exit_code=result.returncode)
    except (OSError, subprocess.TimeoutExpired) as exc:
        row = dict(name=name, status="FAIL", error=type(exc).__name__)
    row.update(seconds=round(time.monotonic() - started, 2), log=log.name)
    print(f"{row['status']}: {name} ({row['seconds']}s)", flush=True)
    return row


def report(out, metadata, rows):
    counts = Counter(row["status"] for row in rows)
    data = dict(metadata=metadata, phase_counts=dict(counts), phases=rows)
    (out / "results.json").write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = ["# PointSnap full test run", "", f"Model review: {metadata['review_model']}",
             f"Source: {metadata['source_commit']} / {metadata['branch']}",
             f"Time: {metadata['started_at']} (Asia/Bangkok)", "",
             "| Phase | Status | Individual cases | Seconds | Log |",
             "|---|---|---|---|---|"]
    for row in rows:
        cases = ", ".join(f"{k}={v}" for k, v in row.get("cases", {}).items())
        detail = row.get("detail", "").replace("|", "/")
        lines.append(f"| {row['name']} | {row['status']} {detail} | {cases} | "
                     f"{row.get('seconds', '')} | {row.get('log', '')} |")
    lines += ["", "SKIP and XFAIL are not passed checks. A successful evaluation command",
              "does not mean quality targets passed; inspect evaluation/summary.json.",
              "Browser rendering, installed MV3 extension behavior and human precision",
              "are not certified by these automated tests."]
    (out / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return 1 if counts["FAIL"] else 0


def tracked_sources():
    output = subprocess.check_output(["git", "ls-files", "-z", "--", "*.py", "*.js"], cwd=ROOT)
    paths = [ROOT / p for p in output.decode("utf-8").split("\0") if p]
    # Include new test tools before they are committed, but do not import local data.
    paths += list((ROOT / "auto-tests").glob("*.py"))
    return sorted(set(paths))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, help="Explicit nuScenes directory; otherwise read NUSCENES_ROOT")
    parser.add_argument("--live-cvat", action="store_true", help="Create and delete only owned temporary CVAT tasks")
    parser.add_argument("--cvat-url", default="http://localhost:8080")
    parser.add_argument("--evaluate", action="store_true", help="Run all 10 mini scenes with synthetic error injection")
    parser.add_argument("--rounds", type=int, default=10)
    parser.add_argument("--docker", action="store_true", help="Build a separately tagged image and smoke its CLI")
    parser.add_argument("--model-smoke", action="store_true", help="Fresh inference with the cached Mask R-CNN checkpoint")
    parser.add_argument("--review-model", default="unspecified (pass --review-model to record the reviewer model)")
    args = parser.parse_args(argv)
    if not (REPO / '.git').exists():
        parser.error('Run the complete workflow from a Git checkout; helper tests also support an archived /source tree')
    if args.rounds < 1:
        parser.error("--rounds must be positive")
    from pointsnap.cli.main import load_dotenv
    load_dotenv(ROOT / ".env")
    dataset = args.dataset or (Path(os.environ["NUSCENES_ROOT"]) if os.environ.get("NUSCENES_ROOT") else None)
    live_env = dict(os.environ, CVAT_URL=args.cvat_url, PYTHONIOENCODING="utf-8", PYTHONUTF8="1", PYTHONUNBUFFERED="1")
    env = {k: v for k, v in live_env.items() if not k.startswith(("CVAT_", "NUSCENES_", "POINTSNAP_", "PYTHONPATH"))}
    env["PYTHONPATH"] = str(ROOT)
    env["POINTSNAP_LIVE_CVAT"] = "0"
    out = ROOT / "out" / "all-tests" / datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    out.mkdir(parents=True)
    env["POINTSNAP_HOME"] = str(out / "home")
    git = lambda *a: subprocess.check_output(["git", *a], cwd=REPO).decode("utf-8").strip()
    versions = {}
    for package in ("pytest", "numpy", "fastapi", "httpx", "torch", "torchvision", "transformers", "build"):
        try:
            versions[package] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            versions[package] = None
    metadata = dict(started_at=datetime.now(timezone(timedelta(hours=7))).isoformat(),
                    review_model=args.review_model, source_commit=git("rev-parse", "HEAD"),
                    branch=git("branch", "--show-current"), python=sys.version,
                    dependencies=versions, dataset=str(dataset.resolve()) if dataset else None,
                    source_changes=git("status", "--porcelain", "--", "source-tool/pointsnap-3d/pointsnap"))
    import hashlib
    metadata["runner_sha256"] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    metadata["options"] = dict(live_cvat=args.live_cvat, docker=args.docker, evaluate=args.evaluate,
                              rounds=args.rounds, model_smoke=args.model_smoke)
    rows = []
    print(f"Results: {out}", flush=True)

    def run(name, argv, cwd=ROOT, phase_env=None, timeout=900):
        row = command(name, argv, cwd, phase_env or env, out, timeout)
        rows.append(row)
        report(out, metadata, rows)
        return row

    def skip(name, detail):
        rows.append(dict(name=name, status="SKIP", detail=detail))
        report(out, metadata, rows)

    def pytest_phase(name, targets, phase_env):
        xml = out / (name + ".xml")
        row = run(name, [sys.executable, "-m", "pytest", "-q", "-ra", "-p", "no:cacheprovider",
                         *targets, f"--junitxml={xml}", f"--basetemp={out / (name + '-tmp')}"], phase_env=phase_env)
        row["cases"] = dict(junit_counts(xml))
        if not row["cases"]:
            row.update(status="FAIL", detail="No individual cases reported")
        report(out, metadata, rows)

    pytest_phase("python", ["tests", "auto-tests", "--ignore=tests/test_live_cvat.py",
                             "--ignore=tests/test_real_nuscenes.py"], env)
    if dataset:
        pytest_phase("dataset", ["tests/test_real_nuscenes.py", "tests/test_ground.py::test_estimate_ground_real_nuscenes"],
                     dict(env, NUSCENES_ROOT=str(dataset.resolve())))
    else:
        skip("dataset", "NUSCENES_ROOT/--dataset missing")
    if args.live_cvat:
        pytest_phase("live-cvat", ["tests/test_live_cvat.py"],
                     dict(live_env, PYTHONPATH=str(ROOT), POINTSNAP_LIVE_CVAT="1"))
        run("service-smoke", [sys.executable, str(ROOT / "auto-tests/smoke_services.py"),
                              "--cvat-url", args.cvat_url, "--out", str(out / "services")], phase_env=live_env)
    else:
        skip("live-cvat", "Use --live-cvat; creates/deletes owned test tasks")

    node = shutil.which("node")
    if node:
        row = run("extension", [node, "--test", "--test-reporter=junit",
                                *map(str, sorted((ROOT / "extension/tests").glob("*.test.js")))])
        row["cases"] = dict(junit_counts(out / "extension.log"))
        if not row["cases"]:
            row.update(status="FAIL", detail="No Node test cases reported")
    else:
        skip("extension", "Node executable missing")
    sources = tracked_sources()
    failures = []
    for path in sources:
        if path.suffix == ".py":
            try:
                ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))
            except (SyntaxError, UnicodeError) as exc:
                failures.append(f"{path.relative_to(ROOT)}: {type(exc).__name__}")
    rows.append(dict(name="python-syntax", status="FAIL" if failures else "PASS",
                     files=sum(p.suffix == ".py" for p in sources), detail="; ".join(failures)))
    if node:
        for index, path in enumerate(p for p in sources if p.suffix == ".js"):
            row = command(f"js-syntax-{index}", [node, "--check", str(path)], ROOT, env, out, 60)
            if row["status"] == "FAIL":
                rows.append(row)
        syntax_logs = list(out.glob("js-syntax-*.log"))
        rows.append(dict(name="js-syntax", status="FAIL" if any(r["name"].startswith("js-syntax-") for r in rows) else "PASS",
                         files=len(syntax_logs)))
        run("extension-manifest", [node, "-e", "JSON.parse(require('fs').readFileSync('extension/manifest.json','utf8'))"])
    else:
        skip("js-syntax", "Node executable missing")
    pwsh = shutil.which("pwsh") or shutil.which("powershell")
    if pwsh:
        run("powershell-syntax", [pwsh, "-NoProfile", "-NonInteractive", "-File",
                                   str(ROOT / "auto-tests/Check-PowerShell.ps1")])
    else:
        skip("powershell-syntax", "PowerShell executable missing")
    run("pip-check", [sys.executable, "-m", "pip", "check"])

    # Build a clean checkout of HEAD so local secrets/data never enter the package.
    archive = out / "source.tar"
    archived = run("source-archive", ["git", "archive", "--format=tar", f"--output={archive}",
                                      "HEAD", "source-tool/pointsnap-3d"], cwd=REPO)
    if archived["status"] == "PASS":
        source_dir = out / "source"
        with tarfile.open(archive) as tar:
            tar.extractall(source_dir, filter="data")
        source = source_dir / "source-tool/pointsnap-3d"
        build = run("package-build", [sys.executable, "-m", "build", "--no-isolation", "--outdir", str(out / "dist")], cwd=source)
        if build["status"] == "PASS":
            venv = out / "installed"
            made = run("package-venv", [sys.executable, "-m", "venv", str(venv)], cwd=out)
            installed_python = venv / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
            wheel = next((out / "dist").glob("*.whl"))
            installed_env = {k: v for k, v in env.items() if k != "PYTHONPATH"}
            if made["status"] == "PASS":
                install = run("package-install", [str(installed_python), "-m", "pip", "install", "--disable-pip-version-check", str(wheel)],
                              cwd=out, phase_env=installed_env)
                if install["status"] == "PASS":
                    run("installed-pip-check", [str(installed_python), "-m", "pip", "check"], cwd=out, phase_env=installed_env)
                    run("installed-http-smoke", [str(installed_python), str(source / "scripts/smoke_package.py")],
                        cwd=out, phase_env=installed_env)
        if args.docker:
            docker = shutil.which("docker")
            if docker:
                image = "pointsnap-review:" + out.name.lower()
                built = run("docker-build", [docker, "build", "--build-arg", "PYTHON_VERSION=3.11", "-t", image, "."], cwd=source, timeout=1200)
                if built["status"] == "PASS":
                    run("docker-cli", [docker, "run", "--rm", image, "--help"])
                    run("docker-pip-check", [docker, "run", "--rm", "--entrypoint", "python", image, "-m", "pip", "check"])
                    linux = out / "linux"
                    linux.mkdir()
                    row = run("docker-pytest", [docker, "run", "--rm", "--entrypoint", "python",
                                                "-v", f"{source}:/source:ro", "-v", f"{linux}:/results",
                                                "-v", f"{ROOT / 'auto-tests/docker_pytest.py'}:/runner.py:ro",
                                                "-w", "/source", image, "/runner.py"])
                    row["cases"] = dict(junit_counts(linux / "linux.xml"))
                    if not row["cases"]:
                        row.update(status="FAIL", detail="No Linux cases reported")
            else:
                skip("docker-build", "Docker executable missing")
        else:
            skip("docker-build", "Use --docker")
    if args.model_smoke and dataset:
        for model in ("maskrcnn", "gdino-sam2", "hybrid"):
            row = run("model-" + model, [sys.executable, str(ROOT / "auto-tests/smoke_model.py"),
                                       "--dataset", str(dataset.resolve()), "--model", model,
                                       "--out", str(out / ("model-" + model))])
            if row.get("exit_code") == 77:
                row.update(status="SKIP", detail="Required cached checkpoint missing; no download attempted")
    else:
        skip("model-smoke", "Use --model-smoke and configure dataset")
    if args.evaluate:
        if dataset:
            # Reuse the existing camera inference cache; fresh model inference is a
            # separate smoke check. No CVAT credentials are passed into evaluation.
            eval_env = {k: v for k, v in env.items() if not k.startswith("POINTSNAP_")}
            run("evaluation", [sys.executable, "-m", "pointsnap", "eval", "--dataroot", str(dataset.resolve()),
                               "--scenes", "all", "--rounds", str(args.rounds), "--seed", "0", "--out", str(out / "evaluation")],
                cwd=out, phase_env=eval_env, timeout=7200)
            run("heldout-quality", [sys.executable, str(ROOT / "auto-tests/check_quality.py"),
                                    "--dataset", str(dataset.resolve()), "--out", str(out / "heldout-quality.json")],
                cwd=out, phase_env=eval_env)
        else:
            skip("evaluation", "Dataset missing")
    else:
        skip("evaluation", "Use --evaluate; command success is separate from quality targets")
    status = report(out, metadata, rows)
    print(f"Report: {out / 'report.md'}", flush=True)
    return status


if __name__ == "__main__":
    raise SystemExit(main())
