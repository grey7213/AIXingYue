"""Conversation preset/database lifecycle self-test.

Uses an isolated temporary SQLite database. It never reads or mutates the
normal Homer runtime state.
"""

from __future__ import annotations

import base64
import io
import json
import tempfile
import zipfile
from pathlib import Path

import ai_fengyue_local_server as homer


def make_regex_package() -> str:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(
            "visible.json",
            json.dumps(
                {
                    "id": "visible-probe",
                    "scriptName": "Visible Probe",
                    "findRegex": "VISIBLE_PROBE",
                    "replaceString": "VISIBLE_OK",
                    "placement": [2],
                    "disabled": False,
                }
            ),
        )
    return base64.b64encode(buffer.getvalue()).decode("ascii")


def seed(store: homer.Store) -> tuple[str, str]:
    user = store.upsert_user("database@example.test", "Database User", "password")
    app = store.create_admin_app({"name": "Database Character", "summary": "database test"})
    return str(user["id"]), str(app["id"])


def test_profile_and_database(store: homer.Store, user_id: str, app_id: str) -> str:
    legacy_id = "legacy-conversation"
    store.upsert_conversation(legacy_id, user_id, app_id, app_name="Legacy")
    legacy = store.get_conversation_runtime_profile(legacy_id, user_id, include_choices=True)
    assert legacy and legacy["database_enabled"] is False
    assert legacy["database"]["table_count"] == 8

    conv_id = "database-conversation"
    store.upsert_conversation(conv_id, user_id, app_id, app_name="Database")
    created = store.ensure_conversation_runtime_profile(conv_id, user_id, database_enabled=True)
    assert created and created["database_enabled"] is True

    prompt = store.import_global_prompt_preset(
        {
            "name": "Conversation Prompt",
            "prompts": [{"identifier": "main", "name": "Main", "role": "system", "content": "PROMPT_PROBE"}],
            "prompt_order": [{"character_id": 100001, "order": [{"identifier": "main", "enabled": True}]}],
        },
        "conversation-prompt.json",
    )
    regex = store.import_global_regex_preset(make_regex_package(), "visible.zip", "Conversation Regex")
    profile = store.save_conversation_runtime_profile(
        conv_id,
        user_id,
        {
            "prompt_preset_id": prompt["id"],
            "regex_preset_id": regex["id"],
            "status_mode": "mvu",
            "strict_output": True,
            "update_frequency": 2,
        },
    )
    assert profile and profile["effective"]["prompt_preset_id"] == prompt["id"]
    assert profile["effective"]["regex_preset_id"] == regex["id"]
    assert profile["status_mode"] == "mvu"
    assert profile["strict_output"] is True
    assert profile["update_frequency"] == 2

    try:
        store.save_conversation_runtime_profile(conv_id, user_id, {"prompt_preset_id": "missing"})
    except ValueError as exc:
        assert "not found" in str(exc)
    else:
        raise AssertionError("missing preset id should be rejected")

    result = store.apply_conversation_database_updates(
        conv_id,
        user_id,
        [
            {
                "action": "upsert",
                "table": "inventory",
                "row_key": "spirit-stone",
                "row": {
                    "item_name": "灵石",
                    "quantity": 12,
                    "description": "修炼资源",
                    "unknown_field": "must be removed",
                },
            },
            {"action": "upsert", "table": "unknown_table", "row": {"name": "skip"}},
        ],
        updated_by="selftest",
    )
    assert result["applied"] == 1
    assert result["skipped"] == 1
    database = store.get_conversation_database(conv_id, user_id, include_rows=True)
    inventory = next(item for item in database["tables"] if item["key"] == "inventory")
    assert inventory["row_count"] == 1
    assert inventory["rows"][0]["data"]["item_name"] == "灵石"
    assert inventory["rows"][0]["data"]["quantity"] == 12
    assert "unknown_field" not in inventory["rows"][0]["data"]

    prompt_text = store.conversation_database_prompt(
        conv_id,
        user_id,
        history=[{"role": "assistant", "content": "first reply"}],
    )
    assert "结构化剧情数据库" in prompt_text
    assert "homer_database_update" in prompt_text
    assert "灵石" in prompt_text
    print("PASS legacy migration/new defaults/profile selection/database CRUD/prompt injection")
    return conv_id


def test_reply_update_and_stream_buffering(store: homer.Store, user_id: str, app_id: str, conv_id: str) -> None:
    app = dict(store.get_local_app(app_id))
    context = store.chat_context(user_id, app_id, conv_id, "继续", [])
    reply = (
        "VISIBLE_PROBE\n"
        '<homer_database_update>{"operations":[{"action":"upsert","table":"quests_events",'
        '"row_key":"trial","row":{"quest_name":"试炼","status":"进行中"}}]}</homer_database_update>'
    )
    rendered = homer.process_model_reply(
        app,
        reply,
        char_name="Database Character",
        user_name="User",
        template_context=context,
        global_regex_preset=context["conversation_settings"]["regex_preset"],
    )
    assert rendered == "VISIBLE_OK"
    assert "homer_database_update" not in rendered
    database = store.get_conversation_database(conv_id, user_id, include_rows=True)
    quests = next(item for item in database["tables"] if item["key"] == "quests_events")
    assert quests["row_count"] == 1
    assert quests["rows"][0]["data"]["quest_name"] == "试炼"
    assert homer.stream_reply_requires_buffering(
        app,
        context["conversation_settings"]["regex_preset"],
        context["conversation_settings"],
    )
    print("PASS hidden reply update/global Regex/rendering/stream buffering")


def test_copy_delete_and_ownership(store: homer.Store, user_id: str, conv_id: str) -> None:
    other = store.upsert_user("other@example.test", "Other User", "password")
    other_id = str(other["id"])
    assert store.get_conversation_runtime_profile(conv_id, other_id) is None
    assert store.get_conversation_database(conv_id, other_id) is None

    copied = store.copy_conversation(conv_id, user_id)
    assert copied and copied["id"] != conv_id
    copied_id = str(copied["id"])
    copied_profile = store.get_conversation_runtime_profile(copied_id, user_id)
    copied_database = store.get_conversation_database(copied_id, user_id, include_rows=True)
    assert copied_profile and copied_profile["database_enabled"] is True
    assert copied_database and copied_database["row_count"] == 2
    assert store.delete_conversation(copied_id, user_id) is True
    with store.lock:
        for table in (
            "conversation_runtime_profiles",
            "conversation_database_tables",
            "conversation_database_rows",
        ):
            count = store.conn.execute(
                f"select count(*) from {table} where conversation_id=? and user_id=?",
                (copied_id, user_id),
            ).fetchone()[0]
            assert count == 0
    print("PASS ownership/copy/delete lifecycle")


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="homer-conversation-db-selftest-") as temp_dir:
        store = homer.Store(Path(temp_dir) / "state.sqlite3")
        try:
            user_id, app_id = seed(store)
            conv_id = test_profile_and_database(store, user_id, app_id)
            test_reply_update_and_stream_buffering(store, user_id, app_id, conv_id)
            test_copy_delete_and_ownership(store, user_id, conv_id)
        finally:
            store.conn.close()
    print("\nALL CONVERSATION DATABASE TESTS PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
