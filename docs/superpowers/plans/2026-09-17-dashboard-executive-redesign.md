# Executive Intelligence Dashboard Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将现有静态 ECharts 大屏重构为高级、可信、响应式的 Executive Intelligence 数据产品，并新增真实数据治理页面。

**Architecture:** 保留 `dashboard_data.js` 与既有图表 DOM ID，在静态 HTML/CSS/JavaScript 范围内重做应用外壳。新增纯函数模块 `dashboard_core.js` 处理路由、格式化和治理视图模型，使关键行为可由 Node 测试；`app.js` 负责 DOM/交互，`charts.js` 负责 ECharts 和治理页渲染。

**Tech Stack:** HTML5、CSS3、原生 JavaScript、ECharts 5、本地静态资源、Python unittest、Node.js built-in test runner

**Spec:** `docs/superpowers/specs/2026-09-17-dashboard-executive-redesign.md`

## Global Constraints

- 不引入 React、Vue、TypeScript、构建工具、外部 CDN、联网字体或图标库。
- 保留现有七个分析页面、现有图表 DOM ID 和 `DASHBOARD_DATA` 数据接口。
- 新增数据治理页面时只读取真实 `governance` 字段；不可用时显示 unavailable，禁止生成推断指标。
- 所有页面必须由 Nginx 或 `python -m http.server` 直接托管。
- 桌面、平板、手机可用；支持键盘焦点、Escape 关闭、hash 恢复和 reduced motion。
- 本地未跟踪的简历、Notebook、artifacts 与浏览器扩展目录不得加入提交。

## File Map

- Create `src/dashboard/styles.css`: 设计 tokens、应用 shell、组件、响应式和无障碍样式。
- Create `src/dashboard/dashboard_core.js`: 可测试的路由、数字格式化、治理视图模型纯函数。
- Modify `src/dashboard/index.html`: 语义结构、八页面导航、治理页和无障碍节点。
- Modify `src/dashboard/app.js`: hash 路由、抽屉、状态栏、modal、加载和事件绑定。
- Modify `src/dashboard/charts.js`: 统一图表主题、空状态、内容增强和治理页渲染。
- Create `tests/test_dashboard_frontend.py`: 静态 HTML/CSS/接口契约测试。
- Create `tests/dashboard_core.test.js`: Node 纯函数行为测试。
- Modify `README.md`: 新页面、运行和验收说明。

---

### Task 1: Lock the Frontend Contract With Failing Tests

**Files:**
- Create: `tests/test_dashboard_frontend.py`
- Create: `tests/dashboard_core.test.js`

**Interfaces:**
- Consumes: current `src/dashboard/index.html` and existing chart IDs.
- Produces: executable structure contract and desired pure-function API.

- [x] **Step 1: Write the static structure tests**

```python
from html.parser import HTMLParser
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
DASHBOARD = ROOT / "src" / "dashboard"

class TestDashboardFrontend(unittest.TestCase):
    def test_external_design_system_and_eight_pages(self):
        html = (DASHBOARD / "index.html").read_text(encoding="utf-8")
        self.assertIn('href="styles.css"', html)
        self.assertNotIn("<style>", html)
        for route in ("overview", "sentiment", "products", "geography", "timeline", "qa", "diagnosis", "governance"):
            self.assertIn(f'id="page-{route}"', html)
            self.assertIn(f'data-page="{route}"', html)

    def test_existing_chart_contract_is_preserved(self):
        html = (DASHBOARD / "index.html").read_text(encoding="utf-8")
        for chart_id in ("ovTrend", "ovRating", "ovProductRank", "ovWordcloud", "ovPlatform", "sentPie", "prodMonthly", "geoChart", "tlHeatmap", "qaIntent", "diagRootCause"):
            self.assertIn(f'id="{chart_id}"', html)

    def test_accessible_shell_and_governance_nodes_exist(self):
        html = (DASHBOARD / "index.html").read_text(encoding="utf-8")
        for token in ('id="mobileMenu"', 'id="navBackdrop"', 'id="mainContent"', 'aria-label="主导航"', 'id="governanceContent"'):
            self.assertIn(token, html)
```

- [x] **Step 2: Write the Node behavior tests**

```javascript
const test = require('node:test');
const assert = require('node:assert/strict');
const core = require('../src/dashboard/dashboard_core.js');

test('normalizeRoute restores valid hashes and rejects unknown routes', () => {
  const routes = ['overview', 'governance'];
  assert.equal(core.normalizeRoute('#governance', routes), 'governance');
  assert.equal(core.normalizeRoute('#unknown', routes), 'overview');
});

test('buildGovernanceView never fabricates missing metrics', () => {
  const view = core.buildGovernanceView({status: 'unavailable'});
  assert.equal(view.available, false);
  assert.equal(view.metrics.length, 0);
});
```

- [x] **Step 3: Run both tests and verify expected failures**

Run: `python -m unittest tests.test_dashboard_frontend -v`

Expected: FAIL because `styles.css`, governance page and accessible shell do not exist.

Run: `node --test tests/dashboard_core.test.js`

Expected: FAIL because `dashboard_core.js` does not exist.

- [x] **Step 4: Commit the failing contract tests**

```bash
git add tests/test_dashboard_frontend.py tests/dashboard_core.test.js
git commit -m "test: define executive dashboard contract"
```

### Task 2: Build the Design System and Semantic App Shell

**Files:**
- Create: `src/dashboard/styles.css`
- Modify: `src/dashboard/index.html`
- Test: `tests/test_dashboard_frontend.py`

**Interfaces:**
- Consumes: existing chart IDs and script loading order.
- Produces: eight `.page` sections, `[data-page]` navigation buttons, `#mobileMenu`, `#navBackdrop`, `#mainContent`, `#governanceContent`.

- [x] **Step 1: Extract all inline CSS and introduce design tokens**

Create `styles.css` with tokens beginning:

```css
:root {
  --bg-canvas: #070b14;
  --bg-shell: #0b1120;
  --bg-card: rgba(17, 26, 46, .78);
  --border-soft: rgba(148, 163, 184, .14);
  --text-primary: #f4f7fb;
  --text-secondary: #9aa8bd;
  --accent-cyan: #4fd1ff;
  --accent-indigo: #7c6cff;
  --positive: #39d98a;
  --warning: #f5b942;
  --negative: #ff6b7a;
  --radius-card: 18px;
  --shadow-card: 0 24px 80px rgba(0, 0, 0, .24);
}
```

Add component classes for skip link, sidebar, nav button, topbar, status pill, KPI, card, chart, controls, modal, empty state and governance panels. Add breakpoints at 1200px, 768px and 480px plus `prefers-reduced-motion`.

- [x] **Step 2: Replace the app shell with semantic markup**

In `index.html`:

- link `styles.css` in `<head>` and remove the `<style>` block;
- change nav items to `<button class="nav-item" data-page="...">` with inline SVG and text;
- add skip link, mobile menu button, backdrop and topbar;
- preserve all existing chart IDs and controls;
- remove per-element inline style attributes;
- add `page-governance` with `governanceContent`, manifest metrics, source comparison area and limitations area;
- load `dashboard_core.js` before `app.js`.

- [x] **Step 3: Run the static contract test**

Run: `python -m unittest tests.test_dashboard_frontend -v`

Expected: PASS for structure, preserved IDs and accessibility nodes.

- [x] **Step 4: Validate HTML references and JavaScript syntax**

Run: `python -m unittest tests.test_dashboard_frontend -v`

Run: `node --check src/dashboard/app.js && node --check src/dashboard/charts.js`

Expected: all commands exit 0.

- [x] **Step 5: Commit**

```bash
git add src/dashboard/index.html src/dashboard/styles.css tests/test_dashboard_frontend.py
git commit -m "feat: redesign dashboard shell and visual system"
```

### Task 3: Implement Tested Routing and Governance View Models

**Files:**
- Create: `src/dashboard/dashboard_core.js`
- Modify: `src/dashboard/app.js`
- Test: `tests/dashboard_core.test.js`

**Interfaces:**
- Produces: `normalizeRoute(hash: string, routes: string[]) -> string`
- Produces: `formatMetric(value: unknown, options?: object) -> string`
- Produces: `buildGovernanceView(governance: object | null) -> object`
- Exposes: `window.DashboardCore` in browsers and `module.exports` in Node.

- [x] **Step 1: Implement the pure functions minimally**

```javascript
(function(root, factory) {
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  root.DashboardCore = api;
})(typeof globalThis !== 'undefined' ? globalThis : this, function() {
  function normalizeRoute(hash, routes) {
    const route = String(hash || '').replace(/^#/, '');
    return routes.includes(route) ? route : 'overview';
  }

  function formatMetric(value, {suffix = '', digits = 0} = {}) {
    if (value === null || value === undefined || value === '') return '—';
    const number = Number(value);
    return Number.isFinite(number) ? `${number.toLocaleString('zh-CN', {maximumFractionDigits: digits})}${suffix}` : '—';
  }

  function buildGovernanceView(governance) {
    if (!governance || governance.status !== 'available') {
      return {available: false, status: 'unavailable', metrics: [], comparison: null};
    }
    const manifest = governance.run_manifest || null;
    return {
      available: Boolean(manifest || governance.source_comparison),
      status: governance.status,
      metrics: manifest ? [
        {label: '输入记录', value: manifest.input_rows},
        {label: '接受记录', value: manifest.accepted_rows},
        {label: '隔离记录', value: manifest.quarantined_rows},
        {label: '重复记录', value: manifest.duplicate_rows},
      ] : [],
      manifest,
      comparison: governance.source_comparison || null,
    };
  }

  return {normalizeRoute, formatMetric, buildGovernanceView};
});
```

- [x] **Step 2: Run Node tests and verify green**

Run: `node --test tests/dashboard_core.test.js`

Expected: all tests pass.

- [x] **Step 3: Refactor `app.js` around a single navigation function**

Implement `navigateTo(route, {updateHash = true} = {})` to:

- set active page and `aria-current`;
- update topbar title;
- initialize the selected page once;
- close the mobile drawer;
- resize live charts;
- update hash only when necessary.

Bind `hashchange`, nav clicks, mobile menu, backdrop, Escape and modal focus behavior. Guard every optional DOM node and render a styled fatal data state when `DASHBOARD_DATA` is missing.

- [x] **Step 4: Validate behavior module and syntax**

Run: `node --test tests/dashboard_core.test.js`

Run: `node --check src/dashboard/dashboard_core.js && node --check src/dashboard/app.js`

Expected: all commands exit 0.

- [x] **Step 5: Commit**

```bash
git add src/dashboard/dashboard_core.js src/dashboard/app.js tests/dashboard_core.test.js
git commit -m "feat: add accessible dashboard routing and state"
```

### Task 4: Unify Chart Presentation and Add the Governance Experience

**Files:**
- Modify: `src/dashboard/charts.js`
- Modify: `src/dashboard/index.html`
- Modify: `src/dashboard/styles.css`
- Modify: `tests/test_dashboard_frontend.py`

**Interfaces:**
- Consumes: `DashboardCore.buildGovernanceView(D.governance)`.
- Produces: `initGovernance()`, `renderEmptyState(element, message)`, consistent ECharts option helpers.

- [x] **Step 1: Extend the static test for governance honesty**

```python
def test_governance_copy_is_honest(self):
    html = (DASHBOARD / "index.html").read_text(encoding="utf-8")
    charts = (DASHBOARD / "charts.js").read_text(encoding="utf-8")
    self.assertIn("不是随机 A/B 实验", html)
    self.assertIn("function initGovernance", charts)
    self.assertIn("buildGovernanceView", charts)
    self.assertNotIn("mockGovernance", charts)
```

- [x] **Step 2: Run the targeted test and verify it fails**

Run: `python -m unittest tests.test_dashboard_frontend.TestDashboardFrontend.test_governance_copy_is_honest -v`

Expected: FAIL because `initGovernance` is absent.

- [x] **Step 3: Add shared ECharts helpers**

Update `PAL`, `COLORS` and `baseOpt`; add helpers for axis, tooltip, legend, linear gradients and empty state. Preserve every data field and chart function currently used. Correct invalid color literals encountered during the touched chart paths.

- [x] **Step 4: Implement `initGovernance()`**

Use only `D.governance` through `DashboardCore.buildGovernanceView`:

- unavailable: render an empty state with the generation command;
- manifest: render run ID, generated time, counts, pass rate and semantic gate badge;
- comparison: render sample sizes, matched product count, text metrics and limitations;
- absent rating comparison: state that the source lacks valid ratings rather than showing zero.

- [x] **Step 5: Enrich existing pages using current data only**

- Overview: add a data-status rail and concise headline insight derived from KPI/trend values;
- Products: replace emoji stats with styled labels and safe escaped text;
- Diagnosis: add count/percentage context to severity and root-cause cards;
- All pages: render card-local empty states when required fields are missing.

- [x] **Step 6: Run targeted tests and syntax checks**

Run: `python -m unittest tests.test_dashboard_frontend -v`

Run: `node --test tests/dashboard_core.test.js`

Run: `node --check src/dashboard/charts.js`

Expected: all commands pass.

- [x] **Step 7: Commit**

```bash
git add src/dashboard/charts.js src/dashboard/index.html src/dashboard/styles.css tests/test_dashboard_frontend.py
git commit -m "feat: add governance and executive chart experience"
```

### Task 5: Browser QA, Documentation, Regression and GitHub Delivery

**Files:**
- Modify: `README.md`
- Modify: `docs/project_optimization_log.md`
- Modify: `docs/superpowers/plans/2026-09-17-dashboard-executive-redesign.md`

**Interfaces:**
- Consumes: completed static dashboard.
- Produces: verified browser behavior, updated project documentation and a pushed feature branch.

- [x] **Step 1: Start a local static server**

Run: `python -m http.server 8899 --directory src/dashboard`

Expected: `http://127.0.0.1:8899/` returns the dashboard assets.

- [x] **Step 2: Perform desktop browser QA**

At 1440×900 verify:

- loading overlay disappears;
- eight nav items switch pages and update the hash;
- topbar title, date range and update time are populated;
- overview charts render without horizontal overflow;
- products, filters, timeline slider and product modal respond;
- governance unavailable state is explicit with current generated data.

Capture a screenshot under ignored `tmp/dashboard-qa/desktop.png`.

- [x] **Step 3: Perform mobile browser QA**

At 390×844 verify:

- menu button opens and closes the drawer;
- backdrop and Escape close it;
- KPI uses two columns and chart cards use one column;
- modal is usable without clipped close button;
- no page causes document-level horizontal scrolling.

Capture a screenshot under ignored `tmp/dashboard-qa/mobile.png`.

- [x] **Step 4: Update documentation with implemented facts**

README must list the eight pages, local launch command, hash navigation and governance behavior. Optimization log must record the commits, automated tests and browser sizes; do not claim the online deployment has updated until the main branch deployment is observed.

- [x] **Step 5: Run the complete verification suite**

Run: `python -m unittest discover tests -v`

Run: `node --test tests/dashboard_core.test.js`

Run: `node --check src/dashboard/dashboard_core.js && node --check src/dashboard/app.js && node --check src/dashboard/charts.js`

Run with Python 3.12: `python -m unittest tests.test_spark_pipeline -v`

Run: `git diff --check`

Expected: all tests and syntax checks pass; the default suite may skip the three Spark worker tests on Python 3.14, which must pass in the separate Python 3.12 command.

- [x] **Step 6: Check commit scope and secrets**

Run: `git status --short`

Run: `git grep -n -I -E "(sk-[A-Za-z0-9_-]{20,}|AKIA[0-9A-Z]{16}|-----BEGIN (RSA|OPENSSH|EC) PRIVATE KEY-----)"`

Expected: only intended tracked frontend/docs changes; secret scan may match documented placeholder `sk-your-deepseek-api-key` and no real credential.

- [x] **Step 7: Commit and push**

```bash
git add README.md docs/project_optimization_log.md docs/superpowers/plans/2026-09-17-dashboard-executive-redesign.md
git commit -m "docs: document executive dashboard experience"
git push -u origin codex/dashboard-executive-redesign
```

Report the branch URL and test evidence. Merge to `main` only after user approval or an explicit instruction that already authorizes merging after successful verification.

## Plan Self-Review

- Spec coverage: visual tokens, semantic shell, eight pages, governance, hash routing, mobile drawer, accessibility, reduced motion, error states, browser QA and deployment constraints all map to Tasks 1–5.
- Placeholder scan: no deferred implementation markers or ambiguous “handle errors” steps remain.
- Type consistency: `DashboardCore` exposes the same three function names consumed by `app.js`, `charts.js` and Node tests; route names match page and navigation IDs.
- Scope: the plan changes only the static dashboard and supporting documentation; backend metric definitions remain untouched.
