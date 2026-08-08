"""Prepare isolated runtime data for the SillyTavern browser E2E test.

Secrets are generated at runtime under output/sillytavern-e2e and are never
printed. The directory is test-only and is recreated after a strict path check.
"""

from __future__ import annotations

import json
import os
import secrets
import shutil
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TOOLS_DIR = ROOT / "tools"
DAO_CARD = Path(os.environ.get("HOMER_COMPLEX_CARD_FIXTURE") or r"D:\网站\绘梦物语\《道渊》v5.2.png")
ROLEPLAYHUB_CARD = next(
    (
        path
        for path in (
            Path(os.environ.get("HOMER_ROLEPLAYHUB_FIXTURE") or ""),
            ROOT / "samples" / "rp-hub-bgm-popup-card.png",
            ROOT / "output" / "homer-handoff-20260731" / "samples" / "rp-hub-bgm-popup-card.png",
        )
        if str(path) and path.is_file()
    ),
    ROOT / "samples" / "rp-hub-bgm-popup-card.png",
)
STATE_DIR = (ROOT / "output" / "sillytavern-e2e").resolve()
EXPECTED_STATE_DIR = (ROOT / "output" / "sillytavern-e2e").resolve()

if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))


def private_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    try:
        path.chmod(0o600)
    except OSError:
        pass


def main() -> int:
    if STATE_DIR != EXPECTED_STATE_DIR or STATE_DIR.parent != (ROOT / "output").resolve():
        raise SystemExit(f"unsafe E2E state path: {STATE_DIR}")
    if STATE_DIR.exists():
        shutil.rmtree(STATE_DIR)
    media_dir = STATE_DIR / "data" / "media"
    runtime_dir = STATE_DIR / "runtime"
    artifact_dir = STATE_DIR / "artifacts"
    for path in (media_dir, runtime_dir, artifact_dir):
        path.mkdir(parents=True, exist_ok=True)

    email = "sillytavern-e2e@homer.local"
    password = "E2E-" + secrets.token_urlsafe(24) + "-9A"
    regular_email = "sillytavern-user-e2e@homer.local"
    regular_password = "E2E-" + secrets.token_urlsafe(24) + "-9U"
    auth_secret = secrets.token_urlsafe(48)
    db_path = STATE_DIR / "data" / "state.sqlite3"
    os.environ.update(
        {
            "ADMIN_EMAILS": email,
            "AUTH_TOKEN_SECRET": auth_secret,
            "MEDIA_DIR": str(media_dir),
            "OFFLINE_DEV_MODE": "1",
            "HOMER_OFFLINE_DEV": "1",
            "CONTENT_MODE": "offline",
            "PUBLIC_BASE_URL": "http://127.0.0.1:18081",
            "SILLYTAVERN_PUBLIC_URL": "http://127.0.0.1:18081/module/dialogue",
            "ALLOWED_CORS_ORIGINS": "http://127.0.0.1:18081",
            "USER_BYOK_ENABLED": "0",
        }
    )

    import ai_fengyue_local_server as homer

    homer.MEDIA_DIR = media_dir
    store = homer.Store(db_path)
    store.configure_card_media(media_dir)
    try:
        user = store.upsert_user(email, "惑梦 E2E", password)
        user_id = str(user["id"])
        store.set_user_admin(user_id, True)
        store.set_advanced_creator_override(user_id, True)
        store.add_credit_points(user_id, 500, "free")
        store.import_global_prompt_preset(
            {
                "id": "homer-e2e-global-prompt",
                "name": "惑梦 E2E 官方公开预设",
                "prompts": [
                    {
                        "identifier": "global-visible-on",
                        "name": "官方公开默认开启",
                        "role": "system",
                        "content": "HOMER_GLOBAL_VISIBLE_ON_SENTINEL",
                        "user_toggleable": True,
                    },
                    {
                        "identifier": "global-visible-off",
                        "name": "官方公开默认关闭",
                        "role": "system",
                        "content": "HOMER_GLOBAL_VISIBLE_OFF_SENTINEL",
                        "user_toggleable": True,
                    },
                    {
                        "identifier": "global-visible-marker",
                        "name": "官方公开结构条目",
                        "role": "system",
                        "content": "",
                        "marker": True,
                        "user_toggleable": True,
                    },
                    {
                        "identifier": "global-hidden",
                        "name": "官方后台隐藏条目",
                        "role": "system",
                        "content": "HOMER_GLOBAL_HIDDEN_SENTINEL",
                        "user_toggleable": False,
                    },
                    {
                        "identifier": "chatHistory",
                        "name": "聊天历史",
                        "role": "system",
                        "content": "",
                        "marker": True,
                    },
                ],
                "prompt_order": [{
                    "character_id": 100001,
                    "order": [
                        {"identifier": "global-visible-on", "enabled": True},
                        {"identifier": "global-visible-off", "enabled": False},
                        {"identifier": "global-visible-marker", "enabled": True},
                        {"identifier": "global-hidden", "enabled": True},
                        {"identifier": "chatHistory", "enabled": True},
                    ],
                }],
            },
            "homer-e2e-global-prompt.json",
        )
        generic_card = {
            "spec": "chara_card_v3",
            "spec_version": "3.0",
            "data": {
                "name": "惑梦 E2E 角色",
                "description": "用于本地自动化验收的隔离角色。",
                "personality": "",
                "scenario": "",
                "first_mes": "惑梦 E2E 已就绪。",
                "mes_example": "",
                "system_prompt": "",
                "post_history_instructions": "",
                "alternate_greetings": [],
                "tags": ["E2E"],
                "creator_notes": "验证扩展宿主、卡内脚本和创作工坊往返。",
                "creator": "Homer E2E",
                "character_version": "3.0",
                "character_book": {
                    "name": "E2E 世界书",
                    "entries": [
                        {
                            "id": "e2e-world-1",
                            "name": "E2E 世界书",
                            "content": "E2E_ORIGINAL_WORLD",
                            "constant": True,
                            "enabled": True,
                            "extensions": {"future_world_field": {"preserve": True}},
                        }
                    ],
                },
                "extensions": {
                    "homer_card_prompt_preset": {
                        "enabled": True,
                        "name": "惑梦 E2E 角色卡预设",
                        "prompts": [
                            {
                                "identifier": "card-visible-on",
                                "name": "卡片条目默认开启",
                                "role": "system",
                                "content": "HOMER_CARD_VISIBLE_ON_SENTINEL",
                            },
                            {
                                "identifier": "card-visible-off",
                                "name": "卡片条目默认关闭",
                                "role": "system",
                                "content": "HOMER_CARD_VISIBLE_OFF_SENTINEL",
                            },
                            {
                                "identifier": "card-marker",
                                "name": "卡片结构条目",
                                "role": "system",
                                "content": "",
                                "marker": True,
                            },
                            {
                                "identifier": "card-unlisted",
                                "name": "卡片未进顺序条目",
                                "role": "system",
                                "content": "HOMER_CARD_UNLISTED_SENTINEL",
                            },
                            {
                                "identifier": "chatHistory",
                                "name": "聊天历史",
                                "role": "system",
                                "content": "",
                                "marker": True,
                            },
                        ],
                        "prompt_order": [{
                            "character_id": 100001,
                            "order": [
                                {"identifier": "card-visible-on", "enabled": True},
                                {"identifier": "card-visible-off", "enabled": False},
                                {"identifier": "card-marker", "enabled": True},
                                {"identifier": "chatHistory", "enabled": True},
                            ],
                        }],
                    },
                    "regex_scripts": [
                        {
                            "id": "e2e-regex-1",
                            "scriptName": "E2E Regex",
                            "findRegex": "E2E_ORIGINAL",
                            "replaceString": "E2E_REPLACED",
                            "placement": [1, 2],
                            "disabled": False,
                        }
                    ],
                    "tavern_helper": {
                        "variables": {"preserve": True},
                        "scripts": [
                            {
                                "id": "seed-helper",
                                "name": "Seed Helper",
                                "type": "script",
                                "enabled": True,
                                "info": "Generic card-script execution probe",
                                "button": {"enabled": True, "buttons": []},
                                "data": [],
                                "export_with": {"button": True, "data": True},
                                "content": "window.parent.__cardHelperProbe = 'mounted';",
                            }
                        ],
                    },
                    "future_extension_probe": {"preserve": ["unknown", 3]},
                },
                "assets": [
                    {
                        "type": "x_homer_e2e",
                        "uri": "embeded://future-asset",
                        "name": "future",
                        "ext": "bin",
                    }
                ],
            },
        }
        generic_payload = homer.silly_card_to_app(generic_card)
        generic_payload["is_public"] = True
        row = store.create_user_app(user_id, generic_payload)
        app_id = str(row["id"])
        dao_app_id = ""
        if DAO_CARD.is_file():
            dao_png = DAO_CARD.read_bytes()
            dao_card = homer.parse_png_card_metadata(dao_png)
            dao_payload = homer.silly_card_to_app(dao_card)
            dao_cover_url, _dao_cover_path = homer.store_imported_card_png_cover(dao_png, DAO_CARD.name)
            dao_payload["cover_url"] = dao_cover_url
            dao_payload["is_public"] = True
            dao_row = store.create_user_app(user_id, dao_payload)
            dao_app_id = str(dao_row["id"])
        if not ROLEPLAYHUB_CARD.is_file():
            raise FileNotFoundError(f"RoleplayHub fixture not found: {ROLEPLAYHUB_CARD}")
        roleplayhub_png = ROLEPLAYHUB_CARD.read_bytes()
        roleplayhub_card = homer.parse_png_card_metadata(roleplayhub_png)
        roleplayhub_payload = homer.silly_card_to_app(roleplayhub_card)
        roleplayhub_cover_url, _roleplayhub_cover_path = homer.store_imported_card_png_cover(
            roleplayhub_png,
            ROLEPLAYHUB_CARD.name,
        )
        roleplayhub_payload["cover_url"] = roleplayhub_cover_url
        roleplayhub_payload["is_public"] = True
        roleplayhub_row = store.create_user_app(user_id, roleplayhub_payload)
        roleplayhub_app_id = str(roleplayhub_row["id"])

        regular_user = store.upsert_user(regular_email, "SillyTavern 普通用户", regular_password)
        regular_user_id = str(regular_user["id"])
        store.set_user_admin(regular_user_id, False)
        store.add_credit_points(regular_user_id, 500, "free")
    finally:
        store.conn.close()

    private_write(
        runtime_dir / "credentials.json",
        json.dumps(
            {
                "email": email,
                "password": password,
                "regular_email": regular_email,
                "regular_password": regular_password,
            },
            ensure_ascii=False,
        ),
    )
    private_write(runtime_dir / "auth-token-secret.txt", auth_secret)
    private_write(
        runtime_dir / "config.json",
        json.dumps(
            {
                "state_dir": str(STATE_DIR),
                "db_path": str(db_path),
                "media_dir": str(media_dir),
                "artifact_dir": str(artifact_dir),
                "app_id": app_id,
                "dao_app_id": dao_app_id,
                "roleplayhub_app_id": roleplayhub_app_id,
                "base_url": "http://127.0.0.1:18081",
                "backend_url": "http://127.0.0.1:18080",
                "dialogue_url": "http://127.0.0.1:18081/module/dialogue",
                "dialogue_internal_url": "http://127.0.0.1:18091",
            },
            ensure_ascii=False,
            indent=2,
        ),
    )
    print(f"E2E state prepared at {STATE_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
