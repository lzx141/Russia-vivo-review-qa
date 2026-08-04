"""
本地批量抓取 6-7 月 OZON + Wildberries 数据（无头模式加速版）
=============================================================

已抓取状态：
  - WB 6月 ✅ 已完成（评论 2263 + 问答 454）
  - OZON 6月 ⚠️ 部分（将重跑补全，无头模式更快）
  - WB 7月 ❌ 待抓
  - OZON 7月 ❌ 待抓

用法：
  PYTHONIOENCODING=utf-8 python scripts/crawl_jun_jul.py
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.config import PRODUCT_URLS_EXCEL, PROJECT_ROOT

RAW_DIR = os.path.join(PROJECT_ROOT, "原始数据")


def crawl_ozon_range(start_date: str, end_date: str):
    """只跑 OZON 爬虫（无头模式）"""
    from src.crawler.ozon_crawler import crawl_from_excel as crawl_ozon
    print("\n--- OZON 爬取（无头模式）---")
    try:
        crawl_ozon(PRODUCT_URLS_EXCEL, start_date=start_date, end_date=end_date)
    except Exception as e:
        print(f"⚠️ OZON 爬取异常: {e}")


def crawl_wb_range(start_date: str, end_date: str):
    """只跑 Wildberries 爬虫"""
    from src.crawler.wildberries_crawler import crawl_from_excel as crawl_wb
    print("\n--- Wildberries 爬取 ---")
    try:
        crawl_wb(PRODUCT_URLS_EXCEL, start_date=start_date, end_date=end_date)
    except Exception as e:
        print(f"⚠️ WB 爬取异常: {e}")


def move_files(tag: str):
    """将根目录爬虫输出移动到 原始数据/ 并按 tag 命名"""
    import pandas as pd

    os.makedirs(RAW_DIR, exist_ok=True)
    mappings = {
        "ozon_reviews.xlsx": f"ozon_reviews{tag}.xlsx",
        "ozon_questions.xlsx": f"ozon_questions{tag}.xlsx",
        "wildberries_reviews.xlsx": f"wildberries_reviews{tag}.xlsx",
        "wildberries_qa.xlsx": f"wildberries_qa{tag}.xlsx",
    }
    for src_name, dst_name in mappings.items():
        src_path = os.path.join(PROJECT_ROOT, src_name)
        dst_path = os.path.join(RAW_DIR, dst_name)
        if os.path.exists(src_path):
            new_df = pd.read_excel(src_path, engine="openpyxl")
            if os.path.exists(dst_path):
                old_df = pd.read_excel(dst_path, engine="openpyxl")
                combined = pd.concat([old_df, new_df], ignore_index=True).drop_duplicates()
                combined.to_excel(dst_path, index=False, engine="openpyxl")
                print(f"  📝 {dst_name}: 追加后 {len(combined)} 条")
            else:
                new_df.to_excel(dst_path, index=False, engine="openpyxl")
                print(f"  ✅ {dst_name}: 新建 {len(new_df)} 条")
            os.remove(src_path)


if __name__ == "__main__":
    print("🚀 开始抓取（无头模式加速）")
    print(f"商品链接文件: {PRODUCT_URLS_EXCEL}")

    # 1. WB 7 月（requests 快）
    crawl_wb_range("2026-07-01", "2026-07-31")
    move_files("6")

    # 2. OZON 6 月（重跑补全，无头更快）
    crawl_ozon_range("2026-06-01", "2026-06-30")
    move_files("4")

    time.sleep(3)

    # 3. OZON 7 月
    crawl_ozon_range("2026-07-01", "2026-07-31")
    move_files("5")

    print("\n🎉 抓取完成")
