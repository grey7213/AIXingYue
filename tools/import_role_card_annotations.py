#!/usr/bin/env python3
"""Prepare and safely apply AI星月 role-card tag/feature annotations."""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import re
import sqlite3
import time
import unicodedata
import zipfile
from collections import Counter
from pathlib import Path
from typing import Any


PLAN_SCHEMA = "ai-xingyue-role-card-annotation-plan/v1"
MANIFEST_SCHEMA = "ai-xingyue-card-tag-roundtrip/v1"
CARD_SCHEMA = "ai-xingyue-role-card-export/v1"
SCOPE_SQL = "source='admin' and status='published' and is_public=1"
FLAG_RE = re.compile(r"\[(√|✗)\]\[(√|✗)\]\[(√|✗)\]\.json$")
CARD_RE = re.compile(r"^(?P<display_id>[^/]+?)__.*\.json$")


def now_ms() -> int:
    return int(time.time() * 1000)


def json_bytes(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def parse_json(value: object, default: object) -> object:
    if value in (None, ""):
        return default
    if not isinstance(value, str):
        return value
    try:
        return json.loads(value)
    except Exception:
        return default


def normalize_tags(value: object) -> list[str]:
    parsed = parse_json(value, [])
    if not isinstance(parsed, list):
        raise ValueError("tags must be a JSON list")
    out: list[str] = []
    seen: set[str] = set()
    for raw in parsed:
        tag = unicodedata.normalize("NFC", str(raw or "")).strip()
        if not tag:
            continue
        key = tag.casefold()
        if key in seen:
            continue
        seen.add(key)
        out.append(tag)
    return out


def meaningful(value: Any) -> bool:
    if value is None or value is False:
        return False
    if isinstance(value, str):
        text = value.strip()
        if not text or text.casefold() in {"null", "none", "[]", "{}", "false"}:
            return False
        if text[:1] in "[{\"":
            try:
                return meaningful(json.loads(text))
            except Exception:
                pass
        return True
    if isinstance(value, dict):
        return any(meaningful(item) for item in value.values())
    if isinstance(value, (list, tuple, set)):
        return any(meaningful(item) for item in value)
    if isinstance(value, (int, float)):
        return value != 0
    return True


def detected_features(record: dict[str, Any]) -> dict[str, bool]:
    extra = parse_json(record.get("extra_settings"), {})
    if not isinstance(extra, dict):
        extra = {}
    return {
        "opening": bool(str(record.get("opening_statement") or "").strip()),
        "world_info": meaningful(extra.get("world_info")),
        "regex": meaningful(extra.get("regex_scripts")),
    }


def has_effective_nested_regex(record: dict[str, Any]) -> bool:
    extra = parse_json(record.get("extra_settings"), {})
    if not isinstance(extra, dict):
        return False
    extensions = extra.get("extensions")
    if not isinstance(extensions, dict):
        return False
    return any(
        meaningful(extensions.get(key))
        for key in ("regex_scripts", "TavernHelper_scripts", "tavern_helper_scripts")
    )


def archive_root(names: list[str]) -> str:
    candidates = [name[:-len("manifest.original.json")] for name in names if name.endswith("manifest.original.json")]
    if len(candidates) != 1:
        raise ValueError(f"expected one manifest.original.json, found {len(candidates)}")
    return candidates[0]


def read_manifest(zf: zipfile.ZipFile, root: str) -> tuple[dict, bytes, str]:
    raw = zf.read(root + "manifest.original.json")
    declared = zf.read(root + "manifest.original.sha256").decode("ascii", "replace").strip().split()[0]
    actual = sha256_bytes(raw)
    if actual != declared:
        raise ValueError("manifest SHA-256 mismatch")
    manifest = json.loads(raw.decode("utf-8-sig"))
    if manifest.get("schema") != MANIFEST_SCHEMA:
        raise ValueError(f"unsupported manifest schema: {manifest.get('schema')}")
    return manifest, raw, actual


def prepare(zip_path: Path) -> dict:
    archive_sha = sha256_file(zip_path)
    with zipfile.ZipFile(zip_path, "r") as zf:
        infos = zf.infolist()
        names = [item.filename for item in infos]
        if len(names) != len(set(names)):
            raise ValueError("ZIP contains duplicate archive paths")
        root = archive_root(names)
        manifest, _manifest_raw, manifest_sha = read_manifest(zf, root)
        items = manifest.get("items") or []
        if int(manifest.get("count") or 0) != len(items):
            raise ValueError("manifest count mismatch")

        by_display: dict[str, dict] = {}
        seen_internal: set[str] = set()
        for item in items:
            display_id = str(item.get("display_id") or "").strip()
            internal_id = str(item.get("internal_id") or "").strip()
            if not display_id or display_id in by_display:
                raise ValueError(f"missing or duplicate manifest display_id: {display_id!r}")
            if not internal_id or internal_id in seen_internal:
                raise ValueError(f"missing or duplicate manifest internal_id: {internal_id!r}")
            by_display[display_id] = item
            seen_internal.add(internal_id)

        csv_member = root + "tag-overrides.filled.csv"
        if csv_member not in names:
            raise ValueError("tag-overrides.filled.csv is missing")
        csv_rows = list(csv.DictReader(io.StringIO(zf.read(csv_member).decode("utf-8-sig"))))
        if len(csv_rows) != len(items):
            raise ValueError(f"filled CSV row count mismatch: {len(csv_rows)} != {len(items)}")
        csv_by_display: dict[str, dict] = {}
        for row in csv_rows:
            display_id = str(row.get("display_id_readonly") or "").strip()
            if not display_id or display_id in csv_by_display:
                raise ValueError(f"missing or duplicate CSV display_id: {display_id!r}")
            item = by_display.get(display_id)
            if not item or str(item.get("internal_id")) != str(row.get("internal_id_readonly") or ""):
                raise ValueError(f"CSV/manifest ID mismatch: {display_id}")
            csv_by_display[display_id] = row

        card_members: dict[str, str] = {}
        feature_by_display: dict[str, dict[str, bool]] = {}
        suffix_counts: Counter[str] = Counter()
        for name in names:
            if not (name.startswith(root + "cards/") and name.endswith(".json")):
                continue
            base = name.rsplit("/", 1)[-1]
            card_match = CARD_RE.match(base)
            flag_match = FLAG_RE.search(base)
            if not card_match or not flag_match:
                raise ValueError(f"unparseable card filename: {base}")
            display_id = card_match.group("display_id")
            if display_id in card_members:
                raise ValueError(f"duplicate card display_id: {display_id}")
            if display_id not in by_display:
                raise ValueError(f"unknown card display_id: {display_id}")
            flags = tuple(value == "√" for value in flag_match.groups())
            feature_by_display[display_id] = {
                "opening": flags[0],
                "world_info": flags[1],
                "regex": flags[2],
            }
            suffix_counts.update(["".join("√" if value else "✗" for value in flags)])
            card_members[display_id] = name

        if set(card_members) != set(by_display):
            missing = sorted(set(by_display) - set(card_members))
            raise ValueError(f"card/manifest membership mismatch; missing={missing[:10]}")

        plan_items: list[dict] = []
        action_counts: Counter[str] = Counter()
        tag_change_counts: Counter[str] = Counter()
        feature_counts: Counter[str] = Counter()
        effective_regex_conflicts: list[dict[str, str]] = []
        for index, manifest_item in enumerate(items, start=1):
            display_id = str(manifest_item["display_id"])
            csv_row = csv_by_display[display_id]
            raw = zf.read(card_members[display_id])
            if sha256_bytes(raw) != str(manifest_item.get("card_sha256") or ""):
                raise ValueError(f"card content SHA mismatch: {display_id}")
            payload = json.loads(raw.decode("utf-8-sig"))
            if payload.get("schema") != CARD_SCHEMA or not isinstance(payload.get("record"), dict):
                raise ValueError(f"invalid card payload: {display_id}")
            record = payload["record"]
            internal_id = str(manifest_item["internal_id"])
            if str(record.get("id") or "") != internal_id:
                raise ValueError(f"card/manifest internal ID mismatch: {display_id}")

            manual_features = feature_by_display[display_id]
            actual_features = detected_features(record)
            if manual_features != actual_features:
                raise ValueError(
                    f"manual/content feature mismatch for {display_id}: "
                    f"manual={manual_features}, actual={actual_features}"
                )

            original_tags = normalize_tags(manifest_item.get("original_tags") or [])
            if str(csv_row.get("card_ref") or "").strip() != f"id:{display_id}":
                raise ValueError(f"CSV card_ref mismatch: {display_id}")
            csv_original_tags = normalize_tags(csv_row.get("original_tags_json_readonly") or "[]")
            if csv_original_tags != original_tags:
                raise ValueError(f"CSV original tags mismatch: {display_id}")
            action = str(csv_row.get("action") or "skip").strip().lower()
            if action not in {"replace", "skip"}:
                raise ValueError(f"unsupported CSV action for {display_id}: {action}")
            if action == "replace":
                new_tags = normalize_tags(csv_row.get("new_tags_json") or "[]")
            else:
                new_tags = original_tags
            action_counts.update([action])
            tag_change_counts.update(["changed" if new_tags != original_tags else "unchanged"])
            for key, enabled in manual_features.items():
                feature_counts.update([key + ("_yes" if enabled else "_no")])
            if not manual_features["regex"] and has_effective_nested_regex(record):
                effective_regex_conflicts.append({
                    "display_id": display_id,
                    "internal_id": internal_id,
                    "name": str(manifest_item.get("name") or record.get("name") or ""),
                })
            plan_items.append({
                "internal_id": internal_id,
                "display_id": display_id,
                "name": str(manifest_item.get("name") or record.get("name") or ""),
                "source": str(manifest_item.get("source") or ""),
                "status": str(manifest_item.get("status") or ""),
                "is_public": bool(manifest_item.get("is_public")),
                "expected_updated_at": int(manifest_item.get("db_updated_at") or 0),
                "expected_original_tags": original_tags,
                "action": action,
                "new_tags": new_tags,
                "features": manual_features,
                "card_sha256": str(manifest_item.get("card_sha256") or ""),
                "source_filename": card_members[display_id].rsplit("/", 1)[-1],
            })
            if index % 1000 == 0:
                print(f"prepared {index}/{len(items)}", flush=True)

    return {
        "schema": PLAN_SCHEMA,
        "prepared_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "archive": str(zip_path.resolve()),
        "archive_size": zip_path.stat().st_size,
        "archive_sha256": archive_sha,
        "manifest_sha256": manifest_sha,
        "scope_sql": SCOPE_SQL,
        "count": len(plan_items),
        "stats": {
            "actions": dict(action_counts),
            "tag_changes": dict(tag_change_counts),
            "feature_suffixes": dict(sorted(suffix_counts.items())),
            "features": dict(sorted(feature_counts.items())),
            "effective_nested_regex_conflict_count": len(effective_regex_conflicts),
            "effective_nested_regex_conflict_samples": effective_regex_conflicts[:50],
        },
        "items": plan_items,
    }


def read_plan(path: Path) -> dict:
    plan = json.loads(path.read_text(encoding="utf-8-sig"))
    if plan.get("schema") != PLAN_SCHEMA:
        raise ValueError(f"unsupported plan schema: {plan.get('schema')}")
    items = plan.get("items")
    if not isinstance(items, list) or len(items) != int(plan.get("count") or -1):
        raise ValueError("plan count mismatch")
    return plan


def db_rows(conn: sqlite3.Connection) -> dict[str, sqlite3.Row]:
    rows = conn.execute(
        f"select id,display_id,source,status,is_public,tags,updated_at from local_apps where {SCOPE_SQL}"
    ).fetchall()
    return {str(row["id"]): row for row in rows}


def preflight(conn: sqlite3.Connection, plan: dict) -> dict:
    rows = db_rows(conn)
    conflicts: list[dict] = []
    replace_count = 0
    changed_count = 0
    for item in plan["items"]:
        internal_id = str(item["internal_id"])
        row = rows.get(internal_id)
        if row is None:
            conflicts.append({"internal_id": internal_id, "display_id": item["display_id"], "reason": "missing"})
            continue
        if str(row["display_id"] or "") != str(item["display_id"]):
            conflicts.append({"internal_id": internal_id, "reason": "display_id_changed"})
        if int(row["updated_at"] or 0) != int(item["expected_updated_at"] or 0):
            conflicts.append({"internal_id": internal_id, "reason": "updated_at_changed"})
        current_tags = normalize_tags(row["tags"])
        if current_tags != normalize_tags(item["expected_original_tags"]):
            conflicts.append({"internal_id": internal_id, "reason": "tags_changed"})
        if item["action"] == "replace":
            replace_count += 1
            if current_tags != normalize_tags(item["new_tags"]):
                changed_count += 1
    expected_ids = {str(item["internal_id"]) for item in plan["items"]}
    extra_ids = sorted(set(rows) - expected_ids)
    if extra_ids:
        conflicts.append({"reason": "unexpected_scope_rows", "count": len(extra_ids), "samples": extra_ids[:20]})
    return {
        "database_scope_count": len(rows),
        "plan_count": len(plan["items"]),
        "replace_count": replace_count,
        "tag_rows_requiring_change": changed_count,
        "annotation_rows": len(plan["items"]),
        "conflict_count": len(conflicts),
        "conflicts": conflicts[:100],
    }


def online_backup(conn: sqlite3.Connection, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise FileExistsError(f"refusing to overwrite backup: {path}")
    target = sqlite3.connect(path)
    try:
        conn.backup(target)
    finally:
        target.close()


def apply_plan(
    db_path: Path,
    plan: dict,
    *,
    do_apply: bool,
    backup_path: Path | None,
    plan_sha256: str,
    expected_plan_sha256: str | None,
) -> dict:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        before = preflight(conn, plan)
        report: dict[str, Any] = {
            "schema": PLAN_SCHEMA,
            "mode": "apply" if do_apply else "dry-run",
            "db": str(db_path.resolve()),
            "manifest_sha256": plan.get("manifest_sha256"),
            "archive_sha256": plan.get("archive_sha256"),
            "plan_sha256": plan_sha256,
            "preflight": before,
        }
        if expected_plan_sha256 and plan_sha256.casefold() != expected_plan_sha256.strip().casefold():
            report["applied"] = False
            report["ready_to_apply"] = False
            report["plan_sha256_mismatch"] = True
            return report
        if before["conflict_count"]:
            report["applied"] = False
            return report
        if not do_apply:
            report["applied"] = False
            report["ready_to_apply"] = True
            return report
        if backup_path is None:
            raise ValueError("--backup is required with --apply")
        online_backup(conn, backup_path)

        changed_tags = 0
        annotation_rows = 0
        annotated_at = now_ms()
        conn.execute("begin immediate")
        try:
            locked_preflight = preflight(conn, plan)
            if locked_preflight["conflict_count"]:
                raise RuntimeError(f"transaction preflight conflicts: {locked_preflight['conflict_count']}")
            conn.execute(
                """
                create table if not exists role_card_annotations (
                    app_id text primary key,
                    has_opening integer not null,
                    has_world_info integer not null,
                    has_regex integer not null,
                    annotation_source text not null,
                    annotated_at integer not null
                )
                """
            )
            for item in plan["items"]:
                internal_id = str(item["internal_id"])
                if item["action"] == "replace":
                    new_tags = normalize_tags(item["new_tags"])
                    current = conn.execute("select tags from local_apps where id=?", (internal_id,)).fetchone()
                    if normalize_tags(current["tags"]) != new_tags:
                        updated = conn.execute(
                            """
                            update local_apps set tags=?
                            where id=? and display_id=? and updated_at=?
                              and source='admin' and status='published' and is_public=1
                            """,
                            (
                                json.dumps(new_tags, ensure_ascii=False, separators=(",", ":")),
                                internal_id,
                                str(item["display_id"]),
                                int(item["expected_updated_at"] or 0),
                            ),
                        )
                        if updated.rowcount != 1:
                            raise RuntimeError(f"conditional tag update failed: {internal_id}")
                        changed_tags += 1
                features = item["features"]
                conn.execute(
                    """
                    insert into role_card_annotations(
                        app_id,has_opening,has_world_info,has_regex,annotation_source,annotated_at
                    ) values(?,?,?,?,?,?)
                    on conflict(app_id) do update set
                        has_opening=excluded.has_opening,
                        has_world_info=excluded.has_world_info,
                        has_regex=excluded.has_regex,
                        annotation_source=excluded.annotation_source,
                        annotated_at=excluded.annotated_at
                    """,
                    (
                        internal_id,
                        1 if features.get("opening") else 0,
                        1 if features.get("world_info") else 0,
                        1 if features.get("regex") else 0,
                        f"manifest:{plan.get('manifest_sha256')}",
                        annotated_at,
                    ),
                )
                annotation_rows += 1
            conn.commit()
        except Exception:
            conn.rollback()
            raise

        annotation_rows_db = conn.execute(
            """
            select ra.app_id,ra.has_opening,ra.has_world_info,ra.has_regex
            from role_card_annotations ra
            join local_apps a on a.id=ra.app_id
            where a.source='admin' and a.status='published' and a.is_public=1
            """
        ).fetchall()
        annotations = {str(row["app_id"]): row for row in annotation_rows_db}
        after_rows = db_rows(conn)
        tag_mismatches = []
        annotation_mismatches = []
        for item in plan["items"]:
            internal_id = str(item["internal_id"])
            if item["action"] != "replace":
                pass
            else:
                current_tags = normalize_tags(after_rows[internal_id]["tags"])
                if current_tags != normalize_tags(item["new_tags"]):
                    tag_mismatches.append(internal_id)
            annotation = annotations.get(internal_id)
            expected_features = item["features"]
            if annotation is None or {
                "opening": bool(annotation["has_opening"]),
                "world_info": bool(annotation["has_world_info"]),
                "regex": bool(annotation["has_regex"]),
            } != expected_features:
                annotation_mismatches.append(internal_id)
        report.update({
            "applied": True,
            "backup": str(backup_path.resolve()),
            "changed_tag_rows": changed_tags,
            "annotation_upserts": annotation_rows,
            "verify": {
                "annotation_count": len(annotations),
                "has_opening": sum(bool(row["has_opening"]) for row in annotation_rows_db),
                "has_world_info": sum(bool(row["has_world_info"]) for row in annotation_rows_db),
                "has_regex": sum(bool(row["has_regex"]) for row in annotation_rows_db),
                "tag_mismatch_count": len(tag_mismatches),
                "tag_mismatch_samples": tag_mismatches[:20],
                "annotation_mismatch_count": len(annotation_mismatches),
                "annotation_mismatch_samples": annotation_mismatches[:20],
            },
        })
        return report
    finally:
        conn.close()


def write_report(path: Path | None, value: dict) -> None:
    rendered = json_bytes(value)
    if path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(rendered)
    print(rendered.decode("utf-8"), end="")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    prepare_parser = sub.add_parser("prepare", help="Validate the returned ZIP and create an import plan.")
    prepare_parser.add_argument("--zip", type=Path, required=True)
    prepare_parser.add_argument("--plan", type=Path, required=True)
    prepare_parser.add_argument("--report", type=Path)

    apply_parser = sub.add_parser("apply", help="Dry-run or apply a prepared plan to SQLite.")
    apply_parser.add_argument("--db", type=Path, required=True)
    apply_parser.add_argument("--plan", type=Path, required=True)
    apply_parser.add_argument("--apply", action="store_true", dest="do_apply")
    apply_parser.add_argument("--backup", type=Path)
    apply_parser.add_argument("--expected-plan-sha256")
    apply_parser.add_argument("--report", type=Path)

    args = parser.parse_args()
    if args.command == "prepare":
        plan = prepare(args.zip)
        args.plan.parent.mkdir(parents=True, exist_ok=True)
        args.plan.write_bytes(json_bytes(plan))
        write_report(args.report, {key: value for key, value in plan.items() if key != "items"})
        return 0

    if args.do_apply and not args.expected_plan_sha256:
        parser.error("--expected-plan-sha256 is required with --apply")
    plan_sha256 = sha256_file(args.plan)
    plan = read_plan(args.plan)
    result = apply_plan(
        args.db,
        plan,
        do_apply=args.do_apply,
        backup_path=args.backup,
        plan_sha256=plan_sha256,
        expected_plan_sha256=args.expected_plan_sha256,
    )
    write_report(args.report, result)
    clean = result.get("preflight", {}).get("conflict_count", 1) == 0 and not result.get("plan_sha256_mismatch")
    return 0 if clean else 2


if __name__ == "__main__":
    raise SystemExit(main())
