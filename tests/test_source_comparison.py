import unittest


class TestSourceComparison(unittest.TestCase):
    def setUp(self):
        self.records = [
            {
                "record_id": "p1-a",
                "product_id": "wildberries:1",
                "dataset_role": "business_primary",
                "text": "Очень хороший телефон",
                "rating": 5,
            },
            {
                "record_id": "p1-b",
                "product_id": "wildberries:1",
                "dataset_role": "business_primary",
                "text": "Плохая батарея",
                "rating": 2,
            },
            {
                "record_id": "e1-a",
                "product_id": "wildberries:1",
                "dataset_role": "external_validation",
                "text": "Есть ли NFC",
                "rating": None,
            },
            {
                "record_id": "e1-b",
                "product_id": "wildberries:1",
                "dataset_role": "external_validation",
                "text": "Какая гарантия",
                "rating": None,
            },
            {
                "record_id": "p2-only",
                "product_id": "wildberries:2",
                "dataset_role": "business_primary",
                "text": "Только основной источник",
                "rating": 4,
            },
        ]

    def test_matched_cohort_keeps_shared_products_and_balances_sources(self):
        from src.analysis.source_comparison import build_matched_cohort

        cohort = build_matched_cohort(self.records, max_per_product=10, seed=7)
        self.assertEqual({row["product_id"] for row in cohort}, {"wildberries:1"})
        counts = {}
        for row in cohort:
            counts[row["dataset_role"]] = counts.get(row["dataset_role"], 0) + 1
        self.assertEqual(counts, {"business_primary": 2, "external_validation": 2})

    def test_comparison_handles_question_dataset_without_ratings(self):
        from src.analysis.source_comparison import build_matched_cohort, compare_sources

        result = compare_sources(build_matched_cohort(self.records, seed=7), seed=7)
        self.assertEqual(result["sample_sizes"]["business_primary"], 2)
        self.assertEqual(result["sample_sizes"]["external_validation"], 2)
        self.assertIsNone(result["rating_comparison"])
        self.assertIn("not a randomized A/B test", result["limitations"])
        self.assertIn("rating comparison unavailable", result["limitations"])

    def test_empty_comparison_is_explicitly_unavailable(self):
        from src.analysis.source_comparison import compare_sources

        result = compare_sources([])
        self.assertEqual(result["status"], "unavailable")
        self.assertEqual(result["sample_sizes"], {})


if __name__ == "__main__":
    unittest.main()
