"""Start an isolated Homer + original SillyTavern E2E stack.

Runtime secrets and process identifiers stay under output/sillytavern-e2e.
The production database and the already-running development services are not
used by this helper.
"""

from __future__ import annotations

import json
import os
import hashlib
import secrets
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path

from offline_dev import ensure_windows_junction


ROOT = Path(__file__).resolve().parents[1]
STATE_DIR = (ROOT / "output" / "sillytavern-e2e").resolve()
EXPECTED_STATE_DIR = (ROOT / "output" / "sillytavern-e2e").resolve()
PYTHON = Path(sys.executable).resolve()
NODE = Path(shutil.which("node") or "__missing_node__")


def sillytavern_launch_paths() -> tuple[Path, Path, bool]:
    runtime_dir = (ROOT / "sillytavern-runtime").resolve()
    data_dir = (STATE_DIR / "st-data").resolve()
    needs_alias = os.name == "nt" and (
        not str(runtime_dir).isascii() or not str(data_dir).isascii()
    )
    if not needs_alias:
        return runtime_dir, data_dir, False

    local_app_data = os.environ.get("LOCALAPPDATA") or os.environ.get("TEMP")
    if not local_app_data or not str(local_app_data).isascii():
        raise RuntimeError(
            "SillyTavern E2E needs an ASCII LOCALAPPDATA/TEMP path on Windows"
        )
    workspace_key = hashlib.sha256(
        (str(ROOT).casefold() + "|sillytavern-e2e").encode("utf-8")
    ).hexdigest()[:12]
    alias_root = Path(local_app_data) / "HomerOfflineDev" / workspace_key
    runtime_alias = alias_root / "runtime"
    state_alias = alias_root / "state"
    ensure_windows_junction(runtime_alias, runtime_dir)
    ensure_windows_junction(state_alias, STATE_DIR)
    return runtime_alias, state_alias / "st-data", True


def assert_port_free(port: int) -> None:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.settimeout(0.4)
        if probe.connect_ex(("127.0.0.1", port)) == 0:
            raise RuntimeError(f"E2E port {port} is already in use")


def wait_for_port(port: int, process: subprocess.Popen[bytes], timeout: float = 45.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f"service on port {port} exited with {process.returncode}")
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
            probe.settimeout(0.3)
            if probe.connect_ex(("127.0.0.1", port)) == 0:
                return
        time.sleep(0.2)
    raise TimeoutError(f"service on port {port} did not become ready")


def open_log(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    return path.open("ab", buffering=0)


def main() -> int:
    if STATE_DIR != EXPECTED_STATE_DIR or STATE_DIR.parent != (ROOT / "output").resolve():
        raise SystemExit(f"unsafe E2E state path: {STATE_DIR}")
    if not PYTHON.is_file() or not NODE.is_file():
        raise SystemExit("required Python or Node runtime is missing")

    config = json.loads((STATE_DIR / "runtime" / "config.json").read_text(encoding="utf-8"))
    secret = (STATE_DIR / "runtime" / "auth-token-secret.txt").read_text(encoding="utf-8").strip()
    backend_port = 18080
    frontend_port = 18081
    model_stub_port = 18082
    sillytavern_port = 18091
    assert_port_free(backend_port)
    assert_port_free(frontend_port)
    assert_port_free(model_stub_port)
    assert_port_free(sillytavern_port)

    logs = STATE_DIR / "logs"
    detached = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW
    model_stub_api_key = "homer-e2e-" + secrets.token_urlsafe(24)
    model_stub = subprocess.Popen(
        [
            str(PYTHON),
            str(ROOT / "tools" / "_e2e_model_stub.py"),
            "--host",
            "127.0.0.1",
            "--port",
            str(model_stub_port),
            "--api-key",
            model_stub_api_key,
        ],
        cwd=ROOT,
        stdin=subprocess.DEVNULL,
        stdout=open_log(logs / "model-stub.stdout.log"),
        stderr=open_log(logs / "model-stub.stderr.log"),
        creationflags=detached,
    )
    wait_for_port(model_stub_port, model_stub, timeout=30.0)

    backend_env = os.environ.copy()
    backend_env.update(
        {
            "AUTH_TOKEN_SECRET": secret,
            "AUTH_COOKIE_SECURE": "0",
            "AUTH_COOKIE_SAMESITE": "Lax",
            "OFFLINE_DEV_MODE": "1",
            "HOMER_OFFLINE_DEV": "1",
            "CONTENT_MODE": "offline",
            "PUBLIC_BASE_URL": config["base_url"],
            "SILLYTAVERN_PUBLIC_URL": config["dialogue_url"],
            "ALLOWED_CORS_ORIGINS": config["base_url"],
            "MEDIA_DIR": config["media_dir"],
            "MAIL_DB_PATH": str(STATE_DIR / "data" / "mail.sqlite3"),
            "USER_BYOK_ENABLED": "0",
            "USER_LLM_BASE_URL": f"http://127.0.0.1:{model_stub_port}/v1",
            "USER_LLM_API_KEY": model_stub_api_key,
            "USER_LLM_MODEL": "homer-e2e",
        }
    )
    backend = subprocess.Popen(
        [
            str(PYTHON),
            str(ROOT / "tools" / "ai_fengyue_local_server.py"),
            "--host",
            "127.0.0.1",
            "--port",
            str(backend_port),
            "--db",
            config["db_path"],
        ],
        cwd=ROOT,
        env=backend_env,
        stdin=subprocess.DEVNULL,
        stdout=open_log(logs / "backend.stdout.log"),
        stderr=open_log(logs / "backend.stderr.log"),
        creationflags=detached,
    )
    wait_for_port(backend_port, backend, timeout=60.0)

    frontend = subprocess.Popen(
        [
            str(PYTHON),
            str(ROOT / "tools" / "offline_dev_proxy.py"),
            "--host",
            "127.0.0.1",
            "--port",
            str(frontend_port),
            "--backend",
            config["backend_url"],
            "--dialogue-runtime",
            config["dialogue_internal_url"],
            "--frontend",
            str(ROOT / "frontend"),
            "--state-dir",
            str(STATE_DIR),
        ],
        cwd=ROOT,
        stdin=subprocess.DEVNULL,
        stdout=open_log(logs / "frontend.stdout.log"),
        stderr=open_log(logs / "frontend.stderr.log"),
        creationflags=detached,
    )
    wait_for_port(frontend_port, frontend, timeout=60.0)

    sillytavern_env = os.environ.copy()
    sillytavern_env.update(
        {
            "HOMER_BACKEND_BASE_URL": config["base_url"],
            "HOMER_AUTH_COOKIE_NAME": "ai_xingyue_token",
        }
    )
    sillytavern_cwd, sillytavern_data_dir, uses_ascii_alias = sillytavern_launch_paths()
    sillytavern_command = [str(NODE)]
    if uses_ascii_alias:
        sillytavern_command.extend(["--preserve-symlinks", "--preserve-symlinks-main"])
    sillytavern_command.extend(
        [
            "server.js",
            "--port",
            str(sillytavern_port),
            "--dataRoot",
            str(sillytavern_data_dir),
            "--browserLaunchEnabled",
            "false",
        ]
    )
    sillytavern = subprocess.Popen(
        sillytavern_command,
        cwd=sillytavern_cwd,
        env=sillytavern_env,
        stdin=subprocess.DEVNULL,
        stdout=open_log(logs / "sillytavern.stdout.log"),
        stderr=open_log(logs / "sillytavern.stderr.log"),
        creationflags=detached,
    )
    wait_for_port(sillytavern_port, sillytavern, timeout=120.0)

    process_file = STATE_DIR / "runtime" / "original-sillytavern-processes.json"
    process_file.write_text(
        json.dumps(
            {
                "model_stub": model_stub.pid,
                "backend": backend.pid,
                "frontend": frontend.pid,
                "sillytavern": sillytavern.pid,
                "model_stub_port": model_stub_port,
                "backend_port": backend_port,
                "frontend_port": frontend_port,
                "sillytavern_port": sillytavern_port,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(
        "isolated E2E stack ready: "
        f"frontend={frontend.pid}, backend={backend.pid}, "
        f"model_stub={model_stub.pid}, sillytavern={sillytavern.pid}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
