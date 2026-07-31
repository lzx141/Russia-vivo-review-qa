"""
月度数据爬取主脚本（本地运行）
=================================

每月 3 号运行：爬取上个月的 OZON / Wildberries 评论与问答，
随后自动完成「翻译 → 入库 → 生成大屏数据」的完整流程。

注意：
  - 爬虫依赖本地 Chrome（Selenium），服务器无 Chrome，需在本机运行
  - 运行后会自动 git 提交新数据，push 后服务器 webhook 会完成部署

用法：
  python scripts/run_crawler_monthly.py                 # 爬取上月数据 + 完整处理
  python scripts/run_crawler_monthly.py --dry-run       # 仅打印目标月份，不执行
  python scripts/run_crawler_monthly.py --crawl-only    # 仅爬虫，不翻译/入库/生成
  python scripts/run_crawler_monthly.py --start-date 2026-05-01 --end-date 2026-05-31  # 自定义日期
"""
import argparse
import os
import subprocess
import sys
from datetime import datetime

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from config.config import PROJECT_ROOT as _PROJ
from config.config import MERGED_TRANSLATED_CSV, DASHBOARD_DIR


def last_month_range() -> tuple[str, str]:
    """返回上月起止日期 (start, end)"""
    import pandas as pd

    today = pd.Timestamp.today()
    first = today.replace(day=1)
    end = first - pd.Timedelta(days=1)
    start = end.replace(day=1)
    return start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")


def run_cmd(cmd: list[str], cwd: str = None) -> int:
    print(f"\n▶️  {' '.join(cmd)}")
    r = subprocess.run(cmd, cwd=cwd or PROJECT_ROOT)
    if r.returncode != 0:
        print(f"❌ 命令失败: {' '.join(cmd)}")
    return r.returncode


def step_crawl(start_date: str, end_date: str) -> int:
    """运行 OZON + Wildberries 爬虫"""
    print("=" * 60)
    print("🔍 Step 1/4: 爬取数据（OZON + Wildberries）")
    print(f"   日期范围: {start_date} ~ {end_date}")
    print("=" * 60)

    from config.config import PRODUCT_URLS_EXCEL

    if not os.path.exists(PRODUCT_URLS_EXCEL):
        print(f"❌ 商品链接 Excel 不存在: {PRODUCT_URLS_EXCEL}")
        return 1

    from src.crawler.ozon_crawler import crawl_from_excel as crawl_ozon
    from src.crawler.wildberries_crawler import crawl_from_excel as crawl_wb

    # OZON 爬虫（自动在 URL 追加 sort=published_at_desc 按时间排序）
    print("\n--- Wildberries ---")
    crawl_wb(PRODUCT_URLS_EXCEL, start_date=start_date, end_date=end_date)

    print("\n--- OZON ---")
    crawl_ozon(PRODUCT_URLS_EXCEL, start_date=start_date, end_date=end_date)

    print("\n✅ 爬取完成")
    return 0


def step_translate() -> int:
    """运行 DeepSeek 增量翻译"""
    print("=" * 60)
    print("🈶 Step 2/4: DeepSeek 增量翻译")
    print("=" * 60)
    return run_cmd([sys.executable, "src/translation/translate_deepseek.py"])


def step_load_db() -> int:
    """翻译数据入库"""
    print("=" * 60)
    print("🗄️  Step 3/4: 翻译数据入库")
    print("=" * 60)
    return run_cmd([sys.executable, "src/etl/init_database.py", "--load-translated"])


def step_dashboard() -> int:
    """生成大屏数据"""
    print("=" * 60)
    print("📊 Step 4/4: 生成大屏数据")
    print("=" * 60)
    return run_cmd([sys.executable, "src/dashboard/generate_stats.py"])


def git_commit_and_push() -> int:
    """提交并推送新数据（供服务器 webhook 自动部署）"""
    print("=" * 60)
    print("🔄 提交并推送 git")
    print("=" * 60)
    run_cmd(["git", "add", "原始数据/"])
    run_cmd(["git", "add", "-f", MERGED_TRANSLATED_CSV])
    run_cmd(["git", "add", DASHBOARD_DIR + "/dashboard_data.js"])
    msg = f"data: 月度数据更新 {datetime.now().strftime('%Y%m')}"
    run_cmd(["git", "commit", "-m", msg])
    run_cmd(["git", "push", "origin", "main"])
    return 0


def main():
    parser = argparse.ArgumentParser(description="月度数据爬取与处理")
    parser.add_argument("--dry-run", action="store_true", help="仅打印目标月份")
    parser.add_argument("--crawl-only", action="store_true", help="仅爬虫")
    parser.add_argument("--start-date", default=None, help="开始日期")
    parser.add_argument("--end-date", default=None, help="结束日期")
    args = parser.parse_args()

    start_date, end_date = last_month_range()
    if args.start_date:
        start_date = args.start_date
    if args.end_date:
        end_date = args.end_date

    print(f"📅 目标月份: {start_date} ~ {end_date}")
    if args.dry_run:
        print("[dry-run] 不执行任何操作")
        return

    # Step 1: 爬虫
    if step_crawl(start_date, end_date) != 0:
        print("❌ 爬虫失败，中止")
        return

    if args.crawl_only:
        print("✅ 仅爬虫完成（--crawl-only）")
        return

    # Step 2-4: 翻译 → 入库 → 生成
    step_translate()
    step_load_db()
    step_dashboard()

    # 提交推送，触发服务器部署
    git_commit_and_push()
    print("\n🎉 月度数据流程全部完成！")
    print(f"   GitHub push 后，服务器 webhook 将自动更新网站。")


if __name__ == "__main__":
    main()
