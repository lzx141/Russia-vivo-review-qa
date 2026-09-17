import json
import tempfile
import unittest
from pathlib import Path


class TestDashboardGovernance(unittest.TestCase):
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
