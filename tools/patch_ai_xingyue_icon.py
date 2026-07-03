#!/usr/bin/env python3
import argparse
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
DECODED = ROOT / "reverse-analysis" / "zip-1-target" / "decoded-base-1-full"
DEFAULT_ICON = ROOT / "output" / "zip-1-repack" / "ai-xingyue-icon-source.png"


def log(message: str) -> None:
    print(f"[ai-xingyue-icon] {message}", flush=True)


def resize_cover(src: Image.Image, width: int, height: int) -> Image.Image:
    image = src.convert("RGBA")
    sw, sh = image.size
    scale = max(width / sw, height / sh)
    nw, nh = int(round(sw * scale)), int(round(sh * scale))
    resized = image.resize((nw, nh), Image.Resampling.LANCZOS)
    left = max(0, (nw - width) // 2)
    top = max(0, (nh - height) // 2)
    return resized.crop((left, top, left + width, top + height))


def patch_image(src: Image.Image, target: Path) -> None:
    try:
        with Image.open(target) as existing:
            width, height = existing.size
    except Exception:
        width, height = (192, 192)
    output = resize_cover(src, width, height)
    target.parent.mkdir(parents=True, exist_ok=True)
    suffix = target.suffix.lower()
    if suffix == ".webp":
        output.save(target, "WEBP", quality=95, method=6)
    else:
        output.save(target, "PNG", optimize=True)
    log(f"patched {target.relative_to(ROOT)} -> {width}x{height}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Patch AI Xingyue APK icon/logo resources.")
    parser.add_argument("--icon", type=Path, default=DEFAULT_ICON)
    parser.add_argument("--decoded", type=Path, default=DECODED)
    args = parser.parse_args()

    if not args.icon.exists():
        raise FileNotFoundError(args.icon)
    if not args.decoded.exists():
        raise FileNotFoundError(args.decoded)

    with Image.open(args.icon) as src:
        targets: list[Path] = []
        targets.extend(sorted(args.decoded.glob("res/mipmap-*/logo.png")))
        for rel in [
            "res/drawable/logo.png",
            "res/drawable/base_logo.webp",
            "res/mipmap-mdpi/ic_launcher.webp",
            "res/mipmap-hdpi/ic_launcher.webp",
            "res/mipmap-xhdpi/ic_launcher.webp",
            "res/mipmap-xxhdpi/ic_launcher.webp",
            "res/mipmap-xxxhdpi/ic_launcher.webp",
            "res/mipmap-mdpi/ic_launcher_round.webp",
            "res/mipmap-hdpi/ic_launcher_round.webp",
            "res/mipmap-xhdpi/ic_launcher_round.webp",
            "res/mipmap-xxhdpi/ic_launcher_round.webp",
            "res/mipmap-xxxhdpi/ic_launcher_round.webp",
        ]:
            p = args.decoded / rel
            if p.exists():
                targets.append(p)
        seen = set()
        for target in targets:
            key = str(target.resolve()).lower()
            if key in seen:
                continue
            seen.add(key)
            patch_image(src, target)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
