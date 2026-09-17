"""Metric-aware aggregations for trusted feedback marts."""

from __future__ import annotations

from collections import defaultdict
from statistics import mean
from typing import Any, Callable, Iterable, Mapping


MART_NAMES = (
    "quality_summary",
    "source_summary",
    "platform_summary",
    "product_summary",
    "monthly_trend",
)


def _summary(rows: list[dict[str, Any]], dimensions: Mapping[str, Any]) -> dict[str, Any]:
    total = len(rows)
    rating_rows = [row for row in rows if row.get("is_rating_eligible")]
    text_rows = [row for row in rows if row.get("is_text_eligible")]
    trend_rows = [row for row in rows if row.get("is_trend_eligible")]
    product_rows = [row for row in rows if row.get("is_product_eligible")]
    scores = [float(row["quality_score"]) for row in rows if row.get("quality_score") is not None]
    ratings = [float(row["rating"]) for row in rating_rows if row.get("rating") is not None]
    return {
        **dimensions,
        "total_records": total,
        "rating_eligible_records": len(rating_rows),
        "text_eligible_records": len(text_rows),
        "trend_eligible_records": len(trend_rows),
        "product_eligible_records": len(product_rows),
        "quality_pass_rate": round(len(text_rows) / total * 100, 2) if total else 0.0,
        "average_quality_score": round(mean(scores), 2) if scores else None,
        "average_rating": round(mean(ratings), 2) if ratings else None,
        "negative_rate": round(sum(rating <= 2 for rating in ratings) / len(ratings) * 100, 2)
        if ratings
        else None,
    }


def _group(
    rows: list[dict[str, Any]],
    key_name: str,
    key_fn: Callable[[dict[str, Any]], Any],
    *,
    eligibility: str | None = None,
) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        if eligibility and not row.get(eligibility):
            continue
        key = key_fn(row)
        if key is not None and str(key).strip():
            grouped[str(key)].append(row)
    return [_summary(grouped[key], {key_name: key}) for key in sorted(grouped)]


def build_business_marts(
    records: Iterable[Mapping[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    rows = [dict(record) for record in records]
    if not rows:
        return {name: [] for name in MART_NAMES}
    quality_summary = [_summary(rows, {"scope": "all_records"})]
    source_summary = _group(rows, "source_dataset", lambda row: row.get("source_dataset"))
    platform_summary = _group(rows, "platform", lambda row: row.get("platform"))
    product_summary = _group(
        rows,
        "product_id",
        lambda row: row.get("product_id"),
        eligibility="is_product_eligible",
    )
    monthly_trend = _group(
        rows,
        "month",
        lambda row: str(row.get("event_date"))[:7] if row.get("event_date") else None,
        eligibility="is_trend_eligible",
    )
    for row in monthly_trend:
        row["eligible_records"] = row["total_records"]
    return {
        "quality_summary": quality_summary,
        "source_summary": source_summary,
        "platform_summary": platform_summary,
        "product_summary": product_summary,
        "monthly_trend": monthly_trend,
    }
