"""The full runner must preserve failing commands and known failures in evidence."""
import importlib.util
import os
from pathlib import Path
import sys


def runner():
    spec = importlib.util.spec_from_file_location("full_runner", Path(__file__).with_name("run_all.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_junit_distinguishes_xfail_skip_failure_and_pass(tmp_path):
    xml = tmp_path / "results.xml"
    xml.write_text('<testsuite><testcase name="ok"/><testcase name="bad"><failure/></testcase>'
                   '<testcase name="known"><skipped type="pytest.xfail"/></testcase>'
                   '<testcase name="offline"><skipped/></testcase></testsuite>')
    assert runner().junit_counts(xml) == {"PASS": 1, "FAIL": 1, "XFAIL": 1, "SKIP": 1}


def test_nonzero_command_keeps_exit_and_log(tmp_path):
    row = runner().command("broken", [sys.executable, "-c", 'print("diagnostic"); raise SystemExit(7)'],
                           tmp_path, dict(os.environ), tmp_path, 10)
    assert row["status"] == "FAIL" and row["exit_code"] == 7
    assert "diagnostic" in (tmp_path / row["log"]).read_text()


def test_timeout_is_a_failure(tmp_path):
    row = runner().command("timeout", [sys.executable, "-c", "import time; time.sleep(5)"],
                           tmp_path, dict(os.environ), tmp_path, 0.1)
    assert row["status"] == "FAIL" and row["error"] == "TimeoutExpired"


def test_report_failure_exit_does_not_hide_remaining_phases(tmp_path):
    metadata = dict(review_model="test", source_commit="fixture", branch="fixture", started_at="fixture")
    rows = [dict(name="broken", status="FAIL"), dict(name="next", status="PASS"), dict(name="offline", status="SKIP")]
    assert runner().report(tmp_path, metadata, rows) == 1
    text = (tmp_path / "report.md").read_text()
    assert "broken" in text and "next" in text and "SKIP" in text
