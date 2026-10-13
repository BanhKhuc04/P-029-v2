"""Kiểm tra danh mục quy tắc tập trung (Rule Catalog) và API /api/rules."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from pointsnap.core.config import load_config
from pointsnap.core.rules import (
    DEFAULT_FIX_TIP,
    RULES_CATALOG,
    SINK_FIX_TIP,
    get_rule,
    rule_fix_tip,
    rule_label,
    rule_of_message,
    rule_switch_key,
    rules_catalog_dict,
)
from pointsnap.core.scanner import is_rule_enabled
from pointsnap.web.app import create_app


def test_rules_catalog_completeness():
    """Catalog phải chứa ít nhất 30 quy tắc, không trùng lặp ID và đầy đủ thông tin."""
    assert len(RULES_CATALOG) >= 30
    ids = [r.id for r in RULES_CATALOG]
    assert len(ids) == len(set(ids)), "Có rule ID bị trùng lặp"

    for rule in RULES_CATALOG:
        assert rule.id
        assert rule.switch_key
        assert rule.label_vi
        assert rule.fix_tip
        assert len(rule.patterns) > 0


def test_rule_helpers():
    """Kiểm tra các hàm helper tra cứu quy tắc."""
    rule = get_rule("floating")
    assert rule is not None
    assert rule.label_vi == "Lơ lửng / lún"
    assert rule_switch_key("floating") == "floating"
    assert rule_switch_key("track.jump") == "track_jump"

    # Nhận diện rule từ thông báo
    assert rule_of_message("Box lơ lửng 0.35m so với mặt đất") == "floating"
    assert rule_of_message("Đáy box (lún) -0.25m") == "floating"
    assert rule_of_message("Tâm box nhảy 3.2m giữa hai frame") == "track.jump"
    assert rule_of_message("Vật đổi hướng nhanh bất thường 2.5 rad") == "heading.flip"
    assert rule_of_message("Box không có điểm LiDAR nào") == "fit.empty"
    assert rule_of_message("Câu không khớp quy tắc nào") is None

    # Fix tips
    assert rule_fix_tip("floating", "Box lơ lửng 0.3m") != SINK_FIX_TIP
    assert rule_fix_tip("floating", "Box (lún) 0.3m") == SINK_FIX_TIP
    assert rule_fix_tip("floating", "nằm dưới mặt đất") == SINK_FIX_TIP
    assert rule_fix_tip("unknown.rule") == DEFAULT_FIX_TIP


def test_is_rule_enabled_with_catalog():
    """Kiểm tra is_rule_enabled trong scanner đọc đúng cấu hình thông qua catalog."""
    config = load_config()
    assert is_rule_enabled("floating", config) is True
    assert is_rule_enabled("heading.flip", config) is True
    assert is_rule_enabled("track.jump", config) is False
    assert is_rule_enabled("fit.loose", config) is False
    assert is_rule_enabled("fit.outside", config) is False

    # Thay đổi cờ luật (RulesConfig là frozen dataclass)
    import dataclasses
    new_rules = dataclasses.replace(config.rules, floating=False, track_jump=True)
    config = dataclasses.replace(config, rules=new_rules)
    assert is_rule_enabled("floating", config) is False
    assert is_rule_enabled("floating.no_evidence", config) is False
    assert is_rule_enabled("track.jump", config) is True
    assert is_rule_enabled("heading.flip", config) is True


def test_api_rules_endpoint(tmp_path):
    """API GET /api/rules phải trả về status 200 và catalog đầy đủ."""
    app = create_app(home_dir=tmp_path)
    client = TestClient(app)
    resp = client.get("/api/rules")
    assert resp.status_code == 200
    data = resp.json()

    assert "rules" in data
    assert "labels" in data
    assert "tips" in data
    assert "sink_fix_tip" in data
    assert len(data["rules"]) >= 30
    assert data["labels"]["floating"] == "Lơ lửng / lún"
    assert data["labels"]["track.jump"] == "Nhảy vị trí"
    assert data["sink_fix_tip"] == SINK_FIX_TIP
