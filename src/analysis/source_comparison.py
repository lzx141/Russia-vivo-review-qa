"""Observational source-comparison utilities for matched feedback cohorts."""

from __future__ import annotations

import math
import random
from collections import defaultdict
from statistics import mean, median
from typing import Any, Iterable, Mapping

from scipy.spatial.distance import jensenshannon
from scipy.stats import chi2_contingency, mannwhitneyu


ROLES = ("business_primary", "external_validation")


def build_matched_cohort(
    records: Iterable[Mapping[str, Any]],
    *,
    max_per_product: int = 500,
    seed: int = 42,
) -> list[dict[str, Any]]:
    """Keep shared product IDs and balance each source within product."""
    if max_per_product <= 0:
        raise ValueError("max_per_product must be positive")
    grouped: dict[str, dict[str, list[dict[str, Any]]]] = defaultdict(
        lambda: defaultdict(list)
    )
    for raw in records:
        row = dict(raw)
        product_id = str(row.get("product_id") or "").strip()
        role = str(row.get("dataset_role") or "").strip()
        if product_id and role in ROLES:
            grouped[product_id][role].append(row)

    rng = random.Random(seed)
    cohort: list[dict[str, Any]] = []
    for product_id in sorted(grouped):
        by_role = grouped[product_id]
        if any(not by_role.get(role) for role in ROLES):
            continue
        sample_size = min(
            max_per_product,
            *(len(by_role[role]) for role in ROLES),
        )
        for role in ROLES:
            candidates = sorted(
                by_role[role], key=lambda row: str(row.get("record_id") or "")
            )
            if len(candidates) > sample_size:
                candidates = rng.sample(candidates, sample_size)
            cohort.extend(candidates)
    return cohort


def _valid_rating(value: Any) -> float | None:
    try:
        rating = float(value)
    except (TypeError, ValueError):
        return None
    return rating if 1 <= rating <= 5 else None


def _text(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    return "" if text.casefold() in {"none", "null", "nan"} else text


def _bootstrap_delta(
    left: list[float], right: list[float], *, seed: int, iterations: int = 1000
) -> list[float] | None:
    if not left or not right:
        return None
    rng = random.Random(seed)
    deltas = []
    for _ in range(iterations):
        left_mean = mean(rng.choice(left) for _ in range(len(left)))
        right_mean = mean(rng.choice(right) for _ in range(len(right)))
        deltas.append(left_mean - right_mean)
    deltas.sort()
    low = deltas[int(iterations * 0.025)]
    high = deltas[min(iterations - 1, int(iterations * 0.975))]
    return [round(low, 4), round(high, 4)]


def _mann_whitney(left: list[float], right: list[float]) -> dict[str, float] | None:
    if not left or not right:
        return None
    result = mannwhitneyu(left, right, alternative="two-sided")
    effect = 1 - (2 * float(result.statistic)) / (len(left) * len(right))
    return {
        "statistic": round(float(result.statistic), 4),
        "p_value": round(float(result.pvalue), 6),
        "rank_biserial_effect": round(effect, 4),
    }


def _rating_comparison(by_role: Mapping[str, list[dict[str, Any]]]) -> dict | None:
    ratings = {
        role: [
            rating
            for row in by_role[role]
            if (rating := _valid_rating(row.get("rating"))) is not None
        ]
        for role in ROLES
    }
    if any(not ratings[role] for role in ROLES):
        return None
    histograms = {
        role: [sum(1 for rating in ratings[role] if round(rating) == star) for star in range(1, 6)]
        for role in ROLES
    }
    contingency = [histograms[role] for role in ROLES]
    chi_square = None
    nonzero_columns = [
        index for index in range(5) if sum(row[index] for row in contingency) > 0
    ]
    if len(nonzero_columns) >= 2:
        reduced = [[row[index] for index in nonzero_columns] for row in contingency]
        chi2, p_value, _, _ = chi2_contingency(reduced)
        chi_square = {"statistic": round(float(chi2), 4), "p_value": round(float(p_value), 6)}
    distributions = []
    for role in ROLES:
        total = sum(histograms[role])
        distributions.append([count / total for count in histograms[role]])
    divergence = float(jensenshannon(distributions[0], distributions[1], base=2) ** 2)
    return {
        "mean_rating": {role: round(mean(ratings[role]), 4) for role in ROLES},
        "negative_rate": {
            role: round(sum(rating <= 2 for rating in ratings[role]) / len(ratings[role]), 4)
            for role in ROLES
        },
        "rating_distribution": {role: histograms[role] for role in ROLES},
        "mann_whitney": _mann_whitney(ratings[ROLES[0]], ratings[ROLES[1]]),
        "chi_square": chi_square,
        "jensen_shannon_divergence": round(divergence, 6) if math.isfinite(divergence) else None,
    }


def compare_sources(
    records: Iterable[Mapping[str, Any]], *, seed: int = 42
) -> dict[str, Any]:
    rows = [dict(row) for row in records]
    if not rows:
        return {
            "status": "unavailable",
            "sample_sizes": {},
            "limitations": "no matched records available; not a randomized A/B test",
        }
    by_role = {role: [row for row in rows if row.get("dataset_role") == role] for role in ROLES}
    sample_sizes = {role: len(by_role[role]) for role in ROLES}
    lengths = {
        role: [float(len(_text(row.get("text")))) for row in by_role[role] if _text(row.get("text"))]
        for role in ROLES
    }
    missing_text_rate = {
        role: round(
            sum(not _text(row.get("text")) for row in by_role[role]) / len(by_role[role]),
            4,
        )
        if by_role[role]
        else None
        for role in ROLES
    }
    rating_result = _rating_comparison(by_role)
    limitations = "observational matched-source comparison; not a randomized A/B test"
    record_types = {
        role: sorted({str(row.get("record_type")) for row in by_role[role] if row.get("record_type")})
        for role in ROLES
    }
    if record_types[ROLES[0]] != record_types[ROLES[1]]:
        limitations += "; record-type mix differs across sources and may confound text metrics"
    if rating_result is None:
        limitations += "; rating comparison unavailable because at least one source has no valid ratings"
    return {
        "status": "available",
        "sample_sizes": sample_sizes,
        "matched_product_count": len({row.get("product_id") for row in rows}),
        "missing_text_rate": missing_text_rate,
        "mean_text_length": {
            role: round(mean(lengths[role]), 4) if lengths[role] else None for role in ROLES
        },
        "median_text_length": {
            role: round(median(lengths[role]), 4) if lengths[role] else None for role in ROLES
        },
        "record_types": record_types,
        "text_length_delta_ci_95": _bootstrap_delta(
            lengths[ROLES[0]], lengths[ROLES[1]], seed=seed
        ),
        "text_length_mann_whitney": _mann_whitney(
            lengths[ROLES[0]], lengths[ROLES[1]]
        ),
        "rating_comparison": rating_result,
        "limitations": limitations,
    }
