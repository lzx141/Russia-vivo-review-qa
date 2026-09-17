# Executive Intelligence Dashboard Redesign

## Goal

将现有静态 ECharts 大屏重构为适合秋招作品展示和日常分析演示的专业数据产品。新版应在不改变现有统计数据接口和 Nginx 静态部署方式的前提下，提高视觉品质、信息层级、移动端可用性和数据治理可信度。

## Product Positioning

视觉方向采用 **Executive Intelligence**：深色曜石底色、克制的蓝紫渐变光、清晰的留白和高密度但可快速扫描的信息布局。页面应更像成熟企业数据产品，避免霓虹堆叠、装饰性 3D、无意义粒子效果和夸张动效。

首要使用场景：

1. 面试官在 1–3 分钟内理解项目规模、业务洞察和数据工程可信度；
2. 用户在桌面端浏览完整分析，并能在平板或手机上查看核心指标；
3. 页面由现有 Nginx 直接托管，不依赖前端构建链或外部 CDN。

## Scope

### Included

- 重构应用外壳、侧边栏、顶部状态栏、页面标题、KPI、卡片、控件、弹窗、加载态和空状态；
- 保留现有七个分析页面及其图表 DOM ID；
- 新增“数据治理”页面，消费 `DASHBOARD_DATA.governance`；
- 提升导航、键盘访问、移动端抽屉、URL hash 和窗口缩放行为；
- 统一 ECharts 主题、tooltip、坐标轴、图例、色板、动画和无数据状态；
- 增加静态结构/行为测试和桌面、移动端浏览器验收；
- 更新 README 中的页面说明和运行截图说明。

### Excluded

- 不引入 React、Vue、TypeScript 或打包工具；
- 不更改 MySQL、Spark、ETL 和统计生成的核心口径；
- 不增加机器学习功能；
- 不使用需要联网加载的字体、图标库或 CDN；
- 不伪造治理数据、来源对照指标或刷新状态。

## Information Architecture

应用保留单页多视图结构，导航顺序调整为：

1. 总览
2. 情感洞察
3. 产品分析
4. 地域分析
5. 时间趋势
6. 问答洞察
7. 差评诊断
8. 数据治理

桌面端使用固定侧边栏和顶部状态栏；移动端侧边栏转为可关闭抽屉。顶部状态栏展示当前页面、数据时间范围、最后更新时间和数据状态，不重复展示侧边栏内容。

URL 使用 `#overview`、`#sentiment` 等 hash。刷新后恢复当前页面；无效 hash 回退到总览。导航项目采用按钮语义并提供 `aria-current`，移动端抽屉支持 Escape 关闭。

## Visual System

### Tokens

- Background: 深蓝黑曜石层级，页面、侧栏、卡片至少三个明度层；
- Accent: cyan → indigo 的克制渐变，主要用于选中态、关键趋势和品牌标识；
- Semantic: positive、warning、negative、neutral 独立颜色，保证图表和文本一致；
- Typography: 系统字体栈，数字使用等宽字体；标题采用紧凑字距，正文保持高可读行高；
- Radius: 10–18px 分级，交互控件小圆角、主卡片大圆角；
- Motion: 160–320ms，使用透明度和轻微位移；`prefers-reduced-motion` 时关闭非必要动画。

### Layout

- 最大内容宽度约 1600px，适配 1440p 和常见笔记本屏幕；
- 总览首屏采用 KPI strip + 主趋势 + 评分/平台卡片的非对称布局；
- 卡片标题包含 eyebrow、标题和可选说明，避免所有标题使用相同视觉权重；
- 图表容器统一内边距和最小高度；窄屏下单列排列；
- KPI 卡片显示标签、数值、单位和语义化辅助信息，不使用纯装饰 emoji。

### Icons

使用内联 SVG 图标集，由 HTML 直接引用或在 CSS 中呈现。不引入外部图标依赖。图标仅辅助识别，导航文本始终保留。

## Component Changes

### `index.html`

- 保留所有现有图表节点 ID，以兼容 `charts.js`；
- 将内联样式移至 `styles.css`；
- 使用 `aside`、`header`、`main`、`section`、`button` 等语义结构；
- 增加移动端菜单按钮、遮罩、全局状态区域和治理页节点；
- 增加可访问标题、aria 标签、焦点顺序和跳转到主内容链接；
- 继续按本地顺序加载 ECharts、地图、数据、`app.js` 与 `charts.js`。

### `styles.css`

- 定义设计 tokens、响应式断点和可复用组件样式；
- 实现应用 shell、导航、topbar、KPI、card、badge、empty state、modal 和治理组件；
- 使用伪元素创建轻量背景光晕，不使用持续消耗资源的 canvas 粒子；
- 提供 `:focus-visible`、高对比状态和 reduced-motion 分支。

### `app.js`

- 将导航封装为可测试的 hash 路由逻辑；
- 管理移动端抽屉、Escape、modal、加载遮罩和 resize；
- 填充日期范围、更新时间、数据状态和当前页面标题；
- 对缺失 `DASHBOARD_DATA` 提供可读错误状态；
- 避免重复绑定事件或重复创建 KPI 节点。

### `charts.js`

- 保留现有业务图表初始化函数和数据字段；
- 抽取统一 axis、tooltip、legend、grid、empty state 和渐变 helper；
- 调整色板、字号和间距，使图表与新视觉系统一致；
- 新增 `initGovernance()`，只读取真实治理字段；
- 页面没有所需数据时渲染明确空状态，而不是使用 mock 值。

## Governance Page

数据治理页读取：

```text
DASHBOARD_DATA.governance.status
DASHBOARD_DATA.governance.run_manifest
DASHBOARD_DATA.governance.source_comparison
```

当 manifest 可用时显示运行 ID、生成时间、输入、接受、隔离、重复、质量通过率和门禁状态。当来源对照可用时显示匹配产品数、两来源样本量、文本缺失率、文本长度差和 limitations。

当治理数据不可用时显示说明卡片和生成命令，不显示 0、100% 或任何推断值。页面文案明确来源比较是观察性研究，不是随机 A/B Test。

## Error and Empty States

- 数据文件未加载：显示完整错误面板和 `python src/dashboard/generate_stats.py` 命令；
- 单个图表字段缺失：仅该卡片显示 empty state，不影响其他页面；
- 地图或词云扩展缺失：显示降级提示；
- 治理 JSON 缺失：显示 unavailable 与接入说明；
- 所有用户可见字符串通过安全文本写入或 HTML 转义。

## Responsive Behavior

- `>= 1200px`：完整侧边栏、多列分析网格；
- `768–1199px`：紧凑侧边栏或抽屉，两列/单列混合；
- `< 768px`：顶部菜单、单列卡片、横向可滚动控件、适当降低图表高度；
- `< 480px`：KPI 两列，长标题和状态标签换行；
- modal 在移动端改为接近全屏，并保持关闭按钮可见。

## Testing and Acceptance

### Automated

新增前端静态测试，至少验证：

- `styles.css` 外链存在，HTML 不再包含大段内联样式；
- 八个页面和导航目标一一对应；
- 所有现有图表 ID 保留；
- 治理页、不可用状态、移动端菜单和可访问属性存在；
- app 路由支持 hash 恢复和未知页面回退；
- Python 全量测试与 Python 3.12 Spark 测试继续通过。

### Browser QA

- 本地 HTTP 服务加载无控制台致命错误；
- 1440×900 桌面端：首屏层级清晰，无横向溢出；
- 390×844 移动端：抽屉可开关，页面单列，图表可读；
- 逐页点击八个页面，图表 resize 正常；
- 治理有数据/无数据两种状态均可读；
- modal、筛选按钮和产品选择器正常工作。

## Delivery

实现放在 `codex/dashboard-executive-redesign` 分支。通过自动测试和浏览器 QA 后提交，推送 GitHub，并在用户授权后合并到 `main`。本地未跟踪的简历、Notebook、artifacts 和扩展目录不纳入提交。
