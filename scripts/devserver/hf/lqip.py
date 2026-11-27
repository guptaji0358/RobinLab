"""Blurred placeholder manifest."""

import json

from devserver.core.caches import lqip_cache
from devserver.core.config import LQIP_PATH
from devserver.hf.stream import open_file_stream


def get_lqip(token: str, thumbs: dict) -> dict:
    """The placeholder manifest, refetched only when the bucket copy changes."""
    entry = thumbs.get(LQIP_PATH)
    if not entry:
        return {}
    key = f"{entry['size']}|{entry.get('uploadedAt') or ''}"
    if lqip_cache["key"] == key:
        return lqip_cache["map"]  # type: ignore[return-value]
    try:
        conn, resp = open_file_stream(token, LQIP_PATH)
        try:
            if resp.status == 200:
                lqip_cache["map"] = json.loads(resp.read().decode("utf-8"))
                lqip_cache["key"] = key
        finally:
            conn.close()
    except Exception:  # noqa: BLE001 - placeholders are cosmetic
        pass
    return lqip_cache["map"]  # type: ignore[return-value]
