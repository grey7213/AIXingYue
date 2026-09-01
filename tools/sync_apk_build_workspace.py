r"""把仓库工作区的 frontend / runtime 同步到 APK 构建目录（纯 ASCII 路径）。

构建目录 E:\homer-apk-1140 是从交接 ZIP 抽出来的，落在 HEAD~1；
Gradle 的 syncHomerClientAssets 从它读 frontend/ 与 sillytavern-runtime/，
所以出包前必须先把仓库的现行版本推过去，否则 APK 内置的是旧前端。

MemoryBooks 的 node_modules 不同步：扩展入口是打包后的 index.build.js，
运行时不加载 node_modules，同步只会白涨包体。
"""

from __future__ import annotations

import filecmp
import hashlib
import shutil
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

REPO = Path(r"E:\酒馆开发")
WORKSPACE = Path(r"E:\homer-apk-1140")
SUBTREES = ("frontend", "sillytavern-runtime/public")
SKIP_PARTS = ("node_modules", "__pycache__")


def relevant(path: Path) -> bool:
    return not any(part in SKIP_PARTS for part in path.parts)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    copied: list[str] = []
    added: list[str] = []
    for subtree in SUBTREES:
        source_root = REPO / subtree
        target_root = WORKSPACE / subtree
        for source in sorted(source_root.rglob("*")):
            if not source.is_file():
                continue
            rel = source.relative_to(source_root)
            if not relevant(rel):
                continue
            target = target_root / rel
            # 新增模块也必须过去。之前这里是「工作区没有就跳过」，结果
            # page-cache.js 这种新文件不会进 APK，explore.js/me.js 的 import
            # 在包内 404，两页直接白屏。
            new_file = not target.exists()
            if not new_file and filecmp.cmp(source, target, shallow=False):
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
            assert digest(source) == digest(target)
            (added if new_file else copied).append(f"{subtree}/{rel.as_posix()}")

    print(f"synced {len(copied)} changed + {len(added)} new files into {WORKSPACE}")
    for rel in added:
        print(f"  + {rel}")
    for rel in copied:
        print(f"    {rel}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
