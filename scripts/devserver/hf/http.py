"""Low-level HTTPS GET against Hugging Face."""

import http.client


def open_conn(host: str, path: str, headers: dict[str, str] | None = None):
    conn = http.client.HTTPSConnection(host, timeout=60)
    conn.request("GET", path, headers=headers or {})
    return conn, conn.getresponse()
