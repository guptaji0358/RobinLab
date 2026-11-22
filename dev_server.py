#!/usr/bin/env python3
"""Local preview server for the RobinLab site + the private Hugging Face bucket.

Serves the static site in `scripts/root/` and implements the same JSON API contract as the
Cloudflare Pages Functions (`scripts/functions/`): /api/collection/*, /api/canva/*, /decks/*.
The implementation lives in the `devserver/` package, one concern per module.

Usage:
    python dev_server.py                # http://localhost:5500
    python dev_server.py --port 8080
    python dev_server.py --dir root

The Hugging Face token is read from the HF_TOKEN environment variable, or from a
git-ignored `.dev.vars` file (lines of the form KEY=VALUE). Nothing is hard-coded.
"""

from devserver.server import main

if __name__ == "__main__":
    raise SystemExit(main(__doc__))
