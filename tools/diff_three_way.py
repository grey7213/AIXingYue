#!/usr/bin/env python3
"""三方比较 zip / 本地工作区 / git HEAD，判断每个文件的分歧方向。

用途：交接 ZIP 与本地工作区都从同一个 HEAD 分叉出去时，直接把 ZIP 铺上去会
静默吃掉本地未提交的改动。本脚本给出逐文件结论：
  zip-only-ahead   → 可以安全采用 zip 版本
  local-only-ahead → 采用 zip 会回退本地改动（危险）
  both-ahead       → 真冲突，需要人工合并
  same             → 无差异
"""

from __future__ import annotations

import argparse
import hashlib
import subprocess
import sys
from pathlib import Path

TEXT_SUFFIXES = {
    ".html", ".css", ".js", ".mjs", ".json", ".md", ".txt", ".java", ".xml",
    ".gradle", ".properties", ".yaml", ".yml", ".py", ".svg", ".pro", ".cjs",
}


def norm(data: bytes, suffix: str) -> str:
    if suffix.lower() in TEXT_SUFFIXES:
        data = data.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    return hashlib.sha256(data).hexdigest()


def head_blobs(repo: Path, prefix: str) -> dict[str, str]:
    listing = subprocess.run(
        ["git", "-C", str(repo), "ls-tree", "-r", "HEAD", "--name-only", prefix],
        capture_output=True, text=True, encoding="utf-8", check=True,
    ).stdout.split("\n")
    result = {}
    for path in listing:
        path = path.strip()
        if not path:
            continue
        blob = subprocess.run(
            ["git", "-C", str(repo), "show", f"HEAD:{path}"],
            capture_output=True, check=True,
        ).stdout
        rel = path[len(prefix):].lstrip("/")
        result[rel] = norm(blob, Path(path).suffix)
    return result


def tree_hashes(root: Path) -> dict[str, str]:
    return {
        str(p.relative_to(root)).replace("\\", "/"): norm(p.read_bytes(), p.suffix)
        for p in root.rglob("*") if p.is_file()
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", type=Path, required=True)
    ap.add_argument("--prefix", required=True, help="e.g. frontend")
    ap.add_argument("--zip-tree", type=Path, required=True)
    args = ap.parse_args()

    head = head_blobs(args.repo, args.prefix)
    local = tree_hashes(args.repo / args.prefix)
    zipt = tree_hashes(args.zip_tree)

    buckets: dict[str, list[str]] = {
        "same": [], "zip-only-ahead": [], "local-only-ahead": [],
        "both-ahead": [], "zip-new-file": [], "local-new-file": [],
        "missing-in-zip": [],
    }

    for rel in sorted(set(head) | set(local) | set(zipt)):
        h, l, z = head.get(rel), local.get(rel), zipt.get(rel)
        if z is None:
            buckets["missing-in-zip"].append(rel)
        elif h is None and l is None:
            buckets["zip-new-file"].append(rel)
        elif h is None:
            buckets["zip-new-file" if z != l else "same"].append(rel)
        elif l is None:
            buckets["local-new-file"].append(rel)
        elif l == z:
            buckets["same"].append(rel)
        elif l == h:
            buckets["zip-only-ahead"].append(rel)
        elif z == h:
            buckets["local-only-ahead"].append(rel)
        else:
            buckets["both-ahead"].append(rel)

    order = ["local-only-ahead", "both-ahead", "missing-in-zip",
             "zip-only-ahead", "zip-new-file", "local-new-file", "same"]
    danger = {"local-only-ahead", "both-ahead", "missing-in-zip"}
    for name in order:
        items = buckets[name]
        mark = "!!" if name in danger and items else "  "
        print(f"\n{mark} {name} ({len(items)})")
        limit = None if name in danger else 12
        for rel in items[:limit]:
            print(f"     {rel}")
        if limit and len(items) > limit:
            print(f"     ... +{len(items) - limit} more")

    risky = sum(len(buckets[k]) for k in danger)
    print(f"\nfiles where taking the zip wholesale loses work: {risky}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
