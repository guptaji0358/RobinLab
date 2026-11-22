"""Download without a watermark Space: stamp the image here with the same Pillow code."""

import sys
import urllib.parse

from .hf_stream import open_file_stream
from .paths import WATERMARK_DIR
from .responses import send_json


def serve_local_download(h, path: str) -> None:
    try:
        sys.path.insert(0, WATERMARK_DIR)
        from watermark import apply_watermark  # type: ignore

        conn, resp = open_file_stream(h.token or "", path, {})
        try:
            original = resp.read()
        finally:
            conn.close()
        data, fmt = apply_watermark(original)
    except Exception as err:  # noqa: BLE001
        send_json(h, {"error": "upstream_error", "message": f"Local watermark failed: {err}"}, 502)
        return
    stem = path.rsplit("/", 1)[-1].rpartition(".")[0]
    ext = {"JPEG": "jpg"}.get(fmt, fmt.lower())
    media = {"PNG": "image/png", "JPEG": "image/jpeg", "WEBP": "image/webp"}.get(fmt, "image/png")
    h.send_response(200)
    h.send_header("Content-Type", media)
    h.send_header("Content-Disposition", f"attachment; filename*=UTF-8''{urllib.parse.quote(stem + '-RGS.' + ext)}")
    h.send_header("Content-Length", str(len(data)))
    h.send_header("Cache-Control", "private, no-store")
    h.end_headers()
    h.wfile.write(data)
