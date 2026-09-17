import unittest


class TestPipelineBenchmark(unittest.TestCase):
    def test_benchmark_compares_same_input_without_accuracy_claims(self):
        from src.analysis.pipeline_benchmark import compare_pipeline_variants

        records = [
            {
                "record_id": "good",
                "record_type": "review",
                "product_id": "wildberries:1",
                "product_match_method": "source_product_id",
                "product_match_confidence": 1.0,
                "event_date": "2026-01-01",
                "rating": 5,
                "text": "Очень хороший телефон",
            },
            {
                "record_id": "duplicate",
                "record_type": "review",
                "product_id": "wildberries:1",
                "product_match_method": "source_product_id",
                "product_match_confidence": 1.0,
                "event_date": "2026-01-01",
                "rating": 5,
                "text": "Очень хороший телефон",
            },
            {
                "record_id": "bad",
                "record_type": "review",
                "product_id": "unresolved:x",
                "product_match_method": "unresolved",
                "product_match_confidence": 0.0,
                "event_date": None,
                "rating": None,
                "text": "",
            },
        ]
        result = compare_pipeline_variants(records)
        self.assertEqual(result["input_records"], 3)
        self.assertEqual(result["baseline"]["retained_records"], 3)
        self.assertEqual(result["governed"]["retained_records"], 1)
        self.assertEqual(result["governed"]["duplicate_records"], 1)
        self.assertNotIn("accuracy", result)
        self.assertIn("not an accuracy evaluation", result["limitations"])


if __name__ == "__main__":
    unittest.main()
