#!/usr/bin/env python3
import argparse
import hashlib
import posixpath
import re
import secrets
import sys
import tarfile
import tempfile
import time
from pathlib import Path
from pathlib import PurePosixPath
from urllib.parse import urlsplit

import paramiko


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BACKEND = ROOT / "tools" / "ai_fengyue_local_server.py"
DEFAULT_CARD_MEDIA_EXTENSION = ROOT / "tools" / "card_experience_extension.py"
DEFAULT_CARD_VERSION_WORKSHOP = ROOT / "tools" / "card_version_workshop.py"
DEFAULT_COMMUNITY_WORKSHOP = ROOT / "tools" / "community_workshop.py"
DEFAULT_CARD_EXTRA_WORKSHOP = ROOT / "tools" / "card_extra_workshop.py"
DEFAULT_CHAT_MOD_WORKSHOP = ROOT / "tools" / "chat_mod_workshop.py"
DEFAULT_SPINE_MEDIA_SUPPORT = ROOT / "tools" / "spine_media_support.py"
DEFAULT_REQUIRED_WORLD_BOOK = ROOT / "tools" / "data" / "tavo_anti_scrape_worldbook.json"
DEFAULT_FRONTEND = ROOT / "frontend"
DEFAULT_DIALOGUE_RUNTIME = ROOT / "sillytavern-runtime"
DEFAULT_APK = ROOT / "output" / "zip-1-repack" / "ai-xingyue-patcher-signed.apk"
DEFAULT_KEY = Path.home() / ".ssh" / "villainy_backup_ed25519"
NGINX_CONF = "/etc/nginx/sites-available/sub2api.conf"
PATCHER_NGINX_CONF = "/etc/nginx/sites-available/ai-fengyue-patcher.conf"
FRONTEND_REMOTE = "/var/www/ai-fengyue-frontend"
DIALOGUE_REMOTE = "/opt/homer-dialogue-runtime"
DIALOGUE_DATA_REMOTE = "/var/lib/homer-dialogue"
DIALOGUE_UNIT = "/etc/systemd/system/homer-dialogue.service"
DIALOGUE_EXPECTED_WEBPACK = "5.105.4"
DIALOGUE_REQUIRED_EXTENSIONS = (
    "js-slash-runner",
    "ST-Prompt-Template",
    "st-yuzi-phone",
    "SillyTavern-MemoryBooks",
)
DIALOGUE_EXCLUDED_TOP_LEVEL = {
    ".git",
    ".gemini",
    ".idea",
    ".vscode",
    "backups",
    "data",
    "dist",
    "node_modules",
    "output",
    "test-results",
}
DIALOGUE_EXCLUDED_PUBLIC_PREFIXES = (
    PurePosixPath("public/chats"),
    PurePosixPath("public/characters"),
    PurePosixPath("public/User Avatars"),
    PurePosixPath("public/backgrounds"),
    PurePosixPath("public/groups"),
    PurePosixPath("public/group chats"),
    PurePosixPath("public/worlds"),
    PurePosixPath("public/user"),
    PurePosixPath("public/themes"),
    PurePosixPath("public/OpenAI Settings"),
    PurePosixPath("public/KoboldAI Settings"),
    PurePosixPath("public/NovelAI Settings"),
    PurePosixPath("public/TextGen Settings"),
    PurePosixPath("public/instruct"),
    PurePosixPath("public/context"),
    PurePosixPath("public/movingUI"),
    PurePosixPath("public/QuickReplies"),
    PurePosixPath("public/assets"),
    PurePosixPath("public/error"),
)
FRONTEND_EXCLUDED_TOP_LEVEL = {
    ".git",
    "download",
    "media-cache",
    "node_modules",
    "output",
}
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
        banner_timeout=20,
        auth_timeout=20,
    )
    transport = client.get_transport()
    if transport is not None:
        transport.set_keepalive(15)
    return client


def connect_with_retries(
    host: str,
    user: str,
    key: Path,
    *,
    attempts: int = 3,
    delay_seconds: int = 5,
) -> paramiko.SSHClient:
    last_error = None
    for attempt in range(1, attempts + 1):
        try:
            return connect(host, user, key)
        except Exception as exc:
            last_error = exc
            if attempt >= attempts:
                break
            log(f"SSH connection attempt {attempt}/{attempts} failed; retrying in {delay_seconds}s")
            time.sleep(delay_seconds)
    assert last_error is not None
    raise last_error


def ssh_connection_active(ssh: paramiko.SSHClient | None) -> bool:
    if ssh is None:
        return False
    transport = ssh.get_transport()
    return bool(transport and transport.is_active())


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


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def nginx_location_header_pattern(path: str) -> str:
    if not path.startswith("/"):
        raise ValueError("redirect path must be absolute")
    return rf"^location: (https?://[^/]+)?{re.escape(path)}$"


def dialogue_archive_excluded(relative_path: PurePosixPath) -> bool:
    parts = relative_path.parts
    if not parts:
        return False
    if parts[0] in DIALOGUE_EXCLUDED_TOP_LEVEL:
        return True
    if any(part in {"node_modules", "__pycache__"} for part in parts):
        return True
    if any(
        relative_path == prefix or prefix in relative_path.parents
        for prefix in DIALOGUE_EXCLUDED_PUBLIC_PREFIXES
    ):
        return True
    name = parts[-1].lower()
    if name in {".env", "secrets.json", "whitelist.txt", "access.log", "content.log"}:
        return True
    if name.startswith(("cookie", "token")) and name.endswith((".txt", ".json")):
        return True
    if name.endswith((".sqlite", ".sqlite3", ".db", ".pem", ".key", ".p12", ".jks", ".keystore")):
        return True
    return False


def build_dialogue_runtime_archive(runtime_root: Path, destination: Path) -> dict:
    runtime_root = runtime_root.resolve()
    required = (
        runtime_root / "server.js",
        runtime_root / "package.json",
        runtime_root / "package-lock.json",
        runtime_root / "config.yaml",
        runtime_root / "LICENSE",
    )
    for path in required:
        if not path.is_file():
            raise FileNotFoundError(path)
    for extension in DIALOGUE_REQUIRED_EXTENSIONS:
        manifest = runtime_root / "public" / "scripts" / "extensions" / "third-party" / extension / "manifest.json"
        if not manifest.is_file():
            raise FileNotFoundError(manifest)

    included_files = 0
    included_bytes = 0
    with tarfile.open(destination, "w:gz", format=tarfile.PAX_FORMAT) as archive:
        for item in sorted(runtime_root.rglob("*"), key=lambda path: path.as_posix().lower()):
            relative = PurePosixPath(item.relative_to(runtime_root).as_posix())
            if dialogue_archive_excluded(relative):
                continue
            if item.is_symlink():
                raise RuntimeError(f"dialogue runtime package refuses symlink: {relative}")
            if not item.is_dir() and not item.is_file():
                raise RuntimeError(f"dialogue runtime package refuses special file: {relative}")
            archive.add(item, arcname=relative.as_posix(), recursive=False)
            if item.is_file():
                included_files += 1
                included_bytes += item.stat().st_size

    with tarfile.open(destination, "r:gz") as archive:
        names = {PurePosixPath(member.name) for member in archive.getmembers()}
        if any(member.name.startswith("/") or ".." in PurePosixPath(member.name).parts for member in archive.getmembers()):
            raise RuntimeError("dialogue runtime archive contains an unsafe path")
        expected = {
            PurePosixPath("server.js"),
            PurePosixPath("package-lock.json"),
            *{
                PurePosixPath(f"public/scripts/extensions/third-party/{extension}/manifest.json")
                for extension in DIALOGUE_REQUIRED_EXTENSIONS
            },
        }
        missing = sorted(str(path) for path in expected if path not in names)
        if missing:
            raise RuntimeError(f"dialogue runtime archive missing required files: {missing}")
        forbidden = [str(path) for path in names if dialogue_archive_excluded(path)]
        if forbidden:
            raise RuntimeError(f"dialogue runtime archive contains excluded paths: {forbidden[:5]}")
    return {
        "path": destination,
        "sha256": sha256_file(destination),
        "archive_bytes": destination.stat().st_size,
        "source_bytes": included_bytes,
        "files": included_files,
        "package_lock_sha256": sha256_file(runtime_root / "package-lock.json"),
    }


def frontend_archive_excluded(relative_path: PurePosixPath) -> bool:
    parts = relative_path.parts
    if not parts:
        return False
    if parts[0] in FRONTEND_EXCLUDED_TOP_LEVEL:
        return True
    return any(part == "__pycache__" for part in parts)


def normalize_frontend_tarinfo(member: tarfile.TarInfo) -> tarfile.TarInfo:
    member.uid = 0
    member.gid = 0
    member.uname = "root"
    member.gname = "root"
    member.mode = 0o755 if member.isdir() else 0o644
    return member


def build_frontend_archive(frontend_root: Path, destination: Path) -> dict:
    frontend_root = frontend_root.resolve()
    required = (
        frontend_root / "index.html",
        frontend_root / "admin.html",
        frontend_root / "app" / "chat.html",
    )
    for path in required:
        if not path.is_file():
            raise FileNotFoundError(path)

    included_files = 0
    included_bytes = 0
    with tarfile.open(destination, "w:gz", format=tarfile.PAX_FORMAT) as archive:
        for item in sorted(frontend_root.rglob("*"), key=lambda path: path.as_posix().lower()):
            relative = PurePosixPath(item.relative_to(frontend_root).as_posix())
            if frontend_archive_excluded(relative):
                continue
            if item.is_symlink():
                raise RuntimeError(f"frontend package refuses symlink: {relative}")
            if not item.is_dir() and not item.is_file():
                raise RuntimeError(f"frontend package refuses special file: {relative}")
            archive.add(
                item,
                arcname=relative.as_posix(),
                recursive=False,
                filter=normalize_frontend_tarinfo,
            )
            if item.is_file():
                included_files += 1
                included_bytes += item.stat().st_size

    with tarfile.open(destination, "r:gz") as archive:
        members = archive.getmembers()
        names = {PurePosixPath(member.name) for member in members}
        if any(member.name.startswith("/") or ".." in PurePosixPath(member.name).parts for member in members):
            raise RuntimeError("frontend archive contains an unsafe path")
        expected = {
            PurePosixPath("index.html"),
            PurePosixPath("admin.html"),
            PurePosixPath("app/chat.html"),
        }
        missing = sorted(str(path) for path in expected if path not in names)
        if missing:
            raise RuntimeError(f"frontend archive missing required files: {missing}")
        forbidden = [str(path) for path in names if frontend_archive_excluded(path)]
        if forbidden:
            raise RuntimeError(f"frontend archive contains excluded paths: {forbidden[:5]}")
    return {
        "path": destination,
        "sha256": sha256_file(destination),
        "archive_bytes": destination.stat().st_size,
        "source_bytes": included_bytes,
        "files": included_files,
    }


def validate_deploy_args(args: argparse.Namespace) -> None:
    if not 1 <= args.port <= 65535:
        raise ValueError("--port must be between 1 and 65535")
    if not 1 <= args.dialogue_port <= 65535 or args.dialogue_port == args.port:
        raise ValueError("--dialogue-port must be a distinct port between 1 and 65535")
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

    # Keep the normal API body limit at 32 MiB, but allow the raw card-asset
    # upload endpoint to carry a validated Spine package up to 60 MiB.  The
    # backend still enforces the per-intent declared size, MIME and SHA-256.
    location ~ ^/console/api/web/card-assets/[^/]+/content$ {{
        client_max_body_size 60M;
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


def dialogue_proxy_directives(port: int, upstream_path: str = "/") -> str:
    dialogue_csp = (
        "default-src 'self' data: blob:; "
        "script-src 'self' 'unsafe-inline' 'unsafe-eval' blob: "
        "https://cdn.jsdelivr.net https://fastly.jsdelivr.net https://testingcf.jsdelivr.net https://raw.githubusercontent.com; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com https://fonts.gstatic.com "
        "https://cdn.jsdelivr.net https://fastly.jsdelivr.net https://testingcf.jsdelivr.net; "
        "img-src 'self' data: blob: https:; "
        "media-src 'self' data: blob: https://raw.githubusercontent.com https://cdn.jsdelivr.net "
        "https://fastly.jsdelivr.net https://testingcf.jsdelivr.net https://thumbsnap.com https://files.catbox.moe; "
        "font-src 'self' data: https://fonts.gstatic.com https://cdn.jsdelivr.net https://fastly.jsdelivr.net https://testingcf.jsdelivr.net; "
        "connect-src 'self' blob: https://raw.githubusercontent.com https://cdn.jsdelivr.net https://fastly.jsdelivr.net "
        "https://testingcf.jsdelivr.net https://gitlab.com https://thumbsnap.com https://files.catbox.moe; "
        "worker-src 'self' blob:; frame-src 'self' data: blob:; child-src 'self' blob:; "
        "object-src 'none'; base-uri 'self'; form-action 'self'; frame-ancestors 'self'"
    )
    return f"""        proxy_pass http://127.0.0.1:{port}{upstream_path};
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Forwarded-Host $host;
        proxy_set_header X-Forwarded-Prefix /module/dialogue;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_read_timeout 300s;
        proxy_send_timeout 300s;
        proxy_buffering off;
        proxy_request_buffering off;
        proxy_cookie_path / /module/dialogue/;
        proxy_redirect http://127.0.0.1:{port}/ /module/dialogue/;
        proxy_redirect ~^/(?!app(?:/|$)|assets(?:/|$)|console(?:/|$)|admin(?:/|$)|go(?:/|$)|health(?:/|$)|img(?:/|$)|media-cache(?:/|$)|download(?:/|$))(.*)$ /module/dialogue/$1;
        proxy_hide_header X-Frame-Options;
        proxy_hide_header Content-Security-Policy;
        proxy_hide_header Referrer-Policy;
        proxy_hide_header Permissions-Policy;
        add_header X-Content-Type-Options "nosniff" always;
        add_header X-Frame-Options "SAMEORIGIN" always;
        add_header Referrer-Policy "same-origin" always;
        add_header Permissions-Policy "camera=(), geolocation=(), payment=(), usb=()" always;
        add_header Content-Security-Policy "{dialogue_csp}" always;
"""


def dialogue_nginx_locations(port: int) -> str:
    proxy_root = dialogue_proxy_directives(port)
    memory_books = dialogue_proxy_directives(
        port,
        "/scripts/extensions/third-party/SillyTavern-MemoryBooks/",
    )
    return f"""    # BEGIN HOMER_DIALOGUE_RUNTIME
    location = /dialogue-core {{
        return 307 /module/dialogue/$is_args$args;
    }}

    location ~ ^/dialogue-core/(?<homer_dialogue_legacy_path>.*)$ {{
        return 307 /module/dialogue/$homer_dialogue_legacy_path$is_args$args;
    }}

    location = /module/dialogue {{
        return 308 /module/dialogue/$is_args$args;
    }}

    # The website launcher adds homer_embed=1 only to its same-origin iframe.
    # Direct document navigation without that marker returns to the site shell.
    location = /module/dialogue/ {{
        if ($arg_homer_embed != "1") {{ return 302 /app/chat.html; }}
{proxy_root}    }}

    location = /module/dialogue/index.html {{
        if ($arg_homer_embed != "1") {{ return 302 /app/chat.html; }}
{proxy_root}    }}

    location ^~ /module/dialogue/scripts/extensions/third-party/dialogue-memory-books/ {{
{memory_books}    }}

    location ^~ /module/dialogue/ {{
{proxy_root}    }}

    # SillyTavern still emits a small set of root-relative resource/API URLs.
    # Only requests originating from the embedded module are moved under its
    # cookie-scoped prefix; normal Homer-owned paths keep their existing role.
    location ~ ^/(?:api(?:/|$)|csrf-token(?:/|$)|scripts(?:/|$)|lib(?:/|$)|css(?:/|$)|webfonts(?:/|$)|locales(?:/|$)|img(?:/|$)|backgrounds(?:/|$)|characters(?:/|$)|User\\ Avatars(?:/|$)|user(?:/|$)|thumbnail(?:/|$)|socket\\.io(?:/|$)|sounds(?:/|$)|script\\.js$|lib\\.js$|style\\.css$|manifest\\.json$|favicon\\.ico$|version$) {{
        if ($http_referer ~* "^https?://[^/]+/(?:module/dialogue|dialogue-core)(?:/|$)") {{
            return 307 /module/dialogue$request_uri;
        }}
        try_files $uri =404;
    }}
    # END HOMER_DIALOGUE_RUNTIME

"""


def patcher_server_config(domain_name: str, port: int, dialogue_port: int = 8091) -> str:
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
    add_header Content-Security-Policy "default-src 'self'; script-src 'self' 'unsafe-inline' 'unsafe-eval' blob: https://unpkg.com; style-src 'self' 'unsafe-inline' https://cdnjs.cloudflare.com; img-src 'self' data: blob: https:; font-src 'self' data: https://cdnjs.cloudflare.com; connect-src 'self'; media-src 'self' blob: https://raw.githubusercontent.com; frame-src 'self' data: blob:; object-src 'none'; base-uri 'self'; form-action 'self'; frame-ancestors 'none'; worker-src 'self'" always;

{proxy_locations(port)}
{dialogue_nginx_locations(dialogue_port)}

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

    # The retired platform license page must not fall through to the app shell.
    location = /app/open-source.html {{
        return 404;
    }}

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


def dialogue_service_unit(port: int = 8091) -> str:
    return f"""[Unit]
Description=Homer SillyTavern dialogue runtime
After=network-online.target ai-fengyue-backend.service
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory={DIALOGUE_REMOTE}/current
Environment=NODE_ENV=production
Environment=HOMER_BACKEND_BASE_URL=http://127.0.0.1:8008
Environment=HOMER_LOGIN_URL=/app/login.html
ExecStart=/usr/bin/node server.js --port {port} --dataRoot {DIALOGUE_DATA_REMOTE}
Restart=on-failure
RestartSec=3
TimeoutStartSec=180
TimeoutStopSec=30
User=homer-dialogue
Group=homer-dialogue
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
ReadWritePaths={DIALOGUE_DATA_REMOTE}

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
NEW_USER_INITIAL_POINTS=2500
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
    parser.add_argument("--card-version-workshop", type=Path, default=DEFAULT_CARD_VERSION_WORKSHOP)
    parser.add_argument("--community-workshop", type=Path, default=DEFAULT_COMMUNITY_WORKSHOP)
    parser.add_argument("--card-extra-workshop", type=Path, default=DEFAULT_CARD_EXTRA_WORKSHOP)
    parser.add_argument("--chat-mod-workshop", type=Path, default=DEFAULT_CHAT_MOD_WORKSHOP)
    parser.add_argument("--spine-media-support", type=Path, default=DEFAULT_SPINE_MEDIA_SUPPORT)
    parser.add_argument("--frontend", type=Path, default=DEFAULT_FRONTEND, help="前端目录，会上传到 /var/www/ai-fengyue-frontend")
    parser.add_argument("--dialogue-runtime", type=Path, default=DEFAULT_DIALOGUE_RUNTIME, help="固定 SillyTavern runtime 源码目录")
    parser.add_argument("--dialogue-port", type=int, default=8091, help="内部 dialogue runtime loopback 端口")
    parser.add_argument("--apk", type=Path, default=DEFAULT_APK, help="要发布到 /download/ai-xingyue-latest.apk 的 APK 文件")
    parser.add_argument("--skip-frontend", action="store_true", help="跳过前端上传")
    parser.add_argument("--skip-dialogue-runtime", action="store_true", help="跳过 SillyTavern runtime 上传与重启（Nginx 路由仍保留）")
    parser.add_argument("--skip-apk", action="store_true", help="跳过 APK 上传")
    parser.add_argument("--admin-emails", default="", help="逗号分隔的管理员邮箱列表（写入 ai-fengyue.env，会替换现有 ADMIN_EMAILS 行）")
    parser.add_argument("--domain", default="https://patcher.villainy.top")
    parser.add_argument("--domain-name", default="patcher.villainy.top")
    parser.add_argument("--patch-main-site", action="store_true", help="also expose backend paths on villainy.top")
    parser.add_argument("--skip-certbot", action="store_true")
    parser.add_argument("--skip-mail-install", action="store_true")
    args = parser.parse_args()

    validate_deploy_args(args)

    backend_modules = [
        ("ai_fengyue_local_server.py", args.backend),
        ("card_experience_extension.py", args.card_media_extension),
        ("card_version_workshop.py", args.card_version_workshop),
        ("community_workshop.py", args.community_workshop),
        ("card_extra_workshop.py", args.card_extra_workshop),
        ("chat_mod_workshop.py", args.chat_mod_workshop),
        ("spine_media_support.py", args.spine_media_support),
    ]
    for _, local_path in backend_modules:
        if not local_path.is_file():
            raise FileNotFoundError(local_path)
    if not args.skip_dialogue_runtime and not args.dialogue_runtime.is_dir():
        raise FileNotFoundError(args.dialogue_runtime)
    if not args.key.exists():
        raise FileNotFoundError(args.key)

    dialogue_temp_dir = None
    dialogue_package = None
    if not args.skip_dialogue_runtime:
        dialogue_temp_dir = tempfile.TemporaryDirectory(prefix="homer-dialogue-deploy-")
        archive_path = Path(dialogue_temp_dir.name) / "homer-dialogue-runtime.tgz"
        dialogue_package = build_dialogue_runtime_archive(args.dialogue_runtime, archive_path)
        log(
            "prepared dialogue runtime package: "
            f"{dialogue_package['files']} files, {dialogue_package['archive_bytes']:,} bytes, "
            f"sha256={dialogue_package['sha256']}"
        )

    frontend_temp_dir = None
    frontend_package = None
    if not args.skip_frontend and args.frontend.exists():
        frontend_temp_dir = tempfile.TemporaryDirectory(prefix="homer-frontend-deploy-")
        frontend_archive_path = Path(frontend_temp_dir.name) / "homer-frontend.tgz"
        frontend_package = build_frontend_archive(args.frontend, frontend_archive_path)
        log(
            "prepared frontend package: "
            f"{frontend_package['files']} files, {frontend_package['archive_bytes']:,} bytes, "
            f"sha256={frontend_package['sha256']}"
        )

    ssh = None
    rollback_ssh = None
    dialogue_previous_target = ""
    dialogue_current_kind = "missing"
    dialogue_legacy_backup = ""
    dialogue_release_dir = ""
    dialogue_switched = False
    patcher_nginx_existed = False
    dialogue_unit_existed = False
    patcher_nginx_backup = ""
    dialogue_unit_backup = ""
    try:
        ssh = connect_with_retries(args.host, args.user, args.key)
        sftp = ssh.open_sftp()
        timestamp = time.strftime("%Y%m%d-%H%M%S")
        patcher_nginx_backup = f"{PATCHER_NGINX_CONF}.bak-{timestamp}"
        dialogue_unit_backup = f"{DIALOGUE_UNIT}.bak-{timestamp}"
        patcher_nginx_existed = run(
            ssh,
            f"if [ -f {PATCHER_NGINX_CONF} ]; then printf 1; else printf 0; fi",
        ).strip() == "1"
        dialogue_unit_existed = run(
            ssh,
            f"if [ -s {DIALOGUE_UNIT} ]; then printf 1; else printf 0; fi",
        ).strip() == "1"
        run(ssh, "hostname && python3 --version && nginx -t")
        run(ssh, f"mkdir -p {args.deploy_dir}/data")
        backup_dir = posixpath.join(args.deploy_dir, "backups")
        run(ssh, f"mkdir -p {backup_dir} && chmod 700 {backup_dir}")
        unit_path = "/etc/systemd/system/ai-fengyue-backend.service"
        run(ssh, f"[ -f {unit_path} ] && cp {unit_path} {unit_path}.bak-{timestamp} || true")
        remote_db = posixpath.join(args.deploy_dir, "data", "ai_fengyue.sqlite3")
        remote_db_backup = posixpath.join(backup_dir, f"ai_fengyue-before-community-versions-{timestamp}.sqlite3")
        run(
            ssh,
            f"if [ -f {remote_db} ]; then "
            "python3 -c 'import sqlite3,sys; "
            "src=sqlite3.connect(sys.argv[1]); dst=sqlite3.connect(sys.argv[2]); "
            "src.backup(dst); a=src.execute(\"pragma quick_check\").fetchone()[0]; "
            "b=dst.execute(\"pragma quick_check\").fetchone()[0]; "
            "print(\"sqlite backup quick_check: live=%s backup=%s\"%(a,b)); "
            "assert a==\"ok\" and b==\"ok\"; dst.close(); src.close()' "
            f"{remote_db} {remote_db_backup}; chmod 600 {remote_db_backup}; fi",
        )
        run(ssh, "id -u ai-xingyue >/dev/null 2>&1 || useradd --system --home /nonexistent --shell /usr/sbin/nologin ai-xingyue")
        run(ssh, f"cp {NGINX_CONF} {NGINX_CONF}.bak-ai-xingyue-{timestamp}")
        run(ssh, f"[ -f {PATCHER_NGINX_CONF} ] && cp {PATCHER_NGINX_CONF} {patcher_nginx_backup} || true")

        if not args.skip_dialogue_runtime:
            run(ssh, "node --version && npm --version && node -e \"if(Number(process.versions.node.split('.')[0])<20)process.exit(1)\"")
            run(ssh, "id -u homer-dialogue >/dev/null 2>&1 || useradd --system --home /nonexistent --shell /usr/sbin/nologin homer-dialogue")
            run(
                ssh,
                f"mkdir -p {DIALOGUE_REMOTE}/releases {DIALOGUE_REMOTE}/backups "
                f"{DIALOGUE_DATA_REMOTE} {DIALOGUE_DATA_REMOTE}/backups && "
                f"chown root:homer-dialogue {DIALOGUE_REMOTE} {DIALOGUE_REMOTE}/releases && "
                f"chmod 750 {DIALOGUE_REMOTE} {DIALOGUE_REMOTE}/releases && "
                f"chown root:root {DIALOGUE_REMOTE}/backups && chmod 700 {DIALOGUE_REMOTE}/backups && "
                f"chown homer-dialogue:homer-dialogue {DIALOGUE_DATA_REMOTE} "
                f"{DIALOGUE_DATA_REMOTE}/backups && "
                f"chmod 750 {DIALOGUE_DATA_REMOTE} {DIALOGUE_DATA_REMOTE}/backups",
            )
            dialogue_current_kind = run(
                ssh,
                f"if [ -L {DIALOGUE_REMOTE}/current ]; then printf symlink; "
                f"elif [ -d {DIALOGUE_REMOTE}/current ]; then printf directory; "
                f"elif [ -e {DIALOGUE_REMOTE}/current ]; then printf other; else printf missing; fi",
            ).strip()
            if dialogue_current_kind == "other":
                raise RuntimeError("existing dialogue runtime current path is not a directory or symlink")
            if dialogue_current_kind in {"symlink", "directory"}:
                dialogue_previous_target = run(
                    ssh,
                    f"readlink -f {DIALOGUE_REMOTE}/current 2>/dev/null || true",
                ).strip()
            else:
                dialogue_previous_target = ""
            if dialogue_current_kind == "symlink" and not dialogue_previous_target:
                raise RuntimeError("existing dialogue runtime symlink is broken")
            if dialogue_previous_target and not re.fullmatch(r"/[A-Za-z0-9._/-]+", dialogue_previous_target):
                raise RuntimeError("existing dialogue runtime target has an unsafe path")
            run(ssh, f"[ -s {DIALOGUE_UNIT} ] && cp {DIALOGUE_UNIT} {dialogue_unit_backup} || true")
            dialogue_data_backup = f"{DIALOGUE_REMOTE}/backups/homer-dialogue-data-{timestamp}.tgz"
            run(
                ssh,
                f"if [ -d {DIALOGUE_DATA_REMOTE} ] && "
                f"[ -n \"$(find {DIALOGUE_DATA_REMOTE} -mindepth 1 -print -quit)\" ]; then "
                f"tar -C {posixpath.dirname(DIALOGUE_DATA_REMOTE)} -czf {dialogue_data_backup} "
                f"--exclude='{posixpath.basename(DIALOGUE_DATA_REMOTE)}/_webpack' "
                f"{posixpath.basename(DIALOGUE_DATA_REMOTE)} && chmod 600 {dialogue_data_backup}; fi",
            )

        remote_backend_modules = []
        for remote_name, local_path in backend_modules:
            remote_path = posixpath.join(args.deploy_dir, remote_name)
            remote_backend_modules.append(remote_path)
            run(ssh, f"[ -f {remote_path} ] && cp {remote_path} {remote_path}.bak-{timestamp} || true")
            log(f"uploading backend module {local_path.name} to {remote_path}")
            put_file(sftp, local_path, remote_path, 0o644)
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
            migrated_lines = []
            for line in lines:
                if line.lstrip().startswith("NEW_USER_INITIAL_POINTS="):
                    current_value = line.split("=", 1)[1].strip()
                    if current_value == "500":
                        line = "NEW_USER_INITIAL_POINTS=2500"
                        changed_env = True
                        log(f"updated NEW_USER_INITIAL_POINTS from 500 to 2500 in {env_path}")
                migrated_lines.append(line)
            lines = migrated_lines
            defaults = {
                "AUTH_TOKEN_SECRET": secrets.token_urlsafe(48),
                "AUTH_TOKEN_TTL_SECONDS": "2592000",
                "NEW_USER_INITIAL_POINTS": "2500",
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

        log(f"writing systemd unit: {unit_path}")
        upload_text(sftp, unit_path, service_unit(args.deploy_dir, args.port))

        log(f"writing patcher nginx site: {PATCHER_NGINX_CONF}")
        upload_text(sftp, PATCHER_NGINX_CONF, patcher_server_config(args.domain_name, args.port, args.dialogue_port))
        run(ssh, f"[ -L /etc/nginx/sites-enabled/patcher.conf ] && rm -f /etc/nginx/sites-enabled/patcher.conf || true")
        run(ssh, f"ln -sf {PATCHER_NGINX_CONF} /etc/nginx/sites-enabled/ai-fengyue-patcher.conf")

        if not args.skip_dialogue_runtime:
            assert dialogue_package is not None
            remote_dialogue_archive = f"/tmp/homer-dialogue-runtime-{timestamp}.tgz"
            dialogue_release_dir = f"{DIALOGUE_REMOTE}/releases/{timestamp}"
            log(f"uploading dialogue runtime package -> {remote_dialogue_archive}")
            put_file(sftp, dialogue_package["path"], remote_dialogue_archive, 0o600)
            run(
                ssh,
                f"printf '%s  %s\n' '{dialogue_package['sha256']}' '{remote_dialogue_archive}' | sha256sum -c -",
            )
            run(
                ssh,
                f"test ! -e {dialogue_release_dir} && mkdir -p {dialogue_release_dir} && "
                f"tar -xzf {remote_dialogue_archive} -C {dialogue_release_dir} && "
                f"rm -f {remote_dialogue_archive} && "
                f"test -f {dialogue_release_dir}/server.js && "
                f"test -f {dialogue_release_dir}/package-lock.json",
            )
            run(
                ssh,
                f"cd {dialogue_release_dir} && "
                f"printf '%s  package-lock.json\n' '{dialogue_package['package_lock_sha256']}' | sha256sum -c - && "
                "npm ci --omit=dev --no-audit --no-fund",
            )
            run(
                ssh,
                f"cd {dialogue_release_dir} && node -e \"const v=require('./node_modules/webpack/package.json').version;"
                f"console.log('webpack='+v);if(v!=='{DIALOGUE_EXPECTED_WEBPACK}')process.exit(1)\"",
            )
            run(
                ssh,
                f"chown -R root:root {dialogue_release_dir} && chmod -R u=rwX,go=rX {dialogue_release_dir} && "
                f"mkdir -p {DIALOGUE_DATA_REMOTE}/backups && "
                f"chown -R homer-dialogue:homer-dialogue {DIALOGUE_DATA_REMOTE} && "
                f"chmod 750 {DIALOGUE_DATA_REMOTE} {DIALOGUE_DATA_REMOTE}/backups && "
                f"test ! -e {dialogue_release_dir}/backups && "
                f"ln -s {DIALOGUE_DATA_REMOTE}/backups {dialogue_release_dir}/backups && "
                f"test -L {dialogue_release_dir}/backups && "
                f"test \"$(readlink {dialogue_release_dir}/backups)\" = \"{DIALOGUE_DATA_REMOTE}/backups\"",
            )
            log(f"writing dialogue systemd unit: {DIALOGUE_UNIT}")
            upload_text(sftp, DIALOGUE_UNIT, dialogue_service_unit(args.dialogue_port), 0o644)
            next_link = f"{DIALOGUE_REMOTE}/current.next-{timestamp}"
            if dialogue_current_kind == "directory":
                dialogue_legacy_backup = f"{DIALOGUE_REMOTE}/current.legacy-{timestamp}"
                run(
                    ssh,
                    f"test ! -e {dialogue_legacy_backup} && mv {DIALOGUE_REMOTE}/current {dialogue_legacy_backup}",
                )
                dialogue_previous_target = dialogue_legacy_backup
            run(
                ssh,
                f"ln -s releases/{timestamp} {next_link} && mv -Tf {next_link} {DIALOGUE_REMOTE}/current",
            )
            dialogue_switched = True

        # 前端上传
        if not args.skip_frontend:
            if not args.frontend.exists():
                log(f"warning: frontend dir not found: {args.frontend}; skip frontend upload")
            else:
                assert frontend_package is not None
                frontend_backup = posixpath.join(backup_dir, f"frontend-source-before-community-versions-{timestamp}.tgz")
                run(
                    ssh,
                    f"if [ -d {FRONTEND_REMOTE} ]; then tar -C {posixpath.dirname(FRONTEND_REMOTE)} -czf {frontend_backup} "
                    f"--exclude='{posixpath.basename(FRONTEND_REMOTE)}/media-cache' "
                    f"--exclude='{posixpath.basename(FRONTEND_REMOTE)}/download' "
                    f"{posixpath.basename(FRONTEND_REMOTE)}; chmod 600 {frontend_backup}; fi",
                )
                log(f"uploading frontend from {args.frontend} -> {FRONTEND_REMOTE}")
                remote_frontend_archive = f"/tmp/homer-frontend-{timestamp}.tgz"
                put_file(sftp, frontend_package["path"], remote_frontend_archive, 0o600)
                run(
                    ssh,
                    f"printf '%s  %s\n' '{frontend_package['sha256']}' '{remote_frontend_archive}' | sha256sum -c - && "
                    f"mkdir -p {FRONTEND_REMOTE}/download {FRONTEND_REMOTE}/media-cache && "
                    f"tar -xzf {remote_frontend_archive} -C {FRONTEND_REMOTE} && "
                    f"rm -f {remote_frontend_archive} {FRONTEND_REMOTE}/app/open-source.html",
                )
                log(f"uploaded {frontend_package['files']} frontend files from verified archive")
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
        run(ssh, f"python3 -m py_compile {' '.join(remote_backend_modules)}")
        run(ssh, "systemctl enable --now ai-fengyue-backend.service")
        run(ssh, "systemctl restart ai-fengyue-backend.service")
        run(
            ssh,
            f"ok=0; for i in $(seq 1 90); do "
            f"if curl -fsS http://127.0.0.1:{args.port}/health >/tmp/ai-fengyue-health.txt 2>/dev/null; then "
            "cat /tmp/ai-fengyue-health.txt; ok=1; break; fi; sleep 1; done; "
            "if [ \"$ok\" -ne 1 ]; then "
            "systemctl --no-pager --full status ai-fengyue-backend.service | sed -n '1,40p'; "
            "journalctl -u ai-fengyue-backend.service -n 80 --no-pager; "
            f"ss -ltnp | grep ':{args.port} ' || true; exit 1; fi",
        )
        run(ssh, "systemctl --no-pager --full status ai-fengyue-backend.service | sed -n '1,18p'")
        run(
            ssh,
            f"python3 -c 'import sqlite3; db=sqlite3.connect(\"{remote_db}\"); "
            "result=db.execute(\"pragma quick_check\").fetchone()[0]; print(\"live sqlite quick_check:\",result); "
            "assert result==\"ok\"; db.close()'",
        )
        if not args.skip_dialogue_runtime:
            run(ssh, "systemctl enable --now homer-dialogue.service")
            run(ssh, "systemctl restart homer-dialogue.service")
            run(
                ssh,
                f"ok=0; for i in $(seq 1 180); do "
                f"if curl -fsS -o /dev/null http://127.0.0.1:{args.dialogue_port}/csrf-token 2>/dev/null; then "
                'echo "dialogue health: ok"; ok=1; break; fi; sleep 1; done; '
                "if [ \"$ok\" -ne 1 ]; then "
                "systemctl --no-pager --full status homer-dialogue.service | sed -n '1,50p'; "
                "journalctl -u homer-dialogue.service -n 120 --no-pager; "
                f"ss -ltnp | grep ':{args.dialogue_port} ' || true; exit 1; fi",
            )
            run(ssh, "systemctl --no-pager --full status homer-dialogue.service | sed -n '1,22p'")
            run(
                ssh,
                f"listeners=\"$(ss -H -ltn | awk '$4 ~ /:{args.dialogue_port}$/ {{print $4}}')\"; "
                "printf 'dialogue listeners: %s\\n' \"$listeners\"; "
                f"[ \"$listeners\" = \"127.0.0.1:{args.dialogue_port}\" ]",
            )
            run(
                ssh,
                f"cd {DIALOGUE_REMOTE}/current && node -e \"const v=require('./node_modules/webpack/package.json').version;"
                f"console.log('runtime webpack='+v);if(v!=='{DIALOGUE_EXPECTED_WEBPACK}')process.exit(1)\"",
            )
        run(
            ssh,
            f"if ! nginx -t; then "
            f"if [ -f {patcher_nginx_backup} ]; then cp {patcher_nginx_backup} {PATCHER_NGINX_CONF}; fi; "
            "nginx -t || true; exit 1; fi",
        )
        if not args.skip_certbot:
            run(ssh, f"certbot --nginx -d {args.domain_name} --non-interactive --agree-tos -m admin@{args.domain_name} --redirect", check=False)
            run(ssh, "nginx -t")
        run(ssh, "systemctl reload nginx")
        run(ssh, f"curl -k -sS http://127.0.0.1:{args.port}/health")
        run(ssh, f"curl -k -sS {args.domain}/health")
        run(ssh, f"grep -qx 'CONTENT_MODE=local_only' {env_path}")
        run(
            ssh,
            f"curl -k -fsSI {args.domain}/module/dialogue/ | tr -d '\\r' | "
            f"grep -iE '{nginx_location_header_pattern('/app/chat.html')}'",
        )
        run(
            ssh,
            f"curl -k -fsSI {args.domain}/dialogue-core/version | tr -d '\\r' | "
            f"grep -iE '{nginx_location_header_pattern('/module/dialogue/version')}'",
        )
        run(
            ssh,
            f"curl -k -fsSI -H 'Referer: {args.domain}/module/dialogue/' {args.domain}/script.js | tr -d '\\r' | "
            f"grep -iE '{nginx_location_header_pattern('/module/dialogue/script.js')}'",
        )
        run(
            ssh,
            f"curl -k -sSI '{args.domain}/module/dialogue/?homer_embed=1' | tr -d '\\r' | "
            "grep -iE '^(content-security-policy: .*frame-ancestors .self.|x-frame-options: SAMEORIGIN|location: /app/login.html)$'",
        )
        # 验证前端
        if not args.skip_frontend:
            run(ssh, f"curl -k -sI {args.domain}/ | head -n 5", check=False)
            run(ssh, f"curl -k -sI {args.domain}/dashboard.html | head -n 5", check=False)
            run(ssh, f"curl -k -sI {args.domain}/admin.html | head -n 5", check=False)
            run(
                ssh,
                f"curl -k -fsSI {args.domain}/app/assets/js/card-experience-runtime.mjs | "
                "tr -d '\\r' | grep -iE '^content-type: (text|application)/(javascript|x-javascript)'",
            )
            run(
                ssh,
                f"curl -k -fsSI {args.domain}/app/assets/vendor/spine-webgl.js | "
                "tr -d '\\r' | grep -iE '^content-type: (text|application)/(javascript|x-javascript)'",
            )
            run(ssh, f"curl -k -fsSI {args.domain}/app/assets/vendor/SPINE-RUNTIMES-LICENSE.txt | head -n 5")
            run(ssh, f"test ! -e {FRONTEND_REMOTE}/app/open-source.html")
            run(
                ssh,
                f"test \"$(curl -k -sS -o /dev/null -w '%{{http_code}}' "
                f"{args.domain}/app/open-source.html)\" = 404",
            )
            run(
                ssh,
                f"! curl -k -fsS {args.domain}/app/assets/js/layout.js | "
                "grep -F '/app/open-source.html' >/dev/null",
            )
            run(
                ssh,
                f"! curl -k -fsS {args.domain}/app/info.html | "
                "grep -F '开源许可与源码' >/dev/null",
            )
        # Keep deploy verification read-only. Registration/email probes send real
        # messages and consume abuse-control quotas, so they belong in an explicit
        # post-deploy acceptance test rather than the deploy helper.
        log("deployment complete")
        return 0
    except Exception:
        if ssh is not None:
            log("deployment failed; restoring dialogue runtime/Nginx pointers where backups exist")
            try:
                rollback_ssh = ssh
                if not ssh_connection_active(rollback_ssh):
                    try:
                        rollback_ssh.close()
                    except Exception:
                        pass
                    log("deployment SSH session is unavailable; reconnecting for rollback")
                    rollback_ssh = connect_with_retries(args.host, args.user, args.key)
                if dialogue_switched:
                    if dialogue_legacy_backup:
                        run(
                            rollback_ssh,
                            f"rm -f {DIALOGUE_REMOTE}/current && "
                            f"if [ -d {dialogue_legacy_backup} ]; then mv {dialogue_legacy_backup} {DIALOGUE_REMOTE}/current; fi",
                            check=False,
                        )
                    elif dialogue_previous_target:
                        rollback_link = f"{DIALOGUE_REMOTE}/current.rollback-{int(time.time())}"
                        run(
                            rollback_ssh,
                            f"ln -s {dialogue_previous_target} {rollback_link} && "
                            f"mv -Tf {rollback_link} {DIALOGUE_REMOTE}/current",
                            check=False,
                        )
                    else:
                        run(rollback_ssh, f"rm -f {DIALOGUE_REMOTE}/current", check=False)
                elif dialogue_legacy_backup:
                    run(
                        rollback_ssh,
                        f"if [ ! -e {DIALOGUE_REMOTE}/current ] && [ -d {dialogue_legacy_backup} ]; then "
                        f"mv {dialogue_legacy_backup} {DIALOGUE_REMOTE}/current; fi",
                        check=False,
                    )
                if dialogue_unit_existed and dialogue_unit_backup:
                    run(
                        rollback_ssh,
                        f"if [ -f {dialogue_unit_backup} ]; then cp {dialogue_unit_backup} {DIALOGUE_UNIT}; fi",
                        check=False,
                    )
                else:
                    run(rollback_ssh, "systemctl disable --now homer-dialogue.service || true", check=False)
                    run(rollback_ssh, f"rm -f {DIALOGUE_UNIT}", check=False)
                if patcher_nginx_existed and patcher_nginx_backup:
                    run(
                        rollback_ssh,
                        f"if [ -f {patcher_nginx_backup} ]; then cp {patcher_nginx_backup} {PATCHER_NGINX_CONF}; fi",
                        check=False,
                    )
                else:
                    run(
                        rollback_ssh,
                        f"rm -f {PATCHER_NGINX_CONF} /etc/nginx/sites-enabled/ai-fengyue-patcher.conf",
                        check=False,
                    )
                run(rollback_ssh, "systemctl daemon-reload", check=False)
                if dialogue_unit_existed and dialogue_previous_target:
                    run(rollback_ssh, "systemctl restart homer-dialogue.service", check=False)
                run(rollback_ssh, "nginx -t && systemctl reload nginx", check=False)
            except Exception as rollback_error:
                log(f"warning: automatic dialogue rollback encountered an error: {rollback_error}")
        raise
    finally:
        if rollback_ssh is not None and rollback_ssh is not ssh:
            rollback_ssh.close()
        if ssh is not None:
            ssh.close()
        if dialogue_temp_dir is not None:
            dialogue_temp_dir.cleanup()
        if frontend_temp_dir is not None:
            frontend_temp_dir.cleanup()


if __name__ == "__main__":
    raise SystemExit(main())
