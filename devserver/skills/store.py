"""Cached list of skills read from the bucket's `Claude Skills/` folder."""

import time

from devserver.core.caches import skills_cache
from devserver.core.config import LISTING_TTL_S, SKILLS_FOLDER
from devserver.hf.stream import open_file_stream
from devserver.hf.listing import get_listing
from devserver.skills.summary import summarise_skill


def get_skills(token: str) -> list[dict]:
    now = time.time()
    if skills_cache["items"] is not None and now - float(skills_cache["at"]) < LISTING_TTL_S:
        return skills_cache["items"]  # type: ignore[return-value]

    items = []
    for entry in get_listing(token)["files"]:  # type: ignore[union-attr]
        if entry["folder"] != SKILLS_FOLDER or not entry["name"].lower().endswith(".md"):
            continue
        conn, resp = open_file_stream(token, entry["path"])
        try:
            if resp.status != 200:
                raise RuntimeError(f"Skill fetch failed (HTTP {resp.status})")
            items.append(summarise_skill(entry, resp.read().decode("utf-8", "replace")))
        finally:
            conn.close()
    items.sort(key=lambda item: item["title"].lower())
    skills_cache["at"] = now
    skills_cache["items"] = items
    return items
