#!/usr/bin/env python3
"""Generate the RobinLab icon set from the studio logo.

The source artwork is a 1:1 poster: the orbital "R" emblem sits above the
ROBINLAB wordmark and the tagline. A wordmark is unreadable at 16-48 px, so the
script keeps only the emblem, centres it on the artwork's own background colour
and writes the standard icon sizes.

    python tools/make_icons.py                          # uses root/assets/robinlab-logo.png
    python tools/make_icons.py --source path/to/logo.png

Outputs (all under root/assets/):

    robinlab-mark.png        512x512 emblem, used for large/manifest icons
    robinlab-icon-192.png    192x192 manifest icon
    apple-touch-icon.png     180x180, opaque background (iOS applies its own mask)
    favicon.ico              16/32/48/64 multi-size favicon

The source image itself is copied to root/assets/robinlab-logo.png (1024x1024)
by `--install-logo`, which is how the repo stopped depending on a file outside
it. Re-running is safe: every output is deterministic.

Requires Pillow (`pip install Pillow`).
"""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ASSETS = PROJECT_ROOT / "root" / "assets"

# Content detection: pixels brighter than this count as artwork. The background
# is a near-black navy (~2, 4, 19), so 45 separates glyph/glow from empty space.
CONTENT_THRESHOLD = 45
# Gaps shorter than this are noise inside a band, not the space between blocks.
MIN_BAND_HEIGHT = 12
# Favicons are 16-48 px, so they zoom the emblem in a little; the extra margin
# of the large tile would otherwise leave the mark too small to read in a tab.
FAVICON_ZOOM = 1.12


def content_bands(luminance: np.ndarray) -> list[tuple[int, int]]:
    """Rows holding artwork, split into blocks (emblem / wordmark / tagline)."""
    rows = luminance.max(axis=1)
    bands: list[tuple[int, int]] = []
    start: int | None = None
    for y, value in enumerate(rows):
        if value > CONTENT_THRESHOLD and start is None:
            start = y
        elif value <= CONTENT_THRESHOLD and start is not None:
            bands.append((start, y - 1))
            start = None
    if start is not None:
        bands.append((start, len(rows) - 1))
    return [band for band in bands if band[1] - band[0] + 1 >= MIN_BAND_HEIGHT]


def background_colour(image: Image.Image) -> tuple[int, int, int]:
    """Average of the top-left corner, which is always empty background."""
    patch = np.asarray(image.crop((0, 0, 48, 48)).convert("RGB"), dtype=float)
    return tuple(int(round(v)) for v in patch.reshape(-1, 3).mean(axis=0))


def emblem_tile(source: Image.Image) -> Image.Image:
    """Return a square tile holding just the emblem, on the artwork background."""
    image = source.convert("RGB")
    width, height = image.size
    luminance = np.asarray(image.convert("L"), dtype=np.int16)
    bands = content_bands(luminance)
    if not bands:
        raise SystemExit("No artwork found in the source image.")

    # The first block is the emblem; everything below it is type.
    top, bottom = bands[0]
    margin = max(6, int(round(height * 0.025)))
    top = max(0, top - margin)
    bottom = min(height, bottom + margin)

    emblem = image.crop((0, top, width, bottom))
    side = width  # the tile is square, matching the original poster
    canvas = Image.new("RGB", (side, side), background_colour(image))
    y = (side - emblem.height) // 2

    # Feather the paste edges so the emblem's glow blends into the flat surround
    # instead of showing a rectangle where the crop ends.
    mask = Image.new("L", emblem.size, 255)
    draw = ImageDraw.Draw(mask)
    fade = max(8, int(round(emblem.height * 0.03)))
    for i in range(fade):
        alpha = int(255 * i / fade)
        draw.line([(0, i), (emblem.width - 1, i)], fill=alpha)
        draw.line([(0, emblem.height - 1 - i), (emblem.width - 1, emblem.height - 1 - i)], fill=alpha)
    canvas.paste(emblem, (0, y), mask)
    return canvas


def zoom_tile(tile: Image.Image, factor: float) -> Image.Image:
    """Centre-crop the tile so the emblem fills more of a small icon."""
    side = int(round(tile.width / factor))
    offset = (tile.width - side) // 2
    return tile.crop((offset, offset, offset + side, offset + side))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--source",
        type=Path,
        default=ASSETS / "robinlab-logo.png",
        help="studio logo PNG (default: root/assets/robinlab-logo.png)",
    )
    parser.add_argument(
        "--install-logo",
        action="store_true",
        help="copy --source to root/assets/robinlab-logo.png (1024px) before generating icons",
    )
    args = parser.parse_args()

    if not args.source.is_file():
        raise SystemExit(f"Source image not found: {args.source}")

    ASSETS.mkdir(parents=True, exist_ok=True)
    logo_target = ASSETS / "robinlab-logo.png"

    if args.install_logo:
        logo = Image.open(args.source).convert("RGB")
        if max(logo.size) > 1024:
            logo = logo.resize((1024, 1024) if logo.width == logo.height else
                               (1024, round(logo.height * 1024 / logo.width)), Image.LANCZOS)
        logo.save(logo_target, "PNG", optimize=True)
        print(f"logo     {logo_target.relative_to(PROJECT_ROOT)}  {logo_target.stat().st_size // 1024} KB")
        source = logo
    else:
        source = Image.open(args.source)

    tile = emblem_tile(source)

    mark = tile.resize((512, 512), Image.LANCZOS)
    mark.save(ASSETS / "robinlab-mark.png", "PNG", optimize=True)

    tile.resize((192, 192), Image.LANCZOS).save(ASSETS / "robinlab-icon-192.png", "PNG", optimize=True)

    # iOS masks the corners itself; an opaque square is what it expects.
    tile.resize((180, 180), Image.LANCZOS).save(ASSETS / "apple-touch-icon.png", "PNG", optimize=True)

    favicon = zoom_tile(tile, FAVICON_ZOOM).resize((64, 64), Image.LANCZOS)
    favicon.save(
        ASSETS / "favicon.ico",
        sizes=[(16, 16), (32, 32), (48, 48), (64, 64)],
    )

    for name in ("robinlab-mark.png", "robinlab-icon-192.png", "apple-touch-icon.png", "favicon.ico"):
        path = ASSETS / name
        print(f"wrote    {path.relative_to(PROJECT_ROOT)}  {path.stat().st_size // 1024} KB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
