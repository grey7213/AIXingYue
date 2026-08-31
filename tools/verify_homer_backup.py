#!/usr/bin/env python3
"""Independent spot-check of a Homer backup directory.

The backup tool verifies its own work; this script re-checks it from the outside,
comparing archive *contents* against the live server rather than trusting the
manifest. Run after a backup completes.

  python tools/verify_homer_backup.py E:\\homer-backups\\homer-prod-YYYYmmdd-HHMMSS
"""
import argparse
import hashlib
import json
import random
import shlex
import sqlite3
import tarfile
import tempfile
from pathlib import Path

import paramiko
import zstandard

HOST = "38.76.218.46"
USER = "root"
KEY = Path.home() / ".ssh" / "villainy_backup_ed25519"
LIVE_DB = "/opt/ai-fengyue-backend/data/ai_fengyue.sqlite3"
MEDIA_ROOT = "/var/www/ai-fengyue-frontend/media-cache"
SAMPLE_COVERS = 6


def log(message: str) -> None:
    print(f"[verify] {message}", flush=True)


def ssh_run(ssh: paramiko.SSHClient, command: str) -> str:
    _, stdout, stderr = ssh.exec_command(command)
    out = stdout.read().decode("utf-8", errors="replace")
    code = stdout.channel.recv_exit_status()
    if code != 0:
        raise RuntimeError(f"remote failed ({code}): {command}\n"
                           f"{stderr.read().decode('utf-8', errors='replace')}")
    return out


def dctx() -> zstandard.ZstdDecompressor:
    return zstandard.ZstdDecompressor(max_window_size=2 ** 31)


def check_checksums(backup: Path, results: list) -> None:
    """SHA256SUMS.txt must match the files actually sitting on disk."""
    sums = (backup / "SHA256SUMS.txt").read_text(encoding="utf-8").strip().splitlines()
    for line in sums:
        expected, name = line.split("  ", 1)
        path = backup / name
        digest = hashlib.sha256()
        with path.open("rb") as fh:
            for chunk in iter(lambda: fh.read(4 * 1024 * 1024), b""):
                digest.update(chunk)
        ok = digest.hexdigest() == expected
        results.append((f"sha256 {name}", ok, "match" if ok else "MISMATCH"))
        log(f"  {'ok ' if ok else 'FAIL'} sha256 {name}")


def check_database(backup: Path, ssh: paramiko.SSHClient, manifest: dict, results: list) -> None:
    """Decompress the DB and check it two ways.

    Against the manifest: must match exactly — the archive has to contain the
    snapshot the server said it took.

    Against live: only a sanity direction check. A snapshot is a point in time;
    users/conversations/messages keep growing after it, so live >= backup is
    correct and a nonzero delta is information, not a failure.
    """
    tables = ("users", "local_apps", "content_versions", "conversations", "messages",
              "role_card_annotations", "api_settings")
    table_list = ",".join(f"'{t}'" for t in tables)
    live_counts = json.loads(ssh_run(ssh, (
        "python3 -c \"import json,sqlite3;"
        f"c=sqlite3.connect('file:{LIVE_DB}?mode=ro',uri=True);"
        "print(json.dumps({t:c.execute('select count(*) from '+t).fetchone()[0] "
        f"for t in ({table_list})}}))\"")))
    live_sample = json.loads(ssh_run(ssh, (
        "python3 -c \"import json,sqlite3;"
        f"c=sqlite3.connect('file:{LIVE_DB}?mode=ro',uri=True);"
        "print(json.dumps([list(map(str,r)) for r in c.execute("
        "'select id,name,cover_url from local_apps order by id limit 5')]))\"")))

    with tempfile.TemporaryDirectory() as tmp:
        plain = Path(tmp) / "db.sqlite3"
        with (backup / "ai_fengyue.sqlite3.zst").open("rb") as src, plain.open("wb") as dst:
            dctx().copy_stream(src, dst, write_size=8 * 1024 * 1024)
        size = plain.stat().st_size
        conn = sqlite3.connect(f"file:{plain.as_posix()}?immutable=1", uri=True)
        quick = conn.execute("pragma quick_check").fetchone()[0]
        integrity = conn.execute("pragma integrity_check").fetchone()[0]
        journal = conn.execute("pragma journal_mode").fetchone()[0]
        backup_counts = {t: conn.execute(f"select count(*) from {t}").fetchone()[0]
                         for t in tables}
        backup_sample = [list(map(str, r)) for r in conn.execute(
            "select id,name,cover_url from local_apps order by id limit 5")]
        settings_keys = {r[0] for r in conn.execute("select key from api_settings")}
        preset_count = len(json.loads(dict(conn.execute(
            "select key,value from api_settings where key='model_presets'"
        )).get("model_presets", "[]")))
        conn.close()

    results.append(("db quick_check", quick == "ok", quick))
    results.append(("db integrity_check", integrity == "ok", integrity))
    log(f"  {'ok ' if quick == 'ok' else 'FAIL'} quick_check={quick} integrity_check={integrity}")
    results.append(("db journal_mode=delete (self-contained)", journal.lower() == "delete", journal))
    log(f"  {'ok ' if journal.lower() == 'delete' else 'FAIL'} journal_mode={journal}")

    snap = manifest["database_snapshot"]
    size_ok = size == snap["snapshot_bytes"]
    results.append(("db size == manifest snapshot", size_ok,
                    f"archive={size} manifest={snap['snapshot_bytes']}"))
    log(f"  {'ok ' if size_ok else 'FAIL'} size matches manifest snapshot ({size:,} B)")

    manifest_counts = {t: snap["row_counts"][t] for t in tables if t in snap["row_counts"]}
    counts_ok = all(backup_counts[t] == v for t, v in manifest_counts.items())
    results.append(("db row counts == manifest", counts_ok,
                    f"archive={backup_counts} manifest={manifest_counts}"))
    log(f"  {'ok ' if counts_ok else 'FAIL'} row counts match manifest: {backup_counts}")

    grew = {t: live_counts[t] - backup_counts[t] for t in tables}
    direction_ok = all(delta >= 0 for delta in grew.values())
    results.append(("db live >= backup (snapshot is a point in time)", direction_ok, str(grew)))
    drift = {t: d for t, d in grew.items() if d}
    log(f"  {'ok ' if direction_ok else 'FAIL'} live >= backup for every table"
        + (f"; drift since snapshot: {drift}" if drift else "; live unchanged since snapshot"))

    same_sample = backup_sample == live_sample
    results.append(("db first 5 role cards == live", same_sample, ""))
    log(f"  {'ok ' if same_sample else 'FAIL'} first 5 role cards byte-identical to live")

    # api_settings is a flat key/value table. 2026-08-24: production holds LLM
    # config keys only — there is NO 'site_settings' row, so the site copy is
    # currently served from the backend's own defaults. The thing that would
    # actually hurt to lose is the model preset config (endpoints + API keys).
    needed = {"model_presets", "default_model_preset_id", "api_key", "base_url"}
    settings_ok = needed <= settings_keys and preset_count >= 1
    results.append(("db carries LLM config + >=1 model preset", settings_ok,
                    f"keys={sorted(settings_keys)} presets={preset_count}"))
    log(f"  {'ok ' if settings_ok else 'FAIL'} LLM config present, {preset_count} model preset(s), "
        f"{len(settings_keys)} api_settings keys")


def check_media(backup: Path, ssh: paramiko.SSHClient, results: list) -> None:
    """Count entries in the media tar and byte-compare a random sample against live.

    Like the DB, the archive is a point in time: live may have gained covers since,
    so the check is live >= archive rather than equality.
    """
    live_count = int(ssh_run(ssh, f"find {MEDIA_ROOT} -type f | wc -l").strip())
    reservoir: list[tuple[str, bytes]] = []
    members = 0
    covers_seen = 0
    with (backup / "media-cache.tar.zst").open("rb") as fh:
        reader = dctx().stream_reader(fh)
        with tarfile.open(fileobj=reader, mode="r|") as tar:
            for member in tar:
                if not member.isfile():
                    continue
                members += 1
                if not member.name.startswith("media-cache/cover/"):
                    continue
                # Textbook reservoir sampling: every cover has an equal chance of
                # ending up in the sample, and we only ever hold SAMPLE_COVERS of them.
                covers_seen += 1
                if len(reservoir) < SAMPLE_COVERS:
                    reservoir.append((member.name, tar.extractfile(member).read()))
                else:
                    slot = random.randrange(covers_seen)
                    if slot < SAMPLE_COVERS:
                        reservoir[slot] = (member.name, tar.extractfile(member).read())

    ok_count = live_count >= members
    delta = live_count - members
    results.append(("media count: live >= archive", ok_count,
                    f"archive={members} live={live_count}"))
    log(f"  {'ok ' if ok_count else 'FAIL'} media files archive={members} live={live_count}"
        + (f" (+{delta} added since backup)" if delta else " (unchanged)"))
    log(f"  info sampled {len(reservoir)} of {covers_seen} covers for byte comparison")

    for name, blob in reservoir:
        remote = "/" + name.replace("media-cache/", MEDIA_ROOT.lstrip("/") + "/", 1)
        live_hash = ssh_run(ssh, f"sha256sum {shlex.quote(remote)} | cut -d' ' -f1").strip()
        ok = hashlib.sha256(blob).hexdigest() == live_hash
        results.append((f"cover byte-identical: {Path(name).name}", ok, ""))
        log(f"  {'ok ' if ok else 'FAIL'} cover byte-identical {Path(name).name} ({len(blob):,} B)")


def check_tar(backup: Path, filename: str, must_contain: list[str], results: list) -> None:
    """Stream a tar archive and assert the paths that matter are inside it."""
    found: set[str] = set()
    members = 0
    with (backup / filename).open("rb") as fh:
        reader = dctx().stream_reader(fh)
        with tarfile.open(fileobj=reader, mode="r|") as tar:
            for member in tar:
                members += 1
                for needle in must_contain:
                    if needle in member.name:
                        found.add(needle)
    missing = [n for n in must_contain if n not in found]
    ok = not missing
    results.append((f"{filename} contents", ok,
                    f"{members} entries" + (f", missing {missing}" if missing else "")))
    log(f"  {'ok ' if ok else 'FAIL'} {filename}: {members} entries"
        + (f", MISSING {missing}" if missing else ", all expected paths present"))


def check_production_health(ssh: paramiko.SSHClient, results: list) -> None:
    """The backup must not have disturbed anything."""
    active = ssh_run(ssh, "systemctl is-active ai-fengyue-backend homer-dialogue nginx").split()
    ok = active == ["active", "active", "active"]
    results.append(("services active", ok, " ".join(active)))
    log(f"  {'ok ' if ok else 'FAIL'} services: {' '.join(active)}")

    health = ssh_run(ssh, "curl -sS http://127.0.0.1:8008/health").strip()
    results.append(("backend /health", health == "OK", health))
    log(f"  {'ok ' if health == 'OK' else 'FAIL'} backend /health -> {health!r}")

    public = ssh_run(ssh, "curl -sk https://patcher.villainy.top/health").strip()
    results.append(("public /health", public == "OK", public))
    log(f"  {'ok ' if public == 'OK' else 'FAIL'} public /health -> {public!r}")

    csrf = ssh_run(ssh, "curl -sS -o /dev/null -w '%{http_code}' "
                        "http://127.0.0.1:8091/csrf-token").strip()
    results.append(("dialogue runtime /csrf-token", csrf == "200", csrf))
    log(f"  {'ok ' if csrf == '200' else 'FAIL'} dialogue /csrf-token -> {csrf}")

    staging = ssh_run(ssh, "ls -d /opt/homer-backup-staging 2>/dev/null || echo GONE").strip()
    results.append(("server staging removed", staging == "GONE", staging))
    log(f"  {'ok ' if staging == 'GONE' else 'FAIL'} server staging: {staging}")

    stale = ssh_run(ssh, f"ls {LIVE_DB}-wal {LIVE_DB}-shm 2>/dev/null | wc -l").strip()
    log(f"  info live DB wal/shm files present: {stale} (normal for a running WAL database)")

    presets = ssh_run(ssh, "curl -sk https://patcher.villainy.top/console/api/web/model-presets")
    has_presets = '"list"' in presets and '"total"' in presets
    results.append(("model-presets endpoint serving", has_presets, presets[:120]))
    log(f"  {'ok ' if has_presets else 'FAIL'} model-presets endpoint responds with a preset list")


TAR_EXPECTATIONS = {
    "backend.tar.zst": [
        "ai-fengyue-backend/ai_fengyue_local_server.py",
        "ai-fengyue-backend/ai-fengyue.env",
        "ai-fengyue-backend/card_experience_extension.py",
        "ai-fengyue-backend/data/verification_mail.sqlite3",
    ],
    "server-config.tar.zst": [
        "nginx/sites-available/ai-fengyue-patcher.conf",
        "systemd/ai-fengyue-backend.service",
        "systemd/homer-dialogue.service",
        "letsencrypt/live/patcher.villainy.top",
        "inventory/packages.txt",
    ],
    "homer-dialogue-runtime-source.tar.zst": [
        "/server.js",
        "/package-lock.json",
        "public/scripts/extensions/homer-bridge/index.js",
    ],
    "homer-dialogue-data.tar.zst": [
        "homer-dialogue/default-user", "/characters/", "/chats/", "/worlds/",
    ],
    "frontend.tar.zst": [
        "ai-fengyue-frontend/index.html", "ai-fengyue-frontend/admin.html",
        "app/chat.html", "app/assets/js/create.js",
    ],
    "download.tar.zst": [
        "download/release.json", "download/ai-xingyue-latest.apk",
    ],
}


def main() -> int:
    parser = argparse.ArgumentParser(description="Independently verify a Homer backup directory.")
    parser.add_argument("backup", type=Path)
    parser.add_argument("--skip-server", action="store_true",
                        help="offline mode: checksum + archive structure only")
    args = parser.parse_args()

    backup: Path = args.backup
    if not (backup / "MANIFEST.json").exists():
        raise SystemExit(f"not a backup directory (no MANIFEST.json): {backup}")
    manifest = json.loads((backup / "MANIFEST.json").read_text(encoding="utf-8"))
    present = {entry["file"] for entry in manifest["archives"]}
    log(f"backup {backup.name} captured {manifest['captured_at_local']} "
        f"from {manifest['server']['hostname']} — {len(present)} archive(s)")

    results: list[tuple[str, bool, str]] = []

    log("1/6 checksums")
    check_checksums(backup, results)

    log("2/6 archive structure")
    # A --only backup contains a subset; check what's there, say what isn't.
    for filename, needles in TAR_EXPECTATIONS.items():
        if filename in present:
            check_tar(backup, filename, needles, results)
    skipped = sorted(set(TAR_EXPECTATIONS) - present)
    if skipped:
        log(f"  info not in this backup: {', '.join(skipped)}")

    if args.skip_server:
        log("skipping server-side comparisons (--skip-server)")
    else:
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(HOST, username=USER, key_filename=str(KEY),
                    look_for_keys=False, allow_agent=False, timeout=20)
        try:
            if "ai_fengyue.sqlite3.zst" in present:
                log("3/6 database vs live server")
                check_database(backup, ssh, manifest, results)
            else:
                log("3/6 database archive not in this backup; skipping")
            if "media-cache.tar.zst" in present:
                log("4/6 media library vs live server")
                check_media(backup, ssh, results)
            else:
                log("4/6 media archive not in this backup; skipping")
            log("5/6 production health")
            check_production_health(ssh, results)
        finally:
            ssh.close()

    log("6/6 summary")
    failed = [name for name, ok, _ in results if not ok]
    for name, ok, detail in results:
        if not ok:
            print(f"  FAIL {name}: {detail}")
    log(f"{len(results) - len(failed)}/{len(results)} checks passed")
    if failed:
        log("FAILED: " + ", ".join(failed))
        return 1
    log("all checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
