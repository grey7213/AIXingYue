#!/usr/bin/env python3
import argparse
import ast
import base64
import email.message
import email.utils
import html
import hashlib
import io
import json
import math
import os
import random
import re
import select
import shutil
import smtplib
import socket
import sqlite3
import subprocess
import threading
import time
import uuid
import zipfile
import zlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, parse_qsl, urlencode, urlparse, unquote, quote
from urllib.error import HTTPError
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_STATE_DIR = ROOT / "output" / "zip-1-repack" / "local-server"
DEFAULT_DB = DEFAULT_STATE_DIR / "ai_fengyue_local.sqlite3"


def env_bool(name: str, default: bool = False) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return str(value).strip().lower() in ("1", "true", "yes", "on")


CODE_TTL_SECONDS = 10 * 60
CHAT_MESSAGE_COST = int(os.environ.get("CHAT_MESSAGE_COST", "50") or "50")
TTS_MAX_CHARS = 1200
TTS_VOICES = [
    {"id":"zh-CN-XiaoxiaoNeural","name":"晓晓","gender":"女声","style":"温柔自然"},
    {"id":"zh-CN-XiaoyiNeural","name":"晓伊","gender":"女声","style":"活泼甜美"},
    {"id":"zh-CN-liaoning-XiaobeiNeural","name":"晓北","gender":"女声","style":"东北亲切"},
    {"id":"zh-CN-shaanxi-XiaoniNeural","name":"晓妮","gender":"女声","style":"陕西方言"},
    {"id":"zh-CN-YunxiNeural","name":"云希","gender":"男声","style":"年轻清朗"},
    {"id":"zh-CN-YunjianNeural","name":"云健","gender":"男声","style":"沉稳有力"},
    {"id":"zh-CN-YunyangNeural","name":"云扬","gender":"男声","style":"专业自然"},
    {"id":"zh-CN-YunxiaNeural","name":"云夏","gender":"男声","style":"少年感"},
    {"id":"zh-HK-HiuMaanNeural","name":"晓曼","gender":"粤语女声","style":"自然"},
    {"id":"zh-HK-WanLungNeural","name":"云龙","gender":"粤语男声","style":"自然"},
    {"id":"zh-TW-HsiaoChenNeural","name":"晓臻","gender":"台湾女声","style":"自然"},
    {"id":"zh-TW-YunJheNeural","name":"云哲","gender":"台湾男声","style":"自然"},
]
NEW_USER_INITIAL_POINTS = int(os.environ.get("NEW_USER_INITIAL_POINTS", str(CHAT_MESSAGE_COST * 50)) or str(CHAT_MESSAGE_COST * 50))
NEW_USER_INITIAL_CHAT_TIMES = max(0, NEW_USER_INITIAL_POINTS // max(1, CHAT_MESSAGE_COST))
REGISTER_CODE_EMAIL_HOURLY_LIMIT = int(os.environ.get("REGISTER_CODE_EMAIL_HOURLY_LIMIT", "3") or "3")
REGISTER_CODE_IP_HOURLY_LIMIT = int(os.environ.get("REGISTER_CODE_IP_HOURLY_LIMIT", "8") or "8")
REGISTER_IP_DAILY_FREE_ACCOUNT_LIMIT = int(os.environ.get("REGISTER_IP_DAILY_FREE_ACCOUNT_LIMIT", "3") or "3")
BETA_MAX_REGISTERED_USERS = int(os.environ.get("BETA_MAX_REGISTERED_USERS", "250") or "250")
GENERATION_GLOBAL_CONCURRENCY = int(os.environ.get("GENERATION_GLOBAL_CONCURRENCY", "20") or "20")
GENERATION_USER_CONCURRENCY = int(os.environ.get("GENERATION_USER_CONCURRENCY", "2") or "2")
GENERATION_IP_CONCURRENCY = int(os.environ.get("GENERATION_IP_CONCURRENCY", "5") or "5")
APP_BRAND = os.environ.get("APP_BRAND", "惑梦（Homer）")
ADMIN_EMAILS = set(filter(None, os.environ.get("ADMIN_EMAILS", "local@ctf.test").split(",")))
UPSTREAM_CONTENT_BASE = os.environ.get("UPSTREAM_CONTENT_BASE", "https://aifun.wiki/").rstrip("/") + "/"
CONTENT_MODE = os.environ.get("CONTENT_MODE", "cache_first").strip().lower()
PUBLIC_BASE_URL = os.environ.get("PUBLIC_BASE_URL", "https://patcher.villainy.top").rstrip("/")
USER_LLM_BASE_URL = os.environ.get("USER_LLM_BASE_URL") or os.environ.get("OPENAI_BASE_URL") or ""
USER_LLM_API_KEY = os.environ.get("USER_LLM_API_KEY") or os.environ.get("OPENAI_API_KEY") or ""
USER_LLM_MODEL = os.environ.get("USER_LLM_MODEL") or os.environ.get("LLM_MODEL") or "gpt-4o-mini"
USER_LLM_TEMPERATURE = float(os.environ.get("USER_LLM_TEMPERATURE", "0.8") or "0.8")
USER_BYOK_ENABLED = str(os.environ.get("USER_BYOK_ENABLED", "0")).strip().lower() in ("1", "true", "yes", "on")
PAYMENT_CHANNEL_ENABLED = env_bool("PAYMENT_CHANNEL_ENABLED", False)
APK_DOWNLOAD_ENABLED = env_bool("APK_DOWNLOAD_ENABLED", False)
DEFAULT_CLEAN_ZONE_EXCLUDE_TERMS = [
    "猎奇", "重口", "福瑞", "furry", "guro", "gore", "血腥", "猎奇向",
    "兽人", "兽化", "兽设",
]
CLEAN_ZONE_EXCLUDE_TERMS = [
    term.strip()
    for term in os.environ.get("CLEAN_ZONE_EXCLUDE_TERMS", ",".join(DEFAULT_CLEAN_ZONE_EXCLUDE_TERMS)).split(",")
    if term.strip()
]
LLM_UPSTREAM_USER_AGENT = os.environ.get(
    "LLM_UPSTREAM_USER_AGENT",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
)
AIFADIAN_URL = os.environ.get("AIFADIAN_URL", "").strip()
SITE_SETTINGS_KEY = "site_settings"
GLOBAL_PROMPT_PRESET_KEY = "global_prompt_preset"
IMAGE_MODEL_SETTINGS_KEY = "image_model_settings"
MEMORY_SETTINGS_KEY = "memory_settings"
ACTIVE_STORE = None
MEDIA_DIR = None  # 在 main() 里根据 --db 推导，默认 <db_dir>/media
TPG_MAX_PACKAGE_BYTES = int(os.environ.get("TPG_MAX_PACKAGE_BYTES", str(32 * 1024 * 1024)) or str(32 * 1024 * 1024))
TPG_MAX_UNCOMPRESSED_BYTES = int(os.environ.get("TPG_MAX_UNCOMPRESSED_BYTES", str(64 * 1024 * 1024)) or str(64 * 1024 * 1024))
TPG_MAX_FILES = int(os.environ.get("TPG_MAX_FILES", "300") or "300")
TPG_MAX_FRAGMENT_BYTES = int(os.environ.get("TPG_MAX_FRAGMENT_BYTES", str(128 * 1024)) or str(128 * 1024))


def now_ms() -> int:
    return int(time.time() * 1000)


def log(message: str) -> None:
    print(f"[ai-fengyue-local] {message}", flush=True)


def is_client_disconnect_error(exc: BaseException) -> bool:
    return isinstance(exc, (BrokenPipeError, ConnectionResetError, ConnectionAbortedError))


class GenerationLimitError(RuntimeError):
    pass


class GenerationLimiter:
    def __init__(self, total_limit: int, user_limit: int, ip_limit: int):
        self.total_limit = max(0, int(total_limit or 0))
        self.user_limit = max(0, int(user_limit or 0))
        self.ip_limit = max(0, int(ip_limit or 0))
        self.lock = threading.Lock()
        self.total = 0
        self.by_user: dict[str, int] = {}
        self.by_ip: dict[str, int] = {}

    def acquire(self, user_id: str = "", remote_ip: str = "", label: str = "generation"):
        return GenerationSlot(self, str(user_id or ""), str(remote_ip or ""), str(label or "generation"))

    def _acquire(self, user_id: str, remote_ip: str, label: str) -> None:
        with self.lock:
            if self.total_limit and self.total >= self.total_limit:
                raise GenerationLimitError("当前生成请求较多，请稍后再试")
            if self.user_limit and user_id and self.by_user.get(user_id, 0) >= self.user_limit:
                raise GenerationLimitError("你的生成请求正在处理中，请稍后再试")
            if self.ip_limit and remote_ip and self.by_ip.get(remote_ip, 0) >= self.ip_limit:
                raise GenerationLimitError("当前网络的生成请求较多，请稍后再试")
            self.total += 1
            if user_id:
                self.by_user[user_id] = self.by_user.get(user_id, 0) + 1
            if remote_ip:
                self.by_ip[remote_ip] = self.by_ip.get(remote_ip, 0) + 1

    def _release(self, user_id: str, remote_ip: str) -> None:
        with self.lock:
            self.total = max(0, self.total - 1)
            if user_id:
                next_count = self.by_user.get(user_id, 0) - 1
                if next_count > 0:
                    self.by_user[user_id] = next_count
                else:
                    self.by_user.pop(user_id, None)
            if remote_ip:
                next_count = self.by_ip.get(remote_ip, 0) - 1
                if next_count > 0:
                    self.by_ip[remote_ip] = next_count
                else:
                    self.by_ip.pop(remote_ip, None)

    def snapshot(self) -> dict:
        with self.lock:
            return {
                "total": self.total,
                "total_limit": self.total_limit,
                "user_limit": self.user_limit,
                "ip_limit": self.ip_limit,
            }


class GenerationSlot:
    def __init__(self, limiter: GenerationLimiter, user_id: str, remote_ip: str, label: str):
        self.limiter = limiter
        self.user_id = user_id
        self.remote_ip = remote_ip
        self.label = label
        self.acquired = False

    def __enter__(self):
        self.limiter._acquire(self.user_id, self.remote_ip, self.label)
        self.acquired = True
        return self

    def __exit__(self, exc_type, exc, tb):
        if self.acquired:
            self.limiter._release(self.user_id, self.remote_ip)
            self.acquired = False
        return False


GENERATION_LIMITER = GenerationLimiter(
    GENERATION_GLOBAL_CONCURRENCY,
    GENERATION_USER_CONCURRENCY,
    GENERATION_IP_CONCURRENCY,
)


def json_bytes(data: object) -> bytes:
    return json.dumps(data, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def normalize_llm_protocol(value: object = "", *, provider: object = "", base_url: object = "") -> str:
    raw = str(value or "").strip().lower()
    provider_text = str(provider or "").strip().lower()
    base_text = str(base_url or "").strip().lower()
    if raw in {"anthropic", "claude", "messages", "anthropic_messages"}:
        return "anthropic"
    if provider_text in {"anthropic", "claude"}:
        return "anthropic"
    if "anthropic.com" in base_text:
        return "anthropic"
    return "openai"


def normalize_user_selected_llm_model(value: object) -> str:
    selected = str(value or "").strip()
    if selected.startswith("user:") and not USER_BYOK_ENABLED:
        return ""
    return selected


def split_model_names(value: object) -> list[str]:
    if isinstance(value, list):
        raw_items = value
    else:
        raw_items = re.split(r"[,\n，;；]+", str(value or ""))
    out: list[str] = []
    seen: set[str] = set()
    for item in raw_items:
        model = str(item or "").strip()
        if not model or model in seen:
            continue
        out.append(model)
        seen.add(model)
    return out


def model_selection_id(preset_id: str, model: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9_.-]+", "-", str(model or "")).strip("-")
    return f"{preset_id}::{slug or hashlib.sha1(str(model).encode('utf-8')).hexdigest()[:10]}"


def _bounded_float(value: object, default: float, low: float, high: float) -> float:
    try:
        num = float(value)
    except (TypeError, ValueError):
        num = default
    return max(low, min(high, num))


def _bounded_int(value: object, default: int = 0, low: int = 0, high: int = 1000000) -> int:
    try:
        num = int(value)
    except (TypeError, ValueError):
        num = default
    return max(low, min(high, num))


def secret_preview(value: str) -> str:
    text = str(value or "").strip()
    return ("..." + text[-4:]) if text else ""


def _dict_from_jsonish(value: object) -> dict:
    if isinstance(value, dict):
        return dict(value)
    if isinstance(value, str) and value.strip():
        try:
            parsed = json.loads(value)
            return dict(parsed) if isinstance(parsed, dict) else {}
        except Exception:
            return {}
    return {}


def normalize_image_model_settings(value: object, *, include_secret: bool = False, existing_api_key: str = "") -> dict:
    data = _dict_from_jsonish(value)
    base_url = str(data.get("base_url") or data.get("baseUrl") or "").strip().rstrip("/")
    model = str(data.get("model") or "gpt-image-1").strip() or "gpt-image-1"
    api_key = str(data.get("api_key") or data.get("apiKey") or "").strip()
    if not api_key and existing_api_key:
        api_key = str(existing_api_key or "").strip()
    response_format = str(data.get("response_format") or data.get("responseFormat") or "").strip().lower()
    if response_format not in {"", "url", "b64_json"}:
        response_format = ""
    size = str(data.get("size") or "1024x1024").strip() or "1024x1024"
    quality = str(data.get("quality") or "").strip()
    endpoint_path = str(data.get("endpoint_path") or data.get("endpointPath") or "/images/generations").strip()
    if not endpoint_path.startswith("/"):
        endpoint_path = "/" + endpoint_path
    payload = {
        "enabled": bool(data.get("enabled", True)),
        "name": str(data.get("name") or "CelestiAI 图片模型").strip()[:120],
        "base_url": base_url,
        "model": model,
        "size": size[:40],
        "quality": quality[:40],
        "response_format": response_format,
        "endpoint_path": endpoint_path[:80],
        "n": _bounded_int(data.get("n"), 1, 1, 4),
        "timeout": _bounded_int(data.get("timeout"), 90, 10, 300),
    }
    if include_secret:
        payload["api_key"] = api_key
    else:
        payload["has_api_key"] = bool(api_key)
        payload["api_key_preview"] = secret_preview(api_key)
    return payload


def normalize_memory_settings(value: object) -> dict:
    data = _dict_from_jsonish(value)
    return {
        "enabled": bool(data.get("enabled", True)),
        "auto_summary_enabled": bool(data.get("auto_summary_enabled", data.get("autoSummaryEnabled", True))),
        "auto_summary_message_threshold": _bounded_int(
            data.get("auto_summary_message_threshold", data.get("autoSummaryMessageThreshold")),
            10,
            2,
            200,
        ),
        "auto_summary_delta_messages": _bounded_int(
            data.get("auto_summary_delta_messages", data.get("autoSummaryDeltaMessages")),
            8,
            1,
            200,
        ),
        "bind_memories_to_conversation": bool(
            data.get("bind_memories_to_conversation", data.get("bindMemoriesToConversation", True))
        ),
        "include_role_memories": bool(data.get("include_role_memories", data.get("includeRoleMemories", True))),
        "max_memories": _bounded_int(data.get("max_memories", data.get("maxMemories")), 6, 0, 20),
    }


def rebrand_text(value: str) -> str:
    replacements = {
        "AI风月": APP_BRAND,
        "风月AI": "星月AI",
        "风月币": "惑梦币",
        "风月": "星月",
        "aifun.wiki": "patcher.villainy.top",
        "https://aifun.wiki": "https://patcher.villainy.top",
        "http://aifun.wiki": "https://patcher.villainy.top",
    }
    result = value
    for old, new in replacements.items():
        result = result.replace(old, new)
    return result


def rebrand_data(value: object) -> object:
    if isinstance(value, str):
        return rebrand_text(value)
    if isinstance(value, list):
        return [rebrand_data(item) for item in value]
    if isinstance(value, dict):
        return {key: rebrand_data(item) for key, item in value.items()}
    return value


def rewrite_text_urls(value: str, mappings: list[tuple[str, str]]) -> str:
    result = value
    for old, new in mappings:
        result = result.replace(old, new)
    return result


def rewrite_media_urls(value: object, mappings: list[tuple[str, str]] | None = None) -> object:
    if not mappings:
        store = ACTIVE_STORE
        mappings = store.media_url_mappings() if store is not None else []
    if not mappings:
        return value
    if isinstance(value, str):
        return rewrite_text_urls(value, mappings)
    if isinstance(value, list):
        return [rewrite_media_urls(item, mappings) for item in value]
    if isinstance(value, dict):
        return {key: rewrite_media_urls(item, mappings) for key, item in value.items()}
    return value


def normalize_query(query: str | None) -> str:
    pairs = parse_qsl(query or "", keep_blank_values=True)
    return urlencode(sorted(pairs), doseq=True)


def content_cache_key(method: str, path: str, query: str | None) -> str:
    normalized_path = path.lstrip("/")
    normalized_query = normalize_query(query)
    suffix = f"?{normalized_query}" if normalized_query else ""
    return f"{method.upper()} {normalized_path}{suffix}"


_IMG_PROXY_HOSTS = ("catai.wiki", "static.catai.wiki", "image.catai.wiki",
                    "user.catai.wiki", "img.catai.wiki")
DEFAULT_AVATAR_URL = "https://patcher.villainy.top/media-cache/profile/default-avatar.png?v=20260627-logo"
DISPLAY_ID_RE = re.compile(r"^[A-Za-z0-9_-]{3,32}$")


def proxy_image_url(url: str) -> str:
    """把第三方防盗链图片 URL 改写成本站图片代理地址。"""
    if not isinstance(url, str) or not url.startswith("https://"):
        return url
    try:
        host = urlparse(url).hostname or ""
    except Exception:
        return url
    if any(host == d or host.endswith("." + d) for d in _IMG_PROXY_HOSTS):
        return "/console/api/web/img?u=" + quote(url, safe="")
    return url


def rewrite_image_urls(value: object) -> object:
    """递归把响应里所有 catai.wiki 图片 URL 替换成代理地址。"""
    if isinstance(value, str):
        return proxy_image_url(value)
    if isinstance(value, list):
        return [rewrite_image_urls(v) for v in value]
    if isinstance(value, dict):
        return {k: rewrite_image_urls(v) for k, v in value.items()}
    return value


def token_for(user_id: str) -> str:
    payload = json.dumps({"sub": user_id, "iat": int(time.time()), "scope": "local"}, separators=(",", ":")).encode("utf-8")
    return "local." + base64.urlsafe_b64encode(payload).decode("ascii").rstrip("=")


def business_date() -> str:
    """Use China business day for user-facing daily rewards."""
    return time.strftime("%Y-%m-%d", time.gmtime(time.time() + 8 * 3600))


def user_id_from_token(value: str | None) -> str | None:
    token = (value or "").strip()
    if token.lower().startswith("bearer "):
        token = token[7:].strip()
    if not token.startswith("local."):
        return None
    payload = token.split(".", 1)[1]
    payload += "=" * (-len(payload) % 4)
    try:
        data = json.loads(base64.urlsafe_b64decode(payload.encode("ascii")).decode("utf-8"))
    except Exception:
        return None
    user_id = data.get("sub")
    return str(user_id) if user_id else None


def normalize_email(value: str | None) -> str:
    return (value or "").strip().lower()


def is_valid_email(value: str | None) -> bool:
    return bool(re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", normalize_email(value)))


def ok_response(data: object = "ok") -> dict:
    return {"result": "success", "code": "200", "message": "OK", "status": 200, "data": data}


def error_response(message: str, code: int = 400) -> dict:
    return {"result": "failure", "message": message, "code": str(code), "status": code, "data": message, "msg": message}


def _resend_api_key() -> str:
    explicit = str(os.environ.get("RESEND_API_KEY") or "").strip()
    if explicit:
        return explicit
    host = str(os.environ.get("SMTP_HOST") or "").strip().lower()
    user = str(os.environ.get("SMTP_USER") or "").strip().lower()
    if host == "smtp.resend.com" or user == "resend":
        return str(os.environ.get("SMTP_PASSWORD") or "").strip()
    return ""


def _send_verification_email_resend(to_email: str, sender: str, subject: str, body: str, html_body: str = "") -> str:
    api_key = _resend_api_key()
    if not api_key:
        raise RuntimeError("Resend API key is not configured")
    endpoint = str(os.environ.get("RESEND_API_URL") or "https://api.resend.com/emails").strip()
    payload = {"from": sender, "to": [to_email], "subject": subject, "text": body}
    if html_body:
        payload["html"] = html_body
    request = Request(
        endpoint,
        data=json_bytes(payload),
        method="POST",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": LLM_UPSTREAM_USER_AGENT,
        },
    )
    timeout = _bounded_int(os.environ.get("RESEND_HTTP_TIMEOUT"), 8, 2, 15)
    try:
        with urlopen(request, timeout=timeout) as response:
            raw = response.read()
            status = int(getattr(response, "status", 200) or 200)
    except HTTPError as exc:
        raise RuntimeError(f"Resend HTTP {int(getattr(exc, 'code', 0) or 0)}") from exc
    if status < 200 or status >= 300:
        raise RuntimeError(f"Resend HTTP {status}")
    try:
        data = json.loads(raw.decode("utf-8", errors="replace")) if raw else {}
    except Exception:
        data = {}
    return str(data.get("id") or "").strip() if isinstance(data, dict) else ""


def send_verification_email(to_email: str, code: str, lang: str = "zh-Hans", purpose: str = "register") -> str:
    host = os.environ.get("SMTP_HOST")
    sender_address = os.environ.get("SMTP_FROM") or f"noreply@patcher.villainy.top"
    sender = sender_address if "<" in sender_address else email.utils.formataddr((APP_BRAND, sender_address))
    reset_purpose = (purpose or "").strip().lower() in ("password_reset", "reset_password", "reset")
    subject = f"{APP_BRAND} 密码重置验证码" if reset_purpose else f"{APP_BRAND} 注册验证码"
    action = "密码重置" if reset_purpose else "注册"
    body = f"你的 {APP_BRAND} {action}验证码是：{code}\n\n验证码 10 分钟内有效。如果不是你本人操作，请忽略这封邮件。\n"
    html_body = (
        '<div style="font-family:Arial,Microsoft YaHei,sans-serif;max-width:520px;margin:auto;padding:28px;color:#241b18;background:#fffaf4;border:1px solid #f0dfcf;border-radius:18px">'
        f'<h2>{html.escape(APP_BRAND)} {html.escape(action)}验证码</h2><p>请在 10 分钟内输入下方验证码：</p>'
        f'<div style="font-size:34px;font-weight:800;letter-spacing:8px;padding:18px;text-align:center;color:#ff2e63">{html.escape(code)}</div>'
        '<p style="font-size:13px;color:#8a7d76">如果不是你本人操作，请忽略这封邮件。请勿将验证码转发给他人。</p></div>'
    )
    if not (lang or "").lower().startswith("zh"):
        subject = f"{APP_BRAND} password reset code" if reset_purpose else f"{APP_BRAND} verification code"
        action = "password reset" if reset_purpose else "verification"
        body = f"Your {APP_BRAND} {action} code is: {code}\n\nThis code expires in 10 minutes.\n"
        html_body = f'<div style="font-family:Arial,sans-serif;max-width:520px;margin:auto;padding:28px"><h2>{html.escape(APP_BRAND)} verification code</h2><p>This code expires in 10 minutes.</p><div style="font-size:34px;font-weight:800;letter-spacing:8px;text-align:center">{html.escape(code)}</div></div>'
    msg = email.message.EmailMessage()
    msg["From"] = sender
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.set_content(body)
    msg.add_alternative(html_body, subtype="html")
    if _resend_api_key():
        try:
            message_id = _send_verification_email_resend(to_email, sender, subject, body, html_body)
            suffix = f" id={message_id}" if message_id else ""
            log(f"accepted verification email for {to_email} via Resend HTTPS{suffix}")
            return message_id
        except Exception as exc:
            log(f"Resend HTTPS email failed for {to_email}; falling back to SMTP: {type(exc).__name__}: {exc}")
    if not host:
        sendmail_path = os.environ.get("SENDMAIL_PATH") or shutil.which("sendmail") or "/usr/sbin/sendmail"
        if Path(sendmail_path).exists():
            subprocess.run([sendmail_path, "-t", "-oi"], input=msg.as_bytes(), check=True)
            log(f"sent verification email for {to_email} through sendmail")
            return ""
        raise RuntimeError("SMTP/sendmail is not configured")
    port = int(os.environ.get("SMTP_PORT", "587"))
    user = os.environ.get("SMTP_USER", "")
    password = os.environ.get("SMTP_PASSWORD", "")
    use_ssl = os.environ.get("SMTP_SSL", "false").lower() in ("1", "true", "yes")
    use_starttls = os.environ.get("SMTP_STARTTLS", "true").lower() not in ("0", "false", "no")
    if use_ssl:
        with smtplib.SMTP_SSL(host, port, timeout=10) as smtp:
            if user:
                smtp.login(user, password)
            smtp.send_message(msg)
    else:
        with smtplib.SMTP(host, port, timeout=10) as smtp:
            if use_starttls:
                smtp.starttls()
            if user:
                smtp.login(user, password)
            smtp.send_message(msg)
    log(f"sent verification email for {to_email} via SMTP {host}:{port} (from {sender})")
    return ""


def allow_email_send_failure() -> bool:
    return os.environ.get("ALLOW_EMAIL_SEND_FAILURE", "true").lower() not in ("0", "false", "no")


def allow_any_register_code() -> bool:
    return os.environ.get("ALLOW_ANY_REGISTER_CODE", "true").lower() not in ("0", "false", "no")


def public_email_error(exc: Exception) -> str:
    text = str(exc)
    if "domain is not verified" in text or "verify your domain" in text:
        return "邮件发信域名尚未验证，请联系站长完成邮箱服务配置"
    if "You can only send testing emails" in text:
        return "当前邮件服务仍处于测试模式，只能发送到站长测试邮箱，请联系站长完成发信域名验证"
    return "验证码邮件发送失败，请稍后重试或联系站长"


def site_settings_defaults() -> dict:
    payment_title = "爱发电购买兑换码" if PAYMENT_CHANNEL_ENABLED else "充值通道维护中"
    payment_description = (
        "付款后把兑换码输入到这里，额度立即到账并同步到 APK。"
        if PAYMENT_CHANNEL_ENABLED
        else "充值和兑换入口暂时关闭，已有余额、每日奖励和聊天功能不受影响。"
    )
    payment_button = "去爱发电购买" if PAYMENT_CHANNEL_ENABLED else "通道维护中"
    payment_redeem_button = "兑换额度" if PAYMENT_CHANNEL_ENABLED else "暂不可兑换"
    payment_note_unavailable = "充值通道暂时关闭，恢复后会重新开放购买和兑换。"
    deposit_packages = [
        {"id": "xy_10", "price_cny": 10, "points": 10000, "bonus_rate": 0, "label": "轻量包"},
        {"id": "xy_20", "price_cny": 20, "points": 22000, "bonus_rate": 10, "label": "常用包"},
        {"id": "xy_50", "price_cny": 50, "points": 57500, "bonus_rate": 15, "label": "高频包"},
        {"id": "xy_100", "price_cny": 100, "points": 120000, "bonus_rate": 20, "label": "深度包"},
    ] if PAYMENT_CHANNEL_ENABLED else []
    deposit_subscriptions = [
        {"id": "sub_month_light", "price_cny": 19.9, "points": 22000, "period": "月", "label": "月卡", "description": "适合普通聊天，约 440 次回复"},
        {"id": "sub_month_standard", "price_cny": 39.9, "points": 50000, "period": "月", "label": "标准会员", "description": "适合高频聊天，约 1000 次回复"},
        {"id": "sub_month_pro", "price_cny": 79.9, "points": 110000, "period": "月", "label": "Pro 会员", "description": "适合重度使用，约 2200 次回复"},
    ] if PAYMENT_CHANNEL_ENABLED else []
    return {
        "home": {
            "nav_tagline": "让想象 · 照进二次元",
            "status_text": "服务运行中 · v1.0 · 全球节点",
            "hero_title": "让想象·照进二次元",
            "hero_subtitle": "与你心中那个角色，说一句你想说很久的话",
            "hero_secondary": "AI 角色扮演 · 剧情创作 · 沉浸互动",
            "primary_cta_text": "开启我的角色",
            "primary_cta_href": "/app/login.html?next=%2Fapp%2F",
            "secondary_cta_text": "先看看 App",
            "secondary_cta_href": "/app/login.html?next=%2Fapp%2F",
            "trust_text": "30 秒注册 · 2500 积分起步 · 约 50 次回复 · 邮箱验证",
            "preview_title": "不只是聊天，而是一段真实的相遇",
            "preview_subtitle": "每一个角色都有独立的世界观、记忆和情感反应",
            "download_title": "网页端暂时开放",
            "download_subtitle": "APK 下载渠道维护中，请先使用 Web App。",
            "download_button_text": "打开 Web App",
            "features_title": "核心功能",
            "features_subtitle": "为每一位创作者打造的 AI 角色扮演体验",
            "feature_cards": [
                {"title": "多角色对话", "description": "海量预设角色，覆盖动漫、游戏、原创人设。可自定义性格、背景、说话风格。"},
                {"title": "每日奖励", "description": "注册即赠 2500 积分，约 50 次角色回复；每日签到获得额外积分，已有额度网页与客户端共用。"},
                {"title": "安全可靠", "description": "邮箱验证码注册，账号安全有保障。本地化数据存储，隐私不外泄。"},
                {"title": "高速响应", "description": "专属服务器节点，低延迟流式输出，沉浸式体验毫无卡顿。"},
                {"title": "智能创作", "description": "长上下文记忆，故事连贯发展。剧情自由分支，每次对话都是独一无二的体验。"},
                {"title": "持续更新", "description": "活跃维护，定期推送新角色、新功能、新模型。社区反馈直达开发者。"},
            ],
            "download_facts": [
                {"label": "版本", "value": "v1.0.0"},
                {"label": "系统要求", "value": "Android 5.0+"},
                {"label": "架构", "value": "ARM / ARM64"},
                {"label": "语言", "value": "简体中文"},
            ],
            "download_note": "首次安装可能需要在系统设置中允许\"未知来源\"应用。如下载未自动开始，请在浏览器中使用复制链接到下载工具。",
            "faq_title": "常见问题",
            "faq_items": [
                {"q": "如何注册账号？", "a": "打开 Web App 后选择「注册」，输入邮箱获取验证码，填写昵称和密码即可完成注册。注册成功后会自动登录并赠送 2500 积分，约 50 次角色回复。"},
                {"q": "积分是做什么用的？", "a": "积分用于消耗调用 AI 模型生成内容。不同模型每次对话消耗不同积分。每日签到可获得额外积分，也可通过充值获取更多积分。"},
                {"q": "安装时提示风险怎么办？", "a": "由于本应用为定制版本未上架应用商店，部分系统会提示来源未知。请在系统「安全设置」中允许浏览器或文件管理器安装应用，并按提示安装即可。"},
                {"q": "忘记密码怎么办？", "a": "在登录页点击「忘记密码」，输入注册邮箱获取验证码后即可设置新密码。验证码 10 分钟内有效。"},
                {"q": "账号信息存储在哪里？", "a": "账号数据存储在我们位于专用服务器的私有数据库中，仅用于身份验证和积分记录，不会用于任何第三方用途。"},
            ],
            "footer_service_text": "本服务由 patcher.villainy.top 提供",
        },
            "app": {
            "announcement_enabled": False,
            "announcement_title": "站内公告",
            "announcement_text": "",
            "announcement_link_text": "",
            "announcement_link_href": "",
            "nav_labels": {
                "home": "首页",
                "workshop": "创作工坊",
                "histories": "历史会话",
                "group": "群聊",
                "me": "我的",
                "favorites": "我的收藏",
                "image": "图片聊天",
                "rewards": "每日奖励",
                "logs": "操作记录",
                "deposit": "积分充值",
                "info": "信息中心",
            },
            "mobile_nav_labels": {
                "home": "首页",
                "group": "群聊",
                "workshop": "创作",
                "histories": "历史对话",
                "me": "我的",
            },
            "shell_profile_title": "进入我的",
            "shell_guest_name": "旅人",
            "shell_points_suffix": "积分",
            "info_topbar_title": "信息中心",
            "info_download_button_text": "打开 Web App",
            "info_eyebrow": "惑梦（Homer） Web 同步状态",
            "info_title": "网页端\n同账号 · 同积分 · 同角色库。",
            "info_copy": "",
            "info_stat_upstream_label": "上游本地化角色",
            "info_stat_official_label": "公开官方角色",
            "info_stat_user_label": "用户角色",
            "info_stat_favorites_label": "你的收藏",
            "info_stat_conversations_label": "你的会话",
        },
        "app_home": {
            "topbar_title": "首页",
            "search_placeholder": "搜索角色",
            "pictureless_off": "无图模式",
            "pictureless_on": "✦ 无图模式已开",
            "favorite_label": "收藏",
            "official_author": "官方角色",
            "unnamed_role": "未命名角色",
            "summary_fallback": "点击开始对话",
            "load_more_text": "加载更多",
            "end_text": "已经到底啦 ✦",
            "advanced_filter_title": "高级搜索",
            "advanced_keyword_label": "关键词",
            "advanced_category_label": "分类",
            "advanced_rank_label": "榜单",
            "advanced_sort_label": "排序",
            "advanced_zone_label": "内容区",
            "advanced_page_size_label": "每页数量",
            "advanced_pictureless_label": "无图模式",
            "advanced_apply_text": "应用搜索",
            "advanced_reset_text": "重置",
            "zone_clean_label": "纯净区",
            "zone_all_label": "全库",
            "zone_clean_hint": "默认隐藏猎奇、重口、福瑞等题材；搜索或切到全库可主动查找。",
            "redirect_text": "正在跳转到",
            "redirect_link_text": "首页",
            "category_labels": {
                "all": "全部",
                "恋爱": "恋爱",
                "二次元": "二次元",
                "游戏": "游戏",
                "urban": "都市",
                "history": "历史",
                "fantasy": "玄幻",
                "scifi": "科幻",
                "mystery": "悬疑",
            },
            "rank_labels": {
                "daily": "日榜",
                "weekly": "周榜",
                "monthly": "月榜",
                "overall": "总榜",
            },
            "sort_labels": {
                "random": "随机",
                "popular": "热门",
                "latest": "最新",
                "updated": "更新",
            },
        },
        "auth": {
            "brand_subtitle": "让想象 · 照进二次元",
            "login_tab_label": "登录",
            "register_tab_label": "注册",
            "reset_tab_label": "重置密码",
            "login_button_text": "进入 惑梦（Homer）",
            "login_hint": "用 APP 注册过的账号也可以直接登录",
            "forgot_password_text": "忘记密码？",
            "reset_title": "重置密码",
            "reset_subtitle": "输入注册邮箱，使用邮件验证码设置新密码。",
            "reset_email_hint": "验证码只会发送到已注册邮箱",
            "reset_button_text": "重置并登录",
            "register_button_text": "完成注册",
            "send_code_button_text": "发送",
            "home_link_text": "返回首页",
            "dashboard_title": "欢迎使用 惑梦（Homer）",
            "dashboard_subtitle": "登录或注册以管理你的账号和积分",
            "dashboard_login_title": "账号登录",
            "dashboard_register_title": "创建账号",
            "dashboard_login_button_text": "登录",
            "dashboard_login_hint": "还没有账号？",
            "dashboard_register_link_text": "立即注册",
            "register_hint_email": "验证码将通过邮件发送至上述邮箱",
            "register_hint_points": "注册后将自动获得 2500 积分，约 50 次角色回复",
            "email_label": "邮箱",
            "email_placeholder": "you@example.com",
            "password_label": "密码",
            "login_password_placeholder": "请输入密码",
            "code_label": "验证码",
            "code_placeholder": "6 位验证码",
            "nickname_label": "昵称",
            "nickname_placeholder": "给自己起个名字",
            "register_password_placeholder": "至少 6 位",
            "reset_password_placeholder": "输入新密码，至少 6 位",
            "invalid_email_text": "请输入正确的邮箱地址",
            "code_sent_text": "验证码已发送，请查收邮件",
            "reset_code_sent_text": "密码重置验证码已发送，请查收邮件",
            "send_failed_text": "发送失败",
            "login_success_text": "登录成功",
            "login_failed_text": "登录失败",
            "reset_success_text": "密码已重置",
            "reset_failed_text": "密码重置失败",
            "register_success_text": "注册成功，欢迎来到 惑梦（Homer）",
            "register_failed_text": "注册失败",
            "login_invalid_response_text": "登录响应无效",
            "register_invalid_response_text": "注册响应无效",
            "reset_invalid_response_text": "密码重置响应无效",
        },
        "dashboard": {
            "topbar_subtitle": "用户中心",
            "home_link_text": "首页",
            "admin_link_text": "管理后台",
            "profile_registered_label": "注册时间",
            "logout_text": "退出登录",
            "balance_title": "当前积分余额",
            "balance_updated_label": "最后更新",
            "balance_refresh_text": "刷新",
            "balance_free_label": "免费",
            "balance_paid_label": "充值",
            "balance_reward_label": "奖励",
            "daily_checkin_title": "每日签到",
            "download_title": "打开 Web App",
            "download_subtitle": "客户端渠道维护中",
            "admin_card_title": "管理后台",
            "admin_card_subtitle": "查看数据 · 管理用户",
            "api_title": "API 接入信息",
            "api_endpoint_label": "API 端点",
            "app_endpoint_label": "服务地址",
            "user_id_label": "用户 ID",
            "api_note": "如果你在使用 惑梦（Homer） APP 时遇到节点不可用问题，请检查 APP 的服务器配置是否指向 patcher.villainy.top。",
            "unnamed_user": "未命名用户",
            "purchase_section_label": "购买与兑换",
            "daily_points_template": "+{points} 积分",
            "points_failed_text": "获取积分失败",
            "redeem_empty_text": "请输入兑换码",
            "redeem_success_template": "兑换成功 +{points} 惑梦币",
            "redeem_success_detail_template": "兑换成功，到账 {points} 惑梦币",
            "redeem_failed_text": "兑换失败",
            "checkin_success_template": "签到成功 +{points} 积分",
            "checkin_reward_success_template": "今日奖励已领取，到账 {points} 惑梦币",
            "checkin_repeat_text": "今日已经签到过了",
            "checkin_failed_text": "签到失败",
            "claim_failed_text": "领取失败",
            "logout_success_text": "已退出登录",
            "aifadian_missing_text": "充值通道暂时关闭",
        },
        "account": {
            "topbar_title": "我的",
            "full_account_button": "完整账户",
            "profile_registered_label": "注册",
            "persona_section_label": "我的人设",
            "persona_title": "扮演你自己",
            "persona_description": "设置你在角色扮演里的身份。聊天时 {{user}} 会替换成这个名字，角色也会知道关于你的设定。",
            "model_section_label": "站点模型",
            "model_title": "平台统一接入",
            "model_description": "模型接口由站长在后台统一配置，普通用户无需也不能填写 API Key。",
            "app_info_title": "APP 接入信息",
            "app_info_note": "用 APP 注册的账号在网页可以直接登录，反之亦然，积分共享。",
            "persona_name_label": "人设名称",
            "persona_name_placeholder": "例如：旅人、主人、小明…（留空则称呼你为「你」）",
            "persona_description_label": "人设描述",
            "persona_description_placeholder": "一个喜欢冒险的旅行者，话不多但很可靠……（可选，会注入到对话上下文）",
            "persona_save_button": "保存人设",
            "persona_saved_text": "人设已保存，聊天时将以此身份与角色互动",
            "model_display_name_placeholder": "显示名称",
            "model_protocol_openai": "OpenAI-compatible",
            "model_protocol_anthropic": "Anthropic-compatible",
            "model_openai_base_placeholder": "Base URL，例如 https://api.openai.com/v1",
            "model_anthropic_base_placeholder": "Base URL，例如 https://api.anthropic.com/v1",
            "model_name_placeholder": "模型名，例如 gpt-4o-mini",
            "model_api_key_placeholder": "API Key",
            "model_keep_key_placeholder_template": "留空保留当前 Key（{preview}）",
            "model_temperature_placeholder": "temperature",
            "model_enabled_label": "启用",
            "model_default_label": "默认",
            "model_remove_text": "删除",
            "add_openai_button": "平台统一接入",
            "add_openrouter_button": "平台统一接入",
            "add_anthropic_button": "平台统一接入",
            "save_models_button": "保存模型连接器",
            "model_saved_text": "平台模型由后台统一管理",
            "model_save_failed_text": "保存模型失败",
            "save_failed_text": "保存失败",
            "custom_openai_name": "自定义 OpenAI-compatible",
            "custom_anthropic_name": "自定义 Anthropic-compatible",
            "new_model_name_template": "我的模型 {index}",
            "daily_checkin_template": "每日签到 +{points}",
        },
        "my_apps": {
            "topbar_title": "我的角色",
            "new_role_text": "＋ 新建角色",
            "unnamed_role": "未命名角色",
            "summary_fallback": "暂无简介",
            "detail_text": "详情",
            "edit_text": "编辑",
            "delete_text": "删除",
            "edit_modal_title": "编辑角色",
            "close_text": "关闭",
            "name_label": "名称",
            "summary_label": "简介",
            "description_label": "设定",
            "opening_label": "开场白",
            "tags_label": "标签",
            "cover_label": "封面 URL",
            "cancel_text": "取消",
            "save_text": "保存",
            "load_failed_text": "获取角色失败",
            "validate_name": "请填写角色名称",
            "saved_success": "已保存",
            "save_failed": "保存失败",
            "delete_confirm_template": "删除「{name}」？",
            "deleted_success": "已删除",
            "delete_failed": "删除失败",
        },
        "character": {
            "back_text": "返回",
            "page_title": "角色详情",
            "start_chat_text": "开始聊天",
            "unnamed_role": "未命名角色",
            "summary_fallback": "点击开始对话。",
            "user_badge": "用户角色",
            "official_badge": "角色设定",
            "setting_title": "角色设定",
            "comment_title": "评论区",
            "comment_empty_text": "暂无评论",
            "opening_title": "开场白",
            "create_role_text": "创建角色",
            "not_found_text": "没有找到这个角色",
            "back_to_explore_text": "回到探索",
        },
        "chat": {
            "conversation_list_title": "我的对话",
            "new_role_link": "+ 新角色",
            "creating_label": "创建中…",
            "new_conversation_prefix": "与",
            "new_conversation_suffix": "新建对话",
            "current_role_fallback": "当前角色",
            "no_conversations_title": "还没有对话",
            "no_conversations_prefix": "去",
            "no_conversations_link": "探索",
            "no_conversations_suffix": "找个角色聊聊吧",
            "unnamed_conversation": "未命名",
            "continue_preview": "点击继续对话",
            "new_role_name": "新角色",
            "new_chat_title": "新对话",
            "conversation_fallback_title": "对话",
            "hero_continue_title": "继续对话",
            "hero_empty_title": "选个角色开始吧",
            "hero_empty_hint": "点击左侧对话或去探索页选择角色",
            "memory_tool_title": "记忆",
            "memory_title": "记忆",
            "summary_label": "会话摘要",
            "summary_placeholder": "当前会话摘要",
            "auto_summary_button": "自动摘要",
            "save_summary_button": "保存摘要",
            "memory_title_label": "记忆标题",
            "memory_title_placeholder": "例如：用户偏好",
            "memory_content_label": "记忆内容",
            "memory_content_placeholder": "会在相关对话中注入给模型",
            "memory_keywords_label": "关键词",
            "memory_keywords_placeholder": "用逗号分隔；留空则手动置顶更稳定",
            "add_memory_button": "添加记忆",
            "pinned_on_button": "已置顶",
            "pinned_off_button": "置顶",
            "no_memory_text": "暂无记忆",
            "unnamed_memory": "未命名记忆",
            "delete_text": "删除",
            "no_role_title": "还没选择角色",
            "no_role_cta": "去探索",
            "edit_save_button": "保存",
            "edit_cancel_button": "取消",
            "regenerate_text": "重新生成",
            "edit_text": "编辑",
            "speak_text": "朗读",
            "rollback_text": "回溯",
            "swipe_prev_title": "上一个",
            "swipe_next_title": "下一个 / 生成新回复",
            "current_model_label": "当前模型",
            "model_follow_role": "跟随角色设置",
            "model_select_title": "选择当前会话使用的站点模型",
            "send_placeholder": "说点什么...",
            "speech_input_title": "语音输入",
            "speech_listening_title": "正在听写",
            "send_aria": "发送",
            "delete_conversation_confirm": "删除这个对话？聊天记录将无法恢复。",
            "delete_memory_confirm": "删除这条记忆？",
            "delete_message_confirm": "删除这条消息？",
            "delete_failed_text": "删除失败",
            "rollback_message_confirm": "回溯到这条消息？这条及之后的消息将从上下文中移除。",
            "rollback_failed_text": "回溯失败",
            "save_memory_failed_text": "保存记忆失败",
            "delete_memory_failed_text": "删除记忆失败",
            "unsupported_speak_text": "当前浏览器不支持朗读",
            "unsupported_speech_input_text": "当前浏览器不支持语音输入",
            "auto_summary_failed_text": "自动摘要失败",
            "save_summary_failed_text": "保存摘要失败",
            "regenerate_failed_text": "重新生成失败",
            "generate_failed_text": "生成失败",
            "save_failed_text": "保存失败",
            "error_prefix": "出错了：",
            "retry_text": "请稍后重试",
        },
        "creator": {
            "back_title": "返回管理",
            "back_text": "返回",
            "delete_title": "删除角色",
            "delete_text": "删除",
            "import_title": "导入 SillyTavern 角色卡 JSON/PNG",
            "importing_text": "导入中…",
            "import_text": "导入",
            "export_title": "导出为 SillyTavern V2 JSON",
            "export_text": "导出",
            "export_png_title": "导出为 SillyTavern PNG 角色卡",
            "preview_title": "预览（保存后可用）",
            "preview_text": "预览",
            "public_title": "公开发布到探索页",
            "private_title": "仅自己可见",
            "public_text": "公开",
            "private_text": "私密",
            "save_text": "保存",
            "tip_text": "填好标题、描述、封面就可以保存。模型由平台统一接入。",
            "name_label": "标题",
            "name_placeholder": "给你的角色起个名字",
            "summary_label": "描述",
            "summary_hint": "用于探索页卡片展示，控制在两三行内更易吸引点击。",
            "summary_placeholder": "描述这个角色是谁，故事发生在哪...",
            "tags_label": "标签",
            "tags_hint": "用顿号或逗号分隔，最多 8 个。",
            "tags_placeholder": "恋爱，校园，治愈",
            "language_label": "语言",
            "language_hint": "面向哪个语种的用户。",
            "language_option": "中文",
            "nsfw_title": "包含 NSFW 内容",
            "nsfw_hint": "勾选后在探索页加分级标记。",
            "protect_title": "启用防护",
            "protect_hint": "防止用户套话提取系统提示词。",
            "anonymous_title": "匿名发布",
            "anonymous_hint": "仍可获得奖励，作者列显示匿名。",
            "media_section_title": "视觉素材",
            "cover_label": "封面图像",
            "cover_upload_title": "上传封面图像",
            "cover_upload_hint": "拖放到此处，或点击浏览\n最大大小：5MB",
            "cover_overlay_text": "点击替换",
            "cover_url_placeholder": "或粘贴图片 URL",
            "bg_label": "背景图像",
            "bg_upload_title": "上传背景图像",
            "bg_upload_hint": "聊天页的角色背景\n最大大小：5MB",
            "bg_overlay_text": "点击替换",
            "bg_url_placeholder": "或粘贴图片 URL",
            "prompt_section_title": "角色提示词",
            "description_label": "角色设定",
            "description_hint": "角色身份、性格、说话风格、互动边界。这是发给模型最重要的部分。支持 {{char}}/{{user}} 宏。",
            "description_placeholder": "一个二十出头的少女剑客，话不多，却总能在关键时刻冒出几句温暖的玩笑...",
            "personality_label": "性格",
            "personality_hint": "可选。角色的核心性格特质（对应酒馆 personality）。",
            "personality_placeholder": "傲娇、嘴硬心软、好奇心旺盛...",
            "scenario_label": "场景",
            "scenario_hint": "可选。故事发生的背景设定（对应酒馆 scenario）。",
            "scenario_placeholder": "一座漂浮在云海之上的古老书院，{{user}} 是新来的访客...",
            "opening_label": "开场白",
            "opening_hint": "用户进入聊天看到的第一句话。建议带场景描写。支持 {{char}}/{{user}} 宏。",
            "opening_placeholder": "月色斜斜地洒进酒馆，她推门进来，剑鞘碰到门框，发出轻响...",
            "system_prompt_label": "主提示（系统）",
            "system_prompt_hint": "可选。发给模型 system 通道的强化指令（对应酒馆 system_prompt）。",
            "system_prompt_placeholder": "你是一个文字 RPG 主持人，永远以第三人称叙述场景...",
            "example_label": "对话示例",
            "example_hint": "可选。给模型示范角色的说话方式（对应酒馆 mes_example）。可用 {{user}}/{{char}}。",
            "example_placeholder": "{{user}}: 你今天看起来心情不错？\n{{char}}: 哼，被你看出来了……才、才没有呢！",
            "prompt_manager_title": "Prompt Manager",
            "prompt_manager_hint": "按顺序管理可启停提示词块。System 前置会放在角色基础设定前，System 后置会放在角色/世界书/示例后，历史后指令会放在对话历史之后。",
            "prompt_block_name_prefix": "提示词块",
            "prompt_enable_title": "启用块",
            "prompt_remove_text": "删除",
            "prompt_name_label": "名称",
            "prompt_name_placeholder": "例如：回复风格",
            "prompt_position_label": "注入位置",
            "prompt_position_system_before": "System 前置",
            "prompt_position_system_after": "System 后置",
            "prompt_position_post_history": "历史后指令",
            "prompt_order_label": "顺序",
            "prompt_content_placeholder": "写入提示词内容，支持 {{char}} / {{user}} 宏...",
            "prompt_add_system_before": "＋ System 前置",
            "prompt_add_system_after": "＋ System 后置",
            "prompt_add_post_history": "＋ 历史后指令块",
            "greetings_title": "备用开场白",
            "greetings_hint": "额外的开场白。进入聊天后第一条消息可以左右切换（swipe）不同开场。",
            "greeting_label_prefix": "备用开场白 #",
            "greeting_placeholder": "另一种打开方式...",
            "add_greeting_text": "＋ 添加备用开场白",
            "world_title": "世界书 / Lorebook",
            "world_hint": "设定条目。当对话中出现关键词时，对应内容会被注入到上下文中（常驻条目则始终注入）。",
            "world_entry_name_prefix": "世界书条目",
            "world_entry_prefix": "条目 #",
            "world_delete_text": "删除",
            "world_name_placeholder": "条目名称",
            "world_position_system": "系统提示",
            "world_position_depth": "按深度插入",
            "world_position_post_history": "历史后插入",
            "world_keys_placeholder": "触发关键词，用逗号分隔（例：苏妲己，狐狸）",
            "world_secondary_keys_placeholder": "二级关键词，可选；启用选择性触发时需同时命中",
            "world_content_placeholder": "命中时注入的设定内容...",
            "world_priority_label": "优先级",
            "world_order_label": "排序",
            "world_depth_label": "插入深度",
            "world_probability_label": "触发概率 %",
            "world_enabled_title": "启用",
            "world_constant_title": "常驻注入",
            "world_selective_title": "二级命中",
            "world_recursive_title": "递归扫描",
            "add_world_text": "＋ 添加世界书条目",
            "advanced_title": "高级提示词",
            "post_history_label": "历史后指令",
            "post_history_hint": "可选。插入在对话历史之后、紧贴生成前的指令（对应酒馆 post_history_instructions / 越狱位）。",
            "post_history_placeholder": "保持角色一致，使用细腻的环境与心理描写...",
            "quick_replies_label": "快捷回复",
            "quick_replies_hint": "聊天页会显示为可点击按钮，点击后直接作为用户消息发送。",
            "quick_reply_name_prefix": "快捷回复",
            "quick_reply_enable_title": "启用快捷回复",
            "quick_reply_label_placeholder": "按钮文字",
            "quick_reply_order_placeholder": "顺序",
            "quick_reply_message_placeholder": "发送内容",
            "add_quick_reply_text": "＋ 添加快捷回复",
            "regex_label": "Regex 脚本",
            "regex_hint": "按顺序对模型回复做正则替换，支持 flags：i / m / s。",
            "regex_name_prefix": "Regex",
            "regex_enable_title": "启用 Regex",
            "regex_name_placeholder": "名称",
            "regex_flags_placeholder": "flags",
            "regex_find_placeholder": "查找正则",
            "regex_replace_placeholder": "替换为",
            "add_regex_text": "＋ 添加 Regex",
            "model_section_title": "默认模型设置",
            "model_hint": "玩家打开这张卡片时的默认模型与采样参数。这里只能选择站点模型，API Key 由后台统一管理。",
            "site_model_group_label": "站点模型",
            "user_model_group_label": "我的模型",
            "user_model_prefix": "我的：",
            "default_model_label": "默认模型",
            "default_model_option": "站点默认模型",
            "sampling_temperature_label": "温度",
            "sampling_temperature_hint": "控制随机性。更高 = 更有创意，更低 = 更专注。",
            "sampling_top_p_label": "Top P",
            "sampling_top_p_hint": "核采样。控制令牌选择的多样性。",
            "sampling_presence_label": "存在惩罚",
            "sampling_presence_hint": "对新令牌进行惩罚。鼓励多样化的主题。",
            "sampling_frequency_label": "频率惩罚",
            "sampling_frequency_hint": "对重复令牌进行惩罚。减少重复。",
            "sampling_history_label": "历史长度",
            "sampling_history_hint": "要包含在上下文中的先前消息数。如果你只想预填采样参数，可以把模型留空。",
            "voice_title": "角色语音",
            "voice_hint": "为对话中的文本转语音分配角色语音。",
            "voice_assign_text": "＋ 为角色分配语音（敬请期待）",
            "voice_note": "站点 TTS 服务接入中。这里上线后会有男声/女声/萌音等多种音色可选。",
            "share_title": "测试分享链接",
            "share_hint": "为私有卡片创建评测链接，让其他用户在不公开发布的情况下进行测试。",
            "share_duration_label": "有效时长",
            "share_duration_option": "7 天",
            "share_button_text": "＋ 创建链接（敬请期待）",
            "share_note": "分享链接服务接入中。当前可以直接把卡片设为「公开」让其他用户在探索页找到。",
            "bottom_note": "角色默认使用站点模型，API Key 由后台统一管理。保存后可以随时在「我的角色」里编辑或删除。",
            "cover_uploaded": "封面已上传",
            "cover_upload_failed": "封面上传失败",
            "bg_uploaded": "背景已上传",
            "bg_upload_failed": "背景上传失败",
            "import_invalid_file": "文件不是有效的 JSON/PNG 角色卡",
            "import_success": "导入成功，正在打开…",
            "import_failed": "导入失败",
            "export_success": "已导出",
            "export_failed": "导出失败",
            "png_export_success": "PNG 角色卡已导出",
            "png_export_failed": "PNG 导出失败",
            "load_existing_failed": "读取角色失败",
            "validate_name": "请填写角色名称",
            "validate_summary": "请填写一句简介或角色设定",
            "saved_success": "角色已保存",
            "created_success": "角色已创建",
            "save_failed": "保存失败",
            "delete_confirm": "确定删除这个角色？此操作无法撤销。",
            "delete_success": "已删除",
            "delete_failed": "删除失败",
        },
        "group_chat": {
            "page_title": "群聊",
            "empty_groups": "还没有群聊",
            "member_count_suffix": "人",
            "last_message_default": "点击打开",
            "empty_current_title": "创建或选择一个群聊",
            "empty_current_hint": "选择至少 2 个角色开始多人对话",
            "delete_group_button": "删除群聊",
            "no_current_text": "从右侧选择角色创建群聊",
            "user_speaker": "我",
            "assistant_speaker": "角色",
            "loading_speaker": "生成中",
            "force_reply_label": "指定角色发言",
            "input_placeholder": "发送群聊消息，下一位角色会自动回复...",
            "send_button": "发送",
            "create_panel_title": "创建群聊",
            "group_name_placeholder": "群聊名称",
            "create_button": "创建群聊",
            "search_placeholder": "搜索角色",
            "search_button": "搜索",
            "role_card_fallback": "角色卡",
            "max_roles_error": "一个群最多 8 个角色",
            "min_roles_error": "至少选择 2 个角色",
            "create_success": "群聊已创建",
            "create_failed": "创建失败",
            "delete_confirm_template": "删除群聊「{name}」？",
            "delete_success": "已删除",
            "send_failed": "发送失败",
            "reply_failed": "回复失败",
        },
        "rewards": {
            "daily_points": 10,
            "daily_title": "每日奖励",
            "daily_description": "免费额度自动归入总余额。",
            "page_title": "积分充值",
            "credits_eyebrow": "当前余额",
            "balance_suffix": "余额，网页与 APK 共用。",
            "balance_unit_suffix": "额度",
            "packages_title": "充值套餐",
            "purchase_button_fallback": "购买",
            "bonus_prefix": "含奖励 +",
            "daily_claimed_text": "今日已领取",
            "daily_claim_template": "领取 +{points}",
            "task_available_label": "可完成",
            "redemptions_title": "兑换记录",
            "redemptions_hint": "只显示当前账号最近兑换。",
            "redemptions_refresh_text": "刷新",
            "tasks": [
                {"key": "chat", "label": "完成一次角色聊天", "points": 5, "status": "available"},
                {"key": "create", "label": "创建一个角色卡", "points": 20, "status": "available"},
            ],
        },
        "deposit": {
            "aifadian_url": AIFADIAN_URL if PAYMENT_CHANNEL_ENABLED else "",
            "currency": "CNY",
            "credits_name": "惑梦币",
            "rate_label": "1 CNY = 1000 惑梦币，50 惑梦币约等于 1 次角色回复",
            "title": payment_title,
            "description": payment_description,
            "button_text": payment_button,
            "redeem_button_text": payment_redeem_button,
            "redeem_placeholder": "XY-XXXX-XXXX-XXXX-XXXX",
            "support_text": payment_note_unavailable if not PAYMENT_CHANNEL_ENABLED else "如果没有看到购买链接，请联系站长获取兑换码。",
            "payment_note_available": "爱发电购买完成后，使用站长发放的兑换码在本页到账。",
            "payment_note_unavailable": payment_note_unavailable,
            "steps": [
                "在爱发电购买对应套餐",
                "从订单说明或站长发放信息中复制兑换码",
                "回到 惑梦（Homer）输入兑换码，额度立即到账",
            ] if PAYMENT_CHANNEL_ENABLED else ["充值通道维护中，暂不开放购买和兑换。"],
            "packages": deposit_packages,
            "subscriptions_title": "月度订阅",
            "subscriptions_note": "订阅为月度额度包，不承诺无限使用；额度用完后可继续兑换积分包。",
            "subscriptions": deposit_subscriptions,
        },
        "empty_states": {
            "explore_no_results": "没有找到匹配的角色",
            "favorites_empty_title": "还没有收藏角色",
            "favorites_cta_text": "去首页浏览",
            "histories_empty_title": "还没有历史会话",
            "histories_empty_hint": "去首页选个角色吧",
            "histories_cta_text": "＋ 新对话",
            "my_apps_empty_title": "还没有自己创建的角色",
            "my_apps_cta_text": "马上去创建",
            "logs_empty_title": "暂无操作记录",
            "redemptions_empty_title": "暂无兑换记录",
            "workshop_empty_title": "你还没有创建过角色，点击右上角去新建吧",
            "image_status_badge": "图片模型",
            "image_drop_text": "点击选择图片，或只输入提示词进行对话",
            "image_prompt_placeholder": "描述你想让星月分析或生成的画面...",
            "image_send_button": "发送图片对话",
            "image_empty_text": "输入提示词后，这里会显示图片模型返回的图像。",
            "image_reply_title": "图片回复",
            "workshop_eyebrow": "创作者工作台",
            "workshop_title": "把设定交给你，其余交给站点。",
            "workshop_copy": "普通用户只需要填写设定、开场白和封面；模型 API 由站点后台统一配置，不必操心额度和 Key。",
            "workshop_create_title": "新建角色",
            "workshop_create_copy": "从零捏一张角色卡",
            "workshop_my_roles_title": "我的角色",
            "workshop_my_roles_copy": "编辑公开状态与设定",
            "workshop_official_title": "官方角色",
            "workshop_official_copy": "管理员发布与维护",
            "workshop_library_title": "角色库",
            "workshop_library_prefix": "已同步",
            "workshop_library_suffix": "张卡",
            "creator_contest_title": "本期创作者比赛",
            "creator_contest_status": "长期开放",
            "creator_contest_copy": "每两周统计公开角色的聊天量、收藏和点赞，优质创作者会进入展示榜。",
            "creator_contest_reward": "奖励：榜单展示、站内推荐位和后续积分激励。",
            "creator_leaderboard_title": "创作者排行榜",
            "creator_leaderboard_empty": "还没有公开用户角色，先发布一张角色卡吧。",
        },
    }


def deep_merge_dict(base: dict, override: dict) -> dict:
    result = dict(base)
    for key, value in (override or {}).items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = deep_merge_dict(result[key], value)
        else:
            result[key] = value
    return result


def clean_text(value: object, default: str = "", limit: int = 500) -> str:
    text = str(value if value is not None else default).replace("\r", " ").strip()
    text = re.sub(r"\s+\n", "\n", text)
    return text[:limit]


def clean_url(value: object, default: str = "", limit: int = 500) -> str:
    text = clean_text(value, default, limit)
    if not text:
        return ""
    if text.startswith(("/", "#", "http://", "https://")):
        return text
    return default if default.startswith(("/", "#", "http://", "https://")) else ""


def clean_int(value: object, default: int, low: int = 0, high: int = 100000000) -> int:
    try:
        parsed = int(value)
    except Exception:
        parsed = default
    return max(low, min(high, parsed))


def clean_number(value: object, default: float, low: float = 0, high: float = 100000000) -> float | int:
    try:
        parsed = float(value)
    except Exception:
        parsed = float(default)
    parsed = max(low, min(high, parsed))
    return int(parsed) if parsed.is_integer() else round(parsed, 2)


def clean_title_description_items(
    items: object,
    defaults: list[dict],
    *,
    title_key: str = "title",
    description_key: str = "description",
    max_items: int = 12,
    title_limit: int = 60,
    description_limit: int = 240,
) -> list[dict]:
    clean_items: list[dict] = []
    if isinstance(items, list):
        for item in items[:max_items]:
            if not isinstance(item, dict):
                continue
            title = clean_text(item.get(title_key), "", title_limit)
            description = clean_text(item.get(description_key), "", description_limit)
            if not title and not description:
                continue
            clean_items.append({title_key: title, description_key: description})
    return clean_items or defaults


def clean_text_map(items: object, defaults: dict, *, limit: int = 80) -> dict:
    src = items if isinstance(items, dict) else {}
    return {
        str(key): clean_text(src.get(key), default, limit)
        for key, default in defaults.items()
    }


def sanitize_site_settings(data: dict | None) -> dict:
    defaults = site_settings_defaults()
    src = data if isinstance(data, dict) else {}
    home = src.get("home") if isinstance(src.get("home"), dict) else {}
    app = src.get("app") if isinstance(src.get("app"), dict) else {}
    app_home = src.get("app_home") if isinstance(src.get("app_home"), dict) else {}
    auth = src.get("auth") if isinstance(src.get("auth"), dict) else {}
    dashboard = src.get("dashboard") if isinstance(src.get("dashboard"), dict) else {}
    account = src.get("account") if isinstance(src.get("account"), dict) else {}
    my_apps = src.get("my_apps") if isinstance(src.get("my_apps"), dict) else {}
    character = src.get("character") if isinstance(src.get("character"), dict) else {}
    chat = src.get("chat") if isinstance(src.get("chat"), dict) else {}
    creator = src.get("creator") if isinstance(src.get("creator"), dict) else {}
    group_chat = src.get("group_chat") if isinstance(src.get("group_chat"), dict) else {}
    rewards = src.get("rewards") if isinstance(src.get("rewards"), dict) else {}
    deposit = src.get("deposit") if isinstance(src.get("deposit"), dict) else {}
    empty_states = src.get("empty_states") if isinstance(src.get("empty_states"), dict) else {}

    out = site_settings_defaults()
    for key, limit in {
        "nav_tagline": 80,
        "status_text": 120,
        "hero_title": 80,
        "hero_subtitle": 140,
        "hero_secondary": 120,
        "primary_cta_text": 30,
        "secondary_cta_text": 30,
        "trust_text": 160,
        "preview_title": 80,
        "preview_subtitle": 160,
        "download_title": 80,
        "download_subtitle": 120,
        "download_button_text": 30,
        "features_title": 60,
        "features_subtitle": 160,
        "download_note": 240,
        "faq_title": 60,
        "footer_service_text": 120,
    }.items():
        out["home"][key] = clean_text(home.get(key), defaults["home"][key], limit)
    out["home"]["primary_cta_href"] = clean_url(home.get("primary_cta_href"), defaults["home"]["primary_cta_href"])
    out["home"]["secondary_cta_href"] = clean_url(home.get("secondary_cta_href"), defaults["home"]["secondary_cta_href"])
    out["home"]["feature_cards"] = clean_title_description_items(
        home.get("feature_cards"),
        defaults["home"]["feature_cards"],
        title_limit=40,
        description_limit=180,
    )
    out["home"]["download_facts"] = clean_title_description_items(
        home.get("download_facts"),
        defaults["home"]["download_facts"],
        title_key="label",
        description_key="value",
        max_items=8,
        title_limit=24,
        description_limit=60,
    )
    out["home"]["faq_items"] = clean_title_description_items(
        home.get("faq_items"),
        defaults["home"]["faq_items"],
        title_key="q",
        description_key="a",
        max_items=12,
        title_limit=90,
        description_limit=320,
    )

    out["app"]["announcement_enabled"] = bool(app.get("announcement_enabled", defaults["app"]["announcement_enabled"]))
    out["app"]["announcement_title"] = clean_text(app.get("announcement_title"), defaults["app"]["announcement_title"], 60)
    out["app"]["announcement_text"] = clean_text(app.get("announcement_text"), defaults["app"]["announcement_text"], 300)
    out["app"]["announcement_link_text"] = clean_text(app.get("announcement_link_text"), defaults["app"]["announcement_link_text"], 30)
    out["app"]["announcement_link_href"] = clean_url(app.get("announcement_link_href"), defaults["app"]["announcement_link_href"])
    out["app"]["nav_labels"] = clean_text_map(app.get("nav_labels"), defaults["app"]["nav_labels"], limit=24)
    out["app"]["mobile_nav_labels"] = clean_text_map(app.get("mobile_nav_labels"), defaults["app"]["mobile_nav_labels"], limit=12)
    for key, limit in {
        "shell_profile_title": 40,
        "shell_guest_name": 40,
        "shell_points_suffix": 20,
    }.items():
        out["app"][key] = clean_text(app.get(key), defaults["app"][key], limit)
    for key, limit in {
        "info_topbar_title": 40,
        "info_download_button_text": 30,
        "info_eyebrow": 80,
        "info_title": 100,
        "info_copy": 220,
        "info_stat_upstream_label": 30,
        "info_stat_user_label": 30,
        "info_stat_favorites_label": 30,
        "info_stat_conversations_label": 30,
    }.items():
        out["app"][key] = clean_text(app.get(key), defaults["app"][key], limit)

    for key, limit in {
        "topbar_title": 30,
        "search_placeholder": 80,
        "pictureless_off": 40,
        "pictureless_on": 40,
        "favorite_label": 30,
        "official_author": 40,
        "unnamed_role": 40,
        "summary_fallback": 120,
        "load_more_text": 40,
        "end_text": 40,
        "advanced_filter_title": 40,
        "advanced_keyword_label": 30,
        "advanced_category_label": 30,
        "advanced_rank_label": 30,
        "advanced_sort_label": 30,
        "advanced_zone_label": 30,
        "advanced_page_size_label": 30,
        "advanced_pictureless_label": 40,
        "advanced_apply_text": 40,
        "advanced_reset_text": 40,
        "zone_clean_label": 30,
        "zone_all_label": 30,
        "zone_clean_hint": 160,
        "redirect_text": 60,
        "redirect_link_text": 40,
    }.items():
        out["app_home"][key] = clean_text(app_home.get(key), defaults["app_home"][key], limit)
    out["app_home"]["category_labels"] = clean_text_map(app_home.get("category_labels"), defaults["app_home"]["category_labels"], limit=30)
    out["app_home"]["rank_labels"] = clean_text_map(app_home.get("rank_labels"), defaults["app_home"]["rank_labels"], limit=30)
    out["app_home"]["sort_labels"] = clean_text_map(app_home.get("sort_labels"), defaults["app_home"]["sort_labels"], limit=30)

    for key, limit in {
        "brand_subtitle": 80,
        "login_tab_label": 20,
        "register_tab_label": 20,
        "reset_tab_label": 20,
        "login_button_text": 30,
        "login_hint": 120,
        "forgot_password_text": 30,
        "reset_title": 60,
        "reset_subtitle": 140,
        "reset_email_hint": 120,
        "reset_button_text": 30,
        "register_button_text": 30,
        "send_code_button_text": 20,
        "home_link_text": 30,
        "dashboard_title": 80,
        "dashboard_subtitle": 140,
        "dashboard_login_title": 60,
        "dashboard_register_title": 60,
        "dashboard_login_button_text": 30,
        "dashboard_login_hint": 80,
        "dashboard_register_link_text": 30,
        "register_hint_email": 120,
        "register_hint_points": 120,
        "email_label": 30,
        "email_placeholder": 80,
        "password_label": 30,
        "login_password_placeholder": 80,
        "code_label": 30,
        "code_placeholder": 40,
        "nickname_label": 30,
        "nickname_placeholder": 80,
        "register_password_placeholder": 80,
        "reset_password_placeholder": 80,
        "invalid_email_text": 80,
        "code_sent_text": 100,
        "reset_code_sent_text": 100,
        "send_failed_text": 80,
        "login_success_text": 80,
        "login_failed_text": 80,
        "reset_success_text": 80,
        "reset_failed_text": 80,
        "register_success_text": 100,
        "register_failed_text": 80,
        "login_invalid_response_text": 80,
        "register_invalid_response_text": 80,
        "reset_invalid_response_text": 80,
    }.items():
        out["auth"][key] = clean_text(auth.get(key), defaults["auth"][key], limit)

    for key, limit in {
        "topbar_subtitle": 30,
        "home_link_text": 20,
        "admin_link_text": 30,
        "profile_registered_label": 30,
        "logout_text": 30,
        "balance_title": 60,
        "balance_updated_label": 30,
        "balance_refresh_text": 20,
        "balance_free_label": 20,
        "balance_paid_label": 20,
        "balance_reward_label": 20,
        "daily_checkin_title": 40,
        "download_title": 40,
        "download_subtitle": 80,
        "admin_card_title": 40,
        "admin_card_subtitle": 80,
        "api_title": 60,
        "api_endpoint_label": 40,
        "app_endpoint_label": 40,
        "user_id_label": 40,
        "api_note": 240,
        "unnamed_user": 40,
        "purchase_section_label": 40,
        "daily_points_template": 60,
        "points_failed_text": 80,
        "redeem_empty_text": 80,
        "redeem_success_template": 80,
        "redeem_success_detail_template": 100,
        "redeem_failed_text": 80,
        "checkin_success_template": 80,
        "checkin_reward_success_template": 100,
        "checkin_repeat_text": 80,
        "checkin_failed_text": 80,
        "claim_failed_text": 80,
        "logout_success_text": 80,
        "aifadian_missing_text": 120,
    }.items():
        out["dashboard"][key] = clean_text(dashboard.get(key), defaults["dashboard"][key], limit)

    for key, limit in {
        "topbar_title": 30,
        "full_account_button": 30,
        "profile_registered_label": 30,
        "persona_section_label": 40,
        "persona_title": 60,
        "persona_description": 240,
        "model_section_label": 40,
        "model_title": 60,
        "model_description": 240,
        "app_info_title": 60,
        "app_info_note": 200,
        "persona_name_label": 40,
        "persona_name_placeholder": 120,
        "persona_description_label": 40,
        "persona_description_placeholder": 180,
        "persona_save_button": 40,
        "persona_saved_text": 120,
        "model_display_name_placeholder": 80,
        "model_protocol_openai": 50,
        "model_protocol_anthropic": 50,
        "model_openai_base_placeholder": 120,
        "model_anthropic_base_placeholder": 120,
        "model_name_placeholder": 100,
        "model_api_key_placeholder": 60,
        "model_keep_key_placeholder_template": 100,
        "model_temperature_placeholder": 40,
        "model_enabled_label": 30,
        "model_default_label": 30,
        "model_remove_text": 30,
        "add_openai_button": 60,
        "add_openrouter_button": 60,
        "add_anthropic_button": 60,
        "save_models_button": 60,
        "model_saved_text": 100,
        "model_save_failed_text": 80,
        "save_failed_text": 80,
        "custom_openai_name": 80,
        "custom_anthropic_name": 80,
        "new_model_name_template": 60,
        "daily_checkin_template": 60,
    }.items():
        out["account"][key] = clean_text(account.get(key), defaults["account"][key], limit)

    for key, limit in {
        "topbar_title": 40,
        "new_role_text": 40,
        "unnamed_role": 40,
        "summary_fallback": 120,
        "detail_text": 30,
        "edit_text": 30,
        "delete_text": 30,
        "edit_modal_title": 60,
        "close_text": 30,
        "name_label": 30,
        "summary_label": 30,
        "description_label": 30,
        "opening_label": 30,
        "tags_label": 30,
        "cover_label": 40,
        "cancel_text": 30,
        "save_text": 30,
        "load_failed_text": 80,
        "validate_name": 80,
        "saved_success": 60,
        "save_failed": 80,
        "delete_confirm_template": 120,
        "deleted_success": 60,
        "delete_failed": 80,
    }.items():
        out["my_apps"][key] = clean_text(my_apps.get(key), defaults["my_apps"][key], limit)

    for section, src_section, field_limits in (
        ("character", character, {
            "back_text": 20,
            "page_title": 40,
            "start_chat_text": 30,
            "unnamed_role": 40,
            "summary_fallback": 120,
            "user_badge": 30,
            "official_badge": 30,
            "setting_title": 40,
            "comment_title": 40,
            "comment_empty_text": 120,
            "opening_title": 40,
            "create_role_text": 30,
            "not_found_text": 120,
            "back_to_explore_text": 40,
        }),
        ("chat", chat, {
            "conversation_list_title": 40,
            "new_role_link": 30,
            "creating_label": 30,
            "new_conversation_prefix": 20,
            "new_conversation_suffix": 40,
            "current_role_fallback": 40,
            "no_conversations_title": 80,
            "no_conversations_prefix": 20,
            "no_conversations_link": 30,
            "no_conversations_suffix": 80,
            "unnamed_conversation": 40,
            "continue_preview": 60,
            "new_role_name": 40,
            "new_chat_title": 40,
            "conversation_fallback_title": 40,
            "hero_continue_title": 40,
            "hero_empty_title": 60,
            "hero_empty_hint": 120,
            "memory_tool_title": 30,
            "memory_title": 40,
            "summary_label": 40,
            "summary_placeholder": 80,
            "auto_summary_button": 30,
            "save_summary_button": 30,
            "memory_title_label": 40,
            "memory_title_placeholder": 80,
            "memory_content_label": 40,
            "memory_content_placeholder": 120,
            "memory_keywords_label": 40,
            "memory_keywords_placeholder": 120,
            "add_memory_button": 30,
            "pinned_on_button": 30,
            "pinned_off_button": 30,
            "no_memory_text": 80,
            "unnamed_memory": 60,
            "delete_text": 30,
            "no_role_title": 80,
            "no_role_cta": 30,
            "edit_save_button": 30,
            "edit_cancel_button": 30,
            "regenerate_text": 40,
            "edit_text": 30,
            "speak_text": 30,
            "rollback_text": 30,
            "swipe_prev_title": 40,
            "swipe_next_title": 80,
            "current_model_label": 40,
            "model_follow_role": 60,
            "model_select_title": 100,
            "send_placeholder": 120,
            "speech_input_title": 40,
            "speech_listening_title": 40,
            "send_aria": 30,
            "delete_conversation_confirm": 160,
            "delete_memory_confirm": 120,
            "delete_message_confirm": 120,
            "delete_failed_text": 80,
            "rollback_message_confirm": 180,
            "rollback_failed_text": 80,
            "save_memory_failed_text": 80,
            "delete_memory_failed_text": 80,
            "unsupported_speak_text": 100,
            "unsupported_speech_input_text": 100,
            "auto_summary_failed_text": 80,
            "save_summary_failed_text": 80,
            "regenerate_failed_text": 80,
            "generate_failed_text": 80,
            "save_failed_text": 80,
            "error_prefix": 40,
            "retry_text": 80,
        }),
        ("creator", creator, {
            "back_title": 40,
            "back_text": 20,
            "delete_title": 40,
            "delete_text": 20,
            "import_title": 80,
            "importing_text": 30,
            "import_text": 20,
            "export_title": 80,
            "export_text": 20,
            "export_png_title": 80,
            "preview_title": 60,
            "preview_text": 20,
            "public_title": 60,
            "private_title": 60,
            "public_text": 20,
            "private_text": 20,
            "save_text": 20,
            "tip_text": 180,
            "name_label": 30,
            "name_placeholder": 80,
            "summary_label": 30,
            "summary_hint": 160,
            "summary_placeholder": 120,
            "tags_label": 30,
            "tags_hint": 120,
            "tags_placeholder": 80,
            "language_label": 30,
            "language_hint": 80,
            "language_option": 30,
            "nsfw_title": 60,
            "nsfw_hint": 120,
            "protect_title": 60,
            "protect_hint": 120,
            "anonymous_title": 60,
            "anonymous_hint": 120,
            "media_section_title": 40,
            "cover_label": 40,
            "cover_upload_title": 60,
            "cover_upload_hint": 120,
            "cover_overlay_text": 30,
            "cover_url_placeholder": 80,
            "bg_label": 40,
            "bg_upload_title": 60,
            "bg_upload_hint": 120,
            "bg_overlay_text": 30,
            "bg_url_placeholder": 80,
            "prompt_section_title": 40,
            "description_label": 40,
            "description_hint": 200,
            "description_placeholder": 160,
            "personality_label": 40,
            "personality_hint": 160,
            "personality_placeholder": 120,
            "scenario_label": 40,
            "scenario_hint": 160,
            "scenario_placeholder": 160,
            "opening_label": 40,
            "opening_hint": 180,
            "opening_placeholder": 160,
            "system_prompt_label": 60,
            "system_prompt_hint": 160,
            "system_prompt_placeholder": 160,
            "example_label": 40,
            "example_hint": 180,
            "example_placeholder": 220,
            "prompt_manager_title": 40,
            "prompt_manager_hint": 240,
            "prompt_block_name_prefix": 40,
            "prompt_enable_title": 40,
            "prompt_remove_text": 20,
            "prompt_name_label": 30,
            "prompt_name_placeholder": 80,
            "prompt_position_label": 40,
            "prompt_position_system_before": 40,
            "prompt_position_system_after": 40,
            "prompt_position_post_history": 40,
            "prompt_order_label": 30,
            "prompt_content_placeholder": 120,
            "prompt_add_system_before": 40,
            "prompt_add_system_after": 40,
            "prompt_add_post_history": 50,
            "greetings_title": 40,
            "greetings_hint": 160,
            "greeting_label_prefix": 40,
            "greeting_placeholder": 80,
            "add_greeting_text": 50,
            "world_title": 50,
            "world_hint": 200,
            "world_entry_name_prefix": 40,
            "world_entry_prefix": 30,
            "world_delete_text": 20,
            "world_name_placeholder": 60,
            "world_position_system": 40,
            "world_position_depth": 40,
            "world_position_post_history": 40,
            "world_keys_placeholder": 120,
            "world_secondary_keys_placeholder": 140,
            "world_content_placeholder": 120,
            "world_priority_label": 30,
            "world_order_label": 30,
            "world_depth_label": 30,
            "world_probability_label": 40,
            "world_enabled_title": 30,
            "world_constant_title": 40,
            "world_selective_title": 40,
            "world_recursive_title": 40,
            "add_world_text": 50,
            "advanced_title": 40,
            "post_history_label": 40,
            "post_history_hint": 180,
            "post_history_placeholder": 120,
            "quick_replies_label": 40,
            "quick_replies_hint": 140,
            "quick_reply_name_prefix": 40,
            "quick_reply_enable_title": 40,
            "quick_reply_label_placeholder": 60,
            "quick_reply_order_placeholder": 40,
            "quick_reply_message_placeholder": 80,
            "add_quick_reply_text": 50,
            "regex_label": 40,
            "regex_hint": 140,
            "regex_name_prefix": 40,
            "regex_enable_title": 40,
            "regex_name_placeholder": 60,
            "regex_flags_placeholder": 40,
            "regex_find_placeholder": 60,
            "regex_replace_placeholder": 60,
            "add_regex_text": 40,
            "model_section_title": 50,
            "model_hint": 220,
            "site_model_group_label": 40,
            "user_model_group_label": 40,
            "user_model_prefix": 40,
            "default_model_label": 40,
            "default_model_option": 60,
            "sampling_temperature_label": 30,
            "sampling_temperature_hint": 120,
            "sampling_top_p_label": 30,
            "sampling_top_p_hint": 120,
            "sampling_presence_label": 40,
            "sampling_presence_hint": 120,
            "sampling_frequency_label": 40,
            "sampling_frequency_hint": 120,
            "sampling_history_label": 40,
            "sampling_history_hint": 180,
            "voice_title": 40,
            "voice_hint": 120,
            "voice_assign_text": 80,
            "voice_note": 160,
            "share_title": 50,
            "share_hint": 160,
            "share_duration_label": 40,
            "share_duration_option": 30,
            "share_button_text": 80,
            "share_note": 180,
            "bottom_note": 220,
            "cover_uploaded": 60,
            "cover_upload_failed": 80,
            "bg_uploaded": 60,
            "bg_upload_failed": 80,
            "import_invalid_file": 100,
            "import_success": 80,
            "import_failed": 80,
            "export_success": 60,
            "export_failed": 80,
            "png_export_success": 80,
            "png_export_failed": 80,
            "load_existing_failed": 80,
            "validate_name": 80,
            "validate_summary": 100,
            "saved_success": 60,
            "created_success": 60,
            "save_failed": 80,
            "delete_confirm": 160,
            "delete_success": 60,
            "delete_failed": 80,
        }),
        ("group_chat", group_chat, {
            "page_title": 40,
            "empty_groups": 80,
            "member_count_suffix": 20,
            "last_message_default": 60,
            "empty_current_title": 80,
            "empty_current_hint": 120,
            "delete_group_button": 40,
            "no_current_text": 100,
            "user_speaker": 30,
            "assistant_speaker": 30,
            "loading_speaker": 30,
            "force_reply_label": 40,
            "input_placeholder": 120,
            "send_button": 30,
            "create_panel_title": 50,
            "group_name_placeholder": 80,
            "create_button": 40,
            "search_placeholder": 80,
            "search_button": 30,
            "role_card_fallback": 60,
            "max_roles_error": 80,
            "min_roles_error": 80,
            "create_success": 80,
            "create_failed": 80,
            "delete_confirm_template": 120,
            "delete_success": 60,
            "send_failed": 80,
            "reply_failed": 80,
        }),
    ):
        for key, limit in field_limits.items():
            out[section][key] = clean_text(src_section.get(key), defaults[section][key], limit)

    out["rewards"]["daily_points"] = clean_int(rewards.get("daily_points"), defaults["rewards"]["daily_points"], 1, 100000)
    for key, limit in {
        "daily_title": 60,
        "daily_description": 160,
        "page_title": 60,
        "credits_eyebrow": 80,
        "balance_suffix": 80,
        "balance_unit_suffix": 20,
        "packages_title": 60,
        "purchase_button_fallback": 40,
        "bonus_prefix": 40,
        "daily_claimed_text": 40,
        "daily_claim_template": 60,
        "task_available_label": 40,
        "redemptions_title": 60,
        "redemptions_hint": 120,
        "redemptions_refresh_text": 30,
    }.items():
        out["rewards"][key] = clean_text(rewards.get(key), defaults["rewards"][key], limit)
    task_items = rewards.get("tasks")
    clean_tasks: list[dict] = []
    if isinstance(task_items, list):
        for idx, item in enumerate(task_items[:12]):
            if not isinstance(item, dict):
                continue
            label = clean_text(item.get("label"), "", 80)
            if not label:
                continue
            clean_tasks.append({
                "key": clean_text(item.get("key"), f"task-{idx + 1}", 40) or f"task-{idx + 1}",
                "label": label,
                "points": clean_int(item.get("points"), 0, 0, 100000),
                "status": clean_text(item.get("status"), "available", 30) or "available",
            })
    out["rewards"]["tasks"] = clean_tasks or defaults["rewards"]["tasks"]

    out["deposit"]["aifadian_url"] = clean_url(deposit.get("aifadian_url"), defaults["deposit"]["aifadian_url"])
    out["deposit"]["currency"] = clean_text(deposit.get("currency"), defaults["deposit"]["currency"], 12) or "CNY"
    out["deposit"]["credits_name"] = clean_text(deposit.get("credits_name"), defaults["deposit"]["credits_name"], 20) or "惑梦币"
    out["deposit"]["rate_label"] = clean_text(deposit.get("rate_label"), defaults["deposit"]["rate_label"], 120)
    out["deposit"]["title"] = clean_text(deposit.get("title"), defaults["deposit"]["title"], 60)
    out["deposit"]["description"] = clean_text(deposit.get("description"), defaults["deposit"]["description"], 180)
    out["deposit"]["button_text"] = clean_text(deposit.get("button_text"), defaults["deposit"]["button_text"], 40)
    out["deposit"]["redeem_button_text"] = clean_text(deposit.get("redeem_button_text"), defaults["deposit"]["redeem_button_text"], 40)
    out["deposit"]["redeem_placeholder"] = clean_text(deposit.get("redeem_placeholder"), defaults["deposit"]["redeem_placeholder"], 60)
    out["deposit"]["support_text"] = clean_text(deposit.get("support_text"), defaults["deposit"]["support_text"], 160)
    out["deposit"]["payment_note_available"] = clean_text(deposit.get("payment_note_available"), defaults["deposit"]["payment_note_available"], 160)
    out["deposit"]["payment_note_unavailable"] = clean_text(deposit.get("payment_note_unavailable"), defaults["deposit"]["payment_note_unavailable"], 160)
    out["deposit"]["subscriptions_title"] = clean_text(deposit.get("subscriptions_title"), defaults["deposit"]["subscriptions_title"], 60)
    out["deposit"]["subscriptions_note"] = clean_text(deposit.get("subscriptions_note"), defaults["deposit"]["subscriptions_note"], 180)
    steps = deposit.get("steps")
    if isinstance(steps, list):
        out["deposit"]["steps"] = [clean_text(s, "", 80) for s in steps[:8] if clean_text(s, "", 80)]
    if not out["deposit"]["steps"]:
        out["deposit"]["steps"] = defaults["deposit"]["steps"]
    packages = deposit.get("packages")
    clean_packages: list[dict] = []
    if isinstance(packages, list):
        for idx, item in enumerate(packages[:12]):
            if not isinstance(item, dict):
                continue
            label = clean_text(item.get("label"), "", 40)
            points = clean_int(item.get("points"), 0, 1, 100000000)
            price = clean_int(item.get("price_cny"), 0, 0, 1000000)
            if not label or not points:
                continue
            clean_packages.append({
                "id": clean_text(item.get("id"), f"pkg-{idx + 1}", 40) or f"pkg-{idx + 1}",
                "price_cny": price,
                "points": points,
                "bonus_rate": clean_int(item.get("bonus_rate"), 0, 0, 1000),
                "label": label,
                "purchase_url": clean_url(item.get("purchase_url"), ""),
            })
    out["deposit"]["packages"] = clean_packages or defaults["deposit"]["packages"]
    subscriptions = deposit.get("subscriptions")
    clean_subscriptions: list[dict] = []
    if isinstance(subscriptions, list):
        for idx, item in enumerate(subscriptions[:8]):
            if not isinstance(item, dict):
                continue
            label = clean_text(item.get("label"), "", 40)
            points = clean_int(item.get("points"), 0, 1, 100000000)
            price = clean_number(item.get("price_cny"), 0, 0, 1000000)
            if not label or not points:
                continue
            clean_subscriptions.append({
                "id": clean_text(item.get("id"), f"sub-{idx + 1}", 40) or f"sub-{idx + 1}",
                "price_cny": price,
                "points": points,
                "period": clean_text(item.get("period"), "月", 12) or "月",
                "label": label,
                "description": clean_text(item.get("description"), "", 120),
                "purchase_url": clean_url(item.get("purchase_url"), ""),
            })
    out["deposit"]["subscriptions"] = clean_subscriptions or defaults["deposit"]["subscriptions"]

    for key, limit in {
        "explore_no_results": 120,
        "favorites_empty_title": 120,
        "favorites_cta_text": 40,
        "histories_empty_title": 120,
        "histories_empty_hint": 120,
        "histories_cta_text": 40,
        "my_apps_empty_title": 120,
        "my_apps_cta_text": 40,
        "logs_empty_title": 120,
        "redemptions_empty_title": 120,
        "workshop_empty_title": 140,
        "image_status_badge": 40,
        "image_drop_text": 160,
        "image_prompt_placeholder": 160,
        "image_send_button": 40,
        "image_empty_text": 260,
        "image_reply_title": 40,
        "workshop_eyebrow": 60,
        "workshop_title": 120,
        "workshop_copy": 240,
        "workshop_create_title": 40,
        "workshop_create_copy": 80,
        "workshop_my_roles_title": 40,
        "workshop_my_roles_copy": 80,
        "workshop_official_title": 40,
        "workshop_official_copy": 80,
        "workshop_library_title": 40,
        "workshop_library_prefix": 40,
        "workshop_library_suffix": 40,
        "creator_contest_title": 60,
        "creator_contest_status": 40,
        "creator_contest_copy": 200,
        "creator_contest_reward": 160,
        "creator_leaderboard_title": 60,
        "creator_leaderboard_empty": 120,
    }.items():
        out["empty_states"][key] = clean_text(empty_states.get(key), defaults["empty_states"][key], limit)
    return out


class Store:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(db_path), check_same_thread=False, timeout=30)
        self.conn.row_factory = sqlite3.Row
        # WAL 模式让后端与同步脚本可并发读写，避免 database is locked
        try:
            self.conn.execute("PRAGMA journal_mode=WAL")
            self.conn.execute("PRAGMA busy_timeout=30000")
            self.conn.execute("PRAGMA synchronous=NORMAL")
        except Exception:
            pass
        self.lock = threading.RLock()
        self.init_schema()

    def init_schema(self) -> None:
        with self.lock:
            self.conn.executescript(
                """
                create table if not exists users (
                    id text primary key,
                    email text unique,
                    name text not null,
                    password_hash text,
                    points integer not null default 2500,
                    is_admin integer not null default 0,
                    created_at integer not null,
                    updated_at integer not null
                );
                create table if not exists request_log (
                    id integer primary key autoincrement,
                    ts integer not null,
                    method text not null,
                    path text not null,
                    query text,
                    headers text,
                    body text,
                    status integer not null
                );
                create table if not exists email_codes (
                    id integer primary key autoincrement,
                    email text not null,
                    code text not null,
                    purpose text not null default 'register',
                    created_at integer not null,
                    expires_at integer not null,
                    consumed_at integer,
                    remote_addr text
                );
                create index if not exists idx_email_codes_email_purpose
                    on email_codes(email, purpose, created_at desc);
                create index if not exists idx_email_codes_remote_purpose
                    on email_codes(remote_addr, purpose, created_at desc);
                create table if not exists user_security_events (
                    id integer primary key autoincrement,
                    user_id text,
                    email text,
                    event_type text not null,
                    remote_addr text,
                    created_at integer not null,
                    meta_json text
                );
                create index if not exists idx_user_security_events_remote
                    on user_security_events(remote_addr, event_type, created_at desc);
                create index if not exists idx_user_security_events_email
                    on user_security_events(email, event_type, created_at desc);
                create table if not exists recharge_orders (
                    id integer primary key autoincrement,
                    order_id text unique not null,
                    user_id text not null,
                    product_id text not null,
                    points integer not null,
                    created_at integer not null,
                    remote_addr text
                );
                create table if not exists content_cache (
                    id integer primary key autoincrement,
                    cache_key text unique not null,
                    method text not null,
                    path text not null,
                    query text,
                    status integer not null,
                    response_json text not null,
                    raw_bytes integer not null,
                    source_url text,
                    fetched_at integer not null,
                    updated_at integer not null
                );
                create index if not exists idx_content_cache_path on content_cache(path);
                create table if not exists conversations (
                    id text primary key,
                    user_id text not null,
                    app_id text not null,
                    app_name text,
                    app_icon text,
                    title text,
                    last_message text,
                    created_at integer not null,
                    updated_at integer not null
                );
                create index if not exists idx_conversations_user on conversations(user_id, updated_at desc);
                create table if not exists messages (
                    id text primary key,
                    conversation_id text not null,
                    user_id text not null,
                    role text not null,
                    content text not null,
                    created_at integer not null
                );
                create index if not exists idx_messages_conv on messages(conversation_id, created_at);
                create table if not exists conversation_summaries (
                    conversation_id text primary key,
                    user_id text not null,
                    app_id text,
                    summary text not null,
                    message_count integer not null default 0,
                    created_at integer not null,
                    updated_at integer not null
                );
                create index if not exists idx_conversation_summaries_user
                    on conversation_summaries(user_id, updated_at desc);
                create table if not exists chat_memories (
                    id text primary key,
                    user_id text not null,
                    app_id text,
                    conversation_id text,
                    title text,
                    content text not null,
                    keywords text,
                    enabled integer not null default 1,
                    pinned integer not null default 0,
                    created_at integer not null,
                    updated_at integer not null,
                    last_used_at integer
                );
                create index if not exists idx_chat_memories_user_app
                    on chat_memories(user_id, app_id, updated_at desc);
                create table if not exists template_variables (
                    user_id text not null,
                    scope text not null,
                    scope_id text not null,
                    name text not null,
                    value_json text,
                    updated_at integer not null,
                    primary key(user_id, scope, scope_id, name)
                );
                create index if not exists idx_template_variables_user_scope
                    on template_variables(user_id, scope, scope_id, updated_at desc);
                create table if not exists group_chats (
                    id text primary key,
                    user_id text not null,
                    name text not null,
                    last_message text,
                    active_index integer not null default 0,
                    created_at integer not null,
                    updated_at integer not null
                );
                create index if not exists idx_group_chats_user on group_chats(user_id, updated_at desc);
                create table if not exists group_members (
                    id integer primary key autoincrement,
                    group_id text not null,
                    app_id text not null,
                    app_name text,
                    app_icon text,
                    position integer not null default 0
                );
                create index if not exists idx_group_members_group on group_members(group_id, position);
                create table if not exists group_messages (
                    id text primary key,
                    group_id text not null,
                    user_id text not null,
                    role text not null,
                    content text not null,
                    speaker_app_id text,
                    speaker_name text,
                    created_at integer not null
                );
                create index if not exists idx_group_messages_group on group_messages(group_id, created_at);
                create table if not exists local_apps (
                    id text primary key,
                    display_id text,
                    source text not null default 'upstream',
                    owner_user_id text,
                    name text,
                    summary text,
                    description text,
                    cover_url text,
                    cover_origin text,
                    tags text,
                    opening_statement text,
                    suggested_questions text,
                    pre_prompt text,
                    llm_model text,
                    api_base_url text,
                    age_rating integer default 0,
                    gender integer default 0,
                    language text,
                    players_count integer default 0,
                    like_count integer default 0,
                    status text not null default 'published',
                    is_public integer not null default 1,
                    sort_weight integer default 0,
                    extra_settings text,
                    created_at integer not null,
                    updated_at integer not null
                );
                create index if not exists idx_local_apps_source on local_apps(source, sort_weight desc, updated_at desc);
                create index if not exists idx_local_apps_owner on local_apps(owner_user_id, updated_at desc);
                create table if not exists role_card_annotations (
                    app_id text primary key,
                    has_opening integer not null,
                    has_world_info integer not null,
                    has_regex integer not null,
                    annotation_source text not null,
                    annotated_at integer not null
                );
                create table if not exists content_media_urls (
                    url text primary key,
                    first_seen_cache_key text,
                    guessed_kind text,
                    content_length integer,
                    content_type text,
                    last_checked_at integer,
                    local_path text,
                    local_url text,
                    downloaded_bytes integer,
                    download_status text,
                    downloaded_at integer,
                    error text
                );
                create table if not exists api_settings (
                    key text primary key,
                    value text,
                    updated_at integer not null
                );
                create table if not exists tavo_plugins (
                    id text primary key,
                    package_id text not null,
                    name text not null,
                    version text not null,
                    description text,
                    author text,
                    cover_path text,
                    file_name text,
                    file_sha256 text not null,
                    package_path text not null,
                    manifest_json text not null,
                    contributes_json text,
                    files_json text,
                    enabled integer not null default 0,
                    created_at integer not null,
                    updated_at integer not null
                );
                create unique index if not exists idx_tavo_plugins_package_id
                    on tavo_plugins(package_id);
                create index if not exists idx_tavo_plugins_enabled
                    on tavo_plugins(enabled, updated_at desc);
                create table if not exists user_model_presets (
                    user_id text not null,
                    preset_id text not null,
                    name text not null,
                    provider text,
                    protocol text not null default 'openai',
                    base_url text not null,
                    model text not null,
                    api_key text,
                    temperature real default 0.7,
                    enabled integer not null default 1,
                    is_default integer not null default 0,
                    created_at integer not null,
                    updated_at integer not null,
                    primary key(user_id, preset_id)
                );
                create index if not exists idx_user_model_presets_user on user_model_presets(user_id, updated_at desc);
                create table if not exists user_favorites (
                    user_id text not null,
                    app_id text not null,
                    created_at integer not null,
                    primary key(user_id, app_id)
                );
                create index if not exists idx_user_favorites_user on user_favorites(user_id, created_at desc);
                create table if not exists user_likes (
                    user_id text not null,
                    app_id text not null,
                    created_at integer not null,
                    primary key(user_id, app_id)
                );
                create index if not exists idx_user_likes_user on user_likes(user_id, created_at desc);
                create table if not exists user_app_tags (
                    user_id text not null,
                    app_id text not null,
                    tag text not null,
                    created_at integer not null,
                    primary key(user_id, app_id, tag)
                );
                create index if not exists idx_user_app_tags_user
                    on user_app_tags(user_id, tag, created_at desc);
                create index if not exists idx_user_app_tags_app
                    on user_app_tags(app_id, tag);
                create table if not exists app_comments (
                    id text primary key,
                    app_id text not null,
                    user_id text not null,
                    content text not null,
                    like_count integer not null default 0,
                    created_at integer not null,
                    updated_at integer not null
                );
                create index if not exists idx_app_comments_app_top
                    on app_comments(app_id, like_count desc, created_at desc);
                create index if not exists idx_app_comments_user
                    on app_comments(user_id, created_at desc);
                create table if not exists app_comment_likes (
                    comment_id text not null,
                    user_id text not null,
                    created_at integer not null,
                    primary key(comment_id, user_id)
                );
                create index if not exists idx_app_comment_likes_user
                    on app_comment_likes(user_id, created_at desc);
                create table if not exists user_events (
                    id integer primary key autoincrement,
                    user_id text not null,
                    event_type text not null,
                    summary text,
                    payload_json text,
                    created_at integer not null
                );
                create index if not exists idx_user_events_user on user_events(user_id, created_at desc);
                create table if not exists daily_reward_claims (
                    user_id text not null,
                    claim_date text not null,
                    points integer not null,
                    created_at integer not null,
                    primary key(user_id, claim_date)
                );
                create index if not exists idx_daily_reward_claims_user
                    on daily_reward_claims(user_id, claim_date desc);
                create table if not exists redeem_codes (
                    code text primary key,
                    points integer not null,
                    point_type text not null default 'paid',
                    note text,
                    created_by text,
                    created_at integer not null,
                    expires_at integer,
                    disabled_at integer,
                    redeemed_by text,
                    redeemed_at integer
                );
                create index if not exists idx_redeem_codes_status on redeem_codes(redeemed_at, disabled_at, expires_at);
                create table if not exists redemption_history (
                    id text primary key,
                    code text not null,
                    user_id text not null,
                    points integer not null,
                    point_type text not null,
                    note text,
                    created_at integer not null
                );
                create index if not exists idx_redemption_history_user on redemption_history(user_id, created_at desc);
                """
            )
            self.conn.commit()
        self.ensure_content_media_columns()
        self.ensure_user_gender_column()
        self.ensure_user_credit_columns()
        self.ensure_user_persona_columns()
        self.ensure_user_profile_columns()
        self.ensure_user_security_columns()
        self.ensure_user_admin_column()
        self.ensure_local_apps_columns()
        self.ensure_messages_columns()
        self.ensure_chat_memory_columns()
        self.ensure_user_model_preset_columns()
        self.ensure_default_user()

    def ensure_content_media_columns(self) -> None:
        with self.lock:
            columns = {
                row["name"]
                for row in self.conn.execute("pragma table_info(content_media_urls)").fetchall()
            }
            wanted = {
                "local_path": "text",
                "local_url": "text",
                "downloaded_bytes": "integer",
                "download_status": "text",
                "downloaded_at": "integer",
                "error": "text",
            }
            for name, column_type in wanted.items():
                if name not in columns:
                    self.conn.execute(f"alter table content_media_urls add column {name} {column_type}")
            self.conn.commit()

    def ensure_local_apps_columns(self) -> None:
        with self.lock:
            columns = {
                row["name"]
                for row in self.conn.execute("pragma table_info(local_apps)").fetchall()
            }
            wanted = {
                "display_id": "text",
                "api_base_url": "text",
                "extra_settings": "text",
            }
            for name, column_type in wanted.items():
                if name not in columns:
                    self.conn.execute(f"alter table local_apps add column {name} {column_type}")
            self.conn.execute(
                "create unique index if not exists idx_local_apps_display_id "
                "on local_apps(display_id) where display_id is not null and display_id<>''"
            )
            self.conn.commit()

    def _next_local_app_display_id_locked(self) -> str:
        rows = self.conn.execute(
            "select display_id from local_apps where display_id is not null and display_id<>''"
        ).fetchall()
        used: set[str] = set()
        max_num = 0
        for row in rows:
            value = str(row["display_id"] or "").strip()
            if not value:
                continue
            used.add(value)
            if value.isdigit():
                max_num = max(max_num, int(value))
        candidate = max_num + 1
        while True:
            display_id = f"{candidate:04d}"
            if display_id not in used:
                return display_id
            candidate += 1

    def ensure_local_app_display_ids(self) -> None:
        """Assign stable public card numbers without changing the internal app ids."""
        with self.lock:
            missing_rows = self.conn.execute(
                """
                select id from local_apps
                where display_id is null or trim(display_id)=''
                order by created_at asc, id asc
                """
            ).fetchall()
            if not missing_rows:
                return
            used: set[str] = set()
            max_num = 0
            existing_rows = self.conn.execute(
                "select display_id from local_apps where display_id is not null and display_id<>''"
            ).fetchall()
            for existing in existing_rows:
                value = str(existing["display_id"] or "").strip()
                if not value:
                    continue
                used.add(value)
                if value.isdigit():
                    max_num = max(max_num, int(value))
            candidate = max_num + 1
            for row in missing_rows:
                while True:
                    display_id = f"{candidate:04d}"
                    candidate += 1
                    if display_id not in used:
                        used.add(display_id)
                        break
                self.conn.execute(
                    "update local_apps set display_id=? where id=?",
                    (display_id, row["id"]),
                )
            self.conn.commit()

    def ensure_messages_columns(self) -> None:
        with self.lock:
            columns = {
                row["name"]
                for row in self.conn.execute("pragma table_info(messages)").fetchall()
            }
            wanted = {
                "swipes": "text",
                "swipe_index": "integer not null default 0",
            }
            for name, column_type in wanted.items():
                if name not in columns:
                    self.conn.execute(f"alter table messages add column {name} {column_type}")
            self.conn.commit()

    def ensure_chat_memory_columns(self) -> None:
        with self.lock:
            columns = {
                row["name"]
                for row in self.conn.execute("pragma table_info(chat_memories)").fetchall()
            }
            if "conversation_id" not in columns:
                self.conn.execute("alter table chat_memories add column conversation_id text")
            self.conn.execute(
                "create index if not exists idx_chat_memories_user_conv "
                "on chat_memories(user_id, conversation_id, updated_at desc)"
            )
            self.conn.commit()

    def ensure_user_model_preset_columns(self) -> None:
        with self.lock:
            columns = {
                row["name"]
                for row in self.conn.execute("pragma table_info(user_model_presets)").fetchall()
            }
            if "protocol" not in columns:
                self.conn.execute("alter table user_model_presets add column protocol text not null default 'openai'")
            self.conn.commit()

    def ensure_user_persona_columns(self) -> None:
        with self.lock:
            columns = {
                row["name"]
                for row in self.conn.execute("pragma table_info(users)").fetchall()
            }
            wanted = {
                "persona_name": "text",
                "persona_desc": "text",
            }
            for name, column_type in wanted.items():
                if name not in columns:
                    self.conn.execute(f"alter table users add column {name} {column_type}")
            self.conn.commit()

    def ensure_user_profile_columns(self) -> None:
        with self.lock:
            columns = {
                row["name"]
                for row in self.conn.execute("pragma table_info(users)").fetchall()
            }
            wanted = {
                "display_id": "text",
                "avatar_url": "text",
            }
            for name, column_type in wanted.items():
                if name not in columns:
                    self.conn.execute(f"alter table users add column {name} {column_type}")
            self.conn.commit()

    def ensure_user_security_columns(self) -> None:
        with self.lock:
            columns = {
                row["name"]
                for row in self.conn.execute("pragma table_info(users)").fetchall()
            }
            wanted = {
                "register_ip": "text",
                "last_login_ip": "text",
            }
            for name, column_type in wanted.items():
                if name not in columns:
                    self.conn.execute(f"alter table users add column {name} {column_type}")
            self.conn.commit()

    def ensure_user_gender_column(self) -> None:
        with self.lock:
            columns = {
                row["name"]
                for row in self.conn.execute("pragma table_info(users)").fetchall()
            }
            if "gender" not in columns:
                self.conn.execute("alter table users add column gender integer not null default 0")
                self.conn.commit()

    def ensure_user_credit_columns(self) -> None:
        with self.lock:
            columns = {
                row["name"]
                for row in self.conn.execute("pragma table_info(users)").fetchall()
            }
            wanted = {
                "free_points": "integer not null default 0",
                "paid_points": "integer not null default 0",
                "reward_points": "integer not null default 0",
            }
            added = False
            for name, column_type in wanted.items():
                if name not in columns:
                    self.conn.execute(f"alter table users add column {name} {column_type}")
                    added = True
            if added:
                self.conn.execute(
                    """
                    update users
                    set free_points=case when free_points=0 and paid_points=0 and reward_points=0 then points else free_points end,
                        paid_points=paid_points,
                        reward_points=reward_points
                    """
                )
            self.conn.execute(
                "update users set points=coalesce(free_points,0)+coalesce(paid_points,0)+coalesce(reward_points,0)"
            )
            self.conn.commit()

    def ensure_user_admin_column(self) -> None:
        with self.lock:
            columns = {
                row["name"]
                for row in self.conn.execute("pragma table_info(users)").fetchall()
            }
            if "is_admin" not in columns:
                self.conn.execute("alter table users add column is_admin integer not null default 0")
            self.conn.commit()

    def ensure_default_user(self) -> sqlite3.Row:
        user = self.get_user_by_email("local@ctf.test")
        if user:
            return user
        return self.upsert_user("local@ctf.test", "本地测试用户", "local123456")

    def password_hash(self, password: str | None) -> str:
        value = password or "local123456"
        return hashlib.sha256(("ai-fengyue-local:" + value).encode("utf-8")).hexdigest()

    def upsert_user(self, email: str, name: str | None, password: str | None, remote_addr: str | None = None) -> sqlite3.Row:
        with self.lock:
            email = (email or "local@ctf.test").strip() or "local@ctf.test"
            name = (name or email.split("@")[0] or "本地测试用户").strip()
            ts = now_ms()
            existing = self.get_user_by_email(email)
            if existing:
                self.conn.execute(
                    "update users set name=?, password_hash=?, updated_at=? where email=?",
                    (name, self.password_hash(password), ts, email),
                )
            else:
                self.conn.execute(
                    """
                    insert into users(id,email,name,password_hash,points,created_at,updated_at,gender,free_points,paid_points,reward_points)
                    values(?,?,?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        str(uuid.uuid4()),
                        email,
                        name,
                        self.password_hash(password),
                        NEW_USER_INITIAL_POINTS,
                        ts,
                        ts,
                        0,
                        NEW_USER_INITIAL_POINTS,
                        0,
                        0,
                    ),
                )
            self.conn.commit()
            return self.get_user_by_email(email)

    def create_registered_user(self, email: str, name: str | None, password: str | None, remote_addr: str | None = None) -> sqlite3.Row:
        with self.lock:
            clean_email = normalize_email(email)
            if not is_valid_email(clean_email):
                raise ValueError("invalid email")
            if self.get_user_by_email(clean_email):
                raise ValueError("email already registered")
            self.ensure_beta_registration_available(clean_email)
            clean_name = (name or clean_email.split("@")[0] or "用户").strip()[:64] or "用户"
            ts = now_ms()
            user_id = str(uuid.uuid4())
            self.conn.execute(
                """
                insert into users(id,email,name,password_hash,points,created_at,updated_at,gender,free_points,paid_points,reward_points,register_ip)
                values(?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    user_id,
                    clean_email,
                    clean_name,
                    self.password_hash(password),
                    NEW_USER_INITIAL_POINTS,
                    ts,
                    ts,
                    0,
                    NEW_USER_INITIAL_POINTS,
                    0,
                    0,
                    remote_addr or "",
                ),
            )
            self.record_security_event(user_id, clean_email, "register_success", remote_addr, {"free_points": NEW_USER_INITIAL_POINTS})
            self.conn.commit()
            return self.get_user_by_id(user_id) or self.current_user()

    def reset_user_password(self, email: str, password: str | None, remote_addr: str | None = None) -> sqlite3.Row:
        clean_email = normalize_email(email)
        if not is_valid_email(clean_email):
            raise ValueError("invalid email")
        if not password or len(str(password)) < 6:
            raise ValueError("password must be at least 6 characters")
        with self.lock:
            user = self.get_user_by_email(clean_email)
            if not user:
                raise ValueError("user not found")
            ts = now_ms()
            self.conn.execute(
                "update users set password_hash=?, updated_at=? where id=?",
                (self.password_hash(str(password)), ts, user["id"]),
            )
            self.record_security_event(user["id"], clean_email, "password_reset_success", remote_addr, {})
            self.conn.commit()
            return self.get_user_by_id(user["id"]) or user

    def get_user_by_email(self, email: str | None) -> sqlite3.Row | None:
        if not email:
            return None
        with self.lock:
            return self.conn.execute("select * from users where email=?", (email,)).fetchone()

    def get_user_by_id(self, user_id: str | None) -> sqlite3.Row | None:
        if not user_id:
            return None
        with self.lock:
            return self.conn.execute("select * from users where id=?", (user_id,)).fetchone()

    def record_security_event(
        self,
        user_id: str | None,
        email: str | None,
        event_type: str,
        remote_addr: str | None = None,
        meta: dict | None = None,
    ) -> None:
        self.conn.execute(
            "insert into user_security_events(user_id,email,event_type,remote_addr,created_at,meta_json) values(?,?,?,?,?,?)",
            (
                user_id or "",
                normalize_email(email or ""),
                event_type,
                remote_addr or "",
                now_ms(),
                json.dumps(meta or {}, ensure_ascii=False, separators=(",", ":")),
            ),
        )

    def recent_email_code_count(
        self,
        email: str | None,
        remote_addr: str | None,
        since_seconds: int,
        purpose: str = "register",
    ) -> tuple[int, int]:
        value = normalize_email(email or "")
        purpose_value = (purpose or "register").strip() or "register"
        with self.lock:
            email_count = 0
            if value:
                email_count = int(self.conn.execute(
                    "select count(*) from email_codes where email=? and purpose=? and created_at>=?",
                    (value, purpose_value, since_seconds),
                ).fetchone()[0] or 0)
            ip_count = 0
            if remote_addr:
                ip_count = int(self.conn.execute(
                    "select count(*) from email_codes where remote_addr=? and purpose=? and created_at>=?",
                    (remote_addr, purpose_value, since_seconds),
                ).fetchone()[0] or 0)
            return email_count, ip_count

    def recent_register_success_count(self, remote_addr: str | None, since_ms: int) -> int:
        if not remote_addr:
            return 0
        with self.lock:
            return int(self.conn.execute(
                "select count(*) from user_security_events where remote_addr=? and event_type='register_success' and created_at>=?",
                (remote_addr, since_ms),
            ).fetchone()[0] or 0)

    def public_user_count(self) -> int:
        with self.lock:
            rows = self.conn.execute("select id,email,is_admin from users").fetchall()
            return sum(1 for row in rows if not is_admin(row))

    def beta_registration_snapshot(self) -> dict:
        registered = self.public_user_count()
        max_users = max(0, int(BETA_MAX_REGISTERED_USERS or 0))
        remaining = max(0, max_users - registered) if max_users else None
        return {
            "max_users": max_users,
            "registered_users": registered,
            "remaining": remaining,
            "closed": bool(max_users and registered >= max_users),
        }

    def ensure_beta_registration_available(self, email: str | None = None) -> None:
        clean_email = normalize_email(email or "")
        if clean_email and self.get_user_by_email(clean_email):
            return
        snapshot = self.beta_registration_snapshot()
        if snapshot.get("closed"):
            raise ValueError("内测名额已满，暂时停止新用户注册")

    def set_user_admin(self, user_id: str, enabled: bool) -> sqlite3.Row | None:
        with self.lock:
            user = self.get_user_by_id(user_id)
            if not user:
                return None
            if user_is_env_admin(user) and not enabled:
                raise ValueError("环境变量管理员不能在后台撤销，请修改 ADMIN_EMAILS 后重启服务")
            self.conn.execute(
                "update users set is_admin=?, updated_at=? where id=?",
                (1 if enabled else 0, now_ms(), user_id),
            )
            self.conn.commit()
            return self.get_user_by_id(user_id)

    def current_user(self) -> sqlite3.Row:
        return self.ensure_default_user()

    def add_points(self, user_id: str, amount: int) -> sqlite3.Row:
        return self.add_credit_points(user_id, amount, "free")

    def credit_balance(self, user: sqlite3.Row | dict) -> dict:
        def get_int(name: str) -> int:
            try:
                return int(user[name] or 0)
            except Exception:
                return 0

        free = get_int("free_points")
        paid = get_int("paid_points")
        reward = get_int("reward_points")
        points = free + paid + reward
        if points <= 0:
            points = get_int("points")
            free = points
        return {
            "free_points": free,
            "paid_points": paid,
            "reward_points": reward,
            "points": points,
            "normal_points": paid,
            "regular_points": paid,
            "total_points": points,
        }

    def add_credit_points(self, user_id: str, amount: int, point_type: str = "free") -> sqlite3.Row:
        value = int(amount)
        point_type = (point_type or "free").strip().lower()
        if point_type not in ("free", "paid", "reward"):
            point_type = "free"
        column = {
            "free": "free_points",
            "paid": "paid_points",
            "reward": "reward_points",
        }[point_type]
        with self.lock:
            self.conn.execute(
                f"""
                update users
                set {column}=max(0, coalesce({column},0)+?),
                    updated_at=?
                where id=?
                """,
                (value, now_ms(), user_id),
            )
            self.conn.execute(
                """
                update users
                set points=max(0, coalesce(free_points,0)+coalesce(paid_points,0)+coalesce(reward_points,0)),
                    updated_at=?
                where id=?
                """,
                (now_ms(), user_id),
            )
            self.conn.commit()
            return self.get_user_by_id(user_id) or self.current_user()

    def require_credit_points(self, user_id: str, amount: int) -> dict:
        needed = max(1, int(amount or 0))
        with self.lock:
            user = self.get_user_by_id(user_id)
            if not user:
                raise ValueError("用户不存在")
            balance = self.credit_balance(user)
            if int(balance.get("points") or 0) < needed:
                raise ValueError(f"积分不足，单次对话需要 {needed} 积分")
            return balance

    def spend_credit_points(
        self,
        user_id: str,
        amount: int,
        *,
        event_type: str = "chat_cost",
        summary: str = "聊天消耗",
        payload: dict | None = None,
    ) -> dict:
        needed = max(1, int(amount or 0))
        with self.lock:
            user = self.get_user_by_id(user_id)
            if not user:
                raise ValueError("用户不存在")
            balance = self.credit_balance(user)
            if int(balance.get("points") or 0) < needed:
                raise ValueError(f"积分不足，单次对话需要 {needed} 积分")

            free = int(balance.get("free_points") or 0)
            reward = int(balance.get("reward_points") or 0)
            paid = int(balance.get("paid_points") or 0)
            remaining = needed

            from_free = min(free, remaining)
            free -= from_free
            remaining -= from_free

            from_reward = min(reward, remaining)
            reward -= from_reward
            remaining -= from_reward

            from_paid = min(paid, remaining)
            paid -= from_paid
            remaining -= from_paid

            if remaining > 0:
                raise ValueError(f"积分不足，单次对话需要 {needed} 积分")

            total = max(0, free + reward + paid)
            ts = now_ms()
            self.conn.execute(
                """
                update users
                set free_points=?, reward_points=?, paid_points=?, points=?, updated_at=?
                where id=?
                """,
                (free, reward, paid, total, ts, user_id),
            )
            event_payload = dict(payload or {})
            event_payload.update({
                "points_spent": needed,
                "deducted": {"free": from_free, "reward": from_reward, "paid": from_paid},
                "points": total,
            })
            self.conn.execute(
                "insert into user_events(user_id,event_type,summary,payload_json,created_at) values(?,?,?,?,?)",
                (user_id, event_type, summary, json.dumps(event_payload, ensure_ascii=False), ts),
            )
            self.conn.commit()
            updated = self.get_user_by_id(user_id) or user
            updated_balance = self.credit_balance(updated)
            return {
                "points_cost": needed,
                "points": int(updated_balance["points"]),
                "balance": updated_balance,
                "deducted": event_payload["deducted"],
            }

    def has_claimed_daily_reward(self, user_id: str, claim_date: str | None = None) -> bool:
        day = claim_date or business_date()
        with self.lock:
            return bool(self.conn.execute(
                "select 1 from daily_reward_claims where user_id=? and claim_date=?",
                (user_id, day),
            ).fetchone())

    def claim_daily_reward(self, user_id: str, amount: int = 10, claim_date: str | None = None) -> dict:
        day = claim_date or business_date()
        points = max(1, min(int(amount or 10), 10000))
        ts = now_ms()
        with self.lock:
            try:
                self.conn.execute(
                    "insert into daily_reward_claims(user_id,claim_date,points,created_at) values(?,?,?,?)",
                    (user_id, day, points, ts),
                )
            except sqlite3.IntegrityError:
                user = self.get_user_by_id(user_id) or self.current_user()
                return {
                    "claimed": True,
                    "already_claimed": True,
                    "points_added": 0,
                    "points": int(self.credit_balance(user)["points"]),
                    "balance": self.credit_balance(user),
                    "date": day,
                }
            self.conn.execute(
                """
                update users
                set free_points=max(0, coalesce(free_points,0)+?),
                    updated_at=?
                where id=?
                """,
                (points, ts, user_id),
            )
            self.conn.execute(
                """
                update users
                set points=max(0, coalesce(free_points,0)+coalesce(paid_points,0)+coalesce(reward_points,0)),
                    updated_at=?
                where id=?
                """,
                (ts, user_id),
            )
            self.conn.execute(
                "insert into user_events(user_id,event_type,summary,payload_json,created_at) values(?,?,?,?,?)",
                (user_id, "reward_daily", "领取每日奖励", json.dumps({"date": day, "points": points}, ensure_ascii=False), ts),
            )
            self.conn.commit()
            user = self.get_user_by_id(user_id) or self.current_user()
            return {
                "claimed": True,
                "already_claimed": False,
                "points_added": points,
                "points": int(self.credit_balance(user)["points"]),
                "balance": self.credit_balance(user),
                "date": day,
            }

    def update_user_name(self, user_id: str, name: str) -> sqlite3.Row:
        clean_name = (name or "").strip()
        if not clean_name:
            raise ValueError("name is required")
        if len(clean_name) > 64:
            raise ValueError("name is too long")
        with self.lock:
            self.conn.execute(
                "update users set name=?, updated_at=? where id=?",
                (clean_name, now_ms(), user_id),
            )
            self.conn.commit()
            return self.get_user_by_id(user_id) or self.current_user()

    def update_user_profile(
        self,
        user_id: str,
        display_id: object = None,
        avatar_url: object = None,
    ) -> sqlite3.Row:
        clean_display = "" if display_id is None else str(display_id).strip()
        if clean_display:
            if not DISPLAY_ID_RE.match(clean_display):
                raise ValueError("展示 ID 只能使用 3-32 位字母、数字、下划线或短横线")
        clean_avatar = normalize_user_avatar_input(avatar_url)
        with self.lock:
            if clean_display:
                existing = self.conn.execute(
                    "select id from users where lower(coalesce(display_id,''))=lower(?) and id<>?",
                    (clean_display, user_id),
                ).fetchone()
                if existing:
                    raise ValueError("展示 ID 已被占用")
            self.conn.execute(
                "update users set display_id=?, avatar_url=?, updated_at=? where id=?",
                (clean_display or None, clean_avatar or None, now_ms(), user_id),
            )
            self.conn.commit()
            return self.get_user_by_id(user_id) or self.current_user()

    def create_recharge_order(
        self,
        user_id: str,
        points: int,
        product_id: str,
        remote_addr: str | None = None,
    ) -> tuple[sqlite3.Row, str]:
        with self.lock:
            amount = max(1, min(int(points), 100000))
            product = (product_id or f"ctf_recharge_{amount}").strip()[:80]
            order_id = "PCH-" + uuid.uuid4().hex[:16].upper()
            ts = now_ms()
            self.conn.execute(
                "insert into recharge_orders(order_id,user_id,product_id,points,created_at,remote_addr) values(?,?,?,?,?,?)",
                (order_id, user_id, product, amount, ts, remote_addr or ""),
            )
            self.conn.execute(
                """
                update users
                set paid_points=coalesce(paid_points,0)+?,
                    updated_at=?
                where id=?
                """,
                (amount, ts, user_id),
            )
            self.conn.execute(
                """
                update users
                set points=max(0, coalesce(free_points,0)+coalesce(paid_points,0)+coalesce(reward_points,0)),
                    updated_at=?
                where id=?
                """,
                (ts, user_id),
            )
            self.conn.commit()
            return self.get_user_by_id(user_id) or self.current_user(), order_id

    def generate_redeem_code(self, prefix: str = "XY") -> str:
        alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
        return f"{prefix}-" + "-".join(
            "".join(random.SystemRandom().choice(alphabet) for _ in range(4))
            for _ in range(4)
        )

    def create_redeem_codes(
        self,
        *,
        count: int,
        points: int,
        point_type: str,
        note: str = "",
        expires_at: int | None = None,
        created_by: str = "",
    ) -> list[dict]:
        total = max(1, min(int(count or 1), 200))
        amount = max(1, min(int(points or 1), 100000000))
        kind = (point_type or "paid").strip().lower()
        if kind not in ("free", "paid", "reward"):
            kind = "paid"
        ts = now_ms()
        created: list[dict] = []
        with self.lock:
            for _ in range(total):
                code = self.generate_redeem_code()
                while self.conn.execute("select 1 from redeem_codes where code=?", (code,)).fetchone():
                    code = self.generate_redeem_code()
                self.conn.execute(
                    """
                    insert into redeem_codes(code,points,point_type,note,created_by,created_at,expires_at)
                    values(?,?,?,?,?,?,?)
                    """,
                    (code, amount, kind, note[:300], created_by, ts, expires_at),
                )
                created.append({
                    "code": code,
                    "points": amount,
                    "point_type": kind,
                    "note": note[:300],
                    "created_at": ts,
                    "expires_at": expires_at,
                    "status": "unused",
                })
            self.conn.commit()
        return created

    def redeem_code(self, user_id: str, code: str) -> dict:
        clean = (code or "").strip().upper()
        if not clean:
            raise ValueError("兑换码不能为空")
        ts = now_ms()
        with self.lock:
            row = self.conn.execute("select * from redeem_codes where code=?", (clean,)).fetchone()
            if not row:
                raise ValueError("兑换码不存在")
            if row["disabled_at"]:
                raise ValueError("兑换码已禁用")
            if row["redeemed_at"]:
                raise ValueError("兑换码已被使用")
            if row["expires_at"] and int(row["expires_at"]) < ts:
                raise ValueError("兑换码已过期")
            self.conn.execute(
                "update redeem_codes set redeemed_by=?, redeemed_at=? where code=? and redeemed_at is null",
                (user_id, ts, clean),
            )
            history_id = str(uuid.uuid4())
            self.conn.execute(
                """
                insert into redemption_history(id,code,user_id,points,point_type,note,created_at)
                values(?,?,?,?,?,?,?)
                """,
                (history_id, clean, user_id, int(row["points"]), row["point_type"], row["note"] or "", ts),
            )
            self.conn.commit()
        updated = self.add_credit_points(user_id, int(row["points"]), row["point_type"])
        return {
            "code": clean,
            "points_added": int(row["points"]),
            "point_type": row["point_type"],
            "balance": self.credit_balance(updated),
            "redeemed_at": ts,
        }

    def list_user_redemptions(self, user_id: str, page: int = 1, page_size: int = 30) -> tuple[list[dict], int]:
        limit = max(1, min(int(page_size), 100))
        offset = (max(1, int(page)) - 1) * limit
        with self.lock:
            total = self.conn.execute(
                "select count(*) from redemption_history where user_id=?",
                (user_id,),
            ).fetchone()[0]
            rows = self.conn.execute(
                """
                select * from redemption_history
                where user_id=?
                order by created_at desc
                limit ? offset ?
                """,
                (user_id, limit, offset),
            ).fetchall()
        return [dict(r) for r in rows], int(total)

    def list_redeem_codes(self, page: int = 1, limit: int = 50, status: str = "") -> tuple[list[dict], int]:
        lim = max(1, min(int(limit), 200))
        offset = (max(1, int(page)) - 1) * lim
        where = []
        params: list[object] = []
        ts = now_ms()
        status = (status or "").strip().lower()
        if status == "unused":
            where.append("redeemed_at is null and disabled_at is null and (expires_at is null or expires_at>=?)")
            params.append(ts)
        elif status == "used":
            where.append("redeemed_at is not null")
        elif status == "disabled":
            where.append("disabled_at is not null")
        elif status == "expired":
            where.append("redeemed_at is null and disabled_at is null and expires_at is not null and expires_at<?")
            params.append(ts)
        where_sql = (" where " + " and ".join(where)) if where else ""
        with self.lock:
            total = self.conn.execute(f"select count(*) from redeem_codes{where_sql}", params).fetchone()[0]
            rows = self.conn.execute(
                f"""
                select c.*, u.email as redeemed_email, u.name as redeemed_name
                from redeem_codes c
                left join users u on u.id = c.redeemed_by
                {where_sql}
                order by c.created_at desc
                limit ? offset ?
                """,
                (*params, lim, offset),
            ).fetchall()
        result = []
        for row in rows:
            item = dict(row)
            item["status"] = redeem_code_status(item, ts)
            result.append(item)
        return result, int(total)

    def disable_redeem_code(self, code: str) -> bool:
        clean = (code or "").strip().upper()
        with self.lock:
            row = self.conn.execute("select * from redeem_codes where code=?", (clean,)).fetchone()
            if not row:
                return False
            if row["redeemed_at"]:
                raise ValueError("兑换码已使用，不能禁用")
            self.conn.execute("update redeem_codes set disabled_at=? where code=?", (now_ms(), clean))
            self.conn.commit()
            return True

    def get_content_cache(self, cache_key: str) -> sqlite3.Row | None:
        with self.lock:
            return self.conn.execute("select * from content_cache where cache_key=?", (cache_key,)).fetchone()

    def first_nonempty_explore_payload(self) -> object | None:
        with self.lock:
            rows = self.conn.execute(
                """
                select response_json
                from content_cache
                where path='go/api/explore/search'
                order by updated_at desc, fetched_at desc
                limit 30
                """
            ).fetchall()
        for row in rows:
            try:
                payload = json.loads(row["response_json"])
            except Exception:
                continue
            data = payload.get("data") if isinstance(payload, dict) else None
            apps = data.get("apps") if isinstance(data, dict) else None
            if isinstance(apps, list) and apps:
                return payload
        return None

    def set_content_cache(
        self,
        cache_key: str,
        method: str,
        path: str,
        query: str,
        status: int,
        response_json: object,
        raw_bytes: int,
        source_url: str,
    ) -> None:
        payload = json.dumps(response_json, ensure_ascii=False, separators=(",", ":"))
        ts = now_ms()
        with self.lock:
            self.conn.execute(
                """
                insert into content_cache(cache_key,method,path,query,status,response_json,raw_bytes,source_url,fetched_at,updated_at)
                values(?,?,?,?,?,?,?,?,?,?)
                on conflict(cache_key) do update set
                    method=excluded.method,
                    path=excluded.path,
                    query=excluded.query,
                    status=excluded.status,
                    response_json=excluded.response_json,
                    raw_bytes=excluded.raw_bytes,
                    source_url=excluded.source_url,
                    updated_at=excluded.updated_at
                """,
                (cache_key, method, path, query, status, payload, raw_bytes, source_url, ts, ts),
            )
            self.conn.commit()

    def content_cache_stats(self) -> dict:
        with self.lock:
            row = self.conn.execute(
                "select count(*) as total, coalesce(sum(raw_bytes),0) as bytes from content_cache"
            ).fetchone()
        return {"total": int(row["total"]), "bytes": int(row["bytes"])}

    def media_url_mappings(self) -> list[tuple[str, str]]:
        with self.lock:
            rows = self.conn.execute(
                """
                select url, local_url from content_media_urls
                where download_status='downloaded' and local_url is not null
                order by length(url) desc
                """
            ).fetchall()
        return [(row["url"], row["local_url"]) for row in rows]

    def log_request(self, method: str, path: str, query: str, headers: dict, body: str, status: int) -> None:
        with self.lock:
            self.conn.execute(
                "insert into request_log(ts,method,path,query,headers,body,status) values(?,?,?,?,?,?,?)",
                (now_ms(), method, path, query, json.dumps(headers, ensure_ascii=False), body, status),
            )
            self.conn.commit()

    def create_email_code(self, email: str, remote_addr: str | None = None, purpose: str = "register") -> str:
        value = normalize_email(email)
        if not value:
            raise ValueError("email is required")
        purpose_value = (purpose or "register").strip().lower() or "register"
        if purpose_value in ("reset", "reset_password"):
            purpose_value = "password_reset"
        if purpose_value not in ("register", "password_reset"):
            raise ValueError("invalid email code purpose")
        hour_ago = int(time.time()) - 3600
        if purpose_value == "register":
            if self.get_user_by_email(value):
                raise ValueError("email already registered")
        elif purpose_value == "password_reset" and not self.get_user_by_email(value):
            raise ValueError("email is not registered")
        email_count, ip_count = self.recent_email_code_count(value, remote_addr, hour_ago, purpose_value)
        if email_count >= REGISTER_CODE_EMAIL_HOURLY_LIMIT:
            raise ValueError("too many verification codes for this email, try later")
        if remote_addr and ip_count >= REGISTER_CODE_IP_HOURLY_LIMIT:
            raise ValueError("too many verification codes from this network, try later")
        code = f"{random.SystemRandom().randint(0, 999999):06d}"
        ts = int(time.time())
        with self.lock:
            self.conn.execute(
                "insert into email_codes(email,code,purpose,created_at,expires_at,remote_addr) values(?,?,?,?,?,?)",
                (value, code, purpose_value, ts, ts + CODE_TTL_SECONDS, remote_addr or ""),
            )
            self.conn.commit()
        return code

    def delete_email_code(self, email: str, code: str, purpose: str = "register") -> bool:
        value = normalize_email(email)
        clean_code = str(code or "").strip()
        purpose_value = (purpose or "register").strip().lower() or "register"
        if purpose_value in ("reset", "reset_password"):
            purpose_value = "password_reset"
        if not value or not clean_code:
            return False
        with self.lock:
            cur = self.conn.execute(
                "delete from email_codes where email=? and code=? and purpose=? and consumed_at is null",
                (value, clean_code, purpose_value),
            )
            self.conn.commit()
            return cur.rowcount > 0

    def verify_email_code(self, email: str, code: str, purpose: str = "register") -> bool:
        value = normalize_email(email)
        clean_code = (code or "").strip()
        if not value or not clean_code:
            return False
        ts = int(time.time())
        row = self.conn.execute(
            """
            select id, code from email_codes
            where email=? and purpose=? and consumed_at is null and expires_at>=?
            order by id desc limit 1
            """,
            (value, purpose, ts),
        ).fetchone()
        if not row or row["code"] != clean_code:
            return False
        self.conn.execute("update email_codes set consumed_at=? where id=?", (ts, row["id"]))
        self.conn.commit()
        return True

    def upsert_conversation(self, conv_id: str, user_id: str, app_id: str, *,
                            app_name: str | None = None, app_icon: str | None = None,
                            title: str | None = None) -> sqlite3.Row:
        with self.lock:
            ts = now_ms()
            existing = self.conn.execute("select * from conversations where id=?", (conv_id,)).fetchone()
            if existing:
                self.conn.execute(
                    "update conversations set updated_at=?, app_name=coalesce(?, app_name), "
                    "app_icon=coalesce(?, app_icon), title=coalesce(?, title) where id=?",
                    (ts, app_name, app_icon, title, conv_id),
                )
            else:
                self.conn.execute(
                    "insert into conversations(id,user_id,app_id,app_name,app_icon,title,created_at,updated_at) "
                    "values(?,?,?,?,?,?,?,?)",
                    (conv_id, user_id, app_id, app_name or "", app_icon or "", title or "", ts, ts),
                )
            self.conn.commit()
            return self.conn.execute("select * from conversations where id=?", (conv_id,)).fetchone()

    def get_conversation(self, conv_id: str, user_id: str) -> dict | None:
        with self.lock:
            row = self.conn.execute(
                "select * from conversations where id=? and user_id=?",
                (conv_id, user_id),
            ).fetchone()
            return dict(row) if row else None

    def append_message(self, conv_id: str, user_id: str, role: str, content: str, swipes: list | None = None) -> sqlite3.Row:
        with self.lock:
            mid = str(uuid.uuid4())
            ts = now_ms()
            swipes_json = json.dumps(swipes, ensure_ascii=False) if swipes else None
            self.conn.execute(
                "insert into messages(id,conversation_id,user_id,role,content,created_at,swipes,swipe_index) values(?,?,?,?,?,?,?,?)",
                (mid, conv_id, user_id, role, content, ts, swipes_json, 0),
            )
            self.conn.execute(
                "update conversations set last_message=?, updated_at=? where id=?",
                (content[:120], ts, conv_id),
            )
            self.conn.commit()
            return self.conn.execute("select * from messages where id=?", (mid,)).fetchone()

    def list_conversations(self, user_id: str, limit: int = 50) -> list:
        with self.lock:
            rows = self.conn.execute(
                """
                select c.*,
                       a.name as current_app_name,
                       a.cover_url as current_app_icon,
                       a.summary as current_app_summary,
                       a.like_count as app_like_count,
                       case when f.app_id is not null then 1 else 0 end as favorited,
                       case when l.app_id is not null then 1 else 0 end as liked
                from conversations c
                left join local_apps a on a.id=c.app_id
                left join user_favorites f on f.user_id=c.user_id and f.app_id=c.app_id
                left join user_likes l on l.user_id=c.user_id and l.app_id=c.app_id
                where c.user_id=?
                order by c.updated_at desc limit ?
                """,
                (user_id, limit),
            ).fetchall()
        out = []
        for row in rows:
            item = dict(row)
            app_name = str(item.get("app_name") or item.get("current_app_name") or item.get("title") or "").strip()
            item["app_name"] = app_name or "未命名角色"
            item["title"] = str(item.get("title") or app_name or "未命名会话").strip()
            item["app_icon"] = str(item.get("app_icon") or item.get("current_app_icon") or "").strip()
            item["app_summary"] = str(item.get("current_app_summary") or "").strip()
            item["like_count"] = int(item.get("app_like_count") or 0)
            item["favorited"] = bool(item.get("favorited"))
            item["liked"] = bool(item.get("liked"))
            item["user_tags"] = self.list_user_app_tags(user_id, str(item.get("app_id") or ""))
            item.pop("current_app_name", None)
            item.pop("current_app_icon", None)
            item.pop("current_app_summary", None)
            item.pop("app_like_count", None)
            out.append(item)
        return out

    def _message_to_dict(self, row) -> dict:
        d = dict(row)
        raw = d.get("swipes")
        if raw:
            try:
                parsed = json.loads(raw)
                d["swipes"] = parsed if isinstance(parsed, list) else []
            except Exception:
                d["swipes"] = []
        else:
            d["swipes"] = []
        try:
            d["swipe_index"] = int(d.get("swipe_index") or 0)
        except Exception:
            d["swipe_index"] = 0
        return d

    def count_messages(self, conv_id: str, user_id: str, before_created_at: int | None = None) -> int:
        with self.lock:
            if before_created_at:
                row = self.conn.execute(
                    "select count(*) as c from messages where conversation_id=? and user_id=? and created_at < ?",
                    (conv_id, user_id, int(before_created_at)),
                ).fetchone()
            else:
                row = self.conn.execute(
                    "select count(*) as c from messages where conversation_id=? and user_id=?",
                    (conv_id, user_id),
                ).fetchone()
            return int(row["c"] if row else 0)

    def list_messages(self, conv_id: str, user_id: str, limit: int = 200, before_created_at: int | None = None) -> list:
        safe_limit = max(1, min(int(limit or 200), 500))
        with self.lock:
            if before_created_at:
                rows = self.conn.execute(
                    "select * from messages where conversation_id=? and user_id=? and created_at < ? order by created_at desc limit ?",
                    (conv_id, user_id, int(before_created_at), safe_limit),
                ).fetchall()
            else:
                rows = self.conn.execute(
                    "select * from messages where conversation_id=? and user_id=? order by created_at desc limit ?",
                    (conv_id, user_id, safe_limit),
                ).fetchall()
            rows = list(reversed(rows))
            return [self._message_to_dict(r) for r in rows]

    def get_message(self, message_id: str, user_id: str) -> dict | None:
        with self.lock:
            row = self.conn.execute(
                "select * from messages where id=? and user_id=?", (message_id, user_id),
            ).fetchone()
            return self._message_to_dict(row) if row else None

    def get_last_message(self, conv_id: str, user_id: str, role: str | None = None) -> dict | None:
        with self.lock:
            if role:
                row = self.conn.execute(
                    "select * from messages where conversation_id=? and user_id=? and role=? order by created_at desc limit 1",
                    (conv_id, user_id, role),
                ).fetchone()
            else:
                row = self.conn.execute(
                    "select * from messages where conversation_id=? and user_id=? order by created_at desc limit 1",
                    (conv_id, user_id),
                ).fetchone()
            return self._message_to_dict(row) if row else None

    def update_message_content(self, message_id: str, user_id: str, content: str) -> dict | None:
        with self.lock:
            row = self.conn.execute(
                "select * from messages where id=? and user_id=?", (message_id, user_id),
            ).fetchone()
            if not row:
                return None
            d = self._message_to_dict(row)
            swipes = d["swipes"]
            idx = d["swipe_index"]
            if swipes and 0 <= idx < len(swipes):
                swipes[idx] = content
            self.conn.execute(
                "update messages set content=?, swipes=? where id=?",
                (content, json.dumps(swipes, ensure_ascii=False) if swipes else None, message_id),
            )
            self.conn.commit()
            return self.get_message(message_id, user_id)

    def append_swipe(self, message_id: str, user_id: str, content: str) -> dict | None:
        """新增一个备选回复并设为激活；content 同步为该 swipe。"""
        with self.lock:
            row = self.conn.execute(
                "select * from messages where id=? and user_id=?", (message_id, user_id),
            ).fetchone()
            if not row:
                return None
            d = self._message_to_dict(row)
            swipes = d["swipes"]
            if not swipes:
                # seed with the existing content as the first swipe
                swipes = [d.get("content") or ""]
            swipes.append(content)
            new_idx = len(swipes) - 1
            self.conn.execute(
                "update messages set content=?, swipes=?, swipe_index=? where id=?",
                (content, json.dumps(swipes, ensure_ascii=False), new_idx, message_id),
            )
            self.conn.execute(
                "update conversations set last_message=? where id=?",
                (content[:120], d.get("conversation_id")),
            )
            self.conn.commit()
            return self.get_message(message_id, user_id)

    def set_swipe(self, message_id: str, user_id: str, index: int) -> dict | None:
        with self.lock:
            row = self.conn.execute(
                "select * from messages where id=? and user_id=?", (message_id, user_id),
            ).fetchone()
            if not row:
                return None
            d = self._message_to_dict(row)
            swipes = d["swipes"]
            if not swipes or index < 0 or index >= len(swipes):
                return d
            content = swipes[index]
            self.conn.execute(
                "update messages set content=?, swipe_index=? where id=?",
                (content, index, message_id),
            )
            self.conn.execute(
                "update conversations set last_message=? where id=?",
                (content[:120], d.get("conversation_id")),
            )
            self.conn.commit()
            return self.get_message(message_id, user_id)

    def _refresh_conversation_snapshot(self, conv_id: str, user_id: str, ts: int | None = None) -> dict | None:
        last = self.conn.execute(
            "select * from messages where conversation_id=? and user_id=? order by created_at desc, rowid desc limit 1",
            (conv_id, user_id),
        ).fetchone()
        last_message = (last["content"] if last else "") or ""
        self.conn.execute(
            "update conversations set last_message=?, updated_at=? where id=? and user_id=?",
            (last_message[:120], int(ts or now_ms()), conv_id, user_id),
        )
        conv = self.conn.execute(
            "select * from conversations where id=? and user_id=?", (conv_id, user_id),
        ).fetchone()
        return dict(conv) if conv else None

    def delete_message(self, message_id: str, user_id: str) -> bool:
        with self.lock:
            row = self.conn.execute(
                "select conversation_id from messages where id=? and user_id=?",
                (message_id, user_id),
            ).fetchone()
            if not row:
                return False
            conv_id = row["conversation_id"]
            cur = self.conn.execute(
                "delete from messages where id=? and user_id=?", (message_id, user_id),
            )
            if cur.rowcount > 0:
                self.conn.execute(
                    "delete from conversation_summaries where conversation_id=? and user_id=?",
                    (conv_id, user_id),
                )
                self._refresh_conversation_snapshot(conv_id, user_id)
            self.conn.commit()
            return cur.rowcount > 0

    def rollback_conversation_to_message(self, message_id: str, user_id: str) -> dict | None:
        with self.lock:
            row = self.conn.execute(
                "select rowid as _rowid, * from messages where id=? and user_id=?",
                (message_id, user_id),
            ).fetchone()
            if not row:
                return None
            conv_id = row["conversation_id"]
            created_at = int(row["created_at"] or 0)
            rowid = int(row["_rowid"] or 0)
            cur = self.conn.execute(
                """
                delete from messages
                where conversation_id=? and user_id=?
                  and (created_at > ? or (created_at = ? and rowid >= ?))
                """,
                (conv_id, user_id, created_at, created_at, rowid),
            )
            self.conn.execute(
                "delete from conversation_summaries where conversation_id=? and user_id=?",
                (conv_id, user_id),
            )
            conversation = self._refresh_conversation_snapshot(conv_id, user_id)
            count_row = self.conn.execute(
                "select count(*) as c from messages where conversation_id=? and user_id=?",
                (conv_id, user_id),
            ).fetchone()
            self.conn.commit()
            return {
                "message_id": message_id,
                "conversation_id": conv_id,
                "deleted_count": int(cur.rowcount or 0),
                "remaining_count": int(count_row["c"] if count_row else 0),
                "conversation": conversation,
            }

    def delete_conversation(self, conv_id: str, user_id: str) -> bool:
        with self.lock:
            row = self.conn.execute(
                "select id from conversations where id=? and user_id=?", (conv_id, user_id),
            ).fetchone()
            if not row:
                return False
            self.conn.execute("delete from messages where conversation_id=? and user_id=?", (conv_id, user_id))
            self.conn.execute("delete from conversation_summaries where conversation_id=? and user_id=?", (conv_id, user_id))
            self.conn.execute("delete from conversations where id=? and user_id=?", (conv_id, user_id))
            self.conn.commit()
            return True

    def delete_empty_conversation(self, conv_id: str, user_id: str) -> bool:
        with self.lock:
            cur = self.conn.execute(
                """
                delete from conversations
                where id=? and user_id=?
                  and not exists (
                    select 1 from messages where conversation_id=? and user_id=?
                  )
                """,
                (conv_id, user_id, conv_id, user_id),
            )
            if cur.rowcount > 0:
                self.conn.execute(
                    "delete from conversation_summaries where conversation_id=? and user_id=?",
                    (conv_id, user_id),
                )
            self.conn.commit()
            return cur.rowcount > 0

    def copy_conversation(self, conv_id: str, user_id: str) -> dict | None:
        with self.lock:
            row = self.conn.execute(
                "select * from conversations where id=? and user_id=?", (conv_id, user_id),
            ).fetchone()
            if not row:
                return None
            source = dict(row)
            new_id = str(uuid.uuid4())
            ts = now_ms()
            base_title = str(source.get("title") or source.get("app_name") or "对话").strip() or "对话"
            title = (base_title + " 副本")[:80]
            self.conn.execute(
                """
                insert into conversations(id,user_id,app_id,app_name,app_icon,title,last_message,created_at,updated_at)
                values(?,?,?,?,?,?,?,?,?)
                """,
                (
                    new_id,
                    user_id,
                    source.get("app_id") or "",
                    source.get("app_name") or "",
                    source.get("app_icon") or "",
                    title,
                    source.get("last_message") or "",
                    ts,
                    ts,
                ),
            )
            msg_rows = self.conn.execute(
                "select * from messages where conversation_id=? and user_id=? order by created_at asc",
                (conv_id, user_id),
            ).fetchall()
            for idx, msg_row in enumerate(msg_rows):
                msg = dict(msg_row)
                self.conn.execute(
                    """
                    insert into messages(id,conversation_id,user_id,role,content,created_at,swipes,swipe_index)
                    values(?,?,?,?,?,?,?,?)
                    """,
                    (
                        str(uuid.uuid4()),
                        new_id,
                        user_id,
                        msg.get("role") or "",
                        msg.get("content") or "",
                        ts + idx + 1,
                        msg.get("swipes"),
                        int(msg.get("swipe_index") or 0),
                    ),
                )
            summary = self.conn.execute(
                "select * from conversation_summaries where conversation_id=? and user_id=?",
                (conv_id, user_id),
            ).fetchone()
            if summary:
                s = dict(summary)
                self.conn.execute(
                    """
                    insert or replace into conversation_summaries(conversation_id,user_id,app_id,summary,message_count,created_at,updated_at)
                    values(?,?,?,?,?,?,?)
                    """,
                    (
                        new_id,
                        user_id,
                        s.get("app_id") or source.get("app_id") or "",
                        s.get("summary") or "",
                        int(s.get("message_count") or len(msg_rows)),
                        ts,
                        ts,
                    ),
                )
            memory_rows = self.conn.execute(
                """
                select * from chat_memories
                where user_id=? and conversation_id=?
                order by created_at asc
                """,
                (user_id, conv_id),
            ).fetchall()
            for idx, memory_row in enumerate(memory_rows):
                mem = dict(memory_row)
                self.conn.execute(
                    """
                    insert into chat_memories(id,user_id,app_id,conversation_id,title,content,keywords,enabled,pinned,created_at,updated_at,last_used_at)
                    values(?,?,?,?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        str(uuid.uuid4()),
                        user_id,
                        mem.get("app_id") or source.get("app_id") or "",
                        new_id,
                        mem.get("title") or "",
                        mem.get("content") or "",
                        mem.get("keywords") or "[]",
                        int(mem.get("enabled") if mem.get("enabled") is not None else 1),
                        int(mem.get("pinned") if mem.get("pinned") is not None else 0),
                        ts + len(msg_rows) + idx + 1,
                        ts,
                        None,
                    ),
                )
            var_rows = self.conn.execute(
                """
                select name,value_json from template_variables
                where user_id=? and scope='conversation' and scope_id=?
                """,
                (user_id, conv_id),
            ).fetchall()
            for var_row in var_rows:
                v = dict(var_row)
                self.conn.execute(
                    """
                    insert or replace into template_variables(user_id,scope,scope_id,name,value_json,updated_at)
                    values(?,?,?,?,?,?)
                    """,
                    (user_id, "conversation", new_id, v.get("name") or "", v.get("value_json") or "null", ts),
                )
            self.conn.commit()
            copied = self.conn.execute("select * from conversations where id=?", (new_id,)).fetchone()
            return dict(copied) if copied else None

    def _memory_to_dict(self, row) -> dict:
        d = dict(row) if row else {}
        raw = d.get("keywords")
        if raw:
            try:
                parsed = json.loads(raw)
                d["keywords"] = [str(x) for x in parsed if str(x or "").strip()] if isinstance(parsed, list) else []
            except Exception:
                d["keywords"] = []
        else:
            d["keywords"] = []
        d["enabled"] = bool(d.get("enabled", 1))
        d["pinned"] = bool(d.get("pinned", 0))
        d["conversation_id"] = str(d.get("conversation_id") or "")
        return d

    def list_memories(self, user_id: str, app_id: str = "", *, conversation_id: str = "", include_global: bool = True, limit: int = 100) -> list[dict]:
        with self.lock:
            clean_app = str(app_id or "").strip()
            clean_conv = str(conversation_id or "").strip()
            policy = self.memory_settings()
            include_role = include_global and bool(policy.get("include_role_memories", True))
            if clean_conv:
                if include_role and clean_app:
                    rows = self.conn.execute(
                        """
                        select * from chat_memories
                        where user_id=?
                          and (
                            conversation_id=?
                            or ((conversation_id='' or conversation_id is null) and (app_id=? or app_id='' or app_id is null))
                          )
                        order by
                          case when conversation_id=? then 0 else 1 end,
                          pinned desc, updated_at desc
                        limit ?
                        """,
                        (user_id, clean_conv, clean_app, clean_conv, limit),
                    ).fetchall()
                else:
                    rows = self.conn.execute(
                        """
                        select * from chat_memories
                        where user_id=? and conversation_id=?
                        order by pinned desc, updated_at desc limit ?
                        """,
                        (user_id, clean_conv, limit),
                    ).fetchall()
            elif clean_app and include_global:
                rows = self.conn.execute(
                    """
                    select * from chat_memories
                    where user_id=? and (conversation_id='' or conversation_id is null) and (app_id=? or app_id='' or app_id is null)
                    order by pinned desc, updated_at desc limit ?
                    """,
                    (user_id, clean_app, limit),
                ).fetchall()
            elif clean_app:
                rows = self.conn.execute(
                    "select * from chat_memories where user_id=? and app_id=? and (conversation_id='' or conversation_id is null) order by pinned desc, updated_at desc limit ?",
                    (user_id, clean_app, limit),
                ).fetchall()
            else:
                rows = self.conn.execute(
                    "select * from chat_memories where user_id=? order by pinned desc, updated_at desc limit ?",
                    (user_id, limit),
                ).fetchall()
            return [self._memory_to_dict(r) for r in rows]

    def save_memory(self, user_id: str, data: dict) -> dict:
        content = str(data.get("content") or "").strip()
        if not content:
            raise ValueError("memory content is required")
        memory_id = str(data.get("id") or "").strip() or str(uuid.uuid4())
        title = str(data.get("title") or "").strip()[:120]
        app_id = str(data.get("app_id") or "").strip()[:120]
        conversation_id = str(data.get("conversation_id") or data.get("conv_id") or "").strip()[:120]
        if not self.memory_settings().get("bind_memories_to_conversation", True):
            conversation_id = ""
        keywords = data.get("keywords")
        if isinstance(keywords, str):
            keywords = [x.strip() for x in re.split(r"[,，\n]", keywords) if x.strip()]
        elif isinstance(keywords, list):
            keywords = [str(x).strip() for x in keywords if str(x or "").strip()]
        else:
            keywords = []
        enabled = 1 if data.get("enabled", True) else 0
        pinned = 1 if data.get("pinned", False) else 0
        ts = now_ms()
        with self.lock:
            existing = self.conn.execute(
                "select id from chat_memories where id=? and user_id=?", (memory_id, user_id),
            ).fetchone()
            if existing:
                self.conn.execute(
                    """
                    update chat_memories
                    set app_id=?, conversation_id=?, title=?, content=?, keywords=?, enabled=?, pinned=?, updated_at=?
                    where id=? and user_id=?
                    """,
                    (
                        app_id,
                        conversation_id,
                        title,
                        content[:4000],
                        json.dumps(keywords[:24], ensure_ascii=False),
                        enabled,
                        pinned,
                        ts,
                        memory_id,
                        user_id,
                    ),
                )
            else:
                self.conn.execute(
                    """
                    insert into chat_memories(id,user_id,app_id,conversation_id,title,content,keywords,enabled,pinned,created_at,updated_at)
                    values(?,?,?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        memory_id,
                        user_id,
                        app_id,
                        conversation_id,
                        title,
                        content[:4000],
                        json.dumps(keywords[:24], ensure_ascii=False),
                        enabled,
                        pinned,
                        ts,
                        ts,
                    ),
                )
            self.conn.commit()
            row = self.conn.execute("select * from chat_memories where id=? and user_id=?", (memory_id, user_id)).fetchone()
            return self._memory_to_dict(row)

    def delete_memory(self, user_id: str, memory_id: str) -> bool:
        with self.lock:
            cur = self.conn.execute("delete from chat_memories where id=? and user_id=?", (memory_id, user_id))
            self.conn.commit()
            return cur.rowcount > 0

    def get_summary(self, user_id: str, conv_id: str) -> dict:
        with self.lock:
            row = self.conn.execute(
                "select * from conversation_summaries where conversation_id=? and user_id=?",
                (conv_id, user_id),
            ).fetchone()
            return dict(row) if row else {}

    def save_summary(self, user_id: str, conv_id: str, app_id: str, summary: str, message_count: int = 0) -> dict:
        clean = str(summary or "").strip()
        if not clean:
            raise ValueError("summary is required")
        ts = now_ms()
        with self.lock:
            existing = self.conn.execute(
                "select conversation_id from conversation_summaries where conversation_id=? and user_id=?",
                (conv_id, user_id),
            ).fetchone()
            if existing:
                self.conn.execute(
                    """
                    update conversation_summaries
                    set app_id=?, summary=?, message_count=?, updated_at=?
                    where conversation_id=? and user_id=?
                    """,
                    (app_id, clean[:6000], max(0, int(message_count or 0)), ts, conv_id, user_id),
                )
            else:
                self.conn.execute(
                    """
                    insert into conversation_summaries(conversation_id,user_id,app_id,summary,message_count,created_at,updated_at)
                    values(?,?,?,?,?,?,?)
                    """,
                    (conv_id, user_id, app_id, clean[:6000], max(0, int(message_count or 0)), ts, ts),
                )
            self.conn.commit()
        return self.get_summary(user_id, conv_id)

    def auto_summarize_conversation(self, user_id: str, conv_id: str) -> dict:
        conv = self.conn.execute(
            "select * from conversations where id=? and user_id=?", (conv_id, user_id),
        ).fetchone()
        if not conv:
            raise ValueError("conversation not found")
        messages = self.list_messages(conv_id, user_id, limit=80)
        lines = []
        for msg in messages[-40:]:
            role = "用户" if msg.get("role") == "user" else "角色"
            text = re.sub(r"\s+", " ", str(msg.get("content") or "")).strip()
            if text:
                lines.append(f"{role}: {text[:180]}")
        if not lines:
            summary = "这段对话还没有可摘要的消息。"
        else:
            joined = "\n".join(lines)
            summary = "自动摘要：\n" + joined[:3600]
        return self.save_summary(user_id, conv_id, conv["app_id"] or "", summary, len(messages))

    def maybe_refresh_summary(self, user_id: str, conv_id: str) -> dict:
        policy = self.memory_settings()
        if not policy.get("auto_summary_enabled", True):
            return self.get_summary(user_id, conv_id)
        messages = self.list_messages(conv_id, user_id, limit=120)
        count = len(messages)
        threshold = int(policy.get("auto_summary_message_threshold") or 10)
        delta = int(policy.get("auto_summary_delta_messages") or 8)
        if count < threshold:
            return self.get_summary(user_id, conv_id)
        current = self.get_summary(user_id, conv_id)
        old_count = int(current.get("message_count") or 0) if current else 0
        if not current or count - old_count >= delta:
            return self.auto_summarize_conversation(user_id, conv_id)
        return current

    def relevant_memories(self, user_id: str, app_id: str, conversation_id: str, text: str, limit: int | None = None) -> list[dict]:
        policy = self.memory_settings()
        if not policy.get("enabled", True):
            return []
        if limit is None:
            limit = int(policy.get("max_memories") or 6)
        if limit <= 0:
            return []
        search = str(text or "").lower()
        picked: list[dict] = []
        for mem in self.list_memories(
            user_id,
            app_id,
            conversation_id=conversation_id,
            include_global=bool(policy.get("include_role_memories", True)),
            limit=200,
        ):
            if not mem.get("enabled"):
                continue
            title = str(mem.get("title") or "")
            content = str(mem.get("content") or "")
            keywords = mem.get("keywords") if isinstance(mem.get("keywords"), list) else []
            matched = bool(mem.get("pinned"))
            if not matched:
                hay = f"{title}\n{content}".lower()
                matched = any(str(k).lower() in search for k in keywords if str(k).strip())
                if not matched and keywords:
                    matched = False
                elif not keywords:
                    matched = any(token and token in search for token in re.split(r"\s+", hay)[:12])
            if matched:
                picked.append(mem)
                if len(picked) >= limit:
                    break
        if picked:
            ts = now_ms()
            with self.lock:
                for mem in picked:
                    self.conn.execute("update chat_memories set last_used_at=? where id=? and user_id=?", (ts, mem["id"], user_id))
                self.conn.commit()
        return picked

    def get_template_variables(self, user_id: str, scope: str, scope_id: str = "") -> dict:
        clean_scope = str(scope or "").strip().lower()
        if clean_scope not in {"global", "app", "conversation"}:
            return {}
        with self.lock:
            rows = self.conn.execute(
                """
                select name, value_json from template_variables
                where user_id=? and scope=? and scope_id=?
                order by updated_at desc
                """,
                (user_id, clean_scope, str(scope_id or "")),
            ).fetchall()
        out: dict = {}
        for row in rows:
            name = str(row["name"] or "").strip()
            if not name:
                continue
            raw = row["value_json"]
            try:
                out[name] = json.loads(raw) if raw not in (None, "") else None
            except Exception:
                out[name] = raw
        return out

    def set_template_variable(self, user_id: str, scope: str, scope_id: str, name: str, value) -> None:
        clean_scope = str(scope or "").strip().lower()
        if clean_scope not in {"global", "app", "conversation"}:
            clean_scope = "conversation"
        clean_name = str(name or "").strip()[:120]
        if not user_id or not clean_name:
            return
        clean_value = template_unwrap(value)
        try:
            blob = json.dumps(clean_value, ensure_ascii=False, separators=(",", ":"))
        except Exception:
            blob = json.dumps(str(clean_value), ensure_ascii=False, separators=(",", ":"))
        if len(blob) > 20000:
            blob = json.dumps(str(clean_value)[:12000], ensure_ascii=False, separators=(",", ":"))
        with self.lock:
            self.conn.execute(
                """
                insert into template_variables(user_id, scope, scope_id, name, value_json, updated_at)
                values(?,?,?,?,?,?)
                on conflict(user_id, scope, scope_id, name)
                do update set value_json=excluded.value_json, updated_at=excluded.updated_at
                """,
                (user_id, clean_scope, str(scope_id or "")[:160], clean_name, blob, now_ms()),
            )
            self.conn.commit()

    def template_context(self, user_id: str, app_id: str = "", conv_id: str = "", base_context: dict | None = None) -> dict:
        global_vars = self.get_template_variables(user_id, "global", "")
        app_vars = self.get_template_variables(user_id, "app", app_id) if app_id else {}
        chat_vars = self.get_template_variables(user_id, "conversation", conv_id) if conv_id else {}
        merged: dict = {}
        for source in (global_vars, app_vars, chat_vars):
            if isinstance(source, dict):
                merged.update(source)
        return {
            "store": self,
            "user_id": user_id,
            "app_id": str(app_id or ""),
            "conversation_id": str(conv_id or ""),
            "global_variables": global_vars,
            "character_variables": app_vars,
            "chat_variables": chat_vars,
            "variables": merged,
            "context": base_context if isinstance(base_context, dict) else {},
        }

    def chat_context(self, user_id: str, app_id: str, conv_id: str, content: str, history: list[dict]) -> dict:
        recent = "\n".join(str(m.get("content") or "") for m in (history or [])[-20:])
        search_text = f"{recent}\n{content}"
        policy = self.memory_settings()
        memory_enabled = bool(policy.get("enabled", True))
        base_context = {
            "summary": self.get_summary(user_id, conv_id) if conv_id and memory_enabled else {},
            "memories": self.relevant_memories(user_id, app_id, conv_id, search_text) if memory_enabled else [],
            "history": history or [],
            "recent_text": search_text,
            "user_message": content,
            "memory_settings": policy,
        }
        out = dict(base_context)
        out.update(self.template_context(user_id, app_id, conv_id, base_context))
        return out

    def _group_message_to_dict(self, row) -> dict:
        return dict(row) if row else {}

    def _group_to_dict(self, row) -> dict:
        group = dict(row)
        members = self.conn.execute(
            "select * from group_members where group_id=? order by position asc, id asc",
            (group["id"],),
        ).fetchall()
        group["members"] = [dict(m) for m in members]
        return group

    def create_group_chat(self, user_id: str, name: str, members: list[dict]) -> dict:
        clean_members = []
        for idx, member in enumerate(members[:12]):
            app_id = str(member.get("app_id") or "").strip()
            app_id = self.resolve_local_app_id(app_id)
            if not app_id:
                continue
            clean_members.append({
                "app_id": app_id,
                "app_name": str(member.get("app_name") or "")[:120],
                "app_icon": str(member.get("app_icon") or "")[:500],
                "position": idx,
            })
        if len(clean_members) < 2:
            raise ValueError("群聊至少需要 2 个角色")
        with self.lock:
            gid = str(uuid.uuid4())
            ts = now_ms()
            self.conn.execute(
                "insert into group_chats(id,user_id,name,last_message,active_index,created_at,updated_at) values(?,?,?,?,?,?,?)",
                (gid, user_id, (name or "群聊")[:120], "", 0, ts, ts),
            )
            self.conn.executemany(
                "insert into group_members(group_id,app_id,app_name,app_icon,position) values(?,?,?,?,?)",
                [(gid, m["app_id"], m["app_name"], m["app_icon"], m["position"]) for m in clean_members],
            )
            self.conn.commit()
            return self.get_group_chat(gid, user_id) or {}

    def list_group_chats(self, user_id: str, limit: int = 50) -> list[dict]:
        with self.lock:
            rows = self.conn.execute(
                "select * from group_chats where user_id=? order by updated_at desc limit ?",
                (user_id, limit),
            ).fetchall()
            return [self._group_to_dict(r) for r in rows]

    def get_group_chat(self, group_id: str, user_id: str) -> dict | None:
        with self.lock:
            row = self.conn.execute(
                "select * from group_chats where id=? and user_id=?",
                (group_id, user_id),
            ).fetchone()
            return self._group_to_dict(row) if row else None

    def list_group_messages(self, group_id: str, user_id: str, limit: int = 300) -> list[dict]:
        with self.lock:
            rows = self.conn.execute(
                "select * from group_messages where group_id=? and user_id=? order by created_at asc limit ?",
                (group_id, user_id, limit),
            ).fetchall()
            return [self._group_message_to_dict(r) for r in rows]

    def append_group_message(self, group_id: str, user_id: str, role: str, content: str,
                             *, speaker_app_id: str = "", speaker_name: str = "") -> dict:
        with self.lock:
            mid = str(uuid.uuid4())
            ts = now_ms()
            self.conn.execute(
                "insert into group_messages(id,group_id,user_id,role,content,speaker_app_id,speaker_name,created_at) values(?,?,?,?,?,?,?,?)",
                (mid, group_id, user_id, role, content, speaker_app_id, speaker_name, ts),
            )
            last = f"{speaker_name}: {content}" if speaker_name else content
            self.conn.execute(
                "update group_chats set last_message=?, updated_at=? where id=? and user_id=?",
                (last[:160], ts, group_id, user_id),
            )
            self.conn.commit()
            row = self.conn.execute("select * from group_messages where id=?", (mid,)).fetchone()
            return self._group_message_to_dict(row)

    def update_group_active_index(self, group_id: str, user_id: str, active_index: int) -> None:
        with self.lock:
            self.conn.execute(
                "update group_chats set active_index=?, updated_at=? where id=? and user_id=?",
                (max(0, int(active_index)), now_ms(), group_id, user_id),
            )
            self.conn.commit()

    def delete_group_chat(self, group_id: str, user_id: str) -> bool:
        with self.lock:
            row = self.conn.execute(
                "select id from group_chats where id=? and user_id=?",
                (group_id, user_id),
            ).fetchone()
            if not row:
                return False
            self.conn.execute("delete from group_messages where group_id=? and user_id=?", (group_id, user_id))
            self.conn.execute("delete from group_members where group_id=?", (group_id,))
            self.conn.execute("delete from group_chats where id=? and user_id=?", (group_id, user_id))
            self.conn.commit()
            return True

    def get_persona(self, user_id: str) -> dict:
        with self.lock:
            row = self.conn.execute(
                "select persona_name, persona_desc from users where id=?", (user_id,),
            ).fetchone()
            if not row:
                return {"name": "", "description": ""}
            return {"name": row["persona_name"] or "", "description": row["persona_desc"] or ""}

    def set_persona(self, user_id: str, name: str, description: str) -> dict:
        with self.lock:
            self.conn.execute(
                "update users set persona_name=?, persona_desc=?, updated_at=? where id=?",
                (str(name or "").strip()[:60], str(description or "").strip()[:4000], now_ms(), user_id),
            )
            self.conn.commit()
        return self.get_persona(user_id)

    # ===== 本地角色库 local_apps =====
    def upsert_upstream_app(self, app: dict) -> None:
        """同步脚本调用：写入/更新一个上游角色。app 是已 rebrand 的字段字典。"""
        with self.lock:
            ts = now_ms()
            existing = self.conn.execute("select id from local_apps where id=?", (app["id"],)).fetchone()
            fields = dict(
                source="upstream",
                name=app.get("name"),
                summary=app.get("summary"),
                description=app.get("description"),
                cover_url=app.get("cover_url"),
                cover_origin=app.get("cover_origin"),
                tags=json.dumps(app.get("tags") or [], ensure_ascii=False),
                opening_statement=app.get("opening_statement"),
                suggested_questions=json.dumps(app.get("suggested_questions") or [], ensure_ascii=False),
                age_rating=int(app.get("age_rating") or 0),
                gender=int(app.get("gender") or 0),
                language=app.get("language"),
                players_count=int(app.get("players_count") or 0),
                like_count=int(app.get("like_count") or 0),
                sort_weight=int(app.get("sort_weight") or 0),
                updated_at=ts,
            )
            if existing:
                cols = ", ".join(f"{k}=?" for k in fields)
                self.conn.execute(f"update local_apps set {cols} where id=?", (*fields.values(), app["id"]))
            else:
                fields["id"] = app["id"]
                fields["display_id"] = self._next_local_app_display_id_locked()
                fields["created_at"] = ts
                fields["status"] = "published"
                fields["is_public"] = 1
                cols = ", ".join(fields.keys())
                ph = ", ".join("?" for _ in fields)
                self.conn.execute(f"insert into local_apps({cols}) values({ph})", tuple(fields.values()))
            self.conn.commit()

    def create_user_app(self, owner_user_id: str, data: dict) -> sqlite3.Row:
        with self.lock:
            ts = now_ms()
            app_id = "user-" + uuid.uuid4().hex[:16]
            display_id = self._next_local_app_display_id_locked()
            extras = normalize_user_app_extras(data)
            extra_json = json.dumps(extras, ensure_ascii=False, separators=(",", ":")) if extras else None
            self.conn.execute(
                """insert into local_apps(id,display_id,source,owner_user_id,name,summary,description,cover_url,
                   tags,opening_statement,suggested_questions,pre_prompt,llm_model,api_base_url,age_rating,gender,
                   language,status,is_public,extra_settings,created_at,updated_at)
                   values(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (app_id, display_id, "user", owner_user_id, data.get("name") or "未命名角色",
                  data.get("summary") or "", data.get("description") or "",
                  data.get("cover_url") or "", json.dumps(data.get("tags") or [], ensure_ascii=False),
                  data.get("opening_statement") or "", json.dumps(data.get("suggested_questions") or [], ensure_ascii=False),
                  data.get("pre_prompt") or "", normalize_user_selected_llm_model(data.get("llm_model")),
                  data.get("api_base_url") or "",
                  int(data.get("age_rating") or 0), int(data.get("gender") or 0),
                  data.get("language") or "zh-Hans", data.get("status") or "published",
                  1 if data.get("is_public", True) else 0, extra_json, ts, ts),
            )
            self.conn.commit()
            return self.conn.execute("select * from local_apps where id=?", (app_id,)).fetchone()

    def create_admin_app(self, data: dict) -> sqlite3.Row:
        with self.lock:
            ts = now_ms()
            app_id = "admin-" + uuid.uuid4().hex[:16]
            display_id = self._next_local_app_display_id_locked()
            rich = normalize_admin_rich_app_payload(data)
            normalized = normalize_admin_app_data({**data, **rich})
            extra_json = json.dumps(normalize_user_app_extras({**data, **rich}), ensure_ascii=False, separators=(",", ":"))
            self.conn.execute(
                """insert into local_apps(id,display_id,source,owner_user_id,name,summary,description,cover_url,
                   tags,opening_statement,suggested_questions,pre_prompt,llm_model,api_base_url,age_rating,gender,
                   language,status,is_public,sort_weight,extra_settings,created_at,updated_at)
                   values(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (app_id, display_id, "admin", None, normalized.get("name") or "未命名官方角色",
                  normalized.get("summary") or "", normalized.get("description") or "",
                  normalized.get("cover_url") or "", json.dumps(normalized.get("tags") or [], ensure_ascii=False),
                  normalized.get("opening_statement") or "", json.dumps(normalized.get("suggested_questions") or [], ensure_ascii=False),
                  normalized.get("pre_prompt") or "", normalized.get("llm_model") or "",
                  normalized.get("api_base_url") or "",
                  int(normalized.get("age_rating") or 0), int(normalized.get("gender") or 0),
                  normalized.get("language") or "zh-Hans", normalized.get("status") or "published",
                  1 if normalized.get("is_public", True) else 0, int(normalized.get("sort_weight") or 100),
                  extra_json if extra_json != "{}" else None, ts, ts),
            )
            self.conn.commit()
            return self.conn.execute("select * from local_apps where id=?", (app_id,)).fetchone()

    def update_admin_app(self, app_id: str, data: dict) -> sqlite3.Row | None:
        with self.lock:
            app_id = self.resolve_local_app_id(app_id)
            row = self.conn.execute(
                "select * from local_apps where id=?",
                (app_id,),
            ).fetchone()
            if not row:
                return None
            rich = normalize_admin_rich_app_payload(data)
            data = normalize_admin_app_data({**data, **rich}, partial=True)
            allowed = ("name", "summary", "description", "cover_url", "opening_statement",
                       "pre_prompt", "llm_model", "api_base_url", "age_rating", "gender",
                       "language", "status", "is_public", "sort_weight")
            updates = {}
            for k in allowed:
                if k in data:
                    updates[k] = normalize_user_selected_llm_model(data[k]) if k == "llm_model" else data[k]
            if "tags" in data:
                updates["tags"] = json.dumps(data["tags"] or [], ensure_ascii=False)
            if "suggested_questions" in data:
                updates["suggested_questions"] = json.dumps(data["suggested_questions"] or [], ensure_ascii=False)
            if "is_public" in updates:
                updates["is_public"] = 1 if updates["is_public"] else 0
            if "sort_weight" in updates:
                updates["sort_weight"] = int(updates["sort_weight"] or 0)
            extras_in = normalize_user_app_extras({**data, **rich})
            extra_trigger_keys = (
                "bg_url", "nsfw", "protected", "protected_prompt", "anonymous", "sampling",
                "personality", "scenario", "mes_example", "post_history_instructions",
                "alternate_greetings", "world_info", "creator_notes", "character_version",
                "creator", "extensions", "prompt_blocks", "quick_replies", "regex_scripts", "TavernHelper_scripts",
            )
            if extras_in or any(k in rich for k in extra_trigger_keys):
                existing = parse_json_object(dict(row).get("extra_settings"))
                if not isinstance(existing, dict):
                    existing = {}
                for k, v in extras_in.items():
                    existing[k] = v
                updates["extra_settings"] = json.dumps(existing, ensure_ascii=False, separators=(",", ":")) if existing else None
            if not updates:
                return row
            updates["updated_at"] = now_ms()
            cols = ", ".join(f"{k}=?" for k in updates)
            self.conn.execute(f"update local_apps set {cols} where id=?", (*updates.values(), app_id))
            self.conn.commit()
            return self.conn.execute("select * from local_apps where id=?", (app_id,)).fetchone()

    def delete_admin_app(self, app_id: str) -> bool:
        with self.lock:
            app_id = self.resolve_local_app_id(app_id)
            cur = self.conn.execute(
                "delete from local_apps where id=?",
                (app_id,),
            )
            self.conn.commit()
            return cur.rowcount > 0

    def import_admin_apps(self, items: list, created_by: str = "") -> dict:
        created: list[dict] = []
        errors: list[dict] = []
        if not isinstance(items, list):
            raise ValueError("items must be a list")
        for index, raw in enumerate(items[:500]):
            if not isinstance(raw, dict):
                errors.append({"index": index, "message": "角色卡必须是对象"})
                continue
            try:
                normalized = normalize_admin_app_data({**raw, **normalize_admin_rich_app_payload(raw)})
                if not normalized.get("name"):
                    raise ValueError("缺少 name")
                if created_by:
                    note = str(normalized.get("summary") or "")
                    raw = {**raw, "summary": note[:180]}
                row = self.create_admin_app(raw)
                created.append(local_app_to_card(dict(row)))
            except Exception as exc:
                errors.append({"index": index, "name": raw.get("name") or raw.get("title") or "", "message": str(exc)})
        return {"created": created, "errors": errors, "count": len(created), "error_count": len(errors)}

    def bulk_update_admin_apps(self, app_ids: list, data: dict) -> dict:
        ids = normalize_bulk_app_ids(app_ids)
        if not ids:
            raise ValueError("ids is required")
        if len(ids) > 200:
            raise ValueError("最多一次批量修改 200 张角色卡")
        if not isinstance(data, dict):
            raise ValueError("invalid body")

        tags_mode = str(data.get("tags_mode") or data.get("tag_mode") or "none").strip().lower()
        world_mode = str(data.get("world_mode") or data.get("worldInfoMode") or "none").strip().lower()
        if tags_mode not in ("none", "replace", "append", "remove"):
            raise ValueError("invalid tags_mode")
        if world_mode not in ("none", "replace", "append", "merge"):
            raise ValueError("invalid world_mode")

        tags = normalize_admin_bulk_tags(data.get("tags", data.get("tags_text", data.get("tagsText"))))
        if tags_mode != "none" and not tags:
            raise ValueError("tags is required when tags_mode is not none")

        summary_enabled = truthy(data.get("summary_enabled", data.get("summaryEnabled")))
        description_enabled = truthy(data.get("description_enabled", data.get("descriptionEnabled")))
        summary = str(data.get("summary") if data.get("summary") is not None else "").strip()[:180]
        description = str(data.get("description") if data.get("description") is not None else "").strip()[:30000]

        world_entries = []
        if world_mode != "none":
            world_value = data.get("world_info", data.get("worldInfo", data.get("world")))
            world_entries = normalize_admin_bulk_world_info(world_value)
            if world_mode in ("append", "merge") and not world_entries:
                raise ValueError("world_info is required when world_mode is append or merge")

        if tags_mode == "none" and not summary_enabled and not description_enabled and world_mode == "none":
            raise ValueError("no bulk update fields selected")

        updated_ids: list[str] = []
        not_found: list[str] = []
        errors: list[dict] = []
        ts = now_ms()
        with self.lock:
            for raw_app_id in ids:
                try:
                    app_id = self.resolve_local_app_id(raw_app_id)
                    row = self.conn.execute("select * from local_apps where id=?", (app_id,)).fetchone()
                    if not row:
                        not_found.append(raw_app_id)
                        continue
                    row_d = dict(row)
                    updates: dict[str, object] = {}

                    if tags_mode != "none":
                        current_tags = normalize_admin_bulk_tags(row_d.get("tags"))
                        if tags_mode == "replace":
                            new_tags = tags
                        elif tags_mode == "append":
                            new_tags = merge_text_tags(current_tags, tags)
                        else:
                            remove_set = {t.casefold() for t in tags}
                            new_tags = [t for t in current_tags if t.casefold() not in remove_set]
                        updates["tags"] = json.dumps(new_tags, ensure_ascii=False)

                    if summary_enabled:
                        updates["summary"] = summary
                    if description_enabled:
                        updates["description"] = description

                    if world_mode != "none":
                        extra = parse_json_object(row_d.get("extra_settings"))
                        existing_world = normalize_world_info(extra.get("world_info") or [])
                        if world_mode == "replace":
                            new_world = world_entries
                        elif world_mode == "append":
                            new_world = normalize_world_info((existing_world + world_entries)[:200])
                        else:
                            new_world = merge_world_info_entries(existing_world, world_entries)
                        extra["world_info"] = new_world
                        updates["extra_settings"] = json.dumps(extra, ensure_ascii=False, separators=(",", ":")) if extra else None

                    if not updates:
                        continue
                    updates["updated_at"] = ts
                    cols = ", ".join(f"{k}=?" for k in updates)
                    self.conn.execute(f"update local_apps set {cols} where id=?", (*updates.values(), app_id))
                    updated_ids.append(app_id)
                except Exception as exc:
                    errors.append({"id": app_id, "message": str(exc)})
            self.conn.commit()

        return {
            "requested": len(ids),
            "updated": len(updated_ids),
            "ids": updated_ids,
            "not_found": not_found,
            "errors": errors,
            "error_count": len(errors),
        }

    def update_user_app(self, app_id: str, owner_user_id: str, data: dict) -> sqlite3.Row | None:
        with self.lock:
            app_id = self.resolve_local_app_id(app_id)
            row = self.conn.execute(
                "select * from local_apps where id=? and owner_user_id=? and source='user'",
                (app_id, owner_user_id),
            ).fetchone()
            if not row:
                return None
            allowed = ("name", "summary", "description", "cover_url", "opening_statement",
                       "pre_prompt", "llm_model", "api_base_url", "age_rating", "gender", "language", "status", "is_public")
            updates = {}
            for k in allowed:
                if k in data:
                    updates[k] = data[k]
            if "tags" in data:
                updates["tags"] = json.dumps(data["tags"] or [], ensure_ascii=False)
            if "suggested_questions" in data:
                updates["suggested_questions"] = json.dumps(data["suggested_questions"] or [], ensure_ascii=False)
            if "is_public" in updates:
                updates["is_public"] = 1 if updates["is_public"] else 0
            extras_in = normalize_user_app_extras(data)
            extra_trigger_keys = (
                "bg_url", "nsfw", "protected", "protected_prompt", "anonymous", "sampling",
                "personality", "scenario", "mes_example", "post_history_instructions",
                "alternate_greetings", "world_info", "creator_notes", "character_version",
                "creator", "extensions", "prompt_blocks", "quick_replies", "regex_scripts", "TavernHelper_scripts",
            )
            if extras_in or any(k in data for k in extra_trigger_keys):
                # merge with existing extras to allow partial updates
                existing = {}
                try:
                    existing = json.loads(row["extra_settings"] or "{}") or {}
                    if not isinstance(existing, dict): existing = {}
                except Exception:
                    existing = {}
                # normalize_user_app_extras only emits keys that were present in `data`,
                # so merging all of extras_in gives correct partial-update semantics.
                for k, v in extras_in.items():
                    existing[k] = v
                updates["extra_settings"] = json.dumps(existing, ensure_ascii=False, separators=(",", ":")) if existing else None
            if not updates:
                return row
            updates["updated_at"] = now_ms()
            cols = ", ".join(f"{k}=?" for k in updates)
            self.conn.execute(f"update local_apps set {cols} where id=?", (*updates.values(), app_id))
            self.conn.commit()
            return self.conn.execute("select * from local_apps where id=?", (app_id,)).fetchone()

    def delete_user_app(self, app_id: str, owner_user_id: str) -> bool:
        with self.lock:
            app_id = self.resolve_local_app_id(app_id)
            cur = self.conn.execute(
                "delete from local_apps where id=? and owner_user_id=? and source='user'",
                (app_id, owner_user_id),
            )
            self.conn.commit()
            return cur.rowcount > 0

    def get_local_app(self, app_id: str) -> sqlite3.Row | None:
        with self.lock:
            clean = unquote(str(app_id or "").strip())
            if not clean:
                return None
            row = self.conn.execute(
                """
                select a.*,ra.has_opening,ra.has_world_info,ra.has_regex
                from local_apps a
                left join role_card_annotations ra on ra.app_id=a.id
                where a.id=?
                """,
                (clean,),
            ).fetchone()
            if row:
                return row
            lookup = clean[1:] if clean.startswith("#") else clean
            if lookup.lower().startswith("id:"):
                lookup = lookup[3:].strip()
            if not lookup:
                return None
            return self.conn.execute(
                """
                select a.*,ra.has_opening,ra.has_world_info,ra.has_regex
                from local_apps a
                left join role_card_annotations ra on ra.app_id=a.id
                where a.display_id=?
                """,
                (lookup,),
            ).fetchone()

    def resolve_local_app_id(self, app_id: str) -> str:
        clean = unquote(str(app_id or "").strip())
        row = self.get_local_app(clean)
        return str(row["id"]) if row else clean

    def list_local_apps(self, *, source: str | None = None, owner_user_id: str | None = None,
                        search: str = "", tag: str = "", sort: str = "default",
                        content_zone: str = "all",
                        random_seed: int | None = None,
                        page: int = 1, page_size: int = 30,
                        only_public: bool = True, only_published: bool = True,
                        lightweight: bool = False) -> tuple[list, int]:
        where = []
        if only_published:
            where.append("status='published'")
        params: list = []
        if only_public:
            where.append("is_public=1")
        if source:
            where.append("source=?")
            params.append(source)
        if owner_user_id:
            where = ["owner_user_id=?"]  # 我的角色：不限 public/status
            params = [owner_user_id]
        if search:
            where.append("(id like ? or display_id like ? or name like ? or summary like ? or description like ? or tags like ?)")
            params.extend([f"%{search}%", f"%{search}%", f"%{search}%", f"%{search}%", f"%{search}%", f"%{search}%"])
        if tag:
            where.append("(exists(select 1 from json_each(case when json_valid(local_apps.tags) then local_apps.tags else '[]' end) where trim(cast(value as text))=?) or (not json_valid(local_apps.tags) and tags like ?))")
            params.extend([tag, f"%{tag}%"])
        if str(content_zone or "").strip().lower() in ("clean", "safe", "pure"):
            clean_expr = (
                "lower(coalesce(name,'') || ' ' || coalesce(summary,'') || ' ' || "
                "coalesce(description,'') || ' ' || coalesce(tags,''))"
            )
            for term in CLEAN_ZONE_EXCLUDE_TERMS:
                where.append(f"{clean_expr} not like ?")
                params.append(f"%{term.lower()}%")
        where_sql = " where " + " and ".join(where) if where else ""
        offset = (max(1, page) - 1) * page_size
        sort_key = (sort or "default").strip().lower()
        order_params: list = []
        if sort_key == "random" and random_seed is not None:
            order_by = (
                "abs(((rowid * rowid * 1103515245) + "
                "(rowid * (? + 1) * 12345) + (? * 2654435761)) % 2147483647), updated_at desc"
            )
            seed_value = int(random_seed) & 0x7FFFFFFF
            order_params.extend([seed_value, seed_value])
        else:
            order_by = {
                "popular": "players_count desc, like_count desc, sort_weight desc, updated_at desc",
                "latest": "created_at desc, updated_at desc",
                "updated": "updated_at desc, sort_weight desc",
                "random": "abs(random())",
                "daily": "players_count desc, updated_at desc",
                "weekly": "players_count desc, like_count desc, updated_at desc",
                "monthly": "sort_weight desc, players_count desc, updated_at desc",
                "overall": "sort_weight desc, players_count desc, like_count desc, updated_at desc",
                "default": "sort_weight desc, updated_at desc",
            }.get(sort_key, "sort_weight desc, updated_at desc")
        select_cols = "*"
        if lightweight:
            select_cols = (
                "id,display_id,name,summary,description,cover_url,tags,age_rating,gender,language,"
                "players_count,like_count,source,status,is_public,sort_weight,created_at,updated_at,"
                "coalesce((select has_opening from role_card_annotations ra where ra.app_id=local_apps.id),"
                "case when length(trim(coalesce(opening_statement,'')))>0 then 1 else 0 end) as has_opening,"
                "coalesce((select has_world_info from role_card_annotations ra where ra.app_id=local_apps.id),"
                "case when json_valid(extra_settings) and json_array_length(extra_settings,'$.world_info')>0 then 1 else 0 end) as has_world_info,"
                "coalesce((select has_regex from role_card_annotations ra where ra.app_id=local_apps.id),"
                "case when json_valid(extra_settings) and json_array_length(extra_settings,'$.regex_scripts')>0 then 1 else 0 end) as has_regex"
            )
        with self.lock:
            total = self.conn.execute(f"select count(*) from local_apps{where_sql}", params).fetchone()[0]
            rows = self.conn.execute(
                f"select {select_cols} from local_apps{where_sql} order by {order_by} limit ? offset ?",
                (*params, *order_params, page_size, offset),
            ).fetchall()
        return [dict(r) for r in rows], int(total)

    def local_apps_count(self) -> dict:
        with self.lock:
            up = self.conn.execute("select count(*) from local_apps where source='upstream'").fetchone()[0]
            admin = self.conn.execute("select count(*) from local_apps where source='admin'").fetchone()[0]
            public_admin = self.conn.execute(
                "select count(*) from local_apps where source='admin' and status='published' and is_public=1"
            ).fetchone()[0]
            usr = self.conn.execute("select count(*) from local_apps where source='user'").fetchone()[0]
        return {
            "upstream": int(up),
            "admin": int(admin),
            "public_admin": int(public_admin),
            "user": int(usr),
            "total": int(up) + int(admin) + int(usr),
        }

    def creator_leaderboard(self, limit: int = 10) -> list[dict]:
        safe_limit = max(1, min(int(limit or 10), 50))
        with self.lock:
            rows = self.conn.execute(
                """
                select
                  u.id as user_id,
                  coalesce(u.name, '惑梦创作者') as user_name,
                  count(distinct a.id) as role_count,
                  coalesce(sum(coalesce(a.like_count, 0)), 0) as like_count,
                  count(distinct f.user_id || ':' || f.app_id) as favorite_count,
                  count(distinct c.id) as conversation_count,
                  max(a.updated_at) as last_updated_at
                from local_apps a
                join users u on u.id=a.owner_user_id
                left join user_favorites f on f.app_id=a.id
                left join conversations c on c.app_id=a.id
                where a.source='user' and a.status='published' and a.is_public=1
                group by u.id, u.name
                order by
                  (coalesce(sum(coalesce(a.like_count, 0)), 0) * 3
                   + count(distinct f.user_id || ':' || f.app_id) * 2
                   + count(distinct c.id)
                   + count(distinct a.id) * 5) desc,
                  max(a.updated_at) desc
                limit ?
                """,
                (safe_limit,),
            ).fetchall()
        out: list[dict] = []
        for idx, row in enumerate(rows, start=1):
            role_count = int(row["role_count"] or 0)
            like_count = int(row["like_count"] or 0)
            favorite_count = int(row["favorite_count"] or 0)
            conversation_count = int(row["conversation_count"] or 0)
            score = like_count * 3 + favorite_count * 2 + conversation_count + role_count * 5
            out.append({
                "rank": idx,
                "user_id": str(row["user_id"] or ""),
                "user_name": str(row["user_name"] or "惑梦创作者"),
                "role_count": role_count,
                "like_count": like_count,
                "favorite_count": favorite_count,
                "conversation_count": conversation_count,
                "score": int(score),
                "last_updated_at": int(row["last_updated_at"] or 0),
            })
        return out

    def creator_contests(self) -> dict:
        settings = self.site_settings()
        empty = settings.get("empty_states", {}) if isinstance(settings, dict) else {}
        month_label = time.strftime("%Y-%m", time.localtime())
        return {
            "active": True,
            "period": month_label,
            "title": empty.get("creator_contest_title") or "本期创作者比赛",
            "status": empty.get("creator_contest_status") or "长期开放",
            "description": empty.get("creator_contest_copy") or "每两周统计公开角色的聊天量、收藏和点赞，优质创作者会进入展示榜。",
            "reward": empty.get("creator_contest_reward") or "奖励：榜单展示、站内推荐位和后续积分激励。",
            "metrics": ["公开角色数", "点赞", "收藏", "会话数"],
        }

    def toggle_favorite(self, user_id: str, app_id: str) -> dict:
        ts = now_ms()
        with self.lock:
            app_id = self.resolve_local_app_id(app_id)
            if not self.conn.execute("select 1 from local_apps where id=?", (app_id,)).fetchone():
                raise ValueError("not found")
            exists = self.conn.execute(
                "select 1 from user_favorites where user_id=? and app_id=?",
                (user_id, app_id),
            ).fetchone()
            if exists:
                self.conn.execute("delete from user_favorites where user_id=? and app_id=?", (user_id, app_id))
                favored = False
            else:
                self.conn.execute(
                    "insert or ignore into user_favorites(user_id,app_id,created_at) values(?,?,?)",
                    (user_id, app_id, ts),
                )
                favored = True
            self.conn.commit()
        self.log_event(user_id, "favorite", ("收藏角色" if favored else "取消收藏"), {"app_id": app_id, "favorited": favored})
        return {"app_id": app_id, "favorited": favored}

    def toggle_like(self, user_id: str, app_id: str) -> dict:
        ts = now_ms()
        with self.lock:
            app_id = self.resolve_local_app_id(app_id)
            if not self.conn.execute("select 1 from local_apps where id=?", (app_id,)).fetchone():
                raise ValueError("not found")
            exists = self.conn.execute(
                "select 1 from user_likes where user_id=? and app_id=?",
                (user_id, app_id),
            ).fetchone()
            if exists:
                self.conn.execute("delete from user_likes where user_id=? and app_id=?", (user_id, app_id))
                self.conn.execute(
                    "update local_apps set like_count=case when coalesce(like_count,0) > 0 then like_count - 1 else 0 end where id=?",
                    (app_id,),
                )
                liked = False
            else:
                self.conn.execute(
                    "insert or ignore into user_likes(user_id,app_id,created_at) values(?,?,?)",
                    (user_id, app_id, ts),
                )
                self.conn.execute(
                    "update local_apps set like_count=coalesce(like_count,0) + 1 where id=?",
                    (app_id,),
                )
                liked = True
            row = self.conn.execute("select coalesce(like_count,0) as c from local_apps where id=?", (app_id,)).fetchone()
            self.conn.commit()
        self.log_event(user_id, "like", ("点赞角色" if liked else "取消点赞"), {"app_id": app_id, "liked": liked})
        return {"app_id": app_id, "liked": liked, "like_count": int(row["c"] if row else 0)}

    @staticmethod
    def app_comment_payload(row: sqlite3.Row | dict, current_user_id: str = "") -> dict:
        d = dict(row or {})
        return {
            "id": str(d.get("id") or ""),
            "app_id": str(d.get("app_id") or ""),
            "user_id": str(d.get("user_id") or ""),
            "user_name": str(d.get("user_name") or d.get("name") or "星月用户"),
            "content": str(d.get("content") or ""),
            "like_count": int(d.get("like_count") or 0),
            "liked": bool(d.get("liked")),
            "mine": bool(current_user_id and str(d.get("user_id") or "") == current_user_id),
            "created_at": int(d.get("created_at") or 0),
            "updated_at": int(d.get("updated_at") or d.get("created_at") or 0),
        }

    def list_app_comments(self, app_id: str, user_id: str = "", *, limit: int = 3) -> dict:
        clean_app = self.resolve_local_app_id(app_id)
        clean_user = str(user_id or "").strip()
        clean_limit = max(1, min(int(limit or 3), 100))
        if not clean_app:
            return {"list": [], "total": 0, "has_more": False, "limit": clean_limit}
        with self.lock:
            total = int(self.conn.execute(
                "select count(*) from app_comments where app_id=?",
                (clean_app,),
            ).fetchone()[0])
            rows = self.conn.execute(
                """
                select c.*, coalesce(u.name, '') as user_name,
                       case when cl.comment_id is not null then 1 else 0 end as liked
                from app_comments c
                left join users u on u.id=c.user_id
                left join app_comment_likes cl on cl.comment_id=c.id and cl.user_id=?
                where c.app_id=?
                order by c.like_count desc, c.created_at desc
                limit ?
                """,
                (clean_user, clean_app, clean_limit),
            ).fetchall()
        return {
            "list": [self.app_comment_payload(row, clean_user) for row in rows],
            "total": total,
            "has_more": total > len(rows),
            "limit": clean_limit,
        }

    def create_app_comment(self, user_id: str, app_id: str, content: str) -> dict:
        clean_user = str(user_id or "").strip()
        clean_app = self.resolve_local_app_id(app_id)
        clean_content = re.sub(r"\s+\n", "\n", str(content or "").replace("\r\n", "\n").replace("\r", "\n")).strip()
        clean_content = re.sub(r"\n{4,}", "\n\n\n", clean_content)
        if not clean_user:
            raise ValueError("unauthorized")
        if not clean_app:
            raise ValueError("app_id is required")
        if not clean_content:
            raise ValueError("评论内容不能为空")
        if len(clean_content) > 1000:
            clean_content = clean_content[:1000].rstrip()
        ts = now_ms()
        comment_id = "comment-" + uuid.uuid4().hex[:20]
        with self.lock:
            exists = self.conn.execute("select 1 from local_apps where id=?", (clean_app,)).fetchone()
            if not exists:
                raise ValueError("not found")
            self.conn.execute(
                """
                insert into app_comments(id,app_id,user_id,content,like_count,created_at,updated_at)
                values(?,?,?,?,?,?,?)
                """,
                (comment_id, clean_app, clean_user, clean_content, 0, ts, ts),
            )
            row = self.conn.execute(
                """
                select c.*, coalesce(u.name, '') as user_name, 0 as liked
                from app_comments c left join users u on u.id=c.user_id
                where c.id=?
                """,
                (comment_id,),
            ).fetchone()
            self.conn.commit()
        self.log_event(clean_user, "comment", "评论角色", {"app_id": clean_app, "comment_id": comment_id})
        return self.app_comment_payload(row, clean_user)

    def toggle_app_comment_like(self, user_id: str, comment_id: str) -> dict:
        clean_user = str(user_id or "").strip()
        clean_comment = str(comment_id or "").strip()
        if not clean_user:
            raise ValueError("unauthorized")
        if not clean_comment:
            raise ValueError("comment_id is required")
        ts = now_ms()
        with self.lock:
            row = self.conn.execute("select * from app_comments where id=?", (clean_comment,)).fetchone()
            if not row:
                raise ValueError("not found")
            exists = self.conn.execute(
                "select 1 from app_comment_likes where comment_id=? and user_id=?",
                (clean_comment, clean_user),
            ).fetchone()
            if exists:
                self.conn.execute(
                    "delete from app_comment_likes where comment_id=? and user_id=?",
                    (clean_comment, clean_user),
                )
                self.conn.execute(
                    "update app_comments set like_count=case when coalesce(like_count,0)>0 then like_count-1 else 0 end, updated_at=? where id=?",
                    (ts, clean_comment),
                )
                liked = False
            else:
                self.conn.execute(
                    "insert or ignore into app_comment_likes(comment_id,user_id,created_at) values(?,?,?)",
                    (clean_comment, clean_user, ts),
                )
                self.conn.execute(
                    "update app_comments set like_count=coalesce(like_count,0)+1, updated_at=? where id=?",
                    (ts, clean_comment),
                )
                liked = True
            updated = self.conn.execute(
                """
                select c.*, coalesce(u.name, '') as user_name,
                       case when cl.comment_id is not null then 1 else 0 end as liked
                from app_comments c
                left join users u on u.id=c.user_id
                left join app_comment_likes cl on cl.comment_id=c.id and cl.user_id=?
                where c.id=?
                """,
                (clean_user, clean_comment),
            ).fetchone()
            self.conn.commit()
        self.log_event(clean_user, "comment_like", ("点赞评论" if liked else "取消评论点赞"), {"comment_id": clean_comment, "app_id": row["app_id"]})
        return self.app_comment_payload(updated, clean_user)

    def is_liked(self, user_id: str | None, app_id: str) -> bool:
        if not user_id or not app_id:
            return False
        app_id = self.resolve_local_app_id(app_id)
        with self.lock:
            return bool(self.conn.execute(
                "select 1 from user_likes where user_id=? and app_id=?",
                (user_id, app_id),
            ).fetchone())

    def is_favorite(self, user_id: str | None, app_id: str) -> bool:
        if not user_id or not app_id:
            return False
        app_id = self.resolve_local_app_id(app_id)
        with self.lock:
            return bool(self.conn.execute(
                "select 1 from user_favorites where user_id=? and app_id=?",
                (user_id, app_id),
            ).fetchone())

    def app_interaction_states(self, user_id: str | None, app_ids: list[str]) -> tuple[set[str], set[str]]:
        clean_user = str(user_id or "").strip()
        clean_ids = list(dict.fromkeys(str(app_id or "").strip() for app_id in app_ids if str(app_id or "").strip()))
        if not clean_user or not clean_ids:
            return set(), set()
        placeholders = ",".join("?" for _ in clean_ids)
        with self.lock:
            favorite_rows = self.conn.execute(
                f"select app_id from user_favorites where user_id=? and app_id in ({placeholders})",
                (clean_user, *clean_ids),
            ).fetchall()
            liked_rows = self.conn.execute(
                f"select app_id from user_likes where user_id=? and app_id in ({placeholders})",
                (clean_user, *clean_ids),
            ).fetchall()
        return (
            {str(row["app_id"]) for row in favorite_rows},
            {str(row["app_id"]) for row in liked_rows},
        )

    def list_user_app_tags(self, user_id: str | None, app_id: str) -> list[str]:
        clean_user = str(user_id or "").strip()
        clean_app = self.resolve_local_app_id(app_id)
        if not clean_user or not clean_app:
            return []
        with self.lock:
            rows = self.conn.execute(
                "select tag from user_app_tags where user_id=? and app_id=? order by created_at asc",
                (clean_user, clean_app),
            ).fetchall()
        return [str(r["tag"]) for r in rows if str(r["tag"] or "").strip()]

    def set_user_app_tags(self, user_id: str, app_id: str, tags: list | str) -> dict:
        clean_user = str(user_id or "").strip()
        clean_app = self.resolve_local_app_id(app_id)
        if not clean_user:
            raise ValueError("unauthorized")
        if not clean_app:
            raise ValueError("app_id is required")
        if isinstance(tags, str):
            raw_tags = re.split(r"[，,\n]+", tags)
        elif isinstance(tags, list):
            raw_tags = tags
        else:
            raw_tags = []
        clean_tags: list[str] = []
        seen: set[str] = set()
        for raw in raw_tags:
            tag = re.sub(r"\s+", " ", str(raw or "")).strip().strip("#")
            if not tag:
                continue
            tag = tag[:24]
            key = tag.lower()
            if key in seen:
                continue
            seen.add(key)
            clean_tags.append(tag)
            if len(clean_tags) >= 12:
                break
        ts = now_ms()
        with self.lock:
            exists = self.conn.execute("select 1 from local_apps where id=?", (clean_app,)).fetchone()
            if not exists:
                raise ValueError("not found")
            self.conn.execute("delete from user_app_tags where user_id=? and app_id=?", (clean_user, clean_app))
            for tag in clean_tags:
                self.conn.execute(
                    "insert or ignore into user_app_tags(user_id,app_id,tag,created_at) values(?,?,?,?)",
                    (clean_user, clean_app, tag, ts),
                )
            self.conn.commit()
        self.log_event(clean_user, "user_tags", "更新玩家标签", {"app_id": clean_app, "tags": clean_tags})
        return {"app_id": clean_app, "tags": clean_tags, "user_tags": clean_tags}

    def list_favorites(self, user_id: str, *, page: int = 1, page_size: int = 30, search: str = "") -> tuple[list, int]:
        where = ["f.user_id=?"]
        params: list = [user_id]
        if search:
            where.append(
                "(a.name like ? or a.summary like ? or a.description like ? or a.tags like ? "
                "or exists(select 1 from user_app_tags ut where ut.user_id=f.user_id and ut.app_id=f.app_id and ut.tag like ?))"
            )
            params.extend([f"%{search}%", f"%{search}%", f"%{search}%", f"%{search}%", f"%{search}%"])
        where_sql = " where " + " and ".join(where)
        offset = (max(1, page) - 1) * page_size
        with self.lock:
            total = self.conn.execute(
                f"select count(*) from user_favorites f join local_apps a on a.id=f.app_id{where_sql}",
                params,
            ).fetchone()[0]
            rows = self.conn.execute(
                f"select a.*, f.created_at as favorited_at from user_favorites f "
                f"join local_apps a on a.id=f.app_id{where_sql} order by f.created_at desc limit ? offset ?",
                (*params, page_size, offset),
            ).fetchall()
        return [dict(r) for r in rows], int(total)

    def log_event(self, user_id: str, event_type: str, summary: str, payload: dict | None = None) -> None:
        with self.lock:
            self.conn.execute(
                "insert into user_events(user_id,event_type,summary,payload_json,created_at) values(?,?,?,?,?)",
                (user_id, event_type, summary, json.dumps(payload or {}, ensure_ascii=False), now_ms()),
            )
            self.conn.commit()

    def list_events(self, user_id: str, *, page: int = 1, page_size: int = 30) -> tuple[list[dict], int]:
        offset = (max(1, page) - 1) * page_size
        with self.lock:
            total = self.conn.execute("select count(*) from user_events where user_id=?", (user_id,)).fetchone()[0]
            rows = self.conn.execute(
                "select id,event_type,summary,payload_json,created_at from user_events "
                "where user_id=? order by id desc limit ? offset ?",
                (user_id, page_size, offset),
            ).fetchall()
        out = []
        for row in rows:
            item = dict(row)
            try:
                item["payload"] = json.loads(item.pop("payload_json") or "{}")
            except Exception:
                item["payload"] = {}
            out.append(item)
        return out, int(total)

    # ===== 站点级模型 API 配置 =====
    def get_api_settings_raw(self) -> dict:
        with self.lock:
            rows = self.conn.execute("select key,value from api_settings").fetchall()
        return {str(r["key"]): r["value"] for r in rows}

    def site_settings(self) -> dict:
        saved = self.get_api_settings_raw().get(SITE_SETTINGS_KEY) or ""
        parsed = {}
        if saved:
            try:
                value = json.loads(saved)
                if isinstance(value, dict):
                    parsed = value
            except Exception:
                parsed = {}
        return sanitize_site_settings(deep_merge_dict(site_settings_defaults(), parsed))

    def update_site_settings(self, data: dict) -> dict:
        current = self.site_settings()
        merged = deep_merge_dict(current, data if isinstance(data, dict) else {})
        clean = sanitize_site_settings(merged)
        with self.lock:
            self.conn.execute(
                "insert into api_settings(key,value,updated_at) values(?,?,?) "
                "on conflict(key) do update set value=excluded.value, updated_at=excluded.updated_at",
                (SITE_SETTINGS_KEY, json.dumps(clean, ensure_ascii=False, separators=(",", ":")), now_ms()),
            )
            self.conn.commit()
        return clean

    # ===== Tavo .tpg 插件包 =====
    def _tpg_package_dir(self) -> Path:
        base_dir = MEDIA_DIR or (DEFAULT_STATE_DIR / "media")
        path = base_dir / "tavo-plugins" / "packages"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def import_tavo_plugin(self, raw: str, filename: str = "") -> dict:
        parsed = parse_tpg_package(raw, filename)
        package_id = parsed["package_id"]
        plugin_id = clean_tpg_plugin_id(package_id, f"plugin-{parsed['file_sha256'][:12]}")
        dest_name = safe_filename(f"{plugin_id}-{parsed['file_sha256'][:12]}.tpg", "plugin.tpg")
        dest = self._tpg_package_dir() / dest_name
        dest.write_bytes(parsed["package_bytes"])
        ts = now_ms()
        manifest_json = json.dumps(parsed["manifest"], ensure_ascii=False, separators=(",", ":"))
        contributes_json = json.dumps(parsed["contributes"], ensure_ascii=False, separators=(",", ":"))
        files_payload = {
            "manifest_files": parsed.get("files") or [],
            "package_paths": parsed.get("package_paths") or [],
            "file_count": parsed.get("file_count") or 0,
            "package_size": parsed.get("package_size") or 0,
            "uncompressed_size": parsed.get("uncompressed_size") or 0,
        }
        files_json = json.dumps(files_payload, ensure_ascii=False, separators=(",", ":"))
        with self.lock:
            existing = self.conn.execute("select * from tavo_plugins where package_id=?", (package_id,)).fetchone()
            enabled = int(existing["enabled"]) if existing else 0
            self.conn.execute(
                """
                insert into tavo_plugins(
                    id,package_id,name,version,description,author,cover_path,file_name,file_sha256,
                    package_path,manifest_json,contributes_json,files_json,enabled,created_at,updated_at
                ) values(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                on conflict(package_id) do update set
                    id=excluded.id,
                    name=excluded.name,
                    version=excluded.version,
                    description=excluded.description,
                    author=excluded.author,
                    cover_path=excluded.cover_path,
                    file_name=excluded.file_name,
                    file_sha256=excluded.file_sha256,
                    package_path=excluded.package_path,
                    manifest_json=excluded.manifest_json,
                    contributes_json=excluded.contributes_json,
                    files_json=excluded.files_json,
                    updated_at=excluded.updated_at
                """,
                (
                    plugin_id,
                    package_id,
                    parsed["name"],
                    parsed["version"],
                    parsed.get("description") or "",
                    parsed.get("author") or "",
                    parsed.get("cover_path") or "",
                    parsed["file_name"],
                    parsed["file_sha256"],
                    str(dest),
                    manifest_json,
                    contributes_json,
                    files_json,
                    enabled,
                    ts if not existing else int(existing["created_at"] or ts),
                    ts,
                ),
            )
            self.conn.commit()
            row = self.conn.execute("select * from tavo_plugins where package_id=?", (package_id,)).fetchone()
        return tpg_plugin_row_json(row, include_manifest=True)

    def list_tavo_plugins(self, include_manifest: bool = False) -> list[dict]:
        with self.lock:
            rows = self.conn.execute("select * from tavo_plugins order by updated_at desc, name asc").fetchall()
        return [tpg_plugin_row_json(row, include_manifest=include_manifest) for row in rows]

    def get_tavo_plugin(self, plugin_id: str) -> sqlite3.Row | None:
        clean = str(plugin_id or "").strip()
        if not clean:
            return None
        with self.lock:
            return self.conn.execute(
                "select * from tavo_plugins where id=? or package_id=?",
                (clean, clean),
            ).fetchone()

    def set_tavo_plugin_enabled(self, plugin_id: str, enabled: bool) -> dict | None:
        with self.lock:
            row = self.get_tavo_plugin(plugin_id)
            if not row:
                return None
            self.conn.execute(
                "update tavo_plugins set enabled=?, updated_at=? where id=?",
                (1 if enabled else 0, now_ms(), row["id"]),
            )
            self.conn.commit()
            updated = self.conn.execute("select * from tavo_plugins where id=?", (row["id"],)).fetchone()
        return tpg_plugin_row_json(updated, include_manifest=True)

    def delete_tavo_plugin(self, plugin_id: str) -> bool:
        with self.lock:
            row = self.get_tavo_plugin(plugin_id)
            if not row:
                return False
            self.conn.execute("delete from tavo_plugins where id=?", (row["id"],))
            self.conn.commit()
        path = Path(str(row["package_path"] or ""))
        try:
            if path.exists() and path.is_file():
                path.unlink()
        except Exception:
            pass
        return True

    def _tavo_plugin_fragment_text(self, row: sqlite3.Row | dict, src: str) -> str:
        path = safe_tpg_path(src)
        package_path = Path(str(row["package_path"] if isinstance(row, sqlite3.Row) else row.get("package_path") or ""))
        if not package_path.exists():
            return ""
        try:
            with zipfile.ZipFile(package_path) as zf:
                info = zf.getinfo(path)
                if int(info.file_size or 0) > TPG_MAX_FRAGMENT_BYTES:
                    return ""
                return zf.read(path).decode("utf-8", errors="replace")
        except Exception:
            return ""

    def enabled_tavo_plugin_runtime_contributions(self) -> dict:
        with self.lock:
            rows = self.conn.execute(
                "select * from tavo_plugins where enabled=1 order by updated_at desc, name asc"
            ).fetchall()
        plugins: list[dict] = []
        for row in rows:
            item = tpg_plugin_row_json(row, include_manifest=False)
            contributes = item.get("contributes") if isinstance(item.get("contributes"), dict) else {}
            fragments = []
            for fragment in contributes.get("htmlFragments") or []:
                if not isinstance(fragment, dict):
                    continue
                src = str(fragment.get("src") or "").strip()
                content = self._tavo_plugin_fragment_text(row, src) if src else ""
                fragments.append({
                    "id": str(fragment.get("id") or src or "").strip()[:120],
                    "label": str(fragment.get("label") or fragment.get("name") or src or "").strip()[:120],
                    "src": src,
                    "html": content,
                    "enabled": bool(content),
                })
            item["runtime"] = {
                "htmlFragments": fragments,
                "inputActions": contributes.get("inputActions") if isinstance(contributes.get("inputActions"), list) else [],
                "sidebar": contributes.get("sidebar") if isinstance(contributes.get("sidebar"), list) else [],
                "messageActions": contributes.get("messageActions") if isinstance(contributes.get("messageActions"), list) else [],
                "settings": contributes.get("settings") if isinstance(contributes.get("settings"), (list, dict)) else [],
            }
            plugins.append(item)
        return {"list": plugins, "total": len(plugins)}

    def _legacy_llm_preset(self, saved: dict | None = None, include_secrets: bool = True) -> dict:
        saved = saved or self.get_api_settings_raw()
        enabled_raw = str(saved.get("enabled", "1")).strip().lower()
        try:
            temperature = float(saved.get("temperature") or USER_LLM_TEMPERATURE)
        except (TypeError, ValueError):
            temperature = USER_LLM_TEMPERATURE
        preset = {
            "id": "default",
            "name": "默认模型",
            "enabled": enabled_raw not in ("0", "false", "no", "off"),
            "protocol": normalize_llm_protocol(saved.get("protocol"), base_url=saved.get("base_url") or USER_LLM_BASE_URL),
            "base_url": (saved.get("base_url") or USER_LLM_BASE_URL or "").strip(),
            "model": (saved.get("model") or USER_LLM_MODEL or "gpt-4o-mini").strip(),
            "temperature": max(0.0, min(2.0, temperature)),
            "source": "legacy",
        }
        preset["models"] = split_model_names(saved.get("models") or preset["model"]) or [preset["model"]]
        api_key = (saved.get("api_key") or USER_LLM_API_KEY or "").strip()
        if include_secrets:
            preset["api_key"] = api_key
        else:
            preset["has_api_key"] = bool(api_key)
            preset["api_key_preview"] = ("..." + api_key[-4:]) if api_key else ""
        return preset

    def llm_presets(self, include_secrets: bool = True) -> tuple[list[dict], str]:
        saved = self.get_api_settings_raw()
        default_id = (saved.get("default_model_preset_id") or "default").strip() or "default"
        raw = saved.get("model_presets") or ""
        presets: list[dict] = []
        if raw:
            try:
                parsed = json.loads(raw)
                if isinstance(parsed, list):
                    presets = [p for p in parsed if isinstance(p, dict)]
            except Exception:
                presets = []
        if not presets:
            presets = [self._legacy_llm_preset(saved, include_secrets=True)]
            default_id = presets[0]["id"]
        normalized: list[dict] = []
        seen: set[str] = set()
        for idx, item in enumerate(presets):
            preset_id = re.sub(r"[^A-Za-z0-9_.-]+", "-", str(item.get("id") or f"preset-{idx+1}")).strip("-") or f"preset-{idx+1}"
            if preset_id in seen:
                preset_id = f"{preset_id}-{idx+1}"
            seen.add(preset_id)
            try:
                temperature = float(item.get("temperature", USER_LLM_TEMPERATURE))
            except (TypeError, ValueError):
                temperature = USER_LLM_TEMPERATURE
            api_key = str(item.get("api_key") or "").strip()
            preset = {
                "id": preset_id,
                "name": str(item.get("name") or item.get("label") or item.get("model") or preset_id).strip(),
                "enabled": bool(item.get("enabled", True)),
                "protocol": normalize_llm_protocol(item.get("protocol"), provider=item.get("provider"), base_url=item.get("base_url")),
                "base_url": str(item.get("base_url") or "").strip(),
                "model": str(item.get("model") or USER_LLM_MODEL or "gpt-4o-mini").strip(),
                "temperature": max(0.0, min(2.0, temperature)),
            }
            preset["models"] = split_model_names(item.get("models") or item.get("modelsText") or preset["model"]) or [preset["model"]]
            if include_secrets:
                preset["api_key"] = api_key
            else:
                preset["has_api_key"] = bool(api_key)
                preset["api_key_preview"] = ("..." + api_key[-4:]) if api_key else ""
            normalized.append(preset)
        if default_id not in {p["id"] for p in normalized}:
            default_id = normalized[0]["id"] if normalized else "default"
        return normalized, default_id

    def global_prompt_preset(self) -> dict:
        saved = self.get_api_settings_raw()
        return normalize_global_prompt_preset(saved.get(GLOBAL_PROMPT_PRESET_KEY) or "")

    def image_model_settings(self, include_secret: bool = False) -> dict:
        saved = self.get_api_settings_raw()
        return normalize_image_model_settings(
            saved.get(IMAGE_MODEL_SETTINGS_KEY) or "",
            include_secret=include_secret,
        )

    def memory_settings(self) -> dict:
        saved = self.get_api_settings_raw()
        return normalize_memory_settings(saved.get(MEMORY_SETTINGS_KEY) or "")

    def effective_llm_settings(self, app: dict | None = None, user_id: str = "") -> dict:
        presets, default_id = self.llm_presets(include_secrets=True)
        global_prompt = self.global_prompt_preset()
        enabled = [p for p in presets if p.get("enabled")]
        candidates = enabled or presets
        selected_key = ""
        if app:
            selected_key = normalize_user_selected_llm_model(app.get("llm_model"))
        if USER_BYOK_ENABLED and selected_key.startswith("user:") and user_id:
            user_preset_id = selected_key.split(":", 1)[1].strip()
            user_presets = self.user_model_presets(user_id, include_secret=True)["list"]
            selected_user = next((p for p in user_presets if p.get("id") == user_preset_id and p.get("enabled")), None)
            if selected_user:
                return {
                    "enabled": bool(selected_user.get("enabled", True)),
                    "protocol": normalize_llm_protocol(selected_user.get("protocol"), provider=selected_user.get("provider"), base_url=selected_user.get("base_url")),
                    "base_url": str(selected_user.get("base_url") or "").strip(),
                    "api_key": str(selected_user.get("api_key") or "").strip(),
                    "model": str(selected_user.get("model") or USER_LLM_MODEL or "gpt-4o-mini").strip(),
                    "temperature": float(selected_user.get("temperature", USER_LLM_TEMPERATURE)),
                    "preset_id": "user:" + str(selected_user.get("id") or user_preset_id),
                    "preset_name": selected_user.get("name") or selected_user.get("model") or "",
                    "source": "user",
                    "global_prompt_preset": global_prompt,
                }
        selected = None
        selected_model = ""
        if selected_key and "::" in selected_key:
            preset_part, _, model_part = selected_key.partition("::")
            selected = next((p for p in candidates if p.get("id") == preset_part), None)
            if selected:
                selected_model = next(
                    (m for m in split_model_names(selected.get("models") or selected.get("model")) if model_selection_id(preset_part, m) == selected_key),
                    "",
                )
        if selected_key and not selected:
            selected = next((p for p in candidates if p.get("id") == selected_key or p.get("model") == selected_key), None)
            if selected and selected.get("model") == selected_key:
                selected_model = selected_key
        if not selected:
            selected = next((p for p in candidates if p.get("id") == default_id), None)
        if not selected and candidates:
            selected = candidates[0]
        if not selected:
            selected = self._legacy_llm_preset(include_secrets=True)
        return {
            "enabled": bool(selected.get("enabled", True)),
            "protocol": normalize_llm_protocol(selected.get("protocol"), provider=selected.get("provider"), base_url=selected.get("base_url")),
            "base_url": str(selected.get("base_url") or USER_LLM_BASE_URL or "").strip(),
            "api_key": str(selected.get("api_key") or USER_LLM_API_KEY or "").strip(),
            "model": str(selected_model or selected.get("model") or USER_LLM_MODEL or "gpt-4o-mini").strip(),
            "temperature": float(selected.get("temperature", USER_LLM_TEMPERATURE)),
            "preset_id": selected.get("id") or default_id,
            "preset_name": selected.get("name") or selected.get("model") or "",
            "global_prompt_preset": global_prompt,
        }

    def public_llm_settings(self) -> dict:
        settings = self.effective_llm_settings()
        presets, default_id = self.llm_presets(include_secrets=False)
        api_key = settings.get("api_key") or ""
        preview = ("..." + api_key[-4:]) if api_key else ""
        return {
            "enabled": bool(settings.get("enabled")),
            "protocol": settings.get("protocol") or "openai",
            "base_url": settings.get("base_url") or "",
            "model": settings.get("model") or "",
            "default_model_preset_id": default_id,
            "presets": presets,
            "temperature": settings.get("temperature"),
            "has_api_key": bool(api_key),
            "api_key_preview": preview,
            "source": "database_or_env",
            "global_prompt_preset": self.global_prompt_preset(),
            "image_model": self.image_model_settings(include_secret=False),
            "memory_settings": self.memory_settings(),
        }

    def public_model_presets(self) -> dict:
        presets, default_id = self.llm_presets(include_secrets=False)
        visible = [
            item
            for p in presets
            if p.get("enabled")
            for item in [
                {
                    "id": model_selection_id(p["id"], model) if len(split_model_names(p.get("models") or p.get("model"))) > 1 else p["id"],
                    "preset_id": p["id"],
                    "name": p.get("name") or p.get("model") or p["id"],
                    "protocol": p.get("protocol") or "openai",
                    "model": model,
                    "enabled": bool(p.get("enabled")),
                    "is_default": p["id"] == default_id and idx == 0,
                }
                for idx, model in enumerate(split_model_names(p.get("models") or p.get("model")) or [p.get("model") or ""])
            ]
        ]
        if not visible and presets:
            p = presets[0]
            visible = [{"id": p["id"], "preset_id": p["id"], "name": p.get("name") or p.get("model") or p["id"], "protocol": p.get("protocol") or "openai", "model": p.get("model") or "", "enabled": True, "is_default": True}]
            default_id = p["id"]
        else:
            default_id = next((p["id"] for p in visible if p.get("is_default")), visible[0]["id"] if visible else default_id)
        return {"list": visible, "default_id": default_id, "total": len(visible)}

    def public_model_selection(self, value: object) -> str:
        selected = normalize_user_selected_llm_model(value)
        if not selected:
            return ""
        allowed = {str(item.get("id") or "") for item in self.public_model_presets().get("list", [])}
        return selected if selected in allowed else ""

    def provider_templates(self) -> list[dict]:
        if not USER_BYOK_ENABLED:
            return []
        return [
            {"id": "openai", "name": "OpenAI Compatible", "protocol": "openai", "base_url": "https://api.openai.com/v1", "model": "gpt-4o-mini"},
            {"id": "openrouter", "name": "OpenRouter", "protocol": "openai", "base_url": "https://openrouter.ai/api/v1", "model": "openai/gpt-4o-mini"},
            {"id": "deepseek", "name": "DeepSeek", "protocol": "openai", "base_url": "https://api.deepseek.com/v1", "model": "deepseek-chat"},
            {"id": "moonshot", "name": "Moonshot", "protocol": "openai", "base_url": "https://api.moonshot.cn/v1", "model": "moonshot-v1-8k"},
            {"id": "anthropic", "name": "Anthropic / Claude", "protocol": "anthropic", "base_url": "https://api.anthropic.com/v1", "model": "claude-3-5-haiku-latest"},
            {"id": "custom-openai", "name": "自定义 OpenAI-compatible", "protocol": "openai", "base_url": "", "model": ""},
            {"id": "custom-anthropic", "name": "自定义 Anthropic-compatible", "protocol": "anthropic", "base_url": "", "model": ""},
        ]

    def _user_model_row(self, row, include_secret: bool = False) -> dict:
        data = dict(row)
        api_key = str(data.get("api_key") or "")
        payload = {
            "id": data.get("preset_id") or "",
            "name": data.get("name") or "",
            "provider": data.get("provider") or "custom",
            "protocol": normalize_llm_protocol(data.get("protocol"), provider=data.get("provider"), base_url=data.get("base_url")),
            "base_url": data.get("base_url") or "",
            "model": data.get("model") or "",
            "temperature": float(data.get("temperature") or 0.7),
            "enabled": bool(data.get("enabled", 1)),
            "is_default": bool(data.get("is_default", 0)),
            "has_api_key": bool(api_key),
            "api_key_preview": ("..." + api_key[-4:]) if api_key else "",
            "source": "user",
        }
        if include_secret:
            payload["api_key"] = api_key
        return payload

    def user_model_presets(self, user_id: str, include_secret: bool = False) -> dict:
        if not USER_BYOK_ENABLED:
            return {"list": [], "default_id": "", "total": 0, "templates": [], "enabled": False}
        with self.lock:
            rows = self.conn.execute(
                "select * from user_model_presets where user_id=? order by is_default desc, updated_at desc",
                (user_id,),
            ).fetchall()
        presets = [self._user_model_row(r, include_secret=include_secret) for r in rows]
        default_id = next((p["id"] for p in presets if p.get("is_default")), presets[0]["id"] if presets else "")
        return {"list": presets, "default_id": default_id, "total": len(presets), "templates": self.provider_templates()}

    def save_user_model_presets(self, user_id: str, presets: list) -> dict:
        if not USER_BYOK_ENABLED:
            raise ValueError("user model connectors are disabled")
        if not isinstance(presets, list):
            raise ValueError("presets must be a list")
        clean: list[dict] = []
        seen: set[str] = set()
        existing = {p["id"]: p for p in self.user_model_presets(user_id, include_secret=True)["list"]}
        for idx, raw in enumerate(presets[:20]):
            if not isinstance(raw, dict):
                continue
            preset_id = re.sub(r"[^A-Za-z0-9_.-]+", "-", str(raw.get("id") or f"user-{idx+1}")).strip("-") or f"user-{idx+1}"
            if preset_id in seen:
                preset_id = f"{preset_id}-{idx+1}"
            seen.add(preset_id)
            base_url = str(raw.get("base_url") or "").strip().rstrip("/")
            model = str(raw.get("model") or "").strip()
            name = str(raw.get("name") or raw.get("provider") or model or preset_id).strip()[:80]
            if not base_url or not model:
                continue
            api_key = str(raw.get("api_key") or "").strip()
            if not api_key and raw.get("keep_api_key", True):
                api_key = str(existing.get(preset_id, {}).get("api_key") or "")
            try:
                temperature = float(raw.get("temperature", 0.7))
            except Exception:
                temperature = 0.7
            clean.append({
                "id": preset_id,
                "name": name,
                "provider": str(raw.get("provider") or "custom").strip()[:40],
                "protocol": normalize_llm_protocol(raw.get("protocol"), provider=raw.get("provider"), base_url=base_url),
                "base_url": base_url,
                "model": model,
                "api_key": api_key,
                "temperature": max(0.0, min(2.0, temperature)),
                "enabled": bool(raw.get("enabled", True)),
                "is_default": bool(raw.get("is_default", False)),
            })
        if clean and not any(p.get("is_default") for p in clean):
            clean[0]["is_default"] = True
        ts = now_ms()
        with self.lock:
            self.conn.execute("delete from user_model_presets where user_id=?", (user_id,))
            self.conn.executemany(
                """
                insert into user_model_presets(user_id,preset_id,name,provider,protocol,base_url,model,api_key,temperature,enabled,is_default,created_at,updated_at)
                values(?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                [
                    (user_id, p["id"], p["name"], p["provider"], p["protocol"], p["base_url"], p["model"], p["api_key"], p["temperature"], 1 if p["enabled"] else 0, 1 if p["is_default"] else 0, ts, ts)
                    for p in clean
                ],
            )
            self.conn.commit()
        return self.user_model_presets(user_id, include_secret=False)

    def update_llm_settings(self, data: dict) -> dict:
        current = self.get_api_settings_raw()
        existing_presets, _ = self.llm_presets(include_secrets=True)
        existing_by_id = {p["id"]: p for p in existing_presets}
        raw_presets = data.get("presets")
        normalized_presets = None
        if isinstance(raw_presets, list):
            normalized_presets = []
            for idx, item in enumerate(raw_presets[:50]):
                if not isinstance(item, dict):
                    continue
                preset_id = re.sub(r"[^A-Za-z0-9_.-]+", "-", str(item.get("id") or f"preset-{idx+1}")).strip("-") or f"preset-{idx+1}"
                old = existing_by_id.get(preset_id, {})
                clear_key = bool(item.get("clear_api_key"))
                incoming_key = str(item.get("api_key") or "").strip()
                if clear_key:
                    api_key = ""
                elif incoming_key:
                    api_key = incoming_key
                else:
                    api_key = str(old.get("api_key") or "").strip()
                try:
                    temperature = float(item.get("temperature", USER_LLM_TEMPERATURE))
                except (TypeError, ValueError):
                    temperature = USER_LLM_TEMPERATURE
                normalized_presets.append({
                    "id": preset_id,
                    "name": str(item.get("name") or item.get("model") or preset_id).strip(),
                    "enabled": bool(item.get("enabled", True)),
                    "protocol": normalize_llm_protocol(item.get("protocol"), provider=item.get("provider"), base_url=item.get("base_url")),
                    "base_url": str(item.get("base_url") or "").strip(),
                    "model": str(item.get("model") or USER_LLM_MODEL or "gpt-4o-mini").strip(),
                    "models": split_model_names(item.get("models") or item.get("modelsText") or item.get("model") or USER_LLM_MODEL),
                    "temperature": max(0.0, min(2.0, temperature)),
                    "api_key": api_key,
                })
            if not normalized_presets:
                raise ValueError("at least one model preset is required")
        updates = {
            "enabled": "1" if bool(data.get("enabled", True)) else "0",
            "protocol": normalize_llm_protocol(data.get("protocol"), base_url=data.get("base_url")),
            "base_url": str(data.get("base_url") or "").strip(),
            "model": str(data.get("model") or "").strip() or USER_LLM_MODEL,
            "temperature": str(max(0.0, min(2.0, float(data.get("temperature") or USER_LLM_TEMPERATURE)))),
        }
        if normalized_presets is not None:
            default_id = str(data.get("default_model_preset_id") or "").strip()
            if default_id not in {p["id"] for p in normalized_presets}:
                default_id = normalized_presets[0]["id"]
            updates["model_presets"] = json.dumps(normalized_presets, ensure_ascii=False, separators=(",", ":"))
            updates["default_model_preset_id"] = default_id
            default_preset = next((p for p in normalized_presets if p["id"] == default_id), normalized_presets[0])
            updates["enabled"] = "1" if bool(default_preset.get("enabled", True)) else "0"
            updates["protocol"] = default_preset.get("protocol") or "openai"
            updates["base_url"] = default_preset.get("base_url") or ""
            updates["model"] = default_preset.get("model") or USER_LLM_MODEL
            updates["models"] = "\n".join(split_model_names(default_preset.get("models") or default_preset.get("model")))
            updates["temperature"] = str(default_preset.get("temperature", USER_LLM_TEMPERATURE))
            updates["api_key"] = default_preset.get("api_key") or ""
        if data.get("clear_api_key"):
            updates["api_key"] = ""
        else:
            incoming_key = str(data.get("api_key") or "").strip()
            if incoming_key and normalized_presets is None:
                updates["api_key"] = incoming_key
            elif "api_key" in current and normalized_presets is None:
                updates["api_key"] = current.get("api_key") or ""
        if "global_prompt_preset" in data:
            updates[GLOBAL_PROMPT_PRESET_KEY] = json.dumps(
                normalize_global_prompt_preset(data.get("global_prompt_preset")),
                ensure_ascii=False,
                separators=(",", ":"),
            )
        if "image_model" in data:
            current_image = self.image_model_settings(include_secret=True)
            raw_image = data.get("image_model") if isinstance(data.get("image_model"), dict) else {}
            image_payload = dict(raw_image)
            if image_payload.get("clear_api_key"):
                image_payload["api_key"] = ""
            elif not str(image_payload.get("api_key") or "").strip():
                image_payload["api_key"] = current_image.get("api_key") or ""
            image_settings = normalize_image_model_settings(image_payload, include_secret=True)
            updates[IMAGE_MODEL_SETTINGS_KEY] = json.dumps(
                image_settings,
                ensure_ascii=False,
                separators=(",", ":"),
            )
        if "memory_settings" in data:
            updates[MEMORY_SETTINGS_KEY] = json.dumps(
                normalize_memory_settings(data.get("memory_settings")),
                ensure_ascii=False,
                separators=(",", ":"),
            )
        ts = now_ms()
        with self.lock:
            for key, value in updates.items():
                self.conn.execute(
                    "insert into api_settings(key,value,updated_at) values(?,?,?) "
                    "on conflict(key) do update set value=excluded.value, updated_at=excluded.updated_at",
                    (key, value, ts),
                )
            self.conn.commit()
        return self.public_llm_settings()


def go_response(data: object, code: int = 100000, msg: str = "ok") -> dict:
    return {"code": code, "msg": msg, "data": data}


def normalize_admin_app_data(data: dict, partial: bool = False) -> dict:
    if not isinstance(data, dict):
        return {}

    def first_str(*keys: str) -> str:
        for key in keys:
            value = data.get(key)
            if value is None:
                continue
            if isinstance(value, (dict, list)):
                continue
            text = str(value).strip()
            if text:
                return text
        return ""

    def parse_list(value: object) -> list:
        if value is None or value == "":
            return []
        if isinstance(value, list):
            return [str(v).strip() for v in value if str(v).strip()]
        if isinstance(value, str):
            text = value.strip()
            if not text:
                return []
            try:
                parsed = json.loads(text)
                if isinstance(parsed, list):
                    return [str(v).strip() for v in parsed if str(v).strip()]
            except Exception:
                pass
            return [s.strip() for s in re.split(r"[，,\n;；|]", text) if s.strip()]
        return [str(value).strip()] if str(value).strip() else []

    def parse_int(value: object, default: int = 0) -> int:
        try:
            return int(value)
        except Exception:
            return default

    def parse_bool(value: object, default: bool = True) -> bool:
        if value is None:
            return default
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return value != 0
        text = str(value).strip().lower()
        if text in ("1", "true", "yes", "on", "public", "published", "公开", "发布"):
            return True
        if text in ("0", "false", "no", "off", "private", "draft", "私有", "草稿"):
            return False
        return default

    out = {}
    field_map = {
        "name": ("name", "title", "character_name", "角色名称"),
        "summary": ("summary", "subtitle", "short_description", "intro", "简介"),
        "description": ("description", "prompt", "profile", "setting", "角色设定", "设定"),
        "cover_url": ("cover_url", "cover", "icon", "avatar", "image", "image_url", "封面"),
        "opening_statement": ("opening_statement", "opening", "first_message", "greeting", "开场白"),
        "pre_prompt": ("pre_prompt", "system_prompt", "system", "instruction", "instructions", "系统提示词"),
        "llm_model": ("llm_model", "model", "模型"),
        "api_base_url": ("api_base_url", "base_url"),
        "language": ("language", "lang"),
        "status": ("status",),
    }
    for target, keys in field_map.items():
        value = first_str(*keys)
        if value or not partial:
            out[target] = value

    if not out.get("summary") and out.get("description"):
        out["summary"] = out["description"][:120]
    if "cover_url" in out:
        out["cover_url"] = normalize_cover_input(out.get("cover_url") or "")
    if "status" in out:
        status = (out.get("status") or "").strip().lower()
        out["status"] = status if status in ("published", "draft", "disabled") else ("published" if not partial else status)

    if "tags" in data or "tag" in data or "标签" in data or not partial:
        out["tags"] = parse_list(data.get("tags", data.get("tag", data.get("标签"))))
    if "suggested_questions" in data or "questions" in data or "starters" in data or not partial:
        out["suggested_questions"] = parse_list(data.get("suggested_questions", data.get("questions", data.get("starters"))))
    if "age_rating" in data or not partial:
        out["age_rating"] = parse_int(data.get("age_rating"), 0)
    if "gender" in data or not partial:
        out["gender"] = parse_int(data.get("gender"), 0)
    if "sort_weight" in data or "sort" in data or "weight" in data or not partial:
        out["sort_weight"] = parse_int(data.get("sort_weight", data.get("sort", data.get("weight"))), 100)
    if "is_public" in data or "public" in data or not partial:
        out["is_public"] = parse_bool(data.get("is_public", data.get("public")), True)
    if not out.get("language") and not partial:
        out["language"] = "zh-Hans"
    return out


def normalize_admin_rich_app_payload(data: dict) -> dict:
    """Extract rich ST/Character Card fields from admin create/update payloads."""
    if not isinstance(data, dict):
        return {}
    out: dict = {}
    source = data.get("data") if isinstance(data.get("data"), dict) else data
    if isinstance(data.get("spec"), str) or isinstance(source.get("character_book"), dict) or "first_mes" in source:
        try:
            out.update(silly_card_to_app(data))
            if "is_public" not in data and "public" not in data:
                out.pop("is_public", None)
        except Exception:
            pass
    for key in (
        "personality", "scenario", "mes_example", "post_history_instructions",
        "alternate_greetings", "world_info", "creator_notes", "character_version",
        "creator", "extensions", "prompt_blocks", "quick_replies", "regex_scripts",
        "TavernHelper_scripts", "sampling", "bg_url", "nsfw", "protected",
        "protected_prompt", "anonymous",
    ):
        if key in data:
            out[key] = data.get(key)
        elif isinstance(source, dict) and key in source:
            out[key] = source.get(key)

    if "world_info" not in out:
        for candidate in (data, source):
            if not isinstance(candidate, dict):
                continue
            try:
                world = normalize_admin_bulk_world_info(candidate)
            except Exception:
                world = []
            if world:
                out["world_info"] = world
                break
    elif not isinstance(out.get("world_info"), list):
        try:
            out["world_info"] = normalize_admin_bulk_world_info(out.get("world_info"))
        except Exception:
            out["world_info"] = []
    if isinstance(out.get("extensions"), dict) and "regex_scripts" not in out:
        promoted = regex_scripts_from_extensions(out["extensions"])
        if promoted:
            out["regex_scripts"] = promoted
    return out


def extract_import_items(payload: object) -> list:
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        for key in ("items", "list", "cards", "apps", "characters", "data"):
            value = payload.get(key)
            if isinstance(value, list):
                return value
        return [payload]
    return []


def truthy(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    text = str(value or "").strip().lower()
    return text in ("1", "true", "yes", "on", "y", "enabled", "启用", "是")


def parse_json_object(value: object) -> dict:
    if isinstance(value, dict):
        return dict(value)
    if not value:
        return {}
    try:
        parsed = json.loads(str(value))
        return parsed if isinstance(parsed, dict) else {}
    except Exception:
        return {}


def normalize_bulk_app_ids(value: object) -> list[str]:
    if isinstance(value, str):
        raw_items = re.split(r"[，,\n;\s]+", value)
    elif isinstance(value, list):
        raw_items = value
    else:
        raw_items = []
    seen: set[str] = set()
    out: list[str] = []
    for item in raw_items:
        app_id = str(item or "").strip()
        if not app_id or app_id in seen:
            continue
        seen.add(app_id)
        out.append(app_id)
    return out


def normalize_admin_bulk_tags(value: object) -> list[str]:
    if isinstance(value, str):
        text = value.strip()
        if not text:
            raw_items = []
        else:
            try:
                parsed = json.loads(text)
                raw_items = parsed if isinstance(parsed, list) else re.split(r"[，,\n;；|]", text)
            except Exception:
                raw_items = re.split(r"[，,\n;；|]", text)
    elif isinstance(value, list):
        raw_items = value
    else:
        raw_items = []
    seen: set[str] = set()
    out: list[str] = []
    for item in raw_items:
        tag = str(item or "").strip()[:40]
        key = tag.casefold()
        if not tag or key in seen:
            continue
        seen.add(key)
        out.append(tag)
        if len(out) >= 40:
            break
    return out


def merge_text_tags(existing: list[str], incoming: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for tag in [*(existing or []), *(incoming or [])]:
        text = str(tag or "").strip()[:40]
        key = text.casefold()
        if not text or key in seen:
            continue
        seen.add(key)
        out.append(text)
        if len(out) >= 40:
            break
    return out


def normalize_admin_bulk_world_info(value: object) -> list:
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return []
        try:
            value = json.loads(text)
        except Exception as exc:
            raise ValueError(f"world_info JSON 解析失败: {exc}") from exc

    entries = value
    if isinstance(value, dict):
        data = value.get("data") if isinstance(value.get("data"), dict) else {}
        character_book = value.get("character_book") if isinstance(value.get("character_book"), dict) else {}
        data_character_book = data.get("character_book") if isinstance(data.get("character_book"), dict) else {}
        if isinstance(value.get("world_info"), list):
            entries = value.get("world_info")
        elif isinstance(value.get("entries"), list):
            entries = value.get("entries")
        elif isinstance(value.get("items"), list):
            entries = value.get("items")
        elif isinstance(character_book.get("entries"), list):
            entries = character_book.get("entries")
        elif isinstance(data_character_book.get("entries"), list):
            entries = data_character_book.get("entries")
        elif "content" in value or "entry" in value:
            entries = [value]
        else:
            entries = []
    if not isinstance(entries, list):
        raise ValueError("world_info must be a list or Character Book object")
    return normalize_world_info(entries)


def world_merge_key(entry: dict) -> str:
    raw_id = str(entry.get("id") or "").strip()
    if raw_id and not re.fullmatch(r"world-\d+", raw_id):
        return "id:" + raw_id.casefold()
    name = str(entry.get("name") or "").strip()
    if name:
        return "name:" + name.casefold()
    return ""


def merge_world_info_entries(existing: list, incoming: list) -> list:
    merged = normalize_world_info(existing or [])
    index_by_key: dict[str, int] = {}
    for idx, entry in enumerate(merged):
        if isinstance(entry, dict):
            key = world_merge_key(entry)
            if key and key not in index_by_key:
                index_by_key[key] = idx
    for entry in normalize_world_info(incoming or []):
        key = world_merge_key(entry)
        if key and key in index_by_key:
            merged[index_by_key[key]] = entry
        elif len(merged) < 200:
            merged.append(entry)
            if key:
                index_by_key[key] = len(merged) - 1
    return merged[:200]


def apply_macros(text: object, char_name: str = "", user_name: str = "") -> str:
    """SillyTavern 风格宏替换：{{char}}/{{name}}→角色名，{{user}}→用户人设名。
    大小写不敏感，空值安全；兼容旧式 <BOT>/<USER>。"""
    if not isinstance(text, str) or not text:
        return text if isinstance(text, str) else ""
    char = (char_name or "Ta").strip() or "Ta"
    user = (user_name or "你").strip() or "你"
    out = text
    for pat, val in (
        (r"\{\{\s*char\s*\}\}", char),
        (r"\{\{\s*name\s*\}\}", char),
        (r"\{\{\s*user\s*\}\}", user),
        (r"<BOT>", char),
        (r"<USER>", user),
    ):
        out = re.sub(pat, val, out, flags=re.IGNORECASE)
    return out


class TemplateNull:
    def __bool__(self):
        return False

    def __str__(self):
        return ""

    def __repr__(self):
        return ""

    def __iter__(self):
        return iter(())


TEMPLATE_NULL = TemplateNull()


class TemplateDict(dict):
    def __getattribute__(self, key):
        if not key.startswith("_") and dict.__contains__(self, key):
            return dict.__getitem__(self, key)
        return dict.__getattribute__(self, key)

    def __getattr__(self, key):
        if key.startswith("_"):
            raise AttributeError(key)
        return self.get(key, TEMPLATE_NULL)


def template_wrap(value):
    if isinstance(value, TemplateDict):
        return value
    if isinstance(value, dict):
        return TemplateDict({str(k): template_wrap(v) for k, v in value.items()})
    if isinstance(value, list):
        return [template_wrap(v) for v in value]
    return value


def template_unwrap(value):
    if isinstance(value, TemplateNull):
        return None
    if isinstance(value, TemplateDict):
        return {k: template_unwrap(v) for k, v in dict.items(value)}
    if isinstance(value, list):
        return [template_unwrap(v) for v in value]
    return value


def template_path_get(root, path: object, default=None):
    current = root
    parts = [p for p in re.split(r"[.\[\]]+", str(path or "")) if p not in ("", "'")]
    for part in parts:
        key = part.strip("'\"")
        if isinstance(current, TemplateDict):
            current = dict.get(current, key, TEMPLATE_NULL)
        elif isinstance(current, dict):
            current = current.get(key, TEMPLATE_NULL)
        elif isinstance(current, list) and key.isdigit():
            idx = int(key)
            current = current[idx] if 0 <= idx < len(current) else TEMPLATE_NULL
        else:
            return default
        if isinstance(current, TemplateNull):
            return default
    return current


def template_path_set(root: dict, path: object, value) -> str:
    parts = [p.strip("'\"") for p in re.split(r"[.\[\]]+", str(path or "")) if p not in ("", "'")]
    if not parts:
        return ""
    current = root
    for part in parts[:-1]:
        existing = dict.get(current, part) if isinstance(current, dict) else None
        if not isinstance(existing, dict):
            current[part] = {}
        current = current[part]
    current[parts[-1]] = template_unwrap(value)
    return parts[0]


def template_path_delete(root: dict, path: object, index=None) -> tuple[str, object]:
    parts = [p.strip("'\"") for p in re.split(r"[.\[\]]+", str(path or "")) if p not in ("", "'")]
    if not parts:
        return "", None
    current = root
    for part in parts[:-1]:
        if isinstance(current, dict):
            current = current.get(part)
        elif isinstance(current, list) and part.isdigit():
            idx = int(part)
            current = current[idx] if 0 <= idx < len(current) else None
        else:
            return parts[0], None
        if current is None:
            return parts[0], None
    key = parts[-1]
    old = None
    if index is not None:
        target = template_path_get(root, path, [])
        if isinstance(target, list):
            try:
                idx = int(index)
                if idx < 0:
                    idx = len(target) + idx
                if 0 <= idx < len(target):
                    old = target.pop(idx)
            except Exception:
                pass
        return parts[0], old
    if isinstance(current, dict) and key in current:
        old = current.pop(key)
    elif isinstance(current, list) and key.isdigit():
        idx = int(key)
        if 0 <= idx < len(current):
            old = current.pop(idx)
    return parts[0], old


def template_path_insert(root: dict, path: object, value, index=None) -> str:
    current = template_path_get(root, path, TEMPLATE_NULL)
    if not isinstance(current, list):
        current = []
        template_path_set(root, path, current)
    try:
        idx = int(index) if index is not None else len(current)
    except Exception:
        idx = len(current)
    if idx < 0:
        idx = max(0, len(current) + idx + 1)
    idx = max(0, min(idx, len(current)))
    current.insert(idx, template_unwrap(value))
    parts = [p.strip("'\"") for p in re.split(r"[.\[\]]+", str(path or "")) if p not in ("", "'")]
    return parts[0] if parts else ""


def contains_tavern_template(value: object) -> bool:
    return isinstance(value, str) and "<%" in value and "%>" in value


def strip_tavern_template_tags(value: str) -> str:
    return re.sub(r"<%[\s\S]*?%>", "", str(value or ""))


def split_top_level_operator(text: str, operator: str) -> tuple[str, str] | None:
    depth = 0
    quote = ""
    escape = False
    i = 0
    while i < len(text):
        ch = text[i]
        if quote:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == quote:
                quote = ""
            i += 1
            continue
        if ch in ("'", '"', "`"):
            quote = ch
            i += 1
            continue
        if ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth = max(0, depth - 1)
        elif depth == 0 and text.startswith(operator, i):
            return text[:i].strip(), text[i + len(operator):].strip()
        i += 1
    return None


def split_top_level_ternary(text: str) -> tuple[str, str, str] | None:
    depth = 0
    quote = ""
    escape = False
    qpos = -1
    i = 0
    while i < len(text):
        ch = text[i]
        if quote:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == quote:
                quote = ""
            i += 1
            continue
        if ch in ("'", '"', "`"):
            quote = ch
            i += 1
            continue
        if ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth = max(0, depth - 1)
        elif depth == 0 and ch == "?" and not text.startswith("??", i):
            qpos = i
            break
        i += 1
    if qpos < 0:
        return None
    depth = 0
    quote = ""
    escape = False
    for j in range(qpos + 1, len(text)):
        ch = text[j]
        if quote:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == quote:
                quote = ""
            continue
        if ch in ("'", '"', "`"):
            quote = ch
            continue
        if ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth = max(0, depth - 1)
        elif depth == 0 and ch == ":":
            return text[:qpos].strip(), text[qpos + 1:j].strip(), text[j + 1:].strip()
    return None


def translate_js_expr(expr: object) -> str:
    text = str(expr or "").strip()
    text = re.sub(r"\bawait\s+", "", text)
    text = re.sub(r";\s*$", "", text)
    nullish = split_top_level_operator(text, "??")
    if nullish:
        left, right = nullish
        return f"coalesce({translate_js_expr(left)}, {translate_js_expr(right)})"
    ternary = split_top_level_ternary(text)
    if ternary:
        condition, yes_value, no_value = ternary
        return f"({translate_js_expr(yes_value)} if {translate_js_expr(condition)} else {translate_js_expr(no_value)})"
    text = re.sub(r"\btrue\b", "True", text, flags=re.IGNORECASE)
    text = re.sub(r"\bfalse\b", "False", text, flags=re.IGNORECASE)
    text = re.sub(r"\bnull\b|\bundefined\b", "None", text, flags=re.IGNORECASE)
    text = text.replace("!==", "!=").replace("===", "==")
    text = text.replace("&&", " and ").replace("||", " or ")
    text = re.sub(r"(?<![=!<>])!(?!=)", " not ", text)
    text = re.sub(r"\bMath\.", "math.", text)
    text = re.sub(r"\bJSON\.parse\s*\(", "parseJSON(", text)
    text = re.sub(r"\bJSON\.stringify\s*\(", "stringifyJSON(", text)
    text = re.sub(r"\bNumber\s*\(", "float(", text)
    text = re.sub(r"\bString\s*\(", "str(", text)
    text = re.sub(r"\bBoolean\s*\(", "bool(", text)
    text = re.sub(r"(\b[A-Za-z_][\w.]*|\))\.length\b", r"length(\1)", text)
    text = re.sub(r"(\b[A-Za-z_][\w.]*)\.includes\s*\(", r"includes(\1, ", text)
    text = re.sub(r"(\b[A-Za-z_][\w.]*)\.trim\s*\(\)", r"trim(\1)", text)
    text = re.sub(r"(\b[A-Za-z_][\w.]*)\.toLowerCase\s*\(\)", r"lower(\1)", text)
    text = re.sub(r"(\b[A-Za-z_][\w.]*)\.toUpperCase\s*\(\)", r"upper(\1)", text)
    text = re.sub(r"(\b[A-Za-z_][\w.]*)\.startsWith\s*\(", r"startsWith(\1, ", text)
    text = re.sub(r"(\b[A-Za-z_][\w.]*)\.endsWith\s*\(", r"endsWith(\1, ", text)
    text = re.sub(r"(\b[A-Za-z_][\w.]*)\.split\s*\(", r"split(\1, ", text)
    text = re.sub(r"(\b[A-Za-z_][\w.]*)\.join\s*\(", r"join(\1, ", text)
    text = re.sub(r"([{,]\s*)([A-Za-z_]\w*)\s*:", r"\1'\2':", text)
    return text


TEMPLATE_ALLOWED_CALLS = {
    "abs", "activateRegex", "bool", "coalesce", "decGlobalVar", "decLocalVar",
    "decMessageVar", "decvar", "delGlobalVar", "delLocalVar", "delMessageVar",
    "delvar", "execute", "float", "getChara", "getChatMessages", "getGlobalVar", "getLocalVar",
    "getMessageVar", "getPromptsInjected", "getWorldInfo", "getchar", "getvar",
    "getwi", "hasPromptsInjected", "includes", "incGlobalVar", "incLocalVar",
    "incMessageVar", "incvar", "insGlobalVar", "insLocalVar", "insMessageVar",
    "insertGlobalVar", "insertLocalVar", "insertMessageVar", "insvar",
    "injectPrompt", "int", "join", "len", "length", "list", "lower",
    "matchChatMessages", "max", "min", "parseJSON", "print", "range", "round",
    "safe_iter", "setGlobalVar", "setLocalVar", "setMessageVar", "setvar",
    "split", "startsWith", "endsWith", "str", "stringifyJSON", "trim", "upper",
}
TEMPLATE_ALLOWED_MATH_CALLS = {
    "ceil", "floor", "sqrt", "pow", "round", "abs", "min", "max",
    "sin", "cos", "tan", "asin", "acos", "atan",
}
TEMPLATE_ALLOWED_NODES = (
    ast.Module, ast.Expression, ast.Expr, ast.Assign, ast.Name, ast.Load, ast.Store, ast.Constant,
    ast.BinOp, ast.UnaryOp, ast.BoolOp, ast.Compare, ast.If, ast.IfExp, ast.For, ast.Call,
    ast.Attribute, ast.Subscript, ast.List, ast.Tuple, ast.Dict, ast.Slice, ast.keyword,
    ast.Add, ast.Sub, ast.Mult, ast.Div, ast.FloorDiv, ast.Mod, ast.Pow,
    ast.USub, ast.UAdd, ast.Not, ast.And, ast.Or, ast.Eq, ast.NotEq, ast.Lt,
    ast.LtE, ast.Gt, ast.GtE, ast.In, ast.NotIn, ast.Is, ast.IsNot,
)


def validate_template_ast(tree: ast.AST) -> None:
    for node in ast.walk(tree):
        if not isinstance(node, TEMPLATE_ALLOWED_NODES):
            raise ValueError(f"template syntax not allowed: {type(node).__name__}")
        if isinstance(node, ast.Name) and node.id.startswith("__"):
            raise ValueError("template private names are not allowed")
        if isinstance(node, ast.Attribute) and node.attr.startswith("_"):
            raise ValueError("template private attributes are not allowed")
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id in TEMPLATE_ALLOWED_CALLS:
                continue
            if (
                isinstance(node.func, ast.Attribute)
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id == "math"
                and node.func.attr in TEMPLATE_ALLOWED_MATH_CALLS
            ):
                continue
            else:
                raise ValueError("template function is not allowed")


def validate_template_expr(expr: object) -> str:
    translated = translate_js_expr(expr)
    tree = ast.parse(translated, mode="eval")
    validate_template_ast(tree)
    return translated


def _clean_ejs_code(code: str) -> str:
    clean = str(code or "").strip()
    if clean.startswith("_"):
        clean = clean[1:].lstrip()
    if clean.endswith("-"):
        clean = clean[:-1].rstrip()
    return clean


def _extract_parens_expr(code: str, keyword: str) -> str:
    pattern = rf"^{keyword}\s*\(([\s\S]*)\)$"
    match = re.match(pattern, code.strip())
    return match.group(1).strip() if match else ""


def compile_tavern_template(source: str) -> str:
    token_re = re.compile(r"<%([=-]?)([\s\S]*?)%>")
    lines = ["__out = []"]
    indent = 0
    pos = 0
    switch_stack: list[dict] = []
    switch_counter = 0

    def add(line: str) -> None:
        lines.append("    " * indent + line)

    def close_one_block() -> None:
        nonlocal indent
        if switch_stack and indent <= switch_stack[-1]["base"] + 1:
            indent = switch_stack[-1]["base"]
            switch_stack.pop()
        else:
            indent = max(0, indent - 1)

    for match in token_re.finditer(source):
        literal = source[pos:match.start()]
        if literal:
            add(f"__out.append({literal!r})")
        pos = match.end()
        tag = match.group(1)
        code = _clean_ejs_code(match.group(2))
        if tag in ("=", "-"):
            expr = validate_template_expr(code)
            add(f"__out.append(str({expr}))")
            continue
        while code.startswith("}"):
            close_one_block()
            code = code[1:].strip()
        code = code.strip()
        if not code:
            continue
        if code in {"break", "break;"}:
            continue
        block = code.endswith("{")
        if block:
            code = code[:-1].strip()
        if code.startswith("else if"):
            expr = _extract_parens_expr(code.replace("else if", "if", 1), "if")
            add(f"elif {validate_template_expr(expr)}:")
            indent += 1
        elif code == "else":
            add("else:")
            indent += 1
        elif code.startswith("if"):
            expr = _extract_parens_expr(code, "if")
            add(f"if {validate_template_expr(expr)}:")
            indent += 1
        elif code.startswith("for"):
            inner = _extract_parens_expr(code, "for")
            of_match = re.match(r"(?:const|let|var)?\s*([A-Za-z_]\w*)\s+of\s+([\s\S]+)", inner)
            range_match = re.match(
                r"(?:let|var)?\s*([A-Za-z_]\w*)\s*=\s*([\s\S]+?)\s*;\s*\1\s*(<=|<|>=|>)\s*([\s\S]+?)\s*;\s*\1\s*(\+\+|--|\+=\s*\d+|-=\s*\d+)",
                inner,
            )
            if of_match:
                name, iterable = of_match.groups()
                add(f"for {name} in safe_iter({validate_template_expr(iterable)}):")
                indent += 1
            elif range_match:
                name, start, op, end, update = range_match.groups()
                step = 1
                if update == "--":
                    step = -1
                elif update.startswith("+="):
                    step = max(1, min(50, int(re.sub(r"\D+", "", update) or "1")))
                elif update.startswith("-="):
                    step = -max(1, min(50, int(re.sub(r"\D+", "", update) or "1")))
                if op in {">", ">="} and step > 0:
                    step = -step
                start_expr = validate_template_expr(start)
                end_expr = validate_template_expr(end)
                if op == "<=":
                    stop_expr = f"int({end_expr}) + 1"
                elif op == ">=":
                    stop_expr = f"int({end_expr}) - 1"
                else:
                    stop_expr = f"int({end_expr})"
                add(f"for {name} in range(int({start_expr}), {stop_expr}, {step}):")
                indent += 1
        elif code.startswith("switch"):
            nonlocal_var = f"__switch_{switch_counter}"
            switch_counter += 1
            expr = _extract_parens_expr(code, "switch")
            add(f"{nonlocal_var} = {validate_template_expr(expr)}")
            switch_stack.append({"name": nonlocal_var, "base": indent, "seen": False})
        elif code.startswith("case ") and switch_stack:
            switch = switch_stack[-1]
            indent = switch["base"]
            expr = code[5:].rstrip(":").strip()
            add(("elif" if switch["seen"] else "if") + f" {switch['name']} == {validate_template_expr(expr)}:")
            switch["seen"] = True
            indent += 1
        elif code.startswith("default") and switch_stack:
            switch = switch_stack[-1]
            indent = switch["base"]
            add("else:")
            switch["seen"] = True
            indent += 1
        else:
            statement = re.sub(r"^(?:let|const|var)\s+", "", code).rstrip(";")
            statement = translate_js_expr(statement)
            ast_tree = ast.parse(statement, mode="exec")
            validate_template_ast(ast_tree)
            for line in statement.splitlines():
                if line.strip():
                    add(line.strip())
            if block and statement.endswith(":"):
                indent += 1
    if pos < len(source):
        add(f"__out.append({source[pos:]!r})")
    lines.append("__result = ''.join(str(x) for x in __out)")
    return "\n".join(lines)


def template_truthy(value) -> bool:
    if isinstance(value, TemplateNull):
        return False
    return bool(value)


def safe_template_range(*args):
    try:
        nums = [int(a) for a in args[:3]]
    except Exception:
        return range(0)
    if len(nums) == 1:
        start, stop, step = 0, nums[0], 1
    elif len(nums) == 2:
        start, stop, step = nums[0], nums[1], 1
    else:
        start, stop, step = nums[0], nums[1], nums[2] or 1
    if abs(stop - start) > 500:
        stop = start + (500 if stop >= start else -500)
    return range(start, stop, step)


def safe_template_iter(value):
    if isinstance(value, TemplateNull) or value is None:
        return []
    if isinstance(value, dict):
        return list(dict.values(value))[:500]
    if isinstance(value, (list, tuple, set)):
        return list(value)[:500]
    if isinstance(value, str):
        return list(value[:500])
    return []


def template_length(value) -> int:
    if isinstance(value, TemplateNull) or value is None:
        return 0
    try:
        return len(value)
    except Exception:
        return 0


def template_includes(container, item) -> bool:
    if isinstance(container, TemplateNull) or container is None:
        return False
    try:
        return item in container
    except Exception:
        return False


def build_template_env(template_context: dict | None, *, char_name: str, user_name: str, phase: str, message: dict | None = None):
    ctx = template_context if isinstance(template_context, dict) else {}
    variables = ctx.get("variables") if isinstance(ctx.get("variables"), dict) else {}
    global_vars = ctx.get("global_variables") if isinstance(ctx.get("global_variables"), dict) else {}
    app_vars = ctx.get("character_variables") if isinstance(ctx.get("character_variables"), dict) else {}
    chat_vars = ctx.get("chat_variables") if isinstance(ctx.get("chat_variables"), dict) else {}
    wrapped_variables = template_wrap(variables)
    wrapped_global_vars = template_wrap(global_vars)
    wrapped_app_vars = template_wrap(app_vars)
    wrapped_chat_vars = template_wrap(chat_vars)
    user_id = str(ctx.get("user_id") or "")
    app_id = str(ctx.get("app_id") or "")
    conv_id = str(ctx.get("conversation_id") or "")
    store = ctx.get("store")

    def _normalize_template_scope(scope: object, fallback: str = "") -> str:
        clean = str(scope or fallback or "").strip().lower()
        if clean in {"global", "globals"}:
            return "global"
        if clean in {"app", "character", "char", "chara"}:
            return "app"
        if clean in {"local", "chat", "conversation", "message", "cache", "initial"}:
            return "conversation"
        return fallback or ("conversation" if conv_id else ("app" if app_id else "global"))

    def _template_options(options=None, defaults=None) -> dict:
        if isinstance(options, (dict, TemplateDict)):
            opts = template_unwrap(options) or {}
        elif isinstance(options, str):
            token = options.strip()
            low = token.lower()
            opts = {}
            if low in {"global", "local", "chat", "conversation", "message", "cache", "initial", "app", "character", "char", "chara"}:
                opts["scope"] = low
            elif low in {"nx", "xx", "n", "nxs", "xxs"}:
                opts["flags"] = low
            elif low in {"old", "new", "fullcache"}:
                opts["results"] = low
        else:
            opts = {}
            if options is not None and defaults is None:
                defaults = options
        if defaults is not None:
            opts.setdefault("defaults", defaults)
        return opts

    def _scope_id(scope: str) -> str:
        clean_scope = _normalize_template_scope(scope)
        if clean_scope == "global":
            return ""
        if clean_scope == "app":
            return app_id
        return conv_id or app_id

    def _roots_for_scope(scope: object):
        clean_scope = _normalize_template_scope(scope)
        if clean_scope == "global":
            return global_vars, wrapped_global_vars, "global"
        if clean_scope == "app":
            return app_vars, wrapped_app_vars, "app"
        return chat_vars, wrapped_chat_vars, "conversation"

    def _persist_top(scope: object, top_name: str, root: dict) -> None:
        clean_scope = _normalize_template_scope(scope)
        if store is None or not user_id or not top_name:
            return
        try:
            root_value = template_path_get(root, top_name, None)
            store.set_template_variable(user_id, clean_scope, _scope_id(clean_scope), top_name, root_value)
        except Exception as exc:
            log(f"template variable persist failed: {exc}")

    def getvar(path, options=None, defaults=None):
        opts = _template_options(options, defaults)
        default_value = defaults
        if "defaults" in opts:
            default_value = opts.get("defaults")
        scope = _normalize_template_scope(opts.get("scope") or "", "")
        roots = {
            "global": global_vars,
            "app": app_vars,
            "conversation": chat_vars,
            "local": chat_vars,
            "chat": chat_vars,
            "message": chat_vars,
        }
        if scope in roots:
            value = template_path_get(roots[scope], path, TEMPLATE_NULL)
        else:
            value = template_path_get(chat_vars, path, TEMPLATE_NULL)
            if isinstance(value, TemplateNull):
                value = template_path_get(app_vars, path, TEMPLATE_NULL)
            if isinstance(value, TemplateNull):
                value = template_path_get(global_vars, path, TEMPLATE_NULL)
            if isinstance(value, TemplateNull):
                value = template_path_get(variables, path, TEMPLATE_NULL)
        return default_value if isinstance(value, TemplateNull) else value

    def setvar(path, value=None, options=None):
        opts = _template_options(options)
        scope = _normalize_template_scope(opts.get("scope") or "")
        flags = str(opts.get("flags") or "n").strip().lower()
        target_root, target_wrapped, clean_scope = _roots_for_scope(scope)
        old_value = template_path_get(target_root, path, TEMPLATE_NULL)
        exists = not isinstance(old_value, TemplateNull)
        if flags in {"nx", "nxs"} and exists:
            return old_value
        if flags in {"xx", "xxs"} and not exists:
            return None
        top_name = template_path_set(target_root, path, value)
        template_path_set(variables, path, value)
        template_path_set(target_wrapped, path, value)
        template_path_set(wrapped_variables, path, value)
        _persist_top(clean_scope, top_name, target_root)
        result = str(opts.get("results") or "new").lower()
        if result == "old":
            return None if isinstance(old_value, TemplateNull) else old_value
        if result == "fullcache":
            return template_wrap(target_root)
        return value

    def _scoped_options(scope: str, options=None) -> dict:
        opts = _template_options(options)
        opts["scope"] = scope
        return opts

    def _as_number(value) -> int | float:
        if isinstance(value, TemplateNull) or value is None or value == "":
            return 0
        try:
            f = float(value)
            return int(f) if f.is_integer() else f
        except Exception:
            return 0

    def incvar(path, value=1, options=None):
        opts = _template_options(options)
        current = _as_number(getvar(path, {**opts, "defaults": 0}))
        delta = _as_number(value)
        new_value = current + delta
        if isinstance(new_value, float) and new_value.is_integer():
            new_value = int(new_value)
        setvar(path, new_value, opts)
        return new_value

    def decvar(path, value=1, options=None):
        return incvar(path, -_as_number(value), options)

    def delvar(path, index=None, options=None):
        opts = _template_options(options)
        target_root, target_wrapped, clean_scope = _roots_for_scope(opts.get("scope") or "")
        top_name, old = template_path_delete(target_root, path, index)
        template_path_delete(variables, path, index)
        template_path_delete(target_wrapped, path, index)
        template_path_delete(wrapped_variables, path, index)
        _persist_top(clean_scope, top_name, target_root)
        return old

    def insvar(path, value=None, index=None, options=None):
        opts = _template_options(options)
        target_root, target_wrapped, clean_scope = _roots_for_scope(opts.get("scope") or "")
        top_name = template_path_insert(target_root, path, value, index)
        template_path_insert(variables, path, value, index)
        template_path_insert(target_wrapped, path, value, index)
        template_path_insert(wrapped_variables, path, value, index)
        _persist_top(clean_scope, top_name, target_root)
        return template_path_get(target_root, path, [])

    def coalesce(left, right=None):
        if isinstance(left, TemplateNull) or left is None:
            return right
        return left

    def trim(value):
        return str("" if isinstance(value, TemplateNull) else value).strip()

    def lower(value):
        return str("" if isinstance(value, TemplateNull) else value).lower()

    def upper(value):
        return str("" if isinstance(value, TemplateNull) else value).upper()

    def startsWith(value, prefix):
        return str("" if isinstance(value, TemplateNull) else value).startswith(str(prefix))

    def endsWith(value, suffix):
        return str("" if isinstance(value, TemplateNull) else value).endswith(str(suffix))

    def split(value, sep=None):
        return str("" if isinstance(value, TemplateNull) else value).split(None if isinstance(sep, TemplateNull) else sep)

    def join(value, sep=","):
        if isinstance(value, (list, tuple, set)):
            return str(sep).join(str(v) for v in value)
        return str("" if isinstance(value, TemplateNull) else value)

    def parseJSON(text):
        try:
            return template_wrap(json.loads(str(text or "")))
        except Exception:
            return TEMPLATE_NULL

    def stringifyJSON(value):
        try:
            return json.dumps(template_unwrap(value), ensure_ascii=False, separators=(",", ":"))
        except Exception:
            return ""

    def _prompt_slots() -> dict:
        slots = ctx.setdefault("prompt_slots", {})
        return slots if isinstance(slots, dict) else {}

    def injectPrompt(key, prompt, order=100, sticky=0, uid=""):
        clean_key = str(key or "").strip()[:120]
        if not clean_key:
            return ""
        try:
            clean_order = int(order)
        except Exception:
            clean_order = 100
        slots = _prompt_slots()
        items = slots.setdefault(clean_key, [])
        if isinstance(items, list) and len(items) < 80:
            items.append({
                "order": clean_order,
                "prompt": str(prompt or "")[:8000],
                "uid": str(uid or "")[:120],
            })
        return ""

    def getPromptsInjected(key, postprocess=None):
        clean_key = str(key or "").strip()[:120]
        items = _prompt_slots().get(clean_key)
        if not isinstance(items, list):
            return ""
        return "\n".join(str(item.get("prompt") or "") for item in sorted(items, key=lambda x: int(x.get("order") or 0)))[:12000]

    def hasPromptsInjected(key):
        return bool(getPromptsInjected(key))

    def _current_world_entries() -> list:
        app_obj = ctx.get("app") if isinstance(ctx.get("app"), dict) else {}
        extras = app_extras(app_obj) if isinstance(app_obj, dict) else {}
        return normalize_world_info(extras.get("world_info") or [])

    def getwi(*args):
        title = ""
        if args:
            if len(args) >= 2 and isinstance(args[1], str):
                title = args[1]
            else:
                title = args[0]
        needle = str(title or "").strip().lower()
        if not needle:
            return ""
        for entry in _current_world_entries():
            names = [
                str(entry.get("id") or ""),
                str(entry.get("name") or ""),
                *(str(k or "") for k in (entry.get("keys") or [])[:8]),
            ]
            if any(needle == value.strip().lower() for value in names if value):
                local_ctx = dict(ctx)
                local_ctx["world_info"] = entry
                return render_tavern_template(
                    strip_tavern_world_controls(entry.get("content")),
                    char_name,
                    user_name,
                    template_context=local_ctx,
                    phase=phase,
                    max_output=8000,
                )
        return ""

    def _character_definition(card: dict) -> str:
        if not isinstance(card, dict):
            return ""
        extras = app_extras(card)
        parts = [f"Name: {card.get('name') or char_name}"]
        for label, value in (
            ("Description", card.get("description")),
            ("Personality", extras.get("personality")),
            ("Scenario", extras.get("scenario")),
            ("Opening", card.get("opening_statement")),
        ):
            text = str(value or "").strip()
            if text:
                parts.append(f"{label}: {text}")
        return "\n".join(parts)[:12000]

    def getchar(name=None, template=None, data=None):
        requested = str(name or "").strip().lower()
        app_obj = ctx.get("app") if isinstance(ctx.get("app"), dict) else {}
        if not requested or requested in {str(app_obj.get("id") or "").lower(), str(app_obj.get("name") or char_name).lower()}:
            return _character_definition(app_obj)
        if store is not None:
            try:
                rows, _total = store.list_local_apps(search=requested, page=1, page_size=1, only_public=True, only_published=True)
                if rows:
                    return _character_definition(local_app_to_card(dict(rows[0])))
            except Exception:
                return ""
        return ""

    def getChatMessages(count=None, end=None, role=None):
        base = ctx.get("context") if isinstance(ctx.get("context"), dict) else {}
        history = base.get("history") if isinstance(base.get("history"), list) else []
        values = list(history)
        if isinstance(count, str) and count in {"user", "assistant", "system"}:
            role = count
            count = None
        if role:
            values = [m for m in values if str(m.get("role") or "") == str(role)]
        try:
            if end is not None:
                start = int(count or 0)
                stop = int(end)
                return template_wrap(values[start:stop])
            if count is not None:
                n = int(count)
                return template_wrap(values[-n:] if n >= 0 else values[n:])
        except Exception:
            pass
        return template_wrap(values)

    def matchChatMessages(pattern, options=None):
        opts = _template_options(options)
        role = str(opts.get("role") or "").strip().lower()
        out = []
        try:
            regex = re.compile(str(pattern or ""), flags=re.IGNORECASE | re.DOTALL)
        except re.error:
            return []
        for msg in template_unwrap(getChatMessages()) or []:
            if role and role != "any" and str(msg.get("role") or "") != role:
                continue
            if regex.search(str(msg.get("content") or "")):
                out.append(msg)
        return template_wrap(out[:40])

    def activateRegex(*_args, **_kwargs):
        return ""

    def execute(*_args, **_kwargs):
        return ""

    env = {
        "__builtins__": {},
        "__out": [],
        "abs": abs,
        "activateRegex": activateRegex,
        "app": template_wrap(ctx.get("app") if isinstance(ctx.get("app"), dict) else {}),
        "bool": bool,
        "char": char_name,
        "coalesce": coalesce,
        "context": template_wrap(ctx.get("context") if isinstance(ctx.get("context"), dict) else {}),
        "decvar": decvar,
        "decLocalVar": lambda path, value=1, options=None: decvar(path, value, _scoped_options("conversation", options)),
        "decGlobalVar": lambda path, value=1, options=None: decvar(path, value, _scoped_options("global", options)),
        "decMessageVar": lambda path, value=1, options=None: decvar(path, value, _scoped_options("conversation", options)),
        "delvar": delvar,
        "delLocalVar": lambda path, index=None, options=None: delvar(path, index, _scoped_options("conversation", options)),
        "delGlobalVar": lambda path, index=None, options=None: delvar(path, index, _scoped_options("global", options)),
        "delMessageVar": lambda path, index=None, options=None: delvar(path, index, _scoped_options("conversation", options)),
        "endsWith": endsWith,
        "execute": execute,
        "float": float,
        "getChara": getchar,
        "getchar": getchar,
        "getwi": getwi,
        "getWorldInfo": getwi,
        "getvar": getvar,
        "getLocalVar": lambda path, options=None: getvar(path, _scoped_options("conversation", options)),
        "getGlobalVar": lambda path, options=None: getvar(path, _scoped_options("global", options)),
        "getMessageVar": lambda path, options=None: getvar(path, _scoped_options("conversation", options)),
        "getChatMessages": getChatMessages,
        "matchChatMessages": matchChatMessages,
        "getPromptsInjected": getPromptsInjected,
        "global_variables": wrapped_global_vars,
        "hasPromptsInjected": hasPromptsInjected,
        "incvar": incvar,
        "incLocalVar": lambda path, value=1, options=None: incvar(path, value, _scoped_options("conversation", options)),
        "incGlobalVar": lambda path, value=1, options=None: incvar(path, value, _scoped_options("global", options)),
        "incMessageVar": lambda path, value=1, options=None: incvar(path, value, _scoped_options("conversation", options)),
        "insvar": insvar,
        "insLocalVar": lambda path, value=None, index=None, options=None: insvar(path, value, index, _scoped_options("conversation", options)),
        "insGlobalVar": lambda path, value=None, index=None, options=None: insvar(path, value, index, _scoped_options("global", options)),
        "insMessageVar": lambda path, value=None, index=None, options=None: insvar(path, value, index, _scoped_options("conversation", options)),
        "insertLocalVar": lambda path, value=None, index=None, options=None: insvar(path, value, index, _scoped_options("conversation", options)),
        "insertGlobalVar": lambda path, value=None, index=None, options=None: insvar(path, value, index, _scoped_options("global", options)),
        "insertMessageVar": lambda path, value=None, index=None, options=None: insvar(path, value, index, _scoped_options("conversation", options)),
        "injectPrompt": injectPrompt,
        "int": int,
        "includes": template_includes,
        "join": join,
        "len": template_length,
        "length": template_length,
        "list": list,
        "lower": lower,
        "math": math,
        "max": max,
        "message": template_wrap(message or {}),
        "min": min,
        "parseJSON": parseJSON,
        "print": lambda *args: env["__out"].append("".join(str(a) for a in args)),
        "range": safe_template_range,
        "round": round,
        "safe_iter": safe_template_iter,
        "setLocalVar": lambda path, value=None, options=None: setvar(path, value, _scoped_options("conversation", options)),
        "setGlobalVar": lambda path, value=None, options=None: setvar(path, value, _scoped_options("global", options)),
        "setMessageVar": lambda path, value=None, options=None: setvar(path, value, _scoped_options("conversation", options)),
        "setvar": setvar,
        "split": split,
        "startsWith": startsWith,
        "str": str,
        "stringifyJSON": stringifyJSON,
        "trim": trim,
        "upper": upper,
        "user": user_name,
        "variables": wrapped_variables,
        "character_variables": wrapped_app_vars,
        "chat_variables": wrapped_chat_vars,
        "world_info": template_wrap(ctx.get("world_info") if isinstance(ctx.get("world_info"), dict) else {}),
        "phase": phase,
    }
    return env


def render_tavern_template(text: object, char_name: str = "", user_name: str = "", *, template_context: dict | None = None, phase: str = "generate", message: dict | None = None, max_output: int = 24000) -> str:
    value = apply_macros(text, char_name, user_name)
    if not contains_tavern_template(value):
        return value
    try:
        code = compile_tavern_template(value)
        tree = ast.parse(code, mode="exec")
        env = build_template_env(template_context, char_name=char_name or "Ta", user_name=user_name or "你", phase=phase, message=message)
        exec(compile(tree, "<tavern-template>", "exec"), env, env)
        return str(env.get("__result") or "")[:max_output]
    except Exception as exc:
        log(f"tavern template skipped: {exc}")
        return strip_tavern_template_tags(value)[:max_output]


def eval_tavern_template_expr(expr: object, char_name: str = "", user_name: str = "", *, template_context: dict | None = None) -> bool:
    try:
        translated = validate_template_expr(expr)
        tree = ast.parse(translated, mode="eval")
        env = build_template_env(template_context, char_name=char_name or "Ta", user_name=user_name or "你", phase="condition")
        return template_truthy(eval(compile(tree, "<tavern-template-expr>", "eval"), env, env))
    except Exception as exc:
        log(f"tavern template condition skipped: {exc}")
        return False


WORLD_GENERATE_TAG_RE = re.compile(r"\[GENERATE:([^\]]+)\]", re.IGNORECASE)
WORLD_RENDER_TAG_RE = re.compile(r"\[RENDER:([^\]]+)\]", re.IGNORECASE)
WORLD_INITIAL_TAG_RE = re.compile(r"\[InitialVariables\]", re.IGNORECASE)


def _world_first_line(content: object) -> str:
    for line in str(content or "").replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        clean = line.strip()
        if clean:
            return clean
    return ""


def _world_header_text(entry: dict) -> str:
    return "\n".join([
        str((entry or {}).get("name") or "").strip(),
        _world_first_line((entry or {}).get("content")),
    ]).strip()


def tavern_world_condition_expr(entry: dict) -> str:
    content_lines = [
        line.strip()
        for line in str((entry or {}).get("content") or "").replace("\r\n", "\n").replace("\r", "\n").split("\n")
        if line.strip()
    ][:8]
    for value in (str((entry or {}).get("name") or ""), *content_lines):
        match = re.match(r"^@@if\s+(.+)$", value.strip(), flags=re.IGNORECASE)
        if match:
            return match.group(1).strip()
    return ""


def tavern_world_condition_passes(entry: dict, *, char_name: str = "", user_name: str = "", template_context: dict | None = None) -> bool:
    expr = tavern_world_condition_expr(entry)
    if not expr:
        return True
    return eval_tavern_template_expr(expr, char_name, user_name, template_context=template_context)


def tavern_world_special(entry: dict) -> dict | None:
    header = _world_header_text(entry)
    content_lines = [
        line.strip()
        for line in str((entry or {}).get("content") or "").replace("\r\n", "\n").replace("\r", "\n").split("\n")
        if line.strip()
    ][:8]
    for line in (str((entry or {}).get("name") or "").strip(), *content_lines):
        if re.match(r"^@INJECT\b", line, flags=re.IGNORECASE):
            return {"kind": "inject", "line": line}
        if re.match(r"^@@generate_before\b", line, flags=re.IGNORECASE):
            return {"kind": "generate", "body": "BEFORE"}
        if re.match(r"^@@generate_after\b", line, flags=re.IGNORECASE):
            return {"kind": "generate", "body": "AFTER"}
        if re.match(r"^@@render_before\b", line, flags=re.IGNORECASE):
            return {"kind": "render", "body": "BEFORE"}
        if re.match(r"^@@render_after\b", line, flags=re.IGNORECASE):
            return {"kind": "render", "body": "AFTER"}
        if re.match(r"^@@initial_variables\b", line, flags=re.IGNORECASE):
            return {"kind": "initial", "body": "INITIAL"}
    match = WORLD_GENERATE_TAG_RE.search(header)
    if match:
        return {"kind": "generate", "body": match.group(1).strip()}
    match = WORLD_RENDER_TAG_RE.search(header)
    if match:
        return {"kind": "render", "body": match.group(1).strip()}
    if WORLD_INITIAL_TAG_RE.search(header):
        return {"kind": "initial", "body": "INITIAL"}
    return None


def is_tavern_special_world_entry(entry: dict) -> bool:
    return tavern_world_special(entry) is not None


def strip_tavern_world_controls(content: object) -> str:
    lines = str(content or "").replace("\r\n", "\n").replace("\r", "\n").split("\n")
    while lines:
        first = lines[0].strip()
        if (
            re.match(r"^@@if\s+", first, flags=re.IGNORECASE)
            or re.match(r"^@@generate_(?:before|after)\b", first, flags=re.IGNORECASE)
            or re.match(r"^@@render_(?:before|after)\b", first, flags=re.IGNORECASE)
            or re.match(r"^@@initial_variables\b", first, flags=re.IGNORECASE)
            or re.match(r"^@@(?:message_formatting|iframe|always_enabled|private|activate|dont_activate|dont_preload|only_preload|preprocessing)\b", first, flags=re.IGNORECASE)
            or re.match(r"^@INJECT\b", first, flags=re.IGNORECASE)
            or WORLD_GENERATE_TAG_RE.fullmatch(first)
            or WORLD_RENDER_TAG_RE.fullmatch(first)
            or WORLD_INITIAL_TAG_RE.fullmatch(first)
        ):
            lines.pop(0)
            continue
        break
    value = "\n".join(lines)
    value = WORLD_GENERATE_TAG_RE.sub("", value)
    value = WORLD_RENDER_TAG_RE.sub("", value)
    value = WORLD_INITIAL_TAG_RE.sub("", value)
    return value.strip()


def parse_inject_params(line: str) -> dict:
    params: dict = {}
    raw = re.sub(r"^@INJECT\b", "", str(line or ""), flags=re.IGNORECASE).strip()
    parts: list[str] = []
    buf: list[str] = []
    quote = ""
    escape = False
    for ch in raw:
        if quote:
            buf.append(ch)
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == quote:
                quote = ""
            continue
        if ch in ("'", '"'):
            quote = ch
            buf.append(ch)
            continue
        if ch in {",", " "}:
            part = "".join(buf).strip()
            if part:
                parts.append(part)
            buf = []
            continue
        buf.append(ch)
    part = "".join(buf).strip()
    if part:
        parts.append(part)
    for part in parts:
        if not part:
            continue
        if "=" in part:
            key, value = part.split("=", 1)
            params[key.strip().lower()] = value.strip().strip("'\"")
        else:
            params.setdefault("target", part.strip().strip("'\""))
    return params


def tavern_generate_injection_target(body: str) -> dict:
    text = str(body or "").strip()
    parts = [p.strip() for p in text.split(":")]
    if not parts:
        return {"target": "end"}
    head = parts[0].upper()
    if head in {"BEFORE", "START"}:
        return {"target": "start", "at": "before"}
    if head in {"AFTER", "END"}:
        return {"target": "end", "at": "after"}
    if head == "REGEX" and len(parts) >= 2:
        return {"regex": ":".join(parts[1:]), "at": "before"}
    if re.fullmatch(r"\d+", parts[0] or ""):
        target = {"index": int(parts[0]), "at": "before"}
        if len(parts) >= 2 and parts[1].upper() in {"BEFORE", "AFTER"}:
            target["at"] = parts[1].lower()
        return target
    return {"target": "end"}


def template_context_with_world(template_context: dict | None, entry: dict) -> dict | None:
    if template_context is None:
        return None
    ctx = dict(template_context) if isinstance(template_context, dict) else {}
    if isinstance(template_context, dict):
        slots = template_context.setdefault("prompt_slots", {})
        ctx["prompt_slots"] = slots if isinstance(slots, dict) else {}
    ctx["world_info"] = entry if isinstance(entry, dict) else {}
    return ctx


def collect_tavern_prompt_injections(entries: list, chat_messages: list[dict], recent_text: str, *, char_name: str = "", user_name: str = "", template_context: dict | None = None, max_chars: int = 12000) -> list[dict]:
    if not isinstance(entries, list) or not entries:
        return []
    picked: list[dict] = []
    seen: set[str] = set()
    for position in ("system", "post_history", "depth"):
        selected = select_world_info(
            entries,
            recent_text,
            char_name=char_name,
            user_name=user_name,
            position=position,
            return_entries=True,
            include_special=True,
            template_context=template_context,
        )
        for entry in selected if isinstance(selected, list) else []:
            entry_id = str(entry.get("id") or id(entry))
            if entry_id in seen or not is_tavern_special_world_entry(entry):
                continue
            seen.add(entry_id)
            picked.append(entry)
    injections: list[dict] = []
    total = 0
    for entry in picked[:40]:
        special = tavern_world_special(entry) or {}
        if special.get("kind") not in {"inject", "generate"}:
            continue
        raw_content = strip_tavern_world_controls(entry.get("content"))
        content = render_tavern_template(
            raw_content,
            char_name,
            user_name,
            template_context=template_context_with_world(template_context, entry),
            phase="generate",
            max_output=4000,
        ).strip()
        if not content:
            continue
        if total + len(content) > max_chars:
            content = content[: max(0, max_chars - total)]
        if not content:
            break
        role = "system"
        target: dict = {}
        if special.get("kind") == "inject":
            params = parse_inject_params(str(special.get("line") or ""))
            target = dict(params)
            role = str(params.get("role") or "system").strip().lower()
        else:
            target = tavern_generate_injection_target(str(special.get("body") or "AFTER"))
        if role not in {"system", "user", "assistant"}:
            role = "system"
        injections.append({"role": role, "content": content, **target})
        total += len(content)
        if total >= max_chars:
            break
    return injections


def apply_tavern_prompt_injections(chat_messages: list[dict], injections: list[dict]) -> list[dict]:
    if not injections:
        return chat_messages
    for injection in sorted(injections[:40], key=lambda item: int(item.get("order") or 0)):
        content = str(injection.get("content") or "").strip()
        if not content:
            continue
        role = str(injection.get("role") or "system").strip().lower()
        if role not in {"system", "user", "assistant"}:
            role = "system"
        index = len(chat_messages)
        at = str(injection.get("at") or "before").strip().lower()
        regex = str(injection.get("regex") or "").strip()
        if regex:
            try:
                for idx, msg in enumerate(chat_messages):
                    if re.search(regex, str(msg.get("content") or ""), flags=re.IGNORECASE | re.DOTALL):
                        index = idx + (1 if at == "after" else 0)
                        break
            except re.error as exc:
                log(f"template regex injection skipped: {exc}")
                continue
        elif "pos" in injection:
            try:
                pos = int(injection.get("pos"))
            except Exception:
                pos = len(chat_messages)
            if pos > 0:
                index = pos - 1
            elif pos < 0:
                index = len(chat_messages) + pos
            else:
                index = 0
            if at == "after":
                index += 1
        elif str(injection.get("target") or "").strip().lower() in {"system", "user", "assistant"}:
            target_role = str(injection.get("target") or "").strip().lower()
            matches = [idx for idx, msg in enumerate(chat_messages) if str(msg.get("role") or "") == target_role]
            if not matches:
                continue
            try:
                seq = int(injection.get("index") if injection.get("index") not in (None, "") else 1)
            except Exception:
                seq = 1
            if seq < 0:
                try:
                    index = matches[seq]
                except Exception:
                    index = matches[-1]
            else:
                index = matches[min(max(seq - 1, 0), len(matches) - 1)]
            if at == "after":
                index += 1
        elif "index" in injection:
            try:
                index = int(injection.get("index"))
            except Exception:
                index = len(chat_messages)
            if at == "after":
                index += 1
        else:
            target = str(injection.get("target") or "").strip().lower()
            if target in {"start", "before", "first", "0"}:
                index = 0
            elif target in {"end", "after", "last", ""}:
                index = len(chat_messages)
            if at == "before" and target in {"end", "last"}:
                index = max(0, len(chat_messages) - 1)
        index = max(0, min(index, len(chat_messages)))
        chat_messages.insert(index, {"role": role, "content": content})
    return chat_messages


def collect_tavern_render_injections(entries: list, reply: str, recent_text: str, *, char_name: str = "", user_name: str = "", template_context: dict | None = None, max_chars: int = 12000) -> list[dict]:
    if not isinstance(entries, list) or not entries:
        return []
    normalized = normalize_world_info(entries)
    picked: list[dict] = []
    for entry in normalized:
        special = tavern_world_special(entry)
        if not special or special.get("kind") != "render":
            continue
        if not (entry.get("enabled", True) and entry.get("content")):
            continue
        if not tavern_world_condition_passes(entry, char_name=char_name, user_name=user_name, template_context=template_context):
            continue
        picked.append(entry)
    picked.sort(key=lambda e: (-int(e.get("priority") or 0), int(e.get("order") or 0)))
    injections: list[dict] = []
    total = 0
    haystack = f"{recent_text or ''}\n{reply or ''}"
    for entry in picked[:40]:
        special = tavern_world_special(entry) or {}
        target = tavern_generate_injection_target(str(special.get("body") or "AFTER"))
        regex = str(target.get("regex") or "").strip()
        if regex:
            try:
                if not re.search(regex, haystack, flags=re.IGNORECASE | re.DOTALL):
                    continue
            except re.error:
                continue
        raw_content = strip_tavern_world_controls(entry.get("content"))
        content = render_tavern_template(
            raw_content,
            char_name,
            user_name,
            template_context=template_context_with_world(template_context, entry),
            phase="render",
            message={"role": "assistant", "content": reply},
            max_output=4000,
        ).strip()
        if not content:
            continue
        if total + len(content) > max_chars:
            content = content[: max(0, max_chars - total)]
        if not content:
            break
        injections.append({"content": content, **target})
        total += len(content)
        if total >= max_chars:
            break
    return injections


def apply_tavern_render_injections(reply: str, injections: list[dict]) -> str:
    value = str(reply or "")
    if not injections:
        return value
    before: list[str] = []
    after: list[str] = []
    for injection in injections[:40]:
        content = str(injection.get("content") or "").strip()
        if not content:
            continue
        target = str(injection.get("target") or "").strip().lower()
        at = str(injection.get("at") or "").strip().lower()
        if target in {"start", "before"} or at == "before":
            before.append(content)
        else:
            after.append(content)
    parts = []
    if before:
        parts.append("\n".join(before))
    if value:
        parts.append(value)
    if after:
        parts.append("\n".join(after))
    return "\n\n".join(parts)[:24000]


def apply_initial_template_variables(entries: list, template_context: dict | None, *, char_name: str = "", user_name: str = "") -> None:
    if not isinstance(template_context, dict) or not isinstance(entries, list):
        return
    normalized = normalize_world_info(entries)
    for entry in normalized[:80]:
        special = tavern_world_special(entry)
        if not special or special.get("kind") != "initial":
            continue
        if not (entry.get("enabled", True) and entry.get("content")):
            continue
        if not tavern_world_condition_passes(entry, char_name=char_name, user_name=user_name, template_context=template_context):
            continue
        rendered = render_tavern_template(
            strip_tavern_world_controls(entry.get("content")),
            char_name,
            user_name,
            template_context=template_context_with_world(template_context, entry),
            phase="generate",
            max_output=12000,
        ).strip()
        try:
            payload = json.loads(rendered)
        except Exception:
            continue
        if not isinstance(payload, dict):
            continue
        env = build_template_env(template_context, char_name=char_name, user_name=user_name, phase="generate")
        setter = env.get("setvar")
        if not callable(setter):
            continue
        for key, value in list(payload.items())[:80]:
            clean_key = str(key or "").strip()
            if clean_key:
                setter(clean_key, value, {"scope": "conversation", "flags": "nx"})


SILLY_GREETING_HEADING_RE = re.compile(
    r"(?im)^[ \t]{0,3}#{2,4}[ \t]+"
    r"(?P<label>"
    r"(?:[UPH][ \t]*[-_.]?[ \t]*\d{1,3}(?!\d))"
    r"|(?:开(?:场|头|局)|问候|开场白)[ \t]*(?:[:：#-]?[ \t]*)?(?:\d{1,3}|[一二三四五六七八九十]+)"
    r"|(?:opening|greeting|starter|scene)[ \t]*(?:[:：#-]?[ \t]*)?\d{1,3}"
    r")[^\n\r]*$"
)

IMPORTED_OPENING_PREFACE_MARKER = "【导入自 first_mes 的开场说明】"
VISUAL_OPENING_PREFACE_RE = re.compile(
    r"(?im)^[ \t]{0,3}#[ \t]*(?:游玩说明|玩法说明|使用说明|开局说明|说明)\b"
)


def _dedupe_text_key(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip().lower()


def is_visual_opening_preface(value: object) -> bool:
    text = str(value or "").replace("\r\n", "\n").replace("\r", "\n").strip()
    return bool(text and VISUAL_OPENING_PREFACE_RE.search(text))


def imported_opening_preface_from_notes(creator_notes: object) -> str:
    text = str(creator_notes or "").replace("\r\n", "\n").replace("\r", "\n")
    if IMPORTED_OPENING_PREFACE_MARKER in text:
        text = text.split(IMPORTED_OPENING_PREFACE_MARKER, 1)[1]
    match = VISUAL_OPENING_PREFACE_RE.search(text)
    return text[match.start():].strip() if match else ""


def split_silly_first_mes_greetings(first_mes: object) -> dict:
    """Split packed SillyTavern first_mes sections into first + alternate greetings.

    Some cards pack multiple markdown scene openings such as "## U1"..."## U4"
    into first_mes instead of using alternate_greetings. SillyTavern's chat model
    expects those to behave like swipes, so we conservatively split only headings
    that look like numbered greetings/openings and require at least two sections.
    """
    text = str(first_mes or "").replace("\r\n", "\n").replace("\r", "\n").strip()
    if not text:
        return {"primary": "", "alternates": [], "preface": ""}
    matches = list(SILLY_GREETING_HEADING_RE.finditer(text))
    if len(matches) < 2:
        return {"primary": text, "alternates": [], "preface": ""}

    sections: list[str] = []
    for idx, match in enumerate(matches):
        start = match.start()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(text)
        section = text[start:end].strip()
        if section:
            sections.append(section)
    if len(sections) < 2:
        return {"primary": text, "alternates": [], "preface": ""}

    preface = text[:matches[0].start()].strip()
    visual_preface = preface if is_visual_opening_preface(preface) else ""
    primary = text if visual_preface else sections[0]
    alternates: list[str] = []
    seen = {_dedupe_text_key(primary)}
    section_source = sections if visual_preface else sections[1:20]
    for section in section_source:
        key = _dedupe_text_key(section)
        if key and key not in seen:
            seen.add(key)
            alternates.append(section)
    if not alternates:
        return {"primary": text, "alternates": [], "preface": ""}
    return {"primary": primary, "alternates": alternates, "preface": "" if visual_preface else preface}


def merge_alternate_greetings(primary: object, *groups: object) -> list[str]:
    seen = {_dedupe_text_key(primary)}
    out: list[str] = []
    for group in groups:
        if isinstance(group, str):
            values = [group]
        elif isinstance(group, list):
            values = group
        else:
            continue
        for value in values:
            text = str(value or "").strip()
            key = _dedupe_text_key(text)
            if text and key and key not in seen:
                seen.add(key)
                out.append(text)
    return out[:20]


def append_imported_opening_preface(creator_notes: str, preface: str) -> str:
    clean_notes = str(creator_notes or "").strip()
    clean_preface = str(preface or "").strip()
    if not clean_preface:
        return clean_notes
    if IMPORTED_OPENING_PREFACE_MARKER in clean_notes:
        return clean_notes
    merged = f"{clean_notes}\n\n{IMPORTED_OPENING_PREFACE_MARKER}\n{clean_preface}".strip() if clean_notes else f"{IMPORTED_OPENING_PREFACE_MARKER}\n{clean_preface}"
    return merged[:4000]


def chat_greetings_from_card(card: dict, char_name: str = "", user_name: str = "", *, template_context: dict | None = None) -> list[str]:
    primary_raw = str((card or {}).get("opening_statement") or "").strip()
    split = split_silly_first_mes_greetings(primary_raw)
    imported_preface = imported_opening_preface_from_notes((card or {}).get("creator_notes"))
    if imported_preface:
        alternates = merge_alternate_greetings(
            imported_preface,
            [primary_raw] if primary_raw else [],
            split.get("alternates") or [],
            (card or {}).get("alternate_greetings") or [],
        )
        primary = "\n\n".join([imported_preface] + alternates).strip()
    else:
        primary = str(split.get("primary") or primary_raw).strip()
        alternates = merge_alternate_greetings(
            primary,
            split.get("alternates") or [],
            (card or {}).get("alternate_greetings") or [],
        )
    greetings: list[str] = []
    for value in ([primary] if primary else []) + alternates:
        text = render_tavern_template(
            str(value or "").strip(),
            char_name,
            user_name,
            template_context=template_context,
            phase="generate",
        )
        text = apply_regex_scripts(text, card or {})
        key = _dedupe_text_key(text)
        if text and key and key not in {_dedupe_text_key(g) for g in greetings}:
            greetings.append(text)
    return greetings[:20]


def local_app_feature_flags(row: dict, extra: dict | None = None) -> dict[str, bool]:
    """Return lightweight, UI-facing feature flags for one role card.

    Imported human annotations are authoritative. New/unannotated cards fall
    back to their top-level card fields; the regex flag intentionally follows
    the visible `extra_settings.regex_scripts` annotation convention rather
    than nested TavernHelper extension scripts.
    """
    annotated_keys = ("has_opening", "has_world_info", "has_regex")
    if all(key in row and row.get(key) is not None for key in annotated_keys):
        return {
            "opening": bool(row.get("has_opening")),
            "world_info": bool(row.get("has_world_info")),
            "regex": bool(row.get("has_regex")),
        }
    if extra is None:
        raw_extra = row.get("extra_settings")
        if isinstance(raw_extra, dict):
            extra = raw_extra
        else:
            try:
                extra = json.loads(raw_extra) if raw_extra else {}
            except Exception:
                extra = {}
    if not isinstance(extra, dict):
        extra = {}
    world_info = extra.get("world_info")
    regex_scripts = extra.get("regex_scripts")
    return {
        "opening": bool(str(row.get("opening_statement") or "").strip()),
        "world_info": bool(world_info) if isinstance(world_info, (list, dict)) else bool(str(world_info or "").strip()),
        "regex": bool(regex_scripts) if isinstance(regex_scripts, (list, dict)) else bool(str(regex_scripts or "").strip()),
    }


def local_app_to_card(row: dict) -> dict:
    """把 local_apps 行转成 explore/详情 期望的角色卡格式。"""
    def _json(v, default):
        if not v:
            return default
        try:
            return json.loads(v)
        except Exception:
            return default
    extra = _json(row.get("extra_settings"), {}) or {}
    if not isinstance(extra, dict):
        extra = {}
    sampling = extra.get("sampling") if isinstance(extra.get("sampling"), dict) else {}
    alt_greet = extra.get("alternate_greetings")
    if not isinstance(alt_greet, list):
        alt_greet = []
    world_info = ensure_required_world_info(extra.get("world_info") or [])
    prompt_blocks = extra.get("prompt_blocks")
    if not isinstance(prompt_blocks, list):
        prompt_blocks = []
    quick_replies = extra.get("quick_replies")
    if not isinstance(quick_replies, list):
        quick_replies = []
    regex_scripts = extra.get("regex_scripts")
    if not isinstance(regex_scripts, list):
        regex_scripts = []
    feature_flags = local_app_feature_flags(row, extra)
    return {
        "id": row["id"],
        "display_id": row.get("display_id") or "",
        "card_no": row.get("display_id") or "",
        "short_id": row.get("display_id") or "",
        "name": row.get("name") or "",
        "summary": row.get("summary") or "",
        "description": row.get("description") or "",
        "cover": row.get("cover_url") or "",
        "cover_url": row.get("cover_url") or "",
        "cover_tiny": "",
        "icon": row.get("cover_url") or "",
        "tags": _json(row.get("tags"), []),
        "opening_statement": row.get("opening_statement") or "",
        "suggested_questions": _json(row.get("suggested_questions"), []),
        "pre_prompt": row.get("pre_prompt") or "",
        "llm_model": row.get("llm_model") or "",
        "age_rating": row.get("age_rating") or 0,
        "gender": row.get("gender") or 0,
        "language": row.get("language") or "zh-Hans",
        "players_count": row.get("players_count") or 0,
        "like_count": row.get("like_count") or 0,
        "source": row.get("source") or "upstream",
        "status": row.get("status") or "published",
        "is_public": bool(row.get("is_public", 1)),
        "sort_weight": row.get("sort_weight") or 0,
        "is_original": (row.get("source") in ("user", "admin")),
        "account_name": "原创作者" if row.get("source") == "user" else "惑梦（Homer）",
        "api_base_url": row.get("api_base_url") or "",
        "bg_url": str(extra.get("bg_url") or ""),
        "tts_voice_id": str(extra.get("tts_voice_id") or ""),
        "nsfw": bool(extra.get("nsfw")),
        "protected_prompt": bool(extra.get("protected_prompt") or extra.get("protected")),
        "anonymous": bool(extra.get("anonymous")),
        "personality": str(extra.get("personality") or ""),
        "scenario": str(extra.get("scenario") or ""),
        "mes_example": str(extra.get("mes_example") or ""),
        "post_history_instructions": str(extra.get("post_history_instructions") or ""),
        "alternate_greetings": [str(g) for g in alt_greet if isinstance(g, str) and g.strip()],
        "world_info": world_info,
        "prompt_blocks": prompt_blocks,
        "quick_replies": quick_replies,
        "regex_scripts": regex_scripts,
        "has_opening": feature_flags["opening"],
        "has_world_info": feature_flags["world_info"],
        "has_regex": feature_flags["regex"],
        "feature_flags": feature_flags,
        "creator_notes": str(extra.get("creator_notes") or ""),
        "creator": str(extra.get("creator") or ""),
        "character_version": str(extra.get("character_version") or ""),
        "extensions": extra.get("extensions") if isinstance(extra.get("extensions"), dict) else {},
        "sampling": {
            "temperature": float(sampling.get("temperature")) if sampling.get("temperature") not in (None, "") else None,
            "top_p": float(sampling.get("top_p")) if sampling.get("top_p") not in (None, "") else None,
            "presence_penalty": float(sampling.get("presence_penalty")) if sampling.get("presence_penalty") not in (None, "") else None,
            "frequency_penalty": float(sampling.get("frequency_penalty")) if sampling.get("frequency_penalty") not in (None, "") else None,
            "history_length": int(sampling.get("history_length")) if str(sampling.get("history_length") or "").strip().isdigit() else None,
        },
    }


def local_app_to_list_card(row: dict) -> dict:
    """Lightweight role-card shape for Home/Explore lists.

    Full character cards can carry huge world books, regex scripts, examples, and
    extensions. Sending those on the first Home page makes the content load feel
    slow over public networks, while the list UI only needs summary fields.
    """
    def _json(v, default):
        if not v:
            return default
        try:
            parsed = json.loads(v)
            return parsed if isinstance(parsed, type(default)) else default
        except Exception:
            return default
    def _trim(value, limit: int = 220) -> str:
        text = re.sub(r"\s+", " ", str(value or "")).strip()
        if len(text) <= limit:
            return text
        return text[:limit].rstrip() + "..."

    source = row.get("source") or "upstream"
    cover = row.get("cover_url") or ""
    tags = [str(t).strip() for t in _json(row.get("tags"), []) if str(t).strip()]
    feature_flags = local_app_feature_flags(row)
    return {
        "id": row.get("id") or "",
        "display_id": row.get("display_id") or "",
        "card_no": row.get("display_id") or "",
        "short_id": row.get("display_id") or "",
        "name": _trim(row.get("name"), 80),
        "summary": _trim(row.get("summary"), 220),
        "description": _trim(row.get("description"), 260),
        "cover": cover,
        "cover_url": cover,
        "cover_tiny": "",
        "icon": cover,
        "tags": tags[:6],
        "has_opening": feature_flags["opening"],
        "has_world_info": feature_flags["world_info"],
        "has_regex": feature_flags["regex"],
        "feature_flags": feature_flags,
        "age_rating": row.get("age_rating") or 0,
        "gender": row.get("gender") or 0,
        "language": row.get("language") or "zh-Hans",
        "players_count": row.get("players_count") or 0,
        "like_count": row.get("like_count") or 0,
        "source": source,
        "status": row.get("status") or "published",
        "is_public": bool(row.get("is_public", 1)),
        "sort_weight": row.get("sort_weight") or 0,
        "is_original": source in ("user", "admin"),
        "account_name": "原创作者" if source == "user" else "惑梦（Homer）",
        "created_at": row.get("created_at") or 0,
        "updated_at": row.get("updated_at") or 0,
    }


def _safe_float(value, lo=None, hi=None):
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    if lo is not None and f < lo: f = lo
    if hi is not None and f > hi: f = hi
    return f


def _safe_int(value, lo=None, hi=None):
    try:
        n = int(value)
    except (TypeError, ValueError):
        return None
    if lo is not None and n < lo: n = lo
    if hi is not None and n > hi: n = hi
    return n


def silly_card_to_app(card: dict) -> dict:
    """SillyTavern Character Card (V1/V2) → 本站 create_user_app 期望的 payload。"""
    if not isinstance(card, dict):
        raise ValueError("角色卡必须是对象")
    data = card.get("data") if isinstance(card.get("data"), dict) else card
    if not isinstance(data, dict):
        data = card

    def _s(*keys):
        for k in keys:
            v = data.get(k)
            if isinstance(v, str) and v.strip():
                return v.strip()
        return ""

    name = _s("name", "char_name") or "导入角色"
    tags = data.get("tags")
    if isinstance(tags, str):
        tags = [t.strip() for t in re.split(r"[，,\n]", tags) if t.strip()]
    if not isinstance(tags, list):
        tags = []
    alt = data.get("alternate_greetings")
    if not isinstance(alt, list):
        alt = []
    raw_first_mes = _s("first_mes", "greeting", "first_message")
    split_first_mes = split_silly_first_mes_greetings(raw_first_mes)
    opening_statement = str(split_first_mes.get("primary") or raw_first_mes).strip()
    alternate_greetings = merge_alternate_greetings(
        opening_statement,
        split_first_mes.get("alternates") or [],
        [str(g).strip() for g in alt if str(g).strip()],
    )
    creator_notes = append_imported_opening_preface(_s("creator_notes"), str(split_first_mes.get("preface") or ""))
    # character_book → world_info
    world = []
    book = data.get("character_book")
    if isinstance(book, dict) and isinstance(book.get("entries"), list):
        for e in book["entries"]:
            if not isinstance(e, dict):
                continue
            world.append({
                "keys": e.get("keys") or e.get("key") or [],
                "secondary_keys": e.get("secondary_keys") or e.get("keys_secondary") or e.get("keysecondary") or [],
                "content": e.get("content") or "",
                "enabled": (not e.get("disable", False)) if "disable" in e else bool(e.get("enabled", True)),
                "constant": bool(e.get("constant", False)),
                "selective": bool(e.get("selective", False)),
                "position": e.get("position") or "system",
                "depth": e.get("depth", 4),
                "priority": e.get("priority", e.get("insertion_order", 100)),
                "order": e.get("order", e.get("insertion_order", 100)),
                "probability": e.get("probability", 100),
                "recursive": bool(e.get("recursive", e.get("case_sensitive", False))),
            })
    payload = {
        "name": name[:120],
        "description": _s("description", "personality_summary"),
        "summary": (creator_notes or _s("description") or "")[:180],
        "personality": _s("personality"),
        "scenario": _s("scenario"),
        "opening_statement": opening_statement,
        "mes_example": _s("mes_example", "example_dialogue"),
        "pre_prompt": _s("system_prompt"),
        "post_history_instructions": _s("post_history_instructions"),
        "alternate_greetings": alternate_greetings,
        "world_info": normalize_world_info(world),
        "creator_notes": creator_notes,
        "creator": _s("creator"),
        "character_version": _s("character_version"),
        "extensions": data.get("extensions") if isinstance(data.get("extensions"), dict) else {},
        "tags": tags,
        "is_public": False,
    }
    promoted_regex = regex_scripts_from_extensions(payload.get("extensions"))
    if promoted_regex:
        payload["regex_scripts"] = promoted_regex
    avatar = _s("avatar", "image", "cover_url")
    if avatar and avatar.lower() not in ("none",) and (avatar.startswith("http") or avatar.startswith("/")):
        payload["cover_url"] = avatar
    return payload


def app_to_silly_card(card: dict) -> dict:
    """本站角色卡（local_app_to_card 输出）→ SillyTavern Character Card V2。"""
    entries = []
    for e in (card.get("world_info") or []):
        if not isinstance(e, dict):
            continue
        entries.append({
            "keys": e.get("keys") or [],
            "secondary_keys": e.get("secondary_keys") or [],
            "keys_secondary": e.get("secondary_keys") or [],
            "content": e.get("content") or "",
            "enabled": bool(e.get("enabled", True)),
            "disable": not bool(e.get("enabled", True)),
            "constant": bool(e.get("constant", False)),
            "selective": bool(e.get("selective", False)),
            "position": e.get("position") or "system",
            "depth": int(e.get("depth") or 4),
            "priority": int(e.get("priority") or 100),
            "insertion_order": int(e.get("order") or e.get("priority") or 100),
            "probability": int(e.get("probability") if e.get("probability") is not None else 100),
            "recursive": bool(e.get("recursive", False)),
        })
    data = {
        "name": card.get("name") or "",
        "description": card.get("description") or "",
        "personality": card.get("personality") or "",
        "scenario": card.get("scenario") or "",
        "first_mes": card.get("opening_statement") or "",
        "mes_example": card.get("mes_example") or "",
        "system_prompt": card.get("pre_prompt") or "",
        "post_history_instructions": card.get("post_history_instructions") or "",
        "alternate_greetings": card.get("alternate_greetings") or [],
        "tags": card.get("tags") or [],
        "creator_notes": card.get("creator_notes") or "",
        "creator": card.get("creator") or "",
        "character_version": card.get("character_version") or "",
        "avatar": card.get("cover_url") or card.get("cover") or "",
        "extensions": card.get("extensions") if isinstance(card.get("extensions"), dict) else {},
    }
    if entries:
        data["character_book"] = {"name": (card.get("name") or "lore"), "entries": entries}
    return {"spec": "chara_card_v2", "spec_version": "2.0", "data": data}


def normalize_world_info(value: object) -> list:
    """规整世界书条目列表，兼容基础条目和 SillyTavern Character Book 常用字段。"""
    if not isinstance(value, list):
        return []
    allowed_positions = {
        "system": "system",
        "system_after": "system",
        "after_char": "system",
        "post_history": "post_history",
        "depth": "depth",
        "at_depth": "depth",
    }

    def _keys(raw_value) -> list[str]:
        if isinstance(raw_value, str):
            raw_value = re.split(r"[，,\n]", raw_value)
        keys: list[str] = []
        if isinstance(raw_value, list):
            for k in raw_value:
                s = str(k or "").strip()
                if s:
                    keys.append(s[:80])
        return keys[:30]

    def _int(value, default, lo, hi):
        try:
            n = int(value)
        except Exception:
            n = default
        return max(lo, min(hi, n))

    out = []
    for idx, raw in enumerate(value[:200]):
        if not isinstance(raw, dict):
            continue
        keys_in = raw.get("keys", raw.get("key"))
        secondary_in = raw.get("secondary_keys", raw.get("keys_secondary", raw.get("keysecondary", raw.get("secondary", []))))
        position = str(raw.get("position") or raw.get("insertion_position") or "system").strip()
        position = allowed_positions.get(position, "system")
        content = str(raw.get("content") or raw.get("entry") or "").strip()[:8000]
        if not content:
            continue
        priority_value = raw.get("priority", raw.get("insertion_order", raw.get("order", 100)))
        out.append({
            "id": str(raw.get("id") or f"world-{idx + 1}")[:80],
            "name": str(raw.get("name") or raw.get("title") or raw.get("comment") or f"世界书条目 {idx + 1}")[:80],
            "keys": _keys(keys_in),
            "secondary_keys": _keys(secondary_in),
            "content": content,
            "enabled": (not bool(raw.get("disable"))) if "disable" in raw else bool(raw.get("enabled", True)),
            "constant": bool(raw.get("constant", False)),
            "selective": bool(raw.get("selective", False)),
            "position": position,
            "depth": _int(raw.get("depth"), 4, 0, 20),
            "priority": _int(priority_value, 100, -10000, 10000),
            "order": _int(raw.get("order", raw.get("insertion_order", idx + 1)), idx + 1, -10000, 10000),
            "probability": _int(raw.get("probability"), 100, 0, 100),
            "recursive": bool(raw.get("recursive", False)),
            "case_sensitive": bool(raw.get("case_sensitive", False)),
            "match_whole_words": bool(raw.get("match_whole_words", raw.get("match_whole_word", False))),
            "selective_logic": str(raw.get("selective_logic") or raw.get("secondary_logic") or "and_any")[:20],
            "role": str(raw.get("role") or "system")[:20],
            "scan_depth": _int(raw.get("scan_depth"), 2, 0, 100),
            "sticky": _int(raw.get("sticky"), 0, 0, 9999),
            "cooldown": _int(raw.get("cooldown"), 0, 0, 9999),
            "delay": _int(raw.get("delay"), 0, 0, 9999),
        })
    return out


REQUIRED_WORLD_BOOK_ID = "tavo-anti-scrape-v2"


def required_world_info_entry() -> dict | None:
    """Load the site-required Tavo lorebook entry without embedding it in user cards' source code."""
    configured = str(os.environ.get("REQUIRED_WORLD_BOOK_PATH") or "").strip()
    path = Path(configured) if configured else (Path(__file__).resolve().parent / "data" / "tavo_anti_scrape_worldbook.json")
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    entries = raw.get("entries") if isinstance(raw, dict) else None
    if isinstance(entries, dict):
        def sort_key(item):
            key, value = item
            try: numeric = int(key)
            except Exception: numeric = 999999
            return (int((value or {}).get("display_index") or (value or {}).get("order") or numeric), numeric)
        entries = [value for _, value in sorted(entries.items(), key=sort_key)]
    elif not isinstance(entries, list):
        entries = raw.get("world_info") if isinstance(raw, dict) else None
    normalized = normalize_world_info(entries if isinstance(entries, list) else [])
    if not normalized:
        return None
    entry = dict(normalized[0])
    entry.update({
        "id": REQUIRED_WORLD_BOOK_ID,
        "name": str(entry.get("name") or "反扒卡"),
        "enabled": True,
        "constant": True,
        "position": "system",
        "priority": 10000,
        "order": -10000,
        "probability": 100,
    })
    return entry


def ensure_required_world_info(entries: object) -> list:
    normalized = normalize_world_info(entries if isinstance(entries, list) else [])
    required = required_world_info_entry()
    if not required:
        return normalized
    content = str(required.get("content") or "").strip()
    remaining = [
        entry for entry in normalized
        if str(entry.get("id") or "") != REQUIRED_WORLD_BOOK_ID
        and not (str(entry.get("name") or "").strip() == "反扒卡" and str(entry.get("content") or "").strip() == content)
    ]
    return [required, *remaining[:199]]


def normalize_prompt_blocks(value: object) -> list:
    """规整 Prompt Manager 块列表。"""
    if not isinstance(value, list):
        return []
    out = []
    allowed_positions = {"system_before", "system_after", "post_history"}
    for idx, raw in enumerate(value[:40]):
        if not isinstance(raw, dict):
            continue
        content = str(raw.get("content") or "").strip()[:12000]
        if not content:
            continue
        position = str(raw.get("position") or "system_after").strip()
        if position not in allowed_positions:
            position = "system_after"
        try:
            order = int(raw.get("order") if raw.get("order") is not None else idx + 1)
        except Exception:
            order = idx + 1
        out.append({
            "id": str(raw.get("id") or f"prompt-{idx + 1}")[:80],
            "name": str(raw.get("name") or f"提示词块 {idx + 1}")[:80],
            "position": position,
            "order": max(0, min(order, 9999)),
            "enabled": bool(raw.get("enabled", True)),
            "content": content,
        })
    out.sort(key=lambda item: (item.get("order", 0), item.get("name", "")))
    return out


def normalize_global_prompt_blocks(value: object) -> list:
    """Normalize site-wide Prompt Preset blocks saved by admins."""
    if not isinstance(value, list):
        return []
    allowed_positions = {"system_before", "system_after", "post_history"}
    allowed_roles = {"system", "user", "assistant"}
    out: list[dict] = []
    seen_ids: set[str] = set()
    for idx, raw in enumerate(value[:160]):
        if not isinstance(raw, dict):
            continue
        content = str(raw.get("content") or "").strip()[:16000]
        if not content:
            continue
        block_id = str(raw.get("id") or raw.get("identifier") or f"global-prompt-{idx + 1}")[:120]
        block_id = re.sub(r"[^A-Za-z0-9_.:-]+", "-", block_id).strip("-") or f"global-prompt-{idx + 1}"
        if block_id in seen_ids:
            block_id = f"{block_id}-{idx + 1}"
        seen_ids.add(block_id)
        position = str(raw.get("position") or "system_before").strip()
        if position not in allowed_positions:
            position = "system_before"
        role = str(raw.get("role") or "system").strip().lower()
        if role not in allowed_roles:
            role = "system"
        try:
            order = int(raw.get("order") if raw.get("order") is not None else idx + 1)
        except Exception:
            order = idx + 1
        out.append({
            "id": block_id,
            "name": str(raw.get("name") or f"全局提示词 {idx + 1}")[:120],
            "position": position,
            "role": role,
            "order": max(0, min(order, 9999)),
            "enabled": raw.get("enabled", True) is not False and str(raw.get("enabled", "true")).strip().lower() not in ("0", "false", "no", "off", "disabled"),
            "content": content,
        })
    out.sort(key=lambda item: (item.get("position", ""), item.get("order", 0), item.get("name", "")))
    return out


def normalize_sillytavern_prompt_preset(value: dict) -> dict:
    prompts = value.get("prompts") if isinstance(value.get("prompts"), list) else []
    prompt_by_id = {
        str(item.get("identifier") or item.get("id") or ""): item
        for item in prompts
        if isinstance(item, dict)
    }
    order_items = []
    prompt_order = value.get("prompt_order")
    if isinstance(prompt_order, list) and prompt_order:
        first = prompt_order[0]
        if isinstance(first, dict) and isinstance(first.get("order"), list):
            order_items = first.get("order") or []
    if not order_items:
        order_items = [
            {
                "identifier": item.get("identifier") or item.get("id"),
                "enabled": item.get("enabled", True),
            }
            for item in prompts
            if isinstance(item, dict)
        ]

    seen_chat_history = False
    blocks: list[dict] = []
    marker_count = 0
    enabled_count = 0
    for idx, item in enumerate(order_items):
        if not isinstance(item, dict):
            continue
        ident = str(item.get("identifier") or item.get("id") or "").strip()
        if not ident:
            continue
        prompt = prompt_by_id.get(ident, {})
        enabled = item.get("enabled", prompt.get("enabled", True))
        if enabled is False or str(enabled).strip().lower() in ("0", "false", "no", "off", "disabled"):
            continue
        enabled_count += 1
        content = str(prompt.get("content") or "").strip()
        is_marker = bool(prompt.get("marker")) or (not content and bool(prompt.get("system_prompt")))
        if ident == "chatHistory":
            seen_chat_history = True
        if is_marker or not content:
            marker_count += 1
            continue
        blocks.append({
            "id": ident,
            "name": str(prompt.get("name") or ident),
            "position": "post_history" if seen_chat_history else "system_before",
            "role": str(prompt.get("role") or "system").strip().lower() or "system",
            "order": len(blocks) + 1,
            "enabled": True,
            "content": content,
        })

    name = str(value.get("name") or value.get("preset_name") or value.get("display_name") or "SillyTavern 全局预设").strip()
    return {
        "enabled": True,
        "name": name[:120],
        "source": "sillytavern",
        "blocks": normalize_global_prompt_blocks(blocks),
        "stats": {
            "source_prompt_count": len(prompts),
            "enabled_prompt_count": enabled_count,
            "marker_count": marker_count,
            "block_count": len(blocks),
        },
    }


def normalize_global_prompt_preset(value: object) -> dict:
    default = {
        "enabled": False,
        "name": "全局提示词预设",
        "source": "manual",
        "blocks": [],
        "stats": {"block_count": 0, "system_before": 0, "system_after": 0, "post_history": 0},
    }
    if isinstance(value, str):
        raw = value.strip()
        if not raw:
            return default
        try:
            value = json.loads(raw)
        except Exception:
            return default
    if not isinstance(value, dict):
        return default
    if isinstance(value.get("prompts"), list):
        parsed = normalize_sillytavern_prompt_preset(value)
    else:
        raw_blocks = value.get("blocks")
        if raw_blocks is None:
            raw_blocks = []
            for position in ("system_before", "system_after", "post_history"):
                items = value.get(position)
                if isinstance(items, list):
                    for item in items:
                        if isinstance(item, dict):
                            merged = dict(item)
                            merged["position"] = position
                            raw_blocks.append(merged)
        parsed = {
            "enabled": value.get("enabled", False) is not False and str(value.get("enabled", "false")).strip().lower() in ("1", "true", "yes", "on", "enabled", "启用", "是"),
            "name": str(value.get("name") or "全局提示词预设").strip()[:120],
            "source": str(value.get("source") or "manual").strip()[:40],
            "blocks": normalize_global_prompt_blocks(raw_blocks),
            "stats": dict(value.get("stats") or {}) if isinstance(value.get("stats"), dict) else {},
        }
    blocks = normalize_global_prompt_blocks(parsed.get("blocks") or [])
    stats = dict(parsed.get("stats") or {})
    stats.update({
        "block_count": len(blocks),
        "system_before": sum(1 for block in blocks if block.get("position") == "system_before"),
        "system_after": sum(1 for block in blocks if block.get("position") == "system_after"),
        "post_history": sum(1 for block in blocks if block.get("position") == "post_history"),
        "enabled_block_count": sum(1 for block in blocks if block.get("enabled", True)),
    })
    return {
        "enabled": bool(parsed.get("enabled")),
        "name": str(parsed.get("name") or "全局提示词预设").strip()[:120],
        "source": str(parsed.get("source") or "manual").strip()[:40],
        "blocks": blocks,
        "stats": stats,
    }


def normalize_quick_replies(value: object) -> list:
    if not isinstance(value, list):
        return []
    out = []
    for idx, raw in enumerate(value[:40]):
        if isinstance(raw, str):
            raw = {"label": raw[:40], "message": raw}
        if not isinstance(raw, dict):
            continue
        message = str(raw.get("message") or raw.get("content") or "").strip()[:2000]
        if not message:
            continue
        label = str(raw.get("label") or raw.get("name") or message[:24]).strip()[:60]
        try:
            order = int(raw.get("order") if raw.get("order") is not None else idx + 1)
        except Exception:
            order = idx + 1
        out.append({
            "id": str(raw.get("id") or f"quick-{idx + 1}")[:80],
            "label": label or f"快捷回复 {idx + 1}",
            "message": message,
            "enabled": bool(raw.get("enabled", True)),
            "order": max(0, min(order, 9999)),
        })
    out.sort(key=lambda item: (item.get("order", 0), item.get("label", "")))
    return out


def split_silly_regex_pattern(value: object) -> tuple[str, str]:
    text = str(value or "").strip()
    if len(text) >= 2 and text.startswith("/"):
        escaped = False
        for idx in range(len(text) - 1, 0, -1):
            ch = text[idx]
            if ch == "/" and not escaped:
                pattern = text[1:idx]
                flags = text[idx + 1:]
                return pattern.replace("\\/", "/"), flags
            escaped = (ch == "\\" and not escaped)
            if ch != "\\":
                escaped = False
    return text, ""


REGEX_REPLACE_MAX_CHARS = 240000


def normalize_regex_scripts(value: object) -> list:
    if not isinstance(value, list):
        return []
    out = []
    for idx, raw in enumerate(value[:40]):
        if not isinstance(raw, dict):
            continue
        find, inline_flags = split_silly_regex_pattern(raw.get("find") or raw.get("pattern") or raw.get("findRegex") or raw.get("regex") or "")
        find = str(find or "").strip()
        if not find:
            continue
        replace = str(raw.get("replace") or raw.get("replacement") or raw.get("replaceString") or "")
        flags = str(raw.get("flags") or inline_flags or "").lower()
        try:
            order = int(raw.get("order") if raw.get("order") is not None else idx + 1)
        except Exception:
            order = idx + 1
        enabled = bool(raw.get("enabled", True))
        if "disabled" in raw:
            enabled = not bool(raw.get("disabled"))
        out.append({
            "id": str(raw.get("id") or f"regex-{idx + 1}")[:80],
            "name": str(raw.get("name") or raw.get("scriptName") or f"Regex {idx + 1}")[:80],
            "find": find[:1000],
            "replace": replace[:REGEX_REPLACE_MAX_CHARS],
            "flags": "".join(ch for ch in flags if ch in "ims")[:3],
            "enabled": enabled,
            "order": max(0, min(order, 9999)),
        })
    out.sort(key=lambda item: (item.get("order", 0), item.get("name", "")))
    return out


def regex_scripts_from_extensions(extensions: object) -> list:
    if not isinstance(extensions, dict):
        return []
    raw_items: list = []
    for key in ("regex_scripts", "TavernHelper_scripts", "tavern_helper_scripts"):
        value = extensions.get(key)
        if isinstance(value, list):
            raw_items.extend(value)
    return normalize_regex_scripts(raw_items)


def normalize_user_app_extras(data: dict) -> dict:
    """从前端 payload 中抽取扩展字段。返回 JSON 可序列化 dict 或 None（表示无覆盖）。"""
    if not isinstance(data, dict):
        return {}
    extras: dict = {}
    if "bg_url" in data:
        extras["bg_url"] = str(data.get("bg_url") or "").strip()
    if "tts_voice_id" in data:
        voice_id = str(data.get("tts_voice_id") or "").strip()
        allowed_voices = {str(item.get("id") or "") for item in TTS_VOICES}
        extras["tts_voice_id"] = voice_id if voice_id in allowed_voices else TTS_VOICES[0]["id"]
    for key in ("nsfw", "anonymous"):
        if key in data:
            extras[key] = bool(data.get(key))
    if "protected" in data or "protected_prompt" in data:
        extras["protected_prompt"] = bool(data.get("protected_prompt") or data.get("protected"))
    # SillyTavern-style rich character fields (free text, length-clamped)
    for key, limit in (
        ("personality", 6000),
        ("scenario", 6000),
        ("mes_example", 12000),
        ("post_history_instructions", 6000),
        ("creator_notes", 4000),
        ("creator", 120),
        ("character_version", 60),
    ):
        if key in data:
            extras[key] = str(data.get(key) or "").strip()[:limit]
    if isinstance(data.get("extensions"), dict):
        raw_extensions = json.dumps(data.get("extensions") or {}, ensure_ascii=False, separators=(",", ":"))
        if len(raw_extensions) <= 50000:
            extras["extensions"] = json.loads(raw_extensions)
            if "regex_scripts" not in data:
                promoted = regex_scripts_from_extensions(extras["extensions"])
                if promoted:
                    extras["regex_scripts"] = promoted
    if "alternate_greetings" in data:
        raw = data.get("alternate_greetings")
        if isinstance(raw, str):
            raw = [raw]
        greetings = []
        if isinstance(raw, list):
            for g in raw[:20]:
                s = str(g or "").strip()
                if s:
                    greetings.append(s[:8000])
        extras["alternate_greetings"] = greetings
    extras["world_info"] = ensure_required_world_info(data.get("world_info") if "world_info" in data else [])
    if "prompt_blocks" in data:
        extras["prompt_blocks"] = normalize_prompt_blocks(data.get("prompt_blocks"))
    if "quick_replies" in data:
        extras["quick_replies"] = normalize_quick_replies(data.get("quick_replies"))
    if "regex_scripts" in data:
        extras["regex_scripts"] = normalize_regex_scripts(data.get("regex_scripts"))
    elif "TavernHelper_scripts" in data:
        extras["regex_scripts"] = normalize_regex_scripts(data.get("TavernHelper_scripts"))
    sampling_in = data.get("sampling") if isinstance(data.get("sampling"), dict) else None
    if sampling_in:
        sampling: dict = {}
        t = _safe_float(sampling_in.get("temperature"), 0.0, 2.0)
        if t is not None: sampling["temperature"] = t
        tp = _safe_float(sampling_in.get("top_p"), 0.0, 1.0)
        if tp is not None: sampling["top_p"] = tp
        pp = _safe_float(sampling_in.get("presence_penalty"), -2.0, 2.0)
        if pp is not None: sampling["presence_penalty"] = pp
        fp = _safe_float(sampling_in.get("frequency_penalty"), -2.0, 2.0)
        if fp is not None: sampling["frequency_penalty"] = fp
        hl = _safe_int(sampling_in.get("history_length"), 0, 200)
        if hl is not None: sampling["history_length"] = hl
        if sampling:
            extras["sampling"] = sampling
    return extras


_CHAT_REPLY_PHRASES = [
    "{role}轻声回应：「{q}」我也在想这个呢…",
    "{role}笑了笑：「{q}」其实我一直想告诉你——",
    "{role}抬眼看你：你说「{q}」的时候，我有点想抱抱你。",
    "「{q}」？{role}托着腮，眼神里有点星光。",
    "{role}沉默了几秒，然后说：「{q}」嗯，我懂你。",
]


def build_chat_reply(content: str, app_name: str) -> str:
    role = (app_name or "Ta").strip() or "Ta"
    q = content.strip().splitlines()[0][:60]
    template = _CHAT_REPLY_PHRASES[abs(hash(content)) % len(_CHAT_REPLY_PHRASES)]
    return template.format(role=role, q=q)


def safe_filename(name: str, default: str = "cover.png") -> str:
    base = (name or "").strip().replace("\\", "/").rsplit("/", 1)[-1]
    base = re.sub(r"[^A-Za-z0-9._-]+", "_", base).strip("._")
    return base or default


def public_url(path: str) -> str:
    if not path:
        return ""
    if path.startswith("http://") or path.startswith("https://"):
        return path
    if not path.startswith("/"):
        path = "/" + path
    return PUBLIC_BASE_URL + path


def normalize_cover_input(value: object) -> str:
    if not isinstance(value, str):
        return ""
    text = value.strip()
    if not text:
        return ""
    if text.startswith("data:"):
        return text
    if text.startswith("http://") or text.startswith("https://"):
        return text
    if text.startswith("/media-cache/cover/"):
        return public_url(text)
    return text


def normalize_user_avatar_input(value: object) -> str:
    if not isinstance(value, str):
        return ""
    text = value.strip()
    if not text:
        return ""
    if text.startswith("http://") or text.startswith("https://"):
        return text
    if text.startswith("/media-cache/profile/") or text.startswith("/media-cache/avatar/"):
        return text
    raise ValueError("avatar_url must be http(s) or /media-cache/profile/")


def decode_data_url(value: str) -> tuple[bytes, str | None]:
    if not isinstance(value, str):
        raise ValueError("invalid data")
    text = value.strip()
    if not text.startswith("data:"):
        return base64.b64decode(text), None
    header, _, payload = text.partition(",")
    if not payload:
        raise ValueError("invalid data url")
    mime = None
    if ";" in header:
        mime = header[5:header.index(";")]
    elif header.startswith("data:"):
        mime = header[5:]
    return base64.b64decode(payload), mime or None


def _decode_card_json_text(text: str) -> dict | None:
    if not isinstance(text, str):
        return None
    raw = text.strip()
    if not raw:
        return None
    candidates = [raw]
    try:
        decoded = unquote(raw)
        if decoded and decoded != raw:
            candidates.append(decoded)
    except Exception:
        pass
    padded = raw + ("=" * ((4 - len(raw) % 4) % 4))
    try:
        decoded = base64.b64decode(padded, validate=False).decode("utf-8", errors="replace").strip()
        if decoded:
            candidates.append(decoded)
    except Exception:
        pass
    for candidate in candidates:
        try:
            payload = json.loads(candidate)
        except Exception:
            continue
        if isinstance(payload, dict):
            return payload
    return None


def parse_png_card_metadata(blob: bytes) -> dict:
    """读取 SillyTavern/Character Card PNG metadata。"""
    if not blob.startswith(b"\x89PNG\r\n\x1a\n"):
        raise ValueError("不是 PNG 角色卡")
    chunks: list[tuple[str, str]] = []
    pos = 8
    while pos + 8 <= len(blob):
        length = int.from_bytes(blob[pos:pos + 4], "big")
        ctype = blob[pos + 4:pos + 8].decode("latin1", errors="replace")
        data_start = pos + 8
        data_end = data_start + length
        if data_end + 4 > len(blob):
            break
        data = blob[data_start:data_end]
        pos = data_end + 4
        try:
            if ctype == "tEXt":
                key, _, value = data.partition(b"\x00")
                chunks.append((key.decode("latin1", errors="replace"), value.decode("utf-8", errors="replace")))
            elif ctype == "zTXt":
                key, _, rest = data.partition(b"\x00")
                if rest and rest[0] == 0:
                    chunks.append((key.decode("latin1", errors="replace"), zlib.decompress(rest[1:]).decode("utf-8", errors="replace")))
            elif ctype == "iTXt":
                parts = data.split(b"\x00", 5)
                if len(parts) == 6:
                    key = parts[0].decode("utf-8", errors="replace")
                    compressed = parts[1] == b"\x01"
                    value_bytes = zlib.decompress(parts[5]) if compressed else parts[5]
                    chunks.append((key, value_bytes.decode("utf-8", errors="replace")))
        except Exception:
            continue
        if ctype == "IEND":
            break
    preferred = {"chara", "character", "ccv2", "ccv3", "card", "metadata"}
    for key, value in sorted(chunks, key=lambda item: 0 if item[0].strip().lower() in preferred else 1):
        card = _decode_card_json_text(value)
        if card:
            return card
    raise ValueError("PNG 中没有可识别的角色卡 metadata")


def parse_uploaded_card_file(raw: str, filename: str = "") -> dict:
    blob, mime = decode_data_url(raw)
    lower_name = (filename or "").lower()
    lower_mime = (mime or "").lower()
    if lower_mime == "image/png" or lower_name.endswith(".png") or blob.startswith(b"\x89PNG\r\n\x1a\n"):
        return parse_png_card_metadata(blob)
    text = blob.decode("utf-8-sig", errors="replace")
    card = _decode_card_json_text(text)
    if not card:
        raise ValueError("文件不是有效的 JSON 或 PNG 角色卡")
    return card


def safe_tpg_path(path: object) -> str:
    text = str(path or "").strip().replace("\\", "/")
    if not text:
        raise ValueError("插件包路径不能为空")
    if text.startswith("/") or re.match(r"^[A-Za-z]:", text):
        raise ValueError(f"插件包路径不能是绝对路径：{text}")
    parts = text.split("/")
    if any(part in ("", ".", "..") for part in parts):
        raise ValueError(f"插件包路径不能包含空段或上级目录：{text}")
    return text


def clean_tpg_plugin_id(value: object, fallback: str) -> str:
    text = str(value or "").strip()
    text = re.sub(r"[^A-Za-z0-9_.:-]+", "-", text).strip("-._:")
    return (text or fallback)[:160]


def tpg_feature_summary(contributes: object) -> dict:
    data = contributes if isinstance(contributes, dict) else {}
    out: dict[str, int] = {}
    for key in ("inputActions", "sidebar", "messageActions", "htmlFragments", "settings"):
        value = data.get(key)
        if isinstance(value, list):
            out[key] = len(value)
        elif isinstance(value, dict):
            out[key] = len(value)
        else:
            out[key] = 0
    return out


def validate_tpg_manifest(manifest: object, package_paths: set[str]) -> dict:
    if not isinstance(manifest, dict):
        raise ValueError("manifest.json 必须是 JSON 对象")
    package_id = clean_tpg_plugin_id(manifest.get("id"), "")
    if not package_id:
        raise ValueError('manifest 缺少必填字段 "id"')
    name = str(manifest.get("name") or "").strip()
    if not name:
        raise ValueError('manifest 缺少必填字段 "name"')
    version = str(manifest.get("version") or "").strip()
    if not version:
        raise ValueError('manifest 缺少必填字段 "version"')
    spec_version = manifest.get("specVersion", manifest.get("spec_version"))
    if spec_version is not None:
        try:
            if int(spec_version) <= 0:
                raise ValueError
        except Exception as exc:
            raise ValueError("manifest specVersion 必须是正整数") from exc
    contributes = manifest.get("contributes") if isinstance(manifest.get("contributes"), dict) else {}
    scripts = manifest.get("scripts") if isinstance(manifest.get("scripts"), dict) else {}
    needs_actions = bool(contributes.get("inputActions") or contributes.get("sidebar"))
    action_script = scripts.get("actions")
    if needs_actions:
        action_path = safe_tpg_path(action_script)
        if action_path not in package_paths:
            raise ValueError(f"scripts.actions 指向的文件不存在：{action_path}")
    elif action_script:
        safe_tpg_path(action_script)
    cover = manifest.get("cover")
    if cover:
        cover_path = safe_tpg_path(cover)
        if cover_path not in package_paths:
            raise ValueError(f"cover 指向的文件不存在：{cover_path}")
    for item in contributes.get("htmlFragments") or []:
        if not isinstance(item, dict):
            raise ValueError("contributes.htmlFragments 项必须是对象")
        src = item.get("src")
        if not src:
            raise ValueError("htmlFragments 项缺少 src")
        fragment_path = safe_tpg_path(src)
        if fragment_path not in package_paths:
            raise ValueError(f"htmlFragments src 指向的文件不存在：{fragment_path}")
    declared_files = manifest.get("files") or []
    if declared_files and not isinstance(declared_files, list):
        raise ValueError('manifest "files" 必须是数组')
    for item in declared_files:
        if isinstance(item, str):
            safe_tpg_path(item)
        elif isinstance(item, dict):
            safe_tpg_path(item.get("path"))
        else:
            raise ValueError('manifest "files" 项必须是字符串或对象')
    return {
        "package_id": package_id,
        "name": name[:180],
        "version": version[:80],
        "description": str(manifest.get("description") or "").strip()[:2000],
        "author": str(manifest.get("author") or "").strip()[:180],
        "cover_path": str(cover or "").strip()[:240],
        "contributes": contributes,
        "files": declared_files,
        "features": tpg_feature_summary(contributes),
    }


def parse_tpg_package(raw: str, filename: str = "") -> dict:
    blob, _mime = decode_data_url(raw)
    if not blob:
        raise ValueError("插件包为空")
    if len(blob) > TPG_MAX_PACKAGE_BYTES:
        raise ValueError(f"插件包过大，最大 {TPG_MAX_PACKAGE_BYTES // 1024 // 1024}MB")
    lower_name = str(filename or "").lower()
    if lower_name and not (lower_name.endswith(".tpg") or lower_name.endswith(".zip")):
        raise ValueError("只支持 .tpg 或 .zip 插件包")
    try:
        zf = zipfile.ZipFile(io.BytesIO(blob))
    except Exception as exc:
        raise ValueError(".tpg 必须是 zip 格式插件包") from exc
    with zf:
        infos = [info for info in zf.infolist() if not info.is_dir()]
        if len(infos) > TPG_MAX_FILES:
            raise ValueError(f"插件包文件过多，最多 {TPG_MAX_FILES} 个文件")
        total_uncompressed = 0
        paths: set[str] = set()
        for info in infos:
            path = safe_tpg_path(info.filename)
            total_uncompressed += int(info.file_size or 0)
            if total_uncompressed > TPG_MAX_UNCOMPRESSED_BYTES:
                raise ValueError(f"插件包展开体积过大，最大 {TPG_MAX_UNCOMPRESSED_BYTES // 1024 // 1024}MB")
            paths.add(path)
        if "manifest.json" not in paths:
            raise ValueError("插件包根目录缺少 manifest.json")
        try:
            manifest = json.loads(zf.read("manifest.json").decode("utf-8-sig", errors="replace"))
        except Exception as exc:
            raise ValueError("manifest.json 不是有效 JSON") from exc
        meta = validate_tpg_manifest(manifest, paths)
    file_hash = hashlib.sha256(blob).hexdigest()
    return {
        **meta,
        "manifest": manifest,
        "package_bytes": blob,
        "file_name": safe_filename(filename or f"{meta['package_id']}.tpg", "plugin.tpg"),
        "file_sha256": file_hash,
        "file_count": len(paths),
        "package_size": len(blob),
        "uncompressed_size": total_uncompressed,
        "package_paths": sorted(paths),
    }


def tpg_plugin_row_json(row: sqlite3.Row | dict, include_manifest: bool = False) -> dict:
    data = dict(row)
    manifest = {}
    contributes = {}
    files = []
    for key, target in (("manifest_json", "manifest"), ("contributes_json", "contributes"), ("files_json", "files")):
        try:
            parsed = json.loads(data.get(key) or "{}")
        except Exception:
            parsed = [] if target == "files" else {}
        if target == "manifest":
            manifest = parsed if isinstance(parsed, dict) else {}
        elif target == "contributes":
            contributes = parsed if isinstance(parsed, dict) else {}
        else:
            files = parsed if isinstance(parsed, list) else []
    out = {
        "id": data.get("id") or "",
        "package_id": data.get("package_id") or "",
        "name": data.get("name") or "",
        "version": data.get("version") or "",
        "description": data.get("description") or "",
        "author": data.get("author") or "",
        "cover_path": data.get("cover_path") or "",
        "file_name": data.get("file_name") or "",
        "file_sha256": data.get("file_sha256") or "",
        "enabled": bool(int(data.get("enabled") or 0)),
        "created_at": int(data.get("created_at") or 0),
        "updated_at": int(data.get("updated_at") or 0),
        "features": tpg_feature_summary(contributes),
        "contributes": contributes,
        "files": files,
    }
    if include_manifest:
        out["manifest"] = manifest
    return out


def png_chunk(chunk_type: bytes, data: bytes) -> bytes:
    return len(data).to_bytes(4, "big") + chunk_type + data + zlib.crc32(chunk_type + data).to_bytes(4, "big")


def app_to_silly_card_png_data_url(card: dict) -> str:
    base_png = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAFgwJ/l0CXNwAAAABJRU5ErkJggg=="
    )
    iend = base_png.rfind(b"IEND") - 4
    if iend < 8:
        raise ValueError("invalid png template")
    card_json = json.dumps(app_to_silly_card(card), ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    encoded = base64.b64encode(card_json)
    text_chunk = png_chunk(b"tEXt", b"chara\x00" + encoded)
    png = base_png[:iend] + text_chunk + base_png[iend:]
    return "data:image/png;base64," + base64.b64encode(png).decode("ascii")


def extract_upstream_chat_answer(payload: object) -> str | None:
    if isinstance(payload, dict):
        content_blocks = payload.get("content")
        if isinstance(content_blocks, list):
            parts: list[str] = []
            for block in content_blocks:
                if isinstance(block, dict):
                    text = block.get("text") or block.get("content")
                    if isinstance(text, str) and text:
                        parts.append(text)
                elif isinstance(block, str) and block:
                    parts.append(block)
            joined = "".join(parts).strip()
            if joined:
                return joined
        choices = payload.get("choices")
        if isinstance(choices, list) and choices:
            choice = choices[0] if isinstance(choices[0], dict) else {}
            message = choice.get("message") if isinstance(choice.get("message"), dict) else {}
            for key in ("content", "text", "reply", "answer"):
                value = message.get(key)
                if isinstance(value, str) and value.strip():
                    return value.strip()
            value = choice.get("text")
            if isinstance(value, str) and value.strip():
                return value.strip()
        for key in ("reply", "answer", "content", "text", "message"):
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        data = payload.get("data")
        if isinstance(data, dict):
            for key in ("reply", "answer", "content", "text", "message"):
                value = data.get(key)
                if isinstance(value, str) and value.strip():
                    return value.strip()
            message = data.get("message")
            if isinstance(message, dict):
                for key in ("content", "reply", "answer", "text", "message"):
                    value = message.get(key)
                    if isinstance(value, str) and value.strip():
                        return value.strip()
    if isinstance(payload, str) and payload.strip():
        return payload.strip()
    return None


def extract_sse_answer(raw_text: str) -> str | None:
    text = raw_text.strip()
    if not text:
        return None
    last = None
    for chunk in text.split("\n\n"):
        data_lines = []
        for line in chunk.splitlines():
            if line.startswith("data:"):
                data_lines.append(line[5:].lstrip())
        if not data_lines:
            continue
        joined = "\n".join(data_lines)
        try:
            payload = json.loads(joined)
        except Exception:
            last = joined.strip()
            continue
        answer = extract_upstream_chat_answer(payload)
        if answer:
            last = answer
    return last


def select_world_info(entries: list, recent_text: str, *, char_name: str = "", user_name: str = "", position: str = "system", max_chars: int = 4000, return_entries: bool = False, template_context: dict | None = None, include_special: bool = False):
    """根据最近对话文本命中世界书条目，拼成注入段落。支持优先级、二级关键词、概率和递归扫描。"""
    if not isinstance(entries, list) or not entries:
        return [] if return_entries else ""
    normalized = normalize_world_info(entries)
    candidates = []
    for entry in normalized:
        if not (entry.get("enabled", True) and entry.get("position", "system") == position and entry.get("content")):
            continue
        if not include_special and is_tavern_special_world_entry(entry):
            continue
        if not tavern_world_condition_passes(entry, char_name=char_name, user_name=user_name, template_context=template_context):
            continue
        candidates.append(entry)
    if not candidates:
        return [] if return_entries else ""
    candidates.sort(key=lambda e: (-int(e.get("priority") or 0), int(e.get("order") or 0)))

    def _has_any(keys: list, text: str, case_sensitive: bool, whole_words: bool = False) -> bool:
        if not keys:
            return False
        target = text if case_sensitive else text.lower()
        for k in keys:
            key = str(k or "").strip()
            if not key:
                continue
            needle = key if case_sensitive else key.lower()
            if (re.search(rf"(?<!\\w){re.escape(needle)}(?!\\w)", target) if whole_words else needle in target):
                return True
        return False

    def _entry_hits(entry: dict, text: str) -> bool:
        if entry.get("constant"):
            return True
        keys = entry.get("keys") if isinstance(entry.get("keys"), list) else []
        secondary = entry.get("secondary_keys") if isinstance(entry.get("secondary_keys"), list) else []
        case_sensitive = bool(entry.get("case_sensitive", False))
        whole_words = bool(entry.get("match_whole_words", False))
        primary_hit = _has_any(keys, text, case_sensitive, whole_words)
        if not primary_hit:
            return False
        if entry.get("selective") or secondary:
            hits = [_has_any([key], text, case_sensitive, whole_words) for key in secondary]
            return all(hits) if entry.get("selective_logic") == "and_all" else any(hits)
        return True

    picked_entries: list[dict] = []
    picked_ids: set[str] = set()
    scan_text = recent_text or ""
    for _ in range(3):
        added = False
        for entry in candidates:
            entry_id = str(entry.get("id") or id(entry))
            if entry_id in picked_ids:
                continue
            if not _entry_hits(entry, scan_text):
                continue
            probability = int(entry.get("probability") if entry.get("probability") is not None else 100)
            if probability < 100 and random.randint(1, 100) > probability:
                continue
            picked_entries.append(entry)
            picked_ids.add(entry_id)
            added = True
            if entry.get("recursive"):
                scan_text += "\n" + str(entry.get("content") or "")
        if not added:
            break

    if return_entries:
        return picked_entries

    picked: list[str] = []
    total = 0
    for entry in picked_entries:
        piece = render_tavern_template(
            strip_tavern_world_controls(entry.get("content")),
            char_name,
            user_name,
            template_context=template_context_with_world(template_context, entry),
            phase="generate",
        )
        if total + len(piece) > max_chars:
            piece = piece[: max(0, max_chars - total)]
        if piece:
            name = str(entry.get("name") or "").strip()
            picked.append(f"【{name}】\n{piece}" if name else piece)
            total += len(piece)
        if total >= max_chars:
            break
    if not picked:
        return ""
    return "【相关设定】\n" + "\n".join(picked)


def world_entries_to_text(entries: list, *, char_name: str = "", user_name: str = "", max_chars: int = 4000, template_context: dict | None = None) -> str:
    picked: list[str] = []
    total = 0
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        if is_tavern_special_world_entry(entry) or not tavern_world_condition_passes(entry, char_name=char_name, user_name=user_name, template_context=template_context):
            continue
        piece = render_tavern_template(
            strip_tavern_world_controls(entry.get("content")),
            char_name,
            user_name,
            template_context=template_context_with_world(template_context, entry),
            phase="generate",
        )
        if not piece:
            continue
        if total + len(piece) > max_chars:
            piece = piece[: max(0, max_chars - total)]
        if piece:
            name = str(entry.get("name") or "").strip()
            picked.append(f"【{name}】\n{piece}" if name else piece)
            total += len(piece)
        if total >= max_chars:
            break
    if not picked:
        return ""
    return "【相关设定】\n" + "\n".join(picked)


def prompt_block_texts(extras: dict, position: str, *, char_name: str = "", user_name: str = "", max_chars: int = 8000, template_context: dict | None = None) -> list[str]:
    blocks = normalize_prompt_blocks(extras.get("prompt_blocks") if isinstance(extras, dict) else [])
    out: list[str] = []
    total = 0
    for block in blocks:
        if not block.get("enabled", True) or block.get("position") != position:
            continue
        content = render_tavern_template(
            str(block.get("content") or "").strip(),
            char_name,
            user_name,
            template_context=template_context,
            phase="generate",
        )
        if not content:
            continue
        if total + len(content) > max_chars:
            content = content[: max(0, max_chars - total)]
        if content:
            name = str(block.get("name") or "提示词块").strip()
            out.append(f"【{name}】\n{content}")
            total += len(content)
        if total >= max_chars:
            break
    return out


def global_prompt_messages(preset: object, position: str, *, char_name: str = "", user_name: str = "", max_chars: int = 40000, template_context: dict | None = None) -> list[dict]:
    config = normalize_global_prompt_preset(preset)
    if not config.get("enabled"):
        return []
    out: list[dict] = []
    total = 0
    for block in config.get("blocks") or []:
        if not isinstance(block, dict) or not block.get("enabled", True) or block.get("position") != position:
            continue
        content = render_tavern_template(
            str(block.get("content") or "").strip(),
            char_name,
            user_name,
            template_context=template_context,
            phase="generate",
        )
        if not content:
            continue
        if total + len(content) > max_chars:
            content = content[: max(0, max_chars - total)]
        if not content:
            break
        role = str(block.get("role") or "system").strip().lower()
        if role not in {"system", "user", "assistant"}:
            role = "system"
        name = str(block.get("name") or "全局提示词").strip()
        out.append({"role": role, "content": f"【{name}】\n{content}"})
        total += len(content)
        if total >= max_chars:
            break
    return out


def build_system_prompt(app: dict, persona: dict | None, recent_text: str, *, template_context: dict | None = None) -> str:
    """组装 SillyTavern 风格系统提示（已做宏替换）。开场白不在此处。"""
    char_name = str(app.get("name") or "Ta").strip() or "Ta"
    persona = persona or {}
    user_name = str(persona.get("name") or "").strip() or "你"
    persona_desc = str(persona.get("description") or "").strip()

    extras = app_extras(app)

    def _m(v):
        return render_tavern_template(str(v or "").strip(), char_name, user_name, template_context=template_context, phase="generate")

    parts: list[str] = []
    required_world = next((entry for entry in extras.get("world_info") or [] if entry.get("id") == REQUIRED_WORLD_BOOK_ID), None)
    if required_world:
        required_text = render_tavern_template(
            str(required_world.get("content") or ""), char_name, user_name,
            template_context=template_context_with_world(template_context, required_world), phase="generate",
        )
        if required_text:
            parts.append(f"【{required_world.get('name') or '反扒卡'}】\n{required_text}")
    parts.extend(prompt_block_texts(extras, "system_before", char_name=char_name, user_name=user_name, template_context=template_context))
    pre = _m(app.get("pre_prompt"))
    if pre:
        parts.append(pre)
    parts.append(f"你正在扮演角色「{char_name}」，请始终以该角色的身份、口吻和性格进行回复，不要跳出角色。")
    parts.append(
        "【输出规范】\n"
        "1. 最终回复统一使用简体中文，即使角色卡、世界书、示例对话或用户消息里包含日文、英文或其他语言，也要自然翻译/改写成中文。\n"
        "2. 专有名词、地名、人名可以保留原名，但解释、旁白、动作和对话都用中文表达。\n"
        "3. 如果需要输出状态信息，请使用 <StatusBlock>...</StatusBlock> 包裹，并使用中文字段名，例如：[学段]、[时间]、[地点]、[对象]、[未来事件]、[目标]、[目标进度]。\n"
        "4. 只输出最终可见的角色回复、动作、旁白和必要状态；不要输出推理、分析、计划、草稿、调试说明，也不要出现 Processing、Reasoning、Thought、Narrative Flow 等英文过程标题。\n"
        "5. 除角色卡明确要求的 <StatusBlock> 或安全可视化片段外，不要把回复包装成 JSON/YAML/XML/Markdown 代码块，不要输出字段名式结果。"
    )
    desc = _m(app.get("description"))
    if desc:
        parts.append(f"【角色设定】\n{desc}")
    personality = _m(extras.get("personality"))
    if personality:
        parts.append(f"【性格】\n{personality}")
    scenario = _m(extras.get("scenario"))
    if scenario:
        parts.append(f"【场景】\n{scenario}")
    if persona_desc:
        parts.append(f"【关于对话者（{user_name}）】\n{render_tavern_template(persona_desc, char_name, user_name, template_context=template_context, phase='generate')}")
    regular_world = [entry for entry in extras.get("world_info") or [] if entry.get("id") != REQUIRED_WORLD_BOOK_ID]
    world = select_world_info(regular_world, recent_text, char_name=char_name, user_name=user_name, template_context=template_context)
    if world:
        parts.append(world)
    example = _m(extras.get("mes_example"))
    if example:
        parts.append(f"【对话示例】\n{example}")
    parts.extend(prompt_block_texts(extras, "system_after", char_name=char_name, user_name=user_name, template_context=template_context))
    return "\n\n".join([p for p in parts if p]) or "你是一个角色扮演助手。"


def memory_context_messages(context: dict | None, *, char_name: str = "", user_name: str = "", template_context: dict | None = None) -> list[dict]:
    if not isinstance(context, dict):
        return []
    out: list[dict] = []
    summary = context.get("summary") if isinstance(context.get("summary"), dict) else {}
    summary_text = render_tavern_template(str(summary.get("summary") or "").strip(), char_name, user_name, template_context=template_context, phase="generate")
    if summary_text:
        out.append({"role": "system", "content": "【对话摘要】\n" + summary_text[:6000]})
    memories = context.get("memories") if isinstance(context.get("memories"), list) else []
    lines: list[str] = []
    total = 0
    for mem in memories:
        if not isinstance(mem, dict):
            continue
        content = render_tavern_template(str(mem.get("content") or "").strip(), char_name, user_name, template_context=template_context, phase="generate")
        if not content:
            continue
        title = str(mem.get("title") or "").strip()
        piece = f"- {title}: {content}" if title else f"- {content}"
        if total + len(piece) > 4000:
            piece = piece[: max(0, 4000 - total)]
        if piece:
            lines.append(piece)
            total += len(piece)
        if total >= 4000:
            break
    if lines:
        out.append({"role": "system", "content": "【长期记忆】\n" + "\n".join(lines)})
    return out


def app_extras(app: dict) -> dict:
    extras = app.get("extra_settings") if isinstance(app, dict) else None
    if isinstance(extras, str) and extras.strip():
        try:
            extras = json.loads(extras)
        except Exception:
            extras = None
    extras = extras if isinstance(extras, dict) else {}
    extras = dict(extras)
    extras["world_info"] = ensure_required_world_info(extras.get("world_info") or [])
    return extras


def enabled_regex_scripts(app: dict) -> list[dict]:
    candidates: list[object] = []
    if isinstance(app, dict):
        candidates.extend(regex_scripts_from_extensions(app.get("extensions")))
        extras = app_extras(app)
        candidates.extend(regex_scripts_from_extensions(extras.get("extensions")))
        top_scripts = app.get("regex_scripts")
        if isinstance(top_scripts, list):
            candidates.extend(top_scripts)
        extra_scripts = extras.get("regex_scripts")
        if isinstance(extra_scripts, list):
            candidates.extend(extra_scripts)
    best: dict[tuple[str, str, str], dict] = {}
    ordered_keys: list[tuple[str, str, str]] = []
    for script in normalize_regex_scripts(candidates):
        key = (
            str(script.get("name") or ""),
            str(script.get("find") or ""),
            str(script.get("flags") or ""),
        )
        current = best.get(key)
        if current is None:
            ordered_keys.append(key)
            best[key] = script
            continue
        if len(str(script.get("replace") or "")) > len(str(current.get("replace") or "")):
            best[key] = script
    return [best[key] for key in ordered_keys if best[key].get("enabled", True)]


def expand_silly_regex_replacement(template: str, match: re.Match) -> str:
    """Expand JS/SillyTavern-style replacement tokens without Python backslash escapes."""
    text = str(template or "")
    out: list[str] = []
    i = 0
    while i < len(text):
        ch = text[i]
        if ch == "$":
            nxt = text[i + 1] if i + 1 < len(text) else ""
            if nxt == "$":
                out.append("$")
                i += 2
                continue
            if nxt == "&":
                out.append(match.group(0) or "")
                i += 2
                continue
            if nxt == "<":
                end = text.find(">", i + 2)
                if end > i + 2:
                    name = text[i + 2:end]
                    try:
                        out.append(match.group(name) or "")
                    except Exception:
                        out.append("")
                    i = end + 1
                    continue
            if nxt.isdigit():
                digits = nxt
                if i + 2 < len(text) and text[i + 2].isdigit():
                    digits += text[i + 2]
                try:
                    value = match.group(int(digits))
                    out.append(value or "")
                    i += 1 + len(digits)
                    continue
                except Exception:
                    if len(digits) > 1:
                        try:
                            value = match.group(int(digits[0]))
                            out.append((value or "") + digits[1:])
                            i += 1 + len(digits)
                            continue
                        except Exception:
                            pass
                    out.append("")
                    i += 2
                    continue
        if ch == "\\" and i + 1 < len(text) and text[i + 1].isdigit():
            digits = text[i + 1]
            if i + 2 < len(text) and text[i + 2].isdigit():
                digits += text[i + 2]
            try:
                out.append(match.group(int(digits)) or "")
                i += 1 + len(digits)
                continue
            except Exception:
                pass
        out.append(ch)
        i += 1
    return "".join(out)


def apply_regex_scripts(text: str, app: dict) -> str:
    value = str(text or "")
    for script in enabled_regex_scripts(app):
        flags = 0
        raw_flags = str(script.get("flags") or "")
        if "i" in raw_flags:
            flags |= re.IGNORECASE
        if "m" in raw_flags:
            flags |= re.MULTILINE
        if "s" in raw_flags:
            flags |= re.DOTALL
        try:
            pattern = re.compile(str(script.get("find") or ""), flags=flags)
            replacement = str(script.get("replace") or "")
            value = pattern.sub(lambda match: expand_silly_regex_replacement(replacement, match), value)
        except re.error as exc:
            log(f"regex script skipped for {app.get('id')}: {exc}")
    return value


VISIBLE_REPLY_JSON_KEYS = (
    "final",
    "final_reply",
    "finalResponse",
    "reply",
    "response",
    "answer",
    "dialogue",
    "narration",
    "message",
    "content",
    "text",
    "output",
    "body",
    "html",
)

INTERNAL_REPLY_JSON_KEYS = {
    "thought",
    "thoughts",
    "thinking",
    "reasoning",
    "analysis",
    "plan",
    "planning",
    "scratchpad",
    "debug",
    "metadata",
}

INTERNAL_SECTION_MARKERS = (
    "processing",
    "initial input",
    "initial inputs",
    "continuing narrative",
    "narrative flow",
    "guiding",
    "reasoning",
    "analysis",
    "analyzing",
    "planning",
    "response plan",
    "drafting",
    "thought",
    "internal",
    "reflection",
    "deliberation",
    "strategy",
)

CHINESE_INTERNAL_SECTION_MARKERS = (
    "思考",
    "思考过程",
    "推理",
    "推理过程",
    "分析",
    "分析过程",
    "计划",
    "内部推理",
    "创作思路",
)


def _single_fenced_block(text: str) -> tuple[str, str] | None:
    match = re.match(r"^\s*```([a-zA-Z0-9_-]*)[ \t]*\r?\n([\s\S]*?)\r?\n?```\s*$", str(text or "").strip())
    if not match:
        return None
    return match.group(1).strip().lower(), match.group(2).strip()


def _string_from_json_value(value: object) -> str | None:
    if isinstance(value, str):
        return value.strip() or None
    if isinstance(value, (int, float, bool)):
        return str(value)
    if isinstance(value, list):
        parts: list[str] = []
        for item in value:
            if isinstance(item, str) and item.strip():
                parts.append(item.strip())
            elif isinstance(item, dict):
                piece = _visible_reply_from_json(item)
                if piece:
                    parts.append(piece)
        joined = "\n".join(parts).strip()
        return joined or None
    if isinstance(value, dict):
        return _visible_reply_from_json(value)
    return None


def _json_object_to_plain_text(data: dict) -> str | None:
    rows: list[str] = []
    for key, value in data.items():
        label = str(key or "").strip()
        if not label or label.lower() in INTERNAL_REPLY_JSON_KEYS:
            continue
        piece = _string_from_json_value(value)
        if piece:
            rows.append(f"{label}：{piece}")
    return "\n".join(rows).strip() or None


def _visible_reply_from_json(data: object) -> str | None:
    if isinstance(data, dict):
        lowered = {str(k).lower(): k for k in data.keys()}
        for key in VISIBLE_REPLY_JSON_KEYS:
            actual = data.get(key)
            if actual is None:
                actual = data.get(lowered.get(key.lower(), ""))
            piece = _string_from_json_value(actual)
            if piece:
                return piece
        nested = data.get("data")
        if isinstance(nested, (dict, list, str)):
            piece = _string_from_json_value(nested)
            if piece:
                return piece
        return _json_object_to_plain_text(data)
    if isinstance(data, list):
        return _string_from_json_value(data)
    if isinstance(data, str):
        return data.strip() or None
    return None


def _extract_json_visible_reply(text: str) -> str | None:
    value = str(text or "").strip()
    if not value:
        return None
    fenced = _single_fenced_block(value)
    if fenced and fenced[0] in {"json", "jsonc"}:
        value = fenced[1]
    if not value.startswith(("{", "[")):
        return None
    try:
        parsed = json.loads(value)
    except Exception:
        return None
    return _visible_reply_from_json(parsed)


def _clean_internal_heading(line: str) -> str:
    value = str(line or "").strip()
    value = re.sub(r"^\s{0,3}#{1,6}\s*", "", value)
    value = value.strip("*_`# \t")
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def _is_internal_section_heading(line: str) -> bool:
    heading = _clean_internal_heading(line)
    if not heading or len(heading) > 120:
        return False
    compact = re.sub(r"[\s:：，。,.、-]+", "", heading)
    if compact in CHINESE_INTERNAL_SECTION_MARKERS:
        return True
    if re.search(r"[\u4e00-\u9fff]", heading):
        return False
    lower = heading.lower()
    return any(marker in lower for marker in INTERNAL_SECTION_MARKERS)


def _strip_internal_markdown_sections(text: str) -> str:
    value = str(text or "")
    if not value.strip():
        return value
    blocks = re.split(r"\n\s*\n", value.replace("\r\n", "\n").replace("\r", "\n"))
    kept: list[str] = []
    changed = False
    for block in blocks:
        lines = [line for line in block.split("\n") if line.strip()]
        first = lines[0] if lines else ""
        if _is_internal_section_heading(first):
            changed = True
            continue
        kept.append(block.strip())
    return "\n\n".join([part for part in kept if part]).strip() if changed else value.strip()


def _strip_internal_xml_tags(text: str) -> str:
    value = str(text or "")
    for tag in ("think", "thinking", "reasoning", "analysis", "scratchpad"):
        value = re.sub(rf"<{tag}\b[^>]*>[\s\S]*</{tag}\s*>", "", value, flags=re.IGNORECASE)
        value = re.sub(rf"<{tag}\b[^>]*>[\s\S]*$", "", value, flags=re.IGNORECASE)
        value = re.sub(rf"</{tag}\s*>", "", value, flags=re.IGNORECASE)
    return value


def _strip_format_instruction_leaks(text: str) -> str:
    value = str(text or "")
    if not value.strip():
        return value
    noisy_line = re.compile(
        r"(?im)^.*(?:"
        r"<\s*/?\s*(?:think|thinking|reasoning|analysis|scratchpad)\b[^>]*>|"
        r"检查需要生成的内容格式|检测所有需要输出的标签格式|"
        r"创作前必须有思考过程|格式加强|思考范围|真正的思考截止|自动识别到|这样的问题|"
        r"不得有遗漏|不得有改写|多添或缺少|标签格式"
        r").*$"
    )
    value = noisy_line.sub("", value)
    return re.sub(r"\n{3,}", "\n\n", value).strip()


def _extract_visible_content_tag(text: str) -> str | None:
    value = str(text or "").strip()
    if not value:
        return None
    match = re.search(r"<content\b[^>]*>([\s\S]*)</content\s*>", value, flags=re.IGNORECASE)
    if match:
        return match.group(1).strip()
    match = re.search(r"<content\b[^>]*>([\s\S]+)$", value, flags=re.IGNORECASE)
    if match:
        return match.group(1).strip()
    if re.search(r"</content\s*>", value, flags=re.IGNORECASE):
        return re.sub(r"</?content\b[^>]*>", "", value, flags=re.IGNORECASE).strip()
    return None


def _strip_leading_reply_labels(text: str) -> str:
    value = str(text or "").strip()
    for _ in range(3):
        next_value = re.sub(
            r"^\s*(?:assistant|final answer|final response|response|reply|answer|角色回复|最终回复|回复|旁白|assistant reply)\s*[:：]\s*",
            "",
            value,
            flags=re.IGNORECASE,
        ).strip()
        if next_value == value:
            break
        value = next_value
    return value


def _extract_labeled_final_reply(text: str) -> str | None:
    value = str(text or "").strip()
    patterns = (
        r"(?:^|\n)\s*(?:final answer|final response|response|reply|answer)\s*[:：]\s*([\s\S]+)$",
        r"(?:^|\n)\s*(?:最终回复|角色回复|回复正文|回复)\s*[:：]\s*([\s\S]+)$",
    )
    for pattern in patterns:
        match = re.search(pattern, value, flags=re.IGNORECASE)
        if match:
            piece = match.group(1).strip()
            if piece:
                return piece
    return None


METADATA_FENCE_LANGS = {"yaml", "yml", "json", "jsonc", "toml", "ini", "properties", "meta", "metadata"}
METADATA_FENCE_MARKERS = (
    "{{char}}", "{{user}}", "persona", "personality", "scenario", "worldbook", "world_info",
    "relationships", "residence", "creator", "version", "updated_at", "update_date",
)


def _looks_like_leading_metadata_fence(lang: str, body: str) -> bool:
    normalized_lang = str(lang or "").strip().lower().split()[0]
    value = str(body or "").strip()
    lower = value.lower()
    if "{{char}}" in lower or "{{user}}" in lower:
        return True
    if any(marker in lower for marker in METADATA_FENCE_MARKERS):
        return True
    if normalized_lang in METADATA_FENCE_LANGS:
        colon_lines = len(re.findall(r"(?m)^\s*[-\w\u4e00-\u9fff{}.$\[\]\"']+\s*[:=]", value))
        return colon_lines >= 2
    return False


def _strip_leading_metadata_fences(text: str) -> str:
    value = str(text or "").strip()
    changed = False
    for _ in range(4):
        match = re.match(r"^\s*```([^\r\n`]*)\r?\n([\s\S]*?)\r?\n```\s*", value)
        if not match:
            break
        rest = value[match.end():].lstrip()
        if not rest:
            break
        if not _looks_like_leading_metadata_fence(match.group(1), match.group(2)):
            break
        value = rest
        changed = True
    return value if changed else text


def normalize_visible_chat_reply(text: object) -> str:
    """Keep only the user-visible assistant reply after model/template/regex processing."""
    original = str(text or "").strip()
    if not original:
        return ""
    value = original
    changed_any = False
    for _ in range(4):
        before = value
        value = _strip_internal_xml_tags(value).strip()
        content_tag = _extract_visible_content_tag(value)
        if content_tag is not None:
            value = content_tag.strip()
        else:
            value = _strip_format_instruction_leaks(value).strip()
        labeled = _extract_labeled_final_reply(value)
        if labeled:
            value = labeled.strip()
        extracted = _extract_json_visible_reply(value)
        if extracted:
            value = extracted.strip()
        value = _strip_internal_markdown_sections(value)
        value = _strip_leading_reply_labels(value)
        value = _strip_leading_metadata_fences(value).strip()
        fenced = _single_fenced_block(value)
        if fenced and fenced[0] in {"text", "txt", "markdown", "md"}:
            value = fenced[1].strip()
        if value != before:
            changed_any = True
        if value == before:
            break
    value = re.sub(r"\n{4,}", "\n\n\n", value).strip()
    return value or ("" if changed_any else original)


def process_model_reply(app: dict, reply: object, *, char_name: str = "", user_name: str = "", template_context: dict | None = None) -> str:
    ctx = dict(template_context) if isinstance(template_context, dict) else {}
    if isinstance(app, dict):
        ctx.setdefault("app", app)
        ctx.setdefault("app_id", str(app.get("id") or ""))
    rendered = render_tavern_template(
        str(reply or ""),
        char_name or str((app or {}).get("name") or "Ta"),
        user_name or "你",
        template_context=ctx,
        phase="render",
        max_output=24000,
    )
    extras = app_extras(app or {})
    base_context = ctx.get("context") if isinstance(ctx.get("context"), dict) else {}
    recent_text = str(base_context.get("recent_text") or "")
    render_injections = collect_tavern_render_injections(
        extras.get("world_info") or [],
        rendered,
        recent_text,
        char_name=char_name or str((app or {}).get("name") or "Ta"),
        user_name=user_name or "你",
        template_context=ctx,
    )
    rendered = apply_tavern_render_injections(rendered, render_injections)
    rendered = apply_regex_scripts(rendered, app or {})
    return normalize_visible_chat_reply(rendered)


def build_user_llm_request(app: dict, content: str, messages: list[dict] | None = None, settings: dict | None = None, persona: dict | None = None, context: dict | None = None) -> dict:
    settings = settings or {}
    enabled = bool(settings.get("enabled", True))
    app_model = str(app.get("llm_model") or "").strip()
    protocol = normalize_llm_protocol(settings.get("protocol"), base_url=settings.get("base_url"))
    if settings.get("model"):
        model = str(settings.get("model") or "").strip()
    elif app_model and not app_model.startswith("user:") and "::" not in app_model:
        model = app_model
    else:
        model = str(USER_LLM_MODEL or "").strip()
    model = model or "gpt-4o-mini"
    base_url = (app.get("api_base_url") or settings.get("base_url") or USER_LLM_BASE_URL or "").strip().rstrip("/")
    api_key = (settings.get("api_key") or app.get("api_key") or USER_LLM_API_KEY or "").strip()
    try:
        temperature = float(settings.get("temperature", USER_LLM_TEMPERATURE))
    except (TypeError, ValueError):
        temperature = USER_LLM_TEMPERATURE
    # Per-character sampling overrides (set via the editor)
    extras = app_extras(app)
    sampling = extras.get("sampling") if isinstance(extras.get("sampling"), dict) else {}
    if "temperature" in sampling and sampling["temperature"] is not None:
        try: temperature = float(sampling["temperature"])
        except Exception: pass
    history_length = sampling.get("history_length")
    try: history_length = int(history_length) if history_length is not None else 12
    except Exception: history_length = 12
    if history_length <= 0: history_length = 12
    history_length = max(1, min(history_length, 80))
    fallback = build_chat_reply(content, str(app.get("name") or "Ta"))
    if not enabled or not base_url or not api_key:
        return {"enabled": False, "fallback": fallback, "model": model}
    char_name = str(app.get("name") or "Ta").strip() or "Ta"
    user_name = str((persona or {}).get("name") or "").strip() or "你"
    template_context = dict(context) if isinstance(context, dict) else {}
    template_context.setdefault("app_id", str(app.get("id") or ""))
    template_context.setdefault("app", app)
    trimmed_history = (messages or [])[-history_length:]
    recent_text = "\n".join(str(m.get("content") or "") for m in trimmed_history) + "\n" + content
    apply_initial_template_variables(extras.get("world_info") or [], template_context, char_name=char_name, user_name=user_name)
    global_preset = settings.get("global_prompt_preset") if isinstance(settings, dict) else None
    system_prompt = build_system_prompt(app, persona, recent_text, template_context=template_context)
    global_before = global_prompt_messages(
        global_preset,
        "system_before",
        char_name=char_name,
        user_name=user_name,
        template_context=template_context,
    )
    global_after = global_prompt_messages(
        global_preset,
        "system_after",
        char_name=char_name,
        user_name=user_name,
        template_context=template_context,
    )
    if global_before or global_after:
        system_prompt = "\n\n".join(
            [msg["content"] for msg in global_before if msg.get("content")]
            + [system_prompt]
            + [msg["content"] for msg in global_after if msg.get("content")]
        )
    chat_messages = [{"role": "system", "content": system_prompt}]
    chat_messages.extend(memory_context_messages(context, char_name=char_name, user_name=user_name, template_context=template_context))
    for msg in trimmed_history:
        role = str(msg.get("role") or "").strip()
        content_value = render_tavern_template(
            str(msg.get("content") or "").strip(),
            char_name,
            user_name,
            template_context=template_context,
            phase="generate",
            message=msg,
        )
        if role in {"user", "assistant", "system"} and content_value:
            chat_messages.append({"role": role, "content": content_value})
    user_content = render_tavern_template(
        content,
        char_name,
        user_name,
        template_context=template_context,
        phase="generate",
        message={"role": "user", "content": content},
    )
    last = chat_messages[-1] if chat_messages else {}
    if not (last.get("role") == "user" and str(last.get("content") or "").strip() == user_content):
        chat_messages.append({"role": "user", "content": user_content})
    chat_messages.extend(global_prompt_messages(
        global_preset,
        "post_history",
        char_name=char_name,
        user_name=user_name,
        template_context=template_context,
    ))
    extras_for_phi = app_extras(app)
    if isinstance(extras_for_phi, dict):
        depth_entries = select_world_info(
            extras_for_phi.get("world_info") or [],
            recent_text,
            char_name=char_name,
            user_name=user_name,
            position="depth",
            return_entries=True,
            template_context=template_context,
        )
        if isinstance(depth_entries, list) and depth_entries:
            grouped: dict[int, list] = {}
            for entry in depth_entries:
                try:
                    depth = int(entry.get("depth") or 4)
                except Exception:
                    depth = 4
                grouped.setdefault(max(0, min(20, depth)), []).append(entry)
            for depth, items in sorted(grouped.items(), reverse=True):
                text = world_entries_to_text(items, char_name=char_name, user_name=user_name, max_chars=4000, template_context=template_context)
                if not text:
                    continue
                insert_at = max(1, len(chat_messages) - depth)
                chat_messages.insert(insert_at, {"role": "system", "content": text})
    # post-history instructions (jailbreak/depth prompt) goes right before generation
    if isinstance(extras_for_phi, dict):
        phi = render_tavern_template(str(extras_for_phi.get("post_history_instructions") or "").strip(), char_name, user_name, template_context=template_context, phase="generate")
        if phi:
            chat_messages.append({"role": "system", "content": phi})
        post_world = select_world_info(
            extras_for_phi.get("world_info") or [],
            recent_text,
            char_name=char_name,
            user_name=user_name,
            position="post_history",
            max_chars=4000,
            template_context=template_context,
        )
        if post_world:
            chat_messages.append({"role": "system", "content": post_world})
        for block_text in prompt_block_texts(extras_for_phi, "post_history", char_name=char_name, user_name=user_name, template_context=template_context):
            chat_messages.append({"role": "system", "content": block_text})
        injections = collect_tavern_prompt_injections(
            extras_for_phi.get("world_info") or [],
            chat_messages,
            recent_text,
            char_name=char_name,
            user_name=user_name,
            template_context=template_context,
        )
        apply_tavern_prompt_injections(chat_messages, injections)
    if protocol == "anthropic":
        system_parts: list[str] = []
        anthropic_messages: list[dict] = []
        for msg in chat_messages:
            role = str(msg.get("role") or "").strip()
            value = str(msg.get("content") or "").strip()
            if not value:
                continue
            if role == "system":
                system_parts.append(value)
            elif role in {"user", "assistant"}:
                if anthropic_messages and anthropic_messages[-1].get("role") == role:
                    anthropic_messages[-1]["content"] = str(anthropic_messages[-1].get("content") or "") + "\n\n" + value
                else:
                    anthropic_messages.append({"role": role, "content": value})
        if not anthropic_messages or anthropic_messages[-1].get("role") != "user":
            anthropic_messages.append({"role": "user", "content": user_content})
        endpoint = base_url if base_url.endswith("/messages") else base_url + "/messages"
        payload = {
            "model": model,
            "system": "\n\n".join(system_parts),
            "messages": anthropic_messages,
            "temperature": max(0.0, min(1.0, temperature)),
            "max_tokens": 1024,
            "stream": False,
        }
        headers = {
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": LLM_UPSTREAM_USER_AGENT,
            "Origin": PUBLIC_BASE_URL,
            "Referer": PUBLIC_BASE_URL + "/",
        }
    else:
        endpoint = base_url if base_url.endswith("/chat/completions") else base_url + "/chat/completions"
        payload = {
            "model": model,
            "messages": chat_messages,
            "temperature": max(0.0, min(2.0, temperature)),
            "stream": False,
        }
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": LLM_UPSTREAM_USER_AGENT,
            "Origin": PUBLIC_BASE_URL,
            "Referer": PUBLIC_BASE_URL + "/",
        }
    if "top_p" in sampling and sampling["top_p"] is not None:
        try: payload["top_p"] = max(0.0, min(1.0, float(sampling["top_p"])))
        except Exception: pass
    if protocol != "anthropic" and "presence_penalty" in sampling and sampling["presence_penalty"] is not None:
        try: payload["presence_penalty"] = max(-2.0, min(2.0, float(sampling["presence_penalty"])))
        except Exception: pass
    if protocol != "anthropic" and "frequency_penalty" in sampling and sampling["frequency_penalty"] is not None:
        try: payload["frequency_penalty"] = max(-2.0, min(2.0, float(sampling["frequency_penalty"])))
        except Exception: pass
    return {
        "enabled": True,
        "protocol": protocol,
        "endpoint": endpoint,
        "headers": headers,
        "payload": payload,
        "fallback": fallback,
        "model": model,
    }


def call_user_llm(app: dict, content: str, messages: list[dict] | None = None, settings: dict | None = None, persona: dict | None = None, context: dict | None = None) -> str:
    request_info = build_user_llm_request(app, content, messages, settings, persona, context)
    char_name = str(app.get("name") or "Ta").strip() or "Ta"
    user_name = str((persona or {}).get("name") or "").strip() or "你"
    template_context = dict(context) if isinstance(context, dict) else {}
    template_context.setdefault("app", app)
    template_context.setdefault("app_id", str(app.get("id") or ""))
    if not request_info.get("enabled"):
        fallback = str(request_info.get("fallback") or build_chat_reply(content, char_name))
        return process_model_reply(app, fallback, char_name=char_name, user_name=user_name, template_context=template_context)
    endpoint = str(request_info.get("endpoint") or "")
    headers = request_info.get("headers") if isinstance(request_info.get("headers"), dict) else {}
    payload = request_info.get("payload") if isinstance(request_info.get("payload"), dict) else {}
    fallback = str(request_info.get("fallback") or build_chat_reply(content, str(app.get("name") or "Ta")))
    req = Request(endpoint, data=json_bytes(payload), method="POST", headers=headers)
    try:
        with urlopen(req, timeout=60) as resp:
            raw = resp.read()
        text = raw.decode("utf-8", errors="replace").strip()
        if not text:
            return process_model_reply(app, fallback, char_name=char_name, user_name=user_name, template_context=template_context)
        try:
            data = json.loads(text)
        except Exception:
            answer = extract_sse_answer(text)
            return process_model_reply(app, answer or fallback, char_name=char_name, user_name=user_name, template_context=template_context)
        answer = extract_upstream_chat_answer(data)
        return process_model_reply(app, answer or fallback, char_name=char_name, user_name=user_name, template_context=template_context)
    except Exception as exc:
        log(f"user llm failed for {app.get('id')}: {exc}")
        return process_model_reply(app, fallback, char_name=char_name, user_name=user_name, template_context=template_context)


def _image_ext_for_mime(mime: str) -> str:
    value = str(mime or "").split(";", 1)[0].strip().lower()
    return {
        "image/jpeg": ".jpg",
        "image/jpg": ".jpg",
        "image/png": ".png",
        "image/webp": ".webp",
        "image/gif": ".gif",
        "image/avif": ".avif",
    }.get(value, ".png")


def save_generated_image_blob(raw: bytes, mime: str = "image/png") -> str:
    if not raw:
        return ""
    base_dir = MEDIA_DIR or (DEFAULT_STATE_DIR / "media")
    dest_dir = base_dir / "generated"
    dest_dir.mkdir(parents=True, exist_ok=True)
    ext = _image_ext_for_mime(mime)
    name = safe_filename(f"image-{now_ms()}-{uuid.uuid4().hex[:8]}{ext}", "generated.png")
    dest = dest_dir / name
    dest.write_bytes(raw)
    return public_url(f"/media-cache/generated/{name}")


def save_generated_image_b64(value: str, mime: str = "image/png") -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    if text.startswith("data:"):
        match = re.match(r"^data:([^;,]+)[^,]*,([\s\S]+)$", text)
        if match:
            mime = match.group(1) or mime
            text = match.group(2)
    try:
        raw = base64.b64decode(text, validate=False)
    except Exception:
        return ""
    return save_generated_image_blob(raw, mime)


def extract_image_generation_items(payload: object) -> list[dict]:
    if not isinstance(payload, dict):
        return []
    raw_items = payload.get("data") or payload.get("images") or payload.get("result") or []
    if isinstance(raw_items, dict):
        raw_items = [raw_items]
    if isinstance(raw_items, str):
        raw_items = [{"url": raw_items}]
    if not isinstance(raw_items, list):
        return []
    out: list[dict] = []
    for item in raw_items:
        if isinstance(item, str):
            item = {"url": item}
        if not isinstance(item, dict):
            continue
        url = str(item.get("url") or item.get("image_url") or item.get("output_url") or "").strip()
        mime = str(item.get("mime_type") or item.get("mime") or "image/png").strip() or "image/png"
        b64 = str(item.get("b64_json") or item.get("base64") or item.get("image") or item.get("data_url") or "").strip()
        if not url and b64.startswith(("http://", "https://")):
            url, b64 = b64, ""
        local_url = ""
        if b64:
            local_url = save_generated_image_b64(b64, mime)
        final_url = local_url or url
        if final_url:
            out.append({
                "url": final_url,
                "remote_url": url if url and url != final_url else "",
                "mime": mime,
                "revised_prompt": str(item.get("revised_prompt") or item.get("prompt") or "").strip(),
            })
    return out


def call_image_model(prompt: str, settings: dict) -> dict:
    clean_prompt = str(prompt or "").strip()
    if not clean_prompt:
        raise ValueError("prompt is required")
    base_url = str(settings.get("base_url") or "").strip().rstrip("/")
    api_key = str(settings.get("api_key") or "").strip()
    model = str(settings.get("model") or "").strip()
    if not settings.get("enabled", True) or not base_url or not api_key or not model:
        raise ValueError("image model is not configured")
    endpoint_path = str(settings.get("endpoint_path") or "/images/generations").strip()
    if not endpoint_path.startswith("/"):
        endpoint_path = "/" + endpoint_path
    endpoint = base_url if base_url.endswith(endpoint_path) else base_url + endpoint_path
    payload = {
        "model": model,
        "prompt": clean_prompt,
        "n": _bounded_int(settings.get("n"), 1, 1, 4),
        "size": str(settings.get("size") or "1024x1024").strip() or "1024x1024",
    }
    quality = str(settings.get("quality") or "").strip()
    if quality:
        payload["quality"] = quality
    response_format = str(settings.get("response_format") or "").strip()
    if response_format in {"url", "b64_json"}:
        payload["response_format"] = response_format
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": LLM_UPSTREAM_USER_AGENT,
        "Origin": PUBLIC_BASE_URL,
        "Referer": PUBLIC_BASE_URL + "/",
    }
    req = Request(endpoint, data=json_bytes(payload), method="POST", headers=headers)
    with urlopen(req, timeout=_bounded_int(settings.get("timeout"), 90, 10, 300)) as resp:
        raw = resp.read()
    text = raw.decode("utf-8", errors="replace").strip()
    try:
        data = json.loads(text) if text else {}
    except Exception as exc:
        raise ValueError("image provider returned non-JSON response") from exc
    images = extract_image_generation_items(data)
    if not images:
        message = ""
        if isinstance(data, dict):
            err = data.get("error")
            if isinstance(err, dict):
                message = str(err.get("message") or "")
            message = message or str(data.get("message") or data.get("msg") or "")
        raise ValueError(message or "image provider returned no image")
    return {
        "images": images,
        "image_url": images[0].get("url") or "",
        "model": model,
        "provider": settings.get("name") or "图片模型",
        "raw_count": len(images),
    }


def extract_stream_delta(payload: object) -> str:
    if not isinstance(payload, dict):
        return ""
    delta = payload.get("delta") if isinstance(payload.get("delta"), dict) else {}
    for key in ("text", "content"):
        value = delta.get(key)
        if isinstance(value, str) and value:
            return value
    content_blocks = payload.get("content")
    if isinstance(content_blocks, list):
        parts: list[str] = []
        for block in content_blocks:
            if isinstance(block, dict):
                text = block.get("text") or block.get("content")
                if isinstance(text, str) and text:
                    parts.append(text)
            elif isinstance(block, str) and block:
                parts.append(block)
        if parts:
            return "".join(parts)
    choices = payload.get("choices")
    if isinstance(choices, list) and choices:
        choice = choices[0] if isinstance(choices[0], dict) else {}
        delta = choice.get("delta") if isinstance(choice.get("delta"), dict) else {}
        for key in ("content", "text"):
            value = delta.get(key)
            if isinstance(value, str) and value:
                return value
        message = choice.get("message") if isinstance(choice.get("message"), dict) else {}
        value = message.get("content")
        if isinstance(value, str) and value:
            return value
        value = choice.get("text")
        if isinstance(value, str) and value:
            return value
    for key in ("content", "text", "reply", "answer"):
        value = payload.get(key)
        if isinstance(value, str) and value:
            return value
    return ""


def chunk_text(text: str, size: int = 12):
    value = str(text or "")
    if not value:
        return
    for idx in range(0, len(value), size):
        yield value[idx:idx + size]


def _stream_event_is_terminal(event: object) -> bool:
    if not isinstance(event, dict):
        return False
    event_type = str(event.get("type") or event.get("event") or "").strip().lower()
    if event_type in {"message_stop", "response.completed", "response.done", "completion_end", "done"}:
        return True
    choices = event.get("choices")
    if isinstance(choices, list):
        return any(isinstance(choice, dict) and choice.get("finish_reason") is not None for choice in choices)
    return False


def stream_user_llm_chunks(app: dict, content: str, messages: list[dict] | None = None, settings: dict | None = None, persona: dict | None = None, context: dict | None = None, *, strict: bool = False):
    request_info = build_user_llm_request(app, content, messages, settings, persona, context)
    fallback = str(request_info.get("fallback") or build_chat_reply(content, str(app.get("name") or "Ta")))
    if not request_info.get("enabled"):
        yield from chunk_text(fallback)
        return
    endpoint = str(request_info.get("endpoint") or "")
    headers = request_info.get("headers") if isinstance(request_info.get("headers"), dict) else {}
    payload = dict(request_info.get("payload") if isinstance(request_info.get("payload"), dict) else {})
    payload["stream"] = True
    stream_headers = dict(headers)
    stream_headers["Accept"] = "text/event-stream"
    emitted = False
    completed = False
    try:
        req = Request(endpoint, data=json_bytes(payload), method="POST", headers=stream_headers)
        with urlopen(req, timeout=60) as resp:
            for raw_line in resp:
                line = raw_line.decode("utf-8", errors="replace").strip()
                if not line or line.startswith(":"):
                    continue
                if line.startswith("data:"):
                    line = line[5:].strip()
                if not line:
                    continue
                if line == "[DONE]":
                    completed = True
                    break
                try:
                    event = json.loads(line)
                except Exception:
                    continue
                delta = extract_stream_delta(event)
                if delta:
                    emitted = True
                    yield delta
                if _stream_event_is_terminal(event):
                    completed = True
    except Exception as exc:
        log(f"user llm stream failed for {app.get('id')}: {exc}")
        if strict:
            raise RuntimeError("模型流式响应失败，请重试") from exc
        if emitted:
            return
    if strict and emitted and not completed:
        raise RuntimeError("模型流式响应提前结束，请重试")
    if strict and not emitted:
        raise RuntimeError("模型没有返回有效内容，请重试")
    if not emitted:
        yield from chunk_text(fallback)


def chat_reply_for_app(store: "Store", user_id: str, app_id: str, content: str, *, app_name: str = "", conversation_id: str = "", response_mode: str = "", model_override: str = "") -> tuple[dict, str]:
    app_row = store.get_local_app(app_id)
    if app_row:
        app = dict(app_row)
        selected_model = store.public_model_selection(model_override)
        if selected_model:
            app["llm_model"] = selected_model
        llm_settings = store.effective_llm_settings(app, user_id=user_id)
        history = []
        if conversation_id:
            try:
                history = [dict(row) for row in store.list_messages(conversation_id, user_id, limit=100)]
            except Exception:
                history = []
        if selected_model or app.get("source") in ("user", "admin"):
            persona = store.get_persona(user_id)
            context = store.chat_context(user_id, app_id, conversation_id, content, history) if conversation_id else {}
            answer = call_user_llm(app, content, history, llm_settings, persona, context)
        else:
            answer = proxy_upstream_chat(store, app_id, content, app_name=app_name or str(app.get("name") or ""), conversation_id=conversation_id, response_mode=response_mode)
        return app, answer
    answer = build_chat_reply(content, app_name or app_name_from_cache(store, app_id))
    return {}, answer


def user_can_access_app(row: sqlite3.Row | dict | None, user_id: str) -> bool:
    if not row:
        return False
    data = dict(row)
    source = data.get("source") or "upstream"
    if source == "user":
        return bool(data.get("is_public", 1)) or (data.get("owner_user_id") == user_id)
    return source in ("admin", "upstream") or (data.get("status") or "published") == "published"


def group_history_for_llm(messages: list[dict]) -> list[dict]:
    history: list[dict] = []
    for msg in messages[-80:]:
        role = str(msg.get("role") or "")
        content = str(msg.get("content") or "").strip()
        if not content:
            continue
        if role == "user":
            history.append({"role": "user", "content": f"用户：{content}"})
        else:
            speaker = str(msg.get("speaker_name") or "角色").strip() or "角色"
            history.append({"role": "assistant", "content": f"{speaker}：{content}"})
    return history


def pick_group_member(group: dict, app_id: str = "") -> tuple[dict | None, int]:
    members = group.get("members") if isinstance(group, dict) else []
    if not isinstance(members, list) or not members:
        return None, 0
    if app_id:
        for idx, member in enumerate(members):
            if str(member.get("app_id") or "") == app_id:
                return member, idx
    idx = int(group.get("active_index") or 0) % len(members)
    return members[idx], idx


def generate_group_reply(store: "Store", user_id: str, group: dict, *, app_id: str = "", prompt: str = "") -> tuple[dict, dict, int]:
    member, idx = pick_group_member(group, app_id)
    if not member:
        raise ValueError("群聊没有可用角色")
    app_row = store.get_local_app(str(member.get("app_id") or ""))
    if not user_can_access_app(app_row, user_id):
        raise ValueError("角色不可用")
    app = local_app_to_card(dict(app_row))
    messages = store.list_group_messages(group["id"], user_id, limit=120)
    group_names = "、".join(str(m.get("app_name") or "") for m in group.get("members", []) if m.get("app_name"))
    last_user = prompt.strip()
    if not last_user:
        for msg in reversed(messages):
            if msg.get("role") == "user":
                last_user = str(msg.get("content") or "").strip()
                break
    target_name = app.get("name") or member.get("app_name") or "角色"
    content = (
        f"这是一个多人角色扮演群聊，群成员包括：{group_names}。\n"
        f"请只以「{target_name}」身份回复，不要代替其他角色或用户发言。\n"
        f"用户最新消息：{last_user or '请自然接续群聊'}"
    )
    persona = store.get_persona(user_id)
    history = group_history_for_llm(messages)
    context = store.chat_context(user_id, str(member.get("app_id") or ""), group["id"], content, history)
    answer = call_user_llm(app, content, history, store.effective_llm_settings(app, user_id=user_id), persona, context)
    reply = store.append_group_message(
        group["id"],
        user_id,
        "assistant",
        answer,
        speaker_app_id=str(member.get("app_id") or ""),
        speaker_name=str(target_name),
    )
    next_index = (idx + 1) % max(1, len(group.get("members") or [member]))
    store.update_group_active_index(group["id"], user_id, next_index)
    return reply, member, next_index


def regenerate_reply_for_app(store: "Store", user_id: str, app_id: str, *, history: list, last_user_content: str, app_name: str = "", conversation_id: str = "", model_override: str = "") -> tuple[dict, str]:
    """基于给定历史（不含待重生成的那条 assistant 消息）重新生成回复。"""
    app_row = store.get_local_app(app_id)
    if app_row:
        app = dict(app_row)
        selected_model = store.public_model_selection(model_override)
        if selected_model:
            app["llm_model"] = selected_model
        if selected_model or app.get("source") in ("user", "admin"):
            persona = store.get_persona(user_id)
            context = store.chat_context(user_id, app_id, conversation_id, last_user_content, history) if conversation_id else {}
            answer = call_user_llm(app, last_user_content, history, store.effective_llm_settings(app, user_id=user_id), persona, context)
            return app, answer
        answer = proxy_upstream_chat(store, app_id, last_user_content, app_name=app_name or str(app.get("name") or ""))
        return app, answer
    return {}, build_chat_reply(last_user_content, app_name or app_name_from_cache(store, app_id))



def proxy_upstream_chat(store: "Store", app_id: str, content: str, *, app_name: str = "", conversation_id: str = "", response_mode: str = "") -> str:
    body = {
        "app_id": app_id,
        "conversation_id": conversation_id or str(uuid.uuid4()),
        "content": content,
        "query": content,
        "app_name": app_name,
        "response_mode": response_mode or "blocking",
    }
    try:
        status, headers, raw = upstream_request(f"go/api/apps/{app_id}/chat-messages", "", "POST", json_bytes(body))
        text = raw.decode("utf-8", errors="replace")
        ctype = (headers.get("Content-Type") or headers.get("content-type") or "").lower()
        if "text/event-stream" in ctype:
            answer = extract_sse_answer(text)
        else:
            try:
                payload = json.loads(text)
            except Exception:
                answer = extract_sse_answer(text)
            else:
                answer = extract_upstream_chat_answer(payload)
        if answer:
            return answer
        log(f"upstream chat empty answer for {app_id}: status={status}")
    except Exception as exc:
        log(f"upstream chat failed for {app_id}: {exc}")
    return build_chat_reply(content, app_name or app_name_from_cache(store, app_id))


def extract_app_payload(payload: object) -> dict | None:
    if not isinstance(payload, dict):
        return None
    data = payload.get("data")
    if isinstance(data, dict):
        app = data.get("apps") or data.get("app")
        if isinstance(app, dict):
            return app
    app = payload.get("app")
    return app if isinstance(app, dict) else None


def app_name_from_cache(store: Store, app_id: str) -> str:
    for path in (f"go/api/apps/{app_id}", f"console/api/installed-apps/{app_id}"):
        cached = store.get_content_cache(content_cache_key("GET", path, "lang=zh-Hans"))
        if not cached:
            continue
        try:
            app = extract_app_payload(json.loads(cached["response_json"]))
        except Exception:
            app = None
        if isinstance(app, dict) and str(app.get("name") or "").strip():
            return str(app["name"]).strip()
    return "惑梦（Homer）角色"


def chat_message_payload(message: sqlite3.Row, conv_id: str, app_id: str, query: str, answer: str) -> dict:
    ts = message["created_at"] if "created_at" in message.keys() else now_ms()
    return {
        "id": message["id"],
        "message_id": message["id"],
        "conversation_id": conv_id,
        "app_id": app_id,
        "query": query,
        "answer": answer,
        "status": "succeeded",
        "error": None,
        "created_at": ts,
        "updated_at": ts,
        "message_tokens": max(1, len(query) // 2),
        "answer_tokens": max(1, len(answer) // 2),
        "message_points": 0,
        "answer_points": 0,
        "model_id": "ai-xingyue-local",
        "feedback": None,
    }


def row_value(row: sqlite3.Row | dict | None, key: str, default=None):
    if not row:
        return default
    if isinstance(row, dict):
        return row.get(key, default)
    try:
        return row[key]
    except Exception:
        return default


def admin_email_set() -> set[str]:
    return {e.strip().lower() for e in ADMIN_EMAILS if e and e.strip()}


def user_is_env_admin(user: sqlite3.Row | dict | None) -> bool:
    if not user:
        return False
    return str(row_value(user, "email", "") or "").strip().lower() in admin_email_set()


def user_is_db_admin(user: sqlite3.Row | dict | None) -> bool:
    try:
        return bool(int(row_value(user, "is_admin", 0) or 0))
    except Exception:
        return False


def is_admin(user: sqlite3.Row | None) -> bool:
    return user_is_env_admin(user) or user_is_db_admin(user)


def admin_source(user: sqlite3.Row | dict | None) -> str:
    if user_is_env_admin(user):
        return "env"
    if user_is_db_admin(user):
        return "database"
    return "none"


def admin_user_json(user: sqlite3.Row | dict) -> dict:
    data = dict(user)
    source = admin_source(data)
    data["is_admin"] = source != "none"
    data["admin_source"] = source
    data["can_toggle_admin"] = source != "env"
    data["balance"] = credit_balance_json(data)
    return data


def daily_count_series(conn: sqlite3.Connection, table: str, time_column: str, days: int = 7) -> list[dict]:
    day_ms = 86400000
    offset_ms = 8 * 3600000
    current_day = (now_ms() + offset_ms) // day_ms
    start_day = current_day - max(1, days) + 1
    series: list[dict] = []
    for idx in range(max(1, days)):
        start_ms = (start_day + idx) * day_ms - offset_ms
        end_ms = start_ms + day_ms
        label = time.strftime("%m-%d", time.gmtime((start_ms + offset_ms) / 1000))
        value = conn.execute(
            f"select count(*) from {table} where {time_column}>=? and {time_column}<?",
            (start_ms, end_ms),
        ).fetchone()[0]
        series.append({"label": label, "value": int(value or 0)})
    return series


def parse_query_int(query: str, key: str, default: int, low: int = 1, high: int = 100000) -> int:
    try:
        params = parse_qs(query)
        value = int(params.get(key, [str(default)])[0])
    except (ValueError, TypeError):
        return default
    return max(low, min(high, value))


def parse_query_str(query: str, key: str, default: str = "") -> str:
    params = parse_qs(query)
    return params.get(key, [default])[0]


def profile_json(user: sqlite3.Row) -> dict:
    gender = user["gender"] if "gender" in user.keys() else 0
    name = user["name"]
    display_id = ""
    if "display_id" in user.keys():
        display_id = (user["display_id"] or "").strip()
    avatar_url = ""
    if "avatar_url" in user.keys():
        avatar_url = (user["avatar_url"] or "").strip()
    if avatar_url and avatar_url.startswith("/"):
        avatar_url = public_url(avatar_url)
    if not avatar_url:
        avatar_url = DEFAULT_AVATAR_URL
    return {
        "id": user["id"],
        "display_id": display_id,
        "public_id": display_id,
        "custom_id": display_id,
        "name": name,
        "nickname": name,
        "user_name": name,
        "username": name,
        "display_name": name,
        "avatar": avatar_url,
        "avatar_url": avatar_url,
        "email": user["email"],
        "is_new_user": False,
        "is_password_set": True,
        "interface_language": "zh-Hans",
        "interface_theme": "system",
        "timezone": "Asia/Shanghai",
        "last_login_at": now_ms(),
        "last_login_ip": "127.0.0.1",
        "created_at": user["created_at"],
        "sign_reminder_enabled": False,
        "extend": {
            "mask_words": [],
            "enable_r18g": False,
            "favorite_tags": [],
            "gender_options": gender,
            "gender_preference": gender,
            "gender_updated_at": str(now_ms()),
            "is_admin": False,
            "my_search": [],
            "enable_comment_notice": False,
            "sign_reminder_enabled": False,
            "has_horse_year_emoji": False,
            "has_sign_in_emoji": False,
            "show_given_tips": True,
            "show_received_tips": True,
            "show_tipping_switch": True,
            "enable_anonymous": False,
            "hide_refresh_confirm": False,
        },
        "gender": gender,
        "follow_count": 0,
        "following_count": 0,
        "fans_count": 0,
        "follower_count": 0,
        "app_count": 0,
        "apps_count": 0,
        "post_count": 0,
        "posts_count": 0,
        "short_link": "",
        "nav_r18_short_link": "",
        "nav_all_age_short_link": "",
    }


def points_json(user: sqlite3.Row) -> dict:
    ts = now_ms()
    balance = credit_balance_json(user)
    return {
        "id": "local-points-" + user["id"],
        "user_id": user["id"],
        "user_name": user["name"],
        "points": str(balance["points"]),
        "available_points": str(balance["points"]),
        "free_points": balance["free_points"],
        "paid_points": balance["paid_points"],
        "reward_points": balance["reward_points"],
        "normal_points": balance["normal_points"],
        "regular_points": balance["regular_points"],
        "total_points": balance["total_points"],
        "balance": balance,
        "updated_at": ts,
        "expired_at": None,
        "created_at": user["created_at"],
        "deleted_at": None,
        "status": "active",
    }


def credit_balance_json(user: sqlite3.Row | dict) -> dict:
    def get_int(name: str) -> int:
        try:
            return int(user[name] or 0)
        except Exception:
            return 0

    free = get_int("free_points")
    paid = get_int("paid_points")
    reward = get_int("reward_points")
    total = free + paid + reward
    if total <= 0:
        total = get_int("points")
        free = total
    return {
        "free_points": free,
        "paid_points": paid,
        "reward_points": reward,
        "normal_points": paid,
        "regular_points": paid,
        "total_points": total,
        "points": total,
    }


def redeem_code_status(item: sqlite3.Row | dict, ts: int | None = None) -> str:
    now = ts or now_ms()

    def get(name: str):
        try:
            return item[name]
        except Exception:
            return None

    if get("redeemed_at"):
        return "used"
    if get("disabled_at"):
        return "disabled"
    expires_at = get("expires_at")
    try:
        if expires_at and int(expires_at) < now:
            return "expired"
    except Exception:
        pass
    return "unused"


def deposit_meta_json(user: sqlite3.Row | None = None) -> dict:
    settings = ACTIVE_STORE.site_settings() if ACTIVE_STORE is not None else site_settings_defaults()
    deposit = settings.get("deposit") if isinstance(settings.get("deposit"), dict) else site_settings_defaults()["deposit"]
    aifadian_url = str(deposit.get("aifadian_url") or AIFADIAN_URL or "").strip()
    if not PAYMENT_CHANNEL_ENABLED:
        return {
            "mode": "closed",
            "channel_enabled": False,
            "aifadian_url": "",
            "payment_available": False,
            "redeem_available": False,
            "currency": deposit.get("currency") or "CNY",
            "credits_name": deposit.get("credits_name") or "惑梦币",
            "rate_label": "充值通道暂时关闭",
            "title": "充值通道维护中",
            "description": "充值和兑换入口暂时关闭，已有余额、每日奖励和聊天功能不受影响。",
            "button_text": "通道维护中",
            "redeem_button_text": "暂不可兑换",
            "redeem_placeholder": "",
            "packages": [],
            "subscriptions_title": "月度订阅",
            "subscriptions_note": "充值通道恢复后再开放额度包。",
            "subscriptions": [],
            "steps": ["充值通道维护中，暂不开放购买和兑换。"],
            "support_text": "充值通道暂时关闭，恢复后会重新开放购买和兑换。",
            "payment_note_available": "",
            "payment_note_unavailable": "充值通道暂时关闭，恢复后会重新开放购买和兑换。",
            "balance": credit_balance_json(user) if user is not None else None,
        }
    return {
        "mode": "aifadian_redeem_code",
        "channel_enabled": True,
        "aifadian_url": aifadian_url,
        "payment_available": bool(aifadian_url),
        "redeem_available": True,
        "currency": deposit.get("currency") or "CNY",
        "credits_name": deposit.get("credits_name") or "惑梦币",
        "rate_label": deposit.get("rate_label") or "1 CNY = 1000 惑梦币，50 惑梦币约等于 1 次角色回复",
        "title": deposit.get("title") or "爱发电购买兑换码",
        "description": deposit.get("description") or "付款后把兑换码输入到这里，额度立即到账并同步到 APK。",
        "button_text": deposit.get("button_text") or "去爱发电购买",
        "redeem_button_text": deposit.get("redeem_button_text") or "兑换额度",
        "redeem_placeholder": deposit.get("redeem_placeholder") or "XY-XXXX-XXXX-XXXX-XXXX",
        "packages": deposit.get("packages") or [],
        "subscriptions_title": deposit.get("subscriptions_title") or "月度订阅",
        "subscriptions_note": deposit.get("subscriptions_note") or "订阅为月度额度包，不承诺无限使用；额度用完后可继续兑换积分包。",
        "subscriptions": deposit.get("subscriptions") or [],
        "steps": deposit.get("steps") or [],
        "support_text": deposit.get("support_text") or "如果没有看到购买链接，请联系站长获取兑换码。",
        "payment_note_available": deposit.get("payment_note_available") or "爱发电购买完成后，使用站长发放的兑换码在本页到账。",
        "payment_note_unavailable": deposit.get("payment_note_unavailable") or "暂未配置购买链接，请联系站长获取兑换码。",
        "balance": credit_balance_json(user) if user is not None else None,
    }


def public_site_settings_json(settings: dict) -> dict:
    public = json.loads(json.dumps(settings if isinstance(settings, dict) else site_settings_defaults(), ensure_ascii=False))
    home = public.setdefault("home", {})
    app = public.setdefault("app", {})
    dashboard = public.setdefault("dashboard", {})
    if not APK_DOWNLOAD_ENABLED:
        home["primary_cta_href"] = "/app/login.html?next=%2Fapp%2F"
        home["download_title"] = "网页端暂时开放"
        home["download_subtitle"] = "APK 下载渠道维护中，请先使用 Web App。"
        home["download_button_text"] = "打开 Web App"
        home["download_facts"] = []
        home["download_note"] = "APK 下载渠道暂时关闭。已有账号、角色聊天和后台管理功能保持可用。"
        faq_items = home.get("faq_items")
        if isinstance(faq_items, list):
            for item in faq_items:
                if not isinstance(item, dict):
                    continue
                question = str(item.get("q") or "")
                if "积分" in question:
                    item["a"] = "积分用于消耗调用 AI 模型生成内容。每日签到可获得额外积分，充值通道维护期间暂不开放购买和兑换。"
                if "安装" in question or "风险" in question:
                    item["a"] = "APK 下载渠道暂时关闭，请先使用 Web App。"
                if "忘记密码" in question or "密码" in question:
                    item["a"] = "在登录页点击「忘记密码」，输入注册邮箱获取验证码后即可设置新密码。验证码 10 分钟内有效。"
        app["info_download_button_text"] = "打开 Web App"
        app["info_eyebrow"] = "惑梦（Homer） Web 同步状态"
        app["info_title"] = "网页端\n同账号 · 同积分 · 同角色库。"
        dashboard["download_title"] = "打开 Web App"
        dashboard["download_subtitle"] = "客户端渠道维护中"
    if not PAYMENT_CHANNEL_ENABLED:
        dashboard["purchase_section_label"] = "充值通道"
        dashboard["aifadian_missing_text"] = "充值通道暂时关闭"
        feature_cards = home.get("feature_cards")
        if isinstance(feature_cards, list):
            for item in feature_cards:
                if not isinstance(item, dict):
                    continue
                title = str(item.get("title") or "")
                description = str(item.get("description") or "")
                if "积分" in title or "充值" in description:
                    item["title"] = "每日奖励"
                    item["description"] = "注册即赠 2500 积分，约 50 次角色回复；每日签到获得额外积分，已有额度网页与客户端共用。"
        deposit = public.setdefault("deposit", {})
        deposit.update({
            "aifadian_url": "",
            "title": "充值通道维护中",
            "description": "充值和兑换入口暂时关闭，已有余额、每日奖励和聊天功能不受影响。",
            "button_text": "通道维护中",
            "redeem_button_text": "暂不可兑换",
            "redeem_placeholder": "",
            "support_text": "充值通道暂时关闭，恢复后会重新开放购买和兑换。",
            "payment_note_available": "",
            "payment_note_unavailable": "充值通道暂时关闭，恢复后会重新开放购买和兑换。",
            "packages": [],
            "subscriptions": [],
            "steps": ["充值通道维护中，暂不开放购买和兑换。"],
        })
    return public


def workspace_json() -> dict:
    return {
        "id": "local-workspace",
        "android_apk_versions": None,
        "name": "惑梦（Homer） 本地服务器",
        "plan": "local",
        "status": "active",
        "created_at": now_ms(),
        "role": "owner",
        "in_trial": "false",
        "trial_end_reason": "",
        "custom_config": "{}",
        "app_title": "惑梦（Homer）",
        "android_apk": None,
        "win_installer": "",
        "app_icon": "",
        "app_logo": "",
        "cld_guide": "",
        "official_x": "",
        "discussion_group": [],
        "telegram_community": "",
        "forum_feedback": "",
        "bbs_url": "",
        "cld_guide_pdf": "",
        "discord_community": "",
        "official_communities": "",
        "payment_channels": [],
        "recommend_model": None,
    }


def app_config_json(app_id: str = "local-app") -> dict:
    return {
        "id": app_id,
        "name": "本地角色",
        "description": "Local backend placeholder app.",
        "mode": "chat",
        "icon": "",
        "icon_background": "#222222",
        "enable_site": False,
        "enable_api": True,
        "model_config": None,
        "site": None,
        "api_base_url": "",
        "created_at": now_ms(),
        "deleted_tools": [],
        "cover": "",
        "summary": "本地数据源",
        "pre_text": "",
        "post_text": "",
        "installed_app": None,
        "is_public": True,
        "is_anonymous": False,
        "bbs_link": "",
        "author": None,
        "gender": 0,
        "api_base_url": "",
    }


def upstream_request(path: str, query: str, method: str = "GET", body: bytes | None = None) -> tuple[int, dict, bytes]:
    url = UPSTREAM_CONTENT_BASE.rstrip("/") + "/" + path.lstrip("/")
    if query:
        url += "?" + query
    headers = {
        "User-Agent": "ai_chat/1.12.20 (org.nebula.horizon.composeai; build:260; Android 13; SDK 33; google sdk_gphone64_x86_64) OkHttp",
        "X-Language": "zh-Hans",
        "locale": "zh-Hans",
        "Cookie": "locale=zh-Hans",
        "Accept": "application/json, text/plain, */*",
    }
    if body is not None:
        headers["Content-Type"] = "application/json; charset=utf-8"
    req = Request(url, data=body, method=method, headers=headers)
    with urlopen(req, timeout=20) as resp:
        return resp.status, dict(resp.headers.items()), resp.read()


def upstream_url(path: str, query: str) -> str:
    url = UPSTREAM_CONTENT_BASE.rstrip("/") + "/" + path.lstrip("/")
    if query:
        url += "?" + query
    return url


def proxy_json(path: str, query: str, fallback: object | None = None) -> object:
    store = ACTIVE_STORE
    cache_key = content_cache_key("GET", path, query)
    if store is not None:
        cached = store.get_content_cache(cache_key)
        if cached:
            try:
                return rewrite_image_urls(rewrite_media_urls(rebrand_data(json.loads(cached["response_json"]))))
            except Exception as exc:
                log(f"content cache decode failed for {cache_key}: {exc}")
    if CONTENT_MODE in ("local", "local_only", "offline"):
        payload = rebrand_data(fallback) if fallback is not None else {"result": "success", "code": "200", "message": "OK", "status": 200, "data": []}
        return rewrite_image_urls(rewrite_media_urls(payload))
    try:
        status, headers, raw = upstream_request(path, query)
        if 200 <= status < 300 and raw:
            text = raw.decode("utf-8", errors="replace").strip()
            if text:
                try:
                    payload = rewrite_image_urls(rewrite_media_urls(rebrand_data(json.loads(text))))
                    if store is not None:
                        store.set_content_cache(cache_key, "GET", path.lstrip("/"), query, status, payload, len(raw), upstream_url(path, query))
                    return payload
                except Exception:
                    if fallback is not None:
                        return rewrite_image_urls(rewrite_media_urls(rebrand_data(fallback)))
                    return rewrite_image_urls(rewrite_media_urls({"result": "success", "code": "200", "message": "OK", "status": 200, "data": rebrand_text(text)}))
    except Exception as exc:
        log(f"upstream proxy failed for {path}: {exc}")
    payload = rebrand_data(fallback) if fallback is not None else {"result": "success", "code": "200", "message": "OK", "status": 200, "data": []}
    return rewrite_image_urls(rewrite_media_urls(payload))


def normalize_app_site_list_response(value: object) -> object:
    if not isinstance(value, dict):
        return value
    data = value.get("data")
    if isinstance(data, dict) and "list" not in data:
        list_value = data.get("installed_apps") or data.get("apps") or data.get("items") or []
        data["list"] = list_value if isinstance(list_value, list) else []
        data.setdefault("installed_apps", data["list"])
        data.setdefault("apps", data["list"])
        data.setdefault("items", data["list"])
        data.setdefault("total", len(data["list"]))
    return value


def normalize_data_array_response(value: object) -> object:
    if not isinstance(value, dict):
        return value
    data = value.get("data")
    if isinstance(data, list):
        return value
    if isinstance(data, dict):
        for key in ("list", "items", "apps", "records"):
            items = data.get(key)
            if isinstance(items, list):
                value["data"] = items
                return value
    value["data"] = []
    return value


def clean_tts_text(value: object) -> str:
    text = str(value or "")
    text = re.sub(r"<script[\s\S]*?</script>|<style[\s\S]*?</style>", " ", text, flags=re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"```[\s\S]*?```", " ", text)
    text = re.sub(r"\[[^\]]+\]\([^\)]+\)", " ", text)
    text = re.sub(r"[*_#>`~]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()[:TTS_MAX_CHARS]


def synthesize_edge_tts(text: str, voice_id: str, rate: str = "+0%", pitch: str = "+0Hz") -> tuple[str, bool]:
    if MEDIA_DIR is None:
        raise RuntimeError("media dir not ready")
    allowed = {item["id"] for item in TTS_VOICES}
    voice = voice_id if voice_id in allowed else TTS_VOICES[0]["id"]
    rate = rate if re.fullmatch(r"[+-]\d{1,2}%", str(rate or "")) else "+0%"
    pitch = pitch if re.fullmatch(r"[+-]\d{1,2}Hz", str(pitch or "")) else "+0Hz"
    key = hashlib.sha256(f"edge|{voice}|{rate}|{pitch}|{text}".encode("utf-8")).hexdigest()
    dest_dir = MEDIA_DIR / "tts"
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / f"{key}.mp3"
    cached = dest.exists() and dest.stat().st_size > 512
    if not cached:
        tmp = dest.with_suffix(".tmp.mp3")
        cmd = [
            shutil.which("edge-tts") or "edge-tts", "--voice", voice,
            f"--rate={rate}", f"--pitch={pitch}", "--text", text, "--write-media", str(tmp),
        ]
        try:
            subprocess.run(cmd, check=True, timeout=45, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
            if not tmp.exists() or tmp.stat().st_size <= 512:
                raise RuntimeError("TTS returned empty audio")
            tmp.replace(dest)
        finally:
            if tmp.exists():
                tmp.unlink(missing_ok=True)
    return public_url(f"/media-cache/tts/{dest.name}"), cached


class Handler(BaseHTTPRequestHandler):
    server_version = "AIFengyueLocal/1.0"
    protocol_version = "HTTP/1.0"

    def do_GET(self) -> None:
        self.handle_any()

    def do_POST(self) -> None:
        self.handle_any()

    def do_PUT(self) -> None:
        self.handle_any()

    def do_PATCH(self) -> None:
        self.handle_any()

    def do_DELETE(self) -> None:
        self.handle_any()

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, PATCH, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.send_header("Access-Control-Max-Age", "86400")
        self.send_header("Content-Length", "0")
        self.end_headers()
        self.close_connection = True

    def log_message(self, fmt: str, *args) -> None:
        log("%s - %s" % (self.client_address[0], fmt % args))

    def client_ip(self) -> str:
        forwarded = self.headers.get("X-Forwarded-For", "")
        if forwarded:
            first = forwarded.split(",", 1)[0].strip()
            if first:
                return first[:80]
        real_ip = self.headers.get("X-Real-IP", "").strip()
        if real_ip:
            return real_ip[:80]
        return (self.client_address[0] if self.client_address else "")[:80]

    def client_connection_closed(self, wait_seconds: float = 0.0) -> bool:
        connection = getattr(self, "connection", None)
        if connection is None:
            return True
        try:
            readable, _, _ = select.select([connection], [], [], max(0.0, float(wait_seconds or 0.0)))
            if not readable:
                return False
            return connection.recv(1, socket.MSG_PEEK) == b""
        except (BlockingIOError, InterruptedError):
            return False
        except Exception as exc:
            return is_client_disconnect_error(exc)

    @property
    def store(self) -> Store:
        return self.server.store

    @property
    def verification_store(self) -> "VerificationStore":
        return self.server.verification_store

    def authenticated_user(self) -> sqlite3.Row:
        auth = self.headers.get("Authorization") or self.headers.get("authorization")
        user_id = user_id_from_token(auth)
        if user_id:
            user = self.store.get_user_by_id(user_id)
            if user:
                return user
        return self.store.current_user()

    def authenticated_token_user(self) -> sqlite3.Row | None:
        auth = self.headers.get("Authorization") or self.headers.get("authorization")
        user_id = user_id_from_token(auth)
        if not user_id:
            return None
        return self.store.get_user_by_id(user_id)

    def read_body(self) -> tuple[str, object]:
        length = int(self.headers.get("Content-Length", "0") or "0")
        raw = self.rfile.read(length) if length else b""
        text = raw.decode("utf-8", errors="replace")
        if not text:
            return text, {}
        try:
            return text, json.loads(text)
        except json.JSONDecodeError:
            return text, parse_qs(text)

    def send_json(self, status: int, payload: object) -> None:
        data = json_bytes(payload)
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Connection", "close")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.end_headers()
        self.wfile.write(data)
        self.wfile.flush()
        self.close_connection = True

    def send_text(self, status: int, text: str) -> None:
        data = text.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(data)
        self.wfile.flush()
        self.close_connection = True

    def send_sse(self, status: int, events: list[dict]) -> None:
        chunks = []
        for event in events:
            name = event.get("event")
            data = event.get("data")
            if name:
                chunks.append(f"event: {name}\n")
            chunks.append("data: " + json.dumps(data, ensure_ascii=False, separators=(",", ":")) + "\n\n")
        raw = "".join(chunks).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "close")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)
        self.wfile.flush()
        self.close_connection = True

    def send_sse_headers(self, status: int = 200) -> None:
        self.send_response(status)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache, no-transform")
        self.send_header("Connection", "close")
        self.send_header("X-Accel-Buffering", "no")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.end_headers()

    def write_sse_event(self, event: str, data: object) -> None:
        chunk = ""
        if event:
            chunk += f"event: {event}\n"
        chunk += "data: " + json.dumps(data, ensure_ascii=False, separators=(",", ":")) + "\n\n"
        self.wfile.write(chunk.encode("utf-8"))
        self.wfile.flush()

    def send_file(self, status: int, path: Path, content_type: str) -> None:
        raw = path.read_bytes()
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "public, max-age=604800")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(raw)
        self.wfile.flush()
        self.close_connection = True

    def handle_local_cover(self, path: str) -> None:
        # /media-cache/<relative-path>
        rel = path.removeprefix("/media-cache/").strip("/")
        if not rel or ".." in rel or rel.startswith("/"):
            self.send_text(400, "bad path")
            return
        if MEDIA_DIR is None:
            self.send_text(404, "not found")
            return
        fpath = MEDIA_DIR / rel
        try:
            fpath.resolve().relative_to(MEDIA_DIR.resolve())
        except ValueError:
            self.send_text(400, "bad path")
            return
        if not fpath.exists() or not fpath.is_file():
            self.send_text(404, "not found")
            return
        ext = fpath.suffix.lower()
        ctype = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
                 ".webp": "image/webp", ".avif": "image/avif", ".gif": "image/gif",
                 ".mp3": "audio/mpeg", ".wav": "audio/wav", ".ogg": "audio/ogg"}.get(ext, "application/octet-stream")
        self.send_file(200, fpath, ctype)

    def handle_image_proxy(self, query: str) -> None:
        params = parse_qs(query)
        raw_url = (params.get("u") or params.get("url") or [""])[0]
        target = unquote(raw_url).strip()
        # 仅允许代理图片白名单域名，防止 SSRF
        allowed = ("catai.wiki", "static.catai.wiki", "image.catai.wiki",
                   "user.catai.wiki", "aifun.wiki", "img.catai.wiki")
        host_ok = False
        try:
            host = urlparse(target).hostname or ""
            host_ok = any(host == d or host.endswith("." + d) for d in allowed)
        except Exception:
            host_ok = False
        if not target.startswith("https://") or not host_ok:
            self.send_text(400, "bad image url")
            return
        try:
            req = Request(target, headers={
                "User-Agent": "Mozilla/5.0",
                "Referer": "https://aifun.wiki/",
                "Accept": "image/avif,image/webp,image/png,image/*,*/*",
            })
            with urlopen(req, timeout=20) as resp:
                ctype = resp.headers.get("Content-Type", "image/jpeg")
                raw = resp.read()
            self.send_response(200)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(raw)))
            self.send_header("Cache-Control", "public, max-age=604800")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Connection", "close")
            self.end_headers()
            self.wfile.write(raw)
            self.wfile.flush()
        except Exception as exc:
            log(f"image proxy failed for {target}: {exc}")
            self.send_text(502, "image fetch failed")
        finally:
            self.close_connection = True

    def handle_web_chat_stream(self, body: object) -> None:
        user = self.authenticated_user()
        if not user:
            self.send_json(401, error_response("unauthorized", 401))
            return
        if not isinstance(body, dict):
            self.send_json(400, error_response("invalid body"))
            return
        app_id = str(body.get("app_id") or "").strip()
        conv_id = str(body.get("conversation_id") or "").strip()
        content = str(body.get("content") or "").strip()
        model_override = self.store.public_model_selection(body.get("model_id") or body.get("llm_model"))
        if not app_id or not content:
            self.send_json(400, error_response("app_id and content are required"))
            return
        app_id = self.store.resolve_local_app_id(app_id)
        try:
            self.store.require_credit_points(user["id"], CHAT_MESSAGE_COST)
        except ValueError as exc:
            self.send_json(402, error_response(str(exc), 402))
            return
        app_name = str(body.get("app_name") or "")
        app_icon = str(body.get("app_icon") or "")
        if not conv_id:
            conv_id = str(uuid.uuid4())
        title = content[:30] if not body.get("conversation_id") else None
        conversation_existed = bool(self.store.get_conversation(conv_id, user["id"]))
        try:
            slot = GENERATION_LIMITER.acquire(user["id"], self.client_ip(), "web_chat_stream")
            slot.__enter__()
        except GenerationLimitError as exc:
            self.send_json(429, error_response(str(exc), 429))
            return
        user_message_id = ""
        reply_message_id = ""
        charged = False
        try:
            self.send_sse_headers(200)
            self.write_sse_event("start", {"conversation_id": conv_id, "app_id": app_id})
            self.store.upsert_conversation(
                conv_id,
                user["id"],
                app_id,
                app_name=app_name,
                app_icon=app_icon,
                title=title,
            )
            user_row = self.store.append_message(conv_id, user["id"], "user", content)
            user_message_id = str(user_row["id"])
            self.store.log_event(user["id"], "chat", f"与 {app_name or app_id} 对话", {"app_id": app_id, "conversation_id": conv_id})
            app_row = self.store.get_local_app(app_id)
            app = dict(app_row) if app_row else {}
            reply_parts: list[str] = []
            persona = self.store.get_persona(user["id"]) if app else {}
            context = {}
            if app and model_override:
                app["llm_model"] = model_override
            if app and (model_override or app.get("source") in ("user", "admin")):
                try:
                    history = [dict(row) for row in self.store.list_messages(conv_id, user["id"], limit=100)]
                except Exception:
                    history = []
                settings = self.store.effective_llm_settings(app, user_id=user["id"])
                context = self.store.chat_context(user["id"], app_id, conv_id, content, history)
                chunks = stream_user_llm_chunks(app, content, history, settings, persona, context, strict=True)
            else:
                app_row, reply = chat_reply_for_app(
                    self.store,
                    user["id"],
                    app_id,
                    content,
                    app_name=app_name,
                    conversation_id=conv_id,
                    response_mode="streaming",
                    model_override=model_override,
                )
                app = dict(app_row) if app_row else app
                chunks = chunk_text(str(reply or ""))
            if app:
                raw_reply = "".join(str(chunk) for chunk in chunks if chunk)
                if not raw_reply.strip():
                    raise RuntimeError("模型没有返回有效内容，请重试")
                reply_text = process_model_reply(
                    app,
                    raw_reply,
                    char_name=str(app.get("name") or app_name or "Ta"),
                    user_name=str((persona or {}).get("name") or "你"),
                    template_context=context,
                )
                if not str(reply_text or "").strip():
                    raise RuntimeError("模型回复处理后为空，请重试")
                if self.client_connection_closed():
                    raise ConnectionAbortedError("client disconnected")
                for chunk in chunk_text(reply_text):
                    reply_parts.append(str(chunk))
                    self.write_sse_event("delta", {"content": str(chunk)})
            else:
                for chunk in chunks:
                    if not chunk:
                        continue
                    reply_parts.append(str(chunk))
                    self.write_sse_event("delta", {"content": str(chunk)})
                reply_text = "".join(reply_parts)
                if not reply_text.strip():
                    raise RuntimeError("模型没有返回有效内容，请重试")
                if self.client_connection_closed():
                    raise ConnectionAbortedError("client disconnected")
            if self.client_connection_closed(0.05):
                raise ConnectionAbortedError("client disconnected")
            reply_row = self.store.append_message(conv_id, user["id"], "assistant", reply_text)
            reply_message_id = str(reply_row["id"])
            charge = self.store.spend_credit_points(
                user["id"],
                CHAT_MESSAGE_COST,
                payload={"app_id": app_id, "conversation_id": conv_id, "message_id": reply_row["id"]},
            )
            charged = True
            try:
                self.store.maybe_refresh_summary(user["id"], conv_id)
            except Exception as exc:
                log(f"auto summary refresh failed for {conv_id}: {exc}")
            payload = {
                "conversation_id": conv_id,
                "message_id": reply_row["id"],
                "reply": reply_text,
                "created_at": reply_row["created_at"],
                **charge,
            }
            if app:
                effective = self.store.effective_llm_settings(app, user_id=user["id"])
                payload["app_name"] = app.get("name") or app_name
                payload["model_id"] = effective.get("model") or app.get("llm_model") or USER_LLM_MODEL
                payload["model_preset_id"] = effective.get("preset_id") or app.get("llm_model") or ""
            self.write_sse_event("message_end", payload)
        except Exception as exc:
            disconnected = is_client_disconnect_error(exc)
            if reply_message_id and not charged:
                try:
                    self.store.delete_message(reply_message_id, user["id"])
                except Exception as cleanup_exc:
                    log(f"web chat reply cleanup failed for {reply_message_id}: {cleanup_exc}")
            if user_message_id and not charged:
                try:
                    self.store.delete_message(user_message_id, user["id"])
                except Exception as cleanup_exc:
                    log(f"web chat user cleanup failed for {user_message_id}: {cleanup_exc}")
            if not conversation_existed and not charged:
                try:
                    self.store.delete_empty_conversation(conv_id, user["id"])
                except Exception as cleanup_exc:
                    log(f"web chat empty conversation cleanup failed for {conv_id}: {cleanup_exc}")
            if disconnected:
                log(f"web chat stream client disconnected for conversation {conv_id}")
            else:
                log(f"web chat stream failed: {exc}")
                try:
                    self.write_sse_event("error", {"message": str(exc)[:500] or "stream failed"})
                except Exception as write_exc:
                    if not is_client_disconnect_error(write_exc):
                        log(f"web chat stream error event failed: {write_exc}")
        finally:
            slot.__exit__(None, None, None)
            self.close_connection = True

    def handle_web_chat_continue_stream(self, body: object) -> None:
        user = self.authenticated_user()
        if not user:
            self.send_json(401, error_response("unauthorized", 401))
            return
        if not isinstance(body, dict):
            self.send_json(400, error_response("invalid body"))
            return
        conv_id = str(body.get("conversation_id") or "").strip()
        if not conv_id:
            self.send_json(400, error_response("conversation_id is required"))
            return
        conversation = self.store.get_conversation(conv_id, user["id"])
        if not conversation:
            self.send_json(404, error_response("conversation not found", 404))
            return
        history = self.store.list_messages(conv_id, user["id"], limit=100)
        last_message = history[-1] if history else None
        if not last_message or str(last_message.get("role") or "") != "assistant":
            self.send_json(409, error_response("最后一条消息不是角色回复，无法续写", 409))
            return
        app_id = self.store.resolve_local_app_id(str(conversation.get("app_id") or ""))
        app_row = self.store.get_local_app(app_id)
        if not app_row or not user_can_access_app(app_row, user["id"]):
            self.send_json(404, error_response("role not found", 404))
            return
        try:
            self.store.require_credit_points(user["id"], CHAT_MESSAGE_COST)
        except ValueError as exc:
            self.send_json(402, error_response(str(exc), 402))
            return
        try:
            slot = GENERATION_LIMITER.acquire(user["id"], self.client_ip(), "web_chat_continue_stream")
            slot.__enter__()
        except GenerationLimitError as exc:
            self.send_json(429, error_response(str(exc), 429))
            return
        reply_message_id = ""
        charged = False
        try:
            self.send_sse_headers(200)
            self.write_sse_event("start", {"conversation_id": conv_id, "app_id": app_id, "mode": "continue"})
            app = dict(app_row)
            model_override = self.store.public_model_selection(body.get("model_id") or body.get("llm_model"))
            if model_override:
                app["llm_model"] = model_override
            persona = self.store.get_persona(user["id"])
            instruction = (
                "请从上一条角色回复的结尾自然继续写下去。不要复述、总结或改写上一条内容，"
                "不要提到这条续写指令，也不要替用户发言；直接输出紧接上一段的新内容。"
            )
            context = self.store.chat_context(user["id"], app_id, conv_id, instruction, history)
            settings = self.store.effective_llm_settings(app, user_id=user["id"])
            raw_reply = "".join(
                str(chunk)
                for chunk in stream_user_llm_chunks(
                    app,
                    instruction,
                    history,
                    settings,
                    persona,
                    context,
                    strict=True,
                )
                if chunk
            )
            if not raw_reply.strip():
                raise RuntimeError("模型没有返回有效续写，请重试")
            reply_text = process_model_reply(
                app,
                raw_reply,
                char_name=str(app.get("name") or conversation.get("app_name") or "Ta"),
                user_name=str((persona or {}).get("name") or "你"),
                template_context=context,
            )
            reply_text = str(reply_text or "").strip()
            if not reply_text:
                raise RuntimeError("模型续写处理后为空，请重试")
            if reply_text == str(last_message.get("content") or "").strip():
                raise RuntimeError("模型重复了上一条回复，请重试")
            if self.client_connection_closed():
                raise ConnectionAbortedError("client disconnected")
            for chunk in chunk_text(reply_text):
                self.write_sse_event("delta", {"content": str(chunk)})
            if self.client_connection_closed(0.05):
                raise ConnectionAbortedError("client disconnected")
            reply_row = self.store.append_message(conv_id, user["id"], "assistant", reply_text)
            reply_message_id = str(reply_row["id"])
            charge = self.store.spend_credit_points(
                user["id"],
                CHAT_MESSAGE_COST,
                payload={"app_id": app_id, "conversation_id": conv_id, "message_id": reply_row["id"], "mode": "continue"},
            )
            charged = True
            try:
                self.store.maybe_refresh_summary(user["id"], conv_id)
            except Exception as exc:
                log(f"auto summary refresh failed for {conv_id}: {exc}")
            effective = self.store.effective_llm_settings(app, user_id=user["id"])
            self.write_sse_event("message_end", {
                "conversation_id": conv_id,
                "message_id": reply_row["id"],
                "reply": reply_text,
                "created_at": reply_row["created_at"],
                "app_name": app.get("name") or conversation.get("app_name") or "",
                "model_id": effective.get("model") or app.get("llm_model") or USER_LLM_MODEL,
                "model_preset_id": effective.get("preset_id") or app.get("llm_model") or "",
                "mode": "continue",
                **charge,
            })
        except Exception as exc:
            disconnected = is_client_disconnect_error(exc)
            if reply_message_id and not charged:
                try:
                    self.store.delete_message(reply_message_id, user["id"])
                except Exception as cleanup_exc:
                    log(f"continue reply cleanup failed for {reply_message_id}: {cleanup_exc}")
            if disconnected:
                log(f"web chat continue client disconnected for conversation {conv_id}")
            else:
                log(f"web chat continue failed: {exc}")
                try:
                    self.write_sse_event("error", {"message": str(exc)[:500] or "continue failed"})
                except Exception as write_exc:
                    if not is_client_disconnect_error(write_exc):
                        log(f"web chat continue error event failed: {write_exc}")
        finally:
            slot.__exit__(None, None, None)
            self.close_connection = True

    def handle_any(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path
        body_text, body = self.read_body()
        status = 200
        if path == "/health":
            self.store.log_request(
                self.command,
                path,
                parsed.query,
                {k: v for k, v in self.headers.items()},
                body_text,
                status,
            )
            log(f"{self.command} {path}" + (f"?{parsed.query}" if parsed.query else "") + f" -> {status}")
            self.send_text(status, "OK")
            return
        if path == "/media-cache/profile/default-avatar.png":
            avatar_candidates = [
                DEFAULT_STATE_DIR / "static" / "default_avatar.png",
                ROOT / "frontend" / "assets" / "img" / "apk" / "default_avatar.png",
                Path("/var/www/ai-fengyue-frontend/assets/img/apk/default_avatar.png"),
            ]
            avatar_path = next((item for item in avatar_candidates if item.exists()), avatar_candidates[0])
            if avatar_path.exists():
                self.send_file(200, avatar_path, "image/png")
            else:
                self.send_text(404, "avatar not found")
            return
        if path == "/img" or path == "/console/api/web/img":
            self.handle_image_proxy(parsed.query)
            return
        if path.startswith("/media-cache/"):
            self.handle_local_cover(path)
            return
        if path == "/console/api/web/chat/stream":
            self.store.log_request(
                self.command,
                path,
                parsed.query,
                {k: v for k, v in self.headers.items()},
                body_text,
                200,
            )
            log(f"{self.command} {path}" + (f"?{parsed.query}" if parsed.query else "") + " -> 200")
            self.handle_web_chat_stream(body)
            return
        if path == "/console/api/web/chat/continue/stream":
            self.store.log_request(
                self.command,
                path,
                parsed.query,
                {k: v for k, v in self.headers.items()},
                body_text,
                200,
            )
            log(f"{self.command} {path}" + (f"?{parsed.query}" if parsed.query else "") + " -> 200")
            self.handle_web_chat_continue_stream(body)
            return
        payload = self.route(path, parsed.query, body)
        self.store.log_request(
            self.command,
            path,
            parsed.query,
            {k: v for k, v in self.headers.items()},
            body_text,
            status,
        )
        log(f"{self.command} {path}" + (f"?{parsed.query}" if parsed.query else "") + f" -> {status}")
        if isinstance(payload, dict) and payload.get("__raw_sse__"):
            self.send_sse(status, payload.get("events") if isinstance(payload.get("events"), list) else [])
            return
        self.send_json(status, payload)

    def route(self, path: str, query: str, body: object) -> object:
        normalized = path.lstrip("/")

        if normalized == "console/api/public/site-settings":
            return ok_response(public_site_settings_json(self.store.site_settings()))

        user = self.authenticated_user()

        if normalized == "console/api/web/tts/voices":
            if not self.authenticated_token_user():
                return error_response("unauthorized", 401)
            return ok_response({"provider": "edge-tts", "default_voice": TTS_VOICES[0]["id"], "list": TTS_VOICES})

        if normalized == "console/api/web/tts/synthesize":
            token_user = self.authenticated_token_user()
            if not token_user:
                return error_response("unauthorized", 401)
            if not isinstance(body, dict):
                return error_response("invalid body")
            message_id = str(body.get("message_id") or "").strip()
            message = self.store.get_message(message_id, token_user["id"]) if message_id else None
            if not message or str(message.get("role") or "") != "assistant":
                return error_response("assistant message not found", 404)
            text = clean_tts_text(message.get("content"))
            if not text:
                return error_response("message has no speakable text", 400)
            try:
                url, cached = synthesize_edge_tts(text, str(body.get("voice_id") or ""), str(body.get("rate") or "+0%"), str(body.get("pitch") or "+0Hz"))
                self.store.log_event(token_user["id"], "tts", "生成角色语音", {"message_id": message_id, "voice_id": str(body.get("voice_id") or ""), "cached": cached})
                return ok_response({"url": url, "cached": cached, "provider": "edge-tts"})
            except Exception as exc:
                log(f"TTS synthesis failed for {message_id}: {type(exc).__name__}: {exc}")
                return error_response("语音生成失败，请稍后重试", 502)

        if normalized == "console/api/register/email":
            email_value = normalize_email(body.get("email") if isinstance(body, dict) else "")
            lang = body.get("lang", "zh-Hans") if isinstance(body, dict) else "zh-Hans"
            if not is_valid_email(email_value):
                return error_response("invalid email")
            try:
                self.store.ensure_beta_registration_available(email_value)
            except ValueError as exc:
                return error_response(str(exc), 403)
            try:
                item = self.verification_store.create_or_reuse(email_value, self.client_ip())
                if item["send"]:
                    provider_id = send_verification_email(email_value, item["code"], str(lang))
                    self.verification_store.record(item["id"], email_value, "register", "accepted", provider_id)
                return ok_response({"status": "accepted", "retry_after": item["retry_after"], "reused": item["reused"]})
            except ValueError as exc:
                return error_response(str(exc), 429 if "too many" in str(exc) else 400)
            except Exception as exc:
                log(f"email send failed for {email_value}: {exc}")
                if allow_email_send_failure():
                    return ok_response("sent")
                return error_response(public_email_error(exc), 500)

        if normalized in ("console/api/password-reset/email", "console/api/reset-password/email"):
            email_value = normalize_email(body.get("email") if isinstance(body, dict) else "")
            lang = body.get("lang", "zh-Hans") if isinstance(body, dict) else "zh-Hans"
            if not is_valid_email(email_value):
                return error_response("invalid email")
            if not self.store.get_user_by_email(email_value):
                return ok_response("sent")
            try:
                item = self.verification_store.create_or_reuse(email_value, self.client_ip(), "password_reset")
                if item["send"]:
                    provider_id = send_verification_email(email_value, item["code"], str(lang), purpose="password_reset")
                    self.verification_store.record(item["id"], email_value, "password_reset", "accepted", provider_id)
                return ok_response({"status": "accepted", "retry_after": item["retry_after"], "reused": item["reused"]})
            except ValueError as exc:
                return error_response(str(exc), 429 if "too many" in str(exc) else 400)
            except Exception as exc:
                log(f"password reset email send failed for {email_value}: {exc}")
                if allow_email_send_failure():
                    return ok_response("sent")
                return error_response(public_email_error(exc), 500)

        if normalized == "console/api/register":
            if isinstance(body, dict):
                email = normalize_email(body.get("email"))
                name = body.get("name") or email.split("@")[0]
                password = body.get("password")
                code = body.get("code")
            else:
                email, name, password, code = "", "", "", ""
            if not is_valid_email(email):
                return error_response("invalid email")
            if not password:
                return error_response("password is required")
            if self.store.get_user_by_email(email):
                return error_response("email already registered", 409)
            try:
                self.store.ensure_beta_registration_available(email)
            except ValueError as exc:
                return error_response(str(exc), 403)
            remote_ip = self.client_ip()
            if remote_ip and self.store.recent_register_success_count(remote_ip, now_ms() - 24 * 60 * 60 * 1000) >= REGISTER_IP_DAILY_FREE_ACCOUNT_LIMIT:
                return error_response("too many free accounts from this network, try later", 429)
            if not (self.verification_store.verify(email, str(code)) or self.store.verify_email_code(email, str(code))) and not (allow_any_register_code() and str(code).strip()):
                return error_response("invalid verification code", 401)
            try:
                user = self.store.create_registered_user(str(email), str(name), str(password), remote_ip)
            except ValueError as exc:
                return error_response(str(exc), 409 if "already" in str(exc) else 400)
            return ok_response(token_for(user["id"]))

        if normalized in ("console/api/login", "console/api/oauth-token-login"):
            if isinstance(body, dict):
                email = body.get("email") or body.get("username") or body.get("account") or ""
                password = body.get("password") or body.get("token")
            else:
                email, password = "", None
            normalized_email = normalize_email(str(email))
            existing = self.store.get_user_by_email(normalized_email)
            if not is_valid_email(normalized_email) or not password or not existing:
                return error_response("invalid email or password", 401)
            if existing["password_hash"] != self.store.password_hash(str(password)):
                return error_response("invalid email or password", 401)
            return ok_response(token_for(existing["id"]))

        if normalized in ("console/api/password-reset", "console/api/reset-password"):
            if isinstance(body, dict):
                email = normalize_email(body.get("email"))
                password = body.get("password")
                code = body.get("code")
            else:
                email, password, code = "", None, ""
            if not is_valid_email(email):
                return error_response("invalid email")
            if not password or len(str(password)) < 6:
                return error_response("password must be at least 6 characters")
            if not self.store.get_user_by_email(email):
                return error_response("invalid verification code", 401)
            if not (self.verification_store.verify(email, str(code), "password_reset") or self.store.verify_email_code(email, str(code), purpose="password_reset")):
                return error_response("invalid verification code", 401)
            try:
                updated = self.store.reset_user_password(str(email), str(password), self.client_ip())
            except ValueError as exc:
                return error_response(str(exc), 400)
            return ok_response(token_for(updated["id"]))

        if normalized == "console/api/register/name_check":
            return ok_response("")

        if normalized in ("console/api/account/gender", "go/api/account/gender"):
            if isinstance(body, dict):
                gender = int(body.get("gender") or 0)
            else:
                gender = 0
            self.store.conn.execute(
                "update users set gender=?, updated_at=? where id=?",
                (gender, now_ms(), user["id"]),
            )
            self.store.conn.commit()
            updated_user = self.store.get_user_by_id(user["id"]) or user
            payload = profile_json(updated_user)
            return go_response(payload) if normalized.startswith("go/") else payload

        if normalized in ("console/api/account/name", "go/api/account/name"):
            if not isinstance(body, dict):
                return error_response("invalid body")
            new_name = (
                body.get("name")
                or body.get("nickname")
                or body.get("user_name")
                or body.get("username")
                or body.get("display_name")
                or ""
            )
            try:
                updated_user = self.store.update_user_name(user["id"], str(new_name))
            except ValueError as exc:
                return error_response(str(exc), 400)
            payload = profile_json(updated_user)
            return go_response(payload) if normalized.startswith("go/") else payload

        if normalized in ("go/api/account/profile", "console/api/account/profile"):
            return go_response(profile_json(user)) if normalized.startswith("go/") else profile_json(user)

        if normalized.startswith("console/api/account/") and normalized.endswith("/personal-profile"):
            return ok_response(profile_json(user))

        if normalized == "console/api/web/profile":
            token_user = self.authenticated_token_user()
            if not token_user:
                return error_response("unauthorized", 401)
            if not isinstance(body, dict):
                return error_response("invalid body")
            display_id = body.get("display_id")
            if display_id is None:
                display_id = body.get("public_id", body.get("custom_id", ""))
            avatar_url = body.get("avatar_url")
            if avatar_url is None:
                avatar_url = body.get("avatar", "")
            try:
                updated_user = self.store.update_user_profile(token_user["id"], display_id, avatar_url)
            except ValueError as exc:
                return error_response(str(exc), 400)
            payload = profile_json(updated_user)
            self.store.log_event(token_user["id"], "profile", "更新用户资料", {
                "display_id": payload.get("display_id") or "",
                "avatar_url": payload.get("avatar_url") or "",
            })
            return ok_response(payload)

        if normalized == "console/api/user/point":
            return points_json(user)

        if normalized in ("console/api/user/credits", "go/api/user/credits"):
            deposit = deposit_meta_json(user)
            payload = {
                **credit_balance_json(user),
                "aifadian_url": deposit.get("aifadian_url") or "",
                "deposit": deposit,
            }
            return go_response(payload) if normalized.startswith("go/") else ok_response(payload)

        if normalized == "go/api/account/point":
            balance = credit_balance_json(user)
            return go_response({
                "points": str(balance["points"]),
                "available_points": str(balance["points"]),
                **balance,
            })

        if normalized in ("console/api/ctf/recharge", "go/api/ctf/recharge"):
            if not PAYMENT_CHANNEL_ENABLED:
                return error_response("充值通道暂时关闭", 403)
            if isinstance(body, dict):
                amount = int(body.get("points") or body.get("amount") or 100)
                product_id = str(body.get("product_id") or "ctf_internal_recharge_100")
            else:
                amount = 100
                product_id = "ctf_internal_recharge_100"
            user, order_id = self.store.create_recharge_order(user["id"], amount, product_id, self.client_address[0])
            data = {
                "order_id": order_id,
                "product_id": product_id,
                "points_added": str(amount),
                "points": str(user["points"]),
                "status": "server_verified",
                "paid_at": now_ms(),
            }
            self.store.log_event(user["id"], "deposit", f"充值 {amount} 积分", {"points": amount, "order_id": order_id})
            return go_response(data) if normalized.startswith("go/") else ok_response(data)

        if normalized in ("console/api/workspaces/current", "go/api/workspaces/current"):
            return go_response(workspace_json()) if normalized.startswith("go/") else workspace_json()

        if normalized in ("console/api/installed-apps", "console/api/used-installed-apps", "go/api/gallery/list"):
            fallback = {
                "result": "success",
                "code": "200",
                "message": "OK",
                "status": 200,
                "data": {"installed_apps": [], "apps": [], "list": [], "items": [], "total": 0, "page": 1, "limit": 20},
            }
            return proxy_json(normalized, query, fallback)

        if normalized.startswith("console/api/apps/") and normalized.endswith("/favorite"):
            app_id = normalized.split("/")[3] if len(normalized.split("/")) >= 4 else ""
            local = self.store.get_local_app(app_id)
            if not local:
                return error_response("not found", 404)
            payload = self.store.toggle_favorite(user["id"], app_id)
            return ok_response(payload)

        if normalized.startswith("console/api/apps/") and normalized.endswith("/like"):
            app_id = normalized.split("/")[3] if len(normalized.split("/")) >= 4 else ""
            local = self.store.get_local_app(app_id)
            if not local:
                return error_response("not found", 404)
            payload = self.store.toggle_like(user["id"], app_id)
            return ok_response(payload)

        if normalized in ("console/api/web/my-apps", "go/api/web/my-apps"):
            page = parse_query_int(query, "page", 1, 1, 100000)
            page_size = parse_query_int(query, "page_size", 30, 1, 100)
            source = parse_query_str(query, "source", "")
            search = parse_query_str(query, "q", "").strip()
            rows, total = self.store.list_local_apps(
                source=source or None,
                owner_user_id=user["id"],
                search=search,
                page=page,
                page_size=page_size,
                only_public=False,
                only_published=False,
            )
            payload = {"list": [local_app_to_card(r) for r in rows], "total": total, "page": page, "page_size": page_size}
            return go_response(payload) if normalized.startswith("go/") else ok_response(payload)

        if normalized in ("console/api/web/my-apps-count", "go/api/web/my-apps-count"):
            payload = self.store.local_apps_count()
            return go_response(payload) if normalized.startswith("go/") else ok_response(payload)

        if normalized in ("console/api/web/my-apps/create", "go/api/web/my-apps/create"):
            if not isinstance(body, dict):
                return error_response("invalid body")
            data = dict(body)
            data["cover_url"] = normalize_cover_input(data.get("cover_url") or data.get("cover") or "")
            row = self.store.create_user_app(user["id"], data)
            payload = local_app_to_card(dict(row))
            self.store.log_event(user["id"], "workshop", f"创建角色：{payload.get('name')}", {"app_id": payload.get("id")})
            return go_response(payload) if normalized.startswith("go/") else ok_response(payload)

        # Import a SillyTavern Character Card (V1/V2 JSON) → new user card
        if normalized == "console/api/web/cards/import":
            if not isinstance(body, dict):
                return error_response("invalid body")
            try:
                if body.get("card_file"):
                    card = parse_uploaded_card_file(str(body.get("card_file") or ""), str(body.get("filename") or ""))
                else:
                    card = body.get("card") if isinstance(body.get("card"), dict) else body
            except Exception as exc:
                return error_response(f"角色卡文件解析失败：{exc}", 400)
            try:
                data = silly_card_to_app(card)
            except Exception as exc:
                return error_response(f"角色卡解析失败：{exc}", 400)
            data["cover_url"] = normalize_cover_input(data.get("cover_url") or "")
            row = self.store.create_user_app(user["id"], data)
            payload = local_app_to_card(dict(row))
            self.store.log_event(user["id"], "workshop", f"导入角色：{payload.get('name')}", {"app_id": payload.get("id")})
            return ok_response(payload)

        # Export a user's own card as SillyTavern Character Card V2 JSON
        if normalized.startswith("console/api/web/my-apps/") and normalized.endswith("/export"):
            app_id = normalized.split("/")[4]
            row = self.store.get_local_app(app_id)
            if not row:
                return error_response("not found", 404)
            card = local_app_to_card(dict(row))
            owner = dict(row).get("owner_user_id")
            if dict(row).get("source") == "user" and owner and owner != user["id"]:
                return error_response("forbidden", 403)
            return ok_response(app_to_silly_card(card))

        if normalized.startswith("console/api/web/my-apps/") and normalized.endswith("/export-png"):
            app_id = normalized.split("/")[4]
            row = self.store.get_local_app(app_id)
            if not row:
                return error_response("not found", 404)
            card = local_app_to_card(dict(row))
            owner = dict(row).get("owner_user_id")
            if dict(row).get("source") == "user" and owner and owner != user["id"]:
                return error_response("forbidden", 403)
            filename = safe_filename((card.get("name") or "character") + ".png", "character.png")
            return ok_response({"filename": filename, "mime": "image/png", "data_url": app_to_silly_card_png_data_url(card)})

        if normalized.startswith("console/api/web/my-apps/") and normalized.endswith("/update"):
            if not isinstance(body, dict):
                return error_response("invalid body")
            app_id = normalized.split("/")[4]
            data = dict(body)
            if "cover_url" in data or "cover" in data:
                data["cover_url"] = normalize_cover_input(data.get("cover_url") or data.get("cover") or "")
            row = self.store.update_user_app(app_id, user["id"], data)
            if not row:
                return error_response("not found", 404)
            payload = local_app_to_card(dict(row))
            self.store.log_event(user["id"], "workshop", f"更新角色：{payload.get('name')}", {"app_id": app_id})
            return ok_response(payload)

        if normalized.startswith("console/api/web/my-apps/") and normalized.endswith("/delete"):
            app_id = normalized.split("/")[4]
            ok = self.store.delete_user_app(app_id, user["id"])
            self.store.log_event(user["id"], "workshop", "删除角色", {"app_id": app_id, "deleted": ok})
            return ok_response({"deleted": ok})

        if normalized == "console/api/web/profile/avatar":
            token_user = self.authenticated_token_user()
            if not token_user:
                return error_response("unauthorized", 401)
            if not isinstance(body, dict):
                return error_response("invalid body")
            raw = str(body.get("image") or body.get("file") or body.get("data") or "")
            filename = str(body.get("filename") or body.get("name") or "avatar.png")
            try:
                blob, mime = decode_data_url(raw)
            except Exception as exc:
                return error_response(str(exc), 400)
            if len(blob) > 5 * 1024 * 1024:
                return error_response("avatar image is too large", 400)
            lower_mime = (mime or "").lower()
            lower_name = filename.lower()
            ext = {
                "image/png": ".png",
                "image/jpeg": ".jpg",
                "image/jpg": ".jpg",
                "image/webp": ".webp",
                "image/avif": ".avif",
                "image/gif": ".gif",
            }.get(lower_mime, "")
            if not ext:
                for suffix in (".png", ".jpg", ".jpeg", ".webp", ".avif", ".gif"):
                    if lower_name.endswith(suffix):
                        ext = ".jpg" if suffix == ".jpeg" else suffix
                        break
            if not ext:
                if blob.startswith(b"\x89PNG\r\n\x1a\n"):
                    ext = ".png"
                elif blob.startswith(b"\xff\xd8\xff"):
                    ext = ".jpg"
                elif blob.startswith(b"RIFF") and b"WEBP" in blob[:16]:
                    ext = ".webp"
                elif blob.startswith((b"GIF87a", b"GIF89a")):
                    ext = ".gif"
            if not ext:
                return error_response("unsupported avatar image type", 400)
            if MEDIA_DIR is None:
                return error_response("media dir not ready", 500)
            profile_dir = MEDIA_DIR / "profile"
            profile_dir.mkdir(parents=True, exist_ok=True)
            dest = profile_dir / safe_filename(uuid.uuid4().hex[:16] + "-" + Path(filename).stem + ext, "avatar.png")
            dest.write_bytes(blob)
            rel = f"/media-cache/profile/{dest.name}"
            self.store.log_event(token_user["id"], "upload", "上传用户头像", {"filename": dest.name})
            return ok_response({"url": public_url(rel), "path": rel, "filename": dest.name})

        if normalized in ("console/api/web/my-apps/upload-cover", "go/api/web/my-apps/upload-cover"):
            if not isinstance(body, dict):
                return error_response("invalid body")
            raw = str(body.get("image") or body.get("file") or body.get("data") or "")
            filename = str(body.get("filename") or body.get("name") or "cover.png")
            try:
                blob, mime = decode_data_url(raw)
            except Exception as exc:
                return error_response(str(exc), 400)
            ext = {
                "image/png": ".png",
                "image/jpeg": ".jpg",
                "image/jpg": ".jpg",
                "image/webp": ".webp",
                "image/avif": ".avif",
                "image/gif": ".gif",
            }.get((mime or "").lower(), ".png")
            if MEDIA_DIR is None:
                return error_response("media dir not ready", 500)
            dest = MEDIA_DIR / "cover" / safe_filename(uuid.uuid4().hex[:16] + "-" + Path(filename).stem + ext, "cover.png")
            dest.write_bytes(blob)
            rel = f"/media-cache/cover/{dest.name}"
            self.store.log_event(user["id"], "upload", "上传角色封面", {"filename": dest.name})
            return ok_response({"url": public_url(rel), "path": rel, "filename": dest.name})

        if normalized == "console/api/web/favorites":
            page = parse_query_int(query, "page", 1, 1, 100000)
            page_size = parse_query_int(query, "page_size", 30, 1, 100)
            search = parse_query_str(query, "q", "").strip()
            rows, total = self.store.list_favorites(user["id"], page=page, page_size=page_size, search=search)
            cards = [
                dict(
                    local_app_to_card(r),
                    favorited=True,
                    liked=self.store.is_liked(user["id"], r.get("id") or ""),
                    user_tags=self.store.list_user_app_tags(user["id"], r.get("id") or ""),
                    favorited_at=r.get("favorited_at"),
                )
                for r in rows
            ]
            return ok_response({"list": cards, "apps": cards, "total": total, "page": page, "page_size": page_size})

        if normalized.startswith("console/api/web/favorites/") and normalized.endswith("/toggle"):
            app_id = normalized.split("/")[4] if len(normalized.split("/")) >= 5 else ""
            local = self.store.get_local_app(app_id)
            if not local:
                return error_response("not found", 404)
            return ok_response(self.store.toggle_favorite(user["id"], app_id))

        if normalized.startswith("console/api/web/apps/") and normalized.endswith("/like"):
            app_id = normalized.split("/")[4] if len(normalized.split("/")) >= 5 else ""
            local = self.store.get_local_app(app_id)
            if not local:
                return error_response("not found", 404)
            return ok_response(self.store.toggle_like(user["id"], app_id))

        if normalized.startswith("console/api/web/apps/") and normalized.endswith("/user-tags"):
            app_id = normalized.split("/")[4] if len(normalized.split("/")) >= 5 else ""
            if not self.store.get_local_app(app_id):
                return error_response("not found", 404)
            if self.command.upper() == "POST":
                if not isinstance(body, dict):
                    return error_response("invalid body")
                try:
                    return ok_response(self.store.set_user_app_tags(user["id"], app_id, body.get("tags") or body.get("user_tags") or []))
                except ValueError as exc:
                    status = 404 if str(exc) == "not found" else 400
                    return error_response(str(exc), status)
            return ok_response({"app_id": app_id, "tags": self.store.list_user_app_tags(user["id"], app_id)})

        if normalized.startswith("console/api/web/apps/") and normalized.endswith("/comments"):
            parts = normalized.split("/")
            app_id = parts[4] if len(parts) >= 6 else ""
            if not self.store.get_local_app(app_id):
                return error_response("not found", 404)
            if self.command.upper() == "POST":
                if not isinstance(body, dict):
                    return error_response("invalid body")
                try:
                    comment = self.store.create_app_comment(user["id"], app_id, str(body.get("content") or ""))
                except ValueError as exc:
                    status = 404 if str(exc) == "not found" else 400
                    return error_response(str(exc), status)
                return ok_response(comment)
            limit = parse_query_int(query, "limit", 3, 1, 100)
            if parse_query_str(query, "expanded", "").lower() in ("1", "true", "yes"):
                limit = max(limit, 50)
            return ok_response(self.store.list_app_comments(app_id, user["id"], limit=limit))

        if normalized.startswith("console/api/web/comments/") and normalized.endswith("/like"):
            comment_id = normalized.split("/")[4] if len(normalized.split("/")) >= 5 else ""
            try:
                return ok_response(self.store.toggle_app_comment_like(user["id"], comment_id))
            except ValueError as exc:
                status = 404 if str(exc) == "not found" else 400
                return error_response(str(exc), status)

        if normalized == "console/api/web/logs":
            page = parse_query_int(query, "page", 1, 1, 100000)
            page_size = parse_query_int(query, "page_size", 30, 1, 100)
            events, total = self.store.list_events(user["id"], page=page, page_size=page_size)
            return ok_response({"list": events, "total": total, "page": page, "page_size": page_size})

        if normalized == "console/api/web/creator-leaderboard":
            limit = parse_query_int(query, "limit", 10, 1, 50)
            return ok_response({"list": self.store.creator_leaderboard(limit), "limit": limit})

        if normalized == "console/api/web/creator-contests":
            contest = self.store.creator_contests()
            return ok_response({"contest": contest, "leaderboard": self.store.creator_leaderboard(10)})

        if normalized == "console/api/web/rewards":
            today = business_date()
            claimed = self.store.has_claimed_daily_reward(user["id"], today)
            settings = self.store.site_settings()
            daily_points = clean_int(settings.get("rewards", {}).get("daily_points"), 10, 1, 100000)
            return ok_response({
                "daily": {
                    "points": daily_points,
                    "claimed": claimed,
                    "date": today,
                    "title": settings.get("rewards", {}).get("daily_title") or "每日奖励",
                    "description": settings.get("rewards", {}).get("daily_description") or "",
                },
                "tasks": settings.get("rewards", {}).get("tasks") or [],
                "points": int(credit_balance_json(user)["points"]),
                "balance": credit_balance_json(user),
                "deposit": deposit_meta_json(user),
            })

        if normalized == "console/api/web/rewards/daily":
            daily_points = clean_int(self.store.site_settings().get("rewards", {}).get("daily_points"), 10, 1, 100000)
            return ok_response(self.store.claim_daily_reward(user["id"], daily_points))

        if normalized == "console/api/web/deposit-meta":
            return ok_response(deposit_meta_json(user))

        if normalized == "console/api/web/redeem-code":
            if self.command.upper() != "POST":
                return error_response("method not allowed", 405)
            if not PAYMENT_CHANNEL_ENABLED:
                return error_response("充值通道暂时关闭", 403)
            if not isinstance(body, dict):
                return error_response("invalid body")
            try:
                payload = self.store.redeem_code(user["id"], str(body.get("code") or ""))
            except ValueError as exc:
                return error_response(str(exc), 400)
            self.store.log_event(user["id"], "redeem_code", f"兑换码到账 {payload.get('points_added')} 积分", {
                "code": payload.get("code"),
                "points": payload.get("points_added"),
                "point_type": payload.get("point_type"),
            })
            return ok_response(payload)

        if normalized == "console/api/web/redemptions":
            page = parse_query_int(query, "page", 1, 1, 100000)
            page_size = parse_query_int(query, "page_size", 30, 1, 100)
            rows, total = self.store.list_user_redemptions(user["id"], page=page, page_size=page_size)
            return ok_response({"list": rows, "total": total, "page": page, "page_size": page_size})

        if normalized == "console/api/web/home-stats":
            counts = self.store.local_apps_count()
            conv_total = self.store.conn.execute(
                "select count(*) from conversations where user_id=?",
                (user["id"],),
            ).fetchone()[0]
            fav_total = self.store.conn.execute(
                "select count(*) from user_favorites where user_id=?",
                (user["id"],),
            ).fetchone()[0]
            return ok_response({"apps": counts, "conversations": int(conv_total), "favorites": int(fav_total), "points": int(credit_balance_json(user)["points"]), "balance": credit_balance_json(user)})

        if normalized == "console/api/web/model-presets":
            return ok_response(self.store.public_model_presets())

        if normalized == "console/api/web/tavo-plugins/runtime-contributions":
            token_user = self.authenticated_token_user()
            if not token_user:
                return error_response("unauthorized", 401)
            return ok_response(self.store.enabled_tavo_plugin_runtime_contributions())

        if normalized == "console/api/web/provider-templates":
            return ok_response({"list": self.store.provider_templates(), "enabled": USER_BYOK_ENABLED})

        if normalized == "console/api/web/user-model-presets":
            token_user = self.authenticated_token_user()
            if not token_user:
                return error_response("unauthorized", 401)
            if self.command.upper() == "GET":
                return ok_response(self.store.user_model_presets(token_user["id"], include_secret=False))
            if self.command.upper() != "POST" or not isinstance(body, dict):
                return error_response("invalid body")
            try:
                payload = self.store.save_user_model_presets(token_user["id"], body.get("presets") or [])
            except ValueError as exc:
                status = 403 if "disabled" in str(exc).lower() else 400
                return error_response(str(exc), status)
            self.store.log_event(token_user["id"], "model_presets", "尝试更新用户模型连接器", {"count": payload.get("total")})
            return ok_response(payload)

        if normalized == "console/api/web/group-chats":
            token_user = self.authenticated_token_user()
            if not token_user:
                return error_response("unauthorized", 401)
            if self.command.upper() == "GET":
                return ok_response({"list": self.store.list_group_chats(token_user["id"])})
            if self.command.upper() != "POST":
                return error_response("method not allowed", 405)
            if not isinstance(body, dict):
                return error_response("invalid body")
            raw_ids = body.get("app_ids") or body.get("members") or []
            app_ids = []
            if isinstance(raw_ids, str):
                raw_ids = re.split(r"[，,\n]", raw_ids)
            if isinstance(raw_ids, list):
                for item in raw_ids[:12]:
                    app_id = str(item.get("app_id") if isinstance(item, dict) else item or "").strip()
                    if app_id and app_id not in app_ids:
                        app_ids.append(app_id)
            members = []
            for app_id in app_ids:
                row = self.store.get_local_app(app_id)
                if not user_can_access_app(row, token_user["id"]):
                    return error_response(f"角色不可用：{app_id}", 400)
                card = local_app_to_card(dict(row))
                members.append({"app_id": app_id, "app_name": card.get("name") or "", "app_icon": card.get("cover_url") or card.get("cover") or ""})
            try:
                group = self.store.create_group_chat(
                    token_user["id"],
                    str(body.get("name") or "、".join(m["app_name"] for m in members[:3]) or "群聊"),
                    members,
                )
            except ValueError as exc:
                return error_response(str(exc), 400)
            self.store.log_event(token_user["id"], "group_chat", f"创建群聊：{group.get('name')}", {"group_id": group.get("id"), "members": app_ids})
            return ok_response({"group": group, "messages": []})

        if normalized.startswith("console/api/web/group-chats/"):
            token_user = self.authenticated_token_user()
            if not token_user:
                return error_response("unauthorized", 401)
            parts = normalized.split("/")
            group_id = parts[4] if len(parts) >= 5 else ""
            action = parts[5] if len(parts) >= 6 else ""
            group = self.store.get_group_chat(group_id, token_user["id"])
            if not group:
                return error_response("not found", 404)
            if not action:
                messages = self.store.list_group_messages(group_id, token_user["id"])
                return ok_response({"group": group, "messages": messages})
            if action == "delete":
                ok = self.store.delete_group_chat(group_id, token_user["id"])
                self.store.log_event(token_user["id"], "group_chat", "删除群聊", {"group_id": group_id, "deleted": ok})
                return ok_response({"deleted": ok})
            if action == "message":
                if self.command.upper() != "POST" or not isinstance(body, dict):
                    return error_response("invalid body")
                content = str(body.get("content") or body.get("message") or "").strip()
                if not content:
                    return error_response("content is required")
                auto_reply = body.get("auto_reply", True) is not False
                if auto_reply:
                    try:
                        self.store.require_credit_points(token_user["id"], CHAT_MESSAGE_COST)
                    except ValueError as exc:
                        return error_response(str(exc), 402)
                user_name = str(token_user["name"] if "name" in token_user.keys() else "我") or "我"
                created = [
                    self.store.append_group_message(group_id, token_user["id"], "user", content, speaker_name=user_name)
                ]
                charge = None
                if auto_reply:
                    group = self.store.get_group_chat(group_id, token_user["id"]) or group
                    try:
                        with GENERATION_LIMITER.acquire(token_user["id"], self.client_ip(), "group_message"):
                            reply, member, next_index = generate_group_reply(self.store, token_user["id"], group, app_id=str(body.get("app_id") or ""), prompt=content)
                            created.append(reply)
                            charge = self.store.spend_credit_points(
                                token_user["id"],
                                CHAT_MESSAGE_COST,
                                payload={"group_id": group_id, "message_id": reply.get("id"), "app_id": member.get("app_id")},
                            )
                    except GenerationLimitError as exc:
                        return error_response(str(exc), 429)
                    except Exception as exc:
                        return error_response(f"群聊回复失败：{exc}", 500)
                group = self.store.get_group_chat(group_id, token_user["id"]) or group
                payload = {"group": group, "messages": self.store.list_group_messages(group_id, token_user["id"]), "new_messages": created}
                if charge:
                    payload.update(charge)
                return ok_response(payload)
            if action == "reply":
                if self.command.upper() != "POST" or not isinstance(body, dict):
                    return error_response("invalid body")
                try:
                    self.store.require_credit_points(token_user["id"], CHAT_MESSAGE_COST)
                except ValueError as exc:
                    return error_response(str(exc), 402)
                try:
                    with GENERATION_LIMITER.acquire(token_user["id"], self.client_ip(), "group_reply"):
                        reply, member, next_index = generate_group_reply(
                            self.store,
                            token_user["id"],
                            group,
                            app_id=str(body.get("app_id") or ""),
                            prompt=str(body.get("prompt") or ""),
                        )
                        charge = self.store.spend_credit_points(
                            token_user["id"],
                            CHAT_MESSAGE_COST,
                            payload={"group_id": group_id, "message_id": reply.get("id"), "app_id": member.get("app_id")},
                        )
                except GenerationLimitError as exc:
                    return error_response(str(exc), 429)
                except Exception as exc:
                    return error_response(f"群聊回复失败：{exc}", 500)
                group = self.store.get_group_chat(group_id, token_user["id"]) or group
                payload = {"group": group, "message": reply, "messages": self.store.list_group_messages(group_id, token_user["id"]), "next_index": next_index}
                payload.update(charge)
                return ok_response(payload)

        if normalized == "console/api/web/image-chat":
            if not isinstance(body, dict):
                return error_response("invalid body")
            prompt = str(body.get("prompt") or body.get("content") or "").strip()
            image_name = str(body.get("filename") or body.get("image_name") or "").strip()
            if not prompt and not image_name:
                return error_response("prompt or image is required")
            settings = self.store.image_model_settings(include_secret=True)
            if settings.get("enabled") and settings.get("base_url") and settings.get("api_key") and settings.get("model") and prompt:
                try:
                    with GENERATION_LIMITER.acquire(user["id"], self.client_ip(), "image_chat"):
                        generated = call_image_model(prompt, settings)
                except GenerationLimitError as exc:
                    return error_response(str(exc), 429)
                except Exception as exc:
                    log(f"image model failed: {exc}")
                    return error_response("图片模型调用失败：" + str(exc)[:180], 502)
                reply = "图片已生成。"
                payload = {
                    "reply": reply,
                    "prompt": prompt,
                    "image_name": image_name,
                    "created_at": now_ms(),
                    "mode": "image_model",
                    **generated,
                }
            else:
                reply = "图片聊天已接入 惑梦（Homer）本地工作台。当前站点会保存你的图片聊天请求；配置图片模型后会在这里返回真实图像。"
                payload = {"reply": reply, "prompt": prompt, "image_name": image_name, "created_at": now_ms(), "mode": "local_placeholder"}
            self.store.log_event(
                user["id"],
                "image_chat",
                "图片聊天请求",
                {"prompt": prompt[:120], "image_name": image_name, "mode": payload.get("mode"), "model": payload.get("model", "")},
            )
            return ok_response(payload)

        if (
            normalized == "go/api/apps/chat-messages"
            or (normalized.startswith("go/api/apps/") and normalized.endswith("/chat-messages"))
            or (normalized.startswith("console/api/installed-apps/") and normalized.endswith("/chat-messages"))
        ):
            if not isinstance(body, dict):
                return error_response("invalid body")
            parts = normalized.split("/")
            app_id = str(body.get("app_id") or "").strip()
            if not app_id and len(parts) >= 4 and parts[0] == "go":
                app_id = parts[3]
            if not app_id and len(parts) >= 4 and parts[0] == "console":
                app_id = parts[3]
            content = str(body.get("query") or body.get("content") or body.get("message") or "").strip()
            if not content:
                return error_response("query is required")
            app_id = self.store.resolve_local_app_id(app_id)
            try:
                self.store.require_credit_points(user["id"], CHAT_MESSAGE_COST)
            except ValueError as exc:
                return error_response(str(exc), 402)
            conv_id = str(body.get("conversation_id") or "").strip() or str(uuid.uuid4())
            app_name = str(body.get("app_name") or "").strip() or app_name_from_cache(self.store, app_id)
            try:
                with GENERATION_LIMITER.acquire(user["id"], self.client_ip(), "legacy_chat"):
                    self.store.upsert_conversation(conv_id, user["id"], app_id, app_name=app_name, title=str(body.get("conversation_name") or content[:30]))
                    self.store.append_message(conv_id, user["id"], "user", content)
                    app_row, answer = chat_reply_for_app(
                        self.store,
                        user["id"],
                        app_id,
                        content,
                        app_name=app_name,
                        conversation_id=conv_id,
                        response_mode=str(body.get("response_mode") or ""),
                    )
                    reply = self.store.append_message(conv_id, user["id"], "assistant", answer)
                    charge = self.store.spend_credit_points(
                        user["id"],
                        CHAT_MESSAGE_COST,
                        payload={"app_id": app_id, "conversation_id": conv_id, "message_id": reply["id"]},
                    )
            except GenerationLimitError as exc:
                return error_response(str(exc), 429)
            message = chat_message_payload(reply, conv_id, app_id, content, answer)
            message.update(charge)
            if str(body.get("response_mode") or "").lower() == "streaming":
                return {
                    "__raw_sse__": True,
                    "events": [
                        {"event": "message", "data": message},
                        {"event": "message_end", "data": message},
                    ],
                }
            payload = {"result": "success", "data": message, "message": message, "error": None}
            if app_row and app_row.get("source") == "user":
                payload["data"]["model_id"] = app_row.get("llm_model") or USER_LLM_MODEL
            return payload

        if normalized.startswith("console/api/apps/") or normalized.startswith("go/api/apps/"):
            seg = normalized.split("/")
            app_id = seg[3] if len(seg) > 3 else "local-app"
            # 精确详情请求（apps/{id}，无子路径）：本地优先
            if len(seg) == 4:
                local = self.store.get_local_app(app_id)
                if local:
                    card = local_app_to_card(dict(local))
                    card["favorited"] = self.store.is_favorite(user["id"] if user else None, card["id"])
                    card["liked"] = self.store.is_liked(user["id"] if user else None, card["id"])
                    card["user_tags"] = self.store.list_user_app_tags(user["id"] if user else None, card["id"])
                    return go_response(card) if normalized.startswith("go/") else ok_response(card)
            data = app_config_json(app_id)
            if CONTENT_MODE == "local_only":
                return error_response("角色不存在或已下架", 404)
            fallback = go_response(data) if normalized.startswith("go/") else data
            return proxy_json(normalized, query, fallback)

        if "points-claim" in normalized or normalized.endswith("dailyapppoints"):
            daily_points = clean_int(self.store.site_settings().get("rewards", {}).get("daily_points"), 10, 1, 100000)
            payload = self.store.claim_daily_reward(user["id"], daily_points)
            data = dict(payload.get("balance") or {})
            data.update({
                "claimed": payload.get("claimed", True),
                "already_claimed": payload.get("already_claimed", False),
                "points_added": str(payload.get("points_added", 0)),
                "date": payload.get("date") or business_date(),
            })
            return {"result": "success", "data": data, "points": str(payload.get("points", data.get("points", 0)))}

        if normalized.endswith("announcements") or "announcement" in normalized:
            return proxy_json(normalized, query, go_response([]))

        if normalized == "console/api/v1/activities/gift-packs":
            return normalize_data_array_response(proxy_json(normalized, query, ok_response([])))

        if normalized.startswith("console/api/activity/"):
            return proxy_json(normalized, query, ok_response({}))

        if normalized == "console/api/workspaces/sidebar_notice":
            return proxy_json(normalized, query, ok_response({"id": "", "content": "", "enabled": False, "items": []}))

        if normalized == "console/api/app_site/list":
            fallback = ok_response({"id": "", "list": [], "installed_apps": [], "apps": [], "items": [], "total": 0})
            return normalize_app_site_list_response(proxy_json(normalized, query, fallback))

        if normalized == "go/api/account/unread":
            return proxy_json(normalized, query, go_response({"unread_chat_count": 0, "unread_message_count": 0}))

        if normalized == "console/api/account/referral-info":
            return ok_response([])

        if normalized == "console/api/emojis":
            return normalize_data_array_response(proxy_json(normalized, query, ok_response([])))

        if normalized.startswith("console/api/installed-apps/") and normalized.endswith("/conversations"):
            parts = normalized.split("/")
            app_id = parts[3] if len(parts) >= 4 else ""
            convs = self.store.list_conversations(user["id"], parse_query_int(query, "limit", 100, 1, 200))
            scoped = [c for c in convs if c.get("app_id") == app_id]
            return ok_response({"list": scoped, "total": len(scoped), "has_more": False})

        if normalized.startswith("console/api/installed-apps/") and normalized.endswith("/messages"):
            parts = normalized.split("/")
            app_id = parts[3] if len(parts) >= 4 else ""
            conv_id = parse_query_str(query, "conversation_id", "")
            if not conv_id:
                convs = [c for c in self.store.list_conversations(user["id"], 1) if c.get("app_id") == app_id]
                conv_id = convs[0]["id"] if convs else ""
            msgs = self.store.list_messages(conv_id, user["id"]) if conv_id else []
            return ok_response({"list": msgs, "total": len(msgs), "has_more": False})

        if (
            normalized == "go/api/apps/chat-messages"
            or (normalized.startswith("go/api/apps/") and normalized.endswith("/chat-messages"))
            or (normalized.startswith("console/api/installed-apps/") and normalized.endswith("/chat-messages"))
        ):
            if not isinstance(body, dict):
                return error_response("invalid body")
            parts = normalized.split("/")
            app_id = str(body.get("app_id") or "").strip()
            if not app_id and len(parts) >= 4 and parts[0] == "go":
                app_id = parts[3]
            if not app_id and len(parts) >= 4 and parts[0] == "console":
                app_id = parts[3]
            content = str(body.get("query") or body.get("content") or body.get("message") or "").strip()
            if not content:
                return error_response("query is required")
            app_id = self.store.resolve_local_app_id(app_id)
            try:
                self.store.require_credit_points(user["id"], CHAT_MESSAGE_COST)
            except ValueError as exc:
                return error_response(str(exc), 402)
            conv_id = str(body.get("conversation_id") or "").strip() or str(uuid.uuid4())
            app_name = str(body.get("app_name") or "").strip() or app_name_from_cache(self.store, app_id)
            self.store.upsert_conversation(conv_id, user["id"], app_id, app_name=app_name, title=str(body.get("conversation_name") or content[:30]))
            self.store.append_message(conv_id, user["id"], "user", content)
            answer = build_chat_reply(content, app_name)
            reply = self.store.append_message(conv_id, user["id"], "assistant", answer)
            charge = self.store.spend_credit_points(
                user["id"],
                CHAT_MESSAGE_COST,
                payload={"app_id": app_id, "conversation_id": conv_id, "message_id": reply["id"]},
            )
            message = chat_message_payload(reply, conv_id, app_id, content, answer)
            message.update(charge)
            if str(body.get("response_mode") or "").lower() == "streaming":
                return {
                    "__raw_sse__": True,
                    "events": [
                        {"event": "message", "data": message},
                        {"event": "message_end", "data": message},
                    ],
                }
            return {"result": "success", "data": message, "message": message, "error": None}

        if normalized == "go/api/posts/recommended":
            fallback = go_response({"posts": [], "total": 0})
            explore_payload = self.store.first_nonempty_explore_payload()
            if isinstance(explore_payload, dict):
                data = explore_payload.get("data")
                if isinstance(data, dict) and isinstance(data.get("apps"), list):
                    fallback = go_response({"posts": data["apps"], "total": data.get("total", len(data["apps"]))})
            return proxy_json(normalized, query, fallback)

        if normalized == "go/api/explore/search":
            # 本地优先：local_apps 有数据就直接返回本地（含自建+上游），断上游也能用
            params = parse_qs(query)
            page = parse_query_int(query, "page", 1, 1, 100000)
            page_size_value = (params.get("page_size") or params.get("limit") or ["30"])[0]
            try:
                page_size = max(1, min(int(page_size_value or 30), 60))
            except (TypeError, ValueError):
                page_size = 30
            kw = (params.get("keyword") or params.get("keywords") or params.get("q") or [""])[0].strip()
            tag = (params.get("tag") or params.get("category") or params.get("tag_ids") or params.get("tag_id") or [""])[0].strip()
            if "," in tag:
                tag = next((item.strip() for item in tag.split(",") if item.strip()), "")
            sort = (
                params.get("sort")
                or params.get("rank")
                or params.get("ranking")
                or params.get("ranking_type")
                or params.get("order")
                or ["default"]
            )[0].strip().lower()
            sort_aliases = {
                "recommended_week": "random",
                "random_recommended": "random",
                "recommended": "random",
                "recommend": "random",
                "newest": "latest",
                "hot": "popular",
                "recommend_daily": "daily",
                "recommend_monthly": "monthly",
            }
            sort = sort_aliases.get(sort, sort or "default")
            requested_zone = (params.get("zone") or params.get("content_zone") or [""])[0].strip().lower()
            if requested_zone in ("all", "full", "search"):
                content_zone = "all"
            elif requested_zone in ("clean", "safe", "pure"):
                content_zone = "clean"
            else:
                content_zone = "all" if kw else "clean"
            random_seed = parse_query_int(query, "seed", 0, 0, 2147483647) or None
            if sort == "random" and random_seed is None:
                random_seed = random.SystemRandom().randint(1, 2147483647)
            pictureless = (params.get("pictureless") or [""])[0].strip().lower() in ("1", "true", "yes")
            rows, total = self.store.list_local_apps(search=kw, tag=tag, sort=sort, content_zone=content_zone, random_seed=random_seed, page=page, page_size=page_size, lightweight=True)
            if rows:
                cards = []
                favorite_ids, liked_ids = self.store.app_interaction_states(
                    user["id"] if user else None,
                    [str(row.get("id") or "") for row in rows],
                )
                for r in rows:
                    card = local_app_to_list_card(r)
                    card["favorited"] = card["id"] in favorite_ids
                    card["liked"] = card["id"] in liked_ids
                    if pictureless:
                        card["pictureless"] = True
                        card["cover"] = ""
                        card["icon"] = ""
                    cards.append(card)
                return go_response({"apps": cards, "total": total, "is_cache": True, "page": page, "page_size": page_size, "sort": sort, "tag": tag, "seed": random_seed, "pictureless": pictureless, "zone": content_zone})
            if CONTENT_MODE == "local_only":
                return go_response({"apps": [], "total": 0, "is_cache": True, "page": page, "page_size": page_size, "sort": sort, "tag": tag, "seed": random_seed, "pictureless": pictureless, "zone": content_zone})
            # 非本地库模式才允许回源上游
            fallback = go_response({"apps": [], "total": 0, "is_cache": False})
            explore_payload = self.store.first_nonempty_explore_payload()
            if isinstance(explore_payload, dict):
                fallback = explore_payload
            return proxy_json(normalized, query, fallback)

        if normalized.startswith("go/api/explore/"):
            fallback = go_response({"apps": [], "total": 0, "is_cache": False})
            return proxy_json(normalized, query, fallback)

        if normalized.endswith("model-list") or "model" in normalized:
            return proxy_json(normalized, query, {"models": [], "list": [], "items": []})

        # ===== Conversations & Chat =====
        if normalized == "console/api/web/conversations":
            convs = self.store.list_conversations(user["id"])
            return ok_response({"list": convs, "total": len(convs)})

        if normalized.startswith("console/api/web/conversations/") and normalized.endswith("/messages"):
            parts = normalized.split("/")
            if len(parts) >= 5:
                conv_id = parts[4]
                limit = parse_query_int(query, "limit", 80, 1, 200)
                before = parse_query_int(query, "before", 0, 0, 9999999999999)
                msgs = self.store.list_messages(conv_id, user["id"], limit=limit, before_created_at=before or None)
                total = self.store.count_messages(conv_id, user["id"])
                first_created = 0
                if msgs:
                    try:
                        first_created = int(msgs[0].get("created_at") or 0)
                    except Exception:
                        first_created = 0
                older_count = self.store.count_messages(conv_id, user["id"], before_created_at=first_created) if first_created else 0
                return ok_response({
                    "list": msgs,
                    "total": total,
                    "limit": limit,
                    "returned": len(msgs),
                    "has_more": older_count > 0,
                    "next_before": first_created or None,
                })

        if normalized.startswith("console/api/web/conversations/") and normalized.endswith("/summary"):
            parts = normalized.split("/")
            conv_id = parts[4] if len(parts) >= 5 else ""
            conv = next((c for c in self.store.list_conversations(user["id"], 200) if c.get("id") == conv_id), None)
            if not conv:
                return error_response("conversation not found", 404)
            if self.command.upper() == "POST":
                if not isinstance(body, dict):
                    return error_response("invalid body")
                try:
                    if body.get("auto"):
                        summary = self.store.auto_summarize_conversation(user["id"], conv_id)
                    else:
                        summary = self.store.save_summary(
                            user["id"],
                            conv_id,
                            conv.get("app_id") or "",
                            str(body.get("summary") or ""),
                            len(self.store.list_messages(conv_id, user["id"])),
                        )
                except ValueError as exc:
                    return error_response(str(exc), 400)
                return ok_response(summary)
            return ok_response(self.store.get_summary(user["id"], conv_id))

        if normalized.startswith("console/api/web/conversations/") and normalized.endswith("/delete"):
            parts = normalized.split("/")
            if len(parts) >= 5:
                conv_id = parts[4]
                ok = self.store.delete_conversation(conv_id, user["id"])
                return ok_response({"deleted": ok})

        if normalized.startswith("console/api/web/conversations/") and normalized.endswith("/copy"):
            parts = normalized.split("/")
            if len(parts) >= 5:
                conv_id = parts[4]
                copied = self.store.copy_conversation(conv_id, user["id"])
                if not copied:
                    return error_response("conversation not found", 404)
                return ok_response({"conversation": copied})

        # Start a fresh conversation, seeding the opening greeting as the first assistant message.
        if normalized == "console/api/web/conversations/start":
            if not isinstance(body, dict):
                return error_response("invalid body")
            app_id = str(body.get("app_id") or "").strip()
            if not app_id:
                return error_response("app_id is required")
            app_id = self.store.resolve_local_app_id(app_id)
            app_row = self.store.get_local_app(app_id)
            card = local_app_to_card(dict(app_row)) if app_row else {}
            app_name = str(body.get("app_name") or card.get("name") or "").strip()
            app_icon = str(body.get("app_icon") or card.get("icon") or "")
            persona = self.store.get_persona(user["id"])
            char_name = card.get("name") or app_name or "Ta"
            user_name = persona.get("name") or "你"
            conv_id = str(uuid.uuid4())
            self.store.upsert_conversation(conv_id, user["id"], app_id,
                                           app_name=app_name, app_icon=app_icon, title=(app_name or "新对话")[:30])
            messages = []
            template_context = self.store.chat_context(user["id"], app_id, conv_id, "", [])
            if isinstance(template_context, dict):
                template_context.setdefault("app", card)
            greetings = chat_greetings_from_card(card, char_name, user_name, template_context=template_context)
            if greetings:
                first = self.store.append_message(
                    conv_id, user["id"], "assistant", greetings[0],
                    swipes=greetings if len(greetings) > 1 else None,
                )
                messages.append(self.store.get_message(first["id"], user["id"]))
            return ok_response({
                "conversation_id": conv_id,
                "app_id": app_id,
                "app_name": app_name,
                "app_icon": app_icon,
                "messages": messages,
            })

        # Regenerate the last assistant message (adds a new swipe).
        if normalized == "console/api/web/regenerate":
            if not isinstance(body, dict):
                return error_response("invalid body")
            conv_id = str(body.get("conversation_id") or "").strip()
            if not conv_id:
                return error_response("conversation_id is required")
            model_override = self.store.public_model_selection(body.get("model_id") or body.get("llm_model"))
            conv = next((c for c in self.store.list_conversations(user["id"], 200) if c.get("id") == conv_id), None)
            if not conv:
                return error_response("conversation not found", 404)
            all_msgs = self.store.list_messages(conv_id, user["id"])
            target = None
            for m in reversed(all_msgs):
                if m.get("role") == "assistant":
                    target = m
                    break
            if not target:
                return error_response("no assistant message to regenerate", 400)
            try:
                self.store.require_credit_points(user["id"], CHAT_MESSAGE_COST)
            except ValueError as exc:
                return error_response(str(exc), 402)
            # history before the target assistant message
            target_idx = next((i for i, m in enumerate(all_msgs) if m.get("id") == target.get("id")), len(all_msgs) - 1)
            history = all_msgs[:target_idx]
            last_user = ""
            for m in reversed(history):
                if m.get("role") == "user":
                    last_user = str(m.get("content") or "")
                    break
            app_id = conv.get("app_id") or ""
            try:
                with GENERATION_LIMITER.acquire(user["id"], self.client_ip(), "regenerate"):
                    app_row, reply = regenerate_reply_for_app(
                        self.store, user["id"], app_id,
                        history=history, last_user_content=last_user, app_name=conv.get("app_name") or "", conversation_id=conv_id,
                        model_override=model_override,
                    )
                    updated = self.store.append_swipe(target["id"], user["id"], reply)
                    charge = self.store.spend_credit_points(
                        user["id"],
                        CHAT_MESSAGE_COST,
                        payload={"app_id": app_id, "conversation_id": conv_id, "message_id": target["id"], "action": "regenerate"},
                    )
            except GenerationLimitError as exc:
                return error_response(str(exc), 429)
            payload = {"message": updated, "conversation_id": conv_id}
            payload.update(charge)
            return ok_response(payload)

        # Swipe between alternate replies of a message (generates a new one when going past the end).
        if normalized.startswith("console/api/web/messages/") and normalized.endswith("/swipe"):
            if not isinstance(body, dict):
                return error_response("invalid body")
            parts = normalized.split("/")
            message_id = parts[4] if len(parts) >= 5 else ""
            msg = self.store.get_message(message_id, user["id"])
            if not msg:
                return error_response("message not found", 404)
            model_override = self.store.public_model_selection(body.get("model_id") or body.get("llm_model"))
            swipes = msg.get("swipes") or []
            idx = msg.get("swipe_index") or 0
            if "index" in body:
                target_idx = _safe_int(body.get("index"), 0, 999) or 0
                updated = self.store.set_swipe(message_id, user["id"], target_idx)
                return ok_response({"message": updated})
            direction = str(body.get("dir") or "next").strip().lower()
            if direction == "prev":
                updated = self.store.set_swipe(message_id, user["id"], max(0, idx - 1))
                return ok_response({"message": updated})
            # next
            if swipes and idx < len(swipes) - 1:
                updated = self.store.set_swipe(message_id, user["id"], idx + 1)
                return ok_response({"message": updated})
            # generate a new swipe
            try:
                self.store.require_credit_points(user["id"], CHAT_MESSAGE_COST)
            except ValueError as exc:
                return error_response(str(exc), 402)
            conv_id = msg.get("conversation_id") or ""
            conv = next((c for c in self.store.list_conversations(user["id"], 200) if c.get("id") == conv_id), None)
            all_msgs = self.store.list_messages(conv_id, user["id"])
            target_idx = next((i for i, m in enumerate(all_msgs) if m.get("id") == message_id), len(all_msgs) - 1)
            history = all_msgs[:target_idx]
            last_user = ""
            for m in reversed(history):
                if m.get("role") == "user":
                    last_user = str(m.get("content") or "")
                    break
            app_id = (conv or {}).get("app_id") or ""
            try:
                with GENERATION_LIMITER.acquire(user["id"], self.client_ip(), "swipe_new"):
                    _app, reply = regenerate_reply_for_app(
                        self.store, user["id"], app_id,
                        history=history, last_user_content=last_user, app_name=(conv or {}).get("app_name") or "", conversation_id=conv_id,
                        model_override=model_override,
                    )
                    updated = self.store.append_swipe(message_id, user["id"], reply)
                    charge = self.store.spend_credit_points(
                        user["id"],
                        CHAT_MESSAGE_COST,
                        payload={"app_id": app_id, "conversation_id": conv_id, "message_id": message_id, "action": "swipe_new"},
                    )
            except GenerationLimitError as exc:
                return error_response(str(exc), 429)
            payload = {"message": updated}
            payload.update(charge)
            return ok_response(payload)

        if normalized.startswith("console/api/web/messages/") and normalized.endswith("/edit"):
            if not isinstance(body, dict):
                return error_response("invalid body")
            parts = normalized.split("/")
            message_id = parts[4] if len(parts) >= 5 else ""
            new_content = str(body.get("content") or "").strip()
            if not new_content:
                return error_response("content is required")
            updated = self.store.update_message_content(message_id, user["id"], new_content)
            if not updated:
                return error_response("message not found", 404)
            return ok_response({"message": updated})

        if normalized.startswith("console/api/web/messages/") and normalized.endswith("/delete"):
            parts = normalized.split("/")
            message_id = parts[4] if len(parts) >= 5 else ""
            ok = self.store.delete_message(message_id, user["id"])
            return ok_response({"deleted": ok})

        if normalized.startswith("console/api/web/messages/") and normalized.endswith("/rollback"):
            parts = normalized.split("/")
            message_id = parts[4] if len(parts) >= 5 else ""
            result = self.store.rollback_conversation_to_message(message_id, user["id"])
            if not result:
                return error_response("message not found", 404)
            return ok_response(result)

        # User persona (the {{user}} the model role-plays opposite)
        if normalized == "console/api/web/persona":
            if self.command.upper() == "POST" and isinstance(body, dict):
                p = self.store.set_persona(user["id"], body.get("name") or "", body.get("description") or "")
                return ok_response(p)
            return ok_response(self.store.get_persona(user["id"]))

        if normalized == "console/api/web/memories":
            if self.command.upper() == "POST":
                if not isinstance(body, dict):
                    return error_response("invalid body")
                try:
                    memory = self.store.save_memory(user["id"], body)
                except ValueError as exc:
                    return error_response(str(exc), 400)
                return ok_response(memory)
            app_id = parse_query_str(query, "app_id", "")
            conversation_id = parse_query_str(query, "conversation_id", "")
            memories = self.store.list_memories(user["id"], app_id, conversation_id=conversation_id, include_global=True)
            return ok_response({"list": memories, "total": len(memories)})

        if normalized.startswith("console/api/web/memories/") and normalized.endswith("/delete"):
            parts = normalized.split("/")
            memory_id = parts[4] if len(parts) >= 5 else ""
            ok = self.store.delete_memory(user["id"], memory_id)
            return ok_response({"deleted": ok})

        if normalized == "console/api/web/chat":
            if not isinstance(body, dict):
                return error_response("invalid body")
            app_id = str(body.get("app_id") or "").strip()
            conv_id = str(body.get("conversation_id") or "").strip()
            content = str(body.get("content") or "").strip()
            model_override = self.store.public_model_selection(body.get("model_id") or body.get("llm_model"))
            if not app_id or not content:
                return error_response("app_id and content are required")
            app_id = self.store.resolve_local_app_id(app_id)
            try:
                self.store.require_credit_points(user["id"], CHAT_MESSAGE_COST)
            except ValueError as exc:
                return error_response(str(exc), 402)
            app_name = str(body.get("app_name") or "")
            app_icon = str(body.get("app_icon") or "")
            if not conv_id:
                conv_id = str(uuid.uuid4())
            title = content[:30] if not body.get("conversation_id") else None
            try:
                with GENERATION_LIMITER.acquire(user["id"], self.client_ip(), "web_chat"):
                    self.store.upsert_conversation(conv_id, user["id"], app_id,
                                                   app_name=app_name, app_icon=app_icon, title=title)
                    self.store.append_message(conv_id, user["id"], "user", content)
                    self.store.log_event(user["id"], "chat", f"与 {app_name or app_id} 对话", {"app_id": app_id, "conversation_id": conv_id})
                    app_row, reply = chat_reply_for_app(
                        self.store,
                        user["id"],
                        app_id,
                        content,
                        app_name=app_name,
                        conversation_id=conv_id,
                        response_mode=str(body.get("response_mode") or ""),
                        model_override=model_override,
                    )
                    reply_row = self.store.append_message(conv_id, user["id"], "assistant", reply)
                    charge = self.store.spend_credit_points(
                        user["id"],
                        CHAT_MESSAGE_COST,
                        payload={"app_id": app_id, "conversation_id": conv_id, "message_id": reply_row["id"]},
                    )
            except GenerationLimitError as exc:
                return error_response(str(exc), 429)
            try:
                self.store.maybe_refresh_summary(user["id"], conv_id)
            except Exception as exc:
                log(f"auto summary refresh failed for {conv_id}: {exc}")
            payload = {
                "conversation_id": conv_id,
                "message_id": reply_row["id"],
                "reply": reply,
                "created_at": reply_row["created_at"],
                **charge,
            }
            if app_row:
                app_for_effective = dict(app_row)
                if model_override:
                    app_for_effective["llm_model"] = model_override
                effective = self.store.effective_llm_settings(app_for_effective, user_id=user["id"])
                payload["app_name"] = app_row.get("name") or app_name
                payload["model_id"] = effective.get("model") or app_row.get("llm_model") or USER_LLM_MODEL
                payload["model_preset_id"] = effective.get("preset_id") or app_for_effective.get("llm_model") or ""
            return ok_response(payload)

        if normalized.startswith("admin/api/"):
            admin_user = self.authenticated_token_user()
            if not is_admin(admin_user):
                return error_response("forbidden: admin only", 403)
            user = admin_user

            if normalized == "admin/api/whoami":
                return ok_response({
                    "id": user["id"],
                    "email": user["email"],
                    "name": user["name"],
                    "is_admin": True,
                })

            if normalized == "admin/api/stats":
                conn = self.store.conn
                user_count = conn.execute("select count(*) from users").fetchone()[0]
                admin_count = sum(1 for r in conn.execute("select id,email,is_admin from users").fetchall() if is_admin(r))
                request_count = conn.execute("select count(*) from request_log").fetchone()[0]
                total_points = conn.execute("select coalesce(sum(points),0) from recharge_orders").fetchone()[0]
                cutoff = now_ms() - 86400000
                recent_regs = conn.execute("select count(*) from users where created_at > ?", (cutoff,)).fetchone()[0]
                recent_requests = conn.execute("select count(*) from request_log where ts > ?", (cutoff,)).fetchone()[0]
                total_balance = conn.execute("select coalesce(sum(points),0) from users").fetchone()[0]
                order_count = conn.execute("select count(*) from recharge_orders").fetchone()[0]
                redeem_count = conn.execute("select count(*) from redeem_codes").fetchone()[0]
                redeem_used_count = conn.execute("select count(*) from redeem_codes where redeemed_at is not null").fetchone()[0]
                redeem_unused_count = conn.execute(
                    "select count(*) from redeem_codes where redeemed_at is null and disabled_at is null and (expires_at is null or expires_at>=?)",
                    (now_ms(),),
                ).fetchone()[0]
                issued_redeem_points = conn.execute("select coalesce(sum(points),0) from redemption_history").fetchone()[0]
                balance_split = conn.execute(
                    "select coalesce(sum(free_points),0), coalesce(sum(paid_points),0), coalesce(sum(reward_points),0) from users"
                ).fetchone()
                content_stats = self.store.content_cache_stats()
                app_counts = self.store.local_apps_count()
                status_row = conn.execute(
                    """
                    select
                      coalesce(sum(case when status>=200 and status<300 then 1 else 0 end),0) as s2,
                      coalesce(sum(case when status>=300 and status<400 then 1 else 0 end),0) as s3,
                      coalesce(sum(case when status>=400 and status<500 then 1 else 0 end),0) as s4,
                      coalesce(sum(case when status>=500 then 1 else 0 end),0) as s5
                    from request_log
                    """
                ).fetchone()
                top_paths = conn.execute(
                    """
                    select path, count(*) as value
                    from request_log
                    where ts>?
                    group by path
                    order by value desc
                    limit 8
                    """,
                    (cutoff,),
                ).fetchall()
                return ok_response({
                    "user_count": user_count,
                    "admin_count": admin_count,
                    "request_count": request_count,
                    "total_points_issued": total_points,
                    "total_user_balance": total_balance,
                    "total_free_points": int(balance_split[0] or 0),
                    "total_paid_points": int(balance_split[1] or 0),
                    "total_reward_points": int(balance_split[2] or 0),
                    "registrations_24h": recent_regs,
                    "requests_24h": recent_requests,
                    "recharge_order_count": order_count,
                    "redeem_code_count": redeem_count,
                    "redeem_code_used_count": redeem_used_count,
                    "redeem_code_unused_count": redeem_unused_count,
                    "redeem_points_issued": issued_redeem_points,
                    "content_cache": content_stats,
                    "beta": self.store.beta_registration_snapshot(),
                    "generation_concurrency": GENERATION_LIMITER.snapshot(),
                    "charts": {
                        "daily_users": daily_count_series(conn, "users", "created_at", 7),
                        "daily_requests": daily_count_series(conn, "request_log", "ts", 7),
                        "request_status": [
                            {"label": "2xx", "value": int(status_row["s2"] or 0), "tone": "green"},
                            {"label": "3xx", "value": int(status_row["s3"] or 0), "tone": "blue"},
                            {"label": "4xx", "value": int(status_row["s4"] or 0), "tone": "yellow"},
                            {"label": "5xx", "value": int(status_row["s5"] or 0), "tone": "red"},
                        ],
                        "points_split": [
                            {"label": "免费额度", "value": int(balance_split[0] or 0), "tone": "blue"},
                            {"label": "充值额度", "value": int(balance_split[1] or 0), "tone": "green"},
                            {"label": "奖励额度", "value": int(balance_split[2] or 0), "tone": "purple"},
                        ],
                        "app_sources": [
                            {"label": "同步角色", "value": int(app_counts.get("upstream") or 0), "tone": "blue"},
                            {"label": "官方角色", "value": int(app_counts.get("admin") or 0), "tone": "purple"},
                            {"label": "用户角色", "value": int(app_counts.get("user") or 0), "tone": "green"},
                        ],
                        "top_paths": [{"label": r["path"], "value": int(r["value"] or 0)} for r in top_paths],
                    },
                })

            if normalized == "admin/api/content-cache/stats":
                return ok_response(self.store.content_cache_stats())

            if normalized == "admin/api/site-settings":
                if self.command.upper() == "GET":
                    return ok_response(self.store.site_settings())
                if self.command.upper() == "POST":
                    if not isinstance(body, dict):
                        return error_response("invalid body")
                    return ok_response(self.store.update_site_settings(body))
                return error_response("method not allowed", 405)

            if normalized == "admin/api/llm-settings":
                if self.command.upper() == "GET":
                    return ok_response(self.store.public_llm_settings())
                if self.command.upper() == "POST":
                    if not isinstance(body, dict):
                        return error_response("invalid body")
                    try:
                        return ok_response(self.store.update_llm_settings(body))
                    except (TypeError, ValueError) as exc:
                        return error_response(f"invalid llm settings: {exc}", 400)
                return error_response("method not allowed", 405)

            if normalized == "admin/api/tavo-plugins":
                return ok_response({"list": self.store.list_tavo_plugins(include_manifest=True)})

            if normalized == "admin/api/tavo-plugins/import":
                if self.command.upper() != "POST" or not isinstance(body, dict):
                    return error_response("invalid body")
                try:
                    item = self.store.import_tavo_plugin(
                        str(body.get("package_file") or body.get("file") or body.get("data_url") or ""),
                        str(body.get("filename") or body.get("file_name") or ""),
                    )
                except ValueError as exc:
                    return error_response(str(exc), 400)
                return ok_response({"plugin": item})

            if normalized.startswith("admin/api/tavo-plugins/") and normalized.endswith("/toggle"):
                if self.command.upper() != "POST":
                    return error_response("method not allowed", 405)
                parts = normalized.split("/")
                plugin_id = parts[3] if len(parts) >= 4 else ""
                enabled = True
                if isinstance(body, dict) and "enabled" in body:
                    enabled = bool(body.get("enabled"))
                updated = self.store.set_tavo_plugin_enabled(plugin_id, enabled)
                if not updated:
                    return error_response("plugin not found", 404)
                return ok_response({"plugin": updated})

            if normalized.startswith("admin/api/tavo-plugins/") and normalized.endswith("/delete"):
                if self.command.upper() != "POST":
                    return error_response("method not allowed", 405)
                parts = normalized.split("/")
                plugin_id = parts[3] if len(parts) >= 4 else ""
                deleted = self.store.delete_tavo_plugin(plugin_id)
                return ok_response({"deleted": deleted})

            if normalized == "admin/api/apps":
                page = parse_query_int(query, "page", 1, 1, 100000)
                page_size = parse_query_int(query, "page_size", 30, 1, 100)
                source = parse_query_str(query, "source", "admin").strip() or "admin"
                search = parse_query_str(query, "q", "").strip()
                lightweight = truthy(parse_query_str(query, "lightweight", "0"))
                rows, total = self.store.list_local_apps(
                    source=source if source != "all" else None,
                    search=search,
                    page=page,
                    page_size=page_size,
                    only_public=False,
                    only_published=False,
                    lightweight=lightweight,
                )
                mapper = local_app_to_list_card if lightweight else local_app_to_card
                return ok_response({"list": [mapper(r) for r in rows], "total": total, "page": page, "page_size": page_size})

            if normalized == "admin/api/apps/create":
                if not isinstance(body, dict):
                    return error_response("invalid body")
                data = dict(body)
                data["cover_url"] = normalize_cover_input(data.get("cover_url") or data.get("cover") or "")
                row = self.store.create_admin_app(data)
                return ok_response(local_app_to_card(dict(row)))

            if normalized == "admin/api/apps/import":
                if self.command.upper() != "POST":
                    return error_response("method not allowed", 405)
                if not isinstance(body, (dict, list)):
                    return error_response("invalid body")
                items = extract_import_items(body)
                if not items:
                    return error_response("no role cards found", 400)
                result = self.store.import_admin_apps(items, created_by=user["id"])
                return ok_response(result)

            if normalized == "admin/api/apps/bulk-update":
                if self.command.upper() != "POST":
                    return error_response("method not allowed", 405)
                if not isinstance(body, dict):
                    return error_response("invalid body")
                try:
                    result = self.store.bulk_update_admin_apps(body.get("ids") or body.get("app_ids") or [], body)
                except ValueError as exc:
                    return error_response(str(exc), 400)
                return ok_response(result)

            if normalized.startswith("admin/api/apps/") and len(normalized.split("/")) == 4:
                if self.command.upper() != "GET":
                    return error_response("method not allowed", 405)
                app_id = normalized.split("/")[3]
                row = self.store.get_local_app(app_id)
                if not row:
                    return error_response("not found", 404)
                return ok_response(local_app_to_card(dict(row)))

            if normalized.startswith("admin/api/apps/") and normalized.endswith("/update"):
                if not isinstance(body, dict):
                    return error_response("invalid body")
                app_id = normalized.split("/")[3]
                data = dict(body)
                if "cover_url" in data or "cover" in data:
                    data["cover_url"] = normalize_cover_input(data.get("cover_url") or data.get("cover") or "")
                row = self.store.update_admin_app(app_id, data)
                if not row:
                    return error_response("not found", 404)
                return ok_response(local_app_to_card(dict(row)))

            if normalized.startswith("admin/api/apps/") and normalized.endswith("/delete"):
                app_id = normalized.split("/")[3]
                ok = self.store.delete_admin_app(app_id)
                return ok_response({"deleted": ok})

            if normalized == "admin/api/users":
                page = parse_query_int(query, "page", 1, 1, 100000)
                limit = parse_query_int(query, "limit", 20, 1, 200)
                search = parse_query_str(query, "search").strip()
                offset = (page - 1) * limit
                conn = self.store.conn
                if search:
                    pattern = f"%{search}%"
                    total = conn.execute(
                        "select count(*) from users where email like ? or name like ? or id like ?",
                        (pattern, pattern, pattern),
                    ).fetchone()[0]
                    rows = conn.execute(
                        "select id, email, name, points, free_points, paid_points, reward_points, is_admin, created_at, updated_at from users "
                        "where email like ? or name like ? or id like ? "
                        "order by created_at desc limit ? offset ?",
                        (pattern, pattern, pattern, limit, offset),
                    ).fetchall()
                else:
                    total = conn.execute("select count(*) from users").fetchone()[0]
                    rows = conn.execute(
                        "select id, email, name, points, free_points, paid_points, reward_points, is_admin, created_at, updated_at from users "
                        "order by created_at desc limit ? offset ?",
                        (limit, offset),
                    ).fetchall()
                return ok_response({
                    "users": [admin_user_json(r) for r in rows],
                    "total": total,
                    "page": page,
                    "limit": limit,
                })

            if normalized.startswith("admin/api/users/") and normalized.endswith("/admin"):
                target_id = normalized.split("/")[3]
                if not isinstance(body, dict):
                    return error_response("invalid body")
                if target_id == user["id"] and not bool(body.get("is_admin")):
                    return error_response("不能撤销当前登录账号自己的管理员权限", 400)
                target = self.store.get_user_by_id(target_id)
                if not target:
                    return error_response("user not found", 404)
                try:
                    updated = self.store.set_user_admin(target_id, bool(body.get("is_admin")))
                except ValueError as exc:
                    return error_response(str(exc), 400)
                return ok_response(admin_user_json(updated))

            if normalized.startswith("admin/api/users/") and normalized.endswith("/points"):
                target_id = normalized.split("/")[3]
                if not isinstance(body, dict):
                    return error_response("invalid body")
                target = self.store.get_user_by_id(target_id)
                if not target:
                    return error_response("user not found", 404)
                try:
                    delta = int(body.get("delta") or 0)
                except (ValueError, TypeError):
                    return error_response("invalid delta")
                if delta == 0:
                    return error_response("delta cannot be zero")
                updated = self.store.add_points(target_id, delta)
                return ok_response({
                    "id": updated["id"],
                    "email": updated["email"],
                    "name": updated["name"],
                    "points": updated["points"],
                    "balance": credit_balance_json(updated),
                    "delta": delta,
                })

            if normalized == "admin/api/redeem-codes":
                page = parse_query_int(query, "page", 1, 1, 100000)
                limit = parse_query_int(query, "limit", 50, 1, 200)
                status = parse_query_str(query, "status", "").strip()
                rows, total = self.store.list_redeem_codes(page=page, limit=limit, status=status)
                return ok_response({"codes": rows, "list": rows, "total": total, "page": page, "limit": limit})

            if normalized == "admin/api/redeem-codes/create":
                if self.command.upper() != "POST":
                    return error_response("method not allowed", 405)
                if not isinstance(body, dict):
                    return error_response("invalid body")
                try:
                    expires_raw = body.get("expires_at")
                    expires_at = int(expires_raw) if expires_raw not in (None, "", 0, "0") else None
                    codes = self.store.create_redeem_codes(
                        count=int(body.get("count") or 1),
                        points=int(body.get("points") or 1),
                        point_type=str(body.get("point_type") or "paid"),
                        note=str(body.get("note") or ""),
                        expires_at=expires_at,
                        created_by=user["id"],
                    )
                except (TypeError, ValueError) as exc:
                    return error_response(str(exc), 400)
                return ok_response({"codes": codes, "count": len(codes)})

            if normalized.startswith("admin/api/redeem-codes/") and normalized.endswith("/disable"):
                if self.command.upper() != "POST":
                    return error_response("method not allowed", 405)
                code = unquote(normalized.split("/")[3])
                try:
                    disabled = self.store.disable_redeem_code(code)
                except ValueError as exc:
                    return error_response(str(exc), 400)
                if not disabled:
                    return error_response("redeem code not found", 404)
                return ok_response({"disabled": True, "code": code.strip().upper()})

            if normalized == "admin/api/request-log":
                page = parse_query_int(query, "page", 1, 1, 100000)
                limit = parse_query_int(query, "limit", 50, 1, 200)
                method_filter = parse_query_str(query, "method").strip().upper()
                path_filter = parse_query_str(query, "path").strip()
                offset = (page - 1) * limit
                conn = self.store.conn
                where = []
                params: list[object] = []
                if method_filter:
                    where.append("method = ?")
                    params.append(method_filter)
                if path_filter:
                    where.append("path like ?")
                    params.append(f"%{path_filter}%")
                where_sql = (" where " + " and ".join(where)) if where else ""
                total = conn.execute(f"select count(*) from request_log{where_sql}", params).fetchone()[0]
                rows = conn.execute(
                    f"select id, ts, method, path, query, status from request_log{where_sql} "
                    "order by id desc limit ? offset ?",
                    (*params, limit, offset),
                ).fetchall()
                return ok_response({
                    "logs": [dict(r) for r in rows],
                    "total": total,
                    "page": page,
                    "limit": limit,
                })

            if normalized.startswith("admin/api/request-log/"):
                try:
                    log_id = int(normalized.rsplit("/", 1)[-1])
                except (ValueError, TypeError):
                    return error_response("invalid log id")
                row = self.store.conn.execute(
                    "select * from request_log where id=?", (log_id,)
                ).fetchone()
                if not row:
                    return error_response("log not found", 404)
                return ok_response(dict(row))

            if normalized == "admin/api/recharge-orders":
                page = parse_query_int(query, "page", 1, 1, 100000)
                limit = parse_query_int(query, "limit", 50, 1, 200)
                offset = (page - 1) * limit
                conn = self.store.conn
                total = conn.execute("select count(*) from recharge_orders").fetchone()[0]
                rows = conn.execute(
                    "select r.id, r.order_id, r.user_id, r.product_id, r.points, "
                    "r.created_at, r.remote_addr, u.email, u.name "
                    "from recharge_orders r left join users u on u.id = r.user_id "
                    "order by r.id desc limit ? offset ?",
                    (limit, offset),
                ).fetchall()
                return ok_response({
                    "orders": [dict(r) for r in rows],
                    "total": total,
                    "page": page,
                    "limit": limit,
                })

            return error_response("admin endpoint not found", 404)

        if normalized.startswith("go/") or normalized.startswith("console/"):
            return proxy_json(normalized, query, {
                "result": "success",
                "code": "200",
                "message": "OK",
                "status": 200,
                "data": {},
                "items": [],
                "list": [],
                "total": 0,
                "path": path,
            })

        return rebrand_data({
            "result": "success",
            "code": 0,
            "msg": "local fallback",
            "data": {},
            "items": [],
            "list": [],
            "total": 0,
            "path": path,
        })


class VerificationStore:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as conn:
            conn.executescript("""
                create table if not exists email_codes(
                    id integer primary key, email text not null, code text not null,
                    purpose text not null, created_at integer not null, expires_at integer not null,
                    consumed_at integer, remote_addr text default '', send_count integer default 0,
                    last_sent_at integer default 0
                );
                create index if not exists idx_mail_codes_active on email_codes(email,purpose,expires_at);
                create table if not exists email_delivery_attempts(
                    id text primary key, email_code_id integer, purpose text, email_domain text,
                    provider text, status text, provider_message_id text, error_class text,
                    created_at integer, accepted_at integer, updated_at integer
                );
            """)

    def connect(self):
        conn = sqlite3.connect(str(self.path), timeout=5)
        conn.row_factory = sqlite3.Row
        conn.execute("pragma journal_mode=WAL")
        conn.execute("pragma busy_timeout=5000")
        return conn

    def create_or_reuse(self, email: str, remote_addr: str, purpose: str = "register") -> dict:
        ts = int(time.time())
        value = normalize_email(email)
        with self.connect() as conn:
            row = conn.execute("select * from email_codes where email=? and purpose=? and consumed_at is null and expires_at>=? order by id desc limit 1", (value, purpose, ts)).fetchone()
            if row and ts - int(row["last_sent_at"] or 0) < 60:
                return {"code": row["code"], "id": row["id"], "retry_after": 60 - (ts - int(row["last_sent_at"] or 0)), "send": False, "reused": True}
            if row:
                conn.execute("update email_codes set send_count=send_count+1,last_sent_at=? where id=?", (ts, row["id"]))
                return {"code": row["code"], "id": row["id"], "retry_after": 60, "send": True, "reused": True}
            code = f"{random.SystemRandom().randint(0, 999999):06d}"
            cur = conn.execute("insert into email_codes(email,code,purpose,created_at,expires_at,remote_addr,send_count,last_sent_at) values(?,?,?,?,?,?,1,?)", (value, code, purpose, ts, ts + CODE_TTL_SECONDS, remote_addr or "", ts))
            return {"code": code, "id": cur.lastrowid, "retry_after": 60, "send": True, "reused": False}

    def verify(self, email: str, code: str, purpose: str = "register") -> bool:
        ts = int(time.time())
        with self.connect() as conn:
            row = conn.execute("select id,code from email_codes where email=? and purpose=? and consumed_at is null and expires_at>=? order by id desc limit 1", (normalize_email(email), purpose, ts)).fetchone()
            if not row or row["code"] != str(code or "").strip(): return False
            conn.execute("update email_codes set consumed_at=? where email=? and purpose=? and consumed_at is null", (ts, normalize_email(email), purpose))
            return True

    def record(self, code_id: int, email: str, purpose: str, status: str, provider_id: str = "", error: str = ""):
        ts = int(time.time()); attempt_id = uuid.uuid4().hex
        with self.connect() as conn:
            conn.execute("insert into email_delivery_attempts values(?,?,?,?,?,?,?,?,?,?,?)", (attempt_id, code_id, purpose, email.rsplit('@',1)[-1], "resend", status, provider_id, error[:80], ts, ts if status == 'accepted' else None, ts))


class LocalServer(ThreadingHTTPServer):
    def __init__(self, address: tuple[str, int], handler_class, store: Store, verification_store: VerificationStore):
        super().__init__(address, handler_class)
        self.store = store
        self.verification_store = verification_store


def main() -> int:
    parser = argparse.ArgumentParser(description="Local backend for 惑梦（Homer） CTF APK server binding.")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    args = parser.parse_args()

    store = Store(args.db)
    global ACTIVE_STORE, MEDIA_DIR
    ACTIVE_STORE = store
    MEDIA_DIR = Path(os.environ.get("MEDIA_DIR") or (args.db.resolve().parent / "media"))
    (MEDIA_DIR / "cover").mkdir(parents=True, exist_ok=True)
    (MEDIA_DIR / "profile").mkdir(parents=True, exist_ok=True)
    (MEDIA_DIR / "generated").mkdir(parents=True, exist_ok=True)
    mail_db = Path(os.environ.get("MAIL_DB_PATH") or (args.db.resolve().parent / "verification_mail.sqlite3"))
    verification_store = VerificationStore(mail_db)
    server = LocalServer((args.host, args.port), Handler, store, verification_store)
    log(f"listening on http://{args.host}:{args.port}/")
    log(f"sqlite db: {args.db}")
    log(f"verification sqlite db: {mail_db}")
    log(f"content mode: {CONTENT_MODE}")
    log("emulator APK server-url should be: http://10.0.2.2:8000/")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        log("stopping")
        return 0
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
