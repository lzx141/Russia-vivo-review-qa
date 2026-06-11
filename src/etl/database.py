"""
数据库操作封装
支持：原始数据表 + 翻译数据表 + 分析缓存表 + 统计查询
"""
import hashlib
import json
import logging
import sys
import os

import mysql.connector
from mysql.connector import Error


sys.path.append(os.path.join(os.path.dirname(__file__), "..", ".."))
from config.config import DB_CONFIG

logger = logging.getLogger(__name__)


class Database:
    def __init__(self):
        self.connection = None
        self.cursor = None

    # ── 连接管理 ──────────────────────────────────────────────

    def connect(self):
        """建立数据库连接"""
        try:
            self.connection = mysql.connector.connect(
                host=DB_CONFIG["host"],
                port=DB_CONFIG["port"],
                user=DB_CONFIG["user"],
                password=DB_CONFIG["password"],
                database=DB_CONFIG["database"],
                charset=DB_CONFIG["charset"],
            )
            if self.connection.is_connected():
                self.cursor = self.connection.cursor(buffered=True)
                logger.info("数据库连接成功")
        except Error as e:
            logger.error(f"数据库连接失败: {e}")
            raise

    def disconnect(self):
        """关闭数据库连接"""
        if self.connection and self.connection.is_connected():
            if self.cursor:
                self.cursor.close()
            self.connection.close()
            logger.info("数据库连接已关闭")

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.disconnect()

    # ── 底层操作 ──────────────────────────────────────────────

    def execute_query(self, query, params=None):
        """执行 SQL（INSERT/UPDATE/CREATE 等）"""
        try:
            self.cursor.execute(query, params or ())
            self.connection.commit()
            return self.cursor.rowcount
        except Error as e:
            logger.error(f"SQL 执行失败: {e}")
            self.connection.rollback()
            raise

    def execute_many(self, query, params_list):
        """批量执行"""
        if not params_list:
            return 0
        try:
            self.cursor.executemany(query, params_list)
            self.connection.commit()
            return len(params_list)
        except Error as e:
            logger.error(f"批量执行失败: {e}")
            self.connection.rollback()
            raise

    def fetch_query(self, query, params=None):
        """执行查询并返回所有结果"""
        try:
            self.cursor.execute(query, params or ())
            return self.cursor.fetchall()
        except Error as e:
            logger.error(f"SQL 查询失败: {e}")
            raise

    def fetch_one(self, query, params=None):
        """查询单条结果"""
        try:
            self.cursor.execute(query, params or ())
            return self.cursor.fetchone()
        except Error as e:
            logger.error(f"SQL 查询失败: {e}")
            raise

    # ════════════════════════════════════════════════════════════
    # 表创建
    # ════════════════════════════════════════════════════════════

    def create_tables(self):
        """创建所有表（幂等）"""
        self._create_reviews_table()
        self._create_questions_table()
        self._create_translated_records_table()
        self._create_analysis_cache_table()
        logger.info("所有表创建/验证完毕")

    def _create_reviews_table(self):
        sql = """
        CREATE TABLE IF NOT EXISTS reviews (
            id INT AUTO_INCREMENT PRIMARY KEY,
            author VARCHAR(255) DEFAULT NULL,
            publish_date DATETIME DEFAULT NULL,
            rate INT DEFAULT NULL,
            content TEXT DEFAULT NULL,
            name VARCHAR(255) DEFAULT NULL,
            sku VARCHAR(255) DEFAULT NULL,
            url TEXT DEFAULT NULL,
            site_name VARCHAR(50) DEFAULT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            INDEX idx_site_name (site_name),
            INDEX idx_publish_date (publish_date),
            INDEX idx_name (name)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
        """
        self.execute_query(sql)

    def _create_questions_table(self):
        sql = """
        CREATE TABLE IF NOT EXISTS questions (
            id INT AUTO_INCREMENT PRIMARY KEY,
            author VARCHAR(255) DEFAULT NULL,
            publish_date DATETIME DEFAULT NULL,
            question TEXT DEFAULT NULL,
            content TEXT DEFAULT NULL,
            name VARCHAR(255) DEFAULT NULL,
            sku VARCHAR(255) DEFAULT NULL,
            url TEXT DEFAULT NULL,
            site_name VARCHAR(50) DEFAULT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            INDEX idx_site_name (site_name),
            INDEX idx_publish_date (publish_date),
            INDEX idx_name (name)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
        """
        self.execute_query(sql)

    def _create_translated_records_table(self):
        """翻译后数据统一存储表"""
        sql = """
        CREATE TABLE IF NOT EXISTS translated_records (
            id BIGINT AUTO_INCREMENT PRIMARY KEY,
            data_type VARCHAR(20) NOT NULL COMMENT 'review 或 qa',
            source_file VARCHAR(255) DEFAULT NULL,
            author VARCHAR(255) DEFAULT NULL,
            publish_date DATETIME DEFAULT NULL,
            rate INT DEFAULT NULL,
            question TEXT DEFAULT NULL COMMENT '原始俄语问题',
            answer TEXT DEFAULT NULL COMMENT '原始俄语回答',
            review TEXT DEFAULT NULL COMMENT '原始俄语评论',
            name VARCHAR(255) DEFAULT NULL,
            sku VARCHAR(255) DEFAULT NULL,
            url TEXT DEFAULT NULL,
            site_name VARCHAR(50) DEFAULT NULL,
            question_zh TEXT DEFAULT NULL COMMENT '中文翻译-问题',
            question_en TEXT DEFAULT NULL COMMENT '英文翻译-问题',
            answer_zh TEXT DEFAULT NULL COMMENT '中文翻译-回答',
            answer_en TEXT DEFAULT NULL COMMENT '英文翻译-回答',
            review_zh TEXT DEFAULT NULL COMMENT '中文翻译-评论',
            review_en TEXT DEFAULT NULL COMMENT '英文翻译-评论',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            INDEX idx_data_type (data_type),
            INDEX idx_site_name (site_name),
            INDEX idx_publish_date (publish_date),
            INDEX idx_name (name),
            INDEX idx_rate (rate)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
        """
        self.execute_query(sql)

    def _create_analysis_cache_table(self):
        """LLM 分析缓存表，避免重复调用 API"""
        sql = """
        CREATE TABLE IF NOT EXISTS analysis_cache (
            id BIGINT AUTO_INCREMENT PRIMARY KEY,
            content_hash VARCHAR(64) NOT NULL COMMENT '输入内容的 SHA256',
            analysis_type VARCHAR(50) NOT NULL COMMENT 'sentiment / intent / ner / root_cause / summary',
            model_name VARCHAR(50) DEFAULT NULL,
            result JSON NOT NULL COMMENT '分析结果 JSON',
            tokens_used INT DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE KEY uk_content_analysis (content_hash, analysis_type)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
        """
        self.execute_query(sql)

    # ════════════════════════════════════════════════════════════
    # 原始数据插入（向后兼容）
    # ════════════════════════════════════════════════════════════

    def insert_review(self, review):
        sql = """
        INSERT INTO reviews (author, publish_date, rate, content, name, sku, url, site_name)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """
        params = (
            review.get("author"),
            review.get("publishDate"),
            review.get("rate"),
            review.get("content"),
            review.get("name"),
            review.get("SKU"),
            review.get("URL"),
            review.get("siteName"),
        )
        self.execute_query(sql, params)

    def insert_question(self, question):
        sql = """
        INSERT INTO questions (author, publish_date, question, content, name, sku, url, site_name)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """
        params = (
            question.get("author"),
            question.get("publishDate"),
            question.get("question"),
            question.get("content"),
            question.get("name"),
            question.get("SKU"),
            question.get("URL"),
            question.get("siteName"),
        )
        self.execute_query(sql, params)

    def insert_reviews_batch(self, reviews):
        if not reviews:
            return 0
        sql = """
        INSERT INTO reviews (author, publish_date, rate, content, name, sku, url, site_name)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """
        params = [
            (
                r.get("author"),
                r.get("publishDate"),
                r.get("rate"),
                r.get("content"),
                r.get("name"),
                r.get("SKU"),
                r.get("URL"),
                r.get("siteName"),
            )
            for r in reviews
        ]
        return self.execute_many(sql, params)

    def insert_questions_batch(self, questions):
        if not questions:
            return 0
        sql = """
        INSERT INTO questions (author, publish_date, question, content, name, sku, url, site_name)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """
        params = [
            (
                q.get("author"),
                q.get("publishDate"),
                q.get("question"),
                q.get("content"),
                q.get("name"),
                q.get("SKU"),
                q.get("URL"),
                q.get("siteName"),
            )
            for q in questions
        ]
        return self.execute_many(sql, params)

    # ════════════════════════════════════════════════════════════
    # 翻译数据插入
    # ════════════════════════════════════════════════════════════

    @staticmethod
    def _nan_to_none(v):
        """将 float NaN / NaT 转为 None"""
        if v is None:
            return None
        if isinstance(v, float):
            import math
            if math.isnan(v):
                return None
        return v

    def insert_translated_record(self, record: dict) -> int:
        """插入一条翻译记录"""
        sql = """
        INSERT INTO translated_records
            (data_type, source_file, author, publish_date, rate,
             question, answer, review, name, sku, url, site_name,
             question_zh, question_en, answer_zh, answer_en, review_zh, review_en)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        params = tuple(
            self._nan_to_none(record.get(k))
            for k in [
                "data_type", "source_file", "author", "publishDate", "rate",
                "question", "answer", "review", "name", "SKU", "URL", "siteName",
                "question_zh", "question_en", "answer_zh", "answer_en", "review_zh", "review_en",
            ]
        )
        return self.execute_query(sql, params)

    def insert_translated_records_batch(self, records: list) -> int:
        """批量插入翻译记录"""
        if not records:
            return 0
        sql = """
        INSERT INTO translated_records
            (data_type, source_file, author, publish_date, rate,
             question, answer, review, name, sku, url, site_name,
             question_zh, question_en, answer_zh, answer_en, review_zh, review_en)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        keys = [
            "data_type", "source_file", "author", "publishDate", "rate",
            "question", "answer", "review", "name", "SKU", "URL", "siteName",
            "question_zh", "question_en", "answer_zh", "answer_en", "review_zh", "review_en",
        ]
        params = [tuple(self._nan_to_none(rec.get(k)) for k in keys) for rec in records]
        return self.execute_many(sql, params)

    # ════════════════════════════════════════════════════════════
    # 分析缓存
    # ════════════════════════════════════════════════════════════

    @staticmethod
    def _hash_content(content: str) -> str:
        return hashlib.sha256(content.encode("utf-8")).hexdigest()

    def get_cached_analysis(self, content: str, analysis_type: str) -> dict | None:
        """获取缓存的分析结果"""
        content_hash = self._hash_content(content)
        row = self.fetch_one(
            "SELECT result FROM analysis_cache WHERE content_hash=%s AND analysis_type=%s",
            (content_hash, analysis_type),
        )
        if row:
            try:
                return json.loads(row[0])
            except (json.JSONDecodeError, TypeError):
                return None
        return None

    def save_analysis_cache(
        self, content: str, analysis_type: str, result: dict, model_name: str = None, tokens_used: int = 0
    ):
        """保存分析结果到缓存"""
        content_hash = self._hash_content(content)
        sql = """
        INSERT INTO analysis_cache (content_hash, analysis_type, model_name, result, tokens_used)
        VALUES (%s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE result=%s, model_name=%s, tokens_used=%s
        """
        result_json = json.dumps(result, ensure_ascii=False)
        self.execute_query(
            sql,
            (content_hash, analysis_type, model_name, result_json, tokens_used,
             result_json, model_name, tokens_used),
        )

    def get_cache_stats(self) -> dict:
        """获取缓存统计"""
        rows = self.fetch_query(
            "SELECT analysis_type, COUNT(*), SUM(tokens_used) FROM analysis_cache GROUP BY analysis_type"
        )
        return {r[0]: {"count": r[1], "tokens": r[2] or 0} for r in rows}

    # ════════════════════════════════════════════════════════════
    # 统计查询（供 generate_stats.py 使用）
    # ════════════════════════════════════════════════════════════

    def get_kpi_stats(self) -> dict:
        """获取 KPI 概览数据"""
        total = self.fetch_one("SELECT COUNT(*) FROM translated_records")[0]
        reviews = self.fetch_one(
            "SELECT COUNT(*) FROM translated_records WHERE data_type='review'"
        )[0]
        qa_count = self.fetch_one(
            "SELECT COUNT(*) FROM translated_records WHERE data_type='qa'"
        )[0]
        product_count = self.fetch_one(
            "SELECT COUNT(DISTINCT name) FROM translated_records"
        )[0]
        sku_count = self.fetch_one(
            "SELECT COUNT(DISTINCT sku) FROM translated_records WHERE sku IS NOT NULL AND sku != ''"
        )[0]
        user_count = self.fetch_one(
            "SELECT COUNT(DISTINCT author) FROM translated_records WHERE author IS NOT NULL AND author != ''"
        )[0]

        avg = self.fetch_one(
            "SELECT AVG(rate) FROM translated_records WHERE data_type='review' AND rate IS NOT NULL"
        )
        avg_rating = round(float(avg[0]), 2) if avg and avg[0] else 4.83

        positive = self.fetch_one(
            "SELECT COUNT(*) FROM translated_records WHERE data_type='review' AND rate >= 4"
        )[0]
        five = self.fetch_one(
            "SELECT COUNT(*) FROM translated_records WHERE data_type='review' AND rate = 5"
        )[0]
        positive_rate = round(positive / reviews * 100, 1) if reviews else 0
        five_star_rate = round(five / reviews * 100, 1) if reviews else 0

        platforms = self.fetch_one(
            "SELECT COUNT(DISTINCT site_name) FROM translated_records"
        )[0]

        return {
            "total_records": total,
            "total_reviews": reviews,
            "total_qa": qa_count,
            "product_count": product_count,
            "sku_count": sku_count,
            "user_count": user_count,
            "avg_rating": avg_rating,
            "positive_rate": positive_rate,
            "five_star_rate": five_star_rate,
            "platforms": platforms,
            "date_range_start": "2025-03",
            "date_range_end": "2026-04",
        }

    def get_rating_dist(self) -> dict:
        """评分分布"""
        rows = self.fetch_query(
            "SELECT rate, COUNT(*) FROM translated_records WHERE data_type='review' AND rate IS NOT NULL GROUP BY rate ORDER BY rate"
        )
        labels_map = {0: "0星", 1: "1星", 2: "2星", 3: "3星", 4: "4星", 5: "5星"}
        values_map = {r[0]: r[1] for r in rows}
        labels = [labels_map.get(i, f"{i}星") for i in range(6)]
        values = [values_map.get(i, 0) for i in range(6)]
        return {"labels": labels, "values": values}

    def get_monthly_trend(self) -> dict:
        """月度趋势"""
        months = [
            "2025-03", "2025-04", "2025-05", "2025-06",
            "2025-07", "2025-08", "2025-09", "2025-10",
            "2025-11", "2025-12", "2026-01", "2026-02",
            "2026-03", "2026-04",
        ]
        result = {"months": months, "total": [], "reviews": [], "qa": [], "avg_rating": []}
        for m in months:
            prefix = f"{m}%"
            total = self.fetch_one(
                "SELECT COUNT(*) FROM translated_records WHERE publish_date LIKE %s",
                (prefix,),
            )[0]
            reviews = self.fetch_one(
                "SELECT COUNT(*) FROM translated_records WHERE data_type='review' AND publish_date LIKE %s",
                (prefix,),
            )[0]
            qa_m = self.fetch_one(
                "SELECT COUNT(*) FROM translated_records WHERE data_type='qa' AND publish_date LIKE %s",
                (prefix,),
            )[0]
            avg = self.fetch_one(
                "SELECT AVG(rate) FROM translated_records WHERE data_type='review' AND rate IS NOT NULL AND publish_date LIKE %s",
                (prefix,),
            )
            avg_rating = round(float(avg[0]), 2) if avg and avg[0] else 4.85
            result["total"].append(total)
            result["reviews"].append(reviews)
            result["qa"].append(qa_m)
            result["avg_rating"].append(avg_rating)
        return result

    def get_product_ranking(self) -> list:
        """产品排行"""
        rows = self.fetch_query(
            "SELECT name, COUNT(*) as total, "
            "COUNT(CASE WHEN data_type='review' THEN 1 END) as reviews, "
            "AVG(CASE WHEN data_type='review' AND rate IS NOT NULL THEN rate END) as avg_rating, "
            "COUNT(CASE WHEN data_type='review' AND rate=5 THEN 1 END) * 100.0 / "
            "NULLIF(COUNT(CASE WHEN data_type='review' THEN 1 END), 0) as five_star_pct "
            "FROM translated_records "
            "GROUP BY name ORDER BY total DESC"
        )
        return [
            {
                "name": r[0],
                "total": r[1],
                "reviews": r[2],
                "avg_rating": round(float(r[3]), 2) if r[3] else 0,
                "five_star_pct": round(float(r[4]), 1) if r[4] else 0,
            }
            for r in rows
        ]

    def get_platform_comparison(self) -> dict:
        """平台对比"""
        platforms = {}
        for row in self.fetch_query(
            "SELECT site_name, COUNT(*), "
            "COUNT(CASE WHEN data_type='review' THEN 1 END), "
            "AVG(CASE WHEN data_type='review' AND rate IS NOT NULL THEN rate END) "
            "FROM translated_records GROUP BY site_name"
        ):
            name = row[0]
            if "OZON" in name.upper() and "OZON" not in [p.upper() for p in platforms]:
                key = "OZON"
            elif "WILDBERRIES" in name.upper() and "WILDBERRIES" not in [p.upper() for p in platforms]:
                key = "Wildberries"
            else:
                continue
            if key not in platforms:
                platforms[key] = {"total": 0, "reviews": 0, "qa": 0, "avg_rating": 0.0}
            platforms[key]["total"] += row[1]
            platforms[key]["reviews"] += row[2]
            platforms[key]["qa"] += row[1] - row[2]
            platforms[key]["avg_rating"] = row[3] if row[3] else 0
        if "OZON" in platforms:
            platforms["OZON"]["avg_rating"] = round(float(platforms["OZON"]["avg_rating"]), 2)
        if "Wildberries" in platforms:
            platforms["Wildberries"]["avg_rating"] = round(float(platforms["Wildberries"]["avg_rating"]), 2)
        return platforms

    def get_review_length_dist(self) -> dict:
        """评论长度分布"""
        labels = ["0-20", "20-50", "50-100", "100-200", "200-500", "500-1000", "1000+"]
        bins = [(0, 20), (20, 50), (50, 100), (100, 200), (200, 500), (500, 1000), (1000, 10**9)]
        values = []
        for lo, hi in bins:
            cnt = self.fetch_one(
                "SELECT COUNT(*) FROM translated_records WHERE data_type='review' "
                "AND COALESCE(review_zh, review) IS NOT NULL "
                "AND LENGTH(COALESCE(review_zh, review)) >= %s AND LENGTH(COALESCE(review_zh, review)) < %s",
                (lo, hi),
            )[0]
            values.append(cnt)
        return {"labels": labels, "values": values}

    def get_top_authors(self, limit=15) -> dict:
        """活跃用户排行"""
        rows = self.fetch_query(
            "SELECT author, COUNT(*) as cnt FROM translated_records "
            "WHERE author IS NOT NULL AND author != '' "
            "GROUP BY author ORDER BY cnt DESC LIMIT %s",
            (limit,),
        )
        return {"names": [r[0] for r in rows], "counts": [r[1] for r in rows]}

    def get_source_dist(self) -> dict:
        """文件来源分布"""
        rows = self.fetch_query(
            "SELECT source_file, COUNT(*) FROM translated_records "
            "WHERE source_file IS NOT NULL AND source_file != '' "
            "GROUP BY source_file ORDER BY COUNT(*) DESC"
        )
        return {"labels": [r[0] for r in rows], "values": [r[1] for r in rows]}

    def get_rating_length_scatter(self, sample_size=500):
        """评分-长度散点数据"""
        rows = self.fetch_query(
            "SELECT rate, LENGTH(COALESCE(review_zh, review)) as clen "
            "FROM translated_records WHERE data_type='review' AND rate IS NOT NULL "
            "AND COALESCE(review_zh, review) IS NOT NULL "
            "ORDER BY RAND() LIMIT %s",
            (sample_size,),
        )
        return [[int(r[0]), r[1]] for r in rows]

    def get_product_monthly(self) -> dict:
        """各产品月度数据"""
        months = [
            "2025-03", "2025-04", "2025-05", "2025-06",
            "2025-07", "2025-08", "2025-09", "2025-10",
            "2025-11", "2025-12", "2026-01", "2026-02",
            "2026-03", "2026-04",
        ]
        top_names = [
            r[0]
            for r in self.fetch_query(
                "SELECT name FROM translated_records GROUP BY name ORDER BY COUNT(*) DESC LIMIT 10"
            )
        ]
        products = {n: [] for n in top_names}
        for m in months:
            for n in top_names:
                cnt = self.fetch_one(
                    "SELECT COUNT(*) FROM translated_records WHERE name=%s AND publish_date LIKE %s",
                    (n, f"{m}%"),
                )[0]
                products[n].append(cnt)
        return {"months": months, "products": products}

    def get_table_count(self, table_name: str) -> int:
        """获取任意表的行数"""
        return self.fetch_one(f"SELECT COUNT(*) FROM {table_name}")[0]

    def get_daily_heatmap(self) -> list:
        """获取日历热力图数据"""
        rows = self.fetch_query(
            "SELECT DATE(publish_date) as d, COUNT(*) as cnt "
            "FROM translated_records WHERE publish_date IS NOT NULL "
            "GROUP BY DATE(publish_date) ORDER BY d"
        )
        return [[r[0].strftime("%Y-%m-%d"), r[1]] for r in rows]
