import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch


class TestExternalWildberries(unittest.TestCase):
    def test_brand_filter_uses_bound_parameters(self):
        from src.data_platform.external_wb import build_question_filter

        where_sql, params = build_question_filter(["vivo", "iQOO"])
        self.assertNotIn("vivo", where_sql.casefold())
        self.assertNotIn("iqoo", where_sql.casefold())
        self.assertEqual(where_sql.count("?"), 2)
        self.assertEqual(params, ["vivo", "iqoo"])

    @patch("requests.get")
    def test_fetch_parquet_urls_filters_split(self, get):
        from src.data_platform.external_wb import fetch_parquet_urls

        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {
            "parquet_files": [
                {"split": "train", "url": "https://example/train.parquet"},
                {"split": "test", "url": "https://example/test.parquet"},
            ]
        }
        get.return_value = response
        self.assertEqual(
            fetch_parquet_urls("nyuuzyou/wb-questions"),
            ["https://example/train.parquet"],
        )

    def test_extract_subset_writes_parquet_and_metadata(self):
        import duckdb

        from src.data_platform.external_wb import extract_question_subset

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "source.parquet"
            output = root / "subset.parquet"
            metadata = root / "subset.metadata.json"
            connection = duckdb.connect()
            connection.execute(
                """
                CREATE TABLE questions AS
                SELECT * FROM (VALUES
                    (1, 101, 'vivo V50', 'vivo', 'Есть NFC?', 'Да'),
                    (2, 102, 'Other phone', 'Other', 'Есть NFC?', 'Нет')
                ) t(imtId, nmId, productName, brandName, question, answer)
                """
            )
            connection.execute(f"COPY questions TO '{source.as_posix()}' (FORMAT PARQUET)")
            connection.close()

            result = extract_question_subset(
                [str(source)],
                output,
                brands=["vivo"],
                limit=100,
                metadata_path=metadata,
                dataset="nyuuzyou/wb-questions",
            )
            self.assertEqual(result["row_count"], 1)
            self.assertTrue(output.is_file())
            saved = json.loads(metadata.read_text(encoding="utf-8"))
            self.assertEqual(saved["license"], "CC0-1.0")
            self.assertEqual(saved["filters"]["brands"], ["vivo"])


if __name__ == "__main__":
    unittest.main()
