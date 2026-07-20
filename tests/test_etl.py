"""
ETL 管道单元测试
"""
import os
import sys
import unittest
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class TestETLProcessor(unittest.TestCase):
    """ETL 处理器单元测试"""

    def setUp(self):
        from src.etl.etl import ETLProcessor
        self.etl = ETLProcessor()

    def test_parse_datetime_standard(self):
        """测试标准日期格式解析"""
        result = self.etl._parse_datetime("2026-01-15 14:30:00")
        self.assertEqual(result, "2026-01-15 14:30:00")

    def test_parse_datetime_russian(self):
        """测试俄语日期格式解析"""
        result = self.etl._parse_datetime("15.01.2026 14:30")
        self.assertEqual(result, "2026-01-15 14:30:00")

    def test_parse_datetime_empty(self):
        """测试空日期"""
        result = self.etl._parse_datetime(None)
        self.assertIsNone(result)

    def test_parse_datetime_invalid(self):
        """测试无效日期 — 应返回 None（安全处理）"""
        result = self.etl._parse_datetime("not-a-date")
        self.assertIsNone(result)

    def test_remove_duplicates_empty(self):
        """测试空数据去重"""
        result = self.etl._remove_duplicates([])
        self.assertEqual(result, [])

    def test_remove_duplicates_no_dup(self):
        """测试无重复数据"""
        data = [
            {"author": "user1", "content": "good"},
            {"author": "user2", "content": "bad"},
        ]
        result = self.etl._remove_duplicates(data)
        self.assertEqual(len(result), 2)

    def test_remove_duplicates_with_dup(self):
        """测试含重复数据去重"""
        data = [
            {"author": "user1", "content": "good", "name": "X", "SKU": "123", "URL": "url", "siteName": "OZON", "publishDate": "2026-01-01", "rate": "5"},
            {"author": "user1", "content": "good", "name": "X", "SKU": "123", "URL": "url", "siteName": "OZON", "publishDate": "2026-01-01", "rate": "5"},
            {"author": "user3", "content": "ok", "name": "Y", "SKU": "456", "URL": "url2", "siteName": "WB", "publishDate": "2026-01-02", "rate": "4"},
        ]
        result = self.etl._remove_duplicates(data)
        self.assertEqual(len(result), 2)

    def test_transform_reviews(self):
        """测试评论字段映射"""
        raw = [
            {"author": "测试用户", "content": "测试评论", "name": "iQOO Neo 10",
             "SKU": "SKU001", "URL": "https://ozon.ru/1", "siteName": "OZON"},
        ]
        result = self.etl.transform_reviews(raw)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["author"], "测试用户")


class TestDatabase(unittest.TestCase):
    """数据库操作测试（不依赖真实连接）"""

    def test_nan_to_none(self):
        from src.etl.database import Database
        import math
        self.assertIsNone(Database._nan_to_none(float("nan")))
        self.assertIsNone(Database._nan_to_none(None))
        self.assertEqual(Database._nan_to_none("test"), "test")
        self.assertEqual(Database._nan_to_none(0), 0)

    def test_hash_content(self):
        from src.etl.database import Database
        h1 = Database._hash_content("hello")
        h2 = Database._hash_content("hello")
        h3 = Database._hash_content("world")
        self.assertEqual(h1, h2)
        self.assertNotEqual(h1, h3)
        self.assertEqual(len(h1), 64)  # SHA256 hex


class TestConfig(unittest.TestCase):
    """配置模块测试"""

    def test_db_config_structure(self):
        from config.config import DB_CONFIG
        required_keys = ["host", "port", "user", "password", "database"]
        for key in required_keys:
            self.assertIn(key, DB_CONFIG)

    def test_data_paths_structure(self):
        from config.config import DATA_PATHS
        expected_keys = ["ozon_reviews", "ozon_questions", "wildberries_reviews", "wildberries_questions"]
        for key in expected_keys:
            self.assertIn(key, DATA_PATHS)
            self.assertIsInstance(DATA_PATHS[key], list)


if __name__ == "__main__":
    unittest.main(verbosity=2)
