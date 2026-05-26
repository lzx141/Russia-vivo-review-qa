# 跨境电商多语言用户反馈智能分析系统

基于大语言模型的跨境电商多语言用户反馈智能分析数字化大屏  
大数据处理与技术 课程设计

---

## 快速启动

### 方式一：本地启动（推荐）

```bash
# 1. 进入项目目录
cd Russia-vivo-review-qa

# 2. 启动本地 HTTP 服务器（在 src/dashboard 目录下）
cd src/dashboard
python3 -m http.server 8899

# 3. 浏览器访问
open http://localhost:8899/index.html
```

---

## 文件结构

```
Russia-vivo-review-qa/
├── config/                    # 配置文件
│   └── config.py              # 数据库配置（支持环境变量）
├── data/                      # 数据文件
│   └── PlainText.txt          # 原始数据文件
├── src/                       # 源代码目录
│   ├── crawler/               # 爬虫模块
│   │   ├── ozon_crawler.py    # OZON 评论爬虫
│   │   ├── ozon_questions.py  # OZON 问答爬虫
│   │   └── wildberries_crawler.py  # Wildberries 爬虫
│   ├── etl/                   # ETL 模块
│   │   ├── database.py        # 数据库操作封装
│   │   ├── etl.py             # ETL 处理器
│   │   └── init_database.py   # 数据库初始化脚本
│   └── dashboard/             # 可视化大屏
│       ├── index.html         # 主页面（多页面交互式大屏）
│       ├── dashboard_data.js  # 大屏数据文件
│       ├── Russia.js          # 俄罗斯地图 GeoJSON
│       ├── generate_stats.py  # 数据统计生成脚本
│       ├── echarts.min.js     # ECharts 核心库
│       └── echarts-wordcloud.min.js  # ECharts 词云插件
├── .gitignore                 # Git 忽略规则
├── README.md                  # 项目说明文档
└── requirements.txt           # Python 依赖列表
```

---

## 技术架构

```
┌─────────────────────────────────────────────────────────────────┐
│                         前端展示层                                │
│   ECharts 5.5 + WordCloud + GeoMap + 原生 JS 多页面路由          │
├─────────────────────────────────────────────────────────────────┤
│                         数据处理层                                │
│   generate_stats.py → TF-IDF + 统计计算 + LLM 结果解析          │
├─────────────────────────────────────────────────────────────────┤
│                         AI 分析层                                 │
│   Qwen3.6-27B (vLLM) → 情感 / 意图 / NER / 根因 / 摘要         │
├─────────────────────────────────────────────────────────────────┤
│                         翻译层                                    │
│   HY-MT1.5-1.8B (vLLM) → 俄语 → 中文/英文                      │
├─────────────────────────────────────────────────────────────────┤
│                         数据层                                    │
│   Wildberries + OZON 用户评论/问答 → Parquet (71170 条)          │
└─────────────────────────────────────────────────────────────────┘
```

---

## 大屏功能页面

| 页面 | 功能 | 交互方式 |
|------|------|----------|
| **总览** | KPI 卡片 + 趋势图 + 评分分布 + 词云 + 平台对比 | 数字滚动动画、hover 高亮 |
| **情感洞察** | 情感分布饼图 + 维度雷达图 + 正/负面词云 + 维度热度排行 | 正面/中性/负面 toggle 按钮 |
| **产品分析** | 25 个产品卡片 + 月度趋势 + 评分对比 | 点击卡片弹出 Modal 详情 |
| **地域分析** | 俄罗斯全境地图 + effectScatter 涟漪 + 飞线动画 | 缩放拖拽、hover 高亮 |
| **时间轴** | 日历热力图 + DataZoom 趋势图 + 评论长度分布 | 时间滑块拖拽、图表缩放 |
| **问答洞察** | 意图分类 + 问题词云 + 评分-长度散点图 + 活跃用户 | DataZoom 缩放 |
| **差评诊断** | 根因排行 + 严重度分布 + 差评关键词 | LLM Root Cause 分析 |

---

## 重新生成数据

如果修改了数据或 LLM 缓存，重新生成大屏数据：

```bash
cd src/dashboard
python generate_stats.py
# 刷新浏览器即可看到更新
```

---

## ETL 流程

```bash
# 1. 初始化数据库
python src/etl/init_database.py

# 2. 运行 ETL 管道（爬取 -> 转换 -> 加载）
python src/etl/etl.py

# 3. 生成大屏数据
python src/dashboard/generate_stats.py

# 4. 启动服务
cd src/dashboard
python -m http.server 8899
```

---

## 数据概况

- **数据总量**：82,196 条（评论 52,462 + 问答 29,734）
- **产品数**：25 款 vivo/iQOO 手机
- **平均评分**：4.83/5.0
- **数据时间**：2025.03 - 2026.04
- **数据来源**：Wildberries、OZON（俄罗斯电商平台）

---

## 技术栈

| 层级 | 技术 |
|------|------|
| 前端可视化 | ECharts 5.5.0、ECharts WordCloud、ECharts GeoMap |
| AI 模型 | Qwen3.6-27B（情感/意图/NER/根因）、HY-MT1.5-1.8B（翻译）|
| 推理框架 | vLLM（GPU 加速推理） |
| 数据处理 | Pandas、NumPy、TF-IDF |
| 数据库 | MySQL |
| 异步调用 | aiohttp、asyncio |
| 数据格式 | Parquet、JSON、CSV |
| 部署 | Python http.server |
