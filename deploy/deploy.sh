#!/bin/bash
# ==============================================================
# GitHub Webhook 自动部署脚本
#
# 被 deploy/webhook_server.py 调用，用于自动拉取最新代码
# 并刷新仪表盘数据。
#
# 用法: bash deploy/deploy.sh
# ==============================================================

set -e  # 任何失败即退出

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_DIR"

echo "========================================"
echo "🔄 自动部署开始: $(date '+%Y-%m-%d %H:%M:%S')"
echo "   目录: $PROJECT_DIR"
echo "========================================"

# ── Step 1: 拉取最新代码 ─────────────────────────────
echo ""
echo "📥 [1/4] 拉取最新代码..."

# 暂存本地修改（如果有）
git stash push -m "webhook-auto-stash-$(date +%s)" 2>/dev/null || true

# 拉取
git pull origin main 2>&1 || {
    echo "❌ git pull 失败！尝试强制拉取..."
    git fetch origin
    git reset --hard origin/main
}

echo "✅ 代码已更新到最新"
echo "   最新提交: $(git log -1 --oneline)"

# ── Step 2: 安装/更新依赖 ────────────────────────────
echo ""
echo "📦 [2/4] 更新依赖..."
if [ -f "requirements.txt" ]; then
    pip install -r requirements.txt -q 2>&1 | tail -1 || echo "   依赖更新完成（或有警告）"
fi

# ── Step 3: 刷新仪表盘数据 ──────────────────────────
echo ""
echo "📊 [3/4] 刷新仪表盘数据..."

# 优先使用数据库，如果没有数据库则使用 CSV
if python -c "from config.config import DB_CONFIG; assert DB_CONFIG['password']" 2>/dev/null; then
    echo "   数据库已配置，从数据库生成..."
    python src/dashboard/generate_stats.py 2>&1
else
    echo "   数据库未配置，使用 CSV 数据..."
    python src/dashboard/generate_stats.py 2>&1 || echo "   ⚠️ 生成失败，使用已有数据"
fi

# ── Step 4: 重启前端服务 ────────────────────────────
echo ""
echo "🔄 [4/4] 检查 HTTP 服务..."

# 检测当前使用的服务方式
if command -v pm2 &> /dev/null && pm2 list 2>/dev/null | grep -q "dashboard"; then
    echo "   检测到 PM2 管理，重启服务..."
    pm2 restart dashboard
elif pgrep -f "http.server.*8899" > /dev/null 2>&1; then
    echo "   检测到 Python http.server (8899)，无需重启（静态文件已更新）"
else
    echo "   未检测到运行中的服务，如需启动请执行:"
    echo "   cd src/dashboard && python -m http.server 8899 &"
fi

# ── 完成 ──────────────────────────────────────────────
echo ""
echo "========================================"
echo "✅ 部署完成: $(date '+%Y-%m-%d %H:%M:%S')"
echo "========================================"
