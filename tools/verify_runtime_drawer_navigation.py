#!/usr/bin/env python3
"""浏览器侧验证：对话运行时抽屉里的导航项交给宿主页换页，而不是自己在 iframe 里跳。

这条是「完整账户/我的 黑屏」的另一半。生产主站发 `frame-ancestors 'none'`，
所以在 `#dialogue-frame` 里加载 /app/me.html 或 /dashboard.html 会被浏览器直接
拒掉 —— 用户看到的就是一整块黑。改法是 bridge 的抽屉导航项改发 navigate 消息，
由 chat.js 的 allowedNavigationPath 放行后在顶层换页。

只跑本机离线栈（127.0.0.1:8080）。
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
BASE_URL = "http://127.0.0.1:8080"
CREDENTIALS = ROOT / "output" / "offline-dev" / "runtime" / "credentials.json"
ARTIFACTS = ROOT / "output" / "playwright" / "runtime-drawer-navigation-20260901"


def main() -> int:
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    credentials = json.loads(CREDENTIALS.read_text(encoding="utf-8"))
    with sync_playwright() as playwright:
        executable = os.environ.get("HOMER_PLAYWRIGHT_EXECUTABLE", "").strip()
        browser = playwright.chromium.launch(headless=True, executable_path=executable or None)
        context = browser.new_context(viewport={"width": 1440, "height": 900})
        login = context.request.post(
            BASE_URL + "/console/api/login",
            data={"email": credentials["email"], "password": credentials["password"]},
        )
        if login.status != 200:
            raise AssertionError(f"login failed: {login.status}")
        context.add_init_script("localStorage.setItem('ai_xingyue_logged_in', '1')")
        conversations = context.request.get(BASE_URL + "/console/api/web/conversations").json()
        item = conversations["data"]["list"][0]

        page = context.new_page()
        errors: list[str] = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto(
            f"{BASE_URL}/app/chat.html?app_id={item['app_id']}&conversation_id={item['id']}",
            wait_until="commit",
            timeout=30_000,
        )
        page.wait_for_function("document.body.classList.contains('is-ready')", timeout=90_000)
        frame = page.frame(name="homer-dialogue-module")
        if frame is None:
            raise AssertionError("dialogue runtime frame is missing")
        frame.wait_for_selector(".homer-main-navigation__item", state="attached", timeout=20_000)

        # 抽屉默认关闭，直接对锚点派发 click；要验的是 handler，不是抽屉动画。
        clicked = frame.evaluate(
            """() => {
              const link = [...document.querySelectorAll('.homer-main-navigation__item')]
                .find(node => /我的/.test(node.textContent || ''));
              if (!link) return null;
              const before = location.pathname;
              link.click();
              return { href: link.getAttribute('href'), iframePathAfterClick: before };
            }"""
        )
        if not clicked:
            raise AssertionError("runtime drawer has no 我的 entry")
        page.wait_for_url(f"{BASE_URL}/app/me.html", timeout=15_000)
        host_path = page.evaluate("location.pathname")
        page.screenshot(path=str(ARTIFACTS / "host-navigated.png"), full_page=False)

        result = {
            "drawer_link_href": clicked["href"],
            "host_path_after": host_path,
            "page_errors": errors,
        }
        context.close()
        browser.close()

    (ARTIFACTS / "result.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["host_path_after"] == "/app/me.html" and not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
