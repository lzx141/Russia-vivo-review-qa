import json
import tempfile
import unittest
from pathlib import Path

import pandas as pd


class TestDashboardGovernance(unittest.TestCase):
    def test_database_governance_records_include_stable_identity_fields(self):
        from src.dashboard.generate_stats import get_governance_records

        class FakeDatabase:
            query = ""

            def fetch_query(self, query):
                self.query = query
                return [[
                    "review", "wb.xlsx", "A", "2026-09-30", 5,
                    "", "", "great", "Phone A", "sku-1", "https://item/1",
                    "wildberries", "", "", "很好",
                ]]

        database = FakeDatabase()
        provider = type("Provider", (), {"df": None, "db": database})()
        records = get_governance_records(provider)

        self.assertIn("sku, url", database.query)
        self.assertEqual(records.loc[0, "SKU"], "sku-1")
        self.assertEqual(records.loc[0, "URL"], "https://item/1")

    def test_dataset_audit_builds_real_governance_snapshot(self):
        from src.dashboard.generate_stats import build_dataset_governance

        records = pd.DataFrame(
            [
                {
                    "data_type": "review", "source_file": "wb.xlsx",
                    "publishDate": "2026-09-30 08:00:00", "rate": "5",
                    "review": "great", "review_zh": "很好", "name": "Phone A",
                    "siteName": "wildberries",
                },
                {
                    "data_type": "review", "source_file": "wb.xlsx",
                    "publishDate": "2026-09-30 08:00:00", "rate": "5",
                    "review": "great", "review_zh": "很好", "name": "Phone A",
                    "siteName": "wildberries",
                },
                {
                    "data_type": "qa", "source_file": "ozon_questions.xlsx",
                    "publishDate": "2026-09-29 00:00:00", "question": "5G?",
                    "answer": "Yes", "question_zh": "支持5G吗？",
                    "answer_zh": "支持", "name": "Phone A",
                    "siteName": "OZON-question",
                },
                {
                    "data_type": "review", "source_file": "wb.xlsx",
                    "publishDate": "", "rate": "5", "review": "undated",
                    "review_zh": "无日期", "name": "Phone B",
                    "siteName": "wildberries",
                },
                {
                    "data_type": "review", "source_file": "ozon_reviews.xlsx",
                    "publishDate": "2026-09-28 00:00:00", "rate": "4",
                    "review": "", "review_zh": "", "name": "Phone B",
                    "siteName": "OZON",
                },
            ]
        ).fillna("")

        result = build_dataset_governance(
            records,
            generated_at="2026-10-04 12:00:00",
            version="abc1234",
        )

        manifest = result["run_manifest"]
        self.assertEqual(result["status"], "available")
        self.assertEqual(result["evidence_source"], "published_dataset_audit")
        self.assertEqual(manifest["input_rows"], 5)
        self.assertEqual(manifest["accepted_rows"], 3)
        self.assertEqual(manifest["quarantined_rows"], 2)
        self.assertEqual(manifest["duplicate_rows"], 1)
        self.assertEqual(manifest["quality_gate_status"], "failed")
        self.assertEqual(result["freshness"]["latest_record_at"], "2026-09-30 08:00:00")
        self.assertEqual(result["audit_scope"]["version"], "abc1234")
        self.assertEqual(len(result["source_coverage"]), 2)
        self.assertEqual(result["source_comparison"]["matched_product_count"], 1)

    def test_governance_assets_load_when_present(self):
        from src.dashboard.generate_stats import load_governance_assets

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            manifest = root / "manifest.json"
            comparison = root / "comparison.json"
            manifest.write_text(
                json.dumps({"quality_pass_rate": 92.5, "quality_gate_status": "passed"}),
                encoding="utf-8",
            )
            comparison.write_text(
                json.dumps({"status": "available", "sample_sizes": {"business_primary": 10}}),
                encoding="utf-8",
            )
            result = load_governance_assets(manifest, comparison)
            self.assertEqual(result["status"], "available")
            self.assertEqual(result["run_manifest"]["quality_pass_rate"], 92.5)
            self.assertEqual(result["source_comparison"]["status"], "available")

    def test_governance_assets_are_explicitly_unavailable_when_absent(self):
        from src.dashboard.generate_stats import load_governance_assets

        result = load_governance_assets("missing-manifest.json", "missing-comparison.json")
        self.assertEqual(result["status"], "unavailable")
        self.assertIsNone(result["run_manifest"])
        self.assertIsNone(result["source_comparison"])


if __name__ == "__main__":
    unittest.main()
