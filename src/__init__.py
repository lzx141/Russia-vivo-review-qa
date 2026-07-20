"""
跨境电商多语言用户反馈智能分析系统

模块架构：
  src/crawler/    — 数据采集（Wildberries / OZON）
  src/etl/        — ETL 管道（清洗 → 转换 → 加载）
  src/translation/— 多语言翻译（火山引擎 API）
  src/analysis/   — AI 分析（DeepSeek V4 Flash）
  src/dashboard/  — 可视化大屏（ECharts 5.5）
"""
