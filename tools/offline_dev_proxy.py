#!/usr/bin/env python3
"""Homer offline development reverse proxy.

Serves ``frontend/`` on 127.0.0.1:8080 and forwards same-origin API
requests to the local backend on 127.0.0.1:8000.  It is intentionally
stdlib-only and refuses to proxy arbitrary destinations.

Unlike the historical development proxy, event-stream responses are copied
incrementally and flushed so chat SSE behaviour can be debugged locally.
"""

from __future__ import annotations

import argparse
import http.client
import http.server
import mimetypes
import re
import socketserver
import sys
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import parse_qsl, unquote, urlencode, urlsplit, urlunsplit


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_FRONTEND_DIR = ROOT / "frontend"
DEFAULT_DIALOGUE_PUBLIC_DIR = ROOT / "sillytavern-runtime" / "public"
DEFAULT_BACKEND = "http://127.0.0.1:8000"
DEFAULT_DIALOGUE_RUNTIME = "http://127.0.0.1:8091"
DEFAULT_STATE_DIR = ROOT / "output" / "offline-dev"
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8080
MAX_PROXY_REQUEST_BYTES = 256 * 1024 * 1024
DIALOGUE_MOUNT = "/module/dialogue"
LEGACY_DIALOGUE_MOUNT = "/dialogue-core"
DIALOGUE_HOST_ENTRY = "/app/chat.html"

API_PREFIXES = (
    "/console",
    "/admin",
    "/go",
    "/api",
    "/health",
    "/img",
    "/media-cache",
    "/download",
)

SITE_OWNED_PREFIXES = (
    "/app",
    "/assets",
    "/console",
    "/admin",
    "/go",
    "/health",
    "/img",
    "/media-cache",
    "/download",
    "/__offline_dev__",
)

# The embedded dialogue client contains root-relative imports and API calls.
# These namespaces are not used by the Homer site frontend (which uses
# /assets, /app and /console), so they can be mounted directly without
# exposing or depending on the internal 8091 origin.
DIALOGUE_ROOT_PREFIXES = (
    "/api",
    "/csrf-token",
    "/scripts",
    "/lib",
    "/css",
    "/webfonts",
    "/locales",
    "/img",
    "/backgrounds",
    "/characters",
    "/User Avatars",
    "/user",
    "/thumbnail",
    "/socket.io",
    "/sounds",
)

DIALOGUE_ROOT_FILES = {
    "/script.js",
    "/lib.js",
    "/style.css",
    "/manifest.json",
    "/favicon.ico",
    "/version",
}

DIALOGUE_CACHEABLE_PREFIXES = (
    "/scripts",
    "/lib",
    "/css",
    "/webfonts",
    "/locales",
    "/img",
    "/sounds",
)
DIALOGUE_CACHEABLE_FILES = {
    "/script.js",
    "/lib.js",
    "/style.css",
    "/manifest.json",
    "/favicon.ico",
}
DIALOGUE_STATIC_CACHE_CONTROL = "private, max-age=3600, stale-while-revalidate=86400"

_DIALOGUE_LITERAL_PATHS = sorted(
    set(DIALOGUE_ROOT_PREFIXES).union(DIALOGUE_ROOT_FILES),
    key=len,
    reverse=True,
)
_DIALOGUE_LITERAL_ALTERNATION = b"(?:" + b"|".join(
    re.escape(path.encode("ascii")) for path in _DIALOGUE_LITERAL_PATHS
) + b")"
_DIALOGUE_QUOTED_PATH_PATTERN = re.compile(
    br"(?P<quote>[\"'`])(?P<path>" + _DIALOGUE_LITERAL_ALTERNATION
    + br")(?:(?P<boundary>[/\?#])|(?P=quote))"
)
_DIALOGUE_MARKED_PATH_PATTERN = re.compile(
    br"(?P<marker>url\(|URL\(|=|:)(?P<path>" + _DIALOGUE_LITERAL_ALTERNATION
    + br")(?P<boundary>[/\?#])"
)

DIALOGUE_TEXT_CONTENT_TYPES = (
    "text/html",
    "text/css",
    "text/javascript",
    "application/javascript",
    "application/x-javascript",
    "application/manifest+json",
)

IMPLEMENTATION_HEADERS = {
    "date",
    "server",
    "x-powered-by",
    "x-response-time",
    "x-sillytavern-version",
}

DIALOGUE_UPSTREAM_ALIASES = {
    "/scripts/extensions/third-party/dialogue-memory-books":
        "/scripts/extensions/third-party/SillyTavern-MemoryBooks",
}

BLOCKED_PUBLIC_SOURCE_PREFIXES = (
    "/app/_huimeng-ref",
    "/app/assets/vendor/js-slash-runner",
)

BLOCKED_PUBLIC_SOURCE_FILES = {
    "/app/assets/css/sillytavern-theme.css",
    "/app/assets/css/wuyu-theme.css",
}

# The shell and API remain same-origin.  A small compatibility allowlist is
# retained for RoleplayHub cards and bundled public extensions that import
# assets at runtime; arbitrary remote scripts, connections and frames stay
# blocked.  data/blob are available only for local previews, workers or
# sandbox frames.
OFFLINE_CSP = "; ".join(
    (
        "default-src 'self' data: blob:",
        # Alpine's standard build and the bundled Tailwind browser runtime use
        # dynamic Function evaluation.  unsafe-eval is local-dev-only here.
        # 角色卡自带脚本（道渊配置助手/MVU/ZOD）通过 iframe module import 远程 ESM，
        # srcdoc iframe 继承父页 CSP，故 script-src 必须放行这些 CDN，否则 import 被拦、悬浮球起不来。
        "script-src 'self' 'unsafe-inline' 'unsafe-eval' blob: https://cdn.jsdelivr.net https://fastly.jsdelivr.net https://testingcf.jsdelivr.net https://raw.githubusercontent.com",
        # 角色卡 UI 常用 Google Fonts 与 jsDelivr 镜像样式表。
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com https://fonts.gstatic.com https://cdn.jsdelivr.net https://fastly.jsdelivr.net https://testingcf.jsdelivr.net",
        # 角色卡内嵌图片来源广（图床/CDN 各异）；离线自测放行 https: 图片，保证卡 UI 完整。
        "img-src 'self' data: blob: https:",
        "media-src 'self' data: blob: https://raw.githubusercontent.com https://cdn.jsdelivr.net https://fastly.jsdelivr.net https://testingcf.jsdelivr.net https://thumbsnap.com https://files.catbox.moe",
        # Google Fonts 字体文件走 gstatic；data: 保留内联字体。
        "font-src 'self' data: https://fonts.gstatic.com https://cdn.jsdelivr.net https://fastly.jsdelivr.net https://testingcf.jsdelivr.net",
        "connect-src 'self' blob: https://raw.githubusercontent.com https://cdn.jsdelivr.net https://fastly.jsdelivr.net https://testingcf.jsdelivr.net https://gitlab.com https://thumbsnap.com https://files.catbox.moe",
        "worker-src 'self' blob:",
        "frame-src 'self' data: blob:",
        "child-src 'self' blob:",
        "object-src 'none'",
        "base-uri 'self'",
        "form-action 'self'",
        "frame-ancestors 'self'",
    )
)

HOP_BY_HOP_HEADERS = {
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailer",
    "transfer-encoding",
    "upgrade",
}

REPLACED_SECURITY_HEADERS = {
    "content-security-policy",
    "x-content-type-options",
    "referrer-policy",
    "permissions-policy",
}


def _dialogue_public_path(upstream_path: str) -> str:
    path = upstream_path if upstream_path.startswith("/") else "/" + upstream_path
    return DIALOGUE_MOUNT + path


def _rewrite_dialogue_path_literals(data: bytes) -> bytes:
    """Prefix known runtime-root URLs without rewriting arbitrary card text."""

    mount = DIALOGUE_MOUNT.encode("ascii")

    def rewrite_quoted(match: re.Match[bytes]) -> bytes:
        quote = match.group("quote")
        boundary = match.group("boundary") or quote
        return quote + mount + match.group("path") + boundary

    def rewrite_marked(match: re.Match[bytes]) -> bytes:
        return (
            match.group("marker")
            + mount
            + match.group("path")
            + match.group("boundary")
        )

    data = _DIALOGUE_QUOTED_PATH_PATTERN.sub(rewrite_quoted, data)
    data = _DIALOGUE_MARKED_PATH_PATTERN.sub(rewrite_marked, data)

    data = data.replace(b'<base href="/">', b'<base href="' + mount + b'/">')
    data = data.replace(b"<base href='/'>", b"<base href='" + mount + b"/'>")
    data = data.replace(b'"start_url":"/"', b'"start_url":"' + mount + b'/"')
    data = data.replace(b'"start_url": "/"', b'"start_url": "' + mount + b'/"')
    data = data.replace(b'"scope":"/"', b'"scope":"' + mount + b'/"')
    data = data.replace(b'"scope": "/"', b'"scope": "' + mount + b'/"')
    return data


def rewrite_dialogue_payload(data: bytes, content_type: str) -> bytes:
    """Rewrite only browser-executable runtime documents into the module mount."""

    normalized_type = str(content_type or "").lower()
    if not any(item in normalized_type for item in DIALOGUE_TEXT_CONTENT_TYPES):
        return data
    data = _rewrite_dialogue_path_literals(data)
    if "text/html" in normalized_type:
        data = data.replace(b"https://docs.sillytavern.app", b"/app/info.html")
        data = re.sub(
            br'<meta\s+[^>]*name=["\']generator["\'][^>]*>',
            b"",
            data,
            flags=re.IGNORECASE,
        )
    if ("javascript" in normalized_type or "text/css" in normalized_type) and b"sourceMappingURL" in data:
        # Only remove standalone source-map directives. A broad block-comment
        # regex can match text inside a minified JavaScript string (for
        # example style-loader's generated source-map data URL) and delete
        # executable syntax from the bundle.
        data = re.sub(
            br"(?m)^[ \t]*//# sourceMappingURL=[^\r\n]*(?:\r?\n)?",
            b"",
            data,
        )
        data = re.sub(
            br"(?m)^[ \t]*/\*# sourceMappingURL=[^\r\n]*\*/[ \t]*(?:\r?\n)?",
            b"",
            data,
        )
    return data


class NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


UPSTREAM_OPENER = urllib.request.build_opener(NoRedirectHandler())


def _is_local_backend(value: str) -> bool:
    try:
        parsed = urlsplit(value)
    except ValueError:
        return False
    return (
        parsed.scheme == "http"
        and parsed.hostname in {"127.0.0.1", "localhost"}
        and parsed.port is not None
        and not parsed.username
        and not parsed.password
        and parsed.path in {"", "/"}
        and not parsed.query
        and not parsed.fragment
    )


def make_handler(
    frontend_dir: Path,
    backend: str,
    state_dir: Path,
    dialogue_runtime: str = DEFAULT_DIALOGUE_RUNTIME,
    dialogue_public_dir: Path = DEFAULT_DIALOGUE_PUBLIC_DIR,
):
    backend = backend.rstrip("/")
    dialogue_runtime = dialogue_runtime.rstrip("/")
    frontend_root = frontend_dir.resolve()
    dialogue_public_root = dialogue_public_dir.resolve()
    dialogue_static_cache: dict[tuple[str, int, int], tuple[bytes, str]] = {}
    offline_script_tag = b'<script defer src="/assets/js/offline-dev.js"></script>'

    class OfflineHandler(http.server.SimpleHTTPRequestHandler):
        protocol_version = "HTTP/1.1"
        extensions_map = {
            **http.server.SimpleHTTPRequestHandler.extensions_map,
            ".js": "text/javascript",
            ".mjs": "text/javascript",
            ".json": "application/json",
            ".tpg": "application/zip",
            ".tgp": "application/zip",
            ".zip": "application/zip",
            ".thm": "application/json",
        }

        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(frontend_dir), **kwargs)

        def handle_one_request(self) -> None:
            self._serving_dialogue = False
            super().handle_one_request()

        def send_response(self, code: int, message: str | None = None) -> None:
            """Send a normal response without advertising implementation headers."""

            self.log_request(code)
            self.send_response_only(code, message)
            self.send_header("Date", self.date_time_string())

        def log_message(self, fmt: str, *args) -> None:
            sys.stdout.write(
                "[offline-proxy] %s - %s\n"
                % (self.address_string(), fmt % args)
            )
            sys.stdout.flush()

        def end_headers(self) -> None:
            self.send_header("Content-Security-Policy", OFFLINE_CSP)
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header(
                "Referrer-Policy",
                "same-origin" if getattr(self, "_serving_dialogue", False) else "no-referrer",
            )
            self.send_header(
                "Permissions-Policy",
                "camera=(), microphone=(), geolocation=(), payment=()",
            )
            self.send_header("X-Homer-Offline-Dev", "1")
            super().end_headers()

        def _request_path(self) -> str:
            try:
                return urlsplit(self.path).path
            except ValueError:
                return self.path

        def _is_api(self) -> bool:
            path = self._request_path()
            return any(path == prefix or path.startswith(prefix + "/") for prefix in API_PREFIXES)

        def _is_blocked_public_source(self) -> bool:
            path = self._request_path()
            if path.lower().endswith((".map", ".md")):
                return True
            if path in BLOCKED_PUBLIC_SOURCE_FILES:
                return True
            return any(
                path == prefix or path.startswith(prefix + "/")
                for prefix in BLOCKED_PUBLIC_SOURCE_PREFIXES
            )

        def _is_dialogue_mount(self) -> bool:
            path = self._request_path()
            return path == DIALOGUE_MOUNT or path.startswith(DIALOGUE_MOUNT + "/")

        def _is_cacheable_dialogue_asset(self) -> bool:
            if self.command not in {"GET", "HEAD"} or not getattr(self, "_serving_dialogue", False):
                return False
            path = self._request_path()
            if path.startswith(DIALOGUE_MOUNT + "/"):
                path = path[len(DIALOGUE_MOUNT):] or "/"
            return path in DIALOGUE_CACHEABLE_FILES or any(
                path == prefix or path.startswith(prefix + "/")
                for prefix in DIALOGUE_CACHEABLE_PREFIXES
            )

        def _dialogue_static_file(self) -> Path | None:
            """Resolve a read-only runtime asset without involving the runtime HTTP server."""

            if not self._is_cacheable_dialogue_asset():
                return None
            upstream_path = urlsplit(self._dialogue_upstream_path()).path
            # lib.js is a server-side Webpack entry whose bare package imports
            # must be compiled by the runtime before the browser sees it.
            if upstream_path == "/lib.js":
                return None
            try:
                parts = [unquote(part) for part in upstream_path.split("/") if part]
                if any(part in {".", ".."} or "\\" in part or "/" in part for part in parts):
                    return None
                candidate = dialogue_public_root.joinpath(*parts).resolve()
                candidate.relative_to(dialogue_public_root)
            except (OSError, ValueError):
                return None
            return candidate if candidate.is_file() else None

        def _serve_dialogue_static(self, *, include_body: bool) -> bool:
            """Serve immutable runtime code/assets directly from the website process.

            Conversation APIs, user files and generated card data deliberately do
            not enter this path, so live edits, rollback and history switching keep
            their existing real-time semantics.
            """

            source = self._dialogue_static_file()
            if source is None:
                return False
            try:
                stat = source.stat()
                content_type = mimetypes.guess_type(str(source))[0] or "application/octet-stream"
                cache_key = (str(source), stat.st_mtime_ns, stat.st_size)
                cached = dialogue_static_cache.get(cache_key)
                if cached is None:
                    data = rewrite_dialogue_payload(source.read_bytes(), content_type)
                    cached = (data, content_type)
                    for stale_key in tuple(dialogue_static_cache):
                        if stale_key[0] == str(source):
                            dialogue_static_cache.pop(stale_key, None)
                    dialogue_static_cache[cache_key] = cached
                data, content_type = cached
            except OSError:
                self.send_error(404, "File not found")
                return True
            etag = f'"{stat.st_mtime_ns:x}-{stat.st_size:x}"'
            if self.headers.get("If-None-Match") == etag:
                self.send_response(304)
                self.send_header("ETag", etag)
                self.send_header("Last-Modified", self.date_time_string(stat.st_mtime))
                self.send_header("Cache-Control", DIALOGUE_STATIC_CACHE_CONTROL)
                self.end_headers()
                return True
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("ETag", etag)
            self.send_header("Last-Modified", self.date_time_string(stat.st_mtime))
            self.send_header("Cache-Control", DIALOGUE_STATIC_CACHE_CONTROL)
            self.end_headers()
            if include_body:
                self.wfile.write(data)
            return True

        def _is_legacy_dialogue_mount(self) -> bool:
            path = self._request_path()
            return path == LEGACY_DIALOGUE_MOUNT or path.startswith(LEGACY_DIALOGUE_MOUNT + "/")

        def _has_dialogue_referer(self) -> bool:
            try:
                referer_path = urlsplit(str(self.headers.get("Referer") or "")).path
            except ValueError:
                return False
            return (
                referer_path == DIALOGUE_MOUNT
                or referer_path.startswith(DIALOGUE_MOUNT + "/")
                or referer_path == LEGACY_DIALOGUE_MOUNT
                or referer_path.startswith(LEGACY_DIALOGUE_MOUNT + "/")
            )

        def _is_dialogue_request(self) -> bool:
            if self._is_dialogue_mount():
                return True
            path = self._request_path()
            if not self._has_dialogue_referer():
                return False
            if any(
                path == prefix or path.startswith(prefix + "/")
                for prefix in SITE_OWNED_PREFIXES
            ):
                return False
            return path in DIALOGUE_ROOT_FILES or any(
                path == prefix or path.startswith(prefix + "/")
                for prefix in DIALOGUE_ROOT_PREFIXES
            )

        def _redirect(self, target: str, status: int = 302) -> None:
            # A 307/308 asks the client to replay the original method and body.
            # Drain the current body first; otherwise HTTP/1.1 keep-alive can
            # leave those bytes in this handler's socket and prefix the next
            # redirected request line with JSON/form data.
            if self.command not in {"GET", "HEAD"}:
                try:
                    self._read_request_body()
                except ValueError as exc:
                    self.send_error(400, str(exc))
                    return
                except OverflowError as exc:
                    self.send_error(413, str(exc))
                    return
            self.send_response(status)
            self.send_header("Location", target)
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", "0")
            self.end_headers()

        def _legacy_dialogue_target(self) -> str:
            parsed = urlsplit(self.path)
            suffix = parsed.path[len(LEGACY_DIALOGUE_MOUNT):] or "/"
            target = DIALOGUE_MOUNT + suffix
            return urlunsplit(("", "", target, parsed.query, parsed.fragment))

        def _dialogue_mounted_target(self) -> str:
            """Move a legacy root-relative runtime request under the module mount.

            Runtime cookies are intentionally scoped to /module/dialogue. If a
            root-relative /api or /csrf-token request is proxied in place, the
            browser cannot attach that cookie and the runtime creates a second
            session. Redirecting first keeps CSRF and session state consistent
            while retaining compatibility with unrewritten upstream URLs.
            """
            parsed = urlsplit(self.path)
            path = parsed.path or "/"
            if path == DIALOGUE_MOUNT or path.startswith(DIALOGUE_MOUNT + "/"):
                target = path
            else:
                target = DIALOGUE_MOUNT + (path if path.startswith("/") else "/" + path)
            return urlunsplit(("", "", target, parsed.query, parsed.fragment))

        def _dialogue_host_target(self) -> str:
            parsed = urlsplit(self.path)
            incoming = dict(parse_qsl(parsed.query, keep_blank_values=False))
            outgoing: list[tuple[str, str]] = []
            app_id = str(incoming.get("homer_app_id") or incoming.get("app_id") or "").strip()
            conversation_id = str(
                incoming.get("homer_conversation_id")
                or incoming.get("conversation_id")
                or incoming.get("conv_id")
                or ""
            ).strip()
            if app_id:
                outgoing.append(("app_id", app_id))
            if conversation_id:
                outgoing.append(("conversation_id", conversation_id))
            query = urlencode(outgoing)
            return DIALOGUE_HOST_ENTRY + (f"?{query}" if query else "")

        def _is_top_level_dialogue_navigation(self) -> bool:
            if self.command not in {"GET", "HEAD"} or not self._is_dialogue_mount():
                return False
            parsed = urlsplit(self.path)
            if parsed.path not in {DIALOGUE_MOUNT, DIALOGUE_MOUNT + "/", DIALOGUE_MOUNT + "/index.html"}:
                return False
            query = dict(parse_qsl(parsed.query, keep_blank_values=True))
            if query.get("homer_embed") == "1":
                return False
            destination = str(self.headers.get("Sec-Fetch-Dest") or "").lower()
            if destination == "iframe":
                return False
            return destination in {"", "document"}

        def _dialogue_upstream_path(self) -> str:
            parsed = urlsplit(self.path)
            path = parsed.path
            if path == DIALOGUE_MOUNT:
                path = "/"
            elif path.startswith(DIALOGUE_MOUNT + "/"):
                path = path[len(DIALOGUE_MOUNT):] or "/"
            for public_prefix, upstream_prefix in DIALOGUE_UPSTREAM_ALIASES.items():
                if path == public_prefix or path.startswith(public_prefix + "/"):
                    path = upstream_prefix + path[len(public_prefix):]
                    break
            return path + (f"?{parsed.query}" if parsed.query else "")

        def _local_html_file(self) -> Path | None:
            candidate = Path(self.translate_path(self.path))
            if candidate.is_dir():
                if not self._request_path().endswith("/"):
                    return None
                for index_name in ("index.html", "index.htm"):
                    index_path = candidate / index_name
                    if index_path.is_file():
                        candidate = index_path
                        break
                else:
                    return None
            if candidate.suffix.lower() not in {".html", ".htm"} or not candidate.is_file():
                return None
            try:
                candidate.resolve().relative_to(frontend_root)
            except (OSError, ValueError):
                return None
            return candidate

        def _injected_html(self, source: Path) -> bytes:
            data = source.read_bytes()
            if b"/assets/js/offline-dev.js" in data:
                return data
            head_close = re.search(br"</head\s*>", data, flags=re.IGNORECASE)
            if head_close:
                return data[: head_close.start()] + offline_script_tag + data[head_close.start() :]
            body_close = re.search(br"</body\s*>", data, flags=re.IGNORECASE)
            if body_close:
                return data[: body_close.start()] + offline_script_tag + data[body_close.start() :]
            return offline_script_tag + data

        def _serve_local_html(self, *, include_body: bool) -> bool:
            source = self._local_html_file()
            if source is None:
                return False
            try:
                data = self._injected_html(source)
                stat = source.stat()
            except OSError:
                self.send_error(404, "File not found")
                return True
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Last-Modified", self.date_time_string(stat.st_mtime))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            if include_body:
                self.wfile.write(data)
            return True

        def _read_request_body(self) -> bytes | None:
            raw_length = self.headers.get("Content-Length", "0") or "0"
            try:
                length = int(raw_length)
            except ValueError as exc:
                raise ValueError("invalid Content-Length") from exc
            if length < 0 or length > MAX_PROXY_REQUEST_BYTES:
                raise OverflowError("request body is too large")
            return self.rfile.read(length) if length else None

        def _copy_upstream_headers(self, headers, *, streaming: bool, rewritten: bool = False) -> None:
            cacheable_dialogue_asset = self._is_cacheable_dialogue_asset()
            for key, value in headers:
                lower = key.lower()
                if (
                    lower in HOP_BY_HOP_HEADERS
                    or lower in REPLACED_SECURITY_HEADERS
                    or lower in IMPLEMENTATION_HEADERS
                ):
                    continue
                # The proxy always computes/writes the downstream length for
                # buffered responses and omits it for streams.  Forwarding the
                # upstream value as well creates duplicate Content-Length
                # headers that strict HTTP clients reject.
                if lower == "content-length":
                    continue
                if cacheable_dialogue_asset and lower in {"cache-control", "expires", "pragma"}:
                    continue
                if rewritten and lower in {"content-encoding", "content-md5", "etag", "last-modified"}:
                    continue
                if lower == "location" and getattr(self, "_serving_dialogue", False):
                    try:
                        location = urlsplit(value)
                        location_path = location.path or "/"
                        if not location.scheme and not location.netloc and not value.startswith("/"):
                            self.send_header(key, value)
                            continue
                        site_owned = any(
                            location_path == prefix or location_path.startswith(prefix + "/")
                            for prefix in SITE_OWNED_PREFIXES
                        )
                        if not site_owned and not location_path.startswith(DIALOGUE_MOUNT + "/"):
                            location_path = DIALOGUE_MOUNT + location_path
                        value = urlunsplit(("", "", location_path, location.query, location.fragment))
                    except ValueError:
                        pass
                if lower == "set-cookie" and getattr(self, "_serving_dialogue", False):
                    def cookie_path(match: re.Match[str]) -> str:
                        path = match.group(2) or "/"
                        if not path.startswith(DIALOGUE_MOUNT + "/"):
                            path = DIALOGUE_MOUNT + (path if path.startswith("/") else "/" + path)
                        return match.group(1) + path

                    value = re.sub(r"(?i)(;\s*Path=)([^;]*)", cookie_path, value)
                self.send_header(key, value)
            if cacheable_dialogue_asset:
                self.send_header("Cache-Control", DIALOGUE_STATIC_CACHE_CONTROL)
            elif rewritten:
                self.send_header("Cache-Control", "no-store")
            if streaming:
                self.send_header("Cache-Control", "no-cache, no-transform")
                self.send_header("Connection", "close")

        def _stream_response(self, response) -> None:
            try:
                while True:
                    chunk = response.read1(16 * 1024)
                    if not chunk:
                        break
                    self.wfile.write(chunk)
                    self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError):
                pass
            finally:
                self.close_connection = True

        def _proxy(self, *, target: str | None = None, upstream_path: str | None = None) -> None:
            try:
                body = self._read_request_body()
            except ValueError as exc:
                self.send_error(400, str(exc))
                return
            except OverflowError as exc:
                self.send_error(413, str(exc))
                return

            request = urllib.request.Request(
                (target or backend) + (upstream_path or self.path),
                data=body,
                method=self.command,
            )
            for key, value in self.headers.items():
                lower = key.lower()
                if lower in HOP_BY_HOP_HEADERS or lower in {"host", "content-length"}:
                    continue
                if target == dialogue_runtime and lower == "accept-encoding":
                    continue
                request.add_header(key, value)
            if target == dialogue_runtime:
                request.add_header("X-Forwarded-Prefix", DIALOGUE_MOUNT)
                request.add_header("X-Forwarded-Host", str(self.headers.get("Host") or ""))
            if body is not None:
                request.add_header("Content-Length", str(len(body)))

            try:
                with UPSTREAM_OPENER.open(request, timeout=300) as response:
                    content_type = str(response.headers.get("Content-Type") or "").lower()
                    streaming = "text/event-stream" in content_type
                    if streaming:
                        self.send_response(response.status)
                        self._copy_upstream_headers(response.getheaders(), streaming=True)
                        self.end_headers()
                        self._stream_response(response)
                        return
                    raw_data = response.read()
                    data = rewrite_dialogue_payload(raw_data, content_type) if getattr(self, "_serving_dialogue", False) else raw_data
                    rewritten = data != raw_data
                    self.send_response(response.status)
                    self._copy_upstream_headers(
                        response.getheaders(),
                        streaming=False,
                        rewritten=rewritten,
                    )
                    self.send_header("Content-Length", str(len(data)))
                    self.end_headers()
                    if self.command != "HEAD":
                        self.wfile.write(data)
            except urllib.error.HTTPError as exc:
                content_type = str(exc.headers.get("Content-Type") or "").lower()
                raw_data = exc.read()
                data = rewrite_dialogue_payload(raw_data, content_type) if getattr(self, "_serving_dialogue", False) else raw_data
                self.send_response(exc.code)
                self._copy_upstream_headers(
                    exc.headers.items(),
                    streaming=False,
                    rewritten=data != raw_data,
                )
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                if self.command != "HEAD":
                    self.wfile.write(data)
            except (urllib.error.URLError, TimeoutError, http.client.HTTPException) as exc:
                if getattr(self, "_serving_dialogue", False):
                    data = "dialogue module unavailable".encode("utf-8")
                else:
                    data = ("offline backend unavailable: " + str(exc)).encode("utf-8")
                self.send_response(502)
                self.send_header("Content-Type", "text/plain; charset=utf-8")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                if self.command != "HEAD":
                    self.wfile.write(data)

        def _proxy_dialogue(self) -> None:
            self._serving_dialogue = True
            self._proxy(
                target=dialogue_runtime,
                upstream_path=self._dialogue_upstream_path(),
            )

        def do_GET(self) -> None:
            if self._request_path() == "/__offline_dev__/health":
                data = b"OFFLINE_PROXY_OK"
                self.send_response(200)
                self.send_header("Content-Type", "text/plain; charset=utf-8")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
                return
            if self._is_blocked_public_source():
                self.send_error(404)
            elif self._is_legacy_dialogue_mount():
                self._redirect(self._legacy_dialogue_target(), status=308)
            elif self._is_top_level_dialogue_navigation():
                self._redirect(self._dialogue_host_target())
            elif self._is_dialogue_request():
                if self._is_dialogue_mount():
                    self._serving_dialogue = True
                    if not self._serve_dialogue_static(include_body=True):
                        self._proxy_dialogue()
                else:
                    self._redirect(self._dialogue_mounted_target(), status=307)
            elif self._is_api():
                self._proxy()
            elif self._serve_local_html(include_body=True):
                return
            else:
                super().do_GET()

        def do_HEAD(self) -> None:
            if self._is_blocked_public_source():
                self.send_error(404)
            elif self._is_legacy_dialogue_mount():
                self._redirect(self._legacy_dialogue_target(), status=308)
            elif self._is_top_level_dialogue_navigation():
                self._redirect(self._dialogue_host_target())
            elif self._is_dialogue_request():
                if self._is_dialogue_mount():
                    self._serving_dialogue = True
                    if not self._serve_dialogue_static(include_body=False):
                        self._proxy_dialogue()
                else:
                    self._redirect(self._dialogue_mounted_target(), status=307)
            elif self._is_api():
                self._proxy()
            elif self._serve_local_html(include_body=False):
                return
            else:
                super().do_HEAD()

        def do_POST(self) -> None:
            if self._is_legacy_dialogue_mount():
                self._redirect(self._legacy_dialogue_target(), status=307)
            elif self._is_dialogue_request():
                if self._is_dialogue_mount():
                    self._proxy_dialogue()
                else:
                    self._redirect(self._dialogue_mounted_target(), status=307)
            else:
                self._proxy() if self._is_api() else self.send_error(405)

        def do_PUT(self) -> None:
            if self._is_legacy_dialogue_mount():
                self._redirect(self._legacy_dialogue_target(), status=307)
            elif self._is_dialogue_request():
                if self._is_dialogue_mount():
                    self._proxy_dialogue()
                else:
                    self._redirect(self._dialogue_mounted_target(), status=307)
            else:
                self._proxy() if self._is_api() else self.send_error(405)

        def do_PATCH(self) -> None:
            if self._is_legacy_dialogue_mount():
                self._redirect(self._legacy_dialogue_target(), status=307)
            elif self._is_dialogue_request():
                if self._is_dialogue_mount():
                    self._proxy_dialogue()
                else:
                    self._redirect(self._dialogue_mounted_target(), status=307)
            else:
                self._proxy() if self._is_api() else self.send_error(405)

        def do_DELETE(self) -> None:
            if self._is_legacy_dialogue_mount():
                self._redirect(self._legacy_dialogue_target(), status=307)
            elif self._is_dialogue_request():
                if self._is_dialogue_mount():
                    self._proxy_dialogue()
                else:
                    self._redirect(self._dialogue_mounted_target(), status=307)
            else:
                self._proxy() if self._is_api() else self.send_error(405)

        def do_OPTIONS(self) -> None:
            if self._is_legacy_dialogue_mount():
                self._redirect(self._legacy_dialogue_target(), status=307)
            elif self._is_dialogue_request():
                if self._is_dialogue_mount():
                    self._proxy_dialogue()
                else:
                    self._redirect(self._dialogue_mounted_target(), status=307)
            else:
                self._proxy() if self._is_api() else self.send_error(405)

    OfflineHandler.offline_state_dir = state_dir
    return OfflineHandler


class ThreadingOfflineServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def handle_error(self, request, client_address) -> None:
        # Browsers routinely reset speculative/keep-alive localhost sockets
        # while navigating.  Treat that as a normal disconnect so the offline
        # debug log stays focused on actionable server failures.
        error = sys.exc_info()[1]
        if isinstance(
            error,
            (BrokenPipeError, ConnectionAbortedError, ConnectionResetError),
        ):
            return
        super().handle_error(request, client_address)


def main() -> int:
    parser = argparse.ArgumentParser(description="Homer offline static/API development proxy")
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--backend", default=DEFAULT_BACKEND)
    parser.add_argument("--dialogue-runtime", default=DEFAULT_DIALOGUE_RUNTIME)
    parser.add_argument("--dialogue-public", type=Path, default=DEFAULT_DIALOGUE_PUBLIC_DIR)
    parser.add_argument("--frontend", type=Path, default=DEFAULT_FRONTEND_DIR)
    parser.add_argument("--state-dir", type=Path, default=DEFAULT_STATE_DIR)
    args = parser.parse_args()

    frontend_dir = args.frontend.resolve()
    state_dir = args.state_dir.resolve()
    if not frontend_dir.is_dir():
        parser.error(f"frontend directory does not exist: {frontend_dir}")
    if not _is_local_backend(args.backend):
        parser.error("--backend must be an explicit localhost HTTP origin")
    if not _is_local_backend(args.dialogue_runtime):
        parser.error("--dialogue-runtime must be an explicit localhost HTTP origin")
    if args.host not in {"127.0.0.1", "localhost"}:
        parser.error("offline proxy may only bind to localhost")

    mimetypes.add_type("text/javascript", ".mjs")
    handler = make_handler(
        frontend_dir,
        args.backend,
        state_dir,
        args.dialogue_runtime,
        args.dialogue_public,
    )
    with ThreadingOfflineServer((args.host, args.port), handler) as server:
        print(
            f"[offline-proxy] http://{args.host}:{args.port}/ -> {args.backend}",
            flush=True,
        )
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
