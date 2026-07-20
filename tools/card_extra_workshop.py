"""Persistence and validation for character open-source, contest, preset and UI references."""

from __future__ import annotations

import json
import re
import time

from community_workshop import CommunityStore
from card_version_workshop import ContentVersionStore, merge_snapshot_over_row


def now_ms() -> int:
    return int(time.time() * 1000)


def ensure_card_extra_schema(conn, lock) -> None:
    with lock:
        conn.executescript(
            """
            create table if not exists card_extra_flags (
                app_id text primary key,
                is_open_source integer not null default 0,
                contest_opt_in integer not null default 0,
                contest_id text,
                used_preset_work_id text,
                used_preset_version_id text,
                used_ui_template_work_ids text not null default '[]',
                used_ui_template_version_ids text not null default '[]',
                updated_at integer not null
            );
            create index if not exists idx_card_extra_contest on card_extra_flags(contest_id,contest_opt_in);
            """
        )
        cols = {row[1] for row in conn.execute("pragma table_info(card_extra_flags)").fetchall()}
        additions = {
            "used_preset_version_id": "text", "used_ui_template_work_ids": "text not null default '[]'",
            "used_ui_template_version_ids": "text not null default '[]'",
        }
        for name, kind in additions.items():
            if name not in cols:
                conn.execute(f"alter table card_extra_flags add column {name} {kind}")
        conn.commit()


def _list(value) -> list[str]:
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            value = parsed if isinstance(parsed, list) else [value]
        except (TypeError, ValueError):
            value = [value] if value else []
    if not isinstance(value, list):
        return []
    out = []
    for item in value:
        clean = str(item or "").strip()
        if clean and clean not in out:
            out.append(clean)
    return out[:20]


def prepare_card_extra(conn, lock, user_id: str, data: dict, existing: dict | None = None) -> dict:
    existing = existing or {}
    store = CommunityStore(conn, lock)
    preset_id = str(data.get("applied_preset_id", data.get("used_preset_work_id", existing.get("applied_preset_id", ""))) or "").strip()
    ui_ids = _list(data.get("applied_ui_template_ids", data.get("used_ui_template_work_ids", existing.get("applied_ui_template_ids", []))))

    requested_preset_version = str(
        data.get("applied_preset_version_id", data.get("used_preset_version_id", existing.get("applied_preset_version_id", existing.get("used_preset_version_id", ""))))
        or ""
    ).strip()
    preset_version = ""
    if preset_id:
        row = store.get_work(preset_id)
        if not row or row.get("work_type") != "preset" or not store.can_use_work(user_id, row):
            raise ValueError("selected preset is not available or favorited")
        preset_version = requested_preset_version or str(row.get("current_version_id") or "")
        if not store.versions.get_version(preset_version, "preset", preset_id):
            raise ValueError("selected preset version is invalid")
    elif requested_preset_version:
        raise ValueError("selected preset version requires a preset")
    requested_ui_versions = _list(
        data.get(
            "applied_ui_template_version_ids",
            data.get("used_ui_template_version_ids", existing.get("applied_ui_template_version_ids", existing.get("used_ui_template_version_ids", []))),
        )
    )
    ui_versions = []
    for index, work_id in enumerate(ui_ids):
        row = store.get_work(work_id)
        if not row or row.get("work_type") != "ui_template" or not store.can_use_work(user_id, row):
            raise ValueError("selected UI template is not available or favorited")
        version_id = requested_ui_versions[index] if index < len(requested_ui_versions) else str(row.get("current_version_id") or "")
        if not store.versions.get_version(version_id, "ui_template", work_id):
            raise ValueError("selected UI template version is invalid")
        ui_versions.append(version_id)
    return {
        "is_open_source": bool(data.get("is_open_source", existing.get("is_open_source", False))),
        "contest_opt_in": bool(data.get("contest_opt_in", existing.get("contest_opt_in", False))),
        "contest_id": str(existing.get("contest_id") or ""),
        "applied_preset_id": preset_id,
        "applied_preset_version_id": preset_version,
        "applied_ui_template_ids": ui_ids,
        "applied_ui_template_version_ids": ui_versions,
    }


def sync_card_extra_flags(conn, lock, app_id: str, extras: dict, *, contest_id: str = "", commit: bool = True) -> None:
    with lock:
        conn.execute(
            """insert into card_extra_flags(app_id,is_open_source,contest_opt_in,contest_id,
            used_preset_work_id,used_preset_version_id,used_ui_template_work_ids,used_ui_template_version_ids,updated_at)
            values(?,?,?,?,?,?,?,?,?) on conflict(app_id) do update set
            is_open_source=excluded.is_open_source,contest_opt_in=excluded.contest_opt_in,contest_id=excluded.contest_id,
            used_preset_work_id=excluded.used_preset_work_id,used_preset_version_id=excluded.used_preset_version_id,
            used_ui_template_work_ids=excluded.used_ui_template_work_ids,
            used_ui_template_version_ids=excluded.used_ui_template_version_ids,updated_at=excluded.updated_at""",
            (app_id, 1 if extras.get("is_open_source") else 0, 1 if extras.get("contest_opt_in") else 0,
             contest_id or str(extras.get("contest_id") or ""), str(extras.get("applied_preset_id") or ""),
             str(extras.get("applied_preset_version_id") or ""),
             json.dumps(_list(extras.get("applied_ui_template_ids")), ensure_ascii=False),
             json.dumps(_list(extras.get("applied_ui_template_version_ids")), ensure_ascii=False), now_ms()),
        )
        if commit:
            conn.commit()


def card_extra_payload(conn, lock, app_id: str) -> dict:
    with lock:
        row = conn.execute("select * from card_extra_flags where app_id=?", (app_id,)).fetchone()
    if not row:
        return {"app_id":app_id, "is_open_source":False, "contest_opt_in":False, "contest_id":"",
                "used_preset_work_id":"", "used_preset_version_id":"", "used_ui_template_work_ids":[],
                "used_ui_template_version_ids":[]}
    value = dict(row)
    return {
        "app_id": app_id, "is_open_source": bool(value.get("is_open_source")),
        "contest_opt_in": bool(value.get("contest_opt_in")), "contest_id": value.get("contest_id") or "",
        "used_preset_work_id": value.get("used_preset_work_id") or "",
        "used_preset_version_id": value.get("used_preset_version_id") or "",
        "used_ui_template_work_ids": _list(value.get("used_ui_template_work_ids")),
        "used_ui_template_version_ids": _list(value.get("used_ui_template_version_ids")),
    }


def open_source_entries(app_row: dict) -> list[dict]:
    try:
        extra = json.loads(app_row.get("extra_settings") or "{}") if isinstance(app_row.get("extra_settings"), str) else app_row.get("extra_settings") or {}
    except (TypeError, ValueError):
        extra = {}
    out = []
    for entry in extra.get("world_info") or []:
        if isinstance(entry, dict) and str(entry.get("content") or "").strip():
            out.append({"group":"世界书", "name":str(entry.get("name") or entry.get("comment") or "世界书条目")[:80], "content":str(entry.get("content"))})
    for entry in extra.get("prompt_blocks") or []:
        if isinstance(entry, dict) and str(entry.get("content") or "").strip():
            out.append({"group":"提示词", "name":str(entry.get("name") or "提示词块")[:80], "content":str(entry.get("content"))})
    return out[:400]


def handle_card_extra_route(method, normalized, query, body, ctx):
    prefix = "console/api/web/card-extra/"
    if not normalized.startswith(prefix):
        return None
    user, uid, is_admin = ctx.get("user") or {}, str((ctx.get("user") or {}).get("id") or ""), bool(ctx.get("is_admin"))
    get_app = ctx.get("get_app")
    store = CommunityStore(ctx["conn"], ctx["lock"])
    sub, method = normalized[len(prefix):].strip("/"), method.upper()
    match = re.fullmatch(r"flags/([^/]+)", sub)
    if match:
        app_id = match.group(1)
        row = get_app(app_id) if callable(get_app) else None
        if not row:
            return {"code":404,"message":"not found","__http__":404}
        row = dict(row)
        owner = str(row.get("owner_user_id") or "")
        can_edit = bool(is_admin or (uid and owner == uid and row.get("source") == "user"))
        can_view = bool(can_edit or (row.get("is_public") and row.get("status") == "published"))
        if not can_view:
            return {"code":404,"message":"not found","__http__":404}
        if method == "GET":
            payload = card_extra_payload(ctx["conn"], ctx["lock"], str(row.get("id") or app_id))
            if can_edit:
                draft = ContentVersionStore(ctx["conn"], ctx["lock"]).draft_snapshot(str(row.get("id") or app_id), uid)
                if draft:
                    row = merge_snapshot_over_row(row, draft)
                    try:
                        draft_extra = json.loads(row.get("extra_settings") or "{}") if isinstance(row.get("extra_settings"), str) else row.get("extra_settings") or {}
                    except (TypeError, ValueError):
                        draft_extra = {}
                    if isinstance(draft_extra, dict):
                        payload.update({
                            "is_open_source": bool(draft_extra.get("is_open_source")),
                            "contest_opt_in": bool(draft_extra.get("contest_opt_in")),
                            "contest_id": str(draft_extra.get("contest_id") or payload.get("contest_id") or ""),
                            "used_preset_work_id": str(draft_extra.get("applied_preset_id") or ""),
                            "used_preset_version_id": str(draft_extra.get("applied_preset_version_id") or ""),
                            "used_ui_template_work_ids": _list(draft_extra.get("applied_ui_template_ids")),
                            "used_ui_template_version_ids": _list(draft_extra.get("applied_ui_template_version_ids")),
                        })
            if payload["is_open_source"]:
                payload["open_source_entries"] = open_source_entries(row)
            if payload.get("contest_id"):
                payload["votes"] = int(store.one("select count(*) c from community_votes where contest_id=? and app_id=?", (payload["contest_id"], row["id"]))["c"])
                payload["voted"] = bool(uid and store.one("select 1 ok from community_votes where contest_id=? and app_id=? and user_id=?", (payload["contest_id"],row["id"],uid)))
            return {"code":0,"message":"ok","data":payload}
        if method in {"POST","PUT"}:
            if not can_edit: return {"code":403,"message":"forbidden","__http__":403}
            return {"code":409,"message":"card flags must be saved as a draft and published as a new version","__http__":409}
    if sub == "vote" and method == "POST":
        if not uid: return {"code":401,"message":"unauthorized","__http__":401}
        app_id = str((body or {}).get("app_id") or "") if isinstance(body,dict) else ""
        flags = card_extra_payload(ctx["conn"],ctx["lock"],app_id)
        if not flags.get("contest_opt_in") or not flags.get("contest_id"):
            return {"code":400,"message":"角色未参赛","__http__":400}
        try: return {"code":0,"message":"ok","data":store.vote(flags["contest_id"],app_id,uid)}
        except ValueError as exc: return {"code":400,"message":str(exc),"__http__":400}
    return {"code":404,"message":"not found","__http__":404}
