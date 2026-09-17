import unittest


class TestDeduplication(unittest.TestCase):
    def test_cross_source_duplicate_keeps_higher_quality_record(self):
        from src.data_platform.deduplication import deduplicate_records

        low_quality = {
            "record_id": "low",
            "product_id": "wildberries:1",
            "record_type": "review",
            "text": "Отличный телефон",
            "rating": 5,
            "quality_score": 70,
        }
        high_quality = {
            **low_quality,
            "record_id": "high",
            "quality_score": 95,
            "answer": "Спасибо",
        }
        accepted, rejected = deduplicate_records([low_quality, high_quality])
        self.assertEqual(accepted[0]["record_id"], "high")
        self.assertEqual(rejected[0]["duplicate_of"], "high")
        self.assertIn("duplicate", rejected[0]["quality_issues"])

    def test_normalized_text_deduplicates_case_and_whitespace(self):
        from src.data_platform.deduplication import record_fingerprint

        first = {
            "product_id": "wildberries:1",
            "record_type": "review",
            "text": "  Очень   хорошо ",
            "rating": 5,
        }
        second = {**first, "text": "очень хорошо"}
        self.assertEqual(record_fingerprint(first), record_fingerprint(second))

    def test_different_products_are_not_duplicates(self):
        from src.data_platform.deduplication import deduplicate_records

        records = [
            {
                "record_id": "a",
                "product_id": "wildberries:1",
                "record_type": "review",
                "text": "Хорошо",
                "rating": 5,
                "quality_score": 90,
            },
            {
                "record_id": "b",
                "product_id": "wildberries:2",
                "record_type": "review",
                "text": "Хорошо",
                "rating": 5,
                "quality_score": 90,
            },
        ]
        accepted, rejected = deduplicate_records(records)
        self.assertEqual(len(accepted), 2)
        self.assertEqual(rejected, [])


if __name__ == "__main__":
    unittest.main()
