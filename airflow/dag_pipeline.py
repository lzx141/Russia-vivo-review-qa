"""
数据管道编排 DAG — Airflow 示例
==================================

功能：
  1. 每天自动执行 ETL 全流程
  2. 翻译数据增量更新
  3. AI 分析增量运行
  4. 仪表盘数据刷新
  5. ETL 运行状态监控与告警

依赖：
  pip install apache-airflow

部署：
  cp airflow/dag_pipeline.py ~/airflow/dags/
  # 配置 Airflow 连接：MySQL -> airflow connections add 'russia_mysql' ...
"""

from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.bash import BashOperator
from airflow.operators.python import PythonOperator
from airflow.operators.dummy import DummyOperator

# ── 默认参数 ──────────────────────────────────────────
default_args = {
    "owner": "data-engineering",
    "depends_on_past": False,
    "email_on_failure": True,
    "email_on_retry": False,
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
    "execution_timeout": timedelta(hours=2),
}

# ── DAG 定义 ──────────────────────────────────────────
dag = DAG(
    dag_id="russia_ecommerce_data_pipeline",
    default_args=default_args,
    description="俄罗斯跨境电商评论数据管道 — ETL → 翻译 → AI 分析 → 仪表盘",
    schedule_interval="0 6 * * *",          # 每天 06:00 UTC
    start_date=datetime(2026, 1, 1),
    catchup=False,
    tags=["russia", "ecommerce", "etl"],
    # 参数化配置
    params={
        "force_full_refresh": False,
        "analysis_batch_size": 5000,
        "translations_enabled": True,
    },
)

# ── 任务定义 ──────────────────────────────────────────
project_root = "/path/to/Russia-vivo-review-qa"
python_cmd = f"cd {project_root} && python"


start = DummyOperator(task_id="pipeline_start", dag=dag)

# Stage 1: 数据抽取与清洗
extract_data = BashOperator(
    task_id="extract_raw_data",
    bash_command=f"{python_cmd} src/etl/etl.py",
    dag=dag,
)

# Stage 2: 翻译数据加载
load_translations = BashOperator(
    task_id="load_translation_data",
    bash_command=f"{python_cmd} src/etl/init_database.py --load-translated",
    dag=dag,
)

# Stage 3: AI 分析（情感 + 意图 + NER + 根因）
run_ai_analysis = BashOperator(
    task_id="run_ai_analysis",
    bash_command=f"{python_cmd} src/analysis/analyzer.py --mode all --db",
    dag=dag,
)

# Stage 4: 仪表盘数据生成
generate_dashboard = BashOperator(
    task_id="generate_dashboard_data",
    bash_command=f"{python_cmd} src/dashboard/generate_stats.py",
    dag=dag,
)

# Stage 5: 数据质量检查
def _run_quality_check(**context):
    """数据质量检查：记录数、完整性、异常检测"""
    import sys, os
    sys.path.insert(0, project_root)
    from src.etl.database import Database
    db = Database()
    try:
        db.connect()
        report = db.get_data_quality_report()
        total = report["total_records"]
        validity = report["validity"]["valid_rate_pct"]
        missing_date = report["completeness"]["missing_date"]

        print(f"📊 数据质量报告:")
        print(f"  总记录数: {total}")
        print(f"  数据有效率: {validity}%")
        print(f"  缺失日期率: {missing_date}%")

        # 阈值告警
        if validity < 95:
            raise ValueError(f"数据有效率 {validity}% 低于阈值 95%")
        if total == 0:
            raise ValueError("数据为空，管道异常")

        # 推送到 XCom 供下游使用
        context["task_instance"].xcom_push(key="quality_report", value=report)
        print("✅ 数据质量检查通过")
    finally:
        db.disconnect()

quality_check = PythonOperator(
    task_id="data_quality_check",
    python_callable=_run_quality_check,
    dag=dag,
)

end = DummyOperator(task_id="pipeline_complete", dag=dag)

# ── 任务依赖 ──────────────────────────────────────────
start >> extract_data >> load_translations >> run_ai_analysis >> generate_dashboard >> quality_check >> end
