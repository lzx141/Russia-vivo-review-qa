import unittest


class TestSourceAdapters(unittest.TestCase):
    def test_self_collected_adapter_maps_review(self):
        from src.data_platform.adapters import SelfCollectedAdapter

        record = SelfCollectedAdapter().adapt(
            {
                "data_type": "review",
                "siteName": "Wildberries",
                "URL": "https://www.wildberries.ru/catalog/123456/detail.aspx",
                "name": "vivo V50",
                "rate": "5",
                "review": "Отличный телефон",
                "publishDate": "2026-01-10",
            },
            "wildberries_reviews.xlsx",
            run_id="test-run",
        )
        self.assertEqual(record["source_dataset"], "self_crawled")
        self.assertEqual(record["dataset_role"], "business_primary")
        self.assertEqual(record["product_id"], "wildberries:123456")
        self.assertEqual(record["record_type"], "review")

    def test_public_question_adapter_keeps_license_and_source_id(self):
        from src.data_platform.adapters import PublicWbQuestionAdapter

        record = PublicWbQuestionAdapter().adapt(
            {
                "imtId": 1,
                "nmId": 123456,
                "productName": "vivo V50",
                "brandName": "vivo",
                "question": "Есть ли NFC?",
                "answer": "Да.",
            },
            "wb-questions.parquet",
            run_id="test-run",
        )
        self.assertEqual(record["source_dataset"], "nyuuzyou/wb-questions")
        self.assertEqual(record["dataset_role"], "external_validation")
        self.assertEqual(record["license"], "CC0-1.0")
        self.assertEqual(record["product_id"], "wildberries:123456")


if __name__ == "__main__":
    unittest.main()

