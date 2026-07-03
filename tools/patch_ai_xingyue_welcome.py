#!/usr/bin/env python3
import argparse
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
DECODED = ROOT / "reverse-analysis" / "zip-1-target" / "decoded-base-1-full"
DEFAULT_SOURCE = Path(r"E:\xd高级动效\ai_xingyue_welcome.webp")


def log(message: str) -> None:
    print(f"[ai-xingyue-welcome] {message}", flush=True)


def resize_cover(src: Image.Image, width: int, height: int) -> Image.Image:
    image = src.convert("RGB")
    sw, sh = image.size
    scale = max(width / sw, height / sh)
    nw, nh = int(round(sw * scale)), int(round(sh * scale))
    resized = image.resize((nw, nh), Image.Resampling.LANCZOS)
    left = max(0, (nw - width) // 2)
    top = max(0, (nh - height) // 2)
    return resized.crop((left, top, left + width, top + height))


def patch_target(src: Image.Image, target: Path) -> None:
    if target.exists():
        with Image.open(target) as existing:
            width, height = existing.size
    else:
        width, height = 1125, 2436
    output = resize_cover(src, width, height)
    target.parent.mkdir(parents=True, exist_ok=True)
    output.save(target, "WEBP", quality=95, method=6)
    log(f"patched {target.relative_to(ROOT)} -> {width}x{height}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Patch AI Xingyue welcome splash resources.")
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--decoded", type=Path, default=DECODED)
    args = parser.parse_args()

    if not args.source.exists():
        raise FileNotFoundError(args.source)
    if not args.decoded.exists():
        raise FileNotFoundError(args.decoded)

    targets = [
        args.decoded / "res" / "drawable-xhdpi" / "welcome.webp",
        args.decoded / "res" / "drawable-xxhdpi" / "welcome.webp",
        args.decoded / "res" / "drawable-xxxhdpi" / "welcome.webp",
    ]
    with Image.open(args.source) as src:
        log(f"source {args.source} {src.size[0]}x{src.size[1]}")
        for target in targets:
            patch_target(src, target)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
