"""FastAPI server cho PointSnap 3D Web UI (A11)."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from pointsnap.adapters.cvat.client import CvatClient, CvatError
from pointsnap.core.config import ConfigError
from pointsnap.web.projects import ProjectError, ProjectManager
from pointsnap.web.runner import ScanRunner

STATIC_DIR = Path(__file__).parent / "static"

# run_id hợp lệ: YYYYMMDD-HHMMSS[-<ms>]-job<id>  (điểm nhỏ 3 — chặn path traversal)
_RUN_ID_RE = re.compile(r"^\d{8}-\d{6}(?:-\d+)?-job\d+$")


class CreateProjectRequest(BaseModel):
    name: str
    slug: str | None = None
    description: str = ""
    cvat_url: str = "http://localhost:8080"
    cvat_token: str | None = None
    nuscenes_root: str = ""
    export_dirs: list[str] = Field(default_factory=list)
    preset_slug: str | None = None


class UpdateProjectRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    cvat_url: str | None = None
    cvat_token: str | None = None
    nuscenes_root: str | None = None
    export_dirs: list[str] | None = None


class SaveGuidelineRequest(BaseModel):
    config: dict[str, Any] | None = None
    yaml: str | None = None


class StartScanRequest(BaseModel):
    job_id: int
    flag: bool = False


def create_app(home_dir: Path | str | None = None) -> FastAPI:
    pm = ProjectManager(home_dir=home_dir)
    runner = ScanRunner(project_manager=pm)

    application = FastAPI(
        title="PointSnap 3D",
        description="Giao diện Web kiểm tra và giám sát chất lượng nhãn 3D trên CVAT",
        version="0.1.0",
    )

    # Lưu trữ trong app.state để test có thể truy cập nếu cần
    application.state.pm = pm
    application.state.runner = runner

    # --- API Quản lý dự án ---

    @application.get("/api/projects")
    def list_projects() -> list[dict[str, Any]]:
        return pm.list_projects()

    @application.post("/api/projects", status_code=201)
    def create_project(req: CreateProjectRequest) -> dict[str, Any]:
        try:
            return pm.create_project(
                name=req.name,
                slug=req.slug,
                description=req.description,
                cvat_url=req.cvat_url,
                cvat_token=req.cvat_token,
                nuscenes_root=req.nuscenes_root,
                export_dirs=req.export_dirs,
                preset_slug=req.preset_slug,
            )
        except (ProjectError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @application.get("/api/projects/{slug}")
    def get_project(slug: str) -> dict[str, Any]:
        try:
            return pm.get_project(slug)
        except ProjectError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @application.put("/api/projects/{slug}")
    def update_project(slug: str, req: UpdateProjectRequest) -> dict[str, Any]:
        try:
            updates = {k: v for k, v in req.model_dump().items() if v is not None}
            return pm.update_project(slug, updates)
        except ProjectError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @application.delete("/api/projects/{slug}")
    def delete_project(slug: str) -> dict[str, Any]:
        try:
            pm.delete_project(slug)
            return {"ok": True, "message": f"Đã xóa dự án '{slug}'."}
        except ProjectError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    # --- API Guideline ---

    @application.get("/api/projects/{slug}/guideline")
    def get_guideline(slug: str) -> dict[str, Any]:
        try:
            clean_data, raw_yaml = pm.get_guideline(slug)
            return {"config": clean_data, "yaml": raw_yaml}
        except ProjectError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @application.put("/api/projects/{slug}/guideline")
    def save_guideline(slug: str, req: SaveGuidelineRequest) -> dict[str, Any]:
        try:
            content = req.yaml if req.yaml is not None else (req.config or {})
            clean_data = pm.save_guideline(slug, content)
            return {"ok": True, "config": clean_data}
        except ConfigError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except ProjectError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @application.post("/api/projects/{slug}/guideline/reset")
    def reset_guideline(slug: str) -> dict[str, Any]:
        try:
            clean_data = pm.reset_guideline(slug)
            return {"ok": True, "config": clean_data}
        except ProjectError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    # --- API Kết nối CVAT ---

    @application.get("/api/projects/{slug}/cvat/check")
    def check_cvat(slug: str) -> dict[str, Any]:
        # Điểm nhỏ 5: bắt ProjectError trước → trả 404 thay vì 500
        try:
            proj = pm.get_project(slug)
        except ProjectError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        try:
            cfg = pm.get_effective_config(slug)
            if not cfg.cvat.token:
                return {
                    "connected": False,
                    "error": "Dự án chưa có Token CVAT. Vui lòng cập nhật token ở tab Kết nối.",
                    "url": cfg.cvat.url,
                }
            client = CvatClient(cfg.cvat.url, cfg.cvat.token, timeout=10.0)
            ver = client.server_version()
            return {"connected": True, "version": ver, "url": cfg.cvat.url}
        except Exception as exc:
            return {"connected": False, "error": str(exc), "url": proj["cvat_url"]}

    @application.get("/api/projects/{slug}/cvat/tasks")
    def get_cvat_tasks(slug: str) -> dict[str, Any]:
        try:
            cfg = pm.get_effective_config(slug)
            if not cfg.cvat.token:
                raise HTTPException(status_code=400, detail="Chưa cấu hình Token CVAT")
            client = CvatClient(cfg.cvat.url, cfg.cvat.token, timeout=15.0)
            raw_tasks = client.get_tasks()
            tasks_result: list[dict[str, Any]] = []
            for t in raw_tasks:
                task_id = t.get("id")
                # Lấy danh sách job của task
                jobs = client.task_jobs(task_id) if task_id else []
                tasks_result.append({
                    "id": task_id,
                    "name": t.get("name", f"Task #{task_id}"),
                    "jobs": [
                        {
                            "id": j.get("id"),
                            "status": j.get("status"),
                            "stage": j.get("stage"),
                        }
                        for j in jobs
                    ],
                })
            return {"tasks": tasks_result}
        except CvatError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except ProjectError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    # --- API Quét & Báo cáo ---

    def _validate_run_id(run_id: str) -> None:
        """Điểm nhỏ 3: chặn path traversal qua run_id độc hại (vd: ../../etc/passwd)."""
        if not _RUN_ID_RE.match(run_id):
            raise HTTPException(
                status_code=400,
                detail=f"run_id không hợp lệ: '{run_id}'. Định dạng: YYYYMMDD-HHMMSS-job<id>.",
            )

    @application.post("/api/projects/{slug}/scans", status_code=202)
    def start_scan(slug: str, req: StartScanRequest) -> dict[str, Any]:
        try:
            run_id = runner.start_scan(slug, req.job_id, flag=req.flag)
            return {"run_id": run_id}
        except ProjectError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @application.get("/api/projects/{slug}/scans")
    def list_scans(slug: str) -> list[dict[str, Any]]:
        try:
            return runner.list_runs(slug)
        except ProjectError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @application.get("/api/projects/{slug}/scans/{run_id}")
    def get_scan(slug: str, run_id: str) -> dict[str, Any]:
        _validate_run_id(run_id)
        try:
            return runner.get_run(slug, run_id, include_findings=True)
        except ProjectError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @application.post("/api/projects/{slug}/scans/{run_id}/flag", status_code=202)
    def flag_scan(slug: str, run_id: str) -> dict[str, Any]:
        """Gắn cờ kết quả: khởi động một lượt quét lại với flag=True để tránh trượt ID (Điểm 4 Mục 6)."""
        _validate_run_id(run_id)
        try:
            prev_run = runner.get_run(slug, run_id)
            job_id = prev_run.get("job_id")
            if not job_id:
                raise HTTPException(status_code=400, detail="Lần quét cũ thiếu job_id")
            new_run_id = runner.start_scan(slug, int(job_id), flag=True)
            return {
                "run_id": new_run_id,
                "message": f"Đã khởi động quét lại và gắn cờ lỗi cho Job #{job_id}.",
            }
        except ProjectError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @application.get("/api/projects/{slug}/scans/{run_id}/report.html")
    def get_html_report(slug: str, run_id: str) -> FileResponse:
        _validate_run_id(run_id)
        path = pm._project_dir(slug) / "runs" / run_id / "report.html"
        if not path.is_file():
            raise HTTPException(status_code=404, detail="Không tìm thấy file report.html")
        return FileResponse(path, media_type="text/html")

    @application.get("/api/projects/{slug}/scans/{run_id}/report.csv")
    def get_csv_report(slug: str, run_id: str) -> FileResponse:
        _validate_run_id(run_id)
        path = pm._project_dir(slug) / "runs" / run_id / "report.csv"
        if not path.is_file():
            raise HTTPException(status_code=404, detail="Không tìm thấy file report.csv")
        return FileResponse(path, media_type="text/csv", filename=f"report_{run_id}.csv")


    # --- Phục vụ Static Files & Single Page App ---

    if STATIC_DIR.is_dir():
        application.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

        @application.get("/")
        def serve_index() -> FileResponse:
            return FileResponse(STATIC_DIR / "index.html")

    return application


app = create_app()
