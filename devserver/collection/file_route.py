"""GET /api/collection/file: stream one bucket file (Range + ETag aware)."""

from devserver.core.config import FILE_CACHE_SECONDS
from devserver.core.content_types import PPTX_TYPE, is_servable
from devserver.hf.stream import open_file_stream
from devserver.web.hotlink import is_hotlink
from devserver.hf.listing import get_listing
from devserver.web.responses import send_json


def serve_file(h, path: str, decks_only: bool = False) -> None:
    if not decks_only and is_hotlink(h):
        send_json(h, {"error": "forbidden", "message": "Open images from the collection page."}, 403)
        return
    if not path:
        send_json(h, {"error": "missing_path", "message": "A `path` query parameter is required."}, 400)
        return

    try:
        listing = get_listing(h.token or "")
    except Exception as err:  # noqa: BLE001
        send_json(h, {"error": "upstream_error", "message": str(err)}, 502)
        return

    # Generated thumbnails are valid targets too, but stay out of the listing.
    entry = next((file for file in listing["files"] if file["path"] == path), None)
    if entry is None:
        entry = listing["thumbs"].get(path)
    if entry is None:
        send_json(h, {"error": "not_found", "message": "No such file in this bucket."}, 404)
        return
    if not is_servable(entry["contentType"]) or (decks_only and entry["contentType"] != PPTX_TYPE):
        send_json(h, {"error": "unsupported_type", "message": "Only images and PowerPoint decks can be served."}, 415)
        return

    try:
        # Pass Range through so seeks / resumed downloads fetch only the bytes asked for.
        fwd = {k: v for k in ("Range", "If-Range") if (v := h.headers.get(k))}
        conn, resp = open_file_stream(h.token or "", path, fwd)
    except Exception as err:  # noqa: BLE001
        send_json(h, {"error": "upstream_error", "message": str(err)}, 502)
        return

    try:
        if resp.status == 416:
            h.send_response(416)
            h.send_header("Content-Range", resp.getheader("Content-Range") or "bytes */*")
            h.send_header("Content-Length", "0")
            h.end_headers()
            return
        if resp.status not in (200, 206):
            send_json(h, {"error": "upstream_error", "message": f"Resolve failed (HTTP {resp.status})"}, 502)
            return

        etag = resp.getheader("ETag")
        cache_control = f"public, max-age={FILE_CACHE_SECONDS}, stale-while-revalidate=86400"
        inm = h.headers.get("If-None-Match")
        if etag and inm and resp.status == 200:
            strip = lambda v: v.strip().removeprefix("W/")  # noqa: E731
            if inm.strip() == "*" or any(strip(v) == strip(etag) for v in inm.split(",")):
                # Matching ETag: a header-only answer instead of re-sending the file.
                h.send_response(304)
                h.send_header("ETag", etag)
                h.send_header("Cache-Control", cache_control)
                h.end_headers()
                return

        h.send_response(resp.status)
        h.send_header("Content-Type", resp.getheader("Content-Type") or entry["contentType"])
        h.send_header("Content-Disposition", "inline")
        h.send_header("Cache-Control", cache_control)
        h.send_header("X-Content-Type-Options", "nosniff")
        h.send_header("Accept-Ranges", "bytes")
        for name in ("Content-Length", "Content-Range", "ETag", "Last-Modified"):
            value = resp.getheader(name)
            if value:
                h.send_header(name, value)
        h.end_headers()

        if h.command == "HEAD":
            return
        try:
            while True:
                chunk = resp.read(256 * 1024)
                if not chunk:
                    break
                h.wfile.write(chunk)
        except (BrokenPipeError, ConnectionResetError):
            pass  # browser cancelled (scrolled away / navigated); stop streaming
    finally:
        conn.close()
