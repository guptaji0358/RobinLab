"""Time formatting."""

import time


def iso_ms(ms: int) -> str:
    """Milliseconds since epoch -> `2026-10-21T12:00:00Z` (what JS Date parses)."""
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(ms / 1000))
