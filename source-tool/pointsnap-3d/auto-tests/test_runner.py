"""Kiểm runner: thất bại không bị báo đạt và skip không bị tính là pass."""
import importlib.util
from pathlib import Path

SCRIPT = Path(__file__).resolve().with_name('run.py')


def runner():
    spec = importlib.util.spec_from_file_location('auto_test', SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_junit_reports_failure_and_skip(tmp_path):
    xml = tmp_path / 'result.xml'
    xml.write_text('<testsuites><testsuite><testcase name="ok"/>'
                   '<testcase name="bad"><failure message="wrong"/></testcase>'
                   '<testcase name="missing"><skipped message="no data"/></testcase>'
                   '</testsuite></testsuites>')
    assert [r['status'] for r in runner().junit_cases(xml)] == ['PASS', 'FAIL', 'SKIP']


def test_command_failure_and_timeout_are_reported(tmp_path):
    import os
    import sys
    module = runner()
    assert module.run_command('failure', [sys.executable, '-c', 'raise SystemExit(4)'],
                              tmp_path, dict(os.environ), tmp_path / 'fail.log', 10)['status'] == 'FAIL'
    assert module.run_command('timeout', [sys.executable, '-c', 'import time; time.sleep(10)'],
                              tmp_path, dict(os.environ), tmp_path / 'timeout.log', 0.1)['status'] == 'FAIL'


def test_report_marks_skipped_and_does_not_publish_token(tmp_path):
    module = runner()
    module.write_report(tmp_path, [{'name': 'one', 'status': 'PASS'},
                                   {'name': 'two', 'status': 'SKIP'}])
    report = (tmp_path / 'report.md').read_text(encoding='utf-8')
    assert 'PASS: 1' in report and 'SKIP: 1' in report
    assert (tmp_path / 'results.json').is_file()


def test_online_checks_are_read_only_and_reject_missing_cloud(tmp_path, monkeypatch):
    from types import SimpleNamespace
    import requests
    calls = []

    class Session:
        def get(self, url, headers=None, timeout=None):
            calls.append((url, headers))
            status = 200
            if '/report' in url and (not headers or headers.get('Authorization') != 'Bearer secret'):
                status = 401
            fmt = url.split('format=')[-1]
            mime = {'json': 'application/json', 'html': 'text/html', 'csv': 'text/csv'}.get(fmt, 'text/html')
            return SimpleNamespace(status_code=status, text='PointSnap', content=b'body',
                                   headers={'Content-Type': mime},
                                   json=lambda: dict(version='2.78', status='ok', job_id=1,
                                                     findings=[], point_cloud_available=False))

        def close(self):
            pass

    monkeypatch.setattr(requests, 'Session', Session)
    rows = runner().service_checks(SimpleNamespace(cvat_url='http://localhost:8080',
                                                   web_url='http://127.0.0.1:8765', job=1),
                                  {'CVAT_TOKEN': 'secret'}, tmp_path)
    assert next(r for r in rows if r['name'] == 'Authenticated report json')['status'] == 'FAIL'
    assert len(calls) == 8
    assert 'secret' not in str(rows)
    assert all(not headers for url, headers in calls if url.startswith('http://127.0.0.1:8765'))


def test_checklist_failed_skipped_and_absent_tests_do_not_pass():
    module = runner()
    mapping = {'A01': [['one'], 'UI'], 'A02': [['two'], 'UI'],
               'A03': [['missing'], 'UI'], 'B12': [[], 'Human reference']}
    cases = module.checklist_cases([{'name': 'tests.demo::one', 'status': 'FAIL'},
                                    {'name': 'tests.demo::two', 'status': 'SKIP'}], mapping)
    assert [c['code_status'] for c in cases] == ['FAIL', 'NOT_RUN', 'NOT_RUN', 'MANUAL']
    assert all(c['full_checklist_passed'] is False for c in cases)


def test_checklist_mapping_has_every_documented_case():
    import json
    import re
    module = runner()
    mapping = json.loads((SCRIPT.parent / 'checklist-map.json').read_text(encoding='utf-8'))
    document = (module.ROOT / 'docs/checklist-test-thu-cong.md').read_text(encoding='utf-8')
    assert set(mapping) == set(re.findall(r'^\| ([A-F][0-9]{2}) \|', document, re.M))
    cases = module.checklist_cases([{'name': 'tests.demo::one', 'status': 'PASS'}],
                                  {'A01': [['one'], 'UI not checked']})
    assert cases[0]['code_status'] == 'PASS' and not cases[0]['full_checklist_passed']

