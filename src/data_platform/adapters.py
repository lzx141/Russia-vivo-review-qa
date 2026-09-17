"""Adapters that map source-specific records to the canonical contract."""

from __future__ import annotations

from typing import Any, Mapping

from .contract import canonical_record


class SelfCollectedAdapter:
    source_dataset = "self_crawled"
    dataset_role = "business_primary"

    def adapt(
        self,
        row: Mapping[str, Any],
        source_file: str,
        *,
        run_id: str | None = None,
    ) -> dict[str, Any]:
        record_type = str(row.get("data_type") or "").strip().casefold()
        if record_type in {"qa", "question", "questions"} or row.get("question"):
            record_type = "question"
        else:
            record_type = "review"
        return canonical_record(
            row,
            self.source_dataset,
            record_type,
            dataset_role=self.dataset_role,
            source_file=source_file,
            pipeline_run_id=run_id,
        )


class PublicWbQuestionAdapter:
    source_dataset = "nyuuzyou/wb-questions"
    dataset_role = "external_validation"
    license_name = "CC0-1.0"

    def adapt(
        self,
        row: Mapping[str, Any],
        source_file: str,
        *,
        run_id: str | None = None,
    ) -> dict[str, Any]:
        normalized = dict(row)
        normalized["platform"] = "wildberries"
        normalized["source_product_id"] = row.get("nmId")
        return canonical_record(
            normalized,
            self.source_dataset,
            "question",
            dataset_role=self.dataset_role,
            license_name=self.license_name,
            source_file=source_file,
            pipeline_run_id=run_id,
        )


ADAPTERS = {
    "self": SelfCollectedAdapter,
    "public_wb_question": PublicWbQuestionAdapter,
}


def get_adapter(name: str):
    try:
        return ADAPTERS[name]()
    except KeyError as exc:
        raise ValueError(f"Unknown adapter: {name}") from exc

