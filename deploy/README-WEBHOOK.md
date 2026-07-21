# GitHub Webhook 自动部署配置指南

## 整体架构

```
你 push 代码到 GitHub
       │
       ▼
GitHub 发送 POST → http://你的服务器:9000/webhook
       │
       ▼
webhook_server.py（Python 内置 HTTP 服务）
   ├── 验证 HMAC 签名
   ├── ✅ 签名通过 → 后台执行 deploy/deploy.sh
   ├── ❌ 签名失败 → 返回 401
       │
       ▼
deploy/deploy.sh
   ├── git pull origin main
   ├── pip install -r requirements.txt
   ├── python src/dashboard/generate_stats.py
   └── 重启服务（如有必要）
```

---

## 快速部署（5 分钟）

### 1️⃣ 服务器上配置 Webhook Secret

```bash
# 进入项目目录
cd /path/to/Russia-vivo-review-qa

# 编辑 .env，添加 webhook secret
echo 'GITHUB_WEBHOOK_SECRET=你的随机密钥' >> .env

# 给部署脚本执行权限
chmod +x deploy/deploy.sh
```

> 🔑 生成随机密钥：`openssl rand -hex 20`

### 2️⃣ 启动 Webhook 服务

```bash
# 前台运行（测试用）
python deploy/webhook_server.py --port 9000

# 后台运行（生产用）
nohup python deploy/webhook_server.py --port 9000 > logs/webhook_stdout.log 2>&1 &

# 查看日志
tail -f logs/webhook.log
```

### 3️⃣ 配置 Nginx 反向代理（可选但推荐）

将 `deploy/nginx_webhook.conf` 的内容合并到你现有的 Nginx 配置中：

```nginx
location /webhook {
    proxy_pass http://127.0.0.1:9000;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    # ... 其他 proxy 配置
}
```

```bash
# 检查配置并重载
nginx -t && nginx -s reload
```

### 4️⃣ GitHub 仓库设置 Webhook

1. 打开你的 GitHub 仓库 → **Settings** → **Webhooks** → **Add webhook**
2. 填写：

   | 字段 | 值 |
   |------|-----|
   | **Payload URL** | `http://你的服务器IP:9000/webhook`（或通过 Nginx 代理后的 URL） |
   | **Content type** | `application/json` |
   | **Secret** | 第 1 步设置的 `GITHUB_WEBHOOK_SECRET` |
   | **SSL verification** | Enable（如果 HTTPS）或 Disable（仅 HTTP 时） |
   | **Which events** | **Just the push event** |

3. 点击 **Add webhook**
4. 首次配置成功会立即收到一个 Ping ✓

---

## 使用 systemd 管理（生产环境推荐）

```bash
# 编辑 service 文件，修改其中的路径
# vim deploy/webhook.service
# 将 /path/to/Russia-vivo-review-qa 替换为实际路径

sudo cp deploy/webhook.service /etc/systemd/system/webhook.service

# 重新加载并启动
sudo systemctl daemon-reload
sudo systemctl enable webhook
sudo systemctl start webhook

# 查看状态
sudo systemctl status webhook

# 查看日志
sudo journalctl -u webhook -f
```

---

## 使用 PM2 管理（Node.js 用户可选）

```bash
# 安装 pm2
npm install -g pm2

# 启动 webhook 服务
pm2 start deploy/webhook_server.py --name "webhook" --interpreter python3 -- --port 9000

# 保存配置
pm2 save
pm2 startup
```

---

## 验证是否生效

```bash
# 1. 健康检查
curl http://127.0.0.1:9000/health
# 返回: {"status": "ok", "service": "github-webhook", ...}

# 2. 测试 webhook（模拟 GitHub 请求）
python deploy/test_webhook.py --secret 你的密钥

# 3. 查看部署历史
curl http://127.0.0.1:9000/history

# 4. 查看日志
tail -f logs/webhook.log
```

---

## 通知配置（可选）

支持配置飞书/钉钉机器人，部署完成时自动通知。

```bash
# .env 中添加机器人 Webhook 地址
# 飞书机器人
WEBHOOK_NOTIFY_URL=https://open.feishu.cn/open-apis/bot/v2/hook/xxxxx

# 或钉钉机器人
WEBHOOK_NOTIFY_URL=https://oapi.dingtalk.com/robot/send?access_token=xxxxx
```

---

## 安全建议

1. ✅ **务必设置 Secret** — 未设置时签名验证跳过，任何人向 `/webhook` POST 都可能触发部署
2. ✅ **Nginx 反向代理 + HTTPS** — 防止请求明文传输
3. ✅ **绑定 127.0.0.1** — webhook 服务默认只监听本地，通过 Nginx 对外暴露
4. ✅ **限制 `/webhook` 的 IP** — 可在 Nginx 层仅允许 GitHub IP 范围：
   ```nginx
   location /webhook {
       allow 192.30.252.0/22;
       allow 140.82.112.0/20;
       deny all;
       proxy_pass http://127.0.0.1:9000;
   }
   ```

---

## 故障排查

| 问题 | 原因 | 解决 |
|------|------|------|
| GitHub 显示 500 错误 | Webhook 服务未启动 | `systemctl start webhook` |
| GitHub 显示 401 错误 | Secret 不匹配 | 检查 .env 和 GitHub 设置是否一致 |
| GitHub 显示 200 但代码未更新 | deploy.sh 无执行权限 | `chmod +x deploy/deploy.sh` |
| 部署后仪表盘仍是旧数据 | generate_stats.py 失败 | 手动运行 `python src/dashboard/generate_stats.py` 查看报错 |
