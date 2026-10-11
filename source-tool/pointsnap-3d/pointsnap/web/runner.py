"""Quản lý các tác vụ quét nền của PointSnap 3D (A11)."""

from __future__ import annotations

import datetime
import json
import logging
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

from pointsnap.adapters.cvat.client import CvatClient
from pointsnap.adapters.cvat.reader import frame_url, load_job
from pointsnap.adapters.cvat.writer import flag_job_errors, save_snapshot
from pointsnap.cli.common import frames_for_job
from pointsnap.core.gate import gate_verdict
from pointsnap.core.model import Finding, Severity
from pointsnap.core.scanner import actionable, scan_coverage_gaps, scan_cuboids
from pointsnap.report.csv_rep import generate_csv_report
from pointsnap.report.html import generate_html_report
from pointsnap.web.projects import ProjectError, ProjectManager

logger = logging.getLogger(__name__)


def finding_to_dict(
    f: Finding,
    cvat_url: str = "",
    task_id: int | None = None,
    job_id: int | None = None,
) -> dict[str, Any]:
    link = ""
    if cvat_url and task_id is not None and job_id is not None:
        link = frame_url(
            cvat_url,
            task_id,
            job_id,
            f.frame,
            track_id=f.track_id,
            shape_id=f.source_id if f.track_id is None else None,
        )
    return {
        "error_type": f.error_type.value,
        "error_type_label": f.error_type.label_vi,
        "rule": f.rule,
        "severity": f.severity.value,
        "severity_label": f.severity.label_vi,
        "frame": f.frame,
        "label": f.label,
        "message": f.message,
        "track_id": f.track_id,
        "source_id": f.source_id,
        "value": f.value,
        "threshold": f.threshold,
        "cvat_link": link,
    }


class ScanRunner:
    def __init__(self, project_manager: ProjectManager, max_workers: int = 1) -> None:
        self.pm = project_manager
        self._executor = ThreadPoolExecutor(max_workers=max_workers)
        self._scans: dict[str, dict[str, Any]] = {}

    def start_scan(self, slug: str, job_id: int, flag: bool = False) -> str:
        """Bắt đầu quét một job trong luồng nền. Trả về `run_id`."""
        self.pm.get_project(slug)  # kiểm tra dự án tồn tại
        now = datetime.datetime.now()
        # Điểm nhỏ 4: thêm millisecond để tránh run_id trùng khi bấm 2 lần trong 1 giây
        now_str = now.strftime("%Y%m%d-%H%M%S")
        ms = now.microsecond // 1000
        run_id = f"{now_str}-{ms:03d}-job{job_id}"

        run_info: dict[str, Any] = {
            "run_id": run_id,
            "project_slug": slug,
            "job_id": job_id,
            "flag": flag,
            "status": "queued",
            "progress": 0,
            "message": "Đang xếp hàng đợi...",
            "started_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "finished_at": None,
            "error": None,
            "summary": None,
        }
        self._scans[run_id] = run_info

        self._executor.submit(self._execute_scan, run_id, slug, job_id, flag)
        return run_id

    def _execute_scan(self, run_id: str, slug: str, job_id: int, flag: bool) -> None:
        info = self._scans[run_id]
        info["status"] = "running"
        info["progress"] = 5
        info["message"] = "Đang nạp cấu hình và kết nối CVAT..."

        try:
            config = self.pm.get_effective_config(slug)
            proj = self.pm.get_project(slug)

            client = CvatClient(config.cvat.url, config.cvat.token)
            info["progress"] = 20
            info["message"] = f"Đang tải dữ liệu job #{job_id} từ CVAT ({client.url})..."

            job = load_job(client, job_id)

            run_dir = self.pm._project_dir(slug) / "runs" / run_id
            run_dir.mkdir(parents=True, exist_ok=True)

            # 1. Lưu snapshot
            info["progress"] = 35
            info["message"] = "Đang lưu bản chụp nhãn..."
            save_snapshot(job, run_dir / "snapshot.json")

            # 2. Tìm point cloud (Điểm 3 Mục 6: truyền trực tiếp export_dirs và dataroot, không qua os.environ)
            info["progress"] = 50
            info["message"] = "Đang kiểm tra dữ liệu point cloud..."
            custom_exports = proj.get("export_dirs") or None
            custom_nuscenes = proj.get("nuscenes_root") or None
            frames, note = frames_for_job(
                job,
                custom_export_dirs=custom_exports,
                dataroot=custom_nuscenes,
            )

            # 3. Quét kiểm tra chất lượng nhãn
            info["progress"] = 65
            info["message"] = f"Đang quét {len(job.cuboids)} box của job #{job_id}..."
            findings = scan_cuboids(job, config, frames)

            # 4. Xuất báo cáo HTML / CSV
            info["progress"] = 80
            info["message"] = "Đang tạo báo cáo HTML và CSV..."
            generate_html_report(job, findings, run_dir / "report.html")
            generate_csv_report(job, findings, run_dir / "report.csv")

            # 5. Đánh giá Gate
            coverage_gaps = scan_coverage_gaps(job, config, frames)
            passed, reasons = gate_verdict(findings, config.gate, coverage_gaps=coverage_gaps)

            # 6. Gắn cờ lỗi lên CVAT nếu được yêu cầu
            flag_summary: dict[str, int] | None = None
            if flag:
                info["progress"] = 90
                info["message"] = "Đang gắn cờ lỗi trực tiếp lên CVAT..."
                act = actionable(findings)
                f_res = flag_job_errors(
                    client, job, act, flag_attribute=config.cvat.flag_attribute
                )
                flag_summary = {
                    "flagged": f_res.flagged,
                    "cleared": f_res.cleared,
                    "unmatched": f_res.unmatched,
                }

            # 7. Ghi findings.json
            findings_dicts = [
                finding_to_dict(
                    f,
                    cvat_url=config.cvat.url,
                    task_id=job.task_id,
                    job_id=job.job_id,
                )
                for f in findings
            ]
            (run_dir / "findings.json").write_text(
                json.dumps(findings_dicts, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

            # 8. Ghi summary.json
            counts = {
                s.value: sum(1 for f in findings if f.severity is s) for s in Severity
            }
            summary = {
                "run_id": run_id,
                "project_slug": slug,
                "job_id": job_id,
                "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                "num_boxes": sum(1 for c in job.cuboids if not c.outside),
                "num_errors": counts["error"],
                "num_warnings": counts["warning"],
                "num_info": counts["info"],
                "gate_passed": passed,
                "gate_reasons": reasons,
                "coverage_gaps": coverage_gaps,
                "flagged": flag,
                "flag_summary": flag_summary,
                "note": note,
            }
            (run_dir / "summary.json").write_text(
                json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
            )

            info["status"] = "done"
            info["progress"] = 100
            info["message"] = "Hoàn tất."
            info["summary"] = summary
            info["finished_at"] = datetime.datetime.now(
                datetime.timezone.utc
            ).isoformat()

        except Exception as exc:
            logger.exception("Lỗi khi quét job %s", job_id)
            info["status"] = "failed"
            info["progress"] = 100
            info["message"] = f"Lỗi: {exc}"
            info["error"] = str(exc)
            info["finished_at"] = datetime.datetime.now(
                datetime.timezone.utc
            ).isoformat()

    def get_run(
        self, slug: str, run_id: str, include_findings: bool = False
    ) -> dict[str, Any]:
        """Lấy trạng thái chi tiết của một lần quét."""
        # 1. Đang chạy trong memory
        if run_id in self._scans:
            run_data = dict(self._scans[run_id])
            if include_findings and run_data.get("status") == "done":
                run_dir = self.pm._project_dir(slug) / "runs" / run_id
                f_path = run_dir / "findings.json"
                if f_path.is_file():
                    run_data["findings"] = json.loads(f_path.read_text(encoding="utf-8"))
            return run_data

        # 2. Đọc từ ổ đĩa
        run_dir = self.pm._project_dir(slug) / "runs" / run_id
        sum_file = run_dir / "summary.json"
        if not sum_file.is_file():
            raise ProjectError(f"Không tìm thấy lần quét '{run_id}'")

        summary = json.loads(sum_file.read_text(encoding="utf-8"))
        res: dict[str, Any] = {
            "run_id": run_id,
            "project_slug": slug,
            "job_id": summary.get("job_id"),
            "status": "done",
            "progress": 100,
            "message": "Hoàn tất.",
            "started_at": summary.get("timestamp"),
            "finished_at": summary.get("timestamp"),
            "error": None,
            "summary": summary,
        }
        if include_findings:
            f_path = run_dir / "findings.json"
            if f_path.is_file():
                res["findings"] = json.loads(f_path.read_text(encoding="utf-8"))
        return res

    def list_runs(self, slug: str) -> list[dict[str, Any]]:
        """Lấy danh sách tóm tắt các lần quét của dự án (sắp xếp mới nhất trước)."""
        runs_dir = self.pm._project_dir(slug) / "runs"
        results: list[dict[str, Any]] = []
        seen_runs = set()

        # Đang active trong bộ nhớ
        for r_id, r_info in self._scans.items():
            if r_info.get("project_slug") == slug:
                results.append(dict(r_info))
                seen_runs.add(r_id)

        # Đọc từ file
        if runs_dir.is_dir():
            for d in runs_dir.iterdir():
                if d.is_dir() and d.name not in seen_runs:
                    sum_file = d / "summary.json"
                    if sum_file.is_file():
                        try:
                            s = json.loads(sum_file.read_text(encoding="utf-8"))
                            results.append(
                                {
                                    "run_id": d.name,
                                    "project_slug": slug,
                                    "job_id": s.get("job_id"),
                                    "status": "done",
                                    "progress": 100,
                                    "message": "Hoàn tất.",
                                    "started_at": s.get("timestamp"),
                                    "finished_at": s.get("timestamp"),
                                    "summary": s,
                                }
                            )
                        except Exception:
                            continue

        return sorted(results, key=lambda r: r.get("started_at") or "", reverse=True)
