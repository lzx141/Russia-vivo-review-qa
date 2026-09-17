"""Platform and product identity helpers shared by all ingestion paths."""

from __future__ import annotations

import hashlib
import re
import unicodedata
from typing import Any


def _clean(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    return "" if text.lower() in {"", "nan", "none", "null"} else text


def normalize_platform(value: object) -> str:
    text = _clean(value).casefold()
    if "wildberries" in text or text == "wb" or "вайлдберриз" in text:
        return "wildberries"
    if "ozon" in text or "озон" in text:
        return "ozon"
    if "yandex" in text or "яндекс" in text:
        return "yandex_market"
    normalized = re.sub(r"[^a-z0-9]+", "_", text).strip("_")
    return normalized or "unknown"


def extract_source_product_id(url: object, explicit_id: object = None) -> str | None:
    explicit = _clean(explicit_id)
    if explicit:
        if explicit.endswith(".0") and explicit[:-2].isdigit():
            explicit = explicit[:-2]
        return explicit

    text = _clean(url)
    if not text:
        return None
    patterns = (
        r"wildberries\.[^/]+/catalog/(\d+)",
        r"/product/(?:[^/?#]*-)?(\d{5,})(?:/|\?|#|$)",
        r"[?&](?:sku|product_id|nmId)=(\d+)",
    )
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return match.group(1)
    return None


def normalize_product_name(value: object) -> str:
    text = unicodedata.normalize("NFKC", _clean(value)).casefold()
    text = re.sub(r"[^0-9a-zа-яё]+", "-", text, flags=re.IGNORECASE)
    return re.sub(r"-+", "-", text).strip("-")


def build_product_id(
    platform: str,
    source_product_id: str | None,
    product_name: str | None,
) -> tuple[str, str, float]:
    normalized_platform = normalize_platform(platform)
    explicit = _clean(source_product_id)
    if explicit:
        return f"{normalized_platform}:{explicit}", "source_product_id", 1.0

    normalized_name = normalize_product_name(product_name)
    if normalized_name:
        return (
            f"{normalized_platform}:name:{normalized_name}",
            "normalized_name",
            0.65,
        )

    digest = hashlib.sha256(normalized_platform.encode("utf-8")).hexdigest()[:16]
    return f"{normalized_platform}:unknown:{digest}", "unresolved", 0.0

