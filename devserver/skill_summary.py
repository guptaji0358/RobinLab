"""Title, description and section outline of one skill."""

import re

from .skill_frontmatter import parse_front_matter, strip_markdown
from .skill_ids import skill_id


def summarise_skill(entry: dict, text: str) -> dict:
    """Title, description and section outline only; full text comes from /skill."""
    meta, body = parse_front_matter(text.replace("\r\n", "\n"))
    title = ""
    sections: list[str] = []
    fenced = False
    for line in body.split("\n"):
        if re.match(r"^\s*(```|~~~)", line):
            fenced = not fenced
        if fenced:
            continue
        h1 = re.match(r"^#\s+(.+)", line)
        if h1 and not title:
            title = strip_markdown(h1.group(1))
        h2 = re.match(r"^##\s+(.+)", line)
        if h2 and len(sections) < 12:
            sections.append(strip_markdown(h2.group(1)))
    fallback = re.sub(r"\.md$", "", entry["name"], flags=re.I)
    return {
        "id": skill_id(entry["name"]),
        "title": title or meta.get("name") or fallback,
        "skillName": meta.get("name") or fallback,
        "description": meta.get("description", ""),
        "sections": sections,
        "size": entry["size"],
        "uploadedAt": entry.get("uploadedAt"),
    }
