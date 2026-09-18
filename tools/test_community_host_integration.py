"""Isolated checks for the community integration in the real Homer host."""
import tempfile
import unittest
from pathlib import Path

from ai_fengyue_local_server import Store
from community_feed import handle_feed_route
from community_policy import VERSION


class CommunityHostIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="homer-community-host-")
        root = Path(self.temp.name)
        self.store = Store(root / "state.sqlite3")
        self.store.configure_community_media(root / "media")
        self.user = {"id": "community-user", "name": "社区验收用户", "is_admin": 0}

    def tearDown(self):
        self.store.conn.close()
        self.temp.cleanup()

    def context(self, *, admin=False):
        return {
            "conn": self.store.conn,
            "lock": self.store.lock,
            "user": dict(self.user),
            "is_admin": admin,
            "resolve_cards": self.store.resolve_social_cards,
            "media_store": self.store.community_media,
        }

    def call(self, method, path, body=None, *, admin=False):
        return handle_feed_route(
            method,
            "console/api/web/social/" + path,
            {},
            body or {},
            self.context(admin=admin),
        )

    def test_schema_bootstrap_and_media_capability(self):
        tables = {
            row[0]
            for row in self.store.conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'social_%'"
            )
        }
        self.assertIn("social_posts", tables)
        self.assertIn("social_cases", tables)
        self.assertIn("social_uploads", tables)
        bootstrap = self.call("GET", "bootstrap")["data"]
        self.assertTrue(bootstrap["available"])
        self.assertTrue(bootstrap["media"])
        self.assertFalse(bootstrap["consented"])

    def test_consent_post_and_card_reference_resolution(self):
        self.store.upsert_upstream_app({
            "id": "card-community-test",
            "name": "社区引用测试卡",
            "summary": "",
            "description": "",
            "cover_url": "",
            "cover_origin": "",
            "tags": [],
            "opening_statement": "",
            "suggested_questions": [],
            "language": "zh-Hans",
        })
        row = self.store.get_local_app("card-community-test")
        display_id = str(row["display_id"])
        consent = self.call("POST", "consent", {
            "version": VERSION,
            "agreement": True,
            "guidelines": True,
        })
        self.assertEqual(consent["code"], 0)
        resolved = self.call("POST", "resolve-cards", {"ids": [display_id]})["data"]["cards"]
        self.assertEqual(resolved[display_id]["name"], "社区引用测试卡")
        post = self.call("POST", "posts", {
            "title": "引用角色卡",
            "content": "推荐 ID：" + display_id,
            "topic": "角色故事",
            "images": [],
            "client_id": "host-integration-post",
        })
        self.assertEqual(post["code"], 0)
        self.assertEqual(post["data"]["title"], "引用角色卡")

    def test_admin_endpoints_stay_server_authorized(self):
        denied = self.call("GET", "admin/stats")
        self.assertEqual(denied["__http__"], 403)
        allowed = self.call("GET", "admin/stats", admin=True)
        self.assertEqual(allowed["code"], 0)


if __name__ == "__main__":
    unittest.main()
