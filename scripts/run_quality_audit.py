"""Audit a DWD JSONL file and emit a machine-readable quality gate result."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def audit_jsonl(
    input_path: Path,
    output_path: Path,
    *,
    minimum_pass_rate: float = 70.0,
) -> dict[str, Any]:
    rows = []
    with Path(input_path).open("r", encoding="utf-8") as stream:
        rows.extend(json.loads(line) for line in stream if line.strip())
    eligible = sum(bool(row.get("is_text_eligible")) for row in rows)
    pass_rate = round(eligible / len(rows) * 100, 2) if rows else 0.0
    scores = [float(row["quality_score"]) for row in rows if row.get("quality_score") is not None]
    result = {
        "status": "passed" if rows and pass_rate >= minimum_pass_rate else "failed",
        "total_records": len(rows),
        "text_eligible_records": eligible,
        "text_quality_pass_rate": pass_rate,
        "minimum_pass_rate": float(minimum_pass_rate),
        "average_quality_score": round(sum(scores) / len(scores), 2) if scores else None,
    }
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--minimum-pass-rate", type=float, default=70.0)
    args = parser.parse_args()
    result = audit_jsonl(
        args.input, args.output, minimum_pass_rate=args.minimum_pass_rate
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(0 if result["status"] == "passed" else 2)


if __name__ == "__main__":
    main()
