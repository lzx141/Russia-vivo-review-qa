import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from src.translation import translate_deepseek


class TestRuntimeCrawlerInputs(unittest.TestCase):
    def test_extract_all_raw_reads_runtime_crawler_output(self):
        """Catch CI crawler files being ignored because local raw files are absent."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pd.DataFrame(
                [
                    {
                        "author": "Anna",
                        "publishDate": "2026-08-15 10:00",
                        "rate": 5,
                        "content": "Отличный телефон",
                        "name": "Example Phone",
                        "URL": "https://www.wildberries.ru/example",
                        "siteName": "Wildberries",
                    }
                ]
            ).to_excel(root / "wildberries_reviews.xlsx", index=False)

            with (
                patch.object(translate_deepseek, "PROJECT_ROOT", str(root)),
                patch.object(translate_deepseek, "DATA_PATHS", {}),
            ):
                records = translate_deepseek.extract_all_raw()

        self.assertEqual(1, len(records))
        self.assertEqual("Отличный телефон", records[0]["review"])
        self.assertEqual("wildberries_reviews.xlsx", records[0]["source_file"])


if __name__ == "__main__":
    unittest.main()
