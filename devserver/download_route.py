"""GET /api/collection/download: watermarked image (mirror of the Pages Function)."""

import urllib.parse

from .download_local import serve_local_download
from .download_relay import serve_relayed_download
from .listing import get_listing
from .responses import send_json


def serve_download(h, parsed: urllib.parse.SplitResult) -> None:
    if h.headers.get("Sec-Fetch-Site") == "cross-site":
        send_json(h, {"error": "forbidden", "message": "Download from the collection page."}, 403)
        return
    local = not h.watermark_url or not h.watermark_key
    path = (urllib.parse.parse_qs(parsed.query).get("path") or [""])[0]
    if not path:
        send_json(h, {"error": "missing_path", "message": "A file path is required."}, 400)
        return
    try:
        entry = next((f for f in get_listing(h.token or "")["files"] if f["path"] == path), None)
    except Exception as err:  # noqa: BLE001
        send_json(h, {"error": "upstream_error", "message": str(err)}, 502)
        return
    if entry is None:
        send_json(h, {"error": "not_found", "message": "No such file in this bucket."}, 404)
        return
    if not entry["contentType"].startswith("image/"):
        send_json(h, {"error": "unsupported_type", "message": "Only images can be downloaded."}, 415)
        return

    if local:
        serve_local_download(h, path)
    else:
        serve_relayed_download(h, path, entry)
