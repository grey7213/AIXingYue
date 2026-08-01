"""SillyTavern extension host and per-conversation runtime self-test.

Uses an isolated temporary SQLite database and media directory. It never reads
or mutates the normal Homer runtime state.
"""

from __future__ import annotations

import base64
import io
import json
import os
import tempfile
import zipfile
from pathlib import Path

import ai_fengyue_local_server as homer
import offline_dev_proxy

ROOT = Path(__file__).resolve().parents[1]


def resolve_roleplayhub_fixture() -> Path:
    candidates = [
        Path(os.environ.get("HOMER_ROLEPLAYHUB_FIXTURE") or ""),
        ROOT / "samples" / "rp-hub-bgm-popup-card.png",
        ROOT / "output" / "homer-handoff-20260731" / "samples" / "rp-hub-bgm-popup-card.png",
    ]
    return next((path for path in candidates if str(path) and path.is_file()), candidates[1])


ROLEPLAYHUB_CARD = resolve_roleplayhub_fixture()


def test_internal_dialogue_mount_rewrite() -> None:
    source = b'''<base href="/"><script type="module" src="script.js"></script>'''
    html = offline_dev_proxy.rewrite_dialogue_payload(source, "text/html; charset=utf-8")
    assert b'<base href="/module/dialogue/">' in html
    assert b'src="script.js"' in html

    javascript = b'''import x from '/script.js';\nfetch('/api/characters/all');\nfetch('/version');\nfetch(`/characters/${name}`);\nconst site='/assets/img/logo.png';\nconst inlineMap='/*# sourceMappingURL=data:application/json;base64,probe */';\n//# sourceMappingURL=script.js.map\n'''
    rewritten = offline_dev_proxy.rewrite_dialogue_payload(
        javascript,
        "text/javascript; charset=utf-8",
    )
    assert b"'/module/dialogue/script.js'" in rewritten
    assert b"'/module/dialogue/api/characters/all'" in rewritten
    assert b"'/module/dialogue/version'" in rewritten
    assert b"`/module/dialogue/characters/${name}`" in rewritten
    assert b"'/assets/img/logo.png'" in rewritten
    assert b"sourceMappingURL=data:application/json;base64,probe" in rewritten
    assert b"sourceMappingURL=script.js.map" not in rewritten
    assert offline_dev_proxy.rewrite_dialogue_payload(b"\x89PNG\r\n", "image/png") == b"\x89PNG\r\n"
    assert offline_dev_proxy.DIALOGUE_STATIC_CACHE_CONTROL == "private, max-age=3600, stale-while-revalidate=86400"
    assert "/scripts" in offline_dev_proxy.DIALOGUE_CACHEABLE_PREFIXES
    assert "/api" not in offline_dev_proxy.DIALOGUE_CACHEABLE_PREFIXES
    style_policy = next(
        item.strip()
        for item in offline_dev_proxy.OFFLINE_CSP.split(";")
        if item.strip().startswith("style-src ")
    )
    assert "https://testingcf.jsdelivr.net" in style_policy
    print("PASS neutral internal dialogue mount/root-path rewrite")


def test_card_stage_protocol_v2() -> None:
    normalized = homer.normalize_card_experience(
        {
            "stage": {
                "enabled": True,
                "layout": "split",
                "chat_width": 58,
                "background_asset_id": "asset-bg",
                "portrait_asset_id": "asset-portrait",
                "accent_color": "#d7b878",
                "input_style": "floating",
            },
            "structured_components": {
                "enabled": True,
                "map": True,
                "inventory": False,
            },
        },
        {"asset-bg": "background", "asset-portrait": "portrait"},
        set(),
    )
    assert normalized["version"] == 2
    assert normalized["stage"]["layout"] == "split"
    assert normalized["stage"]["background_asset_id"] == "asset-bg"
    assert normalized["stage"]["portrait_asset_id"] == "asset-portrait"
    assert normalized["stage"]["input_style"] == "floating"
    assert normalized["structured_components"]["map"] is True
    assert normalized["structured_components"]["inventory"] is False
    stage_source = (
        ROOT
        / "sillytavern-runtime"
        / "public"
        / "scripts"
        / "extensions"
        / "homer-bridge"
        / "card-stage.js"
    ).read_text(encoding="utf-8")
    assert "homer-ui-json-v1" in stage_source
    assert "MAX_COMPONENT_BYTES" in stage_source
    assert "character_book?.entries" in stage_source
    assert "content: ''" in stage_source
    assert "道渊" not in stage_source and "黎明之契" not in stage_source
    print("PASS generic card stage v2/structured component/privacy contract")


def make_extension_zip(*, enclosing_dir: bool = True) -> tuple[str, bytes]:
    prefix = "sample-extension/" if enclosing_dir else ""
    manifest = {
        "display_name": "Runtime Probe",
        "author": "Homer self-test",
        "version": "1.2.3",
        "loading_order": 7,
        "js": "index.js",
        "css": "style.css",
        "hooks": {"activate": "activate"},
    }
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(prefix + "manifest.json", json.dumps(manifest))
        archive.writestr(
            prefix + "index.js",
            "export function activate(){ window.__stRuntimeProbe = 'active'; }\n",
        )
        archive.writestr(prefix + "style.css", ":root{--st-runtime-probe:1}\n")
    blob = buffer.getvalue()
    return "data:application/zip;base64," + base64.b64encode(blob).decode("ascii"), blob


def test_extension_registry(store: homer.Store) -> None:
    data_url, blob = make_extension_zip()
    parsed = homer.parse_sillytavern_extension_package(data_url, "runtime-probe.zip")
    assert parsed["root_prefix"] == "sample-extension/"
    assert parsed["package_size"] == len(blob)
    assert parsed["package_paths"] == ["index.js", "manifest.json", "style.css"]

    imported = store.import_sillytavern_extension(data_url, "runtime-probe.zip")
    assert imported["display_name"] == "Runtime Probe"
    assert imported["enabled"] is False
    extension_id = imported["id"]

    enabled = store.set_sillytavern_extension_enabled(extension_id, True)
    assert enabled and enabled["enabled"] is True
    registry = store.enabled_sillytavern_extensions()
    assert registry["protocol"] == "dialogue-extension-v1"
    assert registry["total"] == 1
    item = registry["list"][0]
    assert item["js_url"].endswith(f"/{extension_id}/assets/index.js")
    assert item["css_url"].endswith(f"/{extension_id}/assets/style.css")
    js_bytes, js_type = store.read_sillytavern_extension_file(extension_id, "index.js")
    assert b"__stRuntimeProbe" in js_bytes
    assert js_type == "text/javascript; charset=utf-8"

    assert store.read_sillytavern_extension_file(extension_id, "../manifest.json") is None

    assert store.delete_sillytavern_extension(extension_id) is True
    assert store.enabled_sillytavern_extensions()["total"] == 0
    print("PASS extension registry/import/assets/toggle/delete")


def test_runtime_state_and_generation(store: homer.Store) -> None:
    user = store.upsert_user("runtime@example.test", "Runtime User", "password")
    app_row = store.create_admin_app(
        {
            "name": "Runtime Character",
            "summary": "runtime test",
            "world_info": [
                {
                    "id": "world-1",
                    "name": "Original",
                    "content": "ORIGINAL_WORLD_CONTENT",
                    "constant": True,
                    "enabled": True,
                }
            ],
            "regex_scripts": [
                {
                    "id": "regex-1",
                    "name": "Probe Regex",
                    "find": "ORIGINAL",
                    "replace": "REPLACED",
                    "flags": "g",
                    "enabled": True,
                }
            ],
        }
    )
    app_id = str(app_row["id"])
    user_id = str(user["id"])
    store.save_sillytavern_runtime_state(
        user_id,
        app_id,
        "",
        {
            "extension_settings": {"runtime-probe": {"enabled": True, "mode": "test"}},
            "worldbook_overrides": {
                "world-1": {"content": "OVERRIDDEN_WORLD_CONTENT", "enabled": True}
            },
            "regex_overrides": {"regex-1": {"disabled": True}},
            "script_trees": {"global": [], "character": [{"id": "script-1", "enabled": True}]},
        },
    )
    store.save_sillytavern_runtime_state(
        user_id,
        app_id,
        "conversation-1",
        {
            "extension_settings": {
                "runtime-probe": {
                    "enabled": True,
                    "mode": "conversation",
                    "future_nested_field": {"items": [1, 2, 3]},
                },
                "future-extension": {"opaque": {"preserve": True}},
            },
            "variables": {"route": "conversation"},
            "mvu_state": {"stat_data": {"hp": 99}},
        },
    )
    state = store.get_sillytavern_runtime_state(
        user_id,
        app_id,
        "conversation-1",
    )
    assert state["extension_settings"]["runtime-probe"]["mode"] == "conversation"
    assert state["extension_settings"]["runtime-probe"]["future_nested_field"]["items"] == [1, 2, 3]
    assert state["extension_settings"]["future-extension"]["opaque"]["preserve"] is True
    assert state["variables"]["route"] == "conversation"
    assert state["mvu_state"]["stat_data"]["hp"] == 99

    isolated = store.get_sillytavern_runtime_state(user_id, app_id, "conversation-2")
    assert isolated["extension_settings"]["runtime-probe"]["mode"] == "test"
    assert "future-extension" not in isolated["extension_settings"]

    effective = homer.apply_sillytavern_runtime_state(dict(app_row), state)
    extras = homer.app_extras(effective)
    world_entry = next(item for item in extras["world_info"] if item.get("id") == "world-1")
    assert world_entry["content"] == "OVERRIDDEN_WORLD_CONTENT"
    assert homer.enabled_regex_scripts(effective) == []
    print("PASS scoped runtime persistence/worldbook/Regex generation consumption")


def test_original_runtime_extension_settings_bridge_contract() -> None:
    bridge = (
        ROOT
        / "sillytavern-runtime"
        / "public"
        / "scripts"
        / "extensions"
        / "homer-bridge"
        / "index.js"
    ).read_text(encoding="utf-8")
    core = (ROOT / "sillytavern-runtime" / "public" / "script.js").read_text(encoding="utf-8")
    assert "saveConversationExtensionSettings" in bridge
    assert "extension_settings: snapshot.value" in bridge
    assert "const restoredExtensionSettings = cloneJsonObject(extensionSettingsBaseline || {})" in bridge
    assert "synchronizeJsonContainer(restoredExtensionSettings, savedExtensionSettings)" in bridge
    assert "replaceExtensionSettings(conversationExtensionSettings)" in bridge
    assert "function isPlainRuntimeTree" in bridge
    assert "preserveUnsafeNamespaces: true" in bridge
    assert "A conversation snapshot is an overlay" in bridge
    assert "!isPlainRuntimeTree(current) || !isPlainRuntimeTree(value)" in bridge
    assert "extensionSettingsReplayInProgress" in bridge
    assert "function installEmbeddedDocumentLookupBridge" in bridge
    assert "hostDocument.querySelectorAll(selector)" in bridge
    assert "await eventSource.emit(event_types.SETTINGS_LOADED)" in bridge
    assert "__homerNativeExtensionSettingsSnapshot" in bridge
    assert "__homerNativeExtensionSettingsSnapshot(extension_settings)" in core
    print("PASS original runtime awaitable conversation extension-settings bridge contract")


def test_product_owned_dialogue_surface_contract() -> None:
    index_html = (
        ROOT / "sillytavern-runtime" / "public" / "index.html"
    ).read_text(encoding="utf-8")
    bridge = (
        ROOT
        / "sillytavern-runtime"
        / "public"
        / "scripts"
        / "extensions"
        / "homer-bridge"
        / "index.js"
    ).read_text(encoding="utf-8")
    bridge_style = (
        ROOT
        / "sillytavern-runtime"
        / "public"
        / "scripts"
        / "extensions"
        / "homer-bridge"
        / "style.css"
    ).read_text(encoding="utf-8")
    middleware = (
        ROOT / "sillytavern-runtime" / "src" / "middleware" / "homerBridge.js"
    ).read_text(encoding="utf-8")

    assert "homer-embedded-runtime" in index_html
    assert "homer-runtime-pending" in index_html
    assert "inheritedBrandPattern" not in index_html
    assert "installProductSurfaceBoundary" in bridge
    assert "homer-internal-parking" in bridge
    assert "TECHNICAL_NOTICE_PATTERN" in bridge
    assert "会话能力已连接" in bridge
    assert "原版酒馆已连接" not in bridge
    assert "body.homer-runtime #toast-container" in bridge_style
    assert "display: none !important;" in bridge_style
    assert "isInternalModuleRequest" in middleware
    assert "websiteUrl('/app/chat.html')" in middleware
    print("PASS product-owned dialogue surface/parking/notice/direct-entry contract")


def test_card_script_roundtrip() -> None:
    script = {
        "id": "card-helper-1",
        "name": "Card Helper",
        "type": "script",
        "enabled": True,
        "content": "window.parent.__cardHelperRoundtrip = true;",
    }
    source = {
        "spec": "chara_card_v2",
        "spec_version": "2.0",
        "data": {
            "name": "Roundtrip Card",
            "description": "card extension roundtrip",
            "extensions": {
                "tavern_helper": {
                    "scripts": [script],
                    "variables": {"keep": True},
                },
                "third_party_metadata": {"keep": "yes"},
            },
        },
    }
    converted = homer.silly_card_to_app(source)
    extras = homer.normalize_user_app_extras(converted)
    assert extras["extensions"]["tavern_helper"]["scripts"][0]["content"] == script["content"]
    exported = homer.app_to_silly_card({**converted, "extensions": extras["extensions"]})
    exported_extensions = exported["data"]["extensions"]
    assert exported_extensions["tavern_helper"]["scripts"][0]["id"] == "card-helper-1"
    assert exported_extensions["tavern_helper"]["variables"]["keep"] is True
    assert exported_extensions["third_party_metadata"]["keep"] == "yes"
    print("PASS SillyTavern card extensions.tavern_helper.scripts roundtrip")


def test_imported_card_workshop_merge() -> None:
    source = {
        "spec": "chara_card_v2",
        "spec_version": "2.0",
        "future_top_level": {"preserve": True},
        "data": {
            "name": "Before",
            "description": "before description",
            "first_mes": "before opening",
            "future_card_field": {"preserve": "yes"},
            "character_book": {
                "name": "Before lore",
                "future_book_field": "opaque",
                "entries": [
                    {
                        "id": "old-world",
                        "content": "OLD_WORLD",
                        "future_entry_field": {"preserve": "entry"},
                        "extensions": {
                            "future_world_field": {"preserve": True},
                            "homer_media_bindings": [{"asset_id": "old-media"}],
                        },
                    },
                    {
                        "id": "delete-world",
                        "content": "DELETE_ME",
                        "future_entry_field": {"preserve": "deleted-only"},
                    },
                ],
            },
            "extensions": {
                "regex_scripts": [
                    {
                        "id": "old-regex",
                        "find": "OLD",
                        "replace": "old",
                        "enabled": True,
                    }
                ],
                "tavern_helper": {
                    "scripts": [
                        {
                            "id": "hidden-helper",
                            "name": "Hidden Helper",
                            "enabled": True,
                            "content": "window.__hiddenHelper = true;",
                        }
                    ],
                    "variables": {"preserve": True},
                },
                "third_party_metadata": {"preserve": "yes"},
            },
        },
    }
    converted = homer.silly_card_to_app(source)
    extras = homer.normalize_user_app_extras(converted)
    converted_world = next(
        item for item in extras["world_info"] if item.get("id") == "old-world"
    )
    assert converted_world["extensions"]["future_world_field"]["preserve"] is True
    directly_exported = homer.app_to_silly_card({**converted, "world_info": extras["world_info"]})
    direct_entry = directly_exported["data"]["character_book"]["entries"][0]
    assert direct_entry["extensions"]["future_world_field"]["preserve"] is True
    row = {"extra_settings": json.dumps(extras, ensure_ascii=False)}
    edited = {
        **converted,
        "name": "After",
        "description": "after description",
        "opening_statement": "after opening",
        "extensions": extras["extensions"],
        "world_info": [
            {
                **converted_world,
                "name": "Updated lore",
                "content": "UPDATED_WORLD",
                "media_bindings": [{"asset_id": "new-media"}],
            },
            {
                "id": "new-world",
                "name": "New lore",
                "content": "NEW_WORLD",
                "enabled": True,
                "extensions": {"new_world_extension": {"keep": True}},
            }
        ],
        "regex_scripts": [
            {
                "id": "new-regex",
                "name": "New Regex",
                "find": "NEW",
                "replace": "new",
                "enabled": True,
            }
        ],
    }
    merged = homer.local_app_to_silly_card(row, edited)
    data = merged["data"]
    assert data["name"] == "After"
    assert data["description"] == "after description"
    assert data["first_mes"] == "after opening"
    assert data["character_book"]["future_book_field"] == "opaque"
    world_entries = data["character_book"]["entries"]
    assert [entry["id"] for entry in world_entries] == ["old-world", "new-world"]
    updated_world = world_entries[0]
    assert updated_world["content"] == "UPDATED_WORLD"
    assert updated_world["future_entry_field"]["preserve"] == "entry"
    assert updated_world["extensions"]["future_world_field"]["preserve"] is True
    assert updated_world["extensions"]["homer_media_bindings"] == [
        {"asset_id": "new-media"}
    ]
    assert world_entries[1]["extensions"]["new_world_extension"]["keep"] is True
    assert data["extensions"]["regex_scripts"][0]["id"] == "new-regex"
    assert data["extensions"]["tavern_helper"]["scripts"][0]["id"] == "hidden-helper"
    assert data["extensions"]["tavern_helper"]["variables"]["preserve"] is True
    assert data["extensions"]["third_party_metadata"]["preserve"] == "yes"
    assert data["future_card_field"]["preserve"] == "yes"
    assert merged["future_top_level"]["preserve"] is True

    cleared = homer.local_app_to_silly_card(
        row,
        {**edited, "world_info": [], "regex_scripts": []},
    )
    assert "character_book" not in cleared["data"]
    assert "regex_scripts" not in cleared["data"]["extensions"]
    assert cleared["data"]["extensions"]["tavern_helper"]["scripts"][0]["id"] == "hidden-helper"
    print("PASS imported card workshop edits merge without losing hidden extensions")


def test_large_card_storage_roundtrip(store: homer.Store) -> None:
    world_entries = [
        {
            "id": f"large-world-{index:03d}",
            "content": f"LARGE_WORLD_CONTENT_{index:03d}",
            "future_entry_field": {"index": index},
            "extensions": {"future_world_field": {"index": index}},
        }
        for index in range(307)
    ]
    regex_scripts = []
    for index in range(17):
        shared = index in (0, 1)
        regex_scripts.append(
            {
                "id": f"large-regex-{index:02d}",
                "scriptName": f"Large Regex {index:02d}",
                "findRegex": "/SHARED/g" if shared else f"/FIND_{index:02d}/g",
                "replaceString": f"REPLACE_{index:02d}",
                "placement": [1] if index == 0 else [2],
                "disabled": False,
            }
        )
    source = {
        "spec": "chara_card_v2",
        "spec_version": "2.0",
        "data": {
            "name": "Large Card Roundtrip",
            "character_book": {
                "name": "Large Book",
                "future_book_field": {"preserve": True},
                "entries": world_entries,
            },
            "extensions": {"regex_scripts": regex_scripts},
            # Some ecosystem exporters duplicate the same Regex list at the
            # top level. Exact cross-source duplicates should collapse once.
            "regex_scripts": json.loads(json.dumps(regex_scripts)),
        },
    }

    converted = homer.silly_card_to_app(source)
    assert len(converted["world_info"]) == 307
    assert len(converted["regex_scripts"]) == 17
    shared_scripts = [item for item in converted["regex_scripts"] if item["find"] == "SHARED"]
    assert len(shared_scripts) == 2
    assert {item["replace"] for item in shared_scripts} == {"REPLACE_00", "REPLACE_01"}
    assert {tuple(item["placement"]) for item in shared_scripts} == {(1,), (2,)}

    owner = store.upsert_user("large-card@example.test", "Large Card Owner", "password")
    created = store.create_user_app(str(owner["id"]), converted)
    stored = homer.local_app_to_card(dict(created))
    assert len(stored["world_info"]) == 307
    assert len(stored["regex_scripts"]) == 17

    exported = homer.local_app_to_silly_card(dict(created), stored)
    exported_data = exported["data"]
    assert len(exported_data["character_book"]["entries"]) == 307
    assert len(exported_data["extensions"]["regex_scripts"]) == 17
    assert exported_data["character_book"]["future_book_field"]["preserve"] is True
    last_entry = exported_data["character_book"]["entries"][-1]
    assert last_entry["id"] == "large-world-306"
    assert last_entry["future_entry_field"]["index"] == 306
    assert last_entry["extensions"]["future_world_field"]["index"] == 306
    print("PASS 307-entry worldbook/17 semantic Regex storage and export roundtrip")


def test_silly_card_conversion_cache() -> None:
    homer.clear_local_app_silly_card_cache()
    row = {
        "id": "cache-card",
        "updated_at": 100,
        "name": "Cache Before",
        "cover_url": "/media-cache/before.png",
        "extra_settings": json.dumps(
            {
                "extensions": {"cache_probe": {"preserve": True}},
                "world_info": [{"id": "cache-world", "content": "CACHE_WORLD"}],
            },
            ensure_ascii=False,
        ),
    }
    first = homer.cached_local_app_to_silly_card(row)
    second = homer.cached_local_app_to_silly_card(dict(row))
    assert first is second
    assert "messages" not in first

    response_a = homer.silly_card_with_homer_cover(first, "/covers/a.png")
    response_b = homer.silly_card_with_homer_cover(first, "/covers/b.png")
    assert response_a is not first and response_b is not first
    assert response_a["data"] is not first["data"]
    assert response_a["data"]["extensions"] is not first["data"]["extensions"]
    assert response_a["data"]["extensions"]["homer_cover_url"] == "/covers/a.png"
    assert response_b["data"]["extensions"]["homer_cover_url"] == "/covers/b.png"
    assert "homer_cover_url" not in first["data"]["extensions"]

    updated = {**row, "updated_at": 101, "name": "Cache After"}
    after = homer.cached_local_app_to_silly_card(updated)
    assert after is not first
    assert after["data"]["name"] == "Cache After"

    version_a = homer.cached_local_app_to_silly_card(updated, "version-a")
    version_a_again = homer.cached_local_app_to_silly_card(dict(updated), "version-a")
    version_b = homer.cached_local_app_to_silly_card(updated, "version-b")
    assert version_a is version_a_again
    assert version_a is not version_b

    for index in range(homer._LOCAL_APP_SILLY_CARD_CACHE_MAX + 5):
        homer.cached_local_app_to_silly_card(
            {**row, "id": f"bounded-cache-{index}", "updated_at": index + 1}
        )
    assert len(homer._local_app_silly_card_cache) <= homer._LOCAL_APP_SILLY_CARD_CACHE_MAX
    homer.clear_local_app_silly_card_cache()
    print("PASS version-aware bounded card conversion cache/response isolation")


def test_full_html_card_regex_guard() -> None:
    highlighter = {
        "id": "highlight-name",
        "name": "Highlight name",
        "find": "蜜糖",
        "replace": '<span style="color:#fbbf24">蜜糖</span>',
        "flags": "g",
        "enabled": True,
    }
    floating_bootstrap = {
        "id": "append-player",
        "name": "Append floating player",
        "find": r"(</html>)",
        "replace": "$1\n<!doctype html><html><body data-rp-player>player</body></html>",
        "flags": "i",
        "enabled": True,
    }
    app = {"regex_scripts": [highlighter, floating_bootstrap]}
    source = (
        '<!doctype html><html><body><p>蜜糖</p>'
        '<script>var state={"name":"蜜糖"};</script></body></html>'
    )

    rendered = homer.apply_regex_scripts(source, app)
    assert '<script>var state={"name":"蜜糖"};</script>' in rendered
    assert '<span style="color:#fbbf24">' not in rendered
    assert "data-rp-player" in rendered

    plain = homer.apply_regex_scripts("蜜糖向你挥手。", {"regex_scripts": [highlighter]})
    assert plain == '<span style="color:#fbbf24">蜜糖</span>向你挥手。'
    print("PASS full-HTML card Regex guard/plain-text highlight/document append")


def test_roleplayhub_card_adapter() -> None:
    assert ROLEPLAYHUB_CARD.is_file(), f"missing RoleplayHub fixture: {ROLEPLAYHUB_CARD}"
    parsed = homer.parse_png_card_metadata(ROLEPLAYHUB_CARD.read_bytes())
    converted = homer.silly_card_to_app(parsed)
    assert converted["name"] == "黎明之契2.71"
    assert len(converted["world_info"]) == 185
    assert len(converted["regex_scripts"]) == 23
    assert len(converted["legacy_rp_hub"]["bgm_playlist"]) == 5
    assert isinstance(converted.get("sillytavern_card"), dict)

    exported = homer.app_to_silly_card(converted)
    extensions = exported["data"]["extensions"]
    native_regex = extensions["regex_scripts"]
    assert len(native_regex) == 23
    assert native_regex[0]["scriptName"] == "ALTIA_UI_Render"
    assert native_regex[0]["findRegex"].endswith("/gm")
    assert native_regex[0]["placement"] == [2]
    assert native_regex[0]["markdownOnly"] is True
    profile = extensions["homer_roleplayhub"]
    assert profile["source"] == "roleplayhub"
    assert profile["interactive_html"] is True
    assert profile["regex_count"] == 23
    assert profile["ui_template_count"] == 1
    assert len(profile["media_playlist"]) == 5
    assert profile["sandbox"] == "opaque-origin-v1"
    # Unknown upstream fields remain available for future format evolution.
    assert extensions["rp_hub_watermark"]
    assert len(extensions["rp_hub_ui_templates"]) == 1

    # Detection is format-based, not tied to the 黎明之契 name.
    synthetic = {
        "spec": "chara_card_v3",
        "spec_version": "3.0",
        "data": {
            "name": "异名 RoleplayHub 迁移卡",
            "first_mes": "<!doctype html><html><body><button>开始</button></body></html>",
            "extensions": {
                "rp_hub_watermark": {"source": "roleplayhub"},
                "rp_hub_ui_templates": [{"name": "portable", "htmlTemplate": "<main>UI</main>"}],
                "regex_scripts": [
                    {
                        "name": "Portable UI",
                        "regex": "portable:(.+)",
                        "replacement": "<!doctype html><html><body>$1</body></html>",
                        "flags": "gi",
                        "placement": [2],
                    }
                ],
            },
        },
    }
    synthetic_app = homer.silly_card_to_app(synthetic)
    synthetic_export = homer.app_to_silly_card(synthetic_app)
    synthetic_extensions = synthetic_export["data"]["extensions"]
    assert synthetic_app["name"] == "异名 RoleplayHub 迁移卡"
    assert synthetic_extensions["homer_roleplayhub"]["source"] == "roleplayhub"
    assert synthetic_extensions["regex_scripts"][0]["findRegex"] == "/portable:(.+)/gi"
    assert synthetic_extensions["regex_scripts"][0]["replaceString"].startswith("<!doctype html>")

    # Existing installations may only have the server-validated legacy
    # fingerprint because they were imported before upstream extension fields
    # were preserved. They must migrate without a re-import or card-name rule.
    legacy_only = {
        "name": "旧数据异名迁移卡",
        "opening_statement": "<!doctype html><html><body>legacy</body></html>",
        "legacy_rp_hub": {
            "kind": "rp_hub",
            "vue_ui": True,
            "bgm_playlist": [
                {
                    "title": "Legacy",
                    "url": "https://raw.githubusercontent.com/example/creator/main/legacy.mp3",
                }
            ],
        },
        "regex_scripts": [
            {
                "id": "legacy-ui",
                "name": "Legacy UI",
                "find": "legacy",
                "replace": "<!doctype html><html><body>migrated</body></html>",
                "flags": "g",
                "placement": [2],
            }
        ],
    }
    legacy_export = homer.app_to_silly_card(legacy_only)
    legacy_extensions = legacy_export["data"]["extensions"]
    assert legacy_extensions["homer_roleplayhub"]["source"] == "roleplayhub"
    assert legacy_extensions["homer_roleplayhub"]["interactive_html"] is True
    assert len(legacy_extensions["homer_roleplayhub"]["media_playlist"]) == 1
    print("PASS RoleplayHub real-card/import/native-Regex/profile/format-level detection")


def test_conversation_character_rebinding(store: homer.Store) -> None:
    owner = store.upsert_user("rebind-owner@example.test", "Rebind Owner", "password")
    other = store.upsert_user("rebind-other@example.test", "Rebind Other", "password")
    owner_id = str(owner["id"])
    other_id = str(other["id"])
    card_name = "通用兼容卡 2.71"
    owner_card = store.create_user_app(
        owner_id,
        {"name": card_name, "is_public": False, "cover_url": "/media-cache/owner.png"},
    )
    # A newer private card belonging to another user must never be selected.
    store.create_user_app(
        other_id,
        {"name": card_name, "is_public": False, "cover_url": "/media-cache/other.png"},
    )

    conversation_id = "selftest-stale-character"
    stale_app_id = "user-removed-character"
    timestamp = homer.now_ms()
    with store.lock:
        store.conn.execute(
            """
            insert into conversations(id,user_id,app_id,app_name,title,created_at,updated_at)
            values(?,?,?,?,?,?,?)
            """,
            (conversation_id, owner_id, stale_app_id, card_name, card_name, timestamp, timestamp),
        )
        store.conn.commit()
    store.ensure_conversation_runtime_profile(conversation_id, owner_id)
    store.save_sillytavern_runtime_state(
        owner_id,
        stale_app_id,
        conversation_id,
        {"variables": {"chapter": 3}},
    )
    with store.lock:
        store.conn.execute(
            """
            insert into conversation_summaries(
                conversation_id,user_id,app_id,summary,message_count,created_at,updated_at
            ) values(?,?,?,?,?,?,?)
            """,
            (conversation_id, owner_id, stale_app_id, "summary", 1, timestamp, timestamp),
        )
        store.conn.execute(
            """
            insert into chat_memories(
                id,user_id,app_id,conversation_id,title,content,enabled,pinned,created_at,updated_at
            ) values(?,?,?,?,?,?,?,?,?,?)
            """,
            (
                "selftest-rebind-memory",
                owner_id,
                stale_app_id,
                conversation_id,
                "memory",
                "content",
                1,
                0,
                timestamp,
                timestamp,
            ),
        )
        store.conn.commit()

    listed = store.list_conversations(owner_id, limit=20)
    repaired = next(item for item in listed if item["id"] == conversation_id)
    expected_app_id = str(owner_card["id"])
    assert repaired["available"] is True
    assert repaired["app_id"] == expected_app_id
    for table in (
        "conversation_runtime_profiles",
        "conversation_summaries",
        "chat_memories",
        "sillytavern_runtime_states",
    ):
        row = store.conn.execute(
            f"select app_id from {table} where conversation_id=? and user_id=?",
            (conversation_id, owner_id),
        ).fetchone()
        assert row and str(row["app_id"]) == expected_app_id, table

    unavailable_id = "selftest-unavailable-character"
    with store.lock:
        store.conn.execute(
            """
            insert into conversations(id,user_id,app_id,app_name,title,created_at,updated_at)
            values(?,?,?,?,?,?,?)
            """,
            (
                unavailable_id,
                owner_id,
                "user-missing-without-replacement",
                "没有替代卡的角色",
                "没有替代卡的角色",
                timestamp + 1,
                timestamp + 1,
            ),
        )
        store.conn.commit()
    unavailable = store.repair_conversation_app(unavailable_id, owner_id)
    assert unavailable and unavailable["available"] is False
    assert unavailable["app_id"] == "user-missing-without-replacement"
    print("PASS stale conversation safe same-owner rebinding/unavailable preservation")


def main() -> int:
    test_internal_dialogue_mount_rewrite()
    test_card_stage_protocol_v2()
    test_original_runtime_extension_settings_bridge_contract()
    test_product_owned_dialogue_surface_contract()
    with tempfile.TemporaryDirectory(prefix="homer-st-selftest-") as temp_dir:
        root = Path(temp_dir)
        previous_media_dir = homer.MEDIA_DIR
        homer.MEDIA_DIR = root / "media"
        store = homer.Store(root / "state.sqlite3")
        try:
            store.configure_card_media(root / "media")
            test_extension_registry(store)
            test_runtime_state_and_generation(store)
            test_card_script_roundtrip()
            test_imported_card_workshop_merge()
            test_large_card_storage_roundtrip(store)
            test_silly_card_conversion_cache()
            test_full_html_card_regex_guard()
            test_roleplayhub_card_adapter()
            test_conversation_character_rebinding(store)
        finally:
            store.conn.close()
            homer.MEDIA_DIR = previous_media_dir
    print("\nALL SILLYTAVERN RUNTIME TESTS PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
