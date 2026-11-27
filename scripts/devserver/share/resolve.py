"""GET /api/collection/share?token=...: resolve a link back to one image."""

import math
import time
import urllib.parse

from devserver.core.content_types import PPTX_TYPE
from devserver.hf.listing import get_listing
from devserver.web.responses import send_json
from devserver.share.tokens import read_share_token
from devserver.core.timefmt import iso_ms


def resolve_share(h, parsed: urllib.parse.SplitResult, secret: str) -> None:
    params = urllib.parse.parse_qs(parsed.query)
    token = (params.get("token") or [""])[0]
    if not token:
        send_json(h, {"error": "missing_token", "message": "A `token` query parameter is required."}, 400)
        return

    read = read_share_token(secret, token)
    if read.get("error") == "share_expired":
        if str(read.get("path", "")).startswith("presentations/"):
            message = "This shared presentation link has expired. Shared presentation links last 90 days."
        else:
            message = "This shared link has expired. Shared links last 30 minutes."
        send_json(h, {"error": "share_expired", "message": message}, 410)
        return
    if read.get("error"):
        send_json(h, {"error": "share_invalid", "message": "This shared link is not valid."}, 403)
        return

    try:
        listing = get_listing(h.token or "")
    except Exception as err:  # noqa: BLE001
        send_json(h, {"error": "upstream_error", "message": str(err)}, 502)
        return

    entry = next((file for file in listing["files"] if file["path"] == read["path"]), None)
    if entry is None:
        send_json(h, {"error": "not_found", "message": "That artwork is no longer in the collection."}, 404)
        return
    if not entry["previewable"] and entry["contentType"] != PPTX_TYPE:
        send_json(h, {"error": "unsupported_type", "message": "Only images and presentations can be shared."}, 415)
        return

    send_json(
        h,
        {
            "path": entry["path"],
            "name": entry["name"],
            "folder": entry["folder"],
            "size": entry["size"],
            "contentType": entry["contentType"],
            "url": "/api/collection/file?path=" + urllib.parse.quote(entry["path"], safe=""),
            "expiresAt": iso_ms(read["expiresAt"]),
            "secondsLeft": max(0, math.ceil((read["expiresAt"] - time.time() * 1000) / 1000)),
        },
    )
