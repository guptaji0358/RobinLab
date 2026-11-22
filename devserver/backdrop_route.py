"""GET /api/collection/backdrop[?prev=scene]."""

import urllib.parse

from .backdrop import pick_backdrop
from .listing import get_listing
from .responses import send_json


def serve_backdrop(h, parsed: urllib.parse.SplitResult) -> None:
    prev = (urllib.parse.parse_qs(parsed.query).get("prev") or [""])[0]
    try:
        files = get_listing(h.token)["files"]
    except Exception:  # noqa: BLE001 - bucket unreachable: still serve animated scenes
        files = []
    send_json(h, pick_backdrop(files, prev))
