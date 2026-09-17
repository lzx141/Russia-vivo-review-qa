"""Licensed Wildberries subset discovery and extraction helpers."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence

import requests


DATASETS_SERVER = "https://datasets-server.huggingface.co/parquet"
SUPPORTED_DATASET = "nyuuzyou/wb-questions"

QUESTION_COLUMNS = {
    "imtId": "BIGINT",
    "nmId": "BIGINT",
    "productName": "VARCHAR",
    "supplierArticle": "VARCHAR",
    "supplierId": "BIGINT",
    "supplierName": "VARCHAR",
    "brandName": "VARCHAR",
    "question": "VARCHAR",
    "answer": "VARCHAR",
}


def build_question_filter(
    brands: Sequence[str], categories: Sequence[str] = ()
) -> tuple[str, list[str]]:
    normalized_brands = [brand.strip().casefold() for brand in brands if brand.strip()]
    normalized_categories = [
        category.strip().casefold() for category in categories if category.strip()
    ]
    if not normalized_brands and not normalized_categories:
        raise ValueError("At least one brand or category filter is required")

    clauses: list[str] = []
    params: list[str] = []
    if normalized_brands:
        clauses.append(
            f"lower(trim(brandName)) IN ({', '.join('?' for _ in normalized_brands)})"
        )
        params.extend(normalized_brands)
    if normalized_categories:
        category_parts = []
        for category in normalized_categories:
            category_parts.append("lower(productName) LIKE ?")
            params.append(f"%{category}%")
        clauses.append("(" + " OR ".join(category_parts) + ")")
    return " AND ".join(clauses), params


def fetch_parquet_urls(dataset: str, split: str = "train") -> list[str]:
    response = requests.get(
        DATASETS_SERVER,
        params={"dataset": dataset},
        timeout=30,
    )
    response.raise_for_status()
    files = response.json().get("parquet_files", [])
    urls = [item["url"] for item in files if item.get("split") == split and item.get("url")]
    if not urls:
        raise RuntimeError(f"No Parquet files found for {dataset} split={split}")
    return urls


def _duckdb_source(source_urls: Sequence[str]) -> str:
    if not source_urls:
        raise ValueError("source_urls must not be empty")
    quoted = ["'" + str(url).replace("'", "''") + "'" for url in source_urls]
    return "read_parquet([" + ", ".join(quoted) + "], union_by_name=true)"


def extract_question_subset(
    source_urls: Sequence[str],
    output_path: Path,
    *,
    brands: Sequence[str],
    limit: int,
    metadata_path: Path,
    dataset: str = SUPPORTED_DATASET,
    categories: Sequence[str] = (),
) -> dict:
    if dataset != SUPPORTED_DATASET:
        raise ValueError(f"Unsupported dataset: {dataset}")
    if limit <= 0:
        raise ValueError("limit must be positive")

    import duckdb

    where_sql, params = build_question_filter(brands, categories)
    output_path = Path(output_path)
    metadata_path = Path(metadata_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    metadata_path.parent.mkdir(parents=True, exist_ok=True)
    escaped_output = output_path.resolve().as_posix().replace("'", "''")
    connection = duckdb.connect()
    scanned_source_files = 0
    try:
        schema_sql = ", ".join(
            f'"{name}" {sql_type}' for name, sql_type in QUESTION_COLUMNS.items()
        )
        connection.execute(f"CREATE TEMP TABLE extracted ({schema_sql})")
        for source_url in source_urls:
            relation = _duckdb_source([source_url])
            available_columns = {
                row[0]
                for row in connection.execute(
                    f"DESCRIBE SELECT * FROM {relation} LIMIT 0"
                ).fetchall()
            }
            filter_columns = {"brandName"} if brands else set()
            if categories:
                filter_columns.add("productName")
            missing_filter_columns = filter_columns - available_columns
            if missing_filter_columns:
                missing = ", ".join(sorted(missing_filter_columns))
                raise ValueError(f"Source schema lacks required filter columns: {missing}")

            current_count = connection.execute(
                "SELECT COUNT(*) FROM extracted"
            ).fetchone()[0]
            remaining = int(limit) - int(current_count)
            if remaining <= 0:
                break
            select_columns = []
            for name, sql_type in QUESTION_COLUMNS.items():
                if name in available_columns:
                    select_columns.append(f'CAST("{name}" AS {sql_type})')
                else:
                    select_columns.append(f"CAST(NULL AS {sql_type})")
            select_sql = ",\n                    ".join(select_columns)
            connection.execute(
                f"""
                INSERT INTO extracted
                SELECT
                    {select_sql}
                FROM {relation}
                WHERE {where_sql}
                LIMIT ?
                """,
                [*params, remaining],
            )
            scanned_source_files += 1

        connection.execute(
            f"COPY extracted TO '{escaped_output}' (FORMAT PARQUET, COMPRESSION ZSTD)"
        )
        row_count = connection.execute("SELECT COUNT(*) FROM extracted").fetchone()[0]
    finally:
        connection.close()

    metadata = {
        "dataset": dataset,
        "dataset_url": f"https://huggingface.co/datasets/{dataset}",
        "license": "CC0-1.0",
        "extracted_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "filters": {
            "brands": [brand.strip().casefold() for brand in brands if brand.strip()],
            "categories": [
                category.strip().casefold() for category in categories if category.strip()
            ],
            "limit": int(limit),
        },
        "source_file_count": len(source_urls),
        "scanned_source_file_count": scanned_source_files,
        "row_count": int(row_count),
        "output": str(output_path),
    }
    metadata_path.write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return metadata
