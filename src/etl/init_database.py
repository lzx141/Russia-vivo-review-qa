"""
数据库初始化脚本
用法：
  python init_database.py                    # 仅创建表
  python init_database.py --load-translated  # 创建表 + 从 CSV 导入翻译数据
  python init_database.py --run-analysis     # 创建表 + 导入 + 运行 AI 分析
"""
import argparse
import logging
import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), "..", ".."))

from config.config import MERGED_TRANSLATED_CSV
from src.etl.database import Database

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


def create_database():
    """创建数据库（如果不存在）"""
    import mysql.connector
    from config.config import DB_CONFIG

    try:
        conn = mysql.connector.connect(
            host=DB_CONFIG["host"],
            port=DB_CONFIG["port"],
            user=DB_CONFIG["user"],
            password=DB_CONFIG["password"],
        )
        if conn.is_connected():
            cursor = conn.cursor()
            cursor.execute(f"CREATE DATABASE IF NOT EXISTS {DB_CONFIG['database']}")
            logger.info("数据库 %s 创建/确认成功", DB_CONFIG["database"])
            cursor.close()
            conn.close()
    except Exception as e:
        logger.error("创建数据库失败: %s", e)
        raise


def load_translated_csv(db: Database, csv_path: str, batch_size: int = 2000):
    """从 CSV 导入翻译数据到 translated_records 表"""
    import pandas as pd
    from datetime import datetime

    if not os.path.exists(csv_path):
        logger.error("CSV 文件不存在: %s", csv_path)
        return

    logger.info("开始从 %s 加载翻译数据...", csv_path)

    # 读取 CSV，指定所有列 dtypes 为 str 以保持兼容
    df = pd.read_csv(csv_path, encoding="utf-8", dtype=str, low_memory=False)
    total = len(df)
    logger.info("CSV 共 %s 行", total)

    # 获取数据库中已有记录数（用于断点续传）
    existing = db.get_table_count("translated_records")
    logger.info("数据库中已有 %s 条翻译记录", existing)

    if existing >= total:
        logger.info("数据已全部导入，跳过")
        return

    # 从断点处开始
    df = df.iloc[existing:]
    logger.info("待导入 %s 条", len(df))

    # 填充 NaN
    df = df.where(df.notna(), None)

    # 将 DataFrame 行转为字典列表
    records = df.to_dict("records")
    inserted = 0

    from tqdm import tqdm

    for i in tqdm(range(0, len(records), batch_size), desc="导入翻译数据"):
        batch = records[i : i + batch_size]
        count = db.insert_translated_records_batch(batch)
        inserted += count

    logger.info("导入完成，共导入 %s 条", inserted)


def main():
    parser = argparse.ArgumentParser(description="数据库初始化工具")
    parser.add_argument(
        "--load-translated",
        action="store_true",
        help="创建表并从 merged_data_translated.csv 导入数据",
    )
    parser.add_argument(
        "--run-analysis",
        action="store_true",
        help="导入数据后运行 AI 分析",
    )
    args = parser.parse_args()

    logger.info("=" * 50)
    logger.info("初始化数据库...")
    logger.info("=" * 50)

    # 创建数据库
    create_database()

    # 连接并创建表
    db = Database()
    try:
        db.connect()
        db.create_tables()
        logger.info("所有表创建完毕")

        # 导入翻译数据
        if args.load_translated or args.run_analysis:
            load_translated_csv(db, MERGED_TRANSLATED_CSV)

        # 运行 AI 分析
        if args.run_analysis:
            logger.info("触发 AI 分析...")
            try:
                from src.analysis.analyzer import run_full_analysis
                run_full_analysis(db)
                logger.info("AI 分析完成")
            except ImportError as e:
                logger.warning("分析模块尚未就绪: %s", e)
            except Exception as e:
                logger.error("AI 分析失败: %s", e)

        logger.info("=" * 50)
        logger.info("数据库初始化完成!")
        logger.info("=" * 50)

    finally:
        db.disconnect()


if __name__ == "__main__":
    main()
