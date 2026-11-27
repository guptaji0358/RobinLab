#!/usr/bin/env python3
"""Local preview server for the RobinLab site + the private Hugging Face bucket.

Serves the static site in `scripts/root/` and implements the same JSON API contract as the
Cloudflare Pages Functions (`scripts/functions/`): /api/collection/*, /api/canva/*, /decks/*.
The implementation lives in the `devserver/` package, one concern per module.

Usage:
    python scripts/dev_server.py                # http://localhost:5500
    python scripts/dev_server.py --port 8080
    python scripts/dev_server.py --dir scripts/root

The Hugging Face token is read from the HF_TOKEN environment variable, or from a
git-ignored `.dev.vars` file (lines of the form KEY=VALUE). Nothing is hard-coded.
"""

import os
import sys

# Keep bytecode in <repo>/out/ instead of __pycache__ folders beside the sources.
sys.pycache_prefix = sys.pycache_prefix or os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "out", "__pycache__"
)

from devserver.app.server import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main(__doc__))
