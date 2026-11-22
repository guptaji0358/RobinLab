"""Base request handler: configuration slots, logging and cache headers."""

import sys
from http.server import SimpleHTTPRequestHandler


class BaseHandler(SimpleHTTPRequestHandler):
    token: str | None = None
    share_secret: str | None = None
    watermark_url: str | None = None  # the Python watermark service (watermark_service/)
    watermark_key: str | None = None
    canva_id: str | None = None
    canva_secret: str | None = None

    def log_message(self, fmt, *args):  # noqa: A003 - stdlib signature
        sys.stderr.write("  %s\n" % (fmt % args))

    def end_headers(self):
        # Static files carry no Cache-Control, so browsers heuristically cache
        # them (Last-Modified based) and keep showing stale JS/CSS while developing.
        # "no-cache" = always revalidate (cheap 304), never serve a stale copy.
        if not any(h.lower().startswith(b"cache-control") for h in getattr(self, "_headers_buffer", [])):
            self.send_header("Cache-Control", "no-cache")
        super().end_headers()
