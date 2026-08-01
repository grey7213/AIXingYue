"""Card experience v2-compatible schema and structured payload self-test."""

from __future__ import annotations

import json

import ai_fengyue_local_server as homer
from card_experience_extension import (
    CardMediaError,
    MAX_CARD_EXPERIENCE_MARKUP_BYTES,
    MAX_STRUCTURED_COMPONENT_ITEMS,
    MAX_UI_RULES,
    merge_card_experience_fields,
)


def test_extended_stage_and_v2_compatibility() -> None:
    rules = [
        {
            "id": f"rule-{index}",
            "name": f"rule {index}",
            "pattern": rf"\[RULE:{index}\]",
            "action": "show_floating",
            "template_html": "<p>notice</p>",
            "duration_ms": 0,
        }
        for index in range(MAX_UI_RULES + 8)
    ]
    normalized = homer.normalize_card_experience(
        {
            "version": 2,
            "future_protocol": {"mode": "keep", "__proto__": {"polluted": True}},
            "stage": {
                "enabled": True,
                "layout": "landscape",
                "chat_width": 999,
                "show_portrait": False,
                "portrait_position": "center",
                "portrait_width": 999,
                "portrait_opacity": -5,
                "show_avatars": False,
                "avatar_position": "split",
                "bubble_radius": 999,
                "input_style": "floating",
                "input_background_color": "#123456",
                "input_text_color": "invalid",
                "input_border_color": "rgba(1,2,3,.5)",
                "future_stage": {"animation": "keep"},
            },
            "structured_components": {"map": False, "future_component": {"keep": True}},
            "bgm": {"enabled": False, "future_audio": "keep"},
            "ui_rules": rules,
            "sidebars": [{
                "id": "private-lore",
                "name": "private",
                "content_mode": "worldbook",
                "world_entry_id": "secret-world",
                "content_html": "<p>public summary only</p>",
                "future_sidebar": {"keep": True},
            }],
            "galgame": {"future_galgame": {"keep": True}},
        },
        {},
        {"secret-world"},
    )
    assert normalized["version"] == 2
    assert normalized["future_protocol"]["mode"] == "keep"
    assert "__proto__" not in normalized["future_protocol"]
    stage = normalized["stage"]
    assert stage["layout"] == "landscape"
    assert stage["chat_width"] == 100
    assert stage["show_portrait"] is False
    assert stage["portrait_position"] == "center"
    assert stage["portrait_width"] == 70
    assert stage["portrait_opacity"] == 0.2
    assert stage["show_avatars"] is False
    assert stage["avatar_position"] == "split"
    assert stage["bubble_radius"] == 36
    assert stage["input_style"] == "floating"
    assert stage["input_background_color"] == "#123456"
    assert stage["input_text_color"] == "#fff8ed"
    assert stage["input_border_color"] == "rgba(1,2,3,.5)"
    assert stage["future_stage"]["animation"] == "keep"
    assert normalized["structured_components"]["map"] is False
    assert normalized["structured_components"]["inventory"] is True
    assert normalized["structured_components"]["future_component"]["keep"] is True
    assert normalized["bgm"]["future_audio"] == "keep"
    assert len(normalized["ui_rules"]) == MAX_UI_RULES
    assert normalized["ui_rules"][0]["duration_ms"] == 0
    sidebar = normalized["sidebars"][0]
    assert sidebar["content_mode"] == "static"
    assert sidebar["world_entry_id"] == ""
    assert sidebar["future_sidebar"]["keep"] is True
    assert normalized["galgame"]["future_galgame"]["keep"] is True
    print("PASS extended stage fields and v2-compatible opaque fields")


def test_markup_aggregate_limit_and_unsafe_markup() -> None:
    repeated = "<section>" + ("x" * 29_980) + "</section>"
    normalized = homer.normalize_card_experience(
        {
            "ui_rules": [
                {
                    "id": f"markup-{index}",
                    "pattern": rf"\[M:{index}\]",
                    "action": "show_floating",
                    "template_html": repeated,
                    "scoped_css": ".panel{color:#fff}",
                }
                for index in range(40)
            ]
        },
        {},
        set(),
    )
    markup_bytes = sum(
        len(rule["template_html"].encode("utf-8")) + len(rule["scoped_css"].encode("utf-8"))
        for rule in normalized["ui_rules"]
    )
    assert markup_bytes <= MAX_CARD_EXPERIENCE_MARKUP_BYTES
    try:
        homer.normalize_card_experience(
            {"ui_rules": [{"pattern": "x", "template_html": "<script>alert(1)</script>"}]},
            {},
            set(),
        )
    except CardMediaError as exc:
        assert "unsafe HTML" in str(exc)
    else:
        raise AssertionError("unsafe HTML was accepted")
    print("PASS aggregate markup budget and unsafe markup rejection")


def test_structured_component_normalization() -> None:
    map_payload = {
        "type": "map",
        "title": "World",
        "root": {
            "name": "root",
            "children": [
                {
                    "id": f"area {index}",
                    "name": f"Area {index}",
                    "image": "javascript:alert(1)",
                    "x": 999,
                    "y": -1,
                    "onclick": "alert(1)",
                }
                for index in range(MAX_STRUCTURED_COMPONENT_ITEMS + 30)
            ],
        },
    }
    normalized_map = homer.normalize_structured_component_payload(map_payload)
    assert normalized_map["type"] == "map"
    assert len(normalized_map["root"]["children"]) == MAX_STRUCTURED_COMPONENT_ITEMS - 1
    first = normalized_map["root"]["children"][0]
    assert first["id"] == "area-0"
    assert first["x"] == 95 and first["y"] == 8
    assert "image" not in first and "onclick" not in first

    inventory = homer.normalize_structured_component_payload({
        "type": "inventory",
        "items": [
            {"name": f"item {index}", "quantity": index, "category": "tool", "script": "bad"}
            for index in range(MAX_STRUCTURED_COMPONENT_ITEMS + 10)
        ],
    })
    assert len(inventory["items"]) == MAX_STRUCTURED_COMPONENT_ITEMS
    assert "script" not in inventory["items"][0]

    relationship = homer.normalize_structured_component_payload({
        "type": "relationship",
        "center": {"id": "you", "name": "You"},
        "nodes": [{"id": "guide", "name": "Guide"}],
        "edges": [
            {"source": "you", "target": "guide", "label": "friend"},
            {"source": "you", "target": "missing", "label": "invalid"},
        ],
    })
    assert relationship["edges"] == [{"source": "you", "target": "guide", "label": "friend"}]

    skills = homer.normalize_structured_component_payload({
        "type": "skill-tree",
        "nodes": [{"id": "skill", "name": "Skill", "requires": [f"r-{i}" for i in range(40)]}],
    })
    assert skills["type"] == "skill_tree"
    assert len(skills["nodes"][0]["requires"]) == 20

    try:
        homer.normalize_structured_component_payload({"type": "status", "items": [{"value": "x" * 101_000}]})
    except CardMediaError as exc:
        assert "too large" in str(exc)
    else:
        raise AssertionError("oversized structured payload was accepted")
    print("PASS map/inventory/relationship/skill structured payload limits")


def test_asset_validation_and_import_export_roundtrip() -> None:
    try:
        homer.normalize_card_experience(
            {"stage": {"background_asset_id": "not-owned"}},
            {},
            set(),
        )
    except CardMediaError as exc:
        assert "owned background" in str(exc)
    else:
        raise AssertionError("unowned stage background was accepted")

    source = {
        "spec": "chara_card_v2",
        "spec_version": "2.0",
        "future_top_level": {"keep": True},
        "data": {
            "name": "Schema Probe",
            "description": "probe",
            "first_mes": "hello",
            "extensions": {
                "future_extension": {"keep": True},
                "homer_card_experience": {
                    "version": 2,
                    "future_protocol": {"keep": "yes"},
                    "stage": {
                        "enabled": True,
                        "show_portrait": False,
                        "portrait_position": "left",
                        "portrait_width": 34,
                        "input_background_color": "#112233",
                        "future_stage": {"keep": "nested"},
                    },
                    "structured_components": {"inventory": False},
                    "sidebars": [],
                },
            },
        },
    }
    imported = homer.silly_card_to_app(source)
    experience = imported["card_experience"]
    assert experience["future_protocol"]["keep"] == "yes"
    assert experience["stage"]["future_stage"]["keep"] == "nested"
    assert experience["stage"]["show_portrait"] is False
    assert experience["structured_components"]["inventory"] is False

    updated = merge_card_experience_fields(experience, {
        "stage": {"portrait_position": "right", "portrait_width": 47},
    })
    normalized_update = homer.normalize_card_experience(updated, {}, set())
    imported["card_experience"] = normalized_update
    row = {
        "extra_settings": json.dumps({
            "sillytavern_card": source,
            "card_experience": normalized_update,
            "extensions": imported["extensions"],
        }, ensure_ascii=False),
    }
    exported = homer.local_app_to_silly_card(row, imported)
    exported_experience = exported["data"]["extensions"]["homer_card_experience"]
    assert exported["future_top_level"]["keep"] is True
    assert exported["data"]["extensions"]["future_extension"]["keep"] is True
    assert exported_experience["future_protocol"]["keep"] == "yes"
    assert exported_experience["stage"]["future_stage"]["keep"] == "nested"
    assert exported_experience["stage"]["portrait_position"] == "right"
    assert exported_experience["stage"]["portrait_width"] == 47
    print("PASS asset ownership and unknown-field import/export roundtrip")


def main() -> None:
    test_extended_stage_and_v2_compatibility()
    test_markup_aggregate_limit_and_unsafe_markup()
    test_structured_component_normalization()
    test_asset_validation_and_import_export_roundtrip()
    print("\nALL 4 CARD EXPERIENCE SCHEMA TESTS PASSED")


if __name__ == "__main__":
    main()
