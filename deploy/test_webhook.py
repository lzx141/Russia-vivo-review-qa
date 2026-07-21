#!/usr/bin/env python3
"""
GitHub Webhook 本地测试工具
============================

模拟 GitHub 发送 push 事件到 webhook 服务，用于验证配置是否正确。

用法：
  # 使用 .env 中的 secret
  python deploy/test_webhook.py

  # 指定 secret 和 URL
  python deploy/test_webhook.py --secret mysecret --url http://127.0.0.1:9000/webhook

  # 测试线上服务器
  python deploy/test_webhook.py --url http://你的服务器IP:9000/webhook --secret xxx
"""
import argparse
import hashlib
import hmac
import json
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def build_push_payload():
    """构造模拟的 push 事件 payload"""
    now = datetime.now().isoformat()
    return {
        "ref": "refs/heads/main",
        "before": "0000000000000000000000000000000000000000",
        "after": "abcdef1234567890abcdef1234567890abcdef12",
        "repository": {
            "full_name": "lzx141/Russia-vivo-review-qa",
            "name": "Russia-vivo-review-qa",
            "url": "https://github.com/lzx141/Russia-vivo-review-qa",
        },
        "pusher": {"name": "test-user", "email": "test@example.com"},
        "commits": [
            {
                "id": "abcdef1234567890abcdef1234567890abcdef12",
                "message": "test: 验证 webhook 自动部署",
                "timestamp": now,
                "url": "https://github.com/lzx141/Russia-vivo-review-qa/commit/abc",
                "author": {"name": "test-user"},
            }
        ],
        "head_commit": {
            "message": "test: 验证 webhook 自动部署",
        },
    }


def test_webhook(url: str, secret: str):
    """发送模拟的 push 事件到 webhook"""
    payload = build_push_payload()
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")

    # 计算签名
    signature = "sha256=" + hmac.new(
        secret.encode("utf-8"), body, hashlib.sha256
    ).hexdigest()

    try:
        import requests
    except ImportError:
        print("❌ 需要安装 requests 库: pip install requests")
        sys.exit(1)

    headers = {
        "Content-Type": "application/json",
        "X-GitHub-Event": "push",
        "X-Hub-Signature-256": signature,
        "X-GitHub-Delivery": "test-delivery-id",
    }

    print(f"🔗 发送请求到: {url}")
    print(f"🔐 签名: {signature[:30]}...")
    print(f"📦 事件: push (模拟 1 个提交)")
    print()

    try:
        resp = requests.post(url, data=body, headers=headers, timeout=15)
        print(f"📥 状态码: {resp.status_code}")
        print(f"📥 响应: {resp.json()}")
        print()

        if resp.status_code == 200:
            print("✅ Webhook 连接成功！")
            print("   请查看服务端日志确认部署执行:")
            print("   tail -f logs/webhook.log")
        elif resp.status_code == 401:
            print("❌ 签名验证失败！请检查 secret 是否一致:")
            print(f"   使用的 secret: {secret[:10]}...")
        else:
            print(f"⚠️  响应异常: {resp.status_code}")

    except requests.exceptions.ConnectionError:
        print("❌ 连接失败！请确认服务是否运行:")
        print(f"   python deploy/webhook_server.py --port 9000")
    except Exception as e:
        print(f"❌ 请求异常: {e}")


def get_secret():
    """尝试从命令行、环境变量、.env 读取 secret"""
    parser = argparse.ArgumentParser(description="GitHub Webhook 测试工具")
    parser.add_argument("--secret", default="", help="Webhook secret")
    parser.add_argument("--url", default="http://127.0.0.1:9000/webhook",
                        help="Webhook URL (默认 http://127.0.0.1:9000/webhook)")
    args = parser.parse_args()

    secret = args.secret

    # 从环境变量
    if not secret:
        secret = os.environ.get("GITHUB_WEBHOOK_SECRET", "")

    # 从 .env 文件
    if not secret:
        env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
        if os.path.exists(env_path):
            with open(env_path, "r") as f:
                for line in f:
                    if line.startswith("GITHUB_WEBHOOK_SECRET="):
                        secret = line.split("=", 1)[1].strip().strip("\"'")

    return args.url, secret


if __name__ == "__main__":
    url, secret = get_secret()
    if not secret:
        print("⚠️  未设置 secret！可用以下方式设置:")
        print("   1. --secret 参数")
        print("   2. 环境变量 GITHUB_WEBHOOK_SECRET")
        print("   3. .env 文件中 GITHUB_WEBHOOK_SECRET=")
        print()
        # 无 secret 时也测试连接
        print("将使用空 secret 测试...")
        secret = ""

    test_webhook(url, secret)
