#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
财新网「世界」频道 → 手机推送 + 网页日报（一体化脚本，无需任何第三方库）

做三件事：
  1. 抓取财新网「世界」频道过去 24 小时的文章；
  2. 生成手机友好的网页日报 _site/index.html；
  3. 发送 Bark 通知，通知里附带网页地址（点开通知即可看日报）。

手机推送地址有两种填法，任选一种：
  方法A（简单）：把地址填到下面 MY_BARK_URL 的引号里。
  方法B：留空，改由 GitHub 的 Secret（名字固定为 BARK_URL）提供。
"""

# ===== 需要改的地方只有这两行 =====
MY_BARK_URL = ""          # 例："https://api.day.app/你的编号"
MY_PAGE_URL = "https://eristyle.github.io/caixin-daily/"   # 网页日报地址；确认不对就改这里
# =================================

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


def fresh_items(items, hours=24, now=None):
    now = now or datetime.now()
    cutoff = now - timedelta(hours=hours)
    return [i for i in items if i["dt"] >= cutoff], now


def build_message(items, now):
    lines = [f"**财新 · 世界频道**（{now:%m-%d %H:%M}，{len(items)} 条）", ""]
    if not items:
        lines.append("过去 24 小时该频道暂无新文章。")
    for idx, it in enumerate(items, 1):
        lines.append(f"{idx}. {it['title']}　[{it['flag']}]")
        lines.append(f"{it['dt']:%m-%d %H:%M}")
        if it["summary"]:
            lines.append(it["summary"])
        lines.append(it["link"])
        lines.append("")
    lines.append("点这条通知可打开网页版日报。")
    return "\n".join(lines)


def build_html(items, now):
    rows = []
    for it in items:
        rows.append(f"""
    <article>
      <h3><a href="{html.escape(it['link'])}" target="_blank" rel="noopener">{html.escape(it['title'])}</a></h3>
      <div class="meta"><span class="tag">{it['flag']}</span> {it['dt']:%Y-%m-%d %H:%M}</div>
      <p>{html.escape(it['summary'])}</p>
    </article>""")
    body = "".join(rows) or '<p class="empty">过去 24 小时该频道暂无新文章。</p>'
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>财新 · 世界频道日报 {now:%Y-%m-%d}</title>
<style>
  :root {{ color-scheme: light dark; }}
  * {{ box-sizing: border-box; }}
  body {{ margin: 0; padding: 18px 16px 48px; background: #f6f7f9; color: #1b1d21;
         font: 16px/1.65 -apple-system, "PingFang SC", "Microsoft YaHei", sans-serif; }}
  header {{ max-width: 720px; margin: 0 auto 18px; }}
  h1 {{ font-size: 21px; margin: 0 0 6px; }}
  .sub {{ color: #6b7280; font-size: 13px; }}
  main {{ max-width: 720px; margin: 0 auto; }}
  article {{ background: #fff; border-radius: 12px; padding: 16px 16px 4px;
             margin-bottom: 12px; box-shadow: 0 1px 3px rgba(0,0,0,.06); }}
  h3 {{ font-size: 17px; margin: 0 0 8px; line-height: 1.45; }}
  h3 a {{ color: #1b1d21; text-decoration: none; }}
  h3 a:active {{ color: #b91c1c; }}
  .meta {{ font-size: 12px; color: #6b7280; margin-bottom: 8px; }}
  .tag {{ display: inline-block; background: #eef2ff; color: #3b4cca;
          border-radius: 5px; padding: 1px 6px; margin-right: 6px; font-size: 11px; }}
  p {{ margin: 0 0 14px; color: #3f4550; font-size: 14px; }}
  .empty {{ text-align: center; color: #9ca3af; padding: 40px 0; }}
  footer {{ max-width: 720px; margin: 24px auto 0; text-align: center;
            color: #9ca3af; font-size: 12px; }}
  footer a {{ color: #6b7280; }}
  @media (prefers-color-scheme: dark) {{
    body {{ background: #131417; color: #e8eaed; }}
    article {{ background: #1c1e22; box-shadow: none; }}
    h3 a {{ color: #e8eaed; }}
    p {{ color: #b6bac2; }}
    .tag {{ background: #2a2f45; color: #a9b6ff; }}
  }}
</style>
</head>
<body>
<header>
  <h1>财新 · 世界频道日报</h1>
  <div class="sub">更新于 {now:%Y-%m-%d %H:%M}　·　共 {len(items)} 条</div>
</header>
<main>{body}
</main>
<footer>数据来源 <a href="{CHANNEL_URL}" target="_blank" rel="noopener">财新网 · 世界频道</a></footer>
</body>
</html>
"""


def push_bark(text, title="财新 · 世界频道早报", page_url=""):
    url = (MY_BARK_URL.strip() or os.environ.get("BARK_URL") or "").strip().rstrip("/")
    if not url:
        print("没有配置推送地址，本次只打印内容、不推送。", file=sys.stderr)
        return False
    body = text if len(text) <= 3000 else text[:3000] + "\n…（已截断）"
    payload = {"title": title, "body": body, "group": "财新早报", "sound": "bell"}
    if page_url:                       # 点通知即可打开网页日报
        payload["url"] = page_url
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json; charset=utf-8"}, method="POST")
    with urllib.request.urlopen(req, timeout=20) as resp:
        print(f"推送结果：HTTP {resp.status} {resp.read().decode('utf-8', 'ignore')[:200]}")
    return True


def main():
    try:
        all_items = parse(fetch())
    except Exception as e:
        print(f"抓取失败：{e}", file=sys.stderr)
        return 1
    if not all_items:
        print("解析到 0 条，页面结构可能已变更。", file=sys.stderr)
        return 2

    items, now = fresh_items(all_items)

    # 1) 生成网页日报
    page_dir = "_site"
    os.makedirs(page_dir, exist_ok=True)
    with open(os.path.join(page_dir, "index.html"), "w", encoding="utf-8") as f:
        f.write(build_html(items, now))
    with open("index.html", "w", encoding="utf-8") as f:   # 本地也留一份，方便直接打开看
        f.write(build_html(items, now))
    print(f"已生成网页日报：{page_dir}/index.html（{len(items)} 条）")

    # 2) 发送通知
    msg = build_message(items, now)
    print("\n" + msg)
    page_url = (MY_PAGE_URL.strip() or os.environ.get("PAGE_URL") or "").strip()
    try:
        push_bark(msg, page_url=page_url)
    except Exception as e:
        print(f"推送失败：{e}", file=sys.stderr)
        return 3
    return 0


if __name__ == "__main__":
    sys.exit(main())
