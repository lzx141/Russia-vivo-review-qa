"""Canonical schema loading and record normalization."""

from __future__ import annotations

import hashlib
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Mapping

import yaml

from .identity import (
    build_product_id,
    extract_source_product_id,
    normalize_platform,
)


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONTRACT = ROOT / "config" / "data_contract.yaml"


def load_contract(path: str | Path | None = None) -> dict:
    contract_path = Path(path) if path else DEFAULT_CONTRACT
    with contract_path.open("r", encoding="utf-8") as stream:
        contract = yaml.safe_load(stream)
    if not isinstance(contract, dict) or not isinstance(contract.get("fields"), list):
        raise ValueError(f"Invalid data contract: {contract_path}")
    return contract


def _first(raw: Mapping[str, Any], *names: str) -> Any:
    for name in names:
        value = raw.get(name)
        if value is not None and str(value).strip().lower() not in {"", "nan", "none"}:
            return value
    return None


def _text(value: Any) -> str | None:
    if value is None:
        return None
    result = str(value).strip()
    return None if result.lower() in {"", "nan", "none", "null"} else result


def _rating(value: Any) -> float | None:
    if value is None or str(value).strip() == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _date(value: Any) -> str | None:
    if value is None or str(value).strip() == "":
        return None
    if isinstance(value, (datetime, date)):
        return value.isoformat(sep=" ") if isinstance(value, datetime) else value.isoformat()
    text = str(value).strip()
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).isoformat(sep=" ")
    except ValueError:
        return text


def _stable_record_id(parts: list[Any]) -> str:
    material = "\x1f".join("" if value is None else str(value).strip() for value in parts)
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def canonical_record(
    raw: Mapping[str, Any],
    source: str,
    record_type: str,
    *,
    dataset_role: str = "business_primary",
    license_name: str | None = None,
    source_file: str | None = None,
    pipeline_run_id: str | None = None,
) -> dict[str, Any]:
    if record_type not in {"review", "question"}:
        raise ValueError(f"Unsupported record_type: {record_type}")

    platform = normalize_platform(_first(raw, "platform", "siteName", "site_name"))
    url = _first(raw, "url", "URL")
    source_product_id = extract_source_product_id(
        url,
        _first(raw, "source_product_id", "nmId", "nm_id", "SKU", "sku"),
    )
    product_name = _text(_first(raw, "product_name", "productName", "name", "imt_name"))
    product_id, match_method, match_confidence = build_product_id(
        platform, source_product_id, product_name
    )
    text_value = _text(_first(raw, "text", "review", "content"))
    question_value = _text(_first(raw, "question"))
    if record_type == "question":
        text_value = question_value or text_value
    answer = _text(_first(raw, "answer", "seller_answer"))
    event_date = _date(_first(raw, "event_date", "publishDate", "publish_date", "date"))
    rating = _rating(_first(raw, "rating", "rate", "productValuation"))
    source_record_id = _text(_first(raw, "source_record_id", "review_id", "id"))
    record_id = source_record_id or _stable_record_id(
        [source, platform, product_id, record_type, event_date, rating, text_value, answer]
    )

    record = {field: None for field in load_contract()["fields"]}
    record.update(
        {
            "record_id": record_id,
            "source_dataset": source,
            "source_record_id": source_record_id,
            "dataset_role": dataset_role,
            "platform": platform,
            "record_type": record_type,
            "product_id": product_id,
            "source_product_id": source_product_id,
            "product_name": product_name,
            "brand": _text(_first(raw, "brand", "brandName", "brand_name")),
            "category": _text(_first(raw, "category", "category_label", "subj_name")),
            "rating": rating,
            "text": text_value,
            "answer": answer,
            "author": _text(_first(raw, "author", "user", "username")),
            "event_date": event_date,
            "ingested_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
            "pipeline_run_id": pipeline_run_id,
            "license": license_name,
            "source_file": source_file,
            "product_match_method": match_method,
            "product_match_confidence": match_confidence,
            "quality_score": None,
            "quality_issues": [],
            "duplicate_of": None,
            "is_rating_eligible": False,
            "is_trend_eligible": False,
            "is_text_eligible": False,
            "is_product_eligible": False,
        }
    )
    return record

