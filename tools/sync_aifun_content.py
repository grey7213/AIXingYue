#!/usr/bin/env python3
import argparse
import hashlib
import json
import os
import re
import sqlite3
import sys
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qsl, urlencode, urlparse
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = ROOT / "output" / "zip-1-repack" / "local-server" / "ai_fengyue_local.sqlite3"
DEFAULT_UPSTREAM = os.environ.get("UPSTREAM_CONTENT_BASE", "https://aifun.wiki/").rstrip("/") + "/"
URL_RE = re.compile(r"https?://[^\s\"'<>]+")


CORE_REQUESTS = [
    ("GET", "console/api/app_site/list", "lang=zh-Hans"),
    ("GET", "console/api/emojis", "lang=zh-Hans"),
    ("GET", "console/api/v1/activities/gift-packs", "lang=zh-Hans"),
    ("GET", "console/api/workspaces/sidebar_notice", "lang=zh-Hans"),
    ("GET", "console/api/workspaces/announcements", "lang=zh-Hans&page=1&limit=20"),
    ("GET", "go/api/posts/recommended", "lang=zh-Hans&page=1&limit=20"),
    ("GET", "go/api/explore/tags-recommend", "lang=zh-Hans"),
    ("GET", "go/api/explore/search", "lang=zh-Hans&ranking=personal_tailor&page=1&limit=20"),
    ("GET", "go/api/explore/search", "lang=zh-Hans&ranking=recommended_week&page=1&limit=20"),
    ("GET", "go/api/explore/search", "lang=zh-Hans&ranking=recommended_month&page=1&limit=20"),
    ("GET", "go/api/explore/search", "lang=zh-Hans&ranking=latest&page=1&limit=20"),
    ("GET", "go/api/explore/search", "lang=zh-Hans&ranking=hot&page=1&limit=20"),
    ("GET", "console/api/model-list", "lang=zh-Hans"),
]


def now_ms() -> int:
    return int(time.time() * 1000)


def normalize_query(query: str | None) -> str:
    return urlencode(sorted(parse_qsl(query or "", keep_blank_values=True)), doseq=True)


def cache_key(method: str, path: str, query: str | None) -> str:
    q = normalize_query(query)
    return f"{method.upper()} {path.lstrip('/')}" + (f"?{q}" if q else "")


def ensure_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        create table if not exists content_cache (
            id integer primary key autoincrement,
            cache_key text unique not null,
            method text not null,
            path text not null,
            query text,
            status integer not null,
            response_json text not null,
            raw_bytes integer not null,
            source_url text,
            fetched_at integer not null,
            updated_at integer not null
        );
        create index if not exists idx_content_cache_path on content_cache(path);
        create table if not exists content_media_urls (
            url text primary key,
            first_seen_cache_key text,
            guessed_kind text,
            content_length integer,
            content_type text,
            last_checked_at integer,
            local_path text,
            local_url text,
            downloaded_bytes integer,
            download_status text,
            downloaded_at integer,
            error text
        );
        """
    )
    conn.commit()
    ensure_columns(
        conn,
        "content_media_urls",
        {
            "local_path": "text",
            "local_url": "text",
            "downloaded_bytes": "integer",
            "download_status": "text",
            "downloaded_at": "integer",
            "error": "text",
        },
    )


def ensure_columns(conn: sqlite3.Connection, table: str, columns: dict[str, str]) -> None:
    existing = {row[1] for row in conn.execute(f"pragma table_info({table})").fetchall()}
    for name, column_type in columns.items():
        if name not in existing:
            conn.execute(f"alter table {table} add column {name} {column_type}")
    conn.commit()


def rebrand_text(value: str, brand: str) -> str:
    replacements = {
        "AI风月": brand,
        "风月AI": "星月AI",
        "风月币": "星月币",
        "风月": "星月",
        "aifun.wiki": "patcher.villainy.top",
        "https://aifun.wiki": "https://patcher.villainy.top",
        "http://aifun.wiki": "https://patcher.villainy.top",
    }
    for old, new in replacements.items():
        value = value.replace(old, new)
    return value


def rebrand_data(value, brand: str):
    if isinstance(value, str):
        return rebrand_text(value, brand)
    if isinstance(value, list):
        return [rebrand_data(item, brand) for item in value]
    if isinstance(value, dict):
        return {key: rebrand_data(item, brand) for key, item in value.items()}
    return value


def build_url(base: str, path: str, query: str | None) -> str:
    url = base.rstrip("/") + "/" + path.lstrip("/")
    if query:
        url += "?" + query
    return url


def fetch_json(base: str, path: str, query: str, timeout: int) -> tuple[int, bytes, object]:
    url = build_url(base, path, query)
    req = Request(
        url,
        headers={
            "User-Agent": "ai_chat/1.12.20 (org.nebula.horizon.composeai; build:260; Android 13; SDK 33; google sdk_gphone64_x86_64) OkHttp",
            "X-Language": "zh-Hans",
            "locale": "zh-Hans",
            "Cookie": "locale=zh-Hans",
            "Accept": "application/json, text/plain, */*",
        },
    )
    with urlopen(req, timeout=timeout) as resp:
        raw = resp.read()
        text = raw.decode("utf-8", errors="replace").strip()
        return resp.status, raw, json.loads(text) if text else {}


def upsert_cache(conn: sqlite3.Connection, method: str, path: str, query: str, status: int, payload, raw_len: int, source_url: str) -> str:
    key = cache_key(method, path, query)
    ts = now_ms()
    response_json = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    conn.execute(
        """
        insert into content_cache(cache_key,method,path,query,status,response_json,raw_bytes,source_url,fetched_at,updated_at)
        values(?,?,?,?,?,?,?,?,?,?)
        on conflict(cache_key) do update set
            method=excluded.method,
            path=excluded.path,
            query=excluded.query,
            status=excluded.status,
            response_json=excluded.response_json,
            raw_bytes=excluded.raw_bytes,
            source_url=excluded.source_url,
            updated_at=excluded.updated_at
        """,
        (key, method.upper(), path.lstrip("/"), query, status, response_json, raw_len, source_url, ts, ts),
    )
    return key


def iter_urls(value):
    if isinstance(value, str):
        for match in URL_RE.findall(value):
            yield match.rstrip(".,;)]")
    elif isinstance(value, list):
        for item in value:
            yield from iter_urls(item)
    elif isinstance(value, dict):
        for item in value.values():
            yield from iter_urls(item)


def guess_kind(url: str) -> str:
    path = urlparse(url).path.lower()
    if path.endswith((".png", ".jpg", ".jpeg", ".webp", ".gif", ".avif")):
        return "image"
    if path.endswith((".mp4", ".webm", ".mov", ".m4v")):
        return "video"
    if path.endswith((".mp3", ".wav", ".m4a", ".ogg")):
        return "audio"
    return "url"


def is_download_candidate(url: str, kind: str | None, content_type: str | None = None) -> bool:
    host = urlparse(url).netloc.lower()
    path = urlparse(url).path.lower()
    if host in {
        "catai.wiki",
        "static.catai.wiki",
        "image.catai.wiki",
        "user.catai.wiki",
        "pub-197e0f22cc074a569b53a521b65036f1.r2.dev",
        "i.ibb.co",
        "i.postimg.cc",
    }:
        return True
    if kind in ("image", "video", "audio"):
        return True
    if content_type and content_type.split(";", 1)[0].strip().lower().startswith(("image/", "video/", "audio/")):
        return True
    return bool(path.endswith((".png", ".jpg", ".jpeg", ".webp", ".gif", ".avif", ".mp4", ".webm", ".mov", ".m4v", ".mp3", ".wav", ".m4a", ".ogg")))


def extension_for(url: str, content_type: str | None) -> str:
    path = urlparse(url).path
    suffix = Path(path).suffix.lower()
    if suffix and len(suffix) <= 8:
        return suffix
    ctype = (content_type or "").split(";", 1)[0].strip().lower()
    return {
        "image/jpeg": ".jpg",
        "image/png": ".png",
        "image/webp": ".webp",
        "image/gif": ".gif",
        "image/avif": ".avif",
        "video/mp4": ".mp4",
        "video/webm": ".webm",
        "audio/mpeg": ".mp3",
        "audio/mp4": ".m4a",
        "audio/wav": ".wav",
        "audio/ogg": ".ogg",
        "text/css": ".css",
    }.get(ctype, ".bin")


def media_rel_path(url: str, content_type: str | None = None) -> str:
    parsed = urlparse(url)
    host = parsed.netloc.lower().replace(":", "_")
    digest = hashlib.sha256(url.encode("utf-8")).hexdigest()
    ext = extension_for(url, content_type)
    return f"{host}/{digest[:2]}/{digest}{ext}"


def record_media_urls(conn: sqlite3.Connection, key: str, payload) -> int:
    count = 0
    for url in sorted(set(iter_urls(payload))):
        if "patcher.villainy.top" in url:
            continue
        conn.execute(
            """
            insert into content_media_urls(url,first_seen_cache_key,guessed_kind)
            values(?,?,?)
            on conflict(url) do nothing
            """,
            (url, key, guess_kind(url)),
        )
        count += 1
    return count


def item_count(value) -> int:
    best = 0
    if isinstance(value, list):
        best = max(best, len(value))
        for item in value:
            best = max(best, item_count(item))
    elif isinstance(value, dict):
        for key, item in value.items():
            if key in ("data", "list", "items", "apps", "posts", "records", "installed_apps") and isinstance(item, list):
                best = max(best, len(item))
            best = max(best, item_count(item))
    return best


def iter_dicts(value):
    if isinstance(value, dict):
        yield value
        for item in value.values():
            yield from iter_dicts(item)
    elif isinstance(value, list):
        for item in value:
            yield from iter_dicts(item)


def looks_like_app_record(value: dict) -> bool:
    if not isinstance(value.get("id"), str) or len(value["id"]) < 16:
        return False
    app_markers = {
        "app_model_config_id",
        "pre_prompt_length",
        "pre_length",
        "world_book_length",
        "players_count",
        "summary",
        "cover",
        "mode",
    }
    return bool(app_markers.intersection(value.keys()))


def collect_app_ids_from_cache(conn: sqlite3.Connection, limit: int) -> list[str]:
    app_ids: set[str] = set()
    rows = conn.execute(
        """
        select response_json
        from content_cache
        where path in ('go/api/explore/search','go/api/posts/recommended','console/api/app_site/list')
           or path like 'go/api/apps/%'
           or path like 'console/api/installed-apps/%'
        order by updated_at desc, fetched_at desc
        limit 1000
        """
    ).fetchall()
    for (text,) in rows:
        try:
            payload = json.loads(text)
        except Exception:
            continue
        for obj in iter_dicts(payload):
            if looks_like_app_record(obj):
                app_ids.add(obj["id"])
            nested_app = obj.get("app")
            if isinstance(nested_app, dict) and looks_like_app_record(nested_app):
                app_ids.add(nested_app["id"])
            app_id = obj.get("app_id")
            if isinstance(app_id, str) and len(app_id) >= 16:
                app_ids.add(app_id)
    return sorted(app_ids)[:limit]


def app_detail_requests(app_ids: list[str]) -> list[tuple[str, str, str]]:
    requests: list[tuple[str, str, str]] = []
    for app_id in app_ids:
        requests.extend([
            ("GET", f"go/api/apps/{app_id}", "lang=zh-Hans"),
            ("GET", f"console/api/installed-apps/{app_id}", "lang=zh-Hans"),
            ("GET", f"console/api/apps/{app_id}/user_app_model_config", "lang=zh-Hans"),
            ("GET", f"console/api/installed-apps/{app_id}/conversations", "limit=100&pinned=false&lang=zh-Hans"),
        ])
    return requests


def paginate_query(query: str, page: int, limit: int) -> str:
    pairs = dict(parse_qsl(query or "", keep_blank_values=True))
    pairs["page"] = str(page)
    pairs.setdefault("limit", str(limit))
    return urlencode(pairs)


def discover_requests_from_log(conn: sqlite3.Connection, limit: int) -> list[tuple[str, str, str]]:
    try:
        rows = conn.execute(
            """
            select distinct method, ltrim(path, '/') as path, coalesce(query, '') as query
            from request_log
            where method='GET' and (path like '/go/%' or path like '/console/%')
            order by id desc
            limit ?
            """,
            (limit,),
        ).fetchall()
    except sqlite3.OperationalError:
        return []
    out = []
    for method, path, query in rows:
        if path.startswith(("console/api/login", "console/api/register", "console/api/user/point", "console/api/account/profile", "go/api/account/")):
            continue
        out.append((method, path, query or ""))
    return out


def head_media(url: str, timeout: int) -> tuple[int | None, str | None]:
    req = Request(url, method="HEAD", headers={"User-Agent": "AI-Xingyue-content-estimator/1.0"})
    try:
        with urlopen(req, timeout=timeout) as resp:
            length = resp.headers.get("Content-Length")
            return int(length) if length and length.isdigit() else None, resp.headers.get("Content-Type")
    except Exception:
        return None, None


def download_one(url: str, output_dir: Path, public_prefix: str, timeout: int, max_bytes: int) -> dict:
    headers = {"User-Agent": "AI-Xingyue-media-mirror/1.0"}
    req = Request(url, headers=headers)
    with urlopen(req, timeout=timeout) as resp:
        content_type = resp.headers.get("Content-Type")
        length = resp.headers.get("Content-Length")
        expected = int(length) if length and length.isdigit() else None
        if expected is not None and expected > max_bytes:
            raise ValueError(f"content too large: {expected} > {max_bytes}")
        rel = media_rel_path(url, content_type)
        target = output_dir / rel
        tmp = target.with_suffix(target.suffix + ".tmp")
        target.parent.mkdir(parents=True, exist_ok=True)
        total = 0
        with tmp.open("wb") as fh:
            while True:
                chunk = resp.read(1024 * 256)
                if not chunk:
                    break
                total += len(chunk)
                if total > max_bytes:
                    fh.close()
                    tmp.unlink(missing_ok=True)
                    raise ValueError(f"download exceeded max bytes: {total} > {max_bytes}")
                fh.write(chunk)
        tmp.replace(target)
        local_url = public_prefix.rstrip("/") + "/" + rel.replace("\\", "/")
        return {
            "local_path": str(target),
            "local_url": local_url,
            "downloaded_bytes": total,
            "content_length": expected if expected is not None else total,
            "content_type": content_type,
        }


def download_media(conn: sqlite3.Connection, output_dir: Path, public_prefix: str, timeout: int, limit: int, max_bytes: int) -> tuple[int, int, int]:
    rows = conn.execute(
        """
        select url, guessed_kind, content_type from content_media_urls
        where coalesce(download_status, '') != 'downloaded'
        order by case when guessed_kind in ('image','video','audio') then 0 else 1 end, url
        limit ?
        """,
        (limit,),
    ).fetchall()
    downloaded = 0
    skipped = 0
    bytes_total = 0
    for url, kind, content_type in rows:
        if not is_download_candidate(url, kind, content_type):
            conn.execute(
                "update content_media_urls set download_status=?, error=? where url=?",
                ("skipped", "not a media/content resource", url),
            )
            skipped += 1
            continue
        try:
            result = download_one(url, output_dir, public_prefix, timeout, max_bytes)
            conn.execute(
                """
                update content_media_urls
                set local_path=?, local_url=?, downloaded_bytes=?, content_length=?, content_type=?,
                    download_status='downloaded', downloaded_at=?, error=null
                where url=?
                """,
                (
                    result["local_path"],
                    result["local_url"],
                    result["downloaded_bytes"],
                    result["content_length"],
                    result["content_type"],
                    now_ms(),
                    url,
                ),
            )
            downloaded += 1
            bytes_total += int(result["downloaded_bytes"] or 0)
        except Exception as exc:
            conn.execute(
                "update content_media_urls set download_status=?, error=?, downloaded_at=? where url=?",
                ("failed", str(exc)[:300], now_ms(), url),
            )
        conn.commit()
    return downloaded, skipped, bytes_total


def rewrite_cached_media_urls(conn: sqlite3.Connection) -> int:
    mappings = conn.execute(
        "select url, local_url from content_media_urls where download_status='downloaded' and local_url is not null"
    ).fetchall()
    if not mappings:
        return 0
    changed = 0
    rows = conn.execute("select id, response_json from content_cache").fetchall()
    for row_id, text in rows:
        new_text = text
        for old, new in mappings:
            new_text = new_text.replace(old, new)
        if new_text != text:
            conn.execute(
                "update content_cache set response_json=?, updated_at=? where id=?",
                (new_text, now_ms(), row_id),
            )
            changed += 1
    conn.commit()
    return changed


def format_bytes(value: int) -> str:
    units = ["B", "KB", "MB", "GB", "TB"]
    size = float(value)
    for unit in units:
        if size < 1024 or unit == units[-1]:
            return f"{size:.2f} {unit}"
        size /= 1024
    return f"{value} B"


def main() -> int:
    parser = argparse.ArgumentParser(description="Sync AI风月 upstream content into the AI星月 backend SQLite cache.")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--upstream", default=DEFAULT_UPSTREAM)
    parser.add_argument("--brand", default=os.environ.get("APP_BRAND", "AI星月"))
    parser.add_argument("--max-pages", type=int, default=30)
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--timeout", type=int, default=25)
    parser.add_argument("--skip-core", action="store_true", default=False)
    parser.add_argument("--from-request-log", action="store_true", default=False)
    parser.add_argument("--request-log-limit", type=int, default=300)
    parser.add_argument("--from-cached-apps", action="store_true", default=False)
    parser.add_argument("--cached-app-limit", type=int, default=1000)
    parser.add_argument("--head-media", action="store_true")
    parser.add_argument("--head-limit", type=int, default=500)
    parser.add_argument("--download-media", action="store_true")
    parser.add_argument("--download-limit", type=int, default=100000)
    parser.add_argument("--media-dir", type=Path, default=Path("/var/www/ai-fengyue-frontend/media-cache"))
    parser.add_argument("--media-url-prefix", default="https://patcher.villainy.top/media-cache")
    parser.add_argument("--max-media-bytes", type=int, default=200 * 1024 * 1024)
    parser.add_argument("--rewrite-media-urls", action="store_true")
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()

    args.db.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(args.db))
    ensure_schema(conn)

    requests = [] if args.skip_core else list(CORE_REQUESTS)
    if args.from_request_log:
        requests.extend(discover_requests_from_log(conn, args.request_log_limit))
    if args.from_cached_apps:
        requests.extend(app_detail_requests(collect_app_ids_from_cache(conn, args.cached_app_limit)))

    seen = set()
    unique_requests = []
    for method, path, query in requests:
        ident = (method.upper(), path.lstrip("/"), normalize_query(query))
        if ident in seen:
            continue
        seen.add(ident)
        unique_requests.append((method.upper(), path.lstrip("/"), query or ""))

    fetched = 0
    failed = []
    media_found = 0
    for method, path, query in unique_requests:
        page_queries = [query]
        if "page=" in query or path in ("go/api/explore/search", "go/api/posts/recommended", "console/api/workspaces/announcements"):
            page_queries = [paginate_query(query, page, args.limit) for page in range(1, args.max_pages + 1)]
        for page_query in page_queries:
            try:
                status, raw, payload = fetch_json(args.upstream, path, page_query, args.timeout)
                payload = rebrand_data(payload, args.brand)
                key = upsert_cache(conn, method, path, page_query, status, payload, len(raw), build_url(args.upstream, path, page_query))
                media_found += record_media_urls(conn, key, payload)
                conn.commit()
                fetched += 1
                if page_query != query and item_count(payload) == 0:
                    break
            except (HTTPError, URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
                failed.append({"path": path, "query": page_query, "error": str(exc)[:240]})
                if page_query != query:
                    break

    second_pass_requests: list[tuple[str, str, str]] = []
    if args.from_cached_apps:
        second_pass_requests = app_detail_requests(collect_app_ids_from_cache(conn, args.cached_app_limit))
        for method, path, query in second_pass_requests:
            ident = (method.upper(), path.lstrip("/"), normalize_query(query))
            if ident in seen:
                continue
            seen.add(ident)
            try:
                status, raw, payload = fetch_json(args.upstream, path, query, args.timeout)
                payload = rebrand_data(payload, args.brand)
                key = upsert_cache(conn, method, path, query, status, payload, len(raw), build_url(args.upstream, path, query))
                media_found += record_media_urls(conn, key, payload)
                conn.commit()
                fetched += 1
            except (HTTPError, URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
                failed.append({"path": path, "query": query, "error": str(exc)[:240]})

    media_checked = 0
    if args.head_media:
        rows = conn.execute(
            """
            select url from content_media_urls
            where content_length is null and (guessed_kind in ('image','video','audio') or content_type is null)
            limit ?
            """,
            (args.head_limit,),
        ).fetchall()
        for (url,) in rows:
            length, content_type = head_media(url, args.timeout)
            conn.execute(
                "update content_media_urls set content_length=?, content_type=?, last_checked_at=? where url=?",
                (length, content_type, now_ms(), url),
            )
            media_checked += 1
        conn.commit()

    media_downloaded = 0
    media_download_skipped = 0
    media_downloaded_bytes = 0
    if args.download_media:
        media_downloaded, media_download_skipped, media_downloaded_bytes = download_media(
            conn,
            args.media_dir,
            args.media_url_prefix,
            args.timeout,
            args.download_limit,
            args.max_media_bytes,
        )

    rewritten_cache_rows = rewrite_cached_media_urls(conn) if args.rewrite_media_urls else 0

    cache_total, cache_bytes = conn.execute(
        "select count(*), coalesce(sum(raw_bytes),0) from content_cache"
    ).fetchone()
    media_total, media_known, media_bytes = conn.execute(
        """
        select count(*), count(content_length), coalesce(sum(content_length),0)
        from content_media_urls
        """
    ).fetchone()
    dl_total, dl_bytes = conn.execute(
        """
        select count(*), coalesce(sum(downloaded_bytes),0)
        from content_media_urls
        where download_status='downloaded'
        """
    ).fetchone()
    dl_failed = conn.execute(
        "select count(*) from content_media_urls where download_status='failed'"
    ).fetchone()[0]
    dl_skipped_total = conn.execute(
        "select count(*) from content_media_urls where download_status='skipped'"
    ).fetchone()[0]
    by_kind = [
        {"kind": row[0], "count": row[1], "known_bytes": row[2] or 0, "known_size": format_bytes(row[2] or 0)}
        for row in conn.execute(
            "select guessed_kind, count(*), coalesce(sum(content_length),0) from content_media_urls group by guessed_kind order by count(*) desc"
        ).fetchall()
    ]
    report = {
        "db": str(args.db),
        "upstream": args.upstream,
        "fetched_responses_this_run": fetched,
        "failed_count": len(failed),
        "failed": failed[:30],
        "content_cache_rows": cache_total,
        "content_cache_raw_bytes": cache_bytes,
        "content_cache_size": format_bytes(cache_bytes),
        "media_urls_total": media_total,
        "media_urls_new_seen_this_run": media_found,
        "app_detail_requests_generated": len(second_pass_requests),
        "media_urls_head_checked_this_run": media_checked,
        "media_urls_with_known_size": media_known,
        "media_known_bytes": media_bytes,
        "media_known_size": format_bytes(media_bytes),
        "media_downloaded_this_run": media_downloaded,
        "media_download_skipped_this_run": media_download_skipped,
        "media_downloaded_bytes_this_run": media_downloaded_bytes,
        "media_downloaded_size_this_run": format_bytes(media_downloaded_bytes),
        "media_downloaded_total": dl_total,
        "media_downloaded_bytes_total": dl_bytes,
        "media_downloaded_size_total": format_bytes(dl_bytes),
        "media_download_failed_total": dl_failed,
        "media_download_skipped_total": dl_skipped_total,
        "rewritten_content_cache_rows": rewritten_cache_rows,
        "media_by_kind": by_kind,
    }
    text = json.dumps(report, ensure_ascii=False, indent=2)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
