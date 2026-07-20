"""
翻译模块 — 火山引擎翻译 API 封装
支持俄语 → 中文 / 英文批量翻译，断点续传
"""
from .translate import call_volc_translate, run_pipeline

__all__ = ["call_volc_translate", "run_pipeline"]
