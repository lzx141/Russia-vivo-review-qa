# Multisource Feedback Platform Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将现有 Pandas/MySQL 用户反馈项目升级为具备统一数据契约、质量门禁、HDFS/Spark 分层、外部数据子集接入和数据源对照研究的可信分析平台。

**Architecture:** 自采与外部数据先通过适配器映射为统一记录，再进入 ODS/DWD/DWS/ADS。纯 Python/Pandas 路径承担本地测试和小规模复现，Spark 路径使用同一业务规则处理 HDFS Parquet；分析层只消费带指标准入标记的数据，并输出可审计的运行 manifest 和来源对照报告。

**Tech Stack:** Python 3、Pandas、PyYAML、SciPy、PySpark 3.5+、HDFS、Parquet、MySQL、ECharts、unittest

**Spec:** `docs/superpowers/specs/2026-09-17-multisource-feedback-platform-design.md`

## Global Constraints

- 不引入机器学习训练或模型部署。
- 自采数据是业务主数据；外部数据用于验证和补充，不能无标记地混入总体 KPI。
- 当前 ECS 为 2 核 2GB；Spark 使用 local 模式和受控内存，不部署 Hive、Kafka、MLflow 或常驻 Airflow。
- 外部亿级数据不得完整下载到 ECS；只保存目标品牌、品类或商品 ID 子集。
- 新增成果必须有测试或运行产物支撑，未完成能力不得写入简历。
- 所有生产代码遵循测试先行；每项任务先观察预期失败，再写最小实现。

---

### Task 1: 修复 Windows 控制台编码回归

**Files:**
- Modify: `tests/test_ozon_ci.py`
- Modify: `src/crawler/ozon_crawler.py`

**Interfaces:**
- Consumes: `crawl_from_excel(...)` 现有公开接口。
- Produces: `_safe_console_text(value: str, encoding: str | None = None) -> str`，确保控制台日志不会因 emoji 中断爬虫。

- [ ] **Step 1: 新增失败测试**

```python
def test_safe_console_text_removes_unencodable_symbols(self):
    from src.crawler.ozon_crawler import _safe_console_text
    result = _safe_console_text("📝 已读取", encoding="gbk")
    self.assertEqual(result, " 已读取")
```

- [ ] **Step 2: 验证失败原因**

Run: `python -m unittest tests.test_ozon_ci.TestOzonCrawlerCI.test_safe_console_text_removes_unencodable_symbols -v`

Expected: FAIL because `_safe_console_text` does not exist.

- [ ] **Step 3: 实现安全输出并替换问题日志**

```python
def _safe_console_text(value: str, encoding: str | None = None) -> str:
    target = encoding or getattr(sys.stdout, "encoding", None) or "utf-8"
    return value.encode(target, errors="ignore").decode(target)
```

将 `crawl_from_excel` 中包含 emoji 的直接 `print` 改为 `print(_safe_console_text(message))`。

- [ ] **Step 4: 运行 Ozon CI 测试和完整基线**

Run: `python -m unittest tests.test_ozon_ci -v`

Run: `python -m unittest discover tests -v`

Expected: 36 tests pass, 0 failures, 0 errors.

- [ ] **Step 5: 提交**

```bash
git add tests/test_ozon_ci.py src/crawler/ozon_crawler.py
git commit -m "fix: make crawler logs safe on Windows consoles"
```

### Task 2: 建立统一数据契约和稳定商品标识

**Files:**
- Create: `config/data_contract.yaml`
- Create: `config/quality_rules.yaml`
- Create: `src/data_platform/__init__.py`
- Create: `src/data_platform/contract.py`
- Create: `src/data_platform/identity.py`
- Create: `tests/test_data_contract.py`
- Modify: `requirements.txt`

**Interfaces:**
- Produces: `load_contract(path: str | Path | None = None) -> dict`
- Produces: `normalize_platform(value: object) -> str`
- Produces: `extract_source_product_id(url: object, explicit_id: object = None) -> str | None`
- Produces: `build_product_id(platform: str, source_product_id: str | None, product_name: str | None) -> tuple[str, str, float]`
- Produces: `canonical_record(raw: Mapping[str, object], source: str, record_type: str) -> dict[str, object]`

- [ ] **Step 1: 编写契约与身份映射失败测试**

```python
class TestIdentity(unittest.TestCase):
    def test_extracts_wildberries_nm_id(self):
        self.assertEqual(extract_source_product_id("https://www.wildberries.ru/catalog/123456/detail.aspx"), "123456")

    def test_product_id_prefers_platform_identifier(self):
        product_id, method, confidence = build_product_id("wildberries", "123456", "vivo V50")
        self.assertEqual((product_id, method, confidence), ("wildberries:123456", "source_product_id", 1.0))
```

- [ ] **Step 2: 验证测试因模块不存在而失败**

Run: `python -m unittest tests.test_data_contract -v`

- [ ] **Step 3: 创建 YAML 契约和最小实现**

契约定义统一字段、必填字段、记录类型和来源字段映射。`canonical_record` 输出 spec 中的核心字段，不进行质量打分。

- [ ] **Step 4: 运行测试**

Run: `python -m unittest tests.test_data_contract -v`

Expected: PASS.

- [ ] **Step 5: 提交**

```bash
git add config/data_contract.yaml config/quality_rules.yaml src/data_platform tests/test_data_contract.py requirements.txt
git commit -m "feat: add canonical feedback data contract"
```

### Task 3: 实现质量评分、指标准入与跨来源去重

**Files:**
- Create: `src/data_platform/quality.py`
- Create: `src/data_platform/deduplication.py`
- Create: `tests/test_quality_rules.py`
- Create: `tests/test_deduplication.py`

**Interfaces:**
- Consumes: Task 2 canonical record dictionary.
- Produces: `assess_quality(record: Mapping[str, object], rules: Mapping[str, object] | None = None) -> dict[str, object]`
- Produces: `normalize_text(value: object) -> str`
- Produces: `record_fingerprint(record: Mapping[str, object]) -> str`
- Produces: `deduplicate_records(records: Iterable[Mapping[str, object]]) -> tuple[list[dict], list[dict]]`

- [ ] **Step 1: 编写质量适用性失败测试**

```python
def test_rating_only_record_is_not_text_eligible(self):
    assessed = assess_quality({"record_type": "review", "rating": 5, "text": "", "event_date": "2026-01-01", "product_match_confidence": 1.0})
    self.assertTrue(assessed["is_rating_eligible"])
    self.assertFalse(assessed["is_text_eligible"])
```

- [ ] **Step 2: 验证质量测试失败**

Run: `python -m unittest tests.test_quality_rules -v`

- [ ] **Step 3: 实现质量评分**

评论默认权重：文本 30、评分 15、产品匹配 20、日期 15、俄语文本 10、非重复 10。问答使用问题/回答完整性代替评分。输出 `quality_score`、四类 eligibility 和 `quality_issues`。

- [ ] **Step 4: 编写并验证去重失败测试**

```python
def test_cross_source_duplicate_keeps_higher_quality_record(self):
    accepted, rejected = deduplicate_records([low_quality, high_quality])
    self.assertEqual(accepted[0]["record_id"], "high")
    self.assertEqual(rejected[0]["duplicate_of"], "high")
```

Run: `python -m unittest tests.test_deduplication -v`

- [ ] **Step 5: 实现确定性指纹和审计式去重**

使用 `product_id + record_type + normalized_text + rating` 的 SHA256。保留高质量记录，其余记录写入隔离输出并记录 `duplicate_of`。

- [ ] **Step 6: 运行两个测试文件**

Run: `python -m unittest tests.test_quality_rules tests.test_deduplication -v`

- [ ] **Step 7: 提交**

```bash
git add src/data_platform/quality.py src/data_platform/deduplication.py tests/test_quality_rules.py tests/test_deduplication.py
git commit -m "feat: add quality scoring and auditable deduplication"
```

### Task 4: 实现多源适配器和本地可复现管道

**Files:**
- Create: `src/data_platform/adapters.py`
- Create: `src/data_platform/manifest.py`
- Create: `src/data_platform/local_pipeline.py`
- Create: `tests/fixtures/self_review.csv`
- Create: `tests/fixtures/public_wb_question.jsonl`
- Create: `tests/test_source_adapters.py`
- Create: `tests/test_local_pipeline.py`

**Interfaces:**
- Produces: `SelfCollectedAdapter.adapt(row: Mapping[str, object], source_file: str) -> dict`
- Produces: `PublicWbQuestionAdapter.adapt(row: Mapping[str, object], source_file: str) -> dict`
- Produces: `run_local_pipeline(inputs: Sequence[InputSpec], output_dir: Path, run_id: str | None = None) -> RunManifest`
- Produces: `RunManifest.to_dict() -> dict`

- [ ] **Step 1: 编写适配器失败测试**

验证自采 `siteName/name/SKU/URL/review/question` 和公开 `nmId/productName/brandName/question/answer` 被映射到同一字段集合，并保留 `source_dataset`、`source_record_id`、`dataset_role`、`license`。

Run: `python -m unittest tests.test_source_adapters -v`

- [ ] **Step 2: 实现适配器**

公开 WB 数据默认 `dataset_role=external_validation`、`license=CC0-1.0`；自采数据默认 `dataset_role=business_primary`。

- [ ] **Step 3: 编写本地管道失败测试**

验证：

- 生成 `ods/`、`dwd/accepted.jsonl`、`dwd/quarantine.jsonl`、`ads/run_manifest.json`；
- manifest 行数满足 `input = accepted + quarantined`；
- 相同 `run_id` 重跑覆盖同批次产物且不追加重复记录。

- [ ] **Step 4: 实现本地管道**

本地路径作为 Spark/HDFS 作业的规则参考实现和小数据复现入口；只使用流式 JSONL 写入，不一次性保存所有原始文件副本。

- [ ] **Step 5: 运行测试**

Run: `python -m unittest tests.test_source_adapters tests.test_local_pipeline -v`

- [ ] **Step 6: 提交**

```bash
git add src/data_platform/adapters.py src/data_platform/manifest.py src/data_platform/local_pipeline.py tests/fixtures tests/test_source_adapters.py tests/test_local_pipeline.py
git commit -m "feat: add multisource adapters and reproducible local pipeline"
```

### Task 5: 实现 Spark ODS/DWD/DWS/ADS 分层作业

**Files:**
- Create: `src/data_platform/spark_pipeline.py`
- Create: `scripts/run_spark_pipeline.py`
- Create: `tests/test_spark_pipeline.py`
- Create: `requirements-spark.txt`

**Interfaces:**
- Consumes: Task 2 contract fields and Task 3 quality semantics.
- Produces: `create_spark_session(app_name: str, master: str = "local[1]")`
- Produces: `normalize_spark_frame(df, source_dataset: str, dataset_role: str)`
- Produces: `build_dws(df)` and `build_ads(dws_df)`
- Produces CLI arguments `--input`, `--input-format`, `--source-dataset`, `--dataset-role`, `--output-root`, `--master`, `--run-id`.

- [ ] **Step 1: 编写 Spark 失败测试**

```python
def test_spark_pipeline_builds_quality_flags_and_month_partition(self):
    output = normalize_spark_frame(input_df, "self_crawled", "business_primary")
    row = output.collect()[0].asDict()
    self.assertIn("quality_score", row)
    self.assertEqual(row["event_month"], "2026-01")
```

- [ ] **Step 2: 验证失败**

Run: `python -m unittest tests.test_spark_pipeline -v`

- [ ] **Step 3: 实现兼容 Spark 3.5 的转换**

只使用 Spark 3.5 已支持的 SQL 函数。写入：

```text
<output>/ods/source_dataset=<source>/ingest_date=<date>/
<output>/dwd/platform=<platform>/event_month=<month>/
<output>/quarantine/reason=<reason>/
<output>/dws/
<output>/ads/
<output>/manifests/run_id=<run_id>/manifest.json
```

- [ ] **Step 4: 验证本地 Spark 作业**

Run: `python -m unittest tests.test_spark_pipeline -v`

Run: `python scripts/run_spark_pipeline.py --input tests/fixtures/self_review.csv --input-format csv --source-dataset self_crawled --dataset-role business_primary --output-root tmp/spark-smoke --master local[1] --run-id smoke`

Expected: DWD/DWS/ADS Parquet and manifest created; process exit 0.

- [ ] **Step 5: 提交**

```bash
git add src/data_platform/spark_pipeline.py scripts/run_spark_pipeline.py tests/test_spark_pipeline.py requirements-spark.txt
git commit -m "feat: add Spark warehouse layer pipeline"
```

### Task 6: 实现外部 Wildberries 子集提取

**Files:**
- Create: `src/data_platform/external_wb.py`
- Create: `scripts/fetch_public_wb_subset.py`
- Create: `tests/test_external_wb.py`
- Modify: `requirements.txt`

**Interfaces:**
- Produces: `build_question_filter(brands: Sequence[str], categories: Sequence[str] = ()) -> tuple[str, list[str]]`
- Produces: `fetch_parquet_urls(dataset: str, split: str = "train") -> list[str]`
- Produces: `extract_question_subset(source_urls: Sequence[str], output_path: Path, brands: Sequence[str], limit: int) -> dict`
- CLI supports `--dataset`, `--brands`, `--limit`, `--output`, `--metadata-output`, and `--dry-run`.

- [ ] **Step 1: 编写安全查询和来源元数据失败测试**

测试品牌参数不会直接拼入 SQL，输出元数据包含 Hugging Face 数据集 URL、许可证、提取时间、过滤条件和结果行数。

- [ ] **Step 2: 验证失败**

Run: `python -m unittest tests.test_external_wb -v`

- [ ] **Step 3: 实现基于 DuckDB 的分片过滤**

通过 Hugging Face datasets-server 获取 Parquet URL，DuckDB 使用参数化过滤和 `COPY (...) TO ... (FORMAT PARQUET, COMPRESSION ZSTD)` 输出目标子集。默认只处理 `nyuuzyou/wb-questions`，不下载完整 Feedbacks/Products。

- [ ] **Step 4: 本地 fixture 验证和远程 dry-run**

Run: `python -m unittest tests.test_external_wb -v`

Run: `python scripts/fetch_public_wb_subset.py --dataset nyuuzyou/wb-questions --brands vivo iqoo --limit 1000 --output tmp/public-wb/questions.parquet --metadata-output tmp/public-wb/questions.metadata.json --dry-run`

- [ ] **Step 5: 在网络和磁盘允许时提取有限样本**

Run without `--dry-run`, preserving the `--limit 1000` guard for the first real extraction. If remote DuckDB scanning is unsupported, fall back to downloading the 560MB questions Parquet locally and filter it, recording the fallback in metadata.

- [ ] **Step 6: 提交**

```bash
git add src/data_platform/external_wb.py scripts/fetch_public_wb_subset.py tests/test_external_wb.py requirements.txt
git commit -m "feat: add licensed Wildberries subset extraction"
```

### Task 7: 实现数据源对照研究和业务数据集

**Files:**
- Create: `src/analysis/source_comparison.py`
- Create: `src/analysis/business_marts.py`
- Create: `scripts/run_source_comparison.py`
- Create: `tests/test_source_comparison.py`
- Create: `tests/test_business_marts.py`

**Interfaces:**
- Produces: `build_matched_cohort(primary: pd.DataFrame, external: pd.DataFrame, max_per_product: int, seed: int) -> pd.DataFrame`
- Produces: `compare_sources(cohort: pd.DataFrame) -> dict`
- Produces: `build_business_marts(records: pd.DataFrame) -> dict[str, pd.DataFrame]`
- Produces report JSON and HTML with sample sizes, confidence intervals, effect sizes and limitations.

- [ ] **Step 1: 编写匹配样本失败测试**

验证只比较共同 `product_id`，每个来源每个产品样本数相同，固定随机种子得到相同结果。

- [ ] **Step 2: 实现匹配样本**

优先精确 `product_id`；不在分析函数中执行模糊实体匹配。没有共同产品时返回明确诊断而不是生成伪比较。

- [ ] **Step 3: 编写统计输出失败测试**

验证输出包括：样本量、文本缺失率、平均/中位文本长度、评分分布、负面率、Bootstrap 95% CI、Mann-Whitney U、卡方或 Fisher 检验、Jensen-Shannon 散度和限制说明。

- [ ] **Step 4: 实现对照分析与 HTML 报告**

所有统计函数处理空样本、常数列和样本过小情况；无法计算时输出 `null` 和原因，不抛出不可解释异常。

- [ ] **Step 5: 构建 ADS 业务 mart**

只让对应 eligibility 为真的记录进入评分、趋势、文本和产品指标。每个结果表必须带 `eligible_records` 和 `total_records`。

- [ ] **Step 6: 运行测试**

Run: `python -m unittest tests.test_source_comparison tests.test_business_marts -v`

- [ ] **Step 7: 提交**

```bash
git add src/analysis/source_comparison.py src/analysis/business_marts.py scripts/run_source_comparison.py tests/test_source_comparison.py tests/test_business_marts.py
git commit -m "feat: add matched source comparison analysis"
```

### Task 8: 集成统一 CLI、仪表盘数据和质量报告

**Files:**
- Modify: `src/run_pipeline.py`
- Modify: `src/dashboard/generate_stats.py`
- Create: `scripts/run_quality_audit.py`
- Create: `tests/test_platform_cli.py`
- Create: `tests/test_dashboard_governance.py`
- Modify: `airflow/dag_pipeline.py`

**Interfaces:**
- `src/run_pipeline.py` adds stages `warehouse`, `source_comparison`, `governance_export` without breaking existing stage names.
- `dashboard_data.js` adds `governance` with run manifest, quality summary, source comparison status and data freshness.
- Airflow DAG reads `PROJECT_ROOT` from environment and uses non-deprecated operators where possible; it remains an optional template.

- [ ] **Step 1: 编写 CLI 路由失败测试**

验证 `--quality-only` 保持兼容，新 `--platform-local` 和 `--source-comparison` 参数调用对应入口，命令失败时返回非零状态。

- [ ] **Step 2: 修改管道编排**

新平台阶段默认显式启用，避免在现有生产运行中未经配置就读取外部数据。所有路径来自环境变量或 CLI，不硬编码服务器目录。

- [ ] **Step 3: 编写治理数据失败测试**

验证 dashboard 输出在无治理文件时返回 `status=unavailable`，有 manifest 时显示输入、接受、隔离、重复、质量门禁和生成时间。

- [ ] **Step 4: 实现治理导出**

`generate_stats.py` 读取 ADS/manifest 的小型 JSON 产物，不直接扫描 HDFS 大表。

- [ ] **Step 5: 修复 Airflow 示例配置**

将 `/path/to/...` 改为环境变量；DAG 文档明确其为可选模板且当前 ECS 不部署常驻 Airflow。

- [ ] **Step 6: 运行测试**

Run: `python -m unittest tests.test_platform_cli tests.test_dashboard_governance -v`

- [ ] **Step 7: 提交**

```bash
git add src/run_pipeline.py src/dashboard/generate_stats.py scripts/run_quality_audit.py tests/test_platform_cli.py tests/test_dashboard_governance.py airflow/dag_pipeline.py
git commit -m "feat: integrate governance outputs with pipeline and dashboard"
```

### Task 9: 文档、运行验证和优化记录

**Files:**
- Modify: `README.md`
- Create: `docs/data_dictionary.md`
- Create: `docs/metric_dictionary.md`
- Create: `docs/architecture.md`
- Modify: `docs/project_optimization_log.md`
- Modify: `.gitignore`

**Interfaces:**
- README commands must be copy/paste runnable.
- Data dictionary matches contract YAML field names.
- Metric dictionary states eligibility filters and denominators.
- Architecture document distinguishes implemented, optional and planned components.

- [ ] **Step 1: 更新文档但不写死未经验证的数字**

README 从 manifest 或审计 Notebook 引用数据规模；说明自采主数据、外部验证数据、观察性来源对照和离线管道 A/B 的边界。

- [ ] **Step 2: 更新优化日志**

每个完成阶段记录提交号、测试命令、真实结果和遗留限制。将尚未完成项保持为“未开始”或“进行中”。

- [ ] **Step 3: 运行完整测试**

Run: `python -m unittest discover tests -v`

Expected: all tests pass, 0 failures, 0 errors.

- [ ] **Step 4: 运行小数据端到端验证**

```bash
python scripts/run_spark_pipeline.py --input tests/fixtures/self_review.csv --input-format csv --source-dataset self_crawled --dataset-role business_primary --output-root tmp/e2e-warehouse --master local[1] --run-id e2e
python scripts/run_source_comparison.py --primary tests/fixtures/self_review.csv --external tests/fixtures/public_wb_question.jsonl --output-dir tmp/e2e-report
```

Expected: warehouse Parquet, run manifest, comparison JSON and HTML created.

- [ ] **Step 5: 检查仓库状态和差异**

Run: `git diff --check`

Run: `git status --short`

确认没有提交真实密码、API Key、大体积原始数据、临时报告或无关用户文件。

- [ ] **Step 6: 提交**

```bash
git add README.md docs .gitignore
git commit -m "docs: document trustworthy multisource analytics workflow"
```

## Plan Self-Review

- Spec coverage: data contract、稳定商品标识、质量门禁、ODS/DWD/DWS/ADS、外部 WB 子集、来源对照、离线管道 A/B、ADS 治理输出、资源约束均有对应任务。
- Placeholder scan: no TBD/TODO/implement-later placeholders.
- Type consistency: canonical record dictionaries are consumed by quality and deduplication; manifests are consumed by dashboard governance; product IDs are the sole matching key in statistical analysis.
- Scope decision: machine learning remains explicitly out of scope.

