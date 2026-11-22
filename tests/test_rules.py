import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.rules import apply_rules, load_rules, matches  # noqa: E402


def test_high_intent_rule_wins_for_corporate_email():
    rules = load_rules(ROOT / "rules.yaml")
    score, status, rule = apply_rules(
        {"source": "site", "email": "i@company.com", "name": "Ilyas"}, rules
    )
    assert (score, status, rule) == (80, "hot", "high_intent")


def test_gmail_does_not_match_high_intent():
    rules = load_rules(ROOT / "rules.yaml")
    score, status, rule = apply_rules(
        {"source": "site", "email": "i@gmail.com", "name": "Ilyas"}, rules
    )
    assert (score, status, rule) == (0, "new", None)


def test_partner_rule_matches():
    rules = load_rules(ROOT / "rules.yaml")
    score, status, rule = apply_rules(
        {"source": "partner", "email": "x@unknown.io"}, rules
    )
    assert (score, status, rule) == (60, "warm", "partner")


def test_email_domain_in_matches_second_rule():
    rules = load_rules(ROOT / "rules.yaml")
    score, status, rule = apply_rules(
        {"source": "csv", "email": "x@corp.example"}, rules
    )
    assert (score, status, rule) == (70, "hot", "enterprise_domain")


def test_matches_requires_source_when_set():
    assert matches({"source": "site"}, {"source": "partner"}) is False


def test_load_rules_rejects_rule_without_when(tmp_path):
    path = tmp_path / "bad.yaml"
    path.write_text("rules:\n  - name: broken\n    score: 10\n", encoding="utf-8")
    with pytest.raises(ValueError):
        load_rules(path)


def test_load_rules_rejects_unknown_status(tmp_path):
    path = tmp_path / "bad.yaml"
    path.write_text(
        "rules:\n  - name: broken\n    when:\n      source: site\n    status: banana\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError):
        load_rules(path)
