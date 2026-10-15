"""FastAPI server cho PointSnap 3D Web UI (A11)."""

from __future__ import annotations

import copy
import logging
import math
import os
import threading
from contextvars import ContextVar
from pathlib import Path
from typing import Any, Literal
from urllib.parse import urlsplit

from fastapi import FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from pointsnap.adapters.cvat.client import CvatClient, CvatError
from pointsnap.adapters.cvat.repair_sync import same_track, write_verified_track
from pointsnap.adapters.cvat.shapes import cuboid_to_points, points_to_geometry
from pointsnap.adapters.cvat.writer import OCCConflictError, compute_track_etag
from pointsnap.core.config import ConfigError
from pointsnap.core.geometry import normalize_angle
from pointsnap.core.heading_memory import HeadingMemory
from pointsnap.adapters.cvat.reader import ManifestFrames, find_manifest
from pointsnap.cli.common import export_dirs
from pointsnap.core.repair import compute_box_repair
from pointsnap.core.ghost import generate_ghost_target, GhostTarget
from pointsnap.core.serialize import load_cuboids
from pointsnap.detectors.heading import detect_heading_track, _world
from pointsnap.detectors.static import detect_static_errors
from pointsnap.history.manager import HistoryManager, SnapshotIsolationError, track_dict_to_cuboids
from pointsnap.web.link import ExtensionLink
from pointsnap.web.preview import PreviewError, _finding_box, finding_camera, finding_preview, load_reviews, save_review
from pointsnap.web.projects import ProjectError, ProjectManager
from pointsnap.web.runner import ScanRunner, ScanBusyError, RUN_ID_RE
from pointsnap.web.security import LocalRequestBoundary
from pointsnap.web.storage import StorageError

_request_clients = ContextVar("pointsnap__request_clients", default=None)

logger = logging.getLogger(__name__)

STATIC_DIR = Path(__file__).parent / "static"

# run_id hợp lệ: YYYYMMDD-HHMMSS[-<ms>]-job<id>  (điểm nhỏ 3 — chặn path traversal)
_RUN_ID_RE = RUN_ID_RE
_track_lock = threading.RLock()


class ApplyRepairRequest(BaseModel):
    frame: int
    repair: dict[str, Any]
    client_track_etag: str | None = None
    slug: str | None = None


class RollbackRepairRequest(BaseModel):
    history_id: str
    slug: str | None = None



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
    async def close_cvat_clients(request, call_next):
        clients = []
        token = _request_clients.set(clients)
        try:
            return await call_next(request)
        finally:
            _request_clients.reset(token)
            for client in clients:
                client.session.close()

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
    application.state.history_manager = HistoryManager(home_dir=pm.home_dir)
    application.state.mock_tracks = {}
    application.state.mock_points = {}
    application.state.cvat_client = None

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
                            "start_frame": j.get("start_frame"),
                            "stop_frame": j.get("stop_frame"),
                            "frame_count": j.get("frame_count"),
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

    @application.get("/api/projects/{slug}/scans/{run_id}/findings/{index}/camera")
    def get_finding_camera(slug: str, run_id: str, index: int, full: bool = False) -> Response:
        """Ảnh camera (JPEG) thấy box của một mục rõ nhất, có vẽ khung 3D; `full=true` cho cả ảnh thay vì phần cắt."""
        _validate_run_id(run_id)
        try:
            project = pm.get_project(slug)
            jpeg, channel = finding_camera(runner.run_dir(slug, run_id), project, index, full=full)
        except ProjectError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except PreviewError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return Response(content=jpeg, media_type="image/jpeg",
                        headers={"X-Camera-Channel": channel, "Cache-Control": "private, max-age=300"})

    @application.put("/api/projects/{slug}/scans/{run_id}/reviews/{index}")
    def put_review(slug: str, run_id: str, index: int, req: ReviewRequest) -> dict[str, Any]:
        """Lưu kết luận xem tay của một mục: ok = đúng là lỗi, fp = báo nhầm, null = bỏ kết luận."""
        _validate_run_id(run_id)
        try:
            run = runner.get_run(slug, run_id, include_findings=True)
        except ProjectError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        if not any(f["index"] == index for f in run.get("findings") or []):
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
        latest_started_at = ""
        active_scan = None
        for p in projects:
            if cvat_url and _extension_scope(p["cvat_url"]) != _extension_scope(cvat_url):
                continue
            latest, active, started_at = runner.poll_state(p["slug"], job_id)
            if latest and (latest_done is None or started_at > latest_started_at):
                latest_done = latest
                latest_started_at = started_at
            if active and active_scan is None:
                active_scan = {k: active.get(k) for k in ("run_id", "status", "progress", "message")}
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

    # --- API Hỗ trợ sửa tự động & Hoàn tác nhãn (Features F8, F9, F10) ---

    def _is_test_track(job_id, track_id):
        tracks = getattr(application.state, "mock_tracks", {})
        return (job_id, track_id) in tracks or any(
            t.get("id") == track_id for t in tracks.get(job_id, {}).get("tracks", []))

    def _require_project(job_id: int, track_id: int, slug: str | None) -> None:
        if _is_test_track(job_id, track_id):
            return
        if not slug:
            raise HTTPException(400, "Cần chọn dự án để sửa đúng nguồn CVAT")
        try:
            pm.get_project(slug)
        except ProjectError as exc:
            raise HTTPException(400, "Dự án không hợp lệ") from exc

    def _resolve_track(job_id: int, track_id: int, slug: str | None = None, *, allow_snapshot: bool = True) -> tuple[dict[str, Any] | None, CvatClient | None]:
        track_data = None
        cvat_client = getattr(application.state, "cvat_client", None)
        if hasattr(application.state, "mock_tracks"):
            track_data = application.state.mock_tracks.get((job_id, track_id))
            if track_data is None:
                raw_annos = application.state.mock_tracks.get(job_id)
                if isinstance(raw_annos, dict):
                    for t in raw_annos.get("tracks", []):
                        if t.get("id") == track_id:
                            track_data = t
                            break
        if track_data is None and cvat_client is not None:
            try:
                raw_annos = cvat_client.get_job_annotations(job_id)
                for t in raw_annos.get("tracks", []):
                    if t.get("id") == track_id:
                        track_data = t
                        break
            except Exception as exc:
                cvat_client = None
                if not allow_snapshot:
                    raise HTTPException(502, "Không đọc được nhãn từ CVAT") from exc

        if track_data is None:
            target_slug = slug
            if target_slug:
                try:
                    cfg = pm.get_effective_config(target_slug)
                    if cfg.cvat.token:
                        c = CvatClient(cfg.cvat.url, cfg.cvat.token, timeout=10.0)
                        _request_clients.get().append(c)
                        raw_annos = c.get_job_annotations(job_id)
                        for t in raw_annos.get("tracks", []):
                            if t.get("id") == track_id:
                                track_data = t
                                cvat_client = c
                                break
                except Exception as exc:
                    cvat_client = None
                    if not allow_snapshot:
                        raise HTTPException(502, "Không kết nối được CVAT của dự án; chưa đồng bộ") from exc

        # Phương án dự phòng ngoại tuyến: Nạp track từ file snapshot.json của scan runs
        if track_data is None and allow_snapshot:
            candidate_slugs = [slug] if slug else []
            for s in candidate_slugs:
                if not s:
                    continue
                try:
                    runs = runner.list_runs(s)
                except Exception:
                    continue
                for run_summary in runs:
                    try:
                        sum_job = int(run_summary.get("job_id") or 0)
                    except (ValueError, TypeError):
                        sum_job = 0
                    if job_id != 0 and sum_job != 0 and sum_job != job_id:
                        continue
                    r_id = run_summary.get("run_id")
                    if not r_id:
                        continue
                    try:
                        snap_path = runner.run_dir(s, r_id) / "snapshot.json"
                        if snap_path.is_file():
                            cuboids, _ = load_cuboids(snap_path)
                            matching = [c for c in cuboids if c.track_id == track_id]
                            if matching:
                                shapes = []
                                for mc in matching:
                                    pts = cuboid_to_points(mc)
                                    attrs = [{"name": k, "value": str(v)} for k, v in getattr(mc, "attrs", {}).items()]
                                    shapes.append({
                                        "type": "box",
                                        "frame": mc.frame,
                                        "points": pts,
                                        "label_id": 0,
                                        "attributes": attrs,
                                        "occluded": getattr(mc, "occluded", False),
                                        "outside": getattr(mc, "outside", False),
                                        "keyframe": getattr(mc, "keyframe", True),
                                        "id": getattr(mc, "source_id", 0),
                                    })
                                track_data = {
                                    "id": track_id,
                                    "label": matching[0].label,
                                    "shapes": shapes,
                                }
                                break
                    except Exception:
                        pass
                if track_data is not None:
                    break

            # Dự phòng bổ sung: Nạp từ lịch sử sửa đổi (HistoryManager) nếu không có scan runs
            if track_data is None:
                try:
                    history_mgr = getattr(application.state, "history_manager", None) or HistoryManager(home_dir=pm.home_dir)
                    for s in candidate_slugs:
                        snaps = history_mgr.list_snapshots(job_id=job_id, slug=s, track_id=track_id)
                        if snaps:
                            latest = snaps[0]
                            snap_data = history_mgr.get_snapshot(job_id, latest["history_id"], slug=s, track_id=track_id)
                            track_data = snap_data.get("post_repair_track") or snap_data.get("pre_repair_track")
                            if track_data:
                                break
                except Exception:
                    pass

        return track_data, cvat_client

    @application.get("/api/jobs/{job_id}/tracks/{track_id}/repair")
    def get_track_repair(job_id: int, track_id: int, frame: int, rule: str = "floating", slug: str | None = None) -> Any:
        return _compute_track_repair(job_id, track_id, frame, rule, slug)

    def _compute_track_repair(
        job_id: int,
        track_id: int,
        frame: int,
        rule: str = "floating",
        slug: str | None = None,
        points: Any = None,
        finding_details: dict[str, Any] | None = None,
        frame_source: Any = None,
    ) -> Any:
        """Tính toán tham số sửa đổi hình học đề xuất cho một box thuộc track (Feature F8)."""
        track_data, repair_client = _resolve_track(job_id, track_id, slug=slug)
        if track_data is None:
            return JSONResponse(
                status_code=404,
                content={"status": "error", "code": 404, "detail": f"Track {track_id} not found in job {job_id}"},
            )

        label_name = track_data.get("label", "car")
        task_id = job_id
        if repair_client is not None:
            try:
                metadata = repair_client.get_job(job_id)
                task_id = metadata["task_id"]
                labels = repair_client.task_labels(task_id)
                label_name = next((l["name"] for l in labels if l["id"] == track_data.get("label_id")), label_name)
            except Exception:
                pass
        cuboids = track_dict_to_cuboids(track_data, label_name=label_name)
        target_cuboid = next((c for c in cuboids if c.frame == frame), None)
        if target_cuboid is None:
            return JSONResponse(
                status_code=404,
                content={"status": "error", "code": 404, "detail": f"Frame {frame} not found in track {track_id}"},
            )

        frame_source = frame_source or getattr(application.state, "frame_source", None)
        cfg = None
        if slug:
            try:
                proj = pm.get_project(slug)
                cfg = pm.get_effective_config(slug)
                if frame_source is None:
                    manifest = find_manifest(task_id, export_dirs(proj.get("export_dirs") or None), url=cfg.cvat.url)
                    if manifest:
                        frame_source = ManifestFrames(manifest, dataroot=proj.get("nuscenes_root") or None)
            except (ProjectError, ValueError, OSError):
                pass
        heading_prediction = None
        details = dict(finding_details or {})
        if rule.startswith("heading") and frame_source is not None:
            active = [b for b in cuboids if b.visible and b.keyframe]
            poses, timestamps = {}, {}
            for box in active:
                data = frame_source.frame_data(box.frame, with_points=False)
                if data.sensor_to_world is not None:
                    poses[box.frame] = data.sensor_to_world
                if data.timestamp is not None:
                    timestamps[box.frame] = data.timestamp
            if all(b.frame in poses for b in active):
                from pointsnap.core.config import load_config
                cfg = cfg or load_config()
                fresh_findings = detect_heading_track(active, cfg.heading,
                    keyframe_interval_s=cfg.track.keyframe_interval_s, sensor_to_world=poses, timestamps=timestamps)
                fresh_findings += detect_static_errors(active, cfg.static, poses)
                fresh = next((f for f in fresh_findings if f.frame == frame and f.rule == rule), None)
                # Do not use an old world-space angle against a fresh sensor-space cuboid.
                details.pop("target_yaw_sensor", None)
                if fresh:
                    details.update(fresh.details)
                centers, headings, _ = _world(active, poses)
                memory = HeadingMemory()
                for i, box in enumerate(active):
                    if box.frame > frame:
                        break
                    memory.update(track_id, box.frame, timestamps.get(box.frame, box.frame * cfg.track.keyframe_interval_s),
                                  centers[i], headings[i])
                prediction = memory.predict(track_id, cfg.track.keyframe_interval_s)
                heading_prediction = prediction.to_dict() if prediction else None
                if rule in ("heading.flip", "heading.motion", "heading.static") and fresh is None:
                    details["target_yaw_sensor"] = target_cuboid.yaw
        if rule == "heading.motion" and not _is_test_track(job_id, track_id) and "target_yaw_sensor" not in details:
            details["target_yaw_sensor"] = target_cuboid.yaw
        if details.get("maybe_reversing"):
            details["target_yaw_sensor"] = target_cuboid.yaw

        if points is None:
            if hasattr(application.state, "mock_points"):
                points = application.state.mock_points.get((job_id, frame))
            if points is None:
                target_slug = slug
                if target_slug:
                    try:
                        proj = pm.get_project(target_slug)
                        manifest_path = find_manifest(task_id, export_dirs(proj.get("export_dirs") or None), url=proj["cvat_url"])
                        if manifest_path:
                            mf = ManifestFrames(manifest_path, dataroot=proj.get("nuscenes_root") or None)
                            raw_pts = mf.frame_data(frame).points
                            if raw_pts is not None and len(raw_pts) > 0:
                                points = raw_pts[:, :3]
                    except Exception:
                        pass

        if rule == "fit.loose" and points is not None and len(points) >= 10:
            from pointsnap.detectors.fit import loose_measure
            try:
                lm = loose_measure(points, target_cuboid)
                if lm and lm.get("face"):
                    details["face"] = lm["face"]
                    details["gap"] = lm.get("gap", 0.0)
            except Exception:
                pass

        try:
            delta = compute_box_repair(
                cuboid=target_cuboid,
                track=cuboids,
                points=points,
                rule=rule,
                finding_details=details,
            )
            repair_dict = delta.to_dict()
            changed = any(abs(v) > 1e-6 for v in (*delta.delta_center, *delta.delta_dims, delta.delta_yaw))
            repair_dict["applicable"] = changed and delta.confidence > 0 and (repair_client is not None or _is_test_track(job_id, track_id))
            if not changed:
                repair_dict["confidence"] = 0.0
                repair_dict["reason"] = "Đề xuất không thay đổi hình học. Cần kiểm tra thủ công hoặc quét lại. " + delta.reason
        except (ValueError, Exception) as exc:
            target_box_dict = {
                "center": [float(v) for v in target_cuboid.center],
                "dims": [float(v) for v in target_cuboid.dims],
                "yaw": float(target_cuboid.yaw),
                "label": target_cuboid.label,
                "frame": target_cuboid.frame,
                "track_id": target_cuboid.track_id,
                "source_id": target_cuboid.source_id,
            }
            repair_dict = {
                "delta_center": [0.0, 0.0, 0.0],
                "delta_dims": [0.0, 0.0, 0.0],
                "delta_yaw": 0.0,
                "repaired_cuboid": target_box_dict,
                "repaired_box": target_box_dict,
                "rule": rule,
                "target_offset_m": 0.0,
                "confidence": 0.0,
                "reason": f"Không có đề xuất tự động cho quy tắc '{rule}'; cần kiểm tra thủ công",
                "applicable": False,
            }

        server_etag = compute_track_etag(track_data)
        return {
            "status": "ok",
            "repair": repair_dict,
            "rule": rule,
            "job_id": job_id,
            "track_id": track_id,
            "frame": frame,
            "track_etag": server_etag,
            "heading_prediction": heading_prediction,
        }

    @application.get("/api/jobs/{job_id}/tracks/{track_id}/ghost-target")
    def get_track_ghost_target(job_id: int, track_id: int, frame: int, rule: str | None = None, slug: str | None = None) -> Any:
        return _compute_ghost_target(job_id, track_id, frame, rule, slug)

    def _compute_ghost_target(
        job_id: int,
        track_id: int,
        frame: int,
        rule: str | None = None,
        slug: str | None = None,
        points: Any = None,
        finding_details: dict[str, Any] | None = None,
        frame_source: Any = None,
    ) -> Any:
        """Sinh khung gióng mục tiêu (Ghost Target Box) chuẩn xác tuyệt đối cho track (Milestone M1, Features F1-F4)."""
        track_data, repair_client = _resolve_track(job_id, track_id, slug=slug)
        if track_data is None:
            return JSONResponse(
                status_code=404,
                content={"status": "error", "code": 404, "detail": f"Track {track_id} not found in job {job_id}"},
            )

        label_name = track_data.get("label", "car")
        task_id = job_id
        if repair_client is not None:
            try:
                metadata = repair_client.get_job(job_id)
                task_id = metadata["task_id"]
                labels = repair_client.task_labels(task_id)
                label_name = next((l["name"] for l in labels if l["id"] == track_data.get("label_id")), label_name)
            except Exception:
                pass
        cuboids = track_dict_to_cuboids(track_data, label_name=label_name)
        target_cuboid = next((c for c in cuboids if c.frame == frame), None)
        if target_cuboid is None:
            return JSONResponse(
                status_code=404,
                content={"status": "error", "code": 404, "detail": f"Frame {frame} not found in track {track_id}"},
            )

        frame_source = frame_source or getattr(application.state, "frame_source", None)
        cfg = None
        if slug:
            try:
                proj = pm.get_project(slug)
                cfg = pm.get_effective_config(slug)
                if frame_source is None:
                    manifest = find_manifest(task_id, export_dirs(proj.get("export_dirs") or None), url=cfg.cvat.url)
                    if manifest:
                        frame_source = ManifestFrames(manifest, dataroot=proj.get("nuscenes_root") or None)
            except (ProjectError, ValueError, OSError):
                pass

        details = dict(finding_details or {})
        active_rule = rule or ""
        if active_rule.startswith("heading") and frame_source is not None:
            active = [b for b in cuboids if b.visible and b.keyframe]
            poses, timestamps = {}, {}
            for box in active:
                data = frame_source.frame_data(box.frame, with_points=False)
                if data.sensor_to_world is not None:
                    poses[box.frame] = data.sensor_to_world
                if data.timestamp is not None:
                    timestamps[box.frame] = data.timestamp
            if all(b.frame in poses for b in active):
                from pointsnap.core.config import load_config
                cfg = cfg or load_config()
                fresh_findings = detect_heading_track(active, cfg.heading,
                    keyframe_interval_s=cfg.track.keyframe_interval_s, sensor_to_world=poses, timestamps=timestamps)
                fresh_findings += detect_static_errors(active, cfg.static, poses)
                fresh = next((f for f in fresh_findings if f.frame == frame and f.rule == active_rule), None)
                details.pop("target_yaw_sensor", None)
                if fresh:
                    details.update(fresh.details)

        if points is None:
            if hasattr(application.state, "mock_points"):
                points = application.state.mock_points.get((job_id, frame))
            if points is None:
                target_slug = slug
                if target_slug:
                    try:
                        proj = pm.get_project(target_slug)
                        manifest_path = find_manifest(task_id, export_dirs(proj.get("export_dirs") or None), url=proj["cvat_url"])
                        if manifest_path:
                            mf = ManifestFrames(manifest_path, dataroot=proj.get("nuscenes_root") or None)
                            raw_pts = mf.frame_data(frame).points
                            if raw_pts is not None and len(raw_pts) > 0:
                                points = raw_pts[:, :3]
                    except Exception:
                        pass

        if active_rule == "fit.loose" and points is not None and len(points) >= 10:
            from pointsnap.detectors.fit import loose_measure
            try:
                lm = loose_measure(points, target_cuboid)
                if lm and lm.get("face"):
                    details["face"] = lm["face"]
                    details["gap"] = lm.get("gap", 0.0)
            except Exception:
                pass

        try:
            ghost_target = generate_ghost_target(
                cuboid=target_cuboid,
                track=cuboids,
                points=points,
                rule=active_rule,
                details=details,
            )
        except Exception as exc:
            logger.warning("generate_ghost_target failed: %s", exc)
            ghost_target = GhostTarget(
                center=target_cuboid.center,
                dims=target_cuboid.dims,
                yaw=target_cuboid.yaw,
                roll=0.0,
                pitch=0.0,
                ground_z=target_cuboid.bottom_z,
                target_bottom_z=target_cuboid.bottom_z,
                confidence=0.0,
                reason=f"Lỗi tính toán khung mục tiêu: {exc}",
            )

        server_etag = compute_track_etag(track_data)
        return {
            "status": "ok",
            "job_id": job_id,
            "track_id": track_id,
            "frame": frame,
            "ghost_target": ghost_target.to_dict(),
            "tolerances": {
                "snap_distance_m": 0.08,
                "snap_angle_deg": 4.0,
                "lock_distance_m": 0.02,
                "lock_angle_deg": 2.0,
            },
            "track_etag": server_etag,
        }

    @application.post("/api/jobs/{job_id}/tracks/{track_id}/apply-repair")
    def apply_track_repair(job_id: int, track_id: int, req: ApplyRepairRequest) -> Any:
        """Áp dụng sửa hình học đề xuất lên CVAT với OCC và lưu vết snapshot (Features F8, F9, F10)."""
        _require_project(job_id, track_id, req.slug)
        with _track_lock:
            track_data, cvat_client = _resolve_track(job_id, track_id, slug=req.slug, allow_snapshot=True)
            if track_data is None:
                return JSONResponse(
                    status_code=404,
                    content={"status": "error", "code": 404, "detail": f"Track {track_id} not found in job {job_id}"},
                )

            server_etag = compute_track_etag(track_data)
            if req.client_track_etag is not None and req.client_track_etag != server_etag:
                return JSONResponse(
                    status_code=409,
                    content={
                        "status": "conflict",
                        "code": 409,
                        "detail": f"OCC conflict: Client ETag '{req.client_track_etag}' != server ETag '{server_etag}'",
                    },
                )

            target_shape = next((s for s in track_data.get("shapes", []) if s.get("frame") == req.frame), None)
            if target_shape is None:
                return JSONResponse(
                    status_code=404,
                    content={"status": "error", "code": 404, "detail": f"Frame {req.frame} not found in track {track_id}"},
                )

            pre_repair_track = copy.deepcopy(track_data)
            post_repair_track = copy.deepcopy(track_data)
            pshape = next(s for s in post_repair_track.get("shapes", []) if s.get("frame") == req.frame)

            rep = req.repair
            repaired_info = rep.get("repaired_cuboid") or rep.get("repaired_box") or rep
            if not isinstance(repaired_info, dict):
                raise HTTPException(400, "Dữ liệu hình học sửa phải là một đối tượng JSON")

            def _to_float_or_nan(val: Any) -> float:
                if val is None:
                    return float("nan")
                try:
                    return float(val)
                except (TypeError, ValueError):
                    return float("nan")

            if "points" in repaired_info:
                pts_raw = repaired_info.get("points")
                if not isinstance(pts_raw, (list, tuple)):
                    return JSONResponse(
                        status_code=400,
                        content={"status": "error", "code": 400, "detail": "Points array must be a list or tuple"},
                    )
                new_pts = [_to_float_or_nan(v) for v in pts_raw]
            elif "center" in repaired_info and "dims" in repaired_info:
                c = repaired_info.get("center")
                d = repaired_info.get("dims")
                if not isinstance(c, (list, tuple)) or len(c) != 3 or not isinstance(d, (list, tuple)) or len(d) != 3:
                    return JSONResponse(
                        status_code=400,
                        content={"status": "error", "code": 400, "detail": "Center and dims must each contain 3 elements"},
                    )
                c_floats = [_to_float_or_nan(v) for v in c]
                d_floats = [_to_float_or_nan(v) for v in d]
                y = _to_float_or_nan(repaired_info.get("yaw", 0.0))
                r = _to_float_or_nan(repaired_info.get("roll", pshape["points"][3]))
                p = _to_float_or_nan(repaired_info.get("pitch", pshape["points"][4]))
                new_pts = [*c_floats, r, p, y, *d_floats, *pshape["points"][9:]]
            elif "delta_center" in rep or "delta_dims" in rep or "delta_yaw" in rep:
                try:
                    geo = points_to_geometry(pshape["points"])
                except Exception as exc:
                    return JSONResponse(
                        status_code=400,
                        content={"status": "error", "code": 400, "detail": f"Existing shape geometry is invalid: {exc}"},
                    )
                dc = rep.get("delta_center", [0, 0, 0])
                dd = rep.get("delta_dims", [0, 0, 0])
                dy = rep.get("delta_yaw", 0.0)
                if not isinstance(dc, (list, tuple)) or len(dc) != 3:
                    return JSONResponse(
                        status_code=400,
                        content={"status": "error", "code": 400, "detail": "delta_center must contain 3 elements"},
                    )
                if not isinstance(dd, (list, tuple)) or len(dd) != 3:
                    return JSONResponse(
                        status_code=400,
                        content={"status": "error", "code": 400, "detail": "delta_dims must contain 3 elements"},
                    )
                dc_floats = [_to_float_or_nan(v) for v in dc]
                dd_floats = [_to_float_or_nan(v) for v in dd]
                dy_float = _to_float_or_nan(dy)
                new_c = [geo["center"][i] + dc_floats[i] for i in range(3)]
                new_d = [geo["dims"][i] + dd_floats[i] for i in range(3)]
                new_y = normalize_angle(geo["yaw"] + dy_float)
                new_pts = [*new_c, geo["roll"], geo["pitch"], new_y, *new_d, *pshape["points"][9:]]
            else:
                new_pts = list(pshape["points"])

            # 1. Kiểm tra độ dài mảng points phải có đúng 16 số thực
            if len(new_pts) != 16:
                return JSONResponse(
                    status_code=400,
                    content={
                        "status": "error",
                        "code": 400,
                        "detail": f"Points array must have exactly 16 floats, got {len(new_pts)}",
                    },
                )

            # 2. Kiểm tra tất cả các giá trị phải là số hữu hạn (Defect 3)
            if not all(isinstance(v, (int, float)) and math.isfinite(v) for v in new_pts):
                return JSONResponse(
                    status_code=400,
                    content={
                        "status": "error",
                        "code": 400,
                        "detail": "All coordinates, orientation, and dimensions must be finite numbers",
                    },
                )

            # 3. Kiểm tra kích thước hộp phải hoàn toàn dương (> 0) (Defect 2)
            if not (new_pts[6] > 0.0 and new_pts[7] > 0.0 and new_pts[8] > 0.0):
                return JSONResponse(
                    status_code=400,
                    content={
                        "status": "error",
                        "code": 400,
                        "detail": "Dimensions must be strictly positive",
                    },
                )

            if all(math.isclose(a, b, rel_tol=0, abs_tol=1e-6) for a, b in zip(new_pts, pshape["points"])):
                if req.client_track_etag is not None:
                    raise HTTPException(400, "Đề xuất không thay đổi hình học; chưa áp dụng sửa")
                raise HTTPException(422, "Đề xuất không thay đổi hình học; chưa áp dụng sửa")
            if cvat_client is None and not _is_test_track(job_id, track_id):
                raise HTTPException(503, "Chỉ có bản xem ngoại tuyến; chưa kết nối CVAT để đồng bộ")
            pshape["points"] = new_pts

            history_mgr = getattr(application.state, "history_manager", None) or HistoryManager(home_dir=pm.home_dir)
            effective_slug = req.slug or "default"

            if cvat_client is not None:
                try:
                    post_repair_track = write_verified_track(cvat_client, job_id, pre_repair_track, post_repair_track)
                except OCCConflictError as exc:
                    raise HTTPException(409, str(exc)) from exc
                except Exception as exc:
                    logger.warning("Repair synchronization failed: %s", exc)
                    raise HTTPException(502, "Không xác nhận được sửa trên CVAT; chưa báo đồng bộ thành công") from exc

            hid = history_mgr.save_snapshot(
                job_id=job_id,
                track_id=track_id,
                frame=req.frame,
                pre_repair_track=pre_repair_track,
                post_repair_track=post_repair_track,
                applied_repair=req.repair,
                slug=effective_slug,
            )

            if hasattr(application.state, "mock_tracks"):
                if (job_id, track_id) in application.state.mock_tracks:
                    application.state.mock_tracks[(job_id, track_id)] = post_repair_track
                if job_id in application.state.mock_tracks and isinstance(application.state.mock_tracks[job_id], dict):
                    tracks = application.state.mock_tracks[job_id].get("tracks", [])
                    for i, t in enumerate(tracks):
                        if t.get("id") == track_id:
                            tracks[i] = post_repair_track
                            break

            if cvat_client is not None and req.slug:
                link.focus(job_id, {"action": "annotations_changed", "frame": req.frame, "track_id": track_id},
                           scope=_extension_scope(pm.get_project(req.slug)["cvat_url"]))

            return {
                "status": "ok",
                "message": "Đã áp dụng sửa đổi hình học thành công lên CVAT",
                "history_id": hid,
                "job_id": job_id,
                "track_id": track_id,
                "frame": req.frame,
                "new_scan_verdict": "NOT_RUN",
                "sync_status": "verified" if cvat_client is not None else "test",
                "updated_track": post_repair_track,
                "track_etag": compute_track_etag(post_repair_track),
                "reload_required": cvat_client is not None,
            }

    @application.post("/api/jobs/{job_id}/tracks/{track_id}/rollback")
    def rollback_track_repair(job_id: int, track_id: int, req: RollbackRepairRequest) -> Any:
        """Hoàn tác thay đổi nhãn từ snapshot bất biến (Features F8, F10)."""
        _require_project(job_id, track_id, req.slug)
        with _track_lock:
            history_mgr = getattr(application.state, "history_manager", None) or HistoryManager(home_dir=pm.home_dir)
            effective_slug = req.slug or "default"
            try:
                snapshot = history_mgr.get_snapshot(job_id, req.history_id, slug=effective_slug, track_id=track_id)
            except SnapshotIsolationError as exc:
                return JSONResponse(
                    status_code=400,
                    content={
                        "status": "error",
                        "code": 400,
                        "detail": f"Snapshot '{req.history_id}' does not belong to job {job_id} track {track_id}",
                    },
                )
            except (FileNotFoundError, ValueError, KeyError) as exc:
                return JSONResponse(
                    status_code=404,
                    content={"status": "error", "code": 404, "detail": f"Snapshot '{req.history_id}' not found or invalid for job {job_id}"},
                )

            # Kiểm tra cách ly đối tượng (Cross-Job and Cross-Track Isolation Enforcement)
            try:
                snap_job_id = int(snapshot.get("job_id", -1))
                snap_track_id = int(snapshot.get("track_id", -1))
            except (ValueError, TypeError):
                snap_job_id, snap_track_id = -1, -1

            if snap_job_id != job_id or snap_track_id != track_id:
                return JSONResponse(
                    status_code=400,
                    content={
                        "status": "error",
                        "code": 400,
                        "detail": f"Snapshot '{req.history_id}' does not belong to job {job_id} track {track_id}",
                    },
                )

            pre_repair_track = snapshot.get("pre_repair_track")
            if not isinstance(pre_repair_track, dict):
                return JSONResponse(
                    status_code=400,
                    content={"status": "error", "code": 400, "detail": f"Snapshot '{req.history_id}' does not contain valid pre_repair_track"},
                )

            current, cvat_client = _resolve_track(job_id, track_id, slug=req.slug, allow_snapshot=True)
            if current is None:
                raise HTTPException(404, "Track không còn tồn tại trên CVAT")
            if cvat_client is None and not _is_test_track(job_id, track_id):
                raise HTTPException(503, "Chưa kết nối CVAT để hoàn tác")
            if same_track(current, pre_repair_track):
                return {"status": "ok", "restored_track": current, "already_rolled_back": True,
                        "sync_status": "verified" if cvat_client is not None else "test",
                        "track_etag": compute_track_etag(current), "reload_required": cvat_client is not None}
            if not same_track(current, snapshot["post_repair_track"]):
                raise HTTPException(409, "Track đã thay đổi sau lần sửa; không thể hoàn tác đè lên thay đổi mới")
            if cvat_client is not None and isinstance(pre_repair_track, dict) and "shapes" in pre_repair_track:
                try:
                    pre_repair_track = write_verified_track(cvat_client, job_id, current, pre_repair_track)
                except OCCConflictError as exc:
                    raise HTTPException(409, str(exc)) from exc
                except Exception as exc:
                    raise HTTPException(502, "Không xác nhận được hoàn tác trên CVAT") from exc

            if hasattr(application.state, "mock_tracks"):
                if (job_id, track_id) in application.state.mock_tracks:
                    application.state.mock_tracks[(job_id, track_id)] = pre_repair_track
                if job_id in application.state.mock_tracks and isinstance(application.state.mock_tracks[job_id], dict):
                    tracks = application.state.mock_tracks[job_id].get("tracks", [])
                    for i, t in enumerate(tracks):
                        if t.get("id") == track_id:
                            tracks[i] = pre_repair_track
                            break

            if cvat_client is not None and req.slug:
                link.focus(job_id, {"action": "annotations_changed", "frame": snapshot["frame"], "track_id": track_id},
                           scope=_extension_scope(pm.get_project(req.slug)["cvat_url"]))
            return {
                "status": "ok",
                "restored_track": pre_repair_track,
                "sync_status": "verified" if cvat_client is not None else "test",
                "track_etag": compute_track_etag(pre_repair_track),
                "reload_required": cvat_client is not None,
            }

    # Finding-based repair endpoints
    @application.get("/api/projects/{slug}/scans/{run_id}/findings/{index}/repair")
    def get_finding_repair(slug: str, run_id: str, index: int) -> Any:
        _validate_run_id(run_id)
        try:
            run = runner.get_run(slug, run_id, include_findings=True)
        except ProjectError as exc:
            raise HTTPException(404, str(exc)) from exc
        f = next((f for f in run.get("findings", []) if f["index"] == index), None)
        if f is None:
            raise HTTPException(status_code=404, detail=f"Finding index {index} out of range")
        job_id = int(run.get("job_id", 0))
        track_id = f.get("track_id")
        frame = int(f.get("frame", 0))
        rule = f.get("rule", "floating")
        if track_id is None:
            raise HTTPException(status_code=400, detail="Finding does not belong to a track")

        pts_array = None
        repair_frames = None
        finding_details = dict(f.get("details") or {})
        if "message" not in finding_details and f.get("message"):
            finding_details["message"] = f["message"]

        try:
            proj = pm.get_project(slug)
            run_dir = runner.run_dir(slug, run_id)
            _, box, frames = _finding_box(run_dir, proj, index)
            repair_frames = frames
            pts = frames.frame_data(box.frame).points
            if pts is not None and len(pts) > 0:
                pts_array = pts[:, :3]
        except Exception:
            pass

        return _compute_track_repair(
            job_id=job_id,
            track_id=track_id,
            frame=frame,
            rule=rule,
            slug=slug,
            points=pts_array,
            finding_details=finding_details,
            frame_source=repair_frames,
        )

    @application.post("/api/projects/{slug}/scans/{run_id}/findings/{index}/apply-repair")
    def apply_finding_repair(slug: str, run_id: str, index: int, req: ApplyRepairRequest) -> Any:
        _validate_run_id(run_id)
        try:
            run = runner.get_run(slug, run_id, include_findings=True)
        except ProjectError as exc:
            raise HTTPException(404, str(exc)) from exc
        f = next((f for f in run.get("findings", []) if f["index"] == index), None)
        if f is None:
            raise HTTPException(status_code=404, detail=f"Finding index {index} out of range")
        job_id = int(run.get("job_id", 0))
        track_id = f.get("track_id")
        if track_id is None:
            raise HTTPException(status_code=400, detail="Finding does not belong to a track")
        req.slug = slug
        return apply_track_repair(job_id=job_id, track_id=track_id, req=req)

    @application.post("/api/projects/{slug}/history/{history_id}/rollback")
    def rollback_project_repair(slug: str, history_id: str, job_id: int = 0) -> Any:
        req = RollbackRepairRequest(history_id=history_id, slug=slug)
        history_mgr = getattr(application.state, "history_manager", None) or HistoryManager(home_dir=pm.home_dir)
        try:
            snapshot = history_mgr.get_snapshot(job_id, history_id, slug=slug)
            resolved_job_id = snapshot.get("job_id", job_id)
            track_id = snapshot.get("track_id", 0)
        except Exception:
            raise HTTPException(status_code=404, detail=f"Snapshot {history_id} not found")
        return rollback_track_repair(job_id=resolved_job_id, track_id=track_id, req=req)

    # --- Phục vụ Static Files & Single Page App ---

    if STATIC_DIR.is_dir():
        application.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

        @application.get("/")
        def serve_index() -> FileResponse:
            return FileResponse(STATIC_DIR / "index.html")

    return application


app = create_app()
