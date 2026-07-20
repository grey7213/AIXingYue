"""Validated storage support for Spine 4.2 portrait bundles.

A Spine portrait is uploaded as one ``.spine.zip`` containing exactly one
usable skeleton, one atlas, and every texture page referenced by that atlas.
The module never executes bundle content.  It validates the complete archive
in memory, then materializes it atomically into a server-owned directory.
"""

from __future__ import annotations

import io
import json
import os
import re
import shutil
import uuid
import zipfile
from pathlib import Path, PurePosixPath


# Browser runtime is pinned to official @esotericsoftware/spine-webgl 4.2.119.
# We accept any validated 4.2.x export; the real handoff binaries contain the
# later 4.2 referenceScale field and therefore cannot be read by npm 4.2.33.
SPINE_RUNTIME_MAJOR_MINOR = "4.2"
SPINE_MIMES = {"application/zip", "application/x-zip-compressed"}
SPINE_MAX_UPLOAD_BYTES = 60 * 1024 * 1024
SPINE_MAX_ENTRIES = 96
SPINE_MAX_TOTAL_BYTES = 160 * 1024 * 1024
SPINE_MAX_SINGLE_BYTES = 60 * 1024 * 1024
SPINE_MAX_COMPRESSION_RATIO = 200

SKELETON_EXTENSIONS = (".skel", ".skel.bytes", ".json")
ATLAS_EXTENSIONS = (".atlas", ".atlas.bytes", ".atlas.txt")
TEXTURE_EXTENSIONS = (".png", ".webp", ".jpg", ".jpeg")
ALLOWED_EXTENSIONS = SKELETON_EXTENSIONS + ATLAS_EXTENSIONS + TEXTURE_EXTENSIONS

_PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
_JPEG_MAGIC = b"\xff\xd8\xff"
_VERSION_RE = re.compile(r"^(\d+)\.(\d+)(?:\.\d+)?(?:[-+].*)?$")


class SpineMediaError(ValueError):
    """A validation error safe to return as a client-facing 400 response."""


def is_spine_zip(head: bytes) -> bool:
    return bytes(head or b"")[:4] == b"PK\x03\x04"


def _normalized_path(value: object) -> str:
    raw = str(value or "").replace("\\", "/")
    if (
        not raw
        or raw.startswith("/")
        or re.match(r"^[A-Za-z]:", raw)
        or "\0" in raw
    ):
        raise SpineMediaError(f"unsafe spine path: {raw or '(empty)'}")
    parts = raw.split("/")
    if any(part in ("", ".", "..") for part in parts):
        raise SpineMediaError(f"unsafe spine path: {raw}")
    return PurePosixPath(*parts).as_posix()


def _is_symlink(info: zipfile.ZipInfo) -> bool:
    unix_mode = (int(info.external_attr) >> 16) & 0xFFFF
    return (unix_mode & 0o170000) == 0o120000


def _has_extension(path: str, extensions: tuple[str, ...]) -> bool:
    lower = path.lower()
    return any(lower.endswith(extension) for extension in extensions)


def _read_varint(data: bytes, offset: int) -> tuple[int, int]:
    result = 0
    shift = 0
    for _ in range(5):
        if offset >= len(data):
            raise SpineMediaError("truncated Spine binary version")
        value = data[offset]
        offset += 1
        result |= (value & 0x7F) << shift
        if not value & 0x80:
            return result, offset
        shift += 7
    raise SpineMediaError("invalid Spine binary version length")


def _binary_spine_version(data: bytes) -> str:
    # Spine 4.2 SkeletonBinary starts with two int32 hash halves, followed by
    # BinaryInput.readString(): unsigned varint byte length including +1.
    if len(data) < 10:
        raise SpineMediaError("Spine binary skeleton is truncated")
    byte_count, offset = _read_varint(data, 8)
    if byte_count <= 1 or byte_count > 64:
        raise SpineMediaError("Spine binary skeleton has no usable version")
    length = byte_count - 1
    end = offset + length
    if end > len(data):
        raise SpineMediaError("Spine binary skeleton version is truncated")
    try:
        return data[offset:end].decode("utf-8")
    except UnicodeDecodeError as exc:
        raise SpineMediaError("Spine binary skeleton version is invalid") from exc


def _json_spine_version(data: bytes) -> str:
    try:
        payload = json.loads(data.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SpineMediaError("invalid Spine skeleton JSON") from exc
    if not isinstance(payload, dict) or not isinstance(payload.get("bones"), list):
        raise SpineMediaError("JSON file is not a Spine skeleton")
    skeleton = payload.get("skeleton")
    version = skeleton.get("spine") if isinstance(skeleton, dict) else ""
    return str(version or "").strip()


def _validate_version(version: str) -> str:
    match = _VERSION_RE.match(str(version or "").strip())
    if not match:
        raise SpineMediaError(f"invalid Spine export version: {version or '(missing)'}")
    major_minor = f"{match.group(1)}.{match.group(2)}"
    if major_minor != SPINE_RUNTIME_MAJOR_MINOR:
        raise SpineMediaError(
            f"Spine export {version} is incompatible with runtime {SPINE_RUNTIME_MAJOR_MINOR}"
        )
    return str(version).strip()


def _skeleton_version(path: str, data: bytes) -> str:
    version = _json_spine_version(data) if path.lower().endswith(".json") else _binary_spine_version(data)
    return _validate_version(version)


def _texture_header_is_valid(path: str, data: bytes) -> bool:
    lower = path.lower()
    if lower.endswith(".png"):
        return data.startswith(_PNG_MAGIC)
    if lower.endswith((".jpg", ".jpeg")):
        return data.startswith(_JPEG_MAGIC)
    if lower.endswith(".webp"):
        return len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP"
    return False


def _atlas_page_paths(atlas_path: str, atlas_data: bytes, files: dict[str, bytes]) -> list[str]:
    try:
        text = atlas_data.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise SpineMediaError(f"Spine atlas is not UTF-8 text: {atlas_path}") from exc
    pages: list[str] = []
    # Each atlas page begins a blank-line-separated block.  Region names live
    # later in the same block, so only the first non-empty line is a page path.
    for block in re.split(r"(?:\r?\n)[ \t]*(?:\r?\n)+", text.strip()):
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        if not lines:
            continue
        candidate = lines[0]
        if candidate.startswith(("size:", "format:", "filter:", "repeat:", "pma:")):
            continue
        try:
            page = _normalized_path(str(PurePosixPath(atlas_path).parent / candidate))
        except SpineMediaError as exc:
            raise SpineMediaError(f"unsafe texture reference in atlas: {candidate}") from exc
        if page not in files:
            raise SpineMediaError(f"Spine atlas references missing texture: {page}")
        if not _has_extension(page, TEXTURE_EXTENSIONS):
            raise SpineMediaError(f"Spine atlas references unsupported texture: {page}")
        if page not in pages:
            pages.append(page)
    if not pages:
        raise SpineMediaError("Spine atlas contains no texture pages")
    return pages


def _preferred(paths: list[str], tokens: tuple[str, ...]) -> list[str]:
    return sorted(
        paths,
        key=lambda path: (
            0 if any(token in PurePosixPath(path).name.lower() for token in tokens) else 1,
            path.count("/"),
            len(path),
            path.lower(),
        ),
    )


def inspect_spine_zip(body: bytes) -> dict:
    """Return a validated, runtime-neutral description of a Spine 4.2 zip."""
    raw_body = bytes(body or b"")
    if not raw_body or len(raw_body) > SPINE_MAX_UPLOAD_BYTES:
        raise SpineMediaError("Spine package is empty or exceeds 60MB")
    if not is_spine_zip(raw_body[:8]):
        raise SpineMediaError("Spine asset is not a zip container")
    try:
        archive = zipfile.ZipFile(io.BytesIO(raw_body))
    except zipfile.BadZipFile as exc:
        raise SpineMediaError(f"invalid Spine zip: {exc}") from exc

    files: dict[str, bytes] = {}
    sizes: dict[str, int] = {}
    total = 0
    try:
        infos = [info for info in archive.infolist() if not info.is_dir()]
        if len(infos) > SPINE_MAX_ENTRIES:
            raise SpineMediaError(f"Spine zip has too many entries ({len(infos)})")
        for info in infos:
            if _is_symlink(info):
                raise SpineMediaError(f"Spine zip contains a symbolic link: {info.filename}")
            path = _normalized_path(info.filename)
            if not _has_extension(path, ALLOWED_EXTENSIONS):
                continue
            if path in files:
                raise SpineMediaError(f"duplicate Spine path: {path}")
            if info.file_size <= 0 or info.file_size > SPINE_MAX_SINGLE_BYTES:
                raise SpineMediaError(f"invalid Spine entry size: {path}")
            if info.compress_size > 0 and info.file_size / info.compress_size > SPINE_MAX_COMPRESSION_RATIO:
                raise SpineMediaError(f"abusive Spine compression ratio: {path}")
            total += info.file_size
            if total > SPINE_MAX_TOTAL_BYTES:
                raise SpineMediaError("Spine zip expands beyond 160MB")
            try:
                data = archive.read(info)
            except (OSError, RuntimeError, zipfile.BadZipFile) as exc:
                raise SpineMediaError(f"failed to read Spine entry: {path}") from exc
            if len(data) != info.file_size:
                raise SpineMediaError(f"truncated Spine entry: {path}")
            files[path] = data
            sizes[path] = len(data)
    finally:
        archive.close()

    if not files:
        raise SpineMediaError("Spine zip contains no supported files")
    if total / max(1, len(raw_body)) > SPINE_MAX_COMPRESSION_RATIO:
        raise SpineMediaError("Spine zip compression ratio looks abusive")

    skeleton_candidates = _preferred(
        [path for path in files if _has_extension(path, SKELETON_EXTENSIONS)],
        ("main", "skeleton"),
    )
    if not skeleton_candidates:
        raise SpineMediaError("Spine package has no compatible 4.2 skeleton: missing skeleton (.skel/.json)")
    if len(skeleton_candidates) > 1:
        raise SpineMediaError(
            "ambiguous Spine package contains multiple skeleton candidates: "
            + ", ".join(skeleton_candidates)
        )
    skeleton = skeleton_candidates[0]
    try:
        version = _skeleton_version(skeleton, files[skeleton])
    except SpineMediaError as exc:
        raise SpineMediaError(f"Spine package has no compatible 4.2 skeleton: {exc}") from exc

    atlas_candidates = _preferred(
        [path for path in files if _has_extension(path, ATLAS_EXTENSIONS)],
        ("main", "skeleton"),
    )
    if not atlas_candidates:
        raise SpineMediaError("Spine package has no usable atlas: missing atlas (.atlas)")
    if len(atlas_candidates) > 1:
        raise SpineMediaError(
            "ambiguous Spine package contains multiple atlas candidates: "
            + ", ".join(atlas_candidates)
        )
    atlas = atlas_candidates[0]
    try:
        textures = _atlas_page_paths(atlas, files[atlas], files)
        for page in textures:
            if not _texture_header_is_valid(page, files[page]):
                raise SpineMediaError(f"invalid Spine texture file: {page}")
    except SpineMediaError as exc:
        raise SpineMediaError(f"Spine package has no usable atlas: {exc}") from exc

    preview_texture = max(
        textures,
        key=lambda path: (
            1 if re.search(r"(?:body|main|full|portrait)", PurePosixPath(path).name, re.I) else 0,
            sizes.get(path, 0),
        ),
    )
    materialized = {path: files[path] for path in {skeleton, atlas, *textures}}
    return {
        "skeleton": skeleton,
        "atlas": atlas,
        "textures": textures,
        "preview_texture": preview_texture,
        "binary": not skeleton.lower().endswith(".json"),
        "spine_version": version,
        "runtime_major_minor": SPINE_RUNTIME_MAJOR_MINOR,
        "files": materialized,
    }


def materialize_spine_asset(parsed: dict, dest_dir: Path, public_dir_url: str) -> dict:
    """Atomically write a previously inspected bundle and return public metadata."""
    files = parsed.get("files") if isinstance(parsed, dict) else None
    if not isinstance(files, dict) or not files:
        raise SpineMediaError("validated Spine files are missing")
    destination = Path(dest_dir).resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.parent / f".{destination.name}.tmp-{uuid.uuid4().hex}"
    base = str(public_dir_url or "").rstrip("/")
    if not base.startswith("/"):
        raise SpineMediaError("invalid Spine public path")
    try:
        temporary.mkdir(parents=True, exist_ok=False)
        for relative, data in files.items():
            path = _normalized_path(relative)
            target = (temporary / Path(*PurePosixPath(path).parts)).resolve()
            if temporary.resolve() not in target.parents:
                raise SpineMediaError("resolved Spine path escapes destination")
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(bytes(data))
        manifest = {
            "skeleton_url": f"{base}/{parsed['skeleton']}",
            "atlas_url": f"{base}/{parsed['atlas']}",
            "textures": [f"{base}/{path}" for path in parsed["textures"]],
            "preview_texture": f"{base}/{parsed['preview_texture']}",
            "binary": bool(parsed.get("binary")),
            "spine_version": str(parsed.get("spine_version") or ""),
            "runtime_major_minor": SPINE_RUNTIME_MAJOR_MINOR,
        }
        (temporary / "spine.json").write_text(
            json.dumps(manifest, ensure_ascii=False, separators=(",", ":")),
            encoding="utf-8",
        )
        if destination.exists():
            shutil.rmtree(destination)
        os.replace(temporary, destination)
        manifest["manifest_url"] = f"{base}/spine.json"
        return manifest
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise


def remove_spine_directory(path: Path) -> None:
    shutil.rmtree(Path(path), ignore_errors=True)
