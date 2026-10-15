"""Cầu nối giữa giao diện web PointSnap và extension trên trang CVAT (A15).

Web gửi lệnh "mở lỗi này" (`focus`); extension trên tab CVAT đang mở job đó hỏi định kỳ (`poll`), nhận lệnh rồi tự
chuyển frame và làm sáng box mà không tải lại trang. Mỗi lần extension hỏi cũng là một tín hiệu "đang mở job này",
để web biết nên chuyển trong tab CVAT có sẵn hay phải mở link mới. Chỉ giữ trong bộ nhớ: tắt PointSnap là mất, không sao.
"""

from __future__ import annotations

import threading
import time
from typing import Any, Callable

# Extension hỏi mỗi giây; quá ngần này giây không hỏi thì coi như tab CVAT đã đóng.
ONLINE_SECONDS = 4.0


class ExtensionLink:
    def __init__(self, clock: Callable[[], float] = time.monotonic) -> None:
        self._clock = clock
        self._lock = threading.Lock()
        self._seq = 0
        self._commands: dict[tuple[str, int], dict[str, Any]] = {}
        self._seen: dict[tuple[str, int], float] = {}
        self._reviews_rev = 0
        # Sửa / hoàn tác box (1-Click Apply, Rollback) từ web hoặc extension: số phiên bản chung và sự kiện mới nhất
        # của từng job, để phía bên kia cập nhật ngay (không F5) mà không cần đọc lại toàn bộ lịch sử.
        self._history_rev = 0
        self._history: dict[tuple[str, int], dict[str, Any]] = {}

    def _online(self, job_id: int, scope: str = "") -> bool:
        seen = self._seen.get((scope, job_id))
        return seen is not None and self._clock() - seen <= ONLINE_SECONDS

    def focus(self, job_id: int, command: dict[str, Any], *, scope: str = "") -> dict[str, Any]:
        """Ghi lệnh mới nhất cho job; trả về số thứ tự và việc có extension nào đang mở job đó không."""
        with self._lock:
            self._seq += 1
            self._commands[(scope, job_id)] = {**command, "job_id": job_id, "seq": self._seq}
            return {"seq": self._seq, "extension_online": self._online(job_id, scope)}

    def poll(self, job_id: int, after: int, *, scope: str = "") -> dict[str, Any]:
        """Extension hỏi lệnh mới hơn `after`. `after < 0` (vừa mở trang): chỉ lấy số thứ tự hiện tại, không chạy lệnh cũ."""
        with self._lock:
            self._seen[(scope, job_id)] = self._clock()
            command = self._commands.get((scope, job_id))
            fresh = after >= 0 and command is not None and command["seq"] > after
            return {"seq": self._seq, "command": command if fresh else None, "reviews_rev": self._reviews_rev,
                    "history_rev": self._history_rev, "history_event": self._history.get((scope, job_id))}

    def status(self, job_id: int, *, scope: str = "") -> dict[str, Any]:
        with self._lock:
            return {"extension_online": self._online(job_id, scope), "reviews_rev": self._reviews_rev,
                    "history_rev": self._history_rev, "history_event": self._history.get((scope, job_id))}

    @property
    def reviews_rev(self) -> int:
        with self._lock:
            return self._reviews_rev

    @property
    def history_rev(self) -> int:
        with self._lock:
            return self._history_rev

    def bump_history(self, job_id: int, event: dict[str, Any], *, scope: str = "") -> int:
        """Box của job vừa được sửa / hoàn tác: ghi sự kiện mới nhất của job và tăng số phiên bản lịch sử."""
        with self._lock:
            self._history_rev += 1
            self._history[(scope, job_id)] = {**event, "job_id": job_id, "rev": self._history_rev}
            return self._history_rev

    def bump_reviews(self) -> int:
        """Có kết luận xem tay mới (từ web hoặc extension): tăng số phiên bản để phía bên kia đọc lại."""
        with self._lock:
            self._reviews_rev += 1
            return self._reviews_rev
