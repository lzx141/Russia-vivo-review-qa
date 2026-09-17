"""Reproducible operational comparison of baseline and governed pipelines."""

from __future__ import annotations

from time import perf_counter
from typing import Any, Iterable, Mapping

from src.data_platform.deduplication import deduplicate_records
from src.data_platform.quality import assess_quality


def _rate(value: int, total: int) -> float:
    return round(value / total * 100, 2) if total else 0.0


def compare_pipeline_variants(
    records: Iterable[Mapping[str, Any]],
) -> dict[str, Any]:
    rows = [dict(row) for row in records]
    total = len(rows)

    baseline_start = perf_counter()
    baseline_seen = set()
    baseline_retained = []
    for row in rows:
        key = row.get("record_id")
        if key not in baseline_seen:
            baseline_seen.add(key)
            baseline_retained.append(row)
    baseline_ms = (perf_counter() - baseline_start) * 1000

    governed_start = perf_counter()
    candidates = []
    quality_quarantine = []
    for row in rows:
        assessed = assess_quality(row)
        if assessed["quality_score"] < 40 or assessed.get("product_match_method") == "unresolved":
            quality_quarantine.append(assessed)
        else:
            candidates.append(assessed)
    governed_retained, duplicates = deduplicate_records(candidates)
    governed_ms = (perf_counter() - governed_start) * 1000

    return {
        "input_records": total,
        "baseline": {
            "method": "record_id_only_deduplication",
            "retained_records": len(baseline_retained),
            "duplicate_records": total - len(baseline_retained),
            "retention_rate": _rate(len(baseline_retained), total),
            "elapsed_ms": round(baseline_ms, 3),
        },
        "governed": {
            "method": "quality_gate_and_content_fingerprint_deduplication",
            "retained_records": len(governed_retained),
            "quality_quarantine_records": len(quality_quarantine),
            "duplicate_records": len(duplicates),
            "retention_rate": _rate(len(governed_retained), total),
            "text_eligible_records": sum(
                bool(row.get("is_text_eligible")) for row in governed_retained
            ),
            "rating_eligible_records": sum(
                bool(row.get("is_rating_eligible")) for row in governed_retained
            ),
            "elapsed_ms": round(governed_ms, 3),
        },
        "limitations": (
            "Operational benchmark on identical input; not an accuracy evaluation. "
            "Accuracy or recall requires an independently labelled audit sample."
        ),
    }
