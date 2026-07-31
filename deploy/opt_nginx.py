#!/usr/bin/env python3
"""Nginx 性能优化脚本 — 静态资源长缓存 + gzip 强化

在服务器上运行：
  python3 /www/wwwroot/116.62.152.97/deploy/opt_nginx.py
"""
import re

CONF = "/www/server/panel/vhost/nginx/116.62.152.97.conf"

with open(CONF, "r", encoding="utf-8") as f:
    content = f.read()

cache_block = """
    # STATIC-CACHE-BEGIN 静态资源长缓存（30天）
    location ~*\\.(js|css)$ {
        expires 30d;
        add_header Cache-Control "public, max-age=2592000, immutable";
        access_log off;
    }
    location ~*\\.(png|jpg|jpeg|gif|svg|ico|woff|woff2|ttf|otf)$ {
        expires 30d;
        add_header Cache-Control "public, max-age=2592000, immutable";
        access_log off;
    }
    # STATIC-CACHE-END
"""

# 移除旧的 STATIC-CACHE 块
content = re.sub(r"\n\s*# STATIC-CACHE-BEGIN.*?# STATIC-CACHE-END\n", "\n", content, flags=re.DOTALL)

marker = "server_name 116.62.152.97;"
if marker in content and "STATIC-CACHE-BEGIN" not in content:
    content = content.replace(marker, marker + cache_block, 1)
    with open(CONF, "w", encoding="utf-8") as f:
        f.write(content)
    print("✅ 静态缓存块已添加")
else:
    print("⚠️ 标记未找到或已存在")

# 主配置 gzip 优化
MAIN_CONF = "/www/server/nginx/conf/nginx.conf"
with open(MAIN_CONF, "r", encoding="utf-8") as f:
    main_content = f.read()

# gzip 压缩级别提升到 6（5→6 压缩率更高，CPU 开销略增）
if "gzip_comp_level  5;" in main_content:
    main_content = main_content.replace("gzip_comp_level  5;", "gzip_comp_level  6;")
    with open(MAIN_CONF, "w", encoding="utf-8") as f:
        f.write(main_content)
    print("✅ gzip 压缩级别提升到 6")
elif "gzip_comp_level 5;" in main_content:
    main_content = main_content.replace("gzip_comp_level 5;", "gzip_comp_level 6;")
    with open(MAIN_CONF, "w", encoding="utf-8") as f:
        f.write(main_content)
    print("✅ gzip 压缩级别提升到 6")
else:
    print("ℹ️ gzip 级别配置未找到（可能已是最优）")
