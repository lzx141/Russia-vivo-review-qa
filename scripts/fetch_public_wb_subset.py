"""Extract a licensed, topic-focused Wildberries questions subset."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.data_platform.external_wb import (  # noqa: E402
    SUPPORTED_DATASET,
    extract_question_subset,
    fetch_parquet_urls,
)


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", default=SUPPORTED_DATASET)
    parser.add_argument("--brands", nargs="+", required=True)
    parser.add_argument("--categories", nargs="*", default=[])
    parser.add_argument("--limit", type=int, default=100_000)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--metadata-output", type=Path, required=True)
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    urls = fetch_parquet_urls(args.dataset)
    if args.dry_run:
        payload = {
            "status": "dry_run",
            "dataset": args.dataset,
            "dataset_url": f"https://huggingface.co/datasets/{args.dataset}",
            "license": "CC0-1.0",
            "checked_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
            "parquet_files": len(urls),
            "filters": {
                "brands": [value.casefold() for value in args.brands],
                "categories": [value.casefold() for value in args.categories],
                "limit": args.limit,
            },
        }
        args.metadata_output.parent.mkdir(parents=True, exist_ok=True)
        args.metadata_output.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0

    result = extract_question_subset(
        urls,
        args.output,
        brands=args.brands,
        categories=args.categories,
        limit=args.limit,
        metadata_path=args.metadata_output,
        dataset=args.dataset,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

