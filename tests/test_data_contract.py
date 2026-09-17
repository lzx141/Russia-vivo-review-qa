import unittest


class TestIdentity(unittest.TestCase):
    def test_normalizes_platform_aliases(self):
        from src.data_platform.identity import normalize_platform

        self.assertEqual(normalize_platform("WB"), "wildberries")
        self.assertEqual(normalize_platform("OZON.ru"), "ozon")
        self.assertEqual(normalize_platform("Яндекс Маркет"), "yandex_market")

    def test_extracts_wildberries_nm_id(self):
        from src.data_platform.identity import extract_source_product_id

        self.assertEqual(
            extract_source_product_id(
                "https://www.wildberries.ru/catalog/123456/detail.aspx"
            ),
            "123456",
        )

    def test_product_id_prefers_platform_identifier(self):
        from src.data_platform.identity import build_product_id

        result = build_product_id("wildberries", "123456", "vivo V50")
        self.assertEqual(
            result,
            ("wildberries:123456", "source_product_id", 1.0),
        )

    def test_product_id_falls_back_to_normalized_name(self):
        from src.data_platform.identity import build_product_id

        product_id, method, confidence = build_product_id("ozon", None, " Vivo V50 5G ")
        self.assertEqual(product_id, "ozon:name:vivo-v50-5g")
        self.assertEqual(method, "normalized_name")
        self.assertEqual(confidence, 0.65)


class TestContract(unittest.TestCase):
    def test_contract_contains_governance_fields(self):
        from src.data_platform.contract import load_contract

        contract = load_contract()
        fields = set(contract["fields"])
        self.assertTrue(
            {
                "record_id",
                "source_dataset",
                "pipeline_run_id",
                "quality_score",
                "is_rating_eligible",
                "is_text_eligible",
            }.issubset(fields)
        )

    def test_canonical_record_has_stable_id(self):
        from src.data_platform.contract import canonical_record

        raw = {
            "platform": "WB",
            "url": "https://www.wildberries.ru/catalog/123456/detail.aspx",
            "product_name": "vivo V50",
            "rating": "5",
            "text": "Отличный телефон",
            "event_date": "2026-01-02",
        }
        first = canonical_record(raw, "self_crawled", "review")
        second = canonical_record(raw, "self_crawled", "review")
        self.assertEqual(first["record_id"], second["record_id"])
        self.assertEqual(first["product_id"], "wildberries:123456")
        self.assertEqual(first["rating"], 5.0)
        self.assertEqual(first["record_type"], "review")


if __name__ == "__main__":
    unittest.main()
