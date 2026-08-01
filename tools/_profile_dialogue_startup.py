"""Measure product-shell and dialogue-runtime startup without logging credentials.

The script is read-only after authentication: it reuses the newest existing
conversation and records only stage names, elapsed milliseconds, HTTP status,
resource type, and URL paths with query strings removed.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from urllib.parse import urlsplit

from playwright.sync_api import Page, TimeoutError as PlaywrightTimeoutError, sync_playwright


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CREDENTIALS = ROOT / "output" / "offline-dev" / "runtime" / "credentials.json"


def elapsed_ms(started: float) -> int:
    return round((time.perf_counter() - started) * 1000)


def sanitize_url(value: str) -> str:
    parsed = urlsplit(value)
    return f"{parsed.scheme}://{parsed.netloc}{parsed.path}"


def login(page: Page, base_url: str, credentials: dict[str, str]) -> None:
    response = page.context.request.post(
        base_url + "/console/api/login",
        data={"email": credentials["email"], "password": credentials["password"]},
    )
    if response.status != 200:
        raise RuntimeError(f"login failed with HTTP {response.status}")
    page.add_init_script("localStorage.setItem('ai_xingyue_logged_in', '1')")


def latest_conversation(page: Page, base_url: str, app_id: str = '') -> tuple[str, str]:
    response = page.context.request.get(base_url + "/console/api/web/conversations")
    if response.status != 200:
        raise RuntimeError(f"conversation list failed with HTTP {response.status}")
    body = response.json()
    data = body.get("data", body)
    conversations = data.get("list", []) if isinstance(data, dict) else []
    for conversation in conversations:
        conversation_app_id = str(conversation.get("app_id") or "").strip()
        conversation_id = str(conversation.get("id") or conversation.get("conversation_id") or "").strip()
        if app_id and conversation_app_id != app_id:
            continue
        if conversation_app_id and conversation_id:
            return conversation_app_id, conversation_id
    raise RuntimeError("the account has no existing conversation to profile")


def profile_homer(
    page: Page,
    base_url: str,
    app_id: str,
    conversation_id: str,
    *,
    progress: bool = False,
) -> dict:
    started = time.perf_counter()
    stages: list[dict[str, int | str]] = []
    requests: list[dict[str, int | str]] = []
    request_started: dict[int, float] = {}

    def record_request(request) -> None:
        request_started[id(request)] = time.perf_counter()

    def record_response(response) -> None:
        request = response.request
        request_time = request_started.pop(id(request), started)
        requests.append(
            {
                "path": sanitize_url(response.url),
                "status": response.status,
                "type": request.resource_type,
                "start_ms": round((request_time - started) * 1000),
                "duration_ms": round((time.perf_counter() - request_time) * 1000),
            }
        )

    page.on("request", record_request)
    page.on("response", record_response)
    url = f"{base_url}/app/chat.html?app_id={app_id}&conversation_id={conversation_id}"
    page.goto(url, wait_until="commit", timeout=30_000)
    stages.append({"stage": "host_commit", "ms": elapsed_ms(started)})
    if progress:
        print(json.dumps(stages[-1], ensure_ascii=False), flush=True)

    last_detail = ""
    deadline = time.perf_counter() + 150
    while time.perf_counter() < deadline:
        state = page.evaluate(
            """() => ({
              ready: document.body.classList.contains('is-ready'),
              detail: document.querySelector('#launcher-detail')?.textContent?.trim() || '',
              frameSrc: document.querySelector('#dialogue-frame')?.getAttribute('src') || '',
            })"""
        )
        if state["detail"] and state["detail"] != last_detail:
            last_detail = state["detail"]
            stages.append({"stage": "host_status", "detail": last_detail, "ms": elapsed_ms(started)})
            if progress:
                print(json.dumps(stages[-1], ensure_ascii=False), flush=True)
        if state["frameSrc"] and not any(row["stage"] == "frame_src_set" for row in stages):
            stages.append({"stage": "frame_src_set", "ms": elapsed_ms(started)})
            if progress:
                print(json.dumps(stages[-1], ensure_ascii=False), flush=True)

        dialogue_frame = next(
            (frame for frame in page.frames if "/module/dialogue/" in frame.url),
            None,
        )
        if dialogue_frame is not None:
            if not any(row["stage"] == "runtime_document" for row in stages):
                stages.append({"stage": "runtime_document", "ms": elapsed_ms(started)})
                if progress:
                    print(json.dumps(stages[-1], ensure_ascii=False), flush=True)
            try:
                runtime_state = dialogue_frame.evaluate(
                    """() => ({
                      shell: Boolean(document.querySelector('#homer-runtime-root')),
                      ready: document.documentElement.classList.contains('homer-runtime-ready'),
                      messages: document.querySelectorAll('#chat .mes').length,
                    })"""
                )
                if runtime_state["shell"] and not any(row["stage"] == "product_shell" for row in stages):
                    stages.append({"stage": "product_shell", "ms": elapsed_ms(started)})
                    if progress:
                        print(json.dumps(stages[-1], ensure_ascii=False), flush=True)
                if runtime_state["messages"] and not any(row["stage"] == "messages_rendered" for row in stages):
                    stages.append({"stage": "messages_rendered", "ms": elapsed_ms(started)})
                    if progress:
                        print(json.dumps(stages[-1], ensure_ascii=False), flush=True)
                if runtime_state["ready"] and not any(row["stage"] == "runtime_ready" for row in stages):
                    stages.append({"stage": "runtime_ready", "ms": elapsed_ms(started)})
                    if progress:
                        print(json.dumps(stages[-1], ensure_ascii=False), flush=True)
            except Exception:
                pass
        if state["ready"]:
            stages.append({"stage": "host_ready", "ms": elapsed_ms(started)})
            if progress:
                print(json.dumps(stages[-1], ensure_ascii=False), flush=True)
            break
        page.wait_for_timeout(50)
    else:
        raise TimeoutError("dialogue startup exceeded 150 seconds")

    page.remove_listener("request", record_request)
    page.remove_listener("response", record_response)
    slowest = sorted(requests, key=lambda item: int(item["duration_ms"]), reverse=True)[:15]
    return {
        "target": "homer",
        "total_ms": stages[-1]["ms"],
        "stages": stages,
        "request_count": len(requests),
        "slowest_requests": slowest,
    }


def profile_reference(page: Page, reference_url: str) -> dict:
    started = time.perf_counter()
    page.goto(reference_url, wait_until="commit", timeout=30_000)
    committed = elapsed_ms(started)
    page.wait_for_load_state("domcontentloaded", timeout=30_000)
    dom_ready = elapsed_ms(started)
    try:
        page.wait_for_function(
            """() => {
              const frame = document.querySelector('iframe[srcdoc]');
              const input = document.querySelector('textarea, input[type="text"]');
              return Boolean(frame && (frame.getAttribute('srcdoc') || '').length > 1000 && input);
            }""",
            timeout=30_000,
        )
    except PlaywrightTimeoutError:
        page.locator("iframe[srcdoc]").wait_for(state="visible", timeout=30_000)
    interactive = elapsed_ms(started)
    return {
        "target": "reference",
        "total_ms": interactive,
        "stages": [
            {"stage": "commit", "ms": committed},
            {"stage": "dom_ready", "ms": dom_ready},
            {"stage": "product_shell_and_card_slot", "ms": interactive},
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Profile dialogue startup without exposing credentials")
    parser.add_argument("--base-url", default="http://127.0.0.1:8080")
    parser.add_argument("--credentials", type=Path, default=DEFAULT_CREDENTIALS)
    parser.add_argument("--reference-url", default="")
    parser.add_argument("--repeat", type=int, default=2)
    parser.add_argument("--progress", action="store_true")
    parser.add_argument("--app-id", default="")
    parser.add_argument("--conversation-id", default="")
    args = parser.parse_args()

    credentials = json.loads(args.credentials.read_text(encoding="utf-8"))
    results: list[dict] = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            context = browser.new_context(viewport={"width": 1440, "height": 900})
            page = context.new_page()
            login(page, args.base_url.rstrip("/"), credentials)
            app_id, conversation_id = latest_conversation(
                page,
                args.base_url.rstrip("/"),
                str(args.app_id or '').strip(),
            )
            if args.conversation_id:
                conversation_id = str(args.conversation_id).strip()
            for _ in range(max(1, args.repeat)):
                results.append(
                    profile_homer(
                        page,
                        args.base_url.rstrip("/"),
                        app_id,
                        conversation_id,
                        progress=args.progress,
                    )
                )
            context.close()

            if args.reference_url:
                reference_context = browser.new_context(viewport={"width": 1440, "height": 900})
                reference_page = reference_context.new_page()
                for _ in range(max(1, args.repeat)):
                    results.append(profile_reference(reference_page, args.reference_url))
                reference_context.close()
        finally:
            browser.close()

    print(json.dumps({"ok": True, "results": results}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
