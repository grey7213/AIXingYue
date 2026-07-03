"""本地一体化开发服务器：静态前端 + API 代理。

用法：
  python tools/run_frontend_dev.py
  浏览器访问 http://127.0.0.1:8080/
"""
from __future__ import annotations
import argparse
import socket
import threading
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FRONTEND_DIR = ROOT / "frontend"

API_PREFIXES = ("/console/", "/go/", "/admin/", "/health")


def make_handler(api_target: str):
    class Handler(SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(FRONTEND_DIR), **kwargs)

        def log_message(self, fmt, *args):
            print(f"[frontend-dev] {self.client_address[0]} - {fmt % args}", flush=True)

        def _is_api(self) -> bool:
            return any(self.path.startswith(p) for p in API_PREFIXES) or self.path == "/health"

        def _proxy(self):
            target = api_target.rstrip("/") + self.path
            length = int(self.headers.get("Content-Length", "0") or "0")
            body = self.rfile.read(length) if length else None
            req = urllib.request.Request(target, data=body, method=self.command)
            for k, v in self.headers.items():
                if k.lower() in ("host", "content-length", "connection"):
                    continue
                req.add_header(k, v)
            try:
                with urllib.request.urlopen(req, timeout=30) as resp:
                    self.send_response(resp.status)
                    for k, v in resp.getheaders():
                        if k.lower() in ("transfer-encoding", "connection"):
                            continue
                        self.send_header(k, v)
                    self.end_headers()
                    self.wfile.write(resp.read())
            except urllib.error.HTTPError as e:
                self.send_response(e.code)
                for k, v in e.headers.items():
                    if k.lower() in ("transfer-encoding", "connection"):
                        continue
                    self.send_header(k, v)
                self.end_headers()
                self.wfile.write(e.read())
            except Exception as exc:
                self.send_response(502)
                self.send_header("Content-Type", "text/plain; charset=utf-8")
                self.end_headers()
                self.wfile.write(f"upstream error: {exc}".encode("utf-8"))

        def do_GET(self):
            if self._is_api(): return self._proxy()
            super().do_GET()
        def do_POST(self): self._proxy() if self._is_api() else self.send_error(405)
        def do_PUT(self): self._proxy() if self._is_api() else self.send_error(405)
        def do_DELETE(self): self._proxy() if self._is_api() else self.send_error(405)
        def do_PATCH(self): self._proxy() if self._is_api() else self.send_error(405)
        def do_OPTIONS(self): self._proxy()

    return Handler


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--api", default="http://127.0.0.1:8008", help="后端 API 地址")
    args = parser.parse_args()

    print(f"frontend dir: {FRONTEND_DIR}")
    print(f"api target:   {args.api}")
    print(f"open:         http://{args.host}:{args.port}/")
    server = ThreadingHTTPServer((args.host, args.port), make_handler(args.api))
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("stopping")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
