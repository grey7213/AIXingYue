#!/usr/bin/env python3
"""Focused regression checks for the Homer dialogue prompt/empty-message recovery."""

from __future__ import annotations

import argparse
import importlib.util
import json
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load_server(path: Path):
    spec = importlib.util.spec_from_file_location("homer_chat_recovery_server", path)
    if not spec or not spec.loader:
        raise RuntimeError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FakeStore:
    def __init__(self, protocol: str):
        self.protocol = protocol

    def resolve_local_app_id(self, app_id: str) -> str:
        return str(app_id)

    def get_user_by_id(self, user_id: str) -> dict:
        return {"id": user_id, "name": "测试用户"}

    def versioned_app_for_new_conversation(self, app_id: str, user_id: str):
        return ({
            "id": app_id,
            "name": "测试角色",
            "source": "admin",
            "is_public": 1,
            "status": "published",
            "extra_settings": "{}",
        }, None)

    def get_sillytavern_runtime_state(self, user_id: str, app_id: str, conversation_id: str) -> dict:
        return {}

    def public_model_selection(self, model: object) -> str:
        return str(model or "")

    def effective_llm_settings(self, app: dict, user_id: str = "") -> dict:
        return {
            "enabled": True,
            "protocol": self.protocol,
            "model": "test-model",
            "base_url": "https://provider.invalid/v1",
            "api_key": "not-a-real-key",
            "pricing": {"mode": "per_request", "input_price": 25, "output_price": 25},
        }

    def get_persona(self, user_id: str) -> dict:
        return {"name": "测试用户"}


def fake_build_request(app, content, messages, settings, persona, context):
    protocol = str(settings.get("protocol") or "openai")
    if protocol == "anthropic":
        return {
            "enabled": True,
            "protocol": "anthropic",
            "endpoint": "https://provider.invalid/v1/messages",
            "headers": {"x-api-key": "not-a-real-key"},
            "model": "test-model",
            "payload": {
                "model": "test-model",
                "system": "AUTHORITATIVE_HEAD\n" + ("A" * 12_000) + "\nAUTHORITATIVE_TAIL",
                "messages": [{"role": "user", "content": content}],
                "max_tokens": 300,
            },
        }
    return {
        "enabled": True,
        "protocol": "openai",
        "endpoint": "https://provider.invalid/v1/chat/completions",
        "headers": {"Authorization": "Bearer not-a-real-key"},
        "model": "test-model",
        "payload": {
            "model": "test-model",
            "messages": [
                {"role": "system", "content": "CORE_HEAD\n" + ("A" * 7_800) + "\nCORE_TAIL"},
                {"role": "user", "content": content},
                {"role": "system", "content": "POST_HEAD\n" + ("B" * 3_100) + "\nPOST_TAIL"},
            ],
            "max_tokens": 300,
        },
    }


def provider_text(request_info: dict) -> str:
    payload = request_info["payload"]
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def test_prompt_merge(server) -> None:
    original_builder = server.build_user_llm_request
    original_permission = server.user_can_play_app
    server.build_user_llm_request = fake_build_request
    server.user_can_play_app = lambda app, user_id: True
    try:
        raw_messages = [
            {"role": "system", "content": "RAW_SYSTEM_SECRET\n" + ("R" * 37_000)},
            {"role": "assistant", "content": "RECENT_ASSISTANT\n" + ("C" * 2_400)},
            {"role": "user", "content": "RECENT_USER"},
        ]
        claims = {"user_id": "user-1", "app_id": "app-1", "conversation_id": ""}

        openai = server.prepare_sillytavern_bridge_generation(
            FakeStore("openai"),
            claims,
            {"model": "test-model", "messages": raw_messages, "stream": True},
        )
        openai_text = provider_text(openai)
        assert "RAW_SYSTEM_SECRET" not in openai_text
        assert "RECENT_ASSISTANT" in openai_text and "RECENT_USER" in openai_text
        assert "CORE_HEAD" in openai_text and "CORE_TAIL" in openai_text
        assert "POST_HEAD" in openai_text and "POST_TAIL" in openai_text
        assert openai["prompt_stats"]["raw_system_dropped"] == 1
        assert openai["prompt_stats"]["provider_system_chars"] <= server.SILLYTAVERN_BRIDGE_MAX_SYSTEM_CHARS
        assert openai["prompt_stats"]["provider_input_chars"] <= server.SILLYTAVERN_BRIDGE_MAX_INPUT_CHARS
        openai_dialogue = [
            item for item in openai["payload"]["messages"] if item.get("role") in {"user", "assistant"}
        ]
        assert openai_dialogue[-1]["role"] == "user"

        anthropic = server.prepare_sillytavern_bridge_generation(
            FakeStore("anthropic"),
            claims,
            {"model": "test-model", "messages": raw_messages, "stream": True},
        )
        anthropic_text = provider_text(anthropic)
        assert "RAW_SYSTEM_SECRET" not in anthropic_text
        assert "AUTHORITATIVE_HEAD" in anthropic_text and "AUTHORITATIVE_TAIL" in anthropic_text
        assert anthropic["prompt_stats"]["provider_system_chars"] <= server.SILLYTAVERN_BRIDGE_MAX_SYSTEM_CHARS
        assert anthropic["prompt_stats"]["provider_input_chars"] <= server.SILLYTAVERN_BRIDGE_MAX_INPUT_CHARS
        assert anthropic["payload"]["messages"][-1]["role"] == "user"

        long_history = [{"role": "system", "content": "RAW_SYSTEM_SECRET"}]
        for index in range(12):
            long_history.append({
                "role": "assistant" if index % 2 else "user",
                "content": f"HISTORY_{index}_" + (str(index) * 1_000),
            })
        long_history.append({"role": "user", "content": "LATEST_USER_SENTINEL"})
        budgeted = server.prepare_sillytavern_bridge_generation(
            FakeStore("openai"),
            claims,
            {"model": "test-model", "messages": long_history, "stream": True},
        )
        budgeted_text = provider_text(budgeted)
        assert "HISTORY_0_" not in budgeted_text
        assert "LATEST_USER_SENTINEL" in budgeted_text
        assert budgeted["prompt_stats"]["history_dropped"] > 0
        assert budgeted["prompt_stats"]["provider_input_chars"] <= server.SILLYTAVERN_BRIDGE_MAX_INPUT_CHARS
    finally:
        server.build_user_llm_request = original_builder
        server.user_can_play_app = original_permission


def test_empty_snapshot_guard(server) -> None:
    with tempfile.TemporaryDirectory(prefix="homer-chat-recovery-") as temp_dir:
        store = server.Store(Path(temp_dir) / "state.sqlite3")
        try:
            failed = store.sync_sillytavern_chat(
                "conv-failed",
                "user-1",
                "app-1",
                [
                    {"role": "assistant", "mes": "OPENING"},
                    {"role": "user", "mes": "FAILED_USER"},
                    {"role": "assistant", "mes": ""},
                ],
            )
            assert [(item["role"], item["content"]) for item in failed["messages"]] == [
                ("assistant", "OPENING"),
            ]

            succeeded = store.sync_sillytavern_chat(
                "conv-success",
                "user-1",
                "app-1",
                [
                    {"role": "assistant", "mes": "OPENING"},
                    {"role": "user", "mes": "SUCCESS_USER"},
                    {"role": "assistant", "mes": "SUCCESS_ASSISTANT"},
                ],
            )
            assert [(item["role"], item["content"]) for item in succeeded["messages"]][-2:] == [
                ("user", "SUCCESS_USER"),
                ("assistant", "SUCCESS_ASSISTANT"),
            ]

            swipe = store.sync_sillytavern_chat(
                "conv-swipe",
                "user-1",
                "app-1",
                [
                    {"role": "user", "mes": "SWIPE_USER"},
                    {"role": "assistant", "mes": "", "swipes": ["VALID_OLD_SWIPE", ""], "swipe_id": 1},
                ],
            )
            assert [(item["role"], item["content"]) for item in swipe["messages"]] == [
                ("user", "SWIPE_USER"),
                ("assistant", "VALID_OLD_SWIPE"),
            ]
        finally:
            store.conn.close()


def test_bridge_contract(bridge_path: Path) -> None:
    source = bridge_path.read_text(encoding="utf-8")
    for sentinel in (
        "generationSnapshot = captureGenerationSnapshot(type)",
        "function isEmptyGeneratedAssistant",
        "async function recoverFailedGeneration",
        "lastSyncSignature = ''",
        "模型未返回有效回复，本轮消息已撤回",
        "await syncCloudChat()",
    ):
        assert sentinel in source, sentinel
    for unsupported in ("lastApiError", "showApiErrorBar", "hideApiErrorBar"):
        assert unsupported not in source, unsupported


def test_memory_books_first_run_contract(runtime_root: Path) -> None:
    extension = runtime_root / "public" / "scripts" / "extensions" / "third-party" / "SillyTavern-MemoryBooks"
    helper = (extension / "userFiles.js").read_text(encoding="utf-8")
    assert "export async function userFileExists" in helper
    assert "/api/files/verify" in helper
    for name in (
        "summaryPromptManager.js",
        "arcAnalysisPromptManager.js",
        "sidePromptsManager.js",
        "contextSettingsManager.js",
    ):
        source = (extension / name).read_text(encoding="utf-8")
        assert "userFileExists" in source, name


def test_status_abort_contract(runtime_root: Path) -> None:
    source = (runtime_root / "public" / "scripts" / "openai.js").read_text(encoding="utf-8")
    assert "import { AbortReason } from './util/AbortReason.js';" in source
    catch_start = source.index("    } catch (error) {", source.index("async function getStatusOpen()"))
    catch_end = source.index("\n    }\n", catch_start) + len("\n    }\n")
    catch_block = source[catch_start:catch_end]
    assert "if (error instanceof AbortReason)" in catch_block
    assert "console.debug('Status check aborted.'" in catch_block
    assert catch_block.index("if (error instanceof AbortReason)") < catch_block.index("console.error(error)")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--server",
        type=Path,
        default=ROOT / "tools" / "ai_fengyue_local_server.py",
    )
    parser.add_argument(
        "--bridge",
        type=Path,
        default=ROOT / "sillytavern-runtime" / "public" / "scripts" / "extensions" / "homer-bridge" / "index.js",
    )
    args = parser.parse_args()
    server = load_server(args.server.resolve())
    test_prompt_merge(server)
    test_empty_snapshot_guard(server)
    test_bridge_contract(args.bridge.resolve())
    test_memory_books_first_run_contract(ROOT / "sillytavern-runtime")
    test_status_abort_contract(ROOT / "sillytavern-runtime")
    print(
        "PASS Homer chat prompt budget, authoritative merge, empty snapshot guard, "
        "bridge recovery, MemoryBooks first-run, and status-abort contracts"
    )


if __name__ == "__main__":
    main()
