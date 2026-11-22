"""Map `/collection` -> `/collection.html`, matching Cloudflare Pages."""

import os
import urllib.parse


def resolve_clean_url(h) -> None:
    """Cloudflare serves extensionless URLs, so links use `/collection`.
    This keeps local preview consistent with production."""
    parsed = urllib.parse.urlsplit(h.path)
    path = parsed.path
    if path == "/" or path.endswith("/") or "." in path.rsplit("/", 1)[-1]:
        return
    target = os.path.join(h.directory, path.lstrip("/") + ".html")
    if os.path.isfile(target):
        h.path = path + ".html" + (f"?{parsed.query}" if parsed.query else "")
