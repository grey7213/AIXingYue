#!/usr/bin/env python3
"""比较两棵目录树，文本文件先归一化换行再比较，避免 CRLF/LF 噪声。"""
from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

TEXT_SUFFIXES = {
    ".html", ".css", ".js", ".mjs", ".json", ".md", ".txt", ".java", ".xml",
    ".gradle", ".properties", ".yaml", ".yml", ".py", ".svg", ".pro", ".cjs",
}


def digest(path: Path) -> str:
    data = path.read_bytes()
    if path.suffix.lower() in TEXT_SUFFIXES:
        data = data.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    return hashlib.sha256(data).hexdigest()


def index(root: Path) -> dict[str, Path]:
    return {
        str(p.relative_to(root)).replace("\\", "/"): p
        for p in root.rglob("*") if p.is_file()
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("a")
    ap.add_argument("b")
    ap.add_argument("--label-a", default="A")
    ap.add_argument("--label-b", default="B")
    ap.add_argument("--limit", type=int, default=200)
    args = ap.parse_args()

    ia, ib = index(Path(args.a)), index(Path(args.b))
    only_a = sorted(set(ia) - set(ib))
    only_b = sorted(set(ib) - set(ia))
    shared = sorted(set(ia) & set(ib))
    changed = [k for k in shared if digest(ia[k]) != digest(ib[k])]

    print(f"{args.label_a}: {len(ia)} files   {args.label_b}: {len(ib)} files")
    print(f"identical: {len(shared) - len(changed)}   changed: {len(changed)}   "
          f"only-{args.label_a}: {len(only_a)}   only-{args.label_b}: {len(only_b)}")
    for title, items in (
        (f"only in {args.label_a}", only_a),
        (f"only in {args.label_b}", only_b),
        ("changed", changed),
    ):
        print(f"\n--- {title} ({len(items)}) ---")
        for k in items[: args.limit]:
            if title == "changed":
                print(f"  {k}  [{ia[k].stat().st_size} vs {ib[k].stat().st_size}]")
            else:
                print(f"  {k}")
        if len(items) > args.limit:
            print(f"  ... +{len(items) - args.limit} more")
    return 0


if __name__ == "__main__":
    sys.exit(main())
