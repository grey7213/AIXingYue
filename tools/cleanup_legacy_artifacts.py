r"""清理惑梦项目的历史备份产物。默认 dry-run，加 --apply 才真删。

保留原则：
  1. 线上仍在服役的东西（签名 keystore、离线开发种子库、被 tools/ 引用的样本）
  2. 最新几个版本的 APK 与最新的生产备份
  3. CTF/逆向时期的产物（另一个项目，用户明确要求保留）

删除的都是一次性导入产物、历史交接解包、被更新备份取代的快照。
每条都标了「为什么可以删」，执行前用 --apply 之外的默认模式看一遍。
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

REPO = Path(r"E:\酒馆开发")
BACKUPS = Path(r"E:\homer-backups")
BUILD_WS = Path(r"E:\homer-apk-1140")

# 绝不能删：删了会让工具链或下一次出包直接失败。
PROTECTED = {
    REPO / "output" / "zip-1-repack" / "zip1-repack.keystore",       # 唯一正式签名私钥
    REPO / "output" / "zip-1-repack" / "local-server",               # offline_dev 种子库
    REPO / "output" / "zip-1-repack" / "ai-xingyue-icon-source.png", # patch_ai_xingyue_icon 默认输入
    REPO / "output" / "zip-1-repack" / "homer-web-apk-signed.apk",   # deploy 脚本 DEFAULT_APK
    REPO / "output" / "zip-1-repack" / "ctf-breach-artifacts.zip",   # CTF，用户要求保留
    REPO / "output" / "homer-handoff-20260731" / "samples",          # 两个 selftest 读它
    REPO / "output" / "homer-release",                               # 262/263/265/266 成品
    REPO / "output" / "offline-dev",                                 # 本地开发状态
    REPO / "output" / "sillytavern-e2e",                             # 两个 e2e 工具引用
    REPO / "output" / "private-store",                               # CTF 证书实验
    REPO / "output" / "work",                                        # CTF 证书实验
    BACKUPS / "homer-prod-20260824-192623",                          # 唯一全量备份
    BACKUPS / "homer-prod-20260901-160424",                          # 最新数据库
    BUILD_WS / "_sign" / "signer.keystore",
    BUILD_WS / "_sign" / "homer-1.14.1-266-release-signed.apk",
}

# (路径, 删除理由)
TARGETS: list[tuple[Path, str]] = [
    (BACKUPS / "homer-prod-20260831-155027",
     "仅数据库快照，已被 09-01 那份取代"),

    (REPO / "output" / "card-zip-import-20260704",
     "一次性角色卡导入产物（bundle + 封面副本），已入库"),
    (REPO / "output" / "AIXingYue-main-20260818-staging",
     "交接 ZIP 的解包暂存；ZIP 本体保留，需要时可重解"),
    (REPO / "output" / "role-card-download-import",
     "一次性导入产物，已入库"),
    (REPO / "output" / "sillytavern-tavo-check",
     "SillyTavern/Tavo 兼容性排查日志与构建中间物"),
    (REPO / "output" / "role-card-tag-export-20260710-204132",
     "标签导出中间产物，结论已进 role_card_annotations 表"),
    (REPO / "output" / "homer-handoff-audit",
     "07-17 交接审计解包，结论已进 specs"),
    (REPO / "output" / "homer-sillytavern-apk-readiness-20260802",
     "07-29 打包前排查产物，结论已进 specs"),
    (REPO / "output" / "role-card-import-unusable-75",
     "75 张不可用卡的排查副本"),
    (REPO / "output" / "farm-zip-audit",
     "农场 ZIP 审计解包"),
    (REPO / "output" / "apk-build-20260806",
     "1.12.20 (260) 成品与其 prebuild 备份；线上早已是 266"),
    (REPO / "output" / "role-card-import",
     "一次性导入产物"),
    (REPO / "output" / "backup-inspect-20260819",
     "旧服务器备份可达性核查产物"),
    (REPO / "output" / "role-card-import-all",
     "一次性导入产物"),
    (REPO / "output" / "handoff-merge-20260717-142441",
     "07-17 交接合并暂存"),
    (REPO / "output" / "handoff",
     "07-17 交接解包"),
    (REPO / "output" / "handoff-audit",
     "07-17 交接审计"),
    (REPO / "output" / "homer-spine-runtime",
     "Spine 运行时调试产物"),
    (REPO / "output" / "playwright-node",
     "旧 Playwright/Node 下载缓存"),
    (REPO / "output" / "role-card-tag-sync-20260713",
     "标签同步中间产物"),
    (REPO / "output" / "js-slash-runner-audit-4.8.19",
     "扩展审计解包"),
    (REPO / "git-backups",
     "6-16 那版 ai-xingyue-latest.apk 与随手拷的脚本副本；脚本都在 git 里，APK 版本已过时"),
]

# zip-1-repack 里 262 之前的历史签名包：线上从未用过它们做 canonical，
# 且证书与现役一致（真正要紧的是 keystore，已保护）。
LEGACY_REPACK_APKS = [
    "ai-xingyue-public-download-check.apk",
    "ai-xingyue-patcher-signed.apk",
    "ai-fengyue-repacked-with-recharge-unaligned.apk",
    "ai-fengyue-localserver-signed.apk",
    "ai-xingyue-parity-signed.apk",
    "ai-fengyue-recharge-signed.apk",
    "ai-fengyue-villainy-signed.apk",
]

# 构建工作区里未发布/中间产物。264 从未上线，aligned 是签名前中间文件。
BUILD_LEFTOVERS = [
    "homer-1.14.0-264-aligned.apk",
    "homer-1.14.0-264-release-signed.apk",
    "homer-1.14.0-264-release-signed.apk.idsig",
    "homer-1.14.0-265-aligned.apk",
    "homer-1.14.1-266-aligned.apk",
]

# 08-20 官方角色卡恢复：只删大件，留下 KB 级的报告/计划 JSON —— 那些是那次
# 恢复到底改了哪 8778 张卡的唯一书面记录，占地可以忽略。
ROLE_CARD_PUBLISH_BULK = [
    ("local-test.sqlite3", "恢复演练用的本地库副本，生产库另有备份"),
    ("official-covers.tar.gz", "封面归档；生产 8560 张仍在服役，08-24 全量备份也含 media-cache"),
    ("local-test-before.sqlite3", "演练前快照"),
    ("live-before.sqlite3", "演练前快照（结构，非生产全量）"),
]

# 07-31 交接解包：samples/ 被两个 selftest 读，其余是已合并完的快照。
HANDOFF_20260731_BULK = ["output", "sillytavern-runtime", "frontend", "tools", "specs"]


def size_of(path: Path) -> int:
    if path.is_file():
        return path.stat().st_size
    total = 0
    for child in path.rglob("*"):
        if child.is_file():
            try:
                total += child.stat().st_size
            except OSError:
                pass
    return total


def guard(path: Path) -> None:
    """拒绝删除受保护路径本身或它的任何祖先。"""
    resolved = path.resolve()
    for keep in PROTECTED:
        keep = keep.resolve()
        if resolved == keep or keep.is_relative_to(resolved):
            raise SystemExit(f"REFUSING: {path} would remove protected {keep}")


def clear_readonly(func, path, _exc):
    """git 的 objects/ 是只读的，rmtree 会 WinError 5；清掉只读位再重试一次。"""
    import os
    import stat
    os.chmod(path, stat.S_IWRITE)
    func(path)


def remove(path: Path) -> None:
    if path.is_dir():
        shutil.rmtree(path, onexc=clear_readonly)
    else:
        path.unlink()


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="真删；默认只报告")
    args = parser.parse_args()

    plan: list[tuple[Path, str, int]] = []
    for path, reason in TARGETS:
        if path.exists():
            guard(path)
            plan.append((path, reason, size_of(path)))
    for name in LEGACY_REPACK_APKS:
        path = REPO / "output" / "zip-1-repack" / name
        if path.exists():
            guard(path)
            plan.append((path, "262 之前的历史签名包", size_of(path)))
    for name in BUILD_LEFTOVERS:
        path = BUILD_WS / "_sign" / name
        if path.exists():
            guard(path)
            plan.append((path, "未发布的 264 / 签名前中间文件", size_of(path)))
    for name, reason in ROLE_CARD_PUBLISH_BULK:
        path = REPO / "output" / "role-card-publish-20260820" / name
        if path.exists():
            guard(path)
            plan.append((path, reason, size_of(path)))
    for name in HANDOFF_20260731_BULK:
        path = REPO / "output" / "homer-handoff-20260731" / name
        if path.exists():
            guard(path)
            plan.append((path, "07-31 交接解包，已合并进仓库（samples/ 保留）", size_of(path)))
    for path in sorted((REPO / "output").glob("homer-version-test-*")):
        guard(path)
        plan.append((path, "版本对比临时目录", size_of(path)))

    plan.sort(key=lambda item: item[2], reverse=True)
    total = sum(item[2] for item in plan)
    mode = "DELETING" if args.apply else "would delete"
    for path, reason, size in plan:
        label = str(path).replace(str(REPO) + "\\", "").replace(str(BUILD_WS) + "\\", "ws:")
        print(f"{size / 1024 / 1024:9.1f} MB  {label}\n{'':13}└─ {reason}")
        if args.apply:
            remove(path)

    print(f"\n{mode}: {len(plan)} entries, {total / 1024 / 1024 / 1024:.2f} GB")
    if not args.apply:
        print("re-run with --apply to delete")
    else:
        missing = [str(p) for p in PROTECTED if not p.exists()]
        print("protected paths still present:", "ALL OK" if not missing else missing)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
