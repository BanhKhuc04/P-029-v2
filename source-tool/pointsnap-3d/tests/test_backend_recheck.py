from unittest.mock import Mock
import pytest
from pointsnap.api import ReportCvatClient,ReportCvatError
from pointsnap.web.storage import StorageError,read_json


@pytest.mark.parametrize('literal', ['1e999', '-1e999', 'NaN', 'Infinity'])
def test_storage_rejects_nested_nonfinite_numbers(tmp_path, literal):
    path = tmp_path / 'run.json'
    path.write_text('{"nested":{"count":' + literal + '}}', encoding='utf-8')
    with pytest.raises(StorageError):
        read_json(path)


def test_storage_keeps_finite_exponents(tmp_path):
    path = tmp_path / 'run.json'
    path.write_text('{"count":1e300}', encoding='utf-8')
    assert read_json(path)['count'] == 1e300


@pytest.mark.parametrize('next_url', ['/api/labels?page=2', 'labels?page=2'])
def test_report_client_resolves_relative_pagination_inside_api(next_url):
    session = Mock()
    response = Mock(status_code=200, content=b'x')
    response.json.return_value = {'results': [], 'next': None}
    session.request.return_value = response
    client = ReportCvatClient('http://cvat-a.test', 'fake-token', session=session)
    client._request('GET', next_url)
    assert session.request.call_args.args[1] == 'http://cvat-a.test/api/labels?page=2'


def test_report_client_rejects_foreign_pagination_before_request():
    session = Mock()
    client = ReportCvatClient('http://cvat-a.test', 'fake-token', session=session)
    with pytest.raises(ReportCvatError):
        client._request('GET', 'http://cvat-b.test/api/labels?page=2')
    session.request.assert_not_called()
