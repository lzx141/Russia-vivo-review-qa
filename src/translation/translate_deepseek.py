"""
增量翻译脚本 — 使用 DeepSeek API（俄语 → 中文）
=================================================

背景：
  原始翻译管道依赖火山引擎 API，token 未配置时仅返回占位符。
  本脚本改用 DeepSeek API 完成新增数据的俄→中翻译，
  并复用 merged_data_translated.csv 中已翻译的记录，实现增量合并。

逻辑：
  1. 读取旧 merged_data_translated.csv（已翻译部分）
  2. 从 DATA_PATHS 全部原始 Excel 重新抽取记录，按 (source_file, 内容) 去重
  3. 只对新增记录中缺失 review_zh 的文本调用 DeepSeek 翻译
  4. 合并为新的 CSV（保证列结构与旧版一致）

用法：
  python src/translation/translate_deepseek.py            # 全量增量翻译
  python src/translation/translate_deepseek.py --dry-run  # 仅统计待翻译数量，不调用 API
"""
import argparse
import json
import logging
import os
import sys
import time
from typing import Optional

sys.path.append(os.path.join(os.path.dirname(__file__), "..", ".."))

from config.config import (
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


# ════════════════════════════════════════════════════════════
# DeepSeek 翻译调用（批量）
# ════════════════════════════════════════════════════════════

BATCH_TRANSLATE_SIZE = 40
PROGRESS_JSON = os.path.join(PROJECT_ROOT, ".translate_deepseek_progress.json")


def translate_batch(
    texts: list[str],
    model: str = "deepseek-chat",
) -> list[str]:
    """一次调用 DeepSeek 批量翻译多段俄语文本为中文"""
    from openai import OpenAI
    from config.config import DEEPSEEK_API_KEY, DEEPSEEK_API_URL

    client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url=DEEPSEEK_API_URL)
    numbered = "\n".join(f"{i + 1}. {t}" for i, t in enumerate(texts))
    resp = client.chat.completions.create(
        model=model,
        messages=[
            {
                "role": "system",
                "content": (
                    "你是专业的俄语→简体中文翻译。把用户给出的每条俄语文本翻译成中文，"
                    "保留原有的序号，每条一行，只输出译文本身，不要任何解释、空白行或额外文字。"
                    "保留数字、型号、品牌名等专有名词的原文。"
                ),
            },
            {"role": "user", "content": numbered},
        ],
        temperature=0.1,
        max_tokens=2048,
    )
    out = (resp.choices[0].message.content or "").strip()
    # 解析序号 → 译文
    lines = [ln.strip() for ln in out.splitlines() if ln.strip()]
    results: list[str] = []
    for i in range(len(texts)):
        translated = ""
        # 匹配 "i." 前缀
        for ln in lines:
            for sep in (".", "、", ")"):
                idx = ln.find(sep)
                if idx > 0 and ln[:idx].strip() == str(i + 1):
                    translated = ln[idx + 1:].strip()
                    break
            if translated:
                break
        results.append(translated)
    return results


def translate_texts_batch(
    texts: list[str],
    model: str = "deepseek-chat",
    progress_cb: Optional[callable] = None,
) -> list[str]:
    """批量调用 DeepSeek 翻译，返回译文列表（与输入顺序一致），可断点续传"""
    results = load_translation_progress(len(texts))
    for i, t in enumerate(texts):
        if results[i]:
            continue
        t = (t or "").strip()
        if not t or len(t) <= 1:
            results[i] = t
        elif _looks_chinese(t):
            results[i] = t

    pending = [i for i, r in enumerate(results) if not r]
    done = len(texts) - len(pending)
    for start in range(0, len(pending), BATCH_TRANSLATE_SIZE):
        idxs = pending[start:start + BATCH_TRANSLATE_SIZE]
        batch_texts = [texts[i] for i in idxs]
        try:
            translated = translate_batch(batch_texts, model=model)
            for i, tr in zip(idxs, translated):
                results[i] = tr.strip()
        except Exception as e:
            logger.error("批次翻译失败: %s", e)
            for i in idxs:
                results[i] = ""
        done += len(idxs)
        # 实时持久化进度
        _persist_progress(results)
        if progress_cb:
            progress_cb(done, len(texts))
    return results


def _persist_progress(results: list[str]):
    """把当前译文结果写到进度文件（仅存非空译文），支持断点续传"""
    try:
        data = {
            "results": {i: r for i, r in enumerate(results) if r},
            "updated_at": time.time(),
        }
        with open(PROGRESS_JSON, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
    except Exception:
        pass


def load_translation_progress(n: int) -> list[str]:
    """读取进度文件，返回与目标长度对齐的译文列表（未翻译部分为空字符串）"""
    results: list[str] = [""] * n
    if not os.path.exists(PROGRESS_JSON):
        return results
    try:
        with open(PROGRESS_JSON, "r", encoding="utf-8") as f:
            data = json.load(f)
        for k, v in data.get("results", {}).items():
            idx = int(k)
            if 0 <= idx < n:
                results[idx] = v
        return results
    except Exception:
        return results


def _looks_chinese(text: str) -> bool:
    """粗略判断文本是否已含中文字符（已翻译过则跳过）"""
    for ch in text:
        if "一" <= ch <= "鿿":
            return True
    return False


# ════════════════════════════════════════════════════════════
# 数据加载与合并
# ════════════════════════════════════════════════════════════

CSV_COLUMNS = [
    "data_type", "source_file", "author", "publishDate", "rate",
    "question", "answer", "review", "name", "SKU", "URL", "siteName",
    "question_zh", "question_en", "answer_zh", "answer_en", "review_zh", "review_en",
]


def _cell_text(val) -> str:
    """Excel 单元格 → 字符串（去掉 .0 尾缀等）"""
    if val is None:
        return ""
    s = str(val).strip()
    if s.endswith(".0") and s[:-2].isdigit():
        return s[:-2]
    return s


def load_old_csv() -> dict:
    """读取旧 CSV，返回 {dedup_key: record}，并记录每个 source_file 已处理数量"""
    import pandas as pd

    if not os.path.exists(MERGED_TRANSLATED_CSV):
        return {}
    df = pd.read_csv(MERGED_TRANSLATED_CSV, encoding="utf-8", dtype=str, low_memory=False)
    df = df.where(df.notna(), None)
    out = {}
    for rec in df.to_dict("records"):
        key = dedup_key(
            rec.get("source_file", ""),
            rec.get("question", "") or "",
            rec.get("answer", "") or "",
            rec.get("review", "") or "",
        )
        out[key] = rec
    logger.info("旧 CSV 加载 %d 条记录", len(out))
    return out


def load_old_csv_as_list() -> list:
    """读取旧 CSV 全部记录（保留逐行内容与顺序，不做去重）"""
    import pandas as pd

    if not os.path.exists(MERGED_TRANSLATED_CSV):
        return []
    df = pd.read_csv(MERGED_TRANSLATED_CSV, encoding="utf-8", dtype=str, low_memory=False)
    df = df.where(df.notna(), None)
    return df.to_dict("records")


def dedup_key(source_file: str, question: str, answer: str, review: str) -> str:
    """去重键：来源文件 + 俄语正文"""
    import hashlib

    payload = "|".join([source_file, question, answer, review])
    return hashlib.md5(payload.encode("utf-8")).hexdigest()


def extract_all_raw() -> list[dict]:
    """从 DATA_PATHS 所有原始 Excel 抽取记录，转为 CSV 行结构"""
    import pandas as pd

    records: list[dict] = []
    seen_keys: set = set()

    for group, paths in DATA_PATHS.items():
        data_type = "review" if "review" in group else "qa"
        for rel_path in paths:
            full_path = os.path.join(PROJECT_ROOT, rel_path)
            if not os.path.exists(full_path):
                logger.warning("文件不存在: %s", full_path)
                continue
            try:
                df = pd.read_excel(full_path, engine="openpyxl", dtype=str)
            except Exception as e:
                logger.error("读取失败 %s: %s", rel_path, e)
                continue

            source_file = os.path.basename(rel_path)
            added = 0
            for _, row in df.iterrows():
                rec = _row_to_record(row, source_file, data_type)
                key = dedup_key(
                    source_file,
                    rec.get("question", "") or "",
                    rec.get("answer", "") or "",
                    rec.get("review", "") or "",
                )
                if key in seen_keys:
                    continue
                seen_keys.add(key)
                records.append(rec)
                added += 1
            logger.info("  ✓ %s → %d 行（去重后 %d）", rel_path, len(df), added)

    return records


def _row_to_record(row, source_file: str, data_type: str) -> dict:
    """Excel 行 → CSV 标准字段记录"""
    def g(*names):
        for n in names:
            if n in row and row[n] is not None:
                return _cell_text(row[n])
        return ""

    rec = {
        "data_type": data_type,
        "source_file": source_file,
        "author": g("author", "Author"),
        "publishDate": g("publishDate", "PublishDate"),
        "rate": g("rate", "Rate", "rating"),
        "question": g("question", "Question"),
        "answer": g("content", "answer", "Content"),
        "review": g("content", "review_text", "Content", "review"),
        "name": g("name", "Name"),
        "SKU": g("SKU", "sku"),
        "URL": g("URL", "url"),
        "siteName": g("siteName", "SiteName"),
        "question_zh": "", "question_en": "",
        "answer_zh": "", "answer_en": "",
        "review_zh": "", "review_en": "",
    }
    # qa：question 列有值则正文为 question，answer 取自 content
    if data_type == "qa" and rec["question"]:
        rec["review"] = ""
        rec["answer"] = g("content", "answer", "Content")
    else:
        rec["question"] = ""
        rec["answer"] = ""
    return rec


# ════════════════════════════════════════════════════════════
# 主流程
# ════════════════════════════════════════════════════════════

def run_incremental(dry_run: bool = False):
    logger.info("=" * 60)
    logger.info("增量翻译（DeepSeek）启动")
    logger.info("=" * 60)

    old_records = load_old_csv_as_list()
    # 旧 CSV 内容指纹，用于判断新文件记录是否已存在
    old_fp = _content_fingerprints(old_records)
    old_keys = {_rec_key(r) for r in old_records}
    logger.info("旧 CSV 记录 %d 条", len(old_records))

    raw = extract_all_raw()
    logger.info("原始数据抽取共 %d 条（含旧文件）", len(raw))

    # 仅保留真正新增的记录（不在旧 CSV 指纹集合中）
    new_records = []
    seen_new: set = set()
    for rec in raw:
        if rec["data_type"] == "review":
            body = rec.get("review") or ""
            if not body or _fp(body) in old_fp["review"]:
                continue
        else:
            body = (rec.get("question") or "") + "|" + (rec.get("answer") or "")
            if not body.strip("|"):
                continue
            if _fp((rec.get("question") or "")) in old_fp["qa"] or _fp((rec.get("answer") or "")) in old_fp["qa"]:
                continue
        key = _rec_key(rec)
        if key in old_keys or key in seen_new:
            continue
        seen_new.add(key)
        new_records.append(rec)

    logger.info("真正新增记录 %d 条", len(new_records))

    # 找出需要翻译的文本段
    to_translate = []
    for rec in new_records:
        if rec["data_type"] == "qa":
            if rec.get("question"):
                to_translate.append((rec, "question_zh", rec["question"]))
            if rec.get("answer"):
                to_translate.append((rec, "answer_zh", rec["answer"]))
        else:
            if rec.get("review"):
                to_translate.append((rec, "review_zh", rec["review"]))

    logger.info("待翻译文本段数: %d", len(to_translate))
    if dry_run:
        logger.info("[dry-run] 不调用 API，直接结束")
        return

    if not to_translate:
        logger.info("无需翻译，直接合并输出。")
        merge_and_save(old_records + new_records)
        return

    # 一次性批量翻译（内部按 BATCH_TRANSLATE_SIZE 分批并持久化进度，支持断点续传）
    texts = [it[2] for it in to_translate]
    done_results = load_translation_progress(len(texts))
    pending_count = sum(1 for r in done_results if not r)
    logger.info("进度文件中已有 %d/%d 段译文，剩余 %d 段待翻译",
                len(texts) - pending_count, len(texts), pending_count)

    results = translate_texts_batch(texts, progress_cb=lambda d, t: logger.info(
        "翻译进度 %d/%d (%.0f%%)", d, t, d / max(t, 1) * 100
    ))
    for item, translated in zip(to_translate, results):
        rec, field, _t = item
        if translated:
            rec[field] = translated

    # 仍未翻译成功的段，做中文占位标记，避免后续误判为未处理
    for rec, field, text in to_translate:
        if not rec.get(field):
            rec[field] = f"[翻译失败，原文] {text}" if text else ""

    merge_and_save(old_records + new_records)
    logger.info("增量翻译完成")


def _fp(text: str) -> str:
    import hashlib

    return hashlib.md5((text or "").encode("utf-8")).hexdigest()


def _content_fingerprints(records: list) -> dict:
    """旧 CSV 中 review / question 正文的指纹集合"""
    fp_review = set()
    fp_qa = set()
    for r in records:
        if r.get("data_type") == "review" and r.get("review"):
            fp_review.add(_fp(r["review"]))
        else:
            if r.get("question"):
                fp_qa.add(_fp(r["question"]))
            if r.get("answer"):
                fp_qa.add(_fp(r["answer"]))
    return {"review": fp_review, "qa": fp_qa}


def _rec_key(rec: dict) -> str:
    return dedup_key(
        rec.get("source_file", ""),
        rec.get("question", "") or "",
        rec.get("answer", "") or "",
        rec.get("review", "") or "",
    )


def merge_and_save(records: list):
    """写出最终 CSV（保持列顺序与旧版一致）"""
    import pandas as pd

    df = pd.DataFrame(records)
    for col in CSV_COLUMNS:
        if col not in df.columns:
            df[col] = None
    df = df[CSV_COLUMNS]
    # rate 保持字符串；publishDate 统一格式
    df.to_csv(MERGED_TRANSLATED_CSV, index=False, encoding="utf-8")
    logger.info("CSV 已保存: %s（共 %d 条）", MERGED_TRANSLATED_CSV, len(df))

    try:
        xlsx_path = MERGED_TRANSLATED_CSV.replace(".csv", ".xlsx")
        df.to_excel(xlsx_path, index=False, engine="openpyxl")
        logger.info("已同步保存 xlsx: %s", xlsx_path)
    except Exception as e:
        logger.warning("xlsx 保存失败: %s", e)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="DeepSeek 增量翻译（俄→中）")
    parser.add_argument("--dry-run", action="store_true", help="仅统计待翻译数量，不调用 API")
    args = parser.parse_args()
    run_incremental(dry_run=args.dry_run)
