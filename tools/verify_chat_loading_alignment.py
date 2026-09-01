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
ARTIFACTS = ROOT / "output" / "playwright" / "chat-loading-alignment-20260830"


def same_origin(url: str) -> bool:
    target = urlparse(url)
    base = urlparse(BASE_URL)
    return target.scheme == base.scheme and target.netloc == base.netloc


def inspect_viewport(browser, credentials: dict, name: str, width: int, height: int) -> dict:
    context = browser.new_context(viewport={"width": width, "height": height})
    login = context.request.post(
        BASE_URL + "/console/api/login",
        data={"email": credentials["email"], "password": credentials["password"]},
    )
    if login.status != 200:
        raise AssertionError(f"login failed: {login.status}")
    conversations_response = context.request.get(BASE_URL + "/console/api/web/conversations")
    if conversations_response.status != 200:
        raise AssertionError(f"conversation list failed: {conversations_response.status}")
    conversations = conversations_response.json().get("data", {}).get("list", [])
    if not conversations:
        raise AssertionError("offline account has no conversation")
    conversation = next(
        (item for item in conversations if "ChatArchive" not in str(item.get("app_name", ""))),
        conversations[0],
    )
    app_id = str(conversation["app_id"])
    conversation_id = str(conversation["id"])

    page = context.new_page()
    console_errors: list[str] = []
    page_errors: list[str] = []
    network_errors: list[str] = []
    requests: list[str] = []
    page.on("console", lambda message: console_errors.append(message.text) if message.type == "error" else None)
    page.on("pageerror", lambda error: page_errors.append(str(error)))
    page.on("dialog", lambda dialog: dialog.dismiss())
    page.on("request", lambda request: requests.append(request.url))
    page.on(
        "response",
        lambda response: network_errors.append(f"{response.status} {response.url}")
        if same_origin(response.url) and response.status >= 400
        else None,
    )

    started = time.perf_counter()
    page.goto(
        f"{BASE_URL}/app/chat.html?app_id={app_id}&conversation_id={conversation_id}",
        wait_until="commit",
        timeout=30_000,
    )
    page.wait_for_function(
        "document.body.classList.contains('has-preview')",
        timeout=5_000,
    )
    preview_ms = round((time.perf_counter() - started) * 1000)
    page.locator("#preview-settings").click()
    page.wait_for_function("document.body.classList.contains('shell-right-open')")
    page.locator("#preview-settings-close").click()
    page.locator("#preview-menu").click()
    page.wait_for_function("document.body.classList.contains('shell-left-open')")
    page.locator("#preview-left-close").click()
    page.wait_for_function(
        "document.body.classList.contains('is-ready')",
        timeout=90_000,
    )
    ready_ms = round((time.perf_counter() - started) * 1000)
    frame = page.frame(name="homer-dialogue-module")
    if frame is None:
        raise AssertionError("dialogue runtime frame is missing")
    frame.wait_for_selector("#chat", state="attached", timeout=15_000)
    frame.wait_for_function(
        "document.documentElement.classList.contains('homer-runtime-ready')",
        timeout=15_000,
    )
    left_drawer_open = frame.locator("#homer-left-drawer").evaluate(
        "node => node.classList.contains('is-open')"
    )
    if left_drawer_open:
        raise AssertionError("runtime opened the navigation drawer without user input")

    message_data = frame.locator("#chat .mes").evaluate_all(
        """(nodes) => nodes.map((node) => {
          const rect = node.getBoundingClientRect();
          return {
            isUser: node.getAttribute('is_user') === 'true',
            isSystem: node.getAttribute('is_system') === 'true',
            left: Math.round(rect.left),
            right: Math.round(rect.right),
            width: Math.round(rect.width),
          };
        })"""
    )
    if not message_data:
        raise AssertionError("runtime chat has no rendered messages")
    user_messages = [item for item in message_data if item["isUser"]]
    assistant_messages = [item for item in message_data if not item["isUser"]]
    if assistant_messages and user_messages:
        if min(item["left"] for item in assistant_messages) >= min(item["left"] for item in user_messages):
            raise AssertionError(f"assistant messages are not left of user messages: {message_data}")
        if max(item["right"] for item in user_messages) <= max(item["right"] for item in assistant_messages):
            raise AssertionError(f"user messages are not right of assistant messages: {message_data}")

    direction_contract = frame.locator("#chat").first.evaluate(
        """(chat) => {
          const make = (isUser) => {
            const node = document.createElement('article');
            node.className = 'mes';
            node.setAttribute('is_user', String(isUser));
            node.style.width = '80px';
            node.textContent = 'layout probe';
            chat.append(node);
            const style = getComputedStyle(node);
            const result = {
              marginLeft: style.marginLeft,
              marginRight: style.marginRight,
              alignSelf: style.alignSelf,
            };
            node.remove();
            return result;
          };
          return { assistant: make(false), user: make(true) };
        }"""
    )
    if direction_contract["assistant"]["marginLeft"] != "0px" or direction_contract["assistant"]["marginRight"] == "0px":
        raise AssertionError(f"assistant direction contract failed: {direction_contract}")
    if direction_contract["user"]["marginLeft"] == "0px" or direction_contract["user"]["marginRight"] != "0px":
        raise AssertionError(f"user direction contract failed: {direction_contract}")

    runtime_marks = frame.evaluate(
        "performance.getEntriesByType('mark').map((entry) => ({name: entry.name, start: Math.round(entry.startTime)})).filter((entry) => entry.name.startsWith('homer-'))"
    )

    body_text = page.locator("body").inner_text()
    if "角色卡互动界面将在完整功能接入后显示" in body_text:
        raise AssertionError("obsolete HTML-card placeholder is still visible")

    host_conversation_requests = [
        url for url in requests
        if "/console/api/web/conversations" in url
    ]
    # The authoritative first-frame shell makes one bounded history request
    # and one bounded message refresh while rendering Android/browser cache.
    # Only a launch-session request or a repeated host fetch is a regression.
    outer_duplicate_requests = [
        url for url in requests if "/console/api/web/dialogue/session" in url
    ]
    history_requests = [url for url in host_conversation_requests if "/messages?limit=120" not in url]
    message_requests = [url for url in host_conversation_requests if "/messages?limit=120" in url]
    if len(history_requests) > 1:
        outer_duplicate_requests.extend(history_requests[1:])
    if len(message_requests) > 1:
        outer_duplicate_requests.extend(message_requests[1:])
    screenshot = ARTIFACTS / f"{name}.png"
    page.screenshot(path=str(screenshot), full_page=True)
    result = {
        "viewport": {"width": width, "height": height},
        "ready_ms": ready_ms,
        "preview_ms": preview_ms,
        "preview_controls": "passed",
        "runtime_left_drawer_open": left_drawer_open,
        "message_count": len(message_data),
        "user_message_count": len(user_messages),
        "assistant_message_count": len(assistant_messages),
        "message_geometry": message_data,
        "direction_contract": direction_contract,
        "runtime_marks": runtime_marks,
        "outer_duplicate_requests": outer_duplicate_requests,
        "obsolete_placeholder_visible": False,
        "horizontal_overflow": page.evaluate(
            "document.documentElement.scrollWidth > document.documentElement.clientWidth + 1"
        ),
        "console_errors": console_errors,
        "page_errors": page_errors,
        "network_errors": network_errors,
        "screenshot": str(screenshot),
    }
    context.close()
    return result


def main() -> int:
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    credentials = json.loads(CREDENTIALS.read_text(encoding="utf-8"))
    with sync_playwright() as playwright:
        executable = os.environ.get("HOMER_PLAYWRIGHT_EXECUTABLE", "").strip()
        browser = playwright.chromium.launch(
            headless=True,
            executable_path=executable or None,
        )
        results = [
            inspect_viewport(browser, credentials, "desktop", 1440, 900),
            inspect_viewport(browser, credentials, "mobile", 390, 844),
        ]
        browser.close()
    payload = {"base_url": BASE_URL, "results": results}
    (ARTIFACTS / "result.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    failed = any(
        item["outer_duplicate_requests"]
        or item["horizontal_overflow"]
        or item["console_errors"]
        or item["page_errors"]
        or item["network_errors"]
        for item in results
    )
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
