# 统一反馈数据字典

本文与 `config/data_contract.yaml` 同步。`business_primary` 表示自主采集的业务主数据，`external_validation` 表示只用于验证的外部数据。

| 字段 | 含义 | 规则 |
|---|---|---|
| `record_id` | 记录唯一标识 | 优先来源 ID，否则按来源、商品、日期、评分和文本生成 SHA256 |
| `source_dataset` | 数据集名称 | 如 `self_crawled`、`nyuuzyou/wb-questions` |
| `source_record_id` | 来源侧记录 ID | 可空 |
| `dataset_role` | 数据集角色 | `business_primary` / `external_validation` / `benchmark` |
| `platform` | 平台标准名 | 统一为小写标准值，如 `wildberries`、`ozon` |
| `record_type` | 记录类型 | `review` 或 `question` |
| `product_id` | 跨流程商品主键 | 优先 `<platform>:<source_product_id>`；缺失时使用标准化名称哈希 |
| `source_product_id` | 平台商品 ID | 来自 URL、`nmId`、SKU 等 |
| `product_name` | 商品名称 | 去除首尾空白；可空 |
| `brand` | 品牌 | 可空 |
| `category` | 品类 | 可空 |
| `rating` | 评分 | 统一为浮点数；有效范围 1–5 |
| `text` | 评论正文或问题文本 | question 记录优先使用 `question` |
| `answer` | 商家/平台回答 | 可空 |
| `author` | 作者 | 可空，不作为唯一主键 |
| `event_date` | 业务发生日期 | ISO 格式；未来日期判为无效 |
| `ingested_at` | 入湖时间 | UTC ISO 时间 |
| `pipeline_run_id` | 运行批次 | 用于幂等、追溯和对账 |
| `license` | 外部数据许可证 | 自采可空；公开 WB 子集为 `CC0-1.0` |
| `source_file` | 来源文件 | 保留文件名或路径线索 |
| `product_match_method` | 商品映射方法 | `source_product_id`、名称哈希或 `unresolved` |
| `product_match_confidence` | 商品映射置信度 | 0–1；来源商品 ID 为 1.0 |
| `quality_score` | 质量分 | 0–100，由记录类型对应权重计算 |
| `quality_issues` | 质量问题列表 | 如缺正文、缺日期、低俄文比例、重复 |
| `duplicate_of` | 重复记录指向 | 被隔离记录指向保留的 `record_id` |
| `is_rating_eligible` | 评分指标准入 | 仅有效评论评分且达到阈值 |
| `is_trend_eligible` | 趋势指标准入 | 日期有效且达到阈值 |
| `is_text_eligible` | 文本指标准入 | 文本长度、语言与质量分达标 |
| `is_product_eligible` | 商品指标准入 | 商品映射置信度与质量分达标 |

必填字段为 `record_id`、`source_dataset`、`dataset_role`、`platform`、`record_type` 和 `product_id`。
