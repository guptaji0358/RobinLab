"""Generate 1200x630 Open Graph preview images for RobinLab.

Usage:  python scripts/tools/make_og.py

Reads only existing site artwork (logo emblem, app icons, the CodeLens hero
screenshot) and writes optimised JPEGs under scripts/root/assets/og/ and the
project folders. Needs Pillow only. Text comes from the pages, nothing invented.
"""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parents[1] / "root"
W, H = 1200, 630
BG = (5, 7, 17)
TEXT = (237, 243, 255)
MUTED = (155, 169, 197)
CYAN = (60, 190, 255)
VIOLET = (140, 90, 255)

FONT_DIR = Path("C:/Windows/Fonts")


def font(name, size):
    for f in (name, "segoeui.ttf", "arial.ttf"):
        try:
            return ImageFont.truetype(str(FONT_DIR / f), size)
        except OSError:
            continue
    return ImageFont.load_default()


def background():
    img = Image.new("RGB", (W, H), BG)
    glow = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(glow)
    d.ellipse((-200, -250, 600, 450), fill=(20, 60, 150))
    d.ellipse((700, 250, 1400, 900), fill=(70, 30, 150))
    glow = glow.filter(ImageFilter.GaussianBlur(160))
    return Image.blend(img, glow, 0.85)


def fit(im, box):
    im = im.convert("RGBA")
    im.thumbnail(box, Image.LANCZOS)
    return im


def paste_round(base, im, xy, radius=22, border=(60, 80, 140)):
    mask = Image.new("L", im.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, *im.size), radius, fill=255)
    x, y = xy
    ImageDraw.Draw(base).rounded_rectangle(
        (x - 2, y - 2, x + im.width + 2, y + im.height + 2), radius + 2, outline=border, width=2)
    base.paste(im.convert("RGB"), xy, mask)


def text_block(d, x, y, title, tagline, tag, tsize=96):
    d.text((x, y), title, font=font("segoeuib.ttf", tsize), fill=TEXT)
    d.text((x, y + tsize + 22), tagline, font=font("segoeui.ttf", 34), fill=MUTED)
    d.text((x, H - 110), tag, font=font("segoeuisb.ttf", 26), fill=CYAN)


def save(img, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path, quality=90, optimize=True, progressive=True)
    print(path.relative_to(ROOT), img.size, path.stat().st_size // 1024, "KB")


def shared():
    img = background()
    logo = Image.open(ROOT / "assets/brand/robinlab-logo.png").convert("RGB")
    emblem = logo.crop((60, 30, 964, 640)).resize((452, 305), Image.LANCZOS)  # emblem only
    emblem = emblem.crop((40, 0, 412, 305))
    mask = Image.new("L", emblem.size, 0)
    ImageDraw.Draw(mask).rectangle((28, 28, emblem.width - 28, emblem.height - 28), fill=255)
    img.paste(emblem, (110, 160), mask.filter(ImageFilter.GaussianBlur(22)))
    d = ImageDraw.Draw(img)
    text_block(d, 540, 190, "RobinLab", "Software, built and maintained by Robin.",
               "Robin Gupta Studios", 104)
    save(img, ROOT / "assets/og/robinlab-og.jpg")


def product(name, tagline, icon_path, out, screenshot=None):
    img = background()
    d = ImageDraw.Draw(img)
    icon = fit(Image.open(icon_path), (200, 200))
    if screenshot:
        shot = fit(Image.open(screenshot), (560, 355))
        paste_round(img, shot, (W - 560 - 90, (H - shot.height) // 2))
        text_w_x = 90
        img.paste(icon.resize((96, 96), Image.LANCZOS), (text_w_x, 120), icon.resize((96, 96), Image.LANCZOS))
        d.text((text_w_x, 240), name, font=font("segoeuib.ttf", 78), fill=TEXT)
        # wrap tagline
        words, line, y = tagline.split(), "", 345
        f = font("segoeui.ttf", 30)
        for w in words:
            t = (line + " " + w).strip()
            if d.textlength(t, font=f) > 440:
                d.text((text_w_x, y), line, font=f, fill=MUTED); y += 42; line = w
            else:
                line = t
        d.text((text_w_x, y), line, font=f, fill=MUTED)
        d.text((text_w_x, H - 110), "RobinLab · Robin Gupta Studios", font=font("segoeuisb.ttf", 24), fill=CYAN)
    else:
        img.paste(icon, (130, 215), icon)
        text_block(d, 400, 215, name, tagline, "RobinLab · Robin Gupta Studios", 92)
    save(img, out)


if __name__ == "__main__":
    shared()
    P = ROOT / "projects"
    product("CodeLens", "Precision line & symbol search for text files.",
            P / "CodeLens/Assets/app_icon.ico", P / "CodeLens/Assets/og-image.jpg",
            P / "CodeLens/Assets/Screenshots/hero-dark.png")
    product("PyWix", "Turn Python scripts into Windows apps.",
            P / "Pywix/assets/APP_BUILDER_ICON.ico", P / "Pywix/assets/og-image.jpg")
    product("Contact Book", "A private desktop address book.",
            ROOT / "assets/app-icon/contactbook-icon.png", P / "Contact Book/assets/og-image.jpg")
