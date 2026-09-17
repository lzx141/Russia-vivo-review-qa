"""Serializable pipeline run manifest."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class RunManifest:
    run_id: str
    generated_at: str
    input_rows: int
    accepted_rows: int
    quarantined_rows: int
    duplicate_rows: int
    quality_pass_rate: float
    quality_gate_status: str
    input_files: tuple[str, ...] = field(default_factory=tuple)
    notes: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["input_files"] = list(self.input_files)
        payload["notes"] = list(self.notes)
        return payload

