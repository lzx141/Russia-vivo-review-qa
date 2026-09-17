# 俄罗斯跨境电商多源用户反馈分析平台：优化过程记录

> 建立日期：2026-09-17  
> 维护原则：只记录已经完成并经过验证的改动；规划项不得提前写入简历或 README 的成果描述。

## 1. 项目目标

将现有“采集、清洗、翻译、看板”项目升级为一个能够：

1. 识别数据质量下降；
2. 比较自主采集与外部数据的差异；
3. 验证分析结论是否对数据来源敏感；
4. 使用 Hadoop/Spark 稳定处理多源数据；
5. 输出可追溯、可复现业务指标

的多源用户反馈分析平台。

本轮不引入机器学习训练，不以堆叠组件或扩大数据量作为主要目标。

## 2. 当前基线

### 2.1 已有能力

- 支持 Ozon、Wildberries、Yandex Market 评论及问答采集。
- 已形成 Pandas ETL、翻译、MySQL 入库、统计生成和 ECharts 看板链路。
- 已实现内容哈希缓存、翻译断点续传、ETL 运行统计和基础数据质量检查。
- 已部署阿里云 ECS、Nginx、MySQL 和 GitHub Webhook。
- ECS 已安装 Hadoop 3.2.4、Spark 3.5.9 和 Java 11，并完成 Spark 读取/写入 HDFS Parquet 的验证。

### 2.2 数据审计基线

- 原始 Excel 共 97,265 行。
- 当前合并数据共 86,378 行，原始数据到合并数据净差异为 10,887 行。
- 评论共 63,766 行，其中 12,741 行缺少正文，正文缺失率为 19.98%。
- 问答记录的 SKU 缺失率为 95.344%，SKU 不适合作为通用业务主键。
- 平台分布明显不均衡，Wildberries 占主要部分。
- 英文翻译覆盖在 2026 年 5 月后中断。
- 评分高度偏向五星，需要在分析中披露样本结构和有效样本量。

## 3. 已确认的目标架构

```text
自主采集数据 + 外部 Wildberries 目标子集
                    ↓
             多源数据适配器
                    ↓
              HDFS ODS 原始层
                    ↓
     Spark DWD 标准化/映射/去重/质量评分
                    ↓
           Spark DWS 主题汇总层
                    ↓
              ADS 分析指标层
                    ↓
          MySQL / Notebook / ECharts
```

约束：

- 当前 2 核 2GB ECS 不部署 Hive、Kafka、MLflow 或常驻 Airflow 服务。
- Spark 使用受控内存的本地模式。
- 外部数据先在本地分片过滤，服务器只保存目标子集和处理结果。
- 外部数据不直接混入总体 KPI，必须保留来源、许可证和指标适用性。

## 4. 分析设计

### 4.1 数据源对照研究

- A 组：自主采集 Wildberries 数据。
- B 组：公开数据中相同 `nmId`、品牌型号或品类的数据。
- 比较完整率、重复率、文本长度、评分分布、负面率、差评主题和回答覆盖率。
- 对产品执行匹配、等量抽样或加权，避免热门商品主导总体结论。
- 使用 Bootstrap 置信区间、比例检验、Mann-Whitney U 检验、效应量和 Jensen-Shannon 散度。
- 定位“采集质量下降是否改变业务结论”，不将观察性来源比较描述为随机 A/B Test。

### 4.2 离线管道 A/B

- Pipeline A：现有 Pandas 清洗与简单去重。
- Pipeline B：Spark 数据契约、实体映射、质量评分和跨来源去重。
- 两套管道处理相同审计样本，比较有效记录识别、去重、产品映射、指标稳定性、耗时和资源消耗。

## 5. 数据治理设计

统一记录至少包含：

```text
record_id, source_dataset, source_record_id, dataset_role,
platform, record_type, product_id, source_product_id,
product_name, brand, category, rating, text, answer,
event_date, ingested_at, pipeline_run_id, quality_score,
product_match_confidence, duplicate_of,
is_rating_eligible, is_trend_eligible,
is_text_eligible, is_product_eligible
```

核心规则：

- 优先使用平台商品 ID、URL 商品编号和品牌型号建立稳定 `product_id`。
- 一条记录按指标用途决定是否可用，而不是简单整行删除。
- 原始层不可覆盖；每次运行保留输入、输出、隔离、重复、耗时和质量门禁状态。
- ADS 只包含看板和分析实际需要的小型结果表。

## 6. 优化阶段

| 阶段 | 状态 | 交付物 | 验证证据 |
|---|---|---|---|
| 0. 基线审计 | 已完成 | `notebooks/current_data_quality_assessment.ipynb` | 原始/合并行数、缺失率、平台分布、翻译覆盖 |
| 1. 简历基线修订 | 已完成 | 数据分析版、数据工程版一页 PDF | 均为单页 A4；日期、文本与页面渲染检查通过 |
| 2. 数据契约与稳定主键 | 已完成 | YAML contract、来源适配器、稳定商品 ID | 契约与适配器单测通过 |
| 3. Spark 分层管道 | 已完成（本地验证） | ODS/DWD/DWS/ADS Parquet 作业 | Python 3.12 + Spark 3.5.9 单测与 smoke run 通过；尚未部署定时任务 |
| 4. 质量评分与隔离 | 已完成 | 质量规则、四类指标准入、隔离表、manifest | fixture 端到端 4/4 接受，门禁 100%；仅为测试样本结果 |
| 5. 外部数据接入 | 已完成（有限样本） | WB 目标子集、来源元数据 | 远程真实抽取 10 条，扫描 1/8 分片即达到上限；CC0 元数据保留 |
| 6. 数据源对照研究 | 已完成（框架与 fixture） | 匹配 cohort、JSON/HTML、业务 marts | fixture 得到 4 条匹配记录；真实业务结论仍需扩大共同商品样本 |
| 7. 离线管道 A/B | 已完成（工程基准） | 同输入管道基准 JSON | 输出保留、隔离、重复、准入与耗时；无人工标签，不宣称准确率 |
| 8. 看板与文档 | 部分完成 | 治理 JSON 接口、架构/数据/指标文档 | 后端 loader 单测通过；独立质量中心前端页面尚未实现 |

## 7. 变更日志

### 2026-09-17

- 确认取消机器学习训练范围。
- 确认使用“数据源对照研究 + 离线管道 A/B”作为分析与工程验证主线。
- 建立本优化过程记录。
- 完成两份一页简历修订；益普索日期统一为“2026年1月–2026年9月”。
- 数据分析版加入可复现数据审计结果，数据工程版加入已验证的 Hadoop/Spark/HDFS 环境实践；未提前声明规划中的外部数据融合和 Spark 分层成果。
- 完成统一数据契约、稳定商品主键、四类指标准入、质量评分与审计式跨来源去重（`eefb0f1`、`c94f000`）。
- 完成本地多源参考管道和 Spark ODS/DWD/DWS/ADS 管道（`a6a4d31`、`35c0c8c`）。
- 修复 Python 3.14 与 PySpark worker 不兼容问题：Spark 验证固定使用 Python 3.12 + PySpark 3.5.9；manifest 改为 JVM `range` 构造，避免 Python worker 超时。
- 完成 WB CC0 数据子集工具（`a5d90c0`）：支持 schema drift、参数化过滤、逐分片扫描与达到上限即停；真实远端 smoke test 提取 10 条。
- 完成匹配来源对照、业务 marts、JSON/HTML 报告和离线管道工程基准（`60c1245`、`058aa66`、`cca6af1`）。
- 完成统一 CLI、质量审计和 dashboard 治理证据加载（`87c5803`）；前端独立质量中心仍为遗留项。

### 验证命令

```text
python -m unittest tests.test_external_wb -v
python -m unittest tests.test_source_comparison tests.test_business_marts -v
python src/run_pipeline.py --trusted-input ... --trusted-output ... --run-id integration
python scripts/run_source_comparison.py --input ... --output-dir ...
python scripts/run_pipeline_benchmark.py --input ... --output ...
Python 3.12: python -m unittest tests.test_spark_pipeline -v
Python 3.12: python scripts/run_spark_pipeline.py ... --master local[1]
```

## 8. 简历同步规则

只有满足以下条件，项目成果才可同步至简历：

1. 对应代码已提交；
2. 测试或运行命令已通过；
3. 指标来自实际输出且可复核；
4. README 能说明复现步骤；
5. 线上能力与本地示例明确区分。
