"""LIAS Incremental Project Knowledge Indexer.

Indexes key project facts, architecture decisions, and conventions from
CLAUDE.md and memory files into the SQLite FTS5 knowledge store.
"""

from __future__ import annotations
import re
from pathlib import Path
from typing import Dict, List, Tuple

from lias.knowledge.store import KnowledgeStore


FOUNDATIONAL_FACTS: List[Tuple[str, str, str]] = [
    (
        "architecture",
        "RobinLabs is a static site and project portfolio. There is no framework, bundler, or build step. Cloudflare Pages publishes only the root/ directory.",
        "CLAUDE.md:Layout"
    ),
    (
        "rule",
        "Projects live in root/projects/<name>/. There is no second copy or top-level sync directory.",
        "CLAUDE.md:The one rule"
    ),
    (
        "routing",
        "Four main site routes served from root/: / (index.html), /collection (collection.html), /presentations (presentations.html), /skills (skills.html).",
        "CLAUDE.md:Pages"
    ),
    (
        "deploy",
        "Deployment to Cloudflare Pages uses: npx wrangler pages deploy root --project-name=robinlab --branch=master. GitHub push alone does not trigger deploy.",
        "CLAUDE.md:Deploy"
    ),
    (
        "backend",
        "Cloudflare Pages Function at functions/api/collection/* acts as proxy to HuggingFace dataset bucket. dev_server.py provides local emulation.",
        "CLAUDE.md:dev_server.py"
    ),
    (
        "tooling",
        "tools/make_icons.py regenerates site favicons and icons from root/assets/robinlab-logo.png. tools/make_thumbs.py generates collection thumbnails.",
        "CLAUDE.md:Site icons"
    ),
]


class ProjectIndexer:
    def __init__(self, store: KnowledgeStore, project_root: Path):
        self.store = store
        self.project_root = project_root

    def index_foundational(self) -> int:
        """Seed verified foundational facts into knowledge store."""
        count = 0
        for cat, content, prov in FOUNDATIONAL_FACTS:
            self.store.add(
                category=cat,
                content=content,
                provenance=prov,
                confidence=1.0,
                verified=True,
            )
            count += 1
        return count

    def index_markdown_file(self, md_path: Path, category: str = "doc") -> int:
        """Parse markdown headers and paragraphs into structured knowledge chunks."""
        if not md_path.exists():
            return 0

        with open(md_path, "r", encoding="utf-8", errors="ignore") as f:
            text = f.read()

        # Split by markdown headers
        sections = re.split(r"\n(?=#{1,3}\s+)", text)
        indexed = 0
        for sec in sections:
            sec = sec.strip()
            if not sec or len(sec) < 30:
                continue
            lines = sec.splitlines()
            title = lines[0].lstrip("#").strip()
            body = "\n".join(lines[1:]).strip()
            if not body:
                continue

            content = f"[{title}] {body}"
            # Keep chunk reasonable
            if len(content) > 1200:
                content = content[:1200] + "..."

            self.store.add(
                category=category,
                content=content,
                provenance=f"{md_path.name}:{title}",
                confidence=0.9,
                verified=True,
            )
            indexed += 1
        return indexed
