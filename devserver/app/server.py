"""Server start-up: configure the handler and serve forever."""

import os
import sys
from functools import partial
from http.server import ThreadingHTTPServer

from devserver.app.banner import print_serving, print_token_status
from devserver.app.cli import parse_args
from devserver.web.entrypoints import Handler
from devserver.core.paths import PROJECT_ROOT
from devserver.core.settings import load_token, load_var


def configure_handler(directory: str) -> None:
    Handler.directory = os.path.abspath(directory)
    Handler.token = load_token(PROJECT_ROOT)
    # Prefer a dedicated secret so links survive a token rotation; the HF token
    # is a safe local fallback (both stay server-side).
    Handler.share_secret = load_var(PROJECT_ROOT, "SHARE_SECRET") or Handler.token
    Handler.watermark_url = load_var(PROJECT_ROOT, "WATERMARK_URL")
    Handler.watermark_key = load_var(PROJECT_ROOT, "WATERMARK_KEY")
    Handler.canva_id = load_var(PROJECT_ROOT, "CANVA_CLIENT_ID")
    Handler.canva_secret = load_var(PROJECT_ROOT, "CANVA_CLIENT_SECRET")


def main(doc: str | None = None) -> int:
    args = parse_args(doc)
    if not os.path.isdir(args.dir):
        print(f"error: static directory not found: {args.dir}", file=sys.stderr)
        return 1

    configure_handler(args.dir)
    # Pass `directory` explicitly: SimpleHTTPRequestHandler resets it to the CWD
    # when the argument is omitted, which would ignore --dir.
    handler = partial(Handler, directory=Handler.directory)
    print_token_status(bool(Handler.token))

    server = ThreadingHTTPServer((args.host, args.port), handler)
    print_serving(Handler.directory, args.host, args.port)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        server.server_close()
    return 0
