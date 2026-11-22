"""Dispatch /decks, /api/canva and /api/collection routes. Returns True when handled."""

import urllib.parse

from .backdrop_route import serve_backdrop
from .canva_route import serve_canva
from .decks_route import serve_deck
from .download_route import serve_download
from .file_route import serve_file
from .listing_route import serve_listing
from .responses import not_configured, send_json
from .share_route import serve_share
from .skill_routes import serve_skill, serve_skills_list


def handle_api(h, parsed: urllib.parse.SplitResult) -> bool:
    route = parsed.path.rstrip("/") or "/"

    if route.startswith("/decks/"):
        serve_deck(h, parsed)
        return True

    if route.startswith("/api/canva"):
        if h.token is None:
            not_configured(h)
        else:
            serve_canva(h, parsed)
        return True

    if not route.startswith("/api/collection"):
        return False

    if h.token is None:
        not_configured(h)
        return True

    # Share links are the only writable endpoint: minting needs POST, resolving needs GET.
    if route.endswith("/share"):
        serve_share(h, parsed)
        return True

    if h.command not in ("GET", "HEAD"):
        send_json(h, {"error": "method_not_allowed"}, 405)
        return True

    if route.endswith("/download"):
        serve_download(h, parsed)
    elif route.endswith("/backdrop"):
        serve_backdrop(h, parsed)
    elif route.endswith("/skills"):
        serve_skills_list(h)
    elif route.endswith("/skill"):
        serve_skill(h, parsed)
    elif route.endswith("/file"):
        serve_file(h, (urllib.parse.parse_qs(parsed.query).get("path") or [""])[0])
    else:
        serve_listing(h)
    return True
