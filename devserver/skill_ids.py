"""Stable ids for skill files."""

import re


def skill_id(name: str) -> str:
    base = re.sub(r"\.md$", "", name, flags=re.I).lower()
    return re.sub(r"^-|-$", "", re.sub(r"[^a-z0-9]+", "-", base))
