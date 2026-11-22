"""POST /api/collection/share: mint a signed link."""

import json
import time
import urllib.parse

from .config import DECK_SHARE_TTL_SECONDS, SHARE_TTL_SECONDS
from .content_types import PPTX_TYPE
from .listing import get_listing
from .responses import send_json
from .share_tokens import create_share_token
from .timefmt import iso_ms


def create_share(h, secret: str) -> None:
    try:
        length = int(h.headers.get("Content-Length") or 0)
    except ValueError:
        length = 0
    try:
        body = json.loads(h.rfile.read(length).decode("utf-8") or "{}")
    except (ValueError, UnicodeDecodeError, OSError):
        body = {}

    path = body.get("path", "").strip() if isinstance(body, dict) and isinstance(body.get("path"), str) else ""
    if not path:
        send_json(h, {"error": "missing_path", "message": 'Send a JSON body like {"path":"wallpapers/foo.png"}.'}, 400)
        return

    try:
        listing = get_listing(h.token or "")
    except Exception as err:  # noqa: BLE001
        send_json(h, {"error": "upstream_error", "message": str(err)}, 502)
        return

    entry = next((file for file in listing["files"] if file["path"] == path), None)
    if entry is None:
        send_json(h, {"error": "not_found", "message": "No such file in this bucket."}, 404)
        return
    is_deck = entry["contentType"] == PPTX_TYPE
    if not entry["previewable"] and not is_deck:
        send_json(h, {"error": "unsupported_type", "message": "Only images and presentations can be shared."}, 415)
        return

    ttl_seconds = DECK_SHARE_TTL_SECONDS if is_deck else SHARE_TTL_SECONDS
    ttl_ms = ttl_seconds * 1000
    token = create_share_token(secret, entry["path"], ttl_ms)
    host = h.headers.get("Host") or "127.0.0.1:5500"
    page = "presentations" if is_deck else "collection"

    send_json(
        h,
        {
            "token": token,
            "url": f"http://{host}/{page}?share={urllib.parse.quote(token, safe='')}",
            "expiresAt": iso_ms(int(time.time() * 1000) + ttl_ms),
            "ttlSeconds": ttl_seconds,
        },
    )
