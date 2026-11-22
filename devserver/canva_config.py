"""Edit in Canva (mirrors scripts/functions/api/canva/[[path]].js). Dev only: sessions live in memory."""

CANVA_AUTH = "https://www.canva.com/api/oauth/authorize"
CANVA_API = "https://api.canva.com/rest/v1"
CANVA_SCOPES = "asset:write design:content:write"
CANVA_SESSIONS: dict[str, dict] = {}   # cookie id -> {a, r, e}
CANVA_PENDING: dict[str, dict] = {}    # oauth state -> {v, t}
