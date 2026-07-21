"""角色卡互动媒体扩展。

这是可直接拷入生产 Python 服务的独立业务模块，不依赖具体 Web 框架。
HTTP 路由只负责鉴权、读取请求体并调用 ``CardMediaService``；严禁相信客户端
提交的 public_url、app_id 或 MIME。对象存储实现只需符合 ``ObjectStorage`` 协议。
"""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO, Protocol

from spine_media_support import (
    SPINE_MAX_UPLOAD_BYTES,
    SPINE_MIMES,
    SpineMediaError,
    inspect_spine_zip,
    materialize_spine_asset,
    remove_spine_directory,
)


MEDIA_RULES = {
    "bgm": {"mimes": {"audio/mpeg", "audio/mp3"}, "max_size": 30 * 1024 * 1024},
    "portrait": {"mimes": {"image/png", "image/jpeg", "image/webp", "image/gif"}, "max_size": 20 * 1024 * 1024},
    "background": {"mimes": {"image/png", "image/jpeg", "image/webp", "image/gif"}, "max_size": 20 * 1024 * 1024},
    "spine": {"mimes": set(SPINE_MIMES), "max_size": SPINE_MAX_UPLOAD_BYTES},
}
UI_ACTIONS = {"open_popup", "show_floating", "switch_bgm", "open_sidebar", "set_scene"}
CHAT_SHELL_PERMISSIONS = (
    "read_state",
    "send",
    "continue",
    "regenerate",
    "swipe",
    "edit",
    "delete",
    "rollback",
    "load_older",
    "tts",
    "open_settings",
    "exit",
    "slash",
    "set_draft",
    "stop_generation",
)
CHAT_SHELL_PERMISSION_SET = frozenset(CHAT_SHELL_PERMISSIONS)
CHAT_SHELL_LIMITS = {
    "name": 120,
    "version": 40,
    "html": 240000,
    "css": 160000,
    "javascript": 240000,
    "permissions": len(CHAT_SHELL_PERMISSIONS),
}
BAD_REGEX = re.compile(r"\((?:[^()]|\\.)*[+*](?:[^()]|\\.)*\)[+*{]")
AMBIGUOUS_REGEX = re.compile(r"\((?:[^()]|\\.)*\|(?:[^()]|\\.)*\)\s*(?:[+*]|\{\d*,?\d*\})")
BAD_HTML = re.compile(r"<(?:script|style|iframe|object|embed|base|form|meta|link)\b|\bon\w+\s*=|\bsrcdoc\s*=", re.I)
BAD_CSS = re.compile(r"@(?:import|font-face)|\b(?:expression|behavior|-moz-binding)\s*:|url\s*\(", re.I)
MAX_ASSETS_PER_OWNER = 200
MAX_PENDING_INTENTS_PER_HOUR = 40
DEFAULT_STALE_SECONDS = 24 * 60 * 60


CARD_MEDIA_TABLE_SQL = """
CREATE TABLE card_media_assets (
  id TEXT PRIMARY KEY,
  owner_user_id TEXT NOT NULL,
  app_id TEXT,
  draft_id TEXT,
  kind TEXT NOT NULL CHECK(kind IN ('bgm','portrait','background','spine')),
  original_name TEXT NOT NULL,
  object_key TEXT NOT NULL UNIQUE,
  public_url TEXT,
  mime_type TEXT NOT NULL,
  size_bytes INTEGER NOT NULL,
  sha256 TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','ready','deleted')),
  metadata TEXT NOT NULL DEFAULT '{}',
  created_at INTEGER NOT NULL,
  updated_at INTEGER NOT NULL
)
"""

CARD_MEDIA_INDEX_SQL = """
CREATE INDEX IF NOT EXISTS idx_card_media_owner_app ON card_media_assets(owner_user_id, app_id, status);
CREATE INDEX IF NOT EXISTS idx_card_media_owner_draft ON card_media_assets(owner_user_id, draft_id, status);
CREATE INDEX IF NOT EXISTS idx_card_media_owner_status_created ON card_media_assets(owner_user_id, status, created_at);
CREATE INDEX IF NOT EXISTS idx_card_media_app_status ON card_media_assets(app_id, status);
CREATE INDEX IF NOT EXISTS idx_card_media_status_updated ON card_media_assets(status, updated_at);
"""

MIGRATION_SQL = CARD_MEDIA_TABLE_SQL.replace("CREATE TABLE card_media_assets", "CREATE TABLE IF NOT EXISTS card_media_assets") + ";" + CARD_MEDIA_INDEX_SQL


class CardMediaError(ValueError):
    """可安全返回 400/403/404 的业务错误。"""


class ObjectStorage(Protocol):
    def create_upload_target(self, asset_id: str, object_key: str, mime_type: str, size_bytes: int) -> dict: ...
    def open_pending(self, asset_id: str, object_key: str) -> BinaryIO: ...
    def promote(self, asset_id: str, object_key: str) -> tuple[str, str]: ...
    def delete(self, object_key: str) -> None: ...


@dataclass
class LocalObjectStorage:
    """本地开发适配器；生产可替换为 S3/R2/OSS 预签名 PUT 实现。"""

    root: Path
    public_prefix: str = "/media-cache/card-assets/ready"

    def __post_init__(self) -> None:
        self.root = Path(self.root).resolve()
        (self.root / "pending").mkdir(parents=True, exist_ok=True)
        (self.root / "ready").mkdir(parents=True, exist_ok=True)

    def _safe(self, bucket: str, object_key: str) -> Path:
        candidate = (self.root / bucket / object_key).resolve()
        if self.root not in candidate.parents:
            raise CardMediaError("invalid object key")
        return candidate

    def create_upload_target(self, asset_id: str, object_key: str, mime_type: str, size_bytes: int) -> dict:
        return {
            "method": "PUT",
            "url": f"/console/api/web/card-assets/{asset_id}/content",
            "headers": {"Content-Type": mime_type},
            "credentials": "include",
        }

    def write_pending(self, asset_id: str, object_key: str, body: bytes) -> None:
        target = self._safe("pending", object_key)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(body)

    def open_pending(self, asset_id: str, object_key: str) -> BinaryIO:
        return self._safe("pending", object_key).open("rb")

    def promote(self, asset_id: str, object_key: str) -> tuple[str, str]:
        source = self._safe("pending", object_key)
        target = self._safe("ready", object_key)
        target.parent.mkdir(parents=True, exist_ok=True)
        source.replace(target)
        return object_key, f"{self.public_prefix.rstrip('/')}/{object_key}"

    def delete(self, object_key: str) -> None:
        for bucket in ("pending", "ready"):
            path = self._safe(bucket, object_key)
            if path.exists():
                path.unlink()

    def materialize_spine(self, asset_id: str, object_key: str, parsed: dict) -> dict:
        ready_zip = self._safe("ready", object_key)
        destination = ready_zip.parent / str(asset_id)
        public_zip = f"{self.public_prefix.rstrip('/')}/{object_key}"
        public_dir = public_zip.rsplit("/", 1)[0] + f"/{asset_id}"
        return materialize_spine_asset(parsed, destination, public_dir)

    def delete_asset_artifacts(self, asset_id: str, object_key: str) -> None:
        self.delete(object_key)
        ready_zip = self._safe("ready", object_key)
        remove_spine_directory(ready_zip.parent / str(asset_id))


def migrate_card_media(conn: sqlite3.Connection) -> None:
    existing = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='card_media_assets'"
    ).fetchone()
    if not existing:
        conn.executescript(MIGRATION_SQL)
        conn.commit()
        return
    create_sql = str(existing[0] or "")
    if "'spine'" in create_sql:
        conn.executescript(CARD_MEDIA_INDEX_SQL)
        conn.commit()
        return

    # SQLite cannot ALTER a CHECK constraint.  Rebuild the table in one write
    # transaction so existing assets remain intact and startup never observes
    # a partially migrated schema.
    conn.execute("BEGIN IMMEDIATE")
    try:
        conn.execute(CARD_MEDIA_TABLE_SQL.replace("card_media_assets", "card_media_assets_spine_new", 1))
        conn.execute(
            """INSERT INTO card_media_assets_spine_new
               (id,owner_user_id,app_id,draft_id,kind,original_name,object_key,public_url,
                mime_type,size_bytes,sha256,status,metadata,created_at,updated_at)
               SELECT id,owner_user_id,app_id,draft_id,kind,original_name,object_key,public_url,
                      mime_type,size_bytes,sha256,status,metadata,created_at,updated_at
               FROM card_media_assets"""
        )
        conn.execute("DROP TABLE card_media_assets")
        conn.execute("ALTER TABLE card_media_assets_spine_new RENAME TO card_media_assets")
        for statement in CARD_MEDIA_INDEX_SQL.split(";"):
            if statement.strip():
                conn.execute(statement)
        conn.commit()
    except Exception:
        conn.rollback()
        raise


def _clean_id(value: object, label: str, *, optional: bool = False) -> str:
    text = str(value or "").strip()
    if optional and not text:
        return ""
    if not re.fullmatch(r"[\w:.-]{1,128}", text):
        raise CardMediaError(f"invalid {label}")
    return text


def _clean_filename(value: object) -> str:
    name = Path(str(value or "asset").replace("\\", "/")).name.strip()[:120]
    return re.sub(r"[^\w.()\-\u4e00-\u9fff ]", "_", name) or "asset"


def _clean_emotion(value: object) -> str:
    """归一化立绘情绪/姿态标签；空串表示清除该标签。"""
    return str(value or "").strip()[:40]



def _sniff_mime(head: bytes) -> str:
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if head.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if head.startswith((b"GIF87a", b"GIF89a")):
        return "image/gif"
    if len(head) >= 12 and head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return "image/webp"
    if head.startswith(b"ID3") or (len(head) >= 2 and head[0] == 0xFF and head[1] & 0xE0 == 0xE0):
        return "audio/mpeg"
    if head.startswith(b"PK\x03\x04"):
        return "application/zip"
    return "application/octet-stream"


def _stream_fingerprint(stream: BinaryIO, maximum: int) -> tuple[int, str, str]:
    digest = hashlib.sha256()
    size = 0
    head = b""
    while True:
        chunk = stream.read(1024 * 1024)
        if not chunk:
            break
        if not head:
            head = chunk[:32]
        size += len(chunk)
        if size > maximum:
            raise CardMediaError("file too large")
        digest.update(chunk)
    return size, digest.hexdigest(), _sniff_mime(head)


def _asset_dict(row: sqlite3.Row | dict) -> dict:
    item = dict(row)
    metadata = item.get("metadata")
    if isinstance(metadata, str):
        try:
            metadata = json.loads(metadata)
        except json.JSONDecodeError:
            metadata = {}
    return {
        "id": item["id"],
        "kind": item["kind"],
        "name": item["original_name"],
        "url": item.get("public_url") or "",
        "mime_type": item["mime_type"],
        "size_bytes": item["size_bytes"],
        "sha256": item["sha256"],
        "status": item["status"],
        "metadata": metadata if isinstance(metadata, dict) else {},
    }


class CardMediaService:
    def __init__(self, conn: sqlite3.Connection, storage: ObjectStorage):
        self.conn = conn
        self.conn.row_factory = sqlite3.Row
        self.storage = storage

    def create_upload_intent(self, owner_user_id: str, payload: dict) -> dict:
        owner = _clean_id(owner_user_id, "owner_user_id")
        now = int(time.time())
        active_count = int(self.conn.execute(
            "SELECT count(*) FROM card_media_assets WHERE owner_user_id=? AND status IN ('pending','ready')",
            (owner,),
        ).fetchone()[0])
        if active_count >= MAX_ASSETS_PER_OWNER:
            raise CardMediaError(f"media asset limit reached ({MAX_ASSETS_PER_OWNER})")
        recent_pending = int(self.conn.execute(
            "SELECT count(*) FROM card_media_assets WHERE owner_user_id=? AND status='pending' AND created_at>=?",
            (owner, now - 3600),
        ).fetchone()[0])
        if recent_pending >= MAX_PENDING_INTENTS_PER_HOUR:
            raise CardMediaError(f"pending upload intent hourly limit reached ({MAX_PENDING_INTENTS_PER_HOUR})")
        kind = str(payload.get("kind") or "")
        if kind not in MEDIA_RULES:
            raise CardMediaError("unsupported media kind")
        app_id = _clean_id(payload.get("app_id"), "app_id", optional=True)
        draft_id = _clean_id(payload.get("draft_id"), "draft_id", optional=True)
        if not app_id and not draft_id:
            raise CardMediaError("app_id or draft_id is required")
        if app_id:
            owned = self.conn.execute("SELECT 1 FROM local_apps WHERE id=? AND owner_user_id=?", (app_id, owner)).fetchone()
            if not owned:
                raise CardMediaError("card not found or not owned")
        mime = str(payload.get("mime_type") or "").lower()
        size = int(payload.get("size_bytes") or 0)
        sha256 = str(payload.get("sha256") or "").lower()
        rule = MEDIA_RULES[kind]
        if mime not in rule["mimes"] or not 0 < size <= rule["max_size"]:
            raise CardMediaError("invalid media type or size")
        if not re.fullmatch(r"[0-9a-f]{64}", sha256):
            raise CardMediaError("invalid sha256")
        asset_id = f"asset-{uuid.uuid4()}"
        extension = {
            "audio/mpeg": ".mp3", "audio/mp3": ".mp3", "image/png": ".png",
            "image/jpeg": ".jpg", "image/webp": ".webp", "image/gif": ".gif",
            "application/zip": ".spine.zip", "application/x-zip-compressed": ".spine.zip",
        }[mime]
        object_key = f"{owner[:24]}/{asset_id}{extension}"
        self.conn.execute(
            """INSERT INTO card_media_assets
               (id,owner_user_id,app_id,draft_id,kind,original_name,object_key,mime_type,size_bytes,sha256,status,created_at,updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?, 'pending',?,?)""",
            (asset_id, owner, app_id or None, draft_id or None, kind, _clean_filename(payload.get("filename")), object_key, mime, size, sha256, now, now),
        )
        self.conn.commit()
        row = self._owned_asset(asset_id, owner)
        return {"asset": _asset_dict(row), "upload": self.storage.create_upload_target(asset_id, object_key, mime, size)}

    def write_local_upload(self, owner_user_id: str, asset_id: str, body: bytes, content_type: str) -> None:
        """仅供 LocalObjectStorage 的 PUT 路由使用；云存储直传时不调用。"""
        row = self._owned_asset(asset_id, owner_user_id, status="pending")
        if content_type.lower() not in MEDIA_RULES[row["kind"]]["mimes"] or len(body) > row["size_bytes"]:
            raise CardMediaError("upload body does not match intent")
        writer = getattr(self.storage, "write_pending", None)
        if not writer:
            raise CardMediaError("storage does not accept proxied upload")
        writer(asset_id, row["object_key"], body)

    def complete_upload(self, owner_user_id: str, asset_id: str, payload: dict | None = None) -> dict:
        row = self._owned_asset(asset_id, owner_user_id, status="pending")
        rule = MEDIA_RULES[row["kind"]]
        spine_parsed = None
        try:
            with self.storage.open_pending(asset_id, row["object_key"]) as stream:
                size, digest, sniffed = _stream_fingerprint(stream, rule["max_size"])
        except FileNotFoundError as exc:
            raise CardMediaError("uploaded object not found") from exc
        if size != row["size_bytes"] or digest != row["sha256"] or sniffed not in rule["mimes"]:
            self._reject_pending_asset(row, owner_user_id)
            raise CardMediaError("uploaded object verification failed")

        if row["kind"] == "spine":
            try:
                with self.storage.open_pending(asset_id, row["object_key"]) as stream:
                    spine_parsed = inspect_spine_zip(stream.read(SPINE_MAX_UPLOAD_BYTES + 1))
            except (FileNotFoundError, SpineMediaError) as exc:
                self._reject_pending_asset(row, owner_user_id)
                message = str(exc) if isinstance(exc, SpineMediaError) else "uploaded object not found"
                raise CardMediaError(f"spine package invalid: {message}") from exc

        object_key = row["object_key"]
        public_url = ""
        metadata: dict = {}
        try:
            object_key, public_url = self.storage.promote(asset_id, row["object_key"])
            if row["kind"] == "spine":
                materializer = getattr(self.storage, "materialize_spine", None)
                if not callable(materializer):
                    raise SpineMediaError("configured storage cannot materialize Spine assets")
                metadata["spine"] = materializer(asset_id, object_key, spine_parsed)
            now = int(time.time())
            cursor = self.conn.execute(
                """UPDATE card_media_assets
                   SET object_key=?, public_url=?, mime_type=?, metadata=?, status='ready', updated_at=?
                   WHERE id=? AND owner_user_id=? AND status='pending'""",
                (
                    object_key, public_url, "audio/mpeg" if sniffed == "audio/mp3" else sniffed,
                    json.dumps(metadata, ensure_ascii=False, separators=(",", ":")),
                    now, asset_id, str(owner_user_id),
                ),
            )
            if cursor.rowcount != 1:
                raise CardMediaError("asset completion state changed")
            self.conn.commit()
        except Exception as exc:
            self.conn.rollback()
            try:
                self._delete_storage_asset(asset_id, object_key)
            except Exception:
                pass
            self.conn.execute(
                "UPDATE card_media_assets SET status='deleted', public_url=NULL, updated_at=? WHERE id=? AND owner_user_id=?",
                (int(time.time()), asset_id, str(owner_user_id)),
            )
            self.conn.commit()
            if isinstance(exc, CardMediaError):
                raise
            if isinstance(exc, SpineMediaError):
                raise CardMediaError(f"spine package invalid: {exc}") from exc
            raise CardMediaError("asset completion failed") from exc
        return {"asset": _asset_dict(self._owned_asset(asset_id, owner_user_id, status="ready"))}

    def _delete_storage_asset(self, asset_id: str, object_key: str) -> None:
        deleter = getattr(self.storage, "delete_asset_artifacts", None)
        if callable(deleter):
            deleter(asset_id, object_key)
        else:
            self.storage.delete(object_key)

    def _reject_pending_asset(self, row: sqlite3.Row, owner_user_id: str) -> None:
        asset_id = str(row["id"])
        self.conn.execute(
            "UPDATE card_media_assets SET status='deleted', public_url=NULL, updated_at=? "
            "WHERE id=? AND owner_user_id=? AND status='pending'",
            (int(time.time()), asset_id, str(owner_user_id)),
        )
        self.conn.commit()
        try:
            self._delete_storage_asset(asset_id, str(row["object_key"]))
        except Exception:
            return
        self.conn.execute("DELETE FROM card_media_assets WHERE id=? AND status='deleted'", (asset_id,))
        self.conn.commit()

    def bind_payload(
        self,
        owner_user_id: str,
        app_id: str,
        draft_id: str,
        payload: dict,
        *,
        commit: bool = True,
    ) -> dict:
        """保存角色前调用；返回可写入 extra_settings 的已验证媒体字段。"""
        owner = _clean_id(owner_user_id, "owner_user_id")
        app = _clean_id(app_id, "app_id")
        draft = _clean_id(draft_id, "draft_id", optional=True)
        requested = payload.get("media_assets") if isinstance(payload.get("media_assets"), list) else []
        asset_ids = list(dict.fromkeys(_clean_id(item.get("id"), "asset_id") for item in requested[:200] if isinstance(item, dict)))
        assets = self._ready_assets(owner, asset_ids, app, draft)
        if len(assets) != len(asset_ids):
            raise CardMediaError("one or more media assets are missing or not owned")
        allowed = {row["id"]: row["kind"] for row in assets}
        # 客户端提交的情绪/姿态标签（galgame 立绘切换用），按 asset_id 收集。
        requested_emotions = {
            _clean_id(item.get("id"), "asset_id"): _clean_emotion((item.get("metadata") or {}).get("emotion"))
            for item in requested[:200]
            if isinstance(item, dict) and isinstance(item.get("metadata"), dict)
        }
        world_info = normalize_world_media_bindings(payload.get("world_info"), allowed)
        experience = normalize_card_experience(payload.get("card_experience"), allowed, {str(entry.get("id")) for entry in world_info})
        now = int(time.time())
        if draft and asset_ids:
            marks = ",".join("?" for _ in asset_ids)
            self.conn.execute(
                f"UPDATE card_media_assets SET app_id=?, draft_id=NULL, updated_at=? WHERE owner_user_id=? AND draft_id=? AND status='ready' AND id IN ({marks})",
                (app, now, owner, draft, *asset_ids),
            )
        # 将情绪标签持久化进 DB metadata，保证读取时可用于立绘切换。
        persisted: list[sqlite3.Row] = []
        for row in assets:
            emotion = requested_emotions.get(row["id"])
            if emotion is None:
                persisted.append(row)
                continue
            try:
                current = json.loads(row["metadata"]) if isinstance(row["metadata"], str) else {}
            except (TypeError, json.JSONDecodeError):
                current = {}
            if not isinstance(current, dict):
                current = {}
            if emotion:
                current["emotion"] = emotion
            else:
                current.pop("emotion", None)
            self.conn.execute(
                "UPDATE card_media_assets SET metadata=?, updated_at=? WHERE id=? AND owner_user_id=?",
                (json.dumps(current, ensure_ascii=False, separators=(",", ":")), now, row["id"], owner),
            )
            persisted.append(self._owned_asset(row["id"], owner))
        if commit and (asset_ids or requested_emotions):
            self.conn.commit()
        return {"media_assets": [_asset_dict(row) for row in persisted], "world_info": world_info, "card_experience": experience}


    def hydrate_card(self, owner_or_public_card_id: str) -> list[dict]:
        rows = self.conn.execute(
            "SELECT * FROM card_media_assets WHERE app_id=? AND status='ready' ORDER BY created_at,id",
            (str(owner_or_public_card_id),),
        ).fetchall()
        return [_asset_dict(row) for row in rows]

    def delete_asset(self, owner_user_id: str, asset_id: str) -> None:
        row = self._owned_asset(asset_id, owner_user_id)
        if row["app_id"]:
            card = self.conn.execute(
                "SELECT extra_settings FROM local_apps WHERE id=? AND owner_user_id=?",
                (row["app_id"], str(owner_user_id)),
            ).fetchone()
            if card:
                try:
                    extra = json.loads(card["extra_settings"] or "{}")
                except (TypeError, json.JSONDecodeError):
                    extra = {}
                if isinstance(extra, dict):
                    extra["media_assets"] = [item for item in extra.get("media_assets", []) if isinstance(item, dict) and item.get("id") != asset_id]
                    for entry in extra.get("world_info", []):
                        if isinstance(entry, dict):
                            entry["media_bindings"] = [binding for binding in entry.get("media_bindings", []) if isinstance(binding, dict) and binding.get("asset_id") != asset_id]
                    experience = extra.get("card_experience") if isinstance(extra.get("card_experience"), dict) else {}
                    bgm = experience.get("bgm") if isinstance(experience.get("bgm"), dict) else {}
                    if bgm.get("default_asset_id") == asset_id:
                        bgm["default_asset_id"] = ""
                    galgame = experience.get("galgame") if isinstance(experience.get("galgame"), dict) else {}
                    if galgame.get("default_portrait_id") == asset_id:
                        galgame["default_portrait_id"] = ""
                    if galgame.get("default_background_id") == asset_id:
                        galgame["default_background_id"] = ""
                    experience["ui_rules"] = [rule for rule in experience.get("ui_rules", []) if not (isinstance(rule, dict) and rule.get("action") == "switch_bgm" and rule.get("target_id") == asset_id)]
                    self.conn.execute(
                        "UPDATE local_apps SET extra_settings=? WHERE id=? AND owner_user_id=?",
                        (json.dumps(extra, ensure_ascii=False, separators=(",", ":")), row["app_id"], str(owner_user_id)),
                    )
        self.conn.execute("UPDATE card_media_assets SET status='deleted', public_url=NULL, updated_at=? WHERE id=?", (int(time.time()), asset_id))
        self.conn.commit()
        self.purge_deleted_assets(asset_ids=[asset_id])

    def mark_app_assets_deleted(
        self,
        app_id: str,
        owner_user_id: str | None = None,
        *,
        commit: bool = False,
    ) -> list[str]:
        """Mark every object belonging to a card as deleted.

        Store deletion code can call this inside its own transaction, commit the
        card deletion, and then call :meth:`purge_deleted_assets`.
        """
        app = _clean_id(app_id, "app_id")
        query = "SELECT id FROM card_media_assets WHERE app_id=? AND status<>'deleted'"
        args: list[object] = [app]
        if owner_user_id is not None:
            query += " AND owner_user_id=?"
            args.append(_clean_id(owner_user_id, "owner_user_id"))
        asset_ids = [str(row["id"]) for row in self.conn.execute(query, args).fetchall()]
        if asset_ids:
            marks = ",".join("?" for _ in asset_ids)
            self.conn.execute(
                f"UPDATE card_media_assets SET status='deleted', public_url=NULL, updated_at=? "
                f"WHERE id IN ({marks})",
                (int(time.time()), *asset_ids),
            )
            if commit:
                self.conn.commit()
        return asset_ids

    def purge_deleted_assets(
        self,
        *,
        app_id: str | None = None,
        asset_ids: list[str] | None = None,
        limit: int = 500,
    ) -> dict:
        """Delete tombstoned objects, retaining failed rows for a later retry."""
        clauses = ["status='deleted'"]
        args: list[object] = []
        if app_id is not None:
            clauses.append("app_id=?")
            args.append(_clean_id(app_id, "app_id"))
        clean_asset_ids = list(dict.fromkeys(
            _clean_id(item, "asset_id") for item in (asset_ids or [])[:500]
        ))
        if clean_asset_ids:
            marks = ",".join("?" for _ in clean_asset_ids)
            clauses.append(f"id IN ({marks})")
            args.extend(clean_asset_ids)
        safe_limit = max(1, min(2000, int(limit)))
        version_ref_table = self.conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='content_version_assets'"
        ).fetchone()
        retained_clause = (
            " AND NOT EXISTS (SELECT 1 FROM content_version_assets v WHERE v.asset_id=card_media_assets.id)"
            if version_ref_table else ""
        )
        rows = self.conn.execute(
            f"SELECT id,object_key FROM card_media_assets WHERE {' AND '.join(clauses)} "
            f"{retained_clause} ORDER BY updated_at,id LIMIT ?",
            (*args, safe_limit),
        ).fetchall()
        removed: list[str] = []
        failed: list[str] = []
        for row in rows:
            try:
                self._delete_storage_asset(str(row["id"]), str(row["object_key"]))
                removed.append(str(row["id"]))
            except Exception:
                failed.append(str(row["id"]))
        if removed:
            marks = ",".join("?" for _ in removed)
            self.conn.execute(
                f"DELETE FROM card_media_assets WHERE status='deleted' AND id IN ({marks})",
                removed,
            )
            self.conn.commit()
        return {"scanned": len(rows), "removed": len(removed), "failed": len(failed), "failed_ids": failed}

    def cleanup_stale_assets(
        self,
        *,
        max_age_seconds: int = DEFAULT_STALE_SECONDS,
        limit: int = 500,
    ) -> dict:
        """Tombstone uploads/drafts older than 24h and retry deleted objects."""
        age = max(3600, int(max_age_seconds))
        safe_limit = max(1, min(2000, int(limit)))
        cutoff = int(time.time()) - age
        rows = self.conn.execute(
            """SELECT id FROM card_media_assets
               WHERE (status='pending' AND updated_at<?)
                  OR (status='ready' AND app_id IS NULL AND draft_id IS NOT NULL AND updated_at<?)
               ORDER BY updated_at,id LIMIT ?""",
            (cutoff, cutoff, safe_limit),
        ).fetchall()
        stale_ids = [str(row["id"]) for row in rows]
        if stale_ids:
            marks = ",".join("?" for _ in stale_ids)
            self.conn.execute(
                f"UPDATE card_media_assets SET status='deleted', public_url=NULL, updated_at=? "
                f"WHERE id IN ({marks})",
                (int(time.time()), *stale_ids),
            )
            self.conn.commit()
        purged = self.purge_deleted_assets(limit=safe_limit)
        return {"stale_marked": len(stale_ids), **purged}

    def _owned_asset(self, asset_id: str, owner_user_id: str, status: str | None = None) -> sqlite3.Row:
        query = "SELECT * FROM card_media_assets WHERE id=? AND owner_user_id=?"
        args: list[object] = [_clean_id(asset_id, "asset_id"), _clean_id(owner_user_id, "owner_user_id")]
        if status:
            query += " AND status=?"
            args.append(status)
        row = self.conn.execute(query, args).fetchone()
        if not row:
            raise CardMediaError("asset not found or not owned")
        return row

    def _ready_assets(self, owner: str, asset_ids: list[str], app_id: str, draft_id: str) -> list[sqlite3.Row]:
        if not asset_ids:
            return []
        marks = ",".join("?" for _ in asset_ids)
        return self.conn.execute(
            f"""SELECT * FROM card_media_assets WHERE owner_user_id=? AND status='ready' AND id IN ({marks})
                AND (app_id=? OR (?<>'' AND draft_id=?)) ORDER BY created_at,id""",
            [owner, *asset_ids, app_id, draft_id, draft_id],
        ).fetchall()


def _safe_regex(value: object, flags: object = "i") -> tuple[str, str]:
    pattern = str(value or "").strip()[:240]
    clean_flags = "".join(dict.fromkeys(ch for ch in str(flags or "") if ch in "ims"))
    if (
        not pattern
        or BAD_REGEX.search(pattern)
        or AMBIGUOUS_REGEX.search(pattern)
        or re.search(r"\\[1-9]|\(\?[=!<]", pattern)
        or len(re.findall(r"(?<!\\)\|", pattern)) > 8
    ):
        raise CardMediaError("unsafe or empty UI regex")
    try:
        re.compile(pattern, (re.I if "i" in clean_flags else 0) | (re.M if "m" in clean_flags else 0) | (re.S if "s" in clean_flags else 0))
    except re.error as exc:
        raise CardMediaError(f"invalid UI regex: {exc}") from exc
    return pattern, clean_flags


def _safe_markup(value: object, maximum: int, kind: str) -> str:
    text = str(value or "")[:maximum]
    if kind == "html" and BAD_HTML.search(text):
        raise CardMediaError("unsafe HTML in card experience")
    if kind == "css" and BAD_CSS.search(text):
        raise CardMediaError("unsafe CSS in card experience")
    return text


def _chat_shell_source(value: object, maximum: int) -> str:
    """Keep authored shell source intact while bounding storage/runtime cost."""
    if not isinstance(value, str):
        return ""
    return value.replace("\x00", "")[:maximum]


def _normalize_chat_shell(value: object) -> dict:
    """Normalize the isolated full-chat UI manifest; unknown fields are dropped."""
    raw = value if isinstance(value, dict) else {}
    permissions: list[str] = []
    candidates = raw.get("permissions") if isinstance(raw.get("permissions"), list) else []
    for candidate in candidates:
        permission = str(candidate or "").strip()
        if permission not in CHAT_SHELL_PERMISSION_SET or permission in permissions:
            continue
        permissions.append(permission)
        if len(permissions) >= CHAT_SHELL_LIMITS["permissions"]:
            break
    return {
        "enabled": bool(raw.get("enabled")),
        "name": str(raw.get("name") or "").strip()[:CHAT_SHELL_LIMITS["name"]],
        "version": str(raw.get("version") or "1").strip()[:CHAT_SHELL_LIMITS["version"]] or "1",
        "html": _chat_shell_source(raw.get("html"), CHAT_SHELL_LIMITS["html"]),
        "css": _chat_shell_source(raw.get("css"), CHAT_SHELL_LIMITS["css"]),
        "javascript": _chat_shell_source(raw.get("javascript"), CHAT_SHELL_LIMITS["javascript"]),
        "permissions": permissions,
        "fallback": "default",
    }


def normalize_world_media_bindings(value: object, allowed_assets: dict[str, str]) -> list[dict]:
    entries = value if isinstance(value, list) else []
    output: list[dict] = []
    for index, raw in enumerate(entries[:200]):
        if not isinstance(raw, dict):
            continue
        item = dict(raw)
        bindings: list[dict] = []
        for number, binding in enumerate(raw.get("media_bindings") if isinstance(raw.get("media_bindings"), list) else []):
            if not isinstance(binding, dict):
                continue
            asset_id = _clean_id(binding.get("asset_id"), "asset_id")
            kind = str(binding.get("kind") or "")
            if allowed_assets.get(asset_id) != kind:
                raise CardMediaError("worldbook binding does not match an owned asset")
            bindings.append({
                "id": _clean_id(binding.get("id") or f"binding-{index + 1}-{number + 1}", "binding_id"),
                "kind": kind,
                "asset_id": asset_id,
                "label": str(binding.get("label") or "")[:80],
                "activation": str(binding.get("activation") or "entry") if binding.get("activation") in {"entry", "regex", "manual"} else "entry",
            })
        item["media_bindings"] = bindings[:30]
        output.append(item)
    return output


def normalize_card_experience(value: object, allowed_assets: dict[str, str], world_ids: set[str]) -> dict:
    raw = value if isinstance(value, dict) else {}
    bgm_raw = raw.get("bgm") if isinstance(raw.get("bgm"), dict) else {}
    default_bgm = _clean_id(bgm_raw.get("default_asset_id"), "asset_id", optional=True)
    if default_bgm and allowed_assets.get(default_bgm) != "bgm":
        raise CardMediaError("default BGM is not an owned BGM asset")
    rules: list[dict] = []
    for index, item in enumerate(raw.get("ui_rules") if isinstance(raw.get("ui_rules"), list) else []):
        if not isinstance(item, dict) or len(rules) >= 40:
            continue
        pattern, flags = _safe_regex(item.get("pattern"), item.get("flags"))
        action = str(item.get("action") or "open_popup")
        if action not in UI_ACTIONS:
            raise CardMediaError("invalid UI action")
        target = _clean_id(item.get("target_id"), "target_id", optional=True)
        if action == "switch_bgm" and allowed_assets.get(target) != "bgm":
            raise CardMediaError("UI rule BGM target is invalid")
        if action == "set_scene" and target not in world_ids:
            raise CardMediaError("UI rule scene target is invalid")
        rules.append({
            "id": _clean_id(item.get("id") or f"ui-rule-{index + 1}", "ui_rule_id"),
            "name": str(item.get("name") or f"界面规则 {index + 1}")[:80],
            "enabled": item.get("enabled") is not False,
            "pattern": pattern,
            "flags": flags,
            "action": action,
            "target_id": target,
            "template_html": _safe_markup(item.get("template_html"), 30000, "html"),
            "scoped_css": _safe_markup(item.get("scoped_css"), 30000, "css"),
            "duration_ms": max(0, min(120000, int(item.get("duration_ms") or 0))),
            "order": max(-10000, min(10000, int(item.get("order") or index + 1))),
            "remove_match": item.get("remove_match") is not False,
        })
    sidebars: list[dict] = []
    for index, item in enumerate(raw.get("sidebars") if isinstance(raw.get("sidebars"), list) else []):
        if not isinstance(item, dict) or len(sidebars) >= 20:
            continue
        sidebar_id = _clean_id(item.get("id") or f"sidebar-{index + 1}", "sidebar_id")
        pattern, flags = ("", "")
        if str(item.get("open_pattern") or "").strip():
            pattern, flags = _safe_regex(item.get("open_pattern"), item.get("flags"))
        world_id = _clean_id(item.get("world_entry_id"), "world_entry_id", optional=True)
        mode = "worldbook" if item.get("content_mode") == "worldbook" else "static"
        if mode == "worldbook" and world_id not in world_ids:
            raise CardMediaError("sidebar worldbook target is invalid")
        sidebars.append({
            "id": sidebar_id,
            "name": str(item.get("name") or f"侧栏 {index + 1}")[:80],
            "enabled": item.get("enabled") is not False,
            "position": "left" if item.get("position") == "left" else "right",
            "width": max(240, min(720, int(item.get("width") or 340))),
            "order": max(-10000, min(10000, int(item.get("order") or index + 1))),
            "trigger_label": str(item.get("trigger_label") or item.get("name") or "侧栏")[:24],
            "open_pattern": pattern,
            "flags": flags,
            "content_mode": mode,
            "world_entry_id": world_id,
            "content_html": _safe_markup(item.get("content_html"), 50000, "html"),
            "scoped_css": _safe_markup(item.get("scoped_css"), 30000, "css"),
        })
    sidebar_ids = {item["id"] for item in sidebars}
    if any(rule["action"] == "open_sidebar" and rule["target_id"] not in sidebar_ids for rule in rules):
        raise CardMediaError("UI rule sidebar target is invalid")
    galgame = _normalize_galgame(raw.get("galgame"), allowed_assets)
    return {
        "version": 1,
        "bgm": {
            "enabled": bool(bgm_raw.get("enabled")),
            "default_asset_id": default_bgm,
            "autoplay": "after-interaction",
            "volume": max(0.0, min(1.0, float(bgm_raw.get("volume", 0.45)))),
            "loop": bgm_raw.get("loop") is not False,
            "show_floating_player": bgm_raw.get("show_floating_player") is not False,
        },
        "ui_rules": sorted(rules, key=lambda item: (item["order"], item["name"])),
        "sidebars": sorted(sidebars, key=lambda item: (item["order"], item["name"])),
        "galgame": galgame,
        "chat_shell": _normalize_chat_shell(raw.get("chat_shell")),
    }


DEFAULT_PORTRAIT_DIRECTIVE = r"\[(?:立绘|portrait|图)[:：]\s*([^\]]+)\]"
DEFAULT_BACKGROUND_DIRECTIVE = r"\[(?:背景|bg|scene)[:：]\s*([^\]]+)\]"


def _normalize_galgame(value: object, allowed_assets: dict[str, str]) -> dict:
    """校验并归一化 galgame（横板立绘对话）配置。未知字段一律丢弃。"""
    raw = value if isinstance(value, dict) else {}
    default_portrait = _clean_id(raw.get("default_portrait_id"), "asset_id", optional=True)
    if default_portrait and allowed_assets.get(default_portrait) not in {"portrait", "spine"}:
        raise CardMediaError("default portrait is not an owned portrait/spine asset")
    default_background = _clean_id(raw.get("default_background_id"), "asset_id", optional=True)
    if default_background and allowed_assets.get(default_background) != "background":
        raise CardMediaError("default background is not an owned background asset")

    def _directive(candidate: object, fallback: str) -> str:
        text = str(candidate or "").strip()
        if not text:
            return fallback
        try:
            pattern, _ = _safe_regex(text, "")
        except CardMediaError:
            return fallback
        return pattern

    layout = raw.get("portrait_layout")
    return {
        "enabled": bool(raw.get("enabled")),
        "dialogue_position": "top" if raw.get("dialogue_position") == "top" else "bottom",
        "portrait_layout": layout if layout in {"center", "left", "right", "dual"} else "center",
        "default_portrait_id": default_portrait,
        "default_background_id": default_background,
        "portrait_directive": _directive(raw.get("portrait_directive"), DEFAULT_PORTRAIT_DIRECTIVE),
        "background_directive": _directive(raw.get("background_directive"), DEFAULT_BACKGROUND_DIRECTIVE),
        "hide_bubble_avatar": raw.get("hide_bubble_avatar") is not False,
        "typewriter": raw.get("typewriter") is not False,
    }
