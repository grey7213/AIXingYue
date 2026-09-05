#!/usr/bin/env python3
"""把本地 APK 发布到 Homer 生产的 /download/ 目录并更新 release.json。

用法：
    python tools/publish_homer_apk.py E:\\酒馆开发\\output\\homer-release\\homer-1.13.0-262-release-signed.apk
    python tools/publish_homer_apk.py <apk> --prune-debug   # 同时下架旧 debug 体验包
    python tools/publish_homer_apk.py <apk> --dry-run

做的事：
  1. 本地读 APK 的包名/版本/签名证书（aapt + apksigner），拒绝 debuggable 或 .debug 包名。
  2. 校验 versionCode 必须 > 线上 release.json 里 canonical 的 versionCode，
     且签名证书指纹与线上 canonical 一致 —— 否则用户装不上覆盖更新。
  3. SFTP 上传到 `<name>.upload` 再原子 mv，避免半个文件被公网抓到。
  4. 远端 sha256 与本地逐字节比对。
  5. 重写 release.json 与 .sha256，canonical 指向新包。
  6. 通过公网 HTTPS 重新下载校验哈希。

只增不删；`--prune-debug` 才会删旧 debug 包，且会先列出待删文件。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import posixpath
import re
import shlex
import shutil
import ssl
import subprocess
import sys
import tempfile
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import paramiko

DEFAULT_HOST = "38.76.218.46"
DEFAULT_USER = "root"
DEFAULT_KEY = Path.home() / ".ssh" / "villainy_backup_ed25519"
EXPECTED_HOSTNAME = "vm-851a1bc4a978a80f"

DOWNLOAD_DIR = "/var/www/ai-fengyue-frontend/download"
CANONICAL_NAME = "ai-xingyue-latest.apk"
SITE_BASE = "https://patcher.villainy.top"
BUILD_TOOLS = Path("E:/android/Sdk/build-tools/36.1.0")

BRAND = "惑梦（Homer）"


def log(message: str) -> None:
    print(f"[homer-publish] {message}", flush=True)


def sha256_local(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


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


def run(ssh: paramiko.SSHClient, command: str, *, check: bool = True, quiet: bool = False) -> str:
    if not quiet:
        log(f"remote: {command}")
    _, stdout, stderr = ssh.exec_command(command)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    code = stdout.channel.recv_exit_status()
    if err.strip() and not quiet:
        print(err.rstrip(), file=sys.stderr)
    if check and code != 0:
        raise RuntimeError(f"remote command failed with exit {code}: {command}\n{err.strip()}")
    return out


def local_tool(name: str) -> Path:
    for suffix in ("", ".exe", ".bat"):
        candidate = BUILD_TOOLS / f"{name}{suffix}"
        if candidate.exists():
            return candidate
    raise SystemExit(f"missing build tool {name} under {BUILD_TOOLS}")


def inspect_apk(apk: Path) -> dict:
    """读出发布决策需要的全部事实，任何一项缺失就直接失败。"""
    # aapt/apksigner 打不开含非 ASCII 字符的路径（AGENTS.md 记过这个坑），
    # 仓库本身就在 E:\酒馆开发 下，所以先复制到纯 ASCII 暂存目录再读。
    with tempfile.TemporaryDirectory(prefix="homer-apk-inspect-") as staging:
        probe = Path(staging) / "probe.apk"
        shutil.copy2(apk, probe)
        info = _inspect_ascii(probe)
    info["name"] = apk.name
    info["bytes"] = apk.stat().st_size
    info["sha256"] = sha256_local(apk)
    return info


def _inspect_ascii(apk: Path) -> dict:
    badging = subprocess.run(
        [str(local_tool("aapt")), "dump", "badging", str(apk)],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    if badging.returncode != 0:
        raise SystemExit(f"aapt dump badging failed: {badging.stderr.strip()}")
    head = badging.stdout

    match = re.search(
        r"package: name='([^']+)' versionCode='(\d+)' versionName='([^']*)'", head)
    if not match:
        raise SystemExit("could not parse package line from aapt output")
    package, version_code, version_name = match.group(1), int(match.group(2)), match.group(3)

    label = None
    label_match = re.search(r"application-label:'([^']*)'", head)
    if label_match:
        label = label_match.group(1)
    launcher = None
    launcher_match = re.search(r"launchable-activity: name='([^']+)'", head)
    if launcher_match:
        launcher = launcher_match.group(1)

    certs = subprocess.run(
        [str(local_tool("apksigner")), "verify", "--print-certs", str(apk)],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    if certs.returncode != 0:
        raise SystemExit(f"apksigner verify failed: {certs.stderr.strip() or certs.stdout.strip()}")
    fp_match = re.search(r"certificate SHA-256 digest:\s*([0-9a-f]{64})", certs.stdout)
    if not fp_match:
        raise SystemExit("could not read signer certificate fingerprint")
    dn_match = re.search(r"certificate DN:\s*(.+)", certs.stdout)

    manifest = subprocess.run(
        [str(local_tool("aapt")), "dump", "xmltree", str(apk), "AndroidManifest.xml"],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    debuggable = "android:debuggable" in manifest.stdout

    return {
        "package": package,
        "version_code": version_code,
        "version_name": version_name,
        "label": label,
        "launcher": launcher,
        "cert_sha256": fp_match.group(1).lower(),
        "cert_dn": dn_match.group(1).strip() if dn_match else None,
        "debuggable": debuggable,
    }


def fetch_remote_release(ssh: paramiko.SSHClient) -> dict | None:
    raw = run(ssh, f"cat {DOWNLOAD_DIR}/release.json 2>/dev/null || true", quiet=True)
    if not raw.strip():
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        log("warning: existing release.json is not valid JSON; treating as absent")
        return None


def guard_upgrade_path(info: dict, previous: dict | None) -> None:
    """挡住会让用户装不上或装出第二个图标的包。"""
    if info["debuggable"]:
        raise SystemExit("refusing to publish: manifest has android:debuggable")
    if info["package"].endswith(".debug"):
        raise SystemExit(
            f"refusing to publish: package {info['package']} has a .debug suffix, "
            "it installs side-by-side instead of upgrading")
    if not previous:
        return
    canonical = previous.get("canonical") or {}
    prev_code = None
    prev_cert = None
    for entry in previous.get("files") or []:
        if entry.get("name") == canonical.get("name"):
            prev_code = entry.get("version_code")
            prev_cert = (entry.get("cert_sha256") or "").lower() or None
            prev_package = entry.get("package")
            break
    else:
        prev_package = None
    if prev_package and prev_package != info["package"]:
        # 允许「debug 体验包 → 正式包」这一个方向：08-18 误把 .debug 包当成
        # canonical 发了出去，用正式包纠正它是对的。反方向必须拦。
        if prev_package == f"{info['package']}.debug":
            log("warning: published canonical was the .debug package; replacing it with the "
                "release package is a correction, not an upgrade")
            log("warning: anyone who installed that debug build keeps it as a separate app "
                "and must uninstall it manually")
            prev_cert = None
        else:
            raise SystemExit(
                f"refusing to publish: package changed {prev_package} -> {info['package']}; "
                "a different package name cannot upgrade existing installs")
    if prev_code is not None and info["version_code"] < prev_code:
        raise SystemExit(
            f"refusing to publish: versionCode {info['version_code']} is lower "
            f"than the published {prev_code}")
    if (prev_code is not None and info["version_code"] == prev_code
            and info["sha256"] != canonical.get("sha256")):
        raise SystemExit("refusing to replace an existing versionCode with different bytes; increment versionCode")
    if prev_cert and prev_cert != info["cert_sha256"]:
        raise SystemExit(
            f"refusing to publish: signing certificate changed\n"
            f"  published: {prev_cert}\n  new:       {info['cert_sha256']}\n"
            "Android will reject the update. Sign with the original release keystore.")


def upload(ssh: paramiko.SSHClient, apk: Path, remote_name: str) -> None:
    sftp = ssh.open_sftp()
    try:
        target = posixpath.join(DOWNLOAD_DIR, remote_name)
        staging = f"{target}.upload"
        log(f"uploading {apk.name} -> {staging} ({apk.stat().st_size:,} bytes)")
        sftp.put(str(apk), staging)
    finally:
        sftp.close()
    run(ssh, f"chown www-data:www-data {shlex.quote(staging)} && chmod 644 {shlex.quote(staging)}")
    run(ssh, f"mv {shlex.quote(staging)} {shlex.quote(target)}")


def remote_sha256(ssh: paramiko.SSHClient, remote_name: str) -> str:
    out = run(ssh, f"sha256sum {shlex.quote(posixpath.join(DOWNLOAD_DIR, remote_name))}", quiet=True)
    return out.split()[0].lower()


def write_release_json(ssh: paramiko.SSHClient, entries: list[dict], canonical: dict) -> str:
    payload = {
        "product": BRAND,
        "brand": "惑梦",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "canonical": {
            "name": CANONICAL_NAME,
            "url": f"/download/{CANONICAL_NAME}",
            "bytes": canonical["bytes"],
            "sha256": canonical["sha256"],
            "source": canonical["name"],
            "package": canonical["package"],
            "version_name": canonical["version_name"],
            "version_code": canonical["version_code"],
            "cert_sha256": canonical["cert_sha256"],
            "release_notes": canonical.get("release_notes", "性能与稳定性改进。"),
        },
        "files": entries,
        "notice": (
            "canonical 为正式签名包，可直接覆盖安装旧版本。"
            if not canonical.get("debuggable") else
            "canonical 仍为 debug 体验包，不能覆盖正式安装。"
        ),
    }
    body = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    encoded = body.encode("utf-8")
    sftp = ssh.open_sftp()
    try:
        staging = posixpath.join(DOWNLOAD_DIR, "release.json.upload")
        with sftp.open(staging, "wb") as handle:
            handle.write(encoded)
    finally:
        sftp.close()
    run(ssh, f"chown www-data:www-data {staging} && chmod 644 {staging} "
             f"&& mv {staging} {posixpath.join(DOWNLOAD_DIR, 'release.json')}")
    return body


def write_checksum(ssh: paramiko.SSHClient, remote_name: str, digest: str) -> None:
    line = f"{digest}  {remote_name}\n"
    path = posixpath.join(DOWNLOAD_DIR, f"{remote_name}.sha256")
    run(ssh, f"printf %s {shlex.quote(line)} > {shlex.quote(path)} "
             f"&& chown www-data:www-data {shlex.quote(path)} && chmod 644 {shlex.quote(path)}",
        quiet=True)


def public_sha256(url: str) -> tuple[str, int, str | None]:
    context = ssl.create_default_context()
    request = urllib.request.Request(url, headers={"User-Agent": "homer-publish/1.0"})
    digest = hashlib.sha256()
    total = 0
    with urllib.request.urlopen(request, timeout=120, context=context) as response:
        content_type = response.headers.get("Content-Type")
        while True:
            chunk = response.read(1024 * 256)
            if not chunk:
                break
            digest.update(chunk)
            total += len(chunk)
    return digest.hexdigest(), total, content_type


def main() -> int:
    parser = argparse.ArgumentParser(description="发布 APK 到 Homer 生产下载目录")
    parser.add_argument("apk", type=Path, help="本地已签名 APK")
    parser.add_argument("--remote-name", help="服务器文件名，默认按版本自动生成")
    parser.add_argument("--notes-file", type=Path, help="UTF-8 更新说明，发布到应用内更新提示")
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--user", default=DEFAULT_USER)
    parser.add_argument("--key", type=Path, default=DEFAULT_KEY)
    parser.add_argument("--prune-debug", action="store_true",
                        help="同时删除旧的 debug 体验包（会先列出）")
    parser.add_argument("--dry-run", action="store_true", help="只做检查，不改服务器")
    args = parser.parse_args()

    apk: Path = args.apk
    if not apk.is_file():
        raise SystemExit(f"APK not found: {apk}")

    info = inspect_apk(apk)
    info["release_notes"] = (args.notes_file.read_text(encoding="utf-8-sig").strip()
                             if args.notes_file else "性能与稳定性改进。")
    if len(info["release_notes"]) > 10000:
        raise SystemExit("release notes must be at most 10000 characters")
    log(f"local  : {info['package']} {info['version_name']} ({info['version_code']})")
    log(f"         label={info['label']} launcher={info['launcher']}")
    log(f"         {info['bytes']:,} bytes sha256={info['sha256']}")
    log(f"         signer={info['cert_dn']}")
    log(f"         cert={info['cert_sha256']} debuggable={info['debuggable']}")

    ssh = connect(args.host, args.user, args.key)
    try:
        hostname = run(ssh, "hostname", quiet=True).strip()
        if hostname != EXPECTED_HOSTNAME:
            raise SystemExit(f"unexpected host {hostname!r}, expected {EXPECTED_HOSTNAME!r}")
        log(f"host   : {hostname}")

        previous = fetch_remote_release(ssh)
        if previous:
            canonical = previous.get("canonical") or {}
            log(f"remote : canonical {canonical.get('name')} sha256={canonical.get('sha256')}")
        guard_upgrade_path(info, previous)
        log("guard  : upgrade path OK (package, versionCode, signing cert)")

        remote_name = args.remote_name or (
            f"homer-android-{info['version_name']}-{info['version_code']}-release.apk")
        if (not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*\.apk", remote_name)
                or remote_name == CANONICAL_NAME):
            raise SystemExit("remote-name must be an immutable versioned APK filename")

        if args.dry_run:
            log(f"dry-run: would upload as {remote_name} and repoint {CANONICAL_NAME}")
            return 0

        existing_hash = run(ssh, f"test ! -f {shlex.quote(posixpath.join(DOWNLOAD_DIR, remote_name))} || "
                            f"sha256sum {shlex.quote(posixpath.join(DOWNLOAD_DIR, remote_name))}", quiet=True).split()
        if existing_hash and existing_hash[0] != info["sha256"]:
            raise SystemExit("refusing to overwrite an immutable versioned APK with different bytes")
        backup_dir = "/root/homer-apk-release-backup-" + datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        run(ssh, f"install -d -m 700 {backup_dir} && "
                 f"if test -f {DOWNLOAD_DIR}/release.json; then cp -p {DOWNLOAD_DIR}/release.json {backup_dir}/; fi")
        if not existing_hash:
            upload(ssh, apk, remote_name)
        digest = remote_sha256(ssh, remote_name)
        if digest != info["sha256"]:
            raise SystemExit(f"remote hash mismatch: {digest} != {info['sha256']}")
        log(f"verify : remote sha256 matches ({digest})")

        canonical_path = posixpath.join(DOWNLOAD_DIR, CANONICAL_NAME)
        run(ssh, f"cp {posixpath.join(DOWNLOAD_DIR, remote_name)} {canonical_path}.upload "
                 f"&& chown www-data:www-data {canonical_path}.upload "
                 f"&& chmod 644 {canonical_path}.upload && mv {canonical_path}.upload {canonical_path}")
        write_checksum(ssh, remote_name, digest)
        write_checksum(ssh, CANONICAL_NAME, digest)

        if args.prune_debug:
            listing = run(ssh, f"ls -1 {DOWNLOAD_DIR}", quiet=True).split()
            doomed = [n for n in listing if "debug" in n and n.endswith((".apk", ".apk.sha256"))]
            if doomed:
                log("pruning debug builds: " + ", ".join(doomed))
                for name in doomed:
                    run(ssh, f"rm -f {shlex.quote(posixpath.join(DOWNLOAD_DIR, name))}", quiet=True)
            else:
                log("no debug builds to prune")

        entries = [{
            "name": remote_name,
            "url": f"/download/{remote_name}",
            "bytes": info["bytes"],
            "sha256": info["sha256"],
            "package": info["package"],
            "version_name": info["version_name"],
            "version_code": info["version_code"],
            "build_type": "release",
            "signature_scheme": "v2+v3",
            "cert_sha256": info["cert_sha256"],
            "release_notes": info["release_notes"],
        }]
        if not args.prune_debug and previous:
            for entry in previous.get("files") or []:
                if entry.get("name") in {remote_name, CANONICAL_NAME}:
                    continue
                entries.append(entry)
        entries.append({
            "name": CANONICAL_NAME,
            "url": f"/download/{CANONICAL_NAME}",
            "bytes": info["bytes"],
            "sha256": info["sha256"],
            "package": info["package"],
            "version_name": info["version_name"],
            "version_code": info["version_code"],
            "build_type": "release",
            "signature_scheme": "v2+v3",
            "cert_sha256": info["cert_sha256"],
            "release_notes": info["release_notes"],
        })
        write_release_json(ssh, entries, info)
        log("release.json updated")
    finally:
        ssh.close()

    for name in (remote_name, CANONICAL_NAME):
        url = f"{SITE_BASE}/download/{name}"
        digest, size, content_type = public_sha256(url)
        status = "OK" if digest == info["sha256"] and size == info["bytes"] else "MISMATCH"
        log(f"public : {name} {size:,} bytes type={content_type} {status}")
        if status != "OK":
            return 1

    meta_digest, meta_size, meta_type = public_sha256(f"{SITE_BASE}/download/release.json")
    log(f"public : release.json {meta_size:,} bytes type={meta_type}")
    log("done")
    return 0


if __name__ == "__main__":
    sys.exit(main())
