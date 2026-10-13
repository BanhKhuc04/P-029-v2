from unittest.mock import Mock
import pytest
from pointsnap.web.projects import ProjectManager
from pointsnap.web.runner import ScanRunner


@pytest.mark.parametrize('flag', [False, True])
def test_queued_scan_cannot_follow_a_changed_cvat_destination(tmp_path, monkeypatch, flag):
    pm = ProjectManager(tmp_path)
    pm.create_project('a', cvat_url='http://cvat-a.test', cvat_token='fake-a')
    runner = ScanRunner(pm)
    monkeypatch.setattr(runner._executor, 'submit', Mock())
    client_factory = Mock(side_effect=RuntimeError('Must not reach a CVAT server'))
    monkeypatch.setattr('pointsnap.web.runner.CvatClient', client_factory)
    try:
        run_id = runner.start_scan('a', 7, flag)
        pm.update_project('a', {'cvat_url': 'http://cvat-b.test', 'cvat_token': 'fake-b'})
        runner._execute_scan(run_id, 'a', 7, flag)
        client_factory.assert_not_called()
        result = runner.get_run('a', run_id)
        assert result['status'] == 'failed' and 'CVAT' in result['error']
    finally:
        runner._executor.shutdown()
