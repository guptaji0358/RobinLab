"""In-memory Canva sessions keyed by the `rl_canva` cookie."""

import threading
import time

from devserver.canva.config import CANVA_SESSIONS
from devserver.canva.oauth import canva_token

# Canva refresh tokens are single-use: serialise refreshes so two concurrent
# requests don't both spend the same token (mirrors refreshOnce in the Function).
_REFRESH_LOCK = threading.Lock()


def canva_session(h) -> dict | None:
    jar = h.headers.get("Cookie", "")
    sid = next((c.split("=", 1)[1] for c in jar.split("; ") if c.startswith("rl_canva=")), "")
    sess = CANVA_SESSIONS.get(sid)
    if not sess:
        return None
    if time.time() * 1000 >= sess["e"]:
        with _REFRESH_LOCK:
            if time.time() * 1000 < sess["e"]:  # another request refreshed while we waited
                return sess
            if not sess.get("r"):
                return None
            try:
                t = canva_token(h.canva_id, h.canva_secret, {"grant_type": "refresh_token", "refresh_token": sess["r"]})
            except Exception:
                return None
            sess.update(
                a=t["access_token"],
                r=t.get("refresh_token", sess["r"]),
                e=time.time() * 1000 + t.get("expires_in", 3600) * 1000 - 60000,
            )
    return sess
