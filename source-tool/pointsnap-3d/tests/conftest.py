import pytest


@pytest.fixture(autouse=True)
def _isolated_cwd(tmp_path, monkeypatch):
    """Chạy mỗi test trong thư mục tạm, để file `.env` thật của người dùng không lọt vào test."""
    monkeypatch.chdir(tmp_path)
