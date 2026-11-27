"""Watermark one image with Pillow, keeping the original quality.

Pure function, no network: `apply_watermark(data) -> (bytes, format)`.

Quality rules
  * never resizes — output has the same pixel dimensions as the input
  * PNG stays PNG (lossless), JPEG stays JPEG (quality 95, no chroma subsampling),
    WebP is saved lossless
  * the ICC colour profile and EXIF block are carried over
  * only the pixels under the watermark change
"""

from __future__ import annotations

import io
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps

HERE = Path(__file__).resolve().parent
LOGO_PATH = HERE / "logo.png"

TEXT = "RGS™ · Robin Gupta"
CORNER_TEXT = "© Robin Gupta · RGS™"

# Guard against decompression bombs (a 120 MP image is ~480 MB as RGBA).
Image.MAX_IMAGE_PIXELS = 120_000_000

TILE_ALPHA = 46  # 0-255, faint repeating text
CORNER_ALPHA = 215  # corner text
LOGO_OPACITY = 0.85


def _font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for name in ("DejaVuSans-Bold.ttf", "arialbd.ttf", "Arial Bold.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default(size)  # Pillow >= 10.1: scalable bundled font


def _tiled_text(size: tuple[int, int]) -> Image.Image:
    """Faint diagonal repeating text across the whole canvas."""
    width, height = size
    short = min(width, height)
    font = _font(max(14, short // 22))
    stroke = max(1, short // 600)

    probe = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    box = probe.textbbox((0, 0), TEXT, font=font, stroke_width=stroke)
    text_w, text_h = box[2] - box[0], box[3] - box[1]

    pad = text_h
    tile = Image.new("RGBA", (text_w + pad * 2, text_h + pad * 2), (0, 0, 0, 0))
    ImageDraw.Draw(tile).text(
        (pad - box[0], pad - box[1]),
        TEXT,
        font=font,
        fill=(255, 255, 255, TILE_ALPHA),
        stroke_width=stroke,
        stroke_fill=(0, 0, 0, TILE_ALPHA),
    )
    tile = tile.rotate(30, expand=True, resample=Image.BICUBIC)

    # Work on a canvas padded by one tile so edge tiles are cut off naturally
    # (alpha_composite needs non-negative offsets), then crop back to size.
    pad_x, pad_y = tile.width, tile.height
    canvas = Image.new("RGBA", (width + pad_x * 2, height + pad_y * 2), (0, 0, 0, 0))
    step_x = int(tile.width * 1.05)
    step_y = int(tile.height * 1.05)
    for row, y in enumerate(range(0, canvas.height, step_y)):
        offset = (step_x // 2) if row % 2 else 0  # stagger rows
        for x in range(offset, canvas.width, step_x):
            if x + tile.width <= canvas.width and y + tile.height <= canvas.height:
                canvas.alpha_composite(tile, (x, y))
    return canvas.crop((pad_x, pad_y, pad_x + width, pad_y + height))


def _corner_badge(size: tuple[int, int]) -> Image.Image:
    """Logo + text in the bottom-right corner."""
    width, height = size
    short = min(width, height)
    margin = max(10, short // 50)

    layer = Image.new("RGBA", size, (0, 0, 0, 0))

    logo_side = max(40, int(short * 0.13))
    logo = Image.open(LOGO_PATH).convert("RGBA").resize((logo_side, logo_side), Image.LANCZOS)
    mask = Image.new("L", logo.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        (0, 0, logo_side - 1, logo_side - 1), radius=logo_side // 6, fill=int(255 * LOGO_OPACITY)
    )
    logo.putalpha(mask)

    font = _font(max(12, logo_side // 3))
    stroke = max(1, logo_side // 40)
    draw = ImageDraw.Draw(layer)
    box = draw.textbbox((0, 0), CORNER_TEXT, font=font, stroke_width=stroke)
    text_w, text_h = box[2] - box[0], box[3] - box[1]

    gap = max(6, logo_side // 8)
    logo_x = width - margin - logo_side
    logo_y = height - margin - logo_side
    text_x = logo_x - gap - text_w - box[0]
    text_y = logo_y + (logo_side - text_h) // 2 - box[1]

    layer.alpha_composite(logo, (logo_x, logo_y))
    draw.text(
        (text_x, text_y),
        CORNER_TEXT,
        font=font,
        fill=(255, 255, 255, CORNER_ALPHA),
        stroke_width=stroke,
        stroke_fill=(0, 0, 0, CORNER_ALPHA),
    )
    return layer


def apply_watermark(data: bytes) -> tuple[bytes, str]:
    """Return (watermarked bytes, PIL format name) for the given image bytes."""
    src = Image.open(io.BytesIO(data))
    fmt = (src.format or "PNG").upper()
    icc = src.info.get("icc_profile")
    exif = src.info.get("exif")

    src = ImageOps.exif_transpose(src) if fmt == "JPEG" else src
    original_mode = src.mode
    base = src.convert("RGBA")

    base.alpha_composite(_tiled_text(base.size))
    base.alpha_composite(_corner_badge(base.size))

    # Back to the source's colour mode so file size and fidelity match the original.
    if original_mode in ("RGBA", "LA", "PA") or "transparency" in src.info:
        out = base
    else:
        out = base.convert("RGB")

    buf = io.BytesIO()
    params: dict = {}
    if icc:
        params["icc_profile"] = icc
    if fmt == "JPEG":
        params.update(quality=95, subsampling=0, optimize=True)
        if exif:
            params["exif"] = exif
    elif fmt == "PNG":
        params.update(optimize=True)
    elif fmt == "WEBP":
        params.update(lossless=True, quality=100, method=4)
        if exif:
            params["exif"] = exif
    else:  # anything else: PNG is a safe, lossless target
        fmt = "PNG"
        params.update(optimize=True)
    out.save(buf, format=fmt, **params)
    return buf.getvalue(), fmt


if __name__ == "__main__":  # python watermark.py in.png out.png
    import sys

    if len(sys.argv) != 3:
        raise SystemExit("usage: python watermark.py <input> <output>")
    result, used = apply_watermark(Path(sys.argv[1]).read_bytes())
    Path(sys.argv[2]).write_bytes(result)
    print(f"wrote {sys.argv[2]} ({used}, {len(result):,} bytes)")
