"""
ETL 管道 — 爬取 → 转换 → 加载 → 翻译数据入库

优化：
  ✓ logging 替代 print
  ✓ 修复 `extract_excel_data` 路径拼接
  ✓ tqdm 进度条
  ✓ 翻译数据自动入库
  ✓ 更细粒度的异常处理
"""
import logging
import os
import sys
import time

import pandas as pd

sys.path.append(os.path.join(os.path.dirname(__file__), "..", ".."))
from src.etl.database import Database
from config.config import DATA_PATHS, MERGED_TRANSLATED_CSV, PROJECT_ROOT

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


class ETLProcessor:
    def __init__(self):
        self.db = Database()
        self.total_reviews = 0
        self.total_questions = 0

    # ── 提取 ────────────────────────────────────────────────

    def extract_excel_data(self, rel_paths):
        """
        从多个 Excel 文件提取数据
        修复：rel_paths 相对于 PROJECT_ROOT，而非 __file__
        """
        all_data = []
        for rel_path in rel_paths:
            full_path = os.path.join(PROJECT_ROOT, rel_path)
            if not os.path.exists(full_path):
                logger.warning("文件不存在: %s", full_path)
                continue

            try:
                df = pd.read_excel(full_path, engine="openpyxl", dtype=str)
                # 标记来源文件
                df["source_file"] = os.path.basename(rel_path)
                data = df.to_dict("records")
                all_data.extend(data)
                logger.info("  ✓ %s → %d 行", rel_path, len(data))
            except Exception as e:
                logger.error("  ✗ 读取失败 %s: %s", rel_path, e)

        return all_data

    # ── 转换 ────────────────────────────────────────────────

    def _parse_datetime(self, datetime_str):
        if not datetime_str:
            return None
        try:
            formats = [
                "%Y-%m-%d %H:%M",
                "%Y-%m-%d %H:%M:%S",
                "%Y/%m/%d %H:%M",
                "%d.%m.%Y %H:%M",
            ]
            for fmt in formats:
                try:
                    return pd.to_datetime(datetime_str, format=fmt).strftime("%Y-%m-%d %H:%M:%S")
                except (ValueError, TypeError):
                    continue
            return pd.to_datetime(datetime_str, errors="coerce").strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            return None

    def _remove_duplicates(self, data):
        """基于完整字段去重"""
        seen = set()
        unique = []
        for item in data:
            fields = [
                item.get("author", ""),
                item.get("publishDate", ""),
                item.get("rate", ""),
                item.get("content", ""),
                item.get("question", ""),
                item.get("name", ""),
                item.get("SKU", ""),
                item.get("URL", ""),
                item.get("siteName", ""),
            ]
            key = tuple(str(f) if f is not None else "" for f in fields)
            if key not in seen:
                seen.add(key)
                unique.append(item)
        logger.info("  去重: %d → %d 条", len(data), len(unique))
        return unique

    def transform_reviews(self, raw_data):
        transformed = []
        for item in raw_data:
            record = {
                "author": item.get("author", item.get("Author", "")),
                "publishDate": self._parse_datetime(
                    item.get("publishDate", item.get("PublishDate", ""))
                ),
                "rate": item.get("rate", item.get("Rate", item.get("rating", ""))),
                "content": item.get("content", item.get("Content", "")),
                "name": item.get("name", item.get("Name", "")),
                "SKU": item.get("SKU", item.get("sku", "")),
                "URL": item.get("URL", item.get("url", "")),
                "siteName": item.get("siteName", item.get("SiteName", "")),
            }
            transformed.append(record)

        unique = self._remove_duplicates(transformed)
        logger.info("  评论转换: %d → %d", len(raw_data), len(unique))
        return unique

    def transform_questions(self, raw_data):
        transformed = []
        for item in raw_data:
            record = {
                "author": item.get("author", item.get("Author", "")),
                "publishDate": self._parse_datetime(
                    item.get("publishDate", item.get("PublishDate", ""))
                ),
                "question": item.get("question", item.get("Question", "")),
                "content": item.get("content", item.get("Content", item.get("answer", ""))),
                "name": item.get("name", item.get("Name", "")),
                "SKU": item.get("SKU", item.get("sku", "")),
                "URL": item.get("URL", item.get("url", "")),
                "siteName": item.get("siteName", item.get("SiteName", "")),
            }
            transformed.append(record)

        unique = self._remove_duplicates(transformed)
        logger.info("  问答转换: %d → %d", len(raw_data), len(unique))
        return unique

    # ── 加载 ────────────────────────────────────────────────

    def load_data(self, reviews_data, questions_data):
        from tqdm import tqdm

        batch_size = 1000

        # 评论
        if reviews_data:
            for i in tqdm(
                range(0, len(reviews_data), batch_size),
                desc="加载评论",
                unit="批",
            ):
                batch = reviews_data[i : i + batch_size]
                count = self.db.insert_reviews_batch(batch)
                self.total_reviews += count

        # 问答
        if questions_data:
            for i in tqdm(
                range(0, len(questions_data), batch_size),
                desc="加载问答",
                unit="批",
            ):
                batch = questions_data[i : i + batch_size]
                count = self.db.insert_questions_batch(batch)
                self.total_questions += count

    # ── 翻译数据加载 ─────────────────────────────────────

    def load_translated_csv(self, csv_path: str = None, batch_size: int = 2000):
        """将翻译后的 CSV 加载到 translated_records 表"""
        path = csv_path or MERGED_TRANSLATED_CSV
        if not os.path.exists(path):
            logger.warning("翻译 CSV 不存在: %s，跳过", path)
            return

        logger.info("加载翻译数据: %s", path)
        df = pd.read_csv(path, encoding="utf-8", dtype=str, low_memory=False)
        df = df.where(df.notna(), None)  # NaN → None

        records = df.to_dict("records")
        total = len(records)

        existing = self.db.get_table_count("translated_records")
        if existing >= total:
            logger.info("翻译数据已全部入库 (%d 条)", existing)
            return

        # 从断点继续
        if existing > 0:
            records = records[existing:]
            logger.info("断点续传: 剩余 %d 条", len(records))

        from tqdm import tqdm

        inserted = 0
        for i in tqdm(range(0, len(records), batch_size), desc="翻译数据入库"):
            batch = records[i : i + batch_size]
            inserted += self.db.insert_translated_records_batch(batch)

        logger.info("翻译数据入库完成，共 %d 条", inserted)

    # ── ETL 主流程 ──────────────────────────────────────────

    def run(self, load_translated: bool = True):
        logger.info("=" * 50)
        logger.info("ETL 管道启动")
        logger.info("=" * 50)

        try:
            self.db.connect()
            self.db.create_tables()

            # 提取 + 转换 + 加载 评论
            logger.info("\n[1/3] 处理评论数据...")
            all_reviews = []
            t0 = time.time()
            for group in ["ozon_reviews", "wildberries_reviews"]:
                all_reviews.extend(self.extract_excel_data(DATA_PATHS[group]))
            transformed = self.transform_reviews(all_reviews)
            self.load_data(transformed, [])
            logger.info("  ✔ 评论完成 (%d 条, %.1fs)", self.total_reviews, time.time() - t0)

            # 提取 + 转换 + 加载 问答
            logger.info("\n[2/3] 处理问答数据...")
            all_questions = []
            t0 = time.time()
            for group in ["ozon_questions", "wildberries_questions"]:
                all_questions.extend(self.extract_excel_data(DATA_PATHS[group]))
            transformed_q = self.transform_questions(all_questions)
            self.load_data([], transformed_q)
            logger.info("  ✔ 问答完成 (%d 条, %.1fs)", self.total_questions, time.time() - t0)

            # 翻译数据入库
            if load_translated:
                logger.info("\n[3/3] 加载翻译数据...")
                t0 = time.time()
                self.load_translated_csv()
                logger.info("  ✔ 翻译数据完成 (%.1fs)", time.time() - t0)

            # 汇总
            logger.info("\n" + "=" * 50)
            logger.info("ETL 完成!")
            logger.info("  评论: %d 条", self.total_reviews)
            logger.info("  问答: %d 条", self.total_questions)
            logger.info("  翻译: %d 条", self.db.get_table_count("translated_records"))
            logger.info("=" * 50)

        except Exception as e:
            logger.error("ETL 过程异常: %s", e)
            raise
        finally:
            if self.db.connection and self.db.connection.is_connected():
                self.db.disconnect()


if __name__ == "__main__":
    etl = ETLProcessor()
    etl.run()
