#!/usr/bin/env python3
"""对已签名 APK 做静态审计：URL / 旧 IP / 旧品牌 / 高置信凭据 / dex 结构。

只读，不改动任何文件。输出 JSON 摘要 + 人读表格。
"""

from __future__ import annotations

import argparse
import json
import re
import zipfile
from collections import Counter
from pathlib import Path

# 只在文本类条目里搜，二进制资源（png/webp/woff）跳过以免噪声。
TEXT_SUFFIXES = {
    ".html", ".htm", ".css", ".js", ".mjs", ".json", ".txt", ".map", ".svg",
    ".yaml", ".yml", ".md", ".xml", ".properties", ".csv", ".dex", ".arsc",
}

EXPECTED_HOST = "patcher.villainy.top"

# 迁移前的旧服务器 IP 与历史上游域名（AGENTS.md 记录过的那批）
FORBIDDEN = {
    "old-server-ip": r"45\.207\.192\.148",
    "raw-new-ip": r"38\.76\.218\.46",
    "old-brand-xingyue": r"AI星月",
    "old-brand-fengyue": r"AI风月",
    "old-brand-jiuguan": r"绘梦酒馆",
}

CRED_PATTERNS = {
    "sk-key": r"\bsk-[A-Za-z0-9]{20,}\b",
    "aws-akid": r"\bAKIA[0-9A-Z]{16}\b",
    "private-key-pem": r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----",
    "bearer-literal": r"Bearer\s+[A-Za-z0-9._-]{24,}",
    "resend-key": r"\bre_[A-Za-z0-9]{20,}\b",
    "password-assign": r"(?i)\b(?:password|passwd|storepass|keypass)\s*[:=]\s*[\"'][^\"']{6,}[\"']",
}

URL_RE = re.compile(rb"https?://([A-Za-z0-9.-]+)")


def scan(apk: Path) -> dict:
    result = {
        "apk": str(apk),
        "bytes": apk.stat().st_size,
        "entries": 0,
        "dex_files": [],
        "hosts": Counter(),
        "forbidden": {k: [] for k in FORBIDDEN},
        "credentials": {k: [] for k in CRED_PATTERNS},
        "text_entries_scanned": 0,
    }
    forbidden_re = {k: re.compile(v) for k, v in FORBIDDEN.items()}
    cred_re = {k: re.compile(v) for k, v in CRED_PATTERNS.items()}

    with zipfile.ZipFile(apk) as zf:
        infos = zf.infolist()
        result["entries"] = len(infos)
        for info in infos:
            name = info.filename
            if name.endswith(".dex"):
                result["dex_files"].append({"name": name, "bytes": info.file_size})
            suffix = Path(name).suffix.lower()
            if suffix not in TEXT_SUFFIXES:
                continue
            try:
                blob = zf.read(info)
            except (KeyError, zipfile.BadZipFile):
                continue
            result["text_entries_scanned"] += 1
            for host in URL_RE.findall(blob):
                result["hosts"][host.decode("ascii", "replace")] += 1
            text = blob.decode("utf-8", "replace")
            for key, rx in forbidden_re.items():
                if rx.search(text):
                    result["forbidden"][key].append(name)
            for key, rx in cred_re.items():
                for match in rx.findall(text):
                    result["credentials"][key].append(
                        {"entry": name, "sample": str(match)[:12] + "…"}
                    )
    return result


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("apk", type=Path)
    ap.add_argument("--json-out", type=Path)
    ap.add_argument("--top-hosts", type=int, default=25)
    args = ap.parse_args()

    report = scan(args.apk)

    print(f"apk     : {report['apk']}")
    print(f"bytes   : {report['bytes']:,}   entries: {report['entries']}")
    print(f"dex     : {len(report['dex_files'])} -> "
          + ", ".join(f"{d['name']}({d['bytes']:,}b)" for d in report["dex_files"]))
    print(f"scanned : {report['text_entries_scanned']} text entries")

    print("\n-- hosts referenced --")
    for host, count in report["hosts"].most_common(args.top_hosts):
        mark = "OK " if host == EXPECTED_HOST else "   "
        print(f"  {mark}{host}  x{count}")
    extra = len(report["hosts"]) - args.top_hosts
    if extra > 0:
        print(f"  ... +{extra} more distinct hosts")

    print("\n-- forbidden strings --")
    for key, hits in report["forbidden"].items():
        status = f"{len(hits)} hit(s)" if hits else "0"
        print(f"  {key:22s} {status}")
        for entry in hits[:5]:
            print(f"      {entry}")

    print("\n-- credential patterns --")
    for key, hits in report["credentials"].items():
        print(f"  {key:22s} {len(hits)}")
        for hit in hits[:3]:
            print(f"      {hit['entry']}: {hit['sample']}")

    if args.json_out:
        payload = dict(report)
        payload["hosts"] = dict(report["hosts"])
        args.json_out.write_text(json.dumps(payload, ensure_ascii=False, indent=2),
                                 encoding="utf-8")
        print(f"\nwrote {args.json_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
