import argparse
import base64
import csv
import json
import shlex
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BASE_URL = "https://patcher.villainy.top"
DEFAULT_PURCHASE_URL = "https://ifdian.net/a/villainy"
DEFAULT_SSH_KEY = r"C:\Users\86180\.ssh\villainy_backup_ed25519"
DEFAULT_SSH_HOST = "root@45.207.192.148"
DEFAULT_REMOTE_DB = "/opt/ai-fengyue-backend/data/ai_fengyue.sqlite3"
DEFAULT_ADMIN_EMAIL = "local@ctf.test"

PLANS = {
    "xy_10": {
        "product_title": "AI星月轻量包",
        "label": "轻量包",
        "price_cny": 10,
        "points": 10000,
        "replies": 200,
        "point_type": "paid",
        "note": "爱发电轻量包 ¥10 / 10000 星月币",
        "kind": "points",
    },
    "xy_20": {
        "product_title": "AI星月常用包",
        "label": "常用包",
        "price_cny": 20,
        "points": 22000,
        "replies": 440,
        "point_type": "paid",
        "note": "爱发电常用包 ¥20 / 22000 星月币",
        "kind": "points",
    },
    "xy_50": {
        "product_title": "AI星月高频包",
        "label": "高频包",
        "price_cny": 50,
        "points": 57500,
        "replies": 1150,
        "point_type": "paid",
        "note": "爱发电高频包 ¥50 / 57500 星月币",
        "kind": "points",
    },
    "xy_100": {
        "product_title": "AI星月深度包",
        "label": "深度包",
        "price_cny": 100,
        "points": 120000,
        "replies": 2400,
        "point_type": "paid",
        "note": "爱发电深度包 ¥100 / 120000 星月币",
        "kind": "points",
    },
    "sub_month_light": {
        "product_title": "AI星月月卡",
        "label": "月卡",
        "price_cny": 19.9,
        "points": 22000,
        "replies": 440,
        "point_type": "paid",
        "note": "爱发电月卡 ¥19.9 / 22000 星月币（月度额度包）",
        "kind": "monthly",
    },
    "sub_month_standard": {
        "product_title": "AI星月标准会员",
        "label": "标准会员",
        "price_cny": 39.9,
        "points": 50000,
        "replies": 1000,
        "point_type": "paid",
        "note": "爱发电标准会员 ¥39.9 / 50000 星月币（月度额度包）",
        "kind": "monthly",
    },
    "sub_month_pro": {
        "product_title": "AI星月 Pro 会员",
        "label": "Pro 会员",
        "price_cny": 79.9,
        "points": 110000,
        "replies": 2200,
        "point_type": "paid",
        "note": "爱发电 Pro 会员 ¥79.9 / 110000 星月币（月度额度包）",
        "kind": "monthly",
    },
}


def admin_token(args) -> str:
    code = (
        "import sqlite3,base64,json,time;"
        f"conn=sqlite3.connect({args.remote_db!r});"
        f"row=conn.execute('select id from users where lower(email)=lower(?)',({args.admin_email!r},)).fetchone();"
        "assert row;"
        "payload=json.dumps({'sub':row[0],'iat':int(time.time()),'scope':'local'},separators=(',',':')).encode();"
        "print('local.'+base64.urlsafe_b64encode(payload).decode('ascii').rstrip('='))"
    )
    cmd = [
        "ssh",
        "-i",
        args.ssh_key,
        "-o",
        "BatchMode=yes",
        args.ssh_host,
        "python3 -c " + shlex.quote(code),
    ]
    token = subprocess.check_output(cmd, text=True, timeout=30).strip()
    if not token.startswith("local."):
        raise RuntimeError("failed to generate admin token")
    return token


def api_request(args, method: str, path: str, payload: dict | None = None) -> dict:
    token = admin_token(args)
    body = None
    headers = {
        "Accept": "application/json",
        "Authorization": f"Bearer {token}",
    }
    if payload is not None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"
    last_error: Exception | None = None
    text = ""
    for attempt in range(1, 4):
        req = urllib.request.Request(args.base_url.rstrip("/") + path, data=body, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                text = resp.read().decode("utf-8")
            break
        except urllib.error.HTTPError as exc:
            text = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"HTTP {exc.code}: {text}") from exc
        except Exception as exc:
            last_error = exc
            if attempt >= 3:
                raise RuntimeError(f"request failed after retries: {exc}") from exc
            time.sleep(1.5 * attempt)
    if not text and last_error is not None:
        raise RuntimeError(f"request failed: {last_error}") from last_error
    data = json.loads(text)
    if data.get("result") == "failure":
        raise RuntimeError(data.get("message") or data.get("msg") or text)
    return data


def configured_deposit(url: str) -> dict:
    return {
        "aifadian_url": url,
        "currency": "CNY",
        "credits_name": "星月币",
        "rate_label": "1 CNY = 1000 星月币，50 星月币约等于 1 次角色回复",
        "title": "爱发电购买兑换码",
        "description": "付款后复制爱发电自动发货的兑换码，回到这里兑换到账。",
        "button_text": "去爱发电购买",
        "redeem_button_text": "兑换额度",
        "redeem_placeholder": "XY-XXXX-XXXX-XXXX-XXXX",
        "support_text": "购买后请复制爱发电发货内容里的兑换码；如未收到请联系站长。",
        "payment_note_available": "爱发电购买完成后，复制自动发货的兑换码在本页到账。",
        "payment_note_unavailable": "暂未配置购买链接，请联系站长获取兑换码。",
        "steps": [
            "在爱发电选择对应档位购买",
            "复制爱发电自动发货内容中的兑换码",
            "回到 AI星月输入兑换码，额度立即到账",
        ],
        "packages": [
            {"id": "xy_10", "price_cny": 10, "points": 10000, "bonus_rate": 0, "label": "轻量包"},
            {"id": "xy_20", "price_cny": 20, "points": 22000, "bonus_rate": 10, "label": "常用包"},
            {"id": "xy_50", "price_cny": 50, "points": 57500, "bonus_rate": 15, "label": "高频包"},
            {"id": "xy_100", "price_cny": 100, "points": 120000, "bonus_rate": 20, "label": "深度包"},
        ],
        "subscriptions_title": "月度订阅",
        "subscriptions_note": "订阅为月度额度包，不承诺无限使用；额度用完后可继续兑换积分包。",
        "subscriptions": [
            {
                "id": "sub_month_light",
                "price_cny": 19.9,
                "points": 22000,
                "period": "月",
                "label": "月卡",
                "description": "适合普通聊天，约 440 次回复",
            },
            {
                "id": "sub_month_standard",
                "price_cny": 39.9,
                "points": 50000,
                "period": "月",
                "label": "标准会员",
                "description": "适合高频聊天，约 1000 次回复",
            },
            {
                "id": "sub_month_pro",
                "price_cny": 79.9,
                "points": 110000,
                "period": "月",
                "label": "Pro 会员",
                "description": "适合重度使用，约 2200 次回复",
            },
        ],
    }


def configure(args) -> None:
    data = api_request(args, "POST", "/admin/api/site-settings", {"deposit": configured_deposit(args.purchase_url)})
    deposit = data.get("data", {}).get("deposit", {})
    print(json.dumps({
        "configured": True,
        "aifadian_url": deposit.get("aifadian_url"),
        "packages": len(deposit.get("packages") or []),
        "subscriptions": len(deposit.get("subscriptions") or []),
    }, ensure_ascii=False, indent=2))


def delivery_message(code: str, plan: dict) -> str:
    monthly_note = "这是月度额度包，不是无限使用；额度用完后可继续购买积分包。\n" if plan.get("kind") == "monthly" else ""
    return (
        "感谢购买 AI星月。\n\n"
        f"商品：{plan['product_title']}\n"
        f"额度：{plan['points']} 星月币，约 {plan['replies']} 次角色回复\n"
        f"{monthly_note}"
        f"你的兑换码：\n{code}\n\n"
        "兑换方式：\n"
        "1. 打开 https://patcher.villainy.top/app/rewards.html\n"
        "2. 登录你的 AI星月账号\n"
        "3. 在“兑换码”输入框粘贴兑换码\n"
        "4. 点击“兑换额度”，到账后网页和 APK 共用\n\n"
        "注意：\n"
        "- 一个兑换码只能使用一次。\n"
        "- 请勿公开转发兑换码。\n"
        "- 如兑换失败，请带爱发电订单号联系站长。\n"
    )


def product_description(plan: dict) -> str:
    monthly_note = "\n> 本商品为月度额度包，不是无限使用。额度用完后可继续购买积分包。\n" if plan.get("kind") == "monthly" else ""
    return (
        f"# {plan['product_title']}\n\n"
        f"- 价格：{plan['price_cny']} CNY\n"
        f"- 到账：{plan['points']} 星月币\n"
        f"- 约可生成：{plan['replies']} 次角色回复\n"
        "- 消耗规则：每次成功角色回复消耗 50 星月币\n"
        "- 发货方式：购买后自动发货兑换码\n"
        f"{monthly_note}\n"
        "## 兑换方式\n\n"
        "1. 打开 https://patcher.villainy.top/app/rewards.html\n"
        "2. 登录你的 AI星月账号\n"
        "3. 在“兑换码”输入框粘贴爱发电自动发货的兑换码\n"
        "4. 点击“兑换额度”，到账后网页和 APK 共用\n\n"
        "## 注意\n\n"
        "- 一个兑换码只能使用一次。\n"
        "- 兑换码售出后请尽快兑换，避免遗失。\n"
        "- 如兑换失败，请带爱发电订单号联系站长。\n"
    )


def generate(args) -> None:
    selected = list(PLANS) if args.plan == "all" else [args.plan]
    out_dir = Path(args.out_dir or (ROOT / "output" / "aifadian-codes" / time.strftime("%Y%m%d-%H%M%S")))
    out_dir.mkdir(parents=True, exist_ok=True)
    expires_at = None
    if args.expires_days:
        expires_at = int((time.time() + args.expires_days * 86400) * 1000)

    summary = []
    for plan_id in selected:
        plan = PLANS[plan_id]
        payload = {
            "count": args.count,
            "points": plan["points"],
            "point_type": plan["point_type"],
            "note": plan["note"],
            "expires_at": expires_at,
        }
        data = api_request(args, "POST", "/admin/api/redeem-codes/create", payload)
        codes = data.get("data", {}).get("codes") or []
        plan_dir = out_dir / f"{plan_id}-{plan['product_title']}-{plan['price_cny']}元-{plan['points']}星月币"
        plan_dir.mkdir(parents=True, exist_ok=True)
        csv_path = plan_dir / "管理库存.csv"
        txt_path = plan_dir / "卡密库存-一行一码.txt"
        message_path = plan_dir / "自动发货完整文案.txt"
        desc_path = plan_dir / "商品说明.md"
        with csv_path.open("w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=[
                "code",
                "plan_id",
                "product_title",
                "label",
                "price_cny",
                "points",
                "replies",
                "point_type",
                "note",
                "expires_at",
            ])
            writer.writeheader()
            for item in codes:
                writer.writerow({
                    "code": item.get("code"),
                    "plan_id": plan_id,
                    "product_title": plan["product_title"],
                    "label": plan["label"],
                    "price_cny": plan["price_cny"],
                    "points": plan["points"],
                    "replies": plan["replies"],
                    "point_type": plan["point_type"],
                    "note": plan["note"],
                    "expires_at": expires_at or "",
                })
        with txt_path.open("w", encoding="utf-8") as f:
            for item in codes:
                f.write(str(item.get("code") or "").strip() + "\n")
        with message_path.open("w", encoding="utf-8") as f:
            for index, item in enumerate(codes, start=1):
                if index > 1:
                    f.write("\n" + "=" * 40 + "\n\n")
                f.write(delivery_message(str(item.get("code") or "").strip(), plan))
        desc_path.write_text(product_description(plan), encoding="utf-8")
        summary.append({
            "plan_id": plan_id,
            "product_title": plan["product_title"],
            "label": plan["label"],
            "price_cny": plan["price_cny"],
            "points": plan["points"],
            "replies": plan["replies"],
            "count": len(codes),
            "csv": str(csv_path),
            "code_txt": str(txt_path),
            "delivery_messages": str(message_path),
            "product_description": str(desc_path),
        })

    summary_path = out_dir / "summary.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    write_manifest(out_dir)
    print(json.dumps({"generated": True, "out_dir": str(out_dir), "plans": summary}, ensure_ascii=False, indent=2))


def find_plan_dir(out_dir: Path, plan_id: str) -> Path | None:
    matches = sorted(out_dir.glob(f"{plan_id}-*"))
    return matches[0] if matches else None


def write_manifest(out_dir: Path) -> Path:
    lines = [
        "# 爱发电商品配置总表",
        "",
        "把下面 7 个固定档位添加到爱发电。不要用“自选金额/月”承载自动发货；自选金额只适合人工处理或纯赞助。",
        "",
        "每个档位目录里：",
        "",
        "- `商品说明.md`：复制到爱发电商品/方案说明。",
        "- `卡密库存-一行一码.txt`：导入或复制到爱发电自动发货库存，一行一个码。",
        "- `自动发货完整文案.txt`：如果爱发电支持逐条完整发货内容，可用这里的完整模板。",
        "- `管理库存.csv`：本地留档，不要公开。",
        "",
        "| 商品名 | 价格 | 星月币 | 约可回复 | 自动发货库存 | 商品说明 |",
        "|---|---:|---:|---:|---|---|",
    ]
    for plan_id, plan in PLANS.items():
        plan_dir = find_plan_dir(out_dir, plan_id)
        code_path = plan_dir / "卡密库存-一行一码.txt" if plan_dir else None
        desc_path = plan_dir / "商品说明.md" if plan_dir else None
        lines.append(
            "| {title} | {price} | {points} | {replies} | {code} | {desc} |".format(
                title=plan["product_title"],
                price=plan["price_cny"],
                points=plan["points"],
                replies=plan["replies"],
                code=str(code_path) if code_path and code_path.exists() else "未生成",
                desc=str(desc_path) if desc_path and desc_path.exists() else "未生成",
            )
        )
    lines.extend([
        "",
        "## 推荐创建方式",
        "",
        "1. 登录 https://ifdian.net/a/villainy",
        "2. 进入管理/设置/方案或商品管理。",
        "3. 对照上表创建固定档位。",
        "4. 每个档位开启自动发货，导入对应 `卡密库存-一行一码.txt`。",
        "5. 商品说明粘贴对应 `商品说明.md` 内容。",
        "6. 删除或下架价格不匹配的旧 `66 元/月` 方案，避免用户买错。",
        "",
        "## 发货说明",
        "",
        "用户购买后拿到兑换码，回到 https://patcher.villainy.top/app/rewards.html 输入即可到账。",
        "一个兑换码只能使用一次，后台会记录兑换账号和时间。",
        "",
    ])
    manifest = out_dir / "爱发电商品配置总表.md"
    manifest.write_text("\n".join(lines), encoding="utf-8")
    return manifest


def manifest(args) -> None:
    out_dir = Path(args.out_dir)
    path = write_manifest(out_dir)
    print(json.dumps({"manifest": str(path)}, ensure_ascii=False, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(description="Configure AI星月 爱发电 purchase URL and generate redeem-code inventory.")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--ssh-key", default=DEFAULT_SSH_KEY)
    parser.add_argument("--ssh-host", default=DEFAULT_SSH_HOST)
    parser.add_argument("--remote-db", default=DEFAULT_REMOTE_DB)
    parser.add_argument("--admin-email", default=DEFAULT_ADMIN_EMAIL)
    sub = parser.add_subparsers(dest="command", required=True)

    p_config = sub.add_parser("configure", help="Update live deposit settings for 爱发电.")
    p_config.add_argument("--purchase-url", default=DEFAULT_PURCHASE_URL)
    p_config.set_defaults(func=configure)

    p_gen = sub.add_parser("generate", help="Generate redeem-code inventory for one or all plans.")
    p_gen.add_argument("--plan", choices=["all", *PLANS.keys()], required=True)
    p_gen.add_argument("--count", type=int, default=20)
    p_gen.add_argument("--expires-days", type=int, default=0)
    p_gen.add_argument("--out-dir", default="")
    p_gen.set_defaults(func=generate)

    p_manifest = sub.add_parser("manifest", help="Write a product setup manifest for an existing inventory directory.")
    p_manifest.add_argument("--out-dir", required=True)
    p_manifest.set_defaults(func=manifest)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
