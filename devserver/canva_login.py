"""GET /api/canva/login: start the OAuth (PKCE) flow."""

import hashlib
import os
import time
import urllib.parse

from .b64 import b64url
from .canva_config import CANVA_AUTH, CANVA_PENDING, CANVA_SCOPES
from .responses import redirect


def canva_login(h, redirect_uri: str) -> None:
    verifier = b64url(os.urandom(48))
    state = b64url(os.urandom(16))
    CANVA_PENDING[state] = {"v": verifier, "t": time.time()}
    challenge = b64url(hashlib.sha256(verifier.encode()).digest())
    qs = urllib.parse.urlencode({
        "code_challenge": challenge, "code_challenge_method": "s256", "scope": CANVA_SCOPES,
        "response_type": "code", "client_id": h.canva_id, "state": state, "redirect_uri": redirect_uri,
    })
    redirect(h, f"{CANVA_AUTH}?{qs}")
