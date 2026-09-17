"""Deterministic cross-source duplicate detection with audit output."""

from __future__ import annotations

import hashlib
import re
import unicodedata
from collections import defaultdict
from typing import Any, Iterable, Mapping


def normalize_text(value: object) -> str:
    if value is None:
        return ""
    text = unicodedata.normalize("NFKC", str(value)).casefold().strip()
    return re.sub(r"\s+", " ", text)


def record_fingerprint(record: Mapping[str, Any]) -> str:
    material = "\x1f".join(
        [
            str(record.get("product_id") or ""),
            str(record.get("record_type") or ""),
            normalize_text(record.get("text")),
            str(record.get("rating") if record.get("rating") is not None else ""),
        ]
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def deduplicate_records(
    records: Iterable[Mapping[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    groups: dict[str, list[tuple[int, dict[str, Any]]]] = defaultdict(list)
    for index, record in enumerate(records):
        copied = dict(record)
        groups[record_fingerprint(copied)].append((index, copied))

    accepted_with_index: list[tuple[int, dict[str, Any]]] = []
    rejected_with_index: list[tuple[int, dict[str, Any]]] = []
    for group in groups.values():
        best_index, best = max(
            group,
            key=lambda item: (float(item[1].get("quality_score") or 0), -item[0]),
        )
        accepted_with_index.append((best_index, best))
        for index, candidate in group:
            if index == best_index:
                continue
            issues = list(candidate.get("quality_issues") or [])
            issues.append("duplicate")
            candidate["quality_issues"] = sorted(set(issues))
            candidate["duplicate_of"] = best.get("record_id")
            candidate["is_rating_eligible"] = False
            candidate["is_trend_eligible"] = False
            candidate["is_text_eligible"] = False
            candidate["is_product_eligible"] = False
            rejected_with_index.append((index, candidate))

    accepted = [record for _, record in sorted(accepted_with_index)]
    rejected = [record for _, record in sorted(rejected_with_index)]
    return accepted, rejected

