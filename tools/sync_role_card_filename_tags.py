#!/usr/bin/env python3
"""Safely sync optimized role-card filename tags and retire CLEAR cards."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sqlite3
import time
import urllib.parse
import zipfile
from pathlib import Path
from typing import Any

from import_role_card_annotations import (
    CARD_SCHEMA,
    FLAG_RE,
    archive_root,
    detected_features,
    json_bytes,
    normalize_tags,
    now_ms,
    online_backup,
    read_manifest,
    sha256_bytes,
    sha256_file,
)


PLAN_SCHEMA = "ai-xingyue-role-card-filename-tag-sync/v1"
CARD_NAME_RE = re.compile(r"^(?P<display_id>[^/]+?)__(?P<labels>.*)\.json$")
TAG_RE = re.compile(r"\[([^\]]*)\]")
FUNCTIONAL_REFERENCE_COLUMNS = {
    "conversations": "app_id",
    "conversation_summaries": "app_id",
    "chat_memories": "app_id",
    "group_members": "app_id",
    "group_messages": "speaker_app_id",
    "user_favorites": "app_id",
    "user_likes": "app_id",
    "user_app_tags": "app_id",
    "app_comments": "app_id",
}


def plan_sha256(path: Path) -> str:
    return sha256_file(path)


def decode_tag(raw: str) -> str:
    try:
        return urllib.parse.unquote(raw, encoding="utf-8", errors="strict")
    except Exception as exc:
        raise ValueError(f"invalid percent-encoded tag: {raw!r}") from exc


def parse_filename(base: str) -> tuple[str, str, list[str], dict[str, bool]]:
    match = CARD_NAME_RE.match(base)
    flags = FLAG_RE.search(base)
    if not match or not flags:
        raise ValueError(f"unparseable card filename: {base}")
    display_id = match.group("display_id")
    labels = match.group("labels")[: flags.start() - match.start("labels")]
    action = "replace"
    if labels == "CLEAR":
        action = "clear"
        tags: list[str] = []
    elif labels == "KEEP":
        action = "keep"
        tags = []
    else:
        parts = TAG_RE.findall(labels)
        if not parts or "".join(f"[{part}]" for part in parts) != labels:
            raise ValueError(f"invalid tag expression: {base}")
        tags = normalize_tags([decode_tag(part) for part in parts])
        if not tags:
            raise ValueError(f"empty tag expression must use CLEAR: {base}")
    values = tuple(value == "√" for value in flags.groups())
    return display_id, action, tags, {
        "opening": values[0],
        "world_info": values[1],
        "regex": values[2],
    }


def prepare(zip_path: Path) -> dict[str, Any]:
    archive_sha = sha256_file(zip_path)
    with zipfile.ZipFile(zip_path, "r") as zf:
        names = [item.filename for item in zf.infolist()]
        if len(names) != len(set(names)):
            raise ValueError("ZIP contains duplicate archive paths")
        root = archive_root(names)
        manifest, _raw, manifest_sha = read_manifest(zf, root)
        manifest_items = manifest.get("items") or []
        if int(manifest.get("count") or 0) != len(manifest_items):
            raise ValueError("manifest count mismatch")
        by_display = {str(item["display_id"]): item for item in manifest_items}
        if len(by_display) != len(manifest_items):
            raise ValueError("duplicate manifest display_id")
        if len({str(item["internal_id"]) for item in manifest_items}) != len(manifest_items):
            raise ValueError("duplicate manifest internal_id")

        cards: dict[str, str] = {}
        parsed: dict[str, tuple[str, list[str], dict[str, bool]]] = {}
        for member in names:
            if not (member.startswith(root + "cards/") and member.endswith(".json")):
                continue
            base = member.rsplit("/", 1)[-1]
            display_id, action, tags, features = parse_filename(base)
            if display_id in cards or display_id not in by_display:
                raise ValueError(f"duplicate or unknown card display_id: {display_id}")
            cards[display_id] = member
            parsed[display_id] = (action, tags, features)
        if set(cards) != set(by_display):
            raise ValueError("card/manifest membership mismatch")

        items: list[dict[str, Any]] = []
        counts = {"replace": 0, "clear": 0, "keep": 0}
        for index, manifest_item in enumerate(manifest_items, start=1):
            display_id = str(manifest_item["display_id"])
            raw = zf.read(cards[display_id])
            if sha256_bytes(raw) != str(manifest_item.get("card_sha256") or ""):
                raise ValueError(f"card content SHA mismatch: {display_id}")
            payload = json.loads(raw.decode("utf-8-sig"))
            record = payload.get("record")
            if payload.get("schema") != CARD_SCHEMA or not isinstance(record, dict):
                raise ValueError(f"invalid card payload: {display_id}")
            internal_id = str(manifest_item["internal_id"])
            if str(record.get("id") or "") != internal_id:
                raise ValueError(f"card/manifest internal ID mismatch: {display_id}")
            action, tags, features = parsed[display_id]
            if detected_features(record) != features:
                raise ValueError(f"feature mismatch: {display_id}")
            counts[action] += 1
            items.append({
                "internal_id": internal_id,
                "display_id": display_id,
                "name": str(record.get("name") or manifest_item.get("name") or ""),
                "action": action,
                "new_tags": tags,
                "features": features,
                "source_filename": cards[display_id].rsplit("/", 1)[-1],
                "card_sha256": str(manifest_item.get("card_sha256") or ""),
            })
            if index % 1000 == 0:
                print(f"prepared {index}/{len(manifest_items)}", flush=True)
    return {
        "schema": PLAN_SCHEMA,
        "prepared_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "archive": str(zip_path.resolve()),
        "archive_size": zip_path.stat().st_size,
        "archive_sha256": archive_sha,
        "manifest_sha256": manifest_sha,
        "count": len(items),
        "stats": counts,
        "items": items,
    }


def read_plan(path: Path) -> dict[str, Any]:
    plan = json.loads(path.read_text(encoding="utf-8-sig"))
    if plan.get("schema") != PLAN_SCHEMA or len(plan.get("items") or []) != int(plan.get("count") or -1):
        raise ValueError("invalid plan")
    return plan


def table_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {str(row[1]) for row in conn.execute(f'pragma table_info("{table}")')}


def reference_counts(conn: sqlite3.Connection, app_id: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    tables = {str(row[0]) for row in conn.execute("select name from sqlite_master where type='table'")}
    for table, column in FUNCTIONAL_REFERENCE_COLUMNS.items():
        if table in tables and column in table_columns(conn, table):
            counts[table] = int(conn.execute(
                f'select count(*) from "{table}" where "{column}"=?', (app_id,)
            ).fetchone()[0])
    return counts


def preflight(conn: sqlite3.Connection, plan: dict[str, Any]) -> dict[str, Any]:
    conn.row_factory = sqlite3.Row
    ids = [str(item["internal_id"]) for item in plan["items"]]
    rows: dict[str, sqlite3.Row] = {}
    for start in range(0, len(ids), 800):
        chunk = ids[start:start + 800]
        marks = ",".join("?" for _ in chunk)
        for row in conn.execute(
            f"select id,display_id,source,status,is_public,tags from local_apps where id in ({marks})", chunk
        ):
            rows[str(row["id"])] = row
    missing: list[dict[str, str]] = []
    conflicts: list[dict[str, str]] = []
    tag_updates = 0
    clear_delete: list[str] = []
    clear_archive: list[str] = []
    reference_totals: dict[str, int] = {}
    for item in plan["items"]:
        app_id = str(item["internal_id"])
        row = rows.get(app_id)
        if row is None:
            missing.append({"internal_id": app_id, "display_id": str(item["display_id"]), "action": item["action"]})
            continue
        if str(row["display_id"] or "") != str(item["display_id"]):
            conflicts.append({"internal_id": app_id, "reason": "display_id_changed"})
        if str(row["source"] or "") != "admin":
            conflicts.append({"internal_id": app_id, "reason": "source_changed"})
        if item["action"] == "replace" and normalize_tags(row["tags"]) != normalize_tags(item["new_tags"]):
            tag_updates += 1
        if item["action"] == "clear":
            refs = reference_counts(conn, app_id)
            functional = sum(refs.values())
            for key, value in refs.items():
                reference_totals[key] = reference_totals.get(key, 0) + value
            (clear_archive if functional else clear_delete).append(app_id)
    return {
        "plan_count": len(plan["items"]),
        "existing_count": len(rows),
        "missing_count": len(missing),
        "missing": missing[:50],
        "conflict_count": len(conflicts),
        "conflicts": conflicts[:50],
        "tag_updates": tag_updates,
        "clear_delete_count": len(clear_delete),
        "clear_archive_count": len(clear_archive),
        "clear_delete_ids": clear_delete,
        "clear_archive_ids": clear_archive,
        "functional_reference_totals": reference_totals,
    }


def apply(db_path: Path, plan: dict[str, Any], *, do_apply: bool, backup: Path | None,
          actual_plan_sha: str, expected_plan_sha: str | None) -> dict[str, Any]:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        before = preflight(conn, plan)
        report: dict[str, Any] = {
            "schema": PLAN_SCHEMA,
            "mode": "apply" if do_apply else "dry-run",
            "db": str(db_path.resolve()),
            "archive_sha256": plan.get("archive_sha256"),
            "manifest_sha256": plan.get("manifest_sha256"),
            "plan_sha256": actual_plan_sha,
            "preflight": before,
        }
        if expected_plan_sha and actual_plan_sha.casefold() != expected_plan_sha.casefold():
            report.update(applied=False, ready_to_apply=False, plan_sha256_mismatch=True)
            return report
        if before["conflict_count"]:
            report["applied"] = False
            return report
        if not do_apply:
            report.update(applied=False, ready_to_apply=True)
            return report
        if backup is None:
            raise ValueError("--backup is required with --apply")
        online_backup(conn, backup)
        before_user_counts = {
            table: int(conn.execute(f'select count(*) from "{table}"').fetchone()[0])
            for table in FUNCTIONAL_REFERENCE_COLUMNS if table in {
                str(row[0]) for row in conn.execute("select name from sqlite_master where type='table'")
            }
        }
        conn.execute("begin immediate")
        try:
            locked = preflight(conn, plan)
            if locked["conflict_count"] or locked["missing_count"] != before["missing_count"]:
                raise RuntimeError("transaction preflight changed")
            delete_ids = set(locked["clear_delete_ids"])
            archive_ids = set(locked["clear_archive_ids"])
            changed_tags = deleted = archived = annotations = 0
            annotated_at = now_ms()
            for item in plan["items"]:
                app_id = str(item["internal_id"])
                row = conn.execute("select id,tags from local_apps where id=?", (app_id,)).fetchone()
                if row is None:
                    continue
                if app_id in delete_ids:
                    conn.execute("delete from role_card_annotations where app_id=?", (app_id,))
                    conn.execute("delete from local_apps where id=? and source='admin'", (app_id,))
                    deleted += 1
                    continue
                if app_id in archive_ids:
                    conn.execute(
                        "update local_apps set tags='[]',is_public=0 where id=? and source='admin'", (app_id,)
                    )
                    archived += 1
                elif item["action"] == "replace":
                    tags = normalize_tags(item["new_tags"])
                    if normalize_tags(row["tags"]) != tags:
                        conn.execute(
                            "update local_apps set tags=? where id=? and source='admin'",
                            (json.dumps(tags, ensure_ascii=False, separators=(",", ":")), app_id),
                        )
                        changed_tags += 1
                features = item["features"]
                conn.execute(
                    """
                    insert into role_card_annotations(
                      app_id,has_opening,has_world_info,has_regex,annotation_source,annotated_at
                    ) values(?,?,?,?,?,?)
                    on conflict(app_id) do update set
                      has_opening=excluded.has_opening,has_world_info=excluded.has_world_info,
                      has_regex=excluded.has_regex,annotation_source=excluded.annotation_source,
                      annotated_at=excluded.annotated_at
                    """,
                    (app_id, int(features["opening"]), int(features["world_info"]), int(features["regex"]),
                     f"filename:{plan.get('archive_sha256')}", annotated_at),
                )
                annotations += 1
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        after = preflight(conn, plan)
        after_user_counts = {
            table: int(conn.execute(f'select count(*) from "{table}"').fetchone()[0])
            for table in before_user_counts
        }
        quick_check = str(conn.execute("pragma quick_check").fetchone()[0])
        public_clear = int(conn.execute(
            "select count(*) from local_apps where id in ({}) and is_public=1".format(
                ",".join("?" for _ in before["clear_delete_ids"] + before["clear_archive_ids"])
            ), before["clear_delete_ids"] + before["clear_archive_ids"]
        ).fetchone()[0]) if before["clear_delete_ids"] or before["clear_archive_ids"] else 0
        report.update({
            "applied": True,
            "backup": str(backup.resolve()),
            "changed_tag_rows": changed_tags,
            "deleted_clear_cards": deleted,
            "archived_clear_cards": archived,
            "annotation_upserts": annotations,
            "verify": {
                "quick_check": quick_check,
                "public_clear_cards": public_clear,
                "user_table_counts_unchanged": before_user_counts == after_user_counts,
                "user_table_counts_before": before_user_counts,
                "user_table_counts_after": after_user_counts,
                "postflight": after,
            },
        })
        return report
    finally:
        conn.close()


def write(path: Path | None, value: dict[str, Any]) -> None:
    raw = json_bytes(value)
    if path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
    print(raw.decode("utf-8"), end="")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    p_prepare = sub.add_parser("prepare")
    p_prepare.add_argument("--zip", type=Path, required=True)
    p_prepare.add_argument("--plan", type=Path, required=True)
    p_prepare.add_argument("--report", type=Path)
    p_apply = sub.add_parser("apply")
    p_apply.add_argument("--db", type=Path, required=True)
    p_apply.add_argument("--plan", type=Path, required=True)
    p_apply.add_argument("--apply", action="store_true")
    p_apply.add_argument("--backup", type=Path)
    p_apply.add_argument("--expected-plan-sha256")
    p_apply.add_argument("--report", type=Path)
    args = parser.parse_args()
    if args.command == "prepare":
        value = prepare(args.zip)
        args.plan.parent.mkdir(parents=True, exist_ok=True)
        args.plan.write_bytes(json_bytes(value))
        write(args.report, {key: value[key] for key in value if key != "items"})
        return 0
    plan = read_plan(args.plan)
    value = apply(args.db, plan, do_apply=args.apply, backup=args.backup,
                  actual_plan_sha=plan_sha256(args.plan), expected_plan_sha=args.expected_plan_sha256)
    write(args.report, value)
    return 0 if value.get("applied") or value.get("ready_to_apply") else 1


if __name__ == "__main__":
    raise SystemExit(main())
