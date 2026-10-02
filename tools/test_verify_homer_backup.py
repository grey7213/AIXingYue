"""Exercise online census drift without relaxing snapshot verification."""
import contextlib
import io
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

import zstandard
import verify_homer_backup as verifier


class DatabaseSnapshotTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.backup = Path(self.temp.name)
        plain = self.backup / "fixture.sqlite3"
        db = sqlite3.connect(plain)
        for table in ("users", "content_versions", "conversations", "messages", "role_card_annotations"):
            db.execute(f"CREATE TABLE {table} (id INTEGER PRIMARY KEY)")
            db.executemany(f"INSERT INTO {table} VALUES (?)", [(1,), (2,)])
        db.execute("CREATE TABLE local_apps (id TEXT, name TEXT, cover_url TEXT)")
        self.sample = [[str(i), f"role {i}", f"/cover/{i}"] for i in range(5)]
        db.executemany("INSERT INTO local_apps VALUES (?,?,?)", self.sample)
        db.execute("CREATE TABLE api_settings (key TEXT, value TEXT)")
        db.executemany("INSERT INTO api_settings VALUES (?,?)", [
            ("model_presets", '[{"id":"fixture"}]'),
            ("default_model_preset_id", "fixture"),
            ("api_key", "test-placeholder"),
            ("base_url", "http://localhost"),
        ])
        db.commit()
        self.counts = {row[0]: db.execute(f"SELECT COUNT(*) FROM {row[0]}").fetchone()[0]
                       for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        db.close()
        self.manifest = {"database_snapshot": {"snapshot_bytes": plain.stat().st_size,
                                               "row_counts": dict(self.counts)}}
        (self.backup / "ai_fengyue.sqlite3.zst").write_bytes(
            zstandard.ZstdCompressor().compress(plain.read_bytes()))

    def tearDown(self):
        self.temp.cleanup()

    def check(self, live_counts, manifest=None):
        def remote(_ssh, command):
            if "count(*)" in command:
                return json.dumps(live_counts)
            return json.dumps(self.sample)
        results = []
        with patch.object(verifier, "ssh_run", remote), contextlib.redirect_stdout(io.StringIO()):
            verifier.check_database(self.backup, None, manifest or self.manifest, results)
        return {name: ok for name, ok, _ in results}

    def test_live_insertions_and_deletions_do_not_invalidate_snapshot(self):
        for delta in (-1, 1):
            with self.subTest(delta=delta):
                live = dict(self.counts)
                live["messages"] += delta
                live["conversations"] += delta
                self.assertTrue(all(self.check(live).values()))

    def test_manifest_row_mismatch_still_fails(self):
        manifest = json.loads(json.dumps(self.manifest))
        manifest["database_snapshot"]["row_counts"]["messages"] += 1
        self.assertFalse(self.check(self.counts, manifest)["db row counts == manifest"])

    def test_manifest_size_mismatch_still_fails(self):
        manifest = json.loads(json.dumps(self.manifest))
        manifest["database_snapshot"]["snapshot_bytes"] += 4096
        self.assertFalse(self.check(self.counts, manifest)["db size == manifest snapshot"])

    def test_invalid_live_count_fails(self):
        live = dict(self.counts)
        live["messages"] = -1
        self.assertFalse(self.check(live)["db live census readable"])


if __name__ == "__main__":
    unittest.main()
