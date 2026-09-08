"""Offline browser regressions for the PR 7 integration (no production writes)."""
from __future__ import annotations

import argparse
import functools
import json
import threading
import time
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "output" / "pr7-release-20260908"


class Fixture(SimpleHTTPRequestHandler):
    def log_message(self, *_):
        pass

    def do_GET(self):
        path = urlsplit(self.path).path
        if path == "/__review__":
            body = b'''<!doctype html><html data-theme="dark"><head>
              <meta name="viewport" content="width=device-width,initial-scale=1">
              <link rel="stylesheet" href="/app/assets/css/app.css">
              <link rel="stylesheet" href="/assets/css/app-design.css">
              <script defer src="/assets/js/option-picker.js"></script>
              </head><body><button id="origin">Open</button></body></html>'''
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if path.startswith(("/console/", "/go/", "/admin/api/")):
            value = {"data": {"list": [], "total": 0}, "points": 100}
            if path == "/console/api/account/profile":
                # A stale cached identity must not own the active cookie's data.
                time.sleep(0.35)
                value = {"id": "account-b", "name": "Current account", "is_admin": False}
            elif path == "/admin/api/me":
                self.send_response(403)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(b'{"message":"admin required"}')
                return
            elif path == "/console/api/web/my-apps":
                value = {"data": {"list": [{"id": "private-b", "name": "Account B private card", "is_public": False}], "total": 1}}
            elif path.endswith("/home-stats"):
                value = {"data": {"apps": {"total": 1}}}
            elif path.endswith("/site-settings"):
                value = {"data": {}}
            body = json.dumps(value).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        super().do_GET()


CONTRAST = """el => {
  const rgb = s => s.match(/[\\d.]+/g).slice(0,3).map(Number);
  const lum = c => c.map(v => {v /= 255; return v <= .04045 ? v/12.92 : ((v+.055)/1.055)**2.4;})
    .reduce((sum,v,i)=>sum+v*[.2126,.7152,.0722][i],0);
  const fg = lum(rgb(getComputedStyle(el).color));
  let parent = el, bg = 'rgba(0,0,0,0)';
  while(parent) {bg=getComputedStyle(parent).backgroundColor;if(!/rgba\\([^)]*,\\s*0\\)$/.test(bg)&&bg!=='transparent')break;parent=parent.parentElement;}
  const back=lum(rgb(bg));return (Math.max(fg,back)+.05)/(Math.min(fg,back)+.05);
}"""


def run():
    args = argparse.ArgumentParser()
    args.add_argument("--probe", action="store_true", help="Record pre-fix failures without stopping review")
    options = args.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    server = ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Fixture, directory=str(ROOT / "frontend")))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_port}"
    results = []
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, executable_path=r"C:\Program Files\Google\Chrome\Application\chrome.exe")

            def case(name, operation, width=390):
                context = browser.new_context(viewport={"width": width, "height": 844 if width == 390 else 900})
                context.route("**/*", lambda route: route.continue_() if route.request.url.startswith(base) else route.fulfill(status=204))
                page = context.new_page()
                page.set_default_timeout(8000)
                errors = []
                page.on("pageerror", lambda e: errors.append(str(e)))
                try:
                    detail = operation(page)
                    assert not errors, errors
                    results.append({"test": name, "passed": True, "detail": detail})
                except Exception as e:
                    results.append({"test": name, "passed": False, "error": str(e)[:1000], "page_errors": errors})
                finally:
                    try:
                        page.screenshot(path=str(OUT / f"{name}.png"), full_page=True)
                    except Exception:
                        pass
                    context.close()

            def account_cache(page, page_name, scope):
                page.add_init_script("localStorage.setItem('ai_xingyue_logged_in','1');localStorage.setItem('ai_xingyue_user',JSON.stringify({id:'account-a',name:'Old account'}));")
                page.goto(base + f"/app/{page_name}.html", wait_until="networkidle")
                page.wait_for_function("JSON.parse(localStorage.getItem('ai_xingyue_user')).id==='account-b'")
                caches = page.evaluate("() => Object.fromEntries(Object.entries(localStorage).filter(([k])=>k.startsWith('homer.page-cache.')))")
                assert not any("private-b" in value for key, value in caches.items() if key.endswith(".account-a")), "Current account's private cards were cached under the stale account"
                assert any("private-b" in value for key, value in caches.items() if key.endswith(f".{scope}.account-b")), "Current account's cache was not populated"
                return {"cache_keys": list(caches)}

            case("my-apps-account-isolation", lambda page: account_cache(page, "my-apps", "my-apps"))
            case("workshop-account-isolation", lambda page: account_cache(page, "workshop", "workshop"))

            def confirmation(page):
                page.goto(base + "/__review__", wait_until="networkidle")
                page.evaluate("() => {window.answer=null;import('/assets/js/dialogs.js').then(m=>m.confirmAction('<img src=x onerror=alert(1)>')).then(value=>window.answer=value);}")
                dialog = page.locator(".homer-action-dialog")
                dialog.wait_for(state="visible")
                assert dialog.locator("img").count() == 0
                ratios = [dialog.locator(selector).evaluate(CONTRAST) for selector in ["h2", "p", ".homer-action-confirm"]]
                page.get_by_role("button", name="取消", exact=True).click()
                page.wait_for_function("window.answer===false")
                assert min(ratios) >= 4.5, f"Dark confirmation contrast below 4.5: {ratios}"
                return {"contrast": ratios, "cancelled": True}

            case("dark-confirmation", confirmation)

            def picker(page):
                page.goto(base + "/__review__", wait_until="networkidle")
                page.evaluate("() => {window.changes=0;const s=document.createElement('select');s.id='choice';s.setAttribute('aria-label','Model');s.innerHTML='<option value=a>Alpha</option><option value=b>Beta</option><option disabled value=c>Disabled</option>';s.onchange=()=>changes++;document.body.append(s);}")
                page.locator("#choice").click()
                dialog = page.locator(".homer-option-picker")
                dialog.wait_for(state="visible")
                ratio = dialog.locator("h2").evaluate(CONTRAST)
                page.keyboard.press("Escape")
                assert page.evaluate("changes") == 0
                assert page.locator("#choice").input_value() == "a"
                page.locator("#choice").click()
                page.get_by_role("radio", name="Beta", exact=True).click()
                assert page.locator("#choice").input_value() == "b"
                assert page.evaluate("changes") == 1
                assert ratio >= 4.5, f"Dark picker contrast below 4.5: {ratio}"
                return {"contrast": ratio, "changes": 1}

            case("dark-option-picker", picker)

            def appearance(page):
                page.goto(base + "/__review__", wait_until="networkidle")
                page.evaluate("""async () => {
                  const m=await import('/assets/js/chat-appearance.js');window.scope={owner:'account-a',conversation:'one'};
                  window.appearance=m.bindChatAppearance(()=>scope);appearance.open();
                }""")
                page.locator(".homer-appearance-dialog").wait_for(state="visible")
                page.get_by_label("角色气泡 #ffffff", exact=True).click()
                page.evaluate("scope.conversation='two';appearance.refresh();")
                assert not page.locator(".homer-appearance-dialog[open]").count(), "Appearance editor remains tied to the previous conversation after switching"
                assert page.evaluate("document.body.style.getPropertyValue('--tavo-assistant-bubble')") == "#29485f"
                assert page.evaluate("Object.keys(localStorage).filter(k=>k.startsWith('homer.chat-appearance.')).length") == 0
                return {"stale_draft_discarded": True}

            case("appearance-conversation-switch", appearance)

            def preview_gate(page, name):
                page.add_init_script("localStorage.setItem('ai_xingyue_logged_in','1');localStorage.setItem('ai_xingyue_user',JSON.stringify({id:'account-b'}));")
                page.goto(base + f"/app/{name}.html?preview=1", wait_until="networkidle")
                page.wait_for_url("**/app/explore.html", timeout=3000)
                return {"ordinary_user_redirected": True}

            for name in ["community", "community-library", "community-contest"]:
                case(name + "-preview-gate", lambda page, name=name: preview_gate(page, name))

            def groups(page):
                page.add_init_script("localStorage.setItem('ai_xingyue_logged_in','1');localStorage.setItem('ai_xingyue_user',JSON.stringify({id:'account-b'}));")
                page.goto(base + "/app/group-chat.html", wait_until="networkidle")
                assert urlsplit(page.url).path == "/app/group-chat.html", "Group chat URL redirects away from existing conversations"
                methods = page.evaluate("async () => {const {api}=await import('/app/assets/js/app-core.js?v=20260905-notices-v1');return ['groupChats','createGroupChat','sendGroupMessage','groupReply'].every(k=>typeof api[k]==='function');}")
                assert methods, "Group chat client APIs removed"
                assert not page.evaluate("document.documentElement.scrollWidth>innerWidth+1")
                return {"group_chat_retained": True}

            case("existing-group-chat", groups)
            browser.close()
    finally:
        server.shutdown()
        server.server_close()
    report = OUT / ("browser-before-fixes.json" if options.probe else "browser-regressions.json")
    report.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8", newline="\n")
    print(json.dumps(results, ensure_ascii=False))
    return 0 if options.probe or all(result["passed"] for result in results) else 1


if __name__ == "__main__":
    raise SystemExit(run())
