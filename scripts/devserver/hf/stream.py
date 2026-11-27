"""Open a bucket file for streaming."""

import urllib.parse

from devserver.core.config import BUCKET_ID, HF_HOST
from devserver.hf.http import open_conn


def open_file_stream(token: str, path: str, extra: dict[str, str] | None = None):
    """Return (connection, response) for a bucket file."""
    encoded = urllib.parse.quote(path, safe="")
    conn, resp = open_conn(
        HF_HOST,
        f"/buckets/{BUCKET_ID}/resolve/{encoded}",
        {"Authorization": f"Bearer {token}", "Accept": "*/*", **(extra or {})},
    )

    # Private bucket -> 302 to a short-lived signed URL. Follow without the token.
    if resp.status in (301, 302, 303, 307, 308):
        location = resp.getheader("Location")
        conn.close()
        if not location:
            raise RuntimeError("Resolve returned a redirect with no target")
        parsed = urllib.parse.urlsplit(location)
        conn, resp = open_conn(parsed.netloc, urllib.parse.urlunsplit(("", "", parsed.path, parsed.query, "")), dict(extra or {}))

    return conn, resp
