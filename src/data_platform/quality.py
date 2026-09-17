"""Record-level quality scoring and metric eligibility rules."""

from __future__ import annotations

import re
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Mapping

import yaml


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RULES = ROOT / "config" / "quality_rules.yaml"


def load_quality_rules(path: str | Path | None = None) -> dict:
    rules_path = Path(path) if path else DEFAULT_RULES
    with rules_path.open("r", encoding="utf-8") as stream:
        rules = yaml.safe_load(stream)
    if not isinstance(rules, dict) or "thresholds" not in rules:
        raise ValueError(f"Invalid quality rules: {rules_path}")
    return rules


def _clean_text(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    return "" if text.casefold() in {"", "none", "null", "nan"} else text


def _valid_rating(value: Any) -> bool:
    try:
        return 1 <= float(value) <= 5
    except (TypeError, ValueError):
        return False


def _valid_date(value: Any) -> bool:
    if value is None or str(value).strip() == "":
        return False
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, date):
        parsed = datetime.combine(value, datetime.min.time())
    else:
        try:
            parsed = datetime.fromisoformat(str(value).strip().replace("Z", "+00:00"))
        except ValueError:
            return False
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
    return parsed.date() <= datetime.now(timezone.utc).date()


def cyrillic_ratio(value: Any) -> float:
    text = _clean_text(value)
    letters = re.findall(r"[A-Za-zА-Яа-яЁё]", text)
    if not letters:
        return 0.0
    cyrillic = re.findall(r"[А-Яа-яЁё]", text)
    return len(cyrillic) / len(letters)


def assess_quality(
    record: Mapping[str, Any], rules: Mapping[str, Any] | None = None
) -> dict[str, Any]:
    config = dict(rules or load_quality_rules())
    record_type = str(record.get("record_type") or "review")
    weights = config[
        "question_weights" if record_type == "question" else "review_weights"
    ]
    thresholds = config["thresholds"]
    text_config = config["text"]

    result = dict(record)
    issues: list[str] = list(record.get("quality_issues") or [])
    score = 0
    text = _clean_text(record.get("text"))
    answer = _clean_text(record.get("answer"))
    has_text = len(text) >= int(text_config["min_characters"])
    language_ok = has_text and cyrillic_ratio(text) >= float(
        text_config["min_cyrillic_ratio"]
    )
    match_ok = float(record.get("product_match_confidence") or 0) >= 0.65
    date_ok = _valid_date(record.get("event_date"))
    unique_ok = not record.get("duplicate_of")

    if record_type == "question":
        if has_text:
            score += int(weights["question"])
        else:
            issues.append("missing_question")
        if answer:
            score += int(weights["answer"])
        else:
            issues.append("missing_answer")
        rating_ok = False
    else:
        if has_text:
            score += int(weights["text"])
        else:
            issues.append("missing_text")
        rating_ok = _valid_rating(record.get("rating"))
        if rating_ok:
            score += int(weights["rating"])
        else:
            issues.append("invalid_rating")

    if match_ok:
        score += int(weights["product_match"])
    else:
        issues.append("low_product_match_confidence")
    if date_ok:
        score += int(weights["event_date"])
    else:
        issues.append("invalid_or_missing_date")
    if language_ok:
        score += int(weights["language"])
    elif has_text:
        issues.append("low_cyrillic_ratio")
    if unique_ok:
        score += int(weights["unique"])
    else:
        issues.append("duplicate")

    result.update(
        {
            "quality_score": int(score),
            "quality_issues": sorted(set(issues)),
            "is_rating_eligible": bool(
                record_type == "review"
                and rating_ok
                and score >= int(thresholds["rating"])
            ),
            "is_text_eligible": bool(
                has_text and language_ok and score >= int(thresholds["text"])
            ),
            "is_trend_eligible": bool(
                date_ok and score >= int(thresholds["trend"])
            ),
            "is_product_eligible": bool(
                match_ok and score >= int(thresholds["product"])
            ),
        }
    )
    return result

