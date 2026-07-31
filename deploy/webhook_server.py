"""
GitHub Webhook 服务端
======================

功能：
  - 接收 GitHub Push 事件
  - 验证 HMAC-SHA256 签名
  - 自动执行部署脚本（git pull → 数据刷新）
  - 飞书/钉钉机器人通知（可选）
  - 运行日志追踪

部署（使用 Python 内置 http.server，零依赖）：
  nohup python deploy/webhook_server.py --port 9000 --secret your_github_webhook_secret &

或配合 Nginx 反向代理（推荐）：
  将 webhook 路径代理到 127.0.0.1:9000

GitHub 仓库设置：
  Settings → Webhooks → Add webhook
  Payload URL: http://你的域名或IP:9000/webhook
  Content type: application/json
  Secret: 你设置的密钥
  Events: Just the push event
"""
import argparse
import hashlib
import hmac
import json
import logging
import os
import subprocess
import sys
import threading
import time
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler

# 将项目根目录加入路径
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

# ── 日志配置 ──────────────────────────────────────────
LOG_DIR = os.path.join(PROJECT_ROOT, "logs")
os.makedirs(LOG_DIR, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.FileHandler(os.path.join(LOG_DIR, "webhook.log"), encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger("webhook")

# ── 部署脚本路径 ──────────────────────────────────────
DEPLOY_SCRIPT = os.path.join(PROJECT_ROOT, "deploy", "deploy.sh")


class WebhookHandler(BaseHTTPRequestHandler):
    """GitHub Webhook HTTP 处理器"""

    # 在类初始化时从启动参数注入
    webhook_secret = ""
    deploy_script = DEPLOY_SCRIPT

    def log_message(self, format, *args):
        """用 Python logging 替代 stderr 输出"""
        logger.info("→ %s %s", self.client_address[0], format % args)

    def _send_response(self, status_code: int, body: dict):
        """发送 JSON 响应"""
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("X-Webhook-Status", "ok" if status_code == 200 else "error")
        self.end_headers()
        self.wfile.write(json.dumps(body, ensure_ascii=False).encode("utf-8"))

    def _read_body(self) -> bytes:
        """读取请求体并缓存（供签名验证和 payload 解析复用）"""
        if hasattr(self, "_request_body"):
            return self._request_body
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length)
        self._request_body = body
        return body

    def _verify_signature(self) -> bool:
        """验证 GitHub HMAC-SHA256 签名"""
        secret = self.webhook_secret
        if not secret:
            logger.warning("未设置 webhook secret，跳过签名验证")
            return True

        received_sig = self.headers.get("X-Hub-Signature-256", "")
        if not received_sig:
            logger.error("缺少 X-Hub-Signature-256 头")
            return False

        # 读取请求体（缓存复用）
        body = self._read_body()

        # 计算期望签名
        expected_sig = "sha256=" + hmac.new(
            secret.encode("utf-8"), body, hashlib.sha256
        ).hexdigest()

        # 安全比较（防时序攻击）
        if not hmac.compare_digest(received_sig, expected_sig):
            logger.error("签名验证失败 — HMAC 不匹配，请检查 GITHUB_WEBHOOK_SECRET 是否一致")
            return False

        return True

    def _parse_payload(self) -> dict:
        """解析请求体 JSON 为 dict（复用签名验证时读取的 body）"""
        body = self._read_body()
        try:
            return json.loads(body.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            logger.error("payload 解析失败: %s", e)
            return {}

    def _run_deploy_async(self, payload: dict):
        """在后台线程中执行部署"""
        thread = threading.Thread(target=self._run_deploy, args=(payload,), daemon=True)
        thread.start()

    def _run_deploy(self, payload: dict):
        """执行部署"""
        deploy_start = time.time()
        deployment_id = datetime.now().strftime("deploy_%Y%m%d_%H%M%S")

        # 从 payload 提取信息
        ref = payload.get("ref", "")
        branch = ref.replace("refs/heads/", "") if ref else "unknown"
        repo_name = payload.get("repository", {}).get("full_name", "unknown")
        pusher = payload.get("pusher", {}).get("name", "unknown")
        head_commit = (payload.get("head_commit", {}) or {}).get("message", "").split("\n")[0]
        commits = payload.get("commits", [])
        commit_count = len(commits)

        logger.info("=" * 60)
        logger.info("🚀 开始部署 [%s]", deployment_id)
        logger.info("   仓库: %s", repo_name)
        logger.info("   分支: %s", branch)
        logger.info("   推送者: %s", pusher)
        logger.info("   提交数: %d", commit_count)
        if head_commit:
            logger.info("   最新提交: %s", head_commit)
        logger.info("=" * 60)

        # 只部署 main 分支的推送
        if branch != "main":
            logger.info("⏭️  分支 %s 非 main，跳过部署", branch)
            self._save_deploy_log(deployment_id, "skipped", 0, "非 main 分支推送")
            return

        if commit_count == 0:
            logger.info("⏭️  无新提交（可能为 ping 或其他事件），跳过部署")
            self._save_deploy_log(deployment_id, "skipped", 0, "无新提交")
            return

        # 执行部署脚本
        if not os.path.exists(self.deploy_script):
            logger.error("部署脚本不存在: %s", self.deploy_script)
            self._save_deploy_log(deployment_id, "failed", 0, f"脚本不存在: {self.deploy_script}")
            return

        try:
            result = subprocess.run(
                ["bash", self.deploy_script],
                cwd=PROJECT_ROOT,
                capture_output=True,
                text=True,
                timeout=300,  # 5分钟超时
            )

            elapsed = time.time() - deploy_start
            success = result.returncode == 0

            if success:
                logger.info("✅ 部署成功 (%.1fs)", elapsed)
                logger.info("输出:\n%s", result.stdout[-2000:] if result.stdout else "(无输出)")
            else:
                logger.error("❌ 部署失败 (returncode=%d, %.1fs)", result.returncode, elapsed)
                logger.error("stderr:\n%s", result.stderr[-2000:] if result.stderr else "(无错误输出)")

            self._save_deploy_log(
                deployment_id,
                "success" if success else "failed",
                elapsed,
                result.stdout[-1000:] if success else result.stderr[-1000:],
            )

            # 通知（可选）
            if success and os.environ.get("WEBHOOK_NOTIFY_URL"):
                self._send_notification(
                    f"✅ 部署成功\n仓库: {repo_name}\n分支: {branch}\n耗时: {elapsed:.1f}s",
                )

        except subprocess.TimeoutExpired:
            logger.error("❌ 部署超时 (>300s)")
            self._save_deploy_log(deployment_id, "failed", 300, "部署超时")
        except Exception as e:
            logger.error("❌ 部署异常: %s", e)
            self._save_deploy_log(deployment_id, "failed", time.time() - deploy_start, str(e))

    def _save_deploy_log(self, deployment_id: str, status: str, duration: float, message: str):
        """保存部署日志到文件"""
        log_entry = {
            "id": deployment_id,
            "timestamp": datetime.now().isoformat(),
            "status": status,
            "duration_seconds": round(duration, 2),
            "message": message[:500],
        }
        log_file = os.path.join(LOG_DIR, "deploy_history.json")
        try:
            history = []
            if os.path.exists(log_file):
                with open(log_file, "r", encoding="utf-8") as f:
                    history = json.load(f)
            history.insert(0, log_entry)
            # 只保留最近 100 条
            history = history[:100]
            with open(log_file, "w", encoding="utf-8") as f:
                json.dump(history, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning("保存部署日志失败: %s", e)

    def _send_notification(self, text: str):
        """发送通知到飞书/钉钉机器人"""
        url = os.environ.get("WEBHOOK_NOTIFY_URL", "")
        if not url:
            return
        try:
            import requests
            # 飞书机器人格式
            payload = {"msg_type": "text", "content": {"text": text}}
            if "dingtalk" in url or "ding" in url:
                # 钉钉机器人格式
                payload = {"msgtype": "text", "text": {"content": text}}
            requests.post(url, json=payload, timeout=5)
            logger.info("通知已发送")
        except Exception as e:
            logger.warning("通知发送失败: %s", e)

    # ── HTTP 路由 ──────────────────────────────────────

    def do_GET(self):
        """健康检查"""
        if self.path == "/health":
            self._send_response(200, {
                "status": "ok",
                "service": "github-webhook",
                "timestamp": datetime.now().isoformat(),
                "project": "Russia-vivo-review-qa",
            })
        elif self.path == "/history":
            # 返回最近部署历史
            log_file = os.path.join(LOG_DIR, "deploy_history.json")
            if os.path.exists(log_file):
                with open(log_file, "r", encoding="utf-8") as f:
                    history = json.load(f)
                self._send_response(200, {"history": history[:20]})
            else:
                self._send_response(200, {"history": []})
        else:
            self._send_response(404, {"error": "not_found"})

    def do_POST(self):
        """接收 Webhook 事件"""
        if self.path != "/webhook":
            self._send_response(404, {"error": "not_found"})
            return

        # 验证签名
        if not self._verify_signature():
            self._send_response(401, {"error": "signature_verification_failed"})
            return

        # 事件类型
        event = self.headers.get("X-GitHub-Event", "unknown")
        payload = self._parse_payload()
        if not payload:
            self._send_response(400, {"error": "invalid_payload"})
            return

        logger.info("收到事件: %s", event)

        if event == "ping":
            # GitHub 初次配置 webhook 时会发 ping
            hook_id = payload.get("hook_id", "unknown")
            logger.info("🔄 Ping 事件 (hook_id=%s)", hook_id)
            self._send_response(200, {
                "status": "ok",
                "event": "ping",
                "message": "Webhook 配置成功！",
                "hook_id": hook_id,
            })
            return

        if event == "push":
            # 异步执行部署（先响应 200，后台拉取代码）
            self._run_deploy_async(payload)
            self._send_response(200, {
                "status": "accepted",
                "event": "push",
                "message": "部署请求已接收，正在后台执行",
            })
            return

        # 其他事件
        logger.info("忽略事件: %s", event)
        self._send_response(200, {"status": "ignored", "event": event})


def get_secret_from_env() -> str:
    """尝试从 .env 或环境变量读取 webhook secret"""
    # 优先从环境变量
    secret = os.environ.get("GITHUB_WEBHOOK_SECRET", "")
    if secret:
        return secret

    # 尝试从 .env 文件读取
    env_path = os.path.join(PROJECT_ROOT, ".env")
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line.startswith("GITHUB_WEBHOOK_SECRET="):
                    secret = line.split("=", 1)[1].strip().strip("\"'")
                    return secret
    return ""


def main():
    parser = argparse.ArgumentParser(description="GitHub Webhook 服务端")
    parser.add_argument("--port", type=int, default=9000, help="监听端口 (默认 9000)")
    parser.add_argument("--host", default="127.0.0.1", help="监听地址 (默认 127.0.0.1)")
    parser.add_argument("--secret", default="", help="GitHub Webhook Secret（优先于 .env）")
    args = parser.parse_args()

    # 获取 secret
    secret = args.secret or get_secret_from_env()
    if secret:
        logger.info("🔐 Webhook secret 已配置，签名验证已开启")
    else:
        logger.warning("⚠️  未配置 webhook secret！建议在 .env 中设置 GITHUB_WEBHOOK_SECRET")

    # 注入到 handler 类
    WebhookHandler.webhook_secret = secret

    # 启动服务
    server = HTTPServer((args.host, args.port), WebhookHandler)
    logger.info("=" * 50)
    logger.info("🌐 GitHub Webhook 服务启动")
    logger.info("   地址: http://%s:%d", args.host, args.port)
    logger.info("   端点: POST /webhook  (GitHub 推送事件)")
    logger.info("        GET  /health  (健康检查)")
    logger.info("        GET  /history (部署历史)")
    logger.info("   日志: %s", os.path.join(LOG_DIR, "webhook.log"))
    logger.info("=" * 50)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("服务停止")
        server.server_close()


if __name__ == "__main__":
    main()
