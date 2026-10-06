"""Gọi REST API của CVAT 2.x — chỉ các endpoint tool cần.

Endpoint và tên trường theo mã nguồn CVAT 2.77.1 (`cvat/apps/engine/serializers.py`, `views.py`,
`cvat/apps/redis_handler`). Xác thực:
- `Bearer <token>`: Personal Access Token tạo trong giao diện CVAT (mặc định);
- `Token <key>`: token cũ lấy từ `/api/auth/login`.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

import requests


ACCEPT = "application/vnd.cvat+json; version=2.0"


class CvatError(RuntimeError):
    """CVAT trả lỗi hoặc không phản hồi như mong đợi."""


class CvatClient:
    def __init__(
        self,
        url: str,
        token: str | None,
        auth_scheme: str = "Bearer",
        timeout: float = 60.0,
        session: requests.Session | None = None,
    ) -> None:
        if not token:
            raise CvatError("Thiếu token CVAT: đặt biến môi trường CVAT_TOKEN")
        self.url = url.rstrip("/")
        self.timeout = timeout
        self.session = session or requests.Session()
        # CVAT chỉ trả JSON với media type riêng (CVATAPIRenderer); "application/json" bị từ chối với HTTP 406.
        self.session.headers.update({"Authorization": f"{auth_scheme} {token}", "Accept": ACCEPT})

    def _request(self, method: str, path: str, *, expected: tuple[int, ...] = (200,), **kwargs: Any) -> Any:
        url = path if path.startswith("http") else f"{self.url}/api/{path.lstrip('/')}"
        try:
            response = self.session.request(method, url, timeout=self.timeout, **kwargs)
        except requests.RequestException as exc:
            raise CvatError(f"Không kết nối được CVAT tại {self.url}: {exc}") from exc
        if response.status_code not in expected:
            raise CvatError(f"{method} {url} → HTTP {response.status_code}: {response.text[:500]}")
        return response.json() if response.content else {}

    def _get_all(self, path: str, params: dict[str, Any]) -> list[dict[str, Any]]:
        """GET một danh sách có phân trang, gom mọi trang."""
        results: list[dict[str, Any]] = []
        page = self._request("GET", path, params={**params, "page_size": 500})
        while True:
            results.extend(page.get("results", []))
            if not page.get("next"):
                return results
            page = self._request("GET", page["next"])

    # --- Thông tin máy chủ ------------------------------------------------------------------------

    def server_version(self) -> str:
        return str(self._request("GET", "server/about").get("version", ""))

    # --- Task ------------------------------------------------------------------------------------

    def create_task(self, name: str, labels: list[dict[str, Any]]) -> dict[str, Any]:
        return self._request("POST", "tasks", json={"name": name, "labels": labels}, expected=(201,))

    def upload_task_data(self, task_id: int, archive: str | Path, image_quality: int = 70) -> str:
        """Tải file zip chứa các `.pcd` lên task; trả về `rq_id` để theo dõi."""
        archive = Path(archive)
        with archive.open("rb") as f:
            result = self._request(
                "POST",
                f"tasks/{task_id}/data",
                files={"client_files[0]": (archive.name, f, "application/zip")},
                data={"image_quality": image_quality, "sorting_method": "lexicographical"},
                expected=(202,),
            )
        rq_id = result.get("rq_id")
        if not rq_id:
            raise CvatError(f"CVAT không trả rq_id khi tải dữ liệu cho task {task_id}: {result}")
        return rq_id

    def wait_request(self, rq_id: str, timeout: float = 900.0, poll_interval: float = 2.0) -> dict[str, Any]:
        """Chờ một tác vụ nền (`/api/requests/<rq_id>`) xong; báo lỗi nếu thất bại hoặc quá giờ."""
        deadline = time.monotonic() + timeout
        while True:
            status = self._request("GET", f"requests/{rq_id}")
            state = status.get("status")
            if state == "finished":
                return status
            if state == "failed":
                raise CvatError(f"Tác vụ {rq_id} thất bại: {status.get('message', '')}")
            if time.monotonic() > deadline:
                raise CvatError(f"Tác vụ {rq_id} chưa xong sau {timeout:.0f} giây (trạng thái: {state})")
            time.sleep(poll_interval)

    def task_labels(self, task_id: int) -> list[dict[str, Any]]:
        return self._get_all("labels", {"task_id": task_id})

    def task_jobs(self, task_id: int) -> list[dict[str, Any]]:
        return self._get_all("jobs", {"task_id": task_id})

    def get_task(self, task_id: int) -> dict[str, Any]:
        return self._request("GET", f"tasks/{task_id}")

    def get_task_data_meta(self, task_id: int) -> dict[str, Any]:
        """Danh sách frame của task (`frames[].name`) theo đúng thứ tự frame."""
        return self._request("GET", f"tasks/{task_id}/data/meta")

    def delete_task(self, task_id: int) -> None:
        self._request("DELETE", f"tasks/{task_id}", expected=(204,))

    # --- Job -------------------------------------------------------------------------------------

    def get_job(self, job_id: int) -> dict[str, Any]:
        return self._request("GET", f"jobs/{job_id}")

    def get_job_annotations(self, job_id: int) -> dict[str, Any]:
        return self._request("GET", f"jobs/{job_id}/annotations")

    # --- Annotation ------------------------------------------------------------------------------

    def get_task_annotations(self, task_id: int) -> dict[str, Any]:
        return self._request("GET", f"tasks/{task_id}/annotations")

    def put_task_annotations(self, task_id: int, data: dict[str, Any]) -> dict[str, Any]:
        """Thay toàn bộ annotation của task (chỉ dùng khi nạp nhãn chuẩn vào task mới)."""
        return self._request("PUT", f"tasks/{task_id}/annotations", json=data)

    def patch_job_annotations(
        self, job_id: int, data: dict[str, Any], action: str = "update"
    ) -> dict[str, Any]:
        """Cập nhật một phần annotations của job qua endpoint PATCH /api/jobs/<id>/annotations?action=<action>."""
        return self._request(
            "PATCH",
            f"jobs/{job_id}/annotations",
            params={"action": action},
            json=data,
            expected=(200,),
        )
