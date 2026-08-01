#!/usr/bin/env python3
"""Safe lifecycle manager for Homer offline development on Windows.

Commands:

    py -3 tools/offline_dev.py start
    py -3 tools/offline_dev.py status
    py -3 tools/offline_dev.py stop
    py -3 tools/offline_dev.py reset

All mutable state is isolated under ``output/offline-dev``.  The manager only
terminates PIDs from its own registry after verifying their command lines.
"""

from __future__ import annotations

import argparse
import contextlib
import datetime as dt
import hashlib
import json
import os
import secrets
import shutil
import socket
import sqlite3
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path


class OfflineDevError(RuntimeError):
    pass


ROOT = Path(__file__).resolve().parents[1]
TOOLS_DIR = ROOT / "tools"
OUTPUT_DIR = ROOT / "output"
STATE_DIR = OUTPUT_DIR / "offline-dev"
DATA_DIR = STATE_DIR / "data"
LOG_DIR = STATE_DIR / "logs"
RUNTIME_DIR = STATE_DIR / "runtime"
MEDIA_DIR = DATA_DIR / "media"
DB_PATH = DATA_DIR / "ai_fengyue_local.sqlite3"
MAIL_DB_PATH = DATA_DIR / "verification_mail.sqlite3"
PROCESS_FILE = RUNTIME_DIR / "processes.json"
CREDENTIALS_FILE = RUNTIME_DIR / "credentials.json"
SECRET_FILE = RUNTIME_DIR / "auth-token-secret.txt"
SEED_MARKER_FILE = RUNTIME_DIR / "seed-complete.json"
LOCK_FILE = RUNTIME_DIR / "manager.lock"

SEED_STATE_DIR = ROOT / "output" / "zip-1-repack" / "local-server"
SEED_DB_PATH = SEED_STATE_DIR / "ai_fengyue_local.sqlite3"
SEED_MAIL_DB_PATH = SEED_STATE_DIR / "verification_mail.sqlite3"
SEED_TOOL = TOOLS_DIR / "offline_dev_seed.py"
BACKEND_SCRIPT = TOOLS_DIR / "ai_fengyue_local_server.py"
PROXY_SCRIPT = TOOLS_DIR / "offline_dev_proxy.py"
SILLYTAVERN_DIR = ROOT / "sillytavern-runtime"
SILLYTAVERN_SERVER = SILLYTAVERN_DIR / "server.js"
SILLYTAVERN_DATA_DIR = STATE_DIR / "sillytavern-data"
SILLYTAVERN_NODE_MODULES = SILLYTAVERN_DIR / "node_modules"


def _needs_ascii_alias(*paths: Path) -> bool:
    return os.name == "nt" and any(not str(path).isascii() for path in paths)


def _windows_alias_root() -> Path:
    local_app_data = os.environ.get("LOCALAPPDATA") or os.environ.get("TEMP")
    if not local_app_data or not str(local_app_data).isascii():
        raise OfflineDevError(
            "SillyTavern needs an ASCII-only launch path on Windows, but LOCALAPPDATA/TEMP "
            "is unavailable or contains non-ASCII characters"
        )
    workspace_key = hashlib.sha256(str(ROOT).casefold().encode("utf-8")).hexdigest()[:12]
    return Path(local_app_data) / "HomerOfflineDev" / workspace_key


if _needs_ascii_alias(SILLYTAVERN_DIR, SILLYTAVERN_DATA_DIR):
    SILLYTAVERN_ALIAS_ROOT = _windows_alias_root()
    SILLYTAVERN_LAUNCH_DIR = SILLYTAVERN_ALIAS_ROOT / "runtime"
    SILLYTAVERN_LAUNCH_STATE_DIR = SILLYTAVERN_ALIAS_ROOT / "state"
    SILLYTAVERN_LAUNCH_DATA_DIR = SILLYTAVERN_LAUNCH_STATE_DIR / "sillytavern-data"
else:
    SILLYTAVERN_ALIAS_ROOT = None
    SILLYTAVERN_LAUNCH_DIR = SILLYTAVERN_DIR
    SILLYTAVERN_LAUNCH_STATE_DIR = STATE_DIR
    SILLYTAVERN_LAUNCH_DATA_DIR = SILLYTAVERN_DATA_DIR

BACKEND_HOST = "127.0.0.1"
BACKEND_PORT = 8000
PROXY_HOST = "127.0.0.1"
PROXY_PORT = 8080
PUBLIC_BASE_URL = f"http://{PROXY_HOST}:{PROXY_PORT}"
SILLYTAVERN_HOST = "127.0.0.1"
SILLYTAVERN_PORT = 8091
SILLYTAVERN_INTERNAL_URL = f"http://{SILLYTAVERN_HOST}:{SILLYTAVERN_PORT}"
SILLYTAVERN_PUBLIC_URL = f"{PUBLIC_BASE_URL}/module/dialogue"

MINIMUM_PYTHON = (3, 10)
ROLES = ("backend", "proxy", "sillytavern")

EXTERNAL_ENV_EXACT = {
    "AIFADIAN_URL",
    "ALLOW_EMAIL_SEND_FAILURE",
    "ALLOW_ANY_REGISTER_CODE",
    "ANTHROPIC_API_KEY",
    "ANTHROPIC_BASE_URL",
    "APK_DOWNLOAD_ENABLED",
    "CTF_DIRECT_RECHARGE_ENABLED",
    "GEMINI_API_KEY",
    "GOOGLE_API_KEY",
    "HTTP_PROXY",
    "HTTPS_PROXY",
    "ALL_PROXY",
    "LLM_API_KEY",
    "LLM_BASE_URL",
    "OPENAI_API_KEY",
    "OPENAI_BASE_URL",
    "PAYMENT_CHANNEL_ENABLED",
    "RESEND_API_KEY",
    "RESEND_API_URL",
    "SENDMAIL_PATH",
    "SMTP_FROM",
    "SMTP_HOST",
    "SMTP_PASSWORD",
    "SMTP_PORT",
    "SMTP_SSL",
    "SMTP_STARTTLS",
    "SMTP_USER",
    "UPSTREAM_CONTENT_BASE",
    "USER_BYOK_ENABLED",
    "USER_LLM_API_KEY",
    "USER_LLM_BASE_URL",
    "ZPAY_ALLOWED_TYPES",
    "ZPAY_ENABLED",
    "ZPAY_GATEWAY",
    "ZPAY_KEY",
    "ZPAY_PAYMENT_TYPE",
    "ZPAY_PID",
}

def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def ensure_supported_python() -> None:
    if sys.version_info < MINIMUM_PYTHON:
        raise OfflineDevError(
            "Python 3.10 or newer is required; current runtime is "
            + ".".join(map(str, sys.version_info[:3]))
        )


def ensure_safe_state_path() -> None:
    expected_output = OUTPUT_DIR.resolve()
    resolved = STATE_DIR.resolve()
    if resolved != (expected_output / "offline-dev") or resolved.parent != expected_output:
        raise OfflineDevError(f"unsafe offline state path: {resolved}")


def ensure_directories() -> None:
    ensure_safe_state_path()
    for path in (DATA_DIR, LOG_DIR, RUNTIME_DIR, MEDIA_DIR):
        path.mkdir(parents=True, exist_ok=True)


def ensure_windows_junction(alias: Path, target: Path) -> None:
    """Create a verified directory junction without replacing an existing path."""
    target = target.resolve()
    target.mkdir(parents=True, exist_ok=True)
    if os.path.lexists(alias):
        try:
            matches = os.path.samefile(alias, target)
        except OSError as exc:
            raise OfflineDevError(f"could not verify SillyTavern path alias {alias}: {exc}") from exc
        if not matches:
            raise OfflineDevError(
                f"refusing to replace existing SillyTavern path alias {alias}; expected target {target}"
            )
        return

    alias.parent.mkdir(parents=True, exist_ok=True)
    child_env = os.environ.copy()
    child_env["HOMER_JUNCTION_ALIAS"] = str(alias)
    child_env["HOMER_JUNCTION_TARGET"] = str(target)
    script = (
        "$ErrorActionPreference='Stop';"
        "$alias=$env:HOMER_JUNCTION_ALIAS;"
        "$target=$env:HOMER_JUNCTION_TARGET;"
        "New-Item -ItemType Junction -Path $alias -Target $target | Out-Null"
    )
    result = subprocess.run(
        ["powershell.exe", "-NoLogo", "-NoProfile", "-NonInteractive", "-Command", script],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=20,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        env=child_env,
        check=False,
    )
    if result.returncode != 0:
        message = (result.stderr or result.stdout or "junction creation failed").strip()
        raise OfflineDevError(f"could not create SillyTavern path alias {alias}: {message}")
    try:
        matches = os.path.samefile(alias, target)
    except OSError as exc:
        raise OfflineDevError(f"could not verify new SillyTavern path alias {alias}: {exc}") from exc
    if not matches:
        raise OfflineDevError(f"SillyTavern path alias {alias} does not resolve to {target}")


def ensure_sillytavern_launch_paths() -> None:
    if SILLYTAVERN_ALIAS_ROOT is None:
        return
    ensure_windows_junction(SILLYTAVERN_LAUNCH_DIR, SILLYTAVERN_DIR)
    ensure_windows_junction(SILLYTAVERN_LAUNCH_STATE_DIR, STATE_DIR)


def _write_private_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + f".{os.getpid()}.tmp")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    fd = os.open(temp, flags, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp, path)
        with contextlib.suppress(OSError):
            path.chmod(0o600)
    finally:
        with contextlib.suppress(FileNotFoundError):
            temp.unlink()


def _write_private_json(path: Path, value: object) -> None:
    _write_private_text(path, json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def load_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return default


def ensure_secret() -> str:
    try:
        secret = SECRET_FILE.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        secret = ""
    if len(secret.encode("utf-8")) < 32:
        secret = secrets.token_urlsafe(48)
        _write_private_text(SECRET_FILE, secret + "\n")
    return secret


def ensure_credentials() -> dict[str, str]:
    current = load_json(CREDENTIALS_FILE, {})
    email = str(current.get("email") or "").strip().lower()
    password = str(current.get("password") or "")
    if email and len(password) >= 12:
        return {"email": email, "password": password}

    credentials = {
        "email": "admin@homer.local",
        "password": "Homer-" + secrets.token_urlsafe(18) + "-9A",
        "generated_at": utc_now(),
    }
    _write_private_json(CREDENTIALS_FILE, credentials)
    return {"email": credentials["email"], "password": credentials["password"]}


def backup_sqlite(source: Path, destination: Path) -> bool:
    if not source.is_file():
        return False
    destination.parent.mkdir(parents=True, exist_ok=True)
    temp = destination.with_name(destination.name + f".{os.getpid()}.tmp")
    with contextlib.suppress(FileNotFoundError):
        temp.unlink()
    source_uri = source.resolve().as_uri() + "?mode=ro"
    source_conn = sqlite3.connect(source_uri, uri=True, timeout=30)
    destination_conn = sqlite3.connect(str(temp), timeout=30)
    try:
        source_conn.backup(destination_conn)
        result = destination_conn.execute("pragma quick_check").fetchone()
        if not result or result[0] != "ok":
            raise OfflineDevError(f"SQLite seed quick_check failed: {source.name}")
        destination_conn.commit()
    finally:
        destination_conn.close()
        source_conn.close()
    os.replace(temp, destination)
    return True


def offline_environment(*, include_credentials: bool = False) -> dict[str, str]:
    env = dict(os.environ)
    for key in list(env):
        upper = key.upper()
        if (
            upper in EXTERNAL_ENV_EXACT
            or upper.endswith("_API_KEY")
            or upper.endswith("_ACCESS_TOKEN")
            or upper.startswith(("AWS_", "ANTHROPIC_", "GEMINI_", "OPENAI_", "RESEND_", "SMTP_", "ZPAY_"))
        ):
            env.pop(key, None)

    secret = ensure_secret()
    admin_email = ensure_credentials()["email"]
    env.update(
        {
            "ADMIN_EMAILS": admin_email,
            "ALLOWED_CORS_ORIGINS": (
                f"{PUBLIC_BASE_URL},http://localhost:{PROXY_PORT}"
            ),
            "ALLOW_ANY_REGISTER_CODE": "1",
            "ALLOW_EMAIL_SEND_FAILURE": "1",
            "APK_DOWNLOAD_ENABLED": "0",
            "AUTH_COOKIE_SAMESITE": "Lax",
            "AUTH_COOKIE_SECURE": "0",
            "AUTH_TOKEN_SECRET": secret,
            "CONTENT_MODE": "offline",
            "CTF_DIRECT_RECHARGE_ENABLED": "0",
            "HOMER_OFFLINE_DEV": "1",
            "HOMER_OFFLINE_DB": str(DB_PATH),
            "HOMER_OFFLINE_STATE_DIR": str(STATE_DIR),
            "MAIL_DB_PATH": str(MAIL_DB_PATH),
            "MEDIA_DIR": str(MEDIA_DIR),
            "NO_PROXY": "127.0.0.1,localhost",
            "OFFLINE_DEV_MODE": "1",
            "PAYMENT_CHANNEL_ENABLED": "0",
            "PUBLIC_BASE_URL": PUBLIC_BASE_URL,
            "SILLYTAVERN_PUBLIC_URL": SILLYTAVERN_PUBLIC_URL,
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONUNBUFFERED": "1",
            "UPSTREAM_CONTENT_BASE": "http://127.0.0.1:9/",
            "USER_BYOK_ENABLED": "0",
            "ZPAY_ENABLED": "0",
        }
    )
    if include_credentials:
        credentials = ensure_credentials()
        env["HOMER_OFFLINE_ADMIN_EMAIL"] = credentials["email"]
        env["HOMER_OFFLINE_ADMIN_PASSWORD"] = credentials["password"]
    else:
        env.pop("HOMER_OFFLINE_ADMIN_EMAIL", None)
        env.pop("HOMER_OFFLINE_ADMIN_PASSWORD", None)
    return env


def run_seed_tool() -> bool:
    if not SEED_TOOL.is_file():
        return False
    command = [sys.executable, str(SEED_TOOL), "--db", str(DB_PATH)]
    result = subprocess.run(
        command,
        cwd=str(ROOT),
        env=offline_environment(include_credentials=True),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=120,
        check=False,
    )
    if result.returncode != 0:
        # Never echo the environment or credentials.  The seed tool is also
        # expected not to include credentials in its own diagnostics.
        message = (result.stderr or "seed tool failed").strip()[-1200:]
        credentials = ensure_credentials()
        for sensitive in (credentials.get("password"), ensure_secret()):
            if sensitive:
                message = message.replace(sensitive, "[REDACTED]")
        raise OfflineDevError(f"offline seed initialization failed: {message}")
    _write_private_json(
        SEED_MARKER_FILE,
        {
            "seeded_at": utc_now(),
            "tool": SEED_TOOL.name,
            "tool_sha256": hashlib.sha256(SEED_TOOL.read_bytes()).hexdigest(),
        },
    )
    return True


def initialize_state() -> None:
    ensure_directories()
    ensure_secret()
    ensure_credentials()

    if not DB_PATH.exists():
        backup_sqlite(SEED_DB_PATH, DB_PATH)
    if not MAIL_DB_PATH.exists():
        backup_sqlite(SEED_MAIL_DB_PATH, MAIL_DB_PATH)

    if not SEED_MARKER_FILE.exists():
        seeded = run_seed_tool()
        if not seeded:
            print(
                "WARNING: tools/offline_dev_seed.py is not present; "
                "the copied development database was left unchanged.",
                file=sys.stderr,
            )


def ensure_sillytavern_dependencies() -> None:
    required = (
        SILLYTAVERN_NODE_MODULES / "express" / "package.json",
        SILLYTAVERN_NODE_MODULES / "webpack" / "package.json",
    )
    if all(path.is_file() for path in required):
        return
    npm = shutil.which("npm.cmd" if os.name == "nt" else "npm") or shutil.which("npm")
    if not npm:
        raise OfflineDevError("npm is required to install the SillyTavern runtime dependencies")
    if not (SILLYTAVERN_DIR / "package-lock.json").is_file():
        raise OfflineDevError("SillyTavern package-lock.json is missing")
    ensure_directories()
    stdout_path = LOG_DIR / "sillytavern-install.out.log"
    stderr_path = LOG_DIR / "sillytavern-install.err.log"
    print("Installing the pinned SillyTavern runtime dependencies (first start only)...")
    with stdout_path.open("ab", buffering=0) as stdout_handle, stderr_path.open("ab", buffering=0) as stderr_handle:
        result = subprocess.run(
            [npm, "ci", "--omit=dev", "--no-audit", "--no-fund"],
            cwd=str(SILLYTAVERN_DIR),
            env=offline_environment(include_credentials=False),
            stdin=subprocess.DEVNULL,
            stdout=stdout_handle,
            stderr=stderr_handle,
            timeout=15 * 60,
            check=False,
        )
    if result.returncode != 0 or not all(path.is_file() for path in required):
        raise OfflineDevError(
            "SillyTavern dependency installation failed; inspect "
            f"{stderr_path}"
        )


def process_command(role: str) -> list[str]:
    if role == "backend":
        return [
            sys.executable,
            str(BACKEND_SCRIPT),
            "--host",
            BACKEND_HOST,
            "--port",
            str(BACKEND_PORT),
            "--db",
            str(DB_PATH),
        ]
    if role == "proxy":
        return [
            sys.executable,
            str(PROXY_SCRIPT),
            "--host",
            PROXY_HOST,
            "--port",
            str(PROXY_PORT),
            "--backend",
            f"http://{BACKEND_HOST}:{BACKEND_PORT}",
            "--dialogue-runtime",
            SILLYTAVERN_INTERNAL_URL,
            "--frontend",
            str(ROOT / "frontend"),
            "--state-dir",
            str(STATE_DIR),
        ]
    if role == "sillytavern":
        node = shutil.which("node")
        if not node:
            raise OfflineDevError("Node.js is required to start the original SillyTavern runtime")
        if not SILLYTAVERN_SERVER.is_file() or not SILLYTAVERN_NODE_MODULES.is_dir():
            raise OfflineDevError(
                "SillyTavern runtime is incomplete; server.js or node_modules is missing"
            )
        command = [node]
        if SILLYTAVERN_ALIAS_ROOT is not None:
            # Node resolves junction-backed ES modules to their Unicode target by default.
            # SillyTavern's Windows startup can native-crash before listening when that
            # target contains CJK characters, so keep the verified ASCII aliases intact.
            command.extend(["--preserve-symlinks", "--preserve-symlinks-main"])
        command.extend([
            "server.js",
            "--port",
            str(SILLYTAVERN_PORT),
            "--dataRoot",
            str(SILLYTAVERN_LAUNCH_DATA_DIR),
            "--browserLaunchEnabled",
            "false",
        ])
        return command
    raise OfflineDevError(f"unknown process role: {role}")


def expected_markers(role: str) -> list[str]:
    if role == "backend":
        return [str(BACKEND_SCRIPT), str(DB_PATH), "--port", str(BACKEND_PORT)]
    if role == "proxy":
        return [str(PROXY_SCRIPT), str(STATE_DIR), "--port", str(PROXY_PORT)]
    if role == "sillytavern":
        return [
            "server.js",
            str(SILLYTAVERN_LAUNCH_DATA_DIR),
            "--port",
            str(SILLYTAVERN_PORT),
        ]
    return []


def _normalize_command(value: str) -> str:
    return str(value or "").replace("\\", "/").lower()


def windows_process_info(pid: int) -> dict | None:
    script = (
        "$ErrorActionPreference='SilentlyContinue';"
        "[Console]::OutputEncoding=[Text.UTF8Encoding]::new($false);"
        f"$p=Get-CimInstance Win32_Process -Filter \"ProcessId = {int(pid)}\";"
        "if($p){$p|Select-Object ProcessId,ExecutablePath,CommandLine,CreationDate|"
        "ConvertTo-Json -Compress}"
    )
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    result = subprocess.run(
        ["powershell.exe", "-NoLogo", "-NoProfile", "-NonInteractive", "-Command", script],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=12,
        creationflags=flags,
        check=False,
    )
    output = result.stdout.strip()
    if result.returncode != 0 or not output:
        return None
    try:
        value = json.loads(output)
    except json.JSONDecodeError:
        return None
    return value if isinstance(value, dict) else None


def posix_process_info(pid: int) -> dict | None:
    path = Path("/proc") / str(pid) / "cmdline"
    try:
        command = path.read_bytes().replace(b"\0", b" ").decode("utf-8", "replace")
    except OSError:
        return None
    return {"ProcessId": pid, "CommandLine": command}


def process_info(pid: int) -> dict | None:
    if pid <= 0:
        return None
    if os.name == "nt":
        return windows_process_info(pid)
    return posix_process_info(pid)


def record_matches_process(role: str, record: dict, info: dict | None) -> bool:
    if not info:
        return False
    try:
        if int(info.get("ProcessId")) != int(record.get("pid")):
            return False
    except (TypeError, ValueError):
        return False
    command = _normalize_command(info.get("CommandLine") or "")
    return bool(command) and all(_normalize_command(marker) in command for marker in expected_markers(role))


def load_processes() -> dict[str, dict]:
    value = load_json(PROCESS_FILE, {})
    if not isinstance(value, dict):
        return {}
    return {role: row for role, row in value.items() if role in ROLES and isinstance(row, dict)}


def save_processes(value: dict[str, dict]) -> None:
    if value:
        _write_private_json(PROCESS_FILE, value)
    else:
        with contextlib.suppress(FileNotFoundError):
            PROCESS_FILE.unlink()


def role_status(role: str, record: dict | None) -> dict:
    if not record:
        return {"role": role, "state": "not-recorded", "pid": None, "owned": False}
    try:
        pid = int(record.get("pid"))
    except (TypeError, ValueError):
        return {"role": role, "state": "invalid-record", "pid": None, "owned": False}
    info = process_info(pid)
    if info is None:
        return {"role": role, "state": "stopped", "pid": pid, "owned": False}
    owned = record_matches_process(role, record, info)
    return {
        "role": role,
        "state": "running" if owned else "pid-mismatch",
        "pid": pid,
        "owned": owned,
    }


def socket_port_in_use(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.3)
        return sock.connect_ex((host, port)) == 0


def port_owner_pid(port: int) -> int | None:
    if os.name != "nt":
        return None
    script = (
        "$ErrorActionPreference='SilentlyContinue';"
        "[Console]::OutputEncoding=[Text.UTF8Encoding]::new($false);"
        f"$c=Get-NetTCPConnection -State Listen -LocalPort {int(port)}|Select-Object -First 1;"
        "if($c){[Console]::Write($c.OwningProcess)}"
    )
    result = subprocess.run(
        ["powershell.exe", "-NoLogo", "-NoProfile", "-NonInteractive", "-Command", script],
        capture_output=True,
        text=True,
        timeout=12,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        check=False,
    )
    try:
        return int(result.stdout.strip())
    except (TypeError, ValueError):
        return None


def assert_ports_available() -> None:
    conflicts = []
    for role, host, port in (
        ("backend", BACKEND_HOST, BACKEND_PORT),
        ("proxy", PROXY_HOST, PROXY_PORT),
        ("sillytavern", SILLYTAVERN_HOST, SILLYTAVERN_PORT),
    ):
        if socket_port_in_use(host, port):
            owner = port_owner_pid(port)
            conflicts.append(f"{role} {host}:{port}" + (f" (PID {owner})" if owner else ""))
    if conflicts:
        raise OfflineDevError(
            "required local port is already in use: "
            + ", ".join(conflicts)
            + ". Stop that application or choose a different port before starting Homer offline dev."
        )


def spawn_role(role: str) -> dict:
    command = process_command(role)
    stdout_path = LOG_DIR / f"{role}.out.log"
    stderr_path = LOG_DIR / f"{role}.err.log"
    child_env = offline_environment(include_credentials=False)
    if role == "proxy":
        child_env.pop("AUTH_TOKEN_SECRET", None)
    if role == "sillytavern":
        child_env.update(
            {
                "HOMER_BACKEND_BASE_URL": PUBLIC_BASE_URL,
                "HOMER_AUTH_COOKIE_NAME": "ai_xingyue_token",
            }
        )

    creationflags = 0
    popen_kwargs: dict = {}
    if os.name == "nt":
        creationflags = getattr(subprocess, "DETACHED_PROCESS", 0x00000008)
        creationflags |= getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0x00000200)
    else:
        popen_kwargs["start_new_session"] = True

    with stdout_path.open("ab", buffering=0) as stdout_handle, stderr_path.open("ab", buffering=0) as stderr_handle:
        process = subprocess.Popen(
            command,
            cwd=str(SILLYTAVERN_LAUNCH_DIR if role == "sillytavern" else ROOT),
            env=child_env,
            stdin=subprocess.DEVNULL,
            stdout=stdout_handle,
            stderr=stderr_handle,
            close_fds=True,
            creationflags=creationflags,
            **popen_kwargs,
        )
    return {
        "pid": process.pid,
        "role": role,
        "started_at": utc_now(),
        "script": str(
            BACKEND_SCRIPT
            if role == "backend"
            else SILLYTAVERN_SERVER
            if role == "sillytavern"
            else PROXY_SCRIPT
        ),
        "runtime": shutil.which("node") if role == "sillytavern" else sys.executable,
        "python": None if role == "sillytavern" else sys.executable,
        "stdout": str(stdout_path),
        "stderr": str(stderr_path),
    }


def _no_proxy_opener():
    return urllib.request.build_opener(urllib.request.ProxyHandler({}))


def http_ok(url: str, expected: bytes | None = None) -> bool:
    request = urllib.request.Request(url, headers={"Cache-Control": "no-cache"})
    try:
        with _no_proxy_opener().open(request, timeout=2) as response:
            body = response.read(256)
            return response.status == 200 and (expected is None or expected in body)
    except (urllib.error.URLError, TimeoutError, OSError):
        return False


def wait_for_health(processes: dict[str, dict], timeout_seconds: float = 90.0) -> None:
    # A clean SillyTavern data root copies the bundled presets and compiles its
    # frontend before opening the port. On Windows this legitimately takes
    # longer than 35 seconds even on a healthy first launch.
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        for role in ROLES:
            status = role_status(role, processes.get(role))
            if status["state"] != "running":
                raise OfflineDevError(
                    f"{role} exited before becoming healthy; inspect {LOG_DIR / (role + '.err.log')}"
                )
        backend_ok = http_ok(f"http://{BACKEND_HOST}:{BACKEND_PORT}/health", b"OK")
        proxy_ok = http_ok(f"{PUBLIC_BASE_URL}/__offline_dev__/health", b"OFFLINE_PROXY_OK")
        routed_ok = http_ok(f"{PUBLIC_BASE_URL}/health", b"OK")
        dialogue_internal_ok = http_ok(f"{SILLYTAVERN_INTERNAL_URL}/csrf-token", b'"token"')
        dialogue_routed_ok = http_ok(f"{SILLYTAVERN_PUBLIC_URL}/csrf-token", b'"token"')
        if backend_ok and proxy_ok and routed_ok and dialogue_internal_ok and dialogue_routed_ok:
            return
        time.sleep(0.4)
    raise OfflineDevError(
        f"offline services did not become healthy within {timeout_seconds:.0f}s; inspect {LOG_DIR}"
    )


def terminate_owned_process(role: str, record: dict) -> str:
    status = role_status(role, record)
    if status["state"] in {"stopped", "invalid-record", "not-recorded"}:
        return "already-stopped"
    if not status["owned"]:
        return "refused-pid-mismatch"
    pid = int(status["pid"])
    try:
        os.kill(pid, 15)
    except (OSError, ProcessLookupError):
        return "already-stopped"
    deadline = time.monotonic() + 8
    while time.monotonic() < deadline:
        if process_info(pid) is None:
            return "stopped"
        time.sleep(0.2)
    # These local services do not need a graceful shutdown transaction. A
    # second Windows TerminateProcess request is safe because ownership is
    # rechecked against the exact command line.
    current = role_status(role, record)
    if current["owned"]:
        with contextlib.suppress(OSError, ProcessLookupError):
            os.kill(pid, 9)
    return "stopped" if process_info(pid) is None else "stop-timeout"


def stop_services(*, quiet: bool = False) -> bool:
    processes = load_processes()
    success = True
    results = {}
    for role in reversed(ROLES):
        record = processes.get(role)
        if not record:
            results[role] = "not-recorded"
            continue
        result = terminate_owned_process(role, record)
        results[role] = result
        if result in {"refused-pid-mismatch", "stop-timeout"}:
            success = False
    # Remove only stale/stopped records.  Keep a timeout/mismatch record as
    # evidence so a later command still refuses to kill an unrelated PID.
    remaining = {
        role: record
        for role, record in processes.items()
        if results.get(role) in {"refused-pid-mismatch", "stop-timeout"}
    }
    save_processes(remaining)
    if not quiet:
        for role in ROLES:
            print(f"{role}: {results.get(role, 'not-recorded')}")
    return success


def start_services() -> None:
    initialize_state()
    ensure_sillytavern_dependencies()
    ensure_sillytavern_launch_paths()
    processes = load_processes()
    statuses = {role: role_status(role, processes.get(role)) for role in ROLES}
    if all(status["state"] == "running" for status in statuses.values()):
        print(f"Homer offline dev is already running at {PUBLIC_BASE_URL}/")
        print(f"Dialogue module: {SILLYTAVERN_PUBLIC_URL}/")
        print(f"Credentials file: {CREDENTIALS_FILE}")
        return

    if any(status["owned"] for status in statuses.values()):
        if not stop_services(quiet=True):
            raise OfflineDevError("could not stop a partial previous offline-dev run")
    else:
        # Stale records are harmless and must not authorize process termination.
        save_processes({})

    assert_ports_available()
    started: dict[str, dict] = {}
    try:
        for role in ROLES:
            started[role] = spawn_role(role)
            save_processes(started)
        wait_for_health(started)
    except Exception:
        stop_services(quiet=True)
        raise

    print(f"Homer offline dev is ready: {PUBLIC_BASE_URL}/")
    print(f"App login: {PUBLIC_BASE_URL}/app/login.html")
    print(f"Admin: {PUBLIC_BASE_URL}/admin.html")
    print(f"Dialogue module: {SILLYTAVERN_PUBLIC_URL}/")
    print(f"Credentials file: {CREDENTIALS_FILE}")
    print(f"Logs: {LOG_DIR}")


def print_status(as_json: bool = False) -> bool:
    processes = load_processes()
    statuses = {role: role_status(role, processes.get(role)) for role in ROLES}
    payload = {
        "state_dir": str(STATE_DIR),
        "url": PUBLIC_BASE_URL,
        "backend_health": http_ok(f"http://{BACKEND_HOST}:{BACKEND_PORT}/health", b"OK"),
        "proxy_health": http_ok(f"{PUBLIC_BASE_URL}/__offline_dev__/health", b"OFFLINE_PROXY_OK"),
        "dialogue_health": http_ok(
            f"{SILLYTAVERN_INTERNAL_URL}/csrf-token",
            b'"token"',
        ),
        "dialogue_route_health": http_ok(
            f"{SILLYTAVERN_PUBLIC_URL}/csrf-token",
            b'"token"',
        ),
        "processes": statuses,
    }
    healthy = (
        payload["backend_health"]
        and payload["proxy_health"]
        and payload["dialogue_health"]
        and payload["dialogue_route_health"]
        and all(item["state"] == "running" for item in statuses.values())
    )
    payload["healthy"] = healthy
    if as_json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(f"Homer offline dev: {'RUNNING' if healthy else 'STOPPED/DEGRADED'}")
        for role in ROLES:
            item = statuses[role]
            print(f"{role}: {item['state']}" + (f" (PID {item['pid']})" if item["pid"] else ""))
        print(f"backend health: {'OK' if payload['backend_health'] else 'DOWN'}")
        print(f"proxy health: {'OK' if payload['proxy_health'] else 'DOWN'}")
        print(f"dialogue health: {'OK' if payload['dialogue_health'] else 'DOWN'}")
        print(f"dialogue route: {'OK' if payload['dialogue_route_health'] else 'DOWN'}")
        print(f"URL: {PUBLIC_BASE_URL}/")
        print(f"Dialogue: {SILLYTAVERN_PUBLIC_URL}/")
    return healthy


def reset_state() -> None:
    if not stop_services(quiet=True):
        raise OfflineDevError("refusing to reset while an unverified recorded process still exists")
    ensure_safe_state_path()
    if STATE_DIR.exists():
        shutil.rmtree(STATE_DIR)
    initialize_state()
    print("Offline development state has been reset.")
    print(f"Credentials file: {CREDENTIALS_FILE}")


@contextlib.contextmanager
def manager_lock():
    ensure_directories()
    token = secrets.token_hex(12)
    payload = {"pid": os.getpid(), "created_at": utc_now(), "token": token}
    for attempt in range(2):
        try:
            fd = os.open(LOCK_FILE, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError:
            current = load_json(LOCK_FILE, {})
            try:
                current_pid = int(current.get("pid"))
            except (TypeError, ValueError):
                current_pid = 0
            if attempt == 0 and process_info(current_pid) is None:
                with contextlib.suppress(FileNotFoundError):
                    LOCK_FILE.unlink()
                continue
            raise OfflineDevError("another Homer offline-dev lifecycle command is still running")
        else:
            with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
                json.dump(payload, handle, ensure_ascii=False)
            break
    try:
        yield
    finally:
        current = load_json(LOCK_FILE, {})
        if current.get("token") == token:
            with contextlib.suppress(FileNotFoundError):
                LOCK_FILE.unlink()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage isolated Homer offline development services")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser(
        "start",
        help="initialize and start backend, local proxy, and original SillyTavern",
    )
    status_parser = subparsers.add_parser("status", help="show verified process and health state")
    status_parser.add_argument("--json", action="store_true", help="print machine-readable JSON")
    subparsers.add_parser("stop", help="stop only verified offline-dev PIDs")
    subparsers.add_parser("reset", help="stop services and recreate isolated data/credentials")
    return parser


def main() -> int:
    ensure_supported_python()
    args = build_parser().parse_args()
    try:
        if args.command == "status":
            return 0 if print_status(as_json=args.json) else 1
        with manager_lock():
            if args.command == "start":
                start_services()
            elif args.command == "stop":
                return 0 if stop_services() else 2
            elif args.command == "reset":
                reset_state()
        return 0
    except OfflineDevError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("Interrupted.", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
