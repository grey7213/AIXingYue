"""Chromium acceptance for Homer admin user registration/payment columns.

The fixture is written only to the isolated SillyTavern E2E SQLite database
and is removed in ``finally``. Credentials, cookies, and payment metadata are
never printed.
"""

from __future__ import annotations

import json
import sqlite3
import time
import uuid
from pathlib import Path

from playwright.sync_api import sync_playwright

from _e2e_sillytavern_runtime import (
    assert_clean,
    assert_no_overflow,
    goto,
    login,
    monitor_page,
)


ROOT = Path(__file__).resolve().parents[1]
STATE_DIR = ROOT / "output" / "sillytavern-e2e"


def main() -> int:
    config = json.loads((STATE_DIR / "runtime" / "config.json").read_text(encoding="utf-8"))
    credentials = json.loads(
        (STATE_DIR / "runtime" / "credentials.json").read_text(encoding="utf-8")
    )
    base_url = str(config["base_url"]).rstrip("/")
    db_path = Path(config["db_path"])
    output_dir = ROOT / "output" / "playwright"
    output_dir.mkdir(parents=True, exist_ok=True)

    marker = "admin-users-browser-" + uuid.uuid4().hex
    order_numbers = [marker + "-paid-a", marker + "-paid-b", marker + "-pending"]
    legacy_order = marker + "-legacy"
    conn = sqlite3.connect(db_path, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("pragma busy_timeout=30000")
    results: list[dict] = []
    try:
        regular_user = conn.execute(
            "select id,created_at from users where email=?",
            (str(credentials["regular_email"]),),
        ).fetchone()
        if not regular_user:
            raise AssertionError("isolated regular user fixture is missing")
        user_id = str(regular_user["id"])
        created_at = int(regular_user["created_at"] or 0)
        ts = int(time.time() * 1000)
        conn.executemany(
            "insert into payment_orders(order_no,provider,user_id,plan_id,plan_kind,product_name,pay_type,money_cents,points,status,created_at,updated_at,paid_at) "
            "values(?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                (order_numbers[0], "zpay", user_id, "ui-a", "package", "UI A", "alipay", 1234, 1000, "paid", ts, ts, ts),
                (order_numbers[1], "zpay", user_id, "ui-b", "package", "UI B", "alipay", 66, 100, "paid", ts + 1, ts + 1, ts + 1),
                (order_numbers[2], "zpay", user_id, "ui-pending", "package", "UI Pending", "alipay", 9000, 9000, "pending", ts + 2, ts + 2, None),
            ),
        )
        conn.execute(
            "insert into recharge_orders(order_id,user_id,product_id,points,created_at,remote_addr) values(?,?,?,?,?,?)",
            (legacy_order, user_id, "legacy-ui", 999999, ts, "127.0.0.1"),
        )
        conn.commit()

        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            try:
                for label, viewport in (
                    ("desktop", {"width": 1440, "height": 900}),
                    ("mobile", {"width": 390, "height": 844}),
                ):
                    context = browser.new_context(viewport=viewport)
                    page = context.new_page()
                    failures = monitor_page(page, (base_url,))
                    login(page, base_url, credentials)
                    goto(page, base_url + "/admin.html")
                    page.get_by_role("heading", name="数据总览").wait_for(state="visible")
                    if label == "mobile":
                        page.locator(".xy-admin-mobilebar select").select_option("users")
                    else:
                        page.locator(".xy-admin-sidebar .xy-admin-nav-item").filter(
                            has_text="用户管理"
                        ).click()
                    page.get_by_role("heading", name="用户管理").wait_for(state="visible")

                    search = page.locator('input[placeholder="搜索邮箱/昵称/ID"]')
                    search.fill(str(credentials["regular_email"]))
                    page.get_by_role("button", name="搜索").click()
                    row = page.locator("tbody tr").filter(
                        has_text=str(credentials["regular_email"])
                    )
                    row.wait_for(state="visible")
                    cells = [text.strip() for text in row.locator("td").all_inner_texts()]
                    headers = [text.strip() for text in page.locator("thead th").all_inner_texts()]
                    if "累计充值" not in headers or "注册时间" not in headers:
                        raise AssertionError(f"{label}: admin user columns are missing: {headers}")
                    if "¥13.00" not in cells:
                        raise AssertionError(f"{label}: paid money was not rendered from the API: {cells}")
                    registered_text = cells[headers.index("注册时间")]
                    if not registered_text or registered_text == "-" or "2026" not in registered_text:
                        raise AssertionError(
                            f"{label}: registration time was not formatted: {registered_text!r}"
                        )
                    assert_no_overflow(page, f"{label} admin users")
                    assert_clean(failures, f"{label} admin users")
                    if label == "mobile":
                        row.locator("td").nth(headers.index("注册时间")).scroll_into_view_if_needed()
                        page.wait_for_timeout(120)
                    screenshot = output_dir / f"homer-admin-users-{label}.png"
                    page.screenshot(path=str(screenshot), full_page=True)
                    results.append(
                        {
                            "viewport": label,
                            "headers": ["累计充值", "注册时间"],
                            "paid_money": "13.00",
                            "created_at": created_at,
                            "formatted_created_at": registered_text,
                            "horizontal_overflow": False,
                            "console_errors": 0,
                            "page_errors": 0,
                            "network_errors": 0,
                            "screenshot": str(screenshot),
                        }
                    )
                    context.close()
            finally:
                browser.close()

        print(json.dumps({"ok": True, "results": results}, ensure_ascii=False, indent=2))
        return 0
    finally:
        try:
            conn.execute(
                "delete from payment_orders where order_no in (?,?,?)", tuple(order_numbers)
            )
            conn.execute("delete from recharge_orders where order_id=?", (legacy_order,))
            conn.commit()
        finally:
            conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
