"""Run the Spark ODS/DWD/DWS/ADS feedback pipeline."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.data_platform.spark_pipeline import (  # noqa: E402
    build_layers,
    create_spark_session,
    manifest_frame,
    normalize_spark_frame,
)


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True)
    parser.add_argument("--input-format", choices=["csv", "json", "parquet"], required=True)
    parser.add_argument("--source-dataset", required=True)
    parser.add_argument("--dataset-role", required=True)
    parser.add_argument("--license")
    parser.add_argument("--output-root", required=True)
    parser.add_argument("--master", default="local[1]")
    parser.add_argument("--run-id", required=True)
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    spark = create_spark_session("russia-feedback-warehouse", args.master)
    try:
        reader = spark.read
        if args.input_format == "csv":
            raw = reader.option("header", True).option("multiLine", False).csv(args.input)
        elif args.input_format == "json":
            raw = reader.json(args.input)
        else:
            raw = reader.parquet(args.input)

        output = args.output_root.rstrip("/\\")
        raw.write.mode("overwrite").parquet(
            f"{output}/ods/source_dataset={args.source_dataset}/run_id={args.run_id}"
        )
        normalized = normalize_spark_frame(
            raw,
            args.source_dataset,
            args.dataset_role,
            args.run_id,
            license_name=args.license,
        )
        layers = build_layers(normalized)
        layers["dwd"].write.mode("overwrite").partitionBy(
            "platform", "event_month"
        ).parquet(f"{output}/dwd/run_id={args.run_id}")
        layers["quarantine"].write.mode("overwrite").parquet(
            f"{output}/quarantine/run_id={args.run_id}"
        )
        layers["dws"].write.mode("overwrite").parquet(
            f"{output}/dws/run_id={args.run_id}"
        )
        layers["ads"].write.mode("overwrite").parquet(
            f"{output}/ads/run_id={args.run_id}"
        )

        input_rows = raw.count()
        accepted_rows = layers["dwd"].count()
        quarantined_rows = layers["quarantine"].count()
        manifest = {
            "run_id": args.run_id,
            "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
            "input_rows": input_rows,
            "accepted_rows": accepted_rows,
            "quarantined_rows": quarantined_rows,
            "quality_pass_rate": round(accepted_rows / input_rows * 100, 2) if input_rows else 0.0,
            "quality_gate_status": "passed" if input_rows and accepted_rows / input_rows >= 0.5 else "failed",
        }
        manifest_frame(spark, manifest).coalesce(1).write.mode("overwrite").json(
            f"{output}/manifests/run_id={args.run_id}"
        )
        print(json.dumps(manifest, ensure_ascii=False, indent=2))
        return 0
    finally:
        spark.stop()


if __name__ == "__main__":
    raise SystemExit(main())
