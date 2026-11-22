from pathlib import Path

import yaml

ALLOWED_STATUSES = {"new", "hot", "warm", "cold", "won", "lost"}


def load_rules(path: str | Path) -> list[dict]:
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    rules = raw.get("rules")
    if not isinstance(rules, list):
        raise ValueError("rules.yaml must contain a top level 'rules' list")
    for rule in rules:
        validate_rule(rule)
    return rules


def validate_rule(rule: dict) -> None:
    if not isinstance(rule, dict):
        raise ValueError("each rule must be a mapping")
    if not rule.get("name"):
        raise ValueError("rule without a name")
    when = rule.get("when")
    if not isinstance(when, dict) or not when:
        raise ValueError(f"rule {rule['name']}: 'when' must be a non empty mapping")
    score = rule.get("score", 0)
    if not isinstance(score, int) or not 0 <= score <= 100:
        raise ValueError(f"rule {rule['name']}: score must be an int between 0 and 100")
    status = rule.get("status", "new")
    if status not in ALLOWED_STATUSES:
        raise ValueError(f"rule {rule['name']}: unknown status {status}")


def email_domain(email: str | None) -> str:
    if not email or "@" not in email:
        return ""
    return email.rsplit("@", 1)[1].strip().lower()


def matches(lead: dict, when: dict) -> bool:
    if "source" in when and lead.get("source") != when["source"]:
        return False
    domain = email_domain(lead.get("email"))
    if "email_domain_not" in when and domain == str(when["email_domain_not"]).lower():
        return False
    if "email_domain_in" in when:
        allowed = [str(item).lower() for item in when["email_domain_in"]]
        if domain not in allowed:
            return False
    if "name_contains" in when:
        needle = str(when["name_contains"]).lower()
        if needle not in (lead.get("name") or "").lower():
            return False
    return True


def apply_rules(lead: dict, rules: list[dict]) -> tuple[int, str, str | None]:
    for rule in rules:
        if matches(lead, rule["when"]):
            return int(rule.get("score", 0)), rule.get("status", "new"), rule["name"]
    return 0, "new", None
