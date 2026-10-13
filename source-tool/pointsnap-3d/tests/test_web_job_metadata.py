"""Keep CVAT job frame metadata available to the Web job picker."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from pointsnap.web.app import create_app
from pointsnap.web.projects import ProjectManager


@pytest.mark.parametrize("frame_count", [40, None])
def test_task_picker_preserves_frame_count_and_range(tmp_path: Path, monkeypatch, frame_count):
    ProjectManager(tmp_path).create_project(
        name="Job picker", slug="job-picker", cvat_token="test-only-pat"
    )
    closed = []

    class FakeSession:
        def close(self):
            closed.append(True)

    class FakeCvatClient:
        def __init__(self, url, token, timeout):
            self.session = FakeSession()

        def get_tasks(self):
            return [{"id": 4, "name": "Task 4"}]

        def task_jobs(self, task_id):
            assert task_id == 4
            return [{
                "id": 4, "status": "annotation", "stage": "annotation",
                "start_frame": 10, "stop_frame": 49, "frame_count": frame_count,
                "assignee": {"email": "private@example.test"},
            }]

    monkeypatch.setattr("pointsnap.web.app.CvatClient", FakeCvatClient)
    with TestClient(create_app(home_dir=tmp_path)) as client:
        response = client.get("/api/projects/job-picker/cvat/tasks")

    assert response.status_code == 200
    assert response.json()["tasks"][0]["jobs"] == [{
        "id": 4, "status": "annotation", "stage": "annotation",
        "start_frame": 10, "stop_frame": 49, "frame_count": frame_count,
    }]
    assert "test-only-pat" not in response.text
    assert "private@example.test" not in response.text
    assert closed == [True]
