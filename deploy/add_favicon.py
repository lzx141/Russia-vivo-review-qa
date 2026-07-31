#!/usr/bin/env python3
"""Nginx favicon 快速响应优化 — 避免浏览器等待 favicon.ico 404"""
conf = "/www/server/panel/vhost/nginx/116.62.152.97.conf"

with open(conf, "r", encoding="utf-8") as f:
    c = f.read()

fav = """
    # favicon 快速响应，避免 404 等待
    location = /favicon.ico {
        empty_gif;
        access_log off;
        expires 30d;
    }
"""
marker = "# STATIC-CACHE-END"
if marker in c and "location = /favicon.ico" not in c:
    c = c.replace(marker, marker + fav, 1)
    with open(conf, "w", encoding="utf-8") as f:
        f.write(c)
    print("favicon handler added")
else:
    print("already exists or marker not found")
