"""GET /api/canva/callback: finish the OAuth flow and set the session cookie."""

import os
import time
import urllib.parse

from .b64 import b64url
from .canva_config import CANVA_PENDING, CANVA_SESSIONS
from .canva_oauth import canva_token
from .responses import redirect


def canva_callback(h, parsed: urllib.parse.SplitResult, redirect_uri: str) -> None:
    q = urllib.parse.parse_qs(parsed.query)
    pending = CANVA_PENDING.pop((q.get("state") or [""])[0], None)
    code = (q.get("code") or [""])[0]
    if not pending or not code or time.time() - pending["t"] > 600:
        redirect(h, "/logos?canva=denied")
        return
    try:
        t = canva_token(h.canva_id, h.canva_secret, {
            "grant_type": "authorization_code", "code": code,
            "code_verifier": pending["v"], "redirect_uri": redirect_uri,
        })
    except Exception:
        redirect(h, "/logos?canva=error")
        return
    sid = b64url(os.urandom(24))
    CANVA_SESSIONS[sid] = {
        "a": t["access_token"], "r": t.get("refresh_token", ""),
        "e": time.time() * 1000 + t.get("expires_in", 3600) * 1000 - 60000,
    }
    redirect(h, "/logos?canva=connected", [f"rl_canva={sid}; Path=/api/canva; HttpOnly; SameSite=Lax; Max-Age=2592000"])
