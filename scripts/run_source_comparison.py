"""Build business marts and an observational matched-source comparison."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.analysis.business_marts import build_business_marts
from src.analysis.source_comparison import build_matched_cohort, compare_sources


def load_records(paths: list[Path]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for path in paths:
        suffix = path.suffix.casefold()
        if suffix in {".jsonl", ".ndjson"}:
            with path.open("r", encoding="utf-8") as stream:
                records.extend(json.loads(line) for line in stream if line.strip())
        elif suffix == ".csv":
            with path.open("r", encoding="utf-8-sig", newline="") as stream:
                records.extend(csv.DictReader(stream))
        elif suffix == ".parquet":
            import duckdb

            escaped = path.resolve().as_posix().replace("'", "''")
            connection = duckdb.connect()
            try:
                columns = [item[0] for item in connection.execute(
                    f"DESCRIBE SELECT * FROM read_parquet('{escaped}')"
                ).fetchall()]
                records.extend(
                    dict(zip(columns, row))
                    for row in connection.execute(
                        f"SELECT * FROM read_parquet('{escaped}')"
                    ).fetchall()
                )
            finally:
                connection.close()
        else:
            raise ValueError(f"Unsupported input format: {path}")
    return records


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", action="append", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--max-per-product", type=int, default=500)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    records = load_records(args.input)
    cohort = build_matched_cohort(
        records, max_per_product=args.max_per_product, seed=args.seed
    )
    comparison = compare_sources(cohort, seed=args.seed)
    marts = build_business_marts(records)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "source_comparison.json").write_text(
        json.dumps(comparison, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    (args.output_dir / "business_marts.json").write_text(
        json.dumps(marts, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "records": len(records),
                "matched_records": len(cohort),
                "status": comparison["status"],
                "output_dir": str(args.output_dir),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
