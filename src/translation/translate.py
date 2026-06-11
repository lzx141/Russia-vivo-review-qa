"""
翻译管道 — 俄语 → 中文 / 英文
使用火山引擎翻译 API（token 需在 config 或 .env 中填写后生效）

用法：
  python src/translation/translate.py                        # 完整流程
  python src/translation/translate.py --from-csv             # 仅对 CSV 中未翻译部分进行翻译
  python src/translation/translate.py --resume               # 断点续传
"""
import argparse
import hashlib
import json
import logging
import os
import sys
import time

sys.path.append(os.path.join(os.path.dirname(__file__), "..", ".."))

from config.config import (
    VOLC_ACCESS_KEY,
    VOLC_SECRET_KEY,
    VOLC_TRANSLATE_URL,
    VOLC_TRANSLATE_BATCH_SIZE,
    DATA_PATHS,
    MERGED_TRANSLATED_CSV,
    PROJECT_ROOT,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

# ── 进度文件（用于断点续传）────────────────────────────
PROGRESS_FILE = os.path.join(PROJECT_ROOT, ".translate_progress.json")


# ════════════════════════════════════════════════════════════
# 火山引擎翻译 API 封装
# ════════════════════════════════════════════════════════════

def call_volc_translate(texts: list[str], target_lang: str = "zh") -> list[str]:
    """
    调用火山引擎翻译 API
    注意：token 需在 .env 中配置 VOLC_ACCESS_KEY / VOLC_SECRET_KEY
    使用前请先填写对应值

    Args:
        texts: 待翻译文本列表
        target_lang: 目标语言，zh 或 en

    Returns:
        翻译后的文本列表（顺序与输入一致）
    """
    if not texts:
        return []

    if not VOLC_ACCESS_KEY or not VOLC_SECRET_KEY:
        logger.warning(
            "火山引擎 API token 未配置（VOLC_ACCESS_KEY / VOLC_SECRET_KEY）\n"
            "  请在 .env 文件中填写后使用，当前返回空字符串占位。"
        )
        return [""] * len(texts)

    # ── 以下为火山引擎翻译 API 调用示例 ──
    # 实际使用时取消注释并实现签名逻辑

    # import hashlib
    # import hmac
    # import requests
    # from urllib.parse import urlencode
    #
    # def _sign_request(params: dict) -> dict:
    #     """火山引擎 HMAC-SHA256 签名"""
    #     ...
    #
    # payload = {
    #     "source_language": "ru",
    #     "target_language": target_lang,
    #     "text_list": texts,
    # }
    # headers = {
    #     "Content-Type": "application/json",
    #     "X-Date": ...,
    #     "Authorization": ...,
    # }
    # resp = requests.post(VOLC_TRANSLATE_URL, json=payload, headers=headers, timeout=30)
    # result = resp.json()
    # return [item["translation"] for item in result.get("translation_list", [])]

    # ── 占位实现：返回原文（待配置 token 后替换）──
    logger.info("[占位] 翻译 %d 条文本 → %s（请配置 VOLC API token）", len(texts), target_lang)
    return texts  # 占位


# ════════════════════════════════════════════════════════════
# 数据加载
# ════════════════════════════════════════════════════════════

def load_raw_excel_data() -> dict:
    """从原始 Excel 加载数据"""
    import pandas as pd

    all_reviews = []
    all_questions = []

    for key, paths in DATA_PATHS.items():
        for rel_path in paths:
            full_path = os.path.join(PROJECT_ROOT, rel_path)
            if not os.path.exists(full_path):
                logger.warning("文件不存在: %s", full_path)
                continue
            try:
                df = pd.read_excel(full_path, engine="openpyxl", dtype=str)
                df["source_file"] = os.path.basename(rel_path)
                if "review" in key:
                    df["data_type"] = "review"
                    all_reviews.append(df)
                else:
                    df["data_type"] = "qa"
                    all_questions.append(df)
                logger.info("读取: %s → %d 行", rel_path, len(df))
            except Exception as e:
                logger.error("读取失败 %s: %s", rel_path, e)

    return {"reviews": all_reviews, "questions": all_questions}


def load_csv_translated() -> list[dict]:
    """加载已翻译的 CSV（用于断点续传）"""
    import pandas as pd

    if not os.path.exists(MERGED_TRANSLATED_CSV):
        return []
    df = pd.read_csv(MERGED_TRANSLATED_CSV, encoding="utf-8", dtype=str)
    df = df.where(df.notna(), None)
    return df.to_dict("records")


# ════════════════════════════════════════════════════════════
# 翻译处理
# ════════════════════════════════════════════════════════════

def _content_hash(text: str) -> str:
    return hashlib.md5((text or "").encode("utf-8")).hexdigest()


def _needs_translation(records: list[dict], lang_suffix: str) -> list[int]:
    """找出需要翻译的记录索引（译文为空或缺失的）"""
    idxs = []
    for i, rec in enumerate(records):
        field = f"review_{lang_suffix}"
        if rec.get("data_type") == "qa":
            field_q = f"question_{lang_suffix}"
            field_a = f"answer_{lang_suffix}"
            if not rec.get(field_q) and not rec.get(field_a):
                idxs.append(i)
        else:
            if not rec.get(field):
                idxs.append(i)
    return idxs


def translate_records(
    records: list[dict],
    target_lang: str = "zh",
    batch_size: int = None,
) -> list[dict]:
    """
    对记录进行翻译
    返回更新后的 records（原地 + 返回）
    """
    if batch_size is None:
        batch_size = VOLC_TRANSLATE_BATCH_SIZE

    suffix = target_lang
    need_ids = _needs_translation(records, suffix)
    logger.info("需要翻译 %s → %s 的记录数: %d", target_lang, suffix, len(need_ids))

    if not need_ids:
        logger.info("所有记录已翻译完成")
        return records

    # 收集待翻译文本
    to_translate = []
    meta = []  # (index, field_name)
    for idx in need_ids:
        rec = records[idx]
        if rec.get("data_type") == "qa":
            q_text = rec.get("question", "")
            a_text = rec.get("answer", "")
            if q_text:
                to_translate.append(q_text)
                meta.append((idx, f"question_{suffix}"))
            if a_text:
                to_translate.append(a_text)
                meta.append((idx, f"answer_{suffix}"))
        else:
            r_text = rec.get("review", "")
            if r_text:
                to_translate.append(r_text)
                meta.append((idx, f"review_{suffix}"))

    # 分批翻译
    logger.info("共计 %d 段文本需要翻译", len(to_translate))
    for i in range(0, len(to_translate), batch_size):
        batch_texts = to_translate[i : i + batch_size]
        batch_meta = meta[i : i + batch_size]
        translations = call_volc_translate(batch_texts, target_lang)
        for (rec_idx, field), trans_text in zip(batch_meta, translations):
            records[rec_idx][field] = trans_text
        logger.info("翻译进度: %d/%d", min(i + batch_size, len(to_translate)), len(to_translate))
        time.sleep(0.5)  # API 频率控制

    return records


# ════════════════════════════════════════════════════════════
# 输出 & 进度管理
# ════════════════════════════════════════════════════════════

def save_progress(records_count: int):
    """保存翻译进度"""
    with open(PROGRESS_FILE, "w", encoding="utf-8") as f:
        json.dump({"translated_count": records_count, "updated_at": time.time()}, f)


def load_progress() -> int:
    """读取已翻译的记录数"""
    if not os.path.exists(PROGRESS_FILE):
        return 0
    with open(PROGRESS_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
        return data.get("translated_count", 0)


def merge_and_save(all_records: list[dict]):
    """将翻译后的数据合并输出为 CSV"""
    import pandas as pd

    df = pd.DataFrame(all_records)

    # 确保列顺序一致
    columns = [
        "data_type", "source_file", "author", "publishDate", "rate",
        "question", "answer", "review", "name", "SKU", "URL", "siteName",
        "question_zh", "question_en", "answer_zh", "answer_en", "review_zh", "review_en",
    ]
    for col in columns:
        if col not in df.columns:
            df[col] = None
    df = df[columns]

    df.to_csv(MERGED_TRANSLATED_CSV, index=False, encoding="utf-8")
    logger.info("翻译结果已保存到 %s（共 %d 条）", MERGED_TRANSLATED_CSV, len(df))

    # 同时保存一份 xlsx
    try:
        xlsx_path = MERGED_TRANSLATED_CSV.replace(".csv", ".xlsx")
        df.to_excel(xlsx_path, index=False, engine="openpyxl")
        logger.info("已同步保存 xlsx: %s", xlsx_path)
    except Exception as e:
        logger.warning("xlsx 保存失败: %s", e)

    save_progress(len(df))


# ════════════════════════════════════════════════════════════
# 主流程
# ════════════════════════════════════════════════════════════

def run_pipeline(from_csv: bool = False, resume: bool = False):
    """执行完整翻译管道"""
    logger.info("=" * 50)
    logger.info("翻译管道启动")
    logger.info("=" * 50)

    if from_csv:
        # 从已有 CSV 加载（增量翻译）
        records = load_csv_translated()
        if not records:
            logger.error("CSV 文件为空或不存在，请先生成")
            return
        logger.info("从 CSV 加载 %d 条记录", len(records))
    else:
        # 从原始 Excel 加载
        raw = load_raw_excel_data()
        records = []
        for dfs in raw.values():
            for df in dfs:
                records.extend(df.to_dict("records"))
        logger.info("从原始 Excel 加载 %d 条记录", len(records))

    if not records:
        logger.error("无数据可翻译")
        return

    if resume:
        done = load_progress()
        logger.info("断点续传模式：已有 %d 条已翻译", done)
        if done < len(records):
            records = records[done:]
            logger.info("继续翻译剩余 %d 条", len(records))
        else:
            logger.info("全部已完成")
            return

    # 翻译 → 中文
    logger.info("--- 翻译为中文 ---")
    records = translate_records(records, target_lang="zh")

    # 翻译 → 英文
    logger.info("--- 翻译为英文 ---")
    records = translate_records(records, target_lang="en")

    # 输出
    merge_and_save(records)
    logger.info("翻译管道完成")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="俄语→中/英 翻译管道")
    parser.add_argument("--from-csv", action="store_true", help="从已有 CSV 增量翻译")
    parser.add_argument("--resume", action="store_true", help="断点续传")
    args = parser.parse_args()
    run_pipeline(from_csv=args.from_csv, resume=args.resume)
