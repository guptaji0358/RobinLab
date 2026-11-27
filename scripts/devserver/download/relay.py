"""Download through the remote watermark service."""

import json
import urllib.error
import urllib.parse
import urllib.request

from devserver.web.responses import send_json


def serve_relayed_download(h, path: str, entry: dict) -> None:
    target = f"{h.watermark_url.rstrip('/')}/download?path={urllib.parse.quote(path, safe='')}"
    request = urllib.request.Request(target, headers={"X-Watermark-Key": h.watermark_key})
    try:
        with urllib.request.urlopen(request, timeout=120) as upstream:
            body = upstream.read()
            h.send_response(200)
            h.send_header("Content-Type", upstream.headers.get("Content-Type", entry["contentType"]))
            h.send_header("Content-Disposition", upstream.headers.get("Content-Disposition", "attachment"))
            h.send_header("Content-Length", str(len(body)))
            h.send_header("Cache-Control", "private, no-store")
            h.end_headers()
            h.wfile.write(body)
    except urllib.error.HTTPError as err:
        try:
            detail = json.loads(err.read()).get("error")
        except Exception:  # noqa: BLE001
            detail = None
        send_json(h, {"error": "upstream_error", "message": detail or f"Watermark service failed (HTTP {err.code})."}, 502)
    except Exception:  # noqa: BLE001
        send_json(h, {"error": "upstream_error", "message": "The watermark service could not be reached."}, 502)
