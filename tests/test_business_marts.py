import unittest


class TestBusinessMarts(unittest.TestCase):
    def test_marts_use_metric_specific_eligibility_and_keep_denominators(self):
        from src.analysis.business_marts import build_business_marts

        records = [
            {
                "record_id": "1",
                "source_dataset": "self_crawled",
                "dataset_role": "business_primary",
                "platform": "wildberries",
                "product_id": "wildberries:1",
                "event_date": "2026-01-10",
                "rating": 5,
                "text": "Отличный телефон",
                "quality_score": 95,
                "is_rating_eligible": True,
                "is_text_eligible": True,
                "is_trend_eligible": True,
                "is_product_eligible": True,
            },
            {
                "record_id": "2",
                "source_dataset": "self_crawled",
                "dataset_role": "business_primary",
                "platform": "wildberries",
                "product_id": "wildberries:1",
                "event_date": None,
                "rating": None,
                "text": None,
                "quality_score": 35,
                "is_rating_eligible": False,
                "is_text_eligible": False,
                "is_trend_eligible": False,
                "is_product_eligible": True,
            },
        ]
        marts = build_business_marts(records)
        source = marts["source_summary"][0]
        self.assertEqual(source["total_records"], 2)
        self.assertEqual(source["rating_eligible_records"], 1)
        self.assertEqual(source["text_eligible_records"], 1)
        self.assertEqual(source["quality_pass_rate"], 50.0)
        self.assertEqual(marts["monthly_trend"][0]["month"], "2026-01")
        self.assertEqual(marts["monthly_trend"][0]["eligible_records"], 1)
        product = marts["product_summary"][0]
        self.assertEqual(product["total_records"], 2)
        self.assertEqual(product["eligible_records"], 2)

    def test_empty_input_returns_named_empty_marts(self):
        from src.analysis.business_marts import build_business_marts

        marts = build_business_marts([])
        self.assertEqual(
            set(marts),
            {"quality_summary", "source_summary", "platform_summary", "product_summary", "monthly_trend"},
        )
        self.assertTrue(all(not rows for rows in marts.values()))


if __name__ == "__main__":
    unittest.main()
