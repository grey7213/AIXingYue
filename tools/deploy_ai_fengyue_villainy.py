#!/usr/bin/env python3
import argparse
import posixpath
import re
import secrets
import sys
import time
from pathlib import Path
from urllib.parse import urlsplit

import paramiko


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BACKEND = ROOT / "tools" / "ai_fengyue_local_server.py"
DEFAULT_CARD_MEDIA_EXTENSION = ROOT / "tools" / "card_experience_extension.py"
DEFAULT_REQUIRED_WORLD_BOOK = ROOT / "tools" / "data" / "tavo_anti_scrape_worldbook.json"
DEFAULT_FRONTEND = ROOT / "frontend"
DEFAULT_APK = ROOT / "output" / "zip-1-repack" / "ai-xingyue-patcher-signed.apk"
DEFAULT_KEY = Path.home() / ".ssh" / "villainy_backup_ed25519"
NGINX_CONF = "/etc/nginx/sites-available/sub2api.conf"
PATCHER_NGINX_CONF = "/etc/nginx/sites-available/ai-fengyue-patcher.conf"
FRONTEND_REMOTE = "/var/www/ai-fengyue-frontend"
DOMAIN_NAME_RE = re.compile(
    r"(?=.{1,253}\Z)(?:[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?\.)+[A-Za-z]{2,63}\Z"
)
EMAIL_RE = re.compile(r"[^\s@,]+@[^\s@,]+\.[^\s@,]+\Z")


def log(message: str) -> None:
    print(f"[ai-fengyue-deploy] {message}", flush=True)


def run(ssh: paramiko.SSHClient, command: str, check: bool = True) -> str:
    log(f"remote: {command}")
    stdin, stdout, stderr = ssh.exec_command(command)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    code = stdout.channel.recv_exit_status()
    if out.strip():
        print(out.rstrip())
    if err.strip():
        print(err.rstrip(), file=sys.stderr)
    if check and code != 0:
        raise RuntimeError(f"remote command failed with exit {code}: {command}")
    return out


def connect(host: str, user: str, key: Path) -> paramiko.SSHClient:
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(
        hostname=host,
        username=user,
        key_filename=str(key),
        look_for_keys=False,
        allow_agent=False,
        timeout=20,
    )
    return client


def upload_text(sftp: paramiko.SFTPClient, path: str, text: str, mode: int = 0o644) -> None:
    with sftp.file(path, "w") as fh:
        fh.write(text)
    sftp.chmod(path, mode)


def read_text(sftp: paramiko.SFTPClient, path: str) -> str:
    with sftp.file(path, "r") as fh:
        data = fh.read()
    return data.decode("utf-8", errors="replace") if isinstance(data, bytes) else data


def put_file(sftp: paramiko.SFTPClient, src: Path, dst: str, mode: int = 0o644) -> None:
    sftp.put(str(src), dst)
    sftp.chmod(dst, mode)


def remote_exists(sftp: paramiko.SFTPClient, path: str) -> bool:
    try:
        sftp.stat(path)
        return True
    except FileNotFoundError:
        return False


def validate_deploy_args(args: argparse.Namespace) -> None:
    if not 1 <= args.port <= 65535:
        raise ValueError("--port must be between 1 and 65535")
    if not DOMAIN_NAME_RE.fullmatch(args.domain_name):
        raise ValueError("--domain-name must be a plain DNS hostname")

    parsed_domain = urlsplit(args.domain.rstrip("/"))
    if (
        parsed_domain.scheme != "https"
        or parsed_domain.hostname != args.domain_name
        or parsed_domain.port is not None
        or parsed_domain.path not in ("", "/")
        or parsed_domain.query
        or parsed_domain.fragment
        or parsed_domain.username
        or parsed_domain.password
    ):
        raise ValueError("--domain must be the HTTPS origin matching --domain-name")
    args.domain = args.domain.rstrip("/")

    deploy_parts = args.deploy_dir.split("/")
    if (
        not args.deploy_dir.startswith("/")
        or any(part in ("", ".", "..") for part in deploy_parts[1:])
        or not re.fullmatch(r"/[A-Za-z0-9._/-]+", args.deploy_dir)
    ):
        raise ValueError("--deploy-dir must be a simple absolute POSIX path")

    if args.admin_emails:
        emails = [item.strip() for item in args.admin_emails.split(",")]
        if not emails or any(not EMAIL_RE.fullmatch(email) for email in emails):
            raise ValueError("--admin-emails must contain only comma-separated email addresses")
        args.admin_emails = ",".join(emails)


def proxy_locations(port: int) -> str:
    proxy = f"http://127.0.0.1:{port}"
    return f"""    location = /health {{
        proxy_pass {proxy};
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 120s;
        proxy_send_timeout 120s;
    }}

    location /console/ {{
        proxy_pass {proxy};
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 120s;
        proxy_send_timeout 120s;
    }}

    location /go/ {{
        proxy_pass {proxy};
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 120s;
        proxy_send_timeout 120s;
    }}

    location /admin/ {{
        proxy_pass {proxy};
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 120s;
        proxy_send_timeout 120s;
    }}

    location /media-cache/ {{
        proxy_pass {proxy};
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 120s;
        proxy_send_timeout 120s;
    }}

"""


def nginx_block(port: int) -> str:
    return f"""    # BEGIN AI_FENGYUE_BACKEND
{proxy_locations(port)}    # END AI_FENGYUE_BACKEND

"""


def patcher_server_config(domain_name: str, port: int) -> str:
    return f"""server {{
    listen 80;
    listen [::]:80;
    server_name {domain_name};
    return 301 https://$host$request_uri;
}}

server {{
    listen 443 ssl;
    listen [::]:443 ssl;
    server_name {domain_name};
    ssl_certificate /etc/letsencrypt/live/{domain_name}/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/{domain_name}/privkey.pem;
    include /etc/letsencrypt/options-ssl-nginx.conf;
    ssl_dhparam /etc/letsencrypt/ssl-dhparams.pem;

    root {FRONTEND_REMOTE};
    index index.html;
    charset utf-8;

    client_max_body_size 32M;

    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-Frame-Options "DENY" always;
    add_header Referrer-Policy "no-referrer" always;
    add_header Permissions-Policy "camera=(), geolocation=(), payment=(), usb=()" always;
    add_header Content-Security-Policy "default-src 'self'; script-src 'self' 'unsafe-inline' 'unsafe-eval' blob:; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob: https:; font-src 'self' data:; connect-src 'self'; media-src 'self' blob:; frame-src 'self' data: blob:; object-src 'none'; base-uri 'self'; form-action 'self'; frame-ancestors 'none'; worker-src 'self'" always;

{proxy_locations(port)}

    # APK 下载渠道暂时关闭。保留文件目录但不对公网发包，避免旧链接继续分发。
    location /download/ {{
        return 404;
    }}

    # 静态资源：短期缓存 + 验证（每次刷新会问服务器是否更新，但 304 仍然很快）
    location /assets/ {{
        try_files $uri =404;
        expires 1h;
    }}

    location ~* \\.mjs$ {{
        types {{ text/javascript mjs; }}
        try_files $uri =404;
        expires 1h;
    }}

    location ~ /\\. {{
        deny all;
        return 404;
    }}

    location = /robots.txt {{ try_files $uri =404; }}
    location = /.well-known/security.txt {{ try_files $uri =404; }}

    # /app/ Web 应用（仿 riliaichat 角色聊天端）
    location /app/ {{
        try_files $uri $uri/ /app/index.html;
    }}

    # 前端单页应用回退
    location / {{
        try_files $uri $uri/ /index.html;
    }}
}}
"""


def patch_nginx_config(current: str, port: int) -> str:
    start_marker = "    # BEGIN AI_FENGYUE_BACKEND"
    end_marker = "    # END AI_FENGYUE_BACKEND"
    block = nginx_block(port)
    if start_marker in current and end_marker in current:
        start = current.index(start_marker)
        end = current.index(end_marker, start) + len(end_marker)
        while end < len(current) and current[end] in "\r\n":
            end += 1
        return current[:start] + block + current[end:]
    marker = "    location / {"
    if marker not in current:
        raise RuntimeError("could not find main location block in nginx config")
    return current.replace(marker, block + marker, 1)


def service_unit(deploy_dir: str, port: int) -> str:
    script = posixpath.join(deploy_dir, "ai_fengyue_local_server.py")
    db = posixpath.join(deploy_dir, "data", "ai_fengyue.sqlite3")
    env = posixpath.join(deploy_dir, "ai-fengyue.env")
    return f"""[Unit]
Description=AI Xingyue CTF backend
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory={deploy_dir}
Environment=PYTHONUNBUFFERED=1
Environment=PYTHONDONTWRITEBYTECODE=1
Environment=MEDIA_DIR={FRONTEND_REMOTE}/media-cache
EnvironmentFile=-{env}
ExecStart=/usr/bin/python3 {script} --host 127.0.0.1 --port {port} --db {db}
Restart=on-failure
RestartSec=3
User=ai-xingyue
Group=ai-xingyue
UMask=0027
NoNewPrivileges=true
CapabilityBoundingSet=
AmbientCapabilities=
PrivateTmp=true
PrivateDevices=true
ProtectSystem=strict
ProtectHome=true
ProtectKernelTunables=true
ProtectKernelModules=true
ProtectControlGroups=true
RestrictSUIDSGID=true
LockPersonality=true
RestrictAddressFamilies=AF_UNIX AF_INET AF_INET6
ReadWritePaths={deploy_dir}/data {FRONTEND_REMOTE}/media-cache

[Install]
WantedBy=multi-user.target
"""


def env_template() -> str:
    return f"""# AI Xingyue backend mail settings.
# Leave SMTP_HOST empty to use local sendmail/postfix.
APP_BRAND=AI星月
SMTP_HOST=
SMTP_PORT=587
SMTP_USER=
SMTP_PASSWORD=
SMTP_FROM=noreply@patcher.villainy.top
SMTP_SSL=false
SMTP_STARTTLS=true
SENDMAIL_PATH=/usr/sbin/sendmail
# 管理员邮箱（逗号分隔）。这些账号登录后可访问 /admin.html 管理后台。
ADMIN_EMAILS=local@ctf.test
AUTH_TOKEN_SECRET={secrets.token_urlsafe(48)}
AUTH_TOKEN_TTL_SECONDS=2592000
NEW_USER_INITIAL_POINTS=500
BETA_MAX_REGISTERED_USERS=0
ALLOWED_CORS_ORIGINS=https://patcher.villainy.top
MAX_REQUEST_BODY_BYTES=33554432
"""


def upload_dir(sftp: paramiko.SFTPClient, ssh: paramiko.SSHClient, local_dir: Path, remote_dir: str) -> int:
    """递归上传目录，返回上传文件数。"""
    run(ssh, f"mkdir -p {remote_dir}")
    count = 0
    for item in local_dir.rglob("*"):
        rel = item.relative_to(local_dir).as_posix()
        target = posixpath.join(remote_dir, rel)
        if item.is_dir():
            run(ssh, f"mkdir -p {target}")
            continue
        # 确保父目录存在
        parent = posixpath.dirname(target)
        if parent and parent != remote_dir:
            run(ssh, f"mkdir -p {parent}")
        log(f"upload: {rel}")
        sftp.put(str(item), target)
        sftp.chmod(target, 0o644)
        count += 1
    return count



def main() -> int:
    parser = argparse.ArgumentParser(description="Deploy AI Xingyue backend to the Villain Y server.")
    parser.add_argument("--host", default="45.207.192.148")
    parser.add_argument("--user", default="root")
    parser.add_argument("--key", type=Path, default=DEFAULT_KEY)
    parser.add_argument("--deploy-dir", default="/opt/ai-fengyue-backend")
    parser.add_argument("--port", type=int, default=8008)
    parser.add_argument("--backend", type=Path, default=DEFAULT_BACKEND)
    parser.add_argument("--card-media-extension", type=Path, default=DEFAULT_CARD_MEDIA_EXTENSION)
    parser.add_argument("--frontend", type=Path, default=DEFAULT_FRONTEND, help="前端目录，会上传到 /var/www/ai-fengyue-frontend")
    parser.add_argument("--apk", type=Path, default=DEFAULT_APK, help="要发布到 /download/ai-xingyue-latest.apk 的 APK 文件")
    parser.add_argument("--skip-frontend", action="store_true", help="跳过前端上传")
    parser.add_argument("--skip-apk", action="store_true", help="跳过 APK 上传")
    parser.add_argument("--admin-emails", default="", help="逗号分隔的管理员邮箱列表（写入 ai-fengyue.env，会替换现有 ADMIN_EMAILS 行）")
    parser.add_argument("--domain", default="https://patcher.villainy.top")
    parser.add_argument("--domain-name", default="patcher.villainy.top")
    parser.add_argument("--patch-main-site", action="store_true", help="also expose backend paths on villainy.top")
    parser.add_argument("--skip-certbot", action="store_true")
    parser.add_argument("--skip-mail-install", action="store_true")
    args = parser.parse_args()

    validate_deploy_args(args)

    if not args.backend.exists():
        raise FileNotFoundError(args.backend)
    if not args.card_media_extension.exists():
        raise FileNotFoundError(args.card_media_extension)
    if not args.key.exists():
        raise FileNotFoundError(args.key)

    ssh = connect(args.host, args.user, args.key)
    try:
        sftp = ssh.open_sftp()
        timestamp = time.strftime("%Y%m%d-%H%M%S")
        run(ssh, "hostname && python3 --version && nginx -t")
        run(ssh, f"mkdir -p {args.deploy_dir}/data")
        run(ssh, "id -u ai-xingyue >/dev/null 2>&1 || useradd --system --home /nonexistent --shell /usr/sbin/nologin ai-xingyue")
        run(ssh, f"cp {NGINX_CONF} {NGINX_CONF}.bak-ai-xingyue-{timestamp}")
        run(ssh, f"[ -f {PATCHER_NGINX_CONF} ] && cp {PATCHER_NGINX_CONF} {PATCHER_NGINX_CONF}.bak-{timestamp} || true")

        remote_backend = posixpath.join(args.deploy_dir, "ai_fengyue_local_server.py")
        remote_card_media_extension = posixpath.join(args.deploy_dir, "card_experience_extension.py")
        run(ssh, f"[ -f {remote_backend} ] && cp {remote_backend} {remote_backend}.bak-{timestamp} || true")
        run(
            ssh,
            f"[ -f {remote_card_media_extension} ] && cp {remote_card_media_extension} "
            f"{remote_card_media_extension}.bak-{timestamp} || true",
        )
        log(f"uploading backend to {remote_backend}")
        put_file(sftp, args.backend, remote_backend)
        log(f"uploading card media extension to {remote_card_media_extension}")
        put_file(sftp, args.card_media_extension, remote_card_media_extension)
        if DEFAULT_REQUIRED_WORLD_BOOK.exists():
            remote_worldbook = posixpath.join(args.deploy_dir, "data", "tavo_anti_scrape_worldbook.json")
            log(f"uploading required world book to {remote_worldbook}")
            put_file(sftp, DEFAULT_REQUIRED_WORLD_BOOK, remote_worldbook)

        env_path = posixpath.join(args.deploy_dir, "ai-fengyue.env")
        if remote_exists(sftp, env_path):
            log(f"keeping existing env file: {env_path}")
            current_env = read_text(sftp, env_path)
            lines = current_env.splitlines()
            changed_env = False
            if args.admin_emails:
                lines = [ln for ln in current_env.splitlines() if not ln.lstrip().startswith("ADMIN_EMAILS=")]
                lines.append(f"ADMIN_EMAILS={args.admin_emails}")
                changed_env = True
                log(f"updated ADMIN_EMAILS in {env_path}")
            defaults = {
                "AUTH_TOKEN_SECRET": secrets.token_urlsafe(48),
                "AUTH_TOKEN_TTL_SECONDS": "2592000",
                "NEW_USER_INITIAL_POINTS": "500",
                "BETA_MAX_REGISTERED_USERS": "0",
                "ALLOWED_CORS_ORIGINS": "https://patcher.villainy.top",
                "MAX_REQUEST_BODY_BYTES": "33554432",
            }
            existing_names = {ln.split("=", 1)[0].strip() for ln in lines if "=" in ln and not ln.lstrip().startswith("#")}
            for name, value in defaults.items():
                if name not in existing_names:
                    lines.append(f"{name}={value}")
                    changed_env = True
            if changed_env:
                upload_text(sftp, env_path, "\n".join(lines) + "\n", 0o600)
                log("updated production security defaults in env (secret value not logged)")
        else:
            log(f"creating env placeholder: {env_path}")
            template = env_template()
            if args.admin_emails:
                template = template.replace("ADMIN_EMAILS=local@ctf.test", f"ADMIN_EMAILS={args.admin_emails}")
            upload_text(sftp, env_path, template, 0o600)

        unit_path = "/etc/systemd/system/ai-fengyue-backend.service"
        log(f"writing systemd unit: {unit_path}")
        upload_text(sftp, unit_path, service_unit(args.deploy_dir, args.port))

        log(f"writing patcher nginx site: {PATCHER_NGINX_CONF}")
        upload_text(sftp, PATCHER_NGINX_CONF, patcher_server_config(args.domain_name, args.port))
        run(ssh, f"[ -L /etc/nginx/sites-enabled/patcher.conf ] && rm -f /etc/nginx/sites-enabled/patcher.conf || true")
        run(ssh, f"ln -sf {PATCHER_NGINX_CONF} /etc/nginx/sites-enabled/ai-fengyue-patcher.conf")

        # 前端上传
        if not args.skip_frontend:
            if not args.frontend.exists():
                log(f"warning: frontend dir not found: {args.frontend}; skip frontend upload")
            else:
                log(f"uploading frontend from {args.frontend} -> {FRONTEND_REMOTE}")
                run(ssh, f"mkdir -p {FRONTEND_REMOTE}/download")
                count = upload_dir(sftp, ssh, args.frontend, FRONTEND_REMOTE)
                log(f"uploaded {count} frontend files")
                run(ssh, f"chown -R www-data:www-data {FRONTEND_REMOTE} || true")

        # APK 上传到 download/ai-xingyue-latest.apk
        if not args.skip_apk:
            if not args.apk.exists():
                log(f"warning: APK not found: {args.apk}; skip APK upload")
            else:
                run(ssh, f"mkdir -p {FRONTEND_REMOTE}/download")
                apk_remote = f"{FRONTEND_REMOTE}/download/ai-xingyue-latest.apk"
                log(f"uploading APK -> {apk_remote}")
                sftp.put(str(args.apk), apk_remote)
                sftp.chmod(apk_remote, 0o644)
                size = args.apk.stat().st_size
                log(f"APK uploaded ({size:,} bytes)")

        if args.patch_main_site:
            conf = read_text(sftp, NGINX_CONF)
            patched = patch_nginx_config(conf, args.port)
            if patched != conf:
                log("updating main nginx route block")
                upload_text(sftp, NGINX_CONF, patched)
            else:
                log("main nginx route block already up to date")

        if not args.skip_mail_install:
            run(
                ssh,
                "DEBIAN_FRONTEND=noninteractive apt-get update -y >/tmp/ai-xingyue-apt-update.log 2>&1 && "
                "DEBIAN_FRONTEND=noninteractive apt-get install -y postfix mailutils >/tmp/ai-xingyue-mail-install.log 2>&1 && "
                "postconf -e 'myhostname = patcher.villainy.top' && "
                "postconf -e 'inet_interfaces = loopback-only' && "
                "printf 'patcher.villainy.top\\n' >/etc/mailname && "
                "systemctl enable --now postfix && systemctl restart postfix",
            )

        run(ssh, "systemctl daemon-reload")
        run(ssh, f"chown -R ai-xingyue:ai-xingyue {args.deploy_dir}/data && chmod 750 {args.deploy_dir}/data && find {args.deploy_dir}/data -type f -name '*.sqlite3*' -exec chmod 600 {{}} +")
        # The backend writes media even when --skip-frontend is used. Prepare this
        # path unconditionally after any frontend-wide www-data chown.
        run(ssh, f"mkdir -p {FRONTEND_REMOTE}/media-cache && chown -R ai-xingyue:ai-xingyue {FRONTEND_REMOTE}/media-cache && chmod 750 {FRONTEND_REMOTE}/media-cache")
        run(
            ssh,
            f"mkdir -p {FRONTEND_REMOTE}/media-cache/card-assets/pending "
            f"{FRONTEND_REMOTE}/media-cache/card-assets/ready && "
            f"chown -R ai-xingyue:ai-xingyue {FRONTEND_REMOTE}/media-cache/card-assets && "
            f"find {FRONTEND_REMOTE}/media-cache/card-assets -type d -exec chmod 750 {{}} + && "
            f"find {FRONTEND_REMOTE}/media-cache/card-assets -type f -exec chmod 640 {{}} +",
        )
        run(ssh, f"chown root:ai-xingyue {env_path} && chmod 640 {env_path}")
        run(ssh, f"python3 -m py_compile {remote_backend} {remote_card_media_extension}")
        run(ssh, "systemctl enable --now ai-fengyue-backend.service")
        run(ssh, "systemctl restart ai-fengyue-backend.service")
        run(ssh, "sleep 1; systemctl --no-pager --full status ai-fengyue-backend.service | sed -n '1,18p'")
        run(ssh, "nginx -t")
        if not args.skip_certbot:
            run(ssh, f"certbot --nginx -d {args.domain_name} --non-interactive --agree-tos -m admin@{args.domain_name} --redirect", check=False)
            run(ssh, "nginx -t")
        run(ssh, "systemctl reload nginx")
        run(ssh, f"curl -k -sS http://127.0.0.1:{args.port}/health")
        run(ssh, f"curl -k -sS {args.domain}/health")
        # 验证前端
        if not args.skip_frontend:
            run(ssh, f"curl -k -sI {args.domain}/ | head -n 5", check=False)
            run(ssh, f"curl -k -sI {args.domain}/dashboard.html | head -n 5", check=False)
            run(ssh, f"curl -k -sI {args.domain}/admin.html | head -n 5", check=False)
        # Keep deploy verification read-only. Registration/email probes send real
        # messages and consume abuse-control quotas, so they belong in an explicit
        # post-deploy acceptance test rather than the deploy helper.
        log("deployment complete")
        return 0
    finally:
        ssh.close()


if __name__ == "__main__":
    raise SystemExit(main())
