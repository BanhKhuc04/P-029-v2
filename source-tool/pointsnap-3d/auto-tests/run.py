"""Run existing tests and optional read-only local service checks; emit an honest report."""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import uuid
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]


def junit_cases(path):
    if not path.is_file():
        return []
    cases = []
    for case in ET.parse(path).iter('testcase'):
        problem = next((c for c in case if c.tag in ('failure', 'error', 'skipped')), None)
        status = 'PASS' if problem is None else ('SKIP' if problem.tag == 'skipped' else 'FAIL')
        cases.append({'name': case.get('classname', '') + '::' + case.get('name', ''),
                      'status': status, 'detail': problem.get('message', '') if problem is not None else ''})
    return cases


def run_command(name, command, cwd, env, log, timeout=600):
    started = time.monotonic()
    try:
        with log.open('w', encoding='utf-8') as stream:
            result = subprocess.run(command, cwd=cwd, env=env, stdout=stream,
                                    stderr=subprocess.STDOUT, timeout=timeout)
        status = 'PASS' if result.returncode == 0 else 'FAIL'
        detail = f'exit={result.returncode}; log={log.name}'
    except (OSError, subprocess.TimeoutExpired) as exc:
        status, detail = 'FAIL', f'{type(exc).__name__}; log={log.name}'
    print(f'{status}: {name}', flush=True)
    return {'name': name, 'status': status, 'detail': detail,
            'seconds': round(time.monotonic() - started, 2)}


def write_report(out, results):
    counts = Counter(r['status'] for r in results)
    text = ['# PointSnap automatic test report', '',
            f"PASS: {counts['PASS']} | FAIL: {counts['FAIL']} | SKIP: {counts['SKIP']}", '',
            'Includes individual pytest cases and separate service/command checks.',
            'Skipped checks are not verified. Code tests do not prove precision on real scenes.', '',
            '| Check | Result | Detail |', '|---|---|---|']
    for row in results:
        detail = str(row.get('detail', '')).replace('|', '/').replace('\n', ' ')[:500]
        text.append(f"| {row['name'].replace('|', '/')} | {row['status']} | {detail} |")
    text += ['', 'Not covered: browser rendering/interaction, actual installed extension behavior,',
             'camera alignment, human confirmation of false positives and missed labels.']
    (out / 'report.md').write_text('\n'.join(text) + '\n', encoding='utf-8')
    (out / 'results.json').write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding='utf-8')
    write_checklist_report(out, results)


def checklist_cases(results, mapping):
    """Link observed results to code portions; never declare a whole manual case passed."""
    cases = []
    for case_id, (selectors, remaining) in mapping.items():
        matches, missing = [], []
        for selector in selectors:
            selected = [r for r in results if r['name'] == selector or
                        r['name'].split('::')[-1].split('[')[0] == selector]
            if not selected:
                missing.append(selector)
            matches.extend(selected)
        if not selectors:
            status = 'MANUAL'
        elif any(r['status'] == 'FAIL' for r in matches):
            status = 'FAIL'
        elif missing or any(r['status'] != 'PASS' for r in matches):
            status = 'NOT_RUN'
        else:
            status = 'PASS'
        cases.append({'id': case_id, 'code_status': status, 'full_checklist_passed': False,
                      'evidence': matches, 'missing_tests': missing, 'remaining': remaining})
    return cases


def write_checklist_report(out, results):
    import re
    mapping = json.loads((ROOT / 'auto-tests/checklist-map.json').read_text(encoding='utf-8'))
    document = (ROOT / 'docs/checklist-test-thu-cong.md').read_text(encoding='utf-8')
    titles = dict(re.findall(r'^\| ([A-F][0-9]{2}) \| (.*?) \|', document, re.M))
    if set(titles) != set(mapping):
        raise ValueError('Checklist changed: update auto-tests/checklist-map.json')
    cases = checklist_cases(results, mapping)
    counts = Counter(c['code_status'] for c in cases)
    text = ['# Review tự động theo checklist A01–F04', '',
            'Nguồn: docs/checklist-test-thu-cong.md. Bằng chứng: results.json cùng thư mục.', '',
            f"Phần code: PASS {counts['PASS']} / FAIL {counts['FAIL']} / NOT_RUN {counts['NOT_RUN']} / MANUAL {counts['MANUAL']}.", '',
            '**PASS chỉ nói các test ánh xạ cho phần code đã đạt. Không có nghĩa toàn bộ ca thủ công đã đạt.**',
            'MANUAL = chưa có test phù hợp; NOT_RUN = thiếu bằng chứng hoặc có test bị skip.',
            'Không tự đánh dấu cảnh báo thật/báo nhầm và không ghi reviews.json lên dự án.', '',
            '| Mã | Nội dung checklist | Phần code | Bằng chứng | Phần còn lại |', '|---|---|---|---|---|']
    for case in cases:
        evidence = '<br>'.join(f"{r['name']} ({r['status']})" for r in case['evidence']) or '—'
        if case['missing_tests']:
            evidence += '<br>Chưa có kết quả: ' + ', '.join(case['missing_tests'])
        cells = [case['id'], titles[case['id']], case['code_status'], evidence, case['remaining']]
        text.append('| ' + ' | '.join(cell.replace('|', '/') for cell in cells) + ' |')
    text += ['', '## Vấn đề đã thấy từ code', '',
             '- B02: web đang dùng cùng gợi ý `Hạ đáy box...` cho luật floating, kể cả box lún.',
             '  Đây là phát hiện từ đọc code; bảng test thuật toán đạt không xóa vấn đề hướng dẫn này.',
             '- B12/F03: cần nhãn tham chiếu hoặc lỗi chèn có đáp án để đo bỏ sót/precision. Không dùng',
             '  chính finding của tool làm đáp án đúng cho tool.',
             '- C09: kết luận Báo nhầm không tự loại finding khỏi gate.', '',
             'Bảng này không chấm nhãn thực tế trên CVAT; kiểm thử thuật toán đang dùng dữ liệu tổng hợp/đáp án đã biết.']
    (out / 'checklist-review.md').write_text('\n'.join(text) + '\n', encoding='utf-8')
    (out / 'checklist-review.json').write_text(json.dumps(cases, ensure_ascii=False, indent=2), encoding='utf-8')


def service_checks(args, env, out):
    import requests
    rows = []
    session = requests.Session()
    session.trust_env = False

    def check(name, action):
        try:
            detail = action()
            rows.append({'name': name, 'status': 'PASS', 'detail': detail or ''})
        except Exception as exc:
            # Never serialize request headers, responses or credentials into error messages.
            rows.append({'name': name, 'status': 'FAIL', 'detail': type(exc).__name__})

    def get(base, path, headers=None, expected=200):
        response = session.get(base.rstrip('/') + path, headers=headers, timeout=150)
        assert response.status_code == expected, f'HTTP {response.status_code}'
        return response

    cvat, web = args.cvat_url, args.web_url
    token = env.get('CVAT_TOKEN', '')
    headers = {'Authorization': 'Bearer ' + token}
    check('CVAT server', lambda: get(cvat, '/api/server/about').json()['version'])
    def web_page():
        assert 'PointSnap' in get(web, '/').text
        return 'HTTP 200; PointSnap page present'

    def health():
        assert get(cvat, '/pointsnap/health').json()['status'] == 'ok'
        return 'HTTP 200; status=ok'

    check('PointSnap web', web_page)
    check('Report API health', health)
    path = f'/pointsnap/jobs/{args.job}/report'
    check('Report API rejects anonymous request', lambda: str(get(cvat, path, expected=401).status_code))
    check('Report API rejects invalid token', lambda: str(get(cvat, path, {'Authorization': 'Bearer invalid-test-token'}, 401).status_code))
    if token:
        for fmt in ('json', 'html', 'csv'):
            def report(fmt=fmt):
                response = get(cvat, path + '?format=' + fmt, headers)
                expected_type = {'json': 'application/json', 'html': 'text/html', 'csv': 'text/csv'}[fmt]
                assert expected_type in response.headers.get('Content-Type', '')
                assert response.content
                if fmt == 'json':
                    data = response.json()
                    assert data['job_id'] == args.job and isinstance(data['findings'], list)
                    assert data['point_cloud_available'], 'Point cloud unavailable: incomplete scan'
                (out / f'job-{args.job}.{fmt}').write_bytes(response.content)
                return f'HTTP 200; {len(response.content)} bytes; GET-only (no geometry comparison)'
            check('Authenticated report ' + fmt, report)
    else:
        rows.append({'name': 'Authenticated reports', 'status': 'SKIP', 'detail': 'CVAT_TOKEN missing'})
    session.close()
    return rows


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--online', action='store_true', help='GET-only checks of running CVAT/web/report API')
    parser.add_argument('--job', type=int, default=1)
    parser.add_argument('--live-cvat', action='store_true', help='Existing tests create, flag and DELETE their own temporary tasks')
    parser.add_argument('--dataset', type=Path, help='Run real nuScenes reader tests against this directory')
    parser.add_argument('--node', default=shutil.which('node'))
    parser.add_argument('--cvat-url', default='http://localhost:8080')
    parser.add_argument('--web-url', default='http://127.0.0.1:8765')
    args = parser.parse_args(argv)
    if args.job < 1:
        parser.error('--job must be positive')
    from pointsnap.cli.main import load_dotenv
    load_dotenv(ROOT / '.env')
    live_env = dict(os.environ)
    live_env['CVAT_URL'] = args.cvat_url
    live_env['PYTHONIOENCODING'] = 'utf-8'
    clean_env = {k: v for k, v in live_env.items() if not k.startswith(('CVAT_', 'NUSCENES_', 'POINTSNAP_'))}
    # Existing tests expect dataset/token environment to be absent in isolated cases.
    clean_env['POINTSNAP_LIVE_CVAT'] = '0'
    library_paths = [p for p in sys.path if Path(p).name == 'site-packages']
    clean_env['PYTHONPATH'] = os.pathsep.join([str(ROOT), *library_paths])
    live_env['PYTHONPATH'] = clean_env['PYTHONPATH']
    out = ROOT / 'out' / 'auto-tests' / datetime.now().strftime('%Y%m%d-%H%M%S-%f')
    out.mkdir(parents=True)
    clean_env['POINTSNAP_HOME'] = str(out / 'home')
    rows = []

    def pytest_phase(name, targets, env):
        xml = out / f'{name}.xml'
        temporary = ROOT / 'out' / ('t-' + uuid.uuid4().hex[:8])
        command = [sys.executable, '-m', 'pytest', '-q', '-p', 'no:cacheprovider', *targets,
                   f'--junitxml={xml}', f'--basetemp={temporary}']
        result = run_command(name, command, ROOT, env, out / f'{name}.log')
        cases = junit_cases(xml)
        rows.extend(cases)
        if result['status'] == 'FAIL' or not cases:
            rows.append(result if result['status'] == 'FAIL' else
                        {'name': name, 'status': 'FAIL', 'detail': 'No test cases reported'})

    pytest_phase('python', ['tests', 'auto-tests/test_runner.py', '--ignore=tests/test_live_cvat.py',
                            '--ignore=tests/test_real_nuscenes.py'], clean_env)
    node_tests = sorted(str(p) for p in (ROOT / 'extension/tests').glob('*.test.js'))
    if args.node and node_tests:
        rows.append(run_command('extension core (Node)', [args.node, '--test', *node_tests], ROOT,
                                clean_env, out / 'extension.log'))
    else:
        rows.append({'name': 'extension core (Node)', 'status': 'SKIP', 'detail': 'Node or tests missing; use --node'})
    if args.dataset:
        dataset_env = dict(clean_env, NUSCENES_ROOT=str(args.dataset.resolve()))
        pytest_phase('dataset', ['tests/test_real_nuscenes.py'], dataset_env)
    else:
        rows.append({'name': 'real nuScenes', 'status': 'SKIP', 'detail': 'Use --dataset DIRECTORY'})
    if args.live_cvat:
        pytest_phase('live-cvat', ['tests/test_live_cvat.py'], dict(live_env, POINTSNAP_LIVE_CVAT='1'))
    else:
        rows.append({'name': 'CVAT temporary write tests', 'status': 'SKIP', 'detail': 'Use --live-cvat; existing jobs untouched'})
    if args.online:
        rows.extend(service_checks(args, live_env, out))
    else:
        rows.append({'name': 'running services', 'status': 'SKIP', 'detail': 'Use --online'})
    write_report(out, rows)
    counts = Counter(r['status'] for r in rows)
    print(f"PASS={counts['PASS']} FAIL={counts['FAIL']} SKIP={counts['SKIP']}\nReport: {out / 'report.md'}")
    return 1 if counts['FAIL'] else 0


if __name__ == '__main__':
    raise SystemExit(main())
