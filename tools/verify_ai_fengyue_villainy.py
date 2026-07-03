#!/usr/bin/env python3
import argparse
import json
import time
import urllib.error
import urllib.request
from pathlib import Path

import paramiko


DEFAULT_KEY = Path.home() / ".ssh" / "villainy_backup_ed25519"
DB_PATH = "/opt/ai-fengyue-backend/data/ai_fengyue.sqlite3"


def log(message: str) -> None:
    print(f"[ai-fengyue-verify] {message}", flush=True)


def post_json(url: str, payload: dict) -> tuple[int, dict]:
    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            text = response.read().decode("utf-8", errors="replace")
            return response.status, json.loads(text)
    except urllib.error.HTTPError as exc:
        text = exc.read().decode("utf-8", errors="replace")
        try:
            body = json.loads(text)
        except json.JSONDecodeError:
            body = {"raw": text}
        return exc.code, body


def connect(host: str, user: str, key: Path) -> paramiko.SSHClient:
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(
        hostname=host,
        username=user,
        key_filename=str(key),
        look_for_keys=False,
        allow_agent=False,
        timeout=20,
    )
    return client


def remote_code(ssh: paramiko.SSHClient, email: str) -> str:
    snippet = (
        "import json, sqlite3; "
        f"con=sqlite3.connect({DB_PATH!r}); "
        "row=con.execute("
        "'select code from email_codes where email=? and consumed_at is null order by id desc limit 1',"
        f"({email!r},)"
        ").fetchone(); "
        "print(json.dumps({'code': row[0] if row else ''}))"
    )
    command = "python3 -c " + json.dumps(snippet)
    stdin, stdout, stderr = ssh.exec_command(command)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    code = stdout.channel.recv_exit_status()
    if code != 0:
        raise RuntimeError(f"remote sqlite lookup failed: {err.strip()}")
    value = json.loads(out)["code"]
    if not value:
        raise RuntimeError(f"no active verification code for {email}")
    return value


def assert_result(label: str, status: int, body: dict, expected: str) -> None:
    actual = body.get("result")
    log(f"{label}: http={status} result={actual} body={json.dumps(body, ensure_ascii=False)[:180]}")
    if actual != expected:
        raise AssertionError(f"{label}: expected result={expected}, got {actual}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify AI Xingyue email registration and recharge flow.")
    parser.add_argument("--base-url", default="https://patcher.villainy.top")
    parser.add_argument("--host", default="45.207.192.148")
    parser.add_argument("--user", default="root")
    parser.add_argument("--key", type=Path, default=DEFAULT_KEY)
    parser.add_argument("--email", default=None)
    args = parser.parse_args()

    email = args.email or f"ctf-verify-{int(time.time())}@example.com"
    password = "Passw0rd-verify"
    base = args.base_url.rstrip("/")

    ssh = connect(args.host, args.user, args.key)
    try:
        status, body = post_json(f"{base}/console/api/login", {"email": email, "password": password})
        assert_result("login before register", status, body, "failure")

        status, body = post_json(f"{base}/console/api/register/email", {"email": email, "lang": "zh-Hans"})
        assert_result("send email code", status, body, "success")

        code = remote_code(ssh, email)
        log(f"received remote code for test mailbox: {code}")

        status, body = post_json(
            f"{base}/console/api/register",
            {"email": email, "password": password, "name": "CTF Verify", "code": "000000", "remember_me": True},
        )
        assert_result("register with wrong code", status, body, "failure")

        status, body = post_json(
            f"{base}/console/api/register",
            {"email": email, "password": password, "name": "CTF Verify", "code": code, "remember_me": True},
        )
        assert_result("register with correct code", status, body, "success")

        status, body = post_json(
            f"{base}/console/api/login",
            {"email": email, "password": "wrong-password", "remember_me": True},
        )
        assert_result("login with wrong password", status, body, "failure")

        status, body = post_json(
            f"{base}/console/api/login",
            {"email": email, "password": password, "remember_me": True},
        )
        assert_result("login with correct password", status, body, "success")
        token = body.get("data")
        request = urllib.request.Request(
            f"{base}/console/api/ctf/recharge",
            data=json.dumps({"product_id": "ctf_internal_recharge_100", "points": 100}).encode("utf-8"),
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=20) as response:
            recharge_body = json.loads(response.read().decode("utf-8", errors="replace"))
        assert_result("server recharge", response.status, recharge_body, "success")
        log("verification complete")
        return 0
    finally:
        ssh.close()


if __name__ == "__main__":
    raise SystemExit(main())
