"""Command-line arguments."""

import argparse

from devserver.core.paths import DEFAULT_STATIC_DIR


def parse_args(doc: str | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=doc, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=5500)
    parser.add_argument("--dir", default=DEFAULT_STATIC_DIR)
    return parser.parse_args()
