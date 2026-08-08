"""Browser acceptance test for the Homer original-SillyTavern migration."""

from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import urlsplit

from playwright.sync_api import Frame, Page, TimeoutError as PlaywrightTimeoutError, sync_playwright


ROOT = Path(__file__).resolve().parents[1]
STATE_DIR = ROOT / "output" / "sillytavern-e2e"
RUNTIME_DIR = STATE_DIR / "runtime"


def monitor_page(page: Page, allowed_origins: set[str]) -> dict[str, list[str]]:
    failures: dict[str, list[str]] = {
        "console": [],
        "page": [],
        "request": [],
        "http": [],
        "yuzi": [],
    }
    page.on(
        "console",
        lambda message: failures["console"].append(message.text)
        if message.type == "error"
        else None,
    )
    page.on(
        "pageerror",
        lambda error: failures["page"].append(
            str(getattr(error, "stack", None) or error)
        ),
    )
    page.on(
        "requestfailed",
        lambda request: failures["request"].append(
            f"{request.method} {request.url}: {request.failure}"
        )
        if any(request.url.startswith(origin) for origin in allowed_origins)
        else None,
    )
    page.on(
        "response",
        lambda response: failures["http"].append(
            f"{response.status} {response.request.method} {response.url}"
        )
        if any(response.url.startswith(origin) for origin in allowed_origins)
        and response.status >= 400
        else None,
    )
    page.on(
        "request",
        lambda request: failures["yuzi"].append(request.url)
        if "st-yuzi-phone" in request.url.lower()
        and urlsplit(request.url).path.lower().endswith((".js", ".css"))
        else None,
    )
    return failures


def login(page: Page, base_url: str, credentials: dict) -> None:
    # Keep authentication setup on a neutral page. Returning to /app/ can
    # immediately reopen the account's previous chat; the test then navigates
    # to its newly-created conversation and would correctly abort that obsolete
    # iframe's requests, polluting the target page's console/network evidence.
    page.goto(
        base_url + "/app/login.html?next=%2Fapp%2Fexplore.html",
        wait_until="networkidle",
        timeout=30_000,
    )
    page.locator('input[type="email"]').first.fill(credentials["email"])
    page.locator('input[type="password"]').first.fill(credentials["password"])
    page.get_by_role("button", name="进入 惑梦（Homer）").click()
    page.wait_for_url(lambda url: "/app/login.html" not in url, timeout=20_000)
    try:
        page.wait_for_load_state("networkidle", timeout=8_000)
    except PlaywrightTimeoutError:
        page.wait_for_load_state("domcontentloaded", timeout=10_000)


def start_conversation(page: Page, base_url: str, app_id: str) -> str:
    response = page.context.request.post(
        base_url + "/console/api/web/conversations/start",
        data={"app_id": app_id},
    )
    if response.status != 200:
        raise AssertionError(f"conversation start failed: {response.status} {response.text()[:200]}")
    body = response.json()
    data = body.get("data", body)
    return str(data["conversation_id"])


def verify_internal_entry_guards(
    page: Page,
    base_url: str,
    dialogue_internal_url: str = "",
) -> None:
    direct = page.context.request.get(
        base_url + "/module/dialogue/",
        max_redirects=0,
    )
    if direct.status != 302 or direct.headers.get("location") != "/app/chat.html":
        raise AssertionError(
            f"direct dialogue-module navigation was not returned to the website shell: "
            f"{direct.status} {direct.headers.get('location')}"
        )
    legacy = page.context.request.get(
        base_url + "/dialogue-core/",
        max_redirects=0,
    )
    if legacy.status != 308 or legacy.headers.get("location") != "/module/dialogue/":
        raise AssertionError(
            f"legacy dialogue route was not reduced to a compatibility redirect: "
            f"{legacy.status} {legacy.headers.get('location')}"
        )
    if dialogue_internal_url:
        internal = page.context.request.get(
            dialogue_internal_url.rstrip("/") + "/",
            max_redirects=0,
        )
        expected = base_url + "/app/chat.html"
        if internal.status != 302 or internal.headers.get("location") != expected:
            raise AssertionError(
                "direct internal runtime origin remained user-facing: "
                f"{internal.status} {internal.headers.get('location')}"
            )


def assert_product_owned_surface(runtime: Frame) -> None:
    runtime.wait_for_function(
        "document.documentElement.classList.contains('homer-runtime-ready')",
        timeout=90_000,
    )
    exposed = runtime.evaluate(
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
            forbiddenText: forbidden.filter(text => visibleText.includes(text)),
            visibleInheritedControls,
            parkedSettings: document.querySelector('#top-settings-holder')?.parentElement?.id || '',
            ready: document.documentElement.classList.contains('homer-runtime-ready'),
          };
        }"""
    )
    if exposed["forbiddenText"] or exposed["visibleInheritedControls"]:
        raise AssertionError(
            "internal compatibility UI escaped into the product surface: "
            + json.dumps(exposed, ensure_ascii=False)
        )
    if exposed["parkedSettings"] != "homer-internal-parking":
        raise AssertionError(
            "inherited settings subtree was not parked behind the product surface: "
            + json.dumps(exposed, ensure_ascii=False)
        )


def launch_chat(page: Page, base_url: str, app_id: str, conversation_id: str) -> Frame:
    page.goto(
        f"{base_url}/app/chat.html?app_id={app_id}&conversation_id={conversation_id}",
        wait_until="commit",
        timeout=30_000,
    )
    page.wait_for_url(
        lambda url: url.startswith(base_url + "/app/chat.html")
        and f"app_id={app_id}" in url
        and f"conversation_id={conversation_id}" in url,
        timeout=30_000,
    )
    page.locator("#dialogue-frame").wait_for(state="attached", timeout=30_000)
    try:
        page.wait_for_function(
            "document.body.classList.contains('is-ready')",
            timeout=150_000,
        )
    except PlaywrightTimeoutError as error:
        diagnostic = page.evaluate(
            """() => ({
              url: location.pathname,
              classes: document.body?.className || '',
              detail: document.querySelector('#launcher-detail')?.textContent?.trim() || '',
              frameSrc: document.querySelector('#dialogue-frame')?.getAttribute('src')?.split('?')[0] || '',
            })"""
        )
        failed_runtime = page.frame(name="homer-dialogue-module")
        if failed_runtime is not None:
            try:
                diagnostic["runtime"] = failed_runtime.evaluate(
                    """() => ({
                      classes: document.body?.className || '',
                      ready: document.documentElement.classList.contains('homer-runtime-ready'),
                      characterId: window.SillyTavern?.getContext?.()?.characterId ?? null,
                      chatCount: window.SillyTavern?.getContext?.()?.chat?.length ?? null,
                    })"""
                )
            except Exception as runtime_error:
                diagnostic["runtime_error"] = str(runtime_error)[:500]
        raise AssertionError(
            "dialogue launch did not become ready: "
            + json.dumps(diagnostic, ensure_ascii=False)
        ) from error
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
    runtime.locator("#homer-preset-ball").wait_for(state="visible", timeout=90_000)
    runtime.wait_for_function(
        """() => {
          const context = window.SillyTavern?.getContext?.();
          return Boolean(context?.characters?.length && context?.chat?.length && context?.name2);
        }""",
        timeout=90_000,
    )
    exposed_urls = runtime.evaluate(
        """() => performance.getEntriesByType('resource')
          .map(item => item.name)
          .filter(name => name.includes('127.0.0.1:18091') || name.includes('/dialogue-core/'))"""
    )
    if exposed_urls:
        raise AssertionError(f"runtime network exposed an internal or legacy route: {exposed_urls[:8]}")
    visible_text = runtime.locator("body").inner_text()[:200_000]
    if "SillyTavern" in visible_text:
        raise AssertionError("dialogue UI exposed inherited product branding")
    assert_product_owned_surface(runtime)
    return runtime


def launch_card(page: Frame) -> dict:
    result = page.evaluate(
        """async () => {
          const query = new URLSearchParams(location.search);
          const response = await fetch('/api/homer/session?' + new URLSearchParams({
            app_id: query.get('homer_app_id'),
            conversation_id: query.get('homer_conversation_id'),
          }));
          const body = await response.json();
          return {
            status: response.status,
            card: body?.data?.launch?.card || body?.launch?.card || null,
          };
        }"""
    )
    if result["status"] != 200 or not isinstance(result.get("card"), dict):
        raise AssertionError(f"Homer launch card read failed: {result}")
    return result["card"]


def assert_generic_card_fidelity(page: Page) -> dict:
    card = launch_card(page)
    data = card.get("data") if isinstance(card.get("data"), dict) else {}
    extensions = data.get("extensions") if isinstance(data.get("extensions"), dict) else {}
    worldbook = data.get("character_book") if isinstance(data.get("character_book"), dict) else {}
    entries = worldbook.get("entries") if isinstance(worldbook.get("entries"), list) else []
    assets = data.get("assets") if isinstance(data.get("assets"), list) else []
    facts = {
        "spec": card.get("spec"),
        "spec_version": card.get("spec_version"),
        "future_extension_probe": extensions.get("future_extension_probe"),
        "future_world_field": (
            entries[0].get("extensions", {}).get("future_world_field")
            if entries and isinstance(entries[0], dict)
            else None
        ),
        "future_asset": assets[0] if assets else None,
        "regex_count": len(extensions.get("regex_scripts", [])),
        "script_count": len(extensions.get("tavern_helper", {}).get("scripts", [])),
    }
    expected = {
        "spec": "chara_card_v3",
        "spec_version": "3.0",
        "future_extension_probe": {"preserve": ["unknown", 3]},
        "future_world_field": {"preserve": True},
    }
    for key, value in expected.items():
        if facts[key] != value:
            raise AssertionError(
                "generic SillyTavern card lost an unknown field: "
                + json.dumps({"facts": facts, "expected": expected}, ensure_ascii=False)
            )
    if facts["future_asset"] != {
        "type": "x_homer_e2e",
        "uri": "embeded://future-asset",
        "name": "future",
        "ext": "bin",
    }:
        raise AssertionError(f"generic SillyTavern card lost an unknown asset: {facts}")
    page.wait_for_function("window.__cardHelperProbe === 'mounted'", timeout=30_000)
    return facts


def assert_complex_card_runtime(
    page: Page,
    base_url: str,
    app_id: str,
    artifact_dir: Path,
) -> dict:
    conversation_id = start_conversation(page, base_url, app_id)
    runtime = launch_chat(page, base_url, app_id, conversation_id)
    card = launch_card(runtime)
    data = card.get("data") if isinstance(card.get("data"), dict) else {}
    extensions = data.get("extensions") if isinstance(data.get("extensions"), dict) else {}
    worldbook = data.get("character_book") if isinstance(data.get("character_book"), dict) else {}
    counts = {
        "worldbook_entries": len(worldbook.get("entries", [])),
        "regex_scripts": len(extensions.get("regex_scripts", [])),
        "helper_scripts": len(extensions.get("tavern_helper", {}).get("scripts", [])),
    }
    expected = {"worldbook_entries": 307, "regex_scripts": 17, "helper_scripts": 3}
    if counts != expected:
        raise AssertionError(
            "complex card resources were not passed through intact: "
            + json.dumps({"actual": counts, "expected": expected}, ensure_ascii=False)
        )
    avatar_fidelity = runtime.evaluate(
        """async () => {
          const context = window.SillyTavern.getContext();
          const character = context.characters?.[context.characterId] || null;
          const coverUrl = String(
            character?.data?.extensions?.homer_cover_url
            || character?.data?.extensions?.homer_bridge?.cover_url
            || '',
          );
          const avatar = String(character?.avatar || '');
          const response = await fetch(`/characters/${encodeURIComponent(avatar)}`, {
            cache: 'no-store',
          });
          const blob = await response.blob();
          let width = 0;
          let height = 0;
          if (response.ok && blob.type.startsWith('image/')) {
            const bitmap = await createImageBitmap(blob);
            width = bitmap.width;
            height = bitmap.height;
            bitmap.close();
          }
          return {
            coverUrl,
            avatar,
            status: response.status,
            mime: blob.type,
            bytes: blob.size,
            width,
            height,
          };
        }"""
    )
    if (
        not avatar_fidelity["coverUrl"]
        or avatar_fidelity["status"] != 200
        or avatar_fidelity["mime"] != "image/png"
        or avatar_fidelity["bytes"] < 1_000_000
        or avatar_fidelity["width"] < 256
        or avatar_fidelity["height"] < 256
    ):
        raise AssertionError(
            "PNG role-card artwork was not preserved as the native SillyTavern avatar: "
            + json.dumps(avatar_fidelity, ensure_ascii=False)
        )
    runtime.wait_for_function("Boolean(window.TavernHelper)", timeout=45_000)
    for _ in range(5):
        if not dismiss_extension_notice(runtime):
            break
        runtime.wait_for_timeout(300)

    def open_panel() -> None:
        bubble = runtime.locator("#bp-switch-bubble")
        bubble.wait_for(state="visible", timeout=60_000)
        panel = runtime.locator("#bp-switch-panel")
        # The card assistant creates its bubble before its remotely imported
        # module has finished attaching the click handler. Retry during that
        # short first-run window instead of treating DOM presence as readiness.
        for _ in range(20):
            if panel.is_visible():
                return
            bubble.click()
            runtime.wait_for_timeout(750)
        raise AssertionError("card assistant bubble appeared but never became interactive")

    def runtime_worldbook() -> dict:
        return runtime.evaluate(
            """async () => {
              const context = window.SillyTavern.getContext();
              const character = context.characters?.[context.characterId] || null;
              const embedded = character?.data?.character_book || null;
              const names = window.TavernHelper.getWorldbookNames();
              const linked = await window.TavernHelper.getCharWorldbookNames('current');
              const entries = linked?.primary
                ? await window.TavernHelper.getWorldbook(linked.primary)
                : [];
              return {
                embeddedName: embedded?.name || null,
                embeddedCount: Array.isArray(embedded?.entries) ? embedded.entries.length : 0,
                names,
                primary: linked?.primary || null,
                runtimeCount: Array.isArray(entries) ? entries.length : 0,
                enabledSignature: Array.isArray(entries)
                  ? entries.filter(item => item.enabled).map(item => `${item.uid}:${item.name}`).join('|')
                  : '',
                selected: document.querySelector('#bp-wb-select')?.value || null,
                countText: document.querySelector('#bp-wb-count')?.textContent || '',
                panelText: document.querySelector('#bp-switch-panel')?.textContent || '',
              };
            }"""
        )

    open_panel()
    panel = runtime.locator("#bp-switch-panel")
    initial_worldbook = runtime_worldbook()
    if (
        not initial_worldbook["embeddedName"]
        or initial_worldbook["primary"] != initial_worldbook["embeddedName"]
        or initial_worldbook["selected"] != initial_worldbook["embeddedName"]
        or initial_worldbook["embeddedName"] not in initial_worldbook["names"]
        or initial_worldbook["runtimeCount"] != initial_worldbook["embeddedCount"]
    ):
        raise AssertionError(
            "embedded worldbook was not imported, linked, and selected through the universal pipeline: "
            + json.dumps(initial_worldbook, ensure_ascii=False)
        )
    if (
        "获取失败" in initial_worldbook["panelText"]
        or "获取条目失败" in initial_worldbook["panelText"]
        or f"检测到 {initial_worldbook['embeddedCount']}条" not in initial_worldbook["countText"]
    ):
        raise AssertionError(
            "card assistant could not read its active embedded worldbook: "
            + json.dumps(initial_worldbook, ensure_ascii=False)
        )
    prompt_template_loaded = runtime.evaluate(
        """() => [...document.scripts].some(
          item => item.src.includes('/third-party/ST-Prompt-Template/')
        )"""
    )
    if not prompt_template_loaded:
        raise AssertionError("bundled ST-Prompt-Template did not load")

    runtime.locator('#bp-mode-btns [data-mode="xml"]').click()
    runtime.wait_for_timeout(1_800)
    xml_worldbook = runtime_worldbook()
    if xml_worldbook["enabledSignature"] == initial_worldbook["enabledSignature"]:
        raise AssertionError("card assistant XML switch did not mutate the active worldbook")
    runtime.locator('#bp-mode-btns [data-mode="mvu"]').click()
    runtime.wait_for_timeout(1_800)
    restored_worldbook = runtime_worldbook()
    if restored_worldbook["enabledSignature"] != initial_worldbook["enabledSignature"]:
        raise AssertionError("card assistant MVU switch did not restore the active worldbook")

    if "配置最优" not in runtime.locator("#bp-ejs-status").inner_text():
        runtime.locator("#bp-ejs-optimize").click()
        runtime.wait_for_timeout(3_000)
        runtime = launch_chat(page, base_url, app_id, conversation_id)
        runtime.wait_for_function("Boolean(window.TavernHelper)", timeout=60_000)
        open_panel()
    if "配置运行正常" not in runtime.locator("#bp-config-status").inner_text():
        runtime.locator("#bp-mvu-optimize").click()
        # The card intentionally mounts its modal in the website host document
        # so it can cover the full conversation viewport rather than only the
        # embedded runtime frame.
        page.locator("#bp-confirm-overlay").wait_for(state="visible", timeout=15_000)
        # The card attaches mode-card handlers on the next task after mounting
        # the host-level dialog. A real user cannot click within that zero-delay
        # window, but Playwright can, so wait until the listener is attached.
        page.wait_for_timeout(150)
        page.locator("#bp-dlg-sui-card").click()
        page.locator("#bp-confirm-ok").click()
        runtime.wait_for_timeout(3_500)
        runtime = launch_chat(page, base_url, app_id, conversation_id)
        runtime.wait_for_function("Boolean(window.TavernHelper)", timeout=60_000)
        open_panel()
    configuration_status = runtime.locator("#bp-config-status").inner_text()
    if "配置运行正常" not in configuration_status:
        raise AssertionError(f"card assistant configuration controls failed: {configuration_status!r}")

    page.screenshot(
        path=str(artifact_dir / "original-sillytavern-complex-card.png"),
        full_page=True,
    )
    return {
        **counts,
        "card_artwork": {
            "status": "preserved",
            "bytes": avatar_fidelity["bytes"],
            "width": avatar_fidelity["width"],
            "height": avatar_fidelity["height"],
        },
        "card_floating_window": "visible-and-interactive",
        "active_worldbook": initial_worldbook["embeddedName"],
        "worldbook_runtime_entries": initial_worldbook["runtimeCount"],
        "worldbook_mode_switch": "mutated-and-restored",
        "prompt_template": "loaded-and-configurable",
        "configuration_status": configuration_status,
    }


def exercise_regular_user_permissions(page: Page) -> dict:
    if not page.evaluate(
        "document.body.classList.contains('homer-user') && "
        "!document.body.classList.contains('homer-admin')"
    ):
        raise AssertionError("regular Homer account did not receive the non-admin runtime role")
    extension_result = page.evaluate(
        """async () => {
          const context = window.SillyTavern.getContext();
          const response = await fetch('/api/extensions/install', {
            method: 'POST',
            headers: context.getRequestHeaders(),
            body: JSON.stringify({
              url: 'https://example.invalid/homer-permission-e2e.git',
              global: false,
            }),
          });
          return { status: response.status, body: await response.text() };
        }"""
    )
    if extension_result["status"] != 403:
        raise AssertionError(f"regular user extension install was not blocked: {extension_result}")

    worldbook_name = "Homer Permission E2E"
    worldbook_result = page.evaluate(
        """async (name) => {
          const created = await window.TavernHelper.createWorldbook(name);
          const afterCreate = window.TavernHelper.getWorldbookNames();
          const deleted = await window.TavernHelper.deleteWorldbook(name);
          const afterDelete = window.TavernHelper.getWorldbookNames();
          return {
            created,
            presentAfterCreate: afterCreate.includes(name),
            deleted,
            absentAfterDelete: !afterDelete.includes(name),
          };
        }""",
        worldbook_name,
    )
    if not all(
        (
            worldbook_result.get("created"),
            worldbook_result.get("presentAfterCreate"),
            worldbook_result.get("deleted"),
            worldbook_result.get("absentAfterDelete"),
        )
    ):
        raise AssertionError(f"regular user worldbook editing is unavailable: {worldbook_result}")
    hidden_admin_controls = page.evaluate(
        """() => {
          const ids = ['WIDrawerIcon', 'third_party_extension_button'];
          return Object.fromEntries(ids.map(id => {
            const element = document.getElementById(id);
            return [id, !element || getComputedStyle(element).display === 'none'];
          }));
        }"""
    )
    if not all(hidden_admin_controls.values()):
        raise AssertionError(f"raw administrator controls remain exposed: {hidden_admin_controls}")
    return {
        "extension_install_status": extension_result["status"],
        "worldbook_create_delete": "pass",
        "raw_admin_controls_hidden": hidden_admin_controls,
    }


def runtime_snapshot(page: Page) -> dict:
    return page.evaluate(
        """() => {
          const context = window.SillyTavern.getContext();
          const selected = context.characters?.[context.characterId] || null;
          return {
            url: location.href,
            hasTavernHelper: Boolean(window.TavernHelper),
            characterName: context.name2 || selected?.name || null,
            chatLength: context.chat?.length || 0,
            chatId: context.chatId || null,
            runtimeStatus: document.querySelector('#homer-runtime-status')?.textContent || '',
            extensionScripts: [...document.scripts].map(item => item.src).filter(Boolean),
            extensionResources: performance.getEntriesByType('resource')
              .map(item => item.name)
              .filter(name => name.includes('/extensions/')),
            disabledExtensions:
              window.SillyTavern?.getContext?.()?.extensionSettings?.disabledExtensions || [],
          };
        }"""
    )


def assert_no_overflow(page: Page, label: str) -> None:
    overflow = page.evaluate(
        "document.documentElement.scrollWidth > document.documentElement.clientWidth + 1"
    )
    if overflow:
        raise AssertionError(f"{label}: horizontal overflow")


def dismiss_extension_notice(page: Page | Frame) -> str:
    popup = page.locator("dialog.popup[open]").last
    if popup.count() and popup.is_visible():
        text = popup.inner_text()[:500]
        popup_id = popup.get_attribute("data-id")
        affirmative = popup.locator(".popup-button-ok:visible")
        if affirmative.count():
            affirmative.click()
        else:
            close = popup.locator(".popup-button-close:visible, .popup-button-cancel:visible").first
            if close.count():
                close.click()
            else:
                page.keyboard.press("Escape")
        if popup_id:
            page.locator(f'dialog[data-id="{popup_id}"]').wait_for(state="hidden", timeout=10_000)
        else:
            page.wait_for_timeout(400)
        return text

    # Bundled TavernHelper uses its own Vue modal instead of SillyTavern's
    # native dialog. A first-run/upgrade notice can otherwise cover the chat
    # composer even though the extension and character script loaded correctly.
    helper_popup = page.locator(".TH-popup[role='dialog']:visible").last
    if helper_popup.count() == 0:
        return ""
    text = helper_popup.inner_text()[:500]
    affirmative = helper_popup.locator(".popup-button-ok:visible").last
    if affirmative.count():
        affirmative.click()
    else:
        buttons = helper_popup.locator("button:visible")
        if buttons.count():
            buttons.last.click()
        else:
            page.locator("body").press("Escape")
    helper_popup.wait_for(state="hidden", timeout=10_000)
    return text


def exercise_preset_ui(page: Page, failures: dict[str, list[str]]) -> dict:
    page.wait_for_timeout(1_500)
    for _ in range(3):
        if not dismiss_extension_notice(page):
            break
        page.wait_for_timeout(300)
    page.locator("#homer-preset-ball").click()
    panel = page.locator("#homer-preset-panel")
    panel.wait_for(state="visible")
    group_labels = panel.locator(".homer-preset-group__copy strong").all_inner_texts()
    if group_labels != ["角色卡预设", "官方公开预设"]:
        raise AssertionError(f"preset groups are wrong: {group_labels}")
    page.get_by_role("button", name="展开全部条目").click()
    dialog = page.locator("#homer-preset-dialog")
    dialog.wait_for(state="visible")

    card_group = dialog.locator(".homer-preset-group").filter(has_text="角色卡预设")
    global_group = dialog.locator(".homer-preset-group").filter(has_text="官方公开预设")
    card_rows = card_group.locator(".homer-preset-row")
    global_rows = global_group.locator(".homer-preset-row")
    if card_rows.count() != 5:
        raise AssertionError(f"card preset did not show all entries: {card_rows.count()}")
    if global_rows.count() != 3:
        raise AssertionError(f"global preset visibility filter is wrong: {global_rows.count()}")
    visible_text = dialog.inner_text()
    if "官方后台隐藏条目" in visible_text:
        raise AssertionError("hidden official prompt entry leaked into the user panel")
    if "HOMER_CARD_" in visible_text or "HOMER_GLOBAL_" in visible_text:
        raise AssertionError("prompt body sentinel leaked into the user panel")

    card_marker = card_rows.filter(has_text="卡片结构条目")
    card_unlisted = card_rows.filter(has_text="卡片未进顺序条目")
    global_marker = global_rows.filter(has_text="官方公开结构条目")
    for label, row in (
        ("card marker", card_marker),
        ("card unlisted", card_unlisted),
        ("global marker", global_marker),
    ):
        if row.locator('input[type="checkbox"]').count() != 0:
            raise AssertionError(f"{label} unexpectedly remained toggleable")

    def read_config() -> dict:
        state = page.evaluate(
            """async () => {
              const query = new URLSearchParams(location.search);
              const conversationId = query.get('homer_conversation_id');
              const response = await fetch(
                `/api/homer/conversations/${encodeURIComponent(conversationId)}/runtime-config`,
              );
              return { status: response.status, body: await response.json() };
            }"""
        )
        if state["status"] != 200:
            raise AssertionError(f"preset runtime config read failed: {state}")
        return state["body"].get("data", state["body"])

    before_config = read_config()
    prompt_projection = before_config.get("preset", {})
    prompt_entries = (
        prompt_projection.get("card_prompt", {}).get("entries", [])
        + prompt_projection.get("global_prompt", {}).get("entries", [])
    )
    if any("content" in entry for entry in prompt_entries):
        raise AssertionError("runtime prompt projection exposed prompt content")
    serialized_projection = json.dumps(prompt_projection, ensure_ascii=False)
    if "HOMER_CARD_" in serialized_projection or "HOMER_GLOBAL_" in serialized_projection:
        raise AssertionError("runtime prompt projection exposed prompt sentinels")

    card_target = card_rows.filter(has_text="卡片条目默认关闭")
    global_target = global_rows.filter(has_text="官方公开默认开启")
    card_before = card_target.locator('input[type="checkbox"]').is_checked()
    global_before = global_target.locator('input[type="checkbox"]').is_checked()
    if card_before is not False or global_before is not True:
        raise AssertionError(
            f"unexpected preset defaults: card={card_before}, global={global_before}"
        )
    card_target.locator(".homer-switch__track").click()
    page.wait_for_function(
        """async () => {
          const query = new URLSearchParams(location.search);
          const conversationId = query.get('homer_conversation_id');
          const response = await fetch(
            `/api/homer/conversations/${encodeURIComponent(conversationId)}/runtime-config`,
          );
          if (!response.ok) return false;
          const body = await response.json();
          const config = body?.data || body;
          const card = config?.preset?.card_prompt?.entries || [];
          return card.find(item => item.id === 'card-visible-off')?.enabled === true;
        }""",
        timeout=15_000,
    )
    global_target = dialog.locator(".homer-preset-group").filter(
        has_text="官方公开预设"
    ).locator(".homer-preset-row").filter(has_text="官方公开默认开启")
    global_target.locator(".homer-switch__track").click()
    page.wait_for_function(
        """async () => {
          const query = new URLSearchParams(location.search);
          const conversationId = query.get('homer_conversation_id');
          const response = await fetch(
            `/api/homer/conversations/${encodeURIComponent(conversationId)}/runtime-config`,
          );
          if (!response.ok) return false;
          const body = await response.json();
          const config = body?.data || body;
          const global = config?.preset?.global_prompt?.entries || [];
          return global.find(item => item.id === 'global-visible-on')?.enabled === false;
        }""",
        timeout=15_000,
    )
    after_config = read_config()
    after_card = next(
        item
        for item in after_config["preset"]["card_prompt"]["entries"]
        if item["id"] == "card-visible-off"
    )
    after_global = next(
        item
        for item in after_config["preset"]["global_prompt"]["entries"]
        if item["id"] == "global-visible-on"
    )
    if not after_card.get("overridden") or not after_global.get("overridden"):
        raise AssertionError(
            "preset override status did not refresh: "
            + json.dumps({"card": after_card, "global": after_global}, ensure_ascii=False)
        )
    page.get_by_role("button", name="关闭全部条目").click()
    return {
        "card_rows": card_rows.count(),
        "global_rows": global_rows.count(),
        "locked_rows": 3,
        "prompt_body_redacted": True,
        "card_toggle": {"before": card_before, "after": after_card["enabled"]},
        "global_toggle": {"before": global_before, "after": after_global["enabled"]},
    }


def exercise_admin_prompt_visibility_control(
    page: Page,
    base_url: str,
    artifact_dir: Path,
) -> dict:
    page.goto(base_url + "/admin.html", wait_until="domcontentloaded", timeout=30_000)
    page.get_by_role("button", name="全局预设").wait_for(state="visible", timeout=30_000)
    page.get_by_role("button", name="全局预设").click()
    page.get_by_role("heading", name="全局预设").wait_for(state="visible", timeout=30_000)
    page.get_by_text("惑梦 E2E 官方公开预设", exact=True).first.wait_for(
        state="visible",
        timeout=30_000,
    )

    def hidden_entry():
        return page.locator("details").filter(has_text="官方后台隐藏条目")

    def open_hidden_entry():
        entry = hidden_entry()
        entry.wait_for(state="visible", timeout=15_000)
        if not entry.evaluate("element => element.open"):
            entry.locator(":scope > summary").click()
        return entry

    def hidden_checkbox():
        return open_hidden_entry().locator("label").filter(
            has_text="向用户显示并允许开关"
        ).locator('input[type="checkbox"]')

    controls = page.locator("label").filter(has_text="向用户显示并允许开关")
    if controls.count() != 5:
        raise AssertionError(f"admin prompt visibility controls are incomplete: {controls.count()}")
    checkbox = hidden_checkbox()
    if checkbox.is_checked():
        raise AssertionError("historically hidden prompt unexpectedly defaulted to user-visible")

    checkbox.check()
    page.get_by_role("button", name="保存全部修改").click()
    page.wait_for_function(
        """async () => {
          const response = await fetch('/admin/api/global-presets');
          if (!response.ok) return false;
          const body = await response.json();
          const data = body?.data || body;
          const activeId = data?.prompt?.active_id;
          const preset = (data?.prompt?.items || []).find(item => item.id === activeId);
          return preset?.prompts?.find(item => item.identifier === 'global-hidden')?.user_toggleable === true;
        }""",
        timeout=15_000,
    )
    if not hidden_checkbox().is_checked():
        raise AssertionError("admin visibility checkbox did not survive the save/reload round trip")
    page.screenshot(
        path=str(artifact_dir / "admin-global-preset-user-toggleable.png"),
        full_page=True,
    )

    hidden_checkbox().uncheck()
    page.get_by_role("button", name="保存全部修改").click()
    page.wait_for_function(
        """async () => {
          const response = await fetch('/admin/api/global-presets');
          if (!response.ok) return false;
          const body = await response.json();
          const data = body?.data || body;
          const activeId = data?.prompt?.active_id;
          const preset = (data?.prompt?.items || []).find(item => item.id === activeId);
          return preset?.prompts?.find(item => item.identifier === 'global-hidden')?.user_toggleable === false;
        }""",
        timeout=15_000,
    )
    assert_no_overflow(page, "admin global preset")
    return {
        "prompt_entries": controls.count(),
        "default_hidden": True,
        "save_round_trip": True,
        "restored_hidden": True,
    }


def persist_extension_settings_probe(page: Page) -> dict:
    result = page.evaluate(
        """async () => {
          const context = window.SillyTavern.getContext();
          const key = 'homer-e2e-persistence-probe';
          const value = {
            enabled: true,
            nested: { marker: 'conversation-only', count: 17 },
          };
          context.extensionSettings[key] = value;
          const pending = context.saveSettingsDebounced();
          const awaitable = Boolean(pending && typeof pending.then === 'function');
          await pending;
          const query = new URLSearchParams(location.search);
          const response = await fetch('/api/homer/runtime-state?' + new URLSearchParams({
            app_id: query.get('homer_app_id'),
            conversation_id: query.get('homer_conversation_id'),
          }));
          const body = await response.json();
          const state = body?.data || body;
          return {
            awaitable,
            status: response.status,
            saved: state?.extension_settings?.[key] || null,
          };
        }"""
    )
    if (
        not result.get("awaitable")
        or result.get("status") != 200
        or result.get("saved", {}).get("nested", {}).get("marker") != "conversation-only"
    ):
        raise AssertionError(
            "extension settings were not durably saved before an immediate refresh: "
            + json.dumps(result, ensure_ascii=False)
        )
    return result


def assert_extension_settings_probe_restored(page: Page) -> None:
    restored = page.evaluate(
        """() => window.SillyTavern.getContext()
          .extensionSettings?.['homer-e2e-persistence-probe'] || null"""
    )
    if restored is None or restored.get("nested", {}).get("count") != 17:
        raise AssertionError(
            "conversation extension settings did not survive a full runtime refresh: "
            + json.dumps(restored, ensure_ascii=False)
        )


def exercise_keyword_injector(page: Page | Frame) -> dict:
    root = page.locator("#homer-keyword-injector")
    root.wait_for(state="visible", timeout=30_000)
    page.locator("[data-keyword-open]").click()
    panel = page.locator("[data-keyword-panel]")
    panel.wait_for(state="visible", timeout=10_000)

    options = panel.locator("[data-keyword-option]")
    if options.count() != 3:
        raise AssertionError(f"keyword injector exposed the wrong option count: {options.count()}")
    for index in range(options.count()):
        option = options.nth(index)
        if option.get_attribute("aria-pressed") != "true":
            option.click()
    panel.locator("[data-keyword-confirm]").click()
    panel.wait_for(state="hidden", timeout=10_000)
    page.wait_for_function(
        """async () => {
          const query = new URLSearchParams(location.search);
          const response = await fetch('/api/homer/runtime-state?' + new URLSearchParams({
            app_id: query.get('homer_app_id'),
            conversation_id: query.get('homer_conversation_id'),
          }));
          const body = await response.json();
          const value = (body?.data || body)?.extension_settings?.homer_keyword_injector;
          return response.ok
            && value?.enabled === true
            && JSON.stringify(value?.selected || []) === JSON.stringify(['status', 'characters', 'live']);
        }""",
        timeout=15_000,
    )

    before = page.evaluate(
        """() => ({
          chatLength: window.SillyTavern.getContext().chat.length,
          busy: document.body.classList.contains('homer-generating'),
        })"""
    )
    page.locator("#send_textarea").fill("HOMER_KEYWORD_INJECTOR_PROBE")
    page.evaluate(
        """() => {
          window.__homerKeywordInjectorProbe = null;
          const blocker = event => {
            if (!(event.target instanceof Element) || !event.target.closest('#send_but')) return;
            window.__homerKeywordInjectorProbe = {
              value: document.querySelector('#send_textarea')?.value || '',
              chatLength: window.SillyTavern.getContext().chat.length,
              busy: document.body.classList.contains('homer-generating'),
            };
            event.preventDefault();
            event.stopImmediatePropagation();
            document.removeEventListener('click', blocker, true);
          };
          document.addEventListener('click', blocker, true);
        }"""
    )
    page.locator("#send_but").click()
    page.wait_for_function("Boolean(window.__homerKeywordInjectorProbe)", timeout=5_000)
    probe = page.evaluate("window.__homerKeywordInjectorProbe")
    expected = "HOMER_KEYWORD_INJECTOR_PROBE\n【状态栏】【角色开始】【Live】"
    if probe.get("value") != expected:
        raise AssertionError(
            "keyword injector did not augment the composer in the configured order: "
            + json.dumps(probe, ensure_ascii=False)
        )
    if probe.get("chatLength") != before["chatLength"] or probe.get("busy") != before["busy"]:
        raise AssertionError(
            "non-generating keyword probe unexpectedly changed the conversation: "
            + json.dumps({"before": before, "after": probe}, ensure_ascii=False)
        )
    page.locator("#send_textarea").fill("")
    return {
        "panel": "pass",
        "selected": ["status", "characters", "live"],
        "composer_value": expected,
        "generation_suppressed_for_probe": True,
    }


def assert_keyword_injector_restored(page: Page | Frame) -> None:
    restored = page.evaluate(
        """() => window.SillyTavern.getContext()
          .extensionSettings?.homer_keyword_injector || null"""
    )
    if (
        restored is None
        or restored.get("enabled") is not True
        or restored.get("selected") != ["status", "characters", "live"]
    ):
        raise AssertionError(
            "keyword injector settings did not survive a full runtime refresh: "
            + json.dumps(restored, ensure_ascii=False)
        )
    root = page.locator("#homer-keyword-injector")
    root.wait_for(state="visible", timeout=15_000)
    if "is-enabled" not in (root.get_attribute("class") or "").split():
        raise AssertionError("keyword injector UI did not restore its enabled state")


def assert_clean(failures: dict[str, list[str]], label: str) -> None:
    ignored_fragments = (
        "favicon",
        "Failed to load resource: the server responded with a status of 404",
        "Blocked attempt to show a 'beforeunload' confirmation panel for a frame that never had a user gesture",
        # SillyTavern's debounced autocomplete positioning may run once while
        # the old document is being destroyed during a deliberate full-page
        # launcher navigation. These stacks belong to the page being replaced.
        "AutoComplete.updateFloatingPosition",
        "AutoComplete.getCursorPosition",
        "cannot call methods on autocomplete prior to initialization",
    )

    def is_ignored(item: str) -> bool:
        if any(fragment in item for fragment in ignored_fragments):
            return True
        # MemoryBooks probes its own per-user JSON files on first run. A
        # missing file is the expected signal to create and upload defaults;
        # only that exact GET 404 is non-actionable. Other statuses still fail.
        return (
            item.startswith("404 GET ")
            and "/module/dialogue/user/files/stmb-" in item
            and item.endswith(".json")
        )

    cleaned = {
        key: [item for item in values if not is_ignored(item)]
        for key, values in failures.items()
    }
    # A deliberate page navigation cancels in-flight requests from the page
    # being replaced. Playwright reports those as request failures even though
    # the destination runtime loaded successfully.
    cleaned["request"] = [
        item for item in cleaned["request"] if "net::ERR_ABORTED" not in item
    ]
    populated = {key: values for key, values in cleaned.items() if values}
    if populated:
        raise AssertionError(f"{label}: browser failures: {json.dumps(populated, ensure_ascii=False)}")


def remove_expected_permission_denial(failures: dict[str, list[str]]) -> None:
    failures["http"] = [
        item
        for item in failures["http"]
        if not ("403 POST" in item and "/api/extensions/install" in item)
    ]
    failures["console"] = [
        item
        for item in failures["console"]
        if "status of 403" not in item
    ]


def verify_current_tokenizer(page: Page) -> None:
    result = page.evaluate(
        """async () => {
          const context = window.SillyTavern.getContext();
          const response = await fetch('/api/tokenizers/openai/count?model=homer-cloud', {
            method: 'POST',
            headers: context.getRequestHeaders(),
            body: JSON.stringify([{ role: 'user', content: 'Homer tokenizer probe' }]),
          });
          return { status: response.status, body: await response.text() };
        }"""
    )
    if result["status"] != 200:
        raise AssertionError(f"current SillyTavern tokenizer failed: {result}")


def exercise_generation_and_actions(
    page: Page,
    base_url: str,
    conversation_id: str,
) -> dict:
    connection = page.evaluate(
        """() => ({
          shells: document.querySelectorAll('#sheld').length,
          textareas: document.querySelectorAll('#send_textarea').length,
          placeholder: document.querySelector('#send_textarea')?.placeholder || '',
          chatLength: window.SillyTavern.getContext().chat.length,
        })"""
    )
    if connection["shells"] != 1 or connection["textareas"] != 1:
        raise AssertionError(f"duplicate SillyTavern chat shells remain: {connection}")
    if "未连接" in connection["placeholder"] or "Not connected" in connection["placeholder"]:
        raise AssertionError(f"Homer model bridge is not connected: {connection}")

    for _ in range(5):
        if not dismiss_extension_notice(page):
            break
        page.wait_for_timeout(300)
    page.locator("#send_textarea").fill("HOMER_E2E_GENERATION_PROBE")
    page.locator("#send_but").click()
    try:
        page.wait_for_function(
            """minimum => {
              const context = window.SillyTavern.getContext();
              const last = context.chat.at(-1);
              return context.chat.length >= minimum
                && last && !last.is_user && !last.is_system
                && !document.body.classList.contains('homer-generating');
            }""",
            arg=connection["chatLength"] + 2,
            timeout=45_000,
        )
    except PlaywrightTimeoutError as error:
        state = page.evaluate(
            """() => ({
              length: window.SillyTavern.getContext().chat.length,
              last: window.SillyTavern.getContext().chat.at(-1),
              busy: document.body.classList.contains('homer-generating'),
            })"""
        )
        raise AssertionError(f"initial generation did not settle: {state}") from error

    def signature() -> dict:
        return page.evaluate(
            """() => {
              const context = window.SillyTavern.getContext();
              const last = context.chat.at(-1);
              return {
                length: context.chat.length,
                text: String(last?.mes || ''),
                sendDate: String(last?.send_date || ''),
                genStarted: String(last?.gen_started || ''),
                genFinished: String(last?.gen_finished || ''),
                swipes: Array.isArray(last?.swipes) ? last.swipes.length : 0,
                swipe: Number(last?.swipe_id || 0),
                isAssistant: Boolean(last && !last.is_user && !last.is_system),
              };
            }"""
        )

    generated = signature()
    if not generated["isAssistant"] or not generated["text"].strip():
        raise AssertionError(f"SillyTavern generation returned no assistant message: {generated}")

    bindings = page.evaluate(
        """() => [...document.querySelectorAll('#chat .mes')].map(element => ({
          messageIndex: Number(element.getAttribute('mesid')),
          isUser: element.getAttribute('is_user') === 'true',
          isSystem: element.getAttribute('is_system') === 'true',
          barIndex: Number(element.querySelector('.homer-message-actions')?.dataset.messageIndex),
          actions: [...element.querySelectorAll('[data-homer-message-action]')]
            .map(button => button.dataset.homerMessageAction),
        }))"""
    )
    for binding in bindings:
        if binding["isSystem"]:
            if binding["actions"]:
                raise AssertionError(f"system message exposed actions: {binding}")
            continue
        if binding["barIndex"] != binding["messageIndex"]:
            raise AssertionError(f"message action bar is bound to the wrong message: {binding}")
        expected = ["rewind"] if binding["isUser"] else [
            "rewind", "continue", "regenerate", "next", "swipe-left", "swipe-right",
        ]
        if binding["actions"] != expected:
            raise AssertionError(f"message actions are incomplete: {binding}")

    action_results: list[dict] = []
    for action in ("continue", "regenerate", "next"):
        before = signature()
        for _ in range(3):
            if not dismiss_extension_notice(page):
                break
            page.wait_for_timeout(200)
        page.locator(
            '#chat .mes:not([is_user="true"]):not([is_system="true"]) '
            f'[data-homer-message-action="{action}"]'
        ).last.click()
        try:
            page.wait_for_function(
                """before => {
                  const context = window.SillyTavern.getContext();
                  const last = context.chat.at(-1);
                  const current = {
                    length: context.chat.length,
                    text: String(last?.mes || ''),
                    sendDate: String(last?.send_date || ''),
                    genStarted: String(last?.gen_started || ''),
                    genFinished: String(last?.gen_finished || ''),
                    swipes: Array.isArray(last?.swipes) ? last.swipes.length : 0,
                    swipe: Number(last?.swipe_id || 0),
                  };
                  const changed = JSON.stringify(current) !== JSON.stringify({
                    length: before.length,
                    text: before.text,
                    sendDate: before.sendDate,
                    genStarted: before.genStarted,
                    genFinished: before.genFinished,
                    swipes: before.swipes,
                    swipe: before.swipe,
                  });
                  return changed && last && !last.is_user && !last.is_system
                    && !document.body.classList.contains('homer-generating');
                }""",
                arg=before,
                timeout=45_000,
            )
        except PlaywrightTimeoutError as error:
            state = signature()
            state["busy"] = page.locator("body").evaluate(
                "body => body.classList.contains('homer-generating')"
            )
            raise AssertionError(
                f"message {action} did not settle: before={before}, after={state}"
            ) from error
        page.wait_for_timeout(500)
        after = signature()
        if not after["isAssistant"] or not after["text"].strip():
            raise AssertionError(
                f"message {action} did not finish with an assistant message: {after}"
            )
        action_results.append({"action": f"message-{action}", "result": "generated"})

    page.wait_for_function(
        "() => document.querySelector('#homer-runtime-status')?.textContent?.includes('云端已同步')",
        timeout=15_000,
    )
    cloud = page.evaluate(
        """async ({ baseUrl, conversationId }) => {
          const response = await fetch(
            `${baseUrl}/console/api/web/conversations/${encodeURIComponent(conversationId)}/messages?limit=200`,
            { credentials: 'include' },
          );
          return { status: response.status, body: await response.json() };
        }""",
        {"baseUrl": base_url, "conversationId": conversation_id},
    )
    cloud_data = cloud["body"].get("data", cloud["body"])
    final_chat = page.evaluate(
        """() => {
          const chat = window.SillyTavern.getContext().chat;
          return {
            length: chat.length,
            lastRole: chat.at(-1)?.is_user ? 'user' : chat.at(-1)?.is_system ? 'system' : 'assistant',
          };
        }"""
    )
    if (
        cloud["status"] != 200
        or cloud_data.get("total") != final_chat["length"]
        or not cloud_data.get("list")
        or cloud_data["list"][-1].get("role") != final_chat["lastRole"]
    ):
        raise AssertionError(
            "generated SillyTavern chat did not synchronize to Homer cloud storage: "
            + json.dumps({"cloud": cloud, "chat": final_chat}, ensure_ascii=False)
        )
    return {
        "connection": "homer-cloud",
        "send": "generated",
        "actions": action_results,
        "cloud_messages": cloud_data["total"],
    }


def exercise_realtime_rollback(
    host_page: Page,
    runtime: Frame,
    base_url: str,
    conversation_id: str,
) -> dict:
    before_count = runtime.locator("#chat .mes").count()
    if before_count < 1:
        raise AssertionError("rollback fixture did not contain a cloud message")
    original_url = host_page.url
    navigation_count = host_page.evaluate(
        "performance.getEntriesByType('navigation').length"
    )
    host_page.evaluate("window.__homerRollbackSentinel = 'host-alive'")
    runtime.evaluate("window.__homerRollbackSentinel = 'frame-alive'")

    target = runtime.locator("#chat .mes").first
    target.locator(".extraMesButtonsHint").click(force=True)
    rollback = target.locator(".homer-message-rollback")
    rollback.wait_for(state="visible", timeout=10_000)
    rollback.click()
    runtime.locator("#homer-rollback-dialog[open]").wait_for(
        state="visible", timeout=10_000,
    )
    runtime.locator(
        '#homer-rollback-dialog button[value="confirm"]'
    ).click()
    runtime.wait_for_function(
        "() => document.querySelectorAll('#chat .mes').length === 0",
        timeout=15_000,
    )

    cloud = host_page.context.request.get(
        f"{base_url}/console/api/web/conversations/{conversation_id}/messages?limit=200"
    )
    cloud_body = cloud.json()
    cloud_data = cloud_body.get("data", cloud_body)
    state = {
        "before": before_count,
        "after": runtime.locator("#chat .mes").count(),
        "cloud": cloud_data.get("total"),
        "url": host_page.url,
        "navigationCount": host_page.evaluate(
            "performance.getEntriesByType('navigation').length"
        ),
        "hostSentinel": host_page.evaluate("window.__homerRollbackSentinel"),
        "frameSentinel": runtime.evaluate("window.__homerRollbackSentinel"),
        "hostReady": host_page.locator("body").evaluate(
            "body => body.classList.contains('is-ready')"
        ),
    }
    if (
        cloud.status != 200
        or state["after"] != 0
        or state["cloud"] != 0
        or state["url"] != original_url
        or state["navigationCount"] != navigation_count
        or state["hostSentinel"] != "host-alive"
        or state["frameSentinel"] != "frame-alive"
        or not state["hostReady"]
    ):
        raise AssertionError(
            "rollback did not update the current page and cloud in real time: "
            + json.dumps(state, ensure_ascii=False)
        )
    return {
        "messages_before": before_count,
        "messages_after": state["after"],
        "cloud_messages": state["cloud"],
        "document_reload": False,
    }


def main() -> int:
    config = json.loads((RUNTIME_DIR / "config.json").read_text(encoding="utf-8"))
    credentials = json.loads((RUNTIME_DIR / "credentials.json").read_text(encoding="utf-8"))
    base_url = str(config["base_url"]).rstrip("/")
    dialogue_internal_url = str(config.get("dialogue_internal_url") or "").rstrip("/")
    app_id = str(config["app_id"])
    complex_app_id = str(config.get("dao_app_id") or "")
    artifact_dir = Path(config["artifact_dir"])
    artifact_dir.mkdir(parents=True, exist_ok=True)
    allowed_origins = {f"{urlsplit(base_url).scheme}://{urlsplit(base_url).netloc}"}
    results: list[dict] = []

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            desktop = browser.new_context(viewport={"width": 1440, "height": 900})
            desktop_page = desktop.new_page()
            desktop_failures = monitor_page(desktop_page, allowed_origins)
            login(desktop_page, base_url, credentials)
            verify_internal_entry_guards(
                desktop_page,
                base_url,
                dialogue_internal_url,
            )
            first_conversation = start_conversation(desktop_page, base_url, app_id)
            second_conversation = start_conversation(desktop_page, base_url, app_id)
            desktop_runtime = launch_chat(desktop_page, base_url, app_id, first_conversation)
            try:
                desktop_runtime.wait_for_function("Boolean(window.TavernHelper)", timeout=30_000)
            except PlaywrightTimeoutError:
                pass
            snapshot = runtime_snapshot(desktop_runtime)
            if not snapshot["hasTavernHelper"]:
                raise AssertionError(
                    "bundled TavernHelper did not load: "
                    + json.dumps(
                        {"snapshot": snapshot, "browser": desktop_failures},
                        ensure_ascii=False,
                    )
                )
            extension_notice = dismiss_extension_notice(desktop_runtime)
            if snapshot["characterName"] != "惑梦 E2E 角色":
                raise AssertionError(f"wrong imported character: {snapshot['characterName']!r}")
            generic_fidelity = assert_generic_card_fidelity(desktop_runtime)
            preset = exercise_preset_ui(desktop_runtime, desktop_failures)
            keyword_injector = exercise_keyword_injector(desktop_runtime)
            extension_settings_persistence = persist_extension_settings_probe(desktop_runtime)
            desktop_runtime = launch_chat(desktop_page, base_url, app_id, first_conversation)
            assert_extension_settings_probe_restored(desktop_runtime)
            assert_keyword_injector_restored(desktop_runtime)
            if desktop_runtime.locator(".homer-action-dock, .homer-action-button").count():
                raise AssertionError("removed global action dock is still present")
            verify_current_tokenizer(desktop_runtime)
            generation = exercise_generation_and_actions(
                desktop_runtime,
                base_url,
                first_conversation,
            )
            assert_no_overflow(desktop_runtime, "desktop dialogue frame")
            assert_no_overflow(desktop_page, "desktop")
            desktop_page.screenshot(
                path=str(artifact_dir / "original-sillytavern-desktop.png"),
                full_page=True,
            )

            second_runtime = launch_chat(desktop_page, base_url, app_id, second_conversation)
            verify_current_tokenizer(second_runtime)
            second_state = second_runtime.evaluate(
                """async () => {
                  const query = new URLSearchParams(location.search);
                  const conversationId = query.get('homer_conversation_id');
                  const response = await fetch(
                    `/api/homer/conversations/${encodeURIComponent(conversationId)}/runtime-config`,
                  );
                  const body = await response.json();
                  const runtimeConfig = body?.data || body;
                  return {
                    status: response.status,
                    preset: runtimeConfig?.preset || {},
                    extensionProbe: window.SillyTavern.getContext()
                      .extensionSettings?.['homer-e2e-persistence-probe'] || null,
                    keywordInjector: window.SillyTavern.getContext()
                      .extensionSettings?.homer_keyword_injector || null,
                  };
                }"""
            )
            if second_state["status"] != 200:
                raise AssertionError(
                    f"second conversation runtime config failed: {second_state}"
                )
            second_card = next(
                item
                for item in second_state["preset"]["card_prompt"]["entries"]
                if item["id"] == "card-visible-off"
            )
            second_global = next(
                item
                for item in second_state["preset"]["global_prompt"]["entries"]
                if item["id"] == "global-visible-on"
            )
            if (
                second_card.get("enabled") is not False
                or second_card.get("overridden")
                or second_global.get("enabled") is not True
                or second_global.get("overridden")
            ):
                raise AssertionError(
                    "preset overrides leaked into a new conversation: "
                    + json.dumps(
                        {"card": second_card, "global": second_global},
                        ensure_ascii=False,
                    )
                )
            if second_state["extensionProbe"] is not None:
                raise AssertionError(
                    f"extension settings leaked into a new conversation: {second_state['extensionProbe']}"
                )
            second_keyword = second_state.get("keywordInjector") or {}
            if second_keyword.get("enabled") is True or any(
                item in set(second_keyword.get("selected") or []) for item in ("characters", "live")
            ):
                raise AssertionError(
                    "keyword injector settings leaked into a new conversation: "
                    + json.dumps(second_keyword, ensure_ascii=False)
                )
            realtime_rollback = exercise_realtime_rollback(
                desktop_page,
                second_runtime,
                base_url,
                second_conversation,
            )
            assert_clean(desktop_failures, "desktop")
            results.append(
                {
                    "viewport": "desktop",
                    "original_runtime": "1.18.0",
                    "tavern_helper": "loaded",
                    "cloud_card_import": "pass",
                    "v3_unknown_field_round_trip": "pass",
                    "card_script_execution": "pass",
                    "cloud_chat_load": "pass",
                    "preset_quick_panel": "pass",
                    "preset_expanded_dialog": "pass",
                    "preset_scope": "conversation-only",
                    "extension_settings_persistence": extension_settings_persistence,
                    "extension_settings_scope": "conversation-only",
                    "keyword_injector": keyword_injector,
                    "keyword_injector_scope": "conversation-only",
                    "action_dock": "removed",
                    "yuzi_phone_asset_requests": len(desktop_failures["yuzi"]),
                    "generation": generation,
                    "realtime_rollback": realtime_rollback,
                    "extension_notice": bool(extension_notice),
                    "generic_fidelity": generic_fidelity,
                    "preset": preset,
                }
            )

            if complex_app_id:
                complex_result = assert_complex_card_runtime(
                    desktop_page,
                    base_url,
                    complex_app_id,
                    artifact_dir,
                )
                assert_clean(desktop_failures, "desktop complex card")
                results.append(
                    {
                        "viewport": "desktop",
                        "fixture": "high-complexity SillyTavern card",
                        "universal_pipeline": "pass",
                        **complex_result,
                    }
                )
            else:
                results.append(
                    {
                        "viewport": "desktop",
                        "fixture": "high-complexity SillyTavern card",
                        "universal_pipeline": "skipped: fixture not provided",
                    }
                )
            desktop.close()

            mobile = browser.new_context(viewport={"width": 390, "height": 844})
            mobile_page = mobile.new_page()
            mobile_failures = monitor_page(mobile_page, allowed_origins)
            login(mobile_page, base_url, credentials)
            mobile_runtime = launch_chat(mobile_page, base_url, app_id, first_conversation)
            if mobile_runtime.locator(".homer-action-dock, .homer-action-button").count():
                raise AssertionError("removed global action dock is visible on mobile")
            mobile_runtime.locator("#homer-preset-ball").click()
            mobile_runtime.locator("#homer-preset-panel").wait_for(state="visible")
            mobile_runtime.locator("#homer-preset-ball").click()
            mobile_runtime.locator("#homer-preset-panel").wait_for(state="hidden")
            mobile_runtime.locator("[data-keyword-open]").click()
            mobile_runtime.locator("[data-keyword-panel]").wait_for(state="visible")
            assert_no_overflow(mobile_runtime, "mobile dialogue frame")
            assert_no_overflow(mobile_page, "mobile")
            mobile_page.screenshot(
                path=str(artifact_dir / "original-sillytavern-mobile.png"),
                full_page=True,
            )
            assert_clean(mobile_failures, "mobile")
            results.append(
                {
                    "viewport": "mobile",
                    "chat_runtime": "pass",
                    "preset_panel": "pass",
                    "keyword_injector_panel": "pass",
                    "yuzi_phone_asset_requests": len(mobile_failures["yuzi"]),
                    "horizontal_overflow": False,
                }
            )
            mobile.close()

            regular = browser.new_context(viewport={"width": 1440, "height": 900})
            regular_page = regular.new_page()
            regular_failures = monitor_page(regular_page, allowed_origins)
            login(
                regular_page,
                base_url,
                {
                    "email": credentials["regular_email"],
                    "password": credentials["regular_password"],
                },
            )
            regular_conversation = start_conversation(regular_page, base_url, app_id)
            regular_runtime = launch_chat(regular_page, base_url, app_id, regular_conversation)
            regular_runtime.wait_for_function("Boolean(window.TavernHelper)", timeout=45_000)
            permission_result = exercise_regular_user_permissions(regular_runtime)
            remove_expected_permission_denial(regular_failures)
            assert_clean(regular_failures, "regular user")
            results.append(
                {
                    "viewport": "desktop",
                    "role": "regular-user",
                    "extension_mutation": "blocked",
                    "worldbook_mutation": "allowed",
                    **permission_result,
                }
            )
            regular.close()

            admin = browser.new_context(viewport={"width": 1440, "height": 900})
            admin_page = admin.new_page()
            admin_failures = monitor_page(admin_page, allowed_origins)
            login(admin_page, base_url, credentials)
            admin_visibility = exercise_admin_prompt_visibility_control(
                admin_page,
                base_url,
                artifact_dir,
            )
            assert_clean(admin_failures, "admin prompt visibility")
            results.append(
                {
                    "viewport": "desktop",
                    "role": "admin",
                    "prompt_user_visibility_control": "pass",
                    **admin_visibility,
                }
            )
            admin.close()
        finally:
            browser.close()

    print(json.dumps({"ok": True, "results": results}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
