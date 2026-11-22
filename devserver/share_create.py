"""POST /api/collection/share: mint a signed link."""

import json
import time
import urllib.parse

from .config import SHARE_TTL_SECONDS
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
    if not entry["previewable"]:
        send_json(h, {"error": "unsupported_type", "message": "Only images can be shared."}, 415)
        return

    ttl_ms = SHARE_TTL_SECONDS * 1000
    token = create_share_token(secret, entry["path"], ttl_ms)
    host = h.headers.get("Host") or "127.0.0.1:5500"

    send_json(
        h,
        {
            "token": token,
            "url": f"http://{host}/collection?share={urllib.parse.quote(token, safe='')}",
            "expiresAt": iso_ms(int(time.time() * 1000) + ttl_ms),
            "ttlSeconds": SHARE_TTL_SECONDS,
        },
    )
