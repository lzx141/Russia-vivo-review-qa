"""
AI 分析模块 — DeepSeek V4 Flash API 封装
提供情感分析、意图分类、NER 提取、根因分析、产品摘要
"""
from .analyzer import (
    analyze_sentiment,
    classify_intent,
    extract_ner,
    analyze_root_cause,
    generate_summary,
    run_full_analysis,
)

__all__ = [
    "analyze_sentiment",
    "classify_intent",
    "extract_ner",
    "analyze_root_cause",
    "generate_summary",
    "run_full_analysis",
]
