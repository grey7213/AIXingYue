"""Browser E2E for Homer SillyTavern extension/runtime/workshop support."""

from __future__ import annotations

import io
import json
import re
import time
import zipfile
from pathlib import Path
from urllib.parse import urlsplit

from playwright.sync_api import Frame, Page, TimeoutError as PlaywrightTimeoutError, sync_playwright


ROOT = Path(__file__).resolve().parents[1]
STATE_DIR = ROOT / "output" / "sillytavern-e2e"
RUNTIME_DIR = STATE_DIR / "runtime"


def build_extension_package(path: Path) -> None:
    manifest = {
        "display_name": "Browser Runtime Probe",
        "author": "Homer E2E",
        "version": "1.0.0",
        "loading_order": 3,
        "js": "index.js",
        "css": "style.css",
        "hooks": {"enable": "enable", "activate": "activate"},
    }
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("manifest.json", json.dumps(manifest))
        archive.writestr(
            "index.js",
            """
export function enable() {
  window.__stEnableProbe = (window.__stEnableProbe || 0) + 1;
}
export function activate() {
  window.__stRuntimeProbe = 'active';
}
""".strip(),
        )
        archive.writestr("style.css", ":root{--homer-st-e2e:loaded}\n")
    path.write_bytes(buffer.getvalue())


def monitor_page(page: Page, allowed_origins: tuple[str, ...]) -> dict[str, list[str]]:
    failures: dict[str, list[str]] = {
        "console": [],
        "page": [],
        "request": [],
        "http": [],
        "external": [],
    }
    page.on(
        "console",
        lambda message: failures["console"].append(message.text)
        if message.type == "error"
        else None,
    )
    page.on("pageerror", lambda error: failures["page"].append(str(error)))
    def record_request_failure(request) -> None:
        # Chromium reports deliberate navigation cancellation as ERR_ABORTED.
        # It is not a network failure and would otherwise make cross-page E2E
        # coverage flaky, especially for lazy cover images.
        if "ERR_ABORTED" in str(request.failure or ""):
            return
        failures["request"].append(f"{request.method} {request.url}: {request.failure}")

    page.on("requestfailed", record_request_failure)
    page.on(
        "response",
        lambda response: failures["http"].append(
            f"{response.status} {response.request.method} {response.url}"
        )
        if response.status >= 400
        else None,
    )
    page.on(
        "request",
        lambda request: failures["external"].append(request.url)
        if request.url.startswith(("http://", "https://"))
        and not request.url.startswith(allowed_origins)
        else None,
    )
    return failures


def stub_optional_memory_books_user_files(page: Page) -> None:
    # MemoryBooks treats these missing first-run files as empty settings, but
    # Chromium still records the expected 404s as console/network failures.
    for name in ("stmb-side-prompts.json", "stmb-context-settings.json"):
        page.route(
            f"**/user/files/{name}",
            lambda route: route.fulfill(
                status=200,
                content_type="application/json",
                body="{}",
            ),
        )


def goto(page: Page, url: str):
    response = page.goto(url, wait_until="commit", timeout=30_000)
    if response is None or response.status != 200:
        raise AssertionError(f"navigation failed: {url} ({response.status if response else 'none'})")
    try:
        page.wait_for_load_state("networkidle", timeout=12_000)
    except PlaywrightTimeoutError:
        # Chat keeps a live/polling request open; DOM readiness plus the
        # feature-specific readiness assertions below are authoritative there.
        if "/app/chat.html" not in url:
            raise
    return response


def dialogue_runtime_frame(page: Page, base_url: str) -> Frame:
    page.locator("#dialogue-frame").wait_for(state="attached", timeout=30_000)
    page.wait_for_function(
        "document.body.classList.contains('is-ready')",
        timeout=150_000,
    )
    runtime = page.frame(name="homer-dialogue-module")
    if runtime is None:
        raise AssertionError("internal dialogue frame was not created")
    if not runtime.url.startswith(base_url + "/module/dialogue/"):
        raise AssertionError(f"dialogue frame escaped the internal mount: {runtime.url}")
    if not page.url.startswith(base_url + "/app/chat.html"):
        raise AssertionError(f"website shell was replaced by the runtime: {page.url}")
    if "SillyTavern" in page.title():
        raise AssertionError(f"browser title exposed inherited branding: {page.title()!r}")
    runtime.locator("body.homer-runtime").wait_for(state="attached", timeout=90_000)
    visible_text = runtime.locator("body").inner_text()[:200_000]
    if "SillyTavern" in visible_text:
        raise AssertionError("dialogue UI exposed inherited product branding")
    surface = runtime.evaluate(
        """() => {
          const forbidden = [
            '[MVU]脚本加载成功',
            '构建信息',
            'API 连接',
            '角色管理',
            '扩展程序',
            '原版酒馆',
          ];
          const visibleText = document.body?.innerText || '';
          const visibleInheritedControls = [
            '#top-bar',
            '#top-settings-holder',
            '#toast-container .toast',
          ].filter(selector => [...document.querySelectorAll(selector)].some(element => {
            const style = getComputedStyle(element);
            const rect = element.getBoundingClientRect();
            return style.display !== 'none'
              && style.visibility !== 'hidden'
              && rect.width > 0
              && rect.height > 0;
          }));
          return {
            ready: document.documentElement.classList.contains('homer-runtime-ready'),
            forbiddenText: forbidden.filter(text => visibleText.includes(text)),
            visibleInheritedControls,
            parkedSettings: document.querySelector('#top-settings-holder')?.parentElement?.id || '',
          };
        }"""
    )
    if not surface["ready"]:
        raise AssertionError("product-owned runtime surface was not marked ready")
    if surface["forbiddenText"] or surface["visibleInheritedControls"]:
        raise AssertionError(
            "internal compatibility UI escaped into the product surface: "
            + json.dumps(surface, ensure_ascii=False)
        )
    if surface["parkedSettings"] != "homer-internal-parking":
        raise AssertionError(
            "inherited settings subtree was not parked: "
            + json.dumps(surface, ensure_ascii=False)
        )
    exposed_urls = runtime.evaluate(
        """() => performance.getEntriesByType('resource')
          .map(item => item.name)
          .filter(name => name.includes('127.0.0.1:18091') || name.includes('/dialogue-core/'))"""
    )
    if exposed_urls:
        raise AssertionError(
            f"runtime network exposed an internal or legacy route: {exposed_urls[:8]}"
        )
    return runtime


def login(page: Page, base_url: str, credentials: dict) -> None:
    # Authenticate through a neutral destination so an account's previous
    # dialogue iframe cannot start and then be deliberately aborted by the next
    # feature-specific navigation in this cross-page suite.
    goto(page, base_url + "/app/login.html?next=%2Fapp%2Fexplore.html")
    page.locator('input[type="email"]').first.fill(credentials["email"])
    page.locator('input[type="password"]').first.fill(credentials["password"])
    page.get_by_role("button", name="进入 惑梦（Homer）").click()
    page.wait_for_url(lambda url: "/app/login.html" not in url, timeout=20_000)
    try:
        page.wait_for_load_state("networkidle", timeout=12_000)
    except PlaywrightTimeoutError:
        # The authenticated shell may already have a live dialogue request;
        # URL transition plus the feature-specific assertions are authoritative.
        pass


def assert_no_overflow(page: Page, label: str) -> None:
    overflow = page.evaluate(
        "document.documentElement.scrollWidth > document.documentElement.clientWidth + 1"
    )
    if overflow:
        raise AssertionError(f"{label}: horizontal overflow")


def assert_no_inherited_brand(page: Page, label: str) -> None:
    exposure = page.evaluate(
        """() => {
          const needle = ['silly', 'tavern'].join('');
          const resources = performance.getEntriesByType('resource')
            .map(entry => String(entry.name || ''))
            .filter(url => url.toLowerCase().includes(needle));
          const matches = [];
          const html = document.documentElement.innerHTML;
          const htmlIndex = html.toLowerCase().indexOf(needle);
          for (const element of document.querySelectorAll('*')) {
            for (const attribute of [...element.attributes]) {
              if (String(attribute.value || '').toLowerCase().includes(needle)) {
                matches.push({
                  tag: element.tagName,
                  attribute: attribute.name,
                  value: String(attribute.value || '').slice(0, 180),
                });
              }
            }
            for (const node of [...element.childNodes]) {
              if (
                node.nodeType === Node.TEXT_NODE
                && String(node.nodeValue || '').toLowerCase().includes(needle)
              ) {
                matches.push({
                  tag: element.tagName,
                  text: String(node.nodeValue || '').trim().slice(0, 180),
                });
              }
            }
            if (matches.length >= 12) break;
          }
          return {
            url: location.href.toLowerCase().includes(needle),
            title: document.title.toLowerCase().includes(needle),
            visible: (document.body?.innerText || '').toLowerCase().includes(needle),
            dom: htmlIndex >= 0,
            domContext: htmlIndex >= 0
              ? html.slice(Math.max(0, htmlIndex - 120), htmlIndex + 240)
              : '',
            resources,
            matches,
          };
        }"""
    )
    if exposure["url"] or exposure["title"] or exposure["visible"] or exposure["dom"] or exposure["resources"]:
        raise AssertionError(
            f"{label}: inherited runtime branding is exposed: "
            + json.dumps(exposure, ensure_ascii=False)
        )


def assert_clean(failures: dict[str, list[str]], label: str) -> None:
    populated = {
        key: value
        for key, value in failures.items()
        if key != "external" and value
    }
    if populated:
        raise AssertionError(f"{label}: browser failures: {json.dumps(populated, ensure_ascii=False)}")


def install_extension_from_admin(page: Page, base_url: str, extension_zip: Path) -> str:
    goto(page, base_url + "/admin.html")
    page.get_by_role("button", name="对话扩展").click()
    page.get_by_role("heading", name="对话扩展").wait_for(state="visible")
    existing_registry = page.evaluate(
        """async () => {
          const response = await fetch('/console/api/web/dialogue/extensions');
          return response.ok ? (await response.json()).data : { list: [] };
        }"""
    )
    existing = next(
        (
            item
            for item in existing_registry.get("list", [])
            if item.get("display_name") == "Browser Runtime Probe"
        ),
        None,
    )
    if existing:
        return str(existing["id"])
    plugin_panel = page.locator('div[x-show="activeTab === \'plugins\'"]')
    file_input = plugin_panel.locator('input[type="file"][accept*=".zip"]')
    with page.expect_response(
        lambda response: "/admin/api/dialogue/extensions/import" in response.url
        and response.request.method == "POST"
    ) as import_info:
        file_input.set_input_files(str(extension_zip))
    import_response = import_info.value
    if import_response.status != 200:
        raise AssertionError(f"extension import failed: {import_response.status}")
    extension = import_response.json()["data"]["extension"]
    extension_id = str(extension["id"])
    plugin_panel.get_by_role("button", name="关闭", exact=True).click()
    row = page.locator("div.rounded-xl").filter(has_text="Browser Runtime Probe").last
    row.wait_for(state="visible")
    with page.expect_response(
        lambda response: f"/admin/api/dialogue/extensions/{extension_id}/toggle" in response.url
        and response.request.method == "POST"
    ) as toggle_info:
        row.get_by_role("button", name="启用", exact=True).click()
    if toggle_info.value.status != 200:
        raise AssertionError(f"extension enable failed: {toggle_info.value.status}")
    row.get_by_text("已启用", exact=True).wait_for(state="visible")
    registry = page.evaluate(
        """async () => {
          const response = await fetch('/console/api/web/dialogue/extensions');
          return { status: response.status, body: await response.json() };
        }"""
    )
    if registry["status"] != 200:
        raise AssertionError(f"enabled registry failed: {registry['status']}")
    ids = [item["id"] for item in registry["body"]["data"]["list"]]
    if extension_id not in ids:
        raise AssertionError("enabled extension is absent from the user registry")
    return extension_id


def verify_chat_runtime(
    page: Page,
    base_url: str,
    app_id: str,
    *,
    card_marker: str = "__cardHelperProbe",
) -> dict:
    goto(page, f"{base_url}/app/chat.html?app_id={app_id}")
    runtime = dialogue_runtime_frame(page, base_url)
    runtime.locator(".homer-chat-header").wait_for(state="visible", timeout=30_000)
    try:
        runtime.wait_for_function("window.__stRuntimeProbe === 'active'", timeout=20_000)
    except PlaywrightTimeoutError as error:
        diagnostic = runtime.evaluate(
            """() => ({
              readyState: document.readyState,
              url: location.href,
              hasSillyTavern: Boolean(window.SillyTavern?.getContext),
              host: window.__homerDialogueExtensions || null,
              cardHelper: window.__cardHelperProbe || null,
              bodyText: (document.body?.innerText || '').slice(0, 400),
            })"""
        )
        raise AssertionError(
            "extension runtime marker missing: " + json.dumps(diagnostic, ensure_ascii=False)
        ) from error
    try:
        runtime.wait_for_function(
            "marker => Boolean(window[marker])",
            arg=card_marker,
            timeout=30_000,
        )
    except PlaywrightTimeoutError as error:
        diagnostic = runtime.evaluate(
            """marker => ({
              marker: window[marker] || null,
              extensionHost: window.__homerDialogueExtensions || null,
              runtimeRoot: document.querySelectorAll('.homer-runtime-root').length,
              scriptToggles: [...document.querySelectorAll(
                'input[id$="-script-enable-toggle"]',
              )].map(input => ({ id: input.id, checked: input.checked })),
              dialogs: [...document.querySelectorAll('dialog.popup[open]')]
                .map(dialog => (dialog.innerText || '').slice(0, 400)),
              bodyText: (document.body?.innerText || '').slice(0, 800),
            })""",
            card_marker,
        )
        raise AssertionError(
            "card helper marker missing: " + json.dumps(diagnostic, ensure_ascii=False)
        ) from error
    runtime.wait_for_function(
        "window.__homerDialogueExtensions?.result?.failed?.length === 0",
        timeout=20_000,
    )
    css_probe = runtime.evaluate(
        "getComputedStyle(document.documentElement).getPropertyValue('--homer-st-e2e').trim()"
    )
    if css_probe != "loaded":
        raise AssertionError(f"extension CSS did not load: {css_probe!r}")
    if runtime.evaluate("window.__stEnableProbe") != 1:
        raise AssertionError("extension enable hook did not run exactly once")

    state = runtime.evaluate(
        """async () => {
          const params = new URLSearchParams(location.search);
          const runtime = {
            appId: params.get('homer_app_id'),
            convId: params.get('homer_conversation_id'),
          };
          const query = new URLSearchParams({
            app_id: runtime.appId,
            conversation_id: runtime.convId,
          });
          window.SillyTavern.extensionSettings['browser-probe'] = {
            enabled: true,
            mode: 'e2e',
          };
          await window.SillyTavern.saveSettingsDebounced();
          const extensionSettings = JSON.parse(JSON.stringify(
            window.SillyTavern.extensionSettings,
          ));
          const updateResponse = await fetch('/api/homer/runtime-state', {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
              ...window.SillyTavern.getContext().getRequestHeaders(),
            },
            body: JSON.stringify({
              app_id: runtime.appId,
              conversation_id: runtime.convId,
              extension_settings: extensionSettings,
              worldbook_overrides: {
                'e2e-world-1': {
                  content: 'E2E_BROWSER_WORLD_OVERRIDE',
                  enabled: true,
                },
              },
            }),
          });
          if (!updateResponse.ok) {
            return { status: updateResponse.status, body: await updateResponse.json(), runtime };
          }
          const proxied = await fetch('/api/homer/runtime-state?' + query);
          return { status: proxied.status, body: await proxied.json(), runtime };
        }"""
    )
    data = state["body"]["data"]
    if state["status"] != 200:
        raise AssertionError(f"runtime state read failed: {state['status']}")
    if data["extension_settings"]["browser-probe"]["mode"] != "e2e":
        raise AssertionError("extension settings were not persisted")
    if data["worldbook_overrides"]["e2e-world-1"]["content"] != "E2E_BROWSER_WORLD_OVERRIDE":
        raise AssertionError("worldbook override was not persisted")
    return state["runtime"]


def verify_roleplayhub_runtime(
    page: Page,
    base_url: str,
    app_id: str,
    artifact_dir: Path,
    viewport: str,
) -> dict:
    goto(page, f"{base_url}/app/chat.html?app_id={app_id}")
    runtime = dialogue_runtime_frame(page, base_url)
    try:
        runtime.wait_for_function(
            "window.__homerRoleplayHubCompatibility?.isActive() === true",
            timeout=30_000,
        )
    except PlaywrightTimeoutError as error:
        diagnostic = runtime.evaluate(
            """() => ({
              url: location.href,
              title: document.title,
              readyState: document.readyState,
              compatibility: window.__homerRoleplayHubCompatibility
                ? {
                    active: window.__homerRoleplayHubCompatibility.isActive(),
                    keys: Object.keys(window.__homerRoleplayHubCompatibility),
                  }
                : null,
              extensions: window.__homerDialogueExtensions || null,
              hasContext: Boolean(window.SillyTavern?.getContext),
              characterId: window.SillyTavern?.getContext?.().characterId,
              characterNames: window.SillyTavern?.getContext?.().characters?.map?.(
                character => character?.name,
              ) || [],
              iframeCount: document.querySelectorAll('iframe.homer-roleplayhub-frame').length,
              bodyText: (document.body?.innerText || '').slice(0, 800),
            })"""
        )
        raise AssertionError(
            "RoleplayHub compatibility did not activate: "
            + json.dumps(diagnostic, ensure_ascii=False)
        ) from error
    inline_repair = runtime.evaluate(
        """async () => {
          const module = await import('./scripts/extensions/homer-bridge/roleplayhub-compat.js');
          const source = '<html><body><script>const value = "<span style="color:red">x</span>";</' + 'script></body></html>';
          const repaired = module.repairRoleplayHubInlineScripts(source);
          const parsed = new DOMParser().parseFromString(repaired, 'text/html');
          const script = parsed.querySelector('script')?.textContent || '';
          let parseable = true;
          try {
            new Function(script);
          } catch {
            parseable = false;
          }
          return {
            encodedStyle: repaired.includes('style=&quot;color:red&quot;'),
            parseable,
          };
        }"""
    )
    if not inline_repair["encodedStyle"] or not inline_repair["parseable"]:
        raise AssertionError(f"RoleplayHub malformed inline script repair failed: {inline_repair}")
    frame_element = runtime.locator("iframe.homer-roleplayhub-frame").first
    frame_element.wait_for(state="visible", timeout=30_000)
    runtime.wait_for_function(
        """() => {
          const composer = document.querySelector('#send_textarea');
          return composer instanceof HTMLTextAreaElement
            && !composer.disabled
            && !String(composer.placeholder || '').includes('未连接');
        }""",
        timeout=30_000,
    )
    sandbox = frame_element.get_attribute("sandbox")
    if sandbox != "allow-scripts":
        raise AssertionError(f"RoleplayHub iframe sandbox is too broad: {sandbox!r}")
    for forbidden in ("allow-same-origin", "allow-downloads", "allow-popups"):
        if forbidden in (sandbox or ""):
            raise AssertionError(f"RoleplayHub iframe unexpectedly permits {forbidden}")

    runtime.wait_for_function(
        """() => {
          const context = window.SillyTavern?.getContext?.();
          const characters = Array.isArray(context?.characters)
            ? context.characters
            : Object.values(context?.characters || {});
          return characters.some(character =>
            character?.data?.extensions?.homer_roleplayhub?.source === 'roleplayhub'
          );
        }""",
        timeout=30_000,
    )
    native_card = runtime.evaluate(
        """() => {
          const context = window.SillyTavern.getContext();
          const characters = Array.isArray(context.characters)
            ? context.characters
            : Object.values(context.characters || {});
          const active = context.characters?.[context.characterId];
          const character = active?.data?.extensions?.homer_roleplayhub
            ? active
            : characters.find(item =>
                item?.data?.extensions?.homer_roleplayhub?.source === 'roleplayhub'
              );
          const extensions = character?.data?.extensions || {};
          const scripts = Array.isArray(extensions.regex_scripts) ? extensions.regex_scripts : [];
          return {
            source: extensions.homer_roleplayhub?.source,
            regexCount: scripts.length,
            firstRegex: scripts[0] || null,
            templateCount: Array.isArray(extensions.rp_hub_ui_templates)
              ? extensions.rp_hub_ui_templates.length
              : 0,
          };
        }"""
    )
    if native_card["source"] != "roleplayhub":
        raise AssertionError("RoleplayHub capability profile is missing in SillyTavern")
    if native_card["regexCount"] != 23 or native_card["templateCount"] != 1:
        raise AssertionError(f"RoleplayHub extensions were not preserved: {native_card}")
    if native_card["firstRegex"].get("scriptName") != "ALTIA_UI_Render":
        raise AssertionError("RoleplayHub Regex was not converted to native SillyTavern schema")

    card_frame = runtime.frame_locator("iframe.homer-roleplayhub-frame").first
    card_frame.get_by_role("button", name="✦ 翻开序章").wait_for(
        state="visible",
        timeout=20_000,
    )
    intro_button = card_frame.get_by_role("button", name="✦ 翻开序章")
    role_setup = card_frame.get_by_role("button", name="设定角色")
    for _ in range(5):
        intro_button.evaluate("(button) => button.click()")
        page.wait_for_timeout(750)
        if role_setup.is_visible():
            break
    role_setup.wait_for(state="visible", timeout=20_000)
    role_setup.evaluate("(button) => button.click()")
    card_frame.locator("#charName").wait_for(state="visible", timeout=10_000)
    card_frame.locator("#charName").fill("星璃")
    card_frame.locator("#charAge").fill("21")
    female_button = card_frame.get_by_role("button", name="♀ 女性")
    female_button.wait_for(state="visible", timeout=10_000)
    # The card continuously animates the setup panel height. Dispatching the
    # card's normal click event avoids a false "element not stable" result.
    female_button.evaluate("(button) => button.click()")
    if card_frame.locator("#charName").input_value() != "星璃":
        raise AssertionError("RoleplayHub iframe form interaction failed")

    # Verify the card-to-host bridge without starting a model generation.
    card_frame.locator("body").evaluate(
        "() => window.triggerSlash('/setvar key=roleplayhub_probe e2e-ok')"
    )
    runtime.wait_for_function(
        """() => window.SillyTavern.getContext()
          .chatMetadata?.variables?.roleplayhub_probe === 'e2e-ok'""",
        timeout=10_000,
    )

    player_ball = runtime.locator("#homerRoleplayHubBall")
    player_ball.wait_for(state="visible", timeout=10_000)
    player_ball.click()
    player_menu = runtime.locator("#homerRoleplayHubMenu")
    player_menu.wait_for(state="visible")
    runtime.locator("#homerRoleplayHubMode").click()
    if runtime.locator("#homerRoleplayHubCounter").inner_text().strip() != "1 / 5":
        raise AssertionError("RoleplayHub media playlist did not load")

    assert_no_overflow(page, f"{viewport} RoleplayHub chat")
    page.screenshot(
        path=str(artifact_dir / f"roleplayhub-{viewport}.png"),
        full_page=True,
    )
    return {
        "card": "黎明之契2.71",
        "native_regex": native_card["regexCount"],
        "ui_templates": native_card["templateCount"],
        "iframe_sandbox": sandbox,
        "form_interaction": "pass",
        "slash_variable_bridge": "pass",
        "media_playlist": 5,
    }


def verify_card_stage_runtime(page: Page, base_url: str, artifact_dir: Path, viewport: str) -> dict:
    runtime = dialogue_runtime_frame(page, base_url)
    runtime.wait_for_function("Boolean(window.__homerCardStageRuntime)", timeout=20_000)
    injected = runtime.evaluate(
        """async () => {
          const context = window.SillyTavern.getContext();
          const character = context.characters?.[context.characterId];
          if (!character) return { ok: false, reason: 'character unavailable' };
          character.data ||= {};
          character.data.extensions ||= {};
          character.data.character_book ||= { entries: [] };
          character.data.character_book.entries ||= [];
          character.data.character_book.entries.push({
            id: 'stage-private-entry', name: '公开场景名',
            content: 'PRIVATE-WORLDBOOK-CONTENT-MUST-NOT-RENDER',
          });
          character.data.extensions.homer_card_experience = {
            version: 2,
            stage: {
              enabled: true,
              layout: 'split',
              chat_width: 58,
              background_asset_id: 'stage-bg',
              portrait_asset_id: 'stage-portrait',
              show_portrait: true,
              portrait_position: 'left',
              portrait_width: 36,
              portrait_opacity: 0.82,
              show_avatars: true,
              avatar_position: 'split',
              accent_color: '#d7b878',
              user_bubble_color: '#5b4635',
              assistant_bubble_color: '#211d19',
              text_color: '#fff8ed',
              bubble_radius: 18,
              font_scale: 1,
              input_style: 'floating',
              input_background_color: '#18222a',
              input_text_color: '#eef8ff',
              input_border_color: '#65c7d9',
            },
            structured_components: {
              enabled: true, map: true, inventory: true,
              relationship: true, skill_tree: true, status: true,
            },
            bgm: { enabled: false },
            ui_rules: [{
              id: 'stage-float', name: '剧情悬浮窗', enabled: true,
              pattern: '\\\\[FLOAT:stage\\\\]', flags: 'i', action: 'show_floating',
              template_html: '<section><strong>本地悬浮内容</strong><button data-card-action="insert-text" data-text="调查线索">调查</button></section>',
              scoped_css: 'section { padding: 12px; color: #fff; }',
              duration_ms: 0, remove_match: true,
            }],
            sidebars: [{
              id: 'stage-info', name: '资料', enabled: true, position: 'right', width: 340,
              trigger_label: '资料', open_pattern: '\\\\[SIDEBAR:stage\\\\]', flags: 'i',
              content_mode: 'static', content_html: '<section><h3>公开资料</h3><p>可交互侧栏</p></section>',
            }, {
              id: 'stage-world', name: '场景', enabled: true, position: 'right', width: 360,
              trigger_label: '场景', open_pattern: '', flags: 'i', content_mode: 'worldbook',
              world_entry_id: 'stage-private-entry', content_html: '',
            }],
            galgame: { enabled: false },
          };
          const pixel = 'data:image/gif;base64,R0lGODlhAQABAAAAACw=';
          character.data.extensions.homer_media_assets = [
            { id: 'stage-bg', kind: 'background', name: '舞台背景', url: pixel, mime_type: 'image/gif', status: 'ready' },
            { id: 'stage-portrait', kind: 'portrait', name: '角色立绘', url: pixel, mime_type: 'image/gif', status: 'ready' },
          ];
          const fixtures = [{
            type: 'map', title: '世界地图', subtitle: '本地层级探索',
            root: {
              id: 'world', name: '大陆', description: '选择区域继续探索',
              children: [{
                id: 'north', name: '北境', x: 32, y: 36,
                description: '终年覆雪的北方领地',
                children: [{ id: 'capital', name: '霜城', x: 58, y: 48, prompt: '前往霜城', children: [] }],
              }],
            },
          }, {
            type: 'inventory', title: '旅行行囊',
            items: [
              { name: '月光药剂', category: '消耗品', quantity: 2, description: '恢复体力' },
              { name: '旧钥匙', category: '任务', quantity: 1, description: '刻着北境纹章' },
            ],
          }, {
            type: 'relationship', title: '人物关系', center: { name: '我', description: '旅人' },
            nodes: [{ name: '艾拉', relation: '盟友', description: '可靠的向导' }, { name: '诺恩', relation: '未知', description: '身份成谜' }],
          }, {
            type: 'skill_tree', title: '技能树',
            skills: [{ name: '星火', tier: 0, unlocked: true, description: '点燃附近目标' }, { name: '天幕', tier: 1, unlocked: false, description: '尚未解锁' }],
          }, {
            type: 'status', title: '当前状态',
            items: [{ name: '体力', value: 72, max: 100, description: '仍可继续探索' }, { name: '好感', value: 38, max: 100, description: '关系正在升温' }],
          }];
          const startMessageId = context.chat.length;
          const messageIds = fixtures.map((fixture, index) => {
            const messageId = context.chat.length;
            const directives = index === fixtures.length - 1 ? '\\n[FLOAT:stage] [SIDEBAR:stage]' : '';
            context.chat.push({
              name: character.name || '角色', is_user: false, is_system: false,
              send_date: Date.now() + index,
              mes: '```homer-ui\\n' + JSON.stringify(fixture) + '\\n```' + directives,
            });
            return messageId;
          });
          const userMessageId = context.chat.length;
          context.chat.push({
            name: '用户', is_user: true, is_system: false, send_date: Date.now() + 20,
            mes: '```homer-ui\\n' + JSON.stringify({ type: 'inventory', items: [{ name: '伪造组件' }] }) + '\\n```',
          });
          window.__homerStageDocumentToken = crypto.randomUUID();
          await context.printMessages();
          await window.__homerCardStageRuntime.refresh();
          return { ok: true, startMessageId, messageIds, userMessageId, token: window.__homerStageDocumentToken };
        }"""
    )
    if not injected.get("ok"):
        raise AssertionError(f"card stage fixture failed: {injected}")
    runtime.locator("body.homer-card-stage-active.homer-stage-layout-split").wait_for(timeout=20_000)
    components = runtime.locator("#chat .homer-card-component")
    if components.count() != 5:
        raise AssertionError(f"not all structured components rendered: {components.count()}")
    if runtime.locator(
        f'#chat .mes[mesid="{injected["userMessageId"]}"] .homer-card-component'
    ).count():
        raise AssertionError("a user message was allowed to impersonate an AI component")
    for message_id in injected["messageIds"]:
        if runtime.locator(f'#chat .mes[mesid="{message_id}"] pre code').count():
            raise AssertionError("structured JSON source remained visible after successful render")

    auto_sidebar = runtime.locator("#homerCardExperienceRoot .ce-sidebar.is-open")
    if auto_sidebar.count() and auto_sidebar.first.is_visible():
        auto_sidebar.first.get_by_role("button", name="关闭", exact=True).click()
        runtime.wait_for_function(
            "!document.querySelector('#homerCardExperienceRoot')?.shadowRoot?.querySelector('.ce-sidebar.is-open')"
        )
        page.wait_for_timeout(300)

    generation_requests: list[str] = []

    def record_generation_request(request) -> None:
        lowered = request.url.lower()
        if request.method == "POST" and any(
            marker in lowered
            for marker in ("/generate", "chat-completion", "chat/completions")
        ):
            generation_requests.append(request.url)

    page.on("request", record_generation_request)
    try:
        map_component = runtime.locator(".homer-card-component--map")
        map_component.get_by_role("button", name="北境").click()
        map_component.get_by_role("button", name="霜城").click()
        map_component.get_by_text("这里已经是最深层地点").wait_for(state="visible")
        if map_component.locator(".homer-map__breadcrumbs button").count() != 3:
            raise AssertionError("map hierarchy did not advance locally")

        inventory = runtime.locator(".homer-card-component--inventory")
        inventory.get_by_role("searchbox", name="搜索物品").fill("药剂")
        if inventory.locator(".homer-inventory__item:visible").count() != 1:
            raise AssertionError("inventory search did not filter locally")

        relationship = runtime.locator(".homer-card-component--relationship")
        relationship.get_by_role("button", name="艾拉").click()
        if "盟友" not in relationship.locator(".homer-relationship__detail").inner_text():
            raise AssertionError("relationship node did not expose its local detail")

        skills = runtime.locator(".homer-card-component--skill_tree")
        skills.get_by_role("button", name="星火").click()
        if "点燃附近目标" not in skills.locator(".homer-skill-tree__detail").inner_text():
            raise AssertionError("skill detail did not update locally")

        status = runtime.locator(".homer-card-component--status")
        status.get_by_role("button", name=re.compile("体力")).click()
        if "仍可继续探索" not in status.locator(".homer-status-component__detail").inner_text():
            raise AssertionError("status detail did not update locally")

        floating = runtime.locator("#homerCardExperienceRoot .ce-float")
        try:
            floating.wait_for(state="visible", timeout=5_000)
        except PlaywrightTimeoutError as error:
            debug = runtime.evaluate(
                """async () => {
                  const module = await import('/app/assets/js/card-experience-runtime.mjs?v=20260801-stage3');
                  const host = document.querySelector('#homerCardExperienceRoot');
                  return {
                    host: Boolean(host),
                    shadow: Boolean(host?.shadowRoot),
                    floatCount: host?.shadowRoot?.querySelectorAll('.ce-float').length || 0,
                    rules: module.cardExperienceRuntime.config.ui_rules,
                    lastRawMessage: module.cardExperienceRuntime.lastRawMessage,
                    lastMessageSignature: module.cardExperienceRuntime.lastMessageSignature,
                  };
                }"""
            )
            raise AssertionError(f"floating panel did not open: {debug}") from error
        handle = floating.locator(".ce-float__drag")
        before = floating.bounding_box()
        handle.focus()
        handle.press("ArrowRight")
        after = floating.bounding_box()
        if not before or not after:
            raise AssertionError("floating panel bounds are unavailable")
        if after["x"] <= before["x"]:
            handle.press("ArrowDown")
            vertical = floating.bounding_box()
            if not vertical or vertical["y"] <= after["y"]:
                stage_bounds = runtime.locator(
                    "#homerCardExperienceRoot .ce-stage"
                ).bounding_box()
                raise AssertionError(
                    "floating panel keyboard drag did not move within the viewport: "
                    + json.dumps(
                        {
                            "before": before,
                            "after_right": after,
                            "after_down": vertical,
                            "stage": stage_bounds,
                        },
                        ensure_ascii=False,
                    )
                )

        runtime.locator("#homerCardExperienceRoot .ce-edge.right button").first.click()
        sidebar = runtime.locator("#homerCardExperienceRoot .ce-sidebar.is-open")
        sidebar.wait_for(state="visible")
        if sidebar.locator(".ce-sidebar__tab").count() != 2:
            raise AssertionError("same-side panels were not exposed as tabs")
        sidebar.get_by_role("tab", name="场景").click()
        sidebar.get_by_text("公开场景名").wait_for(state="visible")
        if "PRIVATE-WORLDBOOK-CONTENT-MUST-NOT-RENDER" in sidebar.inner_text():
            raise AssertionError("protected worldbook prose leaked into the card sidebar")
        page.wait_for_timeout(150)
    finally:
        page.remove_listener("request", record_generation_request)
    if generation_requests:
        raise AssertionError(f"component-only interaction called the model: {generation_requests}")

    component_width = round(components.first.evaluate("element => element.getBoundingClientRect().width"), 1)
    page.screenshot(path=str(artifact_dir / f"card-stage-{viewport}.png"), full_page=True)
    rollback = runtime.evaluate(
        """async ({ startMessageId, token }) => {
          const context = window.SillyTavern.getContext();
          context.chat.splice(startMessageId);
          await context.printMessages();
          await context.eventSource?.emit?.(context.event_types?.MESSAGE_DELETED, startMessageId);
          await new Promise(resolve => setTimeout(resolve, 80));
          return {
            sameDocument: window.__homerStageDocumentToken === token,
            componentCount: document.querySelectorAll('.homer-card-component').length,
            floatingCount: document.querySelectorAll('#homerCardExperienceRoot .ce-float').length,
          };
        }""",
        injected,
    )
    if (
        not rollback["sameDocument"]
        or rollback["componentCount"] != 0
        or rollback["floatingCount"] != 0
    ):
        raise AssertionError(f"card stage rollback was not real-time: {rollback}")
    return {
        "protocol": "homer-ui-json-v1",
        "layout": "split",
        "map_drilldown": "pass",
        "inventory_filter": "pass",
        "relationship_detail": "pass",
        "skill_detail": "pass",
        "status_detail": "pass",
        "draggable_floating": "pass",
        "tabbed_sidebars": "pass",
        "worldbook_privacy": "pass",
        "user_component_spoofing": "blocked",
        "component_width": component_width,
        "source_hidden": True,
        "token_free_interaction": "pass",
        "realtime_rollback": "pass",
    }


def verify_unified_loading(
    page: Page,
    base_url: str,
    dialogue_url: str,
    app_id: str,
    artifact_dir: Path,
) -> None:
    def delay_host_boot(route):
        response = route.fetch()
        delayed_source = (
            "await new Promise(resolve => setTimeout(resolve, 1500));\n"
            + response.text()
        )
        route.fulfill(response=response, body=delayed_source)

    # Hold the host module briefly so the real initial loading state can be
    # observed deterministically without replacing the page or its styles.
    page.route("**/app/assets/js/chat.js*", delay_host_boot)
    target = (
        f"{dialogue_url}/?homer_app_id={app_id}"
        f"&homer_conversation_id=loading-probe"
        f"&homer_site_origin={base_url}"
    )
    response = page.goto(target, wait_until="commit", timeout=30_000)
    if response is None or response.status != 200:
        raise AssertionError("dialogue loading navigation failed")
    if urlsplit(page.url).path != "/app/chat.html":
        raise AssertionError(f"top-level dialogue entry was not wrapped: {page.url}")
    page.locator(".launcher").wait_for(state="visible", timeout=20_000)
    page.locator(".seal").wait_for(state="visible", timeout=20_000)
    if page.locator("#launcher-title").inner_text().strip() != "加载中":
        raise AssertionError("unified loading title changed before it was rendered")
    if page.locator("#launcher-detail").inner_text().strip() != "正在准备对话…":
        raise AssertionError("unified loading detail changed before it was rendered")
    if page.locator(".launcher").get_attribute("aria-busy") != "true":
        raise AssertionError("unified loading layer is not exposed as busy")
    if page.locator(
        ".splash-logo, img[alt='SillyTavern'], #load-spinner.fa-gear",
    ).count():
        raise AssertionError("inherited branding or gear loader is still visible")
    visible_text = page.locator("body").inner_text()
    if "SillyTavern" in visible_text or "TAVO" in visible_text.upper():
        raise AssertionError("dialogue loading layer exposed an inherited product name")
    page.screenshot(path=str(artifact_dir / "loading-desktop.png"), full_page=True)
    page.unroute("**/app/assets/js/chat.js*", delay_host_boot)


def verify_workshop(page: Page, base_url: str, app_id: str, artifact_dir: Path) -> None:
    goto(page, f"{base_url}/app/create.html?id={app_id}")
    if page.get_by_text("SillyTavern 卡内脚本", exact=True).count():
        raise AssertionError("workshop exposed the removed card-script editor")
    if page.get_by_text("卡内脚本", exact=True).count():
        raise AssertionError("workshop preview exposed hidden card-script metadata")
    for legacy_label in ("世界书 / Lorebook", "使用我收藏的社区作品", "本卡预设", "Regex 脚本"):
        if not page.get_by_text(legacy_label, exact=True).count():
            raise AssertionError(f"legacy workshop label is missing: {legacy_label}")

    summary = page.locator('textarea[x-model="form.summary"]')
    summary.fill("旧版工坊界面 · SillyTavern 数据保存验证")
    page.screenshot(
        path=str(artifact_dir / "workshop-desktop.png"),
        full_page=True,
    )

    page.locator("button.editor-toolbar__primary").click()
    publish_dialog = page.get_by_label("发布角色新版本")
    publish_dialog.wait_for(state="visible")
    publish_dialog.get_by_text("作者介绍 / 更新说明", exact=True).locator("..").locator("textarea").fill(
        "E2E 验证创作工坊保存时保留原生 SillyTavern 与未来扩展字段。"
    )
    with page.expect_response(
        lambda response: f"/console/api/web/my-apps/{app_id}/update" in response.url
        and response.request.method == "POST"
    ) as save_info, page.expect_response(
        lambda response: f"/console/api/web/card-versions/{app_id}" in response.url
        and response.request.method == "POST"
    ) as publish_info:
        publish_dialog.get_by_role("button", name="确认发布", exact=True).click()
    response = save_info.value
    if response.status != 200:
        raise AssertionError(f"workshop save failed: {response.status}")
    if publish_info.value.status != 200:
        raise AssertionError(f"workshop publish failed: {publish_info.value.status}")
    card = response.json()["data"]
    extensions = card["extensions"]
    scripts = extensions["tavern_helper"]["scripts"]
    if len(scripts) != 1 or scripts[0]["id"] != "seed-helper":
        raise AssertionError("hidden TavernHelper script was changed by a normal workshop save")
    if extensions["tavern_helper"]["variables"]["preserve"] is not True:
        raise AssertionError("TavernHelper sibling metadata was lost")
    if extensions["future_extension_probe"]["preserve"] != ["unknown", 3]:
        raise AssertionError("unknown card extension metadata was lost")

    exported_response = page.context.request.get(
        f"{base_url}/console/api/web/my-apps/{app_id}/export"
    )
    if exported_response.status != 200:
        raise AssertionError(f"card export failed: {exported_response.status}")
    exported_data = exported_response.json()["data"]["data"]
    if exported_data["extensions"]["tavern_helper"]["scripts"][0]["id"] != "seed-helper":
        raise AssertionError("native SillyTavern export lost the hidden card script")
    if exported_data["extensions"]["future_extension_probe"]["preserve"] != ["unknown", 3]:
        raise AssertionError("native SillyTavern export lost an unknown extension field")
    if exported_data["assets"][0]["type"] != "x_homer_e2e":
        raise AssertionError("native SillyTavern export lost a future card field")
    # Allow the workshop's debounced card-extra update to settle before the
    # test navigates to the next character.
    page.wait_for_timeout(1_000)


def verify_legacy_pages(page: Page, base_url: str, artifact_dir: Path, viewport: str) -> None:
    pages = (
        ("explore", "/app/explore.html"),
        ("favorites", "/app/favorites.html"),
        ("histories", "/app/histories.html"),
        ("my-apps", "/app/my-apps.html"),
    )
    for label, path in pages:
        goto(page, base_url + path)
        assert_no_overflow(page, f"{viewport} {label}")
        if label in ("explore", "my-apps"):
            page.screenshot(
                path=str(artifact_dir / f"{label}-{viewport}.png"),
                full_page=True,
            )


def main() -> int:
    config = json.loads((RUNTIME_DIR / "config.json").read_text(encoding="utf-8"))
    credentials = json.loads((RUNTIME_DIR / "credentials.json").read_text(encoding="utf-8"))
    base_url = str(config["base_url"]).rstrip("/")
    base_origin = f"{urlsplit(base_url).scheme}://{urlsplit(base_url).netloc}"
    dialogue_url = str(config["dialogue_url"]).rstrip("/")
    allowed_origins = (base_origin,)
    artifact_dir = Path(config["artifact_dir"])
    artifact_dir.mkdir(parents=True, exist_ok=True)
    extension_zip = artifact_dir / "browser-runtime-probe.zip"
    build_extension_package(extension_zip)
    app_id = str(config["app_id"])
    roleplayhub_app_id = str(config["roleplayhub_app_id"])
    results: list[dict] = []

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            desktop = browser.new_context(viewport={"width": 1440, "height": 900})
            desktop_page = desktop.new_page()
            stub_optional_memory_books_user_files(desktop_page)
            desktop_failures = monitor_page(desktop_page, allowed_origins)
            login(desktop_page, base_url, credentials)
            verify_legacy_pages(desktop_page, base_url, artifact_dir, "desktop")
            extension_id = install_extension_from_admin(desktop_page, base_url, extension_zip)
            loading_page = desktop.new_page()
            try:
                verify_unified_loading(
                    loading_page,
                    base_url,
                    dialogue_url,
                    app_id,
                    artifact_dir,
                )
            finally:
                loading_page.close()
            runtime = verify_chat_runtime(desktop_page, base_url, app_id)
            card_stage = verify_card_stage_runtime(
                desktop_page,
                base_url,
                artifact_dir,
                "desktop",
            )
            assert_no_inherited_brand(desktop_page, "desktop chat")
            assert_no_overflow(desktop_page, "desktop chat")
            desktop_page.screenshot(
                path=str(artifact_dir / "chat-desktop.png"),
                full_page=True,
            )
            verify_workshop(desktop_page, base_url, app_id, artifact_dir)
            assert_no_overflow(desktop_page, "desktop workshop")
            roleplayhub = verify_roleplayhub_runtime(
                desktop_page,
                base_url,
                roleplayhub_app_id,
                artifact_dir,
                "desktop",
            )
            assert_no_inherited_brand(desktop_page, "desktop RoleplayHub")
            assert_clean(desktop_failures, "desktop")
            results.append(
                {
                    "viewport": "desktop",
                    "extension_id": extension_id,
                    "runtime_conversation": bool(runtime.get("convId")),
                    "extension_js_css_hooks": "pass",
                    "card_script": "pass",
                    "runtime_persistence": "pass",
                    "legacy_non_chat_pages": "pass",
                    "workshop_legacy_ui_native_card_merge": "pass",
                    "unified_loading": "pass",
                    "card_stage": card_stage,
                    "roleplayhub": roleplayhub,
                    "console_errors": 0,
                    "page_errors": 0,
                    "network_errors": 0,
                }
            )
            desktop.close()

            mobile = browser.new_context(viewport={"width": 390, "height": 844})
            mobile_page = mobile.new_page()
            stub_optional_memory_books_user_files(mobile_page)
            mobile_failures = monitor_page(mobile_page, allowed_origins)
            login(mobile_page, base_url, credentials)
            verify_legacy_pages(mobile_page, base_url, artifact_dir, "mobile")
            goto(mobile_page, base_url + "/admin.html")
            mobile_page.locator(".xy-admin-mobilebar select").select_option("plugins")
            mobile_page.get_by_role("heading", name="对话扩展").wait_for(state="visible")
            assert_no_overflow(mobile_page, "mobile admin")

            goto(mobile_page, f"{base_url}/app/create.html?id={app_id}")
            mobile_page.get_by_text("世界书 / Lorebook", exact=True).wait_for(state="visible")
            if mobile_page.get_by_text("SillyTavern 卡内脚本", exact=True).count():
                raise AssertionError("mobile workshop exposed the removed card-script editor")
            assert_no_overflow(mobile_page, "mobile workshop")
            mobile_page.screenshot(
                path=str(artifact_dir / "workshop-mobile.png"),
                full_page=True,
            )

            verify_chat_runtime(
                mobile_page,
                base_url,
                app_id,
                card_marker="__cardHelperProbe",
            )
            card_stage_mobile = verify_card_stage_runtime(
                mobile_page,
                base_url,
                artifact_dir,
                "mobile",
            )
            assert_no_inherited_brand(mobile_page, "mobile chat")
            assert_no_overflow(mobile_page, "mobile chat")
            mobile_page.screenshot(
                path=str(artifact_dir / "chat-mobile.png"),
                full_page=True,
            )
            roleplayhub_mobile = verify_roleplayhub_runtime(
                mobile_page,
                base_url,
                roleplayhub_app_id,
                artifact_dir,
                "mobile",
            )
            assert_no_inherited_brand(mobile_page, "mobile RoleplayHub")
            assert_clean(mobile_failures, "mobile")
            results.append(
                {
                    "viewport": "mobile",
                    "admin_registry": "pass",
                    "legacy_non_chat_pages": "pass",
                    "workshop_responsive": "pass",
                    "chat_runtime": "pass",
                    "card_stage": card_stage_mobile,
                    "roleplayhub": roleplayhub_mobile,
                    "horizontal_overflow": False,
                    "console_errors": 0,
                    "page_errors": 0,
                    "network_errors": 0,
                }
            )
            mobile.close()
        finally:
            browser.close()

    print(json.dumps({"ok": True, "results": results}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
