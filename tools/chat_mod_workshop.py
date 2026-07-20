"""Conversation Mod selection backed by community Mod works and immutable versions."""

from __future__ import annotations

import json
import re

from community_workshop import CommunityStore


def ensure_chat_mod_schema(conn, lock) -> None:
    with lock:
        conn.executescript(
            """
            create table if not exists conversation_mods_v2 (
                user_id text not null,
                conversation_id text not null,
                position integer not null,
                work_id text not null,
                version_id text not null,
                updated_at integer not null,
                primary key(user_id,conversation_id,work_id)
            );
            create unique index if not exists idx_conversation_mods_position
                on conversation_mods_v2(user_id,conversation_id,position);
            """
        )
        conn.commit()


def _mod_entries(content) -> list[dict]:
    if isinstance(content, dict):
        entries = content.get("entries") or content.get("world_info") or content.get("worldbook") or []
        if isinstance(entries, dict):
            entries = list(entries.values())
    else:
        entries = content if isinstance(content, list) else []
    return [dict(entry) for entry in entries if isinstance(entry, dict)][:400]


def _extras(app: dict) -> dict:
    raw = app.get("extra_settings") if isinstance(app, dict) else None
    try:
        return json.loads(raw) if isinstance(raw, str) and raw else (dict(raw) if isinstance(raw, dict) else {})
    except (TypeError, ValueError):
        return {}


def _deep_merge(base: dict, overlay: dict) -> dict:
    merged = dict(base or {})
    for key, value in (overlay or {}).items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def _snapshot_content(snapshot: dict) -> dict:
    content = snapshot.get("content") if isinstance(snapshot, dict) else None
    return dict(content) if isinstance(content, dict) else {}


class ConversationModStore:
    def __init__(self, conn, lock):
        self.conn, self.lock = conn, lock
        self.community = CommunityStore(conn, lock)

    def conversation_owned(self, user_id: str, conversation_id: str) -> bool:
        with self.lock:
            return bool(self.conn.execute("select 1 from conversations where id=? and user_id=?", (conversation_id, user_id)).fetchone())

    def library(self, user_id: str, query: str = "") -> list[dict]:
        rows = self.community.rows(
            """select w.* from community_works w where w.work_type='mod' and w.status='published' and
            (w.owner_user_id=? or (w.is_public=1 and exists(select 1 from community_work_favorites f where f.user_id=? and f.work_id=w.id)))
            order by w.updated_at desc""",
            (user_id, user_id),
        )
        needle = query.strip().lower()
        return [self.community.public_work(row, user_id) for row in rows
                if not needle or needle in str(row.get("name") or "").lower() or needle in str(row.get("summary") or "").lower()]

    def selection(self, user_id: str, conversation_id: str) -> list[dict]:
        with self.lock:
            rows = [dict(row) for row in self.conn.execute(
                "select * from conversation_mods_v2 where user_id=? and conversation_id=? order by position",
                (user_id, conversation_id),
            ).fetchall()]
        out = []
        for item in rows:
            work = self.community.get_work(item["work_id"])
            version = self.community.versions.get_version(item["version_id"], "mod", item["work_id"])
            if work and version:
                public = self.community.public_work(work, user_id)
                public.update({"version_id": item["version_id"], "position": int(item["position"])})
                out.append(public)
        return out

    def save_selection(self, user_id: str, conversation_id: str, items: list) -> list[dict]:
        if not self.conversation_owned(user_id, conversation_id):
            raise PermissionError("conversation not found")
        normalized = []
        seen = set()
        for raw in items[:30]:
            work_id = str(raw.get("work_id") or raw.get("id") or "") if isinstance(raw, dict) else str(raw or "")
            if not work_id or work_id in seen:
                continue
            work = self.community.get_work(work_id)
            if not work or work.get("work_type") != "mod" or not self.community.can_use_work(user_id, work):
                raise ValueError("mod is not available or favorited")
            requested_version = str(raw.get("version_id") or "") if isinstance(raw, dict) else ""
            version_id = requested_version or str(work.get("current_version_id") or "")
            if not self.community.versions.get_version(version_id, "mod", work_id):
                raise ValueError("mod version is invalid")
            seen.add(work_id)
            normalized.append((work_id, version_id))
        import time
        ts = int(time.time() * 1000)
        with self.lock:
            self.conn.execute("begin immediate")
            try:
                self.conn.execute("delete from conversation_mods_v2 where user_id=? and conversation_id=?", (user_id, conversation_id))
                self.conn.executemany(
                    "insert into conversation_mods_v2(user_id,conversation_id,position,work_id,version_id,updated_at) values(?,?,?,?,?,?)",
                    [(user_id, conversation_id, index, work_id, version_id, ts) for index, (work_id, version_id) in enumerate(normalized)],
                )
                self.conn.commit()
            except Exception:
                self.conn.rollback(); raise
        return self.selection(user_id, conversation_id)

    def ordered_entries(self, user_id: str, conversation_id: str) -> list[dict]:
        entries = []
        for mod_index, item in enumerate(self.selection(user_id, conversation_id)):
            snapshot = self.community.versions.snapshot(item["version_id"], "mod", item["id"]) or {}
            for entry_index, raw in enumerate(_mod_entries(snapshot.get("content"))):
                entry = dict(raw)
                entry["id"] = f"mod:{item['id']}:{item['version_id']}:{entry.get('id') or entry_index}"
                entry["_homer_world_group"] = "mod"
                entry["_homer_world_group_index"] = mod_index
                entry["_homer_world_sequence"] = entry_index
                entry["_mod_id"] = item["id"]
                entry["_mod_version_id"] = item["version_id"]
                entries.append(entry)
        return entries


def apply_locked_community_assets(conn, lock, app: dict) -> dict:
    """Resolve author-selected preset/UI versions server-side without consulting mutable work projections."""
    if not isinstance(app, dict):
        return app
    extras = _extras(app)
    community = CommunityStore(conn, lock)
    preset_id = str(extras.get("applied_preset_id") or "")
    preset_version_id = str(extras.get("applied_preset_version_id") or "")
    if preset_id and preset_version_id:
        snapshot = community.versions.snapshot(preset_version_id, "preset", preset_id)
        if snapshot:
            content = _snapshot_content(snapshot)
            preset = content.get("card_prompt_preset") or content.get("preset") or content
            if isinstance(preset, dict):
                preset = dict(preset)
                preset["enabled"] = True
                preset["source"] = "community"
                preset["source_work_id"] = preset_id
                preset["source_version_id"] = preset_version_id
                extras["card_prompt_preset"] = preset

    ui_ids = extras.get("applied_ui_template_ids") if isinstance(extras.get("applied_ui_template_ids"), list) else []
    ui_versions = extras.get("applied_ui_template_version_ids") if isinstance(extras.get("applied_ui_template_version_ids"), list) else []
    template_experience: dict = {}
    template_legacy: dict = {}
    applied_ui: list[dict] = []
    for index, work_id_raw in enumerate(ui_ids):
        work_id = str(work_id_raw or "")
        version_id = str(ui_versions[index] or "") if index < len(ui_versions) else ""
        if not work_id or not version_id:
            continue
        snapshot = community.versions.snapshot(version_id, "ui_template", work_id)
        if not snapshot:
            continue
        content = _snapshot_content(snapshot)
        source = content.get("ui_template") if isinstance(content.get("ui_template"), dict) else content
        experience = source.get("card_experience") if isinstance(source.get("card_experience"), dict) else {}
        legacy = source.get("legacy_rp_hub") if isinstance(source.get("legacy_rp_hub"), dict) else {}
        template_experience = _deep_merge(template_experience, experience)
        template_legacy = _deep_merge(template_legacy, legacy)
        applied_ui.append({"work_id": work_id, "version_id": version_id})
    own_experience = extras.get("card_experience") if isinstance(extras.get("card_experience"), dict) else {}
    own_legacy = extras.get("legacy_rp_hub") if isinstance(extras.get("legacy_rp_hub"), dict) else {}
    if template_experience:
        extras["card_experience"] = _deep_merge(template_experience, own_experience)
    if template_legacy:
        extras["legacy_rp_hub"] = _deep_merge(template_legacy, own_legacy)
    if applied_ui:
        extras["_applied_ui_template_versions"] = applied_ui
    app["extra_settings"] = extras
    return app


def apply_conversation_mods(conn, lock, app: dict, user_id: str, conversation_id: str, required_world_book_id: str = "") -> dict:
    if not isinstance(app, dict) or not conversation_id:
        return app
    entries = ConversationModStore(conn, lock).ordered_entries(user_id, conversation_id)
    if not entries:
        return app
    extras = _extras(app)
    existing = [entry for entry in extras.get("world_info") or [] if isinstance(entry, dict)]
    required = [entry for entry in existing if entry.get("id") == required_world_book_id]
    authored = []
    for authored_index, raw_entry in enumerate(existing):
        if raw_entry.get("id") == required_world_book_id or str(raw_entry.get("id") or "").startswith("mod:"):
            continue
        entry = dict(raw_entry)
        entry["_homer_world_group"] = "character"
        entry["_homer_world_group_index"] = 1_000_000
        entry["_homer_world_sequence"] = authored_index
        authored.append(entry)
    extras["world_info"] = required + entries + authored
    app["extra_settings"] = extras
    return app


def handle_chat_mod_route(method, normalized, query, body, ctx):
    prefix = "console/api/web/chat-mods/"
    if not normalized.startswith(prefix):
        return None
    user_id = str((ctx.get("user") or {}).get("id") or "")
    if not user_id:
        return {"code":401,"message":"unauthorized","__http__":401}
    store = ConversationModStore(ctx["conn"], ctx["lock"])
    sub, method = normalized[len(prefix):].strip("/"), method.upper()
    if sub == "library" and method == "GET":
        raw = query.get("q", [""]) if isinstance(query, dict) else ""
        q = raw[0] if isinstance(raw, list) and raw else raw
        return {"code":0,"message":"ok","data":{"list":store.library(user_id,str(q or ""))}}
    match = re.fullmatch(r"library/([^/]+)/favorite", sub)
    if match and method == "POST":
        try: return {"code":0,"message":"ok","data":{"favorited":store.community.toggle_favorite(user_id,match.group(1))}}
        except ValueError as exc: return {"code":400,"message":str(exc),"__http__":400}
    match = re.fullmatch(r"conversation/([^/]+)", sub)
    if match:
        conversation_id = match.group(1)
        if not store.conversation_owned(user_id, conversation_id):
            return {"code":404,"message":"conversation not found","__http__":404}
        if method == "GET":
            return {"code":0,"message":"ok","data":{"conversation_id":conversation_id,"list":store.selection(user_id,conversation_id)}}
        if method == "POST":
            data = body if isinstance(body, dict) else {}
            items = data.get("mods") if isinstance(data.get("mods"), list) else data.get("mod_ids") or []
            try:
                selected = store.save_selection(user_id, conversation_id, items)
                return {"code":0,"message":"ok","data":{"conversation_id":conversation_id,"list":selected,
                        "mod_ids":[item["id"] for item in selected]}}
            except (ValueError, PermissionError) as exc:
                return {"code":400,"message":str(exc),"__http__":400}
    return {"code":404,"message":"not found","__http__":404}
