"""Small-data reference pipeline using the same contract and quality rules as Spark."""

from __future__ import annotations

import csv
import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from .adapters import get_adapter
from .deduplication import deduplicate_records
from .manifest import RunManifest
from .quality import assess_quality


@dataclass(frozen=True)
class InputSpec:
    path: Path
    adapter: str


def _read_rows(path: Path) -> Iterable[dict[str, Any]]:
    suffix = path.suffix.casefold()
    if suffix == ".csv":
        with path.open("r", encoding="utf-8-sig", newline="") as stream:
            yield from csv.DictReader(stream)
        return
    if suffix in {".jsonl", ".ndjson"}:
        with path.open("r", encoding="utf-8") as stream:
            for line in stream:
                if line.strip():
                    yield json.loads(line)
        return
    raise ValueError(f"Unsupported input format: {path}")


def _write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as stream:
        for row in rows:
            stream.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def _existing_generated_at(manifest_path: Path) -> str | None:
    if not manifest_path.is_file():
        return None
    try:
        return json.loads(manifest_path.read_text(encoding="utf-8"))["generated_at"]
    except (KeyError, TypeError, ValueError, json.JSONDecodeError):
        return None


def run_local_pipeline(
    inputs: list[InputSpec] | tuple[InputSpec, ...],
    output_dir: Path,
    *,
    run_id: str | None = None,
) -> RunManifest:
    resolved_run_id = run_id or uuid.uuid4().hex
    run_dir = Path(output_dir) / f"run_id={resolved_run_id}"
    manifest_path = run_dir / "ads" / "run_manifest.json"
    generated_at = _existing_generated_at(manifest_path) or datetime.now(
        timezone.utc
    ).replace(microsecond=0).isoformat()

    raw_records: list[dict[str, Any]] = []
    assessed_records: list[dict[str, Any]] = []
    pre_quarantine: list[dict[str, Any]] = []
    for spec in inputs:
        path = Path(spec.path)
        adapter = get_adapter(spec.adapter)
        for row in _read_rows(path):
            canonical = adapter.adapt(row, path.name, run_id=resolved_run_id)
            raw_records.append(canonical)
            assessed = assess_quality(canonical)
            if (
                assessed["quality_score"] < 40
                or assessed.get("product_match_method") == "unresolved"
            ):
                assessed["quality_issues"] = sorted(
                    set(list(assessed.get("quality_issues") or []) + ["quarantined"])
                )
                pre_quarantine.append(assessed)
            else:
                assessed_records.append(assessed)

    accepted, duplicate_quarantine = deduplicate_records(assessed_records)
    quarantine = pre_quarantine + duplicate_quarantine

    _write_jsonl(run_dir / "ods" / "raw.jsonl", raw_records)
    _write_jsonl(run_dir / "dwd" / "accepted.jsonl", accepted)
    _write_jsonl(run_dir / "dwd" / "quarantine.jsonl", quarantine)

    input_rows = len(raw_records)
    accepted_rows = len(accepted)
    pass_rate = round((accepted_rows / input_rows * 100) if input_rows else 0.0, 2)
    manifest = RunManifest(
        run_id=resolved_run_id,
        generated_at=generated_at,
        input_rows=input_rows,
        accepted_rows=accepted_rows,
        quarantined_rows=len(quarantine),
        duplicate_rows=len(duplicate_quarantine),
        quality_pass_rate=pass_rate,
        quality_gate_status="passed" if input_rows and pass_rate >= 50 else "failed",
        input_files=tuple(str(Path(spec.path)) for spec in inputs),
    )
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        json.dumps(manifest.to_dict(), ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return manifest

