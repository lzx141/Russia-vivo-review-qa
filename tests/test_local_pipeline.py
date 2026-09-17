import json
import tempfile
import unittest
from pathlib import Path


class TestLocalPipeline(unittest.TestCase):
    def test_pipeline_writes_reconciled_outputs_and_is_idempotent(self):
        from src.data_platform.local_pipeline import InputSpec, run_local_pipeline

        fixture = Path(__file__).parent / "fixtures" / "self_review.csv"
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir)
            specs = [InputSpec(path=fixture, adapter="self")]
            first = run_local_pipeline(specs, output, run_id="fixed")
            second = run_local_pipeline(specs, output, run_id="fixed")

            run_dir = output / "run_id=fixed"
            self.assertTrue((run_dir / "ods" / "raw.jsonl").is_file())
            self.assertTrue((run_dir / "dwd" / "accepted.jsonl").is_file())
            self.assertTrue((run_dir / "dwd" / "quarantine.jsonl").is_file())
            manifest_path = run_dir / "ads" / "run_manifest.json"
            self.assertTrue(manifest_path.is_file())

            payload = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(payload["input_rows"], 2)
            self.assertEqual(
                payload["input_rows"],
                payload["accepted_rows"] + payload["quarantined_rows"],
            )
            self.assertEqual(first.to_dict(), second.to_dict())
            accepted_lines = (run_dir / "dwd" / "accepted.jsonl").read_text(
                encoding="utf-8"
            ).strip().splitlines()
            self.assertEqual(len(accepted_lines), payload["accepted_rows"])


if __name__ == "__main__":
    unittest.main()
