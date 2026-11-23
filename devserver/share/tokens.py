"""Signed share tokens (mirrors the Cloudflare Function exactly)."""

import hashlib
import hmac
import json
import time

from devserver.core.b64 import b64url, b64url_decode


def create_share_token(secret: str, path: str, ttl_ms: int) -> str:
    """Token = base64url(payload) "." base64url(HMAC-SHA256(payload))."""
    payload = json.dumps({"p": path, "e": int(time.time() * 1000) + ttl_ms}, separators=(",", ":")).encode("utf-8")
    signature = hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).digest()
    return f"{b64url(payload)}.{b64url(signature)}"


def read_share_token(secret: str, token: str) -> dict:
    """Returns {"path", "expiresAt"} or {"error": "share_invalid"|"share_expired"}."""
    payload_part, _, signature_part = token.partition(".")
    if not payload_part or not signature_part:
        return {"error": "share_invalid"}

    try:
        payload_bytes = b64url_decode(payload_part)
        signature = b64url_decode(signature_part)
    except (ValueError, TypeError):
        return {"error": "share_invalid"}

    expected = hmac.new(secret.encode("utf-8"), payload_bytes, hashlib.sha256).digest()
    if not hmac.compare_digest(expected, signature):
        return {"error": "share_invalid"}

    try:
        payload = json.loads(payload_bytes.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        return {"error": "share_invalid"}

    if not isinstance(payload, dict) or not isinstance(payload.get("p"), str) or not isinstance(payload.get("e"), int):
        return {"error": "share_invalid"}
    if int(time.time() * 1000) >= payload["e"]:
        return {"error": "share_expired", "expiresAt": payload["e"], "path": payload["p"]}
    return {"path": payload["p"], "expiresAt": payload["e"]}
