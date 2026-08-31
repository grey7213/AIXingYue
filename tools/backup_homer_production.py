#!/usr/bin/env python3
"""Pull a verified full backup of the Homer (惑梦) production server to local disk.

Captures only what cannot be rebuilt from this repository:

  1. ai_fengyue.sqlite3           consistent snapshot via SQLite Online Backup API
  2. media-cache/                 8,552 role-card cover images (405 MB raw)
  3. /var/lib/homer-dialogue      SillyTavern per-user characters/chats/worlds
  4. deployed frontend            (media-cache + download excluded)
  5. published APK download dir    (release.json exists only on the server)
  6. deployed backend modules     (current .py only, no .bak-* churn)
  7. dialogue runtime source      (current release, node_modules excluded)
  8. server config                nginx site, systemd units, TLS material, env file
  8. data extras                  verification_mail.sqlite3, worldbook, small role-restore backup

Deliberately NOT captured (identity recorded in the manifest instead):
  - node_modules (344 MB, restore with `npm ci` from the archived package-lock.json)
  - /opt/homer-dialogue-runtime/backups/*.tgz (1.2 GB of superseded dialogue snapshots)
  - /opt/ai-fengyue-backend/backups/*.sqlite3 2.4 GB pre-deploy copy from 2026-08-20
    (superseded by the fresh snapshot this script takes)

Integrity: every archive is hashed on the server, hashed again locally after
download, decompressed to prove the frame is readable, and — for the database —
the decompressed bytes are hashed and `pragma quick_check`ed. Server staging is
removed only after every check passes.
"""
import argparse
import concurrent.futures
import hashlib
import json
import posixpath
import shlex
import shutil
import subprocess
import sqlite3
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import paramiko

DEFAULT_HOST = "38.76.218.46"
DEFAULT_USER = "root"
DEFAULT_KEY = Path.home() / ".ssh" / "villainy_backup_ed25519"
DEFAULT_DEST = Path("E:/homer-backups")
EXPECTED_HOSTNAME = "vm-851a1bc4a978a80f"

BACKEND_DIR = "/opt/ai-fengyue-backend"
LIVE_DB = f"{BACKEND_DIR}/data/ai_fengyue.sqlite3"
FRONTEND_DIR = "/var/www/ai-fengyue-frontend"
DIALOGUE_DATA = "/var/lib/homer-dialogue"
DIALOGUE_RUNTIME = "/opt/homer-dialogue-runtime"
PATCHER_NGINX = "/etc/nginx/sites-available/ai-fengyue-patcher.conf"
STAGING_ROOT = "/opt/homer-backup-staging"

# --long=31 (2 GB window) buys ~90 MB over --long=27 on this data set. Restoring
# needs the same flag: verified `zstd -d --long=31` and Python zstandard with
# max_window_size=2**31 both decode it. RESTORE.md records the exact commands.
ZSTD = "zstd -8 -T8 --long=31 -q"
ZSTD_DB = "zstd -12 -T8 --long=31 -q"
PARALLEL_DOWNLOADS = 3


def log(message: str) -> None:
    print(f"[homer-backup] {message}", flush=True)


def human(num: float) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if abs(num) < 1024 or unit == "GB":
            return f"{int(num)} B" if unit == "B" else f"{num:,.1f} {unit}"
        num /= 1024
    return f"{num:,.1f} GB"


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
        banner_timeout=20,
        auth_timeout=20,
    )
    transport = client.get_transport()
    if transport is not None:
        transport.set_keepalive(15)
    return client


def run(ssh: paramiko.SSHClient, command: str, *, check: bool = True,
        label: str | None = None, quiet: bool = False) -> str:
    if not quiet:
        log(f"remote: {label or command}")
    _, stdout, stderr = ssh.exec_command(command)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    code = stdout.channel.recv_exit_status()
    if err.strip() and not quiet:
        print(err.rstrip(), file=sys.stderr)
    if check and code != 0:
        raise RuntimeError(f"remote command failed with exit {code}: {command}\n{err.strip()}")
    return out


def sha256_local(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


# Runs on the server. Uses the SQLite Online Backup API, then collapses the
# snapshot's WAL so the result is one self-contained file, then re-verifies it
# through an independent immutable read-only handle (AGENTS.md recipe).
SNAPSHOT_SCRIPT = r'''
import json, os, sqlite3, sys, time
live, dest = sys.argv[1], sys.argv[2]
if os.path.exists(dest):
    print("refusing to overwrite existing snapshot: %s" % dest, file=sys.stderr)
    raise SystemExit(3)
started = time.time()
tmp = dest + ".partial"
for stray in (tmp, tmp + "-wal", tmp + "-shm"):
    if os.path.exists(stray):
        os.unlink(stray)
src = sqlite3.connect(live)
dst = sqlite3.connect(tmp)
src.backup(dst)
live_check = src.execute("pragma quick_check").fetchone()[0]
snap_check = dst.execute("pragma quick_check").fetchone()[0]
dst.execute("pragma journal_mode=DELETE").fetchone()
counts = {}
for table in ("users", "local_apps", "content_versions", "conversations", "messages",
              "user_favorites", "api_settings", "role_card_annotations", "request_log"):
    try:
        counts[table] = dst.execute("select count(*) from %s" % table).fetchone()[0]
    except sqlite3.Error as exc:
        counts[table] = "ERR:%s" % exc
tables = [r[0] for r in dst.execute(
    "select name from sqlite_master where type='table' order by name")]
dst.close()
src.close()
for stray in (tmp + "-wal", tmp + "-shm"):
    if os.path.exists(stray):
        os.unlink(stray)
os.rename(tmp, dest)
os.chmod(dest, 0o600)
ro = sqlite3.connect("file:%s?immutable=1" % dest, uri=True)
final_check = ro.execute("pragma quick_check").fetchone()[0]
journal = ro.execute("pragma journal_mode").fetchone()[0]
ro.close()
ok = live_check == snap_check == final_check == "ok"
print(json.dumps({
    "live_bytes": os.path.getsize(live),
    "snapshot_bytes": os.path.getsize(dest),
    "live_quick_check": live_check,
    "snapshot_quick_check": snap_check,
    "immutable_quick_check": final_check,
    "snapshot_journal_mode": journal,
    "row_counts": counts,
    "table_count": len(tables),
    "tables": tables,
    "elapsed_seconds": round(time.time() - started, 1),
    "ok": ok,
}, indent=2, sort_keys=True))
raise SystemExit(0 if ok else 1)
'''


def archive_plan(release: str) -> list[dict]:
    """Each entry becomes one .tar.zst (or .zst) staged on the server, then pulled.

    `cmd` writes the archive to {path}; `note` lands in the manifest so a future
    restore knows what the file is for without unpacking it.
    """
    return [
        {
            "name": "database",
            "file": "ai_fengyue.sqlite3.zst",
            "note": "Live business DB: users, role cards (local_apps), content_versions, conversations, messages, api_settings (site copy + LLM presets). Snapshot taken with the SQLite Online Backup API; journal_mode=DELETE so no -wal/-shm needed.",
            "cmd": f"{ZSTD_DB} -c < {{staging}}/ai_fengyue.sqlite3 > {{path}}",
            "kind": "sqlite",
        },
        {
            "name": "media-cache",
            "file": "media-cache.tar.zst",
            "note": f"{FRONTEND_DIR}/media-cache — role-card cover JPGs referenced by local_apps.cover_url. Not reproducible from the repo.",
            "cmd": f"tar -C {FRONTEND_DIR} -cf - media-cache | {ZSTD} -c > {{path}}",
            "kind": "tar",
            "restore_hint": f"tar -C {FRONTEND_DIR} -xf - (owner ai-xingyue:ai-xingyue)",
        },
        {
            "name": "dialogue-data",
            "file": "homer-dialogue-data.tar.zst",
            "note": f"{DIALOGUE_DATA} — SillyTavern per-user state (characters, chats, worlds, settings, avatars). _webpack build cache excluded.",
            "cmd": (
                f"tar -C /var/lib --exclude='homer-dialogue/_webpack' -cf - homer-dialogue "
                f"| {ZSTD} -c > {{path}}"
            ),
            "kind": "tar",
            "restore_hint": "tar -C /var/lib -xf - (owner homer-dialogue:homer-dialogue, dir mode 750)",
        },
        {
            "name": "dialogue-runtime-source",
            "file": "homer-dialogue-runtime-source.tar.zst",
            "note": f"{DIALOGUE_RUNTIME}/releases/{release} with node_modules excluded — the deployed runtime tree incl. public/ assets and the Homer bridge. node_modules restores via `npm ci` from the bundled package-lock.json.",
            "cmd": (
                f"tar -C {DIALOGUE_RUNTIME}/releases -cf - --exclude='*/node_modules' {release} "
                f"| {ZSTD} -c > {{path}}"
            ),
            "kind": "tar",
            "restore_hint": f"tar -C {DIALOGUE_RUNTIME}/releases -xf - && cd {release} && npm ci --omit=dev",
        },
        {
            "name": "frontend",
            "file": "frontend.tar.zst",
            "note": f"{FRONTEND_DIR} with media-cache/ and download/ excluded — deployed marketing site + /app web client.",
            "cmd": (
                f"tar -C /var/www --exclude='ai-fengyue-frontend/media-cache' "
                f"--exclude='ai-fengyue-frontend/download' -cf - ai-fengyue-frontend "
                f"| {ZSTD} -c > {{path}}"
            ),
            "kind": "tar",
        },
        {
            "name": "download",
            "file": "download.tar.zst",
            "note": f"{FRONTEND_DIR}/download — published APKs, their .sha256 files, and release.json. Kept separate from the frontend archive so a future large APK can't bloat the source bundle. release.json was authored on the server during the 2026-08-19 publish and exists nowhere in the repo.",
            "cmd": f"tar -C {FRONTEND_DIR} -cf - download | {ZSTD} -c > {{path}}",
            "kind": "tar",
            "restore_hint": f"tar -C {FRONTEND_DIR} -xf - (owner www-data:www-data)",
        },
        {
            "name": "backend",
            "file": "backend.tar.zst",
            "note": f"{BACKEND_DIR} current Python modules + ai-fengyue.env (CONTAINS SMTP/ZPAY SECRETS) + data/ extras (verification_mail.sqlite3, tavo_anti_scrape_worldbook.json, data/backups/). Excludes the live DB (see database archive), .bak-* copies and __pycache__.",
            "cmd": (
                f"tar -C /opt -cf - "
                f"--exclude='ai-fengyue-backend/*.bak-*' "
                f"--exclude='ai-fengyue-backend/__pycache__' "
                f"--exclude='ai-fengyue-backend/backups' "
                f"--exclude='ai-fengyue-backend/data/ai_fengyue.sqlite3*' "
                f"ai-fengyue-backend | {ZSTD} -c > {{path}}"
            ),
            "kind": "tar",
            "sensitive": True,
        },
        {
            "name": "server-config",
            "file": "server-config.tar.zst",
            "note": "nginx sites-available + sites-enabled, the four systemd units Homer needs, /etc/letsencrypt (TLS KEYS), sshd_config + fail2ban jails (the 2026-08-18 hardening), /etc/hosts, plus text inventories (installed packages, users, listening sockets, firewall rules, effective sshd config, crontabs).",
            "cmd": f"tar -C {{staging}} -cf - server-config | {ZSTD} -c > {{path}}",
            "kind": "tar",
            "sensitive": True,
        },
    ]


def collect_server_config(ssh: paramiko.SSHClient, staging: str) -> None:
    """Stage config + inventory files under {staging}/server-config for archiving."""
    cfg = f"{staging}/server-config"
    run(ssh, f"rm -rf {cfg} && mkdir -p {cfg}/nginx {cfg}/systemd {cfg}/inventory",
        label="stage server-config dirs")
    run(ssh, f"cp -a /etc/nginx/sites-available /etc/nginx/sites-enabled /etc/nginx/nginx.conf {cfg}/nginx/",
        label="copy nginx config")
    units = (
        "ai-fengyue-backend.service",
        "homer-dialogue.service",
        "villainy-clash-forward.service",
        "villainy-clash-forward-cpa.service",
        "villainy-clash-forward-grok2api.service",
    )
    for unit in units:
        run(ssh, f"[ -f /etc/systemd/system/{unit} ] && cp -a /etc/systemd/system/{unit} {cfg}/systemd/ || true",
            quiet=True)
    run(ssh, f"cp -a /etc/letsencrypt {cfg}/letsencrypt && cp -a /etc/hosts {cfg}/inventory/hosts",
        label="copy TLS material and hosts")
    run(ssh, f"mkdir -p {cfg}/ssh {cfg}/fail2ban && "
             f"cp -a /etc/ssh/sshd_config {cfg}/ssh/ 2>/dev/null; "
             f"cp -a /etc/ssh/sshd_config.d {cfg}/ssh/ 2>/dev/null; "
             f"cp -a /etc/fail2ban/jail.local /etc/fail2ban/jail.d {cfg}/fail2ban/ 2>/dev/null; true",
        label="copy sshd + fail2ban config")
    inventory = {
        "os-release": "cat /etc/os-release",
        "hostname": "hostname",
        "uname": "uname -a",
        "packages": "dpkg-query -W -f='${Package}\\t${Version}\\n'",
        "systemd-enabled": "systemctl list-unit-files --state=enabled --no-pager --no-legend",
        "systemd-running": "systemctl list-units --type=service --state=running --no-pager --no-legend",
        "listening": "ss -tlnp",
        "users": "getent passwd",
        "groups": "getent group",
        "crontab-root": "crontab -l 2>/dev/null || echo '(no root crontab)'",
        "cron-d": "ls -la /etc/cron.d/",
        "node-npm": "node --version; npm --version; python3 --version",
        "disk": "df -h",
        "docker-ps": "docker ps --format '{{.Names}}\\t{{.Image}}\\t{{.Status}}' 2>/dev/null || echo '(docker unavailable)'",
        "dialogue-current": f"readlink -f {DIALOGUE_RUNTIME}/current",
        "backend-file-list": f"ls -la {BACKEND_DIR}",
        "fail2ban": "fail2ban-client status 2>/dev/null || echo '(fail2ban query failed)'",
        # Firewall + SSH hardening are part of "how this host is configured" and
        # the 2026-08-18 hardening pass is not reproducible from the repo.
        "firewall": "ufw status verbose 2>/dev/null; iptables -S 2>/dev/null | head -60",
        "sshd-effective": "sshd -T 2>/dev/null | sort || echo '(sshd -T unavailable)'",
    }
    for name, command in inventory.items():
        run(ssh, f"{{ {command} ; }} > {cfg}/inventory/{name}.txt 2>&1 || true", quiet=True)
    log(f"staged server-config with {len(inventory)} inventory files")


def scp_pull(key: Path, host: str, user: str, remote: str, dest_dir: Path, filename: str) -> None:
    """Pull one file with scp, run from dest_dir so Windows drive letters never
    reach scp's host:path parser."""
    scp = shutil.which("scp")
    if not scp:
        raise RuntimeError("scp not found on PATH")
    cmd = [
        scp, "-q", "-i", str(key), "-o", "StrictHostKeyChecking=no",
        "-o", "ServerAliveInterval=15", "-o", "ServerAliveCountMax=8",
        f"{user}@{host}:{remote}", f"./{filename}",
    ]
    proc = subprocess.run(cmd, cwd=str(dest_dir), capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"scp failed for {remote}: {proc.stderr.strip()}")


def verify_zst(path: Path, *, expect_sqlite: bool) -> dict:
    """Decompress the frame to prove it is readable. For the DB, also hash the
    plaintext and run quick_check/integrity_check against the decompressed copy."""
    import zstandard

    dctx = zstandard.ZstdDecompressor(max_window_size=2 ** 31)
    if not expect_sqlite:
        digest = hashlib.sha256()
        total = 0
        with path.open("rb") as fh:
            reader = dctx.stream_reader(fh)
            while True:
                chunk = reader.read(8 * 1024 * 1024)
                if not chunk:
                    break
                total += len(chunk)
                digest.update(chunk)
        return {"decompressed_bytes": total, "decompressed_sha256": digest.hexdigest()}

    scratch = path.with_suffix(".verify.tmp")
    try:
        with path.open("rb") as src, scratch.open("wb") as dst:
            dctx.copy_stream(src, dst, write_size=8 * 1024 * 1024)
        conn = sqlite3.connect(f"file:{scratch.as_posix()}?immutable=1", uri=True)
        quick = conn.execute("pragma quick_check").fetchone()[0]
        integrity = conn.execute("pragma integrity_check").fetchone()[0]
        counts = {}
        for table in ("users", "local_apps", "content_versions", "conversations", "messages"):
            counts[table] = conn.execute(f"select count(*) from {table}").fetchone()[0]
        conn.close()
        return {
            "decompressed_bytes": scratch.stat().st_size,
            "decompressed_sha256": sha256_local(scratch),
            "local_quick_check": quick,
            "local_integrity_check": integrity,
            "local_row_counts": counts,
        }
    finally:
        if scratch.exists():
            scratch.unlink()


def write_restore_doc(out_dir: Path, manifest: dict, plan: list[dict], release: str) -> None:
    """A backup nobody knows how to restore is not a backup. Write the exact
    commands next to the archives."""
    server = manifest["server"]
    snap = manifest["database_snapshot"]
    names = {entry["name"] for entry in plan}
    partial = not {"database", "media-cache", "dialogue-data"} <= names
    lines = [
        f"# Homer 生产备份 {out_dir.name}",
        "",
        f"- 抓取时间：{manifest['captured_at_local']}",
        f"- 来源：`{manifest['host']}` ({server['hostname']}, {server['os']})",
        f"- 对话运行时 release：`{release}`",
        f"- 压缩：`{manifest['compression']['payload']}`（数据库 `{manifest['compression']['database']}`）",
        "",
    ]
    if partial:
        lines += [
            f"> **这是一次部分备份**，只包含：{', '.join(sorted(names))}。",
            "> 下面的还原顺序是完整流程，本目录里没有的归档请跳过对应步骤。",
            "",
        ]
    lines += [
        "## ⚠️ 这个目录含密钥",
        "",
        "`backend.tar.zst` 里有 `ai-fengyue.env`（Resend SMTP 密码、ZPAY 商户密钥、ADMIN_EMAILS），",
        "`server-config.tar.zst` 里有 `/etc/letsencrypt` 的 TLS 私钥。不要提交到 git，不要放进任何同步盘。",
        "",
        "## 解压前提",
        "",
        "所有归档用 `--long=31`（2 GB 窗口）压缩，解压必须带同样的参数，否则报",
        "`Frame requires too much memory for decoding`：",
        "",
        "```bash",
        "zstd -d --long=31 <file>.zst          # 命令行",
        "```",
        "",
        "```python",
        "import zstandard                       # Python",
        "d = zstandard.ZstdDecompressor(max_window_size=2**31)",
        "```",
        "",
        "## 校验",
        "",
        "```bash",
        "sha256sum -c SHA256SUMS.txt",
        "```",
        "",
        "更彻底的独立复核（比对归档内容与线上实况，而不是只信 manifest）：",
        "",
        "```powershell",
        f"D:\\Anconda3\\python.exe tools\\verify_homer_backup.py {out_dir}",
        "```",
        "",
        "抓取时已逐个验证：服务器端 sha256 == 本地 sha256，每个归档都成功解压。",
    ]
    if "database" in names:
        lines.append(
            f"数据库解压后 `quick_check` 与 `integrity_check` 均为 `ok`"
            f"（{snap['row_counts']['local_apps']} 张角色卡、{snap['row_counts']['users']} 个用户、"
            f"{snap['table_count']} 张表）。")
    else:
        lines.append(
            f"本次没有备份数据库。抓取时线上库的只读普查结果："
            f"{snap['row_counts']['local_apps']} 张角色卡、{snap['row_counts']['users']} 个用户、"
            f"{snap['table_count']} 张表 —— 仅作参考，**这个目录里没有可还原的数据库**。")
    lines += [
        "",
        "## 归档内容",
        "",
    ]
    for entry in plan:
        lines.append(f"### `{entry['file']}`")
        lines.append("")
        lines.append(f"{entry['note']}")
        lines.append("")
        lines.append(f"- 压缩后 {human(entry['local_bytes'])}，"
                     f"解压后 {human(entry['verification']['decompressed_bytes'])}")
        lines.append(f"- sha256 `{entry['local_sha256']}`")
        if entry.get("restore_hint"):
            lines.append(f"- 还原位置：`{entry['restore_hint']}`")
        lines.append("")

    lines += [
        "## 还原顺序",
        "",
        "先停服务，再落数据，最后起服务并核对。",
        "",
        "```bash",
        "systemctl stop ai-fengyue-backend homer-dialogue",
        "",
        "# 1. 数据库（唯一不能出错的一步；先备份现场再覆盖）",
        f"cp {LIVE_DB} {LIVE_DB}.before-restore-$(date +%Y%m%d-%H%M%S) 2>/dev/null || true",
        f"rm -f {LIVE_DB}-wal {LIVE_DB}-shm",
        f"zstd -d --long=31 -c ai_fengyue.sqlite3.zst > {LIVE_DB}",
        f"chown ai-xingyue:ai-xingyue {LIVE_DB} && chmod 600 {LIVE_DB}",
        f"python3 -c \"import sqlite3;print(sqlite3.connect('{LIVE_DB}').execute('pragma quick_check').fetchone())\"",
        "",
        "# 2. 封面媒体库",
        f"zstd -d --long=31 -c media-cache.tar.zst | tar -C {FRONTEND_DIR} -xf -",
        f"chown -R ai-xingyue:ai-xingyue {FRONTEND_DIR}/media-cache",
        "",
        "# 3. SillyTavern 对话数据",
        "zstd -d --long=31 -c homer-dialogue-data.tar.zst | tar -C /var/lib -xf -",
        f"chown -R homer-dialogue:homer-dialogue {DIALOGUE_DATA} && chmod 750 {DIALOGUE_DATA}",
        "",
        "# 4. 前端 + 后端代码（也可以直接跑 tools/deploy_ai_fengyue_villainy.py 从仓库重新部署）",
        "zstd -d --long=31 -c frontend.tar.zst | tar -C /var/www -xf -",
        "zstd -d --long=31 -c backend.tar.zst  | tar -C /opt     -xf -",
        f"chown root:ai-xingyue {BACKEND_DIR}/ai-fengyue.env && chmod 640 {BACKEND_DIR}/ai-fengyue.env",
        "",
        "# 5. 公开下载目录（APK + release.json，release.json 仓库里没有）",
        f"zstd -d --long=31 -c download.tar.zst | tar -C {FRONTEND_DIR} -xf -",
        f"chown -R www-data:www-data {FRONTEND_DIR}/download",
        "",
        "# 6. 对话运行时（node_modules 不在备份里，用 package-lock.json 重装）",
        f"zstd -d --long=31 -c homer-dialogue-runtime-source.tar.zst | tar -C {DIALOGUE_RUNTIME}/releases -xf -",
        f"cd {DIALOGUE_RUNTIME}/releases/{release} && npm ci --omit=dev",
        f"ln -sfn releases/{release} {DIALOGUE_RUNTIME}/current",
        "",
        "# 7. 系统配置（按需，通常只取 nginx 站点和 systemd unit）",
        "zstd -d --long=31 -c server-config.tar.zst | tar -C /tmp -xf -",
        f"cp /tmp/server-config/nginx/sites-available/{posixpath.basename(PATCHER_NGINX)} {PATCHER_NGINX}",
        "cp /tmp/server-config/systemd/*.service /etc/systemd/system/",
        "nginx -t && systemctl daemon-reload",
        "",
        "systemctl start ai-fengyue-backend homer-dialogue",
        "```",
        "",
        "## 还原后核对",
        "",
        "```bash",
        "curl -sS http://127.0.0.1:8008/health                  # → OK",
        "curl -sS -o /dev/null -w '%{http_code}\\n' http://127.0.0.1:8091/csrf-token",
        "curl -sk https://patcher.villainy.top/health",
        "curl -sk https://patcher.villainy.top/console/api/web/model-presets",
        "systemctl status ai-fengyue-backend homer-dialogue --no-pager | head -20",
        "```",
        "",
        "## 没有备份的东西",
        "",
    ]
    for path, reason in manifest["excluded"].items():
        lines.append(f"- `{path}` — {reason}")
    lines.append("")
    (out_dir / "RESTORE.md").write_text("\n".join(lines), encoding="utf-8")
    log("wrote RESTORE.md")


def main() -> int:
    parser = argparse.ArgumentParser(description="Back up the Homer production server locally.")
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--user", default=DEFAULT_USER)
    parser.add_argument("--key", type=Path, default=DEFAULT_KEY)
    parser.add_argument("--dest", type=Path, default=DEFAULT_DEST,
                        help="local backup root; a timestamped subdirectory is created inside")
    parser.add_argument("--only", action="append", default=None,
                        help="restrict to named archives (repeatable), e.g. --only database")
    parser.add_argument("--keep-staging", action="store_true",
                        help="leave the server-side staging directory in place for inspection")
    args = parser.parse_args()

    started = time.time()
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    out_dir = args.dest / f"homer-prod-{stamp}"
    out_dir.mkdir(parents=True, exist_ok=False)
    log(f"local destination {out_dir}")

    ssh = connect(args.host, args.user, args.key)
    manifest: dict = {
        "captured_at_local": datetime.now().astimezone().isoformat(timespec="seconds"),
        "captured_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "host": args.host,
        "tool": "tools/backup_homer_production.py",
        "compression": {"payload": ZSTD, "database": ZSTD_DB,
                        "decompress_note": "zstd -d --long=31 required (2 GB window)"},
    }
    try:
        hostname = run(ssh, "hostname", quiet=True).strip()
        log(f"connected to {hostname}")
        if hostname != EXPECTED_HOSTNAME:
            log(f"WARNING: hostname {hostname!r} != expected {EXPECTED_HOSTNAME!r}")
        manifest["server"] = {
            "hostname": hostname,
            "os": run(ssh, ". /etc/os-release && echo $PRETTY_NAME", quiet=True).strip(),
            "kernel": run(ssh, "uname -r", quiet=True).strip(),
            "uptime": run(ssh, "uptime -p", quiet=True).strip(),
            "disk_root": run(ssh, "df -h --output=size,used,avail,pcent / | tail -1", quiet=True).strip(),
        }
        release = posixpath.basename(
            run(ssh, f"readlink -f {DIALOGUE_RUNTIME}/current", quiet=True).strip())
        if not release:
            raise RuntimeError("could not resolve the dialogue runtime current release")
        manifest["dialogue_release"] = release
        log(f"dialogue runtime release {release}")

        avail_kb = int(run(ssh, "df --output=avail / | tail -1", quiet=True).strip())
        if avail_kb < 4 * 1024 * 1024:
            raise RuntimeError(f"server has only {avail_kb // 1024} MB free; need ~4 GB for staging")

        staging = f"{STAGING_ROOT}/{stamp}"
        run(ssh, f"mkdir -p {staging} && chmod 700 {STAGING_ROOT} {staging}",
            label="create staging dir")

        plan = archive_plan(release)
        if args.only:
            wanted = set(args.only)
            unknown = wanted - {entry["name"] for entry in plan}
            if unknown:
                raise SystemExit(f"unknown --only value(s): {sorted(unknown)}")
            plan = [entry for entry in plan if entry["name"] in wanted]
        selected = {entry["name"] for entry in plan}

        if "database" in selected:
            log("taking a consistent SQLite snapshot (Online Backup API)")
            snap_out = run(
                ssh,
                f"python3 - {shlex.quote(LIVE_DB)} {shlex.quote(staging + '/ai_fengyue.sqlite3')} "
                f"<< 'PYEOF'\n{SNAPSHOT_SCRIPT}\nPYEOF",
                label="sqlite online backup",
            )
            snapshot = json.loads(snap_out[snap_out.index("{"):snap_out.rindex("}") + 1])
            if not snapshot.get("ok"):
                raise RuntimeError(f"snapshot verification failed on the server: {snapshot}")
            log(f"snapshot ok: {human(snapshot['snapshot_bytes'])}, "
                f"{snapshot['row_counts']['local_apps']} role cards, "
                f"{snapshot['table_count']} tables, quick_check={snapshot['immutable_quick_check']}")
        else:
            # No DB archive requested — don't spend 50s and 2.3 GB of staging on a
            # snapshot nobody will download. Take a cheap read-only census so the
            # manifest still says what the live DB looked like.
            log("database archive not selected; recording a read-only census instead")
            snapshot = json.loads(run(ssh, (
                "python3 -c \"import json,sqlite3;"
                f"c=sqlite3.connect('file:{LIVE_DB}?mode=ro',uri=True);"
                "t=[r[0] for r in c.execute(\\\"select name from sqlite_master "
                "where type='table' order by name\\\")];"
                "print(json.dumps({'census_only':True,'table_count':len(t),'tables':t,"
                "'row_counts':{n:c.execute('select count(*) from '+n).fetchone()[0] "
                "for n in ('users','local_apps','content_versions','conversations','messages')}}))\""
            ), label="live DB census").strip())
        manifest["database_snapshot"] = snapshot

        if "server-config" in selected:
            collect_server_config(ssh, staging)

        log(f"building {len(plan)} archive(s) on the server")
        for entry in plan:
            remote_path = f"{staging}/{entry['file']}"
            entry["remote_path"] = remote_path
            command = entry["cmd"].format(staging=staging, path=remote_path)
            build_started = time.time()
            run(ssh, f"set -o pipefail; {command}", label=f"build {entry['file']}")
            size = int(run(ssh, f"stat -c %s {remote_path}", quiet=True).strip())
            entry["remote_bytes"] = size
            entry["remote_sha256"] = run(
                ssh, f"sha256sum {remote_path} | cut -d' ' -f1", quiet=True).strip()
            entry["build_seconds"] = round(time.time() - build_started, 1)
            log(f"  {entry['file']:42s} {human(size):>12s}  {entry['build_seconds']}s")
        run(ssh, f"chmod 600 {staging}/*.zst", label="restrict staging permissions")

        total_remote = sum(entry["remote_bytes"] for entry in plan)
        log(f"downloading {human(total_remote)} across {len(plan)} file(s) "
            f"({PARALLEL_DOWNLOADS} parallel streams)")

        def pull(entry: dict) -> dict:
            started_at = time.time()
            scp_pull(args.key, args.host, args.user,
                     entry["remote_path"], out_dir, entry["file"])
            local = out_dir / entry["file"]
            entry["local_bytes"] = local.stat().st_size
            entry["local_sha256"] = sha256_local(local)
            entry["download_seconds"] = round(time.time() - started_at, 1)
            if entry["local_bytes"] != entry["remote_bytes"]:
                raise RuntimeError(
                    f"{entry['file']}: size mismatch "
                    f"(server {entry['remote_bytes']} vs local {entry['local_bytes']})")
            if entry["local_sha256"] != entry["remote_sha256"]:
                raise RuntimeError(f"{entry['file']}: sha256 mismatch after download")
            rate = entry["local_bytes"] / max(entry["download_seconds"], 0.1) / 1048576
            log(f"  pulled {entry['file']:42s} {human(entry['local_bytes']):>12s}  "
                f"{entry['download_seconds']}s  {rate:.2f} MB/s  sha256 match")
            return entry

        with concurrent.futures.ThreadPoolExecutor(max_workers=PARALLEL_DOWNLOADS) as pool:
            list(pool.map(pull, plan))

        log("verifying every archive locally (decompress + hash)")
        for entry in plan:
            local = out_dir / entry["file"]
            verify_started = time.time()
            entry["verification"] = verify_zst(local, expect_sqlite=entry["kind"] == "sqlite")
            entry["verify_seconds"] = round(time.time() - verify_started, 1)
            checks = entry["verification"]
            if entry["kind"] == "sqlite":
                if checks["local_quick_check"] != "ok" or checks["local_integrity_check"] != "ok":
                    raise RuntimeError(f"downloaded DB failed integrity checks: {checks}")
                if checks["decompressed_bytes"] != manifest["database_snapshot"]["snapshot_bytes"]:
                    raise RuntimeError("downloaded DB size differs from the server snapshot")
                log(f"  {entry['file']}: quick_check={checks['local_quick_check']} "
                    f"integrity_check={checks['local_integrity_check']} "
                    f"local_apps={checks['local_row_counts']['local_apps']}")
            else:
                log(f"  {entry['file']}: decompressed {human(checks['decompressed_bytes'])} cleanly")

        manifest["archives"] = [
            {k: v for k, v in entry.items() if k not in {"cmd", "remote_path"}}
            for entry in plan
        ]
        manifest["excluded"] = {
            f"{DIALOGUE_RUNTIME}/releases/*/node_modules": "344 MB of npm deps; restore with `npm ci --omit=dev` using the archived package-lock.json",
            f"{DIALOGUE_RUNTIME}/releases/* (other than {release})": "superseded releases; the repo's sillytavern-runtime/ holds their source and the deploy script rebuilds them",
            f"{DIALOGUE_RUNTIME}/backups/*.tgz": "1.2 GB of superseded pre-deploy dialogue-data snapshots; live data is captured fresh here",
            f"{BACKEND_DIR}/backups/*.sqlite3": "2.4 GB pre-deploy DB copy from 2026-08-20, superseded by this snapshot",
            f"{BACKEND_DIR}/*.bak-*": "timestamped copies of backend modules; current versions are archived and the repo holds their history",
            f"{DIALOGUE_DATA}/_webpack": "regenerated build cache",
            "sub2api / grok2api / CPA (same host)": "different deployment, owned by the villainy-sub2api-ops runbook; out of scope here",
        }
        manifest["totals"] = {
            "archive_count": len(plan),
            "compressed_bytes": sum(entry["local_bytes"] for entry in plan),
            "source_bytes_estimate": sum(
                entry["verification"]["decompressed_bytes"] for entry in plan),
            "elapsed_seconds": round(time.time() - started, 1),
        }
        manifest["contains_secrets"] = sorted(
            entry["file"] for entry in plan if entry.get("sensitive"))

        (out_dir / "MANIFEST.json").write_text(
            json.dumps(manifest, indent=2, sort_keys=True, ensure_ascii=False), encoding="utf-8")
        checksum_lines = [f"{entry['local_sha256']}  {entry['file']}" for entry in plan]
        (out_dir / "SHA256SUMS.txt").write_text("\n".join(checksum_lines) + "\n", encoding="utf-8")
        write_restore_doc(out_dir, manifest, plan, release)

        if args.keep_staging:
            log(f"keeping server staging at {staging} as requested")
        else:
            # The local backup is already written and verified at this point, so a
            # dropped SSH transport must not fail the run — just say what was left.
            try:
                run(ssh, f"rm -rf {staging} && rmdir --ignore-fail-on-non-empty {STAGING_ROOT}",
                    label="remove server staging")
                log("server staging removed (all local checks had already passed)")
            except Exception as exc:
                log(f"WARNING: could not remove {staging} ({exc}); "
                    f"remove it manually to free ~{human(total_remote)} on the server")
    finally:
        ssh.close()

    totals = manifest["totals"]
    log("")
    log(f"backup complete in {totals['elapsed_seconds'] / 60:.1f} min")
    log(f"  {out_dir}")
    log(f"  {totals['archive_count']} archives, {human(totals['compressed_bytes'])} on disk "
        f"(from {human(totals['source_bytes_estimate'])} of source data)")
    log(f"  secrets inside: {', '.join(manifest['contains_secrets'])} — keep this directory private")
    log(f"  independent re-check: python tools/verify_homer_backup.py {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
