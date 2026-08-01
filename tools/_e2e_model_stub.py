"""Local OpenAI-compatible model stub for isolated Homer browser E2E tests.

The server deliberately binds only to loopback, requires a non-production test
token, and never logs prompts or response bodies.
"""

from __future__ import annotations

import argparse
import itertools
import json
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


MODEL_ID = "homer-e2e"
REQUEST_IDS = itertools.count(1)
REQUEST_LOCK = threading.Lock()


def json_bytes(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


class ModelStubHandler(BaseHTTPRequestHandler):
    server_version = "HomerE2EModel/1"
    protocol_version = "HTTP/1.1"

    def log_message(self, format: str, *args: object) -> None:
        # Keep E2E logs free of prompts, headers, and response payloads.
        return

    @property
    def expected_token(self) -> str:
        return str(getattr(self.server, "api_key", ""))

    def send_json(self, status: int, value: object) -> None:
        payload = json_bytes(value)
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Connection", "close")
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(payload)
        self.wfile.flush()
        self.close_connection = True

    def authorized(self) -> bool:
        return self.headers.get("Authorization", "") == f"Bearer {self.expected_token}"

    def do_GET(self) -> None:
        if self.path == "/health":
            self.send_json(200, {"ok": True})
            return
        if self.path == "/v1/models":
            if not self.authorized():
                self.send_json(401, {"error": {"message": "unauthorized"}})
                return
            self.send_json(
                200,
                {
                    "object": "list",
                    "data": [
                        {
                            "id": MODEL_ID,
                            "object": "model",
                            "created": 0,
                            "owned_by": "homer-e2e",
                        }
                    ],
                },
            )
            return
        self.send_json(404, {"error": {"message": "not found"}})

    def do_POST(self) -> None:
        if self.path != "/v1/chat/completions":
            self.send_json(404, {"error": {"message": "not found"}})
            return
        if not self.authorized():
            self.send_json(401, {"error": {"message": "unauthorized"}})
            return
        try:
            length = int(self.headers.get("Content-Length", "0") or "0")
        except ValueError:
            length = 0
        if length <= 0 or length > 8 * 1024 * 1024:
            self.send_json(400, {"error": {"message": "invalid request size"}})
            return
        try:
            body = json.loads(self.rfile.read(length).decode("utf-8"))
        except Exception:
            self.send_json(400, {"error": {"message": "invalid json"}})
            return
        if not isinstance(body, dict) or str(body.get("model") or "") != MODEL_ID:
            self.send_json(400, {"error": {"message": "invalid model"}})
            return
        messages = body.get("messages")
        if not isinstance(messages, list) or not messages:
            self.send_json(400, {"error": {"message": "messages are required"}})
            return

        with REQUEST_LOCK:
            sequence = next(REQUEST_IDS)
        completion_id = "chatcmpl-homer-e2e-" + uuid.uuid4().hex
        created = int(time.time())
        answer = f"惑梦隔离模型回复 #{sequence}。"
        if body.get("stream"):
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream; charset=utf-8")
            self.send_header("Cache-Control", "no-cache, no-store")
            self.send_header("Connection", "close")
            self.end_headers()
            chunks = [
                {
                    "id": completion_id,
                    "object": "chat.completion.chunk",
                    "created": created,
                    "model": MODEL_ID,
                    "choices": [
                        {
                            "index": 0,
                            "delta": {"role": "assistant"},
                            "finish_reason": None,
                        }
                    ],
                },
                {
                    "id": completion_id,
                    "object": "chat.completion.chunk",
                    "created": created,
                    "model": MODEL_ID,
                    "choices": [
                        {
                            "index": 0,
                            "delta": {"content": answer},
                            "finish_reason": None,
                        }
                    ],
                },
                {
                    "id": completion_id,
                    "object": "chat.completion.chunk",
                    "created": created,
                    "model": MODEL_ID,
                    "choices": [
                        {
                            "index": 0,
                            "delta": {},
                            "finish_reason": "stop",
                        }
                    ],
                },
            ]
            for chunk in chunks:
                self.wfile.write(b"data: " + json_bytes(chunk) + b"\n\n")
            self.wfile.write(b"data: [DONE]\n\n")
            self.wfile.flush()
            self.close_connection = True
            return

        self.send_json(
            200,
            {
                "id": completion_id,
                "object": "chat.completion",
                "created": created,
                "model": MODEL_ID,
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": answer},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
            },
        )


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the isolated Homer E2E model stub")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=18082)
    parser.add_argument("--api-key", required=True)
    args = parser.parse_args()
    if args.host not in {"127.0.0.1", "localhost"}:
        raise SystemExit("the E2E model stub may only bind to loopback")
    if not args.api_key or len(args.api_key) < 16:
        raise SystemExit("a non-empty E2E API key is required")
    server = ThreadingHTTPServer((args.host, args.port), ModelStubHandler)
    server.api_key = args.api_key
    server.serve_forever(poll_interval=0.2)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
