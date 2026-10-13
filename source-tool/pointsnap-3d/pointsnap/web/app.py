"""FastAPI server cho PointSnap 3D Web UI (A11)."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal
from urllib.parse import urlsplit

from fastapi import FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from pointsnap.adapters.cvat.client import CvatClient, CvatError
from pointsnap.core.config import ConfigError
from pointsnap.web.link import ExtensionLink
from pointsnap.web.preview import PreviewError, finding_preview, load_reviews, save_review
from pointsnap.web.projects import ProjectError, ProjectManager
from pointsnap.web.runner import ScanRunner, ScanBusyError, RUN_ID_RE
from pointsnap.web.storage import StorageError
from pointsnap.web.security import LocalRequestBoundary

STATIC_DIR = Path(__file__).parent / "static"

# run_id hợp lệ: YYYYMMDD-HHMMSS[-<ms>]-job<id>  (điểm nhỏ 3 — chặn path traversal)
_RUN_ID_RE = RUN_ID_RE


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


class ReviewRequest(BaseModel):
    verdict: Literal["ok", "fp"] | None = None


class FocusRequest(BaseModel):
    track_id: int | None = Field(default=None, ge=0)
    source_id: int | None = Field(default=None, ge=0)
    """Lệnh từ web: tab CVAT có extension đang mở job này hãy chuyển tới frame và làm sáng box của mục này."""

    job_id: int = Field(gt=0)
    frame: int = Field(ge=0)
    cvat_url: str = ""
    label: str | None = None
    message: str | None = None
    run_id: str | None = None
    index: int | None = None
    bring: bool = False  # True: đưa tab CVAT lên trước (bấm "Mở trong CVAT"); False: chỉ đồng bộ theo lựa chọn


class StartScanRequest(BaseModel):
    job_id: int = Field(gt=0)
    flag: bool = False


def _same_cvat(a: str, b: str) -> bool:
    """Hai URL CVAT cùng một máy chủ (coi localhost và 127.0.0.1 là một, bỏ `/` cuối)."""

    def norm(url: str) -> str:
        parts = urlsplit(url.strip())
        host = "localhost" if parts.hostname in ("127.0.0.1", "::1") else (parts.hostname or "")
        return f"{parts.scheme}://{host}:{parts.port or (443 if parts.scheme == 'https' else 80)}{parts.path.rstrip('/')}"

    return norm(a) == norm(b)


def create_app(home_dir: Path | str | None = None) -> FastAPI:
    pm = ProjectManager(home_dir=home_dir)
    runner = ScanRunner(project_manager=pm)
    link = ExtensionLink()

    application = FastAPI(
        title="PointSnap 3D",
        description="Giao diện Web kiểm tra và giám sát chất lượng nhãn 3D trên CVAT",
        version="0.1.0",
    )
    application.add_middleware(LocalRequestBoundary)

    @application.exception_handler(RequestValidationError)
    async def invalid_request(request, exc):
        # Pydantic có thể echo input là token object; chỉ trả vị trí và lý do.
        errors = [{k: e[k] for k in ('loc', 'msg', 'type') if k in e} for e in exc.errors()]
        return JSONResponse(status_code=422, content={'detail': errors})

    @application.middleware("http")
    async def revalidate_ui_files(request, call_next):
        """Trang giao diện luôn được trình duyệt kiểm lại, để bản cập nhật hiện ngay mà không cần xóa cache."""
        response = await call_next(request)
        if request.url.path == "/" or request.url.path.startswith("/static/"):
            response.headers["Cache-Control"] = "no-cache"
        return response

    # Lưu trữ trong app.state để test có thể truy cập nếu cần
    application.state.pm = pm
    application.state.runner = runner
    application.state.link = link

    @application.exception_handler(StorageError)
    async def invalid_storage(request, exc):
        return JSONResponse(status_code=409, content={"detail": str(exc)})

    @application.exception_handler(ConfigError)
    async def invalid_config(request, exc):
        return JSONResponse(status_code=400, content={"detail": str(exc)})

    @application.exception_handler(OSError)
    async def storage_unavailable(request, exc):
        return JSONResponse(status_code=503, content={"detail": "Không đọc/ghi được dữ liệu; kiểm tra quyền và dung lượng ổ đĩa."})

    @application.exception_handler(ScanBusyError)
    async def scan_busy(request, exc):
        return JSONResponse(status_code=429, content={"detail": str(exc)})

    # --- API Danh mục quy tắc kiểm tra (Rule Catalog - Single Source of Truth) ---

    @application.get("/api/rules")
    def get_rules_catalog() -> dict[str, Any]:
        """Danh mục toàn bộ quy tắc kiểm tra nhãn 3D, nhãn hiển thị và gợi ý sửa lỗi."""
        from pointsnap.core.rules import rules_catalog_dict
        return rules_catalog_dict()

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
            runner.delete_project(slug)
            return {"ok": True, "message": f"Đã xóa dự án '{slug}'."}
        except ProjectError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except ScanBusyError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

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
            try:
                ver = client.server_version()
            finally:
                client.session.close()
            return {"connected": True, "version": ver, "url": cfg.cvat.url}
        except Exception as exc:
            token = pm.get_token(slug)
            error = str(exc).replace(token, "***") if token else str(exc)
            return {"connected": False, "error": error, "url": proj["cvat_url"]}

    @application.get("/api/projects/{slug}/cvat/tasks")
    def get_cvat_tasks(slug: str) -> dict[str, Any]:
        client = None
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
            token = pm.get_token(slug)
            error = str(exc).replace(token, "***") if token else str(exc)
            raise HTTPException(status_code=400, detail=error) from exc
        except ProjectError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        finally:
            if client is not None:
                client.session.close()

    # --- API Quét & Báo cáo ---

    def _validate_run_id(run_id: str) -> None:
        """Điểm nhỏ 3: chặn path traversal qua run_id độc hại (vd: ../../etc/passwd)."""
        if not _RUN_ID_RE.fullmatch(run_id):
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
        except (StorageError, OSError, ScanBusyError):
            raise
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
            data = runner.get_run(slug, run_id, include_findings=True)
            data["reviews"] = load_reviews(pm._project_dir(slug) / "runs" / run_id)
            return data
        except ProjectError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @application.get("/api/projects/{slug}/scans/{run_id}/findings/{index}/preview")
    def get_finding_preview(slug: str, run_id: str, index: int) -> dict[str, Any]:
        """Point cloud quanh box của một mục, trong hệ của box, để xem nhanh không cần mở CVAT (A14)."""
        _validate_run_id(run_id)
        try:
            project = pm.get_project(slug)
            return finding_preview(runner.run_dir(slug, run_id), project, index)
        except ProjectError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except PreviewError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @application.put("/api/projects/{slug}/scans/{run_id}/reviews/{index}")
    def put_review(slug: str, run_id: str, index: int, req: ReviewRequest) -> dict[str, Any]:
        """Lưu kết luận xem tay của một mục: ok = đúng là lỗi, fp = báo nhầm, null = bỏ kết luận."""
        _validate_run_id(run_id)
        try:
            run = runner.get_run(slug, run_id, include_findings=True)
        except ProjectError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        if not 0 <= index < len(run.get("findings") or []):
            raise HTTPException(status_code=404, detail=f"Không có mục số {index}")
        reviews = save_review(runner.run_dir(slug, run_id), index, req.verdict)
        link.bump_reviews()
        return {"reviews": reviews}

    @application.get("/api/projects/{slug}/scans/{run_id}/reviews")
    def get_reviews(slug: str, run_id: str) -> dict[str, Any]:
        """Chỉ kết luận xem tay (nhẹ hơn tải cả lần quét), để web và extension đồng bộ với nhau."""
        _validate_run_id(run_id)
        try:
            runner.get_run(slug, run_id)
            run_dir = runner.run_dir(slug, run_id)
        except ProjectError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return {"reviews": load_reviews(run_dir), "rev": link.reviews_rev}

    @application.get("/api/projects/{slug}/learn")
    def get_learning(slug: str) -> dict[str, Any]:
        """Kết quả học từ kết luận đã duyệt hiện đang dùng (lớp 4 của Box Verifier)."""
        from pointsnap.learn import load_model, report

        try:
            pm.get_project(slug)
            model = load_model(pm._project_dir(slug))
        except ProjectError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return {"model": model.to_dict() if model else None, "report": report(model) if model else None}

    @application.post("/api/projects/{slug}/learn")
    def post_learning(slug: str) -> dict[str, Any]:
        """Học lại từ mọi kết luận Đúng / Báo nhầm của dự án; áp dụng từ lần quét sau."""
        from pointsnap.learn import learn_project, report

        try:
            pm.get_project(slug)
            model = learn_project(pm._project_dir(slug))
        except ProjectError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return {"model": model.to_dict(), "report": report(model)}

    @application.post("/api/projects/{slug}/scans/{run_id}/flag", status_code=202)
    def flag_scan(slug: str, run_id: str) -> dict[str, Any]:
        """Gắn cờ kết quả: khởi động một lượt quét lại với flag=True để tránh trượt ID (Điểm 4 Mục 6)."""
        _validate_run_id(run_id)
        try:
            prev_run = runner.get_run(slug, run_id)
            if prev_run.get("status") != "done":
                raise HTTPException(status_code=409, detail="Chỉ gắn cờ từ lần quét đã hoàn tất")
            source_url = (prev_run.get("summary") or {}).get("cvat_url")
            snapshot = runner.run_dir(slug, run_id) / "snapshot.json"
            if not source_url and snapshot.is_file():
                from pointsnap.web.storage import read_json
                source_url = read_json(snapshot).get("meta", {}).get("url")
            if not source_url:
                raise HTTPException(status_code=409, detail="Lần quét cũ thiếu nguồn CVAT; hãy quét mới trước khi gắn cờ")
            if not _same_cvat(source_url, pm.get_project(slug)["cvat_url"]):
                raise HTTPException(status_code=409, detail="URL CVAT đã đổi; hãy quét mới trước khi gắn cờ")
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

    @application.post("/api/extension/focus")
    def extension_focus(req: FocusRequest) -> dict[str, Any]:
        """Web gửi lệnh mở một mục trong tab CVAT có sẵn; `extension_online` = False thì web tự mở link."""
        return link.focus(req.job_id, req.model_dump(exclude={"job_id"}), scope=_extension_scope(req.cvat_url))

    def _extension_scope(url: str) -> str:
        if not url:
            urls = {p["cvat_url"].rstrip('/') for p in pm.list_projects()}
            if len(urls) > 1:
                raise HTTPException(status_code=400, detail="Cần cvat_url khi có nhiều server CVAT; cập nhật Web/extension.")
            url = next(iter(urls), "")
        if not url:
            return ""
        try:
            parts = urlsplit(url.strip())
            host = "localhost" if parts.hostname in ("127.0.0.1", "::1") else parts.hostname
            if parts.scheme not in ("http", "https") or not host or parts.username or parts.password:
                raise ValueError("URL không hợp lệ")
            return f"{parts.scheme}://{host}:{parts.port or (443 if parts.scheme == 'https' else 80)}{parts.path.rstrip('/')}"
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="cvat_url không hợp lệ") from exc

    @application.get("/api/extension/poll")
    def extension_poll(job_id: int, after: int = -1, cvat_url: str = "") -> dict[str, Any]:
        """Extension trên tab CVAT hỏi lệnh mới (mỗi giây); cũng là tín hiệu tab đó đang mở job."""
        res = link.poll(job_id, after, scope=_extension_scope(cvat_url))
        projects = pm.list_projects()
        latest_done = None
        active_scan = None
        for p in projects:
            for r in runner.list_runs(p["slug"]):
                if r.get("job_id") == job_id:
                    if r.get("status") in ("queued", "running") and active_scan is None:
                        active_scan = {
                            "run_id": r.get("run_id"),
                            "status": r.get("status"),
                            "progress": r.get("progress", 0),
                            "message": r.get("message", "Đang quét..."),
                        }
                    elif r.get("status") == "done" and latest_done is None:
                        latest_done = r.get("run_id")
        res["latest_run_id"] = latest_done
        res["active"] = active_scan
        return res

    @application.get("/api/extension/status")
    def extension_status(job_id: int, cvat_url: str = "") -> dict[str, Any]:
        """Web hỏi: có tab CVAT nào (cài extension) đang mở job này không, và phiên bản kết luận xem tay."""
        return link.status(job_id, scope=_extension_scope(cvat_url))

    @application.get("/api/extension/jobs/{job_id}")
    def extension_job(job_id: int, cvat_url: str = "") -> dict[str, Any]:
        """Cho extension trên trang CVAT (A15): dự án ứng với CVAT đang mở, lần quét mới nhất của job.

        `run` là lần quét xong gần nhất (kèm findings, reviews); `active` là lần đang chờ hoặc đang chạy.
        """
        projects = pm.list_projects()
        if cvat_url:
            scope = _extension_scope(cvat_url)
            projects = [p for p in projects if _extension_scope(p.get("cvat_url", "")) == scope]
        else:
            _extension_scope("")
        runs = [
            r for p in projects for r in runner.list_runs(p["slug"])
            if r.get("job_id") == job_id and (not cvat_url or not (r.get("summary") or {}).get("cvat_url")
                or _same_cvat(r["summary"]["cvat_url"], cvat_url))
        ]
        runs.sort(key=lambda r: r.get("started_at") or "", reverse=True)
        active = next((r for r in runs if r.get("status") in ("queued", "running")), None)
        done = next((r for r in runs if r.get("status") == "done"), None)
        run = None
        if done:
            slug = done["project_slug"]
            run = runner.get_run(slug, done["run_id"], include_findings=True)
            run["reviews"] = load_reviews(pm._project_dir(slug) / "runs" / done["run_id"])
        project = projects[0] if projects else None
        if run:
            project = next(p for p in projects if p["slug"] == run["project_slug"])
        return {
            "project": {"slug": project["slug"], "name": project["name"]} if project else None,
            "run": run,
            "active": active,
        }

    @application.get("/api/projects/{slug}/scans/{run_id}/report.html")
    def get_html_report(slug: str, run_id: str) -> FileResponse:
        _validate_run_id(run_id)
        try:
            run_dir = runner.run_dir(slug, run_id)
        except ProjectError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        path = run_dir / "report.html"
        if not path.is_file():
            raise HTTPException(status_code=404, detail="Không tìm thấy file report.html")
        if runner.get_run(slug, run_id).get("status") != "done":
            raise HTTPException(status_code=409, detail="Lần quét chưa hoàn tất; không tải báo cáo dở")
        return FileResponse(path, media_type="text/html")

    @application.get("/api/projects/{slug}/scans/{run_id}/report.csv")
    def get_csv_report(slug: str, run_id: str) -> FileResponse:
        _validate_run_id(run_id)
        try:
            run_dir = runner.run_dir(slug, run_id)
        except ProjectError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        path = run_dir / "report.csv"
        if not path.is_file():
            raise HTTPException(status_code=404, detail="Không tìm thấy file report.csv")
        if runner.get_run(slug, run_id).get("status") != "done":
            raise HTTPException(status_code=409, detail="Lần quét chưa hoàn tất; không tải báo cáo dở")
        return FileResponse(path, media_type="text/csv", filename=f"report_{run_id}.csv")


    # --- Phục vụ Static Files & Single Page App ---

    if STATIC_DIR.is_dir():
        application.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

        @application.get("/")
        def serve_index() -> FileResponse:
            return FileResponse(STATIC_DIR / "index.html")

    return application


app = create_app()
