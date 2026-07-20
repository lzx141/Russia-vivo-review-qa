"""
数据质量剖析工具
==================

功能：
  - 统计各字段完整性
  - 检测异常值分布
  - 生成数据质量报告（JSON/HTML）
  - 追踪 ETL 运行历史

用法：
  python src/etl/data_profiler.py                  # 全量剖析
  python src/etl/data_profiler.py --html           # 生成 HTML 报告
  python src/etl/data_profiler.py --etl-history    # 查看 ETL 运行历史
"""
import argparse
import json
import logging
import os
import sys
from datetime import datetime
from collections import Counter

sys.path.append(os.path.join(os.path.dirname(__file__), "..", ".."))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


def profile_table(db, table_name: str) -> dict:
    """对指定表进行数据质量剖析"""
    info = {"table": table_name, "total_rows": 0, "columns": {}}

    # 获取总行数
    info["total_rows"] = db.get_table_count(table_name)

    # 获取列信息
    try:
        columns = db.fetch_query(f"SHOW COLUMNS FROM {table_name}")
        for col in columns:
            col_name = col[0]
            col_type = col[1]
            nullable = col[2] == "YES"

            # 统计非空率
            if info["total_rows"] > 0:
                non_null = db.fetch_one(
                    f"SELECT COUNT(*) FROM {table_name} WHERE {col_name} IS NOT NULL"
                )[0]
                fill_rate = round(non_null / info["total_rows"] * 100, 2)
            else:
                fill_rate = 0

            info["columns"][col_name] = {
                "type": col_type,
                "nullable": nullable,
                "fill_rate_pct": fill_rate,
                "non_null_count": non_null if info["total_rows"] > 0 else 0,
            }
    except Exception as e:
        logger.warning("无法获取 %s 的列信息: %s", table_name, e)

    return info


def check_anomalies(db) -> list[dict]:
    """检测数据异常"""
    anomalies = []

    # 1. 日期异常（未来日期）
    future = db.fetch_one(
        "SELECT COUNT(*) FROM translated_records WHERE publish_date > NOW()"
    )[0]
    if future > 0:
        anomalies.append({"type": "future_date", "count": future, "severity": "medium"})

    # 2. 重复记录（完全相同的 author + content + name）
    dup = db.fetch_one(
        "SELECT COUNT(*) FROM ("
        "SELECT author, content, name, COUNT(*) as cnt "
        "FROM translated_records "
        "WHERE author IS NOT NULL AND content IS NOT NULL "
        "GROUP BY author, content, name "
        "HAVING cnt > 1"
        ") as dups"
    )[0]
    if dup > 0:
        anomalies.append({"type": "duplicate_content", "count": dup, "severity": "low"})

    # 3. 评分异常（超出 1-5 范围）
    invalid_rate = db.fetch_one(
        "SELECT COUNT(*) FROM translated_records WHERE data_type='review' AND (rate < 1 OR rate > 5)"
    )[0]
    if invalid_rate > 0:
        anomalies.append({"type": "invalid_rating", "count": invalid_rate, "severity": "high"})

    return anomalies


def generate_html_report(report: dict) -> str:
    """生成 HTML 格式的数据质量报告"""
    tables_html = ""
    for table_name, info in report.get("tables", {}).items():
        cols_html = ""
        for col_name, col_info in info.get("columns", {}).items():
            fill_bar = int(col_info["fill_rate_pct"] / 10) * "█"
            empty_bar = (10 - int(col_info["fill_rate_pct"] / 10)) * "░"
            cols_html += f"""
            <tr>
                <td>{col_name}</td>
                <td>{col_info['type']}</td>
                <td>{'❌' if col_info['nullable'] else '✅'}</td>
                <td>{col_info['fill_rate_pct']}%</td>
                <td><span class="fill-bar">{fill_bar}{empty_bar}</span></td>
            </tr>"""

        tables_html += f"""
        <h3>📋 {table_name}</h3>
        <p>总行数: <strong>{info['total_rows']:,}</strong></p>
        <table>
            <tr><th>列名</th><th>类型</th><th>可空</th><th>填充率</th><th></th></tr>
            {cols_html}
        </table>
        <hr>
        """

    anomalies_html = ""
    for a in report.get("anomalies", []):
        severity_class = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(a["severity"], "⚪")
        anomalies_html += f"""
        <tr>
            <td>{severity_class}</td>
            <td>{a['type']}</td>
            <td>{a['count']:,}</td>
            <td>{a['severity'].upper()}</td>
        </tr>"""

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <title>数据质量报告 - {datetime.now().strftime('%Y-%m-%d')}</title>
    <style>
        body {{ font-family: -apple-system, sans-serif; margin: 20px; background: #f5f5f5; }}
        .container {{ max-width: 1000px; margin: auto; background: #fff; padding: 24px; border-radius: 8px; }}
        h1 {{ color: #1a5276; }}
        table {{ width: 100%; border-collapse: collapse; margin: 12px 0; }}
        th, td {{ padding: 8px 12px; text-align: left; border-bottom: 1px solid #ddd; }}
        th {{ background: #eaf2f8; }}
        .fill-bar {{ font-size: 14px; letter-spacing: 1px; }}
        .kpi-box {{ display: inline-block; margin: 8px; padding: 16px 24px; background: #eaf2f8; border-radius: 8px; text-align: center; }}
        .kpi-box .value {{ font-size: 24px; font-weight: bold; color: #1a5276; }}
        .kpi-box .label {{ font-size: 12px; color: #666; }}
        hr {{ border: none; border-top: 1px solid #eee; }}
    </style>
</head>
<body>
<div class="container">
    <h1>📊 数据质量报告</h1>
    <p>生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>

    <div class="kpi-box">
        <div class="value">{report.get('total_records', 0):,}</div>
        <div class="label">总记录数</div>
    </div>
    <div class="kpi-box">
        <div class="value">{report.get('valid_rate', 0)}%</div>
        <div class="label">数据有效率</div>
    </div>
    <div class="kpi-box">
        <div class="value">{len(report.get('anomalies', []))}</div>
        <div class="label">异常数</div>
    </div>

    <h2>🔍 异常检测</h2>
    <table>
        <tr><th></th><th>类型</th><th>数量</th><th>严重度</th></tr>
        {anomalies_html or '<tr><td colspan="4" style="text-align:center;color:#888;">✅ 无异常</td></tr>'}
    </table>

    <h2>📋 表结构剖析</h2>
    {tables_html}
</div>
</body>
</html>"""


def main():
    parser = argparse.ArgumentParser(description="数据质量剖析工具")
    parser.add_argument("--html", action="store_true", help="生成 HTML 报告")
    parser.add_argument("--etl-history", action="store_true", help="查看 ETL 运行历史")
    args = parser.parse_args()

    try:
        from src.etl.database import Database
        db = Database()
        db.connect()
    except Exception as e:
        logger.error("数据库连接失败: %s", e)
        return

    try:
        if args.etl_history:
            history = db.get_etl_summary(30)
            if not history:
                logger.info("暂无 ETL 运行记录")
            else:
                logger.info("📈 最近 %d 条 ETL 运行记录:", len(history))
                for h in history:
                    logger.info("  [%s] %s → %s | in=%d out=%d | %.1f%% | %dms",
                                h["run_id"][:8], h["stage"], h["status"],
                                h["records_in"], h["records_out"],
                                h["success_rate"], h["duration_ms"])
            return

        # 全量剖析
        report = {
            "report_time": datetime.now().isoformat(),
            "total_records": 0,
            "valid_rate": 0,
            "tables": {},
            "anomalies": [],
        }

        tables = ["translated_records", "analysis_cache", "reviews", "questions",
                  "dim_product", "dim_platform", "etl_stats"]

        for table_name in tables:
            try:
                info = profile_table(db, table_name)
                report["tables"][table_name] = info
                if table_name == "translated_records":
                    report["total_records"] = info["total_rows"]
            except Exception as e:
                logger.warning("剖析 %s 失败: %s", table_name, e)

        # 异常检测
        try:
            report["anomalies"] = check_anomalies(db)
        except Exception as e:
            logger.warning("异常检测失败: %s", e)

        # 数据有效率
        report["valid_rate"] = report["tables"].get("translated_records", {}).get("columns", {}).get("rate", {}).get("fill_rate_pct", 0)

        # 输出
        if args.html:
            html = generate_html_report(report)
            output_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                "output",
                f"data_quality_{datetime.now().strftime('%Y%m%d')}.html",
            )
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(html)
            logger.info("HTML 报告已保存: %s", output_path)
        else:
            logger.info("=" * 50)
            logger.info("📊 数据质量报告")
            logger.info("=" * 50)
            for table_name, info in report["tables"].items():
                logger.info("  %s: %d 行", table_name, info["total_rows"])
            if report["anomalies"]:
                logger.info("\n⚠️  异常:")
                for a in report["anomalies"]:
                    logger.info("  [%s] %s: %d", a["severity"].upper(), a["type"], a["count"])
            logger.info("\n✅ 数据有效率: %.1f%%", report["valid_rate"])

    finally:
        db.disconnect()


if __name__ == "__main__":
    main()
