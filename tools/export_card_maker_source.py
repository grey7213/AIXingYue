from __future__ import annotations

import hashlib
import json
import shutil
import sys
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STAMP = "20260715"
EXPORT_NAME = f"card-maker-source-export-{STAMP}"
OUTPUT_ROOT = ROOT / "output"
EXPORT_ROOT = OUTPUT_ROOT / EXPORT_NAME
ZIP_PATH = OUTPUT_ROOT / f"{EXPORT_NAME}.zip"
BACKEND = ROOT / "tools" / "ai_fengyue_local_server.py"


COPY_MAP = {
    "frontend/app/create.html": "production-source/frontend/app/create.html",
    "frontend/app/my-apps.html": "production-source/frontend/app/my-apps.html",
    "frontend/app/assets/js/create.js": "production-source/frontend/app/assets/js/create.js",
    "frontend/app/assets/js/my-apps.js": "production-source/frontend/app/assets/js/my-apps.js",
    "frontend/app/chat.html": "production-source/frontend/app/chat.html",
    "frontend/app/assets/js/chat.js": "production-source/frontend/app/assets/js/chat.js",
    "frontend/app/assets/js/app-core.js": "production-source/frontend/app/assets/js/app-core.js",
    "frontend/app/assets/js/layout.js": "production-source/frontend/app/assets/js/layout.js",
    "frontend/app/assets/css/app.css": "production-source/frontend/app/assets/css/app.css",
    "frontend/app/assets/css/worldbook-editor.css": "production-source/frontend/app/assets/css/worldbook-editor.css",
    "frontend/admin.html": "production-source/admin/admin.html",
    "frontend/assets/js/admin-app.js": "production-source/admin/assets/js/admin-app.js",
    "frontend/assets/js/api.js": "production-source/admin/assets/js/api.js",
    "frontend/assets/css/admin.css": "production-source/admin/assets/css/admin.css",
}


# Verbatim ranges from the current production single-file backend. They are kept
# as text excerpts because several blocks live inside Store/HTTP handler classes.
# Platform-private required-worldbook content and unrelated auth/payment code are
# intentionally excluded.
BACKEND_RANGES = [
    (2460, 2582, "sqlite-schema"),
    (2812, 2895, "local-app-migration-display-id"),
    (5300, 5628, "local-app-store-crud"),
    (6419, 6562, "global-preset-store"),
    (6905, 7208, "admin-import-normalization"),
    (8625, 9144, "card-conversion"),
    (9197, 9850, "rich-field-normalization"),
    (9851, 10230, "json-png-import-export"),
    (10283, 10470, "worldbook-prompt-runtime"),
    (10571, 10740, "regex-runtime"),
    (13503, 13660, "user-card-http-routes"),
    (14988, 15070, "admin-card-http-routes"),
]


def write_text(relative: str, content: str) -> None:
    path = EXPORT_ROOT / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content.rstrip() + "\n", encoding="utf-8", newline="\n")


def clean_target() -> None:
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    resolved_output = OUTPUT_ROOT.resolve()
    resolved_export = EXPORT_ROOT.resolve()
    if resolved_export.parent != resolved_output or not EXPORT_ROOT.name.startswith("card-maker-source-export-"):
        raise RuntimeError("unsafe export target")
    if EXPORT_ROOT.exists():
        shutil.rmtree(EXPORT_ROOT)
    if ZIP_PATH.exists():
        ZIP_PATH.unlink()


def copy_sources() -> None:
    for source_rel, target_rel in COPY_MAP.items():
        source = ROOT / source_rel
        if not source.is_file():
            raise FileNotFoundError(source)
        target = EXPORT_ROOT / target_rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        if target.suffix.lower() in {".html", ".js", ".css"}:
            text = target.read_text(encoding="utf-8")
            text = text.replace("patcher.villainy.top", "example.com")
            text = text.replace("https://api.celestiai.xyz/v1", "https://api.example.com/v1")
            target.write_text(text, encoding="utf-8", newline="\n")


def export_backend_excerpts() -> None:
    lines = BACKEND.read_text(encoding="utf-8").splitlines()
    source_hash = hashlib.sha256(BACKEND.read_bytes()).hexdigest()
    out = [
        "# Production card-maker excerpts",
        "# Source: tools/ai_fengyue_local_server.py",
        f"# Source SHA-256: {source_hash}",
        "# These blocks are verbatim and retain original production line numbers.",
        "# Private required-worldbook content and unrelated platform modules are omitted.",
        "",
    ]
    for start, end, label in BACKEND_RANGES:
        out.extend([
            "# " + "=" * 76,
            f"# {label}: production lines {start}-{end}",
            "# " + "=" * 76,
        ])
        for number in range(start, min(end, len(lines)) + 1):
            out.append(f"{number:05d}: {lines[number - 1]}")
        out.append("")
    write_text("production-source/backend/ai_fengyue_local_server.card-maker-excerpts.py.txt", "\n".join(out))


def create_example() -> None:
    example = {
        "spec": "chara_card_v2",
        "spec_version": "2.0",
        "data": {
            "name": "示例角色",
            "description": "用于演示字段结构的虚构角色。",
            "personality": "沉稳、友善。",
            "scenario": "用户与角色在图书馆初次见面。",
            "first_mes": "你好，我是{{char}}。",
            "mes_example": "<START>\n{{user}}: 你好\n{{char}}: 很高兴见到你。",
            "creator_notes": "仅用于源码包结构演示。",
            "system_prompt": "请始终保持角色设定。",
            "post_history_instructions": "回答自然、简洁。",
            "alternate_greetings": ["欢迎回来，{{user}}。"],
            "tags": ["示例", "安全样本"],
            "creator": "source-export-example",
            "character_version": "1.0",
            "extensions": {
                "regex_scripts": [
                    {
                        "id": "example-regex",
                        "scriptName": "移除演示标记",
                        "findRegex": "/\\[DEMO\\]/g",
                        "replaceString": "",
                        "placement": [2],
                        "disabled": False,
                    }
                ]
            },
            "character_book": {
                "name": "示例世界书",
                "entries": [
                    {
                        "id": 1,
                        "name": "图书馆",
                        "keys": ["图书馆"],
                        "secondary_keys": [],
                        "content": "这是一座安静的公共图书馆。",
                        "enabled": True,
                        "constant": False,
                        "selective": False,
                        "position": "system",
                        "depth": 4,
                        "priority": 100,
                        "order": 100,
                        "probability": 100,
                        "recursive": False,
                    }
                ],
            },
        },
    }
    write_text("examples/minimal-character-card-v2.json", json.dumps(example, ensure_ascii=False, indent=2))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_manifest() -> None:
    files = sorted(
        path for path in EXPORT_ROOT.rglob("*")
        if path.is_file() and path.name != "MANIFEST.sha256"
    )
    rows = [f"{sha256_file(path)}  {path.relative_to(EXPORT_ROOT).as_posix()}" for path in files]
    write_text("MANIFEST.sha256", "\n".join(rows))


def create_zip() -> None:
    with zipfile.ZipFile(ZIP_PATH, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in sorted(EXPORT_ROOT.rglob("*")):
            if path.is_file():
                archive.write(path, (Path(EXPORT_NAME) / path.relative_to(EXPORT_ROOT)).as_posix())


def main() -> int:
    clean_target()
    copy_sources()
    export_backend_excerpts()
    create_example()
    print(f"prepared={EXPORT_ROOT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
