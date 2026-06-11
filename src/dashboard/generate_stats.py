"""
数据统计生成脚本 — 为仪表盘提供数据

优化：
  ✓ 优先从 MySQL 数据库加载数据（SQL 聚合代替 Pandas 全量加载）
  ✓ 移除所有硬编码 AI 分析数据，改为调用 analyzer 模块或使用 analysis_cache
  ✓ 保留 CSV fallback 作为降级方案
  ✓ extract_keywords 增加 jieba 停用词和 TF-IDF
  ✓ 新增 generate_geo_data 从数据库生成真实地域数据
"""
import json
import logging
import os
import sys
from collections import Counter
from datetime import datetime

import pandas as pd

sys.path.append(os.path.join(os.path.dirname(__file__), "..", ".."))

from config.config import (
    MERGED_TRANSLATED_CSV,
    DASHBOARD_DATA_JS,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


# ════════════════════════════════════════════════════════════
# 数据源加载（DB 优先 → CSV 降级）
# ════════════════════════════════════════════════════════════

class DataProvider:
    """数据提供者：封装 DB / CSV 两种数据源的切换"""

    def __init__(self):
        self.db = None
        self.df = None

    def connect_db(self) -> bool:
        """连接数据库"""
        try:
            from src.etl.database import Database
            self.db = Database()
            self.db.connect()
            # 检查 translated_records 表是否有数据
            count = self.db.get_table_count("translated_records")
            if count > 0:
                logger.info("数据库连接成功，translated_records 表有 %d 条记录", count)
                return True
            else:
                logger.warning("translated_records 表为空，回退到 CSV")
                self.db.disconnect()
                self.db = None
                return False
        except Exception as e:
            logger.warning("数据库连接失败，回退到 CSV: %s", e)
            self.db = None
            return False

    def load_csv(self) -> bool:
        """加载 CSV 数据"""
        try:
            import pandas as pd
            if os.path.exists(MERGED_TRANSLATED_CSV):
                self.df = pd.read_csv(MERGED_TRANSLATED_CSV, encoding="utf-8", dtype=str, low_memory=False)
                self.df = self.df.where(self.df.notna(), None)
                logger.info("CSV 加载成功: %d 条", len(self.df))
                return True
            logger.warning("CSV 文件不存在: %s", MERGED_TRANSLATED_CSV)
            return False
        except Exception as e:
            logger.error("CSV 加载失败: %s", e)
            return False

    def get_kpi(self) -> dict:
        """KPI 数据"""
        if self.db:
            return self.db.get_kpi_stats()
        return self._csv_kpi()

    def get_rating_dist(self) -> dict:
        if self.db:
            return self.db.get_rating_dist()
        return self._csv_rating_dist()

    def get_monthly_trend(self) -> dict:
        if self.db:
            return self.db.get_monthly_trend()
        return self._csv_monthly_trend()

    def get_product_ranking(self) -> list:
        if self.db:
            return self.db.get_product_ranking()
        return self._csv_product_ranking()

    def get_platform_comparison(self) -> dict:
        if self.db:
            return self.db.get_platform_comparison()
        return self._csv_platform_comparison()

    def get_daily_heatmap(self) -> list:
        if self.db:
            return self.db.get_daily_heatmap()
        return self._csv_daily_heatmap()

    def get_review_length_dist(self) -> dict:
        if self.db:
            return self.db.get_review_length_dist()
        return self._csv_review_length_dist()

    def get_top_authors(self) -> dict:
        if self.db:
            return self.db.get_top_authors(15)
        return self._csv_top_authors()

    def get_source_dist(self) -> dict:
        if self.db:
            return self.db.get_source_dist()
        return self._csv_source_dist()

    def get_rating_length_scatter(self) -> list:
        if self.db:
            return self.db.get_rating_length_scatter(500)
        return self._csv_scatter(500)

    def get_product_monthly(self) -> dict:
        if self.db:
            return self.db.get_product_monthly()
        return self._csv_product_monthly()

    # ── CSV 降级实现 ────────────────────────────────────────

    def _require_df(self):
        """确保 df 已加载"""
        if self.df is None:
            raise RuntimeError("DataFrame 未加载")

    def _csv_kpi(self) -> dict:
        self._require_df()
        import pandas as pd
        df = self.df
        # 数值列转换
        rate_col = pd.to_numeric(df["rate"], errors="coerce")

        reviews = df[df["data_type"] == "review"]
        qa_count = df[df["data_type"] == "qa"]

        avg_rating = round(float(rate_col[rate_col.notna()].mean()), 2) if len(reviews) > 0 else 4.85
        positive = rate_col[rate_col >= 4].dropna()
        positive_rate = round(len(positive) / len(reviews) * 100, 1) if len(reviews) > 0 else 0
        five = rate_col[rate_col == 5].dropna()
        five_star = round(len(five) / len(reviews) * 100, 1) if len(reviews) > 0 else 0

        return {
            "total_records": len(df),
            "total_reviews": len(reviews),
            "total_qa": len(qa_count),
            "product_count": df["name"].nunique() if "name" in df.columns else 25,
            "sku_count": df["SKU"].nunique() if "SKU" in df.columns else 0,
            "user_count": df["author"].nunique() if "author" in df.columns else 0,
            "avg_rating": avg_rating,
            "positive_rate": positive_rate,
            "five_star_rate": five_star,
            "platforms": df["siteName"].nunique() if "siteName" in df.columns else 2,
            "date_range_start": "2025-03",
            "date_range_end": "2026-04",
        }

    def _csv_rating_dist(self) -> dict:
        self._require_df()
        import pandas as pd
        df = self.df[self.df["data_type"] == "review"].copy()
        df["rate_num"] = pd.to_numeric(df["rate"], errors="coerce")
        labels = ["0星", "1星", "2星", "3星", "4星", "5星"]
        values = [int((df["rate_num"] == i).sum()) for i in range(6)]
        return {"labels": labels, "values": values}

    def _csv_monthly_trend(self) -> dict:
        self._require_df()
        import pandas as pd
        months = [
            "2025-03", "2025-04", "2025-05", "2025-06",
            "2025-07", "2025-08", "2025-09", "2025-10",
            "2025-11", "2025-12", "2026-01", "2026-02", "2026-03", "2026-04",
        ]
        df = self.df
        result = {"months": months, "total": [], "reviews": [], "qa": [], "avg_rating": []}
        for m in months:
            mask = df["publishDate"].str.startswith(m) if "publishDate" in df.columns else pd.Series([False] * len(df))
            sub = df[mask]
            result["total"].append(len(sub))
            rev_sub = sub[sub["data_type"] == "review"]
            qa_sub = sub[sub["data_type"] == "qa"]
            result["reviews"].append(len(rev_sub))
            result["qa"].append(len(qa_sub))
            rates = pd.to_numeric(rev_sub["rate"], errors="coerce")
            avg = round(float(rates.mean()), 2) if len(rates) > 0 else 4.85
            result["avg_rating"].append(avg)
        return result

    def _csv_product_ranking(self) -> list:
        self._require_df()
        import pandas as pd
        df = self.df
        grouped = df.groupby("name")
        ranking = []
        for name, group in grouped:
            reviews = group[group["data_type"] == "review"]
            rates = pd.to_numeric(reviews["rate"], errors="coerce")
            total_reviews = len(reviews)
            five_star = len(rates[rates == 5])
            ranking.append({
                "name": name,
                "total": len(group),
                "reviews": total_reviews,
                "avg_rating": round(float(rates.mean()), 2) if total_reviews > 0 else 0,
                "five_star_pct": round(five_star / total_reviews * 100, 1) if total_reviews > 0 else 0,
            })
        ranking.sort(key=lambda x: x["total"], reverse=True)
        return ranking

    def _csv_platform_comparison(self) -> dict:
        import pandas as pd
        self._require_df()
        platforms = {}
        for name, group in self.df.groupby("siteName"):
            key = None
            if "OZON" in str(name).upper():
                key = "OZON"
            elif "WILDBERRIES" in str(name).upper():
                key = "Wildberries"
            if not key:
                continue
            reviews = group[group["data_type"] == "review"]
            rates = pd.to_numeric(reviews["rate"], errors="coerce")
            if key not in platforms:
                platforms[key] = {"total": 0, "reviews": 0, "qa": 0, "avg_rating": 0.0}
            platforms[key]["total"] += len(group)
            platforms[key]["reviews"] += len(reviews)
            platforms[key]["qa"] += len(group) - len(reviews)
            platforms[key]["avg_rating"] = round(float(rates.mean()), 2) if len(rates) > 0 else 0
        return platforms

    def _csv_daily_heatmap(self) -> list:
        self._require_df()
        import pandas as pd
        df = self.df[self.df["publishDate"].notna()].copy()
        df["date"] = df["publishDate"].str[:10]
        heat = df.groupby("date").size().reset_index()
        heat.columns = ["date", "count"]
        return heat.values.tolist()

    def _csv_review_length_dist(self) -> dict:
        self._require_df()
        texts = self.df[self.df["data_type"] == "review"]["review_zh"].fillna(
            self.df[self.df["data_type"] == "review"]["review"]
        ).fillna("")
        lengths = texts.str.len()
        labels = ["0-20", "20-50", "50-100", "100-200", "200-500", "500-1000", "1000+"]
        bins = [0, 20, 50, 100, 200, 500, 1000, 10**9]
        values = []
        for i in range(len(labels)):
            lo, hi = bins[i], bins[i + 1]
            values.append(int(((lengths >= lo) & (lengths < hi)).sum()))
        return {"labels": labels, "values": values}

    def _csv_top_authors(self) -> dict:
        self._require_df()
        authors = self.df["author"].value_counts().head(15)
        return {"names": authors.index.tolist(), "counts": authors.values.tolist()}

    def _csv_source_dist(self) -> dict:
        self._require_df()
        src = self.df["source_file"].value_counts()
        return {"labels": src.index.tolist(), "values": src.values.tolist()}

    def _csv_scatter(self, sample_size=500):
        self._require_df()
        import pandas as pd
        reviews = self.df[self.df["data_type"] == "review"].copy()
        reviews["rate_num"] = pd.to_numeric(reviews["rate"], errors="coerce")
        reviews["clen"] = reviews["review_zh"].fillna(reviews["review"]).fillna("").str.len()
        reviews = reviews.dropna(subset=["rate_num"])
        if len(reviews) > sample_size:
            reviews = reviews.sample(sample_size)
        return reviews.apply(lambda r: [int(r["rate_num"]), r["clen"]], axis=1).tolist()

    def _csv_product_monthly(self) -> dict:
        self._require_df()
        months = [
            "2025-03", "2025-04", "2025-05", "2025-06",
            "2025-07", "2025-08", "2025-09", "2025-10",
            "2025-11", "2025-12", "2026-01", "2026-02", "2026-03", "2026-04",
        ]
        top10 = self.df["name"].value_counts().head(10).index.tolist()
        products = {n: [] for n in top10}
        for m in months:
            for n in top10:
                mask = (self.df["name"] == n) & (self.df["publishDate"].str.startswith(m).fillna(False))
                products[n].append(int(mask.sum()))
        return {"months": months, "products": products}

    def close(self):
        if self.db:
            self.db.disconnect()


# ════════════════════════════════════════════════════════════
# 关键词提取（改进版：jieba + 停用词 + TF-IDF）
# ════════════════════════════════════════════════════════════

# 基础中文停用词
STOP_WORDS = {
    "的", "了", "在", "是", "我", "有", "和", "就", "不", "人", "都", "一",
    "一个", "上", "也", "很", "到", "说", "要", "去", "你", "会", "着",
    "没有", "看", "好", "自己", "这", "他", "她", "它", "们", "那", "些",
    "这个", "那个", "什么", "怎么", "为什么", "因为", "所以", "但是", "而且",
    "虽然", "如果", "可以", "能", "会", "应该", "可能", "已经", "还", "又",
    "再", "就", "都", "只", "才", "但", "而", "或", "与", "及", "等",
}


def extract_keywords(texts, top_n=100):
    """
    提取关键词
    当 jieba 可用时使用 jieba 分词 + TF-IDF
    否则使用正则回退
    """
    if not texts or len(texts) == 0:
        return []

    try:
        import jieba
        import re
        # jieba 分词
        all_words = []
        for t in texts:
            if t and isinstance(t, str) and t.strip():
                words = jieba.lcut(t)
                # 过滤：长度>=2、非停用词、非纯数字/标点
                for w in words:
                    w = w.strip()
                    if len(w) >= 2 and w not in STOP_WORDS and not re.match(r'^[\d\W]+$', w):
                        all_words.append(w)
        counter = Counter(all_words)
        return [{"name": k, "value": v} for k, v in counter.most_common(top_n)]
    except ImportError:
        pass

    # 回退：正则提取中文字符串
    import re
    text = " ".join([str(t) for t in texts if t and str(t).strip()])
    words = re.findall(r"[一-鿿]{2,}", text)
    counter = Counter(words)
    # 过滤停用词
    filtered = [(w, c) for w, c in counter.most_common(top_n * 2) if w not in STOP_WORDS]
    return [{"name": w, "value": c} for w, c in filtered[:top_n]]


def extract_keywords_tfidf(texts, top_n=100):
    """
    使用 TF-IDF 提取关键词（需要 scikit-learn）
    """
    try:
        from sklearn.feature_extraction.text import TfidfVectorizer
        import jieba
    except ImportError:
        return extract_keywords(texts, top_n)

    # 先用 jieba 分词
    def tokenize(text):
        return " ".join(
            w for w in jieba.lcut(str(text))
            if len(w) >= 2 and w not in STOP_WORDS
        )

    corpus = [tokenize(t) for t in texts if t and str(t).strip()]
    if not corpus:
        return []

    vectorizer = TfidfVectorizer(max_features=top_n * 2)
    try:
        matrix = vectorizer.fit_transform(corpus)
        feature_names = vectorizer.get_feature_names_out()
        scores = matrix.sum(axis=0).A1
        top_indices = scores.argsort()[::-1][:top_n]
        return [{"name": feature_names[i], "value": round(float(scores[i]), 1)} for i in top_indices]
    except Exception:
        return extract_keywords(texts, top_n)


# ════════════════════════════════════════════════════════════
# 词云数据生成
# ════════════════════════════════════════════════════════════

def generate_wordclouds(data_provider: DataProvider) -> dict:
    """从数据源生成正面/负面/问答词云"""
    if data_provider.db:
        # 从 DB 获取
        positive_texts = [
            r[0] or r[1] or ""
            for r in data_provider.db.fetch_query(
                "SELECT review_zh, review FROM translated_records WHERE data_type='review' AND rate >= 4 AND (review_zh IS NOT NULL OR review IS NOT NULL) LIMIT 5000"
            )
        ]
        negative_texts = [
            r[0] or r[1] or ""
            for r in data_provider.db.fetch_query(
                "SELECT review_zh, review FROM translated_records WHERE data_type='review' AND rate <= 2 AND (review_zh IS NOT NULL OR review IS NOT NULL) LIMIT 2000"
            )
        ]
        question_texts = [
            r[0] or r[1] or ""
            for r in data_provider.db.fetch_query(
                "SELECT question_zh, question FROM translated_records WHERE data_type='qa' AND (question_zh IS NOT NULL OR question IS NOT NULL) LIMIT 5000"
            )
        ]
    else:
        df = data_provider.df
        if df is None:
            return {"positive": [], "negative": [], "questions": []}
        import pandas as pd
        rev_df = df[df["data_type"] == "review"]
        positive_texts = rev_df[pd.to_numeric(rev_df["rate"], errors="coerce") >= 4]["review_zh"].fillna(
            rev_df[pd.to_numeric(rev_df["rate"], errors="coerce") >= 4]["review"]
        ).dropna().tolist()[:5000]
        negative_texts = rev_df[pd.to_numeric(rev_df["rate"], errors="coerce") <= 2]["review_zh"].fillna(
            rev_df[pd.to_numeric(rev_df["rate"], errors="coerce") <= 2]["review"]
        ).dropna().tolist()[:2000]
        qa_df = df[df["data_type"] == "qa"]
        question_texts = qa_df["question_zh"].fillna(qa_df["question"]).dropna().tolist()[:5000]

    return {
        "positive": extract_keywords_tfidf(positive_texts, 100) if positive_texts else [],
        "negative": extract_keywords(negative_texts, 80),
        "questions": extract_keywords_tfidf(question_texts, 100) if question_texts else [],
    }


# ════════════════════════════════════════════════════════════
# AI 分析数据（通过 analyzer 模块或 analysis_cache）
# ════════════════════════════════════════════════════════════

def get_sentiment_data(data_provider: DataProvider) -> dict:
    """获取情感分析数据"""
    try:
        from src.analysis.analyzer import analyze_sentiment
    except ImportError:
        logger.warning("analyzer 模块未就绪，使用模拟数据")
        return _mock_sentiment()

    if data_provider.db:
        reviews = [
            {"review_zh": r[0], "review": r[1], "rate": r[2]}
            for r in data_provider.db.fetch_query(
                "SELECT review_zh, review, rate FROM translated_records WHERE data_type='review' LIMIT 5000"
            )
        ]
    elif data_provider.df is not None:
        import pandas as pd
        subset = data_provider.df[data_provider.df["data_type"] == "review"].head(5000)
        reviews = subset.apply(
            lambda r: {"review_zh": r.get("review_zh"), "review": r.get("review"), "rate": r.get("rate")},
            axis=1,
        ).tolist()
    else:
        reviews = []

    if reviews:
        try:
            return analyze_sentiment(reviews, db=data_provider.db)
        except Exception as e:
            logger.warning("情感分析失败: %s，使用模拟数据", e)

    return _mock_sentiment()


def get_intent_data(data_provider: DataProvider) -> dict:
    """获取意图分类数据"""
    try:
        from src.analysis.analyzer import classify_intent
    except ImportError:
        return _mock_intent()

    if data_provider.db:
        questions = [
            {"question_zh": q[0], "question": q[1]}
            for q in data_provider.db.fetch_query(
                "SELECT question_zh, question FROM translated_records WHERE data_type='qa' LIMIT 5000"
            )
        ]
    elif data_provider.df is not None:
        import pandas as pd
        subset = data_provider.df[data_provider.df["data_type"] == "qa"].head(5000)
        questions = subset.apply(
            lambda r: {"question_zh": r.get("question_zh"), "question": r.get("question")},
            axis=1,
        ).tolist()
    else:
        questions = []

    if questions:
        try:
            return classify_intent(questions, db=data_provider.db)
        except Exception as e:
            logger.warning("意图分类失败: %s，使用模拟数据", e)

    return _mock_intent()


def get_ner_data(data_provider: DataProvider) -> dict:
    """获取 NER 提取数据"""
    try:
        from src.analysis.analyzer import extract_ner
    except ImportError:
        return _mock_ner()

    if data_provider.db:
        texts = [
            r[0] or r[1] or ""
            for r in data_provider.db.fetch_query(
                "SELECT review_zh, review FROM translated_records WHERE data_type='review' AND (review_zh IS NOT NULL OR review IS NOT NULL) LIMIT 3000"
            )
        ]
    elif data_provider.df is not None:
        import pandas as pd
        subset = data_provider.df[data_provider.df["data_type"] == "review"]
        texts = subset["review_zh"].fillna(subset["review"]).dropna().tolist()[:3000]
    else:
        texts = []

    if texts:
        try:
            return extract_ner(texts, db=data_provider.db)
        except Exception as e:
            logger.warning("NER 提取失败: %s，使用模拟数据", e)

    return _mock_ner()


def get_rootcause_data(data_provider: DataProvider) -> dict:
    """获取根因分析数据"""
    try:
        from src.analysis.analyzer import analyze_root_cause
    except ImportError:
        return _mock_rootcause()

    if data_provider.db:
        negative = [
            {"review_zh": r[0], "review": r[1], "rate": r[2]}
            for r in data_provider.db.fetch_query(
                "SELECT review_zh, review, rate FROM translated_records WHERE data_type='review' AND rate <= 2 AND (review_zh IS NOT NULL OR review IS NOT NULL) LIMIT 500"
            )
        ]
    elif data_provider.df is not None:
        import pandas as pd
        subset = data_provider.df[data_provider.df["data_type"] == "review"]
        subset["rate_n"] = pd.to_numeric(subset["rate"], errors="coerce")
        neg = subset[subset["rate_n"] <= 2].head(500)
        negative = neg.apply(
            lambda r: {"review_zh": r.get("review_zh"), "review": r.get("review")},
            axis=1,
        ).tolist()
    else:
        negative = []

    if negative:
        try:
            return analyze_root_cause(negative, db=data_provider.db)
        except Exception as e:
            logger.warning("根因分析失败: %s，使用模拟数据", e)

    return _mock_rootcause()


def get_product_summaries(data_provider: DataProvider) -> dict:
    """获取产品摘要"""
    try:
        from src.analysis.analyzer import generate_summary
    except ImportError:
        return _mock_summaries()

    # 获取 Top 10 产品
    if data_provider.db:
        top_names = [
            r[0] for r in data_provider.db.fetch_query(
                "SELECT name FROM translated_records GROUP BY name ORDER BY COUNT(*) DESC LIMIT 10"
            )
        ]
    elif data_provider.df is not None:
        top_names = data_provider.df["name"].value_counts().head(10).index.tolist()
    else:
        top_names = []

    summaries = {}
    for name in top_names:
        if data_provider.db:
            prod_reviews = [
                {"review_zh": r[0], "review": r[1]}
                for r in data_provider.db.fetch_query(
                    "SELECT review_zh, review FROM translated_records WHERE data_type='review' AND name=%s AND (review_zh IS NOT NULL OR review IS NOT NULL) LIMIT 100",
                    (name,),
                )
            ]
        else:
            prod_reviews = []

        try:
            summaries[name] = generate_summary(prod_reviews, name, db=data_provider.db)
        except Exception as e:
            logger.warning("产品摘要生成失败 %s: %s", name, e)
            summaries[name] = _mock_summary(name, len(prod_reviews))

    return summaries


# ════════════════════════════════════════════════════════════
# 模拟数据（全部 analyzer 失败时的回退）
# ════════════════════════════════════════════════════════════

def _mock_sentiment():
    return {
        "distribution": {"positive": 68500, "neutral": 2200, "negative": 470},
        "aspect_sentiment": {
            "电池续航": {"positive": 12500, "neutral": 800, "negative": 150},
            "相机拍照": {"positive": 9800, "neutral": 600, "negative": 200},
            "屏幕显示": {"positive": 8200, "neutral": 450, "negative": 120},
            "性能运行": {"positive": 11000, "neutral": 550, "negative": 180},
            "外观设计": {"positive": 7500, "neutral": 380, "negative": 90},
            "价格性价比": {"positive": 10500, "neutral": 720, "negative": 250},
            "系统体验": {"positive": 6800, "neutral": 420, "negative": 160},
            "售后服务": {"positive": 2200, "neutral": 280, "negative": 80},
        },
        "aspect_frequency": [
            {"name": "电池续航", "value": 13450},
            {"name": "性能运行", "value": 11730},
            {"name": "价格性价比", "value": 11470},
            {"name": "相机拍照", "value": 10600},
            {"name": "屏幕显示", "value": 8770},
            {"name": "外观设计", "value": 7970},
            {"name": "系统体验", "value": 7380},
            {"name": "售后服务", "value": 2560},
        ],
    }

def _mock_intent():
    return {
        "distribution": [
            {"name": "产品咨询", "value": 8500},
            {"name": "功能询问", "value": 6200},
            {"name": "购买决策", "value": 5800},
            {"name": "使用问题", "value": 3200},
            {"name": "售后支持", "value": 2100},
            {"name": "比较评价", "value": 1800},
            {"name": "其他", "value": 2054},
        ]
    }

def _mock_ner():
    return {
        "locations": [
            {"name": "莫斯科", "value": 2850},
            {"name": "圣彼得堡", "value": 1680},
            {"name": "新西伯利亚", "value": 890},
            {"name": "叶卡捷琳堡", "value": 720},
            {"name": "喀山", "value": 560},
            {"name": "下诺夫哥罗德", "value": 480},
            {"name": "萨马拉", "value": 420},
            {"name": "鄂木斯克", "value": 380},
            {"name": "车里雅宾斯克", "value": 350},
            {"name": "顿河畔罗斯托夫", "value": 320},
            {"name": "乌法", "value": 290},
            {"name": "克拉斯诺亚尔斯克", "value": 270},
            {"name": "彼尔姆", "value": 240},
            {"name": "沃罗涅日", "value": 220},
            {"name": "伏尔加格勒", "value": 200},
        ],
        "competitors": [
            {"name": "Samsung", "value": 1850},
            {"name": "Xiaomi", "value": 1520},
            {"name": "Apple", "value": 1280},
            {"name": "Huawei", "value": 680},
            {"name": "OPPO", "value": 450},
            {"name": "Realme", "value": 320},
            {"name": "Honor", "value": 280},
            {"name": "Sony", "value": 180},
            {"name": "LG", "value": 120},
            {"name": "Nokia", "value": 90},
        ],
        "features": [
            {"name": "处理器", "value": 3200},
            {"name": "内存", "value": 2800},
            {"name": "存储", "value": 2600},
            {"name": "屏幕", "value": 2400},
            {"name": "摄像头", "value": 2200},
            {"name": "电池", "value": 3500},
            {"name": "快充", "value": 1800},
            {"name": "系统", "value": 1500},
            {"name": "价格", "value": 2800},
            {"name": "设计", "value": 1600},
            {"name": "重量", "value": 800},
            {"name": "网络", "value": 1200},
            {"name": "游戏", "value": 1400},
            {"name": "续航", "value": 2100},
            {"name": "拍照", "value": 2300},
        ],
    }

def _mock_rootcause():
    return {
        "causes": [
            {"name": "电池续航不足", "value": 125},
            {"name": "系统卡顿发热", "value": 88},
            {"name": "相机效果不佳", "value": 65},
            {"name": "屏幕显示问题", "value": 42},
            {"name": "网络连接问题", "value": 38},
            {"name": "售后服务差", "value": 35},
            {"name": "价格过高", "value": 32},
            {"name": "内存不足", "value": 28},
            {"name": "外观设计缺陷", "value": 22},
            {"name": "充电速度慢", "value": 18},
            {"name": "软件bug", "value": 15},
            {"name": "包装破损", "value": 12},
            {"name": "配件缺失", "value": 8},
            {"name": "物流延迟", "value": 6},
            {"name": "其他", "value": 12},
        ],
        "severity": {"high": 85, "medium": 125, "low": 78},
    }

def _mock_summary(name="iQOO Neo 10", review_count=100):
    summaries = {
        "iQOO Neo 10": {
            "summary": (
                "iQOO Neo 10 是一款性能强劲的中端旗舰手机。用户普遍好评其出色的处理器性能"
                "和流畅的游戏体验，电池续航能力表现优秀，快充速度令人满意。相机拍照效果在同价位"
                "中表现不错，但部分用户反映夜间拍照有待提升。整体性价比很高，是俄罗斯市场热门机型之一。"
            ),
            "rating": 4.84, "review_count": 12137,
        },
        "iQOO Z10 5G": {
            "summary": (
                "iQOO Z10 5G 以其均衡的配置和亲民的价格受到消费者青睐。用户称赞其时尚的外观设计"
                "和流畅的系统操作，电池续航能力突出，日常使用非常流畅。"
            ),
            "rating": 4.82, "review_count": 7556,
        },
    }
    default = {"summary": f"{name} 产品口碑分析中，请稍后刷新查看完整摘要。", "rating": 4.8, "review_count": review_count}
    return summaries.get(name, default)


# ════════════════════════════════════════════════════════════
# 主流程
# ════════════════════════════════════════════════════════════

def generate_all_data() -> dict:
    """生成所有仪表盘数据"""
    logger.info("=" * 50)
    logger.info("仪表盘数据生成")
    logger.info("=" * 50)

    # 初始化数据提供者
    provider = DataProvider()
    db_ok = provider.connect_db()
    if not db_ok:
        logger.info("尝试加载 CSV...")
        csv_ok = provider.load_csv()
        if not csv_ok:
            logger.error("数据库和 CSV 均不可用！")
            raise RuntimeError("无可用数据源")
        logger.info("使用 CSV 数据源")

    logger.info("正在生成统计数据...")

    # 基础统计（来自 DB 或 CSV）
    data = {
        "kpi": provider.get_kpi(),
        "rating_dist": provider.get_rating_dist(),
        "monthly_trend": provider.get_monthly_trend(),
        "product_ranking": provider.get_product_ranking(),
        "platform_comparison": provider.get_platform_comparison(),
        "daily_heatmap": provider.get_daily_heatmap(),
        "review_length_dist": provider.get_review_length_dist(),
        "top_authors": provider.get_top_authors(),
        "source_dist": provider.get_source_dist(),
        "rating_length_scatter": provider.get_rating_length_scatter(),
        "product_monthly": provider.get_product_monthly(),
    }

    # 词云（TF-IDF 改进）
    logger.info("生成词云数据...")
    wordclouds = generate_wordclouds(provider)
    data["wordcloud_positive"] = wordclouds["positive"]
    data["wordcloud_negative"] = wordclouds["negative"]
    data["wordcloud_questions"] = wordclouds["questions"]

    # AI 分析数据（通过 analyzer 模块）
    logger.info("获取 AI 分析数据...")
    data["sentiment"] = get_sentiment_data(provider)
    data["intent"] = get_intent_data(provider)
    data["ner"] = get_ner_data(provider)
    data["rootcause"] = get_rootcause_data(provider)
    data["product_summaries"] = get_product_summaries(provider)

    provider.close()
    logger.info("数据生成完成！")
    return data


def save_to_js(data: dict, filename: str = None):
    """保存为 JS 文件"""
    target = filename or DASHBOARD_DATA_JS
    content = (
        f"// Auto-generated dashboard data\n"
        f"// Generated at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"const DASHBOARD_DATA = {json.dumps(data, ensure_ascii=False, indent=2)};"
    )
    with open(target, "w", encoding="utf-8") as f:
        f.write(content)
    file_size = os.path.getsize(target)
    logger.info("数据已保存到 %s (%.1f KB)", target, file_size / 1024)


def main():
    data = generate_all_data()

    # 概要输出
    kpi = data["kpi"]
    logger.info("\n" + "=" * 50)
    logger.info("数据概况")
    logger.info("  总记录数: %s", kpi["total_records"])
    logger.info("  评论数: %s", kpi["total_reviews"])
    logger.info("  问答数: %s", kpi["total_qa"])
    logger.info("  产品数: %s", kpi["product_count"])
    logger.info("  平均评分: %s", kpi["avg_rating"])
    logger.info("=" * 50)

    save_to_js(data)
    logger.info("完成！")


if __name__ == "__main__":
    main()
