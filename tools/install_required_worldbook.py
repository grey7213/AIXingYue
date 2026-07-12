import argparse
import json
import os
import sqlite3
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="Install the required first world-book entry into all AI Xingyue role cards.")
    parser.add_argument("--db", type=Path, required=True)
    parser.add_argument("--worldbook", type=Path, required=True)
    args = parser.parse_args()

    os.environ["REQUIRED_WORLD_BOOK_PATH"] = str(args.worldbook.resolve())
    from ai_fengyue_local_server import ensure_required_world_info, REQUIRED_WORLD_BOOK_ID

    conn = sqlite3.connect(str(args.db))
    conn.row_factory = sqlite3.Row
    rows = conn.execute("select id,extra_settings from local_apps").fetchall()
    changed = 0
    with conn:
        for row in rows:
            try:
                extras = json.loads(row["extra_settings"] or "{}")
            except Exception:
                extras = {}
            if not isinstance(extras, dict):
                extras = {}
            before = extras.get("world_info") if isinstance(extras.get("world_info"), list) else []
            after = ensure_required_world_info(before)
            if before != after:
                extras["world_info"] = after
                conn.execute(
                    "update local_apps set extra_settings=? where id=?",
                    (json.dumps(extras, ensure_ascii=False, separators=(",", ":")), row["id"]),
                )
                changed += 1
        try:
            conn.execute("update role_card_annotations set has_world_info=1")
        except sqlite3.OperationalError:
            pass
    first = conn.execute(
        "select extra_settings from local_apps order by id limit 1"
    ).fetchone()
    verified = False
    if first:
        data = json.loads(first[0] or "{}")
        world = data.get("world_info") if isinstance(data, dict) else []
        verified = bool(world and world[0].get("id") == REQUIRED_WORLD_BOOK_ID)
    print(json.dumps({"total": len(rows), "changed": changed, "first_entry_verified": verified}, ensure_ascii=False))
    return 0 if verified or not rows else 1


if __name__ == "__main__":
    raise SystemExit(main())
