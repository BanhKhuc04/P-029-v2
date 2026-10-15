"""Read-only audit of current CVAT findings and candidate scanner clearance."""

import argparse
import json
from pathlib import Path

from fastapi.testclient import TestClient

from pointsnap.adapters.cvat.client import CvatClient
from pointsnap.adapters.cvat.reader import load_job, find_manifest, ManifestFrames
from pointsnap.cli.common import export_dirs
from pointsnap.core.repair import verify_repaired_box_passes_scanner
from pointsnap.web.app import create_app


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--slug", required=True)
    parser.add_argument("--job", type=int, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    app = create_app()
    project = app.state.pm.get_project(args.slug)
    cfg = app.state.pm.get_effective_config(args.slug)
    cvat = CvatClient(cfg.cvat.url, cfg.cvat.token)
    app.state.cvat_client = cvat
    job = load_job(cvat, args.job)
    manifest = find_manifest(args.job, export_dirs(project.get("export_dirs")))
    source = ManifestFrames(manifest, dataroot=project.get("nuscenes_root")) if manifest else None
    if source:
        source.check_matches(job.frame_names)
    runs = [r for r in app.state.runner.list_runs(args.slug) if r.get("job_id") == args.job and r.get("status") == "done"]
    run = app.state.runner.get_run(args.slug, runs[0]["run_id"], include_findings=True)
    web = TestClient(app)
    selected = []
    supported = {"floating", "heading.flip", "heading.motion", "heading.points", "heading.static", "fit.outside", "fit.loose"}
    for i, f in enumerate(run["findings"]):
        if f["rule"] in supported and sum(x[1]["rule"] == f["rule"] for x in selected) < 2:
            selected.append((i, f))
    result = {"job_id": args.job, "run_id": run["run_id"], "read_only": True, "cases": []}
    for index, f in selected:
        response = web.get(f"/api/projects/{args.slug}/scans/{run['run_id']}/findings/{index}/repair")
        record = {"index": index, "rule": f["rule"], "track_id": f["track_id"], "frame": f["frame"], "http_status": response.status_code}
        if response.status_code == 200:
            data = response.json()
            rep = data["repair"]
            record.update({k: rep[k] for k in ("delta_center", "delta_dims", "delta_yaw", "applicable", "confidence", "reason")})
            record["heading_prediction"] = data.get("heading_prediction")
            target = next((b for b in job.cuboids if b.track_id == f["track_id"] and b.frame == f["frame"]), None)
            if target and rep["applicable"] and source:
                r = rep["repaired_cuboid"]
                candidate = target.replace(center=tuple(r["center"]), dims=tuple(r["dims"]), yaw=r["yaw"])
                track = [b for b in job.cuboids if b.track_id == target.track_id]
                record["target_rule_cleared"] = verify_repaired_box_passes_scanner(candidate, track, source, f["rule"], cfg)
        result["cases"].append(record)
        print(json.dumps(record, ensure_ascii=False))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    cvat.session.close()


if __name__ == "__main__":
    main()
