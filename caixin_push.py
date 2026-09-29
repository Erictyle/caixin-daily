#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
财新网「世界」频道 → 手机推送（一体化脚本，无需任何第三方库）

本地测试：
    set BARK_URL=https://api.day.app/你的KEY
    python caixin_push.py

云端使用：由 GitHub Actions 每天定时调用，BARK_URL 从仓库 Secret 读取。
"""

import html
import json
import os
import re
import sys
import urllib.request
from datetime import datetime, timedelta

CHANNEL_URL = "https://international.caixin.com/"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")

BOX_RE = re.compile(
    r'<h4>\s*<a href="(?P<link>[^"]+)"[^>]*>(?P<title>.*?)</a>(?P<flag>.*?)</h4>\s*'
    r'<span>(?P<time>.*?)</span>\s*<p>(?P<summary>.*?)</p>', re.S)
TAG_RE = re.compile(r"<[^>]+>")


def clean(text):
    text = TAG_RE.sub("", text or "")
    text = html.unescape(text)
    return re.sub(r"[\s\u3000]+", " ", text).strip()


def fetch(url=CHANNEL_URL):
    req = urllib.request.Request(url, headers={
        "User-Agent": UA, "Accept-Language": "zh-CN,zh;q=0.9"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        raw = resp.read()
    for enc in ("utf-8", "gbk"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", "ignore")


def parse(page):
    start = page.find('id="listArticle"')          # 只取频道主列表，避开侧栏子栏目
    scope = page[start:] if start != -1 else page
    items, seen = [], set()
    for m in BOX_RE.finditer(scope):
        link = m.group("link").split("#")[0]
        dm = re.search(r"/(\d{4}-\d{2}-\d{2})/", link)
        if not dm:
            continue
        tm = re.search(r"(\d{1,2}):(\d{2})", clean(m.group("time")))
        try:
            dt = datetime.strptime(dm.group(1), "%Y-%m-%d")
        except ValueError:
            continue
        if tm:
            dt = dt.replace(hour=int(tm.group(1)) % 24, minute=int(tm.group(2)))
        if link in seen:
            continue
        seen.add(link)
        flag_raw = m.group("flag") or ""
        flag = "收费" if "icon_key" in flag_raw else (
            "限时免费" if "icon_time_12" in flag_raw else "免费")
        items.append({"title": clean(m.group("title")), "link": link, "dt": dt,
                      "summary": clean(m.group("summary")), "flag": flag})
    items.sort(key=lambda x: x["dt"], reverse=True)
    return items


def build_message(items, hours=24, now=None):
    now = now or datetime.now()
    cutoff = now - timedelta(hours=hours)
    fresh = [i for i in items if i["dt"] >= cutoff]
    lines = [f"**财新 · 世界频道**（{now:%m-%d %H:%M}，过去 {hours} 小时 {len(fresh)} 条）", ""]
    if not fresh:
        lines.append("过去 24 小时该频道暂无新文章。")
    for idx, it in enumerate(fresh, 1):
        lines.append(f"{idx}. {it['title']}　[{it['flag']}]")
        lines.append(f"{it['dt']:%m-%d %H:%M}")
        if it["summary"]:
            lines.append(it["summary"])
        lines.append(it["link"])
        lines.append("")
    lines.append(f"频道主页：{CHANNEL_URL}")
    return "\n".join(lines)


def push_bark(text, title="财新 · 世界频道早报"):
    url = (os.environ.get("BARK_URL") or "").strip().rstrip("/")
    if not url:
        print("没有配置 BARK_URL，本次只打印内容、不推送。", file=sys.stderr)
        return False
    body = text if len(text) <= 3000 else text[:3000] + "\n…（已截断）"
    payload = {"title": title, "body": body, "markdown": "1",
               "group": "财新早报", "sound": "bell"}
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json; charset=utf-8"}, method="POST")
    with urllib.request.urlopen(req, timeout=20) as resp:
        print(f"推送结果：HTTP {resp.status} {resp.read().decode('utf-8', 'ignore')[:200]}")
    return True


def main():
    try:
        items = parse(fetch())
    except Exception as e:
        print(f"抓取失败：{e}", file=sys.stderr)
        return 1
    if not items:
        print("解析到 0 条，页面结构可能已变更。", file=sys.stderr)
        return 2

    msg = build_message(items)
    print(msg)
    try:
        push_bark(msg)
    except Exception as e:
        print(f"推送失败：{e}", file=sys.stderr)
        return 3
    return 0


if __name__ == "__main__":
    sys.exit(main())
