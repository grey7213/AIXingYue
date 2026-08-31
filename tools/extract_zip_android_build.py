#!/usr/bin/env python3
"""从 AIXingYue-main.zip 抽出构建正式 APK 所需的最小工作区。

Gradle 的 `syncHomerClientAssets` 读 `rootProject.projectDir.parentFile` 下的
`frontend/` 和 `sillytavern-runtime/`，所以目标目录必须是
    <root>/android-app/
    <root>/frontend/
    <root>/sillytavern-runtime/
的形状；根路径必须纯 ASCII（aapt/apksigner 读不了中文路径）。
"""

from __future__ import annotations

import argparse
import sys
import zipfile
from pathlib import Path

ZIP_ROOT = "AIXingYue-main/"

# 前缀 -> 是否需要。构建产物 / gradle 缓存不抽。
SKIP_PREFIXES = (
    "android-app/.gradle/",
    "android-app/app/build/",
    "output/",
    "specs/",
    "docs/",
    "design-system/",
    "sillytavern-runtime/dist/_webpack/d5f2a851c1201ba5/cache/",
)

WANT_PREFIXES = (
    "android-app/",
    "frontend/",
    "sillytavern-runtime/",
    "AGENTS.md",
)


def wanted(rel: str) -> bool:
    if any(rel.startswith(p) for p in SKIP_PREFIXES):
        return False
    return any(rel.startswith(p) for p in WANT_PREFIXES)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--zip", type=Path,
                        default=Path(r"E:\酒馆开发\AIXingYue-main.zip"))
    parser.add_argument("--dest", type=Path, required=True)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if not args.dest.parent.exists():
        raise SystemExit(f"parent of dest does not exist: {args.dest.parent}")
    if str(args.dest).isascii() is False:
        raise SystemExit(f"dest must be pure ASCII, got {args.dest}")

    total = 0
    count = 0
    with zipfile.ZipFile(args.zip) as zf:
        members = []
        for info in zf.infolist():
            if not info.filename.startswith(ZIP_ROOT):
                continue
            rel = info.filename[len(ZIP_ROOT):]
            if not rel or not wanted(rel):
                continue
            members.append((info, rel))
        print(f"selected {len(members)} entries")
        for info, rel in members:
            total += info.file_size
            count += 1
            if args.dry_run:
                continue
            target = args.dest / rel
            if info.is_dir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            with zf.open(info) as src, target.open("wb") as dst:
                while True:
                    chunk = src.read(1024 * 1024)
                    if not chunk:
                        break
                    dst.write(chunk)
            if count % 2000 == 0:
                print(f"  {count} files, {total/1e6:.0f} MB", flush=True)
    print(f"done: {count} files, {total/1e6:.1f} MB uncompressed -> {args.dest}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
