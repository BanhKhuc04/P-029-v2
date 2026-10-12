"""Kiểm thử lớp 4 của Box Verifier: học từ kết luận Đúng / Báo nhầm của người duyệt (việc C3)."""

from __future__ import annotations

import json

import numpy as np

from pointsnap.core.model import ErrorType, Finding, Severity
from pointsnap.learn import (
    MIN_SAMPLES_MODEL,
    Sample,
    apply,
    collect_reviews,
    learn_project,
    load_model,
    rule_stats,
    train,
)


def _samples(n=120, seed=0):
    """Luật floating: mục vượt ngưỡng nhiều thì thường là lỗi thật; luật fit.loose phần lớn là báo nhầm."""
    rng = np.random.default_rng(seed)
    out = []
    for _ in range(n):
        ratio = rng.uniform(1.0, 3.0)
        out.append(Sample("floating", "warning", "car", 0.12 * ratio, 0.12, "ok" if rng.random() < (ratio - 1) / 2 else "fp"))
    for _ in range(n // 3):
        out.append(Sample("fit.loose", "warning", "car", 0.6, 0.5, "ok" if rng.random() < 0.1 else "fp"))
    return out


def test_rule_stats_beta_posterior():
    stats = rule_stats([Sample("a", "warning", "car", 1, 1, "ok")] * 3 + [Sample("a", "warning", "car", 1, 1, "fp")])
    assert stats["a"]["ok"] == 3 and stats["a"]["fp"] == 1
    assert stats["a"]["precision"] == 4 / 6  # Beta(1 + 3, 1 + 1)


def test_model_used_only_when_cross_validation_better():
    small = train(_samples(n=10))
    assert small.n_samples < MIN_SAMPLES_MODEL and not small.use_model
    model = train(_samples())
    assert model.use_model and model.cv_logloss_model < model.cv_logloss_rule
    strong = model.confidence("floating", "warning", "car", 0.34, 0.12)
    weak = model.confidence("floating", "warning", "car", 0.13, 0.12)
    assert strong > weak
    assert model.confidence("fit.loose", "warning", "car", 0.6, 0.5) < 0.3


def test_apply_adds_confidence_and_downgrades_only_when_enabled():
    model = train(_samples())
    f = Finding(ErrorType.FIT, "fit.loose", Severity.WARNING, 3, "car", "Mặt đầu của box…", value=0.6, threshold=0.5)
    [kept] = apply([f], model)
    assert kept.severity is Severity.WARNING and 0 <= kept.details["confidence"] < 0.3
    [low] = apply([f], model, adjust_severity=True, downgrade_below=0.3, min_rule_reviews=20)
    assert low.severity is Severity.INFO and low.details["downgraded"] and "hạ xuống Thông tin" in low.message
    assert apply([f], None) == [f]


def test_learn_project_reads_reviews_and_keeps_history(tmp_path):
    run = tmp_path / "runs" / "20261010-run1"
    run.mkdir(parents=True)
    findings = [{"rule": "floating", "severity": "warning", "label": "car", "value": 0.3, "threshold": 0.12},
                {"rule": "fit.loose", "severity": "warning", "label": "car", "value": 0.6, "threshold": 0.5}]
    (run / "findings.json").write_text(json.dumps(findings), encoding="utf-8")
    (run / "reviews.json").write_text(json.dumps({"0": "ok", "1": "fp", "7": "ok"}), encoding="utf-8")
    assert [s.verdict for s in collect_reviews(tmp_path)] == ["ok", "fp"]  # mục 7 không tồn tại thì bỏ
    first = learn_project(tmp_path)
    second = learn_project(tmp_path)
    assert (first.version, second.version) == (1, 2)
    assert load_model(tmp_path).version == 2
    assert (tmp_path / "learned-history" / "learned-v1.json").is_file()
