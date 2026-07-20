"""
数据管道一键编排入口
=========================

功能：
  按顺序执行 ETL → 翻译加载 → AI 分析 → 仪表盘生成
  支持断点续传、增量运行、数据质量检查

用法：
  python src/run_pipeline.py                         # 全量运行
  python src/run_pipeline.py --skip-analysis          # 跳过 AI 分析
  python src/run_pipeline.py --skip-dashboard         # 跳过仪表盘生成
  python src/run_pipeline.py --quality-only           # 仅数据质量检查
  python src/run_pipeline.py --stage 2                # 从第 2 阶段开始
"""
import argparse
import logging
import os
import sys
import time
from datetime import datetime
from typing import Optional

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("pipeline")

# ── 阶段定义 ──────────────────────────────────────────
STAGES = [
    ("etl", "ETL 数据抽取与加载"),
    ("translation", "翻译数据入库"),
    ("analysis", "AI 分析（情感/意图/NER/根因）"),
    ("dashboard", "仪表盘数据生成"),
    ("quality", "数据质量检查"),
]


def run_stage(stage_id: str) -> bool:
    """运行单个管道阶段，返回是否成功"""
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    scripts = {
        "etl": ("python", ["src/etl/etl.py"]),
        "translation": ("python", ["src/etl/init_database.py", "--load-translated"]),
        "analysis": ("python", ["src/analysis/analyzer.py", "--mode", "all", "--db"]),
        "dashboard": ("python", ["src/dashboard/generate_stats.py"]),
    }

    if stage_id == "quality":
        return _run_quality_check()

    cmd, args = scripts.get(stage_id, (None, []))
    if not cmd:
        logger.error("未知阶段: %s", stage_id)
        return False

    import subprocess
    full_cmd = [cmd] + args
    logger.info("=" * 50)
    logger.info("▶️  阶段: %s", stage_id)
    logger.info("  命令: %s", " ".join(full_cmd))
    logger.info("=" * 50)

    t0 = time.time()
    result = subprocess.run(
        full_cmd,
        cwd=project_root,
        capture_output=False,
    )
    elapsed = time.time() - t0
    success = result.returncode == 0

    if success:
        logger.info("✅ 阶段 %s 完成 (%.1fs)", stage_id, elapsed)
    else:
        logger.error("❌ 阶段 %s 失败 (returncode=%d, %.1fs)",
                      stage_id, result.returncode, elapsed)

    return success


def _run_quality_check() -> bool:
    """数据质量检查"""
    logger.info("=" * 50)
    logger.info("▶️  阶段: quality (数据质量检查)")
    logger.info("=" * 50)
    try:
        from src.etl.database import Database
        db = Database()
        db.connect()
        report = db.get_data_quality_report()
        summary = db.get_etl_summary(5)
        db.disconnect()

        logger.info("📊 数据质量报告:")
        logger.info("  总记录数: %s", report["total_records"])
        logger.info("  数据有效率: %s%%", report["validity"]["valid_rate_pct"])
        logger.info("  缺失作者率: %s%%", report["completeness"]["missing_author_rate"])
        logger.info("  去重作者数: %s", report["uniqueness"]["distinct_authors"])
        logger.info("  产品种类: %s", report["uniqueness"]["distinct_products"])

        if summary:
            logger.info("\n📈 最近 ETL 运行:")
            for s in summary:
                logger.info("  %s | %s | in=%d out=%d | %.1f%% | %dms | %s",
                            s["run_id"][:8], s["stage"],
                            s["records_in"], s["records_out"],
                            s["success_rate"], s["duration_ms"], s["status"])
        return True
    except Exception as e:
        logger.error("数据质量检查失败: %s", e)
        return False


def main():
    parser = argparse.ArgumentParser(description="数据管道编排入口")
    parser.add_argument("--skip-analysis", action="store_true", help="跳过 AI 分析")
    parser.add_argument("--skip-dashboard", action="store_true", help="跳过仪表盘生成")
    parser.add_argument("--quality-only", action="store_true", help="仅运行数据质量检查")
    parser.add_argument("--stage", type=int, default=1, help="从第几个阶段开始 (1-5)")
    args = parser.parse_args()

    run_id = datetime.now().strftime("run_%Y%m%d_%H%M%S")
    logger.info("🚀 管道启动 [%s]", run_id)

    if args.quality_only:
        _run_quality_check()
        return

    # 确定要运行的阶段
    skip_set = set()
    if args.skip_analysis:
        skip_set.add("analysis")
    if args.skip_dashboard:
        skip_set.add("dashboard")

    stages_to_run = STAGES[args.stage - 1:]
    all_ok = True

    for stage_id, stage_desc in stages_to_run:
        if stage_id in skip_set:
            logger.info("⏭️  跳过阶段: %s (%s)", stage_id, stage_desc)
            continue

        ok = run_stage(stage_id)
        from src.etl.database import Database
        db = Database()
        try:
            db.connect()
            db.log_etl_run(
                run_id=run_id,
                stage=stage_id,
                status="success" if ok else "failed",
                duration_ms=0,
            )
            db.disconnect()
        except Exception:
            pass

        if not ok:
            all_ok = False
            logger.error("🛑 管道在阶段 %s 中止", stage_id)
            break

    if all_ok:
        logger.info("🎉 管道全部完成 [%s]", run_id)
    else:
        logger.warning("⚠️  管道部分完成 [%s]", run_id)


if __name__ == "__main__":
    main()
