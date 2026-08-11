#!/usr/bin/env python3
import contextlib
import io
import json
import os
from pathlib import Path
import tempfile

import deploy_ai_fengyue_villainy as deploy


def run_retention(root: Path, preferred: dict[str, str]):
    stdout = io.StringIO()
    script = deploy.managed_backup_retention_script(str(root.resolve()), preferred)
    with contextlib.redirect_stdout(stdout):
        exec(compile(script, "<managed-backup-retention>", "exec"), {})
    return json.loads(stdout.getvalue())


def write_file(path: Path, size: int, mtime: int):
    path.write_bytes(b"x" * size)
    os.utime(path, (mtime, mtime))


def main():
    with tempfile.TemporaryDirectory(prefix="homer-backup-retention-") as temp_dir:
        root = Path(temp_dir).resolve()
        old_db = root / "ai_fengyue-before-community-versions-20260810-010101.sqlite3"
        current_db = root / "ai_fengyue-current-20260811-020202.sqlite3"
        new_db = root / "ai_fengyue-before-community-versions-20260812-030303.sqlite3"
        old_frontend = root / "frontend-source-current-20260811-020202.tgz"
        new_frontend = root / "frontend-source-before-community-versions-20260812-030303.tgz"
        unrelated = root / "ai_fengyue.sqlite3.manual-recovery.bak"
        unrelated_dir = root / "security-snapshot"
        unrelated_dir.mkdir()
        for index, path in enumerate((old_db, current_db, new_db, old_frontend, new_frontend, unrelated), start=1):
            write_file(path, index, 100 + index)

        result = run_retention(
            root,
            {
                "database": new_db.name,
                "frontend": new_frontend.name,
            },
        )
        assert result["retention"] == 1
        assert result["removed_count"] == 3
        assert result["kept"] == {"database": new_db.name, "frontend": new_frontend.name}
        assert new_db.is_file() and new_frontend.is_file()
        assert unrelated.is_file() and unrelated_dir.is_dir()
        assert not old_db.exists() and not current_db.exists() and not old_frontend.exists()

    with tempfile.TemporaryDirectory(prefix="homer-backup-retention-latest-") as temp_dir:
        root = Path(temp_dir).resolve()
        older = root / "frontend-source-current-20260811-010101.tgz"
        latest = root / "frontend-source-before-community-versions-20260812-020202.tgz"
        write_file(older, 1, 100)
        write_file(latest, 1, 200)
        result = run_retention(root, {"database": "", "frontend": ""})
        assert result["kept"] == {"frontend": latest.name}
        assert latest.is_file() and not older.exists()

    command = deploy.managed_backup_retention_command(
        "/opt/ai-fengyue-backend/backups",
        {"database": "example", "frontend": ""},
    )
    assert command.startswith('python3 -c "import base64;exec(base64.b64decode(')
    print(json.dumps({"managed_backup_retention": True, "retention": deploy.MANAGED_BACKUP_RETENTION}))


if __name__ == "__main__":
    main()
