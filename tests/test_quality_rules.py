import unittest


class TestQualityRules(unittest.TestCase):
    def test_rating_only_record_is_not_text_eligible(self):
        from src.data_platform.quality import assess_quality

        assessed = assess_quality(
            {
                "record_type": "review",
                "rating": 5,
                "text": "",
                "event_date": "2026-01-01",
                "product_match_confidence": 1.0,
                "duplicate_of": None,
            }
        )
        self.assertTrue(assessed["is_rating_eligible"])
        self.assertFalse(assessed["is_text_eligible"])
        self.assertIn("missing_text", assessed["quality_issues"])

    def test_complete_russian_review_is_eligible_for_all_metrics(self):
        from src.data_platform.quality import assess_quality

        assessed = assess_quality(
            {
                "record_type": "review",
                "rating": 4,
                "text": "Отличный телефон и хорошая батарея",
                "event_date": "2026-01-01",
                "product_match_confidence": 1.0,
                "duplicate_of": None,
            }
        )
        self.assertEqual(assessed["quality_score"], 100)
        self.assertTrue(assessed["is_rating_eligible"])
        self.assertTrue(assessed["is_text_eligible"])
        self.assertTrue(assessed["is_trend_eligible"])
        self.assertTrue(assessed["is_product_eligible"])

    def test_invalid_rating_is_reported(self):
        from src.data_platform.quality import assess_quality

        assessed = assess_quality(
            {
                "record_type": "review",
                "rating": 0,
                "text": "Плохой товар",
                "event_date": "2026-01-01",
                "product_match_confidence": 1.0,
            }
        )
        self.assertFalse(assessed["is_rating_eligible"])
        self.assertIn("invalid_rating", assessed["quality_issues"])


if __name__ == "__main__":
    unittest.main()

