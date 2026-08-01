"""Static contract checks for the card-owned stage and structured UI runtime."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STAGE = ROOT / "sillytavern-runtime/public/scripts/extensions/homer-bridge/card-stage.js"
STYLE = ROOT / "sillytavern-runtime/public/scripts/extensions/homer-bridge/style.css"
EXPERIENCE = ROOT / "frontend/app/assets/js/card-experience-runtime.mjs"
SCHEMA = ROOT / "frontend/app/assets/js/card-experience-schema.mjs"


def require(source: str, *needles: str) -> None:
    missing = [needle for needle in needles if needle not in source]
    if missing:
        raise AssertionError(f"missing runtime contract markers: {missing}")


def main() -> int:
    stage = STAGE.read_text(encoding="utf-8")
    style = STYLE.read_text(encoding="utf-8")
    experience = EXPERIENCE.read_text(encoding="utf-8")
    schema = SCHEMA.read_text(encoding="utf-8")

    require(
        stage,
        "const COMPONENT_TYPES = new Set(['map', 'inventory', 'relationship', 'skill_tree', 'status'])",
        "const canRenderStructured = !message?.is_user && !message?.is_system",
        "removeVisibleTextSequence",
        "homer-stage-portrait-${portraitPosition}",
        "homer-stage-avatars-${avatarPosition}",
        "--homer-stage-input-background",
        "video.removeAttribute('src')",
        "latestAssistantIndex",
        "protocol: 'homer-ui-json-v1'",
    )
    for renderer in ("renderMap", "renderInventory", "renderRelationship", "renderSkillTree", "renderStatus"):
        require(stage, f"function {renderer}(")

    require(
        experience,
        "'world.content': ''",
        "makeDraggable(node, handle)",
        "setPointerCapture",
        "role', 'tablist'",
        "aria-selected",
        "this.floatTimers",
        "if (rule.duration_ms > 0)",
        "this.spineLayer.dispose()",
        "publicWorld = world ? { ...world, content: '' } : null",
        "height: 100dvh",
        "min-height: 100dvh",
    )
    require(
        schema,
        "portrait_position: 'right'",
        "portrait_width: 43",
        "portrait_opacity: 1",
        "avatar_position: 'split'",
        "input_background_color",
        "input_text_color",
        "input_border_color",
    )
    require(
        style,
        ".homer-relationship__detail",
        ".homer-status-component__detail",
        ".homer-map__action",
        "body.homer-stage-avatars-split",
        "body.homer-stage-portrait-center",
        "z-index: 30010",
    )

    forbidden = ("黎明之契", "道渊", "roleplayhub_app_id")
    if any(value in stage for value in forbidden):
        raise AssertionError("card-stage runtime contains a card-specific branch")

    print("PASS generic stage fields and five structured components")
    print("PASS draggable floating panels and tabbed sidebars")
    print("PASS assistant-only rendering and worldbook privacy boundary")
    print("PASS card-switch media and renderer cleanup contract")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
