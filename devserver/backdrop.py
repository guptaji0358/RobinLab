"""Random scene config for the collection backdrop (mirror: handleBackdrop in the Function)."""

import random

from .config import BACKDROP_SCENES, WALLPAPER_FOLDER


def pick_backdrop(files: list[dict], prev: str = "") -> dict:
    """`wallpaper` shows one full-screen image from the bucket's `wallpapers/` folder,
    so it is only offered when that folder has images."""
    walls = [
        f["path"] for f in files
        if f["contentType"].startswith("image/")
        and (f["folder"] == WALLPAPER_FOLDER or f["folder"].startswith(WALLPAPER_FOLDER + "/"))
    ]
    pool = [s for s in BACKDROP_SCENES if s != prev and (s != "wallpaper" or walls)]
    scene = random.choice(pool or list(BACKDROP_SCENES[:3]))
    return {
        "scene": scene,
        "hue": random.randrange(360),
        "speed": round(random.uniform(0.7, 1.5), 2),
        "density": round(random.uniform(0.6, 1.4), 2),
        "wallpaper": random.choice(walls) if scene == "wallpaper" else "",
    }
