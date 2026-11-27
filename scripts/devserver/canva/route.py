"""/api/canva/*: login, callback, edit."""

import urllib.parse

from devserver.canva.callback import canva_callback
from devserver.canva.edit import canva_edit
from devserver.canva.login import canva_login
from devserver.web.responses import send_json


def serve_canva(h, parsed: urllib.parse.SplitResult) -> None:
    route = parsed.path.rstrip("/")
    if not (h.canva_id and h.canva_secret):
        send_json(h, {"error": "not_configured", "message": "Set CANVA_CLIENT_ID and CANVA_CLIENT_SECRET in scripts/.dev.vars."}, 503)
        return
    redirect_uri = "http://" + (h.headers.get("Host") or "127.0.0.1:5500") + "/api/canva/callback"

    if route.endswith("/login"):
        canva_login(h, redirect_uri)
    elif route.endswith("/callback"):
        canva_callback(h, parsed, redirect_uri)
    elif route.endswith("/edit") and h.command == "POST":
        canva_edit(h)
    else:
        send_json(h, {"error": "not_found"}, 404)
