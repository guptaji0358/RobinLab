"""Bucket listing: visible files plus the thumbnail index, cached briefly."""

import json
import time

from .caches import listing_cache
from .config import BUCKET_ID, HF_HOST, LISTING_TTL_S, THUMB_PREFIX
from .hf_http import open_conn
from .lqip import get_lqip


def get_listing(token: str) -> dict:
    """Return the cached listing: visible files plus the thumbnail index."""
    now = time.time()
    if listing_cache["files"] and now - float(listing_cache["at"]) < LISTING_TTL_S:
        return listing_cache

    conn, resp = open_conn(
        HF_HOST,
        f"/api/buckets/{BUCKET_ID}/tree?recursive=true",
        {"Authorization": f"Bearer {token}", "Accept": "application/json"},
    )
    try:
        if resp.status != 200:
            raise RuntimeError(f"Bucket listing failed (HTTP {resp.status})")
        entries = json.loads(resp.read().decode("utf-8"))
    finally:
        conn.close()

    # Thumbnails live under `_thumbs/`. They are addressable by path but must not
    # show up as content, so they are indexed separately from the real files.
    thumbs: dict[str, dict] = {}
    for entry in entries:
        if entry.get("type") == "file" and entry["path"].startswith(THUMB_PREFIX):
            thumbs[entry["path"]] = {
                "path": entry["path"],
                "size": entry.get("size", 0),
                "uploadedAt": entry.get("uploadedAt"),
                "contentType": entry.get("contentType") or "application/octet-stream",
            }

    lqip = get_lqip(token, thumbs)

    files = []
    for entry in entries:
        if entry.get("type") != "file":
            continue
        path = entry["path"]
        if path.startswith(THUMB_PREFIX):
            continue
        slash = path.rfind("/")
        content_type = entry.get("contentType") or "application/octet-stream"
        thumb_path = f"{THUMB_PREFIX}{path}.webp"
        files.append(
            {
                "path": path,
                "name": path.rsplit("/", 1)[-1],
                "folder": "" if slash == -1 else path[:slash],
                "size": entry.get("size", 0),
                "contentType": content_type,
                "previewable": content_type.startswith("image/"),
                "uploadedAt": entry.get("uploadedAt"),
                # Set only when a generated preview exists; the client falls back
                # to the full-resolution original when it is None.
                "thumbPath": thumb_path if thumb_path in thumbs else None,
                "lqip": lqip.get(path),
            }
        )
    files.sort(key=lambda item: item["path"])

    listing_cache["at"] = now
    listing_cache["files"] = files
    listing_cache["thumbs"] = thumbs
    return listing_cache
