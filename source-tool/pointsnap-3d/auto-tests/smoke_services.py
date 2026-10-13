"""Exercise the current Report API against an owned temporary real CVAT task.

Checks all output formats and compares complete annotations before/after GETs.
No existing task is edited, and the temporary task is deleted in finally.
"""
import argparse
import json
import os
from pathlib import Path
import sys
import threading

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--cvat-url", default="http://localhost:8080")
    args = parser.parse_args()
    import requests
    import fake_nuscenes
    from pointsnap.adapters.cvat.client import CvatClient
    from pointsnap.adapters.cvat.reader import load_job
    from pointsnap.adapters.nuscenes import NuScenesReader
    from pointsnap.api import ReportServer
    from pointsnap.cli.main import load_dotenv
    from pointsnap.core.config import load_config
    from pointsnap.datasets.nuscenes.to_cvat import export_scene, upload_scene

    args.out = args.out.resolve()
    args.out.mkdir(parents=True, exist_ok=True)
    load_dotenv(ROOT / ".env")
    cfg = load_config(env=dict(os.environ, CVAT_URL=args.cvat_url))
    if not cfg.cvat.token:
        print("SKIP: CVAT_TOKEN missing")
        return 77
    client = CvatClient(args.cvat_url, cfg.cvat.token, auth_scheme=os.environ.get("CVAT_AUTH_SCHEME", "Bearer"))
    session = requests.Session()
    session.trust_env = False
    server = thread = info = None
    rows = []
    result = dict(status="FAIL", checks=rows, existing_jobs_edited=False, cleanup="NOT_RUN")
    try:
        reader = NuScenesReader(fake_nuscenes.build(args.out / "fake-data"))
        export = export_scene(reader, "scene-0001", args.out / "export")
        info = upload_scene(client, export, "PointSnap review API smoke (owned temporary task)", "pointsnap_error")
        result.update(owned_task_id=info["task_id"], owned_job_ids=info["job_ids"])
        [job_id] = info["job_ids"]
        before = load_job(client, job_id)
        os.environ["CVAT_URL"] = args.cvat_url
        os.environ["POINTSNAP_EXPORT_DIR"] = str(export.manifest.parent)
        # The generated fixture must not use the user's real dataset as a path override.
        os.environ["NUSCENES_ROOT"] = str(args.out / "fake-data")
        server = ReportServer(("127.0.0.1", 0), args.cvat_url)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base = f"http://127.0.0.1:{server.server_address[1]}"

        def get(name, path, expected=200, headers=None):
            response = session.get(base + path, headers=headers, timeout=60)
            assert response.status_code == expected, f"{name}: HTTP {response.status_code}"
            rows.append(dict(name=name, status="PASS", http_status=response.status_code))
            return response

        assert get("health", "/pointsnap/health").json()["status"] == "ok"
        path = f"/pointsnap/jobs/{job_id}/report"
        get("anonymous rejected", path, 401)
        get("invalid token rejected", path, 401, {"Authorization": "Bearer invalid-review-token"})
        headers = {"Authorization": "Bearer " + cfg.cvat.token}
        for fmt, mime in (("json", "application/json"), ("html", "text/html"), ("csv", "text/csv")):
            response = get("authenticated " + fmt, path + "?format=" + fmt, headers=headers)
            assert mime in response.headers.get("Content-Type", "") and response.content
            if fmt == "json":
                data = response.json()
                assert data["job_id"] == job_id and data["point_cloud_available"]
            rows[-1].update(bytes=len(response.content), content_type=mime)
        after = load_job(client, job_id)
        assert before.raw_annotations == after.raw_annotations
        rows.append(dict(name="complete annotations unchanged after GET reports", status="PASS"))
        result["status"] = "PASS"
    except Exception as exc:
        result.update(status="FAIL", error=type(exc).__name__)
    finally:
        if server:
            server.shutdown()
            server.server_close()
            thread.join(timeout=10)
        if info:
            try:
                client.delete_task(info["task_id"])
                deleted = client.session.get(args.cvat_url.rstrip("/") + f"/api/tasks/{info['task_id']}", timeout=10)
                result["cleanup_http_status"] = deleted.status_code
                result["cleanup"] = "PASS" if deleted.status_code == 404 else "FAIL"
                if deleted.status_code != 404:
                    result["status"] = "FAIL"
            except Exception as exc:
                result.update(status="FAIL", cleanup="FAIL", cleanup_error=type(exc).__name__)
        client.session.close()
        session.close()
        (args.out / "services.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
