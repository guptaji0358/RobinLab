"""/decks/<name>.pptx: public deck URL for the Office Web Viewer (mirror of functions/decks)."""

import urllib.parse

from .file_route import serve_file
from .responses import not_configured


def serve_deck(h, parsed: urllib.parse.SplitResult) -> None:
    if h.token is None:
        not_configured(h)
        return
    name = urllib.parse.unquote(parsed.path[len("/decks/"):])
    serve_file(h, "presentations/" + name, decks_only=True)
