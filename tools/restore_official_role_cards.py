#!/usr/bin/env python3
"""Prepare, restore, and verify the complete Homer official role-card archive."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sqlite3
import stat
import time
import unicodedata
import zipfile
from collections import Counter
from pathlib import Path, PurePosixPath
from typing import Any, Iterable


PLAN_SCHEMA = "homer-official-role-card-restore-plan/v1"
MANIFEST_SCHEMA = "ai-xingyue-card-tag-roundtrip/v1"
CARD_SCHEMA = "ai-xingyue-role-card-export/v1"
TARGET_SOURCE = "admin"
TARGET_STATUS = "published"
TARGET_PUBLIC = 1
TARGET_TABLES = {"local_apps", "content_versions", "role_card_annotations"}
JSON_COLUMNS = {"tags", "suggested_questions", "extra_settings"}
SNAPSHOT_FIELDS = (
    "display_id", "source", "owner_user_id", "name", "summary", "description",
    "cover_url", "cover_origin", "tags", "opening_statement", "suggested_questions",
    "pre_prompt", "llm_model", "api_base_url", "age_rating", "gender", "language",
    "status", "is_public", "sort_weight", "official_recommended", "extra_settings",
)
LOCAL_APP_COLUMNS = (
    "id", "display_id", "source", "owner_user_id", "name", "summary", "description",
    "cover_url", "cover_origin", "tags", "opening_statement", "suggested_questions",
    "pre_prompt", "llm_model", "api_base_url", "age_rating", "gender", "language",
    "players_count", "like_count", "status", "is_public", "sort_weight",
    "official_recommended", "extra_settings", "created_at", "updated_at",
    "current_version_id",
)
REQUIRED_LOCAL_APP_COLUMNS = set(LOCAL_APP_COLUMNS)
REQUIRED_CONTENT_VERSION_COLUMNS = {
    "id", "entity_type", "entity_id", "version_no", "version_name",
    "author_description", "snapshot_json", "content_hash", "created_by", "created_at",
}
REQUIRED_ANNOTATION_COLUMNS = {
    "app_id", "has_opening", "has_world_info", "has_regex",
    "annotation_source", "annotated_at",
}


def now_ms() -> int:
    return int(time.time() * 1000)


def json_bytes(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def compact_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


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


def normalized_text(value: object) -> str:
    return unicodedata.normalize("NFC", str(value or "")).strip()


def normalize_tags(value: object) -> list[str]:
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except (TypeError, ValueError):
            value = []
    if not isinstance(value, list):
        raise ValueError("tags must be a JSON list")
    out: list[str] = []
    seen: set[str] = set()
    for raw in value:
        tag = normalized_text(raw)
        if not tag:
            continue
        key = tag.casefold()
        if key in seen:
            continue
        seen.add(key)
        out.append(tag)
    return out


def json_object(value: object, *, field: str) -> dict[str, Any]:
    if value in (None, ""):
        return {}
    if isinstance(value, str):
        value = json.loads(value)
    if not isinstance(value, dict):
        raise ValueError(f"{field} must be an object")
    return value


def json_list(value: object, *, field: str) -> list[Any]:
    if value in (None, ""):
        return []
    if isinstance(value, str):
        value = json.loads(value)
    if not isinstance(value, list):
        raise ValueError(f"{field} must be a list")
    return value


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
            except (TypeError, ValueError):
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
    extra = json_object(record.get("extra_settings"), field="extra_settings")
    return {
        "opening": bool(str(record.get("opening_statement") or "").strip()),
        "world_info": meaningful(extra.get("world_info")),
        "regex": meaningful(extra.get("regex_scripts")),
    }


def safe_archive_member(name: str) -> bool:
    if not name or "\x00" in name or "\\" in name:
        return False
    path = PurePosixPath(name)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        return False
    return not (len(path.parts) and path.parts[0].endswith(":"))


def validate_zip_members(infos: Iterable[zipfile.ZipInfo]) -> None:
    names: set[str] = set()
    for info in infos:
        if info.filename in names:
            raise ValueError(f"duplicate ZIP path: {info.filename}")
        names.add(info.filename)
        if not safe_archive_member(info.filename.rstrip("/")):
            raise ValueError(f"unsafe ZIP path: {info.filename}")
        mode = (info.external_attr >> 16) & 0xFFFF
        if mode and stat.S_ISLNK(mode):
            raise ValueError(f"ZIP symlink is not allowed: {info.filename}")


def archive_root(names: list[str]) -> str:
    candidates = [name[:-len("manifest.original.json")] for name in names if name.endswith("manifest.original.json")]
    if len(candidates) != 1:
        raise ValueError(f"expected one manifest.original.json, found {len(candidates)}")
    return candidates[0]


def read_manifest(zf: zipfile.ZipFile, root: str) -> tuple[dict[str, Any], str]:
    raw = zf.read(root + "manifest.original.json")
    declared = zf.read(root + "manifest.original.sha256").decode("ascii", "replace").strip().split()[0]
    actual = sha256_bytes(raw)
    if declared.casefold() != actual.casefold():
        raise ValueError("manifest SHA-256 mismatch")
    manifest = json.loads(raw.decode("utf-8-sig"))
    if manifest.get("schema") != MANIFEST_SCHEMA:
        raise ValueError(f"unsupported manifest schema: {manifest.get('schema')}")
    items = manifest.get("items")
    if not isinstance(items, list) or int(manifest.get("count") or -1) != len(items):
        raise ValueError("manifest count mismatch")
    return manifest, actual


def deterministic_version_id(internal_id: str) -> str:
    digest = hashlib.sha256(("homer-official-restore:" + internal_id).encode("utf-8")).hexdigest()
    return "cver_" + digest[:16]


def int_value(value: object, default: int = 0) -> int:
    try:
        return int(value if value not in (None, "") else default)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"invalid integer value: {value!r}") from exc


def prepared_row(record: dict[str, Any], display_id: str, version_id: str) -> dict[str, Any]:
    internal_id = normalized_text(record.get("id"))
    name = str(record.get("name") or "").strip()
    if not internal_id or not name:
        raise ValueError("record id/name is required")
    tags = normalize_tags(record.get("tags") or [])
    questions = json_list(record.get("suggested_questions"), field="suggested_questions")
    extra = json_object(record.get("extra_settings"), field="extra_settings")
    api_base_url = str(record.get("api_base_url") or "").strip()
    llm_model = str(record.get("llm_model") or "").strip()
    if api_base_url:
        raise ValueError(f"official role must not carry api_base_url: {internal_id}")
    if llm_model.startswith("user:"):
        raise ValueError(f"official role must not carry a user model preset: {internal_id}")
    created = int_value(record.get("created_at"), now_ms())
    updated = int_value(record.get("updated_at"), created)
    return {
        "id": internal_id,
        "display_id": display_id,
        "source": TARGET_SOURCE,
        "owner_user_id": None,
        "name": name,
        "summary": str(record.get("summary") or ""),
        "description": str(record.get("description") or ""),
        "cover_url": str(record.get("cover_url") or "").strip(),
        "cover_origin": str(record.get("cover_origin") or ""),
        "tags": compact_json(tags),
        "opening_statement": str(record.get("opening_statement") or ""),
        "suggested_questions": compact_json(questions),
        "pre_prompt": str(record.get("pre_prompt") or ""),
        "llm_model": llm_model,
        "api_base_url": "",
        "age_rating": int_value(record.get("age_rating"), 0),
        "gender": int_value(record.get("gender"), 0),
        "language": str(record.get("language") or "zh-Hans"),
        "players_count": int_value(record.get("players_count"), 0),
        "like_count": int_value(record.get("like_count"), 0),
        "status": TARGET_STATUS,
        "is_public": TARGET_PUBLIC,
        "sort_weight": int_value(record.get("sort_weight"), 0),
        "official_recommended": 0,
        "extra_settings": compact_json(extra) if extra else None,
        "created_at": created,
        "updated_at": updated,
        "current_version_id": version_id,
    }


def semantic_projection(row: dict[str, Any]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key in LOCAL_APP_COLUMNS:
        if key == "current_version_id":
            continue
        item = row.get(key)
        if key == "tags":
            item = normalize_tags(item or [])
        elif key == "suggested_questions":
            item = json_list(item, field=key)
        elif key == "extra_settings":
            item = json_object(item, field=key)
        value[key] = item
    return value


def projection_sha256(row: dict[str, Any]) -> str:
    raw = json.dumps(semantic_projection(row), ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def version_payload(row: dict[str, Any]) -> tuple[str, str]:
    snapshot = {key: row.get(key) for key in SNAPSHOT_FIELDS}
    blob = json.dumps(snapshot, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    return blob, hashlib.sha256(blob.encode("utf-8")).hexdigest()


def load_card_payload(zf: zipfile.ZipFile, member: str) -> tuple[bytes, dict[str, Any]]:
    raw = zf.read(member)
    payload = json.loads(raw.decode("utf-8-sig"))
    if payload.get("schema") != CARD_SCHEMA or not isinstance(payload.get("record"), dict):
        raise ValueError(f"invalid role-card payload: {member}")
    return raw, payload["record"]


def prepare(zip_path: Path) -> dict[str, Any]:
    archive_sha = sha256_file(zip_path)
    with zipfile.ZipFile(zip_path, "r") as zf:
        infos = zf.infolist()
        validate_zip_members(infos)
        bad_crc = zf.testzip()
        if bad_crc:
            raise ValueError(f"ZIP CRC failure: {bad_crc}")
        names = [info.filename for info in infos]
        root = archive_root(names)
        manifest, manifest_sha = read_manifest(zf, root)
        manifest_items = manifest["items"]

        by_internal: dict[str, dict[str, Any]] = {}
        by_display: dict[str, str] = {}
        for item in manifest_items:
            internal_id = normalized_text(item.get("internal_id"))
            display_id = normalized_text(item.get("display_id"))
            if not internal_id or internal_id in by_internal:
                raise ValueError(f"missing or duplicate manifest internal ID: {internal_id!r}")
            if not display_id or display_id in by_display:
                raise ValueError(f"missing or duplicate manifest display ID: {display_id!r}")
            if str(item.get("source")) != TARGET_SOURCE or str(item.get("status")) != TARGET_STATUS or not item.get("is_public"):
                raise ValueError(f"manifest scope changed: {display_id}")
            by_internal[internal_id] = item
            by_display[display_id] = internal_id

        card_members: dict[str, tuple[str, str]] = {}
        for name in names:
            rel = name[len(root):] if name.startswith(root) else name
            if rel.startswith("cards/") and rel.endswith(".json"):
                kind = "active"
            elif rel.startswith("removed-cards-refinement/") and rel.endswith(".json"):
                kind = "recovered"
            else:
                continue
            raw, record = load_card_payload(zf, name)
            internal_id = normalized_text(record.get("id"))
            if internal_id not in by_internal:
                raise ValueError(f"unknown card internal ID: {internal_id}")
            if internal_id in card_members:
                raise ValueError(f"duplicate card internal ID: {internal_id}")
            manifest_name = str(by_internal[internal_id].get("name") or "")
            if str(record.get("name") or "") != manifest_name:
                raise ValueError(f"card/manifest name mismatch: {internal_id}")
            card_members[internal_id] = (name, kind)

        if set(card_members) != set(by_internal):
            missing = sorted(set(by_internal) - set(card_members))
            extra = sorted(set(card_members) - set(by_internal))
            raise ValueError(f"card membership mismatch; missing={missing[:10]}, extra={extra[:10]}")

        items: list[dict[str, Any]] = []
        kind_counts: Counter[str] = Counter()
        feature_counts: Counter[str] = Counter()
        tag_counts: Counter[str] = Counter()
        cover_counts: Counter[str] = Counter()
        display_mismatch = 0
        for index, manifest_item in enumerate(manifest_items, start=1):
            internal_id = str(manifest_item["internal_id"])
            display_id = str(manifest_item["display_id"])
            member, kind = card_members[internal_id]
            raw, record = load_card_payload(zf, member)
            version_id = deterministic_version_id(internal_id)
            row = prepared_row(record, display_id, version_id)
            features = detected_features(record)
            tags = normalize_tags(record.get("tags") or [])
            kind_counts[kind] += 1
            display_mismatch += int(str(record.get("display_id") or "") != display_id)
            for key, enabled in features.items():
                feature_counts[key + ("_yes" if enabled else "_no")] += 1
            tag_counts.update(tags)
            cover_url = row["cover_url"]
            if not cover_url:
                cover_kind = "empty"
                cover_basename = ""
            elif "patcher.villainy.top/media-cache/cover/" in cover_url:
                cover_kind = "local"
                cover_basename = cover_url.rsplit("/", 1)[-1]
            else:
                cover_kind = "external"
                cover_basename = ""
            cover_counts[cover_kind] += 1
            items.append({
                "internal_id": internal_id,
                "display_id": display_id,
                "name": row["name"],
                "member": member,
                "member_kind": kind,
                "member_sha256": sha256_bytes(raw),
                "row_sha256": projection_sha256(row),
                "version_id": version_id,
                "tags": tags,
                "features": features,
                "cover_kind": cover_kind,
                "cover_basename": cover_basename,
            })
            if index % 500 == 0 or index == len(manifest_items):
                print(f"prepared {index}/{len(manifest_items)}", flush=True)

    return {
        "schema": PLAN_SCHEMA,
        "prepared_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "archive": str(zip_path.resolve()),
        "archive_size": zip_path.stat().st_size,
        "archive_sha256": archive_sha,
        "manifest_sha256": manifest_sha,
        "archive_root": root,
        "count": len(items),
        "stats": {
            "member_kinds": dict(sorted(kind_counts.items())),
            "record_display_id_mismatch_count": display_mismatch,
            "features": dict(sorted(feature_counts.items())),
            "covers": dict(sorted(cover_counts.items())),
            "unique_tags": len(tag_counts),
            "top_tags": tag_counts.most_common(100),
        },
        "items": items,
    }


def read_plan(path: Path) -> dict[str, Any]:
    plan = json.loads(path.read_text(encoding="utf-8-sig"))
    if plan.get("schema") != PLAN_SCHEMA:
        raise ValueError(f"unsupported plan schema: {plan.get('schema')}")
    items = plan.get("items")
    if not isinstance(items, list) or int(plan.get("count") or -1) != len(items):
        raise ValueError("plan count mismatch")
    if len({str(item.get("internal_id")) for item in items}) != len(items):
        raise ValueError("plan internal IDs are not unique")
    if len({str(item.get("display_id")) for item in items}) != len(items):
        raise ValueError("plan display IDs are not unique")
    return plan


def table_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {str(row[1]) for row in conn.execute(f'pragma table_info("{table}")')}


def require_schema(conn: sqlite3.Connection) -> None:
    tables = {str(row[0]) for row in conn.execute("select name from sqlite_master where type='table'")}
    for table in TARGET_TABLES:
        if table not in tables:
            raise ValueError(f"required table is missing: {table}")
    checks = {
        "local_apps": REQUIRED_LOCAL_APP_COLUMNS,
        "content_versions": REQUIRED_CONTENT_VERSION_COLUMNS,
        "role_card_annotations": REQUIRED_ANNOTATION_COLUMNS,
    }
    for table, required in checks.items():
        missing = sorted(required - table_columns(conn, table))
        if missing:
            raise ValueError(f"{table} is missing columns: {missing}")


def chunks(values: list[str], size: int = 700) -> Iterable[list[str]]:
    for start in range(0, len(values), size):
        yield values[start:start + size]


def rows_for_ids(conn: sqlite3.Connection, table: str, column: str, values: list[str], fields: str) -> list[sqlite3.Row]:
    rows: list[sqlite3.Row] = []
    for part in chunks(values):
        marks = ",".join("?" for _ in part)
        rows.extend(conn.execute(f'select {fields} from "{table}" where "{column}" in ({marks})', part).fetchall())
    return rows


def protected_counts(conn: sqlite3.Connection) -> dict[str, int]:
    tables = [str(row[0]) for row in conn.execute(
        "select name from sqlite_master where type='table' and name not like 'sqlite_%' order by name"
    )]
    return {
        table: int(conn.execute(f'select count(*) from "{table}"').fetchone()[0])
        for table in tables if table not in TARGET_TABLES
    }


def business_guard(conn: sqlite3.Connection) -> dict[str, Any]:
    out: dict[str, Any] = {"protected_table_counts": protected_counts(conn)}
    user_cols = table_columns(conn, "users") if "users" in out["protected_table_counts"] else set()
    sums = [name for name in ("free_points", "paid_points", "reward_points", "points") if name in user_cols]
    if sums:
        select = ",".join(f"coalesce(sum({name}),0) as {name}" for name in sums)
        row = conn.execute(f"select {select} from users").fetchone()
        out["user_balance_sums"] = {name: int(row[name] or 0) for name in sums}
    return out


def preflight(conn: sqlite3.Connection, plan: dict[str, Any]) -> dict[str, Any]:
    require_schema(conn)
    items = plan["items"]
    ids = [str(item["internal_id"]) for item in items]
    displays = [str(item["display_id"]) for item in items]
    versions = [str(item["version_id"]) for item in items]
    existing_ids = rows_for_ids(conn, "local_apps", "id", ids, "id,display_id,source")
    existing_displays = rows_for_ids(conn, "local_apps", "display_id", displays, "id,display_id,source")
    existing_versions = rows_for_ids(conn, "content_versions", "id", versions, "id,entity_type,entity_id")
    existing_entity_versions = rows_for_ids(
        conn, "content_versions", "entity_id", ids, "id,entity_type,entity_id"
    )
    target_annotations = rows_for_ids(conn, "role_card_annotations", "app_id", ids, "app_id")
    quick_check = str(conn.execute("pragma quick_check").fetchone()[0])
    conflicts: list[dict[str, Any]] = []
    for row in existing_ids[:50]:
        conflicts.append({"reason": "target_internal_id_exists", "id": row["id"], "display_id": row["display_id"]})
    for row in existing_displays[:50]:
        conflicts.append({"reason": "target_display_id_exists", "id": row["id"], "display_id": row["display_id"]})
    for row in existing_versions[:50]:
        conflicts.append({"reason": "target_version_id_exists", "id": row["id"], "entity_id": row["entity_id"]})
    for row in existing_entity_versions[:50]:
        conflicts.append({"reason": "target_entity_has_version", "id": row["id"], "entity_id": row["entity_id"]})
    for row in target_annotations[:50]:
        conflicts.append({"reason": "target_annotation_exists", "app_id": row["app_id"]})
    if quick_check != "ok":
        conflicts.append({"reason": "quick_check_failed", "value": quick_check})
    return {
        "quick_check": quick_check,
        "existing_local_apps": int(conn.execute("select count(*) from local_apps").fetchone()[0]),
        "existing_official_public": int(conn.execute(
            "select count(*) from local_apps where source='admin' and status='published' and is_public=1"
        ).fetchone()[0]),
        "target_internal_id_conflicts": len(existing_ids),
        "target_display_id_conflicts": len(existing_displays),
        "target_version_id_conflicts": len(existing_versions),
        "target_entity_version_conflicts": len(existing_entity_versions),
        "target_annotation_conflicts": len(target_annotations),
        "conflict_count": len(existing_ids) + len(existing_displays) + len(existing_versions) + len(existing_entity_versions) + len(target_annotations) + int(quick_check != "ok"),
        "conflicts": conflicts[:100],
    }


def online_backup(conn: sqlite3.Connection, path: Path) -> dict[str, Any]:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise FileExistsError(f"refusing to overwrite backup: {path}")
    target = sqlite3.connect(path)
    try:
        conn.backup(target)
        target.commit()
    finally:
        target.close()
    verify = sqlite3.connect(f"file:{path.resolve().as_posix()}?mode=ro&immutable=1", uri=True)
    try:
        quick = str(verify.execute("pragma quick_check").fetchone()[0])
    finally:
        verify.close()
    if quick != "ok":
        raise RuntimeError(f"backup quick_check failed: {quick}")
    return {"path": str(path.resolve()), "size": path.stat().st_size, "sha256": sha256_file(path), "quick_check": quick}


def write_authorizer(action: int, arg1: str | None, _arg2: str | None, _db: str | None, _source: str | None) -> int:
    if action in {sqlite3.SQLITE_INSERT, sqlite3.SQLITE_UPDATE, sqlite3.SQLITE_DELETE}:
        if str(arg1 or "") not in TARGET_TABLES:
            return sqlite3.SQLITE_DENY
    return sqlite3.SQLITE_OK


def database_row_dict(row: sqlite3.Row) -> dict[str, Any]:
    return {key: row[key] for key in row.keys()}


def verify_database(conn: sqlite3.Connection, plan: dict[str, Any]) -> dict[str, Any]:
    conn.row_factory = sqlite3.Row
    ids = [str(item["internal_id"]) for item in plan["items"]]
    expected = {str(item["internal_id"]): item for item in plan["items"]}
    found_rows = rows_for_ids(conn, "local_apps", "id", ids, "*")
    found = {str(row["id"]): row for row in found_rows}
    missing = sorted(set(expected) - set(found))
    row_mismatches: list[str] = []
    display_mismatches: list[str] = []
    current_version_mismatches: list[str] = []
    for internal_id, item in expected.items():
        row = found.get(internal_id)
        if row is None:
            continue
        row_dict = database_row_dict(row)
        if projection_sha256(row_dict) != str(item["row_sha256"]):
            row_mismatches.append(internal_id)
        if str(row["display_id"] or "") != str(item["display_id"]):
            display_mismatches.append(internal_id)
        if str(row["current_version_id"] or "") != str(item["version_id"]):
            current_version_mismatches.append(internal_id)

    version_rows = rows_for_ids(
        conn, "content_versions", "entity_id", ids,
        "id,entity_type,entity_id,version_no,snapshot_json,content_hash"
    )
    versions_by_entity = {str(row["entity_id"]): row for row in version_rows if str(row["entity_type"]) == "character"}
    version_mismatches: list[str] = []
    for internal_id, item in expected.items():
        row = versions_by_entity.get(internal_id)
        app = found.get(internal_id)
        if row is None or app is None:
            version_mismatches.append(internal_id)
            continue
        blob, digest = version_payload(database_row_dict(app))
        if (
            str(row["id"]) != str(item["version_id"])
            or int(row["version_no"] or 0) != 1
            or str(row["snapshot_json"] or "") != blob
            or str(row["content_hash"] or "") != digest
        ):
            version_mismatches.append(internal_id)

    annotation_rows = rows_for_ids(
        conn, "role_card_annotations", "app_id", ids,
        "app_id,has_opening,has_world_info,has_regex"
    )
    annotations = {str(row["app_id"]): row for row in annotation_rows}
    annotation_mismatches: list[str] = []
    for internal_id, item in expected.items():
        row = annotations.get(internal_id)
        wanted = item["features"]
        actual = None if row is None else {
            "opening": bool(row["has_opening"]),
            "world_info": bool(row["has_world_info"]),
            "regex": bool(row["has_regex"]),
        }
        if actual != wanted:
            annotation_mismatches.append(internal_id)

    display_values = [str(row["display_id"] or "") for row in found_rows]
    expected_displays = {str(item["display_id"]) for item in plan["items"]}
    quick = str(conn.execute("pragma quick_check").fetchone()[0])
    official_public = int(conn.execute(
        "select count(*) from local_apps where source='admin' and status='published' and is_public=1"
    ).fetchone()[0])
    return {
        "quick_check": quick,
        "target_rows": len(found_rows),
        "official_public_rows": official_public,
        "unique_internal_ids": len(found),
        "unique_display_ids": len(set(display_values)),
        "display_set_matches": set(display_values) == expected_displays,
        "display_min": min(display_values) if display_values else None,
        "display_max": max(display_values) if display_values else None,
        "missing_count": len(missing),
        "missing_samples": missing[:20],
        "row_mismatch_count": len(row_mismatches),
        "row_mismatch_samples": row_mismatches[:20],
        "display_mismatch_count": len(display_mismatches),
        "display_mismatch_samples": display_mismatches[:20],
        "current_version_mismatch_count": len(current_version_mismatches),
        "current_version_mismatch_samples": current_version_mismatches[:20],
        "version_count": len(versions_by_entity),
        "version_mismatch_count": len(version_mismatches),
        "version_mismatch_samples": version_mismatches[:20],
        "annotation_count": len(annotations),
        "annotation_mismatch_count": len(annotation_mismatches),
        "annotation_mismatch_samples": annotation_mismatches[:20],
        "ok": all((
            quick == "ok",
            len(found_rows) == len(plan["items"]),
            official_public >= len(plan["items"]),
            len(found) == len(plan["items"]),
            len(set(display_values)) == len(plan["items"]),
            set(display_values) == expected_displays,
            not missing,
            not row_mismatches,
            not display_mismatches,
            not current_version_mismatches,
            len(versions_by_entity) == len(plan["items"]),
            not version_mismatches,
            len(annotations) == len(plan["items"]),
            not annotation_mismatches,
        )),
    }


def apply_restore(
    db_path: Path,
    zip_path: Path,
    plan: dict[str, Any],
    *,
    do_apply: bool,
    backup_path: Path | None,
    actual_plan_sha256: str,
    expected_plan_sha256: str | None,
) -> dict[str, Any]:
    if sha256_file(zip_path).casefold() != str(plan.get("archive_sha256") or "").casefold():
        raise ValueError("archive SHA-256 differs from plan")
    conn = sqlite3.connect(db_path, timeout=60)
    conn.row_factory = sqlite3.Row
    conn.execute("pragma foreign_keys=on")
    conn.execute("pragma busy_timeout=60000")
    try:
        before = preflight(conn, plan)
        guards_before = business_guard(conn)
        report: dict[str, Any] = {
            "schema": PLAN_SCHEMA,
            "mode": "apply" if do_apply else "dry-run",
            "db": str(db_path.resolve()),
            "archive_sha256": plan.get("archive_sha256"),
            "manifest_sha256": plan.get("manifest_sha256"),
            "plan_sha256": actual_plan_sha256,
            "preflight": before,
            "business_guard_before": guards_before,
        }
        if expected_plan_sha256 and actual_plan_sha256.casefold() != expected_plan_sha256.strip().casefold():
            report.update(applied=False, ready_to_apply=False, plan_sha256_mismatch=True)
            return report
        if before["conflict_count"]:
            report.update(applied=False, ready_to_apply=False)
            return report
        if not do_apply:
            report.update(applied=False, ready_to_apply=True)
            return report
        if backup_path is None:
            raise ValueError("--backup is required with --apply")
        backup = online_backup(conn, backup_path)
        report["backup"] = backup

        item_by_id = {str(item["internal_id"]): item for item in plan["items"]}
        inserted = 0
        version_ts = now_ms()
        annotation_source = "restore:" + str(plan.get("archive_sha256") or "")[:24]
        local_sql = (
            "insert into local_apps(" + ",".join(LOCAL_APP_COLUMNS) + ") values(" +
            ",".join("?" for _ in LOCAL_APP_COLUMNS) + ")"
        )
        version_sql = (
            "insert into content_versions(id,entity_type,entity_id,version_no,version_name,"
            "author_description,snapshot_json,content_hash,created_by,created_at) values(?,?,?,?,?,?,?,?,?,?)"
        )
        annotation_sql = (
            "insert into role_card_annotations(app_id,has_opening,has_world_info,has_regex,"
            "annotation_source,annotated_at) values(?,?,?,?,?,?)"
        )
        conn.set_authorizer(write_authorizer)
        conn.execute("begin immediate")
        try:
            locked = preflight(conn, plan)
            if locked["conflict_count"]:
                raise RuntimeError(f"transaction preflight conflicts: {locked['conflict_count']}")
            with zipfile.ZipFile(zip_path, "r") as zf:
                for index, item in enumerate(plan["items"], start=1):
                    raw, record = load_card_payload(zf, str(item["member"]))
                    internal_id = str(item["internal_id"])
                    if sha256_bytes(raw) != str(item["member_sha256"]):
                        raise ValueError(f"card member changed: {internal_id}")
                    if normalized_text(record.get("id")) != internal_id:
                        raise ValueError(f"card ID changed: {internal_id}")
                    row = prepared_row(record, str(item["display_id"]), str(item["version_id"]))
                    if projection_sha256(row) != str(item["row_sha256"]):
                        raise ValueError(f"card projection changed: {internal_id}")
                    conn.execute(local_sql, tuple(row[column] for column in LOCAL_APP_COLUMNS))
                    snapshot_json, content_hash = version_payload(row)
                    conn.execute(version_sql, (
                        item["version_id"], "character", internal_id, 1, "v1", "官方角色库恢复",
                        snapshot_json, content_hash, "admin", version_ts,
                    ))
                    features = item["features"]
                    conn.execute(annotation_sql, (
                        internal_id, int(bool(features["opening"])), int(bool(features["world_info"])),
                        int(bool(features["regex"])), annotation_source, version_ts,
                    ))
                    inserted += 1
                    if index % 500 == 0 or index == len(plan["items"]):
                        print(f"inserted {index}/{len(plan['items'])}", flush=True)
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.set_authorizer(None)

        try:
            conn.execute("pragma wal_checkpoint(truncate)")
        except sqlite3.DatabaseError:
            pass
        # Use a fresh read connection after the write authorizer has been used.
        # Some SQLite/Python builds retain the authorizer callback across the
        # commit boundary; running the post-commit guard on that connection can
        # incorrectly fail with `not authorized` even though the transaction is
        # already complete.  A separate immutable/read-only connection keeps
        # verification independent of the write guard lifecycle.
        verify_conn = sqlite3.connect(db_path, timeout=60)
        verify_conn.row_factory = sqlite3.Row
        try:
            guards_after = business_guard(verify_conn)
            verify = verify_database(verify_conn, plan)
        finally:
            verify_conn.close()
        report.update({
            "applied": True,
            "inserted": inserted,
            "business_guard_after": guards_after,
            "protected_data_unchanged": guards_before == guards_after,
            "verify": verify,
        })
        if guards_before != guards_after or not verify["ok"]:
            raise RuntimeError("post-restore verification failed")
        return report
    finally:
        conn.close()


def write_report(path: Path | None, value: dict[str, Any]) -> None:
    raw = json_bytes(value)
    if path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
    print(raw.decode("utf-8"), end="")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    prepare_parser = sub.add_parser("prepare", help="Validate the archive and create an immutable restore plan.")
    prepare_parser.add_argument("--zip", type=Path, required=True)
    prepare_parser.add_argument("--plan", type=Path, required=True)
    prepare_parser.add_argument("--report", type=Path)

    apply_parser = sub.add_parser("apply", help="Dry-run or transactionally restore the archive.")
    apply_parser.add_argument("--db", type=Path, required=True)
    apply_parser.add_argument("--zip", type=Path, required=True)
    apply_parser.add_argument("--plan", type=Path, required=True)
    apply_parser.add_argument("--apply", action="store_true", dest="do_apply")
    apply_parser.add_argument("--backup", type=Path)
    apply_parser.add_argument("--expected-plan-sha256")
    apply_parser.add_argument("--report", type=Path)

    verify_parser = sub.add_parser("verify", help="Verify an already restored SQLite database.")
    verify_parser.add_argument("--db", type=Path, required=True)
    verify_parser.add_argument("--plan", type=Path, required=True)
    verify_parser.add_argument("--report", type=Path)

    args = parser.parse_args()
    if args.command == "prepare":
        plan = prepare(args.zip)
        args.plan.parent.mkdir(parents=True, exist_ok=True)
        args.plan.write_bytes(json_bytes(plan))
        write_report(args.report, {key: value for key, value in plan.items() if key != "items"})
        return 0

    plan = read_plan(args.plan)
    if args.command == "verify":
        conn = sqlite3.connect(args.db)
        conn.row_factory = sqlite3.Row
        try:
            result = verify_database(conn, plan)
        finally:
            conn.close()
        write_report(args.report, result)
        return 0 if result["ok"] else 2

    if args.do_apply and not args.expected_plan_sha256:
        parser.error("--expected-plan-sha256 is required with --apply")
    result = apply_restore(
        args.db,
        args.zip,
        plan,
        do_apply=args.do_apply,
        backup_path=args.backup,
        actual_plan_sha256=sha256_file(args.plan),
        expected_plan_sha256=args.expected_plan_sha256,
    )
    write_report(args.report, result)
    clean = bool(result.get("applied") or result.get("ready_to_apply")) and not result.get("plan_sha256_mismatch")
    return 0 if clean else 2


if __name__ == "__main__":
    raise SystemExit(main())
