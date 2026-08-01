#!/usr/bin/env python3
"""Playwright smoke test for the locally injected Homer offline shell."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from urllib.parse import urlsplit

from playwright.sync_api import sync_playwright


ROOT = Path(__file__).resolve().parents[1]

ALLOWED_EXTERNAL_CSP_SOURCES = {
    "script-src": {
        "https://cdn.jsdelivr.net",
        "https://fastly.jsdelivr.net",
        "https://testingcf.jsdelivr.net",
        "https://raw.githubusercontent.com",
    },
    "style-src": {
        "https://fonts.googleapis.com",
        "https://fonts.gstatic.com",
        "https://cdn.jsdelivr.net",
        "https://fastly.jsdelivr.net",
        "https://testingcf.jsdelivr.net",
    },
    "img-src": {"https:"},
    "media-src": {
        "https://raw.githubusercontent.com",
        "https://cdn.jsdelivr.net",
        "https://fastly.jsdelivr.net",
        "https://testingcf.jsdelivr.net",
        "https://thumbsnap.com",
        "https://files.catbox.moe",
    },
    "font-src": {
        "https://fonts.gstatic.com",
        "https://cdn.jsdelivr.net",
        "https://fastly.jsdelivr.net",
        "https://testingcf.jsdelivr.net",
    },
    "connect-src": {
        "https://raw.githubusercontent.com",
        "https://cdn.jsdelivr.net",
        "https://fastly.jsdelivr.net",
        "https://testingcf.jsdelivr.net",
        "https://gitlab.com",
        "https://thumbsnap.com",
        "https://files.catbox.moe",
    },
}


def assert_csp_external_sources_are_allowlisted(label: str, csp: str) -> None:
    directives = {}
    for raw_directive in csp.split(";"):
        parts = raw_directive.strip().split()
        if parts:
            directives[parts[0]] = set(parts[1:])

    for directive, sources in directives.items():
        external_sources = {
            source
            for source in sources
            if source == "https:" or source.startswith(("http://", "https://"))
        }
        unexpected = external_sources - ALLOWED_EXTERNAL_CSP_SOURCES.get(directive, set())
        if unexpected:
            raise AssertionError(
                f"{label}: offline CSP has non-allowlisted {directive} sources: "
                f"{sorted(unexpected)}"
            )

    missing_required = {
        directive: sorted(required - directives.get(directive, set()))
        for directive, required in ALLOWED_EXTERNAL_CSP_SOURCES.items()
        if required - directives.get(directive, set())
    }
    if missing_required:
        raise AssertionError(
            f"{label}: offline CSP is missing compatibility sources: {missing_required}"
        )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8080")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=ROOT / "output" / "offline-dev" / "test-results" / "browser",
    )
    args = parser.parse_args()
    base_url = args.base_url.rstrip("/")
    base_origin = f"{urlsplit(base_url).scheme}://{urlsplit(base_url).netloc}"
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    results = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            for label, viewport in (
                ("desktop", {"width": 1440, "height": 900}),
                ("mobile", {"width": 390, "height": 844}),
            ):
                context = browser.new_context(viewport=viewport)
                page = context.new_page()
                console_errors: list[str] = []
                page_errors: list[str] = []
                external_requests: list[str] = []
                page.on(
                    "console",
                    lambda message: console_errors.append(message.text)
                    if message.type == "error"
                    else None,
                )
                page.on("pageerror", lambda error: page_errors.append(str(error)))
                page.on(
                    "request",
                    lambda request: external_requests.append(request.url)
                    if request.url.startswith(("http://", "https://"))
                    and not request.url.startswith(base_origin)
                    else None,
                )

                response = page.goto(
                    base_url + "/app/login.html",
                    wait_until="domcontentloaded",
                    timeout=20_000,
                )
                page.wait_for_load_state("networkidle", timeout=20_000)
                if response is None or response.status != 200:
                    raise AssertionError(f"{label}: login page did not return HTTP 200")
                csp = response.headers.get("content-security-policy", "")
                if "connect-src 'self' blob:" not in csp or "'unsafe-eval'" not in csp:
                    raise AssertionError(f"{label}: offline CSP is missing required local directives")
                assert_csp_external_sources_are_allowlisted(label, csp)

                enabled = page.evaluate("Boolean(window.__HOMER_OFFLINE_DEV__?.enabled)")
                if not enabled:
                    raise AssertionError(f"{label}: offline guard was not injected")
                if page.locator("#homer-offline-dev-badge").count():
                    raise AssertionError(f"{label}: offline badge must not be exposed")

                before_url = page.url
                page.evaluate(
                    """
                    () => {
                      const link = document.createElement('a');
                      link.id = 'offline-external-probe';
                      link.href = 'https://example.com/offline-probe';
                      link.textContent = 'external probe';
                      document.body.appendChild(link);
                    }
                    """
                )
                page.locator("#offline-external-probe").click()
                page.wait_for_timeout(150)
                if page.url != before_url:
                    raise AssertionError(f"{label}: external navigation was not blocked")
                if not page.locator("#homer-offline-dev-toast").evaluate(
                    "element => element.classList.contains('is-visible')"
                ):
                    raise AssertionError(f"{label}: blocked-navigation toast was not shown")

                overflow = page.evaluate(
                    "document.documentElement.scrollWidth > document.documentElement.clientWidth + 1"
                )
                if overflow:
                    raise AssertionError(f"{label}: login page has horizontal overflow")
                if console_errors or page_errors or external_requests:
                    raise AssertionError(
                        f"{label}: browser errors; console={console_errors}, "
                        f"page={page_errors}, external={external_requests}"
                    )

                screenshot = output_dir / f"offline-login-{label}.png"
                page.screenshot(path=str(screenshot), full_page=True)
                results.append(
                    {
                        "viewport": label,
                        "http": response.status,
                        "badge": True,
                        "external_navigation_blocked": True,
                        "horizontal_overflow": False,
                        "console_errors": 0,
                        "page_errors": 0,
                        "external_requests": 0,
                        "screenshot": str(screenshot),
                    }
                )
                context.close()
        finally:
            browser.close()

    print(json.dumps({"ok": True, "results": results}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
