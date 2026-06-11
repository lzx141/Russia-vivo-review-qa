# 跨境电商多语言用户反馈智能分析系统

基于大语言模型的跨境电商多语言用户反馈智能分析数字化大屏  
大数据处理与技术 课程设计

---

## 快速启动

```bash
# 1. 进入项目目录
cd Russia-vivo-review-qa

# 2. 配置环境变量（复制并填写）
cp .env.example .env
# 编辑 .env 填入数据库密码、DeepSeek API Key 等

# 3. 安装依赖
pip install -r requirements.txt

# 4. 初始化数据库并导入翻译数据
python src/etl/init_database.py --load-translated

# 5. 生成大屏数据
python src/dashboard/generate_stats.py

# 6. 启动 HTTP 服务器
cd src/dashboard
python -m http.server 8899

# 7. 浏览器访问
open http://localhost:8899/index.html
```

---

## 文件结构

```
Russia-vivo-review-qa/
├── config/                    # 配置文件
│   └── config.py              # 全局配置（支持 .env 环境变量覆盖）
├── data/                      # 数据文件
│   └── PlainText.txt          # 原始数据文件
├── src/                       # 源代码目录
│   ├── analysis/              # AI 分析管道 ★ 新增
│   │   └── analyzer.py        # 情感/意图/NER/根因/摘要分析器
│   ├── crawler/               # 爬虫模块
│   │   ├── base.py            # 爬虫基类（BrowserDriver/DataSaver）★ 新增
│   │   ├── ozon_crawler.py    # OZON 评论爬虫
│   │   ├── ozon_questions.py  # OZON 问答爬虫
│   │   └── wildberries_crawler.py  # Wildberries 爬虫
│   ├── etl/                   # ETL 模块
│   │   ├── database.py        # 数据库操作封装（含翻译表 + 分析缓存表）
│   │   ├── etl.py             # ETL 处理器（logging + 进度条）
│   │   └── init_database.py   # 数据库初始化脚本（支持 --load-translated）
│   ├── translation/           # 翻译管道 ★ 新增
│   │   └── translate.py       # 火山引擎翻译（断点续传）
│   └── dashboard/             # 可视化大屏
│       ├── index.html         # 主页面（多页面交互式大屏）
│       ├── app.js             # 全局状态 + 导航 + 粒子背景 ★ 拆分
│       ├── charts.js          # 各页面图表渲染函数 ★ 拆分
│       ├── russia_cities.js   # 俄罗斯城市坐标（地图涟漪用）★ 新增
│       ├── dashboard_data.js  # 大屏数据文件（自动生成）
│       ├── Russia.js          # 俄罗斯地图 GeoJSON
│       ├── generate_stats.py  # 数据统计生成脚本（DB 优先 → CSV 降级）
│       ├── echarts.min.js     # ECharts 核心库
│       └── echarts-wordcloud.min.js  # ECharts 词云插件
├── .env.example               # 环境变量模板 ★ 新增
├── .gitignore                 # Git 忽略规则
├── README.md                  # 项目说明文档
└── requirements.txt           # Python 依赖列表
```

---

## 技术架构

```
┌─────────────────────────────────────────────────────────────────┐
│                         前端展示层                                │
│   ECharts 5.5 + WordCloud + GeoMap + 俄罗斯地图 + 原生 JS       │
│   app.js（全局） + charts.js（图表） + 按页面懒加载              │
├─────────────────────────────────────────────────────────────────┤
│                         数据处理层                                │
│   generate_stats.py → jieba + TF-IDF + SQL 聚合 + LLM 结果解析  │
│   数据库优先（MySQL）→ CSV 降级                                  │
├─────────────────────────────────────────────────────────────────┤
│                         AI 分析层 ★                              │
│   DeepSeek V4 Flash API → 情感 / 意图 / NER / 根因 / 摘要      │
│   analysis_cache 表缓存结果，避免重复调用                       │
├─────────────────────────────────────────────────────────────────┤
│                         翻译层 ★                                │
│   火山引擎翻译 API → 俄语 → 中文 / 英文（断点续传）             │
├─────────────────────────────────────────────────────────────────┤
│                         数据层                                    │
│   Wildberries + OZON 用户评论/问答 → MySQL (82,196 条)          │
└─────────────────────────────────────────────────────────────────┘
```

---

## 配置说明

### 方式一：`.env` 文件（推荐）

```bash
# 复制模板
cp .env.example .env

# 编辑 .env 填入密钥
MYSQL_PASSWORD=your_mysql_password
DEEPSEEK_API_KEY=sk-your-deepseek-api-key
```

### 方式二：环境变量

```bash
export MYSQL_PASSWORD=your_mysql_password
export DEEPSEEK_API_KEY=sk-your-deepseek-api-key
```

### 配置项一览

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `MYSQL_HOST` | `localhost` | MySQL 主机 |
| `MYSQL_PORT` | `3306` | MySQL 端口 |
| `MYSQL_USER` | `root` | MySQL 用户 |
| `MYSQL_PASSWORD` | `""` | MySQL 密码 |
| `MYSQL_DATABASE` | `russia_ecommerce` | 数据库名 |
| `DEEPSEEK_API_KEY` | `""` | DeepSeek V4 Flash API Key |
| `DEEPSEEK_API_URL` | `https://api.deepseek.com` | DeepSeek API 端点 |
| `VOLC_ACCESS_KEY` | `""` | 火山引擎翻译 Access Key |
| `VOLC_SECRET_KEY` | `""` | 火山引擎翻译 Secret Key |

### 安全说明

⚠️ `.env` 文件已配置 `.gitignore` 规则，**不会提交到代码仓库**。  
所有密码和 API Key 仅从环境变量读取，`config.py` 中无硬编码密钥。

---

## 大屏功能页面

| 页面 | 功能 | 交互方式 |
|------|------|----------|
| **总览** | KPI 卡片 + 趋势图 + 评分分布 + 词云 + 平台对比 | 数字滚动动画、hover 高亮 |
| **情感洞察** | 情感分布饼图 + 维度雷达图 + 正/负面词云 + 维度热度排行 | 正面/中性/负面 toggle 按钮（实时过滤） |
| **产品分析** | 25 个产品卡片 + 月度趋势 + 评分对比 | 点击卡片弹出 Modal 详情 |
| **地域分析** | **俄罗斯全境地图 + effectScatter 涟漪** | 缩放拖拽、hover 高亮 |
| **时间轴** | 日历热力图 + DataZoom 趋势图 + 评论长度分布 | 时间滑块拖拽、图表缩放 |
| **问答洞察** | 意图分类 + 问题词云 + 评分-长度散点图 + 活跃用户 | DataZoom 缩放 |
| **差评诊断** | 根因排行 + 严重度分布 + 差评关键词（LLM Root Cause） | hover 查看 |

---

## 数据流

```
Wildberries / OZON 原始俄语数据 (Excel)
       ↓
[ETL] src/etl/etl.py → 数据清洗、去重 → MySQL (reviews / questions)
       ↓
[翻译] src/translation/translate.py → 火山引擎 API → MySQL (translated_records)
       ↓
[AI 分析] src/analysis/analyzer.py → DeepSeek API → MySQL (analysis_cache)
       ↓
[统计] src/dashboard/generate_stats.py → SQL 聚合 → dashboard_data.js
       ↓
[展示] index.html + app.js + charts.js → ECharts 可视化
```

---

## 命令速查

### 数据导入

```bash
# 初始化数据库 + 创建表
python src/etl/init_database.py

# 从 CSV 导入翻译数据到 DB
python src/etl/init_database.py --load-translated

# 完整 ETL（爬取→转换→加载 + 翻译数据入库）
python src/etl/etl.py
```

### AI 分析

```bash
# 一键运行所有分析（情感 / 意图 / NER / 根因）
python src/analysis/analyzer.py --mode all --db

# 单模式运行
python src/analysis/analyzer.py --mode sentiment --db
python src/analysis/analyzer.py --mode intent --db
```

### 翻译

```bash
# 完整翻译管道（原始 Excel → 翻译 → CSV）
python src/translation/translate.py

# 增量翻译已存在的 CSV
python src/translation/translate.py --from-csv

# 断点续传
python src/translation/translate.py --resume
```

### 仪表盘

```bash
# 生成大屏数据（DB 优先 → CSV 降级）
python src/dashboard/generate_stats.py

# 启动服务
cd src/dashboard
python -m http.server 8899
```

---

## 数据概况

- **数据总量**：82,196 条（评论 52,462 + 问答 29,734）
- **产品数**：25 款 vivo/iQOO 手机
- **平均评分**：4.85 / 5.0
- **数据时间**：2025.03 - 2026.04
- **数据来源**：Wildberries、OZON（俄罗斯电商平台）

---

## 技术栈

| 层级 | 技术 |
|------|------|
| 前端可视化 | ECharts 5.5.0、ECharts WordCloud、ECharts GeoMap |
| AI 模型 | DeepSeek V4 Flash（情感/意图/NER/根因/摘要） |
| 翻译引擎 | 火山引擎翻译 API（俄→中/英） |
| 数据处理 | Pandas、NumPy、jieba 分词、scikit-learn TF-IDF |
| 数据库 | MySQL（含 analysis_cache 缓存表） |
| 爬虫 | Selenium、Requests |
| 部署 | Python http.server |
