#!/usr/bin/env python3
"""把生产上的前端/bridge 文件拉下来，与本地做「归一化」对比。

为什么需要：这个项目踩过两次「生产跑着未提交代码」——手工改完的东西过几天被
部署脚本冲回去，或者反过来，本地推上去把线上手工修复覆盖掉。推之前先看清每个
文件的差异是不是**只有**我这次打算改的东西。

归一化掉的只有 `?v=<缓存串>`：它每轮必然全量变化，留着会把真实差异淹掉。
其余任何差异都会被打印出来。
"""

from __future__ import annotations

import argparse
import difflib
import posixpath
import re
import sys
from pathlib import Path

import paramiko

REPO = Path(__file__).resolve().parent.parent
HOST = "38.76.218.46"
USER = "root"
KEY = Path.home() / ".ssh" / "villainy_backup_ed25519"
EXPECTED_HOSTNAME = "vm-851a1bc4a978a80f"

WEB_ROOT = "/var/www/ai-fengyue-frontend"
REMOTE_MAP = {
    "frontend/": WEB_ROOT + "/",
    "sillytavern-runtime/public/scripts/extensions/homer-bridge/":
        "/opt/homer-dialogue-runtime/current/public/scripts/extensions/homer-bridge/",
    "tools/ai_fengyue_local_server.py":
        "/opt/ai-fengyue-backend/ai_fengyue_local_server.py",
}
CACHE_TOKEN = re.compile(r"\?v=20[0-9]{6}-[a-z0-9-]+")


def remote_path(rel: str) -> str:
    for prefix, target in REMOTE_MAP.items():
        if rel == prefix:
            return target
        if prefix.endswith("/") and rel.startswith(prefix):
            return target + rel[len(prefix):]
    raise SystemExit(f"no remote mapping for {rel}")


def normalize(data: bytes) -> list[str]:
    text = data.decode("utf-8", errors="replace").replace("\r\n", "\n")
    return CACHE_TOKEN.sub("?v=TOKEN", text).split("\n")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("paths", nargs="+", help="仓库相对路径或 glob")
    parser.add_argument("--context", type=int, default=0)
    parser.add_argument("--max-lines", type=int, default=40, help="每个文件最多打印几行差异")
    args = parser.parse_args()

    rels: list[str] = []
    for pattern in args.paths:
        matches = sorted(p for p in REPO.glob(pattern) if p.is_file())
        if not matches:
            raise SystemExit(f"matched nothing: {pattern}")
        rels.extend(m.relative_to(REPO).as_posix() for m in matches)

    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(hostname=HOST, username=USER, key_filename=str(KEY),
                look_for_keys=False, allow_agent=False, timeout=20)
    try:
        _, out, _ = ssh.exec_command("hostname")
        hostname = out.read().decode().strip()
        if hostname != EXPECTED_HOSTNAME:
            raise SystemExit(f"unexpected host {hostname!r}")
        sftp = ssh.open_sftp()
        identical = differing = missing = 0
        try:
            for rel in rels:
                remote = remote_path(rel)
                try:
                    with sftp.open(remote, "rb") as handle:
                        handle.prefetch()
                        remote_bytes = handle.read()
                except IOError:
                    print(f"\n!! ABSENT ON PRODUCTION: {rel} -> {remote}")
                    missing += 1
                    continue
                local_lines = normalize((REPO / rel).read_bytes())
                remote_lines = normalize(remote_bytes)
                if local_lines == remote_lines:
                    identical += 1
                    continue
                differing += 1
                diff = list(difflib.unified_diff(
                    remote_lines, local_lines,
                    f"production:{posixpath.basename(remote)}", f"local:{rel}",
                    lineterm="", n=args.context,
                ))
                print(f"\n### {rel}  ({len(diff)} diff lines, cache tokens normalized)")
                for line in diff[:args.max_lines]:
                    print("   " + line)
                if len(diff) > args.max_lines:
                    print(f"   ... +{len(diff) - args.max_lines} more")
        finally:
            sftp.close()
    finally:
        ssh.close()

    print(f"\nsummary: {identical} identical (modulo cache token), "
          f"{differing} differing, {missing} absent on production")
    return 0


if __name__ == "__main__":
    sys.exit(main())
