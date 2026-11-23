"""Markdown front-matter parsing for skill files."""

import re


def parse_front_matter(text: str) -> tuple[dict[str, str], str]:
    match = re.match(r"^---\n([\s\S]*?)\n---\n?", text)
    if not match:
        return {}, text
    meta: dict[str, str] = {}
    for line in match.group(1).split("\n"):
        kv = re.match(r"^([\w-]+):\s*(.*)$", line)
        if kv:
            meta[kv.group(1)] = re.sub(r"^([\"'])([\s\S]*)\1$", r"\2", kv.group(2).strip())
    return meta, text[match.end():]


def strip_markdown(text: str) -> str:
    return re.sub(r"[`*_]", "", text).strip()
