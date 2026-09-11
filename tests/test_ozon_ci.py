import os
import tempfile
import unittest
from unittest.mock import patch

import pandas as pd

from src.crawler import ozon_crawler


class TestOzonCrawlerCI(unittest.TestCase):
    def setUp(self):
        handle = tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False)
        handle.close()
        self.excel_path = handle.name
        pd.DataFrame(
            [
                {
                    "名称": "OZON",
                    "网址": "https://www.ozon.ru/product/example",
                    "机型": "Example Phone",
                }
            ]
        ).to_excel(self.excel_path, index=False, engine="openpyxl")

    def tearDown(self):
        if os.path.exists(self.excel_path):
            os.unlink(self.excel_path)

    def test_crawl_from_excel_raises_when_every_product_fails(self):
        """Catch the regression where CI stays green after every product crashes."""
        with patch.object(
            ozon_crawler,
            "crawl_ozon_reviews_by_url",
            side_effect=RuntimeError("browser session failed"),
        ):
            with self.assertRaisesRegex(RuntimeError, "all 1 OZON products failed"):
                ozon_crawler.crawl_from_excel(
                    self.excel_path,
                    start_date="2026-08-01",
                    end_date="2026-08-31",
                )

    def test_crawl_from_excel_raises_when_all_products_return_no_records(self):
        """Catch blocked/empty pages that return normally but add no target data."""
        with (
            patch.object(ozon_crawler, "crawl_ozon_reviews_by_url", return_value=[]),
            patch.object(ozon_crawler, "crawl_ozon_qa_by_url", return_value=[]),
        ):
            with self.assertRaisesRegex(RuntimeError, "produced 0 records"):
                ozon_crawler.crawl_from_excel(
                    self.excel_path,
                    start_date="2026-08-01",
                    end_date="2026-08-31",
                )


if __name__ == "__main__":
    unittest.main()
