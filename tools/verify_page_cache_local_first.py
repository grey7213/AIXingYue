#!/usr/bin/env python3
"""验证探索/我的两页的本地优先恢复，以及 iframe 内导航交给顶层容器。

针对 2026-09-01 r2 更新包引入的三件事做真实浏览器断言：

1. `page-cache.js` 按账号隔离地缓存探索列表和我的页余额/人设；
2. 二次进入时先渲染缓存再后台刷新 —— 断言方式是**第二次加载直接掐断对应 API**，
   如果页面仍有内容，说明它确实来自本地缓存而不是这次请求；
3. `layout.js` 的 `installEmbeddedTopNavigation`：/app/ 页被嵌在 iframe 里时，
   站内链接不在 iframe 内跳转，而是 postMessage 给顶层容器。这条是「完整账户
   黑屏」的修法本体 —— 主站发 `frame-ancestors 'none'`，在 iframe 里加载
   /dashboard.html 会被浏览器直接拒掉。

只跑本机离线栈（127.0.0.1:8080），不碰生产。
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from urllib.parse import urlparse

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
BASE_URL = "http://127.0.0.1:8080"
CREDENTIALS = ROOT / "output" / "offline-dev" / "runtime" / "credentials.json"
ARTIFACTS = ROOT / "output" / "playwright" / "page-cache-local-first-20260901"

EXPLORE_API = "**/go/api/explore/search*"
ME_APIS = ("**/console/api/web/credits*", "**/console/api/web/persona*")
# 离线栈只有 1 张种子卡，featuredPool 为空时它会走 featuredCards() 渲染成
# .feature-card，recommendedCards() 反而把它过滤掉 —— 所以两个类都得算。
CARD_SELECTOR = ".feature-card, .char-card"


def same_origin(url: str) -> bool:
    target, base = urlparse(url), urlparse(BASE_URL)
    return target.scheme == base.scheme and target.netloc == base.netloc


class Watch:
    """收集一个 page 上的错误，语义与 verify_chat_loading_alignment.py 一致。

    `expected_failures` 里的子串用于把「我自己掐断的那个请求」产生的
    `Failed to load resource: net::ERR_FAILED` 摘出去 —— 它是断言的手段本身，
    不是被测代码的缺陷。按失败资源的 URL 精确匹配，不放宽其余任何错误。
    """

    def __init__(self, page, expected_failures: tuple[str, ...] = ()):
        self.console: list[str] = []
        self.expected_console: list[str] = []
        self.page_errors: list[str] = []
        self.network: list[str] = []
        self._expected = expected_failures
        page.on("console", self._on_console)
        page.on("pageerror", lambda e: self.page_errors.append(str(e)))
        page.on(
            "response",
            lambda r: self.network.append(f"{r.status} {r.url}")
            if same_origin(r.url) and r.status >= 400
            else None,
        )

    def _on_console(self, message) -> None:
        if message.type != "error":
            return
        source = str((message.location or {}).get("url") or "")
        entry = f"{message.text} @ {source}" if source else message.text
        if any(token in source for token in self._expected):
            self.expected_console.append(entry)
            return
        self.console.append(entry)

    def clean(self) -> bool:
        return not (self.console or self.page_errors or self.network)

    def as_dict(self) -> dict:
        return {
            "console_errors": self.console,
            "expected_console_errors": self.expected_console,
            "page_errors": self.page_errors,
            "network_errors": self.network,
        }


def login(context, credentials: dict) -> None:
    response = context.request.post(
        BASE_URL + "/console/api/login",
        data={"email": credentials["email"], "password": credentials["password"]},
    )
    if response.status != 200:
        raise AssertionError(f"login failed: {response.status}")
    # 页面侧靠 localStorage 的非敏感登录标记决定是否 requireAuth 跳转，
    # 敏感 token 走 HttpOnly Cookie，这里补上标记即可。
    context.add_init_script("localStorage.setItem('ai_xingyue_logged_in', '1')")


def measure_explore(context, name: str) -> dict:
    """第一次正常加载写缓存，第二次掐断搜索 API 只看缓存渲染。"""
    page = context.new_page()
    watch = Watch(page)
    page.goto(BASE_URL + "/app/explore.html", wait_until="commit", timeout=30_000)
    page.wait_for_selector(CARD_SELECTOR, timeout=20_000)
    warm_cards = page.locator(CARD_SELECTOR).count()
    page.wait_for_function(
        "() => Object.keys(localStorage).some(k => k.startsWith('homer.page-cache.v1.explore.'))",
        timeout=10_000,
    )
    cache_entry = page.evaluate(
        """() => {
          const key = Object.keys(localStorage).find(k => k.startsWith('homer.page-cache.v1.explore.'));
          const envelope = JSON.parse(localStorage.getItem(key));
          return { key, savedAt: envelope.savedAt, cards: envelope.value.cards.length };
        }"""
    )
    page.close()

    offline = context.new_page()
    offline_watch = Watch(offline, expected_failures=("/go/api/explore/search",))
    offline.route(EXPLORE_API, lambda route: route.abort())
    started = time.perf_counter()
    offline.goto(BASE_URL + "/app/explore.html", wait_until="commit", timeout=30_000)
    offline.wait_for_selector(CARD_SELECTOR, timeout=15_000)
    restore_ms = round((time.perf_counter() - started) * 1000)
    cached_cards = offline.locator(CARD_SELECTOR).count()
    overflow = offline.evaluate(
        "document.documentElement.scrollWidth > document.documentElement.clientWidth + 1"
    )
    offline.screenshot(path=str(ARTIFACTS / f"{name}-explore-cached.png"), full_page=False)
    offline.close()

    if not cached_cards:
        raise AssertionError("explore rendered nothing from cache with the search API cut")
    return {
        "warm_cards": warm_cards,
        "cache_entry": cache_entry,
        "cached_cards": cached_cards,
        "restore_ms": restore_ms,
        "horizontal_overflow": overflow,
        "warm": watch.as_dict(),
        "cached": offline_watch.as_dict(),
        "clean": watch.clean() and offline_watch.clean(),
    }


def measure_me(context, name: str) -> dict:
    """我的页：第一次拿真实余额/人设，第二次掐断两个 API 看是否仍有数值。"""
    page = context.new_page()
    watch = Watch(page)
    page.goto(BASE_URL + "/app/me.html", wait_until="commit", timeout=30_000)
    page.wait_for_function(
        "() => Object.keys(localStorage).some(k => k.startsWith('homer.page-cache.v1.me.'))",
        timeout=20_000,
    )
    warm_points = page.locator(".profile-wallet-breakdown").inner_text()
    cache_entry = page.evaluate(
        """() => {
          const key = Object.keys(localStorage).find(k => k.startsWith('homer.page-cache.v1.me.'));
          const envelope = JSON.parse(localStorage.getItem(key));
          return { key, savedAt: envelope.savedAt, fields: Object.keys(envelope.value).sort() };
        }"""
    )
    page.close()

    offline = context.new_page()
    offline_watch = Watch(
        offline,
        expected_failures=("/console/api/web/credits", "/console/api/web/persona"),
    )
    for pattern in ME_APIS:
        offline.route(pattern, lambda route: route.abort())
    started = time.perf_counter()
    offline.goto(BASE_URL + "/app/me.html", wait_until="commit", timeout=30_000)
    offline.wait_for_selector(".profile-wallet-breakdown", timeout=15_000)
    restore_ms = round((time.perf_counter() - started) * 1000)
    cached_points = offline.locator(".profile-wallet-breakdown").inner_text()
    overflow = offline.evaluate(
        "document.documentElement.scrollWidth > document.documentElement.clientWidth + 1"
    )
    offline.screenshot(path=str(ARTIFACTS / f"{name}-me-cached.png"), full_page=False)
    offline.close()

    if warm_points.strip() != cached_points.strip():
        raise AssertionError(f"me page cache mismatch: warm={warm_points!r} cached={cached_points!r}")
    return {
        "warm_points": warm_points.strip(),
        "cached_points": cached_points.strip(),
        "cache_entry": cache_entry,
        "restore_ms": restore_ms,
        "horizontal_overflow": overflow,
        "warm": watch.as_dict(),
        "cached": offline_watch.as_dict(),
        "clean": watch.clean() and offline_watch.clean(),
    }


# 顶层容器探针。用 route fulfill 挂在同源路径上，这样 iframe 与它同源，
# postMessage 的 targetOrigin 校验才和 Android 容器里的真实情况一致。
PROBE_PATH = "/__homer_top_nav_probe.html"
PROBE_HTML = """<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8"><title>top nav probe</title></head>
<body style="margin:0">
<iframe id="embedded" src="/app/me.html" style="width:100%;height:100vh;border:0"></iframe>
<script>
  window.__navigateMessages = [];
  window.addEventListener('message', event => {
    if (event.origin !== location.origin) return;
    const data = event.data;
    if (data && data.channel === 'homer:dialogue-host:v1' && data.type === 'navigate') {
      window.__navigateMessages.push(String(data.target || ''));
    }
  });
</script>
</body></html>
"""


def measure_top_navigation(context, name: str) -> dict:
    """iframe 内点「完整账户」应当变成给顶层容器发 navigate，而不是自己跳。"""
    page = context.new_page()
    watch = Watch(page)
    page.route(
        f"**{PROBE_PATH}",
        lambda route: route.fulfill(status=200, content_type="text/html; charset=utf-8", body=PROBE_HTML),
    )
    page.goto(BASE_URL + PROBE_PATH, wait_until="commit", timeout=30_000)
    frame = page.frame_locator("#embedded")
    # 「完整账户」在折叠的 <details class="profile-settings"> 里，不展开点不到。
    settings = frame.locator("#profile-settings")
    settings.wait_for(timeout=20_000)
    settings.evaluate("node => node.open = true")
    full_account = frame.locator('a[href="/dashboard.html"]')
    full_account.wait_for(timeout=20_000)
    embedded_before = page.evaluate("document.querySelector('#embedded').contentWindow.location.pathname")
    full_account.click()
    page.wait_for_function("window.__navigateMessages.length > 0", timeout=10_000)
    messages = page.evaluate("window.__navigateMessages")
    # iframe 自己不许换页：换了就说明 preventDefault 没生效，真实环境下会撞
    # frame-ancestors 被拒 → 黑屏。
    page.wait_for_timeout(400)
    embedded_after = page.evaluate("document.querySelector('#embedded').contentWindow.location.pathname")
    page.screenshot(path=str(ARTIFACTS / f"{name}-top-nav.png"), full_page=False)
    page.close()

    if messages != ["/dashboard.html"]:
        raise AssertionError(f"unexpected navigate messages: {messages}")
    if embedded_after != embedded_before:
        raise AssertionError(f"iframe navigated itself: {embedded_before} -> {embedded_after}")
    return {
        "navigate_messages": messages,
        "embedded_path_before": embedded_before,
        "embedded_path_after": embedded_after,
        "probe": watch.as_dict(),
        "clean": watch.clean(),
    }


def inspect_viewport(browser, credentials: dict, name: str, width: int, height: int) -> dict:
    context = browser.new_context(viewport={"width": width, "height": height})
    login(context, credentials)
    try:
        return {
            "viewport": {"width": width, "height": height},
            "explore": measure_explore(context, name),
            "me": measure_me(context, name),
            "top_navigation": measure_top_navigation(context, name),
        }
    finally:
        context.close()


def main() -> int:
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    credentials = json.loads(CREDENTIALS.read_text(encoding="utf-8"))
    with sync_playwright() as playwright:
        executable = os.environ.get("HOMER_PLAYWRIGHT_EXECUTABLE", "").strip()
        browser = playwright.chromium.launch(headless=True, executable_path=executable or None)
        try:
            results = [
                inspect_viewport(browser, credentials, "desktop", 1440, 900),
                inspect_viewport(browser, credentials, "mobile", 390, 844),
            ]
        finally:
            browser.close()
    payload = {"base_url": BASE_URL, "results": results}
    (ARTIFACTS / "result.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    failed = any(
        not item["explore"]["clean"]
        or not item["me"]["clean"]
        or not item["top_navigation"]["clean"]
        or item["explore"]["horizontal_overflow"]
        or item["me"]["horizontal_overflow"]
        for item in results
    )
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
