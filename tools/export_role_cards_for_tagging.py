#!/usr/bin/env python3
"""Export public AI星月 official role cards for safe tag relabeling round-trips."""

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
from pathlib import Path


SCHEMA = "ai-xingyue-card-tag-roundtrip/v1"
CARD_SCHEMA = "ai-xingyue-role-card-export/v1"
SCOPE_SQL = "source='admin' and status='published' and is_public=1"
JSON_COLUMNS = {"tags", "suggested_questions", "extra_settings"}
ENCODE_IN_FILENAME = set('%[]<>:"/\\|?*')
MAX_FILENAME_COMPONENT = 180


def now_export_id() -> str:
    return time.strftime("%Y%m%d-%H%M%S", time.localtime())


def parse_json_value(value: object, default: object) -> object:
    if value in (None, ""):
        return default
    if not isinstance(value, str):
        return value
    try:
        return json.loads(value)
    except Exception:
        return default


def normalize_tags(value: object) -> list[str]:
    parsed = parse_json_value(value, [])
    if not isinstance(parsed, list):
        return []
    tags: list[str] = []
    seen: set[str] = set()
    for raw in parsed:
        tag = unicodedata.normalize("NFC", str(raw or "")).strip()
        if not tag:
            continue
        key = tag.casefold()
        if key in seen:
            continue
        seen.add(key)
        tags.append(tag)
    return tags


def encode_filename_tag(tag: str) -> str:
    chunks: list[str] = []
    for char in unicodedata.normalize("NFC", tag):
        if char in ENCODE_IN_FILENAME or ord(char) < 32 or ord(char) == 127:
            chunks.extend(f"%{byte:02X}" for byte in char.encode("utf-8"))
        else:
            chunks.append(char)
    return "".join(chunks)


def safe_display_id(value: object, internal_id: str) -> str:
    text = str(value or "").strip()
    if text and not re.search(r'[<>:"/\\|?*\x00-\x1f]', text):
        return text
    return "internal-" + hashlib.sha256(internal_id.encode("utf-8")).hexdigest()[:12]


def tag_expression(tags: list[str]) -> str:
    if not tags:
        return "CLEAR"
    return "".join(f"[{encode_filename_tag(tag)}]" for tag in tags)


def build_filename(display_id: str, tags: list[str], extension: str) -> tuple[str, bool]:
    expression = tag_expression(tags)
    filename = f"{display_id}__{expression}.{extension}"
    if len(filename) <= MAX_FILENAME_COMPONENT:
        return filename, False
    return f"{display_id}__KEEP.{extension}", True


def json_bytes(value: object, *, pretty: bool = False) -> bytes:
    if pretty:
        text = json.dumps(value, ensure_ascii=False, indent=2, sort_keys=False)
    else:
        text = json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=False)
    return (text + "\n").encode("utf-8")


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def serialize_record(row: sqlite3.Row, export_id: str) -> bytes:
    record: dict[str, object] = {}
    for key in row.keys():
        value: object = row[key]
        if key in JSON_COLUMNS:
            default: object = [] if key in {"tags", "suggested_questions"} else {}
            value = parse_json_value(value, default)
        record[key] = value
    payload = {
        "schema": CARD_SCHEMA,
        "export_id": export_id,
        "record": record,
    }
    return json_bytes(payload)


def readme_text(export_id: str, count: int) -> str:
    return f"""AI星月角色卡标签修改说明

导出批次：{export_id}
导出范围：公开、已发布的官方角色卡（source=admin, status=published, is_public=1）
角色数量：{count}

本次同时生成两个 ZIP：
1. 完整角色卡包：cards/ 下是每张卡的完整数据库字段 JSON，封面以 cover_url 引用，不重复打包图片。
2. 轻量标签改名包：labels/ 下是很小的 .tag 文件，推荐把这个包交给负责分类的人。

推荐改名方式：
- 只修改文件名中双下划线“__”后面的部分。
- [恋爱][治愈] 表示把该卡标签完整替换成“恋爱、治愈”。
- CLEAR 表示清空全部标签。
- KEEP 表示保持不变；如需修改 KEEP 文件，请填写 tag-overrides.csv 的 new_tags_json。
- 不要修改前面的 display_id、文件扩展名、文件内容或 manifest.original.json。
- 标签内的特殊字符会用 %XX 百分号转义，请保留该规则。

CSV 方式：
- tag-overrides.csv 使用 UTF-8 BOM，可用 Excel 打开。
- new_tags_json 留空：保持不变。
- new_tags_json 填 []：清空标签。
- new_tags_json 填 [\"恋爱\",\"校园\"]：完整替换标签。
- 如果填写 CSV，action 请改为 replace；文件名应保持 KEEP，避免双重来源冲突。

回传覆盖安全规则：
- 实际数据库匹配使用 manifest 中的 internal_id，不按角色名或文件顺序猜测。
- 缺少的文件保持不变，不表示删除。
- 未知 ID、重复 ID、Manifest 被修改、角色 JSON 内容被修改或数据库已并发变化时会拒绝覆盖。
- 回填前会先备份 SQLite、生成 dry-run 报告，且只更新 local_apps.tags。
"""


def csv_bytes(items: list[dict]) -> bytes:
    output = io.StringIO(newline="")
    writer = csv.writer(output, lineterminator="\r\n", quoting=csv.QUOTE_ALL)
    writer.writerow([
        "card_ref",
        "internal_id_readonly",
        "display_id_readonly",
        "name_readonly",
        "original_tags_json_readonly",
        "new_tags_json",
        "action",
        "original_label_filename_readonly",
    ])
    for item in items:
        writer.writerow([
            f"id:{item['display_id']}",
            item["internal_id"],
            item["display_id"],
            item["name"],
            json.dumps(item["original_tags"], ensure_ascii=False, separators=(",", ":")),
            "",
            "skip",
            item["label_filename"],
        ])
    return b"\xef\xbb\xbf" + output.getvalue().encode("utf-8")


def open_db_readonly(path: Path) -> sqlite3.Connection:
    uri = f"file:{path.resolve().as_posix()}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def zip_write(zf: zipfile.ZipFile, name: str, data: bytes) -> None:
    info = zipfile.ZipInfo(name, date_time=time.localtime()[:6])
    info.compress_type = zipfile.ZIP_DEFLATED
    info.external_attr = 0o644 << 16
    zf.writestr(info, data)


def verify_zip(path: Path, *, prefix: str, expected_count: int, manifest_sha: str) -> dict:
    with zipfile.ZipFile(path, "r") as zf:
        names = zf.namelist()
        card_names = [name for name in names if name.startswith(prefix) and not name.endswith("/")]
        if len(card_names) != expected_count:
            raise RuntimeError(f"{path.name}: expected {expected_count} {prefix} files, got {len(card_names)}")
        if len(names) != len(set(names)):
            raise RuntimeError(f"{path.name}: duplicate archive paths")
        manifest_raw = zf.read("manifest.original.json")
        if hashlib.sha256(manifest_raw).hexdigest() != manifest_sha:
            raise RuntimeError(f"{path.name}: manifest hash mismatch")
        manifest = json.loads(manifest_raw.decode("utf-8"))
        if manifest.get("count") != expected_count or len(manifest.get("items") or []) != expected_count:
            raise RuntimeError(f"{path.name}: manifest count mismatch")
        for index in sorted({0, expected_count // 2, expected_count - 1}):
            item = manifest["items"][index]
            member = item["card_filename"] if prefix == "cards/" else item["label_filename"]
            raw = zf.read(prefix + member)
            if prefix == "cards/":
                payload = json.loads(raw.decode("utf-8"))
                if payload.get("record", {}).get("id") != item["internal_id"]:
                    raise RuntimeError(f"{path.name}: sample ID mismatch for {member}")
                if hashlib.sha256(raw).hexdigest() != item["card_sha256"]:
                    raise RuntimeError(f"{path.name}: sample card hash mismatch for {member}")
        return {
            "path": str(path),
            "size": path.stat().st_size,
            "member_count": len(names),
            "role_file_count": len(card_names),
        }


def export(db_path: Path, full_output: Path, labels_output: Path, export_id: str) -> dict:
    full_output.parent.mkdir(parents=True, exist_ok=True)
    labels_output.parent.mkdir(parents=True, exist_ok=True)
    for path in (full_output, labels_output):
        if path.exists():
            raise FileExistsError(f"refusing to overwrite existing output: {path}")

    conn = open_db_readonly(db_path)
    try:
        count = int(conn.execute(f"select count(*) from local_apps where {SCOPE_SQL}").fetchone()[0])
        rows = conn.execute(
            f"select * from local_apps where {SCOPE_SQL} "
            "order by length(coalesce(display_id,'')), coalesce(display_id,''), id"
        )
        items: list[dict] = []
        seen_internal: set[str] = set()
        seen_display: set[str] = set()
        tagged_count = 0
        keep_count = 0
        with zipfile.ZipFile(full_output, "w", allowZip64=True, compression=zipfile.ZIP_DEFLATED, compresslevel=6) as full_zip, \
             zipfile.ZipFile(labels_output, "w", allowZip64=True, compression=zipfile.ZIP_DEFLATED, compresslevel=6) as label_zip:
            for index, row in enumerate(rows, start=1):
                internal_id = str(row["id"] or "").strip()
                if not internal_id or internal_id in seen_internal:
                    raise RuntimeError(f"missing or duplicate internal id: {internal_id!r}")
                display_id = safe_display_id(row["display_id"], internal_id)
                if display_id in seen_display:
                    raise RuntimeError(f"duplicate display id: {display_id}")
                seen_internal.add(internal_id)
                seen_display.add(display_id)
                tags = normalize_tags(row["tags"])
                if tags:
                    tagged_count += 1
                card_filename, card_keep = build_filename(display_id, tags, "json")
                label_filename, label_keep = build_filename(display_id, tags, "tag")
                forced_keep = card_keep or label_keep
                if forced_keep:
                    card_filename = f"{display_id}__KEEP.json"
                    label_filename = f"{display_id}__KEEP.tag"
                    keep_count += 1
                card_raw = serialize_record(row, export_id)
                card_sha = hashlib.sha256(card_raw).hexdigest()
                zip_write(full_zip, "cards/" + card_filename, card_raw)
                label_payload = (
                    f"display_id={display_id}\ninternal_id={internal_id}\n"
                    f"name={str(row['name'] or '').strip()}\n"
                    f"original_tags={json.dumps(tags, ensure_ascii=False, separators=(',', ':'))}\n"
                ).encode("utf-8")
                zip_write(label_zip, "labels/" + label_filename, label_payload)
                items.append({
                    "display_id": display_id,
                    "internal_id": internal_id,
                    "name": str(row["name"] or ""),
                    "source": str(row["source"] or ""),
                    "status": str(row["status"] or ""),
                    "is_public": bool(row["is_public"]),
                    "original_tags": tags,
                    "card_filename": card_filename,
                    "label_filename": label_filename,
                    "filename_uses_keep": forced_keep,
                    "card_sha256": card_sha,
                    "db_updated_at": int(row["updated_at"] or 0),
                })
                if index % 500 == 0 or index == count:
                    print(f"exported {index}/{count}", flush=True)

            if len(items) != count:
                raise RuntimeError(f"row count changed during export: expected {count}, got {len(items)}")
            manifest = {
                "schema": SCHEMA,
                "export_id": export_id,
                "generated_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "scope": "public_published_admin_cards",
                "scope_sql": SCOPE_SQL,
                "count": count,
                "stats": {
                    "tagged_cards": tagged_count,
                    "untagged_cards": count - tagged_count,
                    "filename_keep_cards": keep_count,
                },
                "items": items,
            }
            manifest_raw = json_bytes(manifest, pretty=True)
            manifest_sha = hashlib.sha256(manifest_raw).hexdigest()
            common = {
                "README-标签修改说明.txt": readme_text(export_id, count).encode("utf-8-sig"),
                "manifest.original.json": manifest_raw,
                "manifest.original.sha256": f"{manifest_sha}  manifest.original.json\n".encode("ascii"),
                "tag-overrides.csv": csv_bytes(items),
            }
            for name, raw in common.items():
                zip_write(full_zip, name, raw)
                zip_write(label_zip, name, raw)
    finally:
        conn.close()

    full_verify = verify_zip(full_output, prefix="cards/", expected_count=count, manifest_sha=manifest_sha)
    labels_verify = verify_zip(labels_output, prefix="labels/", expected_count=count, manifest_sha=manifest_sha)
    result = {
        "schema": SCHEMA,
        "export_id": export_id,
        "count": count,
        "tagged_cards": tagged_count,
        "untagged_cards": count - tagged_count,
        "filename_keep_cards": keep_count,
        "manifest_sha256": manifest_sha,
        "full_zip": {**full_verify, "sha256": file_sha256(full_output)},
        "labels_zip": {**labels_verify, "sha256": file_sha256(labels_output)},
    }
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Export public official AI星月 role cards for tag relabeling.")
    parser.add_argument("--db", type=Path, required=True, help="Path to ai_fengyue.sqlite3")
    parser.add_argument("--full-output", type=Path, required=True, help="Full role-card ZIP output")
    parser.add_argument("--labels-output", type=Path, required=True, help="Lightweight tag-renaming ZIP output")
    parser.add_argument("--export-id", default=now_export_id())
    parser.add_argument("--report", type=Path, help="Optional JSON report path")
    args = parser.parse_args()
    result = export(args.db, args.full_output, args.labels_output, str(args.export_id).strip())
    rendered = json.dumps(result, ensure_ascii=False, indent=2)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
