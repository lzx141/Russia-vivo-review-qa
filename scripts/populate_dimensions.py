"""
维度表填充脚本 — 从事实表反推填充星型模型维度表
================================================

当前 translated_records 是事实表，但维度表（dim_product/dim_platform/dim_date）
只有表结构没有数据，导致星型模型不完整。

本脚本从事实表反向提取维度数据填充三个维度表：
  - dim_product：产品名称、SKU（从事实表 DISTINCT name/sku）
  - dim_platform：平台名称（从事实表 DISTINCT site_name）
  - dim_date：日期维度（从事实表 DISTINCT publish_date，展开年/季/月/周/星期）

用法：
  python scripts/populate_dimensions.py
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.etl.database import Database


def populate_product_dim(db: Database):
    """填充产品维度表"""
    rows = db.fetch_query(
        "SELECT DISTINCT name, sku FROM translated_records "
        "WHERE name IS NOT NULL AND name != ''"
    )
    inserted = 0
    for name, sku in rows:
        db.execute_query(
            "INSERT INTO dim_product (product_name, sku, brand, category) "
            "VALUES (%s, %s, 'vivo', '智能手机') "
            "ON DUPLICATE KEY UPDATE product_name=VALUES(product_name)",
            (name, sku or None),
        )
        inserted += 1
    print(f"✅ dim_product: 填充 {inserted} 条产品")
    return inserted


def populate_platform_dim(db: Database):
    """填充平台维度表"""
    rows = db.fetch_query(
        "SELECT DISTINCT site_name FROM translated_records "
        "WHERE site_name IS NOT NULL AND site_name != ''"
    )
    inserted = 0
    for (site_name,) in rows:
        # 平台类型判断
        platform_type = "ecommerce"
        country = "俄罗斯"
        db.execute_query(
            "INSERT INTO dim_platform (platform_name, platform_type, country) "
            "VALUES (%s, %s, %s) "
            "ON DUPLICATE KEY UPDATE platform_name=VALUES(platform_name)",
            (site_name, platform_type, country),
        )
        inserted += 1
    print(f"✅ dim_platform: 填充 {inserted} 条平台")
    return inserted


def populate_date_dim(db: Database):
    """填充时间维度表"""
    rows = db.fetch_query(
        "SELECT DISTINCT DATE(publish_date) FROM translated_records "
        "WHERE publish_date IS NOT NULL"
    )
    inserted = 0
    for (d,) in rows:
        if not d:
            continue
        year = d.year
        quarter = (d.month - 1) // 3 + 1
        month = d.month
        week = d.isocalendar()[1]  # ISO 周
        day_of_week = d.isoweekday()  # 1=周一
        is_weekend = day_of_week >= 6
        db.execute_query(
            "INSERT INTO dim_date (full_date, year, quarter, month, week, day_of_week, is_weekend) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s) "
            "ON DUPLICATE KEY UPDATE full_date=VALUES(full_date)",
            (d, year, quarter, month, week, day_of_week, is_weekend),
        )
        inserted += 1
    print(f"✅ dim_date: 填充 {inserted} 条日期")
    return inserted


def main():
    db = Database()
    db.connect()
    try:
        # 先确保表存在
        db.create_tables()

        print("=" * 50)
        print("维度表填充开始")
        print("=" * 50)

        # 清空旧维度数据（重新填充，保证一致）
        for t in ["dim_product", "dim_platform", "dim_date"]:
            db.execute_query(f"TRUNCATE TABLE {t}")

        n_product = populate_product_dim(db)
        n_platform = populate_platform_dim(db)
        n_date = populate_date_dim(db)

        print("=" * 50)
        print(f"填充完成: 产品 {n_product} / 平台 {n_platform} / 日期 {n_date}")
        print("=" * 50)
    finally:
        db.disconnect()


if __name__ == "__main__":
    main()
