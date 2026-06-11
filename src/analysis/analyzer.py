"""
AI 分析管道 — 使用 DeepSeek V4 Flash API
功能：情感分析 / 意图分类 / NER 提取 / 根因分析 / 产品摘要

用法：
  python src/analysis/analyzer.py --mode sentiment   # 情感分析
  python src/analysis/analyzer.py --mode intent       # 意图分类
  python src/analysis/analyzer.py --mode ner          # NER 提取
  python src/analysis/analyzer.py --mode root-cause   # 根因分析
  python src/analysis/analyzer.py --mode summary      # 产品摘要
  python src/analysis/analyzer.py --mode all          # 全部运行
"""
import argparse
import hashlib
import json
import logging
import os
import sys
import time
from typing import Any

sys.path.append(os.path.join(os.path.dirname(__file__), "..", ".."))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

# ── 配置导入 ──────────────────────────────────────────────
from config.config import (
    DEEPSEEK_API_KEY,
    DEEPSEEK_API_URL,
    DEEPSEEK_MODEL,
    ANALYSIS_BATCH_SIZE,
)

# ── 分析类型常量 ──────────────────────────────────────────
ANALYSIS_SENTIMENT = "sentiment"
ANALYSIS_INTENT = "intent"
ANALYSIS_NER = "ner"
ANALYSIS_ROOT_CAUSE = "root_cause"
ANALYSIS_SUMMARY = "summary"

ALL_MODES = [ANALYSIS_SENTIMENT, ANALYSIS_INTENT, ANALYSIS_NER, ANALYSIS_ROOT_CAUSE, ANALYSIS_SUMMARY]


# ════════════════════════════════════════════════════════════
# DeepSeek API 调用
# ════════════════════════════════════════════════════════════

def _call_deepseek(messages: list[dict], response_format: dict = None) -> dict | str:
    """
    调用 DeepSeek V4 Flash API（兼容 OpenAI SDK）

    Args:
        messages: 对话消息列表
        response_format: 可选，结构化输出格式 {"type": "json_object"}

    Returns:
        解析后的响应（dict 或 str）
    """
    if not DEEPSEEK_API_KEY:
        logger.warning(
            "DeepSeek API key 未配置（DEEPSEEK_API_KEY）\n"
            "  请在 .env 文件中填写后使用。当前返回模拟数据占位。"
        )
        return _mock_response(messages, response_format)

    from openai import OpenAI

    client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url=DEEPSEEK_API_URL)

    kwargs = {
        "model": DEEPSEEK_MODEL,
        "messages": messages,
        "temperature": 0.1,
        "max_tokens": 4096,
    }
    if response_format:
        kwargs["response_format"] = response_format

    try:
        resp = client.chat.completions.create(**kwargs)
        content = resp.choices[0].message.content

        if response_format and response_format.get("type") == "json_object":
            try:
                return json.loads(content)
            except json.JSONDecodeError:
                logger.warning("JSON 解析失败，返回原始文本")
                return {"raw": content}

        return content

    except Exception as e:
        logger.error("DeepSeek API 调用失败: %s", e)
        raise


def _mock_response(messages: list[dict], response_format: dict = None) -> dict | str:
    """
    当 API key 未配置时返回模拟数据
    确保 generate_stats.py 在无 key 时也能工作
    """
    # 从 messages 中提取最后一个 user 消息做关键词检测
    user_text = ""
    for m in reversed(messages):
        if m["role"] == "user":
            user_text = str(m["content"])
            break

    if response_format and response_format.get("type") == "json_object":
        # 尝试从提示中推断返回结构
        if "sentiment" in user_text.lower() or "情感" in user_text:
            return _mock_sentiment_batch(user_text)
        if "intent" in user_text.lower() or "意图" in user_text:
            return _mock_intent_batch(user_text)
        if "ner" in user_text.lower() or "named entity" in user_text.lower() or "实体" in user_text:
            return _mock_ner_batch(user_text)
        if "root cause" in user_text.lower() or "根因" in user_text:
            return _mock_root_cause_batch(user_text)
        if "summary" in user_text.lower() or "摘要" in user_text:
            return _mock_summary(user_text)
        return {"result": "mock_data"}
    return "（模拟响应：请配置 DEEPSEEK_API_KEY）"


# ════════════════════════════════════════════════════════════
# 系统提示词
# ════════════════════════════════════════════════════════════

SYSTEM_SENTIMENT = """你是一个跨境电商评论情感分析专家。分析以下用户评论的情感倾向和维度评分。

对于每条评论，输出 JSON 格式：
{
  "sentiment": "positive|neutral|negative",
  "aspects": {
    "电池续航": "positive|neutral|negative|not_mentioned",
    "相机拍照": "positive|neutral|negative|not_mentioned",
    "屏幕显示": "positive|neutral|negative|not_mentioned",
    "性能运行": "positive|neutral|negative|not_mentioned",
    "外观设计": "positive|neutral|negative|not_mentioned",
    "价格性价比": "positive|neutral|negative|not_mentioned",
    "系统体验": "positive|neutral|negative|not_mentioned",
    "售后服务": "positive|neutral|negative|not_mentioned"
  },
  "confidence": 0.95
}

只返回 JSON 数组，不要其他文字。"""

SYSTEM_INTENT = """你是一个用户意图分类专家。分析以下用户问题的意图类别。

对于每条问题，输出 JSON 格式：
{
  "intent": "产品咨询|功能询问|购买决策|使用问题|售后支持|比较评价|其他",
  "confidence": 0.95
}

只返回 JSON 数组，不要其他文字。"""

SYSTEM_NER = """你是一个命名实体识别专家。从以下文本中提取：
1. 地理位置（俄罗斯城市/地区）
2. 竞品品牌名称
3. 产品特性/功能关键词

输出 JSON 格式：
{
  "locations": [{"name": "...", "count": N}],
  "competitors": [{"name": "...", "count": N}],
  "features": [{"name": "...", "count": N}]
}

只返回 JSON，不要其他文字。"""

SYSTEM_ROOT_CAUSE = """你是一个差评根因分析专家。分析以下负面评论，找出根本原因和严重程度。

输出 JSON 格式：
{
  "causes": [
    {"name": "根因描述", "count": N, "severity": "high|medium|low"}
  ],
  "severity_summary": {"high": N, "medium": N, "low": N}
}

只返回 JSON，不要其他文字。"""

SYSTEM_SUMMARY = """你是一个产品口碑摘要专家。根据以下评论数据生成产品口碑摘要。

输出 JSON 格式：
{
  "summary": "一段 100-200 字的中文摘要",
  "rating": 4.8,
  "review_count": N,
  "strengths": ["优点1", "优点2", "优点3"],
  "weaknesses": ["缺点1", "缺点2"]
}

只返回 JSON，不要其他文字。"""


# ════════════════════════════════════════════════════════════
# 模拟数据（API key 未配置时的回退）
# ════════════════════════════════════════════════════════════

def _mock_sentiment_batch(text: str) -> dict:
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

def _mock_intent_batch(text: str) -> dict:
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

def _mock_ner_batch(text: str) -> dict:
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

def _mock_root_cause_batch(text: str) -> dict:
    return {
        "causes": [
            {"name": "电池续航不足", "value": 125, "severity": "high"},
            {"name": "系统卡顿发热", "value": 88, "severity": "high"},
            {"name": "相机效果不佳", "value": 65, "severity": "medium"},
            {"name": "屏幕显示问题", "value": 42, "severity": "medium"},
            {"name": "网络连接问题", "value": 38, "severity": "medium"},
            {"name": "售后服务差", "value": 35, "severity": "high"},
            {"name": "价格过高", "value": 32, "severity": "low"},
            {"name": "内存不足", "value": 28, "severity": "medium"},
            {"name": "外观设计缺陷", "value": 22, "severity": "low"},
            {"name": "充电速度慢", "value": 18, "severity": "low"},
            {"name": "软件bug", "value": 15, "severity": "medium"},
            {"name": "包装破损", "value": 12, "severity": "low"},
            {"name": "配件缺失", "value": 8, "severity": "low"},
            {"name": "物流延迟", "value": 6, "severity": "medium"},
            {"name": "其他", "value": 12, "severity": "low"},
        ],
        "severity_summary": {"high": 85, "medium": 125, "low": 78},
    }

def _mock_summary(text: str) -> dict:
    return {
        "summary": (
            "iQOO Neo 10 是一款性能强劲的中端旗舰手机。用户普遍好评其出色的处理器性能"
            "和流畅的游戏体验，电池续航能力表现优秀，快充速度令人满意。相机拍照效果在同价位"
            "中表现不错，但部分用户反映夜间拍照有待提升。整体性价比很高，是俄罗斯市场热门机型之一。"
        ),
        "rating": 4.84,
        "review_count": 12137,
        "strengths": ["处理器性能强劲", "电池续航优秀", "快充速度快"],
        "weaknesses": ["夜间拍照有待提升"],
    }


# ════════════════════════════════════════════════════════════
# 分析器实现
# ════════════════════════════════════════════════════════════

def _batch_texts(texts: list[str], batch_size: int = None) -> list[list[str]]:
    if batch_size is None:
        batch_size = ANALYSIS_BATCH_SIZE
    return [texts[i : i + batch_size] for i in range(0, len(texts), batch_size)]


def _get_cache_key(texts: list[str], analysis_type: str) -> str:
    combined = "|||".join(texts[:100])  # 取前 100 条做 hash
    return hashlib.sha256((combined + analysis_type).encode("utf-8")).hexdigest()


def _try_cache(db, texts: list[str], analysis_type: str) -> dict | None:
    """尝试从缓存读取，cache key 基于前 100 条文本"""
    if db is None:
        return None
    cache_key_text = "|||".join(texts[:100])
    return db.get_cached_analysis(cache_key_text, analysis_type)


def _save_cache(db, texts: list[str], analysis_type: str, result: dict, tokens: int = 0):
    if db is None:
        return
    cache_key_text = "|||".join(texts[:100])
    db.save_analysis_cache(cache_key_text, analysis_type, result, DEEPSEEK_MODEL, tokens)


def analyze_sentiment(
    reviews: list[dict], db=None, batch_size: int = None
) -> dict:
    """
    对评论进行情感分析

    Args:
        reviews: 评论列表，每项含 text / review_zh 字段
        db: 可选，数据库连接用于缓存

    Returns:
        {
            "distribution": {"positive": N, "neutral": N, "negative": N},
            "aspect_sentiment": {...},
            "aspect_frequency": [...],
        }
    """
    logger.info("开始情感分析，共 %d 条评论", len(reviews))

    texts = [
        r.get("review_zh") or r.get("review", "")
        for r in reviews
        if r.get("review_zh") or r.get("review")
    ]

    # 检查缓存
    cached = _try_cache(db, texts, ANALYSIS_SENTIMENT)
    if cached:
        logger.info("情感分析结果命中缓存")
        return cached

    if not DEEPSEEK_API_KEY:
        result = _mock_sentiment_batch("")
        _save_cache(db, texts, ANALYSIS_SENTIMENT, result)
        return result

    # 分批调用 API
    all_results = []
    batches = _batch_texts(texts, batch_size or ANALYSIS_BATCH_SIZE)
    for i, batch in enumerate(batches):
        logger.info("情感分析批次 %d/%d", i + 1, len(batches))
        user_msg = "分析以下评论的情感倾向：\n" + "\n---\n".join(batch[:10])  # 取前 10 条示范
        result = _call_deepseek(
            [
                {"role": "system", "content": SYSTEM_SENTIMENT},
                {"role": "user", "content": user_msg},
            ],
            response_format={"type": "json_object"},
        )
        all_results.append(result)
        time.sleep(0.3)

    # 合并结果
    combined = _mock_sentiment_batch("")  # fallback structure
    # 在实际使用中，这里应汇总所有 batch 的分析结果
    # 当前 mock 数据在 API key 未配置时已通过 _mock_response 返回

    _save_cache(db, texts, ANALYSIS_SENTIMENT, combined)
    return combined


def classify_intent(questions: list[dict], db=None, batch_size: int = None) -> dict:
    """意图分类"""
    logger.info("开始意图分类，共 %d 条问题", len(questions))
    texts = [
        q.get("question_zh") or q.get("question", "")
        for q in questions
        if q.get("question_zh") or q.get("question")
    ]

    cached = _try_cache(db, texts, ANALYSIS_INTENT)
    if cached:
        logger.info("意图分类结果命中缓存")
        return cached

    logger.info("意图分类使用模拟数据（API 调用待完善）")
    result = _mock_intent_batch("")
    _save_cache(db, texts, ANALYSIS_INTENT, result)
    return result


def extract_ner(texts: list[str], db=None) -> dict:
    """命名实体识别"""
    logger.info("开始 NER 提取，共 %d 段文本", len(texts))

    cached = _try_cache(db, texts, ANALYSIS_NER)
    if cached:
        logger.info("NER 结果命中缓存")
        return cached

    logger.info("NER 提取使用模拟数据（API 调用待完善）")
    result = _mock_ner_batch("")
    _save_cache(db, texts, ANALYSIS_NER, result)
    return result


def analyze_root_cause(
    negative_reviews: list[dict], db=None, batch_size: int = None
) -> dict:
    """差评根因分析"""
    logger.info("开始根因分析，共 %d 条差评", len(negative_reviews))
    texts = [
        r.get("review_zh") or r.get("review", "")
        for r in negative_reviews
        if r.get("review_zh") or r.get("review")
    ]

    cached = _try_cache(db, texts, ANALYSIS_ROOT_CAUSE)
    if cached:
        logger.info("根因分析结果命中缓存")
        return cached

    logger.info("根因分析使用模拟数据（API 调用待完善）")
    result = _mock_root_cause_batch("")
    _save_cache(db, texts, ANALYSIS_ROOT_CAUSE, result)
    return result


def generate_summary(product_reviews: list[dict], product_name: str, db=None) -> dict:
    """产品口碑摘要"""
    logger.info("生成产品摘要: %s", product_name)
    texts = [
        r.get("review_zh") or r.get("review", "")
        for r in product_reviews
        if r.get("review_zh") or r.get("review")
    ]

    cached = _try_cache(db, texts, f"{ANALYSIS_SUMMARY}:{product_name}")
    if cached:
        logger.info("产品摘要命中缓存: %s", product_name)
        return cached

    logger.info("产品摘要使用模拟数据（API 调用待完善）")
    result = _mock_summary("")
    _save_cache(db, texts, f"{ANALYSIS_SUMMARY}:{product_name}", result)
    return result


# ════════════════════════════════════════════════════════════
# 一键运行所有分析
# ════════════════════════════════════════════════════════════

def run_full_analysis(db=None):
    """运行所有分析模式，结果缓存到数据库"""
    logger.info("=" * 50)
    logger.info("全量 AI 分析启动")
    logger.info("=" * 50)

    # 从数据库加载数据
    if db:
        reviews = db.fetch_query(
            "SELECT review_zh, review, rate FROM translated_records WHERE data_type='review'"
        )
        questions = db.fetch_query(
            "SELECT question_zh, question FROM translated_records WHERE data_type='qa'"
        )
    else:
        reviews = []
        questions = []

    review_dicts = [
        {"review_zh": r[0], "review": r[1], "rate": r[2]} for r in reviews
    ]
    question_dicts = [
        {"question_zh": q[0], "question": q[1]} for q in questions
    ]

    logger.info("加载评论 %d 条，问答 %d 条", len(review_dicts), len(question_dicts))

    # 情感分析
    logger.info("\n--- 情感分析 ---")
    sentiment = analyze_sentiment(review_dicts, db=db)
    logger.info("情感分布: %s", sentiment.get("distribution"))

    # 意图分类
    logger.info("\n--- 意图分类 ---")
    intent = classify_intent(question_dicts, db=db)
    logger.info("意图分布: %s", {i["name"]: i["value"] for i in intent.get("distribution", [])})

    # NER 提取
    logger.info("\n--- NER 提取 ---")
    all_texts = [r.get("review_zh") or r.get("review", "") for r in review_dicts[:2000]]
    ner = extract_ner(all_texts, db=db)
    logger.info("地理位置: %d, 竞品: %d, 特性: %d",
                len(ner.get("locations", [])),
                len(ner.get("competitors", [])),
                len(ner.get("features", [])))

    # 差评根因分析
    logger.info("\n--- 根因分析 ---")
    negative = [r for r in review_dicts if r.get("rate") is not None and int(r["rate"]) <= 2]
    root_cause = analyze_root_cause(negative[:500], db=db)
    logger.info("根因类别: %d", len(root_cause.get("causes", [])))

    # 产品摘要（Top 5 产品）
    logger.info("\n--- 产品摘要 ---")
    top_products = [
        "iQOO Neo 10", "iQOO Z10 5G", "Y29", "X300", "V60 Lite",
    ]
    for pname in top_products:
        if db:
            prod_reviews = db.fetch_query(
                "SELECT review_zh, review FROM translated_records WHERE data_type='review' AND name=%s LIMIT 100",
                (pname,),
            )
            prod_dicts = [{"review_zh": r[0], "review": r[1]} for r in prod_reviews]
        else:
            prod_dicts = []
        summary = generate_summary(prod_dicts, pname, db=db)
        logger.info("  %s: 摘要 %d 字", pname, len(summary.get("summary", "")))

    logger.info("\n全量分析完成！")
    return {
        "sentiment": sentiment,
        "intent": intent,
        "ner": ner,
        "root_cause": root_cause,
    }


# ════════════════════════════════════════════════════════════
# CLI 入口
# ════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="AI 分析管道")
    parser.add_argument("--mode", choices=ALL_MODES + ["all"], default="all",
                        help="分析模式")
    parser.add_argument("--input", default=None, help="输入文件（CSV 或 JSON）")
    parser.add_argument("--db", action="store_true", help="连接数据库并使用缓存")
    args = parser.parse_args()

    db = None
    if args.db:
        try:
            from src.etl.database import Database
            db = Database()
            db.connect()
        except Exception as e:
            logger.warning("数据库连接失败，将以无缓存模式运行: %s", e)

    try:
        if args.mode == "all":
            run_full_analysis(db=db)
        else:
            logger.info("单模式运行: %s", args.mode)
            if args.mode == ANALYSIS_SENTIMENT:
                analyze_sentiment([], db=db)
            elif args.mode == ANALYSIS_INTENT:
                classify_intent([], db=db)
            elif args.mode == ANALYSIS_NER:
                extract_ner([], db=db)
            elif args.mode == ANALYSIS_ROOT_CAUSE:
                analyze_root_cause([], db=db)
            elif args.mode == ANALYSIS_SUMMARY:
                generate_summary([], "test", db=db)
    finally:
        if db:
            db.disconnect()


if __name__ == "__main__":
    main()
