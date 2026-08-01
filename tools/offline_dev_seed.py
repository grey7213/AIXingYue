#!/usr/bin/env python3
"""Initialize the isolated Homer offline-development database.

The launcher supplies the administrator password through the process environment.
Nothing secret is embedded in this source file or printed by this command.
"""

from __future__ import annotations

import argparse
import os
import secrets
import sys
from pathlib import Path


TOOLS_DIR = Path(__file__).resolve().parent
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Seed an isolated Homer offline-dev database")
    parser.add_argument("--db", required=True, type=Path, help="SQLite database path")
    return parser.parse_args()


def write_demo_cover(media_dir: Path) -> str:
    cover_dir = media_dir / "cover"
    cover_dir.mkdir(parents=True, exist_ok=True)
    cover = cover_dir / "offline-guide.svg"
    if not cover.exists():
        cover.write_text(
            """<svg xmlns="http://www.w3.org/2000/svg" width="960" height="1280" viewBox="0 0 960 1280">
<defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1"><stop stop-color="#18263f"/><stop offset="1" stop-color="#59406f"/></linearGradient></defs>
<rect width="960" height="1280" fill="url(#g)"/><circle cx="730" cy="220" r="145" fill="#f6dca5" opacity=".9"/>
<path d="M0 900 Q240 720 480 900 T960 900 V1280 H0Z" fill="#121a2e" opacity=".85"/>
<path d="M0 1010 Q240 830 480 1010 T960 1010 V1280 H0Z" fill="#27385a" opacity=".9"/>
<g fill="#fff7db"><circle cx="130" cy="180" r="5"/><circle cx="260" cy="300" r="7"/><circle cx="410" cy="160" r="4"/><circle cx="560" cy="340" r="6"/></g>
<text x="72" y="1080" fill="#fff7db" font-family="sans-serif" font-size="76" font-weight="700">离线调试向导</text>
<text x="76" y="1150" fill="#d7cbe8" font-family="sans-serif" font-size="34">HOMER LOCAL DEVELOPMENT</text>
</svg>""",
            encoding="utf-8",
        )
    return "/media-cache/cover/offline-guide.svg"


def main() -> int:
    args = parse_args()
    admin_email = os.environ.get("HOMER_OFFLINE_ADMIN_EMAIL", "admin@homer.local").strip().lower()
    admin_password = os.environ.get("HOMER_OFFLINE_ADMIN_PASSWORD", "")
    if not admin_email or "@" not in admin_email:
        raise SystemExit("HOMER_OFFLINE_ADMIN_EMAIL is invalid")
    if len(admin_password) < 12:
        raise SystemExit("HOMER_OFFLINE_ADMIN_PASSWORD must contain at least 12 characters")

    os.environ.setdefault("OFFLINE_DEV_MODE", "1")
    os.environ.setdefault("HOMER_OFFLINE_DEV", "1")
    os.environ.setdefault("CONTENT_MODE", "offline")
    os.environ.setdefault("PUBLIC_BASE_URL", "http://127.0.0.1:8080")
    os.environ["ADMIN_EMAILS"] = admin_email
    os.environ.setdefault("AUTH_TOKEN_SECRET", secrets.token_urlsafe(48))

    import ai_fengyue_local_server as server

    db_path = args.db.resolve()
    media_dir = Path(os.environ.get("MEDIA_DIR") or (db_path.parent / "media")).resolve()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    media_dir.mkdir(parents=True, exist_ok=True)

    store = server.Store(db_path)
    try:
        store.configure_card_media(media_dir)
        user = store.upsert_user(admin_email, "离线调试管理员", admin_password)
        store.set_user_admin(user["id"], True)
        store.set_advanced_creator_override(user["id"], True)
        with store.lock:
            store.conn.execute(
                """
                update users
                set points=999999, free_points=999999, paid_points=0, reward_points=0, updated_at=?
                where id=?
                """,
                (server.now_ms(), user["id"]),
            )
            store.conn.commit()

        cover_url = write_demo_cover(media_dir)
        app = store.conn.execute(
            "select * from local_apps where owner_user_id=? and name=? order by created_at limit 1",
            (user["id"], "离线调试向导"),
        ).fetchone()
        if app is None:
            app = store.create_user_app(
                user["id"],
                {
                    "name": "离线调试向导",
                    "summary": "用于验证聊天、世界书、正则、创作中心和本地素材的示例角色。",
                    "description": "你是惑梦本地调试向导。回答简洁、友好，并明确说明当前回复来自完全离线的本地模拟逻辑。",
                    "opening_statement": "欢迎来到惑梦离线调试环境。这里不会访问互联网，你可以直接测试对话、角色卡创作、素材上传与管理员功能。",
                    "pre_prompt": "保持中文回答；不要声称访问了互联网；遇到需要联网的内容时说明这是离线调试环境。",
                    "tags": ["离线调试", "示例角色", "本地"],
                    "suggested_questions": ["介绍一下离线模式", "带我测试创作中心", "世界书和正则在哪里编辑"],
                    "cover_url": cover_url,
                    "is_public": True,
                    "status": "published",
                    "language": "zh-Hans",
                    "world_info": [
                        {
                            "id": "offline-world-1",
                            "name": "离线调试环境",
                            "keys": ["离线", "本地调试", "网络"],
                            "secondary_keys": [],
                            "content": "当前为完全离线的本地调试环境，所有数据和素材只保存在 output/offline-dev 中。",
                            "enabled": True,
                            "constant": True,
                            "position": "system",
                            "priority": 100,
                            "order": 1,
                        }
                    ],
                    "regex_scripts": [
                        {
                            "id": "offline-regex-1",
                            "name": "离线标记演示",
                            "find": r"\[离线\]",
                            "replace": "【离线调试】",
                            "flags": "g",
                            "enabled": True,
                            "order": 1,
                        }
                    ],
                    "quick_replies": [
                        {"id": "offline-quick-1", "label": "测试离线回复", "message": "[离线] 请回复一段测试文本。", "enabled": True, "order": 1}
                    ],
                },
            )

        conv_id = f"offline-welcome-{user['id']}"
        conversation = store.upsert_conversation(
            conv_id,
            user["id"],
            app["id"],
            app_name=app["name"],
            app_icon=app["cover_url"],
            title="离线调试欢迎会话",
        )
        existing = store.conn.execute(
            "select 1 from messages where conversation_id=? and user_id=? limit 1",
            (conv_id, user["id"]),
        ).fetchone()
        if not existing:
            store.append_message(
                conversation["id"],
                user["id"],
                "assistant",
                "欢迎进入惑梦离线调试环境。所有 API、数据库、图片和音频测试都在本机完成。",
            )

        result = store.conn.execute("pragma quick_check").fetchone()
        if not result or str(result[0]).lower() != "ok":
            raise RuntimeError("SQLite quick_check failed")
    finally:
        store.conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
