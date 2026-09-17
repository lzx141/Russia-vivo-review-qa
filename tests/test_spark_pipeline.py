import os
import sys
import unittest


@unittest.skipUnless(
    __import__("importlib").util.find_spec("pyspark"), "pyspark is not installed"
)
@unittest.skipIf(
    sys.version_info >= (3, 14),
    "Run Spark worker tests with the documented Python 3.12 runtime",
)
class TestSparkPipeline(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ["PYSPARK_PYTHON"] = sys.executable
        from src.data_platform.spark_pipeline import create_spark_session

        cls.spark = create_spark_session("feedback-platform-tests", "local[1]")

    @classmethod
    def tearDownClass(cls):
        cls.spark.stop()

    def test_normalization_builds_quality_flags_and_month(self):
        from src.data_platform.spark_pipeline import normalize_spark_frame

        frame = self.spark.createDataFrame(
            [
                {
                    "data_type": "review",
                    "siteName": "Wildberries",
                    "URL": "https://www.wildberries.ru/catalog/123456/detail.aspx",
                    "name": "vivo V50",
                    "rate": "5",
                    "review": "Отличный телефон и батарея",
                    "publishDate": "2026-01-10",
                }
            ]
        )
        row = normalize_spark_frame(
            frame, "self_crawled", "business_primary", "run-test"
        ).collect()[0].asDict()
        self.assertEqual(row["product_id"], "wildberries:123456")
        self.assertEqual(row["event_month"], "2026-01")
        self.assertEqual(row["quality_score"], 100)
        self.assertTrue(row["is_text_eligible"])

    def test_layer_builder_separates_duplicates(self):
        from src.data_platform.spark_pipeline import build_layers, normalize_spark_frame

        frame = self.spark.createDataFrame(
            [
                {
                    "data_type": "review",
                    "siteName": "Wildberries",
                    "URL": "https://www.wildberries.ru/catalog/123456/detail.aspx",
                    "name": "vivo V50",
                    "rate": "5",
                    "review": "Отличный телефон",
                    "publishDate": "2026-01-10",
                },
                {
                    "data_type": "review",
                    "siteName": "WB",
                    "URL": "https://www.wildberries.ru/catalog/123456/detail.aspx",
                    "name": "vivo V50",
                    "rate": "5",
                    "review": " отличный  телефон ",
                    "publishDate": "2026-01-10",
                },
            ]
        )
        normalized = normalize_spark_frame(
            frame, "self_crawled", "business_primary", "run-test"
        )
        layers = build_layers(normalized)
        self.assertEqual(layers["dwd"].count(), 1)
        self.assertEqual(layers["quarantine"].count(), 1)
        self.assertEqual(layers["dws"].count(), 1)
        self.assertEqual(layers["ads"].count(), 1)

    def test_manifest_frame_is_built_from_jvm_range(self):
        from src.data_platform.spark_pipeline import manifest_frame

        frame = manifest_frame(
            self.spark,
            {"run_id": "run-test", "input_rows": 2, "quality_pass_rate": 100.0},
        )
        self.assertNotIn("PythonRDD", frame._jdf.queryExecution().logical().toString())
        self.assertEqual(frame.collect()[0]["run_id"], "run-test")


if __name__ == "__main__":
    unittest.main()
