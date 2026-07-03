#!/usr/bin/env python3
"""同步上游 aifun.wiki 角色卡到本地 local_apps 表 + 下载封面图。

在服务器上运行（能直连 aifun.wiki，写本地 sqlite）：
  python3 sync_upstream_content.py --pages 4 --db /opt/ai-fengyue-backend/data/ai_fengyue.sqlite3 \
      --media-dir /opt/ai-fengyue-backend/data/media --public-base https://patcher.villainy.top

断点续传：已存在且封面已下载的角色会 skip（除非 --force）。
"""
from __future__ import annotations
import argparse
import json
import os
import sqlite3
import time
import uuid
from urllib.error import HTTPError
from urllib.parse import urlparse, quote
from urllib.request import Request, urlopen

UPSTREAM = "https://aifun.wiki"
UA = "Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36 OkHttp"


def log(msg: str) -> None:
    print(f"[sync] {msg}", flush=True)


def rebrand(value):
    repl = {
        "AI风月": "AI星月", "风月AI": "星月AI", "风月币": "星月币", "风月": "星月",
        "aifun.wiki": "patcher.villainy.top",
        "https://aifun.wiki": "https://patcher.villainy.top",
        "http://aifun.wiki": "https://patcher.villainy.top",
    }
    if isinstance(value, str):
        for a, b in repl.items():
            value = value.replace(a, b)
        return value
    if isinstance(value, list):
        return [rebrand(v) for v in value]
    if isinstance(value, dict):
        return {k: rebrand(v) for k, v in value.items()}
    return value


def http_get_json(url: str, timeout: int = 25):
    req = Request(url, headers={"User-Agent": UA, "X-Language": "zh-Hans",
                                "Accept": "application/json, */*", "Referer": UPSTREAM + "/"})
    with urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8", errors="replace"))


def http_get_bytes(url: str, timeout: int = 30):
    req = Request(url, headers={"User-Agent": UA, "Referer": UPSTREAM + "/",
                                "Accept": "image/avif,image/webp,image/png,image/*,*/*"})
    with urlopen(req, timeout=timeout) as resp:
        return resp.read(), resp.headers.get("Content-Type", "image/jpeg")


EXT_BY_CTYPE = {"image/png": ".png", "image/jpeg": ".jpg", "image/webp": ".webp",
                "image/avif": ".avif", "image/gif": ".gif"}


def download_cover(cover_url: str, media_dir: str, app_id: str, public_base: str) -> tuple[str, str] | None:
    """下载封面，返回 (local_url, local_path)。失败返回 None。"""
    if not cover_url or not cover_url.startswith("http"):
        return None
    try:
        raw, ctype = http_get_bytes(cover_url)
    except Exception as exc:
        log(f"  cover download failed {app_id}: {exc}")
        return None
    ext = EXT_BY_CTYPE.get(ctype.split(";")[0].strip(), ".jpg")
    cover_dir = os.path.join(media_dir, "cover")
    os.makedirs(cover_dir, exist_ok=True)
    fname = f"{app_id}{ext}"
    fpath = os.path.join(cover_dir, fname)
    with open(fpath, "wb") as f:
        f.write(raw)
    local_url = public_base.rstrip("/") + "/media-cache/cover/" + fname
    return local_url, fpath


def fetch_detail(app_id: str) -> dict:
    """补 description + opening_statement。失败返回空。"""
    out = {}
    try:
        d = http_get_json(f"{UPSTREAM}/go/api/apps/{app_id}")
        data = d.get("data") if isinstance(d, dict) else None
        if isinstance(data, dict):
            out["description"] = data.get("description") or ""
            out["language"] = data.get("language") or ""
            out["gender"] = data.get("gender") or 0
    except Exception:
        pass
    try:
        p = http_get_json(f"{UPSTREAM}/console/api/installed-apps/{app_id}/parameters")
        if isinstance(p, dict):
            out["opening_statement"] = p.get("opening_statement") or ""
            sq = p.get("suggested_questions")
            out["suggested_questions"] = sq if isinstance(sq, list) else []
    except Exception:
        pass
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="/opt/ai-fengyue-backend/data/ai_fengyue.sqlite3")
    ap.add_argument("--media-dir", default="/opt/ai-fengyue-backend/data/media")
    ap.add_argument("--public-base", default="https://patcher.villainy.top")
    ap.add_argument("--pages", type=int, default=4, help="抓多少页（每页30个）")
    ap.add_argument("--start-page", type=int, default=1)
    ap.add_argument("--sleep", type=float, default=0.4, help="请求间隔秒")
    ap.add_argument("--timeout", type=int, default=25, help="单次请求超时秒数")
    ap.add_argument("--retries", type=int, default=1, help="页面请求失败后的重试次数")
    ap.add_argument("--retry-sleep", type=float, default=8.0, help="重试前等待秒数")
    ap.add_argument("--force", action="store_true", help="已存在也重新抓")
    ap.add_argument("--no-detail", action="store_true", help="跳过详情/开场白抓取（更快）")
    ap.add_argument("--report", help="写入 JSON 同步报告，记录成功页和失败页")
    args = ap.parse_args()

    conn = sqlite3.connect(args.db, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=30000")
    try:
        conn.execute("PRAGMA journal_mode=WAL")
    except Exception:
        pass
    ensure_table(conn)

    total_new = 0
    total_img = 0
    ok_pages = []
    failed_pages = []
    for page in range(args.start_page, args.start_page + args.pages):
        url = f"{UPSTREAM}/go/api/explore/search?page={page}&page_size=30"
        resp = None
        last_exc = None
        for attempt in range(args.retries + 1):
            try:
                resp = http_get_json(url, timeout=args.timeout)
                last_exc = None
                break
            except Exception as exc:
                last_exc = exc
                if attempt < args.retries:
                    wait = args.retry_sleep * (attempt + 1)
                    log(f"page {page} fetch failed (attempt {attempt + 1}/{args.retries + 1}): {exc}; retry in {wait:.1f}s")
                    time.sleep(wait)
        if last_exc is not None:
            code = getattr(last_exc, "code", None) if isinstance(last_exc, HTTPError) else None
            log(f"page {page} fetch failed: {last_exc}")
            failed_pages.append({"page": page, "error": str(last_exc), "code": code})
            continue
        apps = (((resp or {}).get("data") or {}).get("apps")) or []
        if not apps:
            log(f"page {page} empty, stop.")
            ok_pages.append({"page": page, "apps": 0, "empty": True})
            break
        log(f"page {page}: {len(apps)} apps")
        ok_pages.append({"page": page, "apps": len(apps), "empty": False})
        for idx, app in enumerate(apps):
            app_id = str(app.get("id") or "").strip()
            if not app_id:
                continue
            existing = conn.execute("select id, cover_url from local_apps where id=?", (app_id,)).fetchone()
            if existing and existing["cover_url"] and not args.force:
                continue
            # 先取原始封面（catai.wiki，不受 rebrand 影响，但保险起见在 rebrand 前取）
            cover_origin = (app.get("cover") or "").strip()
            app = rebrand(app)
            sort_weight = (args.pages * 30 * 1000) - (page * 30 + idx)  # 越靠前权重越大

            cover_local = None
            if cover_origin:
                res = download_cover(cover_origin, args.media_dir, app_id, args.public_base)
                if res:
                    cover_local = res[0]
                    total_img += 1

            detail = {} if args.no_detail else fetch_detail(app_id)
            if not args.no_detail:
                detail = rebrand(detail)
                time.sleep(args.sleep)

            record = {
                "id": app_id,
                "name": app.get("name") or "",
                "summary": app.get("summary") or "",
                "description": detail.get("description") or "",
                "cover_url": cover_local or "",
                "cover_origin": cover_origin,
                "tags": [t.get("name") for t in (app.get("tags") or []) if isinstance(t, dict) and t.get("name")],
                "opening_statement": detail.get("opening_statement") or "",
                "suggested_questions": detail.get("suggested_questions") or [],
                "age_rating": app.get("age_rating") or 0,
                "gender": detail.get("gender") or app.get("gender") or 0,
                "language": detail.get("language") or "zh-Hans",
                "players_count": app.get("players_count") or 0,
                "like_count": app.get("like_count") or 0,
                "sort_weight": sort_weight,
            }
            upsert(conn, record)
            total_new += 1
        conn.commit()
        time.sleep(args.sleep)

    cnt = conn.execute("select count(*) from local_apps where source='upstream'").fetchone()[0]
    log(f"done. processed={total_new} images={total_img} total_upstream_in_db={cnt}")
    if args.report:
        report = {
            "db": args.db,
            "media_dir": args.media_dir,
            "public_base": args.public_base,
            "start_page": args.start_page,
            "pages": args.pages,
            "processed": total_new,
            "images": total_img,
            "total_upstream_in_db": cnt,
            "ok_pages": ok_pages,
            "failed_pages": failed_pages,
            "created_at": int(time.time()),
        }
        with open(args.report, "w", encoding="utf-8") as fh:
            json.dump(report, fh, ensure_ascii=False, indent=2)
            fh.write("\n")
    conn.close()
    return 0


def ensure_table(conn):
    conn.executescript("""
        create table if not exists local_apps (
            id text primary key, source text not null default 'upstream', owner_user_id text,
            name text, summary text, description text, cover_url text, cover_origin text,
            tags text, opening_statement text, suggested_questions text, pre_prompt text, llm_model text,
            age_rating integer default 0, gender integer default 0, language text,
            players_count integer default 0, like_count integer default 0,
            status text not null default 'published', is_public integer not null default 1,
            sort_weight integer default 0, created_at integer not null, updated_at integer not null
        );
        create index if not exists idx_local_apps_source on local_apps(source, sort_weight desc, updated_at desc);
        create index if not exists idx_local_apps_owner on local_apps(owner_user_id, updated_at desc);
    """)
    conn.commit()


def upsert(conn, r):
    ts = int(time.time() * 1000)
    existing = conn.execute("select id from local_apps where id=?", (r["id"],)).fetchone()
    fields = dict(
        source="upstream", name=r["name"], summary=r["summary"], description=r["description"],
        cover_url=r["cover_url"], cover_origin=r["cover_origin"],
        tags=json.dumps(r["tags"], ensure_ascii=False),
        opening_statement=r["opening_statement"],
        suggested_questions=json.dumps(r["suggested_questions"], ensure_ascii=False),
        age_rating=int(r["age_rating"]), gender=int(r["gender"]), language=r["language"],
        players_count=int(r["players_count"]), like_count=int(r["like_count"]),
        sort_weight=int(r["sort_weight"]), updated_at=ts,
    )
    if existing:
        cols = ", ".join(f"{k}=?" for k in fields)
        conn.execute(f"update local_apps set {cols} where id=?", (*fields.values(), r["id"]))
    else:
        fields["id"] = r["id"]
        fields["created_at"] = ts
        fields["status"] = "published"
        fields["is_public"] = 1
        cols = ", ".join(fields.keys())
        ph = ", ".join("?" for _ in fields)
        conn.execute(f"insert into local_apps({cols}) values({ph})", tuple(fields.values()))


if __name__ == "__main__":
    raise SystemExit(main())
