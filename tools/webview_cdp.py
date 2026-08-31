"""Drive an Android WebView page over the DevTools protocol.

Playwright's connect_over_cdp cannot attach to Android WebView (it requires
Browser.setDownloadBehavior, which WebView does not implement), so this speaks
raw CDP to a single page target instead. Used to verify the APK's bundled
offline page: it is the only way to read that DOM, since the WebView exposes no
accessibility tree to uiautomator and the release build has debugging disabled.

Usage:
    adb forward tcp:9333 localabstract:webview_devtools_remote_<pid>
    python tools/webview_cdp.py --url-contains offline/index.html --eval "1+1"
    python tools/webview_cdp.py --url-contains offline/index.html --script probe.js
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.request
from pathlib import Path

import websocket


def find_target(port: int, needle: str) -> dict:
    raw = urllib.request.urlopen(f"http://127.0.0.1:{port}/json/list", timeout=20).read()
    targets = json.loads(raw.decode("utf-8"))
    for target in targets:
        if needle in str(target.get("url", "")):
            return target
    available = ", ".join(str(t.get("url", ""))[:70] for t in targets)
    raise SystemExit(f"no target matching {needle!r}; available: {available}")


def evaluate(ws_url: str, expression: str, await_promise: bool = True) -> object:
    ws = websocket.create_connection(ws_url, timeout=40, suppress_origin=True)
    try:
        ws.send(json.dumps({
            "id": 1,
            "method": "Runtime.evaluate",
            "params": {
                "expression": expression,
                "returnByValue": True,
                "awaitPromise": await_promise,
                "userGesture": True,
            },
        }))
        while True:
            message = json.loads(ws.recv())
            if message.get("id") != 1:
                continue  # skip unsolicited events
            if "error" in message:
                raise SystemExit(f"CDP error: {message['error']}")
            result = message["result"]
            if result.get("exceptionDetails"):
                raise SystemExit(f"JS exception: {result['exceptionDetails'].get('text')} "
                                 f"{result['exceptionDetails'].get('exception', {}).get('description', '')}")
            return result.get("result", {}).get("value")
    finally:
        ws.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate JS in an Android WebView page")
    parser.add_argument("--port", type=int, default=9333)
    parser.add_argument("--url-contains", required=True)
    parser.add_argument("--eval", dest="expression")
    parser.add_argument("--script", type=Path)
    parser.add_argument("--no-await", action="store_true")
    args = parser.parse_args()

    if not args.expression and not args.script:
        raise SystemExit("pass --eval or --script")
    expression = args.expression or args.script.read_text(encoding="utf-8")

    target = find_target(args.port, args.url_contains)
    value = evaluate(target["webSocketDebuggerUrl"], expression, not args.no_await)
    if isinstance(value, (dict, list)):
        print(json.dumps(value, ensure_ascii=False, indent=2))
    else:
        print(value)
    return 0


if __name__ == "__main__":
    sys.exit(main())
