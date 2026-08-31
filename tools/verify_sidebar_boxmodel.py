#!/usr/bin/env python3
"""测量带侧栏页面的导航项盒模型，验证 box-sizing 复位是否生效。

2026-08-26 修过一次：`.app-nav__item` 的 height:38px + padding:9px 在 content-box
下会算成 56px，把侧栏撑到 636px。修法是 app.css 自带 `*{box-sizing:border-box}`。
本脚本用真实 Chromium 渲染本地文件，量 itemH / span / sidebar 宽度。

API 全部用 route fulfill 打桩，不碰任何服务器。
"""

from __future__ import annotations

import argparse
import contextlib
import functools
import http.server
import json
import socketserver
import sys
import threading
from pathlib import Path

from playwright.sync_api import sync_playwright

PAGES = ["explore.html", "farm.html", "histories.html", "me.html",
         "workshop.html", "favorites.html"]

STUB = {
    "result": "success", "code": "200", "status": 200,
    "data": {"list": [], "items": [], "total": 0, "points": 0, "balance": 0},
    "items": [], "list": [], "total": 0,
}

MEASURE = """
() => {
  const items = [...document.querySelectorAll('.app-nav__item')];
  if (!items.length) return { items: 0 };
  const visible = items.filter(el => el.getBoundingClientRect().height > 0);
  const rects = items.map(el => el.getBoundingClientRect());
  const sidebar = document.querySelector('.app-nav, .app-sidebar, aside');
  const sidebarBox = sidebar ? sidebar.getBoundingClientRect() : null;
  return {
    items: items.length,
    visibleItems: visible.length,
    sidebarVisible: Boolean(sidebarBox && sidebarBox.width > 0 && sidebarBox.height > 0),
    itemH: Math.round(rects[0].height * 10) / 10,
    heights: [...new Set(rects.map(r => Math.round(r.height)))],
    span: Math.round(rects.at(-1).bottom - rects[0].top),
    sidebarW: sidebarBox ? Math.round(sidebarBox.width) : null,
    boxSizing: getComputedStyle(items[0]).boxSizing,
    bottomNav: Boolean(document.querySelector('.app-bottom-nav, .app-tabbar, nav[class*=bottom]')),
  };
}
"""


@contextlib.contextmanager
def serve(root: Path):
    """本地静态服务器。页面用根相对 URL 引 /app/assets/js/layout.js，
    file:// 解析不了，所以必须走 http。"""
    handler = functools.partial(http.server.SimpleHTTPRequestHandler,
                                directory=str(root))

    class Quiet(socketserver.ThreadingTCPServer):
        allow_reuse_address = True
        daemon_threads = True

        def handle_error(self, request, client_address):
            pass

    with Quiet(("127.0.0.1", 0), handler) as httpd:
        httpd.RequestHandlerClass.log_message = lambda *a, **k: None
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        try:
            yield f"http://127.0.0.1:{httpd.server_address[1]}"
        finally:
            httpd.shutdown()


def measure_tree(root: Path, label: str, headless: bool = True) -> dict:
    results = {}
    with serve(root) as base, sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        context = browser.new_page(viewport={"width": 1440, "height": 900})

        # 只给 API 打桩；静态资源交给本地服务器。登录态用 localStorage 伪造，
        # 否则 layout.js 会把页面重定向到 login.html，侧栏根本不渲染。
        def handler(route):
            route.fulfill(status=200, content_type="application/json",
                          body=json.dumps(STUB))

        context.route(f"{base}/console/**", handler)
        context.route(f"{base}/admin/**", handler)
        context.route(f"{base}/module/**", handler)
        context.route("**://patcher.villainy.top/**", handler)
        context.add_init_script(
            # api.js 的常量名，登录态缺一个 app-core.js 就 replace 到 login.html，
            # 侧栏根本不会渲染，量到的就全是 (no nav)。
            "try {"
            " localStorage.setItem('ai_xingyue_token', 'local.eyJ1aWQiOjF9');"
            " localStorage.setItem('ai_xingyue_logged_in', '1');"
            " localStorage.setItem('ai_xingyue_user',"
            "   JSON.stringify({id:1,email:'local@ctf.test',nickname:'local'}));"
            "} catch (_) {}"
        )

        errors: list[str] = []
        context.on("pageerror", lambda e: errors.append(str(e)[:200]))

        for page_name in PAGES:
            if not (root / "app" / page_name).exists():
                results[page_name] = {"error": "missing"}
                continue
            before = len(errors)
            context.goto(f"{base}/app/{page_name}")
            context.wait_for_timeout(1500)
            data = context.evaluate(MEASURE)
            data["pageErrors"] = len(errors) - before
            data["landedOn"] = context.url.rsplit("/", 1)[-1]
            results[page_name] = data
        browser.close()
    return {"label": label, "root": str(root), "pages": results}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tree", action="append", required=True,
                    metavar="LABEL=PATH", help="可重复，如 zip=E:\\x\\frontend")
    ap.add_argument("--json-out", type=Path)
    args = ap.parse_args()

    reports = []
    for spec in args.tree:
        label, _, path = spec.partition("=")
        reports.append(measure_tree(Path(path), label))

    header = f"{'page':16s}" + "".join(f"{r['label']:>34s}" for r in reports)
    print(header)
    print("-" * len(header))
    for page_name in PAGES:
        row = f"{page_name:16s}"
        for report in reports:
            d = report["pages"].get(page_name, {})
            if d.get("error") or not d.get("items"):
                row += f"{'(no nav)':>34s}"
            else:
                cell = (f"n={d['items']} h={d['itemH']} span={d['span']} "
                        f"{d['boxSizing'][:7]}")
                row += f"{cell:>34s}"
        print(row)

    print("\nlegend: h=nav item height px (38 = correct, 56 = content-box bug), "
          "span=first-top..last-bottom px")

    if args.json_out:
        args.json_out.write_text(json.dumps(reports, ensure_ascii=False, indent=2),
                                 encoding="utf-8")
        print(f"wrote {args.json_out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
