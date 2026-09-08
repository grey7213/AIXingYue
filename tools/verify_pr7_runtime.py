"""Exercise reviewed UI against the isolated real backend and SillyTavern stack."""
from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import urlsplit

from playwright.sync_api import sync_playwright
from _e2e_original_sillytavern_browser import login, start_conversation

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "output" / "pr7-release-20260908"


def main():
    state = ROOT / "output" / "sillytavern-e2e" / "runtime"
    config = json.loads((state / "config.json").read_text(encoding="utf-8"))
    credentials = json.loads((state / "credentials.json").read_text(encoding="utf-8"))
    base = config["base_url"].rstrip("/")
    assert urlsplit(base).hostname == "127.0.0.1", "Only the isolated local fixture is permitted"
    OUT.mkdir(parents=True, exist_ok=True)
    results = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, executable_path=r"C:\Program Files\Google\Chrome\Application\chrome.exe")
        try:
            for width, height in [(1440, 900), (390, 844)]:
                context = browser.new_context(viewport={"width": width, "height": height})
                page = context.new_page()
                page.set_default_timeout(20000)
                errors = []
                page.on("pageerror", lambda e: errors.append(str(e)))
                page.on("console", lambda m: errors.append(m.text) if m.type == 'error' and m.text != 'AbortError: The user aborted a request.' else None)
                try:
                    login(page, base, credentials)
                    conversation = start_conversation(page, base, config["app_id"])
                    second_conversation = start_conversation(page, base, config["app_id"])
                    target_url = f"{base}/app/chat.html?app_id={config['app_id']}&conversation_id={conversation}"
                    page.goto(target_url, wait_until="domcontentloaded")
                    page.wait_for_function("document.body.classList.contains('is-ready')", timeout=45000)
                    runtime = page.frame(name="homer-dialogue-module")
                    assert runtime is not None
                    runtime.wait_for_function("document.documentElement.classList.contains('homer-runtime-ready')")
                    count = runtime.locator("#chat .mes").count()
                    runtime.locator("#send_textarea").fill("Homer review: reply briefly.")
                    runtime.locator("#send_textarea").press("Enter")
                    runtime.wait_for_function("n=>document.querySelectorAll('#chat .mes').length>=n+2 && !!window.SillyTavern.getContext().chat.at(-1)?.extra?.homer_message_id", arg=count, timeout=60000)
                    message = runtime.locator('#chat .mes[is_user="false"]').last
                    message_id = message.evaluate("el=>window.SillyTavern.getContext().chat[Number(el.getAttribute('mesid'))].extra.homer_message_id")

                    def action(name):
                        message.locator(".mes_text").click(button="right")
                        runtime.locator(f'[data-homer-message-menu-action="{name}"]').click()

                    held = []
                    def delay_presentation(route):
                        if route.request.method == 'POST' and 'homer_message_presentation' in (route.request.post_data or ''):
                            held.append(route)
                        else:
                            route.continue_()
                    context.route('**/api/homer/runtime-state', delay_presentation)
                    action("collapse")
                    page.wait_for_timeout(250)
                    assert held, 'Expected a pending presentation save'
                    page.evaluate("data=>document.querySelector('#dialogue-frame').contentWindow.postMessage(data,location.origin)", {'channel':'homer:dialogue-host:v1','version':1,'type':'switch-conversation','conversation_id':second_conversation,'app_id':config['app_id']})
                    runtime.get_by_text('当前消息保存后才能切换会话', exact=True).wait_for(state='visible')
                    assert runtime.evaluate("id=>window.SillyTavern.getContext().chat.some(m=>m.extra?.homer_message_id===id)", message_id)
                    for route in held:
                        route.continue_()
                    context.unroute('**/api/homer/runtime-state', delay_presentation)
                    runtime.get_by_text('已折叠消息', exact=True).wait_for(state='visible')
                    message.locator(".mes_text").wait_for()
                    runtime.wait_for_function("id=>window.SillyTavern.getContext().chat.some(m=>m.extra?.homer_message_id===id&&m.extra?.homer_collapsed)", arg=message_id)
                    action("hide")
                    runtime.get_by_text('消息已从模型上下文中隐藏', exact=True).wait_for(state='visible')
                    runtime.wait_for_function("id=>window.SillyTavern.getContext().chat.some(m=>m.extra?.homer_message_id===id&&m.extra?.homer_hidden)", arg=message_id)
                    response = context.request.get(base + f"/console/api/web/conversations/{conversation}/messages")
                    cloud = response.json()
                    entries = (cloud.get("data") or cloud).get("list", [])
                    assert any(m.get("id") == message_id and m.get("role") == "assistant" for m in entries), "Hiding must retain the original cloud role"
                    page.reload(wait_until="domcontentloaded")
                    page.wait_for_function("document.body.classList.contains('is-ready')", timeout=90000)
                    runtime = page.frame(name="homer-dialogue-module")
                    runtime.wait_for_function("id=>window.SillyTavern.getContext().chat.some(m=>m.extra?.homer_message_id===id&&m.extra?.homer_hidden&&m.extra?.homer_collapsed)", arg=message_id)
                    message = runtime.locator("#chat .mes").filter(has=runtime.locator(".mes_text")).last
                    action("hide")
                    runtime.get_by_text('消息已恢复到模型上下文', exact=True).wait_for(state='visible')
                    runtime.wait_for_function("id=>window.SillyTavern.getContext().chat.some(m=>m.extra?.homer_message_id===id&&!m.extra?.homer_hidden)", arg=message_id)
                    action("select")
                    runtime.locator("#homer-message-selection").wait_for(state="visible")
                    runtime.locator("#chat .mes").first.click()
                    assert "2" in runtime.locator("[data-selection-count]").inner_text()
                    assert runtime.evaluate("HomerCloseOverlay()") is True
                    assert not runtime.locator("#homer-message-selection").count()
                    assert not runtime.evaluate("document.documentElement.scrollWidth>innerWidth+1")
                    page.screenshot(path=str(OUT / f"runtime-{width}.png"), full_page=True)
                    runtime.locator('[aria-label="打开对话设置"]').click()
                    runtime.get_by_role("button", name="界面设置", exact=True).click()
                    runtime.locator(".homer-appearance-dialog").wait_for(state="visible")
                    runtime.get_by_label("角色气泡 #ffffff", exact=True).click()
                    runtime.get_by_role("button", name="保存", exact=True).click()
                    assert runtime.evaluate("document.body.style.getPropertyValue('--homer-assistant-text')") == "#000000"

                    page.goto(base + "/admin.html", wait_until="networkidle")
                    page.wait_for_function("window.Alpine && document.querySelector('[x-data]')?._x_dataStack?.[0]?.adminInfo")
                    page.evaluate("Alpine.$data(document.querySelector('[x-data]')).switchTab('llm')")
                    page.wait_for_timeout(350)
                    assert not page.evaluate("document.documentElement.scrollWidth>innerWidth+1"), "Admin page overflows"
                    page.screenshot(path=str(OUT / f"admin-{width}.png"), full_page=True)
                    assert not page.get_by_role("button", name="社区管理", exact=True).count(), "Undeployed social moderation is exposed"
                    assert not errors, errors
                    results.append({"viewport": [width, height], "passed": True, "generation": True, "presentation_persisted": True, "selection_cancelled": True, "cloud_role_preserved": True, "page_errors": errors})
                    print(f"Runtime and admin passed at {width}px", flush=True)
                except Exception as e:
                    page.screenshot(path=str(OUT / f"runtime-failure-{width}.png"), full_page=True)
                    diagnostics = []
                    for frame in page.frames[:2]:
                        try:
                            diagnostics.append(frame.evaluate("() => ({path:location.pathname,html:document.documentElement.className,body:document.body.className,text:(document.querySelector('#homer-runtime-gate')?.innerText || document.querySelector('#launcher-detail')?.innerText || '').slice(0,500)})"))
                        except Exception:
                            pass
                    results.append({"viewport": [width, height], "passed": False, "error": str(e)[:1500], "page_errors": errors, "diagnostics": diagnostics})
                    print(json.dumps(results[-1], ensure_ascii=False), flush=True)
                    break
                finally:
                    context.close()
        finally:
            browser.close()
    (OUT / "runtime-regressions.json").write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8", newline="\n")
    return 0 if len(results) == 2 and all(row["passed"] for row in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
