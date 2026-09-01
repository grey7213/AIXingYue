"""生产实测：真实浏览器加载对话运行时与站点页面，确认本次推送没有破坏静态资源。

`curl` 直接取 `/module/dialogue/scripts/**` 会 500 —— 运行时对无会话请求返回
"Session not available"，未被本次推送触碰的 `script.js` 同样 500，所以那不是回归。
判断得用真实浏览器：先加载运行时首页拿到会话，再看 bridge 模块自己的响应码。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = "https://patcher.villainy.top"
ARTIFACTS = Path(__file__).resolve().parents[1] / "output" / "playwright" / "prod-native-bridge"
WATCH = (
    "/module/dialogue/scripts/extensions/homer-bridge/index.js",
    "/module/dialogue/scripts/extensions/homer-bridge/style.css",
    "/module/dialogue/script.js",
    "/module/dialogue/scripts/extensions.js",
)


def check_runtime(browser) -> dict:
    context = browser.new_context(viewport={"width": 412, "height": 915}, ignore_https_errors=True)
    page = context.new_page()
    seen: dict[str, int] = {}
    failures: list[str] = []
    page.on("response", lambda r: seen.setdefault(
        next((w for w in WATCH if r.url.endswith(w)), ""), r.status))
    page.on("response", lambda r: failures.append(f"{r.status} {r.url[:110]}")
            if r.status >= 500 and BASE in r.url else None)
    page.goto(f"{BASE}/module/dialogue/", wait_until="networkidle", timeout=90_000)
    result = {
        "watched_asset_status": {k: v for k, v in seen.items() if k},
        "server_errors": failures,
        "bridge_module_evaluated": page.evaluate(
            "Boolean(document.querySelector('#homer-runtime-gate'))"),
    }
    context.close()
    return result


def check_pages(browser) -> list[dict]:
    out = []
    for name, path, width, height in [
        ("home-desktop", "/", 1440, 900),
        ("home-mobile", "/", 390, 844),
        ("login-mobile", "/app/login.html", 390, 844),
    ]:
        context = browser.new_context(viewport={"width": width, "height": height},
                                      ignore_https_errors=True)
        page = context.new_page()
        console_errors: list[str] = []
        page_errors: list[str] = []
        net_errors: list[str] = []
        page.on("console", lambda m: console_errors.append(m.text) if m.type == "error" else None)
        page.on("pageerror", lambda e: page_errors.append(str(e)))
        page.on("response", lambda r: net_errors.append(f"{r.status} {r.url[:100]}")
                if r.status >= 400 and BASE in r.url else None)
        page.goto(BASE + path, wait_until="load", timeout=60_000)
        page.wait_for_timeout(1500)
        shot = ARTIFACTS / f"{name}.png"
        page.screenshot(path=str(shot), full_page=False)
        out.append({
            "name": name,
            "viewport": f"{width}x{height}",
            "version_text_visible": "v1.14.1" in page.content(),
            "stale_cache_token": "20260901-download-warm" in page.content(),
            "console_errors": console_errors,
            "page_errors": page_errors,
            "network_errors": net_errors,
            "screenshot": str(shot),
        })
        context.close()
    return out


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        payload = {"runtime": check_runtime(browser), "pages": check_pages(browser)}
        browser.close()
    (ARTIFACTS / "result.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))

    runtime = payload["runtime"]
    bad = [s for s in runtime["watched_asset_status"].values() if s >= 400]
    failed = bool(bad or runtime["server_errors"]) or any(
        p["console_errors"] or p["page_errors"] or p["network_errors"] or p["stale_cache_token"]
        for p in payload["pages"])
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
