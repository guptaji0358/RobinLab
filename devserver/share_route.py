"""/api/collection/share: POST mints, GET resolves."""

import urllib.parse

from .responses import send_json
from .share_create import create_share
from .share_resolve import resolve_share


def serve_share(h, parsed: urllib.parse.SplitResult) -> None:
    secret = h.share_secret
    if not secret:
        send_json(h, {"error": "not_configured", "message": "Set SHARE_SECRET (or HF_TOKEN) to enable share links."}, 500)
        return

    if h.command == "POST":
        create_share(h, secret)
    elif h.command in ("GET", "HEAD"):
        resolve_share(h, parsed, secret)
    else:
        send_json(h, {"error": "method_not_allowed"}, 405)
