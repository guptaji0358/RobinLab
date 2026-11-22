"""Canva OAuth token exchange."""

import base64
import urllib.parse

from .canva_config import CANVA_API
from .canva_http import canva_call


def canva_token(client_id: str, secret: str, params: dict) -> dict:
    basic = base64.b64encode(f"{client_id}:{secret}".encode()).decode()
    status, data = canva_call(
        "POST", f"{CANVA_API}/oauth/token",
        {"Authorization": f"Basic {basic}", "Content-Type": "application/x-www-form-urlencoded"},
        urllib.parse.urlencode(params).encode(),
    )
    if status != 200 or "access_token" not in data:
        raise RuntimeError(data.get("error_description") or data.get("error") or f"Canva token error (HTTP {status})")
    return data
