#!/bin/bash
# ============================================================
# 月度数据管道脚本（服务器端，由宝塔定时任务调用）
#
# 每月 3 号 02:00 由宝塔计划任务执行。
# 流程：拉取最新代码 → 翻译数据入库 → 生成大屏数据 → 确认服务
#
# 注意：爬虫需要本地 Chrome，请在本地运行 scripts/run_crawler_monthly.py
# 本脚本只负责拉取已爬好的数据并完成数据处理与部署。
# ============================================================
set -e

PROJECT_DIR="/www/wwwroot/116.62.152.97"
VENV="$PROJECT_DIR/venv/bin"
LOG="$PROJECT_DIR/logs/monthly_pipeline_$(date +%Y%m%d).log"

mkdir -p "$PROJECT_DIR/logs"
exec > >(tee -a "$LOG") 2>&1

echo "========================================"
echo "📅 月度数据管道启动: $(date '+%Y-%m-%d %H:%M:%S')"
echo "========================================"
cd "$PROJECT_DIR"

# ── Step 1: 拉取最新代码 ────────────────────────────
echo ""
echo "📥 [1/4] 拉取最新代码..."
git stash push -m "monthly-auto-stash-$(date +%s)" 2>/dev/null || true
git fetch origin 2>&1
git reset --hard origin/main 2>&1
echo "✅ 代码已更新: $(git log -1 --oneline)"

# ── Step 2: 安装依赖 ────────────────────────────────
echo ""
echo "📦 [2/4] 更新依赖..."
"$VENV/pip" install -r requirements.txt -q 2>&1 | tail -1 || true

# ── Step 3: 翻译数据入库 ────────────────────────────
echo ""
echo "🗄️  [3/4] 翻译数据入库..."
"$VENV/python" src/etl/init_database.py --load-translated 2>&1 | tail -5

# ── Step 4: 生成大屏数据 ────────────────────────────
echo ""
echo "📊 [4/4] 生成大屏数据..."
"$VENV/python" src/dashboard/generate_stats.py 2>&1 | tail -8

# ── 确认 webhook 服务运行 ───────────────────────────
if ! pgrep -f "webhook_server.py" > /dev/null; then
    echo "⚠️  webhook 服务未运行，尝试重启..."
    nohup "$VENV/python" deploy/webhook_server.py --port 9100 --secret bt_webhook_2026_secure > logs/webhook_stdout.log 2>&1 &
    sleep 3
fi
pgrep -f "webhook_server.py" > /dev/null && echo "✅ webhook 服务运行中" || echo "❌ webhook 服务启动失败"

echo ""
echo "========================================"
echo "✅ 月度数据管道完成: $(date '+%Y-%m-%d %H:%M:%S')"
echo "========================================"
