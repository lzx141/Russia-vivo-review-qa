# 多源用户反馈平台架构

## 已实现

```text
自采 CSV/JSONL ─┐
                 ├─ Source Adapter ─ Canonical Contract ─ Quality + Dedup
WB CC0 Parquet ──┘                                      │
                                                       ├─ Local JSONL reference pipeline
                                                       └─ Spark 3.5 Parquet pipeline
                                                            ODS / DWD / quarantine
                                                            DWS / ADS / manifest
                                                                     │
                         ┌───────────────────────────────────────────┤
                         ├─ matched source comparison (JSON + HTML)
                         ├─ business marts
                         ├─ offline pipeline benchmark
                         └─ dashboard governance JSON loader
```

- 本地参考管道用于 fixture、规则测试和低资源复现。
- Spark 管道使用同一数据语义，输出 ODS/DWD/DWS/ADS Parquet 与 manifest。
- 外部 WB 工具从 Hugging Face datasets-server 获取分片 URL，逐分片参数化过滤，达到行数上限即停。
- 自采数据为业务主数据；外部数据保留 `external_validation` 标签，不直接进入总体 KPI。

## 部署边界

当前阿里云 ECS 为 2 核 2 GiB。Hadoop 3.2.4 与 Spark 3.5.9 适合演示离线批处理，但资源不足以支持多守护进程的大数据平台。推荐 `local[1]`、小分区、Parquet 和按需作业。

Airflow 文件只是可选部署模板，需要 `RUSSIA_DATA_PROJECT_ROOT` 环境变量；当前不宣称服务器常驻 Airflow。Hive、Kafka、MLflow、实时流处理和机器学习训练均不在本轮范围。

## 可追溯性

每次运行由 `pipeline_run_id` 标识。产物保留输入数、接受数、隔离数、重复数、质量通过率、输入文件及生成时间。相同 run ID 重跑覆盖同一批次，避免重复追加。

## 已知限制

- 精确来源对照依赖共同 `product_id`；无共同商品时报告 unavailable，不做模糊匹配伪造样本。
- WB 问答没有评分，因此与评论来源比较时评分检验可能不可用。
- Python 3.14 与本机 PySpark worker 组合不稳定；Spark 验证使用 Python 3.12 + PySpark 3.5.9。
- 当前 dashboard 已能读取治理 JSON，但尚未新增独立“质量中心”前端页面。
- 若要报告清洗准确率/召回率，需要新增独立人工标注审计集。
