#!/usr/bin/env python3
"""把指定的单个文件推到 Homer 生产对应位置，推之前先做 root-only 备份。

用途：不跑完整部署脚本就修一两个文件（完整部署会连带重建 Nginx 配置、
前端全量同步和 dialogue runtime release，blast radius 太大）。

    python tools/push_homer_file.py backend
    python tools/push_homer_file.py index dashboard
    python tools/push_homer_file.py --list
"""

from __future__ import annotations

import argparse
import hashlib
import posixpath
import shlex
import sys
from pathlib import Path

import paramiko

DEFAULT_HOST = "38.76.218.46"
DEFAULT_USER = "root"
DEFAULT_KEY = Path.home() / ".ssh" / "villainy_backup_ed25519"
EXPECTED_HOSTNAME = "vm-851a1bc4a978a80f"
REPO = Path(__file__).resolve().parent.parent

# name -> (local path, remote path, owner, mode, restart unit or None)
TARGETS = {
    "backend-notifications": (
        "tools/notifications_extension.py",
        "/opt/ai-fengyue-backend/notifications_extension.py",
        "root:ai-xingyue", "0640", "ai-fengyue-backend",
    ),
    "backend": (
        "tools/ai_fengyue_local_server.py",
        "/opt/ai-fengyue-backend/ai_fengyue_local_server.py",
        "root:ai-xingyue", "0640", "ai-fengyue-backend",
    ),
    # 后端会 `from card_experience_extension import ...`，两者必须同批推。
    # 单推 backend 而这个模块偏旧，服务重启时直接 ImportError。
    "backend-card-ext": (
        "tools/card_experience_extension.py",
        "/opt/ai-fengyue-backend/card_experience_extension.py",
        "root:ai-xingyue", "0640", "ai-fengyue-backend",
    ),
    "index": (
        "frontend/index.html",
        "/var/www/ai-fengyue-frontend/index.html",
        "www-data:www-data", "0644", None,
    ),
    "dashboard": (
        "frontend/dashboard.html",
        "/var/www/ai-fengyue-frontend/dashboard.html",
        "www-data:www-data", "0644", None,
    ),
    "admin": (
        "frontend/admin.html",
        "/var/www/ai-fengyue-frontend/admin.html",
        "www-data:www-data", "0644", None,
    ),
    # 对话运行时的静态模块：改完不用重启服务（server.js 只在启动时编译 lib.js，
    # scripts/ 下的 ESM 是原样发给浏览器的）。注意 nginx 给 scripts/ 加了 10 分钟
    # 缓存，所以已打开的页面最多 10 分钟后才会拿到新版本。
    "dialogue-extensions": (
        "sillytavern-runtime/public/scripts/extensions.js",
        "/opt/homer-dialogue-runtime/current/public/scripts/extensions.js",
        "root:root", "0644", None,
    ),
    "dialogue-index": (
        "sillytavern-runtime/public/index.html",
        "/opt/homer-dialogue-runtime/current/public/index.html",
        "root:root", "0644", None,
    ),
    "dialogue-bridge": (
        "sillytavern-runtime/public/scripts/extensions/homer-bridge/index.js",
        "/opt/homer-dialogue-runtime/current/public/scripts/extensions/homer-bridge/index.js",
        "root:root", "0644", None,
    ),
    "dialogue-bridge-style": (
        "sillytavern-runtime/public/scripts/extensions/homer-bridge/style.css",
        "/opt/homer-dialogue-runtime/current/public/scripts/extensions/homer-bridge/style.css",
        "root:root", "0644", None,
    ),
    "dialogue-bridge-stage": (
        "sillytavern-runtime/public/scripts/extensions/homer-bridge/card-stage.js",
        "/opt/homer-dialogue-runtime/current/public/scripts/extensions/homer-bridge/card-stage.js",
        "root:root", "0644", None,
    ),
    "dialogue-bridge-keywords": (
        "sillytavern-runtime/public/scripts/extensions/homer-bridge/keyword-injector.js",
        "/opt/homer-dialogue-runtime/current/public/scripts/extensions/homer-bridge/keyword-injector.js",
        "root:root", "0644", None,
    ),
    # manifest 带 style.css 的缓存串，改了样式必须同批推，否则浏览器继续用旧 CSS。
    "dialogue-bridge-manifest": (
        "sillytavern-runtime/public/scripts/extensions/homer-bridge/manifest.json",
        "/opt/homer-dialogue-runtime/current/public/scripts/extensions/homer-bridge/manifest.json",
        "root:root", "0644", None,
    ),
    "dialogue-script": (
        "sillytavern-runtime/public/script.js",
        "/opt/homer-dialogue-runtime/current/public/script.js",
        "root:root", "0644", None,
    ),
    "dialogue-st-context": (
        "sillytavern-runtime/public/scripts/st-context.js",
        "/opt/homer-dialogue-runtime/current/public/scripts/st-context.js",
        "root:root", "0644", None,
    ),
    "dialogue-tts": (
        "sillytavern-runtime/public/scripts/extensions/tts/system.js",
        "/opt/homer-dialogue-runtime/current/public/scripts/extensions/tts/system.js",
        "root:root", "0644", None,
    ),
    # src/ 下的是 Node 侧路由，改了必须重启 homer-dialogue 才生效。
    "dialogue-endpoint": (
        "sillytavern-runtime/src/endpoints/homer.js",
        "/opt/homer-dialogue-runtime/current/src/endpoints/homer.js",
        "root:root", "0644", "homer-dialogue",
    ),
}


def log(message: str) -> None:
    print(f"[homer-push] {message}", flush=True)


def sha256_local(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def connect(host: str, user: str, key: Path) -> paramiko.SSHClient:
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(hostname=host, username=user, key_filename=str(key),
                   look_for_keys=False, allow_agent=False, timeout=20,
                   banner_timeout=20, auth_timeout=20)
    return client


def run(ssh: paramiko.SSHClient, command: str, *, check: bool = True, quiet: bool = False) -> str:
    if not quiet:
        log(f"remote: {command}")
    _, stdout, stderr = ssh.exec_command(command)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    code = stdout.channel.recv_exit_status()
    if err.strip() and not quiet:
        print(err.rstrip(), file=sys.stderr)
    if check and code != 0:
        raise RuntimeError(f"remote command failed with exit {code}: {command}\n{err.strip()}")
    return out


def resolve_targets(names: list[str], paths: list[str]) -> list[tuple[str, str, str, str, str | None]]:
    """把命名目标和 --path 通配都归一成 (label, local_rel, remote, owner, mode, unit)。"""
    resolved: list[tuple[str, str, str, str, str, str | None]] = []
    for name in names:
        rel, remote, owner, mode, unit = TARGETS[name]
        resolved.append((name, rel, remote, owner, mode, unit))
    for pattern in paths:
        # frontend/ 下的东西一律映射到 web root，其余不猜，直接拒绝
        matches = sorted(REPO.glob(pattern))
        if not matches:
            raise SystemExit(f"--path matched nothing: {pattern}")
        for match in matches:
            if not match.is_file():
                continue
            rel = match.relative_to(REPO).as_posix()
            if not rel.startswith("frontend/"):
                raise SystemExit(
                    f"--path only supports frontend/* (got {rel}); use a named target for the rest")
            remote = "/var/www/ai-fengyue-frontend/" + rel[len("frontend/"):]
            resolved.append((rel, rel, remote, "www-data:www-data", "0644", None))
    # 同一个远端路径只推一次
    seen: set[str] = set()
    unique = []
    for entry in resolved:
        if entry[2] in seen:
            continue
        seen.add(entry[2])
        unique.append(entry)
    return unique


def main() -> int:
    parser = argparse.ArgumentParser(description="推单个文件到 Homer 生产")
    parser.add_argument("names", nargs="*", help=f"目标名，可选：{', '.join(TARGETS)}")
    parser.add_argument("--path", action="append", default=[], metavar="GLOB",
                        help="仓库相对路径或 glob，仅支持 frontend/*，可重复")
    parser.add_argument("--list", action="store_true", help="列出可推的目标")
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--user", default=DEFAULT_USER)
    parser.add_argument("--key", type=Path, default=DEFAULT_KEY)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if args.list or (not args.names and not args.path):
        for name, (local, remote, owner, mode, unit) in TARGETS.items():
            print(f"{name:10s} {local:40s} -> {remote}  ({owner} {mode}"
                  + (f", restart {unit}" if unit else "") + ")")
        print("\n也可以用 --path frontend/app/*.html 推任意前端文件")
        return 0

    unknown = [n for n in args.names if n not in TARGETS]
    if unknown:
        raise SystemExit(f"unknown target(s): {', '.join(unknown)}")

    targets = resolve_targets(args.names, args.path)
    print(f"[homer-push] {len(targets)} file(s) to consider")

    ssh = connect(args.host, args.user, args.key)
    try:
        hostname = run(ssh, "hostname", quiet=True).strip()
        if hostname != EXPECTED_HOSTNAME:
            raise SystemExit(f"unexpected host {hostname!r}, expected {EXPECTED_HOSTNAME!r}")
        log(f"host: {hostname}")

        stamp = run(ssh, "date +%Y%m%d-%H%M%S", quiet=True).strip()
        units: list[str] = []
        pushed = skipped = 0
        sftp = ssh.open_sftp()
        try:
            for label, rel, remote, owner, mode, unit in targets:
                local = REPO / rel
                if not local.is_file():
                    raise SystemExit(f"local file missing: {local}")
                want = sha256_local(local)
                have = run(ssh, f"sha256sum {shlex.quote(remote)} 2>/dev/null | cut -d' ' -f1",
                           quiet=True).strip()
                if have == want:
                    skipped += 1
                    continue
                if args.dry_run:
                    log(f"{label}: dry-run, would upload -> {remote} "
                        f"(local={want[:12]} remote={have[:12] or 'absent'})")
                    pushed += 1
                    continue
                path_tag = hashlib.sha256(remote.encode("utf-8")).hexdigest()[:12]
                backup = f"/root/homer-push-backup-{stamp}-{path_tag}-{posixpath.basename(remote)}"
                run(ssh, f"[ -f {shlex.quote(remote)} ] && install -m 600 -o root -g root "
                         f"{shlex.quote(remote)} {shlex.quote(backup)} || true", quiet=True)
                # 新增资源目录（如 assets/img/brand/）在线上可能还不存在，
                # SFTP put 不会自动建父目录，会直接 ENOENT。
                parent = posixpath.dirname(remote)
                run(ssh, f"install -d -o {shlex.quote(owner.split(':')[0])} "
                         f"-g {shlex.quote(owner.split(':')[1])} -m 0755 {shlex.quote(parent)}",
                    quiet=True)
                staging = f"{remote}.upload"
                sftp.put(str(local), staging)
                run(ssh, f"chown {owner} {shlex.quote(staging)} && chmod {mode} {shlex.quote(staging)} "
                         f"&& mv {shlex.quote(staging)} {shlex.quote(remote)}", quiet=True)
                got = run(ssh, f"sha256sum {shlex.quote(remote)} | cut -d' ' -f1", quiet=True).strip()
                if got != want:
                    raise SystemExit(f"{label}: remote hash mismatch after upload ({got} != {want})")
                log(f"{label}: uploaded and verified")
                pushed += 1
                if unit and unit not in units:
                    units.append(unit)
        finally:
            sftp.close()
        log(f"{pushed} uploaded, {skipped} already identical")

        for unit in units:
            if args.dry_run:
                log(f"dry-run: would restart {unit}")
                continue
            run(ssh, f"systemctl restart {unit}")
            state = run(ssh, f"systemctl is-active {unit}", quiet=True).strip()
            restarts = run(ssh, f"systemctl show -p NRestarts --value {unit}", quiet=True).strip()
            log(f"{unit}: {state} (NRestarts={restarts})")
            if state != "active":
                run(ssh, f"journalctl -u {unit} -n 30 --no-pager", check=False)
                raise SystemExit(f"{unit} is not active after restart")
    finally:
        ssh.close()
    log("done")
    return 0


if __name__ == "__main__":
    sys.exit(main())
