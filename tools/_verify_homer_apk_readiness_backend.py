"""Focused backend acceptance for the Homer SillyTavern APK-readiness pass.

Runs against the isolated local E2E stack and never prints credentials, cookie
values, prompt text, or tokens.
"""

from __future__ import annotations

import http.cookiejar
import json
import sqlite3
import time
import uuid
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import HTTPCookieProcessor, Request, build_opener


ROOT = Path(__file__).resolve().parents[1]
STATE_DIR = ROOT / "output" / "sillytavern-e2e"


class Client:
    def __init__(self, base_url: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.opener = build_opener(HTTPCookieProcessor(http.cookiejar.CookieJar()))

    def request(self, method: str, path: str, body: object | None = None) -> tuple[int, dict]:
        payload = None if body is None else json.dumps(body, ensure_ascii=False).encode("utf-8")
        request = Request(
            self.base_url + path,
            data=payload,
            method=method,
            headers={"Content-Type": "application/json", "Accept": "application/json"},
        )
        try:
            with self.opener.open(request, timeout=30) as response:
                status = response.status
                raw = response.read()
        except HTTPError as error:
            status = error.code
            raw = error.read()
        try:
            parsed = json.loads(raw.decode("utf-8")) if raw else {}
        except Exception:
            parsed = {}
        return status, parsed if isinstance(parsed, dict) else {}

    def login(self, email: str, password: str) -> None:
        status, body = self.request(
            "POST",
            "/console/api/login",
            {"email": email, "password": password},
        )
        if status != 200 or body.get("result") != "success":
            raise AssertionError(f"isolated login failed with status {status}")


def data_of(body: dict) -> dict:
    data = body.get("data")
    return data if isinstance(data, dict) else body


def main() -> int:
    config = json.loads((STATE_DIR / "runtime" / "config.json").read_text(encoding="utf-8"))
    credentials = json.loads((STATE_DIR / "runtime" / "credentials.json").read_text(encoding="utf-8"))
    base_url = str(config["base_url"])
    app_id = str(config["app_id"])
    db_path = Path(config["db_path"])
    admin = Client(base_url)
    regular = Client(base_url)
    admin.login(str(credentials["email"]), str(credentials["password"]))
    regular.login(str(credentials["regular_email"]), str(credentials["regular_password"]))

    marker = "apkready-" + uuid.uuid4().hex
    event_id = marker + "-event"
    secret_sentinel = "SHOULD-NOT-BE-PERSISTED-" + uuid.uuid4().hex
    conversation_id = ""
    order_numbers = [marker + "-paid-a", marker + "-paid-b", marker + "-pending"]
    legacy_order = marker + "-legacy"
    conn = sqlite3.connect(db_path, timeout=30)
    conn.row_factory = sqlite3.Row
    try:
        status, body = regular.request(
            "POST",
            "/console/api/web/conversations/start",
            {"app_id": app_id},
        )
        if status != 200:
            raise AssertionError(f"conversation fixture failed with status {status}")
        conversation_id = str(data_of(body).get("conversation_id") or "")
        if not conversation_id:
            raise AssertionError("conversation fixture returned no id")

        event_body = {
            "event_id": event_id,
            "event_type": "message_send",
            "app_id": app_id,
            "conversation_id": conversation_id,
            "message_id": "message-apkready",
            "prompt": secret_sentinel,
            "reply": secret_sentinel,
            "token": secret_sentinel,
            "api_key": secret_sentinel,
        }
        first_status, first_body = regular.request(
            "POST", "/console/api/web/dialogue/events", event_body
        )
        second_status, second_body = regular.request(
            "POST", "/console/api/web/dialogue/events", event_body
        )
        first = data_of(first_body)
        second = data_of(second_body)
        if first_status != 200 or first.get("duplicate") is not False:
            raise AssertionError(f"first dialogue event was not accepted once: {first_status} {first}")
        if second_status != 200 or second.get("duplicate") is not True:
            raise AssertionError(f"duplicate dialogue event was not idempotent: {second_status} {second}")

        permission_status, _permission_body = regular.request(
            "POST",
            "/admin/api/dialogue/extensions/import",
            {"filename": "blocked.zip", "package_file": "data:application/zip;base64,AA=="},
        )
        if permission_status != 403:
            raise AssertionError(
                f"ordinary user extension administration returned {permission_status}, expected 403"
            )

        regular_user = conn.execute(
            "select id,created_at from users where email=?",
            (str(credentials["regular_email"]),),
        ).fetchone()
        if not regular_user:
            raise AssertionError("regular user fixture is missing")
        user_id = str(regular_user["id"])
        created_at = int(regular_user["created_at"] or 0)
        ts = int(time.time() * 1000)
        rows = (
            (order_numbers[0], "zpay", user_id, "e2e-a", "package", "E2E A", "alipay", 1234, 1000, "paid", ts, ts, ts),
            (order_numbers[1], "zpay", user_id, "e2e-b", "package", "E2E B", "alipay", 66, 100, "paid", ts + 1, ts + 1, ts + 1),
            (order_numbers[2], "zpay", user_id, "e2e-pending", "package", "E2E Pending", "alipay", 9000, 9000, "pending", ts + 2, ts + 2, None),
        )
        conn.executemany(
            "insert into payment_orders(order_no,provider,user_id,plan_id,plan_kind,product_name,pay_type,money_cents,points,status,created_at,updated_at,paid_at) "
            "values(?,?,?,?,?,?,?,?,?,?,?,?,?)",
            rows,
        )
        conn.execute(
            "insert into recharge_orders(order_id,user_id,product_id,points,created_at,remote_addr) values(?,?,?,?,?,?)",
            (legacy_order, user_id, "legacy-test", 999999, ts, "127.0.0.1"),
        )
        conn.commit()

        query = urlencode({"page": 1, "limit": 20, "search": str(credentials["regular_email"])})
        users_status, users_body = admin.request("GET", "/admin/api/users?" + query)
        users_data = data_of(users_body)
        users = users_data.get("users") if isinstance(users_data.get("users"), list) else []
        if users_status != 200 or len(users) != 1:
            raise AssertionError(f"admin user aggregation failed with status {users_status}")
        user_view = users[0]
        if int(user_view.get("created_at") or 0) != created_at or created_at <= 0:
            raise AssertionError("admin user registration time is missing or incorrect")
        if int(user_view.get("paid_money_cents") or 0) != 1300:
            raise AssertionError(f"paid order aggregation is incorrect: {user_view.get('paid_money_cents')}")
        if str(user_view.get("paid_money") or "") != "13.00":
            raise AssertionError(f"paid money formatting is incorrect: {user_view.get('paid_money')!r}")

        receipt_count = conn.execute(
            "select count(*) from dialogue_event_receipts where user_id=? and event_id=?",
            (user_id, event_id),
        ).fetchone()[0]
        event_rows = conn.execute(
            "select payload_json from user_events where user_id=? and event_type='dialogue_message_send' and payload_json like ?",
            (user_id, f"%{conversation_id}%"),
        ).fetchall()
        request_rows = conn.execute(
            "select body from request_log where path='/console/api/web/dialogue/events' and body like ?",
            (f"%{event_id}%",),
        ).fetchall()
        if receipt_count != 1 or len(event_rows) != 1 or len(request_rows) != 2:
            raise AssertionError(
                "dialogue event persistence counts are incorrect: "
                f"receipts={receipt_count}, user_events={len(event_rows)}, request_logs={len(request_rows)}"
            )
        stored_user_event = str(event_rows[0]["payload_json"] or "")
        stored_request_bodies = [str(row["body"] or "") for row in request_rows]
        if secret_sentinel in stored_user_event or any(secret_sentinel in item for item in stored_request_bodies):
            raise AssertionError("dialogue event logs retained prompt/reply/token data")
        expected_keys = {"event_id", "event_type", "app_id", "conversation_id", "message_id"}
        if any(set(json.loads(item).keys()) != expected_keys for item in stored_request_bodies):
            raise AssertionError("dialogue request logs contain fields outside the metadata whitelist")

        print(
            json.dumps(
                {
                    "ok": True,
                    "dialogue_event_idempotent": True,
                    "dialogue_logs_metadata_only": True,
                    "ordinary_user_extension_admin_status": permission_status,
                    "user_created_at_exposed": True,
                    "paid_money_cents": int(user_view["paid_money_cents"]),
                    "pending_and_legacy_not_counted": True,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0
    finally:
        try:
            conn.execute("delete from payment_orders where order_no in (?,?,?)", tuple(order_numbers))
            conn.execute("delete from recharge_orders where order_id=?", (legacy_order,))
            conn.execute("delete from dialogue_event_receipts where event_id=?", (event_id,))
            conn.execute(
                "delete from user_events where event_type='dialogue_message_send' and payload_json like ?",
                (f"%{conversation_id}%",),
            )
            conn.execute(
                "delete from request_log where path='/console/api/web/dialogue/events' and body like ?",
                (f"%{event_id}%",),
            )
            if conversation_id:
                conn.execute("delete from messages where conversation_id=?", (conversation_id,))
                conn.execute("delete from conversations where id=?", (conversation_id,))
            conn.commit()
        finally:
            conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
