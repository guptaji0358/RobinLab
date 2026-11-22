"""Response helpers shared by every route. `h` is the request handler."""

import json


def send_json(h, body: dict, status: int = 200, cache: str = "no-store") -> None:
    payload = json.dumps(body, ensure_ascii=False).encode("utf-8")
    h.send_response(status)
    h.send_header("Content-Type", "application/json; charset=utf-8")
    h.send_header("Content-Length", str(len(payload)))
    h.send_header("Cache-Control", cache)
    h.end_headers()
    if h.command != "HEAD":
        h.wfile.write(payload)


def not_configured(h) -> None:
    send_json(
        h,
        {
            "error": "not_configured",
            "message": "No HF_TOKEN found. Set the HF_TOKEN environment variable or create a .dev.vars file.",
        },
        500,
    )


def redirect(h, location: str, cookies: list[str] | None = None) -> None:
    h.send_response(302)
    h.send_header("Location", location)
    h.send_header("Cache-Control", "no-store")
    for c in cookies or []:
        h.send_header("Set-Cookie", c)
    h.end_headers()
