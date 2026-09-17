import tempfile
import unittest
from pathlib import Path


class TestPlatformCli(unittest.TestCase):
    def test_parse_input_specs_supports_path_adapter_pairs(self):
        from src.run_pipeline import parse_trusted_inputs

        specs = parse_trusted_inputs(["tests/fixtures/self_review.csv:self"])
        self.assertEqual(specs[0].path, Path("tests/fixtures/self_review.csv"))
        self.assertEqual(specs[0].adapter, "self")

    def test_parse_input_specs_rejects_missing_adapter(self):
        from src.run_pipeline import parse_trusted_inputs

        with self.assertRaises(ValueError):
            parse_trusted_inputs(["tests/fixtures/self_review.csv"])

    def test_quality_audit_writes_machine_readable_result(self):
        from scripts.run_quality_audit import audit_jsonl

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "accepted.jsonl"
            target = root / "audit.json"
            source.write_text(
                '{"quality_score": 90, "is_text_eligible": true}\n'
                '{"quality_score": 30, "is_text_eligible": false}\n',
                encoding="utf-8",
            )
            result = audit_jsonl(source, target, minimum_pass_rate=40)
            self.assertEqual(result["status"], "passed")
            self.assertEqual(result["text_quality_pass_rate"], 50.0)
            self.assertTrue(target.is_file())


if __name__ == "__main__":
    unittest.main()
