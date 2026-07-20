"""
tests/

项目测试目录 — 使用 unittest 框架

运行方式：
  # 运行所有测试
  python -m unittest discover tests -v

  # 运行单个测试文件
  python -m unittest tests.test_etl -v

  # 运行特定测试类
  python -m unittest tests.test_etl.TestETLProcessor -v

测试范围：
  test_etl.py       — ETL 处理器 + 数据库操作 + 配置
  (待添加)           — 翻译管道、AI 分析、仪表盘
"""
